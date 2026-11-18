/* M&Q CRM: sign-in screen (Batch 009c, presentation only).

   Uses the EXISTING auth contract unchanged:
     POST /api/auth/login        {username, password, mode: "cookie"}
     POST /api/auth/login/verify {challenge, code | recovery_code}
   The session is the server's HttpOnly cookie; the CSRF token goes to
   app.js (setSignedIn). Nothing here decides a role or a permission.

   Stored in this browser (localStorage), and nothing else:
     mq_crm_lang                 the chosen language (en | es | pt | ht)
     mq_crm_remembered_username  ONLY when "Remember me" is ticked
   No password, token, challenge or code is ever stored or logged.
   "Remember me" does not change session length (30 min idle / 12 h). */
(function () {
  "use strict";
  const S = window.LOGIN_STRINGS;
  const LANGS = ["en", "es", "pt", "ht"];
  const LANG_KEY = "mq_crm_lang";
  const USER_KEY = "mq_crm_remembered_username";
  const store = {
    get(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { window.localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
    del(k) { try { window.localStorage.removeItem(k); } catch (e) { /* private mode */ } },
  };
  const $id = (id) => document.getElementById(id);
  const saved = store.get(LANG_KEY);
  let cur = LANGS.indexOf(saved) >= 0 ? saved : "en";
  let challenge = null;          // pending two-step challenge (memory only)
  let recovery = false;          // TOTP step: recovery-code mode
  let signedInUser = null;
  const errs = {};               // target -> [key, vars]; re-rendered on language change
  let notice = null;

  function t(key, vars) {
    let s = (S[cur] && S[cur][key]) || S.en[key] || key;
    if (vars) Object.keys(vars).forEach((k) => { s = s.split("{" + k + "}").join(String(vars[k])); });
    return s;
  }

  // ------------------------------------------------------------ rendering
  function render() {
    document.documentElement.lang = cur;
    document.title = t("page_title");
    document.querySelectorAll("[data-li18n]").forEach((el) => { el.textContent = t(el.dataset.li18n); });
    document.querySelectorAll("[data-li18n-title]").forEach((el) => { el.title = t(el.dataset.li18nTitle); });
    document.querySelectorAll("[data-lang-choice]").forEach((b) => {
      const on = b.dataset.langChoice === cur;
      b.setAttribute("aria-pressed", on ? "true" : "false");
      b.classList.toggle("active", on);
    });
    renderPwToggle();
    renderTotpMode();
    const https = window.location.protocol === "https:";
    $id("secure-title").textContent = t(https ? "secure_https" : "secure_http");
    $id("secure-indicator").classList.toggle("is-local", !https);
    Object.keys(errs).forEach(showErr);
    renderNotice();
    renderWhoami();
  }

  function setLang(l) {
    if (LANGS.indexOf(l) < 0) return;
    cur = l;
    store.set(LANG_KEY, l);
    if (typeof lang !== "undefined") lang = l;              // app.js dashboard language
    if (typeof applyLang === "function") applyLang();
    render();
  }

  function renderWhoami() {
    const w = $id("whoami");
    if (!w) return;
    w.textContent = signedInUser
      ? t("signed_in_as", {name: signedInUser.display_name || signedInUser.username,
                           role: t("role_" + signedInUser.role)})
      : t("not_signed_in");
  }

  // ------------------------------------------------------------ errors / notices
  const ERR_EL = {form: "login-error", username: "username-error", password: "password-error",
                  totp: "totp-error", setup: "setup-error"};
  const ERR_INPUT = {username: "login-username", password: "login-password", totp: "totp-code"};
  function setErr(target, key, vars) {
    if (key) errs[target] = [key, vars || null]; else delete errs[target];
    showErr(target);
  }
  function showErr(target) {
    const el = $id(ERR_EL[target]);
    const e = errs[target];
    el.textContent = e ? t(e[0], e[1]) : "";
    el.hidden = !e;
    if (ERR_INPUT[target]) {
      const inp = $id(ERR_INPUT[target]);
      if (e) inp.setAttribute("aria-invalid", "true"); else inp.removeAttribute("aria-invalid");
    }
  }
  function clearErrs() { Object.keys(ERR_EL).forEach((k) => setErr(k, null)); }
  function setNotice(key) { notice = key; renderNotice(); }
  function renderNotice() {
    const n = $id("login-notice");
    n.textContent = notice ? t(notice) : "";
    n.hidden = !notice;
  }

  function errorFor(r, body, step) {
    if (r.status === 429) {
      const s = parseInt(r.headers.get("Retry-After") || "0", 10);
      return s > 0 ? ["err_locked", {minutes: Math.max(1, Math.ceil(s / 60))}] : ["err_locked_generic"];
    }
    if (r.status === 503) return ["err_two_step_unavailable"];
    if (r.status === 401 && step === "login") return ["err_invalid_credentials"];
    if (r.status === 403 && step === "setup") return ["err_setup_taken"];
    if (r.status === 400 && step === "setup") return ["err_setup_failed"];
    if (r.status === 401 && step === "totp")
      return (body && (body.detail_en || body.detail) === "invalid code") ? ["err_code_invalid"] : ["err_challenge_expired"];
    if (r.status >= 500) return ["err_server"];
    return ["err_generic"];
  }

  // ------------------------------------------------------------ views
  function show(view) {          // "login" | "totp" | "forgot" | "setup"
    $id("login-form").hidden = view !== "login";
    $id("setup-form").hidden = view !== "setup";
    $id("totp-form").hidden = view !== "totp";
    $id("forgot-panel").hidden = view !== "forgot";
  }
  function busy(btnId, on, labelKey) {
    const b = $id(btnId);
    b.disabled = on;
    b.setAttribute("aria-busy", on ? "true" : "false");
    b.querySelector("span").textContent = t(labelKey);
    b.querySelector("span").dataset.li18n = labelKey;
  }

  function renderPwToggle() {
    const inp = $id("login-password"), b = $id("pw-toggle");
    const visible = inp.type === "text";
    b.setAttribute("aria-pressed", visible ? "true" : "false");
    b.setAttribute("aria-label", t(visible ? "hide_password" : "show_password"));
    $id("pw-toggle-text").textContent = t(visible ? "hide" : "show");
  }
  function renderTotpMode() {
    const inp = $id("totp-code");
    $id("totp-intro").textContent = t(recovery ? "recovery_intro" : "totp_intro");
    $id("totp-label").textContent = t(recovery ? "recovery_label" : "totp_code_label");
    $id("totp-switch").textContent = t(recovery ? "totp_use_app" : "totp_use_recovery");
    inp.setAttribute("inputmode", recovery ? "text" : "numeric");
    inp.setAttribute("autocomplete", recovery ? "off" : "one-time-code");
    inp.setAttribute("maxlength", recovery ? "24" : "7");
    inp.setAttribute("placeholder", recovery ? "xxxx-xxxx-xxxx-xxxx" : "000000");
  }

  // ------------------------------------------------------------ actions
  async function postJSON(path, body) {
    const r = await fetch(path, {method: "POST", credentials: "same-origin",
                                 headers: {"Content-Type": "application/json"},
                                 body: JSON.stringify(body)});
    let data = null;
    try { data = await r.json(); } catch (e) { data = null; }
    return [r, data];
  }

  function finish(data) {
    challenge = null;
    clearErrs(); setNotice(null);
    $id("totp-code").value = "";
    show("login");
    if (typeof setSignedIn === "function") setSignedIn(data.user, data.csrf_token);
    if (typeof refreshSelects === "function") refreshSelects();
  }

  async function onLogin(e) {
    e.preventDefault();
    clearErrs(); setNotice(null);
    const uEl = $id("login-username"), pEl = $id("login-password");
    const u = uEl.value.trim(), p = pEl.value;
    if (!u) setErr("username", "err_username_required");
    if (!p) setErr("password", "err_password_required");
    if (!u || !p) { (u ? pEl : uEl).focus(); return; }
    if ($id("remember-me").checked) store.set(USER_KEY, u); else store.del(USER_KEY);
    busy("sign-in-btn", true, "signing_in");
    let r, data;
    try {
      [r, data] = await postJSON("/api/auth/login", {username: u, password: p, mode: "cookie"});
    } catch (err) {
      setErr("form", "err_network");
      return;
    } finally {
      pEl.value = "";
      pEl.type = "password"; renderPwToggle();
      busy("sign-in-btn", false, "sign_in");
    }
    if (r.ok && data && data.two_step_required) {
      challenge = data.challenge;
      recovery = false; renderTotpMode();
      show("totp");
      $id("totp-code").focus();
      return;
    }
    if (r.ok && data) { finish(data); return; }
    const [k, v] = errorFor(r, data, "login");
    setErr("form", k, v);
    pEl.focus();
  }

  async function onVerify(e) {
    e.preventDefault();
    setErr("totp", null);
    const raw = $id("totp-code").value.trim();
    let body;
    if (recovery) {
      const norm = raw.toLowerCase().replace(/[\s-]/g, "");
      if (!norm) { setErr("totp", "err_recovery_required"); $id("totp-code").focus(); return; }
      if (!/^[a-z2-7]{16}$/.test(norm)) { setErr("totp", "err_recovery_format"); $id("totp-code").focus(); return; }
      body = {challenge, recovery_code: norm};
    } else {
      const digits = raw.replace(/\s/g, "");
      if (!digits) { setErr("totp", "err_code_required"); $id("totp-code").focus(); return; }
      if (!/^\d{6}$/.test(digits)) { setErr("totp", "err_code_format"); $id("totp-code").focus(); return; }
      body = {challenge, code: digits};
    }
    busy("verify-btn", true, "verifying");
    let r, data;
    try {
      [r, data] = await postJSON("/api/auth/login/verify", body);
    } catch (err) {
      setErr("totp", "err_network");
      return;
    } finally {
      $id("totp-code").value = "";
      busy("verify-btn", false, "verify");
    }
    if (r.ok && data) { finish(data); return; }
    const [k, v] = errorFor(r, data, "totp");
    if (k === "err_challenge_expired") { backToLogin(); setErr("form", k); return; }
    setErr("totp", k, v);
    $id("totp-code").focus();
  }

  // ------------------------------------------------------------ first-run setup
  // A fresh install has NO account, so the sign-in form alone would be
  // a dead end. Ask the server (GET /api/auth/bootstrap): if no owner
  // exists, show the one-time owner-creation form instead. Once an
  // owner exists the server refuses creation and this never shows.
  let needsBootstrap = false;

  async function checkBootstrap() {
    let data = null;
    try {
      const r = await fetch("/api/auth/bootstrap", {credentials: "same-origin"});
      if (r.ok) data = await r.json();
    } catch (e) { data = null; }
    needsBootstrap = !!(data && data.owner_exists === false);
    if (needsBootstrap && !signedInUser) {
      show("setup");
      $id("setup-username").focus();
    }
  }

  async function onSetup(e) {
    e.preventDefault();
    setErr("setup", null); setNotice(null);
    const u = $id("setup-username").value.trim();
    const p = $id("setup-password").value;
    if (!u) { setErr("setup", "err_username_required"); $id("setup-username").focus(); return; }
    if (!p) { setErr("setup", "err_password_required"); $id("setup-password").focus(); return; }
    if (p !== $id("setup-confirm").value) {
      setErr("setup", "err_password_mismatch");
      $id("setup-confirm").focus();
      return;
    }
    busy("setup-btn", true, "setup_creating");
    let r, data;
    try {
      [r, data] = await postJSON("/api/auth/bootstrap", {username: u, password: p, mode: "cookie"});
    } catch (err) {
      setErr("setup", "err_network");
      return;
    } finally {
      $id("setup-password").value = "";
      $id("setup-confirm").value = "";
      busy("setup-btn", false, "setup_create");
    }
    if (r.ok && data) { needsBootstrap = false; finish(data); return; }
    const [k, v] = errorFor(r, data, "setup");
    if (k === "err_setup_taken") needsBootstrap = false;
    setErr("setup", k, v);
  }

  function backToLogin() {
    challenge = null;
    recovery = false;
    setErr("totp", null);
    $id("totp-code").value = "";
    show("login");
    $id("login-password").focus();
  }

  // ------------------------------------------------------------ hooks for app.js
  window.MQLogin = {
    t,
    onSignedIn(user) {
      signedInUser = user;
      document.body.classList.remove("signed-out", "booting");
      renderWhoami();
    },
    onSignedOut(reason) {
      const wasIn = !!signedInUser;
      signedInUser = null;
      document.body.classList.add("signed-out");
      document.body.classList.remove("booting");
      show(needsBootstrap ? "setup" : "login");
      clearErrs();
      setNotice(reason === "session_ended" ? "session_ended" : (reason === "logout" ? "signed_out" : null));
      renderWhoami();
      const remembered = store.get(USER_KEY);
      if (remembered && !$id("login-username").value) {
        $id("login-username").value = remembered;
        $id("remember-me").checked = true;
      }
      if (!wasIn || reason) ($id("login-username").value ? $id("login-password") : $id("login-username")).focus();
    },
  };

  // ------------------------------------------------------------ wiring
  document.querySelectorAll("[data-lang-choice]").forEach((b) => {
    b.addEventListener("click", () => setLang(b.dataset.langChoice));
  });
  LANGS.forEach((l) => { const b = $id("lang-" + l); if (b) b.onclick = () => setLang(l); });
  $id("pw-toggle").addEventListener("click", () => {
    const inp = $id("login-password");
    inp.type = inp.type === "password" ? "text" : "password";
    renderPwToggle();
    inp.focus();
  });
  $id("login-form").addEventListener("submit", onLogin);
  $id("setup-form").addEventListener("submit", onSetup);
  $id("totp-form").addEventListener("submit", onVerify);
  $id("totp-switch").addEventListener("click", () => {
    recovery = !recovery; setErr("totp", null); $id("totp-code").value = "";
    renderTotpMode(); $id("totp-code").focus();
  });
  $id("totp-back").addEventListener("click", backToLogin);
  $id("forgot-link").addEventListener("click", () => { show("forgot"); $id("forgot-title").focus(); });
  $id("forgot-back").addEventListener("click", () => { show("login"); $id("forgot-link").focus(); });
  $id("remember-me").addEventListener("change", (e) => { if (!e.target.checked) store.del(USER_KEY); });

  if (typeof lang !== "undefined") lang = cur;
  if (typeof applyLang === "function") applyLang();
  render();
  checkBootstrap();
})();
