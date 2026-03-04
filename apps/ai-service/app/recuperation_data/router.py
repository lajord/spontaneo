import logging
from fastapi import APIRouter, HTTPException

from app.models.schemas import Company, SearchRequest, SearchResponse
from app.recuperation_data import geo, keywords_service
from app.recuperation_data.google_places import google_places_service

logger = logging.getLogger(__name__)
router = APIRouter()


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

    # 3. Google Places — on ajoute la ville dans chaque query pour forcer Google
    #    à cibler la zone textuellement (le radius seul n'est qu'un biais)
    localisation_label = request.localisation.split(",")[0].strip()  # "Pau, France" → "Pau"
    kws_with_city = [f"{kw} {localisation_label}" for kw in kws]

    places = await google_places_service.search_multi_keywords(
        keywords=kws_with_city,
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
