#!/usr/bin/env python3
"""Exchange the Google ``oauth_token`` cookie for a master token for Google Keep.

    ./google_keep_tools/get-master-token.sh      # creates its own Python environment and asks for everything

1. Open https://accounts.google.com/EmbeddedSetup, sign in and approve (the page then looks stuck; that is normal).
2. In the browser's developer tools, copy the value of the ``oauth_token`` cookie (it starts ``oauth2_4/``).
3. Run this script and paste the cookie when asked. It prints the master token; give it to Jarvis as
   ``GOOGLE_KEEP_MASTER_TOKEN`` and keep it secret: it grants broad access to the account.
   (``set-secrets.sh`` does this step for you: it asks for the cookie and makes the master token itself.)

The cookie is read with a hidden prompt so it does not end up in shell history.
"""

import argparse
import getpass
import sys

DEFAULT_ANDROID_ID = "0123456789abcdef"


def main() -> int:
    parser = argparse.ArgumentParser(description="Get a Google master token for Google Keep")
    parser.add_argument("email", nargs="?", help="the Google account email (asked for when omitted)")
    parser.add_argument("--android-id", default=DEFAULT_ANDROID_ID, help="a 16 hex digit device id")
    parser.add_argument("--stdin", action="store_true",
                        help="read the oauth_token cookie from standard input and print only the token (for scripts)")
    args = parser.parse_args()

    try:
        import gpsoauth
    except ImportError:
        print("Install it first, in a virtual environment: python3 -m venv ~/.venvs/gkeep && ~/.venvs/gkeep/bin/pip install gpsoauth", file=sys.stderr)
        return 2

    email = (args.email or input("Google account email: ")).strip()
    if "@" not in email:
        print("That does not look like an email address.", file=sys.stderr)
        return 1
    if args.stdin:
        oauth_token = sys.stdin.readline().strip()
    else:
        oauth_token = getpass.getpass("oauth_token cookie value: ").strip()
    if not oauth_token.startswith("oauth2_4/"):
        print("That does not look like the oauth_token cookie (it should start with oauth2_4/).", file=sys.stderr)
        return 1

    response = gpsoauth.exchange_token(email, oauth_token, args.android_id)
    token = response.get("Token")
    if not token:
        print(f"Google did not return a token: {response.get('Error', 'unknown error')}", file=sys.stderr)
        return 1
    print(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
