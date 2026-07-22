# UE5 ↔ llama.cpp Relay Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI relay server that lets UE5 NPCs hold stateful conversations with a local llama.cpp server.

**Architecture:** UE5 sends `POST /chat` with the NPC persona (system prompt), per-turn context, and the player's message. The server keeps per-`(player_id, npc_id)` conversation history (in-memory, sliding window), assembles an OpenAI-style `messages` array, calls llama.cpp's OpenAI-compatible endpoint, and returns simple JSON. Failures return HTTP 200 with `ok:false` + an error code.

**Tech Stack:** Python 3.11, FastAPI, httpx (llama.cpp client + TestClient), pytest. Flat modules at repo root, tests in `tests/`.

## Global Constraints

- Python 3.11 (installed: 3.11.9). Native union syntax like `str | None` is available — no `from __future__ import annotations` needed.
- All source modules are flat files at repo root: `config.py`, `history.py`, `prompt.py`, `llm_client.py`, `main.py`.
- Tests live in `tests/` and import source modules by top-level name (`import history`). `pytest.ini` sets `pythonpath = .`.
- Run every command from the repo root `C:\Work\PythonServer` using the venv interpreter: `.venv\Scripts\python.exe -m <tool>` (PowerShell). In git-bash the path is `.venv/Scripts/python -m <tool>`.
- llama.cpp is assumed running at `http://127.0.0.1:8080` exposing the OpenAI-compatible `/v1/chat/completions`. Tests NEVER hit the real server — they mock `httpx`.
- Response contract is fixed by the spec: `/chat` always returns HTTP 200; success/failure is signalled by the `ok` boolean and, on failure, `error` ∈ {`llm_unavailable`, `llm_timeout`}.
- A "turn" = one user message + one assistant reply. The sliding window keeps the most recent `MAX_HISTORY_TURNS` turns.

---

### Task 1: Project scaffold + configuration

**Files:**
- Create: `requirements.txt`, `pytest.ini`, `.gitignore`, `config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `config.Settings` — frozen dataclass with fields `llama_base_url: str`, `max_history_turns: int`, `request_timeout: float`, `llama_model: str`.
  - `config.load_settings() -> Settings` — reads env vars `LLAMA_BASE_URL`, `MAX_HISTORY_TURNS`, `REQUEST_TIMEOUT`, `LLAMA_MODEL`, falling back to defaults `http://127.0.0.1:8080`, `10`, `30.0`, `local`.

- [ ] **Step 1: Initialize git and create the virtualenv**

Run (PowerShell, from repo root):
```powershell
git init
python -m venv .venv
```
Expected: `.venv\` directory created; `git init` prints "Initialized empty Git repository".

- [ ] **Step 2: Create `requirements.txt`**

```
fastapi==0.111.0
uvicorn[standard]==0.30.1
httpx==0.27.0
pytest==8.2.2
```

- [ ] **Step 3: Create `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.env
```

- [ ] **Step 4: Create `pytest.ini`**

```ini
[pytest]
pythonpath = .
testpaths = tests
```

- [ ] **Step 5: Install dependencies**

Run:
```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```
Expected: installs fastapi, uvicorn, httpx, pytest and their deps; ends with "Successfully installed ...".

- [ ] **Step 6: Write the failing test** — `tests/test_config.py`

```python
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
```

- [ ] **Step 7: Run test to verify it fails**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_config.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'config'`.

- [ ] **Step 8: Write `config.py`**

```python
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    llama_base_url: str = "http://127.0.0.1:8080"
    max_history_turns: int = 10
    request_timeout: float = 30.0
    llama_model: str = "local"


def load_settings() -> Settings:
    return Settings(
        llama_base_url=os.getenv("LLAMA_BASE_URL", "http://127.0.0.1:8080"),
        max_history_turns=int(os.getenv("MAX_HISTORY_TURNS", "10")),
        request_timeout=float(os.getenv("REQUEST_TIMEOUT", "30")),
        llama_model=os.getenv("LLAMA_MODEL", "local"),
    )
```

