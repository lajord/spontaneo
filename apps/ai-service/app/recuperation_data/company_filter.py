import asyncio
import json
import logging
import re

from app.core.model_config import get_models
from app.models.schemas import Company
from app.utils.ai_caller import call_ai

logger = logging.getLogger(__name__)

_BATCH_SIZE = 50  # Max entreprises par appel IA (évite les réponses tronquées)

_SYSTEM_PROMPT = (
    "Tu reçois une liste d'entreprises trouvées pour un candidat.\n"
    "Pour chaque entreprise, dis si elle est cohérente avec la recherche du candidat.\n"
    "Base-toi sur le nom de l'entreprise et son activité probable.\n"
    "Si le candidat a exprimé des critères ou des exclusions spécifiques, tu DOIS les respecter à la lettre et en priorité absolue.\n\n"
    "Réponds UNIQUEMENT avec un tableau JSON de booléens dans le même ordre.\n"
    "true = pertinent, false = pas pertinent.\n"
    "Pas de markdown, pas de texte autour, juste le tableau JSON.\n"
    "Exemple pour 5 entreprises : [true, false, true, true, false]\n"
)

_USER_PROMPT = (
    "## Candidat\n"
    "Poste recherché : {secteur}\n"
    "{sectors_context}\n"
    "{user_instructions_section}\n"
    "## Entreprises à évaluer ({count} entreprises)\n"
    "{companies_list}\n\n"
    "Réponds avec un tableau JSON de {count} booléens (un par entreprise, dans l'ordre)."
)


def _extract_json(raw: str) -> str:
    """Extrait le JSON d'une réponse potentiellement enrobée de markdown."""
    # Tenter d'extraire depuis un bloc ```json ... ``` ou ``` ... ```
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Tenter d'extraire un tableau JSON brut
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        return match.group(0).strip()
    return raw.strip()


async def _filter_batch(
    batch: list[Company],
    secteur: str,
    sectors_context: str,
    model: str,
    user_instructions: str | None = None,
) -> list[bool]:
    """Filtre un batch d'entreprises. Retourne une liste de booléens."""
    lines = []
    for i, c in enumerate(batch, 1):
        parts = [f"{i}. {c.nom}"]
        if c.site_web:
            parts.append(f"({c.site_web})")
        lines.append(" ".join(parts))
    companies_list = "\n".join(lines)

    if user_instructions:
        user_instructions_section = (
            f"Instructions du candidat (à respecter absolument) :\n{user_instructions}\n"
        )
    else:
        user_instructions_section = ""

    prompt = _USER_PROMPT.format(
        secteur=secteur,
        sectors_context=sectors_context,
        user_instructions_section=user_instructions_section,
        companies_list=companies_list,
        count=len(batch),
    )

    raw = await call_ai(
        model=model,
        prompt=prompt,
        system_prompt=_SYSTEM_PROMPT,
        temperature=0.1,
    )

    logger.info(f"[FILTER] Réponse brute ({len(raw)} chars) : {raw[:300]}")

    if not raw or not raw.strip():
        logger.warning("[FILTER] Réponse vide — on garde tout le batch")
        return [True] * len(batch)

    extracted = _extract_json(raw)
    verdicts = json.loads(extracted)

    if not isinstance(verdicts, list):
        logger.warning(f"[FILTER] Réponse n'est pas une liste ({type(verdicts).__name__}) — on garde tout")
        return [True] * len(batch)

    if len(verdicts) != len(batch):
        logger.warning(
            f"[FILTER] Taille incohérente ({len(verdicts)} vs {len(batch)} attendus) — on garde tout"
        )
        return [True] * len(batch)

    return [bool(v) for v in verdicts]


async def filter_companies(
    companies: list[Company],
    secteur: str,
    sectors: list[str] | None = None,
    categories: list[str] | None = None,
    user_instructions: str | None = None,
) -> list[Company]:
    """
    Filtre des entreprises par lots en parallèle.
    Retourne uniquement les entreprises pertinentes.
    """
    if not companies:
        return []

    sectors_parts = []
    if categories:
        sectors_parts.append(f"Domaines ciblés : {', '.join(categories)}")
    if sectors:
        sectors_parts.append(f"Sous-secteurs ciblés : {', '.join(sectors)}")
    sectors_context = "\n".join(sectors_parts) if sectors_parts else "Aucun secteur spécifique ciblé."

    models = await get_models()
    model = models.MODEL_FILTER

    # Découper en batches
    batches = [companies[i:i + _BATCH_SIZE] for i in range(0, len(companies), _BATCH_SIZE)]
    logger.info(
        f"[FILTER] Filtrage de {len(companies)} entreprises "
        f"avec {model} en {len(batches)} batch(s) de max {_BATCH_SIZE}"
    )

    # Exécuter tous les batches en parallèle
    try:
        all_verdicts_lists = await asyncio.gather(*[
            _filter_batch(batch, secteur, sectors_context, model, user_instructions)
            for batch in batches
        ])
    except Exception as e:
        logger.error(f"[FILTER] Erreur globale: {e} — on garde tout par défaut")
        return companies

    # Fusionner les verdicts
    all_verdicts: list[bool] = []
    for verdicts in all_verdicts_lists:
        all_verdicts.extend(verdicts)

    result = [c for c, keep in zip(companies, all_verdicts) if keep]
    removed = len(companies) - len(result)
    logger.info(f"[FILTER] {removed} entreprises filtrées, {len(result)} gardées")
    return result
