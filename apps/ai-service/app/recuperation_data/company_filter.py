import asyncio
import json
import logging
import re
import unicodedata

import httpx

from app.core.model_config import get_models
from app.models.schemas import Company
from app.utils.ai_caller import call_ai, call_ai_with_search

logger = logging.getLogger(__name__)

# Taille des batches
_FILTER_BATCH_SIZE = 5    # Pass 1 : filtre binaire avec web search (5 entreprises / appel)
_SCORE_BATCH_SIZE  = 10   # Pass 2 : scoring         (10 entreprises / appel)

# Max appels Perplexity simultanés pour la Pass 2
_SCORE_SEMAPHORE = asyncio.Semaphore(3)

# Vérification URL
_URL_TIMEOUT   = 8.0
_URL_SEMAPHORE = asyncio.Semaphore(15)


# ── Normalisation pour déduplication ─────────────────────────────────────────

_LEGAL_FORMS = re.compile(
    r"\b(sarl|sas|sasu|sa|snc|sci|eurl|gie|eirl|ei|se|selarl|selas|sca|scop|scp|sel)\b",
    re.IGNORECASE,
)


def _normalize_name(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode()
    lower = ascii_name.lower()
    no_legal = _LEGAL_FORMS.sub("", lower)
    clean = re.sub(r"[^\w\s]", "", no_legal)
    return re.sub(r"\s+", " ", clean).strip()


def _extract_postal_code(adresse: str | None) -> str:
    if not adresse:
        return ""
    match = re.search(r"\b(\d{5})\b", adresse)
    return match.group(1) if match else ""


def dedup_companies(companies: list[Company]) -> list[Company]:
    """Dédup par nom normalisé + code postal."""
    seen: dict[str, Company] = {}
    for c in companies:
        norm = _normalize_name(c.nom)
        postal = _extract_postal_code(c.adresse)
        key = f"{norm}|{postal}" if postal else norm
        if key not in seen:
            seen[key] = c
    return list(seen.values())


# ── Vérification URL ─────────────────────────────────────────────────────────

async def _is_url_alive(url: str) -> bool:
    """Retourne False si l'URL est morte (erreur, timeout, 4xx/5xx)."""
    if not url:
        return True
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    async with _URL_SEMAPHORE:
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=_URL_TIMEOUT,
                verify=False,
            ) as client:
                response = await client.head(url, headers={"User-Agent": "Mozilla/5.0"})
                if response.status_code >= 400:
                    response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                return response.status_code < 400
        except Exception:
            return False


async def _url_filter(companies: list[Company]) -> list[Company]:
    """Supprime les entreprises dont le site web est mort (erreur HTTP ou inaccessible)."""
    companies_with_url = [(i, c) for i, c in enumerate(companies) if c.site_web]
    if not companies_with_url:
        return companies

    results = await asyncio.gather(*[_is_url_alive(c.site_web) for _, c in companies_with_url])

    dead_indices = {companies_with_url[i][0] for i, alive in enumerate(results) if not alive}
    if dead_indices:
        logger.info(f"[URL] URLs mortes : {[companies[i].nom for i in sorted(dead_indices)]}")

    kept = [c for i, c in enumerate(companies) if i not in dead_indices]
    logger.info(f"[URL] {len(dead_indices)} exclues (site mort), {len(kept)} gardées")
    return kept


# ── Pass 1 : filtre binaire par batch (avec web search) ──────────────────────

_P1_SYSTEM = (
    "Tu es un classificateur d'entreprises. "
    "Effectue une recherche web pour chaque entreprise avant de te prononcer. "
    "Réponds UNIQUEMENT avec un tableau JSON d'indices entiers, sans texte autour."
)

_P1_PROMPT = """\
Pour chacune des entreprises ci-dessous, fais une recherche web pour vérifier \
sa nature réelle, puis retourne un tableau JSON des indices (base 0) de celles \
qui correspondent à au moins une de ces catégories :

- École, lycée, collège, université, centre de formation, organisme de formation (OPCO, CFA…)
- Administration publique, mairie, préfecture, ministère, collectivité territoriale, service public
- Association à but non lucratif, ONG, fondation, association caritative ou culturelle (loi 1901)
- Agence d'intérim ou entreprise de travail temporaire
- Cabinet de recrutement, chasseur de têtes, agence RH, société de portage salarial
- Syndicat, ordre professionnel, chambre de commerce, chambre des métiers
- Hôpital public, CHU, EHPAD public, clinique publique
- Secte, mouvement sectaire, organisation religieuse

En cas de doute, préfère exclure l'entreprise (sois strict).

Entreprises :
{companies_list}

Réponds UNIQUEMENT avec un tableau JSON, ex: [0, 3, 5] ou [] si aucune.
"""


