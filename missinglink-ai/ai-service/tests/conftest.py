import pytest


@pytest.fixture(autouse=True)
def disable_db_bootstrap(monkeypatch):
    monkeypatch.setenv("AI_BOOTSTRAP_ON_START", "false")
    monkeypatch.setenv("AI_API_KEY", "change-me-ai-key")
    yield