- [ ] **Step 9: Run test to verify it passes**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_config.py -v
```
Expected: PASS (2 passed).

- [ ] **Step 10: Commit**

```powershell
git add requirements.txt pytest.ini .gitignore config.py tests/test_config.py
git commit -m "feat: project scaffold and config loading"
```

---

### Task 2: Conversation history store

**Files:**
- Create: `history.py`
- Test: `tests/test_history.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `history.Turn` — dataclass with `user: str`, `assistant: str`.
  - `history.HistoryStore` — abstract base with `get(player_id: str, npc_id: str) -> list[Turn]`, `append(player_id: str, npc_id: str, turn: Turn) -> None`, `reset(player_id: str, npc_id: str) -> None`.
  - `history.InMemoryHistoryStore(max_turns: int)` — concrete implementation. `get` returns a copy of the stored turns (never the internal list). `append` adds a turn and trims to the most recent `max_turns`. Keys are `(player_id, npc_id)` tuples; different keys are isolated.

- [ ] **Step 1: Write the failing test** — `tests/test_history.py`

```python
from history import Turn, InMemoryHistoryStore


def test_append_and_get():
    store = InMemoryHistoryStore(max_turns=10)
    store.append("p1", "n1", Turn("hi", "hello"))
    turns = store.get("p1", "n1")
    assert turns == [Turn("hi", "hello")]


def test_get_empty_returns_empty_list():
    store = InMemoryHistoryStore(max_turns=10)
    assert store.get("p1", "n1") == []


def test_sliding_window_trims_oldest():
    store = InMemoryHistoryStore(max_turns=2)
    store.append("p1", "n1", Turn("u1", "a1"))
    store.append("p1", "n1", Turn("u2", "a2"))
    store.append("p1", "n1", Turn("u3", "a3"))
    assert store.get("p1", "n1") == [Turn("u2", "a2"), Turn("u3", "a3")]


def test_keys_are_isolated():
    store = InMemoryHistoryStore(max_turns=10)
    store.append("p1", "n1", Turn("u", "a"))
    assert store.get("p1", "n2") == []
    assert store.get("p2", "n1") == []


def test_reset_clears_only_that_key():
    store = InMemoryHistoryStore(max_turns=10)
    store.append("p1", "n1", Turn("u", "a"))
    store.append("p1", "n2", Turn("u2", "a2"))
    store.reset("p1", "n1")
    assert store.get("p1", "n1") == []
    assert store.get("p1", "n2") == [Turn("u2", "a2")]


def test_get_returns_copy_not_internal_list():
    store = InMemoryHistoryStore(max_turns=10)
    store.append("p1", "n1", Turn("u", "a"))
    turns = store.get("p1", "n1")
    turns.append(Turn("x", "y"))
    assert store.get("p1", "n1") == [Turn("u", "a")]
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_history.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'history'`.

- [ ] **Step 3: Write `history.py`**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Turn:
    user: str
    assistant: str


class HistoryStore(ABC):
    @abstractmethod
    def get(self, player_id: str, npc_id: str) -> list[Turn]: ...

    @abstractmethod
    def append(self, player_id: str, npc_id: str, turn: Turn) -> None: ...

    @abstractmethod
    def reset(self, player_id: str, npc_id: str) -> None: ...


