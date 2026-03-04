import re
import json
import logging

from app.core.config import settings
from app.utils.ai_caller import call_ai

logger = logging.getLogger(__name__)

# GPT-4o-mini — rapide et peu coûteux pour de la génération courte (liste de mots-clés)
_KEYWORDS_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = (
    "Tu es un expert de la recherche Google Maps appliquée à la recherche d'emploi en France.\n\n"
    "CONTEXTE : un candidat cherche un emploi et veut trouver des entreprises à qui envoyer une candidature spontanée.\n"
    "Ta mission : à partir de sa recherche, c'est de renvoyer une liste de keywords pour google place API \n"
    "qui retourneront des entreprises susceptibles de recruter ce profil.\n\n"
    "RÈGLES :\n"
    "→ Inclure TOUJOURS la spécialité / l'intitulé professionnel lui-même (ex: 'Développeur web', 'Data scientist')\n"
    "  Google Maps trouve aussi les entreprises qui se décrivent avec ces termes dans leur fiche.\n"
    "→ Ajouter autant de termes de type d'entreprise ou secteur d'activité en lien avec la Recherche du candidat (ex: 'Agence web', 'ESN', 'Cabinet comptable')\n"
    "→ Reste au plus proche de la recherche de l'utilisateur — ne dérive pas vers des secteurs non demandés\n"
    "→ autant de keywords — précis et ciblés valent mieux que beaucoup de termes vagues\n"
    "→ Termes courts (1-3 mots), qui fonctionnent seuls dans Google Maps\n\n"
    "INTERDIT :\n"
    "✗ Écoles, universités, lycées, IUT, centres de formation\n"
    "✗ Pôle emploi, agences d'intérim, cabinets de recrutement\n"
    "✗ Administrations, mairies, préfectures\n\n"
    "Exemples :\n"
    "  'développeur web' → ['Développeur web','Developpeur', 'Agence web', 'ESN']\n"
    "  'data scientist' → ['Data scientist', 'Agence data', 'ESN']\n"
    "  'comptable' → ['Comptable', 'Cabinet comptable']\n"
    "  'avocat droit des affaires' → ['Avocat', 'Cabinet d\\'avocats']\n"
    "  'infirmier' → ['Infirmier', 'Clinique', 'Cabinet médical']\n"
)

_USER_PROMPT = (
    'Recherche du candidat : "{secteur}".\n'
    '{contexte_utilisateur}'
    "Donne 2 à 4 requêtes Google Maps ciblées : l'intitulé métier + 1-2 types d'entreprises qui recrutent ce profil.\n"
    "Réponds UNIQUEMENT avec ce JSON :\n"
    '{{"keywords":["terme 1","terme 2","terme 3"]}}'
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
            f"[IA KEYWORDS] GPT-4o-mini  "
            f"secteur='{secteur}'  user_prompt={'oui' if user_prompt else 'non'}"
        )
        raw = await call_ai(
            model=_KEYWORDS_MODEL,
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            api_key=settings.CHATGPT_API,
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
