const STRINGS = {
  en: {customers:"Customers",bookings:"Bookings",billing:"Quotes & Invoices",comeback:"Comeback",messages:"Messages",reports:"Reports",data_rights:"Your Data Is Yours",add_customer:"Add customer",name:"Name",phone:"Phone",email:"Email",language:"Language",save:"Save",export_all:"Export all data",import_backlog:"Import lapsed list",lapsed_customers:"Lapsed customers",open_invoices:"Open invoices",draft_needs_approval:"Draft — a human must approve before sending",approve:"Approve",send:"Send",new_booking:"New booking",title:"Title",when:"Date & time",create_quote:"Create quote",add_item:"Add item",description:"Description",qty:"Qty",amount_cents:"Amount (cents)",total:"Total",compose:"Compose",template:"Template",review_request:"Request review",referral_code:"Referral code",record_payment:"Record payment",convert_invoice:"Convert to invoice"},
  es: {customers:"Clientes",bookings:"Reservas",billing:"Cotizaciones y facturas",comeback:"Recuperación",messages:"Mensajes",reports:"Informes",data_rights:"Tus datos son tuyos",add_customer:"Agregar cliente",name:"Nombre",phone:"Teléfono",email:"Correo electrónico",language:"Idioma",save:"Guardar",export_all:"Exportar todos los datos",import_backlog:"Importar lista de clientes inactivos",lapsed_customers:"Clientes inactivos",open_invoices:"Facturas abiertas",draft_needs_approval:"Borrador — una persona debe aprobar antes de enviar",approve:"Aprobar",send:"Enviar",new_booking:"Nueva reserva",title:"Título",when:"Fecha y hora",create_quote:"Crear cotización",add_item:"Agregar artículo",description:"Descripción",qty:"Cant.",amount_cents:"Cantidad (centavos)",total:"Total",compose:"Redactar",template:"Plantilla",review_request:"Pedir reseña",referral_code:"Código de referido",record_payment:"Registrar pago",convert_invoice:"Convertir a factura"},
  pt: {customers:"Clientes",bookings:"Agendamentos",billing:"Orçamentos e faturas",comeback:"Recuperação",messages:"Mensagens",reports:"Relatórios",data_rights:"Seus dados são seus",add_customer:"Adicionar cliente",name:"Nome",phone:"Telefone",email:"E-mail",language:"Idioma",save:"Salvar",export_all:"Exportar todos os dados",import_backlog:"Importar lista de clientes inativos",lapsed_customers:"Clientes inativos",open_invoices:"Faturas abertas",draft_needs_approval:"Rascunho — uma pessoa deve aprovar antes de enviar",approve:"Aprovar",send:"Enviar",new_booking:"Novo agendamento",title:"Título",when:"Data e hora",create_quote:"Criar orçamento",add_item:"Adicionar item",description:"Descrição",qty:"Qtd.",amount_cents:"Valor (centavos)",total:"Total",compose:"Escrever",template:"Modelo",review_request:"Pedir avaliação",referral_code:"Código de indicação",record_payment:"Registrar pagamento",convert_invoice:"Converter em fatura"},
  ht: {customers:"Kliyan",bookings:"Randevou",billing:"Estimasyon ak fakti",comeback:"Rekipere kliyan",messages:"Mesaj",reports:"Rapò",data_rights:"Done ou se done ou",add_customer:"Ajoute kliyan",name:"Non",phone:"Telefòn",email:"Imèl",language:"Lang",save:"Anrejistre",export_all:"Ekspòte tout done yo",import_backlog:"Enpòte lis kliyan ki pa aktif",lapsed_customers:"Kliyan ki pa aktif",open_invoices:"Fakti ki louvri",draft_needs_approval:"Bouyon — yon moun dwe apwouve anvan ou voye l",approve:"Apwouve",send:"Voye",new_booking:"Nouvo randevou",title:"Tit",when:"Dat ak lè",create_quote:"Kreye estimasyon",add_item:"Ajoute atik",description:"Deskripsyon",qty:"Kantite",amount_cents:"Montan (santim)",total:"Total",compose:"Ekri",template:"Modèl",review_request:"Mande yon revizyon",referral_code:"Kòd referans",record_payment:"Anrejistre peman",convert_invoice:"Konvèti an fakti"}
};
/* Batch 009d: dynamic list and form strings in all four languages (PT/HT
   pending native-speaker review). Server error text is still English. */
