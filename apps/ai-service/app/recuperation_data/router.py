import asyncio
import json
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import SearchRequest
from app.recuperation_data.keywords_service import build_search_params
from app.recuperation_data.location import normalize_location
from app.recuperation_data.company_filter import dedup_companies, rank_companies
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
    3. Apollo JT + Apollo KW + Google Maps en parallèle
    4. Déduplication normalisée (nom + code postal) sur toutes les sources
    5. Ranking IA avec web search (score 0-100) sur toutes les entreprises
    6. Stream tier "high" (≥70) en premier, puis tier "low" (50-69)
    7. Event "done"
    """

    async def event_stream():
        sectors = request.sectors or []
        categories = request.categories or []

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

        # 3. Apollo JT + Apollo KW + Google Maps en parallèle
        apollo_jt_companies, apollo_kw_companies, maps_companies = await asyncio.gather(
            search_companies_by_job_titles(job_titles=job_titles_en, location=location),
            search_companies_by_keywords(keywords=apollo_keywords_en, location=location),
            search_google_maps(keywords=maps_keywords, location=location, max_per_keyword=50),
        )

        logger.info(
            f"[PIPELINE] Collecte : Apollo JT={len(apollo_jt_companies)}, "
            f"Apollo KW={len(apollo_kw_companies)}, Maps={len(maps_companies)}"
        )

        # 4. Fusion + déduplication normalisée (nom + code postal)
        all_companies = apollo_jt_companies + apollo_kw_companies + maps_companies
        deduplicated = dedup_companies(all_companies)

        logger.info(
            f"[PIPELINE] Après dédup : {len(deduplicated)} entreprises uniques "
            f"(éliminées : {len(all_companies) - len(deduplicated)})"
        )

        yield _sse_event({"type": "ranking", "count": len(deduplicated)})

        # 5. Ranking IA avec web search sur toutes les entreprises
        ranked = await rank_companies(
            companies=deduplicated,
            secteur=request.secteur,
            sectors=sectors if sectors else None,
            categories=categories if categories else None,
            user_instructions=request.prompt if request.prompt else None,
        )

        # 6. Stream : tier "high" (≥60) d'abord, puis tier "low" (30-59)
        high = [c for c in ranked if (c.score or 0) >= 60]
        low = [c for c in ranked if 30 <= (c.score or 0) < 60]

        for company in high:
            yield _sse_event({
                "type": "company",
                "company": company.model_dump(),
                "tier": "high",
            })

        for company in low:
            yield _sse_event({
                "type": "company",
                "company": company.model_dump(),
                "tier": "low",
            })

        total = len(ranked)
        logger.info(
            f"[PIPELINE] Terminé : {total} entreprises envoyées "
            f"(high={len(high)}, low={len(low)})"
        )

        # 7. Done
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
