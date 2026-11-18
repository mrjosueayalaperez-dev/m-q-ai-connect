"""Hardening follow-ups (2026-11-18) — review items L4, L5, L6.

L4  per-address sign-in throttle: X-Forwarded-For is read ONLY when the
    direct peer is a proxy listed in MQ_CRM_TRUSTED_PROXIES (off by default)
L5  requirements pinned exactly; hash lock file consistent with the pins
L6  422 bodies keep loc + type but never echo input values or parser context

Each item has deliberate-break checks: the same detector, pointed at the
pre-fix behaviour, must fail.
"""
import importlib
import itertools
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile

os.environ.setdefault("MQ_CRM_DB", os.path.join(tempfile.mkdtemp(), "hardening2.db"))

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from app import auth  # noqa: E402
from app import client_ip  # noqa: E402
from app import main as main_mod  # noqa: E402
from app import validation_errors  # noqa: E402
from tests.conftest import anonymous_client  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
client = TestClient(main_mod.app)
_n = itertools.count(1)


# ------------------------------------------------------------------ L4 unit

T = client_ip.parse_trusted("127.0.0.1, 10.0.0.0/8, ::1")


def test_l4_default_is_off_and_ignores_forwarded_for():
    assert client_ip.parse_trusted(None) == () and client_ip.parse_trusted("") == ()
    assert client_ip.TRUSTED == ()                  # the test env sets nothing
    assert client_ip.resolve("127.0.0.1", ["203.0.113.9"]) == "127.0.0.1"
    assert client_ip.resolve("198.51.100.4", ["203.0.113.9"], trusted=()) == "198.51.100.4"


def test_l4_untrusted_peer_never_uses_forwarded_for():
    assert client_ip.resolve("198.51.100.4", ["203.0.113.9"], T) == "198.51.100.4"
    assert client_ip.resolve("11.0.0.1", ["203.0.113.9"], T) == "11.0.0.1"


def test_l4_trusted_peer_uses_rightmost_untrusted_hop():
    assert client_ip.resolve("127.0.0.1", ["203.0.113.9"], T) == "203.0.113.9"
    # a client-supplied fake on the left is skipped: the proxy appended the real one
    assert client_ip.resolve("127.0.0.1", ["1.2.3.4, 203.0.113.9"], T) == "203.0.113.9"
    # chain of trusted proxies, several header lines
    assert client_ip.resolve("10.1.1.1", ["1.2.3.4", "203.0.113.9, 10.2.2.2"], T) == "203.0.113.9"
    assert client_ip.resolve("::1", ["2001:db8::5"], T) == "2001:db8::5"


def test_l4_malformed_or_all_trusted_falls_back_to_peer():
    assert client_ip.resolve("127.0.0.1", ["not-an-ip"], T) == "127.0.0.1"
    assert client_ip.resolve("127.0.0.1", ["203.0.113.9, garbage"], T) == "127.0.0.1"
    assert client_ip.resolve("127.0.0.1", ["10.0.0.5"], T) == "127.0.0.1"
    assert client_ip.resolve("127.0.0.1", [], T) == "127.0.0.1"
    assert client_ip.resolve("127.0.0.1", [", ".join(["203.0.113.9"] * 500)], T) == "127.0.0.1"
    assert client_ip.resolve(None, ["203.0.113.9"], T) == "unknown"


