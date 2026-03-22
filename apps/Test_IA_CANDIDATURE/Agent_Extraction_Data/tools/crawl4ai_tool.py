import asyncio
import json
import os
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from langchain_core.tools import tool

def _get_anthropic_key():
    return os.getenv("ANTHROPIC_API_KEY", "")

# Rate limiting
_last_crawl_time = 0.0
CRAWL_DELAY = 2.0  # secondes entre crawls

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}

# Pages prioritaires à chercher sur un site
STRATEGIC_PATHS = [
    "/careers", "/jobs", "/recrutement", "/nous-rejoindre", "/join-us",
    "/about", "/a-propos", "/qui-sommes-nous", "/about-us",
    "/team", "/equipe", "/notre-equipe", "/our-team",
    "/services", "/solutions", "/what-we-do",
    "/technologies", "/tech-stack",
    "/mentions-legales", "/legal", "/cgu", "/cgv",
]

# Regex pour trouver un SIREN/SIRET dans du texte
SIREN_REGEX = re.compile(r'\b(?:SIREN|SIRET|RCS)[^\d]{0,20}(\d[\d\s]{8,16}\d)\b', re.IGNORECASE)
SIREN_SIMPLE_REGEX = re.compile(r'\b(\d{3}[\s.]?\d{3}[\s.]?\d{3}(?:[\s.]?\d{5})?)\b')


def _rate_limit_crawl():
    global _last_crawl_time
    elapsed = time.time() - _last_crawl_time
    if elapsed < CRAWL_DELAY:
        time.sleep(CRAWL_DELAY - elapsed)
    _last_crawl_time = time.time()


def _crawl_single_page(url: str) -> str:
    """Crawle une seule page et retourne son contenu en markdown."""
    try:
        _rate_limit_crawl()
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "iframe", "noscript"]):
            tag.decompose()

        markdown = md(str(soup.body or soup), strip=["img"])
        if len(markdown) > 15000:
            markdown = markdown[:15000] + "\n\n[... contenu tronqué ...]"
        return markdown
    except requests.exceptions.Timeout:
        return f"Erreur: Timeout pour {url}"
    except requests.exceptions.HTTPError as e:
        return f"Erreur HTTP {e.response.status_code} pour {url}"
    except Exception as e:
        return f"Erreur crawl: {type(e).__name__}: {e}"


@tool
def crawl_url(url: str) -> str:
    """Crawle une page web et retourne son contenu en markdown brut.

    Utilise cet outil pour explorer des annuaires, des listings, des pages de résultats,
    des classements de cabinets, ou toute page web contenant des listes de cabinets d'avocats.

    Contrairement à crawl4ai_analyze, cet outil ne fait AUCUNE analyse —
    il retourne juste le contenu markdown pour que tu puisses le lire toi-même.

    Args:
        url: URL de la page à crawler

    Returns:
        Le contenu de la page en format markdown.
    """
    if not url:
        return "Erreur: URL vide"
    if not url.startswith("http"):
        url = f"https://{url}"
    return _crawl_single_page(url)


def _find_strategic_links(html_content: str, base_url: str) -> list[str]:
    """Trouve les liens internes stratégiques (careers, about, team, etc.)."""
    soup = BeautifulSoup(html_content, "html.parser")
    base_domain = urlparse(base_url).netloc
    found_links = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        full_url = urljoin(base_url, href)

        # Garder uniquement les liens internes
        if urlparse(full_url).netloc != base_domain:
            continue

        path = urlparse(full_url).path.lower().rstrip("/")
        # Vérifier si le chemin correspond à une page stratégique
        for strategic in STRATEGIC_PATHS:
            if strategic in path:
                if full_url not in found_links:
                    found_links.append(full_url)
                break

        # Aussi chercher par texte du lien
        link_text = a_tag.get_text(strip=True).lower()
        keywords = [
            "carrière", "recrutement", "rejoindre", "jobs", "careers",
            "équipe", "team", "about", "propos", "services",
        ]
        for kw in keywords:
            if kw in link_text:
                if full_url not in found_links:
                    found_links.append(full_url)
                break

    return found_links[:5]  # Max 5 liens stratégiques


