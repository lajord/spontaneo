import math
import asyncio
import httpx
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Configuration grid search ──────────────────────────────────────
MAX_GRID_DEPTH = 4              # Profondeur max de subdivision
SATURATED_THRESHOLD = 60        # 3 pages × 20 résultats = zone saturée
MAX_CONCURRENT_REQUESTS = 5     # Requêtes Google simultanées max

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


# ── Helpers géographiques pour le grid search ──────────────────────


def _circle_to_bbox(
    lat: float, lng: float, radius_m: float,
) -> tuple[float, float, float, float]:
    """
    Convertit un cercle (centre + rayon) en bounding box (south, west, north, east).
    """
    R = 6371000.0  # Rayon de la Terre en mètres
    d_lat = math.degrees(radius_m / R)
    d_lng = math.degrees(radius_m / (R * math.cos(math.radians(lat))))
    return (lat - d_lat, lng - d_lng, lat + d_lat, lng + d_lng)


def _subdivide_bbox(
    south: float, west: float, north: float, east: float,
) -> list[tuple[float, float, float, float]]:
    """Divise une bounding box en 4 quadrants égaux."""
    mid_lat = (south + north) / 2
    mid_lng = (west + east) / 2
    return [
        (south, west, mid_lat, mid_lng),   # Sud-Ouest
        (south, mid_lng, mid_lat, east),    # Sud-Est
        (mid_lat, west, north, mid_lng),    # Nord-Ouest
        (mid_lat, mid_lng, north, east),    # Nord-Est
    ]


def _bbox_center_radius(
    south: float, west: float, north: float, east: float,
) -> tuple[float, float, int]:
    """Retourne le centre et le rayon (en mètres) couvrant la bounding box."""
    center_lat = (south + north) / 2
    center_lng = (west + east) / 2
    radius_km = _haversine_km(center_lat, center_lng, north, east)
    return center_lat, center_lng, int(radius_km * 1000)


