#!/usr/bin/env bash
# Get a Google master token for Jarvis, asking for everything it needs. Nothing to edit, no arguments.
#
#   ./google_keep_tools/get-master-token.sh
#
# It creates a private Python environment (~/.venvs/gkeep) the first time, because Debian and Ubuntu refuse a
# system-wide `pip install` (PEP 668), then asks for your Google email and the oauth_token cookie.
set -eu

VENV="${GKEEP_VENV:-$HOME/.venvs/gkeep}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v python3 >/dev/null 2>&1 || { echo "Error: python3 is not installed." >&2; exit 1; }
if [ ! -x "$VENV/bin/python" ]; then
  echo "Creating a Python environment in $VENV ..."
  python3 -m venv "$VENV" || { echo "Error: could not create it. On Debian or Ubuntu run: sudo apt install python3-venv" >&2; exit 1; }
fi
"$VENV/bin/python" -c 'import gpsoauth' 2>/dev/null || "$VENV/bin/pip" install -q gpsoauth

cat <<'MSG'

Before continuing, in a browser:
  1. Open https://accounts.google.com/EmbeddedSetup , sign in as the Google account that owns your Keep lists and
     approve. The page then looks stuck on "loading"; that is normal.
  2. Open the developer tools, find the cookie called oauth_token for accounts.google.com (Application or Storage tab)
     and copy its value. It starts with oauth2_4/ and works once, so use it straight away.

MSG
exec "$VENV/bin/python" "$HERE/get_master_token.py" "$@"
