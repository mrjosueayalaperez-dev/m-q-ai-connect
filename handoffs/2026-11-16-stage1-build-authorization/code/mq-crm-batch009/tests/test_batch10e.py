"""Batch 010e: Overview sales funnel (presentation only).

S  the funnel is computed only from lists the Overview already reads
   (customers, quotes, invoices) through app.js api(); no new request, no
   write, no invented metric; pipeline / forecast / deal size stay "—"
M  the math, run in node against the real dashboard.js: counts per tier,
   primary-currency amounts, conversion %, zero denominators -> null ("—"),
   never NaN / Infinity / a fake 0%
E  end to end: the API data a viewer can read gives the expected funnel
L  every funnel string exists in EN / ES / PT / HT
"""
import json
import os
import re
import shutil
import subprocess
import tempfile

import pytest

os.environ.setdefault("MQ_CRM_DB", os.path.join(tempfile.mkdtemp(), "b10e.db"))

from fastapi.testclient import TestClient  # noqa: E402

from app import main as main_mod  # noqa: E402
from tests.conftest import auth_headers  # noqa: E402

WEB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web"))
FUNNEL_KEYS = ["funnel_title", "f_customers", "f_sent", "f_accepted", "f_invoiced",
               "f_paid", "f_of_customers", "f_of_prev", "f_conv", "f_count",
               "f_amount", "f_tier", "funnel_note"]

RUN = r"""
const vm = require("vm"), fs = require("fs"), path = require("path");
const web = process.argv[2], cases = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const stub = () => new Proxy(function () {}, {get: (t, k) => k === Symbol.toPrimitive ? () => "" :
  (k === "dataset" ? {} : (k === "classList" ? {toggle() {}, add() {}, remove() {}} : stub())),
  set: () => true, apply: () => stub()});
const ctx = {console, document: {querySelector: () => stub(), querySelectorAll: () => [],
  getElementById: () => null, documentElement: {}}, fetch: async () => { throw new Error("no fetch"); },
  localStorage: {getItem() { return null; }, setItem() {}, removeItem() {}}, Intl};
ctx.window = ctx; ctx.globalThis = ctx;
vm.createContext(ctx);
for (const f of ["safe_html.js", "app.js", "dashboard.js"])
  vm.runInContext(fs.readFileSync(path.join(web, f), "utf8"), ctx, {filename: f});
const out = cases.map((c) => JSON.parse(JSON.stringify(ctx.MQDash.funnel(c.raw, c.primary),
  (k, v) => (typeof v === "number" && !isFinite(v) ? "NONFINITE" : v))));
console.log(JSON.stringify(out));
"""


