import logging
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.utils.ai_caller import call_ai_gemini
from app.generation_lm.prompts import SYSTEM_PROMPT
from app.generation_mail.router import _parse_response

logger = logging.getLogger(__name__)
router = APIRouter()

MODEL = settings.GEMINI_MODEL


# ── Schémas ────────────────────────────────────────────────────────────────────

class EntrepriseData(BaseModel):
    nom: str
    adresse: Optional[str] = None
    site_web: Optional[str] = None
    secteur: Optional[str] = None


class GenerateLmRequest(BaseModel):
    lm_text: str
    entreprise: EntrepriseData
    secteur: Optional[str] = None
    description: Optional[str] = None
    cv_resume: Optional[str] = None
    campaign_prompt: Optional[str] = None
    destinataire_civilite: Optional[str] = None
    destinataire_prenom: Optional[str] = None
    destinataire_nom: Optional[str] = None
    destinataire_role: Optional[str] = None


class LmStructured(BaseModel):
    exp_prenom_nom: Optional[str] = None
    exp_adresse:    Optional[str] = None
    exp_ville:      Optional[str] = None
    exp_telephone:  Optional[str] = None
    exp_email:      Optional[str] = None
    dest_nom:       Optional[str] = None
    dest_service:   Optional[str] = None
    dest_adresse:   Optional[str] = None
    dest_ville:     Optional[str] = None
    date:           Optional[str] = None
    objet:          Optional[str] = None
    salutation:     Optional[str] = None
    corps:          Optional[str] = None
    prenom_nom:     Optional[str] = None


class GenerateLmResponse(BaseModel):
    lm_adapted:    str
    lm_structured: Optional[LmStructured] = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _structured_to_plain(s: LmStructured) -> str:
    """Reconstruit un texte brut depuis les champs structurés (pour affichage UI)."""
    parts: list[str] = []
    exp_lines = [s.exp_prenom_nom, s.exp_adresse, s.exp_ville, s.exp_telephone, s.exp_email]
    exp_block = "\n".join(l for l in exp_lines if l)
    if exp_block:
        parts.append(exp_block)
    dest_lines = [s.dest_nom, s.dest_service, s.dest_adresse, s.dest_ville]
    dest_block = "\n".join(l for l in dest_lines if l)
    if dest_block:
        parts.append(dest_block)
    if s.date:
        parts.append(s.date)
    if s.objet:
        parts.append(f"Objet : {s.objet}")
    if s.salutation:
        parts.append(s.salutation)
    if s.corps:
        parts.append(s.corps)
    if s.prenom_nom:
        parts.append(f"Cordialement,\n{s.prenom_nom}")
    return "\n\n".join(parts)


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=GenerateLmResponse)
async def generate_lm(request: GenerateLmRequest):
    """
    Adapte une lettre de motivation existante à une entreprise et un destinataire spécifiques.
    Retourne la LM en texte brut (pour l'UI) ET en JSON structuré (pour le DOCX formaté).
    """
    ent = request.entreprise
    logger.info(f"[GENERATION LM] Adaptation pour '{ent.nom}'")

    if request.destinataire_prenom or request.destinataire_nom:
        dest_name = " ".join(filter(None, [request.destinataire_prenom, request.destinataire_nom]))
        dest_civ = request.destinataire_civilite or "Madame/Monsieur"
        dest_role = request.destinataire_role or ""
        destinataire_line = f"{dest_civ} {dest_name}{f' ({dest_role})' if dest_role else ''}"
    elif request.destinataire_civilite:
        destinataire_line = request.destinataire_civilite
    else:
        destinataire_line = "Aucun contact identifié — utiliser 'Madame, Monsieur'"

    prompt = f"""=== ENTREPRISE DESTINATAIRE ===
Nom : {ent.nom}
Adresse : {ent.adresse or "Non précisée"}
Secteur / activité : {request.secteur or "Non précisé"}

=== DESTINATAIRE ===
{destinataire_line}

=== PROFIL CANDIDAT (Résumé CV) ===
{request.cv_resume or "Non disponible"}

=== OBJECTIFS / INSTRUCTIONS DU CANDIDAT ===
{request.campaign_prompt or "Non précisé"}

=== LETTRE DE MOTIVATION ORIGINALE À ADAPTER ===
{request.lm_text}"""

    try:
        raw = await call_ai_gemini(
            model=MODEL,
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            api_key=settings.GEMINI_API_KEY,
            temperature=0.4,
        )

        parsed = _parse_response(raw)
        if parsed and "corps" in parsed:
            structured = LmStructured(**{k: v for k, v in parsed.items() if v is not None and v != ""})
            plain = _structured_to_plain(structured)
            logger.info(f"[GENERATION LM] LM structurée pour '{ent.nom}' ({len(plain)} caractères)")
            return GenerateLmResponse(lm_adapted=plain, lm_structured=structured)

        # Fallback : l'IA a renvoyé du texte brut (non JSON)
        logger.warning(f"[GENERATION LM] Réponse non structurée pour '{ent.nom}', fallback texte brut")
        return GenerateLmResponse(lm_adapted=raw.strip())

    except Exception as e:
        logger.error(f"[GENERATION LM] Erreur pour '{ent.nom}': {e}")
        return GenerateLmResponse(lm_adapted=request.lm_text)
