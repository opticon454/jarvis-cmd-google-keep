# Google Keep for Jarvis

Read, add to, check off and clear your **Google Keep** lists by voice.

> "Hey Jarvis, add milk and eggs to my shopping list."
> "What's on my shopping list?"
> "Check off milk."
> "Clear the ticked items from my shopping list."
> "What lists do I have in Keep?"

## Contents

- [Read this first: it uses an unofficial API](#read-this-first-it-uses-an-unofficial-api)
- [What it does](#what-it-does)
- [Requirements](#requirements)
- [Install and set up](#install-and-set-up)
- [Check that it works](#check-that-it-works)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

## Read this first: it uses an unofficial API

Google Keep has no public API for personal accounts. The official Keep API exists only for Google Workspace
administrators. This package uses [gkeepapi](https://github.com/kiwiz/gkeepapi), which talks to the private API the
Keep mobile app uses, authenticated with a Google **master token**.

- **Google can change or block it without notice.** If it stops working, this package stops working.
- **The master token grants broad access to your whole Google account**, not just Keep. It is stored encrypted in the
  node's secret store. Treat it like a password: do not commit it, paste it into chat or share screenshots of it.
- Use of unofficial clients may be outside Google's terms of service. Use at your own risk, ideally with an account you
  can afford to have rate limited.

If you want something official and limited to one scope, use the sibling package for Google Tasks.

## What it does

One command, `google_keep`, with an `action` parameter:

| Say                                            | Action          | Does                                                                |
| ---------------------------------------------- | --------------- | ------------------------------------------------------------------- |
| "add X (and Y) to my shopping list"            | `add_items`     | Adds each item; an item already open on the list is not added twice |
| "what's on my shopping list"                   | `read_list`     | Reads the open items (the first 10, then "and N more")              |
| "check off / tick off X", "I got the milk"     | `check_off`     | Ticks items (fuzzy matched: "eggs please" finds "Eggs")             |
| "untick X"                                     | `uncheck`       | Puts a ticked item back                                             |
| "clear the ticked items from my shopping list" | `clear_checked` | Deletes the ticked items from the list                              |
| "what lists do I have in Keep"                 | `list_lists`    | Lists your lists with their open item counts                        |

Parameters: `list_name` (optional) and `items` (one entry per item).

If you do not name a list, the default list is used: the `GOOGLE_KEEP_DEFAULT_LIST` setting (default "Shopping"), or the
only list you have if there is just one. Plain notes are ignored; only Keep **lists** (checklists) are handled.

## Requirements

| Requirement    | Detail                                                                                                     |
| -------------- | ---------------------------------------------------------------------------------------------------------- |
| Jarvis node    | A node that can run Pantry packages (`min_jarvis_version` 0.9.0 in the manifest)                           |
| Python package | `gkeepapi` 0.16.0 or newer, installed by the Pantry installer into the node's container                    |
| Network        | The node can reach Google over HTTPS (`android.clients.google.com`, `www.googleapis.com`); nothing inbound |
| Google account | The account that owns the Keep lists, with a **master token** for it (see below)                           |
| Node secrets   | `GOOGLE_KEEP_EMAIL`, `GOOGLE_KEEP_MASTER_TOKEN` (sensitive), optional `GOOGLE_KEEP_DEFAULT_LIST`           |
| For the helper | A machine with a browser and Python 3 with `venv` (`sudo apt install python3-venv` on Debian or Ubuntu)    |

## Install and set up

Two steps: copy one cookie from your browser, then run one script that asks for everything else.

### Step 1: copy the `oauth_token` cookie (in a browser)

1. Open <https://accounts.google.com/EmbeddedSetup>, sign in as the Google account that owns the lists and approve. The
   page then looks stuck on "loading"; that is normal.
2. Open the browser's developer tools (F12), go to the *Application* tab (Chrome, Edge) or *Storage* tab (Firefox),
   choose *Cookies*, `accounts.google.com`, and copy the **value** of the cookie named **`oauth_token`**. It starts with
   `oauth2_4/`.
3. Keep it to hand for step 2. It works **once** and is short lived, so do step 2 straight away. If it fails, repeat
   this step for a fresh cookie.

### Step 2: run the script

```bash
./google_keep_tools/set-secrets.sh
```

You do not need to make the master token yourself: the script takes the cookie and turns it into one. It asks:

| Question                    | Default                                | Notes                                                                                |
| --------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------ |
| Where Docker runs           | this machine                           | Enter, or `user@host` for the node's machine (asks for the SSH password once)        |
| Node container name         | the `jarvis-node*` container it finds  | Press Enter to accept, or type yours (see `docker ps`)                               |
| Google account email        | none                                   | The account that owns the Keep lists                                                 |
| `oauth_token` cookie        | none                                   | From step 1, typed hidden. Press Enter instead if you already have an `aas_et/` token |
| Default list name           | `Shopping`                             | Press Enter to accept                                                                |

It then shows what it will store (the token only as a length) and asks you to confirm. After that it installs the
package from your Pantry, stores the three secrets in the node's encrypted secret store, installs `gkeepapi` if it is
missing, and restarts the node. Each of those steps asks first. Values are sent on standard input, so they never appear
in a command line or in your shell history.

The first run creates a small Python environment in `~/.venvs/gkeep` on the machine you run the script from (it needs
`python3-venv`; `sudo apt install python3-venv` if it complains). That is what lets it work on Debian and Ubuntu, which
refuse a system-wide `pip install` (PEP 668).

You can instead enter the same fields in the Jarvis admin portal or mobile app, in the package's settings.
`google_keep_tools/get-master-token.sh` is still there if you only want to print a master token.

## Check that it works

1. In the Keep app, make sure a checklist called **Shopping** exists (or set `GOOGLE_KEEP_DEFAULT_LIST`).
2. Say, or send as text: "what lists do I have in Keep". It should name your lists.
3. "Add milk to my shopping list", then open Keep: the item appears within a few seconds.
4. "Check off milk", then "clear the ticked items from my shopping list".

The node log (`docker logs jarvis-node`, or your container's name) shows the command running and any error.

## Troubleshooting

| Symptom                                                | Cause and fix                                                                              |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| "Google Keep isn't set up yet"                         | The email or token secret is missing on that node; run `set-secrets.sh` again           |
| "Google rejected the Keep login"                       | Token revoked, expired or for a different account. Copy a fresh cookie (step 1) and run `set-secrets.sh` again                  |
| "does not look like the oauth_token cookie"            | You copied the wrong cookie or an empty value; it must start with `oauth2_4/`              |
| "Google did not give a master token"                   | The cookie was already used or expired. Repeat step 1 for a fresh one                      |
| "The Google Keep library is not installed"             | Run `set-secrets.sh` again and accept the `gkeepapi` install                          |
| "I couldn't find a Keep list called X"                 | The title does not match. Say the list name as it appears in Keep, or set the default list |
| `externally-managed-environment` from pip              | Use `set-secrets.sh`, which creates its own environment; do not use `--break-system-packages`                |
| Worked, then stopped with no change on your side       | Google changed the private API. Upgrade `gkeepapi` and check its issue tracker             |

To revoke access, remove the app at <https://myaccount.google.com/permissions> or change the account password, which
invalidates the master token.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install pytest jarvis-command-sdk gkeepapi
.venv/bin/pytest
```

The tests use fakes shaped like gkeepapi's nodes, so they run offline. The live login has not been exercised in CI.

## Layout

```text
commands/google_keep/command.py          the voice command
google_keep_shared/keep_service.py       list logic (matching, adding, checking), unit tested
google_keep_tools/set-secrets.sh         the main script: asks everything, makes the token, stores it
google_keep_tools/get-master-token.sh    optional: only prints a master token
google_keep_tools/get_master_token.py    the Python helper it runs
tests/                                   offline tests with fakes
jarvis_package.yaml                      the Pantry manifest (secrets, packages)
```

## Licence

Apache-2.0. See `LICENSE` and `NOTICE`.
