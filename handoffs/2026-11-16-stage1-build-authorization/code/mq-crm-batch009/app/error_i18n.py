"""Batch 010b: server/API error messages in EN / ES / PT / HT.

TRANSLATIONS: PT (pt-BR) and HT (Kreyòl ayisyen) are PENDING NATIVE REVIEW.
ES is a careful machine-assisted translation; also worth a native read.

How it works (presentation only, no auth change):
- ErrorLanguageMiddleware is the OUTERMOST /api middleware. For an error
  response (status >= 400) whose JSON body has a string "detail", it swaps
  the English text for the caller's language and adds "detail_en" (the
  original, a stable value for clients that compare strings).
- Everything else is untouched: status code, every header (Retry-After,
  WWW-Authenticate, Set-Cookie, Cache-Control), CSRF / cookie behaviour,
  and the order checks run in. English requests pass through byte for byte.
- Language, first match wins: ?lang=xx, then the X-MQ-Lang header (the web
  UI sends its current language), then Accept-Language; otherwise English.
- The login failure stays ONE generic message per language: the catalog
  has a single entry for it, so wrong user and wrong password still read
  the same and nothing reveals whether an account exists.
- Unknown messages stay English (and get no detail_en), never an error.
- Values inside a message (statuses, names, paths, env-var names) are kept
  as they are; they are codes, not prose.
"""
from __future__ import annotations

import json
import re
from urllib.parse import parse_qs

SUPPORTED = ("en", "es", "pt", "ht")

_HELP = {
    "en": "local_start must be an ISO date or date-time, e.g. 2026-12-02, 2026-12-02 10:30 or 2026-12-02T10:30:00-05:00",
    "es": "local_start debe ser una fecha o fecha y hora ISO, p. ej. 2026-12-02, 2026-12-02 10:30 o 2026-12-02T10:30:00-05:00",
    "pt": "local_start deve ser uma data ou data e hora ISO, ex.: 2026-12-02, 2026-12-02 10:30 ou 2026-12-02T10:30:00-05:00",
    "ht": "local_start dwe yon dat oswa yon dat ak lè ISO, pa egzanp 2026-12-02, 2026-12-02 10:30 oswa 2026-12-02T10:30:00-05:00",
}