def _build_company_line(i: int, c: Company) -> str:
    parts = [f"{i}. {c.nom}"]
    if c.type_activite:
        parts.append(f"(activité: {c.type_activite})")
    if c.adresse:
        parts.append(f"— {c.adresse}")
    return " ".join(parts)


async def _p1_batch(companies: list[Company], model: str) -> list[int]:
    """Retourne les indices locaux à exclure dans ce batch (avec web search Perplexity)."""
    lines = [_build_company_line(i, c) for i, c in enumerate(companies)]
    prompt = _P1_PROMPT.format(companies_list="\n".join(lines))

    try:
        raw = await call_ai_with_search(model=model, prompt=prompt, system_prompt=_P1_SYSTEM)
        match = re.search(r"\[.*?\]", raw.strip(), re.DOTALL)
        if not match:
            logger.warning(f"[P1] Réponse inattendue : '{raw[:100]}' — aucune exclusion")
            return []
        indices = json.loads(match.group(0))
        valid = [i for i in indices if isinstance(i, int) and 0 <= i < len(companies)]
        if valid:
            logger.info(f"[P1] Exclues : {[companies[i].nom for i in valid]}")
        return valid
    except Exception as e:
        logger.error(f"[P1] Erreur batch : {e} — aucune exclusion par sécurité")
        return []


async def _hard_filter(companies: list[Company], model: str) -> list[Company]:
    """
    Pass 1 — filtre binaire séquentiel par batch de {_FILTER_BATCH_SIZE} avec web search Perplexity.
    Batches traités un par un pour ne pas bombarder le rate limit Perplexity.
    Le rate limiter global de ai_caller (1.5s entre appels) gère l'espacement.
    """
    if not companies:
        return []

    batches = [companies[i: i + _FILTER_BATCH_SIZE] for i in range(0, len(companies), _FILTER_BATCH_SIZE)]
    logger.info(f"[P1] {len(companies)} entreprises → {len(batches)} batch(s) de {_FILTER_BATCH_SIZE} (séquentiel, web search)")

    excluded: set[int] = set()
    for batch_idx, batch in enumerate(batches):
        local_indices = await _p1_batch(batch, model)
        offset = batch_idx * _FILTER_BATCH_SIZE
        for li in local_indices:
            excluded.add(offset + li)

    kept = [c for idx, c in enumerate(companies) if idx not in excluded]
    logger.info(f"[P1] {len(excluded)} exclues, {len(kept)} gardées")
    return kept


# ── Pass 2 : scoring par batch (avec web search) ─────────────────────────────

_P2_SYSTEM = (
    "Tu es un expert en candidatures spontanées et en analyse d'entreprises en France. "
    "Utilise la recherche web pour vérifier l'activité réelle de chaque entreprise. "
    "Réponds UNIQUEMENT avec un tableau JSON de scores entiers (0-100), sans texte autour."
)

_P2_PROMPT = """\
## Candidat
Poste visé : {secteur}
{sectors_context}{user_instructions}
## Mission
Pour chacune des {n} entreprises suivantes, fais une recherche web et évalue \
si elle est une bonne cible pour une candidature spontanée au poste de "{secteur}".

## Barème
- 0 à 29  : À exclure — activité sans rapport avec le poste, aucun recrutement probable
- 30 à 59 : Pertinence partielle — secteur adjacent, activité mixte, doute sur les profils
- 60 à 100 : Excellente cible — secteur aligné, recrute probablement des profils similaires

## Entreprises à évaluer
{companies_list}

Réponds UNIQUEMENT avec un tableau JSON de {n} scores dans l'ordre, ex: [75, 45, 80]
"""


