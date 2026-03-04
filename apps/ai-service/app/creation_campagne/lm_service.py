import io
import logging

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extrait le texte d'un fichier DOCX en conservant l'ordre des paragraphes."""
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extrait le texte brut d'un PDF (extraction directe, pas vision)."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    texts = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(texts).strip()
