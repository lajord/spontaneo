import base64
import io
import logging
import re
from copy import deepcopy
from pathlib import Path
from typing import Optional

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.generation_lm.prompts import SYSTEM_PROMPT
from app.generation_mail.router import _parse_response
from app.utils.ai_caller import call_ai

logger = logging.getLogger(__name__)
router = APIRouter()

MODEL = settings.MODEL_CREATION_LM
TEMPLATE_PATH = Path(__file__).parent / "Lettre de motivation template.docx"


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
    lm_docx_b64:   Optional[str] = None   # DOCX bytes encodés en base64


# ── Helpers texte brut ─────────────────────────────────────────────────────────

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


# ── Helpers DOCX template ──────────────────────────────────────────────────────

def _para_full_text(para) -> str:
    return "".join(run.text for run in para.runs)


def _replace_in_para(para, vals: dict) -> None:
    """Replace balises in a paragraph's runs, preserving indentation and formatting.
    Only merges runs when a placeholder is actually detected (to avoid touching unrelated paragraphs).
    """
    full = _para_full_text(para)
    if not any(f"{{{{ {key} }}}}" in full for key in vals):
        return  # Aucune balise → on ne touche pas aux runs
    for key, val in vals.items():
        full = full.replace(f"{{{{ {key} }}}}", val)
    if para.runs:
        para.runs[0].text = full
        for run in para.runs[1:]:
            run.text = ""


def _set_para_right_align(para) -> None:
    """Force l'alignement à droite sur un paragraphe via w:jc right."""
    pPr = para._element.find(qn('w:pPr'))
    if pPr is None:
        pPr = OxmlElement('w:pPr')
        para._element.insert(0, pPr)
    for jc in pPr.findall(qn('w:jc')):
        pPr.remove(jc)
    jc = OxmlElement('w:jc')
    jc.set(qn('w:val'), 'right')
    pPr.append(jc)


def _clean_tabs_from_para(para) -> None:
    """Supprime tous les éléments <w:tab/> des runs d'un paragraphe (héritage template)."""
    for r in para._element.findall('.//' + qn('w:r')):
        for tab in r.findall(qn('w:tab')):
            r.remove(tab)


def _insert_para_before(ref_para, text: str) -> None:
    """Insert a new paragraph with text immediately before ref_para, copying its formatting.
    Les \\n dans text deviennent des w:br (sauts de ligne dans Word) pour respecter
    la mise en forme originale de la lettre de motivation.
    Un espacement après le paragraphe est appliqué pour séparer visuellement les blocs.
    """
    new_p = OxmlElement('w:p')
    pPr = ref_para._element.find(qn('w:pPr'))
    if pPr is not None:
        new_pPr = deepcopy(pPr)
    else:
        new_pPr = OxmlElement('w:pPr')
    # Espacement après chaque paragraphe du corps (~11pt) pour séparation visuelle
    for sp in new_pPr.findall(qn('w:spacing')):
        new_pPr.remove(sp)
    spacing = OxmlElement('w:spacing')
    spacing.set(qn('w:after'), '160')
    new_pPr.append(spacing)
    new_p.append(new_pPr)

    orig_r = ref_para._element.find(qn('w:r'))
    rPr = None
    if orig_r is not None:
        rPr = orig_r.find(qn('w:rPr'))

    lines = text.split('\n')
    for i, line in enumerate(lines):
        new_r = OxmlElement('w:r')
        if rPr is not None:
            new_r.append(deepcopy(rPr))
        new_t = OxmlElement('w:t')
        new_t.text = line
        new_t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        new_r.append(new_t)
        new_p.append(new_r)
        if i < len(lines) - 1:
            br_r = OxmlElement('w:r')
            if rPr is not None:
                br_r.append(deepcopy(rPr))
            br_r.append(OxmlElement('w:br'))
            new_p.append(br_r)

    ref_para._element.addprevious(new_p)


