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


@router.get("/people/search/ping", tags=["apollo-test"])
async def ping_people_search() -> dict:
    """Appel minimal pour vérifier si l'accès à /v1/people/search est disponible."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.apollo.io/v1/people/search",
            json={"page": 1, "per_page": 1},
            headers={"x-api-key": settings.APOLLO_API_KEY, "Content-Type": "application/json"},
        )
        return {"status": resp.status_code, "body": resp.json()}


@router.get("/people/search/search", tags=["apollo-test"])
async def search_people_api(
    person_titles: list[str] = Query(default=[], description='Ex: "accountant", "web developer"'),
    person_seniorities: list[str] = Query(default=[], description='owner, founder, c_suite, vp, director, manager, senior, entry, intern'),
    person_locations: list[str] = Query(default=[], description='Ex: "Paris, France", "Lyon, France"'),
    organization_locations: list[str] = Query(default=["France"], description='Localisation du siège de l\'entreprise'),
    organization_num_employees_ranges: list[str] = Query(default=[], description='Ex: "10,500", "1,10"'),
    contact_email_status: list[str] = Query(default=[], description='verified, unverified, likely to engage, unavailable'),
    q_keywords: str = Query(default=None, description='Mots-clés libres'),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
) -> dict:
    """
    Recherche de personnes via Apollo POST /v1/people/search.
    Paramètres envoyés en JSON body.
    Retourne des profils avec contacts (email, phone si disponibles).
    """
    body: dict = {"page": page, "per_page": per_page}
    if person_titles:
        body["person_titles"] = person_titles
    if person_seniorities:
        body["person_seniorities"] = person_seniorities
    if person_locations:
        body["person_locations"] = person_locations
    if organization_locations:
        body["organization_locations"] = organization_locations
    if organization_num_employees_ranges:
        body["organization_num_employees_ranges"] = organization_num_employees_ranges
    if contact_email_status:
        body["contact_email_status"] = contact_email_status
    if q_keywords:
        body["q_keywords"] = q_keywords

    logger.info(f"[APOLLO TEST people/search] body: {body}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.apollo.io/v1/people/search",
            json=body,
            headers={"x-api-key": settings.APOLLO_API_KEY, "Content-Type": "application/json"},
        )
        data = resp.json()
        logger.info(f"[APOLLO TEST people/search] status={resp.status_code} total_entries={data.get('pagination', {}).get('total_entries')}")
        return {"status": resp.status_code, "body": data}
