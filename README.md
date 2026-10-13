# Google Keep for Jarvis

Read, add to, check off and clear your **Google Keep** lists by voice.

> "Hey Jarvis, add milk and eggs to my shopping list."
> "What's on my shopping list?"
> "Check off milk."
> "Clear the ticked items from my shopping list."
> "What lists do I have in Keep?"

## Read this first: it uses an unofficial API

Google Keep has no public API for personal accounts. The official Keep API exists only for Google Workspace
administrators. This package uses [gkeepapi](https://github.com/kiwiz/gkeepapi), which talks to the private API the
Keep mobile app uses, authenticated with a Google **master token**.

- **Google can change or block it without notice.** If it stops working, this package stops working.
- **The master token grants broad access to your Google account**, not just Keep. It is stored encrypted in the node's
  secret store. Treat it like a password: do not commit it, paste it into chat or share screenshots of it.
- Use of unofficial clients may be outside Google's terms of service. Use at your own risk, ideally with an account
  you can afford to have rate limited.

## Actions

| Say | Does |
| --- | --- |
| "add X (and Y) to my shopping list" | Adds items; an item already open on the list is not added twice |
| "what's on my shopping list" | Reads the open items (first 10, then "and N more") |
| "check off / tick off X" | Ticks items (fuzzy matched: "eggs please" finds "Eggs") |
| "untick X" | Puts a ticked item back |
| "clear the ticked items" | Deletes the ticked items from the list |
| "what lists do I have" | Lists your lists with their open item counts |

If you do not name a list, the default list is used (`GOOGLE_KEEP_DEFAULT_LIST`, default "Shopping"; if you have only one
list, that one).

## Setup

1. Install the package from the Pantry (it installs `gkeepapi`).
2. Get a master token:
   1. Open <https://accounts.google.com/EmbeddedSetup>, sign in and approve. The page then looks stuck; that is normal.
   2. In the browser's developer tools, copy the value of the `oauth_token` cookie (starts `oauth2_4/`).
   3. Use a virtual environment (Debian and Ubuntu refuse system-wide `pip install`, PEP 668):

      ```bash
      python3 -m venv ~/.venvs/gkeep && ~/.venvs/gkeep/bin/pip install gpsoauth
      ~/.venvs/gkeep/bin/python google_keep_tools/get_master_token.py you@gmail.com
      ```

      then paste the cookie at the hidden prompt. (`apt install python3-venv` first if `venv` is missing.)
3. Set the secrets on the node: `GOOGLE_KEEP_EMAIL`, `GOOGLE_KEEP_MASTER_TOKEN` and optionally
   `GOOGLE_KEEP_DEFAULT_LIST`.

## Development

```bash
pip install pytest jarvis-command-sdk gkeepapi
pytest
```

The tests use fakes shaped like gkeepapi's nodes, so they run offline. The live login has not been exercised in CI.

## Layout

```
commands/google_keep/command.py       the voice command
google_keep_shared/keep_service.py    list logic (matching, adding, checking), unit tested
google_keep_tools/get_master_token.py           one-off helper to obtain the master token
```
