const STRINGS = {
  en: {customers:"Customers",bookings:"Bookings",billing:"Quotes & Invoices",comeback:"Comeback",messages:"Messages",reports:"Reports",data_rights:"Your Data Is Yours",add_customer:"Add customer",name:"Name",phone:"Phone",email:"Email",language:"Language",save:"Save",export_all:"Export all data",import_backlog:"Import lapsed list",lapsed_customers:"Lapsed customers",open_invoices:"Open invoices",draft_needs_approval:"Draft — a human must approve before sending",approve:"Approve",send:"Send",new_booking:"New booking",title:"Title",when:"Date & time",create_quote:"Create quote",add_item:"Add item",description:"Description",qty:"Qty",amount_cents:"Amount (cents)",total:"Total",compose:"Compose",template:"Template",review_request:"Request review",referral_code:"Referral code",record_payment:"Record payment",convert_invoice:"Convert to invoice"},
  es: {customers:"Clientes",bookings:"Reservas",billing:"Cotizaciones y facturas",comeback:"Recuperación",messages:"Mensajes",reports:"Informes",data_rights:"Tus datos son tuyos",add_customer:"Agregar cliente",name:"Nombre",phone:"Teléfono",email:"Correo electrónico",language:"Idioma",save:"Guardar",export_all:"Exportar todos los datos",import_backlog:"Importar lista de clientes inactivos",lapsed_customers:"Clientes inactivos",open_invoices:"Facturas abiertas",draft_needs_approval:"Borrador — una persona debe aprobar antes de enviar",approve:"Aprobar",send:"Enviar",new_booking:"Nueva reserva",title:"Título",when:"Fecha y hora",create_quote:"Crear cotización",add_item:"Agregar artículo",description:"Descripción",qty:"Cant.",amount_cents:"Cantidad (centavos)",total:"Total",compose:"Redactar",template:"Plantilla",review_request:"Pedir reseña",referral_code:"Código de referido",record_payment:"Registrar pago",convert_invoice:"Convertir a factura"},
  pt: {customers:"Clientes",bookings:"Agendamentos",billing:"Orçamentos e faturas",comeback:"Recuperação",messages:"Mensagens",reports:"Relatórios",data_rights:"Seus dados são seus",add_customer:"Adicionar cliente",name:"Nome",phone:"Telefone",email:"E-mail",language:"Idioma",save:"Salvar",export_all:"Exportar todos os dados",import_backlog:"Importar lista de clientes inativos",lapsed_customers:"Clientes inativos",open_invoices:"Faturas abertas",draft_needs_approval:"Rascunho — uma pessoa deve aprovar antes de enviar",approve:"Aprovar",send:"Enviar",new_booking:"Novo agendamento",title:"Título",when:"Data e hora",create_quote:"Criar orçamento",add_item:"Adicionar item",description:"Descrição",qty:"Qtd.",amount_cents:"Valor (centavos)",total:"Total",compose:"Escrever",template:"Modelo",review_request:"Pedir avaliação",referral_code:"Código de indicação",record_payment:"Registrar pagamento",convert_invoice:"Converter em fatura"},
  ht: {customers:"Kliyan",bookings:"Randevou",billing:"Estimasyon ak fakti",comeback:"Rekipere kliyan",messages:"Mesaj",reports:"Rapò",data_rights:"Done ou se done ou",add_customer:"Ajoute kliyan",name:"Non",phone:"Telefòn",email:"Imèl",language:"Lang",save:"Anrejistre",export_all:"Ekspòte tout done yo",import_backlog:"Enpòte lis kliyan ki pa aktif",lapsed_customers:"Kliyan ki pa aktif",open_invoices:"Fakti ki louvri",draft_needs_approval:"Bouyon — yon moun dwe apwouve anvan ou voye l",approve:"Apwouve",send:"Voye",new_booking:"Nouvo randevou",title:"Tit",when:"Dat ak lè",create_quote:"Kreye estimasyon",add_item:"Ajoute atik",description:"Deskripsyon",qty:"Kantite",amount_cents:"Montan (santim)",total:"Total",compose:"Ekri",template:"Modèl",review_request:"Mande yon revizyon",referral_code:"Kòd referans",record_payment:"Anrejistre peman",convert_invoice:"Konvèti an fakti"}
};
let lang = "en";
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);
const money = (m, c="USD") => `${c} ${(m/100).toFixed(2)}`;

function applyLang() {
  $$("[data-i18n]").forEach(el => {
    const k = el.getAttribute("data-i18n");
    if (STRINGS[lang][k]) el.textContent = STRINGS[lang][k];
  });
  ["en", "es", "pt", "ht"].forEach(l =>
    $("#lang-" + l).classList.toggle("active", lang === l));
}
["en", "es", "pt", "ht"].forEach(l =>
  $("#lang-" + l).onclick = () => { lang = l; applyLang(); });

