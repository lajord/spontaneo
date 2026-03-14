import json
import logging

from app.core.model_config import get_models
from app.utils.ai_caller import call_ai


logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Tu es un expert en recherche Apollo.io d'entreprises françaises. "
    "Tu reçois un métier en français et tu dois retourner un JSON strict.\n\n"

    "## CONTEXTE APOLLO\n"
    "Apollo.io indexe les profils d'entreprises issus de LinkedIn et de ses propres bases.\n"
    "Le paramètre `q_organization_job_titles` filtre sur les OFFRES D'EMPLOI ACTIVES publiées par l'entreprise.\n\n"

    "## RÈGLE — job_titles_en (liste de 2 à 4 variantes)\n"
    "Génère les variantes de titres de poste en anglais les plus utilisées sur les offres d'emploi anglo-saxonnes.\n"
    "Ce sont les intitulés exacts que les RH et recruteurs tapent sur LinkedIn Jobs / Indeed EN.\n"
    "- 'comptable' → ['accountant', 'accounting manager', 'financial accountant']\n"
    "- 'développeur web' → ['web developer', 'frontend developer', 'fullstack developer']\n"
    "- 'data analyst' → ['data analyst', 'business analyst', 'data scientist']\n"
    "- 'commercial B2B' → ['sales representative', 'account executive', 'business development manager']\n"
    "- 'juriste' → ['legal counsel', 'corporate lawyer', 'in-house counsel']\n"
    "- 'serveur' → ['waiter', 'server', 'food server', 'waitstaff']\n"
    "INTERDIT : inventer un titre sans rapport avec le métier demandé.\n"
)

_USER_PROMPT = (
    'Métier : "{secteur}".\n'
    '{contexte_utilisateur}'
    "Réponds UNIQUEMENT avec ce JSON (rien d'autre) :\n"
    '{{"job_titles_en":["titre1","titre2","titre3"]}}'
)

_CONTEXTE_TEMPLATE = (
    "Contexte supplémentaire du candidat : « {prompt} »\n"
)

# ── Google Maps Keywords ────────────────────────────────────────────────────────

_MAPS_SYSTEM_PROMPT = (
    "Tu es un expert en recherche Google Maps d'entreprises françaises.\n"
    "Tu reçois un métier et éventuellement des secteurs ciblés, et tu dois générer "
    "les mots-clés de recherche Google Maps les plus pertinents.\n\n"

    "RÈGLE FONDAMENTALE : QUALITÉ > QUANTITÉ.\n"
    "Chaque mot-clé doit correspondre à un type de structure RÉEL et VISIBLE sur Google Maps "
    "où une candidature spontanée pour ce poste a du sens.\n\n"

    "SI des secteurs sont fournis par le candidat :\n"
    "→ Utilise-les comme base pour générer des mots-clés précis.\n"
    "→ Ex : Serveur + Restauration, Hôtellerie → ['restaurant', 'brasserie', 'hôtel restaurant']\n\n"

    "SI AUCUN secteur n'est fourni :\n"
    "→ Sois ULTRA CONSERVATEUR. Ne génère que des mots-clés hyper ciblés sur le cœur de métier.\n"
    "→ Préfère 2 mots-clés parfaits plutôt que 5 moyens.\n"
    "→ Ex : Data Analyst → ['cabinet data analytics', 'agence data science']\n"
    "→ Ex : Comptable → ['cabinet comptable', 'expert-comptable']\n"
    "→ Ex : Développeur web → ['agence web', 'agence digitale']\n\n"

    "RÈGLES :\n"
    "→ Entre 2 et 5 mots-clés maximum\n"
    "→ En français (c'est une recherche Google Maps en France)\n"
    "→ Chaque mot-clé = un type de structure visible sur Google Maps\n"
    "→ Pas de doublons, pas de synonymes inutiles\n\n"

    "INTERDIT :\n"
    "✗ Termes vagues ('entreprise', 'société', 'bureau', 'service')\n"
    "✗ Écoles, universités, centres de formation\n"
    "✗ Administrations, mairies, préfectures\n"
    "✗ Agences d'intérim, cabinets de recrutement\n"
    "✗ Mots en anglais (sauf si c'est le terme courant en France)\n"
)

