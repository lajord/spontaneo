import logging
import httpx
from fastapi import APIRouter, Query
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/mixed_companies/search/by-job-titles", tags=["apollo-test"])
async def search_by_job_titles(
    job_titles: list[str] = Query(description='Ex: "data analyst", "sales manager"'),
    location: str = Query(default="France", description='Ex: "France", "Paris, France"'),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
) -> dict:
    """
    Recherche les entreprises ayant des offres actives pour ces job titles.
    Utilise q_organization_job_titles[] + organization_locations[].
    """
    params = [
        ("page", page),
        ("per_page", per_page),
        ("organization_locations[]", location),
    ]
    for title in job_titles:
        params.append(("q_organization_job_titles[]", title))

    logger.info(f"[APOLLO TEST] params: {params}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.apollo.io/api/v1/organizations/search",
            params=params,
            headers={"x-api-key": settings.APOLLO_API_KEY},
        )
        resp.raise_for_status()
        return resp.json()


@router.get("/mixed_companies/search/ping", tags=["apollo-test"])
async def ping_companies_search() -> dict:
    """Appel minimal pour vérifier si l'accès à /organizations/search est disponible."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.apollo.io/api/v1/organizations/search",
            json={"page": 1, "per_page": 1},
            headers={"x-api-key": settings.APOLLO_API_KEY, "Content-Type": "application/json"},
        )
        return {"status": resp.status_code, "body": resp.json()}


@router.get("/mixed_people/api_search/ping", tags=["apollo-test"])
async def ping_people_search() -> dict:
    """Appel minimal pour vérifier si l'accès à /mixed_people/api_search est disponible."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.apollo.io/api/v1/mixed_people/api_search",
            json={"page": 1, "per_page": 1},
            headers={"x-api-key": settings.APOLLO_API_KEY, "Content-Type": "application/json"},
        )
        return {"status": resp.status_code, "body": resp.json()}
