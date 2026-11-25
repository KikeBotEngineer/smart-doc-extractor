import json
from types import SimpleNamespace

import pytest

from app.doc_types.invoice import Invoice
from app.llm.client import LLMError, LLMResponse, Usage
from app.llm.gemini import GeminiLLM
from app.pipeline import extract_fast, render_document

VALID = json.dumps({"invoice_number": "A-1042", "total": 1160.0})


class ScriptedLLM:
    """Devuelve las respuestas en orden; una excepción en la lista se lanza."""

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.prompts = []

    def generate(self, prompt, schema, images=()):
        self.prompts.append(prompt)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return LLMResponse(out, input_tokens=100, output_tokens=10)


def test_render_document_keeps_page_numbers_and_skips_empty():
    expected = "--- Página 1 ---\nuno\n\n--- Página 3 ---\ntres"
    assert render_document(["uno", "  ", "tres"]) == expected


def test_fast_route_returns_model_and_usage():
    llm, usage = ScriptedLLM(VALID), Usage()
    inv = extract_fast(llm, "invoice", ["Factura No. A-1042\nTOTAL $1,160.00"], usage)
    assert inv == Invoice(invoice_number="A-1042", total=1160.0)
    assert usage == Usage(llm_calls=1, input_tokens=100, output_tokens=10)
    assert "Factura No. A-1042" in llm.prompts[0] and "factura" in llm.prompts[0]


def test_invalid_output_is_retried_with_the_error():
    llm, usage = ScriptedLLM('{"total": "mucho"}', VALID), Usage()
    assert extract_fast(llm, "invoice", ["x"], usage).invoice_number == "A-1042"
    assert usage.llm_calls == 2
    assert "no cumplió el esquema" in llm.prompts[1]


def test_call_error_is_retried_once():
    llm, usage = ScriptedLLM(LLMError("timeout"), VALID), Usage()
    assert extract_fast(llm, "invoice", ["x"], usage).total == 1160.0
    assert usage.llm_calls == 1  # la llamada fallida no reporta tokens


def test_two_failures_raise():
    with pytest.raises(LLMError):
        extract_fast(ScriptedLLM("no es json", "{}x"), "invoice", ["x"], Usage())
    with pytest.raises(LLMError):
        extract_fast(ScriptedLLM(LLMError("a"), LLMError("b")), "invoice", ["x"], Usage())


class FakeModels:
    def __init__(self, result):
        self.result, self.calls = result, []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_gemini_sends_schema_at_temperature_zero_and_reports_tokens():
    meta = SimpleNamespace(prompt_token_count=50, candidates_token_count=7, thoughts_token_count=3)
    models = FakeModels(SimpleNamespace(text=VALID, usage_metadata=meta))
    llm = GeminiLLM("key", "gemini-x", client=SimpleNamespace(models=models))
    assert llm.generate("p", Invoice) == LLMResponse(VALID, 50, 10)
    config = models.calls[0]["config"]
    assert models.calls[0]["model"] == "gemini-x"
    assert config.temperature == 0
    assert config.response_json_schema == Invoice.model_json_schema()


def test_gemini_wraps_errors():
    models = FakeModels(RuntimeError("503"))
    with pytest.raises(LLMError):
        GeminiLLM("key", "m", client=SimpleNamespace(models=models)).generate("p", Invoice)
