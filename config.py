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