# (english template, es, pt, ht). {name} = a value carried over unchanged.
CATALOG: list[tuple[str, str, str, str]] = [
    # ---- sign-in, session, CSRF, roles (status codes are set elsewhere and never change)
    ("invalid username or password",
     "usuario o contraseña incorrectos",
     "usuário ou senha incorretos",
     "non itilizatè a oswa modpas la pa bon"),
    ("too many failed sign-in attempts — try again later",
     "demasiados intentos fallidos de inicio de sesión: inténtalo más tarde",
     "muitas tentativas de login sem sucesso: tente novamente mais tarde",
     "twòp tantativ koneksyon ki echwe: eseye ankò pita"),
    ("login required — sign in to get a session",
     "se requiere iniciar sesión: inicia sesión para obtener una sesión",
     "é necessário fazer login: entre para obter uma sessão",
     "ou dwe konekte: konekte pou w jwenn yon sesyon"),
    ("login required — the audit trail must name who acted",
     "se requiere iniciar sesión: el registro de auditoría debe indicar quién actuó",
     "é necessário fazer login: o registro de auditoria deve indicar quem agiu",
     "ou dwe konekte: jounal odit la dwe di kiyès ki fè aksyon an"),
    ("login required",
     "se requiere iniciar sesión",
     "é necessário fazer login",
     "ou dwe konekte"),
    ("cross-site request refused",
     "solicitud entre sitios rechazada",
     "solicitação entre sites recusada",
     "nou refize demann ki soti nan yon lòt sit"),
    ("CSRF token missing or invalid",
     "falta el token CSRF o no es válido",
     "token CSRF ausente ou inválido",
     "jeton CSRF la manke oswa li pa valab"),
    ("role may not modify data",
     "este rol no puede modificar datos",
     "esta função não pode alterar dados",
     "wòl sa a pa ka chanje done"),
    ("owner role required",
     "se requiere el rol de propietario",
     "é necessária a função de proprietário",
     "se sèl wòl pwopriyetè a ki ka fè sa"),
    ("mode must be cookie or token",
     "mode debe ser cookie o token",
     "mode deve ser cookie ou token",
     "mode dwe cookie oswa token"),
    ("current password is incorrect",
     "la contraseña actual es incorrecta",
     "a senha atual está incorreta",
     "modpas aktyèl la pa bon"),
    ("owner passwords are reset only with the server CLI (python -m app.auth_cli reset-password)",
     "las contraseñas del propietario solo se restablecen con la CLI del servidor (python -m app.auth_cli reset-password)",
     "as senhas do proprietário só são redefinidas pela CLI do servidor (python -m app.auth_cli reset-password)",
     "modpas pwopriyetè a chanje sèlman ak CLI sèvè a (python -m app.auth_cli reset-password)"),
    # ---- two-step login
    ("sign-in step expired or invalid — sign in with your password again",
     "el paso de inicio de sesión expiró o no es válido: vuelve a iniciar sesión con tu contraseña",
     "a etapa de login expirou ou é inválida: entre novamente com sua senha",
     "etap koneksyon an ekspire oswa li pa valab: konekte ankò ak modpas ou"),
    ("invalid code",
     "código no válido",
     "código inválido",
     "kòd la pa valab"),
    ("send exactly one of code or recovery_code",
     "envía exactamente uno: code o recovery_code",
     "envie exatamente um: code ou recovery_code",
     "voye youn sèlman: code oswa recovery_code"),
    ("send one of code or recovery_code",
     "envía uno: code o recovery_code",
     "envie um: code ou recovery_code",
     "voye youn: code oswa recovery_code"),
    ("two-step login is available for the owner role",
     "el inicio de sesión en dos pasos está disponible para el rol de propietario",
     "o login em duas etapas está disponível para a função de proprietário",
     "koneksyon an de etap disponib pou wòl pwopriyetè a"),
    ("two-step login is already enabled — disable it first to enroll a new device",
     "el inicio de sesión en dos pasos ya está activado: desactívalo primero para registrar otro dispositivo",
     "o login em duas etapas já está ativado: desative-o primeiro para cadastrar outro dispositivo",
     "koneksyon an de etap deja aktive: dezaktive l anvan pou w anrejistre yon lòt aparèy"),
    ("no pending two-step enrollment — start one first",
     "no hay un registro de dos pasos pendiente: inicia uno primero",
     "não há cadastro de duas etapas pendente: inicie um primeiro",
     "pa gen enskripsyon de etap k ap tann: kòmanse youn anvan"),
    ("that code is not valid — check the device clock and enter the current 6-digit code",
     "ese código no es válido: revisa la hora del dispositivo e ingresa el código actual de 6 dígitos",
     "esse código não é válido: verifique o relógio do dispositivo e digite o código atual de 6 dígitos",
     "kòd sa a pa valab: tcheke lè aparèy la epi antre kòd 6 chif ki la kounye a"),
    ("two-step login is not enabled",
     "el inicio de sesión en dos pasos no está activado",
     "o login em duas etapas não está ativado",
     "koneksyon an de etap pa aktive"),
    ("password and a valid code are both required",
     "se requieren la contraseña y un código válido",
     "são necessários a senha e um código válido",
     "ou bezwen modpas la ak yon kòd ki valab"),
    ("two-step key does not match this database — restore the right key, or use the CLI break-glass reset-totp",
     "la clave de dos pasos no coincide con esta base de datos: restaura la clave correcta o usa la recuperación de emergencia reset-totp de la CLI",
     "a chave de duas etapas não corresponde a este banco de dados: restaure a chave correta ou use o reset-totp de emergência da CLI",
     "kle de etap la pa koresponn ak baz done sa a: remete bon kle a, oswa sèvi ak reset-totp CLI a pou ijans"),
    ("two-step key missing: neither {a} nor {b} is present but this database holds enrolled two-step factors. Restore the key file from the backup taken with the database, or use the server-shell break-glass `python -m app.auth_cli reset-totp --username <name>`.",
     "falta la clave de dos pasos: no existe {a} ni {b}, pero esta base de datos tiene factores de dos pasos registrados. Restaura el archivo de clave desde la copia de seguridad hecha con la base de datos, o usa la recuperación de emergencia del servidor `python -m app.auth_cli reset-totp --username <name>`.",
     "chave de duas etapas ausente: não existe {a} nem {b}, mas este banco de dados tem fatores de duas etapas cadastrados. Restaure o arquivo da chave a partir do backup feito com o banco de dados, ou use a recuperação de emergência do servidor `python -m app.auth_cli reset-totp --username <name>`.",
     "kle de etap la manke: ni {a} ni {b} pa la, men baz done sa a gen faktè de etap ki anrejistre. Remete fichye kle a apati kopi sekirite ki te fèt ak baz done a, oswa sèvi ak solisyon ijans sèvè a `python -m app.auth_cli reset-totp --username <name>`."),
    # ---- passwords and users (owner-only user management)
    ("password required", "se requiere una contraseña", "a senha é obrigatória", "ou bezwen yon modpas"),
    ("password must be at least {n} characters",
     "la contraseña debe tener al menos {n} caracteres",
     "a senha deve ter pelo menos {n} caracteres",
     "modpas la dwe gen omwen {n} karaktè"),
    ("password must be at most {n} characters",
     "la contraseña debe tener como máximo {n} caracteres",
     "a senha deve ter no máximo {n} caracteres",
     "modpas la pa ka gen plis pase {n} karaktè"),
    ("password is too common", "la contraseña es demasiado común", "a senha é comum demais", "modpas la twò komen"),
    ("password needs more distinct characters",
     "la contraseña necesita más caracteres distintos",
     "a senha precisa de mais caracteres diferentes",
     "modpas la bezwen plis karaktè diferan"),
    ("password must not contain the username",
     "la contraseña no debe contener el nombre de usuario",
     "a senha não pode conter o nome de usuário",
     "modpas la pa dwe genyen non itilizatè a"),
    ("username must be 3-64 characters: lowercase letters, digits, '.', '_' or '-'",
     "el nombre de usuario debe tener de 3 a 64 caracteres: minúsculas, dígitos, '.', '_' o '-'",
     "o nome de usuário deve ter de 3 a 64 caracteres: letras minúsculas, dígitos, '.', '_' ou '-'",
     "non itilizatè a dwe gen 3 a 64 karaktè: lèt miniskil, chif, '.', '_' oswa '-'"),
    ("role must be owner, staff or viewer",
     "el rol debe ser owner, staff o viewer",
     "a função deve ser owner, staff ou viewer",
     "wòl la dwe owner, staff oswa viewer"),
    ("username already exists", "el nombre de usuario ya existe", "o nome de usuário já existe", "non itilizatè sa a deja egziste"),
    ("user not found", "usuario no encontrado", "usuário não encontrado", "nou pa jwenn itilizatè a"),
    ("cannot demote the last active owner",
     "no se puede quitar el rol al último propietario activo",
     "não é possível rebaixar o último proprietário ativo",
     "ou pa ka retire wòl dènye pwopriyetè aktif la"),
    ("cannot disable the last active owner",
     "no se puede desactivar al último propietario activo",
     "não é possível desativar o último proprietário ativo",
     "ou pa ka dezaktive dènye pwopriyetè aktif la"),
    ("an owner account already exists — bootstrap is one-time only; the owner manages users in the app",
     "ya existe una cuenta de propietario: la configuración inicial es de una sola vez; el propietario administra los usuarios en la app",
     "já existe uma conta de proprietário: a configuração inicial é feita uma única vez; o proprietário gerencia os usuários no app",
     "yon kont pwopriyetè deja egziste: premye konfigirasyon an fèt yon sèl fwa; pwopriyetè a jere itilizatè yo nan aplikasyon an"),
    # ---- bookings
    ("local_start is required — " + _HELP["en"], "local_start es obligatorio: " + _HELP["es"],
     "local_start é obrigatório: " + _HELP["pt"], "local_start obligatwa: " + _HELP["ht"]),
    ("local_start is not a real calendar date or time — " + _HELP["en"],
     "local_start no es una fecha u hora real del calendario: " + _HELP["es"],
     "local_start não é uma data ou hora real do calendário: " + _HELP["pt"],
     "local_start se pa yon vrè dat oswa yon vrè lè nan kalandriye a: " + _HELP["ht"]),
    (_HELP["en"], _HELP["es"], _HELP["pt"], _HELP["ht"]),
    ("tz is required (an IANA timezone, e.g. America/New_York)",
     "tz es obligatorio (una zona horaria IANA, p. ej. America/New_York)",
     "tz é obrigatório (um fuso horário IANA, ex.: America/New_York)",
     "tz obligatwa (yon zòn lè IANA, pa egzanp America/New_York)"),
    ("unknown timezone — use an IANA name such as America/New_York",
     "zona horaria desconocida: usa un nombre IANA como America/New_York",
     "fuso horário desconhecido: use um nome IANA como America/New_York",
     "nou pa konnen zòn lè sa a: sèvi ak yon non IANA tankou America/New_York"),
    ("booking not found", "reserva no encontrada", "agendamento não encontrado", "nou pa jwenn randevou a"),
    ("cannot cancel a booking with status {s}",
     "no se puede cancelar una reserva con estado {s}",
     "não é possível cancelar um agendamento com status {s}",
     "ou pa ka anile yon randevou ki gen estati {s}"),
    # ---- customers, reviews
    ("customer not found", "cliente no encontrado", "cliente não encontrado", "nou pa jwenn kliyan an"),
    ("name is required", "el nombre es obligatorio", "o nome é obrigatório", "non an obligatwa"),
    ("fields not editable: {f}", "campos no editables: {f}", "campos não editáveis: {f}", "chan ou pa ka modifye: {f}"),
    ("no fields to update", "no hay campos para actualizar", "não há campos para atualizar", "pa gen chan pou mete ajou"),
    ("unsupported language: {l}", "idioma no admitido: {l}", "idioma não suportado: {l}", "lang sa a pa sipòte: {l}"),
    ("contact detail belongs to customer {n} — One Record: merge instead of duplicating",
     "el dato de contacto pertenece al cliente {n}. Un solo registro: combina en lugar de duplicar",
     "o dado de contato pertence ao cliente {n}. Um só registro: mescle em vez de duplicar",
     "enfòmasyon kontak sa a se pou kliyan {n}. Yon sèl dosye: mete yo ansanm olye w double l"),
    ("rating must be 1..5", "la calificación debe ser de 1 a 5", "a avaliação deve ser de 1 a 5", "nòt la dwe ant 1 ak 5"),
    ("referral code not found", "código de referido no encontrado", "código de indicação não encontrado", "nou pa jwenn kòd referans lan"),
    # ---- billing
    ("qty must be positive and amount non-negative",
     "la cantidad debe ser positiva y el monto no puede ser negativo",
     "a quantidade deve ser positiva e o valor não pode ser negativo",
     "kantite a dwe pozitif epi montan an pa ka negatif"),
    ("invalid quote status {s}", "estado de cotización no válido {s}", "status de orçamento inválido {s}", "estati estimasyon an pa valab {s}"),
    ("quote not found", "cotización no encontrada", "orçamento não encontrado", "nou pa jwenn estimasyon an"),
    ("only an accepted quote converts to an invoice",
     "solo una cotización aceptada se convierte en factura",
     "só um orçamento aceito vira fatura",
     "se sèlman yon estimasyon ki aksepte ki ka tounen fakti"),
    ("invoice not found", "factura no encontrada", "fatura não encontrada", "nou pa jwenn fakti a"),
    ("payment must be positive", "el pago debe ser positivo", "o pagamento deve ser positivo", "peman an dwe pozitif"),
    # ---- messages and delivery
    ("message not found", "mensaje no encontrado", "mensagem não encontrada", "nou pa jwenn mesaj la"),
    ("customer has not consented to marketing messages — compose refused",
     "el cliente no aceptó mensajes de marketing: no se puede redactar",
     "o cliente não consentiu mensagens de marketing: composição recusada",
     "kliyan an pa dakò resevwa mesaj maketing: nou refize ekri l"),
    ("purpose must be one of {p} (or omitted, which holds the message for review)",
     "el propósito debe ser uno de {p} (u omitirse, lo que retiene el mensaje para revisión)",
     "a finalidade deve ser uma de {p} (ou omitida, o que retém a mensagem para revisão)",
     "objektif la dwe youn nan {p} (oswa kite l vid, sa ap kenbe mesaj la pou revizyon)"),
    ("purpose must be one of {p}", "el propósito debe ser uno de {p}", "a finalidade deve ser uma de {p}", "objektif la dwe youn nan {p}"),
    ("this message's purpose cannot be classified by an operator",
     "un operador no puede clasificar el propósito de este mensaje",
     "a finalidade desta mensagem não pode ser classificada por um operador",
     "yon operatè pa ka klase objektif mesaj sa a"),
    ("cannot classify a message in status {s}",
     "no se puede clasificar un mensaje con estado {s}",
     "não é possível classificar uma mensagem com status {s}",
     "ou pa ka klase yon mesaj ki gen estati {s}"),
    ("message already delivered or in flight — its classification is history",
     "el mensaje ya se entregó o está en camino: su clasificación ya es historial",
     "a mensagem já foi entregue ou está a caminho: sua classificação já é histórico",
     "mesaj la deja livre oswa l ap prale: klasman li se istwa kounye a"),
    ("a sent message cannot be altered",
     "un mensaje enviado no se puede modificar",
     "uma mensagem enviada não pode ser alterada",
     "ou pa ka chanje yon mesaj ki deja voye"),
    ("a reason is required to release a review hold",
     "se requiere un motivo para liberar una retención de revisión",
     "é necessário um motivo para liberar uma retenção de revisão",
     "ou bezwen yon rezon pou lage yon mesaj ki kenbe pou revizyon"),
    ("only a message held by the promotional-content screen can be released this way",
     "solo un mensaje retenido por el filtro de contenido promocional se puede liberar así",
     "só uma mensagem retida pelo filtro de conteúdo promocional pode ser liberada assim",
     "se sèlman yon mesaj filt kontni piblisite a kenbe ki ka lage konsa"),
    ("message state changed concurrently",
     "el estado del mensaje cambió al mismo tiempo",
     "o estado da mensagem mudou ao mesmo tempo",
     "eta mesaj la chanje an menm tan"),
    ("only a draft can be approved (status is {s})",
     "solo se puede aprobar un borrador (el estado es {s})",
     "só um rascunho pode ser aprovado (o status é {s})",
     "se sèlman yon bouyon ki ka apwouve (estati a se {s})"),
    ("translation pending — a human translation is required first",
     "traducción pendiente: primero se requiere una traducción humana",
     "tradução pendente: primeiro é necessária uma tradução humana",
     "tradiksyon an poko fèt: yon moun dwe tradui l anvan"),
    ("cannot withdraw a message in status {s}",
     "no se puede retirar un mensaje con estado {s}",
     "não é possível retirar uma mensagem com status {s}",
     "ou pa ka retire yon mesaj ki gen estati {s}"),
    ("cannot compose a reminder: the customer has no upcoming booking",
     "no se puede redactar un recordatorio: el cliente no tiene una próxima reserva",
     "não é possível compor um lembrete: o cliente não tem agendamento futuro",
     "ou pa ka ekri yon rapèl: kliyan an pa gen randevou k ap vini"),
    ("cannot compose a quote message: the customer has no quote",
     "no se puede redactar un mensaje de cotización: el cliente no tiene cotización",
     "não é possível compor uma mensagem de orçamento: o cliente não tem orçamento",
     "ou pa ka ekri yon mesaj estimasyon: kliyan an pa gen estimasyon"),
    ("cannot compose a quote message: the quote has no items",
     "no se puede redactar un mensaje de cotización: la cotización no tiene artículos",
     "não é possível compor uma mensagem de orçamento: o orçamento não tem itens",
     "ou pa ka ekri yon mesaj estimasyon: estimasyon an pa gen atik"),
    ("cannot compose an invoice message: the customer has no invoice",
     "no se puede redactar un mensaje de factura: el cliente no tiene factura",
     "não é possível compor uma mensagem de fatura: o cliente não tem fatura",
     "ou pa ka ekri yon mesaj fakti: kliyan an pa gen fakti"),
    # policy refusal reasons (used after "send refused: " / "dispatch refused: ")
    ("message is '{s}', a human must approve first",
     "el mensaje está en '{s}': una persona debe aprobarlo primero",
     "a mensagem está em '{s}': uma pessoa precisa aprovar primeiro",
     "mesaj la nan '{s}': yon moun dwe apwouve l anvan"),
    ("translation still pending — approval was not legitimately reachable for this message",
     "la traducción sigue pendiente: este mensaje no podía aprobarse legítimamente",
     "a tradução ainda está pendente: esta mensagem não podia ser aprovada legitimamente",
     "tradiksyon an toujou poko fèt: mesaj sa a pa t ka apwouve nòmalman"),
    ("content differs from the approved version (approval is bound to the exact text)",
     "el contenido no coincide con la versión aprobada (la aprobación está ligada al texto exacto)",
     "o conteúdo difere da versão aprovada (a aprovação está ligada ao texto exato)",
     "kontni an pa menm ak vèsyon ki apwouve a (apwobasyon an mache ak tèks egzak la)"),
    ("concurrent send in progress", "ya hay un envío en curso al mismo tiempo", "já há um envio simultâneo em andamento", "gen yon lòt voye k ap fèt an menm tan"),
    ("message is held for review: its purpose is unclear or unset",
     "el mensaje está retenido para revisión: su propósito no está claro o no está definido",
     "a mensagem está retida para revisão: a finalidade não está clara ou não foi definida",
     "mesaj la kenbe pou revizyon: objektif li pa klè oswa li pa defini"),
    ("message is held for review: promotional content in a transactional message ({h})",
     "el mensaje está retenido para revisión: contenido promocional en un mensaje transaccional ({h})",
     "a mensagem está retida para revisão: conteúdo promocional em uma mensagem transacional ({h})",
     "mesaj la kenbe pou revizyon: gen kontni piblisite nan yon mesaj tranzaksyonèl ({h})"),
    ("message is held for review ({r})",
     "el mensaje está retenido para revisión ({r})",
     "a mensagem está retida para revisão ({r})",
     "mesaj la kenbe pou revizyon ({r})"),
    ("customer no longer exists", "el cliente ya no existe", "o cliente não existe mais", "kliyan an pa egziste ankò"),
    ("contact is on the do-not-message list for marketing (a retained opt-out)",
     "el contacto está en la lista de no enviar mensajes de marketing (una baja conservada)",
     "o contato está na lista de não enviar mensagens de marketing (um descadastro mantido)",
     "kontak la sou lis pa voye mesaj maketing (yon dezabònman ki kenbe)"),
    ("contact is on the do-not-message list for {c} (a retained opt-out)",
     "el contacto está en la lista de no enviar mensajes por {c} (una baja conservada)",
     "o contato está na lista de não enviar mensagens por {c} (um descadastro mantido)",
     "kontak la sou lis pa voye mesaj pa {c} (yon dezabònman ki kenbe)"),
    ("opt-out confirmation is no longer valid: it belongs to an opt-out event that is not the customer's active one",
     "la confirmación de baja ya no es válida: pertenece a una baja que no es la activa del cliente",
     "a confirmação de descadastro não é mais válida: pertence a um descadastro que não é o ativo do cliente",
     "konfimasyon dezabònman an pa valab ankò: li pou yon dezabònman ki pa sa kliyan an genyen kounye a"),
    ("customer has opted out of {c} — only the one-time opt-out confirmation may be sent on this channel",
     "el cliente se dio de baja de {c}: por este canal solo se puede enviar la confirmación única de baja",
     "o cliente se descadastrou de {c}: neste canal só pode ser enviada a confirmação única de descadastro",
     "kliyan an dezabòne nan {c}: sou kanal sa a, se sèlman konfimasyon dezabònman an yon sèl fwa ki ka voye"),
    ("customer consent is not current for marketing messages",
     "el consentimiento del cliente para mensajes de marketing no está vigente",
     "o consentimento do cliente para mensagens de marketing não está em vigor",
     "konsantman kliyan an pou mesaj maketing pa valab kounye a"),
    ("endpoint host '{h}' has no processing-register entry with terms reviewed — the privacy rule requires terms review before any customer message leaves through an external provider",
     "el host '{h}' no tiene una entrada en el registro de tratamiento con términos revisados: la regla de privacidad exige revisar los términos antes de que un mensaje de cliente salga por un proveedor externo",
     "o host '{h}' não tem registro de tratamento com termos revisados: a regra de privacidade exige revisar os termos antes que qualquer mensagem de cliente saia por um provedor externo",
     "sèvè '{h}' la pa gen antre nan rejis tretman an ak kondisyon ki revize: règ vi prive a mande pou revize kondisyon yo anvan nenpòt mesaj kliyan soti pa yon founisè deyò"),
    ("message is '{s}' — only a sent message can be dispatched",
     "el mensaje está en '{s}': solo un mensaje enviado se puede despachar",
     "a mensagem está em '{s}': só uma mensagem enviada pode ser despachada",
     "mesaj la nan '{s}': se sèlman yon mesaj ki voye ki ka ekspedye"),
    ("message is no longer in 'sent' state",
     "el mensaje ya no está en estado 'sent'",
     "a mensagem não está mais no estado 'sent'",
     "mesaj la pa nan eta 'sent' ankò"),
    ("dispatch already in progress for this message — not sent twice",
     "ya hay un despacho en curso para este mensaje: no se envía dos veces",
     "já há um despacho em andamento para esta mensagem: não é enviada duas vezes",
     "gen yon ekspedisyon k ap fèt deja pou mesaj sa a: li p ap voye de fwa"),
    ("provider returned HTTP {n}", "el proveedor respondió HTTP {n}", "o provedor respondeu HTTP {n}", "founisè a reponn HTTP {n}"),
    ("webhook transport selected but MQ_CRM_WEBHOOK_URL is not configured",
     "se eligió el transporte webhook, pero MQ_CRM_WEBHOOK_URL no está configurado",
     "o transporte webhook foi escolhido, mas MQ_CRM_WEBHOOK_URL não está configurado",
     "ou chwazi transpò webhook la, men MQ_CRM_WEBHOOK_URL pa konfigire"),
    ("unknown transport '{t}'", "transporte desconocido '{t}'", "transporte desconhecido '{t}'", "nou pa konnen transpò '{t}' la"),
    # ---- opt-outs and suppression key (operator messages; paths kept as-is)
    ("channel must be one of {c}", "el canal debe ser uno de {c}", "o canal deve ser um de {c}", "kanal la dwe youn nan {c}"),
    ("no active {c} opt-out for this customer",
     "este cliente no tiene una baja activa de {c}",
     "este cliente não tem descadastro ativo de {c}",
     "kliyan sa a pa gen yon dezabònman {c} ki aktif"),
    ("suppression key file {p} is empty — restore it from its backup (see {d})",
     "el archivo de clave de supresión {p} está vacío: restáuralo desde su copia de seguridad (ver {d})",
     "o arquivo da chave de supressão {p} está vazio: restaure-o a partir do backup (veja {d})",
     "fichye kle sipresyon {p} la vid: remete l apati kopi sekirite li (gade {d})"),
    ("suppression key mismatch: the key from {s} does not match the key check stored in this database. Retained do-not-message records cannot be verified, so sending is refused. Restore the matching key from its backup — see {d}.",
     "la clave de supresión no coincide: la clave de {s} no coincide con la verificación guardada en esta base de datos. No se pueden verificar los registros de no enviar mensajes conservados, así que se rechaza el envío. Restaura la clave correcta desde su copia de seguridad; ver {d}.",
     "a chave de supressão não confere: a chave de {s} não corresponde à verificação guardada neste banco de dados. Os registros de não enviar mensagens mantidos não podem ser verificados, então o envio é recusado. Restaure a chave correta a partir do backup; veja {d}.",
     "kle sipresyon an pa koresponn: kle ki soti nan {s} pa menm ak verifikasyon ki nan baz done sa a. Nou pa ka verifye dosye pa voye mesaj ki kenbe yo, kidonk nou refize voye. Remete bon kle a apati kopi sekirite li; gade {d}."),
    ("suppression key missing: this database already holds a suppression key check and/or retained do-not-message records, but neither {e} nor the key file {p} is present. Refusing to generate a new key (that would silently stop honouring retained opt-outs). Restore the key from its backup — see {d}.",
     "falta la clave de supresión: esta base de datos ya tiene una verificación de clave de supresión o registros de no enviar mensajes conservados, pero no existe {e} ni el archivo de clave {p}. No se generará una clave nueva (eso dejaría de respetar en silencio las bajas conservadas). Restaura la clave desde su copia de seguridad; ver {d}.",
     "chave de supressão ausente: este banco de dados já tem uma verificação de chave de supressão ou registros de não enviar mensagens mantidos, mas não existe {e} nem o arquivo da chave {p}. Uma nova chave não será gerada (isso deixaria de respeitar, em silêncio, os descadastros mantidos). Restaure a chave a partir do backup; veja {d}.",
     "kle sipresyon an manke: baz done sa a deja gen yon verifikasyon kle sipresyon oswa dosye pa voye mesaj ki kenbe, men ni {e} ni fichye kle {p} la pa la. Nou p ap kreye yon nouvo kle (sa t ap fè nou sispann respekte dezabònman ki kenbe yo san moun pa konnen). Remete kle a apati kopi sekirite li; gade {d}."),
    # ---- comeback import, processing register, data rights, audit
    ("CSV must have columns: name, phone, email, language, last_service_date",
     "el CSV debe tener las columnas: name, phone, email, language, last_service_date",
     "o CSV deve ter as colunas: name, phone, email, language, last_service_date",
     "CSV a dwe gen kolòn sa yo: name, phone, email, language, last_service_date"),
    ("data_kind and provider are required", "data_kind y provider son obligatorios", "data_kind e provider são obrigatórios", "data_kind ak provider obligatwa"),
    ("endpoint must be an http(s) URL", "endpoint debe ser una URL http(s)", "endpoint deve ser uma URL http(s)", "endpoint dwe yon URL http(s)"),
    ("processing register entry not found",
     "entrada del registro de tratamiento no encontrada",
     "registro de tratamento não encontrado",
     "nou pa jwenn antre nan rejis tretman an"),
    ("terms_reference is required to record a review (which terms — document, URL or version)",
     "terms_reference es obligatorio para registrar una revisión (qué términos: documento, URL o versión)",
     "terms_reference é obrigatório para registrar uma revisão (quais termos: documento, URL ou versão)",
     "terms_reference obligatwa pou anrejistre yon revizyon (ki kondisyon: dokiman, URL oswa vèsyon)"),
    ("an http(s) endpoint is required to record a review — the review binds to that endpoint",
     "se requiere un endpoint http(s) para registrar una revisión: la revisión queda ligada a ese endpoint",
     "é necessário um endpoint http(s) para registrar uma revisão: a revisão fica ligada a esse endpoint",
     "ou bezwen yon endpoint http(s) pou anrejistre yon revizyon: revizyon an mache ak endpoint sa a"),
    ("a delivery for this customer is in flight — retry once it settles",
     "hay una entrega en curso para este cliente: vuelve a intentarlo cuando termine",
     "há uma entrega em andamento para este cliente: tente novamente quando terminar",
     "gen yon livrezon k ap fèt pou kliyan sa a: eseye ankò lè l fini"),
    ("deletion refused: connection has an open transaction — nothing was changed",
     "eliminación rechazada: la conexión tiene una transacción abierta; no se cambió nada",
     "exclusão recusada: a conexão tem uma transação aberta; nada foi alterado",
     "nou refize efase: koneksyon an gen yon tranzaksyon ki louvri; anyen pa chanje"),
    ("audit chain is intact — nothing to recover",
     "la cadena de auditoría está intacta: no hay nada que recuperar",
     "a cadeia de auditoria está íntegra: não há nada a recuperar",
     "chèn odit la an bon eta: pa gen anyen pou rekipere"),
    ("not found", "no encontrado", "não encontrado", "nou pa jwenn li"),
]

