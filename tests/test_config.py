import importlib
import config


def test_defaults(monkeypatch):
    for var in ("LLAMA_BASE_URL", "MAX_HISTORY_TURNS", "REQUEST_TIMEOUT", "LLAMA_MODEL"):
        monkeypatch.delenv(var, raising=False)
    s = config.load_settings()
    assert s.llama_base_url == "http://127.0.0.1:8080"
    assert s.max_history_turns == 10
    assert s.request_timeout == 30.0
    assert s.llama_model == "local"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("LLAMA_BASE_URL", "http://example:9000")
    monkeypatch.setenv("MAX_HISTORY_TURNS", "3")
    monkeypatch.setenv("REQUEST_TIMEOUT", "5")
    monkeypatch.setenv("LLAMA_MODEL", "mymodel")
    s = config.load_settings()
    assert s.llama_base_url == "http://example:9000"
    assert s.max_history_turns == 3
    assert s.request_timeout == 5.0
    assert s.llama_model == "mymodel"