class InMemoryHistoryStore(HistoryStore):
    def __init__(self, max_turns: int) -> None:
        self._max_turns = max_turns
        self._data: dict[tuple[str, str], list[Turn]] = {}

    def get(self, player_id: str, npc_id: str) -> list[Turn]:
        return list(self._data.get((player_id, npc_id), []))

    def append(self, player_id: str, npc_id: str, turn: Turn) -> None:
        key = (player_id, npc_id)
        turns = self._data.setdefault(key, [])
        turns.append(turn)
        if len(turns) > self._max_turns:
            del turns[: len(turns) - self._max_turns]

    def reset(self, player_id: str, npc_id: str) -> None:
        self._data.pop((player_id, npc_id), None)
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_history.py -v
```
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```powershell
git add history.py tests/test_history.py
git commit -m "feat: in-memory conversation history store with sliding window"
```

---

### Task 3: Prompt assembly

**Files:**
- Create: `prompt.py`
- Test: `tests/test_prompt.py`

**Interfaces:**
- Consumes: `history.Turn`.
- Produces:
  - `prompt.build_messages(system_prompt: str, context: str | None, history: list[Turn], message: str) -> list[dict]` — returns an OpenAI `messages` array: a single `system` message (equal to `system_prompt`, or `system_prompt + "\n\n" + context` when `context` is truthy), then each turn expanded to a `user` then `assistant` message in order, then a final `user` message equal to `message`.

- [ ] **Step 1: Write the failing test** — `tests/test_prompt.py`

```python
from history import Turn
from prompt import build_messages


def test_no_context_no_history():
    msgs = build_messages("You are Bob.", None, [], "hi")
    assert msgs == [
        {"role": "system", "content": "You are Bob."},
        {"role": "user", "content": "hi"},
    ]


def test_context_appended_to_system():
    msgs = build_messages("You are Bob.", "Player returned your hammer.", [], "hi")
    assert msgs[0] == {
        "role": "system",
        "content": "You are Bob.\n\nPlayer returned your hammer.",
    }


def test_empty_context_string_ignored():
    msgs = build_messages("You are Bob.", "", [], "hi")
    assert msgs[0] == {"role": "system", "content": "You are Bob."}


def test_history_expanded_in_order():
    history = [Turn("u1", "a1"), Turn("u2", "a2")]
    msgs = build_messages("sys", None, history, "u3")
    assert msgs == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
        {"role": "user", "content": "u3"},
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_prompt.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'prompt'`.

- [ ] **Step 3: Write `prompt.py`**

```python
from history import Turn


def build_messages(
    system_prompt: str,
    context: str | None,
    history: list[Turn],
    message: str,
) -> list[dict]:
    system_content = system_prompt
    if context:
        system_content = f"{system_prompt}\n\n{context}"

    messages: list[dict] = [{"role": "system", "content": system_content}]
    for turn in history:
        messages.append({"role": "user", "content": turn.user})
        messages.append({"role": "assistant", "content": turn.assistant})
    messages.append({"role": "user", "content": message})
    return messages
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_prompt.py -v
```
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```powershell
git add prompt.py tests/test_prompt.py
git commit -m "feat: assemble OpenAI messages from persona, context, and history"
```

---

### Task 4: llama.cpp client

**Files:**
- Create: `llm_client.py`
- Test: `tests/test_llm_client.py`

**Interfaces:**
- Consumes: `config.Settings`.
- Produces:
  - `llm_client.LLMResult` — dataclass with `ok: bool`, `reply: str`, `error: str | None`.
  - `llm_client.call_llama(messages: list[dict], settings: Settings) -> LLMResult` — POSTs `{"model": settings.llama_model, "messages": messages}` to `settings.llama_base_url + "/v1/chat/completions"` with `timeout=settings.request_timeout`. On success returns `LLMResult(ok=True, reply=<choices[0].message.content>, error=None)`. On `httpx.TimeoutException` returns `error="llm_timeout"`. On any other `httpx.HTTPError` (connection failure, non-2xx) returns `error="llm_unavailable"`.
  - `llm_client.ping(settings: Settings) -> bool` — GETs `settings.llama_base_url + "/health"` with a short timeout; returns True on 2xx, False on any error.

- [ ] **Step 1: Write the failing test** — `tests/test_llm_client.py`

```python
import httpx
import pytest

import llm_client
from config import Settings

SETTINGS = Settings(llama_base_url="http://test:8080", request_timeout=5.0, llama_model="local")


def _make_response(status_code, json_body):
    request = httpx.Request("POST", "http://test:8080/v1/chat/completions")
    return httpx.Response(status_code, json=json_body, request=request)