Object.assign(STRINGS.en, {"marketing_consent": "Marketing consent", "reminders_due": "Reminders due (24h)", "all_bookings": "All bookings", "tpl_reminder": "Reminder", "tpl_quote_ready": "Quote ready", "tpl_invoice_ready": "Invoice ready", "tpl_comeback": "Comeback", "tpl_review_request": "Review request", "ai_draft_btn": "AI draft (comeback)", "csv_hint": "CSV columns:", "saved": "Saved.", "merged": "Matched an existing record — kept as one record.", "review_requested": "Review requested.", "referral_is": "Referral code: {code}", "cancel": "Cancel", "no_reminders": "No reminders due in the next 24 hours.", "quote_created": "Quote created.", "quote_n": "Quote #{n}", "invoice_n": "Invoice #{n}", "paid": "Paid", "mark_sent": "Mark sent", "accept": "Accept", "draft_composed": "Draft composed.", "ai_draft_created": "AI draft created — approval still required.", "inbound": "inbound", "translation_pending": "translation pending", "held_for_review": "held for review", "purpose": "purpose", "purpose_unclear": "purpose unclear", "not_set": "not set", "classify_transactional": "Classify: transactional", "classify_marketing": "Classify: marketing", "release_not_promo": "Release (not promotional)", "withdraw": "Withdraw", "release_prompt": "Why is this NOT promotional? (recorded in the audit log)", "delivery_status": "Delivery {status}: {detail}", "last_service": "last service", "never": "never", "sum_customers": "Customers", "sum_lapsed": "Lapsed", "sum_upcoming": "Upcoming bookings", "sum_rating": "Avg rating", "st_booked": "booked", "st_cancelled": "cancelled", "st_completed": "completed", "st_draft": "draft", "st_sent": "sent", "st_accepted": "accepted", "st_declined": "declined", "st_open": "open", "st_paid": "paid", "st_approved": "approved", "st_held": "held", "st_received": "received", "st_withdrawn": "withdrawn", "st_delivered": "delivered", "st_failed": "failed", "st_queued": "queued", "st_converted": "converted", "st_done": "done", "st_sending": "sending", "by_human": "staff", "by_ai_draft": "AI draft", "by_customer": "customer"});
Object.assign(STRINGS.es, {"marketing_consent": "Consentimiento de marketing", "reminders_due": "Recordatorios pendientes (24 h)", "all_bookings": "Todas las reservas", "tpl_reminder": "Recordatorio", "tpl_quote_ready": "Cotización lista", "tpl_invoice_ready": "Factura lista", "tpl_comeback": "Recuperación", "tpl_review_request": "Solicitud de reseña", "ai_draft_btn": "Borrador con IA (recuperación)", "csv_hint": "Columnas del CSV:", "saved": "Guardado.", "merged": "Coincide con un registro existente: se mantuvo como un solo registro.", "review_requested": "Reseña solicitada.", "referral_is": "Código de referido: {code}", "cancel": "Cancelar", "no_reminders": "No hay recordatorios en las próximas 24 horas.", "quote_created": "Cotización creada.", "quote_n": "Cotización n.º {n}", "invoice_n": "Factura n.º {n}", "paid": "Pagado", "mark_sent": "Marcar como enviada", "accept": "Aceptar", "draft_composed": "Borrador creado.", "ai_draft_created": "Borrador con IA creado: aún requiere aprobación.", "inbound": "entrante", "translation_pending": "traducción pendiente", "held_for_review": "retenido para revisión", "purpose": "propósito", "purpose_unclear": "propósito no claro", "not_set": "sin definir", "classify_transactional": "Clasificar: transaccional", "classify_marketing": "Clasificar: marketing", "release_not_promo": "Liberar (no es promocional)", "withdraw": "Retirar", "release_prompt": "¿Por qué esto NO es promocional? (queda registrado en el registro de auditoría)", "delivery_status": "Entrega {status}: {detail}", "last_service": "último servicio", "never": "nunca", "sum_customers": "Clientes", "sum_lapsed": "Inactivos", "sum_upcoming": "Próximas reservas", "sum_rating": "Calificación promedio", "st_booked": "reservada", "st_cancelled": "cancelada", "st_completed": "completada", "st_draft": "borrador", "st_sent": "enviada", "st_accepted": "aceptada", "st_declined": "rechazada", "st_open": "abierta", "st_paid": "pagada", "st_approved": "aprobado", "st_held": "retenido", "st_received": "recibido", "st_withdrawn": "retirado", "st_delivered": "entregado", "st_failed": "fallido", "st_queued": "en cola", "st_converted": "convertida", "st_done": "realizada", "st_sending": "enviando", "by_human": "equipo", "by_ai_draft": "borrador con IA", "by_customer": "cliente"});
Object.assign(STRINGS.pt, {"marketing_consent": "Consentimento de marketing", "reminders_due": "Lembretes pendentes (24 h)", "all_bookings": "Todos os agendamentos", "tpl_reminder": "Lembrete", "tpl_quote_ready": "Orçamento pronto", "tpl_invoice_ready": "Fatura pronta", "tpl_comeback": "Recuperação", "tpl_review_request": "Pedido de avaliação", "ai_draft_btn": "Rascunho com IA (recuperação)", "csv_hint": "Colunas do CSV:", "saved": "Salvo.", "merged": "Corresponde a um registro existente: mantido como um só registro.", "review_requested": "Avaliação solicitada.", "referral_is": "Código de indicação: {code}", "cancel": "Cancelar", "no_reminders": "Nenhum lembrete nas próximas 24 horas.", "quote_created": "Orçamento criado.", "quote_n": "Orçamento nº {n}", "invoice_n": "Fatura nº {n}", "paid": "Pago", "mark_sent": "Marcar como enviado", "accept": "Aceitar", "draft_composed": "Rascunho criado.", "ai_draft_created": "Rascunho com IA criado: ainda precisa de aprovação.", "inbound": "recebida", "translation_pending": "tradução pendente", "held_for_review": "retida para revisão", "purpose": "finalidade", "purpose_unclear": "finalidade não clara", "not_set": "não definida", "classify_transactional": "Classificar: transacional", "classify_marketing": "Classificar: marketing", "release_not_promo": "Liberar (não é promocional)", "withdraw": "Retirar", "release_prompt": "Por que isto NÃO é promocional? (fica registrado no log de auditoria)", "delivery_status": "Entrega {status}: {detail}", "last_service": "último atendimento", "never": "nunca", "sum_customers": "Clientes", "sum_lapsed": "Inativos", "sum_upcoming": "Próximos agendamentos", "sum_rating": "Avaliação média", "st_booked": "agendado", "st_cancelled": "cancelado", "st_completed": "concluído", "st_draft": "rascunho", "st_sent": "enviado", "st_accepted": "aceito", "st_declined": "recusado", "st_open": "em aberto", "st_paid": "pago", "st_approved": "aprovado", "st_held": "retido", "st_received": "recebido", "st_withdrawn": "retirado", "st_delivered": "entregue", "st_failed": "falhou", "st_queued": "na fila", "st_converted": "convertido", "st_done": "concluído", "st_sending": "enviando", "by_human": "equipe", "by_ai_draft": "rascunho com IA", "by_customer": "cliente"});
Object.assign(STRINGS.ht, {"marketing_consent": "Konsantman pou maketing", "reminders_due": "Rapèl pou 24 èdtan k ap vini yo", "all_bookings": "Tout randevou yo", "tpl_reminder": "Rapèl", "tpl_quote_ready": "Estimasyon pare", "tpl_invoice_ready": "Fakti pare", "tpl_comeback": "Rekipere kliyan", "tpl_review_request": "Demann revizyon", "ai_draft_btn": "Bouyon IA (rekipere kliyan)", "csv_hint": "Kolòn CSV yo:", "saved": "Anrejistre.", "merged": "Li koresponn ak yon dosye ki te deja la: nou kenbe l kòm yon sèl dosye.", "review_requested": "Nou mande revizyon an.", "referral_is": "Kòd referans: {code}", "cancel": "Anile", "no_reminders": "Pa gen rapèl nan 24 èdtan k ap vini yo.", "quote_created": "Estimasyon an kreye.", "quote_n": "Estimasyon #{n}", "invoice_n": "Fakti #{n}", "paid": "Peye", "mark_sent": "Make l voye", "accept": "Aksepte", "draft_composed": "Bouyon an kreye.", "ai_draft_created": "Bouyon IA a kreye: li toujou bezwen apwobasyon.", "inbound": "mesaj ki rantre", "translation_pending": "tradiksyon an poko fèt", "held_for_review": "kenbe pou revizyon", "purpose": "objektif", "purpose_unclear": "objektif la pa klè", "not_set": "poko defini", "classify_transactional": "Klase: tranzaksyonèl", "classify_marketing": "Klase: maketing", "release_not_promo": "Lage l (se pa piblisite)", "withdraw": "Retire", "release_prompt": "Poukisa sa a se PA piblisite? (sa ap anrejistre nan jounal odit la)", "delivery_status": "Livrezon {status}: {detail}", "last_service": "dènye sèvis", "never": "janm", "sum_customers": "Kliyan", "sum_lapsed": "Pa aktif", "sum_upcoming": "Randevou k ap vini", "sum_rating": "Nòt mwayèn", "st_booked": "rezève", "st_cancelled": "anile", "st_completed": "fini", "st_draft": "bouyon", "st_sent": "voye", "st_accepted": "aksepte", "st_declined": "refize", "st_open": "louvri", "st_paid": "peye", "st_approved": "apwouve", "st_held": "kenbe", "st_received": "resevwa", "st_withdrawn": "retire", "st_delivered": "livre", "st_failed": "echwe", "st_queued": "ap tann", "st_converted": "konvèti", "st_done": "fini", "st_sending": "ap voye", "by_human": "ekip la", "by_ai_draft": "bouyon IA", "by_customer": "kliyan"});
const tt = (k, vars) => {
  let s = (STRINGS[lang] && STRINGS[lang][k]) || STRINGS.en[k] || k;
  if (vars) Object.keys(vars).forEach(v => { s = s.split("{" + v + "}").join(String(vars[v])); });
  return s;
};
const st = (s) => (STRINGS.en["st_" + s] ? tt("st_" + s) : s);   // status codes -> words
const by = (s) => (STRINGS.en["by_" + s] ? tt("by_" + s) : s);    // message author codes -> words
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