def _funnel(cases):
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    d = tempfile.mkdtemp()
    js, data = os.path.join(d, "run.js"), os.path.join(d, "cases.json")
    open(js, "w").write(RUN)
    open(data, "w").write(json.dumps(cases))
    out = subprocess.run([node, js, WEB, data], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _tiers(f):
    return [(t["key"], t["count"], t["amount"], t["conv"]) for t in f["tiers"]]


def _q(cid, status, total, cur="USD"):
    return {"customer_id": cid, "status": status, "total_minor": total, "currency": cur}


def _i(cid, status, total, cur="USD"):
    return {"customer_id": cid, "status": status, "total_minor": total, "currency": cur}


# ---------------------------------------------------------------- M: math

def test_counts_amounts_and_conversion():
    raw = {"customers": [{"id": i} for i in range(1, 11)],          # 10 customers
           "quotes": [_q(1, "draft", 999), _q(1, "sent", 10000), _q(2, "sent", 5000),
                      _q(3, "declined", 2000), _q(4, "accepted", 3000),
                      _q(5, "converted", 4000), _q(5, "converted", 1000)],
           "invoices": [_i(5, "paid", 4000), _i(5, "open", 1000)]}
    f = _funnel([{"raw": raw, "primary": "USD"}])[0]
    assert f["primary"] == "USD"
    assert _tiers(f) == [
        ("f_customers", 10, None, None),
        # past draft: 2 sent + declined + accepted + 2 converted = 6; draft excluded
        ("f_sent", 6, 25000, 0.5),            # customers 1-5 quoted / 10 customers
        ("f_accepted", 3, 8000, 0.5),          # accepted + 2 converted, of 6 sent
        ("f_invoiced", 2, 5000, 2 / 3),        # 2 invoices of 3 accepted
        ("f_paid", 1, 4000, 0.5),              # 1 paid of 2 invoiced
    ]


def test_empty_crm_is_all_dashes_never_nan_or_zero_percent():
    f = _funnel([{"raw": {"customers": [], "quotes": [], "invoices": []}, "primary": "USD"}])[0]
    assert _tiers(f) == [("f_customers", 0, None, None), ("f_sent", 0, 0, None),
                         ("f_accepted", 0, 0, None), ("f_invoiced", 0, 0, None),
                         ("f_paid", 0, 0, None)]
    assert "NONFINITE" not in json.dumps(f)


def test_zero_denominators_mid_funnel():
    raw = {"customers": [{"id": 1}, {"id": 2}],
           "quotes": [_q(1, "draft", 500)], "invoices": []}
    f = _funnel([{"raw": raw, "primary": "USD"}])[0]
    conv = [t["conv"] for t in f["tiers"]]
    # 0 of 2 customers quoted is a REAL 0% (denominator 2); below that there is
    # nothing to divide by, so null ("—"), not 0%.
    assert conv == [None, 0, None, None, None]


def test_missing_lists_do_not_crash():
    f = _funnel([{"raw": {}, "primary": "USD"}])[0]
    assert [t["count"] for t in f["tiers"]] == [0, 0, 0, 0, 0]


def test_amounts_use_primary_currency_only_counts_use_all():
    raw = {"customers": [{"id": 1}, {"id": 2}],
           "quotes": [_q(1, "sent", 10000, "USD"), _q(2, "sent", 7000, "EUR")],
           "invoices": [_i(1, "paid", 3000, "USD"), _i(2, "paid", 9000, "EUR")]}
    f = _funnel([{"raw": raw, "primary": "USD"}])[0]
    t = {x["key"]: x for x in f["tiers"]}
    assert t["f_sent"]["count"] == 2 and t["f_sent"]["amount"] == 10000
    assert t["f_paid"]["count"] == 2 and t["f_paid"]["amount"] == 3000


def test_quote_conversion_counts_distinct_customers():
    raw = {"customers": [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}],
           "quotes": [_q(1, "sent", 1), _q(1, "sent", 1), _q(1, "accepted", 1)],
           "invoices": []}
    f = _funnel([{"raw": raw, "primary": "USD"}])[0]
    assert f["tiers"][1]["count"] == 3 and f["tiers"][1]["conv"] == 0.25


# ---------------------------------------------------------------- S: source

def _read(name):
    with open(os.path.join(WEB, name), encoding="utf-8") as f:
        return f.read()


def test_funnel_uses_only_loaded_lists_no_new_requests():
    js = _read("dashboard.js")
    body = js[js.index("function funnel("):js.index("  // ---------------------------------------------------------------- render")]
    assert "api(" not in body and "fetch" not in body and "XMLHttpRequest" not in body
    assert "innerHTML" not in body and "insertAdjacentHTML" not in body
    for banned in ("pipeline", "forecast", "deal", "Math.random", "estimate"):
        assert banned not in body.lower().replace("pipeline value", ""), banned
    # no hardcoded figures inside the funnel code
    assert not re.search(r"\b\d{3,}\b", body)
    # every request the Overview makes is still one of the six reads
    reqs = set(re.findall(r'api\("([^"]+)"\)', js))
    assert reqs == {"/api/reports/summary", "/api/customers", "/api/bookings",
                    "/api/invoices", "/api/messages", "/api/quotes"}


