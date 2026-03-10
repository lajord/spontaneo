import asyncio
import json
import logging
import re

from app.models.schemas import Company
from app.utils.ai_caller import call_ai

logger = logging.getLogger(__name__)

_MODEL = "gemini-3.1-pro-preview"
_BATCH_SIZE = 500  # 2 appels pour 1 000 entreprises

_FILTER_SYSTEM_PROMPT = (
    "Tu es un expert en recrutement et en stratégie de candidature spontanée.\n\n"
    "On te donne une liste d'entreprises trouvées par mots-clés sectoriels.\n"
    "Ton rôle : identifier celles où une candidature spontanée a du sens pour le poste indiqué.\n\n"
    "GARDER :\n"
    "✓ Entreprises du bon secteur avec des salariés\n"
    "✓ Structures où ce poste est plausible\n"
    "✓ PME, grands groupes, filiales opérationnelles\n\n"
    "SUPPRIMER :\n"
    "✗ Administrations, mairies, préfectures, services publics\n"
    "✗ Associations sans salarié, fondations\n"
    "✗ Holdings pures sans activité opérationnelle\n"
    "✗ Établissements scolaires, hôpitaux si hors secteur\n"
    "✗ Agences d'intérim, cabinets de recrutement\n"
    "✗ Entreprises manifestement hors secteur\n\n"
    "Réponds UNIQUEMENT avec un JSON valide, sans texte ni markdown :\n"
    '{"indices_a_garder": [0, 2, 4]}'
)


def _build_prompt(companies: list[Company], job_title: str, user_prompt: str | None) -> str:
    lines = [f"Poste recherché : {job_title}"]
    if user_prompt:
        lines.append(f"Contexte : {user_prompt}")
    lines.append("\nEntreprises à évaluer :")
    for i, c in enumerate(companies):
        parts = [f"[{i}] {c.nom}"]
        if c.adresse:
            parts.append(f"adresse={c.adresse}")
        if c.site_web:
            parts.append(f"site={c.site_web}")
        lines.append(" | ".join(parts))
    lines.append("\nRetourne les indices des entreprises à GARDER.")
    return "\n".join(lines)


def _parse_response(raw: str, count: int) -> list[int] | None:
    def _extract(data) -> list[int] | None:
        if isinstance(data, dict):
            indices = data.get("indices_a_garder")
            if isinstance(indices, list):
                return [i for i in indices if isinstance(i, int) and 0 <= i < count]
        return None

    for attempt in [
        lambda: json.loads(raw),
        lambda: json.loads(re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL).group(1)),
        lambda: json.loads(re.search(r"\{.*\}", raw, re.DOTALL).group(0)),
    ]:
        try:
            result = _extract(attempt())
            if result is not None:
                return result
        except Exception:
            continue
    return None


async def _filter_batch(
    batch: list[Company],
    batch_idx: int,
    job_title: str,
    user_prompt: str | None,
) -> list[Company]:
    """Filtre un batch via un appel IA. Retourne le batch complet en cas d'échec."""
    prompt = _build_prompt(batch, job_title, user_prompt)
    try:
        raw = await call_ai(
            model=_MODEL,
            prompt=prompt,
            system_prompt=_FILTER_SYSTEM_PROMPT,
            temperature=0.1,
        )
        indices = _parse_response(raw, len(batch))
    except Exception as e:
        logger.error(f"[FILTER] Batch {batch_idx} — erreur IA : {e} → fallback sans filtre")
        return batch

    if indices is None:
        logger.warning(f"[FILTER] Batch {batch_idx} — parsing JSON impossible → fallback sans filtre")
        return batch

    kept = [batch[i] for i in indices]
    logger.info(
        f"[FILTER] Batch {batch_idx} : {len(batch)} → {len(kept)} gardées "
        f"({len(batch) - len(kept)} supprimées)"
    )
    return kept


async def filter_keyword_companies(
    companies: list[Company],
    job_title: str,
    user_prompt: str | None = None,
) -> list[Company]:
    """
    Filtre les entreprises apollo_keyword via IA (gemini-3.1-pro-preview).
    Les entreprises apollo_jobtitle ne sont pas touchées.
    Traite les apollo_keyword par batches de _BATCH_SIZE pour éviter les dépassements de contexte.
    Fallback : retourne toutes les entreprises si l'IA échoue.
    """
    jobtitle_companies = [c for c in companies if c.source != "apollo_keyword"]
    keyword_companies = [c for c in companies if c.source == "apollo_keyword"]

    if not keyword_companies:
        logger.info("[FILTER] Aucune entreprise apollo_keyword à filtrer.")
        return companies

    # Découpage en batches
    batches = [
        keyword_companies[i: i + _BATCH_SIZE]
        for i in range(0, len(keyword_companies), _BATCH_SIZE)
    ]
    logger.info(
        f"[FILTER] {len(keyword_companies)} entreprises apollo_keyword → "
        f"{len(batches)} batch(es) de max {_BATCH_SIZE}"
    )

    # Appels séquentiels (évite les rate limits Gemini)
    filtered: list[Company] = []
    for idx, batch in enumerate(batches):
        result = await _filter_batch(batch, idx, job_title, user_prompt)
        filtered.extend(result)

    logger.info(
        f"[FILTER] Total apollo_keyword : {len(keyword_companies)} → {len(filtered)} gardées"
    )

    return jobtitle_companies + filtered
