import logging
from fastapi import APIRouter, UploadFile, File

from app.creation_campagne.cv_service import extract_cv_data

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
