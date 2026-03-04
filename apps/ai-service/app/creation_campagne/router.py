import logging
from fastapi import APIRouter, UploadFile, File

from app.creation_campagne.cv_service import extract_cv_data
from app.creation_campagne.lm_service import extract_text_from_docx, extract_text_from_pdf

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/extract-cv")
async def extract_cv(cv: UploadFile = File(...)):
    """
    Extrait les informations d'un CV au format PDF via le modèle vision OVH (Qwen2.5-VL).
    Le PDF est converti en images PNG puis analysé par l'IA pour extraire :
    compétences brutes, soft skills, expériences, et le poste recherché.
    """
    logger.info(f"[CV EXTRACT] Fichier reçu : {cv.filename}  ({cv.content_type})")
    pdf_bytes = await cv.read()
    return await extract_cv_data(pdf_bytes)


@router.post("/extract-lm")
async def extract_lm(lm: UploadFile = File(...)):
    """
    Extrait le texte brut d'une lettre de motivation (PDF ou DOCX).
    Aucune analyse IA — le texte est retourné tel quel pour être stocké
    et personnalisé plus tard à la génération des mails.
    """
    logger.info(f"[LM EXTRACT] Fichier reçu : {lm.filename} ({lm.content_type})")
    file_bytes = await lm.read()

    filename = (lm.filename or "").lower()
    content_type = lm.content_type or ""

    if filename.endswith(".docx") or "wordprocessingml" in content_type:
        lm_text = extract_text_from_docx(file_bytes)
    else:
        lm_text = extract_text_from_pdf(file_bytes)

    if not lm_text.strip():
        logger.warning("[LM EXTRACT] Aucun texte extrait du fichier")
        return {"lm_text": ""}

    logger.info(f"[LM EXTRACT] {len(lm_text)} caractères extraits")
    return {"lm_text": lm_text}
