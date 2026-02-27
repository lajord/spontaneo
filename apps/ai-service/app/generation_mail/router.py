import re
import json
import logging
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.utils.ai_caller import call_ai
from app.generation_mail.prompts import SYSTEM_PROMPT, USER_PROMPT

logger = logging.getLogger(__name__)
router = APIRouter()

MODEL = "gpt-4o-mini"


# ── Schémas ────────────────────────────────────────────────────────────────────

class CvData(BaseModel):
    nom: Optional[str] = ""
    formation: list[str] = []
    experience: list[str] = []
    competences_brutes: list[str] = []
    soft_skills: list[str] = []
    langues: list[str] = []
    resume: Optional[str] = ""


class CampagneData(BaseModel):
    jobTitle: str
    location: str
    startDate: Optional[str] = None
    duration: Optional[str] = None
    prompt: Optional[str] = None


class EntrepriseData(BaseModel):
    nom: str
    adresse: Optional[str] = None
    # Contacts enrichis (optionnels)
    dirigeant_nom: Optional[str] = None
    dirigeant_prenom: Optional[str] = None
    rh_nom: Optional[str] = None
    rh_prenom: Optional[str] = None
    rh_role: Optional[str] = None


class GenerateMailRequest(BaseModel):
    candidat: CvData
    campagne: CampagneData
    entreprise: EntrepriseData
    has_lm: bool = False


class GenerateMailResponse(BaseModel):
    subject: str
    body: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_response(raw: str) -> dict:
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

    return {}


def _list_to_str(items: list[str], fallback: str = "Non précisé") -> str:
    return ", ".join(items) if items else fallback


def _build_contact_line(entreprise: EntrepriseData) -> str:
    # Priorité : RH > Dirigeant
    if entreprise.rh_nom or entreprise.rh_prenom:
        name = " ".join(filter(None, [entreprise.rh_prenom, entreprise.rh_nom]))
        role = entreprise.rh_role or "Responsable RH"
        return f"Contact RH connu : {name} ({role})"
    if entreprise.dirigeant_nom or entreprise.dirigeant_prenom:
        name = " ".join(filter(None, [entreprise.dirigeant_prenom, entreprise.dirigeant_nom]))
        return f"Dirigeant connu : {name}"
    return "Aucun contact identifié"


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=GenerateMailResponse)
async def generate_mail(request: GenerateMailRequest):
    """
    Génère un email de candidature spontanée personnalisé.
    Utilise GPT-4o-mini avec les données CV, campagne et entreprise.
    """
    logger.info(f"[GENERATION MAIL] Entreprise='{request.entreprise.nom}' | Poste='{request.campagne.jobTitle}'")

    c = request.candidat
    camp = request.campagne
    ent = request.entreprise

    # Construction des lignes optionnelles
    startDate_line = f"Disponible à partir du : {camp.startDate}" if camp.startDate else ""
    duration_line = f"Durée recherchée : {camp.duration}" if camp.duration else ""
    contact_line = _build_contact_line(ent)
    attachments_line = "CV + Lettre de motivation en pièce jointe" if request.has_lm else "CV en pièce jointe"

    prompt = USER_PROMPT.format(
        nom=c.nom or "Le/La candidat(e)",
        resume=c.resume or "Non disponible",
        formation=_list_to_str(c.formation),
        experience=_list_to_str(c.experience),
        competences=_list_to_str(c.competences_brutes),
        soft_skills=_list_to_str(c.soft_skills),
        langues=_list_to_str(c.langues),
        job_title=camp.jobTitle,
        location=camp.location,
        startDate_line=startDate_line,
        duration_line=duration_line,
        prompt=camp.prompt or "Non précisé",
        company_name=ent.nom,
        company_address=ent.adresse or "Non précisée",
        contact_line=contact_line,
        attachments_line=attachments_line,
    )

    try:
        raw = await call_ai(
            model=MODEL,
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            api_key=settings.CHATGPT_API,
            temperature=0.4,
        )
        logger.info(f"[GENERATION MAIL] Réponse [{ent.nom}] → {raw[:100]}...")
        result = _parse_response(raw)

        if not result.get("subject") or not result.get("body"):
            raise ValueError("Réponse IA incomplète")

    except Exception as e:
        logger.error(f"[GENERATION MAIL] Erreur [{ent.nom}]: {e}")
        # Fallback basique
        result = {
            "subject": f"Candidature spontanée – {camp.jobTitle}",
            "body": (
                f"Madame, Monsieur,\n\n"
                f"Je me permets de vous adresser ma candidature spontanée pour un poste de {camp.jobTitle}.\n\n"
                f"Vous trouverez ci-joint mon CV{' et ma lettre de motivation' if request.has_lm else ''}.\n\n"
                f"Cordialement,\n{c.nom or 'Le candidat'}"
            ),
        }

    return GenerateMailResponse(subject=result["subject"], body=result["body"])
