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

Two scripts, run in order. Each one asks for what it needs, so there is nothing to edit.

### Step 1: get a master token

Run this on a machine with a browser:

```bash
./google_keep_tools/get-master-token.sh
```

It creates its own Python environment the first time (so Debian and Ubuntu's refusal of a system-wide `pip install`
does not matter; it needs `python3-venv`, `sudo apt install python3-venv` if it complains), then tells you what to copy
from the browser and asks for:

- your Google email;
- the `oauth_token` cookie value (typed hidden).

To get the cookie: open <https://accounts.google.com/EmbeddedSetup>, sign in as the account that owns the lists and
approve (the page then looks stuck on "loading"; that is normal), then copy the `oauth_token` cookie for
`accounts.google.com` from the browser's developer tools. It starts `oauth2_4/` and works once, so use it straight away.

The script prints a master token starting `aas_et/`. Keep it for step 2, then clear your terminal and clipboard.

### Step 2: store it on the node

Run this on the machine that runs the node's Docker container (for a node on another machine, run it there or over
SSH):

```bash
./google_keep_tools/set-secrets.sh
```

It asks for:

| Question             | Default                                | Notes                                                    |
| -------------------- | -------------------------------------- | -------------------------------------------------------- |
| Node container name  | `jarvis-node`                          | Press Enter to accept, or type yours (see `docker ps`)   |
| Google account email | none                                   | The account that owns the Keep lists                     |
| Master token         | none                                   | From step 1, typed hidden                                |
| Default list name    | `Shopping`                             | Press Enter to accept                                    |

It then shows what it will store (the token only as a length) and asks you to confirm. After that it installs the
package from your Pantry, stores the three secrets in the node's encrypted secret store, installs `gkeepapi` if it is
missing, and restarts the node. Each of those steps asks first. Values travel as environment variables, so they never
appear in a command line or in your shell history.

You can instead enter the same fields in the Jarvis admin portal or mobile app, in the package's settings.

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
| "Google rejected the Keep login"                       | Token revoked, expired or for a different account. Run `get-master-token.sh` again, then `set-secrets.sh`                  |
| `get_master_token.py`: not the `oauth_token` cookie    | You copied the wrong cookie or an empty value; it must start with `oauth2_4/`              |
| `get_master_token.py`: "Google did not return a token" | The cookie was already used or expired. Repeat step 2 from the EmbeddedSetup page          |
| "The Google Keep library is not installed"             | Run `set-secrets.sh` again and accept the `gkeepapi` install                          |
| "I couldn't find a Keep list called X"                 | The title does not match. Say the list name as it appears in Keep, or set the default list |
| `externally-managed-environment` from pip              | Use `get-master-token.sh`, which creates its own environment; do not use `--break-system-packages`                |
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
google_keep_tools/get-master-token.sh    asks for the email and cookie, prints the master token
google_keep_tools/get_master_token.py    the Python helper it runs
google_keep_tools/set-secrets.sh         asks for the settings and stores them on the node
tests/                                   offline tests with fakes
jarvis_package.yaml                      the Pantry manifest (secrets, packages)
```

## Licence

Apache-2.0. See `LICENSE` and `NOTICE`.
