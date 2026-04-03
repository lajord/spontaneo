import json
import os
import time

from langchain_core.tools import tool
from openai import OpenAI

from config import RATE_LIMIT_PERPLEXITY, TOOL_MAX_RETRIES, TOOL_RETRY_BASE_DELAY
from runtime import raise_if_cancelled
from tools.candidate_store import get_candidates_rows, save_candidates_batch


def _get_perplexity_key():
    return os.getenv("PERPLEXITY_API_KEY", "")


_last_call_time = 0.0
RATE_LIMIT_DELAY = RATE_LIMIT_PERPLEXITY
_MAX_RETRIES = TOOL_MAX_RETRIES
_BASE_DELAY = TOOL_RETRY_BASE_DELAY


def _rate_limit():
    """Respecte le rate limit Perplexity."""
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


def _safe_excerpt(text: str, max_chars: int = 300) -> str:
    compact = " ".join((text or "").split())
    return compact[:max_chars]


def _format_report(found_count: int, save_result: dict, companies: list[dict] | None = None) -> str:
    if not save_result.get("ok"):
        return (
            f"web_search_legal_and_save: {found_count} entreprises trouvees, mais sauvegarde echouee. "
            f"{save_result.get('error', 'Erreur inconnue.')}"
        )

    rejected = save_result.get("rejected", 0)
    reject_note = f", rejected: {rejected}" if rejected else ""
    preview = _preview_companies(companies or [])
    report = (
        f"web_search_legal_and_save: added: {save_result.get('added', 0)} "
        f"(found: {found_count}, total: {save_result.get('total', 0)}, "
        f"duplicates: {save_result.get('duplicates', 0)}{reject_note})."
    )
    if preview:
        report += f"\nsource_preview: {preview}"
    return report


@tool
def web_search_legal_and_save(
    location: str,
    organization_types: list[str] = None,
    legal_specialties: list[str] = None,
    max_results: int = 50,
) -> str:
    """Recherche exhaustive sur Perplexity puis sauvegarde immediatement en DB.

    Utilise ce tool pour trouver un maximum d'organisations juridiques avec
    leur site officiel. Il remplace la sequence
    `web_search_legal` -> parse JSON -> `save_candidates`.

    IMPORTANT :
    - ce tool retourne un compte-rendu court avec `added` et `total` ;
    - `total` correspond au total actuel en base de donnees ;
    - privilegie les requetes qui permettent d'obtenir des sites officiels.

    Returns:
        Texte court de la forme :
        `web_search_legal_and_save: added: X (found: Y, total: Z, duplicates: D).`
    """
    raise_if_cancelled()

    api_key = _get_perplexity_key()
    if not api_key:
        return (
            "web_search_legal_and_save: PERPLEXITY_API_KEY non configuree dans le .env. "
            f"added: 0 (found: 0, total: {_current_total()}, duplicates: 0)."
        )

    if not organization_types:
        organization_types = [
            "cabinets d'avocats",
            "etudes notariales",
            "cabinets de conseil juridique",
        ]

    types_str = ", ".join(organization_types)
    specialty_clause = ""
    if legal_specialties:
        specialty_clause = (
            f"\nSPECIALITES RECHERCHEES : {', '.join(legal_specialties)}. "
            f"Trouve UNIQUEMENT les cabinets specialises dans ces domaines."
        )

    system_message = (
        "Tu es un assistant expert en recherche exhaustive d'organisations juridiques francaises. "
        "Tu fouilles TOUTES les sources possibles pour trouver un MAXIMUM de resultats. "
        "Tu reponds UNIQUEMENT en JSON valide, sans texte supplementaire, sans markdown."
    )

    user_message = (
        f"Trouve le MAXIMUM de {types_str} a {location} (France). "
        f"Objectif : au moins {max_results} resultats."
        f"{specialty_clause}\n\n"
        f"SOURCES A EXPLOITER (fouille TOUTES ces sources) :\n"
        f"- Annuaires du barreau de {location}\n"
        f"- Pages Jaunes / PagesJaunes.fr\n"
        f"- Annuaires specialises (avocats.fr, avocat.fr, juritravail.com)\n"
        f"- Classements et guides juridiques (Legal 500, Chambers, Decideurs)\n"
        f"- Google Maps / fiches Google Business\n"
        f"- Sites des ordres professionnels\n"
        f"- Tout autre annuaire ou listing pertinent\n\n"
        f"IMPORTANT : ne te limite PAS aux cabinets les plus connus. "
        f"Inclus aussi les petits cabinets, les cabinets individuels, les structures recentes.\n\n"
        f"Pour chaque organisation trouvee, donne :\n"
        f"- name : le nom exact du cabinet/etude\n"
        f"- url : l'URL du site web officiel (OBLIGATOIRE, exclus ceux sans site web)\n"
        f"- description : une courte description (activite, specialites)\n"
        f"- type : le type (cabinet d'avocats, etude notariale, conseil juridique, etc.)\n"
        f"- address : l'adresse si disponible\n\n"
        f"Reponds UNIQUEMENT avec ce JSON :\n"
        f'{{"organizations": [{{"name": "...", "url": "...", "description": "...", '
        f'"type": "...", "address": "..."}}]}}'
    )

    print(f"  [WEB_SEARCH] Query Perplexity: {types_str} a {location}")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.perplexity.ai",
    )

    for attempt in range(_MAX_RETRIES):
        try:
            raise_if_cancelled()
            _rate_limit()
            response = client.chat.completions.create(
                model="sonar-pro",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
            )

            content = response.choices[0].message.content.strip()

            if "```json" in content:
                content = content.split("```json")[-1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            elif not content.startswith("{"):
                start = content.index("{")
                end = content.rindex("}") + 1
                content = content[start:end]

            data = json.loads(content)
            organizations = data.get("organizations", [])

            companies = []
            for org in organizations:
                companies.append({
                    "name": org.get("name", ""),
                    "websiteUrl": org.get("url") or "",
                    "description": (org.get("description") or "")[:300],
                    "city": location,
                    "source": "perplexity_web_search",
                })

            print(f"  [WEB_SEARCH] {len(companies)} organisations trouvees")
            save_result = save_candidates_batch(companies)
            return _format_report(len(companies), save_result, companies)

        except json.JSONDecodeError as e:
            print(f"  [WEB_SEARCH ERROR] JSON invalide: {e}")
            return (
                "web_search_legal_and_save: Reponse Perplexity non-JSON."
                f"\nsource_raw_excerpt: {_safe_excerpt(content)}"
            )
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                wait = _BASE_DELAY * (attempt + 1)
                print(f"  [WEB_SEARCH] Rate limit - retry dans {wait}s (tentative {attempt + 1}/{_MAX_RETRIES})")
                time.sleep(wait)
                continue

            msg = f"Erreur Perplexity: {type(e).__name__}: {e}"
            print(f"  [WEB_SEARCH ERROR] {msg}")
            return f"web_search_legal_and_save: {msg}"

    return f"web_search_legal_and_save: Echec apres {_MAX_RETRIES} tentatives."
