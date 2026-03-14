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
