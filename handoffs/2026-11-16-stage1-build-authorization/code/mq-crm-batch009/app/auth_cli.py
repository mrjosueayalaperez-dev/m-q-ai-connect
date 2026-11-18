"""Server-shell account commands (Batch 009 / 009b).

    python -m app.auth_cli create-owner --username <name> [--display-name "..."]
        one-time bootstrap of the FIRST owner; prompts twice for the
        password (not echoed), or reads it with --password-stdin:
    printf '%s\n' "$PW" | python -m app.auth_cli create-owner --username <name> --password-stdin

    python -m app.auth_cli reset-password --username <name> [--password-stdin]
        Batch 009b password RECOVERY (e.g. a forgotten owner password). Applies
        the password policy, signs the account out everywhere (all sessions
        and pending two-step challenges revoked), clears its lockout, and
        writes an audit entry (source=cli). Two-step login is NOT changed.

    python -m app.auth_cli reset-totp --username <name> --yes
        Batch 009b BREAK-GLASS for a lost authenticator phone: removes the
        account's two-step factor and recovery codes and signs it out
        everywhere. Audited (source=cli). Re-enroll after signing in.

These exist ONLY on the server shell: there is no web, email or API
password-recovery path. Passwords, secrets and codes are never printed.

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


def _read_password(from_stdin: bool, prompt: str = "New owner password: ") -> str:
    if from_stdin:
        line = sys.stdin.readline()
        return line[:-1] if line.endswith("\n") else line
    if not sys.stdin.isatty():
        raise SystemExit("refusing to read a password from a non-interactive"
                         " stdin without --password-stdin")
    first = getpass.getpass(prompt)
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
    r = sub.add_parser("reset-password",
                       help="server-shell password recovery (signs out everywhere)")
    r.add_argument("--username", required=True)
    r.add_argument("--password-stdin", action="store_true",
                   help="read the new password from the first line of stdin")
    t = sub.add_parser("reset-totp",
                       help="break-glass: remove two-step login (lost phone)")
    t.add_argument("--username", required=True)
    t.add_argument("--yes", action="store_true",
                   help="confirm: remove the factor and recovery codes")
    args = p.parse_args(argv)

    path = _db_path()
    if path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = dbmod.connect(path)
    auth.ensure_schema(conn)
    try:
        if args.cmd == "create-owner":
            return _create_owner(conn, args)
        if args.cmd == "reset-password":
            return _reset_password(conn, args)
        return _reset_totp(conn, args)
    finally:
        conn.close()


def _create_owner(conn, args) -> int:
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
    print(f"owner account '{user['username']}' created. Sign in to the app"
          " with that username and the password you entered.")
    return 0


def _reset_password(conn, args) -> int:
    try:
        username = auth.normalize_username(args.username)
        if conn.execute("SELECT 1 FROM users WHERE username = ?",
                        (username,)).fetchone() is None:
            raise LookupError("user not found")
        password = _read_password(args.password_stdin, f"New password for {username}: ")
        out = auth.cli_reset_password(conn, username, password)
    except (ValueError, LookupError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    print(f"password for '{out['username']}' reset; {out['sessions_revoked']}"
          " session(s) signed out and the account's lockout cleared. Two-step"
          " login (if enabled) is unchanged.")
    return 0


def _reset_totp(conn, args) -> int:
    from . import totp
    if not args.yes:
        print("refused: add --yes to remove this account's two-step login and"
              " recovery codes", file=sys.stderr)
        return 2
    try:
        out = totp.cli_reset(conn, auth.normalize_username(args.username))
    except (ValueError, LookupError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    what = "removed" if out["had_factor"] else "was not set up (nothing to remove)"
    print(f"two-step login for '{out['username']}' {what};"
          f" {out['sessions_revoked']} session(s) signed out. Sign in with the"
          " password and enroll a new device.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
