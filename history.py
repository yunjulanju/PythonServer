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