_MAPS_USER_PROMPT = (
    'Métier : "{secteur}".\n'
    '{contexte_utilisateur}'
    "Réponds UNIQUEMENT avec ce JSON (rien d'autre) :\n"
    '{{"keywords":["mot-clé 1","mot-clé 2"]}}'
)


async def get_job_titles(
    secteur: str, user_prompt: str | None = None, sectors: list[str] | None = None
) -> list[str]:
    """
    Génère via IA les variantes du titre de poste en anglais
    pour le paramètre Apollo `q_organization_job_titles`.
    """
    contexte_utilisateur = _CONTEXTE_TEMPLATE.format(prompt=user_prompt) if user_prompt else ""
    if sectors:
        contexte_utilisateur += f"Secteurs professionnels ciblés par le candidat : {', '.join(sectors)}\n"
    prompt = _USER_PROMPT.format(
        secteur=secteur,
        contexte_utilisateur=contexte_utilisateur,
    )

    try:
        models = await get_models()
        logger.info(f"[IA JOB TITLES] {models.MODEL_KEYWORDS}  secteur='{secteur}'")
        raw = await call_ai(
            model=models.MODEL_KEYWORDS,
            prompt=prompt,
            system_prompt=_SYSTEM_PROMPT,
            temperature=0,
        )

        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                job_titles_en = [t for t in data.get("job_titles_en", []) if isinstance(t, str) and t.strip()]
                if not job_titles_en:
                    job_titles_en = [secteur]
                logger.info(f"[IA JOB TITLES] job_titles_en={job_titles_en}")
                return job_titles_en
        except json.JSONDecodeError:
            pass

        logger.warning(f"[IA JOB TITLES] Parse échoué pour '{secteur}', fallback brut")
        return [secteur]

    except Exception as e:
        logger.error(f"[IA JOB TITLES] Erreur [{secteur}]: {e}")
        return [secteur]


async def get_maps_keywords(
    secteur: str, sectors: list[str] | None = None, user_prompt: str | None = None
) -> list[str]:
    """
    Génère via IA des mots-clés Google Maps en français, ultra sélectifs.
    Si des secteurs sont fournis, les utilise comme base.
    Sinon, génère des keywords hyper ciblés sur le métier.
    """
    contexte_utilisateur = _CONTEXTE_TEMPLATE.format(prompt=user_prompt) if user_prompt else ""
    if sectors:
        contexte_utilisateur += f"Secteurs professionnels ciblés par le candidat : {', '.join(sectors)}\n"
    else:
        contexte_utilisateur += "AUCUN secteur fourni — sois ULTRA CONSERVATEUR, génère uniquement des keywords hyper ciblés.\n"

    prompt = _MAPS_USER_PROMPT.format(
        secteur=secteur,
        contexte_utilisateur=contexte_utilisateur,
    )

    try:
        models = await get_models()
        logger.info(f"[IA MAPS KEYWORDS] {models.MODEL_KEYWORDS}  secteur='{secteur}'  sectors={sectors}")
        raw = await call_ai(
            model=models.MODEL_KEYWORDS,
            prompt=prompt,
            system_prompt=_MAPS_SYSTEM_PROMPT,
            temperature=0,
        )

        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "keywords" in data:
                keywords = [k for k in data["keywords"] if isinstance(k, str) and k.strip()]
                if keywords:
                    logger.info(f"[IA MAPS KEYWORDS] keywords={keywords}")
                    return keywords
        except json.JSONDecodeError:
            pass

        logger.warning(f"[IA MAPS KEYWORDS] Parse échoué pour '{secteur}', fallback brut")
        return [secteur]

    except Exception as e:
        logger.error(f"[IA MAPS KEYWORDS] Erreur [{secteur}]: {e}")
        return [secteur]
