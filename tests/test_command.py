"""The command against the real Jarvis SDK interface, with Keep replaced by fakes."""

import pytest

from commands.google_keep.command import ACTIONS, GoogleKeepCommand, _as_list, join_spoken
from google_keep_shared.keep_service import KeepError, KeepService
from jarvis_command_sdk import CommandExample, IJarvisCommand


@pytest.fixture
def command(keep, monkeypatch):
    cmd = GoogleKeepCommand()
    monkeypatch.setattr(cmd, "_service", lambda: KeepService(keep, "Shopping"))
    return cmd


def run(command, **kwargs):
    return command.run(None, **kwargs)


class TestInterface:
    def test_is_a_jarvis_command(self):
        cmd = GoogleKeepCommand()
        assert isinstance(cmd, IJarvisCommand)
        assert cmd.command_name == "google_keep" and cmd.command_name.islower()

    def test_parameters_and_secrets(self):
        cmd = GoogleKeepCommand()
        names = [p.name for p in cmd.parameters]
        assert names == ["action", "list_name", "items"]
        assert {s.key for s in cmd.required_secrets} == {
            "GOOGLE_KEEP_EMAIL", "GOOGLE_KEEP_MASTER_TOKEN", "GOOGLE_KEEP_DEFAULT_LIST"}
        token = next(s for s in cmd.required_secrets if s.key == "GOOGLE_KEEP_MASTER_TOKEN")
        assert token.is_sensitive is True

    def test_examples_use_known_actions(self):
        cmd = GoogleKeepCommand()
        prompt, adapter = cmd.generate_prompt_examples(), cmd.generate_adapter_examples()
        assert 3 <= len(prompt) <= 6 and 10 <= len(adapter) <= 25
        for ex in prompt + adapter:
            assert isinstance(ex, CommandExample)
            assert ex.expected_parameters["action"] in ACTIONS
        assert sum(1 for e in prompt if e.is_primary) == 1


class TestHelpers:
    def test_join_spoken(self):
        assert join_spoken([]) == "" and join_spoken(["milk"]) == "milk"
        assert join_spoken(["milk", "eggs"]) == "milk and eggs"
        assert join_spoken(["milk", "eggs", "bread"]) == "milk, eggs and bread"

    def test_as_list_accepts_what_the_model_sends(self):
        assert _as_list(None) == [] and _as_list("milk") == ["milk"]
        assert _as_list("milk and eggs, bread") == ["milk", "eggs", "bread"]
        assert _as_list(["milk", " ", "eggs"]) == ["milk", "eggs"]


class TestRun:
    def test_read(self, command):
        r = run(command, action="read_list", list_name="shopping")
        assert r.success and r.context_data["message"] == "Your Shopping list has 2 items: Milk and Eggs."

    def test_read_defaults_to_the_default_list(self, command):
        assert "Shopping" in run(command, action="read_list").context_data["message"]

    def test_read_empty(self, command):
        assert run(command, action="read_list", list_name="packing").context_data["message"] == (
            "Your Packing list is empty.")

    def test_read_caps_the_spoken_items(self, command, keep):
        for n in range(12):
            keep._nodes[0].add(f"Item {n}", False)
        msg = run(command, action="read_list", list_name="shopping").context_data["message"]
        assert "14 items" in msg and msg.endswith("and 4 more.")

    def test_add(self, command):
        r = run(command, action="add_items", list_name="shopping", items=["bananas", "milk"])
        assert r.success
        assert r.context_data["message"] == "Added Bananas to Shopping. Milk was already on it."

    def test_add_without_items_asks(self, command):
        r = run(command, action="add_items", list_name="shopping")
        assert not r.success and r.error_details == "Which items?"

    def test_check_off(self, command):
        msg = run(command, action="check_off", items=["milk", "caviar"]).context_data["message"]
        assert msg == "Checked off Milk. I couldn't find caviar on Shopping."

    def test_clear_checked(self, command):
        msg = run(command, action="clear_checked", list_name="shopping").context_data["message"]
        assert msg == "Cleared 2 checked items from Shopping."

    def test_list_lists(self, command):
        msg = run(command, action="list_lists").context_data["message"]
        assert msg.startswith("You have 3 lists: Shopping with 2 items, To do with 1 item")

    def test_unknown_action(self, command):
        r = run(command, action="delete_everything")
        assert not r.success and r.context_data["error"] == "unknown_action"

    def test_unknown_list_is_spoken(self, command):
        r = run(command, action="read_list", list_name="holiday")
        assert not r.success and "couldn't find a Keep list called holiday" in r.error_details

    def test_not_configured(self, monkeypatch):
        cmd = GoogleKeepCommand()

        class Empty:
            def get_secret(self, *a, **k):
                return None

        cmd._storage = Empty()
        r = cmd.run(None, action="read_list")
        assert not r.success and "isn't set up" in r.error_details

    def test_unexpected_errors_do_not_escape(self, command, monkeypatch):
        def boom():
            raise RuntimeError("network down")

        monkeypatch.setattr(command, "_service", boom)
        r = run(command, action="read_list")
        assert not r.success and "didn't respond" in r.error_details
