import re
import json
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
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
    else:
        logger.info(f"[ENRICHISSEMENT] [{request.nom}] {settings.MODEL_ENRICHISSEMENT} → {len(list1)} contact(s)")
    if isinstance(raw2, Exception):
        logger.error(f"[ENRICHISSEMENT] [{request.nom}] {settings.MODEL_ENRICHISSEMENT_2} échoué: {raw2.__class__.__name__}")
    else:
        logger.info(f"[ENRICHISSEMENT] [{request.nom}] {settings.MODEL_ENRICHISSEMENT_2} → {len(list2)} contact(s)")

    merged = _merge_raw_contacts(list1, list2)
    resultats = _to_enriched_contacts(merged)
    logger.info(f"[ENRICHISSEMENT] [{request.nom}] Total après merge : {len(resultats)} contact(s) uniques")

    return EnrichedCompany(
        nom=request.nom,
        adresse=request.adresse,
        site_web=request.site_web,
        resultats=resultats,
    )


# ── Pipeline complet : Firecrawl+Gemini → Ranking → Apollo ───────────────────

class CompanyFullRequest(CompanyRequest):
    """Requête pour le pipeline complet avec paramètres de ranking et Apollo."""
    job_title: Optional[str] = ""
    max_contacts: int = 3
    min_score: int = 40
    reveal_personal_emails: bool = False
    reveal_phone_number: bool = False


def _extract_domain(site_web: str | None) -> str | None:
    if not site_web:
        return None
    return (
        site_web
        .replace("https://", "")
        .replace("http://", "")
        .split("/")[0]
    )


@router.post("/company-full")
async def enrich_company_full(request: CompanyFullRequest):
    """Pipeline complet : enrichissement Firecrawl+Gemini → ranking Gemini → Apollo.

    1. Appelle l'enrichissement existant (Firecrawl + Gemini)
    2. Classe les contacts par pertinence recrutement (Gemini ranking)
    3. Envoie les top N contacts à Apollo pour vérification email/téléphone
    4. Retourne tous les contacts avec scores + données Apollo pour les tops
    """
    # ── Étape 1 : Enrichissement classique ────────────────────────────────
    base_request = CompanyRequest(
        nom=request.nom,
        site_web=request.site_web,
        adresse=request.adresse,
    )
    base_result = await enrich_company(base_request)
    contacts = base_result.resultats

    logger.info(f"[COMPANY-FULL] [{request.nom}] Étape 1 → {len(contacts)} contacts bruts")

    if not contacts:
        return {
            "nom": request.nom,
            "adresse": request.adresse,
            "site_web": request.site_web,
            "resultats": [],
            "rankings": [],
        }

    # ── Étape 2 : Ranking Gemini ──────────────────────────────────────────
    ranked = await rank_contacts(
        contacts=contacts,
        company_name=request.nom,
        job_title=request.job_title or "",
    )

    logger.info(
        f"[COMPANY-FULL] [{request.nom}] Étape 2 → {len(ranked)} contacts classés, "
        f"scores: {[r.score for r in ranked[:5]]}"
    )

    # ── Étape 3 : Apollo enrichissement des top contacts ──────────────────
    top_contacts = [r for r in ranked if r.score >= request.min_score][:request.max_contacts]

    apollo_results: list[ApolloEnrichedContact] = []
    non_apollo_results: list[dict] = []

    if settings.APOLLO_API_KEY and top_contacts:
        domain = _extract_domain(request.site_web)
        client = ApolloClient(api_key=settings.APOLLO_API_KEY)

        try:
            apollo_tasks = []
            for rc in top_contacts:
                c = rc.contact
                if c.type == "specialise" and (c.prenom or c.nom):
                    apollo_tasks.append((rc, client.match_person(
                        first_name=c.prenom or "",
                        last_name=c.nom or "",
                        domain=domain,
                        email=c.mail,
                        organization_name=request.nom,
                        reveal_personal_emails=request.reveal_personal_emails,
                        reveal_phone_number=request.reveal_phone_number,
                    )))

            # Exécuter les appels Apollo en parallèle
            if apollo_tasks:
                results = await asyncio.gather(
                    *[task for _, task in apollo_tasks],
                    return_exceptions=True,
                )
                for (rc, _), result in zip(apollo_tasks, results):
                    if isinstance(result, Exception):
                        logger.error(f"[COMPANY-FULL] Apollo échoué pour {rc.contact.prenom} {rc.contact.nom}: {result}")
                        enriched = ApolloEnrichedContact(
                            **rc.contact.model_dump(),
                            ranking_score=rc.score,
                        )
                    else:
                        enriched = adapt_person_to_contact(result, rc.contact)
                        enriched.ranking_score = rc.score
                    apollo_results.append(enriched)
        finally:
            await client.close()

        logger.info(f"[COMPANY-FULL] [{request.nom}] Étape 3 → {len(apollo_results)} contacts enrichis Apollo")
    else:
        if not settings.APOLLO_API_KEY:
            logger.info(f"[COMPANY-FULL] [{request.nom}] Apollo désactivé (pas de clé API)")

    # Construire les résultats finaux : Apollo enrichis + reste avec score
    apollo_ids = {id(rc.contact) for rc in top_contacts if any(
        a.nom == rc.contact.nom and a.prenom == rc.contact.prenom for a in apollo_results
    )}

    final_resultats = []

    # D'abord les contacts enrichis Apollo
    for ac in apollo_results:
        final_resultats.append(ac.model_dump())

    # Puis les contacts non-Apollo avec leur score
    for rc in ranked:
        already_in = any(
            r.get("nom") == rc.contact.nom
            and r.get("prenom") == rc.contact.prenom
            and r.get("mail") == rc.contact.mail
            for r in final_resultats
        )
        if not already_in:
            contact_dict = rc.contact.model_dump()
            contact_dict["ranking_score"] = rc.score
            final_resultats.append(contact_dict)

    return {
        "nom": request.nom,
        "adresse": request.adresse,
        "site_web": request.site_web,
        "resultats": final_resultats,
        "rankings": [
            {"index": i, "score": r.score, "reason": r.reason}
            for i, r in enumerate(ranked)
        ],
    }
