import asyncio
import logging
from fastapi import APIRouter

from app.models.schemas import SearchRequest, SearchResponse
from app.recuperation_data.keywords_service import get_job_titles, get_maps_keywords
from app.recuperation_data.location import normalize_location
from app.apollo.company_search import search_companies_by_job_titles
from app.google_maps.scraper import search_google_maps

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/search/apollo", response_model=SearchResponse)
async def search_companies_apollo(request: SearchRequest):
    """
    Pipeline de récupération d'entreprises :
    1. Normalisation localisation → "Ville, France"
    2. IA → job_titles_en (Apollo) + keywords_fr (Google Maps) en parallèle
    3. Apollo search + Google Maps scraper en parallèle
    4. Merge et dédup → résultat final
    """
    logger.info(
        f"[PIPELINE]  secteur='{request.secteur}'  "
        f"localisation='{request.localisation}'  "
        f"sectors={request.sectors}"
    )

    # 1. Normaliser la localisation
    location = await normalize_location(request.localisation)
    logger.info(f"[PIPELINE] Localisation normalisée : '{location}'")

    # 2. Générer les paramètres de recherche
    #    Si l'utilisateur a fourni des sous-secteurs, on les utilise directement
    #    comme keywords Google Maps (pas besoin de passer par l'IA).
    if request.sectors:
        maps_keywords = request.sectors
        job_titles_en = await get_job_titles(request.secteur, request.prompt, request.sectors)
        logger.info(f"[PIPELINE] Sectors fournis → keywords Maps directs : {maps_keywords}")
    else:
        job_titles_en, maps_keywords = await asyncio.gather(
            get_job_titles(request.secteur, request.prompt, request.sectors),
            get_maps_keywords(request.secteur, request.sectors, request.prompt),
        )

    # 3. Lancer les deux recherches en parallèle
    apollo_companies, maps_companies = await asyncio.gather(
        search_companies_by_job_titles(job_titles=job_titles_en, location=location),
        search_google_maps(keywords=maps_keywords, location=location, max_per_keyword=50),
    )

    # 4. Merge — Apollo prioritaire en cas de doublon
    seen: dict[str, object] = {}
    for company in apollo_companies:
        key = company.nom.lower().strip()
        seen[key] = company

    for company in maps_companies:
        key = company.nom.lower().strip()
        if key not in seen:
            seen[key] = company

    entreprises = list(seen.values())

    logger.info(
        f"[PIPELINE] Résultat final : {len(entreprises)} entreprises "
        f"(Apollo={len(apollo_companies)}, Maps={len(maps_companies)}, "
        f"après dédup={len(entreprises)})"
    )

    return SearchResponse(
        secteur=request.secteur,
        localisation=location,
        job_titles=job_titles_en,
        maps_keywords=maps_keywords,
        total=len(entreprises),
        entreprises=entreprises,
    )
