"""Batch 009d: black-and-gold dashboard shell + Overview (presentation only).

D  dashboard.js only READS existing endpoints through app.js api() (no fetch,
   no writes, no innerHTML); pipeline / forecast / deal size are shown as
   "not tracked" and never fetched or computed
I  dashboard strings and app.js STRINGS (incl. the translated dynamic lists)
   have the same non-empty keys and placeholders in EN / ES / PT / HT; every
   key the page uses exists; no English left in ES / PT / HT
R  every endpoint the Overview reads is readable by a viewer and still
   write-protected; the forged X-Role header is still ignored
A  assets served, script order, the old tabs still exist
"""
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile

import pytest

os.environ.setdefault("MQ_CRM_DB", os.path.join(tempfile.mkdtemp(), "b9d.db"))

from app import auth  # noqa: E402
from app import main as main_mod  # noqa: E402
from tests.conftest import anonymous_client  # noqa: E402

WEB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web"))
LANGS = ("en", "es", "pt", "ht")
OVERVIEW_READS = {"/api/reports/summary", "/api/customers", "/api/bookings",
                  "/api/invoices", "/api/messages", "/api/quotes"}

DUMP = r"""
const vm = require("vm"), fs = require("fs"), path = require("path");
const web = process.argv[2];
const stub = () => new Proxy(function () {}, {get: (t, k) => k === Symbol.toPrimitive ? () => "" :
  (k === "dataset" ? {} : (k === "classList" ? {toggle() {}, add() {}, remove() {}} : stub())),
  set: () => true, apply: () => stub()});
const ctx = {console, document: {querySelector: () => stub(), querySelectorAll: () => [],
  getElementById: () => null, documentElement: {}}, fetch: async () => ({ok: true, json: async () => ({})}),
  localStorage: {getItem() { return null; }, setItem() {}, removeItem() {}}, Intl};
ctx.window = ctx; ctx.globalThis = ctx;
vm.createContext(ctx);
for (const f of ["safe_html.js", "app.js", "dashboard.js"])
  vm.runInContext(fs.readFileSync(path.join(web, f), "utf8"), ctx, {filename: f});
console.log(JSON.stringify({app: vm.runInContext("STRINGS", ctx), dash: vm.runInContext("MQDash.T", ctx)}));
"""


