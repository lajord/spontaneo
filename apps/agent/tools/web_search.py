import json
import os
import time
from langchain_core.tools import tool
from openai import OpenAI

from config import RATE_LIMIT_PERPLEXITY, TOOL_MAX_RETRIES, TOOL_RETRY_BASE_DELAY

def _get_perplexity_key():
    return os.getenv("PERPLEXITY_API_KEY", "")

# Rate limiting
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


@tool
def web_search_legal(
    location: str,
    organization_types: list[str] = None,
    legal_specialties: list[str] = None,
    max_results: int = 50,
) -> str:
    """Recherche exhaustive sur internet des cabinets d'avocats et organisations juridiques.

    Utilise Perplexity Sonar Pro pour trouver un MAXIMUM de structures juridiques locales.
    Fouille en profondeur : annuaires, barreaux, classements, Pages Jaunes, etc.

    QUAND UTILISER CET OUTIL :
    - À chaque itération de collecte, en complément d'Apollo et Google Maps
    - Pour les cabinets d'avocats, études notariales, cabinets de conseil juridique
    - Tout en FRANCAIS (location, types, spécialités)

    Args:
        location: Ville ou zone géographique (ex: "Pau", "Bordeaux", "Paris")
        organization_types: Types d'organisations à chercher.
            Exemples: ["cabinets d'avocats", "études notariales", "cabinets de conseil juridique"]
            Défaut: cabinets d'avocats + études notariales + cabinets conseil.
        legal_specialties: Spécialités juridiques pour filtrer.
            Exemples: ["droit des affaires", "droit social", "droit fiscal"]
            Optionnel.
        max_results: Nombre max de résultats (défaut: 50)

    Returns:
        JSON avec la liste des organisations trouvées (name, url, description, type)
    """
    dev_mode = os.environ.get("AGENT_DEV_MODE") == "1"
    if dev_mode:
        max_results = min(max_results, 5)

    api_key = _get_perplexity_key()
    if not api_key:
        return json.dumps({
            "error": "PERPLEXITY_API_KEY non configurée dans le .env",
            "organizations": [],
        })

    if not organization_types:
        organization_types = [
            "cabinets d'avocats",
            "études notariales",
            "cabinets de conseil juridique",
        ]

    types_str = ", ".join(organization_types)
    specialty_clause = ""
    if legal_specialties:
        specialty_clause = (
            f"\nSPECIALITES RECHERCHEES : {', '.join(legal_specialties)}. "
            f"Trouve UNIQUEMENT les cabinets spécialisés dans ces domaines."
        )

    system_message = (
        "Tu es un assistant expert en recherche exhaustive d'organisations juridiques françaises. "
        "Tu fouilles TOUTES les sources possibles pour trouver un MAXIMUM de résultats. "
        "Tu réponds UNIQUEMENT en JSON valide, sans texte supplémentaire, sans markdown."
    )

    user_message = (
        f"Trouve le MAXIMUM de {types_str} à {location} (France). "
        f"Objectif : au moins {max_results} résultats."
        f"{specialty_clause}\n\n"
        f"SOURCES A EXPLOITER (fouille TOUTES ces sources) :\n"
        f"- Annuaires du barreau de {location}\n"
        f"- Pages Jaunes / PagesJaunes.fr\n"
        f"- Annuaires spécialisés (avocats.fr, avocat.fr, juritravail.com)\n"
        f"- Classements et guides juridiques (Legal 500, Chambers, Décideurs)\n"
        f"- Google Maps / fiches Google Business\n"
        f"- Sites des ordres professionnels\n"
        f"- Tout autre annuaire ou listing pertinent\n\n"
        f"IMPORTANT : ne te limite PAS aux cabinets les plus connus. "
        f"Inclus aussi les petits cabinets, les cabinets individuels, les structures récentes.\n\n"
        f"Pour chaque organisation trouvée, donne :\n"
        f"- name : le nom exact du cabinet/étude\n"
        f"- url : l'URL du site web officiel (OBLIGATOIRE, exclus ceux sans site web)\n"
        f"- description : une courte description (activité, spécialités)\n"
        f"- type : le type (cabinet d'avocats, étude notariale, conseil juridique, etc.)\n"
        f"- address : l'adresse si disponible\n\n"
        f"Réponds UNIQUEMENT avec ce JSON :\n"
        f'{{"organizations": [{{"name": "...", "url": "...", "description": "...", '
        f'"type": "...", "address": "..."}}]}}'
    )

    print(f"  [WEB_SEARCH] Recherche: {types_str} à {location}")
    if legal_specialties:
        print(f"  [WEB_SEARCH] Spécialités: {', '.join(legal_specialties)}")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.perplexity.ai",
    )

    for attempt in range(_MAX_RETRIES):
        try:
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

            # Extraire le JSON (même pattern que crawl4ai_tool)
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

            results = []
            for org in organizations:
                results.append({
                    "name": org.get("name", ""),
                    "url": org.get("url"),
                    "description": (org.get("description") or "")[:300],
                    "type": org.get("type", "cabinet d'avocats"),
                    "address": org.get("address", ""),
                    "city": location,
                    "source": "perplexity_web_search",
                })

            print(f"  [WEB_SEARCH] {len(results)} organisations trouvées")

            return json.dumps({
                "organizations": results,
                "count": len(results),
                "location": location,
                "query_types": organization_types,
            }, ensure_ascii=False)

        except json.JSONDecodeError as e:
            print(f"  [WEB_SEARCH ERROR] JSON invalide: {e}")
            print(f"  [WEB_SEARCH ERROR] Réponse brute: {content[:300]}")
            return json.dumps({
                "error": f"Réponse Perplexity non-JSON: {content[:500]}",
                "organizations": [],
            })

        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                wait = _BASE_DELAY * (attempt + 1)
                print(f"  [WEB_SEARCH] Rate limit — retry dans {wait}s (tentative {attempt + 1}/{_MAX_RETRIES})")
                time.sleep(wait)
                continue

            msg = f"Erreur Perplexity: {type(e).__name__}: {e}"
            print(f"  [WEB_SEARCH ERROR] {msg}")
            return json.dumps({"error": msg, "organizations": []})

    return json.dumps({
        "error": "Échec après 3 tentatives (rate limit Perplexity)",
        "organizations": [],
    })
