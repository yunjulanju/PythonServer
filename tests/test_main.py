import pytest
from fastapi.testclient import TestClient

import main
import llm_client
import history
from llm_client import LLMResult


@pytest.fixture(autouse=True)
def fresh_store():
    main.store = history.InMemoryHistoryStore(max_turns=main.settings.max_history_turns)
    yield


@pytest.fixture
def client():
    return TestClient(main.app)


def _chat_body(message="hi"):
    return {
        "player_id": "p1",
        "npc_id": "bob",
        "system_prompt": "You are Bob.",
        "context": "Player waves.",
        "message": message,
    }


def test_chat_success_returns_reply_and_stores_history(client, monkeypatch):
    monkeypatch.setattr(llm_client, "call_llama", lambda messages, settings: LLMResult(True, "hello", None))
    resp = client.post("/chat", json=_chat_body())
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"reply": "hello", "ok": True, "npc_id": "bob", "turn_count": 1, "error": None}
    # history persisted: second call sees turn_count 2
    resp2 = client.post("/chat", json=_chat_body("again"))
    assert resp2.json()["turn_count"] == 2


def test_chat_passes_stored_history_into_prompt(client, monkeypatch):
    captured = {}

    def fake_call(messages, settings):
        captured["messages"] = messages
        return LLMResult(True, "ok", None)

    monkeypatch.setattr(llm_client, "call_llama", fake_call)
    client.post("/chat", json=_chat_body("first"))
    client.post("/chat", json=_chat_body("second"))
    # On the second call the prior turn must appear before the new user message
    contents = [m["content"] for m in captured["messages"]]
    assert "first" in contents
    assert contents[-1] == "second"


def test_chat_failure_returns_ok_false_and_does_not_store(client, monkeypatch):
    monkeypatch.setattr(llm_client, "call_llama", lambda messages, settings: LLMResult(False, "", "llm_timeout"))
    resp = client.post("/chat", json=_chat_body())
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error"] == "llm_timeout"
    assert body["reply"] == ""
    assert body["turn_count"] == 0
    # nothing stored: a subsequent success starts at turn_count 1
    monkeypatch.setattr(llm_client, "call_llama", lambda messages, settings: LLMResult(True, "hi", None))
    resp2 = client.post("/chat", json=_chat_body())
    assert resp2.json()["turn_count"] == 1


def test_reset_clears_history(client, monkeypatch):
    monkeypatch.setattr(llm_client, "call_llama", lambda messages, settings: LLMResult(True, "hi", None))
    client.post("/chat", json=_chat_body())
    resp = client.post("/reset", json={"player_id": "p1", "npc_id": "bob"})
    assert resp.json() == {"ok": True}
    resp2 = client.post("/chat", json=_chat_body())
    assert resp2.json()["turn_count"] == 1


def test_health_reports_llama_status(client, monkeypatch):
    monkeypatch.setattr(llm_client, "ping", lambda settings: False)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"server": True, "llama": False}
