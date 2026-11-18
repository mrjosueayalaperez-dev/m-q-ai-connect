"""Batch 009c: premium sign-in screen (presentation only).

L  every login string exists, non-empty, in EN / ES / PT / HT with the same
   placeholders; every key the page or login.js uses exists; no English left
   in the other three languages (small brand allowlist)
S  the new client stores only the language and (opt-in) the username, never
   a password or token; never sends X-Role; uses the existing endpoints
R  "Remember me" cannot lengthen a session: the login payload is unchanged
   and an extra field gives the same 30 min idle / 12 h absolute session
A  the assets are served, the old login markup is gone, the open paths are
   unchanged and a forged X-Role is still ignored
"""
import json
import os
import re
import secrets
import tempfile
from datetime import datetime, timezone

os.environ.setdefault("MQ_CRM_DB", os.path.join(tempfile.mkdtemp(), "b9c.db"))

from app import auth  # noqa: E402
from app import main as main_mod  # noqa: E402
from tests.conftest import anonymous_client  # noqa: E402

WEB = os.path.join(os.path.dirname(__file__), "..", "web")
LANGS = ("en", "es", "pt", "ht")
# identical-to-English values that are correct in every language
SAME_OK = {"HTTPS"}


def _read(name):
    with open(os.path.join(WEB, name), encoding="utf-8") as f:
        return f.read()


def _strings():
    src = _read("login_i18n.js")
    return json.loads(src.split("window.LOGIN_STRINGS =", 1)[1].strip().rstrip(";"))


def _used_keys():
    html = _read("index.html")
    js = _read("login.js")
    keys = set(re.findall(r'data-li18n(?:-title)?="([a-z_]+)"', html))
    keys |= set(re.findall(r'\bt\("([a-z_]+)"', js))
    keys |= set(re.findall(r'"((?:err|totp|recovery|secure|role)_[a-z_]+)"', js))
    for tern in re.findall(r'\bt\(\s*[^()]*\?\s*"([a-z_]+)"\s*:\s*"([a-z_]+)"', js):
        keys |= set(tern)
    keys |= set(re.findall(r'setNotice\(\s*[^)]*?"([a-z_]+)"', js))
    keys |= set(re.findall(r'busy\("[a-z-]+",\s*(?:true|false),\s*"([a-z_]+)"\)', js))
    keys.discard("role_")                                  # t("role_" + user.role)
    keys |= {"role_owner", "role_staff", "role_viewer"}
    return keys


def test_b9c_L1_all_four_locales_have_identical_non_empty_keys():
    s = _strings()
    assert set(s) == set(LANGS)
    base = set(s["en"])
    assert len(base) >= 60
    for lang in LANGS:
        assert set(s[lang]) == base, (lang, base ^ set(s[lang]))
        empty = [k for k, v in s[lang].items() if not str(v).strip()]
        assert not empty, (lang, empty)


def test_b9c_L2_placeholders_match_in_every_locale():
    s = _strings()
    for k, v in s["en"].items():
        want = sorted(re.findall(r"\{[a-z]+\}", v))
        for lang in LANGS:
            assert sorted(re.findall(r"\{[a-z]+\}", s[lang][k])) == want, (lang, k)


def test_b9c_L3_every_key_used_by_the_page_exists():
    s = _strings()
    used = _used_keys()
    assert len(used) >= 45, sorted(used)
    missing = sorted(k for k in used if k not in s["en"])
    assert not missing, missing


def test_b9c_L4_no_english_left_in_es_pt_ht():
    s = _strings()
    for lang in ("es", "pt", "ht"):
        same = [k for k, v in s["en"].items() if s[lang][k] == v and v not in SAME_OK]
        assert not same, (lang, same)
        joined = " ".join(s[lang].values()).lower()
        for marker in ("todo", "lorem", "[ht]", "[pt]", "[es]", "translate", "xxx "):
            assert marker not in joined, (lang, marker)


def test_b9c_L5_language_selector_offers_all_four_equally():
    html = _read("index.html")
    for lang, label in (("en", "English"), ("es", "Español"), ("pt", "Português"),
                        ("ht", "Kreyòl")):
        assert re.search(rf'data-lang-choice="{lang}" lang="{lang}" aria-pressed="(true|false)">'
                         rf"{label}</button>", html), lang


def test_b9c_S1_client_stores_only_language_and_optional_username():
    js = _read("login.js")
    keys = set(re.findall(r'(?:LANG_KEY|USER_KEY) = "([a-z_]+)"', js))
    assert keys == {"mq_crm_lang", "mq_crm_remembered_username"}
    assert re.findall(r"store\.set\((\w+)", js) and \
        set(re.findall(r"store\.set\((\w+)", js)) <= {"LANG_KEY", "USER_KEY"}
    assert "sessionStorage" not in js and "document.cookie" not in js
    # the only localStorage writes go through store.set with those two keys
    assert js.count("localStorage.setItem(") == 1
    for js_name in ("login.js", "app.js"):
        src = _read(js_name)
        assert not re.search(r"setItem\([^)]*(password|token|challenge|code)", src, re.I), js_name


