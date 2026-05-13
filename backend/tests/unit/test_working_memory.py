from __future__ import annotations

import pytest

from app.agents.memory import WorkingMemory


def test_set_and_get():
    mem = WorkingMemory()
    mem.set("key", "value")
    assert mem.get("key") == "value"


def test_append():
    mem = WorkingMemory()
    mem.append("items", "a")
    mem.append("items", "b")
    assert mem.get("items") == ["a", "b"]


def test_set_membership():
    mem = WorkingMemory()
    mem.add_to_set("visited", "http://example.com")
    assert mem.in_set("visited", "http://example.com") is True
    assert mem.in_set("visited", "http://other.com") is False


def test_increment():
    mem = WorkingMemory()
    assert mem.increment("count") == 1
    assert mem.increment("count", 5) == 6


def test_snapshot_serialisable():
    mem = WorkingMemory()
    mem.set("key", "value")
    mem.add_to_set("urls", "http://example.com")
    snapshot = mem.snapshot()
    assert snapshot["key"] == "value"
    assert isinstance(snapshot["urls"], list)


def test_round_trip():
    mem = WorkingMemory()
    mem.set("step", 3)
    mem.append("passed", 1)
    snapshot = mem.snapshot()
    restored = WorkingMemory.from_snapshot(snapshot)
    assert restored.get("step") == 3
    assert restored.get("passed") == [1]