/* Batch 009 — REAL LOGIN. The browser holds an HttpOnly session cookie that
   scripts cannot read; the role and the audit name come from the server's
   user record. No role or operator name is ever sent. Every state-changing
   request carries the per-session CSRF token (X-CSRF-Token). */
let csrfToken = null;
let me = null;
/* Batch 009c: the sign-in screen (login.js) owns the signed-out view; these
   two functions are the only hand-off and do not change any auth logic. */
const _login = () => (typeof MQLogin !== "undefined" ? MQLogin : null);
function setSignedIn(user, csrf) {
  me = user; csrfToken = csrf || null;
  $("#whoami").textContent = `${user.display_name || user.username} (${user.role})`;
  $("#logout-btn").hidden = false;
  $("#login-view").hidden = true;
  $("#app-main").hidden = false;
  if (_login()) _login().onSignedIn(user);
}
function setSignedOut(reason) {
  me = null; csrfToken = null;
  $("#whoami").textContent = "Not signed in";
  $("#logout-btn").hidden = true;
  $("#login-view").hidden = false;
  $("#app-main").hidden = true;
  if (_login()) _login().onSignedOut(reason || null);
}
async function api(path, opts = {}) {
  opts.headers = Object.assign({}, opts.headers || {});
  opts.headers["X-MQ-Lang"] = lang;   // Batch 010b: server error text in the UI language
  const method = (opts.method || "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD" && csrfToken) opts.headers["X-CSRF-Token"] = csrfToken;
  opts.credentials = "same-origin";
  const r = await fetch(path, opts);
  if (r.status === 401 && path !== "/api/auth/login" && path !== "/api/auth/login/verify")
    setSignedOut(me ? "session_ended" : null);
  if (!r.ok) throw new Error(((await r.json()) || {}).detail || r.status);
  return r.json();
}
const post = (path, body) => api(path, {method: "POST",
  headers: {"Content-Type": "application/json"}, body: body ? JSON.stringify(body) : undefined});