def _extract_siren_from_text(text: str) -> str | None:
    """Cherche un numéro SIREN/SIRET dans du texte brut."""
    # D'abord chercher avec le contexte (SIREN:, SIRET:, RCS...)
    match = SIREN_REGEX.search(text)
    if match:
        digits = "".join(c for c in match.group(1) if c.isdigit())
        if len(digits) >= 9:
            return digits[:9]  # SIREN = 9 premiers chiffres

    # Sinon chercher un pattern numérique qui ressemble à un SIREN
    for match in SIREN_SIMPLE_REGEX.finditer(text):
        digits = "".join(c for c in match.group(1) if c.isdigit())
        if len(digits) >= 9:
            return digits[:9]

    return None


_MAX_CONTENT_CHARS = 15000  # par page, chaque page analysée individuellement
_CLAUDE_MAX_RETRIES = 3
_CLAUDE_RETRY_DELAY = 60  # secondes d'attente sur rate limit 429

_DEFAULT_ANALYSIS = {
    "is_hiring": None,
    "job_page_url": None,
    "tech_stack": [],
    "company_activity": "",
    "culture_notes": "",
    "siren": None,
    "relevance_score": 0,
    "relevance_reason": "",
    "specialties_found": [],
}


def _call_claude(prompt: str, company_name: str) -> dict | None:
    """Appelle Claude avec retry sur rate limit. Retourne le JSON parsé ou None."""
    import anthropic

    client = anthropic.Anthropic(api_key=_get_anthropic_key())

    for attempt in range(_CLAUDE_MAX_RETRIES):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text

            if "```json" in text:
                json_str = text.split("```json")[-1].split("```")[0].strip()
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0].strip()
            elif "{" in text:
                start = text.index("{")
                end = text.rindex("}") + 1
                json_str = text[start:end]
            else:
                json_str = text

            return json.loads(json_str)

        except anthropic.RateLimitError:
            wait = _CLAUDE_RETRY_DELAY * (attempt + 1)
            print(f"  [RATE LIMIT] Claude 429 pour {company_name} — attente {wait}s (tentative {attempt + 1}/{_CLAUDE_MAX_RETRIES})")
            time.sleep(wait)

        except Exception as e:
            print(f"  [ANALYZE ERROR] {company_name}: {type(e).__name__}: {e}")
            return None

    print(f"  [ANALYZE ERROR] {company_name}: rate limit persistant après {_CLAUDE_MAX_RETRIES} tentatives")
    return None


def _analyze_single_page(page_content: str, page_url: str, company_name: str, target_role: str, skills: list[str]) -> dict:
    """Analyse UNE page avec Claude et retourne les infos extraites."""
    content = page_content[:_MAX_CONTENT_CHARS]
    skills_str = ", ".join(skills) if skills else "non spécifiées"

    prompt = f"""Analyse cette page du site de "{company_name}" ({page_url}).
Poste recherché : "{target_role}". Compétences : {skills_str}

Contenu :
{content}

Extrais UNIQUEMENT ce JSON :
{{
    "is_hiring": true/false/null,
    "job_page_url": "url carrière ou null",
    "tech_stack": ["tech1", "tech2"],
    "company_activity": "description courte",
    "culture_notes": "notes culture",
    "siren": "SIREN/SIRET trouvé ou null",
    "relevance_score": 7,
    "relevance_reason": "explication factuelle",
    "specialties_found": ["spécialité1", "spécialité2"]
}}"""

    result = _call_claude(prompt, company_name)
    return result if result else dict(_DEFAULT_ANALYSIS)


def _merge_page_analyses(analyses: list[dict]) -> dict:
    """Fusionne les analyses de plusieurs pages en un seul résultat."""
    merged = dict(_DEFAULT_ANALYSIS)

    all_tech = set()
    all_specialties = set()
    best_score = 0
    best_reason = ""
    activities = []
    culture_notes = []

    for a in analyses:
        # is_hiring : True gagne sur tout
        if a.get("is_hiring") is True:
            merged["is_hiring"] = True
        elif merged["is_hiring"] is None and a.get("is_hiring") is False:
            merged["is_hiring"] = False

        if a.get("job_page_url"):
            merged["job_page_url"] = a["job_page_url"]

        for t in (a.get("tech_stack") or []):
            all_tech.add(t)

        for s in (a.get("specialties_found") or []):
            all_specialties.add(s)

        if a.get("siren"):
            merged["siren"] = a["siren"]

        score = a.get("relevance_score", 0) or 0
        if score > best_score:
            best_score = score
            best_reason = a.get("relevance_reason", "")

        if a.get("company_activity"):
            activities.append(a["company_activity"])

        if a.get("culture_notes"):
            culture_notes.append(a["culture_notes"])

    merged["tech_stack"] = list(all_tech)
    merged["specialties_found"] = list(all_specialties)
    merged["relevance_score"] = best_score
    merged["relevance_reason"] = best_reason
    merged["company_activity"] = " | ".join(activities)[:300] if activities else ""
    merged["culture_notes"] = " | ".join(culture_notes)[:300] if culture_notes else ""

    return merged


