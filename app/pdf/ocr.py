"""Render de páginas y OCR con RapidOCR (ONNX; los modelos vienen en el paquete)."""

from functools import lru_cache
from io import BytesIO

import pypdfium2 as pdfium
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

from app.pdf import PDFIUM_LOCK

DPI = 150  # el escaneo típico; más resolución casi duplica el tiempo de OCR
# Tope por página: A0 a 150 dpi (~17.5 MP) cabe; una página gigante de un PDF hostil
# (14400 pt por lado → 30,000 px, 2.7 GB) se renderiza a menor resolución.
MAX_PIXELS = 20_000_000

# Caja de RapidOCR: 4 esquinas [x, y]
Box = list[list[float]]


def render_page(data: bytes, index: int) -> Image.Image:
    """Imagen RGB de una página (índice base 0), a DPI o menos si pasa de MAX_PIXELS."""
    with PDFIUM_LOCK:
        pdf = pdfium.PdfDocument(data)
        try:
            page = pdf[index]
            width, height = page.get_size()
            scale = min(DPI / 72, (MAX_PIXELS / max(width * height, 1)) ** 0.5)
            return page.render(scale=scale).to_pil().convert("RGB")
        finally:
            pdf.close()


def to_jpeg(image: Image.Image) -> bytes:
    buf = BytesIO()
    image.save(buf, "JPEG", quality=85)
    return buf.getvalue()


@lru_cache(maxsize=1)
def _engine() -> RapidOCR:
    return RapidOCR()


def ocr_image(image: Image.Image) -> tuple[str, float]:
    """Texto en orden de lectura y confianza media (0 a 1)."""
    # ponytail: ~4 s por página en CPU y una sola confianza por página; paralelizar
    # páginas o calificar por línea si la latencia o la calibración lo piden.
    result, _ = _engine()(image)
    if not result:
        return "", 0.0
    text = "\n".join(group_lines([(box, txt) for box, txt, _ in result]))
    return text, sum(score for *_, score in result) / len(result)


def group_lines(items: list[tuple[Box, str]]) -> list[str]:
    """Une en una línea las cajas cuyo centro vertical coincide y las ordena de izquierda
    a derecha. RapidOCR a veces entrega una fila de tabla en desorden."""
    boxes = []
    for box, text in items:
        ys, xs = [p[1] for p in box], [p[0] for p in box]
        boxes.append(((min(ys) + max(ys)) / 2, max(ys) - min(ys), min(xs), text))
    lines: list[tuple[float, list[tuple[float, str]]]] = []
    for center, height, left, text in sorted(boxes):
        if lines and abs(center - lines[-1][0]) < height / 2:
            lines[-1][1].append((left, text))
        else:
            lines.append((center, [(left, text)]))
    return [" ".join(text for _, text in sorted(words)) for _, words in lines]
