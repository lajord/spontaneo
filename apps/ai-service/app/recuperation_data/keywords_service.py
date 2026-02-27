import re
import json
import logging

from app.core.config import settings
from app.models.schemas import GranularityLevel
from app.utils.ai_caller import call_ai

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Tu es un expert du marché du travail français et de la recherche d'entreprises dans Google Maps.\n\n"
    "Ta mission : générer des mots-clés recherchables via Google Places API pour trouver des entreprises\n"
    "susceptibles d'embaucher le profil demandé.\n\n"
    "Tu dois générer UN MIX de deux catégories :\n"
    "1. MÉTIERS / POSTES : intitulés de poste courts et courants (ex: 'Développeur web', 'Ingénieur data')\n"
    "   → Ces termes remontent les grandes entreprises (Total, Capgemini, Terega...) qui ont ces postes\n"
    "2. TYPES D'ENSEIGNES : types d'établissements employeurs (ex: 'Agence informatique', 'ESN', 'Cabinet comptable')\n"
    "   → Ces termes remontent les PME et structures spécialisées\n\n"
    "RÈGLES :\n"
    "→ Chaque terme doit fonctionner seul comme requête dans Google Maps\n"
    "→ Mélange les deux catégories pour couvrir un maximum d'entreprises\n"
    "→ Termes courts et courants, pas de phrases\n\n"
    "Exemples pour 'développeur web' :\n"
    "  Métiers : 'Développeur web', 'Ingénieur logiciel', 'Ingénieur informatique'\n"
    "  Enseignes : 'Agence informatique', 'ESN', 'Agence web', 'SSII'\n"
    "Exemples pour 'Data / IA' :\n"
    "  Métiers : 'Ingénieur data', 'Data scientist', 'Data analyst', 'Ingénieur informatique'\n"
    "  Enseignes : 'Agence digitale', 'ESN', 'Cabinet conseil informatique'\n"
    "Exemples pour 'comptable' :\n"
    "  Métiers : 'Comptable', 'Expert-comptable', 'Contrôleur de gestion'\n"
    "  Enseignes : 'Cabinet comptable', 'Cabinet expertise comptable'\n"
)

PROMPTS = {
    GranularityLevel.faible: (
        'Profil / secteur recherché : "{secteur}".\n\n'
        "Génère entre 5 et 8 mots-clés Google Maps : mix de métiers courants ET types d'enseignes employeurs.\n"
        "Reste centré sur les termes les plus évidents et efficaces.\n"
        "Réponds UNIQUEMENT avec ce JSON :\n"
        '{{"keywords":["terme 1","terme 2",...]}}'
    ),
    GranularityLevel.moyen: (
        'Profil / secteur recherché : "{secteur}".\n\n'
        "Génère entre 8 et 14 mots-clés Google Maps : mix de métiers ET types d'enseignes employeurs.\n"
        "Couvre les termes principaux + leurs variantes pour toucher PME et grandes entreprises.\n"
        "Réponds UNIQUEMENT avec ce JSON :\n"
        '{{"keywords":["terme 1","terme 2",...]}}'
    ),
    GranularityLevel.fort: (
        'Profil / secteur recherché : "{secteur}".\n\n'
        "Génère entre 14 et 20 mots-clés Google Maps : mix de métiers ET types d'enseignes employeurs.\n"
        "Inclure : métiers directs, variantes, postes connexes, types d'enseignes spécialisées et génériques.\n"
        "Maximise la couverture pour trouver PME, start-ups et grands groupes.\n"
        "Réponds UNIQUEMENT avec ce JSON :\n"
        '{{"keywords":["terme 1","terme 2",...]}}'
    ),
}


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


# Fallbacks par domaine si l'IA échoue
_FALLBACKS: dict[str, list[str]] = {
    "dev": ["Développeur web", "Ingénieur informatique", "Agence informatique", "ESN", "Agence web"],
    "data": ["Ingénieur data", "Data scientist", "Ingénieur informatique", "ESN", "Cabinet conseil informatique"],
    "compta": ["Comptable", "Expert-comptable", "Cabinet comptable", "Cabinet expertise comptable"],
    "marketing": ["Chargé de marketing", "Responsable marketing", "Agence marketing", "Agence de communication"],
    "design": ["Designer", "Graphiste", "UX designer", "Agence web", "Studio graphique"],
}


async def get_keywords(secteur: str, granularite: GranularityLevel) -> list[str]:
    """
    Génère les mots-clés de métiers/postes pour Google Places,
    basé sur le profil/secteur recherché et la granularité.
    """
    prompt = PROMPTS[granularite].format(secteur=secteur)

    try:
        logger.info(
            f"[IA KEYWORDS] OVH  model={settings.OVH_AI_MODEL}  "
            f"secteur='{secteur}'  granularite={granularite}"
        )
        raw = await call_ai(
            model=settings.OVH_AI_MODEL,
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            base_url=settings.OVH_AI_BASE_URL,
            api_key=settings.OVH_AI_ENDPOINTS_ACCESS_TOKEN,
            temperature=0,
        )
        keywords = _parse_keywords(raw)

        if not keywords:
            logger.warning(f"[IA KEYWORDS] Aucun keyword retourné pour '{secteur}', utilisation du fallback")
            return [secteur]

        logger.info(f"[IA KEYWORDS] {len(keywords)} keywords générés : {keywords}")
        return keywords

    except Exception as e:
        logger.error(f"[IA KEYWORDS] Erreur [{secteur}]: {e}")
        return [secteur]