def test_call_llama_success(monkeypatch):
    def fake_post(url, json, timeout):
        assert url == "http://test:8080/v1/chat/completions"
        assert json == {"model": "local", "messages": [{"role": "user", "content": "hi"}]}
        return _make_response(200, {"choices": [{"message": {"content": "hello there"}}]})

    monkeypatch.setattr(llm_client.httpx, "post", fake_post)
    result = llm_client.call_llama([{"role": "user", "content": "hi"}], SETTINGS)
    assert result.ok is True
    assert result.reply == "hello there"
    assert result.error is None


def test_call_llama_timeout(monkeypatch):
    def fake_post(url, json, timeout):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(llm_client.httpx, "post", fake_post)
    result = llm_client.call_llama([], SETTINGS)
    assert result.ok is False
    assert result.reply == ""
    assert result.error == "llm_timeout"


def test_call_llama_connection_error(monkeypatch):
    def fake_post(url, json, timeout):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(llm_client.httpx, "post", fake_post)
    result = llm_client.call_llama([], SETTINGS)
    assert result.ok is False
    assert result.error == "llm_unavailable"


def test_call_llama_http_500(monkeypatch):
    def fake_post(url, json, timeout):
        return _make_response(500, {"error": "boom"})

    monkeypatch.setattr(llm_client.httpx, "post", fake_post)
    result = llm_client.call_llama([], SETTINGS)
    assert result.ok is False
    assert result.error == "llm_unavailable"


def test_ping_ok(monkeypatch):
    def fake_get(url, timeout):
        request = httpx.Request("GET", url)
        return httpx.Response(200, request=request)

    monkeypatch.setattr(llm_client.httpx, "get", fake_get)
    assert llm_client.ping(SETTINGS) is True


def test_ping_failure(monkeypatch):
    def fake_get(url, timeout):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(llm_client.httpx, "get", fake_get)
    assert llm_client.ping(SETTINGS) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_llm_client.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'llm_client'`.

- [ ] **Step 3: Write `llm_client.py`**

```python
from dataclasses import dataclass

import httpx

from config import Settings


@dataclass
class LLMResult:
    ok: bool
    reply: str
    error: str | None


def call_llama(messages: list[dict], settings: Settings) -> LLMResult:
    url = settings.llama_base_url + "/v1/chat/completions"
    payload = {"model": settings.llama_model, "messages": messages}
    try:
        response = httpx.post(url, json=payload, timeout=settings.request_timeout)
        response.raise_for_status()
        data = response.json()
        reply = data["choices"][0]["message"]["content"]
        return LLMResult(ok=True, reply=reply, error=None)
    except httpx.TimeoutException:
        return LLMResult(ok=False, reply="", error="llm_timeout")
    except httpx.HTTPError:
        return LLMResult(ok=False, reply="", error="llm_unavailable")


def ping(settings: Settings) -> bool:
    try:
        response = httpx.get(settings.llama_base_url + "/health", timeout=2.0)
        return response.is_success
    except httpx.HTTPError:
        return False
```

Note: `httpx.HTTPError` is the base class for `TimeoutException`, `ConnectError`, and `HTTPStatusError` (raised by `raise_for_status`). The `TimeoutException` branch is ordered first so timeouts get their distinct `llm_timeout` code; everything else falls through to `llm_unavailable`.

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_llm_client.py -v
```
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```powershell
git add llm_client.py tests/test_llm_client.py
git commit -m "feat: llama.cpp client with timeout and error mapping"
```

---

### Task 5: FastAPI app and endpoints

