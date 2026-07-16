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