let customersCache = [];
async function refreshSelects() {
  customersCache = await api("/api/customers");
  $$(".customer-select").forEach(sel => {
    setHTML(sel, html`${customersCache.map(c =>
      html`<option value="${Number(c.id)}">${c.name} (${String(c.language).toUpperCase()})</option>`)}`);
  });
  setHTML($("#customer-list"), html`${customersCache.map(c =>
    html`<li><strong>${c.name}</strong> · ${c.phone || ""} · ${c.email || ""} ·
     <select data-act-change="setLang" data-id="${Number(c.id)}">${["en", "es", "pt", "ht"].map(l => html`<option value="${l}" ${l === c.language ? "selected" : ""}>${l.toUpperCase()}</option>`)}</select>
     <button data-act="askReview" data-id="${Number(c.id)}">${STRINGS[lang].review_request}</button>
     <button data-act="makeReferral" data-id="${Number(c.id)}">${STRINGS[lang].referral_code}</button></li>`)}`);
}
window.askReview = async (id) => { await post("/api/reviews/request", {customer_id: id}); alert(tt("review_requested")); };
window.setLang = async (id, language) => {
  try { await post(`/api/customers/${id}/update`, { language }); }
  catch (err) { $("#customer-msg").textContent = err.message; }
  refreshSelects();
};
window.makeReferral = async (id) => { const r = await post(`/api/referrals?customer_id=${id}`); alert(tt("referral_is", {code: r.code})); };

