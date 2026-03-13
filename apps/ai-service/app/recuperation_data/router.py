import logging
from fastapi import APIRouter, HTTPException

from app.models.schemas import Company, SearchRequest, SearchResponse
from app.recuperation_data import geo, keywords_service
from app.recuperation_data.google_places import google_places_service
from app.recuperation_data.keywords_service import get_apollo_search_params
from app.recuperation_data.location import normalize_location
from app.apollo.company_search import search_companies_by_keywords
from app.apollo.company_filter import filter_keyword_companies

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/search/apollo", response_model=SearchResponse)
async def search_companies_apollo(request: SearchRequest):
    """
    Pipeline Apollo :
    1. Normalisation localisation (ville ou CP) → "Ville, France"
    2. IA → keyword_tags Apollo (secteurs en anglais)
    3. Apollo Organization Search → nom + site web
    """
    logger.info(
        f"[APOLLO PIPELINE]  secteur='{request.secteur}'  "
        f"localisation='{request.localisation}'"
    )

    location = await normalize_location(request.localisation)
    logger.info(f"[APOLLO PIPELINE] Localisation normalisée : '{location}'")

    keyword_tags, job_titles_en = await get_apollo_search_params(request.secteur, request.prompt)

    entreprises = await search_companies_by_keywords(
        keyword_tags=keyword_tags,
        location=location,
        job_titles=job_titles_en,
    )

    entreprises = await filter_keyword_companies(
        companies=entreprises,
        job_title=request.secteur,
        user_prompt=request.prompt,
    )

    if not entreprises:
        logger.warning(
            f"[APOLLO PIPELINE] Aucune entreprise pour '{request.secteur}' à '{location}'"
        )

    return SearchResponse(
        secteur=request.secteur,
        localisation=location,
        keywords=keyword_tags,
        total=len(entreprises),
        entreprises=entreprises,
    )


@router.post("/search", response_model=SearchResponse)
async def search_companies(request: SearchRequest):
    """
    Pipeline de récupération des entreprises :
    1. Géocodage localisation → (lat, lng)
    2. IA (OVH/Qwen) → mots-clés enrichis selon la granularité
    3. Google Places → recherche parallèle par mots-clés + rayon
    4. Retourne toutes les entreprises trouvées
    """
    logger.info(
        f"[PIPELINE]  secteur='{request.secteur}'  "
        f"localisation='{request.localisation}'  "
        f"radius={request.radius}km"
    )

    # 1. Géocodage
    try:
        lat, lng = await geo.geocode(request.localisation)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # 2. Mots-clés via IA + jobTitle de l'utilisateur toujours inclus en premier
    kws_ia = await keywords_service.get_keywords(request.secteur, request.prompt)
    # Le jobTitle saisi par l'user est garanti dans la liste (sans doublon)
    kws_ia_lower = {k.lower() for k in kws_ia}
    kws = (
        [request.secteur] if request.secteur.lower() not in kws_ia_lower else []
    ) + kws_ia

    # 3. Google Places — on ne met PAS le nom de ville dans la query.
    #    Le paramètre location+radius guide déjà Google vers la zone.
    #    Ajouter le nom de ville (ex: "Paris") fait que Google retourne
    #    des résultats de toute la ville, rendant le filtre par rayon
    #    et le grid search inefficaces.
    places = await google_places_service.search_multi_keywords(
        keywords=kws,
        lat=lat,
        lng=lng,
        radius_m=request.radius * 1000,
    )

    entreprises = [
        Company(
            nom=p.get("nom", ""),
            adresse=p.get("adresse"),
            site_web=p.get("site_web"),
            telephone=p.get("telephone"),
            source=p.get("source"),
        )
        for p in places
    ]

    return SearchResponse(
        secteur=request.secteur,
        localisation=request.localisation,
        keywords=kws,
        total=len(entreprises),
        entreprises=entreprises,
    )
