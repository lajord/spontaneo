import asyncio
import json
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import SearchRequest, Company
from app.recuperation_data.keywords_service import build_search_params
from app.recuperation_data.location import normalize_location
from app.recuperation_data.company_filter import filter_companies
from app.apollo.company_search import search_companies_by_job_titles, search_companies_by_keywords
from app.google_maps.scraper import search_google_maps

logger = logging.getLogger(__name__)
router = APIRouter()


def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/search/apollo")
async def search_companies_apollo(request: SearchRequest):
    """
    Pipeline streaming :
    1. Normalisation localisation
    2. Appel IA stratégique → paramètres de recherche
    3. Apollo JT → envoyé immédiatement (pas de filtre)
    4. Apollo KW + Google Maps → dédup → filtre IA (1 appel batch) → envoyé
    5. Event "done"
    """

    async def event_stream():
        sectors = request.sectors or []
        categories = request.categories or []
        total = 0

        logger.info(
            f"[PIPELINE]  secteur='{request.secteur}'  "
            f"localisation='{request.localisation}'  "
            f"sectors={sectors}  categories={categories}"
        )

        # 1. Normaliser la localisation
        location = await normalize_location(request.localisation)
        logger.info(f"[PIPELINE] Localisation normalisée : '{location}'")

        # 2. Appel IA stratégique
        params = await build_search_params(
            secteur=request.secteur,
            sectors=sectors if sectors else None,
            categories=categories if categories else None,
        )

        job_titles_en = params["apollo_job_titles"]
        apollo_keywords_en = params["apollo_keywords"]
        maps_keywords = params["google_maps_keywords"]

        yield _sse_event({
            "type": "params",
            "job_titles": job_titles_en,
            "apollo_keywords": apollo_keywords_en,
            "maps_keywords": maps_keywords,
        })

        # 3. Apollo JT — envoyé immédiatement sans filtre
        apollo_jt_companies = await search_companies_by_job_titles(
            job_titles=job_titles_en, location=location
        )

        seen: set[str] = set()
        for company in apollo_jt_companies:
            key = company.nom.lower().strip()
            if key not in seen:
                seen.add(key)
                total += 1
                yield _sse_event({
                    "type": "company",
                    "company": company.model_dump(),
                })

        logger.info(f"[PIPELINE] Apollo JT : {len(apollo_jt_companies)} envoyées")

        # 4. Apollo KW + Google Maps en parallèle
        apollo_kw_companies, maps_companies = await asyncio.gather(
            search_companies_by_keywords(keywords=apollo_keywords_en, location=location),
            search_google_maps(keywords=maps_keywords, location=location, max_per_keyword=50),
        )

        # Dédup KW + Maps (exclure ceux déjà dans Apollo JT)
        to_filter: list[Company] = []
        for company in apollo_kw_companies:
            key = company.nom.lower().strip()
            if key not in seen:
                seen.add(key)
                to_filter.append(company)

        for company in maps_companies:
            key = company.nom.lower().strip()
            if key not in seen:
                seen.add(key)
                to_filter.append(company)

        logger.info(
            f"[PIPELINE] À filtrer : {len(to_filter)} entreprises "
            f"(Apollo KW={len(apollo_kw_companies)}, Maps={len(maps_companies)})"
        )

        yield _sse_event({"type": "filtering", "count": len(to_filter)})

        # 5. Filtre IA — un seul appel batch
        filtered = await filter_companies(
            companies=to_filter,
            secteur=request.secteur,
            sectors=sectors if sectors else None,
            categories=categories if categories else None,
            user_instructions=request.prompt if request.prompt else None,
        )

        for company in filtered:
            total += 1
            yield _sse_event({
                "type": "company",
                "company": company.model_dump(),
            })

        logger.info(
            f"[PIPELINE] Filtre terminé : {len(filtered)}/{len(to_filter)} gardées. "
            f"Total final : {total}"
        )

        # 6. Done
        yield _sse_event({"type": "done", "total": total})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
