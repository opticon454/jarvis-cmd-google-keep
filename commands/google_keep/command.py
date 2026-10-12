"""GoogleKeepCommand: read, add to, check off and clear Google Keep lists by voice.

Uses ``gkeepapi``, an unofficial client for Keep's private mobile API, with a Google master token held in the node's
encrypted secret store. List logic lives in ``google_keep_shared.keep_service`` so it can be tested without a network.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Installed packages keep shared code at ~/.jarvis/packages/<name>/<name>_lib/. Put it on the path so the import below
# resolves even before the node's discovery cache has refreshed after an install.
for _candidate in ("google_keep_lib", "lib"):
    _lib_dir: str = str(Path.home() / ".jarvis" / "packages" / "google_keep" / _candidate)
    if _lib_dir not in sys.path:
        sys.path.insert(0, _lib_dir)

try:
    from jarvis_log_client import JarvisLogger
except ImportError:
    import logging

    class JarvisLogger:  # noqa: E303
        def __init__(self, **kw: str) -> None:
            self._log = logging.getLogger(kw.get("service", __name__))

        def info(self, msg: str, **kw: object) -> None: self._log.info(msg)
        def warning(self, msg: str, **kw: object) -> None: self._log.warning(msg)
        def error(self, msg: str, **kw: object) -> None: self._log.error(msg)
        def debug(self, msg: str, **kw: object) -> None: self._log.debug(msg)

from jarvis_command_sdk import (
    CommandExample,
    CommandResponse,
    IJarvisCommand,
    IJarvisSecret,
    JarvisPackage,
    JarvisParameter,
    JarvisSecret,
    JarvisStorage,
    RequestInformation,
)

from google_keep_shared.keep_service import KeepError, KeepService

logger = JarvisLogger(service="google-keep")

ACTIONS = ["read_list", "add_items", "check_off", "uncheck", "clear_checked", "list_lists"]
_MAX_SPOKEN_ITEMS = 10


def join_spoken(items: List[str]) -> str:
    """'milk', 'milk and eggs', 'milk, eggs and bread'."""
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _as_list(value: Any) -> List[str]:
    """The model may send one string, a list, or a 'a and b' phrase."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace(" and ", ",").split(",")]
        return [p for p in parts if p]
    return [str(v).strip() for v in value if str(v).strip()]


