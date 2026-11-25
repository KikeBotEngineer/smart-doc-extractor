"""Etapa 2: capa de texto nativa del PDF."""

from io import BytesIO

from pypdf import PdfReader


def page_texts(data: bytes) -> list[str]:
    """Texto de cada página, en orden. Página sin capa de texto: cadena vacía."""
    return [page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages]
