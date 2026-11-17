const STRINGS = {
  en: {customers:"Customers",bookings:"Bookings",billing:"Quotes & Invoices",comeback:"Comeback",messages:"Messages",reports:"Reports",data_rights:"Your Data Is Yours",add_customer:"Add customer",name:"Name",phone:"Phone",email:"Email",language:"Language",save:"Save",export_all:"Export all data",import_backlog:"Import lapsed list",lapsed_customers:"Lapsed customers",open_invoices:"Open invoices",draft_needs_approval:"Draft — a human must approve before sending",approve:"Approve",send:"Send"},
  es: {customers:"Clientes",bookings:"Reservas",billing:"Cotizaciones y facturas",comeback:"Recuperación",messages:"Mensajes",reports:"Informes",data_rights:"Tus datos son tuyos",add_customer:"Agregar cliente",name:"Nombre",phone:"Teléfono",email:"Correo electrónico",language:"Idioma",save:"Guardar",export_all:"Exportar todos los datos",import_backlog:"Importar lista de clientes inactivos",lapsed_customers:"Clientes inactivos",open_invoices:"Facturas abiertas",draft_needs_approval:"Borrador — una persona debe aprobar antes de enviar",approve:"Aprobar",send:"Enviar"}
};
let lang = "en";
const $ = (s) => document.querySelector(s);

function applyLang() {
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const k = el.getAttribute("data-i18n");
    if (STRINGS[lang][k]) el.textContent = STRINGS[lang][k];
  });
  $("#lang-en").classList.toggle("active", lang === "en");
  $("#lang-es").classList.toggle("active", lang === "es");
}
$("#lang-en").onclick = () => { lang = "en"; applyLang(); };
$("#lang-es").onclick = () => { lang = "es"; applyLang(); };

document.querySelectorAll(".tab").forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll("main section").forEach(s => s.hidden = true);
    $("#tab-" + btn.dataset.tab).hidden = false;
    if (btn.dataset.tab === "comeback") loadLapsed();
    if (btn.dataset.tab === "reports") loadSummary();
    if (btn.dataset.tab === "bookings") loadReminders();
  };
});

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error((await r.json()).detail || r.status);
  return r.json();
}

async function loadCustomers() {
  const list = await api("/api/customers");
  $("#customer-list").innerHTML = list.map(c =>
    `<li><strong>${c.name}</strong> · ${c.phone || ""} · ${c.email || ""} · ${c.language.toUpperCase()}</li>`).join("");
}
$("#customer-form").onsubmit = async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = Object.fromEntries(fd.entries());
  body.consent_marketing = fd.get("consent_marketing") === "on";
  try {
    const out = await api("/api/customers", {method: "POST",
      headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    $("#customer-msg").textContent = out.merged_duplicate
      ? "Matched an existing record — kept as one record." : "Saved.";
    e.target.reset(); loadCustomers();
  } catch (err) { $("#customer-msg").textContent = err.message; }
};

async function loadReminders() {
  const due = await api("/api/reminders");
  $("#reminder-list").innerHTML = due.length
    ? due.map(b => `<li>${b.customer_name} — ${b.title} · ${b.starts_at_utc}</li>`).join("")
    : "<li>No reminders due in the next 24 hours.</li>";
}

async function loadLapsed() {
  const lapsed = await api("/api/comeback/lapsed");
  $("#lapsed-list").innerHTML = lapsed.map(c =>
    `<li><strong>${c.name}</strong> · last service: ${c.last_service_at || "never"} · ${c.language.toUpperCase()}</li>`).join("");
}
$("#backlog-btn").onclick = async () => {
  const f = $("#backlog-file").files[0];
  if (!f) return;
  const text = await f.text();
  try {
    const report = await api("/api/comeback/import", {method: "POST",
      headers: {"Content-Type": "text/csv"}, body: text});
    $("#import-report").textContent = JSON.stringify(report, null, 2);
    loadLapsed();
  } catch (err) { $("#import-report").textContent = err.message; }
};

async function loadSummary() {
  const s = await api("/api/reports/summary");
  $("#summary-box").innerHTML = [
    ["Customers", s.customers], ["Lapsed", s.lapsed_customers],
    ["Upcoming bookings", s.upcoming_bookings], ["Avg rating", s.average_rating ?? "—"]
  ].map(([k, v]) => `<div class="card"><div class="num">${v}</div><div>${k}</div></div>`).join("");
}
$("#export-btn").onclick = async () => {
  const data = await api("/api/export");
  const blob = new Blob([JSON.stringify(data, null, 2)], {type: "application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "mq-crm-export.json"; a.click();
};

applyLang(); loadCustomers();
