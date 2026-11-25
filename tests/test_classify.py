import json

import pytest

from app.classify import classify, keyword_scores
from app.evidence import PageText
from app.llm.client import LLMResponse, Usage


class EnumLLM:
    def __init__(self, answer):
        self.answer, self.prompts = answer, []

    def generate(self, prompt, schema, images=()):
        self.prompts.append(prompt)
        return LLMResponse(json.dumps({"doc_type": self.answer}), 20, 2)


def test_keywords_are_whole_words_and_ignore_accents():
    scores = keyword_scores("EXPERIENCIA laboral · Educacion · Habilidades: Python. Activa")
    assert scores == {"invoice": 0, "resume": 3}  # "iva" dentro de "Activa" no cuenta


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Factura No. A-1 RFC: X Subtotal $1 IVA 16% Total", "invoice"),
        ("Perfil\nExperiencia\nEducación\nHabilidades", "resume"),
        ("Factura No.F-77336 RFC:EXD410411Y5R Subtotal IVA16% TOTAL", "invoice"),  # OCR
    ],
)
def test_clear_keywords_need_no_llm(text, expected):
    llm, usage = EnumLLM("other"), Usage()
    result = classify(llm, [PageText(text)], usage)
    assert (result.value, result.method, result.confidence) == (expected, "keywords", "high")
    assert llm.prompts == [] and usage.llm_calls == 0


def test_ambiguous_text_asks_the_llm_with_an_enum():
    llm, usage = EnumLLM("resume"), Usage()
    result = classify(llm, [PageText("Ana López — Ingeniera de datos, 8 años en banca")], usage)
    assert (result.value, result.method, result.confidence) == ("resume", "llm", "medium")
    assert usage.llm_calls == 1
    assert "- invoice: factura" in llm.prompts[0] and "- other:" in llm.prompts[0]


def test_tie_on_keywords_asks_the_llm():
    llm = EnumLLM("invoice")
    assert classify(llm, [PageText("factura rfc experiencia perfil")], Usage()).method == "llm"


def test_unsupported_document_is_none():
    assert classify(EnumLLM("other"), [PageText("Contrato de arrendamiento")], Usage()) is None