$("#customer-form").onsubmit = async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = Object.fromEntries(fd.entries());
  body.consent_marketing = fd.get("consent_marketing") === "on";
  try {
    const out = await post("/api/customers", body);
    $("#customer-msg").textContent = out.merged_duplicate
      ? tt("merged") : tt("saved");
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
  try { await post("/api/bookings", body); $("#booking-msg").textContent = tt("saved");
    e.target.reset(); loadBookings(); loadReminders(); }
  catch (err) { $("#booking-msg").textContent = err.message; }
};
async function loadBookings() {
  const list = await api("/api/bookings");
  setHTML($("#booking-list"), html`${list.map(b =>
    html`<li>${b.customer_name} — ${b.title} · ${b.starts_at_utc} · ${st(b.status)}
     ${b.status === "booked" ? html`<button data-act="cancelBooking" data-id="${Number(b.id)}">${tt("cancel")}</button>` : ""}</li>`)}`);
}
window.cancelBooking = async (id) => { await post(`/api/bookings/${id}/cancel`); loadBookings(); loadReminders(); };
async function loadReminders() {
  const due = await api("/api/reminders");
  setHTML($("#reminder-list"), due.length
    ? html`${due.map(b => html`<li>${b.customer_name} — ${b.title} · ${b.starts_at_utc}</li>`)}`
    : html`<li>${tt("no_reminders")}</li>`);
}

