/* M&Q CRM: Overview dashboard (Batch 009d, presentation only).

   Every number and chart comes from the existing read APIs, through app.js
   api() (same session cookie, same role checks; viewers can read, nothing
   here writes):
     /api/reports/summary  /api/customers  /api/bookings
     /api/invoices         /api/messages   /api/quotes
   Nothing is estimated or invented. Metrics this CRM has no data for
   (pipeline value, revenue forecast, average deal size) are shown as "—"
   under "not tracked".
   Charts are inline SVG built with DOM APIs (no library, no CDN, no
   HTML strings). */
(function () {
  "use strict";
  // PT and HT strings are pending native review.
  const T = {
    en: {overview: "Overview",
      funnel_title: "Sales funnel", f_customers: "Customers", f_sent: "Quotes sent", f_accepted: "Quotes accepted",
      f_invoiced: "Invoiced", f_paid: "Paid in full", f_of_customers: "{p} of customers got a quote",
      f_of_prev: "{p} of the tier above", f_conv: "Conversion", f_count: "Count", f_amount: "Amount", f_tier: "Stage",
      funnel_note: "From your CRM records: quotes past draft, accepted or converted quotes, invoices, and invoices paid in full. Amounts in {cur} only. Tier widths are a fixed shape, not to scale. “—” means there is nothing to divide by.", test_data: "Test data", test_data_hint: "This build runs on synthetic test records only.",
      kpi_paid: "Payments received", kpi_paid_sub: "All recorded payments", kpi_paid_other: "Also: {list}",
      chart_billing: "Invoiced vs. paid in full, last 6 months", series_invoiced: "Invoiced", series_paid: "Paid in full",
      chart_billing_note: "Invoices by issue date; “paid in full” by the date the invoice was fully paid. Currency: {cur}.",
      kpi_customers: "Customers", kpi_upcoming: "Upcoming bookings", kpi_open_inv: "Open invoices",
      kpi_customers_sub: "{n} lapsed (no service in 90+ days)", kpi_open_quotes: "Open quotes", kpi_open_quotes_sub: "{n} sent, awaiting an answer", kpi_drafts: "Drafts awaiting approval",
      kpi_rating: "Average rating", kpi_rating_sub: "From received reviews", kpi_open_inv_sub: "{n} open",
      chart_customers: "Customers, last 6 months", chart_customers_note: "Total customers at the end of each month (by date added).",
      chart_bookings: "Upcoming bookings, next 8 weeks", chart_bookings_note: "Booked appointments per week (cancelled and completed excluded).",
      wk: "Wk of {d}", no_data: "No data yet", loading: "Loading…", load_error: "Couldn't load the overview. Try again.",
      not_tracked_title: "Not tracked in this CRM yet", not_tracked_note: "No data source exists for these, so nothing is shown.",
      nt_pipeline: "Pipeline value", nt_deal: "Average deal size", nt_forecast: "Revenue forecast", updated: "Updated {t}",
      refresh: "Refresh", none: "—"},
    es: {overview: "Resumen",
      funnel_title: "Embudo de ventas", f_customers: "Clientes", f_sent: "Cotizaciones enviadas", f_accepted: "Cotizaciones aceptadas",
      f_invoiced: "Facturado", f_paid: "Pagado por completo", f_of_customers: "{p} de los clientes recibió una cotización",
      f_of_prev: "{p} del nivel anterior", f_conv: "Conversión", f_count: "Cantidad", f_amount: "Monto", f_tier: "Etapa",
      funnel_note: "Según los registros del CRM: cotizaciones que pasaron de borrador, cotizaciones aceptadas o convertidas, facturas y facturas pagadas por completo. Montos solo en {cur}. El ancho de cada nivel es una forma fija, no a escala. “—” significa que no hay con qué dividir.", test_data: "Datos de prueba", test_data_hint: "Esta versión usa solo registros de prueba sintéticos.",
      kpi_paid: "Pagos recibidos", kpi_paid_sub: "Todos los pagos registrados", kpi_paid_other: "También: {list}",
      chart_billing: "Facturado vs. pagado por completo, últimos 6 meses", series_invoiced: "Facturado", series_paid: "Pagado por completo",
      chart_billing_note: "Facturas por fecha de emisión; “pagado por completo” por la fecha en que se pagó toda la factura. Moneda: {cur}.",
      kpi_customers: "Clientes", kpi_upcoming: "Próximas reservas", kpi_open_inv: "Facturas abiertas",
      kpi_customers_sub: "{n} inactivos (sin servicio en 90+ días)", kpi_open_quotes: "Cotizaciones abiertas", kpi_open_quotes_sub: "{n} enviadas, esperando respuesta", kpi_drafts: "Borradores por aprobar",
      kpi_rating: "Calificación promedio", kpi_rating_sub: "De las reseñas recibidas", kpi_open_inv_sub: "{n} abiertas",
      chart_customers: "Clientes, últimos 6 meses", chart_customers_note: "Total de clientes al final de cada mes (por fecha de alta).",
      chart_bookings: "Próximas reservas, siguientes 8 semanas", chart_bookings_note: "Citas reservadas por semana (sin canceladas ni completadas).",
      wk: "Sem. del {d}", no_data: "Aún no hay datos", loading: "Cargando…", load_error: "No se pudo cargar el resumen. Inténtalo de nuevo.",
      not_tracked_title: "Aún no se registra en este CRM", not_tracked_note: "No hay una fuente de datos para estos, así que no se muestra nada.",
      nt_pipeline: "Valor del embudo", nt_deal: "Tamaño promedio de venta", nt_forecast: "Pronóstico de ingresos", updated: "Actualizado {t}",
      refresh: "Actualizar", none: "—"},
    pt: {overview: "Visão geral",
      funnel_title: "Funil de vendas", f_customers: "Clientes", f_sent: "Orçamentos enviados", f_accepted: "Orçamentos aceitos",
      f_invoiced: "Faturado", f_paid: "Pago integralmente", f_of_customers: "{p} dos clientes recebeu um orçamento",
      f_of_prev: "{p} da etapa anterior", f_conv: "Conversão", f_count: "Quantidade", f_amount: "Valor", f_tier: "Etapa",
      funnel_note: "Pelos registros do CRM: orçamentos que saíram do rascunho, orçamentos aceitos ou convertidos, faturas e faturas pagas integralmente. Valores somente em {cur}. A largura de cada etapa é uma forma fixa, fora de escala. “—” significa que não há base para dividir.", test_data: "Dados de teste", test_data_hint: "Esta versão usa somente registros de teste sintéticos.",
      kpi_paid: "Pagamentos recebidos", kpi_paid_sub: "Todos os pagamentos registrados", kpi_paid_other: "Também: {list}",
      chart_billing: "Faturado vs. pago integralmente, últimos 6 meses", series_invoiced: "Faturado", series_paid: "Pago integralmente",
      chart_billing_note: "Faturas pela data de emissão; “pago integralmente” pela data em que a fatura foi totalmente paga. Moeda: {cur}.",
      kpi_customers: "Clientes", kpi_upcoming: "Próximos agendamentos", kpi_open_inv: "Faturas em aberto",
      kpi_customers_sub: "{n} inativos (sem atendimento há 90+ dias)", kpi_open_quotes: "Orçamentos em aberto", kpi_open_quotes_sub: "{n} enviados, aguardando resposta", kpi_drafts: "Rascunhos aguardando aprovação",
      kpi_rating: "Avaliação média", kpi_rating_sub: "Das avaliações recebidas", kpi_open_inv_sub: "{n} em aberto",
      chart_customers: "Clientes, últimos 6 meses", chart_customers_note: "Total de clientes no fim de cada mês (pela data de cadastro).",
      chart_bookings: "Próximos agendamentos, próximas 8 semanas", chart_bookings_note: "Horários agendados por semana (sem cancelados nem concluídos).",
      wk: "Sem. de {d}", no_data: "Ainda não há dados", loading: "Carregando…", load_error: "Não foi possível carregar a visão geral. Tente novamente.",
      not_tracked_title: "Ainda não registrado neste CRM", not_tracked_note: "Não há fonte de dados para estes itens, então nada é exibido.",
      nt_pipeline: "Valor do funil", nt_deal: "Valor médio por venda", nt_forecast: "Previsão de receita", updated: "Atualizado {t}",
      refresh: "Atualizar", none: "—"},
    ht: {overview: "Apèsi",
      funnel_title: "Antonwa lavant", f_customers: "Kliyan", f_sent: "Estimasyon voye", f_accepted: "Estimasyon aksepte",
      f_invoiced: "Fakti voye", f_paid: "Peye nèt", f_of_customers: "{p} nan kliyan yo resevwa yon estimasyon",
      f_of_prev: "{p} nan nivo anwo a", f_conv: "Konvèsyon", f_count: "Kantite", f_amount: "Montan", f_tier: "Etap",
      funnel_note: "Dapre dosye CRM ou: estimasyon ki pa bouyon ankò, estimasyon aksepte oswa konvèti, fakti, ak fakti ki peye nèt. Montan an {cur} sèlman. Lajè chak nivo se yon fòm fiks, li pa a lechèl. “—” vle di pa gen anyen pou divize.", test_data: "Done tès", test_data_hint: "Vèsyon sa a sèvi ak done tès sentetik sèlman.",
      kpi_paid: "Peman resevwa", kpi_paid_sub: "Tout peman ki anrejistre", kpi_paid_other: "Epi tou: {list}",
      chart_billing: "Fakti voye ak fakti peye nèt, 6 dènye mwa", series_invoiced: "Fakti voye", series_paid: "Peye nèt",
      chart_billing_note: "Fakti yo dapre dat yo voye yo; “peye nèt” dapre dat fakti a fin peye. Lajan: {cur}.",
      kpi_customers: "Kliyan", kpi_upcoming: "Randevou k ap vini", kpi_open_inv: "Fakti ki louvri",
      kpi_customers_sub: "{n} pa aktif (pa gen sèvis depi 90 jou oswa plis)", kpi_open_quotes: "Estimasyon ki louvri", kpi_open_quotes_sub: "{n} voye, y ap tann repons", kpi_drafts: "Bouyon k ap tann apwobasyon",
      kpi_rating: "Nòt mwayèn", kpi_rating_sub: "Dapre revizyon ki resevwa", kpi_open_inv_sub: "{n} louvri",
      chart_customers: "Kliyan, 6 dènye mwa", chart_customers_note: "Kantite kliyan nan fen chak mwa (dapre dat yo te ajoute).",
      chart_bookings: "Randevou k ap vini, 8 pwochen semèn", chart_bookings_note: "Randevou chak semèn (san sa ki anile oswa ki fini).",
      wk: "Sem. {d}", no_data: "Poko gen done", loading: "N ap chaje…", load_error: "Nou pa t ka chaje apèsi a. Eseye ankò.",
      not_tracked_title: "CRM sa a poko swiv sa yo", not_tracked_note: "Pa gen sous done pou yo, kidonk nou pa montre anyen.",
      nt_pipeline: "Valè opòtinite yo", nt_deal: "Valè mwayèn yon vant", nt_forecast: "Previzyon revni", updated: "Mete ajou {t}",
      refresh: "Rafrechi", none: "—"},
  };
  const NS = "http://www.w3.org/2000/svg";
  // Number/currency formats: Kreyòl uses en-US digits and symbols so no French
  // words appear; month names for Kreyòl come from HT_MONTHS (not fr-HT).
  const LOCALE = {en: "en-US", es: "es-US", pt: "pt-BR", ht: "en-US"};
  const HT_MONTHS = ["jan", "fev", "mas", "avr", "me", "jen", "jiy", "out", "sep", "okt", "nov", "des"];
  const curLang = () => (typeof lang !== "undefined" && T[lang]) ? lang : "en";
  function t(k, vars) {
    let s = T[curLang()][k] || T.en[k] || k;
    if (vars) Object.keys(vars).forEach((v) => { s = s.split("{" + v + "}").join(String(vars[v])); });
    return s;
  }
  const $id = (id) => document.getElementById(id);
  function el(tag, attrs, text) {
    const e = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach((k) => e.setAttribute(k, attrs[k]));
    if (text != null) e.textContent = text;
    return e;
  }
  function sv(tag, attrs) {
    const e = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach((k) => e.setAttribute(k, attrs[k]));
    return e;
  }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  const nf = (n) => new Intl.NumberFormat(LOCALE[curLang()]).format(n);
  function money(minor, cur, compact) {
    try {
      return new Intl.NumberFormat(LOCALE[curLang()], {style: "currency", currency: cur || "USD",
        notation: compact ? "compact" : "standard", maximumFractionDigits: compact ? 1 : 2}).format(minor / 100);
    } catch (e) { return (cur || "") + " " + (minor / 100).toFixed(2); }
  }
  const monthLabel = (d) => curLang() === "ht" ? HT_MONTHS[d.getUTCMonth()]
    : new Intl.DateTimeFormat(LOCALE[curLang()], {month: "short", timeZone: "UTC"}).format(d).replace(".", "");
  const dayLabel = (d) => curLang() === "en" ? `${d.getUTCMonth() + 1}/${d.getUTCDate()}`
    : `${d.getUTCDate()}/${d.getUTCMonth() + 1}`;
  function parse(s) {
    if (!s) return null;
    let x = String(s).replace(" ", "T");
    if (!/([zZ]|[+-]\d\d:?\d\d)$/.test(x)) x += "Z";
    const d = new Date(x);
    return isNaN(d.getTime()) ? null : d;
  }

  let data = null, loadedAt = null, loading = false, failed = false;

  // ---------------------------------------------------------------- data
  function months6(now) {
    const out = [];
    for (let i = 5; i >= 0; i--) out.push(new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - i, 1)));
    return out;
  }
  const mKey = (d) => d.getUTCFullYear() * 12 + d.getUTCMonth();
  function derive(raw) {
    const now = new Date();
    const ms = months6(now);
    const s = raw.summary;
    const paid = (s.payments_received || []).filter((p) => p.paid_minor > 0)
      .sort((a, b) => b.paid_minor - a.paid_minor);
    const primary = paid.length ? paid[0].currency : ((raw.invoices[0] || {}).currency || "USD");
    const openInv = s.open_invoices || [];
    const openCount = openInv.reduce((a, r) => a + r.count, 0);
    const openPrimary = openInv.find((r) => r.currency === primary);
    // billing by month (primary currency only, so the chart never mixes currencies)
    const inv = ms.map(() => 0), pif = ms.map(() => 0);
    raw.invoices.filter((i) => i.currency === primary).forEach((i) => {
      const iss = parse(i.issued_at); const k = iss ? ms.findIndex((m) => mKey(m) === mKey(iss)) : -1;
      if (k >= 0) inv[k] += i.total_minor;
      if (i.status === "paid" && i.paid_at) {
        const pd = parse(i.paid_at); const j = ms.findIndex((m) => mKey(m) === mKey(pd));
        if (j >= 0) pif[j] += i.paid_minor;
      }
    });
    // customers: cumulative at each month end
    const created = raw.customers.map((c) => parse(c.created_at)).filter(Boolean);
    const custSeries = ms.map((m) => {
      const end = Date.UTC(m.getUTCFullYear(), m.getUTCMonth() + 1, 1);
      return created.filter((d) => d.getTime() < end).length;
    });
    // bookings per week, next 8 weeks (week starts Monday, UTC)
    const today = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
    const monday = new Date(today.getTime() - ((today.getUTCDay() + 6) % 7) * 864e5);
    const weeks = []; for (let i = 0; i < 8; i++) weeks.push(new Date(monday.getTime() + i * 7 * 864e5));
    const wk = weeks.map(() => 0);
    raw.bookings.filter((b) => b.status === "booked").forEach((b) => {
      const d = parse(b.starts_at_utc); if (!d || d < now) return;
      const k = Math.floor((d - monday) / (7 * 864e5)); if (k >= 0 && k < 8) wk[k] += 1;
    });
    return {
      primary, paid, openCount, openPrimary, months: ms, inv, pif, custSeries, weeks, wk,
      customers: s.customers, upcoming: s.upcoming_bookings, lapsed: s.lapsed_customers,
      rating: s.average_rating, drafts: raw.messages.filter((m) => m.status === "draft").length,
      quotesSent: raw.quotes.filter((q) => q.status === "sent"),
      funnel: funnel(raw, primary),
    };
  }

  async function load() {
    if (loading || typeof api !== "function") return;
    loading = true; failed = false; render();
    try {
      const [summary, customers, bookings, invoices, messages, quotes] = await Promise.all([
        api("/api/reports/summary"), api("/api/customers"), api("/api/bookings"),
        api("/api/invoices"), api("/api/messages"), api("/api/quotes")]);
      data = derive({summary, customers, bookings, invoices, messages, quotes});
      loadedAt = new Date();
    } catch (e) { failed = true; }
    loading = false; render();
  }

  // ---------------------------------------------------------------- charts
  function emptyChart(host) {
    host.appendChild(el("p", {class: "chart-empty"}, t("none") + "  " + t("no_data")));
  }
  function areaLine(host, series, labels, opts) {
    clear(host);
    const all = [].concat(...series.map((s) => s.values));
    if (!all.some((v) => v > 0)) { emptyChart(host); return; }
    const W = 600, H = 200, P = {l: 8, r: 8, t: 12, b: 12};
    const max = Math.max(...all) * 1.12 || 1;
    const n = labels.length, xs = labels.map((_, i) => P.l + (i * (W - P.l - P.r)) / (n - 1));
    const y = (v) => P.t + (H - P.t - P.b) * (1 - v / max);
    const svg = sv("svg", {viewBox: `0 0 ${W} ${H}`, class: "chart", role: "img", "aria-label": opts.label});
    const defs = sv("defs"); const g = sv("linearGradient", {id: opts.id + "-g", x1: 0, y1: 0, x2: 0, y2: 1});
    g.appendChild(sv("stop", {offset: "0%", "stop-color": "#C9A54C", "stop-opacity": ".38"}));
    g.appendChild(sv("stop", {offset: "100%", "stop-color": "#C9A54C", "stop-opacity": "0"}));
    defs.appendChild(g); svg.appendChild(defs);
    for (let i = 0; i <= 4; i++) {
      const gy = P.t + i * (H - P.t - P.b) / 4;
      svg.appendChild(sv("line", {x1: P.l, x2: W - P.r, y1: gy, y2: gy, class: "grid"}));
    }
    series.forEach((s, si) => {
      const pts = s.values.map((v, i) => `${xs[i].toFixed(1)},${y(v).toFixed(1)}`);
      if (s.area) svg.appendChild(sv("path", {d: `M${xs[0]},${H - P.b} L${pts.join(" L")} L${xs[n - 1]},${H - P.b} Z`, fill: `url(#${opts.id}-g)`}));
      svg.appendChild(sv("path", {d: "M" + pts.join(" L"), class: si === 0 ? "ln" : "ln ln-2", fill: "none"}));
      s.values.forEach((v, i) => svg.appendChild(sv("circle", {cx: xs[i], cy: y(v), r: 3.2, class: si === 0 ? "pt" : "pt pt-2"})));
    });
    host.appendChild(svg);
    const ax = el("div", {class: "axis", "aria-hidden": "true"});
    labels.forEach((l) => ax.appendChild(el("span", null, l)));
    host.appendChild(ax);
    host.appendChild(dataTable(series, labels, opts));
  }
  function bars(host, values, labels, opts) {
    clear(host);
    if (!values.some((v) => v > 0)) { emptyChart(host); return; }
    const W = 600, H = 200, P = {l: 6, r: 6, t: 18, b: 6};
    const max = Math.max(...values) || 1, n = values.length, slot = (W - P.l - P.r) / n, bw = slot * 0.56;
    const svg = sv("svg", {viewBox: `0 0 ${W} ${H}`, class: "chart", role: "img", "aria-label": opts.label});
    values.forEach((v, i) => {
      const h = (H - P.t - P.b) * (v / max), x = P.l + i * slot + (slot - bw) / 2;
      svg.appendChild(sv("rect", {x, y: H - P.b - Math.max(h, v ? 2 : 0), width: bw, height: Math.max(h, v ? 2 : 0), rx: 3, class: "bar"}));
      svg.appendChild(sv("rect", {x, y: H - P.b - 1, width: bw, height: 1, class: "bar-base"}));
    });
    host.appendChild(svg);
    const ax = el("div", {class: "axis axis-bars", "aria-hidden": "true"});
    values.forEach((v, i) => { const s = el("span"); s.appendChild(el("b", null, nf(v))); s.appendChild(el("i", null, labels[i])); ax.appendChild(s); });
    host.appendChild(ax);
    host.appendChild(dataTable([{name: opts.series, values}], labels, opts));
  }
  function dataTable(series, labels, opts) {   // screen-reader equivalent of each chart
    const wrap = el("div", {class: "sr-only"});      // a <table> ignores width:1px; the div clips it
    const tb = el("table");
    tb.appendChild(el("caption", null, opts.label));
    const hr = el("tr"); hr.appendChild(el("th", null, "")); series.forEach((s) => hr.appendChild(el("th", {scope: "col"}, s.name)));
    tb.appendChild(hr);
    labels.forEach((l, i) => {
      const r = el("tr"); r.appendChild(el("th", {scope: "row"}, l));
      series.forEach((s) => r.appendChild(el("td", null, opts.fmt ? opts.fmt(s.values[i]) : nf(s.values[i])))); tb.appendChild(r);
    });
    wrap.appendChild(tb);
    return wrap;
  }


  // ---------------------------------------------------------------- funnel
  // Batch 010e: sales funnel from existing records only (the CRM has no deal
  // stages). Tiers: customers -> quotes sent (any quote past draft: sent,
  // accepted, declined or converted; there is no "sent" timestamp, so the
  // status is the evidence) -> quotes accepted (accepted or converted) ->
  // invoiced (every invoice) -> paid in full (invoice status "paid").
  // Counts cover every currency; amounts only the primary currency, so
  // currencies are never mixed. Conversion: tier 2 is the share of customers
  // who got at least one quote (same unit: customers); tiers 3-5 are the
  // share of the tier above. A zero denominator is null ("—"), never NaN or 0%.
  const SENT = ["sent", "accepted", "declined", "converted"], ACCEPTED = ["accepted", "converted"];
  const pct = (n, d) => (d > 0 ? n / d : null);
  function funnel(raw, primary) {
    const customers = raw.customers || [], quotes = raw.quotes || [], invoices = raw.invoices || [];
    const amt = (rows) => rows.filter((r) => r.currency === primary).reduce((a, r) => a + (r.total_minor || 0), 0);
    const sent = quotes.filter((q) => SENT.includes(q.status));
    const accepted = quotes.filter((q) => ACCEPTED.includes(q.status));
    const paid = invoices.filter((i) => i.status === "paid");
    const quoted = new Set(sent.map((q) => q.customer_id)).size;
    const tiers = [
      {key: "f_customers", count: customers.length, amount: null, conv: null},
      {key: "f_sent", count: sent.length, amount: amt(sent), conv: pct(quoted, customers.length), base: "customers", quoted},
      {key: "f_accepted", count: accepted.length, amount: amt(accepted), conv: pct(accepted.length, sent.length)},
      {key: "f_invoiced", count: invoices.length, amount: amt(invoices), conv: pct(invoices.length, accepted.length)},
      {key: "f_paid", count: paid.length, amount: amt(paid), conv: pct(paid.length, invoices.length)},
    ];
    return {primary, tiers};
  }
  const pf = (v) => (v == null ? t("none") : new Intl.NumberFormat(LOCALE[curLang()], {style: "percent", maximumFractionDigits: 1}).format(v));
  function renderFunnel(host, f) {
    clear(host);
    const list = el("ol", {class: "funnel", "aria-hidden": "true"});
    f.tiers.forEach((tr, i) => {
      const li = el("li", {class: "f-row"});
      const seg = el("div", {class: "f-seg f-seg-" + i});       // cone segment (rim + rounded base): dashboard.css
      const shape = el("div", {class: "f-tier f-tier-" + i});   // tapering gold body
      shape.appendChild(el("span", {class: "f-count"}, nf(tr.count)));
      seg.appendChild(shape); li.appendChild(seg);
      const info = el("div", {class: "f-info"});
      info.appendChild(el("span", {class: "f-name"}, t(tr.key)));
      info.appendChild(el("span", {class: "f-amt"}, tr.amount == null ? t("none") : money(tr.amount, f.primary)));
      if (i > 0) info.appendChild(el("span", {class: "f-conv"}, t(i === 1 ? "f_of_customers" : "f_of_prev", {p: pf(tr.conv)})));
      li.appendChild(info);
      list.appendChild(li);
    });
    host.appendChild(list);
    // screen-reader table (the visual list above is aria-hidden)
    const wrap = el("div", {class: "sr-only"}), tb = el("table");
    tb.appendChild(el("caption", null, t("funnel_title")));
    const hr = el("tr");
    ["f_tier", "f_count", "f_amount", "f_conv"].forEach((k) => hr.appendChild(el("th", {scope: "col"}, t(k))));
    tb.appendChild(hr);
    f.tiers.forEach((tr, i) => {
      const r = el("tr"); r.appendChild(el("th", {scope: "row"}, t(tr.key)));
      r.appendChild(el("td", null, nf(tr.count)));
      r.appendChild(el("td", null, tr.amount == null ? t("none") : money(tr.amount, f.primary)));
      r.appendChild(el("td", null, i === 0 ? t("none") : t(i === 1 ? "f_of_customers" : "f_of_prev", {p: pf(tr.conv)})));
      tb.appendChild(r);
    });
    wrap.appendChild(tb); host.appendChild(wrap);
  }

  // ---------------------------------------------------------------- render
  function txt(id, s) { const n = $id(id); if (n) n.textContent = s; }
  function render() {
    const root = $id("tab-overview"); if (!root) return;
    document.querySelectorAll("[data-dash-i18n]").forEach((n) => { n.textContent = t(n.dataset.dashI18n); });
    document.querySelectorAll("[data-dash-i18n-title]").forEach((n) => { n.title = t(n.dataset.dashI18nTitle); });
    root.classList.toggle("is-loading", loading && !data);
    txt("ov-status", failed ? t("load_error") : (loading && !data ? t("loading") : (loadedAt ? t("updated", {t: new Intl.DateTimeFormat(LOCALE[curLang()], {hour: "numeric", minute: "2-digit"}).format(loadedAt)}) : "")));
    $id("ov-status").classList.toggle("is-error", failed);
    const d = data, none = t("none");
    if (!d) { ["kpi-paid", "kpi-customers", "kpi-upcoming", "kpi-open", "kpi-quotes", "kpi-drafts", "kpi-rating"].forEach((i) => txt(i, none)); return; }
    const p0 = d.paid[0];
    txt("kpi-paid", p0 ? money(p0.paid_minor, p0.currency) : none);
    txt("kpi-paid-sub", d.paid.length > 1 ? t("kpi_paid_other", {list: d.paid.slice(1).map((p) => money(p.paid_minor, p.currency)).join(" · ")}) : t("kpi_paid_sub"));
    txt("kpi-customers", nf(d.customers));
    txt("kpi-upcoming", nf(d.upcoming));
    txt("kpi-open", d.openCount ? (d.openPrimary ? money(d.openPrimary.total_minor, d.primary) : nf(d.openCount)) : none);
    txt("kpi-open-sub", d.openCount ? t("kpi_open_inv_sub", {n: nf(d.openCount)}) : t("no_data"));
    txt("kpi-customers-sub", t("kpi_customers_sub", {n: nf(d.lapsed)}));
    const qs = d.quotesSent, qp = qs.filter((q) => q.currency === d.primary);
    txt("kpi-quotes", qs.length ? (qp.length ? money(qp.reduce((a, q) => a + q.total_minor, 0), d.primary) : nf(qs.length)) : none);
    txt("kpi-quotes-sub", qs.length ? t("kpi_open_quotes_sub", {n: nf(qs.length)}) : t("no_data"));
    txt("kpi-drafts", nf(d.drafts));
    txt("kpi-rating", d.rating == null ? none : nf(d.rating) + " / 5");
    const ml = d.months.map(monthLabel);
    txt("chart-billing-note", t("chart_billing_note", {cur: d.primary}));
    areaLine($id("chart-billing"), [{name: t("series_invoiced"), values: d.inv, area: true}, {name: t("series_paid"), values: d.pif}],
             ml, {id: "billing", label: t("chart_billing"), fmt: (v) => money(v, d.primary)});
    areaLine($id("chart-customers"), [{name: t("kpi_customers"), values: d.custSeries, area: true}], ml,
             {id: "cust", label: t("chart_customers")});
    bars($id("chart-bookings"), d.wk, d.weeks.map(dayLabel), {label: t("chart_bookings"), series: t("kpi_upcoming")});
    renderFunnel($id("chart-funnel"), d.funnel);
    txt("funnel-note", t("funnel_note", {cur: d.primary}));
  }

  window.MQDash = {load, render, t, T, funnel};
  // re-render on language change and load on sign-in, without changing app.js logic
  // Re-render the visible tab's lists in the new language (read-only GETs).
  const LOADERS = {customers: [], bookings: ["loadReminders", "loadBookings"],
    billing: ["loadQuotes", "loadInvoices"], messages: ["loadMessages"],
    comeback: ["loadLapsed"], reports: ["loadSummary"], overview: []};
  function reloadVisible() {
    if (typeof me === "undefined" || !me) return;
    const act = document.querySelector(".tab.active");
    const names = (act && LOADERS[act.dataset.tab]) || [];
    const calls = (typeof refreshSelects === "function" ? [refreshSelects] : [])
      .concat(names.map((n) => window[n] || (typeof globalThis[n] === "function" ? globalThis[n] : null)).filter(Boolean));
    calls.forEach((fn) => { try { const r = fn(); if (r && r.catch) r.catch(() => {}); } catch (e) { /* ignore */ } });
  }
  if (typeof applyLang === "function") {
    const orig = applyLang;
    applyLang = function () { orig(); render(); reloadVisible(); };   // eslint-disable-line no-global-assign
  }
  if (typeof setSignedIn === "function") {
    const origIn = setSignedIn;
    setSignedIn = function (user, csrf) { origIn(user, csrf); load(); };   // eslint-disable-line no-global-assign
  }
  const tab = document.querySelector('.tab[data-tab="overview"]');
  if (tab) tab.addEventListener("click", load);
  const rb = $id("ov-refresh"); if (rb) rb.addEventListener("click", load);
  render();
})();
