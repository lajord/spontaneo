import json
import os
import time

from apify_client import ApifyClient
from langchain_core.tools import tool

from config import RATE_LIMIT_GOOGLE_MAPS
from runtime import raise_if_cancelled
from tools.candidate_store import get_candidates_rows, save_candidates_batch


_ACTOR_ID = "nwua9Gu5YrADL7ZDj"
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


def _current_total() -> int:
    return len(get_candidates_rows())


def _preview_companies(companies: list[dict], max_items: int = 3) -> str:
    preview = []
    for company in companies[:max_items]:
        name = company.get("name", "").strip()
        website = company.get("websiteUrl", "").strip()
        if name and website:
            preview.append(f"{name} -> {website}")
        elif name:
            preview.append(name)
    return " | ".join(preview)


def _format_report(
    found_count: int,
    save_result: dict,
    companies: list[dict] | None = None,
    errors: list[str] | None = None,
) -> str:
    if not save_result.get("ok"):
        return (
            f"google_maps_search_and_save: {found_count} entreprises trouvees, mais sauvegarde echouee. "
            f"{save_result.get('error', 'Erreur inconnue.')}"
        )

    rejected = save_result.get("rejected", 0)
    reject_note = f", rejected: {rejected}" if rejected else ""
    preview = _preview_companies(companies or [])
    report = (
        f"google_maps_search_and_save: added: {save_result.get('added', 0)} "
        f"(found: {found_count}, total: {save_result.get('total', 0)}, "
        f"duplicates: {save_result.get('duplicates', 0)}{reject_note})."
    )
    if errors:
        report += f"\nsource_errors: {' | '.join(errors[:2])}"
    if preview:
        report += f"\nsource_preview: {preview}"
    return report


@tool
def google_maps_search_and_save(
    keywords: list[str],
    location: str,
    max_per_keyword: int = MAX_RESULTS_PER_KEYWORD,
) -> str:
    """Recherche des entreprises sur Google Maps ET les sauvegarde immediatement.

    Utilise ce tool pour les cabinets, petites structures et recherches locales.
    Il remplace la sequence `google_maps_search` -> `save_candidates`.

    IMPORTANT :
    - les keywords doivent etre en francais ;
    - le tool sauvegarde deja en base de donnees ;
    - lis son compte-rendu pour connaitre `added` et `total`.

    Returns:
        Texte court de la forme :
        `google_maps_search_and_save: added: X (found: Y, total: Z, duplicates: D).`
    """
    raise_if_cancelled()

    api_key = _get_apify_key()
    if not api_key:
        return (
            "google_maps_search_and_save: APIFY_API_KEY non configuree dans le .env. "
            f"added: 0 (found: 0, total: {_current_total()}, duplicates: 0)."
        )

    if not keywords:
        return (
            "google_maps_search_and_save: Aucun keyword fourni. "
            f"added: 0 (found: 0, total: {_current_total()}, duplicates: 0)."
        )

    keywords = keywords[:3]
    max_per_keyword = max(1, min(max_per_keyword, MAX_RESULTS_PER_KEYWORD))

    client = ApifyClient(api_key)
    all_companies = []
    seen = set()
    errors = []

    for keyword in keywords:
        raise_if_cancelled()
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

            for item in dataset_items.items:
                title = item.get("title")
                website = item.get("website")
                if not title or not website:
                    continue

                key = title.lower().strip()
                if key in seen:
                    continue

                seen.add(key)
                all_companies.append({
                    "name": title,
                    "websiteUrl": website,
                    "city": location.split(",")[0].strip(),
                    "description": (item.get("categoryName") or "")[:200],
                    "source": "google_maps",
                })

        except Exception as e:
            msg = f"Erreur Google Maps pour '{keyword}': {type(e).__name__}: {e}"
            print(f"  [GOOGLE MAPS ERROR] {msg}")
            errors.append(msg)

    print(f"  [GOOGLE MAPS] Total : {len(all_companies)} entreprises uniques")
    if not all_companies:
        report = f"google_maps_search_and_save: added: 0 (found: 0, total: {_current_total()}, duplicates: 0)."
        if errors:
            report += f"\nsource_errors: {' | '.join(errors[:2])}"
        return report

    save_result = save_candidates_batch(all_companies)
    return _format_report(len(all_companies), save_result, all_companies, errors)
