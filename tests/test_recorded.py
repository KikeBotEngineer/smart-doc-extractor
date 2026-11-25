import pytest

from app.config import Settings
from app.doc_types.invoice import Invoice
from app.doc_types.resume import Resume
from app.llm import make_llm
from app.llm.client import LLMError, LLMResponse
from app.llm.gemini import GeminiLLM
from app.llm.recorded import RecordedLLM, recording_key


class CountingLLM:
    def __init__(self):
        self.calls = 0

    def generate(self, prompt, schema, images=()):
        self.calls += 1
        return LLMResponse('{"total": 1.5}', 10, 2)


def test_records_then_replays_without_network(tmp_path):
    live = CountingLLM()
    first = RecordedLLM(tmp_path, live).generate("p", Invoice, [b"img"])
    replay = RecordedLLM(tmp_path).generate("p", Invoice, [b"img"])
    assert first == replay == LLMResponse('{"total": 1.5}', 10, 2)
    RecordedLLM(tmp_path, live).generate("p", Invoice, [b"img"])
    assert live.calls == 1  # lo grabado no se vuelve a pedir


def test_missing_recording_raises(tmp_path):
    with pytest.raises(LLMError, match="sin grabación"):
        RecordedLLM(tmp_path).generate("p", Invoice)


def test_key_changes_with_prompt_schema_and_images():
    base = recording_key("p", Invoice, [])
    assert base == recording_key("p", Invoice, [])
    assert len({base, recording_key("q", Invoice, []), recording_key("p", Resume, [])}) == 3
    assert base != recording_key("p", Invoice, [b"img"])


def test_make_llm_modes(tmp_path):
    assert isinstance(make_llm(Settings(llm_mode="recorded")), RecordedLLM)
    assert isinstance(make_llm(Settings(llm_mode="live", gemini_api_key="k")), GeminiLLM)
    recorder = make_llm(Settings(llm_mode="record", gemini_api_key="k"))
    assert isinstance(recorder, RecordedLLM) and isinstance(recorder.live, GeminiLLM)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        make_llm(Settings(llm_mode="live", gemini_api_key=None))
