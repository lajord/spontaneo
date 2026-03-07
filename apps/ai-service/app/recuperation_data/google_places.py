import math
import asyncio
import httpx
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Configuration grid search ──────────────────────────────────────
MAX_GRID_DEPTH = 3              # Profondeur max de subdivision (réduite pour limiter les requêtes)
SATURATED_THRESHOLD = 60        # 3 pages × 20 résultats = zone saturée
MAX_CONCURRENT_REQUESTS = 3     # Requêtes Google simultanées max (réduit pour éviter l'erreur 429)

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


class GooglePlacesService:
    """Service pour rechercher des entreprises via Google Places API (New) avec grid search adaptatif."""

    SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"

    def __init__(self):
        self.api_key = settings.GOOGLE_PLACE_API
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)



    # ── Recherche brute sur une zone ───────────────────────────────

    async def _search_area(
        self,
        client: httpx.AsyncClient,
        query: str,
        bbox: tuple[float, float, float, float],
    ) -> tuple[list[dict], bool]:
        """
        Recherche brute sur une zone stricte (bounding box).
        Retourne (résultats bruts, zone_saturée).
        La zone est considérée saturée si on atteint SATURATED_THRESHOLD résultats.
        """
        raw_places: list[dict] = []
        total_count = 0
        south, west, north, east = bbox

        # https://developers.google.com/maps/documentation/places/web-service/text-search
        payload = {
            "textQuery": query,
            "languageCode": "fr",
            "locationRestriction": {
                "rectangle": {
                    "low": {
                        "latitude": south,
                        "longitude": west
                    },
                    "high": {
                        "latitude": north,
                        "longitude": east
                    }
                }
            },
            "pageSize": 20
        }

        # Demander uniquement les champs nécessaires pour limiter le coût (~ Places API New)
        field_mask = "nextPageToken,places.id,places.displayName.text,places.formattedAddress,places.location,places.rating,places.types,places.websiteUri,places.nationalPhoneNumber"

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": field_mask
        }

        page = 1
        next_page_token = None
        
        while page <= 3:
            if next_page_token:
                payload["pageToken"] = next_page_token

            max_attempts = 1 if page == 1 else 3
            data = None
            response_status = None

            for attempt in range(max_attempts):
                async with self._semaphore:
                    response = await client.post(
                        self.SEARCH_TEXT_URL, json=payload, headers=headers
                    )
                    response_status = response.status_code
                    if response_status == 200:
                        data = response.json()
                        break
                    elif response_status == 429:
                        wait_429 = 3 * (attempt + 1)
                        logger.warning(f"[GRID] Erreur 429 (Quota atteint) ! Retry {attempt+1}/{max_attempts} dans {wait_429}s...")
                        await asyncio.sleep(wait_429)
                        continue # Re-tenter après avoir dormi
                    else:
                        logger.error(f"[GRID] Erreur HTTP {response_status} : {response.text}")
                
                if response_status != 400 or page == 1: 
                    break
                
                wait = 2 * (attempt + 1)
                logger.debug(
                    f"[GRID] Erreur 400 page {page}, "
                    f"retry {attempt + 1}/{max_attempts} dans {wait}s"
                )
                await asyncio.sleep(wait)

            if response_status != 200 or not data:
                if page > 1:
                    logger.debug(
                        f"[GRID] Pagination arrêtée page {page} "
                        f"(HTTP={response_status})  query='{query}'"
                    )
                else:
                    logger.warning(
                        f"[GRID] HTTP={response_status}  query='{query}'  "
                        f"bbox={bbox}"
                    )
                break

            places = data.get("places", [])
            total_count += len(places)

            for place in places:
                place_id = place.get("id")
                if not place_id:
                    continue
                raw_places.append(place)

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break

            await asyncio.sleep(3)
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
        south, west, north, east = bbox
        logger.info(
            f"[GRID] depth={depth}  bbox=({south:.4f}, {west:.4f}) -> ({north:.4f}, {east:.4f})  query='{query}'"
        )

        places, is_saturated = await self._search_area(
            client, query, bbox,
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

            # Fusionner les sous-résultats en dédupliquant par place_id (id dans la nouvelle API)
            seen_ids = {p.get("id") for p in places if p.get("id")}
            for sub_places in sub_results:
                for p in sub_places:
                    pid = p.get("id")
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
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
                    location = place.get("location", {})
                    place_lat = location.get("latitude")
                    place_lng = location.get("longitude")
                    place_name = place.get("displayName", {}).get("text", "")

                    if place_lat is not None and place_lng is not None:
                        dist_km = _haversine_km(lat, lng, place_lat, place_lng)
                        if dist_km > radius_km:
                            skipped_outside += 1
                            logger.debug(
                                f"[GOOGLE PLACES] '{place_name}' "
                                f"à {dist_km:.1f}km > {radius_km}km → ignoré"
                            )
                            continue

                    # ── Filtre structures non-employeuses ──
                    place_types = place.get("types", [])
                    place_name_lower = place_name.lower()
                    if _is_excluded_place(place_types, place_name_lower):
                        logger.debug(
                            f"[GOOGLE PLACES] '{place_name}' "
                            f"(types={place_types}) → structure non-employeuse ignorée"
                        )
                        continue

                    # Plus besoin de récupérer les détails séparément !
                    results.append({
                        "source": "google_places",
                        "place_id": place.get("id"),
                        "nom": place_name,
                        "adresse": place.get("formattedAddress", ""),
                        "site_web": place.get("websiteUri"),
                        "telephone": place.get("nationalPhoneNumber"),
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

        tasks = []
        for kw in keywords:
            tasks.append(self.search_with_radius(kw, lat, lng, radius_m))
            await asyncio.sleep(0.5) # Léger délai pour étaler l'envoi des requêtes parallèles

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
