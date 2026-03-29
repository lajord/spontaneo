import json
import os
import time
import requests
from langchain_core.tools import tool

from config import RATE_LIMIT_APOLLO, TOOL_MAX_RETRIES, TOOL_RETRY_BASE_DELAY, HTTP_TIMEOUT_APOLLO


def _get_apollo_key():
    return os.getenv("APOLLO_API_KEY", "")


APOLLO_BASE_URL = "https://api.apollo.io"

# Rate limiting
_last_call_time = 0.0
RATE_LIMIT_DELAY = RATE_LIMIT_APOLLO
_MAX_RETRIES = TOOL_MAX_RETRIES
_BASE_DELAY = TOOL_RETRY_BASE_DELAY


def _rate_limit():
    """Attend si necessaire pour respecter le rate limit Apollo."""
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < RATE_LIMIT_DELAY:
        time.sleep(RATE_LIMIT_DELAY - elapsed)
    _last_call_time = time.time()


def _extract_contacts_from_people(people: list) -> list[dict]:
    """Extrait les infos pertinentes d'une liste de personnes Apollo."""
    contacts = []
    for person in people:
        if not person:
            continue
        phone = ""
        phone_numbers = person.get("phone_numbers") or []
        if phone_numbers:
            phone = phone_numbers[0].get("sanitized_number", "") or phone_numbers[0].get("raw_number", "")

        contacts.append({
            "first_name": person.get("first_name", ""),
            "last_name": person.get("last_name", ""),
            "full_name": f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
            "email": person.get("email", ""),
            "email_status": person.get("email_status", ""),
            "title": person.get("title", ""),
            "phone": phone,
            "linkedin_url": person.get("linkedin_url", ""),
            "source": "apollo_people",
        })
    return contacts


@tool
def apollo_people_search(
    domain: str = None,
    organization_name: str = None,
    person_titles: list[str] = None,
    person_seniorities: list[str] = None,
    first_name: str = None,
    last_name: str = None,
) -> str:
    """Recherche et enrichit des contacts via Apollo.io People API.

    CET OUTIL A DEUX MODES :

    MODE 1 — RECHERCHE (quand tu fournis domain ou organization_name SANS first_name/last_name) :
    Trouve les decideurs d'une entreprise par leur domaine web.
    Retourne une liste de personnes avec nom, titre, email, LinkedIn.
    Utilise person_titles et person_seniorities pour filtrer.

    MODE 2 — MATCH (quand tu fournis first_name ET last_name) :
    Enrichit une personne specifique dont tu connais le nom.
    Fournir le domain ou organization_name pour ameliorer la precision.
    Retourne l'email, titre, telephone, LinkedIn de cette personne.

    Args:
        domain: Domaine web de l'entreprise (ex: "cabinet-x.fr")
        organization_name: Nom de l'entreprise (ex: "Cabinet X")
        person_titles: Titres a rechercher en MODE RECHERCHE (ex: ["Partner", "Associe", "Directeur"])
        person_seniorities: Niveaux de seniorite (ex: ["director", "vp", "owner", "partner", "c_suite"])
        first_name: Prenom de la personne (MODE MATCH uniquement, ex: "Jean")
        last_name: Nom de la personne (MODE MATCH uniquement, ex: "Dupont")

    Returns:
        JSON avec les contacts trouves (nom, email, titre, telephone, LinkedIn).
    """
    api_key = _get_apollo_key()
    if not api_key:
        return json.dumps({
            "error": "APOLLO_API_KEY non configuree dans le .env",
            "contacts": [],
        })

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }

    # Detecter le mode
    is_match_mode = bool(first_name and last_name)

    if is_match_mode:
        return _people_match(
            headers=headers,
            first_name=first_name,
            last_name=last_name,
            domain=domain,
            organization_name=organization_name,
        )
    else:
        return _people_search(
            headers=headers,
            domain=domain,
            organization_name=organization_name,
            person_titles=person_titles,
            person_seniorities=person_seniorities,
        )


