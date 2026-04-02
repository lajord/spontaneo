import json
import os
import time

from apify_client import ApifyClient
from langchain_core.tools import tool

from config import RATE_LIMIT_GOOGLE_MAPS

_ACTOR_ID = "nwua9Gu5YrADL7ZDj"  # Google Maps Scraper
MAX_RESULTS_PER_KEYWORD = 10


def _get_apify_key():
    return os.getenv("APIFY_API_KEY", "")


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
    max_per_keyword: int = MAX_RESULTS_PER_KEYWORD,
) -> str:
    """Recherche des entreprises sur Google Maps via Apify.

    Utilise cet outil pour trouver des cabinets d'avocats et structures juridiques
    references sur Google Maps. Complementaire a Apollo et web_search_legal.
    Particulierement efficace pour les petits cabinets locaux.

    IMPORTANT : les keywords doivent etre EN FRANCAIS (c'est Google Maps France).
    Exemples : ["cabinet avocat droit des affaires", "avocat fiscaliste"]

    Args:
        keywords: Mots-cles de recherche EN FRANCAIS (max 3 keywords).
            Exemples: ["cabinet avocat droit social Pau", "avocat droit du travail Pau"]
        location: Ville ou zone geographique, ex: "Pau, France"
        max_per_keyword: Nombre max de resultats par keyword (cape a 10)

    Returns:
        JSON avec les entreprises trouvees (name, website_url, city, address, source)
        + un resume des erreurs/messages Google Maps par keyword.
    """
    api_key = _get_apify_key()
    if not api_key:
        return json.dumps({
            "error": "APIFY_API_KEY non configuree dans le .env",
            "message": "Impossible d'appeler Google Maps sans APIFY_API_KEY.",
            "errors": ["APIFY_API_KEY non configuree dans le .env"],
            "keyword_results": [],
            "companies": [],
        }, ensure_ascii=False)

    if not keywords:
        return json.dumps({
            "error": "Aucun keyword fourni",
            "message": "Google Maps n'a recu aucun keyword.",
            "errors": ["Aucun keyword fourni"],
            "keyword_results": [],
            "companies": [],
        }, ensure_ascii=False)

    keywords = keywords[:3]
    max_per_keyword = max(1, min(max_per_keyword, MAX_RESULTS_PER_KEYWORD))

    client = ApifyClient(api_key)
    all_companies = []
    seen = set()
    keyword_summaries = []
    errors = []

    for keyword in keywords:
        run_input = {
            "searchStringsArray": [keyword],
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

        print(f"  [GOOGLE MAPS] Recherche '{keyword}' a '{location}'")

        try:
            _rate_limit()
            run = client.actor(_ACTOR_ID).call(run_input=run_input)
            dataset_items = client.dataset(run["defaultDatasetId"]).list_items()

            count_kw = 0
            raw_items_count = len(dataset_items.items)
            skipped_without_website = 0

            for item in dataset_items.items:
                title = item.get("title")
                website = item.get("website")
                if not title or not website:
                    skipped_without_website += 1
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

            print(f"  [GOOGLE MAPS] '{keyword}' -> {count_kw} resultats")
            keyword_summaries.append({
                "keyword": keyword,
                "status": "ok",
                "raw_items": raw_items_count,
                "count": count_kw,
                "skipped_without_website": skipped_without_website,
                "message": (
                    f"{count_kw} resultats exploitables"
                    if count_kw > 0
                    else (
                        "Aucun resultat exploitable avec site web."
                        if raw_items_count > 0
                        else "Aucun resultat brut retourne par Google Maps."
                    )
                ),
            })

        except Exception as e:
            msg = f"Erreur Google Maps pour '{keyword}': {type(e).__name__}: {e}"
            print(f"  [GOOGLE MAPS ERROR] {msg}")
            errors.append(msg)
            keyword_summaries.append({
                "keyword": keyword,
                "status": "error",
                "raw_items": 0,
                "count": 0,
                "skipped_without_website": 0,
                "message": msg,
            })
            continue

    print(f"  [GOOGLE MAPS] Total : {len(all_companies)} entreprises uniques")

    if all_companies:
        summary_message = f"{len(all_companies)} entreprises uniques trouvees sur Google Maps."
    elif errors:
        summary_message = "Aucun resultat exploitable. Voir errors pour le detail des echecs Google Maps."
    else:
        summary_message = (
            "Aucun resultat exploitable retourne par Google Maps. "
            "Ca peut vouloir dire: 0 resultats, requetes trop restrictives, "
            "ou fiches sans site web exploitable."
        )

    payload = {
        "message": summary_message,
        "errors": errors,
        "keyword_results": keyword_summaries,
        "companies": all_companies,
        "count": len(all_companies),
        "location": location,
    }
    if errors and not all_companies:
        payload["error"] = errors[0]

    return json.dumps(payload, ensure_ascii=False)
