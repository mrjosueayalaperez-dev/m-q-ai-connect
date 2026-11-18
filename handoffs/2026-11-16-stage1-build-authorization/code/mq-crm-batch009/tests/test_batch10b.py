"""Batch 010b: server/API error messages in EN / ES / PT / HT.

C  catalog coverage: every literal error raised in app/ (found by AST) and
   every policy refusal reason has an ES, PT and HT entry
L  language choice: ?lang= > X-MQ-Lang > Accept-Language (q) > English;
   English responses are byte-for-byte what they were
S  security unchanged in every language: same status codes, ONE generic
   login failure (unknown user == wrong password), lockout 429 + Retry-After,
   401 WWW-Authenticate, CSRF 403, cookie flags, forged X-Role still 401
"""
import ast
import itertools
import json
import os
import secrets
import tempfile

import pytest

os.environ.setdefault("MQ_CRM_DB", os.path.join(tempfile.mkdtemp(), "b10b.db"))

from fastapi.testclient import TestClient  # noqa: E402

from app import auth, error_i18n  # noqa: E402
from app import main as main_mod  # noqa: E402
from tests.conftest import anonymous_client  # noqa: E402

LANGS = ("en", "es", "pt", "ht")
OTHER = ("es", "pt", "ht")
APP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
_ip = itertools.count(30)


def _anon(https=False):
    # TEST-NET-1 addresses no other test uses: no shared per-address lockout
    return anonymous_client(main_mod.app, base_url="https://testserver" if https else "http://testserver",
                            client=(f"192.0.2.{next(_ip)}", 41010))


def _user(role="staff"):
    pw = "Syn-" + secrets.token_urlsafe(18)
    u = auth.create_user(main_mod.conn, f"b10b-{role}-{secrets.token_hex(3)}", pw, role,
                         "Synthetic " + role, "b10b-setup", "system")
    return u, pw


def _login(c, username, password, lang=None, mode="token"):
    h = {"X-MQ-Lang": lang} if lang else {}
    return c.post("/api/auth/login", headers=h, json={"username": username, "password": password, "mode": mode})


# ---------------------------------------------------------------- C: coverage

SKIP = {  # not reachable as an HTTP error body (CLI exits, internal asserts, 500s)
    "refusing to read a password from a non-interactive stdin without --password-stdin",
    "passwords do not match", "password hasher is not argon2id", "kind must be cookie or bearer",
}
POLICY_REASONS = [
    "message is held for review: its purpose is unclear or unset",
    "message is held for review (promotional_content_in_transactional)",
    "customer no longer exists",
    "contact is on the do-not-message list for SMS (a retained opt-out)",
    "contact is on the do-not-message list for marketing (a retained opt-out)",
    "opt-out confirmation is no longer valid: it belongs to an opt-out event that is not the customer's active one",
    "customer has opted out of SMS — only the one-time opt-out confirmation may be sent on this channel",
    "customer consent is not current for marketing messages",
    "message is held for review: promotional content in a transactional message (sale, discount)",
]