def _people_search(
    headers: dict,
    domain: str = None,
    organization_name: str = None,
    person_titles: list[str] = None,
    person_seniorities: list[str] = None,
) -> str:
    """MODE RECHERCHE — Trouve des personnes dans une entreprise."""
    payload = {"page": 1, "per_page": 10}

    if domain:
        payload["organization_domains"] = [domain]
    if organization_name:
        payload["q_organization_name"] = organization_name
    if person_titles:
        payload["person_titles"] = person_titles
    if person_seniorities:
        payload["person_seniorities"] = person_seniorities

    if not domain and not organization_name:
        return json.dumps({
            "error": "MODE RECHERCHE: il faut au minimum domain ou organization_name.",
            "contacts": [],
        })

    url = f"{APOLLO_BASE_URL}/api/v1/mixed_people/search"
    print(f"  [APOLLO PEOPLE] SEARCH: {json.dumps(payload, ensure_ascii=False)}")

    for attempt in range(_MAX_RETRIES):
        try:
            _rate_limit()
            response = requests.post(url, json=payload, headers=headers, timeout=HTTP_TIMEOUT_APOLLO)

            if response.status_code == 429:
                wait = _BASE_DELAY * (attempt + 1)
                print(f"  [APOLLO PEOPLE] Rate limit 429 — retry dans {wait}s")
                time.sleep(wait)
                continue

            if response.status_code != 200:
                print(f"  [APOLLO PEOPLE ERROR] {response.status_code}: {response.text[:300]}")
                return json.dumps({
                    "error": f"Apollo People Search HTTP {response.status_code}",
                    "contacts": [],
                })

            data = response.json()
            people = data.get("people", [])
            contacts = _extract_contacts_from_people(people)

            print(f"  [APOLLO PEOPLE] {len(contacts)} contacts trouves")

            return json.dumps({
                "contacts": contacts,
                "count": len(contacts),
                "mode": "search",
            }, ensure_ascii=False)

        except requests.exceptions.Timeout:
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_BASE_DELAY)
                continue
            return json.dumps({"error": "Timeout Apollo People Search", "contacts": []})
        except Exception as e:
            msg = f"Erreur Apollo People: {type(e).__name__}: {e}"
            print(f"  [APOLLO PEOPLE ERROR] {msg}")
            return json.dumps({"error": msg, "contacts": []})

    return json.dumps({"error": "Echec apres 3 tentatives", "contacts": []})


def _people_match(
    headers: dict,
    first_name: str,
    last_name: str,
    domain: str = None,
    organization_name: str = None,
) -> str:
    """MODE MATCH — Enrichit une personne specifique."""
    payload = {
        "first_name": first_name,
        "last_name": last_name,
        "reveal_personal_emails": True,
    }

    if domain:
        payload["domain"] = domain
    if organization_name:
        payload["organization_name"] = organization_name

    url = f"{APOLLO_BASE_URL}/api/v1/people/match"
    print(f"  [APOLLO PEOPLE] MATCH: {first_name} {last_name} @ {domain or organization_name or '?'}")

    for attempt in range(_MAX_RETRIES):
        try:
            _rate_limit()
            response = requests.post(url, json=payload, headers=headers, timeout=HTTP_TIMEOUT_APOLLO)

            if response.status_code == 429:
                wait = _BASE_DELAY * (attempt + 1)
                print(f"  [APOLLO PEOPLE] Rate limit 429 — retry dans {wait}s")
                time.sleep(wait)
                continue

            if response.status_code != 200:
                print(f"  [APOLLO PEOPLE ERROR] {response.status_code}: {response.text[:300]}")
                return json.dumps({
                    "error": f"Apollo People Match HTTP {response.status_code}",
                    "contacts": [],
                })

            data = response.json()
            person = data.get("person")

            if not person:
                print(f"  [APOLLO PEOPLE] Aucun match pour {first_name} {last_name}")
                return json.dumps({
                    "contacts": [],
                    "count": 0,
                    "mode": "match",
                    "message": f"Aucun match Apollo pour {first_name} {last_name}",
                })

            contacts = _extract_contacts_from_people([person])
            print(f"  [APOLLO PEOPLE] Match: {contacts[0].get('email', 'pas d email')}")

            return json.dumps({
                "contacts": contacts,
                "count": len(contacts),
                "mode": "match",
            }, ensure_ascii=False)

        except requests.exceptions.Timeout:
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_BASE_DELAY)
                continue
            return json.dumps({"error": "Timeout Apollo People Match", "contacts": []})
        except Exception as e:
            msg = f"Erreur Apollo People Match: {type(e).__name__}: {e}"
            print(f"  [APOLLO PEOPLE ERROR] {msg}")
            return json.dumps({"error": msg, "contacts": []})

    return json.dumps({"error": "Echec apres 3 tentatives", "contacts": []})
