import logging
import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional
from app.core.config import settings
from app.apollo.client import ApolloClient

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Fill missing emails via bulk_match ───────────────────────────────────────

class FillEmailItem(BaseModel):
    ref: str  # opaque reference retournée telle quelle (ex: "companyId:contactIndex")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    domain: Optional[str] = None
    organization_name: Optional[str] = None


class FillEmailResult(BaseModel):
    ref: str
    mail: Optional[str] = None
    email_verified: bool = False


class FillEmailRequest(BaseModel):
    items: list[FillEmailItem]


class FillEmailResponse(BaseModel):
    results: list[FillEmailResult]


@router.post("/apollo/fill-emails", response_model=FillEmailResponse, tags=["apollo"])
async def fill_missing_emails(request: FillEmailRequest) -> FillEmailResponse:
    """Apollo bulk_match pour récupérer les emails manquants.

    Prend une liste de contacts identifiés (nom/prénom + domaine) sans email
    et tente de récupérer leur email pro via Apollo bulk_match.
    Chaque item est renvoyé avec son ref opaque pour que le caller puisse mapper.
    """
    empty = FillEmailResponse(results=[FillEmailResult(ref=item.ref) for item in request.items])

    if not settings.APOLLO_API_KEY:
        logger.info("[APOLLO FILL] Clé API absente — skip")
        return empty

    if not request.items:
        return FillEmailResponse(results=[])

    details = []
    for item in request.items:
        detail: dict = {}
        if item.first_name:
            detail["first_name"] = item.first_name
        if item.last_name:
            detail["last_name"] = item.last_name
        if item.domain:
            detail["domain"] = item.domain
        if item.organization_name:
            detail["organization_name"] = item.organization_name
        details.append(detail)

    client = ApolloClient(api_key=settings.APOLLO_API_KEY)
    results: list[FillEmailResult] = []
    try:
        response = await client.bulk_match(details=details, reveal_personal_emails=True)
        matches = response.get("matches") or []

        for i, item in enumerate(request.items):
            match = matches[i] if i < len(matches) else None
            person = (match or {}).get("person")
            if person and person.get("email"):
                email_status = person.get("email_status", "")
                results.append(FillEmailResult(
                    ref=item.ref,
                    mail=person["email"],
                    email_verified=(email_status == "verified"),
                ))
            else:
                results.append(FillEmailResult(ref=item.ref))

    except Exception as e:
        logger.error(f"[APOLLO FILL] bulk_match échoué: {e}")
        return empty
    finally:
        await client.close()

    filled = sum(1 for r in results if r.mail)
    logger.info(f"[APOLLO FILL] {filled}/{len(request.items)} emails récupérés")

    return FillEmailResponse(results=results)


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
