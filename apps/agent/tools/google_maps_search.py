import json
import os
import time
from langchain_core.tools import tool
from apify_client import ApifyClient

from config import RATE_LIMIT_GOOGLE_MAPS

_ACTOR_ID = "nwua9Gu5YrADL7ZDj"  # Google Maps Scraper

def _get_apify_key():
    return os.getenv("APIFY_API_KEY", "")

# Rate limiting
_last_call_time = 0.0
RATE_LIMIT_DELAY = RATE_LIMIT_GOOGLE_MAPS


def _rate_limit():
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < RATE_LIMIT_DELAY:
        time.sleep(RATE_LIMIT_DELAY - elapsed)
    _last_call_time = time.time()


@tool
def google_maps_search(
    keywords: list[str],
    location: str,
    max_per_keyword: int = 50,
) -> str:
    """Recherche des entreprises sur Google Maps via Apify.

    Utilise cet outil pour trouver des cabinets d'avocats et structures juridiques
    référencés sur Google Maps. Complémentaire à Apollo et web_search_legal.
    Particulièrement efficace pour les petits cabinets locaux.

    IMPORTANT : les keywords doivent être EN FRANCAIS (c'est Google Maps France).
    Exemples : ["cabinet avocat droit des affaires", "avocat fiscaliste"]

    Args:
        keywords: Mots-clés de recherche EN FRANCAIS (max 3 keywords).
            Exemples: ["cabinet avocat droit social Pau", "avocat droit du travail Pau"]
        location: Ville ou zone géographique, ex: "Pau, France"
        max_per_keyword: Nombre max de résultats par keyword (défaut: 50)

    Returns:
        JSON avec les entreprises trouvées (name, website_url, city, address, source).
    """
    dev_mode = os.environ.get("AGENT_DEV_MODE") == "1"
    if dev_mode:
        max_per_keyword = min(max_per_keyword, 5)

    api_key = _get_apify_key()
    if not api_key:
        return json.dumps({
            "error": "APIFY_API_KEY non configurée dans le .env",
            "companies": [],
        })

    if not keywords:
        return json.dumps({"error": "Aucun keyword fourni", "companies": []})

    # Limiter à 3 keywords pour éviter trop d'appels
    keywords = keywords[:3]

    client = ApifyClient(api_key)
    all_companies = []
    seen = set()

    for keyword in keywords:
        run_input = {
            "searchStringsArray": [keyword],
            "locationQuery": location,
            "maxCrawledPlacesPerSearch": min(max_per_keyword, 50),
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

        print(f"  [GOOGLE MAPS] Recherche '{keyword}' à '{location}'")

        try:
            _rate_limit()
            run = client.actor(_ACTOR_ID).call(run_input=run_input)
            dataset_items = client.dataset(run["defaultDatasetId"]).list_items()

            count_kw = 0
            for item in dataset_items.items:
                title = item.get("title")
                website = item.get("website")
                if not title or not website:
                    continue

                key = title.lower().strip()
                if key not in seen:
                    seen.add(key)
                    all_companies.append({
                        "name": title,
                        "website_url": website,
                        "city": location.split(",")[0].strip(),
                        "description": (item.get("categoryName") or "")[:200],
                        "source": "google_maps",
                    })
                    count_kw += 1

            print(f"  [GOOGLE MAPS] '{keyword}' → {count_kw} résultats")

        except Exception as e:
            msg = f"Erreur Google Maps pour '{keyword}': {type(e).__name__}: {e}"
            print(f"  [GOOGLE MAPS ERROR] {msg}")
            continue

    print(f"  [GOOGLE MAPS] Total : {len(all_companies)} entreprises uniques")

    return json.dumps({
        "companies": all_companies,
        "count": len(all_companies),
        "location": location,
    }, ensure_ascii=False)
