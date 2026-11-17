"""One-time bootstrap of the FIRST owner account (Batch 009).

    python -m app.auth_cli create-owner --username <name> [--display-name "..."]
        prompts twice for the password (not echoed), or
    printf '%s\n' "$PW" | python -m app.auth_cli create-owner --username <name> --password-stdin

There is NO default password and NO HTTP setup route. The command refuses
once any owner account exists; after that the owner manages users in the
app. The password is never printed or logged. Run it on the server, against
the same database the API uses (MQ_CRM_DB).
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys

from . import auth
from . import db as dbmod


def _db_path() -> str:
    return os.environ.get("MQ_CRM_DB", os.path.join(
        os.path.dirname(__file__), "..", "data", "crm.db"))


def _read_password(from_stdin: bool) -> str:
    if from_stdin:
        line = sys.stdin.readline()
        return line[:-1] if line.endswith("\n") else line
    if not sys.stdin.isatty():
        raise SystemExit("refusing to read a password from a non-interactive"
                         " stdin without --password-stdin")
    first = getpass.getpass("New owner password: ")
    second = getpass.getpass("Repeat password: ")
    if first != second:
        raise SystemExit("passwords do not match")
    return first


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.auth_cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-owner", help="create the first owner (one time)")
    c.add_argument("--username", required=True)
    c.add_argument("--display-name", default=None)
    c.add_argument("--password-stdin", action="store_true",
                   help="read the password from the first line of stdin")
    args = p.parse_args(argv)

    path = _db_path()
    if path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = dbmod.connect(path)
    auth.ensure_schema(conn)
    if auth.owner_exists(conn):
        print("refused: an owner account already exists (bootstrap is one-time"
              " only)", file=sys.stderr)
        return 2
    try:
        username = auth.normalize_username(args.username)
        password = _read_password(args.password_stdin)
        user = auth.bootstrap_owner(conn, username, password, args.display_name)
    except (ValueError, auth.BootstrapRefused) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    finally:
        conn.close()
    print(f"owner account '{user['username']}' created. Sign in to the app"
          " with that username and the password you entered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