def test_l4_bad_setting_refuses_to_start():
    with pytest.raises(client_ip.TrustedProxyConfigError):
        client_ip.parse_trusted("127.0.0.1, localhost")
    env = dict(os.environ, MQ_CRM_TRUSTED_PROXIES="10.0.0.0/33",
               MQ_CRM_DB=os.path.join(tempfile.mkdtemp(), "x.db"))
    r = subprocess.run([sys.executable, "-c", "import app.main"], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "TrustedProxyConfigError" in r.stderr


def test_l4_deliberate_break_naive_forwarded_for_is_detected():
    def naive(peer, xff, trusted=None):          # the bug the setting prevents
        return xff[0].split(",")[0].strip() if xff else peer
    # the detector used above: an untrusted peer must keep its own address
    assert naive("198.51.100.4", ["203.0.113.9"], T) != "198.51.100.4"
    assert naive("127.0.0.1", ["1.2.3.4, 203.0.113.9"], T) != "203.0.113.9"


# ------------------------------------------------------------------ L4 end-to-end

def _spray_then_victim(app_client_factory, forwarded):
    """IP_FAIL_LIMIT failures with rotating X-Forwarded-For from ONE peer, then
    a correct sign-in from the same peer. Returns the victim's status."""
    u = auth.create_user(main_mod.conn, f"l4-{secrets.token_hex(4)}",
                         pw := "Synthetic-" + secrets.token_urlsafe(18), "viewer",
                         None, "l4", "system")
    c = app_client_factory()
    for i in range(auth.IP_FAIL_LIMIT):
        c.post("/api/auth/login", headers={"X-Forwarded-For": forwarded(i)},
               json={"username": f"spray-{i}-{secrets.token_hex(2)}",
                     "password": "Spray-password-123", "mode": "token"})
    return c.post("/api/auth/login", headers={"X-Forwarded-For": forwarded(999)},
                  json={"username": u["username"], "password": pw, "mode": "token"}).status_code


def test_l4_e2e_default_spoofed_forwarded_for_cannot_dodge_the_address_lock():
    peer = f"198.51.100.{200 + next(_n) % 50}"
    st = _spray_then_victim(lambda: anonymous_client(main_mod.app, client=(peer, 40000)),
                            lambda i: f"203.0.113.{i % 250}")
    assert st == 429           # all 20 counted against the real peer, rotation ignored


def test_l4_e2e_trusted_proxy_throttles_per_real_client(monkeypatch):
    monkeypatch.setattr(client_ip, "TRUSTED", client_ip.parse_trusted("127.0.0.0/8"))
    peer = f"127.0.{next(_n)}.1"
    base = 100 + next(_n)
    # sprayer behind the proxy is 192.0.2.<base>; victim is another address
    u = auth.create_user(main_mod.conn, f"l4b-{secrets.token_hex(4)}",
                         pw := "Synthetic-" + secrets.token_urlsafe(18), "viewer",
                         None, "l4", "system")
    c = anonymous_client(main_mod.app, client=(peer, 40000))
    for i in range(auth.IP_FAIL_LIMIT):
        c.post("/api/auth/login", headers={"X-Forwarded-For": f"192.0.2.{base}"},
               json={"username": f"spray2-{i}-{secrets.token_hex(2)}",
                     "password": "Spray-password-123", "mode": "token"})
    blocked = c.post("/api/auth/login", headers={"X-Forwarded-For": f"192.0.2.{base}"},
                     json={"username": u["username"], "password": pw, "mode": "token"})
    other = c.post("/api/auth/login", headers={"X-Forwarded-For": f"192.0.2.{base + 1}"},
                   json={"username": u["username"], "password": pw, "mode": "token"})
    assert blocked.status_code == 429          # the real sprayer address is locked
    assert other.status_code == 200            # other clients behind the same proxy are not


# ------------------------------------------------------------------ L5

_PIN = re.compile(r"^([A-Za-z0-9_.\-]+)(\[[^\]]+\])?==([^\s;\\]+)\s*(;.*)?$")


def _reqs(path):
    out = {}
    for ln in open(path, encoding="utf-8"):
        ln = ln.split(" #")[0].strip().rstrip("\\").strip()
        if not ln or ln.startswith("#") or ln.startswith("--"):
            continue
        out[ln.split("==")[0].split("[")[0].split(";")[0].strip().lower()] = ln
    return out


def _unpinned(reqs: dict) -> list[str]:
    return [ln for ln in reqs.values() if not _PIN.match(ln)]


def test_l5_every_requirement_is_pinned_exactly():
    reqs = _reqs(os.path.join(ROOT, "requirements.txt"))
    assert _unpinned(reqs) == []
    for name in ("fastapi", "uvicorn", "pydantic", "pytest", "httpx", "argon2-cffi",
                 "cryptography", "starlette", "pydantic-core", "h11"):
        assert name in reqs, name


def test_l5_pins_match_the_running_environment():
    from importlib import metadata
    from packaging.markers import Marker
    reqs = _reqs(os.path.join(ROOT, "requirements.txt"))
    for name, ln in reqs.items():
        m = _PIN.match(ln)
        if m.group(4) and not Marker(m.group(4)[1:].strip()).evaluate():
            continue
        assert metadata.version(m.group(1)) == m.group(3), (name, metadata.version(m.group(1)))


def test_l5_lock_file_has_hashes_and_matches_pins():
    lock_path = os.path.join(ROOT, "requirements-lock.txt")
    text = open(lock_path, encoding="utf-8").read()
    blocks = re.split(r"\n(?=[A-Za-z0-9])", text.split("\n\n", 1)[1].strip())
    lock = {}
    for b in blocks:
        head = b.splitlines()[0].rstrip("\\").strip()
        assert "--hash=sha256:" in b, head
        lock[head.split("==")[0].lower()] = head.split("==")[1].split()[0].split(";")[0]
    pins = {n: _PIN.match(ln).group(3) for n, ln in
            _reqs(os.path.join(ROOT, "requirements.txt")).items()}
    assert {n: v for n, v in pins.items() if n != "colorama"} == lock


def test_l5_deliberate_break_loose_requirement_is_detected():
    assert _unpinned({"fastapi": "fastapi", "x": "x>=1.0", "y": "y~=2.0"}) == ["fastapi", "x>=1.0", "y~=2.0"]
    assert _unpinned({"a": "a==1.0", "b": 'b==2 ; sys_platform == "win32"'}) == []


# ------------------------------------------------------------------ L6

SECRET = "Pw-" + secrets.token_urlsafe(16)


def _echoes(body_text: str, needle: str) -> bool:
    return needle in body_text


def _shape_ok(body) -> bool:
    return isinstance(body.get("detail"), list) and all(
        set(i) == {"loc", "type", "msg"} for i in body["detail"])


@pytest.mark.parametrize("payload, raw", [
    ({"customer_id": SECRET, "title": "x", "local_start": "2027-01-01"}, None),   # int parsing
    ({"customer_id": 1, "title": {"k": SECRET}, "local_start": "2027-01-01"}, None),
    ({"title": SECRET}, None),                                                       # missing
    (None, '{"customer_id": 1, "title": "' + SECRET + '", oops'),                    # bad JSON
])
def test_l6_422_never_echoes_input(payload, raw):
    kw = {"json": payload} if raw is None else {"content": raw,
                                                "headers": {"Content-Type": "application/json"}}
    r = client.post("/api/bookings", **kw)
    assert r.status_code == 422
    assert not _echoes(r.text, SECRET)
    body = r.json()
    assert _shape_ok(body)
    assert '"input"' not in r.text and '"ctx"' not in r.text and '"url"' not in r.text
    for item in body["detail"]:
        assert item["loc"][0] == "body"
        assert item["msg"] in set(validation_errors.MESSAGES.values()) | {validation_errors.GENERIC}


def test_l6_login_422_never_echoes_password():
    r = anonymous_client(main_mod.app).post("/api/auth/login", json={"username": "x", "password": 12345678901234})
    assert r.status_code == 422 and "12345678901234" not in r.text
    r = anonymous_client(main_mod.app).post("/api/auth/login", json={"password": SECRET})
    assert r.status_code == 422 and SECRET not in r.text
    assert {"loc": ["body", "username"], "type": "missing", "msg": "field required"} in r.json()["detail"]


def test_l6_same_status_and_body_in_every_language_and_headers_kept():
    seen = set()
    for lang in ("en", "es", "pt", "ht"):
        r = client.post("/api/bookings", headers={"X-MQ-Lang": lang},
                        json={"customer_id": SECRET, "title": "x", "local_start": "2027-01-01"})
        assert r.status_code == 422 and SECRET not in r.text
        seen.add(r.text)
        assert r.headers.get("x-content-type-options") == "nosniff"
    assert len(seen) == 1           # 422 lists are not translated (docs/ERROR-LANGUAGES.md)


def test_l6_loc_sanitizer_drops_non_field_text():
    out = validation_errors.sanitize([{"loc": ("body", "context", SECRET, 3, True), "type": "x_y",
                                       "msg": SECRET, "input": SECRET, "ctx": {"e": SECRET}},
                                      {"loc": (SECRET,), "type": SECRET}])
    assert SECRET not in json.dumps(out)
    assert out[0] == {"loc": ["body", "context", "*", 3, "*"], "type": "x_y", "msg": "invalid value"}
    assert out[1]["loc"] == ["*"] and out[1]["type"] == "invalid"


def test_l6_deliberate_break_default_handler_is_detected():
    class In(BaseModel):
        n: int

    def make(with_handler):
        a = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

        @a.post("/x")
        def x(body: In):
            return {}
        if with_handler:
            a.add_exception_handler(main_mod.RequestValidationError, validation_errors.handler)
        return TestClient(a)
    r = make(False).post("/x", json={"n": SECRET})
    assert r.status_code == 422 and _echoes(r.text, SECRET)   # FastAPI's default echoes input
    r = make(True).post("/x", json={"n": SECRET})
    assert r.status_code == 422 and not _echoes(r.text, SECRET) and _shape_ok(r.json())