$$(".tab").forEach(btn => {
  btn.onclick = () => {
    $$(".tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    $$("main section").forEach(s => s.hidden = true);
    $("#tab-" + btn.dataset.tab).hidden = false;
    refreshSelects();
    if (btn.dataset.tab === "comeback") loadLapsed();
    if (btn.dataset.tab === "reports") loadSummary();
    if (btn.dataset.tab === "bookings") { loadReminders(); loadBookings(); }
    if (btn.dataset.tab === "billing") { loadQuotes(); loadInvoices(); }
    if (btn.dataset.tab === "messages") loadMessages();
  };
});

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error((await r.json()).detail || r.status);
  return r.json();
}
const post = (path, body) => api(path, {method: "POST",
  headers: {"Content-Type": "application/json"}, body: body ? JSON.stringify(body) : undefined});

let customersCache = [];
async function refreshSelects() {
  customersCache = await api("/api/customers");
  $$(".customer-select").forEach(sel => {
    sel.innerHTML = customersCache.map(c =>
      `<option value="${c.id}">${c.name} (${c.language.toUpperCase()})</option>`).join("");
  });
  $("#customer-list").innerHTML = customersCache.map(c =>
    `<li><strong>${c.name}</strong> · ${c.phone || ""} · ${c.email || ""} · ${c.language.toUpperCase()}
     <button onclick="askReview(${c.id})">${STRINGS[lang].review_request}</button>
     <button onclick="makeReferral(${c.id})">${STRINGS[lang].referral_code}</button></li>`).join("");
}
window.askReview = async (id) => { await post("/api/reviews/request", {customer_id: id}); alert("Review requested"); };
window.makeReferral = async (id) => { const r = await post(`/api/referrals?customer_id=${id}`); alert("Code: " + r.code); };

$("#customer-form").onsubmit = async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = Object.fromEntries(fd.entries());
  body.consent_marketing = fd.get("consent_marketing") === "on";
  try {
    const out = await post("/api/customers", body);
    $("#customer-msg").textContent = out.merged_duplicate
      ? "Matched an existing record — kept as one record." : "Saved.";
    e.target.reset(); refreshSelects();
  } catch (err) { $("#customer-msg").textContent = err.message; }
};

/* Bookings */
$("#booking-form").onsubmit = async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = Object.fromEntries(fd.entries());
  body.customer_id = Number(body.customer_id);
  body.local_start = body.local_start.replace("T", " ");
  try { await post("/api/bookings", body); $("#booking-msg").textContent = "Saved.";
    e.target.reset(); loadBookings(); loadReminders(); }
  catch (err) { $("#booking-msg").textContent = err.message; }
};
async function loadBookings() {
  const list = await api("/api/bookings");
  $("#booking-list").innerHTML = list.map(b =>
    `<li>${b.customer_name} — ${b.title} · ${b.starts_at_utc} · ${b.status}</li>`).join("");
}
async function loadReminders() {
  const due = await api("/api/reminders");
  $("#reminder-list").innerHTML = due.length
    ? due.map(b => `<li>${b.customer_name} — ${b.title} · ${b.starts_at_utc}</li>`).join("")
    : "<li>No reminders due in the next 24 hours.</li>";
}

