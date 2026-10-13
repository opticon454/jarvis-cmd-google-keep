#!/usr/bin/env bash
# Ask for the Google Keep settings and store them in a Jarvis node's encrypted secret store.
#
#   ./google_keep_tools/set-secrets.sh
#
# It can run on the machine that runs the node's Docker container, or anywhere that can SSH to it: it asks where
# Docker is (press Enter for this machine, or type user@host) and then asks for:
#
#   host        where the node's Docker runs                   (default: this machine)
#   container   the node's container name                      (default: jarvis-node; see `docker ps` on that host)
#   email       the Google account that owns the Keep lists
#   token       the master token from get-master-token.sh      (typed hidden; never shown or kept in shell history)
#   list        the list used when you do not name one         (default: Shopping)
#
# Over SSH it opens one connection (password or key, you are asked at most once). Values go to the container on standard
# input (base64), never on a command line. Nothing is written to disk. It also installs the package and restarts the
# node, asking before each step.

set -u

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }

# ask VAR "Prompt" "default" [hidden|optional]  - reads into VAR; an empty answer takes the default
ask() {
  local var=$1 prompt=$2 default=${3-} mode=${4-} reply
  while true; do
    if [ -n "$default" ]; then prompt_text="$prompt [$default]: "; else prompt_text="$prompt: "; fi
    if [ "$mode" = hidden ]; then
      IFS= read -rsp "$prompt_text" reply; echo
    else
      IFS= read -rp "$prompt_text" reply
    fi
    reply=${reply:-$default}
    if [ -n "$reply" ] || [ "$mode" = optional ]; then printf -v "$var" '%s' "$reply"; return; fi
    echo "A value is required."
  done
}

ask HOST "Where does the node's Docker run? Enter for this machine, or user@host" "" optional

# With a remote host, open ONE SSH connection (SSH may ask for the password or host key once) and reuse it for every
# step below, so you are not asked again. SSH keys are not required.
if [ -n "$HOST" ]; then
  command -v ssh >/dev/null 2>&1 || fail "ssh is not installed on this machine."
  SSH_DIR=$(mktemp -d /tmp/jk-ssh.XXXXXX) || fail "could not create a temporary directory."
  SSH_SOCK="$SSH_DIR/s"
  trap 'ssh -S "$SSH_SOCK" -O exit "$HOST" >/dev/null 2>&1; rm -rf "$SSH_DIR"' EXIT
  echo "Connecting to $HOST (enter its password if it asks) ..."
  ssh -o ControlMaster=yes -o ControlPath="$SSH_SOCK" -o ControlPersist=10m -fN "$HOST" \
    || fail "could not connect to $HOST."
fi

# dk ARGS...  - run `docker ARGS` on the chosen host, quoting each argument for the remote shell
dk() {
  if [ -z "$HOST" ]; then docker "$@"; return; fi
  local q="" a
  for a in "$@"; do q+=" $(printf '%q' "$a")"; done
  ssh -S "$SSH_SOCK" "$HOST" "docker$q"
}

if [ -z "$HOST" ]; then
  command -v docker >/dev/null 2>&1 || fail "docker is not installed on this machine. Run this where the node runs, or give user@host."
fi

RUNNING=$(dk ps --format '{{.Names}}' 2>/dev/null) || fail "could not run docker${HOST:+ on $HOST} (is Docker running, and can you use it?)."

ask CONTAINER "Node container name" "jarvis-node"
printf '%s\n' "$RUNNING" | grep -qx -- "$CONTAINER" \
  || fail "no running container called '$CONTAINER'${HOST:+ on $HOST}. Running there: $(printf '%s' "$RUNNING" | tr '\n' ' ')
If the node runs on a different machine, run this again and give its user@host."

ask KEEP_EMAIL "Google account email (owns the Keep lists)" ""
case $KEEP_EMAIL in *@*.*) ;; *) fail "'$KEEP_EMAIL' does not look like an email address." ;; esac

ask KEEP_TOKEN "Master token (hidden; starts with aas_et/)" "" hidden
case $KEEP_TOKEN in aas_et/*) ;; *) echo "Note: the token does not start with aas_et/. Continuing; check it if the login fails." ;; esac

ask KEEP_LIST "Default list name" "Shopping"

echo
echo "About to store, in '$CONTAINER'${HOST:+ on $HOST}:"
echo "  GOOGLE_KEEP_EMAIL         = $KEEP_EMAIL"
echo "  GOOGLE_KEEP_MASTER_TOKEN  = (hidden, ${#KEEP_TOKEN} characters)"
echo "  GOOGLE_KEEP_DEFAULT_LIST  = $KEEP_LIST"
read -rp "Continue? [Y/n]: " go
case ${go:-Y} in [Yy]*) ;; *) echo "Cancelled; nothing was changed."; exit 0 ;; esac

# Install the package into the node from its Pantry (it may already be installed; this just refreshes it).
read -rp "Install or update the google_keep package in '$CONTAINER' from its Pantry now? [Y/n]: " pk
case ${pk:-Y} in
  [Yy]*) dk exec -w /app "$CONTAINER" python scripts/command_store.py install google_keep \
           || echo "Package install failed; add the package to your Pantry or install it by hand, then run this again." ;;
esac

PY='
import base64, sys
from services.secret_service import set_secret
email, token, default = [base64.b64decode(l).decode() for l in sys.stdin.read().split()]
for key, value in (("GOOGLE_KEEP_EMAIL", email), ("GOOGLE_KEEP_MASTER_TOKEN", token), ("GOOGLE_KEEP_DEFAULT_LIST", default)):
    set_secret(key, value, "integration")
    print("stored", key)
'
b64() { printf '%s' "$1" | base64 | tr -d '\n'; }
printf '%s\n%s\n%s\n' "$(b64 "$KEEP_EMAIL")" "$(b64 "$KEEP_TOKEN")" "$(b64 "$KEEP_LIST")" \
  | dk exec -i -w /app "$CONTAINER" python -c "$PY" \
  || { unset KEEP_TOKEN; fail "could not store the secrets (is this a Jarvis node container?)."; }
unset KEEP_TOKEN KEEP_EMAIL KEEP_LIST

# The package needs gkeepapi inside the container; the installer's pip install is lost when the container is recreated.
if ! dk exec "$CONTAINER" python -c 'import gkeepapi' >/dev/null 2>&1; then
  echo "gkeepapi is not installed in '$CONTAINER'."
  read -rp "Install it now? [Y/n]: " inst
  case ${inst:-Y} in [Yy]*) dk exec "$CONTAINER" pip install -q gkeepapi || echo "pip install failed; install it by hand." ;; esac
fi

read -rp "Restart '$CONTAINER' now so it reloads its commands? [Y/n]: " rs
case ${rs:-Y} in [Yy]*) dk restart "$CONTAINER" >/dev/null && echo "Restarted." ;; *) echo "Not restarted; restart it before testing." ;; esac

echo
echo "Done. Test with: \"what lists do I have in Keep\" (see README, 'Check that it works')."