**Files:**
- Create: `main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `config.load_settings`, `history.InMemoryHistoryStore`, `history.Turn`, `prompt.build_messages`, `llm_client.call_llama`, `llm_client.ping`.
- Produces:
  - `main.app` — FastAPI application.
  - `main.settings` — loaded `Settings` (module global).
  - `main.store` — `InMemoryHistoryStore` (module global; endpoints read it at call time so tests may replace it).
  - Endpoints: `POST /chat` (body `ChatRequest`, returns `ChatResponse`), `POST /reset` (body `ResetRequest`, returns `{"ok": true}`), `GET /health` (returns `{"server": true, "llama": <bool>}`).
  - `ChatRequest`: `player_id: str`, `npc_id: str`, `system_prompt: str`, `context: str | None = None`, `message: str`.
  - `ChatResponse`: `reply: str`, `ok: bool`, `npc_id: str`, `turn_count: int`, `error: str | None = None`.
  - `ResetRequest`: `player_id: str`, `npc_id: str`.

- [ ] **Step 1: Write the failing test** — `tests/test_main.py`

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_main.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'main'`.

- [ ] **Step 3: Write `main.py`**

```python
from fastapi import FastAPI
from pydantic import BaseModel

import config
import history
import llm_client
import prompt

settings = config.load_settings()
store: history.HistoryStore = history.InMemoryHistoryStore(max_turns=settings.max_history_turns)
app = FastAPI()


class ChatRequest(BaseModel):
    player_id: str
    npc_id: str
    system_prompt: str
    context: str | None = None
    message: str


class ChatResponse(BaseModel):
    reply: str
    ok: bool
    npc_id: str
    turn_count: int
    error: str | None = None


class ResetRequest(BaseModel):
    player_id: str
    npc_id: str


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    turns = store.get(req.player_id, req.npc_id)
    messages = prompt.build_messages(req.system_prompt, req.context, turns, req.message)
    result = llm_client.call_llama(messages, settings)
    if not result.ok:
        return ChatResponse(
            reply="", ok=False, npc_id=req.npc_id, turn_count=len(turns), error=result.error
        )
    store.append(req.player_id, req.npc_id, history.Turn(user=req.message, assistant=result.reply))
    turn_count = len(store.get(req.player_id, req.npc_id))
    return ChatResponse(reply=result.reply, ok=True, npc_id=req.npc_id, turn_count=turn_count)


@app.post("/reset")
def reset(req: ResetRequest) -> dict:
    store.reset(req.player_id, req.npc_id)
    return {"ok": True}


@app.get("/health")
def health() -> dict:
    return {"server": True, "llama": llm_client.ping(settings)}
```

Note: endpoints reference the module-global `store` / `llm_client.call_llama` by name at call time, so the test fixtures that reassign `main.store` and monkeypatch `llm_client.call_llama` take effect.

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_main.py -v
```
Expected: PASS (5 passed).

- [ ] **Step 5: Run the full suite**

Run:
```powershell
.venv\Scripts\python.exe -m pytest -v
```
Expected: PASS (all tests across the 5 test files — 23 passed).

- [ ] **Step 6: Manual smoke test (optional, requires llama.cpp running)**

Run the server:
```powershell
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```
Then from another shell:
```powershell
curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"player_id\":\"p1\",\"npc_id\":\"bob\",\"system_prompt\":\"You are a gruff blacksmith.\",\"message\":\"Hello\"}"
```
Expected: JSON with `"ok": true` and a `"reply"` string (if llama.cpp is up), or `"ok": false, "error": "llm_unavailable"` (if not).

- [ ] **Step 7: Commit**

```powershell
git add main.py tests/test_main.py
git commit -m "feat: FastAPI endpoints for chat, reset, and health"
```

---

## Notes for the implementer

- **Import style:** because `pytest.ini` sets `pythonpath = .`, both tests and source modules import each other by bare top-level name (`import config`, `from history import Turn`). Do not create an `app/` package.
- **Never call the real llama.cpp in tests.** Every test monkeypatches `httpx` (Task 4) or `llm_client.call_llama` / `llm_client.ping` (Task 5).
- **`httpx.HTTPError` hierarchy:** `TimeoutException` and `ConnectError` and `HTTPStatusError` all subclass `httpx.HTTPError`. The order of `except` clauses in `call_llama` matters — timeout first, then the catch-all.
- **Fresh store per test:** the `fresh_store` autouse fixture in `test_main.py` replaces `main.store` before each test so history doesn't leak between tests.