def test_b9c_S2_client_never_sends_x_role_and_uses_existing_endpoints():
    js = _read("login.js")
    assert "X-Role" not in js and "x-role" not in js.lower()
    paths = set(re.findall(r'"(/api/[a-z/_-]+)"', js))
    # 2026-11-18 first-run bootstrap fix: the sign-in client also uses
    # /api/auth/bootstrap (status check + one-time owner creation).
    assert paths == {"/api/auth/login", "/api/auth/login/verify",
                     "/api/auth/bootstrap"}
    assert 'mode: "cookie"' in js and "Authorization" not in js
    assert "console." not in js                       # nothing logged


def test_b9c_S3_no_secrets_or_credentials_in_web_assets():
    pat = re.compile(r"(Tp-[A-Za-z0-9]{20}|Synthetic-[A-Za-z0-9_-]{20,}|BEGIN [A-Z ]*PRIVATE KEY|"
                     r"otpauth://|\b[A-Z2-7]{32}\b|api[_-]?key\s*[:=])")
    for name in ("index.html", "login.js", "login.css", "login_i18n.js", "app.js", "styles.css"):
        assert not pat.search(_read(name)), name


def test_b9c_R1_login_payload_has_no_remember_or_duration_field():
    js = _read("login.js")
    body = re.search(r'postJSON\("/api/auth/login", (\{[^}]*\})\)', js).group(1)
    assert re.findall(r"(\w+):", body) == ["username", "password", "mode"]


def test_b9c_R2_extra_remember_field_cannot_extend_the_session():
    pw = "Synthetic-" + secrets.token_urlsafe(18)
    u = auth.create_user(main_mod.conn, f"b9c-{secrets.token_hex(4)}", pw, "staff",
                         "Synthetic staff", "b9c-setup", "system")
    c = anonymous_client(main_mod.app, base_url="https://testserver",
                         client=("192.0.2.209", 41009))   # address used by no other test: no shared IP lock
    before = datetime.now(timezone.utc)
    r = c.post("/api/auth/login", json={"username": u["username"], "password": pw,
                                        "mode": "cookie", "remember": True,
                                        "remember_me": True, "days": 30})
    assert r.status_code == 200, r.text
    cookie = r.headers["set-cookie"].lower()
    # the cookie lifetime is the server's 12 h cap, whatever the client sends
    assert re.search(r"max-age=(\d+)", cookie).group(1) == str(auth.ABSOLUTE_HOURS * 3600)
    me = c.get("/api/auth/me").json()
    assert me["session"]["idle_minutes"] == auth.IDLE_MINUTES == 30
    absolute = datetime.fromisoformat(me["session"]["absolute_expires_at"].replace("Z", "+00:00"))
    assert (absolute - before).total_seconds() <= auth.ABSOLUTE_HOURS * 3600 + 5
    assert auth.ABSOLUTE_HOURS == 12


def test_b9c_A1_assets_served_and_old_login_markup_gone():
    c = anonymous_client(main_mod.app)
    for path in ("/", "/login.js", "/login.css", "/login_i18n.js", "/styles.css"):
        assert c.get(path).status_code == 200, path
    html = _read("index.html")
    assert 'id="login-view"' in html and 'id="login-panel"' not in html
    assert html.index("login_i18n.js") < html.index("app.js") < html.index("login.js")
    assert html.index("safe_html.js") < html.index("app.js")
    for needle in ('role="alert" aria-live="assertive"', 'aria-controls="login-password"',
                   'for="login-username"', 'for="login-password"', 'for="totp-code"'):
        assert needle in html, needle
    assert "cdn" not in html.lower() and "https://" not in html   # no remote fonts/scripts


def test_b9c_A2_open_paths_unchanged_and_forged_role_still_ignored():
    # 2026-11-18: /api/auth/bootstrap added by the founder-ordered
    # first-run bootstrap fix (open only while no owner exists).
    assert main_mod.OPEN_PATHS == {"/api/health", "/api/auth/login",
                                   "/api/auth/login/verify",
                                   "/api/auth/bootstrap"}
    c = anonymous_client(main_mod.app)
    for h in ({"X-Role": "owner"}, {"X-Role": "owner", "X-Actor": "op"}):
        assert c.get("/api/customers", headers=h).status_code == 401
        assert c.get("/api/users", headers=h).status_code == 401
