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
