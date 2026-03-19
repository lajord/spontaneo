import asyncio
import logging

from apify_client import ApifyClientAsync

from app.core.config import settings
from app.models.schemas import Company

logger = logging.getLogger(__name__)

_ACTOR_ID = "nwua9Gu5YrADL7ZDj"  # Google Maps Scraper


async def _search_single_keyword(
    client: ApifyClientAsync,
    keyword: str,
    location: str,
    max_results: int,
) -> list[Company]:
    """Un appel Apify pour UN seul keyword."""
    run_input = {
        "searchStringsArray": [keyword],
        "locationQuery": location,
        "maxCrawledPlacesPerSearch": max_results,
        "language": "fr",
        "website": "withWebsite",
        "skipClosedPlaces": False,
        "scrapePlaceDetailPage": False,
        "scrapeTableReservationProvider": False,
        "includeWebResults": False,
        "scrapeDirectories": False,
        "scrapeContacts": False,
        "scrapeSocialMediaProfiles": {
            "facebooks": False,
            "instagrams": False,
            "youtubes": False,
            "tiktoks": False,
            "twitters": False,
        },
        "maximumLeadsEnrichmentRecords": 0,
        "maxReviews": 0,
        "maxImages": 0,
        "scrapeImageAuthors": False,
        "scrapeReviewsPersonalData": False,
    }

    logger.info(f"[GOOGLE MAPS] Recherche '{keyword}' à '{location}'")

    try:
        run = await client.actor(_ACTOR_ID).call(run_input=run_input)
        dataset_items = await client.dataset(run["defaultDatasetId"]).list_items()

        companies = []
        for item in dataset_items.items:
            title = item.get("title")
            website = item.get("website")
            if not title or not website:
                continue
            companies.append(Company(
                nom=title,
                site_web=website,
                adresse=item.get("address"),
                telephone=item.get("phone"),
                source="google_maps",
                type_activite=item.get("categoryName"),
            ))

        logger.info(f"[GOOGLE MAPS] '{keyword}' → {len(companies)} résultats")
        return companies

    except Exception as e:
        logger.error(f"[GOOGLE MAPS] Erreur pour '{keyword}' : {e}")
        return []


async def search_google_maps(
    keywords: list[str],
    location: str,
    max_per_keyword: int = 50,
) -> list[Company]:
    """
    Recherche d'entreprises via Apify Google Maps Scraper.
    1 appel API par keyword, exécutés en parallèle.
    Dédoublonne les résultats par nom.
    """
    if not settings.APIFY_API_KEY:
        logger.warning("[GOOGLE MAPS] APIFY_API_KEY manquante — skip")
        return []

    if not keywords:
        return []

    client = ApifyClientAsync(settings.APIFY_API_KEY)

    logger.info(
        f"[GOOGLE MAPS] Lancement de {len(keywords)} recherches — "
        f"keywords={keywords}  location='{location}'"
    )

    results = await asyncio.gather(*[
        _search_single_keyword(client, kw, location, max_per_keyword)
        for kw in keywords
    ])

    # Dédup par nom
    seen: dict[str, Company] = {}
    for company_list in results:
        for company in company_list:
            key = company.nom.lower().strip()
            if key not in seen:
                seen[key] = company

    result = list(seen.values())
    logger.info(f"[GOOGLE MAPS] Total : {len(result)} entreprises uniques (avec site web)")
    return result