def _read(name):
    with open(os.path.join(WEB, name), encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def dicts(tmp_path_factory):
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    h = tmp_path_factory.mktemp("b9d") / "dump.js"
    h.write_text(DUMP)
    r = subprocess.run([node, str(h), WEB], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _same_keys(d, name):
    base = set(d["en"])
    for lang in LANGS:
        assert set(d[lang]) == base, (name, lang, sorted(base ^ set(d[lang])))
        assert not [k for k, v in d[lang].items() if not str(v).strip()], (name, lang)
        for k, v in d["en"].items():
            assert sorted(re.findall(r"\{[a-z]+\}", d[lang][k])) == \
                sorted(re.findall(r"\{[a-z]+\}", v)), (name, lang, k)


def test_b9d_D1_dashboard_only_reads_existing_endpoints_via_api():
    js = _read("dashboard.js")
    assert set(re.findall(r'api\("(/api/[a-z/_-]+)"\)', js)) == OVERVIEW_READS
    assert "fetch(" not in js and "post(" not in js and "method" not in js
    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert sink not in js, sink
    assert "X-Role" not in js and "localStorage" not in js and "sessionStorage" not in js


def test_b9d_D2_untracked_metrics_are_honest_empty_states():
    html = _read("index.html")
    nt = html[html.index('class="nt-list"'):html.index("</ul>", html.index('class="nt-list"'))]
    for key in ("nt_pipeline", "nt_forecast", "nt_deal"):
        assert f'data-dash-i18n="{key}"' in nt
    assert nt.count("—") == 3
    js = _read("dashboard.js")
    assert not re.search(r"api\([^)]*(pipeline|forecast|deal)", js, re.I)
    # no hard-coded money or KPI figures in the page or script
    assert not re.search(r"\$\s?\d|\d{1,3},\d{3}(\.\d\d)?", html + js)


def test_b9d_I1_dashboard_strings_complete_in_four_languages(dicts):
    _same_keys(dicts["dash"], "dashboard")
    html = _read("index.html")
    used = set(re.findall(r'data-dash-i18n(?:-title)?="([a-z_]+)"', html))
    used |= set(re.findall(r'\bt\("([a-z_]+)"', _read("dashboard.js")))
    assert not sorted(k for k in used if k not in dicts["dash"]["en"])


def test_b9d_I2_app_strings_incl_dynamic_lists_complete_in_four_languages(dicts):
    _same_keys(dicts["app"], "app")
    html, js = _read("index.html"), _read("app.js")
    used = set(re.findall(r'data-i18n="([a-z_]+)"', html))
    used |= set(re.findall(r'\btt\("([a-z_]+)"', js))
    used -= {"st_", "by_"}                                 # tt("st_" + status), tt("by_" + author)
    assert not sorted(k for k in used if k not in dicts["app"]["en"])


def test_b9d_I3_no_english_left_in_es_pt_ht(dicts):
    allow = {"—", "Total", "Email", "Marketing"}
    for name in ("dash", "app"):
        d = dicts[name]
        for lang in ("es", "pt", "ht"):
            same = [k for k, v in d["en"].items() if d[lang][k] == v and v not in allow]
            assert not same, (name, lang, same)


def test_b9d_I4_no_hardcoded_english_left_in_list_renderers():
    js = "\n".join(l for l in _read("app.js").splitlines()
                   if not l.startswith(("Object.assign(STRINGS.", "  en: {")))
    for s in ("No reminders due", ">Cancel<", "Quote #", "Invoice #", "Paid: ", ">Mark sent<",
              ">Accept<", ">Withdraw<", "held for review", "last service:", '"Saved."',
              '"Lapsed"', '"Avg rating"', "Classify: "):
        assert s not in js, s


def _viewer():
    pw = "Synthetic-" + secrets.token_urlsafe(18)
    u = auth.create_user(main_mod.conn, f"b9d-{secrets.token_hex(4)}", pw, "viewer",
                         "Synthetic viewer", "b9d-setup", "system")
    c = anonymous_client(main_mod.app, base_url="https://testserver", client=("192.0.2.214", 41014))
    r = c.post("/api/auth/login", json={"username": u["username"], "password": pw, "mode": "token"})
    assert r.status_code == 200, r.text
    return c, {"Authorization": "Bearer " + r.json()["token"]}


def test_b9d_R1_viewer_can_read_overview_sources_but_not_write():
    c, h = _viewer()
    for p in sorted(OVERVIEW_READS):
        assert c.get(p, headers=h).status_code == 200, p
    assert c.post("/api/customers", headers=h, json={"name": "Synthetic X"}).status_code == 403
    assert c.post("/api/quotes?customer_id=1", headers=h).status_code == 403
    for p in sorted(OVERVIEW_READS):          # deny by default without a session
        assert anonymous_client(main_mod.app).get(p, headers={"X-Role": "owner"}).status_code == 401, p


def test_b9d_A1_assets_served_script_order_and_tabs_kept():
    c = anonymous_client(main_mod.app)
    for p in ("/dashboard.js", "/dashboard.css"):
        assert c.get(p).status_code == 200, p
    html = _read("index.html")
    order = [html.index(s) for s in ("safe_html.js", "login_i18n.js", "app.js", "login.js", "dashboard.js")]
    assert order == sorted(order)
    for tab in ("overview", "customers", "bookings", "billing", "messages", "comeback", "reports"):
        assert f'data-tab="{tab}"' in html and f'id="tab-{tab}"' in html, tab
    assert "https://" not in html and "cdn" not in html.lower()