async def _p2_batch(
    companies: list[Company],
    secteur: str,
    sectors_context: str,
    user_instructions_section: str,
    model: str,
) -> list[int]:
    """Score un batch de companies, retourne une liste de scores dans le même ordre."""
    n = len(companies)
    lines = []
    for i, c in enumerate(companies):
        parts = [f"{i}. {c.nom}"]
        if c.site_web:
            parts.append(f"(site: {c.site_web})")
        if c.type_activite:
            parts.append(f"(activité: {c.type_activite})")
        if c.adresse:
            parts.append(f"— {c.adresse}")
        lines.append(" ".join(parts))

    prompt = _P2_PROMPT.format(
        secteur=secteur,
        sectors_context=sectors_context,
        user_instructions=user_instructions_section,
        n=n,
        companies_list="\n".join(lines),
    )

    fallback = [50] * n

    async with _SCORE_SEMAPHORE:
        try:
            raw = await call_ai_with_search(model=model, prompt=prompt, system_prompt=_P2_SYSTEM)
        except Exception as e:
            logger.error(f"[P2] Erreur batch : {e} — scores=50 par défaut")
            return fallback

    raw = raw.strip()
    match = re.search(r"\[.*?\]", raw, re.DOTALL)
    if not match:
        logger.warning(f"[P2] Réponse inattendue : '{raw[:120]}' — scores=50")
        return fallback

    try:
        scores_raw = json.loads(match.group(0))
    except json.JSONDecodeError:
        logger.warning(f"[P2] JSON invalide : '{raw[:120]}' — scores=50")
        return fallback

    # Valider et compléter si l'IA a renvoyé moins de scores que prévu
    scores = []
    for i in range(n):
        try:
            s = int(scores_raw[i])
            scores.append(max(0, min(100, s)))
        except (IndexError, TypeError, ValueError):
            scores.append(50)

    names_scores = [(companies[i].nom, scores[i]) for i in range(n)]
    logger.info(f"[P2] Scores : {names_scores}")
    return scores


# ── Point d'entrée ────────────────────────────────────────────────────────────

async def rank_companies(
    companies: list[Company],
    secteur: str,
    sectors: list[str] | None = None,
    categories: list[str] | None = None,
    user_instructions: str | None = None,
) -> list[Company]:
    """
    Pass 1 : filtre binaire par batch de 20 (Perplexity, sans web search exploité).
             Élimine : écoles, admin, asso, intérim, cabinets recrutement.
    Pass 2 : scoring par batch de 10 (Perplexity + web search, semaphore=3).
             Trie le reste, exclut score < 30.
    Retourne la liste triée par score décroissant.
    """
    if not companies:
        return []

    models = await get_models()

    # ── URL check ─────────────────────────────────────────────────────────────
    after_url = await _url_filter(companies)
    if not after_url:
        return []

    # ── Pass 1 ───────────────────────────────────────────────────────────────
    after_filter = await _hard_filter(after_url, model=models.MODEL_FILTER)
    if not after_filter:
        return []

    # ── Pass 2 ───────────────────────────────────────────────────────────────
    sectors_context = ""
    if categories:
        sectors_context += f"Domaines ciblés : {', '.join(categories)}\n"
    if sectors:
        sectors_context += f"Sous-secteurs ciblés : {', '.join(sectors)}\n"

    user_instructions_section = (
        f"## Instructions du candidat (à respecter absolument)\n{user_instructions}\n\n"
        if user_instructions else ""
    )

    batches = [
        after_filter[i: i + _SCORE_BATCH_SIZE]
        for i in range(0, len(after_filter), _SCORE_BATCH_SIZE)
    ]
    logger.info(
        f"[P2] Scoring de {len(after_filter)} entreprises "
        f"→ {len(batches)} batch(s) de {_SCORE_BATCH_SIZE} avec {models.MODEL_RANKING} (semaphore=3)"
    )

    batch_results = await asyncio.gather(*[
        _p2_batch(b, secteur, sectors_context, user_instructions_section, models.MODEL_RANKING)
        for b in batches
    ])

    # Aplatir les résultats et affecter les scores
    all_scores = [score for batch_scores in batch_results for score in batch_scores]
    for company, score in zip(after_filter, all_scores):
        company.score = score

    kept = [c for c in after_filter if (c.score or 0) >= 30]
    kept.sort(key=lambda c: c.score or 0, reverse=True)

    removed = len(after_filter) - len(kept)
    logger.info(f"[P2] {removed} éliminées (score < 30), {len(kept)} gardées")
    return kept
