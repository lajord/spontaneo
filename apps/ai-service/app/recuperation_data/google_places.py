import math
import asyncio
import httpx
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Types Google Places correspondant à des structures non-employeuses
_EXCLUDED_TYPES = {
    "school", "university", "secondary_school", "primary_school",
    "library", "local_government_office", "city_hall", "government_office",
    "embassy", "courthouse", "police", "fire_station",
    "place_of_worship", "cemetery",
}

# Mots-clés dans le nom (fallback si le type n'est pas précis)
_EXCLUDED_NAME_KEYWORDS = [
    "école", "ecole", "université", "universite", "collège", "college",
    "lycée", "lycee", "iut ", " iut", "campus", "centre de formation",
    "organisme de formation", "cpam", "caf ", " caf", "pôle emploi",
    "pole emploi", "france travail", "mairie ", "mairie de", "préfecture",
    "prefecture", "conseil général", "conseil régional", "académie", "academie",
    "médiathèque", "mediatheque", "bibliothèque", "bibliotheque",
]


def _is_excluded_place(types: list[str], name_lower: str) -> bool:
    """Retourne True si le lieu est une structure non-employeuse (école, admin...)."""
    if any(t in _EXCLUDED_TYPES for t in types):
        return True
    return any(kw in name_lower for kw in _EXCLUDED_NAME_KEYWORDS)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcule la distance en km entre deux points GPS (formule de Haversine)."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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
        Recherche par mots-clés centrée sur des coordonnées GPS avec rayon strict.
        Google Places Text Search utilise le radius comme biais uniquement —
        on applique donc un FILTRE STRICT côté serveur via la distance Haversine.
        """
        if not self.api_key:
            logger.warning("Google Places API key non configurée")
            return []

        radius_km = radius_m / 1000
        results = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                search_params = {
                    "query": query,
                    "location": f"{lat},{lng}",
                    "radius": min(radius_m, 50000),
                    "key": self.api_key,
                    "language": "fr",
                    # On demande geometry pour pouvoir filtrer par distance réelle
                    "fields": "place_id,name,formatted_address,geometry,rating,types",
                }

                logger.info(
                    f"[GOOGLE PLACES]  query='{query}'  "
                    f"lat={lat}  lng={lng}  "
                    f"radius={min(radius_m, 50000) // 1000}km"
                )

                page = 1
                skipped_outside = 0

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

                        # ── Filtre strict par distance réelle ──────────────────
                        geometry = place.get("geometry", {}).get("location", {})
                        place_lat = geometry.get("lat")
                        place_lng = geometry.get("lng")

                        if place_lat is not None and place_lng is not None:
                            dist_km = _haversine_km(lat, lng, place_lat, place_lng)
                            if dist_km > radius_km:
                                skipped_outside += 1
                                logger.debug(
                                    f"[GOOGLE PLACES] ⛔ '{place.get('name')}' "
                                    f"à {dist_km:.1f}km > {radius_km}km → ignoré"
                                )
                                continue
                        # ───────────────────────────────────────────────────────

                        # ── Filtre structures non-employeuses ──────────────────
                        place_types = place.get("types", [])
                        place_name_lower = place.get("name", "").lower()
                        if _is_excluded_place(place_types, place_name_lower):
                            logger.debug(
                                f"[GOOGLE PLACES] ⛔ '{place.get('name')}' "
                                f"(types={place_types}) → structure non-employeuse ignorée"
                            )
                            continue
                        # ───────────────────────────────────────────────────────

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

                    if skipped_outside:
                        logger.info(
                            f"[GOOGLE PLACES] query='{query}' → "
                            f"{skipped_outside} résultats hors zone filtrés"
                        )

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

        logger.info(f"[GOOGLE PLACES] Total après fusion + filtre géo : {len(merged)} entreprises")
        return merged


google_places_service = GooglePlacesService()
