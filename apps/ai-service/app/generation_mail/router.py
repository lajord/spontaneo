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

MODEL = settings.MODEL_CREATION_MAIL


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
    site_web: Optional[str] = None
    secteur: Optional[str] = None


class ContactPrincipal(BaseModel):
    civilite: Optional[str] = None   # "Monsieur" | "Madame" | None
    prenom: Optional[str] = None
    nom: Optional[str] = None
    role: Optional[str] = None


class GenerateMailRequest(BaseModel):
    candidat: CvData
    campagne: CampagneData
    entreprise: EntrepriseData
    contact_principal: Optional[ContactPrincipal] = None
    user_mail_template: Optional[str] = None   # None = utiliser le template bullet-point par défaut
    template_prompt: Optional[str] = None      # consignes supplémentaires
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


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=GenerateMailResponse)
async def generate_mail(request: GenerateMailRequest):
    """
    Génère un email de candidature spontanée personnalisé.
    Reçoit toute la data (CV, campagne, entreprise, contact, template optionnel).
    Utilise Gemini Flash — rapide et économique.
    """
    logger.info(f"[GENERATION MAIL] Entreprise='{request.entreprise.nom}' | Poste='{request.campagne.jobTitle}'")

    c = request.candidat
    camp = request.campagne
    ent = request.entreprise

    # Blocs optionnels campagne
    startDate_line = f"Disponible à partir du : {camp.startDate}" if camp.startDate else ""
    duration_line = f"Durée recherchée : {camp.duration}" if camp.duration else ""

    # Bloc entreprise
    site_line = f"Site web : {ent.site_web}" if ent.site_web else ""
    secteur_line = f"Secteur : {ent.secteur}" if ent.secteur else ""

    # Bloc destinataire
    if request.contact_principal:
        cp = request.contact_principal
        parts = [p for p in [cp.civilite, cp.prenom, cp.nom] if p]
        contact_block = " ".join(parts)
        if cp.role:
            contact_block += f" ({cp.role})"
    else:
        contact_block = "Aucun contact identifié — utiliser 'Madame, Monsieur'"

    # Bloc template
    if request.user_mail_template:
        template_block = f"=== TEMPLATE UTILISATEUR (à personnaliser) ===\n{request.user_mail_template}"
    else:
        template_block = "=== TEMPLATE === Utiliser le template bullet-point par défaut."

    # Bloc consignes supplémentaires
    template_prompt_block = (
        f"\n=== CONSIGNES SUPPLÉMENTAIRES ===\n{request.template_prompt}"
        if request.template_prompt else ""
    )

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
        site_line=site_line,
        secteur_line=secteur_line,
        contact_block=contact_block,
        template_block=template_block,
        template_prompt_block=template_prompt_block,
    )

    try:
        raw = await call_ai(
            model=MODEL,
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.4,
        )
        logger.info(f"[GENERATION MAIL] Réponse [{ent.nom}] → {raw[:100]}...")
        result = _parse_response(raw)

        if not result.get("subject") or not result.get("body"):
            raise ValueError("Réponse IA incomplète")

    except Exception as e:
        logger.error(f"[GENERATION MAIL] Erreur [{ent.nom}]: {e}")
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