# "<stage> refused: <reason>": the stage word is translated, the reason recursively.
_PREFIXES = {
    "send refused: ": {"es": "envío rechazado: ", "pt": "envio recusado: ", "ht": "nou refize voye l: "},
    "dispatch refused: ": {"es": "despacho rechazado: ", "pt": "despacho recusado: ", "ht": "nou refize ekspedye l: "},
}


def _compile(template: str) -> tuple[re.Pattern, list[str]]:
    names, out, pos = [], [], 0
    for m in re.finditer(r"\{([a-z])\}", template):
        out.append(re.escape(template[pos:m.start()]))
        out.append(f"(?P<{m.group(1)}>.+?)")
        names.append(m.group(1)); pos = m.end()
    out.append(re.escape(template[pos:]))
    return re.compile("^" + "".join(out) + "$", re.S), names


_RULES = []
_seen = set()
for _en, _es, _pt, _ht in CATALOG:
    if _en in _seen or not (_es and _pt and _ht):
        continue
    _seen.add(_en)
    _rx, _ = _compile(_en)
    _RULES.append((_rx, {"es": _es, "pt": _pt, "ht": _ht}))


def translate(message: str, lang: str) -> str:
    """The message in `lang`, or the original when there is no entry."""
    if lang == "en" or lang not in SUPPORTED or not isinstance(message, str):
        return message
    for prefix, tr in _PREFIXES.items():
        if message.startswith(prefix):
            rest = message[len(prefix):]
            return tr[lang] + translate(rest, lang)
    for rx, tr in _RULES:
        m = rx.match(message)
        if m:
            out = tr[lang]
            for k, v in m.groupdict().items():
                out = out.replace("{" + k + "}", v)
            return out
    return message


