import logging
from fastapi import APIRouter

from app.models.schemas import SearchRequest, SearchResponse
from app.recuperation_data.keywords_service import get_job_titles
from app.recuperation_data.location import normalize_location
from app.apollo.company_search import search_companies_by_job_titles

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/search/apollo", response_model=SearchResponse)
async def search_companies_apollo(request: SearchRequest):
    """
    Pipeline Apollo simplifié :
    1. Normalisation localisation (ville ou CP) → "Ville, France"
    2. IA → job_titles_en (variantes du poste en anglais)
    3. Apollo Organization Search par job titles → entreprises
    """
    logger.info(
        f"[APOLLO PIPELINE]  secteur='{request.secteur}'  "
        f"localisation='{request.localisation}'"
    )

    location = await normalize_location(request.localisation)
    logger.info(f"[APOLLO PIPELINE] Localisation normalisée : '{location}'")

    job_titles_en = await get_job_titles(request.secteur, request.prompt, request.sectors)

    entreprises = await search_companies_by_job_titles(
        job_titles=job_titles_en,
        location=location,
    )

    if not entreprises:
        logger.warning(
            f"[APOLLO PIPELINE] Aucune entreprise pour '{request.secteur}' à '{location}'"
        )

    return SearchResponse(
        secteur=request.secteur,
        localisation=location,
        job_titles=job_titles_en,
        total=len(entreprises),
        entreprises=entreprises,
    )
