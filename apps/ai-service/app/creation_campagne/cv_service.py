import re
import json
import base64
import logging
import fitz  # PyMuPDF

from app.core.config import settings
from app.utils.ai_caller import call_ai_vision
from app.creation_campagne.prompts import SYSTEM_PROMPT, USER_PROMPT

logger = logging.getLogger(__name__)

_EMPTY_CV = {
    "nom": "",
    "email": "",
    "telephone": "",
    "formation": [],
    "experience": [],
    "competences_brutes": [],
    "soft_skills": [],
    "langues": [],
    "poste_recherche": "",
    "secteur_recherche": "",
    "resume": "",
}


def pdf_to_images_b64(pdf_bytes: bytes) -> list[str]:
    """
    Convertit chaque page d'un PDF en image PNG encodée en base64.

    Args:
        pdf_bytes: Contenu brut du fichier PDF

    Returns:
        Liste de chaînes base64 (une par page)
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    # Résolution ×2 pour une lisibilité optimale par le modèle vision
    matrix = fitz.Matrix(2, 2)
    for page in doc:
        pixmap = page.get_pixmap(matrix=matrix)
        png_bytes = pixmap.tobytes("png")
        images.append(base64.b64encode(png_bytes).decode("utf-8"))
    doc.close()
    return images


def _parse_response(raw: str) -> dict:
    """Parse la réponse JSON de l'IA (avec fallbacks regex)."""
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


async def extract_cv_data(pdf_bytes: bytes) -> dict:
    """
    Pipeline complet : PDF → images → analyse IA → données structurées.

    Args:
        pdf_bytes: Contenu brut du fichier PDF

    Returns:
        Dictionnaire avec les données extraites du CV
    """
    try:
        images_b64 = pdf_to_images_b64(pdf_bytes)
        logger.info(f"[CV SERVICE] PDF converti en {len(images_b64)} page(s)")

        raw = await call_ai_vision(
            model=settings.MODEL_CV_READER,
            images_b64=images_b64,
            prompt=USER_PROMPT,
            system_prompt=SYSTEM_PROMPT,
        )
        logger.info(f"[CV SERVICE] Réponse IA → {raw[:150]}...")

        data = _parse_response(raw)
        if not data:
            logger.warning("[CV SERVICE] Parsing JSON échoué, retour structure vide")
            return _EMPTY_CV.copy()

        # Fusion avec les valeurs par défaut pour garantir tous les champs
        result = _EMPTY_CV.copy()
        result.update({k: v for k, v in data.items() if k in _EMPTY_CV})
        return result

    except Exception as e:
        logger.error(f"[CV SERVICE] Erreur extraction CV : {e}")
        return _EMPTY_CV.copy()
