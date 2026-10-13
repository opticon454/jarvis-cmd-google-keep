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

### 1. Install the package on the node

Find the name of your node's container with `docker ps`. The examples use `jarvis-node`, the name in Jarvis's reference
Docker setup; the voice-node image is commonly run as `jarvis-node-audio`, and your own compose file may differ. Set it
once; every command below, and the helper script in step 3, use `$NODE` and default to `jarvis-node`:

```bash
export NODE=jarvis-node        # your node's container name, from `docker ps`
```

Install the package from a Pantry that lists it (a node whose `command_store_url` points at that Pantry):

```bash
docker exec -w /app "$NODE" python scripts/command_store.py install google_keep
docker exec "$NODE" pip install gkeepapi    # only if the installer did not pull it in
```

A private package is added to a Pantry with `POST /v1/admin/commands/from-repo` and this repository's URL.

The installer puts `gkeepapi` in the container's writable layer, so run the `pip install` again after any recreate of
the node container.

### 2. Get a master token

Do this on a machine with a browser. It is a one-off step.

1. Open <https://accounts.google.com/EmbeddedSetup>, sign in as the Google account that owns the lists and approve. The
   page then looks stuck on "loading"; that is normal.
2. In the browser's developer tools (Application or Storage, then Cookies for `accounts.google.com`), copy the value of
   the **`oauth_token`** cookie. It starts with `oauth2_4/`. Use it promptly: it is short lived and single use.
3. Debian and Ubuntu refuse a system-wide `pip install` (PEP 668), so use a virtual environment:

   ```bash
   python3 -m venv ~/.venvs/gkeep
   ~/.venvs/gkeep/bin/pip install gpsoauth
   cd jarvis-cmd-google-keep          # a checkout of this repository
   ~/.venvs/gkeep/bin/python google_keep_tools/get_master_token.py you@gmail.com
   ```

4. Paste the cookie at the hidden prompt. The script prints the master token (it starts with `aas_et/`). Copy it
   somewhere safe for the next step, then clear your terminal and clipboard.

Optional: `--android-id` takes a 16 hex digit device id if you want the token tied to a fixed one.

### 3. Give the node the secrets

Run the helper on the machine that runs the node's Docker container (for a node on another machine, run it there or
over SSH). It asks the questions one at a time and stores the answers in the node's encrypted secret store
with the `integration` scope:

```bash
./google_keep_tools/set-secrets.sh
```

| It asks for                | Default         | Notes                                                                    |
| -------------------------- | --------------- | ------------------------------------------------------------------------ |
| Node container name        | `$NODE`, else `jarvis-node` | Press Enter to accept, or type your container's name         |
| Google account email       | none            | The account that owns the Keep lists                                     |
| Master token               | none            | Typed hidden, so it is not echoed or kept in shell history               |
| Default list name          | `Shopping`      | Press Enter to accept                                                    |

It then shows what it will store (the token only as a length), asks you to confirm, stores the three secrets, offers to
install `gkeepapi` in the container if it is missing, and offers to restart the container (step 4). The values are passed
to the container as environment variables, so they never appear in a command line.

You can instead fill in the same fields in the Jarvis admin portal or mobile app, in the package's settings.

| Secret                     | Sensitive | Required | Meaning                                         |
| -------------------------- | --------- | -------- | ----------------------------------------------- |
| `GOOGLE_KEEP_EMAIL`        | no        | yes      | The Google account that owns the lists          |
| `GOOGLE_KEEP_MASTER_TOKEN` | yes       | yes      | The master token from step 2                    |
| `GOOGLE_KEEP_DEFAULT_LIST` | no        | no       | List used when you do not name one (`Shopping`) |

### 4. Restart the node

The helper offers to do this. By hand:

```bash
docker restart "$NODE"
```

so it reloads its commands.

## Check that it works

1. In the Keep app, make sure a checklist called **Shopping** exists (or set `GOOGLE_KEEP_DEFAULT_LIST`).
2. Say, or send as text: "what lists do I have in Keep". It should name your lists.
3. "Add milk to my shopping list", then open Keep: the item appears within a few seconds.
4. "Check off milk", then "clear the ticked items from my shopping list".

The node log (`docker logs "$NODE"`) shows the command running and any error.

## Troubleshooting

| Symptom                                                | Cause and fix                                                                              |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| "Google Keep isn't set up yet"                         | The email or token secret is missing on that node; set both (step 3) and restart           |
| "Google rejected the Keep login"                       | Token revoked, expired or for a different account. Get a new one (step 2)                  |
| `get_master_token.py`: not the `oauth_token` cookie    | You copied the wrong cookie or an empty value; it must start with `oauth2_4/`              |
| `get_master_token.py`: "Google did not return a token" | The cookie was already used or expired. Repeat step 2 from the EmbeddedSetup page          |
| "The Google Keep library is not installed"             | `docker exec "$NODE" pip install gkeepapi`, then restart                          |
| "I couldn't find a Keep list called X"                 | The title does not match. Say the list name as it appears in Keep, or set the default list |
| `externally-managed-environment` from pip              | Use the virtual environment in step 2; do not use `--break-system-packages`                |
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
google_keep_tools/get_master_token.py    one-off helper to obtain the master token
google_keep_tools/set-secrets.sh         asks for the settings and stores them on the node
tests/                                   offline tests with fakes
jarvis_package.yaml                      the Pantry manifest (secrets, packages)
```

## Licence

Apache-2.0. See `LICENSE` and `NOTICE`.
