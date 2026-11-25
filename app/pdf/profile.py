"""Etapa 3: perfil de calidad por página."""

from typing import Literal

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

PageProfile = Literal["digital", "scanned", "empty"]

MIN_TEXT_DENSITY = 0.5  # caracteres por 10,000 pt²; ~24 caracteres en una hoja carta
MIN_IMAGE_RATIO = 0.3  # fracción de la página cubierta por imágenes


def classify_page(text: str, page_area: float, image_area: float) -> PageProfile:
    # ponytail: no detecta capas de texto basura (fuentes mal codificadas); agregar
    # una proporción de caracteres legibles si aparecen en el dataset.
    density = len("".join(text.split())) / page_area * 10_000
    if density >= MIN_TEXT_DENSITY:
        return "digital"
    return "scanned" if image_area / page_area >= MIN_IMAGE_RATIO else "empty"


def profile_pages(data: bytes, texts: list[str]) -> list[PageProfile]:
    pdf = pdfium.PdfDocument(data)
    try:
        profiles = []
        for page, text in zip(pdf, texts, strict=True):
            width, height = page.get_size()
            images = page.get_objects(filter=(pdfium_c.FPDF_PAGEOBJ_IMAGE,))
            image_area = sum(_clipped_area(img.get_bounds(), width, height) for img in images)
            profiles.append(classify_page(text, width * height, min(image_area, width * height)))
        return profiles
    finally:
        pdf.close()


def _clipped_area(box: tuple[float, float, float, float], width: float, height: float) -> float:
    left, bottom, right, top = box
    return max(0.0, min(right, width) - max(left, 0)) * max(0.0, min(top, height) - max(bottom, 0))
