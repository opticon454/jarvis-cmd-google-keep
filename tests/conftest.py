"""Fakes shaped like gkeepapi's nodes, so the logic runs without Google."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeItem:
    def __init__(self, text: str, checked: bool = False) -> None:
        self.text, self.checked, self.deleted = text, checked, False
        self.parent: "FakeList | None" = None

    def delete(self) -> None:
        self.deleted = True
        if self.parent is not None:
            self.parent.items.remove(self)


class FakeList:
    type = "LIST"
    trashed = False
    archived = False

    def __init__(self, title: str, items: list[tuple[str, bool]] | None = None) -> None:
        self.title = title
        self.items: list[FakeItem] = []
        for text, checked in items or []:
            self.add(text, checked)

    def add(self, text: str, checked: bool = False) -> FakeItem:
        item = FakeItem(text, checked)
        item.parent = self
        self.items.append(item)
        return item


class FakeNote:
    type = "NOTE"
    trashed = False
    archived = False
    title = "A plain note"
    items: list = []


class FakeKeep:
    def __init__(self, nodes: list) -> None:
        self._nodes, self.syncs = nodes, 0

    def all(self) -> list:
        return list(self._nodes)

    def sync(self) -> None:
        self.syncs += 1


@pytest.fixture
def keep() -> FakeKeep:
    return FakeKeep([
        FakeList("Shopping", [("Milk", False), ("Eggs", False), ("Bread", True), ("Butter", True)]),
        FakeList("To do", [("Call the plumber", False)]),
        FakeList("Packing", []),
        FakeNote(),
    ])