def _norm(code: str | None) -> str | None:
    if not code:
        return None
    c = code.strip().lower().replace("_", "-").split("-")[0]
    return c if c in SUPPORTED else None


def choose_language(query_string: bytes, headers) -> str:
    """?lang= > X-MQ-Lang > Accept-Language (by q) > 'en'."""
    try:
        q = parse_qs(query_string.decode("latin-1"))
        lang = _norm((q.get("lang") or [None])[0])
        if lang:
            return lang
    except Exception:  # malformed query: just ignore it
        pass
    hdr = {}
    for k, v in headers:
        hdr.setdefault(k.lower(), v.decode("latin-1"))
    lang = _norm(hdr.get(b"x-mq-lang"))
    if lang:
        return lang
    best, best_q = None, 0.0
    for i, part in enumerate((hdr.get(b"accept-language") or "").split(",")[:20]):
        bits = part.strip().split(";")
        tag, qv = bits[0], 1.0
        for b in bits[1:]:
            if b.strip().startswith("q="):
                try:
                    qv = float(b.strip()[2:])
                except ValueError:
                    qv = 0.0
        code = _norm(tag)
        if code and qv > best_q:
            best, best_q = code, qv
    return best or "en"


class ErrorLanguageMiddleware:
    """Outermost /api ASGI middleware; see the module docstring."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api"):
            return await self.inner(scope, receive, send)
        lang = choose_language(scope.get("query_string") or b"", scope.get("headers") or [])
        if lang == "en":
            return await self.inner(scope, receive, send)   # untouched, byte for byte
        state = {"start": None, "chunks": []}

        async def _send(message):
            if message["type"] == "http.response.start":
                if message["status"] >= 400:
                    state["start"] = message
                    return
                return await send(message)
            if message["type"] == "http.response.body" and state["start"] is not None:
                state["chunks"].append(message.get("body", b""))
                if message.get("more_body"):
                    return
                start, body = state["start"], b"".join(state["chunks"])
                state["start"] = None
                headers = list(start.get("headers") or [])
                new = _translate_body(body, headers, lang)
                if new is not None:
                    body = new
                    headers = [(k, v) for k, v in headers if k.lower() != b"content-length"]
                    headers += [(b"content-length", str(len(body)).encode()),
                                (b"content-language", lang.encode()),
                                (b"vary", b"Accept-Language, X-MQ-Lang")]
                await send({**start, "headers": headers})
                await send({"type": "http.response.body", "body": body})
                return
            await send(message)

        await self.inner(scope, receive, _send)


def _translate_body(body: bytes, headers, lang: str) -> bytes | None:
    ctype = next((v for k, v in headers if k.lower() == b"content-type"), b"")
    if b"json" not in ctype:
        return None
    try:
        data = json.loads(body)
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("detail"), str):
        return None
    out = translate(data["detail"], lang)
    if out == data["detail"]:
        return None
    data["detail_en"] = data["detail"]
    data["detail"] = out
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
