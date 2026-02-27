import httpx
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


async def geocode(localisation: str) -> tuple[float, float]:
    """
    Convertit une localisation textuelle en coordonnées GPS.

    Args:
        localisation: Ville ou code postal (ex: "Pau" ou "64000")

    Returns:
        (latitude, longitude)

    Raises:
        ValueError: Si la localisation est introuvable
    """
    params = {
        "q": localisation,
        "format": "json",
        "limit": 1,
        "countrycodes": "fr",
    }
    headers = {"User-Agent": settings.NOMINATIM_USER_AGENT}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info(f"[GEO] Nominatim  q='{localisation}'  countrycodes=fr")
            response = await client.get(NOMINATIM_URL, params=params, headers=headers)
            data = response.json()

            if not data:
                raise ValueError(f"Localisation introuvable : '{localisation}'")

            lat = float(data[0]["lat"])
            lng = float(data[0]["lon"])
            return lat, lng

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Erreur géocodage '{localisation}': {e}")
        raise ValueError(f"Erreur géocodage : {e}")
