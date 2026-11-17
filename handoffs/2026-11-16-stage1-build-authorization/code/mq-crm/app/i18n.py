"""M&Q CRM — four-language strings (EN/ES/PT/HT) for UI and message templates.

Parity is a product rule, not a nicety: all four key sets must be identical
(enforced by tests/test_i18n_parity.py). Four first-class languages per the
founder directive of Nov 17, 2026 — language is the purpose, not an
accessory. A fifth language is a configuration change here, not a rewrite.
PT/HT strings are authored and await native-speaker review (standing rule).
"""

UI = {
    "en": {
        "app_title": "M&Q CRM",
        "customers": "Customers",
        "bookings": "Bookings",
        "billing": "Quotes & Invoices",
        "comeback": "Comeback",
        "messages": "Messages",
        "reports": "Reports",
        "data_rights": "Your Data Is Yours",
        "add_customer": "Add customer",
        "name": "Name",
        "phone": "Phone",
        "email": "Email",
        "language": "Language",
        "save": "Save",
        "export_all": "Export all data",
        "import_backlog": "Import lapsed list",
        "lapsed_customers": "Lapsed customers",
        "open_invoices": "Open invoices",
        "draft_needs_approval": "Draft — a human must approve before sending",
        "approve": "Approve",
        "send": "Send",
        "new_booking": "New booking",
        "title": "Title",
        "when": "Date & time",
        "create_quote": "Create quote",
        "add_item": "Add item",
        "description": "Description",
        "qty": "Qty",
        "amount_cents": "Amount (cents)",
        "total": "Total",
        "compose": "Compose",
        "template": "Template",
        "review_request": "Request review",
        "referral_code": "Referral code",
        "record_payment": "Record payment",
        "convert_invoice": "Convert to invoice",
    },
    "es": {
        "app_title": "M&Q CRM",
        "customers": "Clientes",
        "bookings": "Reservas",
        "billing": "Cotizaciones y facturas",
        "comeback": "Recuperación",
        "messages": "Mensajes",
        "reports": "Informes",
        "data_rights": "Tus datos son tuyos",
        "add_customer": "Agregar cliente",
        "name": "Nombre",
        "phone": "Teléfono",
        "email": "Correo electrónico",
        "language": "Idioma",
        "save": "Guardar",
        "export_all": "Exportar todos los datos",
        "import_backlog": "Importar lista de clientes inactivos",
        "lapsed_customers": "Clientes inactivos",
        "open_invoices": "Facturas abiertas",
        "draft_needs_approval": "Borrador — una persona debe aprobar antes de enviar",
        "approve": "Aprobar",
        "send": "Enviar",
        "new_booking": "Nueva reserva",
        "title": "Título",
        "when": "Fecha y hora",
        "create_quote": "Crear cotización",
        "add_item": "Agregar artículo",
        "description": "Descripción",
        "qty": "Cant.",
        "amount_cents": "Cantidad (centavos)",
        "total": "Total",
        "compose": "Redactar",
        "template": "Plantilla",
        "review_request": "Pedir reseña",
        "referral_code": "Código de referido",
        "record_payment": "Registrar pago",
        "convert_invoice": "Convertir a factura",
    },
    "pt": {
        "app_title": "M&Q CRM",
        "customers": "Clientes",
        "bookings": "Agendamentos",
        "billing": "Orçamentos e faturas",
        "comeback": "Recuperação",
        "messages": "Mensagens",
        "reports": "Relatórios",
        "data_rights": "Seus dados são seus",
        "add_customer": "Adicionar cliente",
        "name": "Nome",
        "phone": "Telefone",
        "email": "E-mail",
        "language": "Idioma",
        "save": "Salvar",
        "export_all": "Exportar todos os dados",
        "import_backlog": "Importar lista de clientes inativos",
        "lapsed_customers": "Clientes inativos",
        "open_invoices": "Faturas abertas",
        "draft_needs_approval": "Rascunho — uma pessoa deve aprovar antes de enviar",
        "approve": "Aprovar",
        "send": "Enviar",
        "new_booking": "Novo agendamento",
        "title": "Título",
        "when": "Data e hora",
        "create_quote": "Criar orçamento",
        "add_item": "Adicionar item",
        "description": "Descrição",
        "qty": "Qtd.",
        "amount_cents": "Valor (centavos)",
        "total": "Total",
        "compose": "Escrever",
        "template": "Modelo",
        "review_request": "Pedir avaliação",
        "referral_code": "Código de indicação",
        "record_payment": "Registrar pagamento",
        "convert_invoice": "Converter em fatura",
    },
    "ht": {
        "app_title": "M&Q CRM",
        "customers": "Kliyan",
        "bookings": "Randevou",
        "billing": "Estimasyon ak fakti",
        "comeback": "Rekipere kliyan",
        "messages": "Mesaj",
        "reports": "Rapò",
        "data_rights": "Done ou se done ou",
        "add_customer": "Ajoute kliyan",
        "name": "Non",
        "phone": "Telefòn",
        "email": "Imèl",
        "language": "Lang",
        "save": "Anrejistre",
        "export_all": "Ekspòte tout done yo",
        "import_backlog": "Enpòte lis kliyan ki pa aktif",
        "lapsed_customers": "Kliyan ki pa aktif",
        "open_invoices": "Fakti ki louvri",
        "draft_needs_approval": "Bouyon — yon moun dwe apwouve anvan ou voye l",
        "approve": "Apwouve",
        "send": "Voye",
        "new_booking": "Nouvo randevou",
        "title": "Tit",
        "when": "Dat ak lè",
        "create_quote": "Kreye estimasyon",
        "add_item": "Ajoute atik",
        "description": "Deskripsyon",
        "qty": "Kantite",
        "amount_cents": "Montan (santim)",
        "total": "Total",
        "compose": "Ekri",
        "template": "Modèl",
        "review_request": "Mande yon revizyon",
        "referral_code": "Kòd referans",
        "record_payment": "Anrejistre peman",
        "convert_invoice": "Konvèti an fakti",
    },
}

