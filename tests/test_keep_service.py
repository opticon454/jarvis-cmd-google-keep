"""KeepService against fakes shaped like gkeepapi."""

import pytest

from google_keep_shared.keep_service import KeepError, KeepService, best_match, normalise
from tests.conftest import FakeKeep, FakeList


@pytest.fixture
def service(keep):
    return KeepService(keep, default_list="Shopping")


class TestMatching:
    def test_normalise_drops_filler(self):
        assert normalise("My Shopping List!") == "shopping"
        assert normalise("the to do list") == "do"          # filler words removed
        assert normalise("list") == "list"                  # never reduced to nothing

    @pytest.mark.parametrize("query,expected", [
        ("shopping", 0), ("my shopping list", 0), ("Shoping", 0), ("to do", 1), ("packing list", 2),
    ])
    def test_best_match(self, query, expected):
        assert best_match(query, ["Shopping", "To do", "Packing"]) == expected

    def test_no_match(self):
        assert best_match("holiday plans", ["Shopping", "To do"]) is None
        assert best_match("", ["Shopping"]) is None


class TestLists:
    def test_summaries_skip_notes_and_count(self, service):
        s = {x.title: (x.open_count, x.done_count) for x in service.summaries()}
        assert s == {"Shopping": (2, 2), "To do": (1, 0), "Packing": (0, 0)}

    def test_trashed_and_archived_lists_are_ignored(self, keep):
        keep._nodes[1].trashed = True
        keep._nodes[2].archived = True
        assert [x.title for x in KeepService(keep).summaries()] == ["Shopping"]

    def test_default_list_when_no_name(self, service):
        assert service.find_list(None).title == "Shopping"

    def test_unknown_list_names_the_ones_that_exist(self, service):
        with pytest.raises(KeepError, match="Shopping, To do"):
            service.find_list("holiday")

    def test_no_lists(self):
        with pytest.raises(KeepError, match="no lists"):
            KeepService(FakeKeep([])).find_list("x")

    def test_single_list_is_used_without_a_name_even_if_default_differs(self):
        only = FakeList("Groceries", [("Tea", False)])
        assert KeepService(FakeKeep([only]), default_list="Shopping").find_list(None) is only


class TestItems:
    def test_read_only_returns_open_items(self, service):
        assert service.read_list("shopping") == ("Shopping", ["Milk", "Eggs"])

    def test_add_new_items_syncs_once(self, service, keep):
        title, result = service.add_items("shopping", ["bananas", "dog food"])
        assert title == "Shopping" and result.added == ["Bananas", "Dog food"] and not result.already_there
        assert keep.syncs == 1
        assert service.read_list("shopping")[1] == ["Milk", "Eggs", "Bananas", "Dog food"]

    def test_add_skips_items_already_open(self, service, keep):
        _, result = service.add_items("shopping", ["milk", "tea"])
        assert result.already_there == ["Milk"] and result.added == ["Tea"]

    def test_adding_something_that_is_checked_adds_a_new_open_item(self, service):
        _, result = service.add_items("shopping", ["bread"])
        assert result.added == ["Bread"]

    def test_add_nothing_does_not_sync(self, service, keep):
        service.add_items("shopping", ["  ", ""])
        assert keep.syncs == 0

    def test_check_off_fuzzy(self, service, keep):
        title, result = service.check_off("shopping", ["milk", "eggs please"])
        assert result.matched == ["Milk", "Eggs"] and not result.not_found
        assert service.read_list("shopping")[1] == []
        assert keep.syncs == 1

    def test_check_off_reports_unknown_items(self, service):
        _, result = service.check_off("shopping", ["milk", "caviar"])
        assert result.matched == ["Milk"] and result.not_found == ["caviar"]

    def test_uncheck_works_on_checked_items_only(self, service):
        _, result = service.uncheck("shopping", ["bread", "milk"])
        assert result.matched == ["Bread"] and result.not_found == ["milk"]

    def test_same_item_twice_checks_two_entries(self, service):
        service._keep._nodes[0].add("Milk", False)
        _, result = service.check_off("shopping", ["milk", "milk"])
        assert result.matched == ["Milk", "Milk"]

    def test_clear_checked(self, service, keep):
        title, count = service.clear_checked("shopping")
        assert (title, count) == ("Shopping", 2)
        assert [i.text for i in keep._nodes[0].items] == ["Milk", "Eggs"]

    def test_clear_checked_with_none_does_not_sync(self, service, keep):
        assert service.clear_checked("to do") == ("To do", 0)
        assert keep.syncs == 0


class TestConnect:
    def test_login_failure_is_speakable(self, monkeypatch):
        import sys
        import types

        class Boom:
            def authenticate(self, *a, **k):
                raise RuntimeError("BadAuthentication")

        monkeypatch.setitem(sys.modules, "gkeepapi", types.SimpleNamespace(Keep=Boom))
        with pytest.raises(KeepError, match="master token may have expired"):
            KeepService.connect("a@b.c", "bad")

    def test_missing_library_is_speakable(self, monkeypatch):
        import builtins

        real = builtins.__import__

        def fake(name, *a, **k):
            if name == "gkeepapi":
                raise ImportError(name)
            return real(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", fake)
        with pytest.raises(KeepError, match="not installed"):
            KeepService.connect("a@b.c", "t")
