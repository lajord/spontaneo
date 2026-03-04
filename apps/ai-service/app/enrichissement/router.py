import re
import json
import logging
from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import CompanyRequest, EnrichedContact, EnrichedCompany
from app.utils.ai_caller import call_ai_with_search
from app.enrichissement.prompts import SYSTEM_PROMPT, USER_PROMPT_WITH_SITE, USER_PROMPT_WITHOUT_SITE

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
    """Valide et convertit la liste brute en objets EnrichedContact."""
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


@router.post("/company", response_model=EnrichedCompany)
async def enrich_company(request: CompanyRequest):
    """
    Enrichit une entreprise avec ses contacts via web search.
    Retourne une liste plate de contacts typés (generique / specialise).
    """
    logger.info(f"[ENRICHISSEMENT] {settings.MODEL_ENRICHISSEMENT} | nom='{request.nom}'  site_web={request.site_web}")

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

    try:
        raw = await call_ai_with_search(
            model=settings.MODEL_ENRICHISSEMENT,
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )
        logger.info(f"[ENRICHISSEMENT] [{request.nom}] →\n{raw}")
        raw_list = _parse_response(raw)
        resultats = _to_enriched_contacts(raw_list)
        logger.info(f"[ENRICHISSEMENT] [{request.nom}] → {len(resultats)} contact(s)")

    except Exception as e:
        logger.error(f"[ENRICHISSEMENT] Erreur [{request.nom}]: {e}")
        resultats = []

    return EnrichedCompany(
        nom=request.nom,
        adresse=request.adresse,
        site_web=request.site_web,
        resultats=resultats,
    )
