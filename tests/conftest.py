import pytest


@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch):
    """Los reintentos del LLM no esperan en las pruebas."""
    monkeypatch.setattr("app.llm.client.RETRY_WAIT_S", 0)
