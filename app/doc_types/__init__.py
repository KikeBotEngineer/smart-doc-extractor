"""Registro de tipos de documento. Cada módulo expone LABEL, MODEL, IDENTIFIERS y KEYWORDS."""

from types import ModuleType

from app.doc_types import invoice, resume

DOC_TYPES: dict[str, ModuleType] = {"invoice": invoice, "resume": resume}