@tool
def crawl4ai_analyze(
    website_url: str,
    company_name: str,
    target_role: str,
    skills_to_look_for: list[str] = None,
) -> str:
    """Crawle le site web d'une entreprise et analyse sa pertinence.

    Crawle la homepage + sous-pages stratégiques. Chaque page est analysée
    individuellement par Claude, puis les résultats sont fusionnés.

    Args:
        website_url: URL du site web de l'entreprise
        company_name: Nom de l'entreprise
        target_role: Poste recherché par l'utilisateur
        skills_to_look_for: Compétences/technologies à vérifier sur le site

    Returns:
        JSON avec : is_hiring, tech_stack, relevance_score, specialties_found, etc.
    """
    if not website_url:
        return json.dumps({"error": "Pas d'URL fournie", "relevance_score": 0})

    if not website_url.startswith("http"):
        website_url = f"https://{website_url}"

    skills = skills_to_look_for or []
    print(f"  [CRAWL] {company_name} -> {website_url}")

    # 1. Crawl + analyse de la homepage
    try:
        _rate_limit_crawl()
        homepage_resp = requests.get(
            website_url, headers=HEADERS, timeout=15, allow_redirects=True
        )
        homepage_resp.raise_for_status()
        homepage_resp.encoding = homepage_resp.apparent_encoding
        homepage_html = homepage_resp.text
    except Exception as e:
        return json.dumps({
            "company_name": company_name,
            "website_url": website_url,
            "error": f"Site inaccessible: {type(e).__name__}: {e}",
            "relevance_score": 0,
            "relevance_reason": "Site inaccessible",
        })

    soup = BeautifulSoup(homepage_html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "iframe", "noscript"]):
        tag.decompose()
    homepage_md = md(str(soup.body or soup), strip=["img"])

    # Chercher SIREN dans la homepage
    siren_from_regex = _extract_siren_from_text(homepage_md)

    print(f"  [ANALYZE] Homepage ({len(homepage_md)} chars)...")
    analyses = [_analyze_single_page(homepage_md, website_url, company_name, target_role, skills)]
    pages_crawled = 1

    # 2. Trouver et crawl+analyser les sous-pages stratégiques (1 par 1)
    strategic_links = _find_strategic_links(homepage_html, website_url)
    print(f"  [LINKS] {len(strategic_links)} pages stratégiques trouvées")

    for link_url in strategic_links[:2]:
        sub_md = _crawl_single_page(link_url)
        if not sub_md.startswith("Erreur"):
            pages_crawled += 1
            print(f"  [ANALYZE] Sous-page {link_url} ({len(sub_md)} chars)...")
            analyses.append(_analyze_single_page(sub_md, link_url, company_name, target_role, skills))

            if not siren_from_regex:
                siren_from_regex = _extract_siren_from_text(sub_md)

    # 3. Chercher SIREN dans mentions légales si pas encore trouvé
    if not siren_from_regex:
        for path in ["/mentions-legales", "/legal", "/mentions", "/cgu"]:
            legal_url = urljoin(website_url, path)
            legal_md = _crawl_single_page(legal_url)
            if not legal_md.startswith("Erreur"):
                pages_crawled += 1
                siren_from_regex = _extract_siren_from_text(legal_md)
                if siren_from_regex:
                    print(f"  [SIREN] Trouvé dans mentions légales: {siren_from_regex}")
                    break

    # 4. Fusionner les analyses de toutes les pages
    result = _merge_page_analyses(analyses)
    result["company_name"] = company_name
    result["website_url"] = website_url
    result["pages_crawled"] = pages_crawled
    result["verified_by_crawl"] = True

    if siren_from_regex:
        result["siren"] = siren_from_regex
        print(f"  [SIREN] {siren_from_regex}")

    print(f"  [DONE] {company_name} — score {result['relevance_score']}/10 — {pages_crawled} pages analysées")

    return json.dumps(result, ensure_ascii=False)
