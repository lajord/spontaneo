import re
import json
import logging
from typing import Optional
from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import CompanyRequest, Contact, EnrichedCompany
from app.utils.ai_caller import call_ai_with_web_search
from app.enrichissement.prompts import SYSTEM_PROMPT, USER_PROMPT_WITH_SITE, USER_PROMPT_WITHOUT_SITE

logger = logging.getLogger(__name__)
router = APIRouter()

CHATGPT_MODEL = "gpt-5"


def _parse_response(raw: str) -> dict:
    """Parse la réponse JSON de l'IA d'enrichissement."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return {"emails": [], "dirigeant": None, "rh": None, "autres_contacts": []}


def _to_contact(data) -> Optional[Contact]:
    if not data or not isinstance(data, dict) or not any(data.values()):
        return None
    return Contact(**{k: v for k, v in data.items() if k in Contact.model_fields})


@router.post("/company", response_model=EnrichedCompany)
async def enrich_company(request: CompanyRequest):
    """
    Enrichit une entreprise avec ses contacts (dirigeant, RH, emails) via IA.
    Utilise le site web quand disponible pour une recherche plus ciblée.
    """
    logger.info(f"[ENRICHISSEMENT]  nom='{request.nom}'  site_web={request.site_web}")

    # Choix du prompt selon disponibilité du site web
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
        raw = await call_ai_with_web_search(
            model=CHATGPT_MODEL,
            prompt=prompt,
            instructions=SYSTEM_PROMPT,
            api_key=settings.CHATGPT_API,
        )
        logger.info(f"[ENRICHISSEMENT] ChatGPT [{request.nom}] → {raw[:120]}...")
        contacts = _parse_response(raw)

    except Exception as e:
        logger.error(f"[ENRICHISSEMENT] Erreur [{request.nom}]: {e}")
        contacts = {"emails": [], "dirigeant": None, "rh": None, "autres_contacts": []}

    return EnrichedCompany(
        nom=request.nom,
        adresse=request.adresse,
        site_web=request.site_web,
        emails=contacts.get("emails") or [],
        dirigeant=_to_contact(contacts.get("dirigeant")),
        rh=_to_contact(contacts.get("rh")),
        autres_contacts=[
            Contact(**{k: v for k, v in c.items() if k in Contact.model_fields})
            for c in (contacts.get("autres_contacts") or [])
            if isinstance(c, dict)
        ],
    )
