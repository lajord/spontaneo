import re
import json
import logging

from app.core.model_config import get_models
from app.utils.ai_caller import call_ai



logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Tu es un expert en recrutement en France.\n\n"
    "CONTEXTE : un candidat veut envoyer des CANDIDATURES SPONTANÉES à des entreprises "
    "trouvées via Google Maps. On te donne son métier, et tu dois générer les mots-clés "
    "pour trouver les bonnes structures.\n\n"
    "RÈGLE FONDAMENTALE : ne retourne que des structures où ce métier est AU COEUR DE L'ACTIVITÉ, "
    "pas une fonction support.\n"
    "Demande-toi : « Est-ce qu'une candidature spontanée pour ce poste a du sens dans cette structure ? »\n\n"
    "RAISONNEMENT À SUIVRE :\n"
    "1. Ce métier est-il le coeur de métier de la structure ? Si oui → pertinent\n"
    "2. Ce métier n'est qu'une fonction support dans cette structure ? Si oui → NON PERTINENT\n"
    "3. Est-ce qu'on trouve ce type de structure sur Google Maps ? Si non → NON PERTINENT\n\n"
    "Exemple de bon raisonnement :\n"
    "→ Juriste : 'cabinet d'avocats' ✓ (le droit = coeur de métier), 'banque' ✗ (le juridique est une fonction support en banque)\n"
    "→ Cuisinier : 'restaurant' ✓ (la cuisine = coeur de métier), 'hôpital' ✗ (la cuisine est un service annexe)\n"
    "→ Comptable : 'cabinet comptable' ✓, 'expert-comptable' ✓, 'banque' ✗ (la compta est une fonction support)\n\n"
    "RÈGLES :\n"
    "→ Entre 3 et 6 mots-clés — seulement ceux qui sont vraiment pertinents\n"
    "→ Chaque mot-clé = un type de structure visible sur Google Maps où une candidature spontanée a du sens\n"
    "→ Zéro doublon, zéro synonyme inutile\n\n"
    "INTERDIT :\n"
    "✗ Écoles, universités, centres de formation\n"
    "✗ Pôle emploi, agences d'intérim, cabinets de recrutement\n"
    "✗ Administrations, mairies, préfectures, services publics\n"
    "✗ Termes abstraits ('numérique', 'tech', 'innovation', 'digital', 'industrie')\n"
    "✗ Mots isolés trop vagues ('conseil', 'service', 'groupe', 'startup')\n"
    "✗ Structures où le métier n'est qu'une fonction support (ex: 'banque' pour un juriste)\n"
)

_USER_PROMPT = (
    'Le candidat veut envoyer des candidatures spontanées pour le poste de : "{secteur}".\n'
    '{contexte_utilisateur}'
    "Dans quels types de structures ce métier est-il le COEUR DE L'ACTIVITÉ ? "
    "Génère entre 3 et 6 mots-clés Google Maps. "
    "3 bons mots-clés valent mieux que 6 moyens.\n"
    "Réponds UNIQUEMENT avec ce JSON :\n"
    '{{"keywords":["structure 1","structure 2","..."]}}'
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


_APOLLO_SYSTEM_PROMPT = (
    "Tu es un expert en recherche d'entreprises via l'API Apollo.io.\n\n"
    "Tu dois générer deux choses pour optimiser la recherche Apollo :\n\n"
    "1. `job_title_en` — traduction en anglais du titre de poste du candidat.\n"
    "   C'est le titre exact utilisé pour `q_organization_job_titles[]`.\n"
    "   Exemples : 'data analyst', 'software engineer', 'sales manager'\n\n"
    "2. `keyword_tags` — valeurs pour `q_organization_keyword_tags[]`\n"
    "   Mots-clés sectoriels associés aux entreprises susceptibles de recruter ce profil.\n"
    "   Exemples Apollo : 'data analytics', 'business intelligence', 'consulting', 'fintech'\n\n"
    "RÈGLES :\n"
    "→ job_title_en : UN SEUL titre, traduction directe en anglais, sans variantes\n"
    "→ keyword_tags : 5 à 10 tags, en anglais, secteurs/domaines d'activité pertinents\n"
    "→ Exemple pour 'data analyst' :\n"
    "  job_title_en: 'data analyst'\n"
    "  keyword_tags: ['data analytics', 'business intelligence', 'consulting', 'fintech', 'saas']\n"
    "→ Exemple pour 'commercial B2B' :\n"
    "  job_title_en: 'b2b sales representative'\n"
    "  keyword_tags: ['sales strategy', 'b2b', 'wholesale', 'distribution', 'consulting']\n\n"
    "INTERDIT :\n"
    "✗ keyword_tags trop vagues ('company', 'business', 'enterprise', 'service')\n"
    "✗ Agences d'intérim, cabinets de recrutement dans les keyword_tags\n"
)

_APOLLO_USER_PROMPT = (
    'Métier recherché : "{secteur}".\n'
    '{contexte_utilisateur}'
    "Génère la traduction anglaise du titre et les keyword_tags Apollo.\n"
    "Réponds UNIQUEMENT avec ce JSON :\n"
    '{{"job_title_en":"titre en anglais","keyword_tags":["tag1","tag2","..."]}}'
)


async def get_apollo_search_params(
    secteur: str, user_prompt: str | None = None
) -> tuple[list[str], str]:
    """
    Génère en un seul appel IA :
    - keyword_tags  : secteurs/domaines pour q_organization_keyword_tags[]
    - job_title_en  : traduction anglaise du titre de poste (un seul titre)

    Retourne (keyword_tags, job_title_en).
    """
    contexte_utilisateur = _CONTEXTE_TEMPLATE.format(prompt=user_prompt) if user_prompt else ""
    prompt = _APOLLO_USER_PROMPT.format(
        secteur=secteur,
        contexte_utilisateur=contexte_utilisateur,
    )

    try:
        models = await get_models()
        logger.info(f"[IA APOLLO PARAMS] {models.MODEL_KEYWORDS}  secteur='{secteur}'")
        raw = await call_ai(
            model=models.MODEL_KEYWORDS,
            prompt=prompt,
            system_prompt=_APOLLO_SYSTEM_PROMPT,
            temperature=0,
        )

        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                keyword_tags = [t for t in data.get("keyword_tags", []) if isinstance(t, str) and t.strip()]
                job_title_en = data.get("job_title_en", "").strip()
                if not job_title_en:
                    job_title_en = secteur
                logger.info(f"[IA APOLLO PARAMS] job_title_en='{job_title_en}'  keyword_tags={keyword_tags}")
                return keyword_tags, job_title_en
        except json.JSONDecodeError:
            pass

        logger.warning(f"[IA APOLLO PARAMS] Parse échoué pour '{secteur}', fallback brut")
        return [secteur], secteur

    except Exception as e:
        logger.error(f"[IA APOLLO PARAMS] Erreur [{secteur}]: {e}")
        return [secteur], secteur


# Alias conservé pour compatibilité
async def get_apollo_keyword_tags(secteur: str, user_prompt: str | None = None) -> list[str]:
    keyword_tags, _ = await get_apollo_search_params(secteur, user_prompt)
    return keyword_tags


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
        models = await get_models()
        logger.info(
            f"[IA KEYWORDS] {models.MODEL_KEYWORDS}  "
            f"secteur='{secteur}'  user_prompt={'oui' if user_prompt else 'non'}"
        )
        raw = await call_ai(
            model=models.MODEL_KEYWORDS,
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
