import asyncio
import logging
import re
import unicodedata

from app.core.model_config import get_models
from app.models.schemas import Company
from app.utils.ai_caller import call_ai_with_search

logger = logging.getLogger(__name__)

# Sémaphore : 15 appels IA en parallèle (sonar-pro supporte ce débit)
_FILTER_SEMAPHORE = asyncio.Semaphore(15)

# ── Normalisation pour déduplication ─────────────────────────────────────────

_LEGAL_FORMS = re.compile(
    r"\b(sarl|sas|sasu|sa|snc|sci|eurl|gie|eirl|ei|se|selarl|selas|sca|scop|scp|sel)\b",
    re.IGNORECASE,
)


def _normalize_name(name: str) -> str:
    """Supprime accents, formes juridiques et ponctuation pour la comparaison."""
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
    """Dédup par nom normalisé + code postal (si disponible)."""
    seen: dict[str, Company] = {}
    for c in companies:
        norm = _normalize_name(c.nom)
        postal = _extract_postal_code(c.adresse)
        key = f"{norm}|{postal}" if postal else norm
        if key not in seen:
            seen[key] = c
    return list(seen.values())


# ── Scoring per-company avec web search ───────────────────────────────────────

_SCORE_SYSTEM = (
    "Tu es un expert en candidatures spontanées et en analyse d'entreprises en France.\n"
    "Tu dois évaluer si une entreprise est une cible pertinente pour un candidat en recherche d'emploi.\n"
    "Tu as accès à la recherche web — utilise-la pour vérifier l'activité réelle de l'entreprise.\n"
    "Réponds UNIQUEMENT avec un entier entre 0 et 100, sans texte autour."
)

_SCORE_PROMPT = (
    "## Candidat en recherche d'emploi\n"
    "Poste visé : {secteur}\n"
    "{sectors_context}"
    "{user_instructions}"
    "## Entreprise à évaluer\n"
    "Nom : {nom}\n"
    "{site_line}"
    "{type_line}"
    "{adresse_line}"
    "\n## Mission\n"
    "Recherche des informations sur cette entreprise (activité réelle, secteur, profils recrutés).\n"
    "Évalue si elle représente une bonne cible pour une candidature spontanée "
    "au poste de \"{secteur}\".\n\n"
    "## Barème\n"
    "- 0 à 49 : À exclure\n"
    "  • Mauvais secteur d'activité\n"
    "  • Administration publique, école, université, association caritative\n"
    "  • Agence d'intérim ou cabinet de recrutement\n"
    "  • Entreprise sans lien avec le métier du candidat\n"
    "  • Explicitement interdit par les instructions du candidat\n"
    "- 50 à 69 : Pertinence partielle\n"
    "  • Secteur adjacent ou activité mixte\n"
    "  • Doute sur le type de profils recrutés\n"
    "  • Activité de l'entreprise pas totalement claire\n"
    "- 70 à 100 : Excellente cible\n"
    "  • Secteur aligné avec le poste recherché\n"
    "  • Entreprise qui recrute probablement des profils similaires\n"
    "  • Cohérence forte entre l'activité de l'entreprise et le métier du candidat\n\n"
    "Réponds UNIQUEMENT avec un entier entre 0 et 100."
)


async def _score_one(
    company: Company,
    secteur: str,
    sectors_context: str,
    user_instructions_section: str,
    model: str,
) -> int:
    """Score une entreprise (0-100) via IA avec web search."""
    site_line = f"Site web : {company.site_web}\n" if company.site_web else ""
    type_line = f"Type d'activité : {company.type_activite}\n" if company.type_activite else ""
    adresse_line = f"Adresse : {company.adresse}\n" if company.adresse else ""

    prompt = _SCORE_PROMPT.format(
        secteur=secteur,
        sectors_context=sectors_context,
        user_instructions=user_instructions_section,
        nom=company.nom,
        site_line=site_line,
        type_line=type_line,
        adresse_line=adresse_line,
    )

    async with _FILTER_SEMAPHORE:
        try:
            raw = await call_ai_with_search(
                model=model,
                prompt=prompt,
                system_prompt=_SCORE_SYSTEM,
            )
        except Exception as e:
            logger.error(f"[RANKING] Erreur scoring '{company.nom}': {e} — score=50 par défaut")
            return 50

    raw = raw.strip()
    match = re.search(r"\b(\d{1,3})\b", raw)
    if not match:
        logger.warning(f"[RANKING] Réponse inattendue pour '{company.nom}': '{raw[:80]}' — score=50")
        return 50

    score = int(match.group(1))
    score = max(0, min(100, score))
    logger.info(f"[RANKING] '{company.nom}' → {score}")
    return score


async def rank_companies(
    companies: list[Company],
    secteur: str,
    sectors: list[str] | None = None,
    categories: list[str] | None = None,
    user_instructions: str | None = None,
) -> list[Company]:
    """
    Score toutes les entreprises en parallèle (web search).
    Retourne la liste triée par score décroissant, sans les entreprises < 50.
    Chaque company.score est mis à jour en place.
    """
    if not companies:
        return []

    sectors_parts = []
    if categories:
        sectors_parts.append(f"Domaines ciblés : {', '.join(categories)}\n")
    if sectors:
        sectors_parts.append(f"Sous-secteurs ciblés : {', '.join(sectors)}\n")
    sectors_context = "".join(sectors_parts) if sectors_parts else ""

    user_instructions_section = (
        f"## Instructions du candidat (à respecter absolument)\n{user_instructions}\n\n"
        if user_instructions else ""
    )

    models = await get_models()
    model = models.MODEL_FILTER

    logger.info(
        f"[RANKING] Scoring de {len(companies)} entreprises "
        f"avec {model} ({_FILTER_SEMAPHORE._value} slots parallèles)"
    )

    scores = await asyncio.gather(*[
        _score_one(c, secteur, sectors_context, user_instructions_section, model)
        for c in companies
    ])

    for company, score in zip(companies, scores):
        company.score = score

    kept = [c for c in companies if c.score >= 50]
    kept.sort(key=lambda c: c.score, reverse=True)  # type: ignore[arg-type]

    removed = len(companies) - len(kept)
    logger.info(f"[RANKING] {removed} éliminées (score < 50), {len(kept)} gardées")
    return kept