def _templates():
    out = set()
    consts = {"GENERIC_FAILURE": auth.GENERIC_FAILURE, "LOCKED_MESSAGE": auth.LOCKED_MESSAGE}
    from app import totp
    consts.update(CHALLENGE_INVALID=totp.CHALLENGE_INVALID, CODE_INVALID=totp.CODE_INVALID)

    def tmpl(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            return n.value
        if isinstance(n, ast.JoinedStr):
            return "".join(v.value if isinstance(v, ast.Constant) else "X" for v in n.values)
        if isinstance(n, ast.Name) and n.id in consts:
            return consts[n.id]
        if isinstance(n, ast.Attribute) and n.attr in consts:
            return consts[n.attr]
        if isinstance(n, ast.BinOp):      # "prefix — " + START_FORMAT_HELP
            from app.services import bookings
            a = tmpl(n.left)
            b = bookings.START_FORMAT_HELP if getattr(n.right, "id", "") == "START_FORMAT_HELP" else tmpl(n.right)
            return a + b if a is not None and b is not None else None
        return None
    for dp, _, fs in os.walk(APP):
        for f in fs:
            if not f.endswith(".py") or f == "error_i18n.py":
                continue
            for n in ast.walk(ast.parse(open(os.path.join(dp, f), encoding="utf-8").read())):
                call = n.exc if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call) else (
                    n if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_deny" else None)
                if call is None:
                    continue
                for a in call.args:
                    t = tmpl(a)
                    if t:
                        out.add(t)
                        break
    return out - SKIP


def test_every_raised_error_message_has_es_pt_ht():
    temps = _templates()
    assert len(temps) > 90
    missing = []
    for t in sorted(temps):
        sample = t.replace("X refused: X", "send refused: customer no longer exists")
        for lang in OTHER:
            if error_i18n.translate(sample, lang) == sample:
                missing.append((lang, sample))
    assert not missing, missing[:10]


@pytest.mark.parametrize("stage", ["send", "dispatch"])
def test_policy_refusals_translate_stage_and_reason(stage):
    for reason in POLICY_REASONS:
        msg = f"{stage} refused: {reason}"
        for lang in OTHER:
            out = error_i18n.translate(msg, lang)
            assert out != msg and reason not in out, (lang, msg, out)


def test_values_are_carried_over():
    assert error_i18n.translate("cannot cancel a booking with status done", "es") == \
        "no se puede cancelar una reserva con estado done"
    assert error_i18n.translate("password must be at least 12 characters", "ht") == \
        "modpas la dwe gen omwen 12 karaktè"


def test_unknown_message_stays_english():
    assert error_i18n.translate("something brand new", "pt") == "something brand new"


def test_one_generic_login_failure_per_language():
    # the catalog holds exactly one sign-in failure text; nothing account-specific
    for lang in OTHER:
        t = error_i18n.translate(auth.GENERIC_FAILURE, lang)
        assert t != auth.GENERIC_FAILURE
        low = t.lower()
        for leak in ("no existe", "não existe", "pa egziste", "unknown", "desconocido", "desconhecido"):
            assert leak not in low


def test_pending_native_review_is_marked():
    src = open(os.path.join(APP, "error_i18n.py"), encoding="utf-8").read()
    assert "PENDING NATIVE REVIEW" in src


# ---------------------------------------------------------------- L: language choice

@pytest.mark.parametrize("qs,headers,expected", [
    (b"", [], "en"),
    (b"lang=es", [], "es"),
    (b"lang=pt-BR", [(b"x-mq-lang", b"ht")], "pt"),                 # explicit param wins
    (b"", [(b"x-mq-lang", b"ht")], "ht"),
    (b"", [(b"x-mq-lang", b"HT"), (b"accept-language", b"es")], "ht"),
    (b"", [(b"accept-language", b"fr-FR,pt-BR;q=0.8,es;q=0.9")], "es"),  # by q
    (b"", [(b"accept-language", b"de, fr;q=0.5")], "en"),            # unsupported -> en
    (b"", [(b"accept-language", b"es;q=0")], "en"),
    (b"lang=xx", [(b"x-mq-lang", b"zz")], "en"),
    (b"lang=%ff%fe", [], "en"),
])
def test_choose_language(qs, headers, expected):
    assert error_i18n.choose_language(qs, headers) == expected


def test_english_is_byte_for_byte_unchanged():
    c = _anon()
    plain = c.get("/api/customers")
    en = c.get("/api/customers", headers={"X-MQ-Lang": "en", "Accept-Language": "en-US"})
    assert plain.status_code == en.status_code == 401
    assert plain.content == en.content
    assert "detail_en" not in plain.json() and "content-language" not in plain.headers


def test_success_responses_untouched_in_every_language():
    c = TestClient(main_mod.app)
    base = c.get("/api/health").content
    for lang in OTHER:
        r = c.get("/api/health", headers={"X-MQ-Lang": lang})
        assert r.status_code == 200 and r.content == base and "content-language" not in r.headers


# ---------------------------------------------------------------- S: security unchanged

EXPECTED_LOGIN = {
    "es": "usuario o contraseña incorrectos",
    "pt": "usuário ou senha incorretos",
    "ht": "non itilizatè a oswa modpas la pa bon",
}


@pytest.mark.parametrize("lang", LANGS)
def test_login_failure_same_status_and_same_text_for_unknown_and_wrong(lang):
    u, pw = _user()
    wrong = _login(_anon(), u["username"], "Wrong-" + secrets.token_hex(6), lang)
    ghost = _login(_anon(), "ghost-" + secrets.token_hex(4), "Wrong-" + secrets.token_hex(6), lang)
    assert wrong.status_code == ghost.status_code == 401
    assert wrong.json() == ghost.json()                 # indistinguishable
    assert wrong.headers.get("www-authenticate") == ghost.headers.get("www-authenticate")
    if lang == "en":
        assert wrong.json() == {"detail": auth.GENERIC_FAILURE}
    else:
        assert wrong.json() == {"detail": EXPECTED_LOGIN[lang], "detail_en": auth.GENERIC_FAILURE}
        assert wrong.headers["content-language"] == lang
    assert "set-cookie" not in wrong.headers


@pytest.mark.parametrize("lang", OTHER)
def test_lockout_429_and_retry_after_unchanged(lang):
    u, pw = _user()
    for i in range(auth.USER_FAIL_LIMIT):
        assert _login(_anon(), u["username"], f"Nope-{i}-{secrets.token_hex(4)}", lang).status_code == 401
    r = _login(_anon(), u["username"], pw, lang)        # even the right password
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    assert r.json()["detail_en"] == auth.LOCKED_MESSAGE
    assert r.json()["detail"] == error_i18n.translate(auth.LOCKED_MESSAGE, lang) != auth.LOCKED_MESSAGE
    assert "token" not in r.json()


@pytest.mark.parametrize("lang", OTHER)
def test_no_session_401_keeps_www_authenticate(lang):
    en = _anon().get("/api/customers")
    r = _anon().get("/api/customers", headers={"X-MQ-Lang": lang, "X-Role": "owner"})
    assert r.status_code == en.status_code == 401
    assert r.headers["www-authenticate"] == en.headers["www-authenticate"]
    assert r.json()["detail_en"] == "login required — sign in to get a session"


@pytest.mark.parametrize("lang", OTHER)
def test_cookie_flags_and_csrf_unchanged(lang):
    u, pw = _user()
    c = _anon(https=True)
    r = _login(c, u["username"], pw, lang, mode="cookie")
    assert r.status_code == 200
    ck = r.headers["set-cookie"].lower()
    for flag in ("httponly", "secure", "samesite=strict", "path=/api"):
        assert flag in ck
    # cookie session, state-changing request without the CSRF header -> 403
    r = c.post("/api/customers", headers={"X-MQ-Lang": lang}, json={"name": "Syn CSRF"})
    assert r.status_code == 403 and r.json()["detail_en"] == "CSRF token missing or invalid"
    r = c.post("/api/customers", headers={"X-MQ-Lang": lang, "Origin": "https://evil.example"},
               json={"name": "Syn CSRF"})
    assert r.status_code == 403 and r.json()["detail_en"] == "cross-site request refused"


def test_status_codes_identical_across_languages():
    staff_u, staff_pw = _user("staff")
    view_u, view_pw = _user("viewer")
    tok = {r: _login(_anon(), u["username"], p).json()["token"]
           for r, (u, p) in {"staff": (staff_u, staff_pw), "viewer": (view_u, view_pw)}.items()}
    calls = [
        ("viewer", "post", "/api/customers", {"name": "Syn"}),
        ("staff", "post", "/api/bookings", {"customer_id": 1, "title": "x", "local_start": "garbage"}),
        ("staff", "post", "/api/bookings", {"customer_id": 987654, "title": "x", "local_start": "2027-01-01"}),
        ("staff", "post", "/api/bookings", {"customer_id": 1}),                 # 422 validation
        ("staff", "get", "/api/invoices/987654", None),
        ("staff", "delete", "/api/customers/1", None),                           # owner only
        ("staff", "post", "/api/auth/login/verify", {}),
        ("staff", "post", "/api/bookings/987654/cancel", None),
    ]
    for role, m, path, body in calls:
        seen = {}
        for lang in LANGS:
            h = {"Authorization": "Bearer " + tok[role], "X-MQ-Lang": lang}
            r = getattr(TestClient(main_mod.app), m)(path, headers=h, **({"json": body} if body is not None else {}))
            seen[lang] = (r.status_code, r.headers.get("www-authenticate"), r.headers.get("retry-after"))
            if r.status_code == 422:
                assert isinstance(r.json()["detail"], list)      # validation detail left as-is
        assert len(set(seen.values())) == 1, (path, seen)
        assert seen["en"][0] != 500


def test_bookings_400_is_translated():
    c = TestClient(main_mod.app)
    cid = c.post("/api/customers", json={"name": "Syn B10b", "phone": "3215559301"}).json()["customer"]["id"]
    r = c.post("/api/bookings", headers={"X-MQ-Lang": "es"},
               json={"customer_id": cid, "title": "x", "local_start": "2027-02-30"})
    assert r.status_code == 400
    assert r.json()["detail"].startswith("local_start no es una fecha u hora real")
    assert r.json()["detail_en"].startswith("local_start is not a real calendar date")


def test_web_sends_ui_language_and_login_reads_detail_en():
    web = os.path.join(os.path.dirname(APP), "web")
    app_js = open(os.path.join(web, "app.js"), encoding="utf-8").read()
    assert 'opts.headers["X-MQ-Lang"] = lang;' in app_js
    login_js = open(os.path.join(web, "login.js"), encoding="utf-8").read()
    assert '(body.detail_en || body.detail) === "invalid code"' in login_js
