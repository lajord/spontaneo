import re
import httpx
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


async def normalize_location(location: str) -> str:
    """
    Normalise une localisation vers le format "Ville, France" attendu par Apollo.

    Gère :
    - Code postal français (5 chiffres) : "64000" → "Pau, France"
    - Code postal + ville : "75001 Paris" → "Paris, France"
    - Nom de ville simple : "Pau" → "Pau, France"
    - Déjà formaté : "Paris, France" → "Paris, France"
    """
    location = location.strip()

    # Déjà au format "Ville, Pays"
    parts = location.split(",")
    if len(parts) >= 2 and any(c.isalpha() for c in parts[-1]):
        return location

    # Code postal français (5 chiffres seuls ou suivi d'une ville)
    postal_match = re.match(r"^(\d{5})(?:\s+(.+))?$", location)
    if postal_match:
        postal_code = postal_match.group(1)
        city_hint = postal_match.group(2)
        # Si la ville est déjà fournie après le CP, on l'utilise directement
        if city_hint:
            return f"{city_hint.strip().title()}, France"
        return await _resolve_via_nominatim(postal_code, is_postal=True)

    # Nom de ville simple → résolution via Nominatim pour normaliser la casse
    return await _resolve_via_nominatim(location, is_postal=False)


async def _resolve_via_nominatim(query: str, is_postal: bool) -> str:
    """Résout un CP ou une ville via Nominatim et retourne "Ville, France"."""
    try:
        params = {
            "format": "json",
            "limit": 1,
            "countrycodes": "fr",
        }
        if is_postal:
            params["postalcode"] = query
        else:
            params["q"] = query

        headers = {"User-Agent": settings.NOMINATIM_USER_AGENT}

        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info(f"[LOCATION] Nominatim  query='{query}'  postal={is_postal}")
            response = await client.get(NOMINATIM_URL, params=params, headers=headers)
            data = response.json()

            if not data:
                logger.warning(f"[LOCATION] Nominatim aucun résultat pour '{query}', fallback brut")
                return f"{query}, France"

            display_name = data[0].get("display_name", "")
            # display_name = "Paris, Île-de-France, France métropolitaine, France"
            city = display_name.split(",")[0].strip()
            logger.info(f"[LOCATION] '{query}' → '{city}, France'")
            return f"{city}, France"

    except Exception as e:
        logger.error(f"[LOCATION] Erreur Nominatim pour '{query}': {e}")
        return f"{query}, France"
