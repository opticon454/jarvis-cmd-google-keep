"""Google Keep list operations behind a small, testable interface.

``KeepService`` wraps an object shaped like ``gkeepapi.Keep`` (``all()``, ``sync()``, list nodes with ``title``,
``items``, ``add()``), so the matching and bookkeeping can be unit tested with fakes. Nothing here opens a network
connection except ``KeepService.connect``.

gkeepapi uses the private mobile API of Google Keep. It is unofficial and Google can change it without notice.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any

_FILLER_WORDS = {"my", "the", "a", "an", "list", "keep", "google", "on", "to", "from", "in"}


class KeepError(Exception):
    """A problem the person can be told about in a sentence."""


@dataclass
class ListSummary:
    title: str
    open_count: int
    done_count: int


@dataclass
class AddResult:
    added: list[str] = field(default_factory=list)
    already_there: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    matched: list[str] = field(default_factory=list)
    not_found: list[str] = field(default_factory=list)


def normalise(text: str) -> str:
    """Lower-case words with punctuation and filler words removed, for matching."""
    words = re.findall(r"[a-z0-9']+", (text or "").lower())
    kept = [w for w in words if w not in _FILLER_WORDS]
    return " ".join(kept or words)


def best_match(query: str, candidates: list[str], cutoff: float = 0.6) -> int | None:
    """Index of the candidate that best matches ``query``, or None.

    Exact (after normalising), then whole-word containment either way, then fuzzy similarity above ``cutoff``.
    """
    q = normalise(query)
    if not q or not candidates:
        return None
    normalised = [normalise(c) for c in candidates]
    for i, c in enumerate(normalised):
        if c == q:
            return i
    q_words = set(q.split())
    best: tuple[float, int] | None = None
    for i, c in enumerate(normalised):
        c_words = set(c.split())
        if not c_words:
            continue
        if q_words <= c_words or c_words <= q_words:
            score = 0.9 + 0.1 * (len(q_words & c_words) / max(len(q_words | c_words), 1))
        else:
            score = difflib.SequenceMatcher(None, q, c).ratio()
        if score >= cutoff and (best is None or score > best[0]):
            best = (score, i)
    return best[1] if best else None


def _is_list(node: Any) -> bool:
    node_type = getattr(node, "type", None)
    value = getattr(node_type, "value", node_type)
    return str(value).upper() == "LIST"


class KeepService:
    def __init__(self, client: Any, default_list: str = "Shopping") -> None:
        self._keep = client
        self.default_list = default_list or "Shopping"

    @classmethod
    def connect(cls, email: str, master_token: str, default_list: str = "Shopping") -> "KeepService":
        """Log in with a master token and do the first sync. Raises KeepError with a speakable message."""
        try:
            import gkeepapi  # imported here: only the real connection needs it
        except ImportError as exc:
            raise KeepError("The Google Keep library is not installed on this node.") from exc
        keep = gkeepapi.Keep()
        try:
            keep.authenticate(email, master_token)
        except Exception as exc:  # noqa: BLE001 - library raises its own login exceptions
            raise KeepError("Google rejected the Keep login. The master token may have expired.") from exc
        return cls(keep, default_list)

    # -- lists -------------------------------------------------------------

    def _lists(self) -> list[Any]:
        return [n for n in self._keep.all()
                if _is_list(n) and not getattr(n, "trashed", False) and not getattr(n, "archived", False)]

    def summaries(self) -> list[ListSummary]:
        out = []
        for lst in self._lists():
            items = list(lst.items)
            done = sum(1 for i in items if i.checked)
            out.append(ListSummary(lst.title or "Untitled", len(items) - done, done))
        return out

    def find_list(self, name: str | None) -> Any:
        """The list the person means; the default list when no name is given."""
        lists = self._lists()
        if not lists:
            raise KeepError("You have no lists in Google Keep.")
        wanted = (name or "").strip() or self.default_list
        index = best_match(wanted, [lst.title or "" for lst in lists])
        if index is None:
            if not (name or "").strip() and len(lists) == 1:
                return lists[0]
            titles = ", ".join(lst.title for lst in lists[:5] if lst.title)
            raise KeepError(f"I couldn't find a Keep list called {wanted}. You have: {titles}.")
        return lists[index]

    # -- items -------------------------------------------------------------

    @staticmethod
    def open_items(lst: Any) -> list[str]:
        return [i.text for i in lst.items if not i.checked]

    def add_items(self, list_name: str | None, items: list[str]) -> tuple[str, AddResult]:
        lst = self.find_list(list_name)
        result = AddResult()
        existing = self.open_items(lst)
        for raw in items:
            text = " ".join((raw or "").split())
            if not text:
                continue
            text = text[0].upper() + text[1:]
            if best_match(text, existing, cutoff=0.9) is not None:
                result.already_there.append(text)
                continue
            lst.add(text, False)
            existing.append(text)
            result.added.append(text)
        if result.added:
            self._keep.sync()
        return lst.title, result

    def _set_checked(self, list_name: str | None, items: list[str], checked: bool) -> tuple[str, MatchResult]:
        lst = self.find_list(list_name)
        result = MatchResult()
        pool = [i for i in lst.items if bool(i.checked) != checked]
        for raw in items:
            index = best_match(raw, [i.text for i in pool], cutoff=0.75)
            if index is None:
                result.not_found.append(raw)
                continue
            item = pool.pop(index)
            item.checked = checked
            result.matched.append(item.text)
        if result.matched:
            self._keep.sync()
        return lst.title, result

    def check_off(self, list_name: str | None, items: list[str]) -> tuple[str, MatchResult]:
        return self._set_checked(list_name, items, True)

    def uncheck(self, list_name: str | None, items: list[str]) -> tuple[str, MatchResult]:
        return self._set_checked(list_name, items, False)

    def clear_checked(self, list_name: str | None) -> tuple[str, int]:
        lst = self.find_list(list_name)
        done = [i for i in lst.items if i.checked]
        for item in done:
            item.delete()
        if done:
            self._keep.sync()
        return lst.title, len(done)

    def read_list(self, list_name: str | None) -> tuple[str, list[str]]:
        lst = self.find_list(list_name)
        return lst.title, self.open_items(lst)
