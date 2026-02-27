import asyncio
import httpx
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class GooglePlacesService:
    """Service pour rechercher des entreprises via Google Places API."""

    TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

    def __init__(self):
        self.api_key = settings.GOOGLE_PLACE_API

    async def _get_place_details(
        self,
        client: httpx.AsyncClient,
        place_id: str,
    ) -> dict:
        """Récupère les détails d'un lieu (site web, téléphone)."""
        try:
            params = {
                "place_id": place_id,
                "fields": "website,formatted_phone_number,url",
                "key": self.api_key,
            }
            response = await client.get(self.DETAILS_URL, params=params)
            data = response.json()
            if data.get("status") == "OK":
                return data.get("result", {})
        except Exception as e:
            logger.error(f"Erreur détails place {place_id}: {e}")
        return {}

    async def search_with_radius(
        self,
        query: str,
        lat: float,
        lng: float,
        radius_m: int,
    ) -> list[dict]:
        """
        Recherche par mots-clés centrée sur des coordonnées GPS avec rayon.
        Pagine automatiquement jusqu'à 3 pages (60 résultats max par keyword).
        """
        if not self.api_key:
            logger.warning("Google Places API key non configurée")
            return []

        results = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                search_params = {
                    "query": query,
                    "location": f"{lat},{lng}",
                    "radius": min(radius_m, 50000),
                    "key": self.api_key,
                    "language": "fr",
                }

                logger.info(
                    f"[GOOGLE PLACES]  query='{query}'  "
                    f"lat={lat}  lng={lng}  "
                    f"radius={min(radius_m, 50000) // 1000}km"
                )

                page = 1
                while page <= 3:
                    response = await client.get(self.TEXT_SEARCH_URL, params=search_params)
                    data = response.json()
                    status = data.get("status")

                    if status not in ("OK", "ZERO_RESULTS"):
                        logger.warning(f"[GOOGLE PLACES] Status={status}  query='{query}'")
                        break

                    places = data.get("results", [])
                    for place in places:
                        place_id = place.get("place_id")
                        if not place_id:
                            continue
                        details = await self._get_place_details(client, place_id)
                        results.append({
                            "source": "google_places",
                            "place_id": place_id,
                            "nom": place.get("name", ""),
                            "adresse": place.get("formatted_address", ""),
                            "site_web": details.get("website"),
                            "telephone": details.get("formatted_phone_number"),
                            "rating": place.get("rating"),
                            "types": place.get("types", []),
                        })

                    next_token = data.get("next_page_token")
                    if not next_token:
                        break

                    await asyncio.sleep(2)
                    search_params = {"pagetoken": next_token, "key": self.api_key}
                    page += 1

        except Exception as e:
            logger.error(f"Erreur Google Places radius: {e}")

        return results

    async def search_multi_keywords(
        self,
        keywords: list[str],
        lat: float,
        lng: float,
        radius_m: int,
    ) -> list[dict]:
        """
        Lance des recherches parallèles pour chaque mot-clé et fusionne les résultats.
        Déduplication par place_id puis par nom. Aucun plafond sur le total.
        """
        if not keywords:
            return []

        tasks = [self.search_with_radius(kw, lat, lng, radius_m) for kw in keywords]
        all_batches = await asyncio.gather(*tasks)

        seen_ids: set[str] = set()
        seen_names: set[str] = set()
        merged: list[dict] = []

        for batch in all_batches:
            for r in batch:
                pid = r.get("place_id", "")
                name = r.get("nom", "").lower().strip()
                if pid and pid in seen_ids:
                    continue
                if name in seen_names:
                    continue
                if pid:
                    seen_ids.add(pid)
                seen_names.add(name)
                merged.append(r)

        return merged


google_places_service = GooglePlacesService()
