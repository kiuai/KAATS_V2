from __future__ import annotations

from typing import Any


class WorkingMemory:
    """
    Per-run key-value scratch space shared across all tool calls within one agent run.
    Serialised to the Cosmos run document at each checkpoint.
    """

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._store: dict[str, Any] = initial or {}

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def append(self, key: str, value: Any) -> None:
        existing = self._store.setdefault(key, [])
        existing.append(value)

    def add_to_set(self, key: str, value: Any) -> None:
        existing: set = self._store.setdefault(key, set())
        existing.add(value)

    def in_set(self, key: str, value: Any) -> bool:
        return value in self._store.get(key, set())

    def increment(self, key: str, by: int = 1) -> int:
        current = self._store.get(key, 0)
        self._store[key] = current + by
        return self._store[key]

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serialisable snapshot for Cosmos checkpointing."""
        out = {}
        for k, v in self._store.items():
            out[k] = list(v) if isinstance(v, set) else v
        return out

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> "WorkingMemory":
        return cls(initial=data)
