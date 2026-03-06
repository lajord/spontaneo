import re
import json
import logging

from app.core.config import settings
from app.utils.ai_caller import call_ai



logger = logging.getLogger(__name__)

_KEYWORDS_MODEL = settings.MODEL_KEYWORDS

SYSTEM_PROMPT = (
    "Tu es un expert en recherche d'entreprises via Google Places API pour la France.\n\n"
    "MISSION : générer une liste COURTE et ULTRA-PERTINENTE de mots-clés Google Places pour trouver "
    "les entreprises les plus susceptibles d'employer un candidat selon son métier recherché.\n\n"
    "RÈGLES ABSOLUES :\n"
    "→ MAXIMUM 15 mots-clés au total — choisir uniquement les plus impactants\n"
    "→ Le job title exact fourni par le candidat DOIT apparaître tel quel dans la liste\n"
    "→ Termes courts (1-4 mots), exploitables tels quels dans une recherche Google Maps\n"
    "→ Prioriser la précision sur l'exhaustivité : mieux vaut 10 termes excellents que 15 moyens\n"
    "→ Rester dans le périmètre strict du métier demandé — ne pas dériver\n\n"
    "SÉLECTIONNER PARMI CES CATÉGORIES (sans obligation d'en couvrir toutes) :\n"
    "1. Le job title exact du candidat (OBLIGATOIRE)\n"
    "2. 1-2 synonymes ou variantes très proches du métier (si vraiment utiles)\n"
    "3. 2-5 types d'entreprises qui recrutent massivement ce profil\n"
    "4. 1-3 secteurs professionnels principaux où ce métier s'exerce\n\n"
    "INTERDIT :\n"
    "✗ Écoles, universités, centres de formation, organismes de formation\n"
    "✗ Pôle emploi, agences d'intérim, cabinets de recrutement, chasseurs de têtes\n"
    "✗ Administrations, mairies, préfectures, services publics\n"
    "✗ Termes trop génériques (ex: 'entreprise', 'société', 'commerce')\n"
    "✗ Termes redondants ou quasi-identiques entre eux\n"
)

_USER_PROMPT = (
    'Métier recherché par le candidat : "{secteur}".\n'
    '{contexte_utilisateur}'
    "Génère une liste COURTE (maximum 15 mots-clés) et ultra-pertinente pour Google Places.\n"
    'Le terme exact "{secteur}" DOIT figurer dans la liste.\n'
    "Ne retiens que les mots-clés qui maximisent les chances de trouver des entreprises qui recrutent ce profil.\n"
    "Réponds UNIQUEMENT avec ce JSON :\n"
    '{{"keywords":["terme 1","terme 2","..."]}}'
)

_CONTEXTE_TEMPLATE = (
    "Contexte supplémentaire du candidat : « {prompt} »\n"
)


def _parse_keywords(raw: str) -> list[str]:
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "keywords" in data:
            return [k for k in data["keywords"] if isinstance(k, str) and k.strip()]
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict) and "keywords" in data:
                return [k for k in data["keywords"] if isinstance(k, str) and k.strip()]
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict) and "keywords" in data:
                return [k for k in data["keywords"] if isinstance(k, str) and k.strip()]
        except json.JSONDecodeError:
            pass

    logger.warning(f"Impossible de parser les keywords IA : {raw[:200]}")
    return []


async def get_keywords(secteur: str, user_prompt: str | None = None) -> list[str]:
    """
    Reformule la recherche du candidat en 1-3 requêtes Google Maps ciblées.
    Utilise GPT-4o-mini (OpenAI) — économique pour des sorties JSON courtes.
    """
    contexte_utilisateur = _CONTEXTE_TEMPLATE.format(prompt=user_prompt) if user_prompt else ""
    prompt = _USER_PROMPT.format(
        secteur=secteur,
        contexte_utilisateur=contexte_utilisateur,
    )

    try:
        logger.info(
            f"[IA KEYWORDS] {_KEYWORDS_MODEL}  "
            f"secteur='{secteur}'  user_prompt={'oui' if user_prompt else 'non'}"
        )
        raw = await call_ai(
            model=_KEYWORDS_MODEL,
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0,
        )
        keywords = _parse_keywords(raw)

        if not keywords:
            logger.warning(f"[IA KEYWORDS] Aucun keyword retourné pour '{secteur}', fallback sur secteur brut")
            return [secteur]

        logger.info(f"[IA KEYWORDS] {len(keywords)} keywords générés : {keywords}")
        return keywords

    except Exception as e:
        logger.error(f"[IA KEYWORDS] Erreur [{secteur}]: {e}")
        return [secteur]
