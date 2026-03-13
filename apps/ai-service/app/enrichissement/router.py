import re
import json
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.core.model_config import get_models
from app.models.schemas import CompanyRequest, EnrichedContact, EnrichedCompany
from app.utils.ai_caller import call_ai_with_search
from app.enrichissement.prompts import (
    SYSTEM_PROMPT,
    USER_PROMPT_WITH_SITE, USER_PROMPT_WITHOUT_SITE,
)
from app.apollo import (
    ApolloClient,
    rank_contacts,
    adapt_person_to_contact,
    ApolloEnrichedContact,
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
    models = await get_models()
    logger.info(f"[ENRICHISSEMENT] {models.MODEL_ENRICHISSEMENT} + {models.MODEL_ENRICHISSEMENT_2} | nom='{request.nom}'")

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

    is_firecrawl = models.MODEL_ENRICHISSEMENT.startswith("spark")
    urls = [request.site_web] if is_firecrawl and request.site_web else None

    raw1, raw2 = await asyncio.gather(
        call_ai_with_search(
            model=models.MODEL_ENRICHISSEMENT,
            prompt=prompt,
            system_prompt="" if is_firecrawl else SYSTEM_PROMPT,
            urls=urls,
        ),
        call_ai_with_search(
            model=models.MODEL_ENRICHISSEMENT_2,
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        ),
        return_exceptions=True,
    )

    list1 = _parse_response(raw1) if not isinstance(raw1, Exception) else []
    list2 = _parse_response(raw2) if not isinstance(raw2, Exception) else []

    if isinstance(raw1, Exception):
        logger.error(f"[ENRICHISSEMENT] [{request.nom}] {models.MODEL_ENRICHISSEMENT} échoué: {raw1.__class__.__name__}")
    else:
        logger.info(f"[ENRICHISSEMENT] [{request.nom}] {models.MODEL_ENRICHISSEMENT} → {len(list1)} contact(s)")
    if isinstance(raw2, Exception):
        logger.error(f"[ENRICHISSEMENT] [{request.nom}] {models.MODEL_ENRICHISSEMENT_2} échoué: {raw2.__class__.__name__}")
    else:
        logger.info(f"[ENRICHISSEMENT] [{request.nom}] {models.MODEL_ENRICHISSEMENT_2} → {len(list2)} contact(s)")

    merged = _merge_raw_contacts(list1, list2)
    resultats = _to_enriched_contacts(merged)
    logger.info(f"[ENRICHISSEMENT] [{request.nom}] Total après merge : {len(resultats)} contact(s) uniques")

    return EnrichedCompany(
        nom=request.nom,
        adresse=request.adresse,
        site_web=request.site_web,
        resultats=resultats,
    )


# ── Pipeline enrichi : Firecrawl+Perplexity → Ranking → Apollo bulk_match ────

class CompanyRankedRequest(CompanyRequest):
    job_title: Optional[str] = ""
    max_contacts: int = 3
    min_score: int = 50


def _extract_domain(site_web: str | None) -> str | None:
    if not site_web:
        return None
    return (
        site_web
        .replace("https://", "")
        .replace("http://", "")
        .split("/")[0]
    )


@router.post("/company-ranked")
async def enrich_company_ranked(request: CompanyRankedRequest):
    """Pipeline enrichi : Firecrawl+Perplexity → Ranking IA → Apollo bulk_match.

    1. Enrichissement classique (Firecrawl + Perplexity) → contacts bruts
    2. Ranking Gemini → score par pertinence recrutement
    3. Apollo bulk_match → emails vérifiés pour les top contacts
    """
    # ── Étape 1 : Enrichissement classique ────────────────────────────────
    base_result = await enrich_company(CompanyRequest(
        nom=request.nom,
        site_web=request.site_web,
        adresse=request.adresse,
    ))
    contacts = base_result.resultats

    logger.info(f"[COMPANY-RANKED] [{request.nom}] Étape 1 → {len(contacts)} contacts bruts")

    if not contacts:
        return {"nom": request.nom, "adresse": request.adresse, "site_web": request.site_web, "resultats": []}

    # ── Étape 2 : Ranking ─────────────────────────────────────────────────
    ranked = await rank_contacts(
        contacts=contacts,
        company_name=request.nom,
        job_title=request.job_title or "",
    )
    top_contacts = [r for r in ranked if r.score >= request.min_score][:request.max_contacts]

    logger.info(
        f"[COMPANY-RANKED] [{request.nom}] Étape 2 → {len(top_contacts)} tops "
        f"(min_score={request.min_score}, max={request.max_contacts})"
    )

    # ── Étape 3 : Apollo bulk_match ───────────────────────────────────────
    apollo_map: dict[int, ApolloEnrichedContact] = {}

    if settings.APOLLO_API_KEY and top_contacts:
        domain = _extract_domain(request.site_web)

        # Préparer les détails pour bulk_match (specialisés avec nom/prénom uniquement)
        bulk_details: list[dict] = []
        bulk_indices: list[int] = []  # position dans top_contacts
        for i, rc in enumerate(top_contacts):
            c = rc.contact
            if c.type == "specialise" and (c.prenom or c.nom):
                detail: dict = {}
                if c.prenom:
                    detail["first_name"] = c.prenom
                if c.nom:
                    detail["last_name"] = c.nom
                if domain:
                    detail["domain"] = domain
                if request.nom:
                    detail["organization_name"] = request.nom
                if c.mail:
                    detail["email"] = c.mail
                bulk_details.append(detail)
                bulk_indices.append(i)

        if bulk_details:
            client = ApolloClient(api_key=settings.APOLLO_API_KEY)
            try:
                result = await client.bulk_match(
                    details=bulk_details,
                    reveal_personal_emails=True,
                )
                matches = result.get("matches") or []
                for match_pos, match in enumerate(matches):
                    if match_pos >= len(bulk_indices):
                        break
                    top_idx = bulk_indices[match_pos]
                    person_data = match.get("person") if match else None
                    if person_data:
                        enriched = adapt_person_to_contact({"person": person_data}, top_contacts[top_idx].contact)
                        enriched.ranking_score = top_contacts[top_idx].score
                        apollo_map[top_idx] = enriched
            except Exception as e:
                logger.error(f"[COMPANY-RANKED] [{request.nom}] bulk_match échoué: {e}")
            finally:
                await client.close()

        logger.info(f"[COMPANY-RANKED] [{request.nom}] Étape 3 → {len(apollo_map)} contacts enrichis Apollo")
    else:
        logger.info(f"[COMPANY-RANKED] [{request.nom}] Apollo désactivé (clé manquante)")

    # ── Construction des résultats finaux ─────────────────────────────────
    final_resultats = []
    seen_keys: set[str] = set()

    for i, rc in enumerate(top_contacts):
        contact_dict = apollo_map[i].model_dump() if i in apollo_map else {
            **rc.contact.model_dump(), "ranking_score": rc.score
        }
        key = f"{contact_dict.get('nom', '')}:{contact_dict.get('prenom', '')}"
        seen_keys.add(key)
        final_resultats.append(contact_dict)

    for rc in ranked:
        if rc in top_contacts:
            continue
        contact_dict = {**rc.contact.model_dump(), "ranking_score": rc.score}
        key = f"{contact_dict.get('nom', '')}:{contact_dict.get('prenom', '')}"
        if key not in seen_keys:
            seen_keys.add(key)
            final_resultats.append(contact_dict)

    return {
        "nom": request.nom,
        "adresse": request.adresse,
        "site_web": request.site_web,
        "resultats": final_resultats,
    }
