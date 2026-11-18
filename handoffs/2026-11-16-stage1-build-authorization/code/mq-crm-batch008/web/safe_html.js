/* Batch 008 — safe HTML rendering for the operator UI.
 *
 * Customer names, message text (including attacker-controlled INBOUND
 * text), translations, titles and every other server value are DATA, never
 * markup. All dynamic HTML is built with the `html` tagged template: every
 * interpolated value is HTML-escaped unless it is itself the result of
 * `html` (nested fragments) — arrays are rendered element by element under
 * the same rule. `setHTML(el, fragment)` is the ONLY place innerHTML is
 * written, and it refuses anything that is not an `html` fragment.
 */
(function (root) {
  const ESC = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;", "`": "&#96;"};
  function esc(v) {
    if (v === null || v === undefined) return "";
    return String(v).replace(/[&<>"'`]/g, (c) => ESC[c]);
  }
  class SafeHTML {
    constructor(s) { this.s = s; }
    toString() { return this.s; }
  }
  function part(v) {
    if (v instanceof SafeHTML) return v.s;
    if (Array.isArray(v)) return v.map(part).join("");
    if (v === false || v === null || v === undefined) return "";
    return esc(v);
  }
  function html(strings, ...values) {
    let out = strings[0];
    values.forEach((v, i) => { out += part(v) + strings[i + 1]; });
    return new SafeHTML(out);
  }
  function setHTML(el, fragment) {
    if (!(fragment instanceof SafeHTML)) throw new TypeError("setHTML requires an html`` fragment");
    el.innerHTML = fragment.s;
  }
  const api = {esc, html, setHTML, SafeHTML};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  Object.assign(root, api);
})(typeof window !== "undefined" ? window : globalThis);
