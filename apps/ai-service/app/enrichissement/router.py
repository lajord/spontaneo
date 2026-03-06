import re
import json
import asyncio
import logging
from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import CompanyRequest, EnrichedContact, EnrichedCompany
from app.utils.ai_caller import call_ai_with_search
from app.enrichissement.prompts import (
    SYSTEM_PROMPT,
    USER_PROMPT_WITH_SITE, USER_PROMPT_WITHOUT_SITE,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_response(raw: str) -> list[dict]:
    """Parse la réponse JSON de l'IA et retourne la liste brute de résultats."""
    def _extract(data) -> list[dict]:
        if isinstance(data, dict):
            r = data.get("resultats")
            if isinstance(r, list):
                return r
        return []

    try:
        return _extract(json.loads(raw))
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        try:
            return _extract(json.loads(match.group(1)))
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return _extract(json.loads(match.group(0)))
        except json.JSONDecodeError:
            pass

    return []


def _to_enriched_contacts(raw_list: list[dict]) -> list[EnrichedContact]:
    contacts = []
    for r in raw_list:
        if not isinstance(r, dict):
            continue
        t = r.get("type", "")
        if t not in ("generique", "specialise"):
            continue
        contacts.append(EnrichedContact(
            type=t,
            nom=r.get("nom") or None,
            prenom=r.get("prenom") or None,
            role=r.get("role") or None,
            mail=r.get("mail") or None,
            genre=r.get("genre") or None,
        ))
    return contacts


def _merge_raw_contacts(list1: list[dict], list2: list[dict]) -> list[dict]:
    """Fusionne deux listes de contacts sans doublons.
    Clé de dédup : mail (lowercase) si présent, sinon (nom+prenom) lowercase.
    En cas de doublon, on fusionne les champs non-null des deux sources.
    """
    seen: dict[str, dict] = {}

    def _key(c: dict) -> str | None:
        mail = (c.get("mail") or "").strip().lower()
        if mail:
            return f"mail:{mail}"
        nom = (c.get("nom") or "").strip().lower()
        prenom = (c.get("prenom") or "").strip().lower()
        if nom or prenom:
            return f"person:{nom}:{prenom}"
        return None

    def _merge(a: dict, b: dict) -> dict:
        return {k: (a.get(k) or b.get(k)) for k in set(a) | set(b)}

    for contact in list1 + list2:
        key = _key(contact)
        if key is None:
            seen[id(contact).__str__()] = contact
        elif key in seen:
            seen[key] = _merge(seen[key], contact)
        else:
            seen[key] = contact

    return list(seen.values())


@router.post("/company", response_model=EnrichedCompany)
async def enrich_company(request: CompanyRequest):
    logger.info(f"[ENRICHISSEMENT] {settings.MODEL_ENRICHISSEMENT} + {settings.MODEL_ENRICHISSEMENT_2} | nom='{request.nom}'")

    if request.site_web:
        domain = (
            request.site_web
            .replace("https://", "")
            .replace("http://", "")
            .split("/")[0]
        )
        prompt = USER_PROMPT_WITH_SITE.format(
            nom=request.nom,
            site_web=request.site_web,
            adresse=request.adresse or "inconnue",
            domain=domain,
        )
    else:
        prompt = USER_PROMPT_WITHOUT_SITE.format(
            nom=request.nom,
            adresse=request.adresse or "inconnue",
        )

    is_firecrawl = settings.MODEL_ENRICHISSEMENT.startswith("spark")
    urls = [request.site_web] if is_firecrawl and request.site_web else None

    raw1, raw2 = await asyncio.gather(
        call_ai_with_search(
            model=settings.MODEL_ENRICHISSEMENT,
            prompt=prompt,
            system_prompt="" if is_firecrawl else SYSTEM_PROMPT,
            urls=urls,
        ),
        call_ai_with_search(
            model=settings.MODEL_ENRICHISSEMENT_2,
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        ),
        return_exceptions=True,
    )

    list1 = _parse_response(raw1) if not isinstance(raw1, Exception) else []
    list2 = _parse_response(raw2) if not isinstance(raw2, Exception) else []

    if isinstance(raw1, Exception):
        logger.error(f"[ENRICHISSEMENT] [{request.nom}] {settings.MODEL_ENRICHISSEMENT} échoué: {raw1.__class__.__name__}")
    if isinstance(raw2, Exception):
        logger.error(f"[ENRICHISSEMENT] [{request.nom}] {settings.MODEL_ENRICHISSEMENT_2} échoué: {raw2.__class__.__name__}")

    merged = _merge_raw_contacts(list1, list2)
    resultats = _to_enriched_contacts(merged)
    logger.info(f"[ENRICHISSEMENT] [{request.nom}] → {len(list1)} + {len(list2)} contacts → {len(resultats)} après merge")

    return EnrichedCompany(
        nom=request.nom,
        adresse=request.adresse,
        site_web=request.site_web,
        resultats=resultats,
    )
