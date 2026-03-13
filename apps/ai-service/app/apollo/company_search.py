import logging

from app.apollo.client import ApolloClient
from app.core.config import settings
from app.models.schemas import Company

logger = logging.getLogger(__name__)

_MAX_PAGES = 5  # cap à 500 entreprises par appel (100 * 5) — Apollo trie par pertinence, pages 6+ = bruit


async def _fetch_all_pages(
    client: ApolloClient,
    source: str,
    seen: dict[str, Company],
    per_page: int,
    **kwargs,
) -> None:
    """Pagine sur toutes les pages Apollo pour un appel donné et remplit `seen`."""
    page = 1
    total_pages = 1  # sera mis à jour après le premier appel

    while page <= min(total_pages, _MAX_PAGES):
        try:
            data = await client.search_companies(page=page, per_page=per_page, **kwargs)
        except Exception as e:
            logger.error(f"[APOLLO SEARCH] {source} page {page} — erreur: {e}")
            break

        orgs = data.get("organizations", [])
        pagination = data.get("pagination", {})
        total_pages = pagination.get("total_pages", 1)

        logger.info(
            f"[APOLLO SEARCH] {source} page {page}/{min(total_pages, _MAX_PAGES)}"
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


async def search_companies_by_keywords(
    keyword_tags: list[str],
    location: str,
    job_titles: list[str] | None = None,
    per_page: int = 100,
) -> list[Company]:
    """
    Deux appels Apollo indépendants (OR logique) mergés, avec pagination complète.

    Appel B — job_titles (EN PREMIER — priorité dans la dédup)
      → Entreprises avec des offres d'emploi ACTIVES pour ce profil.
      → source="apollo_jobtitle"

    Appel A — keyword_tags
      → Entreprises du bon secteur, qu'elles aient ou non une offre active.
      → source="apollo_keyword"

    Si une entreprise apparaît dans les deux, elle garde "apollo_jobtitle".
    """
    client = ApolloClient(settings.APOLLO_API_KEY)
    seen: dict[str, Company] = {}

    try:
        if job_titles:
            await _fetch_all_pages(
                client,
                source="apollo_jobtitle",
                seen=seen,
                per_page=per_page,
                organization_locations=[location],
                q_organization_job_titles=job_titles,
            )

        if keyword_tags:
            await _fetch_all_pages(
                client,
                source="apollo_keyword",
                seen=seen,
                per_page=per_page,
                organization_locations=[location],
                q_organization_keyword_tags=keyword_tags,
            )

    finally:
        await client.close()

    result = list(seen.values())
    logger.info(f"[APOLLO SEARCH] Total après merge : {len(result)} entreprises pour '{location}'")
    return result
