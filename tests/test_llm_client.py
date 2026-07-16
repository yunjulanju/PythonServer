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
