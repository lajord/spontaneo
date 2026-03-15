import logging

from app.apollo.client import ApolloClient
from app.core.config import settings
from app.models.schemas import Company

logger = logging.getLogger(__name__)

_MAX_PAGES = 5  # cap à 500 entreprises (100 * 5) — Apollo trie par pertinence


async def _fetch_all_pages(
    client: ApolloClient,
    seen: dict[str, Company],
    per_page: int,
    source: str = "apollo_jobtitle",
    **kwargs,
) -> None:
    """Pagine sur toutes les pages Apollo et remplit `seen`."""
    page = 1
    total_pages = 1

    while page <= min(total_pages, _MAX_PAGES):
        try:
            data = await client.search_companies(page=page, per_page=per_page, **kwargs)
        except Exception as e:
            logger.error(f"[APOLLO SEARCH] page {page} — erreur: {e}")
            break

        orgs = data.get("organizations", [])
        pagination = data.get("pagination", {})
        total_pages = pagination.get("total_pages", 1)

        logger.info(
            f"[APOLLO SEARCH] page {page}/{min(total_pages, _MAX_PAGES)}"
            f" → {len(orgs)} résultats ({len(seen)} déjà vus)"
        )

        for org in orgs:
            name = org.get("name")
            if not name:
                continue
            key = name.lower().strip()
            if key not in seen:
                seen[key] = Company(
                    nom=name,
                    site_web=org.get("website_url"),
                    adresse=org.get("raw_address"),
                    source=source,
                )

        page += 1


async def search_companies_by_job_titles(
    job_titles: list[str],
    location: str,
    per_page: int = 100,
) -> list[Company]:
    """
    Recherche Apollo par job titles uniquement.
    Retourne les entreprises ayant des offres d'emploi actives pour ces titres de poste.
    """
    client = ApolloClient(settings.APOLLO_API_KEY)

    try:
        await _fetch_all_pages(
            client,
            seen=(seen := {}),
            per_page=per_page,
            organization_locations=[location],
            q_organization_job_titles=job_titles,
        )
    finally:
        await client.close()

    result = list(seen.values())
    logger.info(f"[APOLLO SEARCH] Total : {len(result)} entreprises pour '{location}'")
    return result


async def search_companies_by_keywords(
    keywords: list[str],
    location: str,
    per_page: int = 100,
) -> list[Company]:
    """
    Recherche Apollo par keyword tags.
    Retourne les entreprises dont le profil correspond aux tags fournis.
    """
    if not keywords:
        logger.info("[APOLLO KEYWORD SEARCH] Aucun keyword fourni, skip")
        return []

    client = ApolloClient(settings.APOLLO_API_KEY)

    try:
        await _fetch_all_pages(
            client,
            seen=(seen := {}),
            per_page=per_page,
            source="apollo_keyword",
            organization_locations=[location],
            q_organization_keyword_tags=keywords,
        )
    finally:
        await client.close()

    result = list(seen.values())
    logger.info(f"[APOLLO KEYWORD SEARCH] Total : {len(result)} entreprises pour '{location}'")
    return result