def test_page_has_funnel_panel_and_not_tracked_dashes():
    html = _read("index.html")
    assert 'id="chart-funnel"' in html and 'data-dash-i18n="funnel_title"' in html
    nt = html[html.index('class="panel half nt"'):]
    assert nt.count('<strong aria-hidden="true">—</strong>') == 3
    # the funnel panel sits before the not-tracked panel (lower-left)
    assert html.index('id="chart-funnel"') < html.index('class="panel half nt"')
    css = _read("dashboard.css")
    assert "clip-path" in css and "http" not in css.replace("http-equiv", "")


def test_funnel_strings_in_four_languages():
    js = _read("dashboard.js")
    for k in FUNNEL_KEYS:
        assert len(re.findall(r"\b" + k + r": \"", js)) == 4, k


# ---------------------------------------------------------------- E: end to end

def test_viewer_reads_feed_the_expected_funnel():
    owner = TestClient(main_mod.app)
    cids = [owner.post("/api/customers", json={"name": f"Syn F{i}", "phone": f"32155592{i:02d}"}
                       ).json()["customer"]["id"] for i in range(3)]
    qa = owner.post(f"/api/quotes?customer_id={cids[0]}").json()["id"]
    owner.post(f"/api/quotes/{qa}/items", json={"description": "Syn", "qty": 2, "unit_amount_minor": 1500})
    qb = owner.post(f"/api/quotes?customer_id={cids[1]}").json()["id"]
    owner.post(f"/api/quotes/{qb}/items", json={"description": "Syn", "qty": 1, "unit_amount_minor": 700})
    for qid, st in ((qa, "sent"), (qa, "accepted"), (qb, "sent")):
        assert owner.post(f"/api/quotes/{qid}/status?status={st}").status_code == 200
    inv = owner.post(f"/api/quotes/{qa}/invoice").json()
    assert owner.post(f"/api/invoices/{inv['id']}/payments", json={"amount_minor": 3000}).status_code == 200

    viewer = TestClient(main_mod.app, headers=auth_headers("viewer"))
    raw = {k: viewer.get(f"/api/{k}").json() for k in ("customers", "quotes", "invoices")}
    assert all(isinstance(v, list) for v in raw.values())
    f = _funnel([{"raw": raw, "primary": "USD"}])[0]
    t = {x["key"]: x for x in f["tiers"]}
    mine = {"customers": len(raw["customers"])}
    assert t["f_customers"]["count"] == mine["customers"]
    assert t["f_sent"]["count"] >= 2 and t["f_accepted"]["count"] >= 1
    assert t["f_paid"]["count"] >= 1 and t["f_paid"]["amount"] >= 3000
    # viewer stays read-only
    assert viewer.post(f"/api/quotes?customer_id={cids[2]}").status_code == 403


def test_funnel_is_one_continuous_cone_css_only():
    """3D look (Josue 7:27 PM): five segments of ONE tapering cone, each with an
    elliptical rim; each tier's bottom width equals the next tier's top width."""
    css = open(os.path.join(WEB, "dashboard.css"), encoding="utf-8").read()
    js = open(os.path.join(WEB, "dashboard.js"), encoding="utf-8").read()
    assert 'class: "f-seg f-seg-" + i' in js and 'class: "f-tier f-tier-" + i' in js
    polys = {}
    for i in range(5):
        m = re.search(r"\.f-tier-%d \{ clip-path: polygon\(([^)]*)\)" % i, css)
        assert m, i
        pts = [p.split()[0] for p in m.group(1).split(",")]
        polys[i] = (pts[0], pts[3])  # top-left x, bottom-left x
    for i in range(4):
        assert polys[i][1] == polys[i + 1][0], (i, polys)          # continuous taper
    assert polys[0][0] in ("0%", "0") and polys[4][1] == "35%"
    for i in range(1, 5):                                           # rim sits on the tier's top edge
        assert re.search(r"\.f-seg-%d \{ --l: %s;" % (i, re.escape(polys[i][0])), css), i
    assert "border-radius: 50%" in css and "url(" not in css.split("sales funnel")[1].split("@media")[0]