/* Billing */
$("#quote-form").onsubmit = async (e) => {
  e.preventDefault();
  const id = new FormData(e.target).get("customer_id");
  await post(`/api/quotes?customer_id=${id}`);
  $("#quote-msg").textContent = tt("quote_created"); loadQuotes();
};
async function loadQuotes() {
  const quotes = await api("/api/quotes");
  setHTML($("#quote-list"), html`${quotes.map(q => html`
    <div class="card-wide">
      <strong>${tt("quote_n", {n: Number(q.id)})}</strong> · ${q.customer_name} · ${st(q.status)} · ${STRINGS[lang].total}: ${money(q.total_minor, q.currency)}
      <div>${q.items.map((i, n) => html`${n ? html`<br>` : ""}${i.description} ×${i.qty} — ${money(i.qty * i.unit_amount_minor)}`)}</div>
      ${q.status === "draft" || q.status === "sent" ? html`
      <form data-act-submit="addItem" data-id="${Number(q.id)}">
        <input name="description" placeholder="${STRINGS[lang].description}" required>
        <input name="qty" type="number" value="1" min="1" class="w-qty">
        <input name="unit_amount_minor" type="number" placeholder="${STRINGS[lang].amount_cents}" required class="w-amount">
        <button>${STRINGS[lang].add_item}</button>
      </form>` : ""}
      ${q.status === "draft" ? html`<button data-act="quoteStatus" data-id="${Number(q.id)}" data-arg="sent">${tt("mark_sent")}</button>` : ""}
      ${q.status === "sent" ? html`<button data-act="quoteStatus" data-id="${Number(q.id)}" data-arg="accepted">${tt("accept")}</button>` : ""}
      ${q.status === "accepted" ? html`<button data-act="convertQuote" data-id="${Number(q.id)}">${STRINGS[lang].convert_invoice}</button>` : ""}
    </div>`)}`);
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
  setHTML($("#invoice-list"), html`${invs.map(i => html`
    <div class="card-wide"><strong>${tt("invoice_n", {n: Number(i.id)})}</strong> · ${st(i.status)} ·
      ${STRINGS[lang].total}: ${money(i.total_minor, i.currency)} · ${tt("paid")}: ${money(i.paid_minor, i.currency)}
      ${i.status === "open" ? html`<form data-act-submit="payInvoice" data-id="${Number(i.id)}">
        <input name="amount_minor" type="number" placeholder="${STRINGS[lang].amount_cents}" required class="w-amount">
        <button>${STRINGS[lang].record_payment}</button></form>` : ""}
    </div>`)}`);
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
    $("#message-msg").textContent = tt("draft_composed"); loadMessages();
  } catch (err) { $("#message-msg").textContent = err.message; }
};
$("#ai-draft-btn").onclick = async () => {
  const id = $("#message-form select[name=customer_id]").value;
  try { await post(`/api/ai/draft-comeback?customer_id=${id}`);
    $("#message-msg").textContent = tt("ai_draft_created"); loadMessages(); }
  catch (err) { $("#message-msg").textContent = err.message; }
};
async function loadMessages() {
  const msgs = await api("/api/messages");
  const deliveries = await api("/api/deliveries");
  const latestDelivery = {};
  for (const d of deliveries) if (!(d.message_id in latestDelivery)) latestDelivery[d.message_id] = d;
  const names = Object.fromEntries(customersCache.map(c => [c.id, c.name]));
  // Message text — inbound text especially — is attacker-controlled:
  // every value below is escaped by the html`` tag.
  setHTML($("#message-list"), html`${msgs.map(m => html`
    <li><strong>${names[m.customer_id] || m.customer_id}</strong> · ${st(m.status)} · ${by(m.created_by)}
      ${m.direction === "in" ? " · ↩ " + tt("inbound") : ""}
      ${m.translation_pending ? " · ⏳ " + tt("translation_pending") : ""}
      ${latestDelivery[m.id] ? html` · 📬 ${latestDelivery[m.id].transport}: ${st(latestDelivery[m.id].status)}` : ""}
      <br>${m.original_text}
      ${m.translated_text ? html`<br><em>${m.translated_text}</em>` : ""}
      ${m.status === "draft" && !m.translation_pending ? html`<br><button data-act="approveMsg" data-id="${Number(m.id)}">${STRINGS[lang].approve}</button>` : ""}
      ${m.status === "approved" ? html`<button data-act="sendMsg" data-id="${Number(m.id)}">${STRINGS[lang].send}</button>` : ""}
      ${m.status === "held" ? html`<br>⚠ ${tt("held_for_review")}: ${m.hold_reason || tt("purpose_unclear")} · ${tt("purpose")}: ${m.purpose || tt("not_set")}
        <button data-act="classifyMsg" data-id="${Number(m.id)}" data-arg="transactional">${tt("classify_transactional")}</button>
        <button data-act="classifyMsg" data-id="${Number(m.id)}" data-arg="marketing">${tt("classify_marketing")}</button>
        ${m.hold_reason === "promotional_content_in_transactional" ? html`<button data-act="releaseHold" data-id="${Number(m.id)}">${tt("release_not_promo")}</button>` : ""}` : ""}
      ${(m.status === "draft" || m.status === "approved" || m.status === "held") ? html`<button data-act="withdrawMsg" data-id="${Number(m.id)}">${tt("withdraw")}</button>` : ""}
    </li>`)}`);
}
window.approveMsg = async (id) => { await post(`/api/messages/${id}/approve`); loadMessages(); };
window.sendMsg = async (id) => {
  try {
    await post(`/api/messages/${id}/send`);
    const d = await post(`/api/messages/${id}/dispatch`);
    if (d.status !== "delivered") $("#message-msg").textContent = tt("delivery_status", {status: st(d.status), detail: d.detail || ""});
  } catch (err) { $("#message-msg").textContent = err.message; }
  loadMessages();
};
window.classifyMsg = async (id, purpose) => {
  try { await post(`/api/messages/${id}/classify`, {purpose}); }
  catch (err) { $("#message-msg").textContent = err.message; }
  loadMessages();
};
window.releaseHold = async (id) => {
  const reason = window.prompt(tt("release_prompt"));
  if (!reason) return;
  try { await post(`/api/messages/${id}/release-hold`, {reason}); }
  catch (err) { $("#message-msg").textContent = err.message; }
  loadMessages();
};
window.withdrawMsg = async (id) => { await post(`/api/messages/${id}/withdraw`); loadMessages(); };