def build_docx_from_template(structured: LmStructured) -> bytes:
    """
    Ouvre le template DOCX, remplace les {{ balises }} par les données structurées.
    Les balises vides → ligne supprimée.
    {{ corps }} → expansion en plusieurs paragraphes.
    Retourne les bytes DOCX.
    """
    doc = Document(TEMPLATE_PATH)

    # Correspondance balise template → valeur (les noms du template peuvent différer du modèle)
    vals: dict[str, str] = {
        "exp_prenom_nom": structured.exp_prenom_nom or "",
        "exp_adresse":    structured.exp_adresse or "",
        "exp_ville":      structured.exp_ville or "",
        "exp_telephone":  structured.exp_telephone or "",
        "exp_mail":       structured.exp_email or "",      # template: exp_mail ≠ exp_email
        "dest_nom":       structured.dest_nom or "",
        "dest_services":  structured.dest_service or "",  # template: dest_services ≠ dest_service
        "dest_adresse":   structured.dest_adresse or "",
        "dest_ville":     structured.dest_ville or "",
        "date":           structured.date or "",
        "objet":          structured.objet or "",
        "salution":       structured.salutation or "",     # template: salution (typo)
        "prenom_nom":     structured.prenom_nom or "",
    }

    # Balises du bloc destinataire → alignement à droite + nettoyage tabs
    DEST_KEYS = {"dest_nom", "dest_services", "dest_adresse", "dest_ville"}

    corps_text = structured.corps or ""
    all_paras = list(doc.paragraphs)
    to_remove: list = []
    corps_para = None

    for para in all_paras:
        raw = _para_full_text(para)

        # Placeholder corps → expansion spéciale
        if re.search(r'\{\{\s*corps\s*\}\}', raw):
            corps_para = para
            continue

        # Paragraphe ne contenant QU'UNE balise → vérif alignement + suppression si vide
        stripped = raw.strip()
        m = re.fullmatch(r'\{\{\s*(\w+)\s*\}\}', stripped)
        if m:
            key = m.group(1)
            # Bloc destinataire : aligner à droite et nettoyer les tabs hérités du template
            if key in DEST_KEYS:
                _set_para_right_align(para)
                _clean_tabs_from_para(para)
            # Balise vide → supprimer la ligne
            if key in vals and not vals[key]:
                to_remove.append(para)
                continue

        _replace_in_para(para, vals)

    # Suppression des lignes vides
    for para in to_remove:
        para._element.getparent().remove(para._element)

    # Expansion du corps
    if corps_para is not None:
        corps_paragraphs = [p for p in corps_text.split('\n\n') if p.strip()]
        for cp_text in corps_paragraphs:
            _insert_para_before(corps_para, cp_text)
        corps_para._element.getparent().remove(corps_para._element)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=GenerateLmResponse)
async def generate_lm(request: GenerateLmRequest):
    """
    Adapte une lettre de motivation existante à une entreprise et un destinataire spécifiques.
    Retourne la LM en texte brut (pour l'UI) ET en DOCX base64 (généré depuis le template).
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
        raw = await call_ai(
            model=MODEL,
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.4,
        )

        parsed = _parse_response(raw)
        if parsed and "corps" in parsed:
            structured = LmStructured(**{k: v for k, v in parsed.items() if v is not None and v != ""})
            plain = _structured_to_plain(structured)
            logger.info(f"[GENERATION LM] LM structurée pour '{ent.nom}' ({len(plain)} caractères)")

            # Génération DOCX depuis le template
            lm_docx_b64: Optional[str] = None
            try:
                docx_bytes = build_docx_from_template(structured)
                lm_docx_b64 = base64.b64encode(docx_bytes).decode('utf-8')
                logger.info(f"[GENERATION LM] DOCX généré pour '{ent.nom}' ({len(docx_bytes)} bytes)")
            except Exception as docx_err:
                logger.warning(f"[GENERATION LM] Erreur DOCX pour '{ent.nom}': {docx_err}")

            return GenerateLmResponse(lm_adapted=plain, lm_structured=structured, lm_docx_b64=lm_docx_b64)

        # Fallback : l'IA a renvoyé du texte brut (non JSON)
        logger.warning(f"[GENERATION LM] Réponse non structurée pour '{ent.nom}', fallback texte brut")
        return GenerateLmResponse(lm_adapted=raw.strip())

    except Exception as e:
        logger.error(f"[GENERATION LM] Erreur pour '{ent.nom}': {e}")
        return GenerateLmResponse(lm_adapted=request.lm_text)