# Customer-facing message templates. Authored in both languages by a human;
# the customer's stored language preference selects the rendering. The
# original text is always preserved on the message record alongside any
# translation (see services/messages.py).
TEMPLATES = {
    "reminder": {
        "en": "Hello {name}, this is a reminder of your appointment on {when}: {title}. Reply if you need to reschedule.",
        "es": "Hola {name}, este es un recordatorio de su cita el {when}: {title}. Responda si necesita cambiar la fecha.",
        "pt": "Olá {name}, este é um lembrete do seu compromisso em {when}: {title}. Responda se precisar remarcar.",
        "ht": "Bonjou {name}, sa se yon rapèl pou randevou ou a {when}: {title}. Reponn si ou bezwen chanje dat la.",
    },
    "quote_ready": {
        "en": "Hello {name}, your quote is ready: {summary}. Total: {total}. Questions? Just reply to this message.",
        "es": "Hola {name}, su cotización está lista: {summary}. Total: {total}. ¿Preguntas? Solo responda a este mensaje.",
        "pt": "Olá {name}, seu orçamento está pronto: {summary}. Total: {total}. Dúvidas? É só responder a esta mensagem.",
        "ht": "Bonjou {name}, estimasyon ou a pare: {summary}. Total: {total}. Ou gen kesyon? Reponn mesaj sa a sèlman.",
    },
    "invoice_ready": {
        "en": "Hello {name}, your invoice for {total} is ready. Thank you for your business.",
        "es": "Hola {name}, su factura por {total} está lista. Gracias por su confianza.",
        "pt": "Olá {name}, sua fatura de {total} está pronta. Obrigado pela preferência.",
        "ht": "Bonjou {name}, fakti ou a pou {total} pare. Mèsi pou konfyans ou.",
    },
    "comeback": {
        "en": "Hello {name}, we miss you! It has been a while since your last visit. We would love to see you again — reply to book.",
        "es": "Hola {name}, ¡lo extrañamos! Ha pasado un tiempo desde su última visita. Nos encantaría verlo de nuevo — responda para reservar.",
        "pt": "Olá {name}, sentimos sua falta! Já faz um tempo desde sua última visita. Adoraríamos vê-lo novamente — responda para agendar.",
        "ht": "Bonjou {name}, ou manke nou! Sa fè yon bon ti tan depi dènye vizit ou a. Nou ta renmen wè ou ankò — reponn pou ou rezève.",
    },
    "review_request": {
        "en": "Hello {name}, thank you for choosing us. Would you share a quick review? It helps neighbors find us.",
        "es": "Hola {name}, gracias por elegirnos. ¿Compartiría una breve reseña? Ayuda a que los vecinos nos encuentren.",
        "pt": "Olá {name}, obrigado por nos escolher. Você compartilharia uma avaliação rápida? Isso ajuda os vizinhos a nos encontrarem.",
        "ht": "Bonjou {name}, mèsi paske ou chwazi nou. Èske ou ta pataje yon ti revizyon? Sa ede vwazen yo jwenn nou.",
    },
}

# Four first-class languages (founder directive, Nov 17, 2026): EN · ES · PT · HT.
# PT/HT strings are authored for Stage 1 and carry the standing requirement of
# native-speaker review before any production claim — stated, not hidden.
SUPPORTED_LANGUAGES = ("en", "es", "pt", "ht")
DESIGNED_FOR_LANGUAGES = ()  # a fifth language remains a catalog entry, not a rewrite


def render(template_key: str, lang: str, **ctx) -> str:
    tpl = TEMPLATES[template_key]
    return tpl.get(lang, tpl["en"]).format(**ctx)


def format_money(amount_minor: int, currency: str = "USD") -> str:
    sign = "-" if amount_minor < 0 else ""
    major, minor = divmod(abs(amount_minor), 100)
    return f"{sign}{currency} {major:,}.{minor:02d}"