/* Comeback */
async function loadLapsed() {
  const lapsed = await api("/api/comeback/lapsed");
  setHTML($("#lapsed-list"), html`${lapsed.map(c =>
    html`<li><strong>${c.name}</strong> · ${tt("last_service")}: ${c.last_service_at || tt("never")} · ${String(c.language).toUpperCase()}</li>`)}`);
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
  setHTML($("#summary-box"), html`${[
    [tt("sum_customers"), s.customers], [tt("sum_lapsed"), s.lapsed_customers],
    [tt("sum_upcoming"), s.upcoming_bookings], [tt("sum_rating"), s.average_rating ?? "—"]
  ].map(([k, v]) => html`<div class="card"><div class="num">${v}</div><div>${k}</div></div>`)}`);
}
$("#export-btn").onclick = async () => {
  const data = await api("/api/export");
  const blob = new Blob([JSON.stringify(data, null, 2)], {type: "application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "mq-crm-export.json"; a.click();
};

/* Sign-in and the two-step step: see login.js (Batch 009c). */
$("#logout-btn").onclick = async () => {
  try { await post("/api/auth/logout"); } catch (err) { /* session already gone */ }
  setSignedOut("logout");
};
async function boot() {
  try {
    const r = await api("/api/auth/me");
    if (r && r.user) { setSignedIn(r.user, r.csrf_token); refreshSelects(); }
    else setSignedOut();
  } catch (err) { setSignedOut(); }
}

applyLang(); boot();

/* Hardening (2026-11-18, review L1): the Content-Security-Policy allows no
   inline event handlers (script-src 'self'), so rendered buttons, selects and
   forms carry data-act* attributes and these three delegated listeners call
   the handler. Only names on this allow-list can be called; the id is always
   a Number and the optional argument is a fixed word from the template. */
const UI_ACTIONS = new Set(["askReview", "makeReferral", "cancelBooking", "quoteStatus",
  "convertQuote", "approveMsg", "sendMsg", "classifyMsg", "releaseHold", "withdrawMsg"]);
const UI_CHANGE = new Set(["setLang"]);
const UI_SUBMIT = new Set(["addItem", "payInvoice"]);
function bindUiActions(doc) {
  doc.addEventListener("click", (e) => {
    const el = e.target.closest ? e.target.closest("[data-act]") : null;
    if (!el || !UI_ACTIONS.has(el.dataset.act) || typeof window[el.dataset.act] !== "function") return;
    const id = Number(el.dataset.id);
    if (el.dataset.arg !== undefined) window[el.dataset.act](id, el.dataset.arg);
    else window[el.dataset.act](id);
  });
  doc.addEventListener("change", (e) => {
    const el = e.target.closest ? e.target.closest("[data-act-change]") : null;
    if (!el || !UI_CHANGE.has(el.dataset.actChange) || typeof window[el.dataset.actChange] !== "function") return;
    window[el.dataset.actChange](Number(el.dataset.id), el.value);
  });
  doc.addEventListener("submit", (e) => {
    const el = e.target.closest ? e.target.closest("form[data-act-submit]") : null;
    if (!el || !UI_SUBMIT.has(el.dataset.actSubmit) || typeof window[el.dataset.actSubmit] !== "function") return;
    window[el.dataset.actSubmit](e, Number(el.dataset.id));
  });
}
// Headless test harnesses stub `document` without addEventListener.
if (typeof document !== "undefined" && typeof document.addEventListener === "function") bindUiActions(document);
