import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_DELAY = 5  # secondes


class ApolloClient:
    """Centre de contrôle pour tous les appels Apollo.io."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.apollo.io"
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Requête HTTP avec retry sur 429."""
        client = self._get_client()
        url = f"{self.base_url}{path}"

        for attempt in range(_MAX_RETRIES):
            try:
                response = await client.request(
                    method, url, json=json, params=params,
                )

                if response.status_code == 429:
                    wait = _BASE_DELAY * (attempt + 1)
                    logger.warning(
                        f"[APOLLO] 429 rate limit — tentative {attempt + 1}/{_MAX_RETRIES}, "
                        f"retry dans {wait}s..."
                    )
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                logger.error(f"[APOLLO] {method} {path} → {e.response.status_code}: {e.response.text[:200]}")
                raise
            except httpx.RequestError as e:
                logger.error(f"[APOLLO] {method} {path} → erreur réseau: {e}")
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_BASE_DELAY * (attempt + 1))
                    continue
                raise

        raise RuntimeError(f"[APOLLO] {method} {path} — échec après {_MAX_RETRIES} tentatives")

    # ── People Match ─────────────────────────────────────────────────────────

    async def match_person(
        self,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        domain: str | None = None,
        email: str | None = None,
        organization_name: str | None = None,
        linkedin_url: str | None = None,
        reveal_personal_emails: bool = False,
        reveal_phone_number: bool = False,
    ) -> dict:
        """POST /api/v1/people/match — Enrichir une personne."""
        body: dict = {}
        if first_name:
            body["first_name"] = first_name
        if last_name:
            body["last_name"] = last_name
        if domain:
            body["domain"] = domain
        if email:
            body["email"] = email
        if organization_name:
            body["organization_name"] = organization_name
        if linkedin_url:
            body["linkedin_url"] = linkedin_url
        if reveal_personal_emails:
            body["reveal_personal_emails"] = True
        if reveal_phone_number:
            body["reveal_phone_number"] = True

        logger.info(f"[APOLLO] match_person: {first_name} {last_name} @ {domain or organization_name}")
        return await self._request("POST", "/api/v1/people/match", json=body)

    # ── Organization Enrichment ──────────────────────────────────────────────

    async def enrich_organization(self, *, domain: str) -> dict:
        """GET /api/v1/organizations/enrich — Enrichir une entreprise par domaine."""
        logger.info(f"[APOLLO] enrich_organization: {domain}")
        return await self._request("GET", "/api/v1/organizations/enrich", params={"domain": domain})

    # ── People Search ────────────────────────────────────────────────────────

    async def search_people(
        self,
        *,
        person_titles: list[str] | None = None,
        person_seniorities: list[str] | None = None,
        person_departments: list[str] | None = None,
        person_locations: list[str] | None = None,
        organization_domains: list[str] | None = None,
        organization_ids: list[str] | None = None,
        q_keywords: str | None = None,
        page: int = 1,
        per_page: int = 10,
    ) -> dict:
        """POST /api/v1/mixed_people/search — Rechercher des personnes."""
        body: dict = {"page": page, "per_page": per_page}
        if person_titles:
            body["person_titles"] = person_titles
        if person_seniorities:
            body["person_seniorities"] = person_seniorities
        if person_departments:
            body["person_departments"] = person_departments
        if person_locations:
            body["person_locations"] = person_locations
        if organization_domains:
            body["organization_domains"] = organization_domains
        if organization_ids:
            body["organization_ids"] = organization_ids
        if q_keywords:
            body["q_keywords"] = q_keywords

        logger.info(f"[APOLLO] search_people: page={page}")
        return await self._request("POST", "/api/v1/mixed_people/search", json=body)

    # ── Company Search ───────────────────────────────────────────────────────

    async def search_companies(
        self,
        *,
        q_organization_name: str | None = None,
        organization_locations: list[str] | None = None,
        organization_num_employees_ranges: list[str] | None = None,
        organization_industry_tag_ids: list[str] | None = None,
        q_organization_keyword_tags: list[str] | None = None,
        page: int = 1,
        per_page: int = 10,
    ) -> dict:
        """POST /api/v1/mixed_companies/search — Rechercher des entreprises."""
        body: dict = {"page": page, "per_page": per_page}
        if q_organization_name:
            body["q_organization_name"] = q_organization_name
        if organization_locations:
            body["organization_locations"] = organization_locations
        if organization_num_employees_ranges:
            body["organization_num_employees_ranges"] = organization_num_employees_ranges
        if organization_industry_tag_ids:
            body["organization_industry_tag_ids"] = organization_industry_tag_ids
        if q_organization_keyword_tags:
            body["q_organization_keyword_tags"] = q_organization_keyword_tags

        logger.info(f"[APOLLO] search_companies: {q_organization_name}, page={page}")
        return await self._request("POST", "/api/v1/mixed_companies/search", json=body)

    # ── Job Postings ─────────────────────────────────────────────────────────

    async def get_job_postings(
        self,
        *,
        organization_id: str,
        page: int = 1,
        per_page: int = 10,
    ) -> dict:
        """GET /api/v1/organizations/{id}/job_postings — Offres d'emploi."""
        logger.info(f"[APOLLO] get_job_postings: org={organization_id}, page={page}")
        return await self._request(
            "GET",
            f"/api/v1/organizations/{organization_id}/job_postings",
            params={"page": page, "per_page": per_page},
        )
