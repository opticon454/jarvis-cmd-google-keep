#!/usr/bin/env bash
# Ask for the Google Keep settings and store them in a Jarvis node's encrypted secret store.
#
#   ./google_keep_tools/set-secrets.sh
#
# Run it on the machine that runs the node's Docker container (the Nemesis host for `jarvis-node`, the Raspberry Pi for
# `jarvis-node-audio`). It asks for:
#
#   container   the node's container name                       (default: jarvis-node)
#   email       the Google account that owns the Keep lists
#   token       the master token from get_master_token.py       (typed hidden; never shown or kept in shell history)
#   list        the list used when you do not name one          (default: Shopping)
#
# Values are passed to the container as environment variables, so they never appear in a process list or in a command
# line. Nothing is written to disk by this script.

set -u

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }

# ask VAR "Prompt" "default" [hidden]  - reads into VAR; an empty answer takes the default
ask() {
  local var=$1 prompt=$2 default=${3-} hidden=${4-} reply
  while true; do
    if [ -n "$default" ]; then prompt_text="$prompt [$default]: "; else prompt_text="$prompt: "; fi
    if [ "$hidden" = hidden ]; then
      IFS= read -rsp "$prompt_text" reply; echo
    else
      IFS= read -rp "$prompt_text" reply
    fi
    reply=${reply:-$default}
    if [ -n "$reply" ]; then printf -v "$var" '%s' "$reply"; return; fi
    echo "A value is required."
  done
}

command -v docker >/dev/null 2>&1 || fail "docker is not installed or not on PATH on this machine."

ask CONTAINER "Node container name" "jarvis-node"
docker ps --format '{{.Names}}' | grep -qx -- "$CONTAINER" \
  || fail "no running container called '$CONTAINER'. Running containers: $(docker ps --format '{{.Names}}' | tr '\n' ' ')"

ask KEEP_EMAIL "Google account email (owns the Keep lists)" ""
case $KEEP_EMAIL in *@*.*) ;; *) fail "'$KEEP_EMAIL' does not look like an email address." ;; esac

ask KEEP_TOKEN "Master token (hidden; starts with aas_et/)" "" hidden
case $KEEP_TOKEN in aas_et/*) ;; *) echo "Note: the token does not start with aas_et/. Continuing; check it if the login fails." ;; esac

ask KEEP_LIST "Default list name" "Shopping"

echo
echo "About to store, in '$CONTAINER':"
echo "  GOOGLE_KEEP_EMAIL         = $KEEP_EMAIL"
echo "  GOOGLE_KEEP_MASTER_TOKEN  = (hidden, ${#KEEP_TOKEN} characters)"
echo "  GOOGLE_KEEP_DEFAULT_LIST  = $KEEP_LIST"
read -rp "Continue? [Y/n]: " go
case ${go:-Y} in [Yy]*) ;; *) echo "Cancelled; nothing was changed."; exit 0 ;; esac

export KEEP_EMAIL KEEP_TOKEN KEEP_LIST
docker exec -w /app -e KEEP_EMAIL -e KEEP_TOKEN -e KEEP_LIST "$CONTAINER" python -c '
import os
from services.secret_service import set_secret
for key, env in (("GOOGLE_KEEP_EMAIL", "KEEP_EMAIL"),
                 ("GOOGLE_KEEP_MASTER_TOKEN", "KEEP_TOKEN"),
                 ("GOOGLE_KEEP_DEFAULT_LIST", "KEEP_LIST")):
    set_secret(key, os.environ[env], "integration")
    print("stored", key)
' || { unset KEEP_TOKEN; fail "could not store the secrets (is this a Jarvis node container?)."; }
unset KEEP_TOKEN KEEP_EMAIL KEEP_LIST

# The package needs gkeepapi inside the container; the installer's pip install is lost when the container is recreated.
if ! docker exec "$CONTAINER" python -c 'import gkeepapi' >/dev/null 2>&1; then
  echo "gkeepapi is not installed in '$CONTAINER'."
  read -rp "Install it now? [Y/n]: " inst
  case ${inst:-Y} in [Yy]*) docker exec "$CONTAINER" pip install -q gkeepapi || echo "pip install failed; install it by hand." ;; esac
fi

read -rp "Restart '$CONTAINER' now so it reloads its commands? [Y/n]: " rs
case ${rs:-Y} in [Yy]*) docker restart "$CONTAINER" >/dev/null && echo "Restarted." ;; *) echo "Not restarted; restart it before testing." ;; esac

echo
echo "Done. Test with: \"what lists do I have in Keep\" (see README, 'Check that it works')."