class GooglePlacesService:
    """Service pour rechercher des entreprises via Google Places API avec grid search adaptatif."""

    TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

    def __init__(self):
        self.api_key = settings.GOOGLE_PLACE_API
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    # ── Détails d'un lieu ──────────────────────────────────────────

    async def _get_place_details(
        self,
        client: httpx.AsyncClient,
        place_id: str,
    ) -> dict:
        """Récupère les détails d'un lieu (site web, téléphone)."""
        try:
            async with self._semaphore:
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

    # ── Recherche brute sur une zone ───────────────────────────────

    async def _search_area(
        self,
        client: httpx.AsyncClient,
        query: str,
        center_lat: float,
        center_lng: float,
        radius_m: int,
    ) -> tuple[list[dict], bool]:
        """
        Recherche brute sur une zone (centre + rayon).
        Retourne (résultats bruts, zone_saturée).
        La zone est considérée saturée si on atteint SATURATED_THRESHOLD résultats.
        """
        raw_places: list[dict] = []
        total_count = 0

        search_params = {
            "query": query,
            "location": f"{center_lat},{center_lng}",
            "radius": min(radius_m, 50000),
            "key": self.api_key,
            "language": "fr",
        }

        page = 1
        while page <= 3:
            async with self._semaphore:
                response = await client.get(
                    self.TEXT_SEARCH_URL, params=search_params
                )
                data = response.json()

            status = data.get("status")
            if status not in ("OK", "ZERO_RESULTS"):
                logger.warning(
                    f"[GRID] Status={status}  query='{query}'  "
                    f"center=({center_lat:.4f}, {center_lng:.4f})"
                )
                break

            places = data.get("results", [])
            total_count += len(places)

            for place in places:
                place_id = place.get("place_id")
                if not place_id:
                    continue
                raw_places.append({
                    "place_id": place_id,
                    "name": place.get("name", ""),
                    "formatted_address": place.get("formatted_address", ""),
                    "geometry": place.get("geometry", {}),
                    "rating": place.get("rating"),
                    "types": place.get("types", []),
                })

            next_token = data.get("next_page_token")
            if not next_token:
                break

            await asyncio.sleep(2)
            search_params = {"pagetoken": next_token, "key": self.api_key}
            page += 1

        is_saturated = total_count >= SATURATED_THRESHOLD
        return raw_places, is_saturated

    # ── Grid search récursif ───────────────────────────────────────

    async def _grid_search(
        self,
        client: httpx.AsyncClient,
        query: str,
        bbox: tuple[float, float, float, float],
        depth: int = 0,
    ) -> list[dict]:
        """
        Recherche récursive avec subdivision adaptative.
        Si une zone retourne ~60 résultats (saturée), elle est divisée en 4 quadrants
        et chaque quadrant est recherché indépendamment.
        """
        center_lat, center_lng, radius_m = _bbox_center_radius(*bbox)

        logger.info(
            f"[GRID] depth={depth}  center=({center_lat:.4f}, {center_lng:.4f})  "
            f"radius={radius_m // 1000}km  query='{query}'"
        )

        places, is_saturated = await self._search_area(
            client, query, center_lat, center_lng, radius_m,
        )

        if is_saturated and depth < MAX_GRID_DEPTH:
            logger.info(
                f"[GRID] Zone saturée ({len(places)} résultats) → subdivision en 4  "
                f"(depth {depth} → {depth + 1})  query='{query}'"
            )
            sub_bboxes = _subdivide_bbox(*bbox)
            sub_tasks = [
                self._grid_search(client, query, sb, depth + 1)
                for sb in sub_bboxes
            ]
            sub_results = await asyncio.gather(*sub_tasks)

            # Fusionner les sous-résultats en dédupliquant par place_id
            seen_ids = {p["place_id"] for p in places}
            for sub_places in sub_results:
                for p in sub_places:
                    if p["place_id"] not in seen_ids:
                        seen_ids.add(p["place_id"])
                        places.append(p)

        elif is_saturated:
            logger.warning(
                f"[GRID] Profondeur max ({MAX_GRID_DEPTH}) atteinte, "
                f"zone encore saturée ({len(places)} résultats)  query='{query}'"
            )

        return places

    # ── Point d'entrée principal ───────────────────────────────────

    async def search_with_radius(
        self,
        query: str,
        lat: float,
        lng: float,
        radius_m: int,
    ) -> list[dict]:
        """
        Recherche par mots-clés avec grid search adaptatif.
        Subdivise automatiquement les zones saturées (≥60 résultats)
        en sous-zones pour capturer toutes les entreprises disponibles.
        """
        if not self.api_key:
            logger.warning("Google Places API key non configurée")
            return []

        radius_km = radius_m / 1000
        bbox = _circle_to_bbox(lat, lng, float(radius_m))

        logger.info(
            f"[GOOGLE PLACES]  query='{query}'  "
            f"lat={lat}  lng={lng}  radius={radius_km}km"
        )

        results = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # ── Grid search récursif ──
                raw_places = await self._grid_search(
                    client, query, bbox, depth=0,
                )

                logger.info(
                    f"[GRID] Total brut après grid search : "
                    f"{len(raw_places)} résultats  query='{query}'"
                )

                skipped_outside = 0

                for place in raw_places:
                    # ── Filtre strict par distance réelle (centre original) ──
                    geometry = place.get("geometry", {}).get("location", {})
                    place_lat = geometry.get("lat")
                    place_lng = geometry.get("lng")

                    if place_lat is not None and place_lng is not None:
                        dist_km = _haversine_km(lat, lng, place_lat, place_lng)
                        if dist_km > radius_km:
                            skipped_outside += 1
                            logger.debug(
                                f"[GOOGLE PLACES] '{place.get('name')}' "
                                f"à {dist_km:.1f}km > {radius_km}km → ignoré"
                            )
                            continue

                    # ── Filtre structures non-employeuses ──
                    place_types = place.get("types", [])
                    place_name_lower = place.get("name", "").lower()
                    if _is_excluded_place(place_types, place_name_lower):
                        logger.debug(
                            f"[GOOGLE PLACES] '{place.get('name')}' "
                            f"(types={place_types}) → structure non-employeuse ignorée"
                        )
                        continue

                    # ── Récupération des détails ──
                    details = await self._get_place_details(
                        client, place["place_id"],
                    )
                    results.append({
                        "source": "google_places",
                        "place_id": place["place_id"],
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

        except Exception as e:
            logger.error(f"Erreur Google Places grid search: {e}")

        logger.info(
            f"[GOOGLE PLACES] query='{query}' → "
            f"{len(results)} entreprises après filtres"
        )
        return results

    # ── Recherche multi-mots-clés ──────────────────────────────────

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

        logger.info(
            f"[GOOGLE PLACES] Total après fusion + filtre géo : "
            f"{len(merged)} entreprises"
        )
        return merged


google_places_service = GooglePlacesService()
