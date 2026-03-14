import logging

from apify_client import ApifyClientAsync

from app.core.config import settings
from app.models.schemas import Company

logger = logging.getLogger(__name__)

_ACTOR_ID = "nwua9Gu5YrADL7ZDj"  # Google Maps Scraper


async def search_google_maps(
    keywords: list[str],
    location: str,
    max_per_keyword: int = 50,
) -> list[Company]:
    """
    Recherche d'entreprises via Apify Google Maps Scraper.
    Ne retourne que les entreprises ayant un site web.
    """
    if not settings.APIFY_API_KEY:
        logger.warning("[GOOGLE MAPS] APIFY_API_KEY manquante — skip")
        return []

    client = ApifyClientAsync(settings.APIFY_API_KEY)

    run_input = {
        "searchStringsArray": keywords,
        "locationQuery": location,
        "maxCrawledPlacesPerSearch": max_per_keyword,
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

    logger.info(
        f"[GOOGLE MAPS] Lancement scraper — keywords={keywords}  "
        f"location='{location}'  max_per_keyword={max_per_keyword}"
    )

    try:
        run = await client.actor(_ACTOR_ID).call(run_input=run_input)

        seen: dict[str, Company] = {}
        dataset_items = await client.dataset(run["defaultDatasetId"]).list_items()

        for item in dataset_items.items:
            title = item.get("title")
            website = item.get("website")
            if not title or not website:
                continue

            key = title.lower().strip()
            if key not in seen:
                seen[key] = Company(
                    nom=title,
                    site_web=website,
                    adresse=item.get("address"),
                    telephone=item.get("phone"),
                    source="google_maps",
                )

        result = list(seen.values())
        logger.info(f"[GOOGLE MAPS] {len(result)} entreprises trouvées (avec site web)")
        return result

    except Exception as e:
        logger.error(f"[GOOGLE MAPS] Erreur scraper : {e}")
        return []
