import secrets
import threading
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from app.config import Settings
from app.doc_types import DOC_TYPES
from app.llm import make_llm
from app.llm.client import LLMClient, LLMError
from app.pipeline import RejectedInput, run
from app.schemas import ExtractResponse

app = FastAPI(title="smart-doc-extractor")

DocTypeName = Literal[tuple(DOC_TYPES)]  # FastAPI responde 422 a un tipo desconocido


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_llm() -> LLMClient:
    return make_llm(get_settings())


def require_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    if not settings.api_key:
        return
    if x_api_key is None or not secrets.compare_digest(
        x_api_key.encode(), settings.api_key.encode()
    ):
        raise HTTPException(401, "API key inválida o ausente")


@lru_cache
def slots(size: int) -> threading.BoundedSemaphore:
    return threading.BoundedSemaphore(size)


def extraction_slot(settings: Annotated[Settings, Depends(get_settings)]) -> Iterator[None]:
    """Sin lugar libre se responde 503 de inmediato: esperar solo acumula hilos y memoria."""
    slot = slots(settings.max_concurrent)
    if not slot.acquire(blocking=False):
        raise HTTPException(503, "servicio ocupado; reintenta", headers={"Retry-After": "10"})
    try:
        yield
    finally:
        slot.release()


@app.exception_handler(RejectedInput)
def rejected_input(_: Request, exc: RejectedInput) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(LLMError)
def llm_failed(_: Request, exc: LLMError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/doc-types")
def doc_types() -> dict:
    return {
        name: {
            "label": kind.LABEL,
            "fields": kind.MODEL.model_json_schema(),
            "rules": [rule.__name__ for rule in kind.RULES],
        }
        for name, kind in DOC_TYPES.items()
    }


@app.post("/extract", dependencies=[Depends(require_api_key), Depends(extraction_slot)])
def extract(
    file: Annotated[UploadFile, File(description="PDF de hasta 10 MB y 20 páginas")],
    settings: Annotated[Settings, Depends(get_settings)],
    llm: Annotated[LLMClient, Depends(get_llm)],
    doc_type: Annotated[DocTypeName | None, Form()] = None,
) -> ExtractResponse:
    # Def síncrono: PDF y OCR son CPU; FastAPI lo corre en su threadpool.
    data = file.file.read(settings.max_file_mb * 1024 * 1024 + 1)  # +1 para detectar el exceso
    return run(data, doc_type, llm, settings)