class GoogleKeepCommand(IJarvisCommand):
    """Voice access to Google Keep lists."""

    def __init__(self) -> None:
        self._storage = JarvisStorage("google_keep")

    @property
    def command_name(self) -> str:
        return "google_keep"

    @property
    def description(self) -> str:
        return (
            "Google Keep lists. action='add_items' adds items to a list, 'read_list' says what is on a list, "
            "'check_off' ticks items off, 'uncheck' puts them back, 'clear_checked' removes ticked items, "
            "'list_lists' says which lists exist. Use for requests that name Keep or a list such as the shopping list."
        )

    @property
    def associated_service(self) -> Optional[str]:
        return "Google Keep"

    @property
    def keywords(self) -> List[str]:
        return ["keep", "google keep", "list", "shopping list", "to do list", "groceries", "add to my list",
                "check off", "tick off", "put on the list", "what's on my list"]

    @property
    def parameters(self) -> List[JarvisParameter]:
        return [
            JarvisParameter(
                "action", "string", required=True, enum_values=ACTIONS,
                description=(
                    "add_items=add things to a list, read_list=say what is on a list, "
                    "check_off=mark items done/bought, uncheck=un-mark items, "
                    "clear_checked=remove the ticked items, list_lists=which lists exist"
                ),
            ),
            JarvisParameter(
                "list_name", "string", required=False,
                description="Which list, e.g. 'shopping'. Leave empty for the default list.",
            ),
            JarvisParameter(
                "items", "array<string>", required=False,
                description="Items to add, check off or uncheck, one entry per item (split 'milk and eggs')",
            ),
        ]

    @property
    def required_secrets(self) -> List[IJarvisSecret]:
        return [
            JarvisSecret("GOOGLE_KEEP_EMAIL", "Google account email that owns the Keep lists", "integration",
                         "string", is_sensitive=False, friendly_name="Google account email"),
            JarvisSecret("GOOGLE_KEEP_MASTER_TOKEN", "Google master token for that account", "integration",
                         "string", friendly_name="Master token"),
            JarvisSecret("GOOGLE_KEEP_DEFAULT_LIST", "List used when none is named (default: Shopping)",
                         "integration", "string", required=False, is_sensitive=False, friendly_name="Default list"),
        ]

    @property
    def required_packages(self) -> List[JarvisPackage]:
        return [JarvisPackage("gkeepapi", ">=0.16.0")]

    @property
    def setup_guide(self) -> Optional[str]:
        return (
            "## Connect Google Keep\n\n"
            "This uses the **unofficial** Keep API with a Google *master token*, which grants broad access to the "
            "account. It is stored encrypted on the node. Google can change the API without notice.\n\n"
            "1. Open <https://accounts.google.com/EmbeddedSetup>, sign in, and approve. Ignore the 'loading' page.\n"
            "2. In your browser's developer tools, copy the value of the `oauth_token` cookie (starts `oauth2_4/`).\n"
            "3. Run `python google_keep_tools/get_master_token.py you@gmail.com` from the package and paste the cookie.\n"
            "4. Enter the email and the printed token in this command's settings.\n"
        )

    def generate_prompt_examples(self) -> List[CommandExample]:
        return [
            CommandExample("Add milk and eggs to my shopping list",
                           {"action": "add_items", "list_name": "shopping", "items": ["milk", "eggs"]}, is_primary=True),
            CommandExample("What's on my shopping list", {"action": "read_list", "list_name": "shopping"}),
            CommandExample("Check off milk", {"action": "check_off", "items": ["milk"]}),
            CommandExample("Clear the ticked items from my shopping list",
                           {"action": "clear_checked", "list_name": "shopping"}),
            CommandExample("What lists do I have in Keep", {"action": "list_lists"}),
        ]

    def generate_adapter_examples(self) -> List[CommandExample]:
        add = [("Put bread on the list", ["bread"], None), ("Add butter to the shopping list", ["butter"], "shopping"),
               ("Add toilet paper and soap to my Keep list", ["toilet paper", "soap"], None),
               ("Keep: add bananas", ["bananas"], None), ("Add dog food to the groceries list", ["dog food"], "groceries"),
               ("Add call the plumber to my to do list", ["call the plumber"], "to do")]
        examples = []
        for text, items, name in add:
            params: Dict[str, Any] = {"action": "add_items", "items": items}
            if name:
                params["list_name"] = name
            examples.append(CommandExample(text, params))
        examples += [
            CommandExample("Read me my shopping list", {"action": "read_list", "list_name": "shopping"}),
            CommandExample("What do I need to buy", {"action": "read_list"}),
            CommandExample("What's on my to do list", {"action": "read_list", "list_name": "to do"}),
            CommandExample("Tick off eggs", {"action": "check_off", "items": ["eggs"]}),
            CommandExample("Mark bread as bought", {"action": "check_off", "items": ["bread"]}),
            CommandExample("I got the milk", {"action": "check_off", "items": ["milk"]}),
            CommandExample("Untick the butter", {"action": "uncheck", "items": ["butter"]}),
            CommandExample("Remove the completed items from my shopping list",
                           {"action": "clear_checked", "list_name": "shopping"}),
            CommandExample("Which Keep lists do I have", {"action": "list_lists"}),
        ]
        return examples

    # -- execution ---------------------------------------------------------

    def _service(self) -> KeepService:
        email = self._storage.get_secret("GOOGLE_KEEP_EMAIL")
        token = self._storage.get_secret("GOOGLE_KEEP_MASTER_TOKEN")
        if not email or not token:
            raise KeepError("Google Keep isn't set up yet. Add your email and master token in the app.")
        default = self._storage.get_secret("GOOGLE_KEEP_DEFAULT_LIST") or "Shopping"
        return KeepService.connect(email, token, default)

    def run(self, request_info: RequestInformation, **kwargs: Any) -> CommandResponse:
        action = str(kwargs.get("action") or "read_list").strip().lower()
        if action not in ACTIONS:
            return CommandResponse.error_response(
                error_details="I can add to a list, read it, check items off or clear them. Which would you like?",
                context_data={"error": "unknown_action", "action": action},
            )
        list_name = kwargs.get("list_name")
        items = _as_list(kwargs.get("items"))
        if action in ("add_items", "check_off", "uncheck") and not items:
            return CommandResponse.error_response(
                error_details="Which items?", context_data={"error": "missing_items", "action": action},
            )
        try:
            message = self._perform(self._service(), action, list_name, items)
        except KeepError as exc:
            return CommandResponse.error_response(error_details=str(exc), context_data={"error": "keep_error"})
        except Exception as exc:  # noqa: BLE001 - never raise into the voice pipeline
            logger.error("Google Keep action failed", action=action, error=str(exc))
            return CommandResponse.error_response(
                error_details="Google Keep didn't respond. Try again in a moment.",
                context_data={"error": "unexpected", "detail": str(exc)},
            )
        return CommandResponse.success_response(
            context_data={"action": action, "message": message}, wait_for_input=False,
        )

    @staticmethod
    def _perform(service: KeepService, action: str, list_name: Any, items: List[str]) -> str:
        if action == "list_lists":
            lists = service.summaries()
            if not lists:
                return "You have no lists in Google Keep."
            parts = [f"{s.title} with {s.open_count} item{'s' if s.open_count != 1 else ''}" for s in lists[:6]]
            return f"You have {len(lists)} list{'s' if len(lists) != 1 else ''}: {join_spoken(parts)}."
        if action == "read_list":
            title, open_items = service.read_list(list_name)
            if not open_items:
                return f"Your {title} list is empty."
            spoken = open_items[:_MAX_SPOKEN_ITEMS]
            more = len(open_items) - len(spoken)
            tail = f", and {more} more" if more > 0 else ""
            noun = "item" if len(open_items) == 1 else "items"
            return f"Your {title} list has {len(open_items)} {noun}: {join_spoken(spoken)}{tail}."
        if action == "add_items":
            title, added = service.add_items(list_name, items)
            bits = []
            if added.added:
                bits.append(f"Added {join_spoken(added.added)} to {title}.")
            if added.already_there:
                bits.append(f"{join_spoken(added.already_there)} {'was' if len(added.already_there) == 1 else 'were'}"
                            " already on it.")
            return " ".join(bits) or "Nothing to add."
        if action in ("check_off", "uncheck"):
            fn = service.check_off if action == "check_off" else service.uncheck
            title, matched = fn(list_name, items)
            verb = "Checked off" if action == "check_off" else "Put back"
            bits = []
            if matched.matched:
                bits.append(f"{verb} {join_spoken(matched.matched)}.")
            if matched.not_found:
                bits.append(f"I couldn't find {join_spoken(matched.not_found)} on {title}.")
            return " ".join(bits)
        title, count = service.clear_checked(list_name)
        if count == 0:
            return f"There are no checked items on {title}."
        return f"Cleared {count} checked item{'s' if count != 1 else ''} from {title}."
