import asyncio
import logging
from fastapi import APIRouter

from app.models.schemas import SearchRequest, SearchResponse
from app.recuperation_data.keywords_service import build_search_params
from app.recuperation_data.location import normalize_location
from app.apollo.company_search import search_companies_by_job_titles, search_companies_by_keywords
from app.google_maps.scraper import search_google_maps

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/search/apollo", response_model=SearchResponse)
async def search_companies_apollo(request: SearchRequest):
    """
    Pipeline de récupération d'entreprises :
    1. Normalisation localisation
    2. Un seul appel IA stratégique → paramètres de recherche pour les 3 sources
    3. Apollo (job titles) + Apollo (keywords) + Google Maps en parallèle
    4. Dédup : Apollo = base, Maps ajoute les nouveaux
    """
    logger.info(
        f"[PIPELINE]  secteur='{request.secteur}'  "
        f"localisation='{request.localisation}'  "
        f"sectors={request.sectors}  categories={request.categories}"
    )

    # 1. Normaliser la localisation
    location = await normalize_location(request.localisation)
    logger.info(f"[PIPELINE] Localisation normalisée : '{location}'")

    # 2. Un seul appel IA stratégique
    params = await build_search_params(
        secteur=request.secteur,
        sectors=request.sectors,
        categories=request.categories,
    )

    job_titles_en = params["apollo_job_titles"]
    apollo_keywords_en = params["apollo_keywords"]
    maps_keywords = params["google_maps_keywords"]

    # 3. Trois recherches en parallèle
    apollo_jt_companies, apollo_kw_companies, maps_companies = await asyncio.gather(
        search_companies_by_job_titles(job_titles=job_titles_en, location=location),
        search_companies_by_keywords(keywords=apollo_keywords_en, location=location),
        search_google_maps(keywords=maps_keywords, location=location, max_per_keyword=50),
    )

    # 4. Dédup — Apollo = base, Google Maps ajoute uniquement les nouvelles
    seen: dict[str, object] = {}
    for company in apollo_jt_companies:
        key = company.nom.lower().strip()
        seen[key] = company

    for company in apollo_kw_companies:
        key = company.nom.lower().strip()
        if key not in seen:
            seen[key] = company

    for company in maps_companies:
        key = company.nom.lower().strip()
        if key not in seen:
            seen[key] = company

    entreprises = list(seen.values())

    logger.info(
        f"[PIPELINE] Résultat final : {len(entreprises)} entreprises "
        f"(Apollo JT={len(apollo_jt_companies)}, "
        f"Apollo KW={len(apollo_kw_companies)}, "
        f"Maps={len(maps_companies)}, "
        f"après dédup={len(entreprises)})"
    )

    return SearchResponse(
        secteur=request.secteur,
        localisation=location,
        job_titles=job_titles_en,
        maps_keywords=maps_keywords,
        apollo_keywords=apollo_keywords_en,
        total=len(entreprises),
        entreprises=entreprises,
    )