/* Billing */
$("#quote-form").onsubmit = async (e) => {
  e.preventDefault();
  const id = new FormData(e.target).get("customer_id");
  await post(`/api/quotes?customer_id=${id}`);
  $("#quote-msg").textContent = "Quote created."; loadQuotes();
};
async function loadQuotes() {
  const quotes = await api("/api/quotes");
  $("#quote-list").innerHTML = quotes.map(q => `
    <div class="card-wide">
      <strong>Quote #${q.id}</strong> · ${q.customer_name} · ${q.status} · ${STRINGS[lang].total}: ${money(q.total_minor, q.currency)}
      <div>${q.items.map(i => `${i.description} ×${i.qty} — ${money(i.qty * i.unit_amount_minor)}`).join("<br>")}</div>
      ${q.status === "draft" || q.status === "sent" ? `
      <form onsubmit="return addItem(event, ${q.id})">
        <input name="description" placeholder="${STRINGS[lang].description}" required>
        <input name="qty" type="number" value="1" min="1" style="width:70px">
        <input name="unit_amount_minor" type="number" placeholder="${STRINGS[lang].amount_cents}" required style="width:130px">
        <button>${STRINGS[lang].add_item}</button>
      </form>` : ""}
      ${q.status === "draft" ? `<button onclick="quoteStatus(${q.id},'sent')">Mark sent</button>` : ""}
      ${q.status === "sent" ? `<button onclick="quoteStatus(${q.id},'accepted')">Accept</button>` : ""}
      ${q.status === "accepted" ? `<button onclick="convertQuote(${q.id})">${STRINGS[lang].convert_invoice}</button>` : ""}
    </div>`).join("");
}
window.addItem = async (e, qid) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  await post(`/api/quotes/${qid}/items`, {description: fd.get("description"),
    qty: Number(fd.get("qty")), unit_amount_minor: Number(fd.get("unit_amount_minor"))});
  loadQuotes(); return false;
};
window.quoteStatus = async (qid, s) => { await post(`/api/quotes/${qid}/status?status=${s}`); loadQuotes(); };
window.convertQuote = async (qid) => { await post(`/api/quotes/${qid}/invoice`); loadQuotes(); loadInvoices(); };
async function loadInvoices() {
  const invs = await api("/api/invoices");
  $("#invoice-list").innerHTML = invs.map(i => `
    <div class="card-wide"><strong>Invoice #${i.id}</strong> · ${i.status} ·
      ${STRINGS[lang].total}: ${money(i.total_minor, i.currency)} · Paid: ${money(i.paid_minor, i.currency)}
      ${i.status === "open" ? `<form onsubmit="return payInvoice(event, ${i.id})">
        <input name="amount_minor" type="number" placeholder="${STRINGS[lang].amount_cents}" required style="width:130px">
        <button>${STRINGS[lang].record_payment}</button></form>` : ""}
    </div>`).join("");
}
window.payInvoice = async (e, iid) => {
  e.preventDefault();
  const amt = Number(new FormData(e.target).get("amount_minor"));
  await post(`/api/invoices/${iid}/payments`, {amount_minor: amt, method: "card"});
  loadInvoices(); return false;
};

/* Messages */
$("#message-form").onsubmit = async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    await post("/api/messages/template", {customer_id: Number(fd.get("customer_id")),
      template_key: fd.get("template_key"),
      context: {}});
    $("#message-msg").textContent = "Draft composed."; loadMessages();
  } catch (err) { $("#message-msg").textContent = err.message; }
};
$("#ai-draft-btn").onclick = async () => {
  const id = $("#message-form select[name=customer_id]").value;
  try { await post(`/api/ai/draft-comeback?customer_id=${id}`);
    $("#message-msg").textContent = "AI draft created — approval still required."; loadMessages(); }
  catch (err) { $("#message-msg").textContent = err.message; }
};
async function loadMessages() {
  const msgs = await api("/api/messages");
  const deliveries = await api("/api/deliveries");
  const latestDelivery = {};
  for (const d of deliveries) if (!(d.message_id in latestDelivery)) latestDelivery[d.message_id] = d;
  const names = Object.fromEntries(customersCache.map(c => [c.id, c.name]));
  $("#message-list").innerHTML = msgs.map(m => `
    <li><strong>${names[m.customer_id] || m.customer_id}</strong> · ${m.status} · ${m.created_by}
      ${m.direction === "in" ? " · ↩ inbound" : ""}
      ${m.translation_pending ? " · ⏳ translation pending" : ""}
      ${latestDelivery[m.id] ? ` · 📬 ${latestDelivery[m.id].transport}: ${latestDelivery[m.id].status}` : ""}
      <br>${m.original_text}
      ${m.translated_text ? `<br><em>${m.translated_text}</em>` : ""}
      ${m.status === "draft" && !m.translation_pending ? `<br><button onclick="approveMsg(${m.id})">${STRINGS[lang].approve}</button>` : ""}
      ${m.status === "approved" ? `<button onclick="sendMsg(${m.id})">${STRINGS[lang].send}</button>` : ""}
      ${(m.status === "draft" || m.status === "approved") ? `<button onclick="withdrawMsg(${m.id})">Withdraw</button>` : ""}
    </li>`).join("");
}
window.approveMsg = async (id) => { await post(`/api/messages/${id}/approve`); loadMessages(); };
window.sendMsg = async (id) => {
  try {
    await post(`/api/messages/${id}/send`);
    const d = await post(`/api/messages/${id}/dispatch`);
    if (d.status !== "delivered") $("#message-msg").textContent = `Delivery ${d.status}: ${d.detail || ""}`;
  } catch (err) { $("#message-msg").textContent = err.message; }
  loadMessages();
};
window.withdrawMsg = async (id) => { await post(`/api/messages/${id}/withdraw`); loadMessages(); };

/* Comeback */
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

/* Reports */
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

applyLang(); refreshSelects();
