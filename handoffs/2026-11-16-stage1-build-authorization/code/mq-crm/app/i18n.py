"""M&Q CRM — bilingual strings (EN/ES) for UI and message templates.

Parity is a product rule, not a nicety: EN and ES key sets must be identical
(enforced by tests/test_i18n_parity.py). PT and HT are designed-for in the
architecture (a fifth language is a configuration change here), not shipped
in Stage 1 — no capability is claimed beyond its evidence.
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
    },
    "quote_ready": {
        "en": "Hello {name}, your quote is ready: {summary}. Total: {total}. Questions? Just reply to this message.",
        "es": "Hola {name}, su cotización está lista: {summary}. Total: {total}. ¿Preguntas? Solo responda a este mensaje.",
    },
    "invoice_ready": {
        "en": "Hello {name}, your invoice for {total} is ready. Thank you for your business.",
        "es": "Hola {name}, su factura por {total} está lista. Gracias por su confianza.",
    },
    "comeback": {
        "en": "Hello {name}, we miss you! It has been a while since your last visit. We would love to see you again — reply to book.",
        "es": "Hola {name}, ¡lo extrañamos! Ha pasado un tiempo desde su última visita. Nos encantaría verlo de nuevo — responda para reservar.",
    },
    "review_request": {
        "en": "Hello {name}, thank you for choosing us. Would you share a quick review? It helps neighbors find us.",
        "es": "Hola {name}, gracias por elegirnos. ¿Compartiría una breve reseña? Ayuda a que los vecinos nos encuentren.",
    },
}

SUPPORTED_LANGUAGES = ("en", "es")          # shipped in Stage 1
DESIGNED_FOR_LANGUAGES = ("pt", "ht")       # architecture only — not claimed


def render(template_key: str, lang: str, **ctx) -> str:
    tpl = TEMPLATES[template_key]
    return tpl.get(lang, tpl["en"]).format(**ctx)


def format_money(amount_minor: int, currency: str = "USD") -> str:
    sign = "-" if amount_minor < 0 else ""
    major, minor = divmod(abs(amount_minor), 100)
    return f"{sign}{currency} {major:,}.{minor:02d}"
