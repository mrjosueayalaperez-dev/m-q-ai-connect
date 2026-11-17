package com.mq.crm.ui

import android.os.Handler
import android.os.Looper
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.mq.crm.BuildConfig
import com.mq.crm.R
import com.mq.crm.auth.Me
import com.mq.crm.auth.NoAuth
import com.mq.crm.auth.SessionManager
import com.mq.crm.auth.TokenStore
import com.mq.crm.data.*
import kotlinx.coroutines.launch

enum class Tab { CUSTOMERS, APPROVALS, SUMMARY, SETTINGS }

sealed interface AuthState {
    data object Checking : AuthState
    data object SignedOut : AuthState
    data class Unreachable(val message: String) : AuthState
    data class SignedIn(val me: Me) : AuthState
}

@Composable
fun CrmApp(settings: Settings, store: TokenStore, onLanguageChanged: () -> Unit) {
    var state by remember { mutableStateOf<AuthState>(AuthState.Checking) }
    var notice by remember { mutableStateOf<String?>(null) }
    var checkTick by remember { mutableIntStateOf(0) }
    val endedText = stringResource(R.string.session_ended)
    val main = remember { Handler(Looper.getMainLooper()) }
    // Any 401 from the server (expired or revoked session): SessionManager has
    // already cleared the token; return to the login screen.
    val session = remember {
        SessionManager(store, onUnauthorized = {
            main.post { state = AuthState.SignedOut; notice = endedText }
        })
    }

    LaunchedEffect(checkTick) {
        val url = Format.normalizeBaseUrl(settings.baseUrl)
        state = when {
            url == null || !session.hasToken() -> AuthState.SignedOut
            else -> try {
                session.restore(url)?.let { AuthState.SignedIn(it) } ?: AuthState.SignedOut
            } catch (e: Throwable) {
                AuthState.Unreachable(errorText(e))
            }
        }
    }

    when (val st = state) {
        AuthState.Checking -> Box(Modifier.fillMaxSize().background(Ink), contentAlignment = Alignment.Center) {
            CircularProgressIndicator(color = Gold)
        }
        is AuthState.Unreachable -> Scaffold(topBar = { TestOnlyBanner(null) }) { pad ->
            Column(Modifier.padding(pad).fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center) {
                Text(stringResource(R.string.error_title), color = MaterialTheme.colorScheme.error,
                    fontWeight = FontWeight.Bold)
                Text(st.message)
                Spacer(Modifier.height(12.dp))
                Button(onClick = { checkTick++ }) { Text(stringResource(R.string.retry)) }
                TextButton(onClick = { store.clear(); state = AuthState.SignedOut }) {
                    Text(stringResource(R.string.sign_out))
                }
            }
        }
        AuthState.SignedOut -> LoginScreen(
            settings = settings,
            session = session,
            notice = notice,
            onSignedIn = { me -> notice = null; state = AuthState.SignedIn(me) },
            onLanguageChanged = onLanguageChanged,
        )
        is AuthState.SignedIn -> SignedInApp(
            settings = settings,
            me = st.me,
            client = session.client(Format.normalizeBaseUrl(settings.baseUrl) ?: ""),
            session = session,
            onSignOut = { revoked ->
                notice = if (revoked) null else endedText
                state = AuthState.SignedOut
            },
            onLanguageChanged = onLanguageChanged,
        )
    }
}

@Composable
fun SignedInApp(
    settings: Settings,
    me: Me,
    client: ApiClient,
    session: SessionManager,
    onSignOut: (revoked: Boolean) -> Unit,
    onLanguageChanged: () -> Unit,
) {
    var tab by remember { mutableStateOf(Tab.CUSTOMERS) }
    var openCustomer by remember { mutableStateOf<Customer?>(null) }
    Scaffold(
        topBar = { TestOnlyBanner(me) },
        bottomBar = {
            NavigationBar(containerColor = Panel) {
                listOf(
                    Tab.CUSTOMERS to R.string.tab_customers,
                    Tab.APPROVALS to R.string.tab_approvals,
                    Tab.SUMMARY to R.string.tab_summary,
                    Tab.SETTINGS to R.string.tab_settings,
                ).forEach { (t, label) ->
                    NavigationBarItem(
                        selected = tab == t,
                        onClick = { tab = t; openCustomer = null },
                        icon = { Text(stringResource(label).take(1), fontWeight = FontWeight.Bold) },
                        label = { Text(stringResource(label), fontSize = 11.sp) },
                    )
                }
            }
        },
    ) { pad ->
        Box(Modifier.padding(pad).fillMaxSize()) {
            when (tab) {
                Tab.CUSTOMERS -> openCustomer?.let {
                    CustomerDetail(client, me, it, onBack = { openCustomer = null })
                } ?: CustomersScreen(client) { openCustomer = it }
                Tab.APPROVALS -> ApprovalsScreen(client, me)
                Tab.SUMMARY -> SummaryScreen(client, me)
                Tab.SETTINGS -> SettingsScreen(settings, me, session, onSignOut, onLanguageChanged)
            }
        }
    }
}

@Composable
fun TestOnlyBanner(me: Me?) {
    Column(
        Modifier.fillMaxWidth().background(Warn).padding(horizontal = 12.dp, vertical = 6.dp)
            .testTag("test_only_banner")
    ) {
        Text(stringResource(R.string.test_only_banner), color = androidx.compose.ui.graphics.Color.White,
            fontWeight = FontWeight.Bold, fontSize = 13.sp)
        Text((if (me == null) stringResource(R.string.not_signed_in)
              else stringResource(R.string.signed_in_as, me.label, me.role)) + " · v" + BuildConfig.VERSION_NAME,
            color = androidx.compose.ui.graphics.Color.White, fontSize = 11.sp)
    }
}

// ----------------------------------------------------------------- login

@Composable
fun LoginScreen(
    settings: Settings,
    session: SessionManager,
    notice: String?,
    onSignedIn: (Me) -> Unit,
    onLanguageChanged: () -> Unit,
) {
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var url by remember { mutableStateOf(settings.baseUrl) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val badUrl = stringResource(R.string.bad_url)
    val wrongCreds = stringResource(R.string.login_failed)
    val locked = stringResource(R.string.login_locked)
    Scaffold(topBar = { TestOnlyBanner(null) }, containerColor = Ink) { pad ->
        Column(
            Modifier.padding(pad).fillMaxSize().background(Ink).verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp, vertical = 16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(Modifier.height(8.dp))
            Box(Modifier.size(84.dp).background(Gold, CircleShape), contentAlignment = Alignment.Center) {
                Box(Modifier.size(76.dp).background(Ink, CircleShape), contentAlignment = Alignment.Center) {
                    Text("MQ", color = Gold, fontWeight = FontWeight.Black, fontSize = 30.sp)
                }
            }
            Spacer(Modifier.height(12.dp))
            Text(stringResource(R.string.app_name), color = Gold, fontSize = 28.sp, fontWeight = FontWeight.Bold)
            Text(stringResource(R.string.login_title), color = Cream, fontSize = 16.sp)
            Spacer(Modifier.height(16.dp))
            notice?.let {
                Text(it, color = Gold, textAlign = TextAlign.Center, modifier = Modifier.padding(bottom = 8.dp))
            }
            OutlinedTextField(username, { username = it }, label = { Text(stringResource(R.string.username)) },
                singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Ascii),
                modifier = Modifier.fillMaxWidth().testTag("username"))
            OutlinedTextField(password, { password = it }, label = { Text(stringResource(R.string.password)) },
                singleLine = true, visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                modifier = Modifier.fillMaxWidth().testTag("password"))
            Spacer(Modifier.height(12.dp))
            Button(
                enabled = !busy && username.isNotBlank() && password.isNotEmpty(),
                modifier = Modifier.fillMaxWidth().testTag("sign_in"),
                onClick = {
                    val norm = Format.normalizeBaseUrl(url)
                    if (norm == null) { error = badUrl; return@Button }
                    settings.baseUrl = norm
                    busy = true; error = null
                    scope.launch {
                        try {
                            val me = session.login(norm, username, password)
                            password = ""
                            onSignedIn(me)
                        } catch (e: ApiException) {
                            password = ""
                            error = when (e.status) {
                                401 -> wrongCreds
                                429 -> locked
                                else -> errorText(e)
                            }
                        } catch (e: Throwable) {
                            error = errorText(e)
                        } finally { busy = false }
                    }
                },
            ) { Text(if (busy) "…" else stringResource(R.string.sign_in), fontWeight = FontWeight.Bold) }
            error?.let {
                Text(it, color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(top = 8.dp).testTag("login_error"))
            }
            Spacer(Modifier.height(20.dp))
            OutlinedTextField(url, { url = it }, label = { Text(stringResource(R.string.backend_url)) },
                singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                modifier = Modifier.fillMaxWidth().testTag("base_url"))
            Text(stringResource(R.string.backend_url_help), fontSize = 11.sp, color = Cream)
            Spacer(Modifier.height(12.dp))
            LanguagePicker(settings, onLanguageChanged)
            Spacer(Modifier.height(12.dp))
            Text(stringResource(R.string.about_test_only), fontSize = 11.sp, color = Cream)
        }
    }
}

@Composable
fun LanguagePicker(settings: Settings, onLanguageChanged: () -> Unit) {
    fun pick(l: String) { if (l != settings.language) { settings.language = l; onLanguageChanged() } }
    Column(Modifier.fillMaxWidth()) {
        Text(stringResource(R.string.language_label), fontSize = 13.sp, color = Gold)
        Settings.LANGUAGES.forEach { l ->
            Row(verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth().clickable { pick(l) }.testTag("lang_$l")) {
                RadioButton(selected = settings.language == l, onClick = { pick(l) })
                Text(languageName(l) + if (l in Settings.PENDING_NATIVE_REVIEW)
                    " — " + stringResource(R.string.pending_native_review) else "")
            }
        }
        Text(stringResource(R.string.pending_native_review_note), fontSize = 11.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun Centered(text: String) = Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
    Text(text, style = MaterialTheme.typography.bodyLarge)
}

/** Loads with the backend; shows the server's own error text, never fake data. */
@Composable
fun <T> Loader(key: Any, load: suspend () -> T, content: @Composable (T, () -> Unit) -> Unit) {
    var state by remember(key) { mutableStateOf<Result<T>?>(null) }
    var tick by remember(key) { mutableIntStateOf(0) }
    LaunchedEffect(key, tick) {
        state = null
        state = runCatching { load() }
    }
    when (val s = state) {
        null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        else -> s.fold(
            onSuccess = { content(it) { tick++ } },
            onFailure = { e -> ErrorBox(e) { tick++ } },
        )
    }
}

@Composable
fun ErrorBox(e: Throwable, retry: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center) {
        Text(stringResource(R.string.error_title), color = MaterialTheme.colorScheme.error,
            fontWeight = FontWeight.Bold)
        Text(errorText(e))
        Spacer(Modifier.height(12.dp))
        Button(onClick = retry) { Text(stringResource(R.string.retry)) }
    }
}

fun errorText(e: Throwable): String = when (e) {
    is ApiException -> "HTTP ${e.status}: ${e.detail}"
    else -> e.message ?: e.javaClass.simpleName
}

// ------------------------------------------------------------- customers

@Composable
fun CustomersScreen(client: ApiClient, onOpen: (Customer) -> Unit) {
    Loader(key = client, load = { client.customers() }) { list, reload ->
        Column {
            HeaderRow(stringResource(R.string.tab_customers) + " (${list.size})", reload)
            if (list.isEmpty()) Centered(stringResource(R.string.no_customers))
            LazyColumn {
                items(list, key = { it.id }) { c ->
                    ListItem(
                        modifier = Modifier.clickable { onOpen(c) }.testTag("customer_${c.id}"),
                        headlineContent = { Text(c.name) },
                        supportingContent = {
                            Text(listOfNotNull(c.phone, c.email, c.language.uppercase()).joinToString(" · "))
                        },
                        trailingContent = {
                            Text(if (c.consentMarketing) stringResource(R.string.consent_yes_short)
                                 else stringResource(R.string.consent_no_short), fontSize = 11.sp)
                        },
                    )
                    HorizontalDivider()
                }
            }
        }
    }
}

@Composable
fun HeaderRow(title: String, reload: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(title, style = MaterialTheme.typography.titleLarge, color = Gold, modifier = Modifier.weight(1f))
        TextButton(onClick = reload) { Text(stringResource(R.string.refresh)) }
    }
}

@Composable
fun CustomerDetail(client: ApiClient, me: Me, customer: Customer, onBack: () -> Unit) {
    Loader(key = customer.id to client, load = {
        Pair(client.channelOptOuts(customer.id), client.messages(customer.id))
    }) { (optOuts, msgs), reload ->
        LazyColumn(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
            item {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    TextButton(onClick = onBack) { Text("← " + stringResource(R.string.back)) }
                    Spacer(Modifier.weight(1f))
                    TextButton(onClick = reload) { Text(stringResource(R.string.refresh)) }
                }
                Text(customer.name, style = MaterialTheme.typography.headlineSmall, color = Gold)
                Text(listOfNotNull(customer.phone, customer.email).joinToString(" · ").ifBlank { Format.NO_DATA })
                Text(stringResource(R.string.language_label) + ": " + customer.language.uppercase())
                Spacer(Modifier.height(8.dp))
                ContactStateCard(customer, optOuts)
                Spacer(Modifier.height(8.dp))
                Text(stringResource(R.string.messages_title), style = MaterialTheme.typography.titleMedium)
                if (msgs.isEmpty()) Text(stringResource(R.string.no_messages))
            }
            items(msgs.sortedByDescending { it.id }, key = { it.id }) { m ->
                MessageCard(client, me, m, onChanged = reload)
            }
        }
    }
}

/** Marketing consent and channel opt-outs, stated plainly. */
@Composable
fun ContactStateCard(c: Customer, optOuts: List<ChannelOptOut>) {
    Card(Modifier.fillMaxWidth().testTag("contact_state")) {
        Column(Modifier.padding(12.dp)) {
            Text(stringResource(R.string.contact_state_title), fontWeight = FontWeight.Bold)
            Text(
                when {
                    c.consentMarketing -> stringResource(R.string.marketing_consent_yes)
                    c.marketingOptOutAt != null -> stringResource(R.string.marketing_opted_out, c.marketingOptOutAt)
                    else -> stringResource(R.string.marketing_consent_none)
                }
            )
            val active = optOuts.filter { it.active }
            if (active.isEmpty()) Text(stringResource(R.string.no_channel_opt_out))
            active.forEach {
                Text(stringResource(R.string.channel_opted_out, it.channel.uppercase(), it.optedOutAt),
                    color = MaterialTheme.colorScheme.error, fontWeight = FontWeight.Bold)
            }
            optOuts.filter { !it.active }.forEach {
                Text(stringResource(R.string.channel_opt_out_revoked, it.channel.uppercase(), it.revokedAt ?: ""),
                    fontSize = 12.sp)
            }
            Text(stringResource(R.string.suppression_note), fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
fun MessageCard(client: ApiClient, me: Me, m: Message, onChanged: () -> Unit) {
    val scope = rememberCoroutineScope()
    var result by remember(m.id, m.status) { mutableStateOf<String?>(null) }
    var reason by remember(m.id) { mutableStateOf("") }
    // UI permission comes from GET /api/auth/me; the server still enforces it.
    val canWrite = me.canWrite
    fun act(block: suspend () -> Unit) {
        scope.launch {
            result = try { block(); null } catch (e: Throwable) { errorText(e) }
            if (result == null) onChanged()
        }
    }
    Card(Modifier.fillMaxWidth().padding(vertical = 4.dp).testTag("message_${m.id}")) {
        Column(Modifier.padding(12.dp)) {
            Row {
                Text("#${m.id} · ${m.channel.uppercase()} · " + (if (m.direction == "in")
                    stringResource(R.string.inbound) else purposeLabel(m.purpose)),
                    fontSize = 12.sp, modifier = Modifier.weight(1f))
                Text(statusLabel(m.status), color = Gold, fontWeight = FontWeight.Bold, fontSize = 12.sp)
            }
            if (m.isOptOutConfirmation) Text(stringResource(R.string.confirmation_note), fontSize = 11.sp)
            Text(m.text)
            m.translatedText?.let { Text("→ $it", fontSize = 13.sp) }
            holdLabel(m.holdReason)?.let {
                Text("⚠ $it", color = MaterialTheme.colorScheme.error, fontSize = 13.sp)
            }
            m.approvedBy?.let { Text(stringResource(R.string.approved_by, it), fontSize = 11.sp) }
            result?.let { Text(it, color = MaterialTheme.colorScheme.error, fontSize = 12.sp) }
            if (canWrite && m.direction == "out") {
                FlowRowActions {
                    when (m.status) {
                        "held" -> {
                            if (m.holdReason == "promotional_content_in_transactional") {
                                OutlinedTextField(reason, { reason = it },
                                    label = { Text(stringResource(R.string.release_reason)) },
                                    modifier = Modifier.fillMaxWidth())
                                Button(enabled = reason.isNotBlank(), onClick = { act { client.releaseHold(m.id, reason) } }) {
                                    Text(stringResource(R.string.release_hold))
                                }
                            }
                            if (!m.isOptOutConfirmation) {
                                OutlinedButton(onClick = { act { client.classify(m.id, "transactional") } }) {
                                    Text(stringResource(R.string.classify_transactional))
                                }
                                OutlinedButton(onClick = { act { client.classify(m.id, "marketing") } }) {
                                    Text(stringResource(R.string.classify_marketing))
                                }
                            }
                        }
                        "draft" -> Button(onClick = { act { client.approve(m.id) } }) { Text(stringResource(R.string.approve)) }
                        "approved" -> Button(onClick = { act { client.send(m.id) } }) { Text(stringResource(R.string.send)) }
                        "sent" -> Button(onClick = { act { client.dispatch(m.id) } }) { Text(stringResource(R.string.dispatch)) }
                    }
                    if (m.status in setOf("held", "draft", "approved")) {
                        TextButton(onClick = { act { client.withdraw(m.id) } }) { Text(stringResource(R.string.withdraw)) }
                    }
                }
            }
        }
    }
}

@Composable
fun FlowRowActions(content: @Composable () -> Unit) {
    Column(Modifier.padding(top = 6.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) { content() }
}

// ------------------------------------------------------------- approvals

@Composable
fun ApprovalsScreen(client: ApiClient, me: Me) {
    Loader(key = client, load = {
        Pair(client.messages().filter { it.needsHumanAction }, client.pendingOptOutConfirmations().toSet())
    }) { (pending, confIds), reload ->
        LazyColumn(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
            item {
                HeaderRow(stringResource(R.string.tab_approvals) + " (${pending.size})", reload)
                Text(stringResource(R.string.approvals_note), fontSize = 12.sp)
                Text(stringResource(R.string.confirmations_waiting, confIds.size), fontSize = 12.sp)
                if (pending.isEmpty()) Text(stringResource(R.string.nothing_pending))
            }
            items(pending.sortedBy { it.id }, key = { it.id }) { m ->
                MessageCard(client, me, m, onChanged = reload)
            }
        }
    }
}

// --------------------------------------------------------------- summary

@Composable
fun SummaryScreen(client: ApiClient, me: Me) {
    Loader(key = client, load = { client.summary() }) { s, reload ->
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(12.dp)) {
            HeaderRow(stringResource(R.string.tab_summary), reload)
            Kpi(stringResource(R.string.kpi_customers), Format.count(s.customers))
            Kpi(stringResource(R.string.kpi_lapsed), Format.count(s.lapsedCustomers))
            Kpi(stringResource(R.string.kpi_upcoming), Format.count(s.upcomingBookings))
            Kpi(stringResource(R.string.kpi_rating), Format.rating(s.averageRating))
            Kpi(stringResource(R.string.kpi_open_invoices), Format.money(s.openInvoices))
            Kpi(stringResource(R.string.kpi_payments), Format.money(s.paymentsReceived))
            Text(stringResource(R.string.kpi_note), fontSize = 11.sp)
            Spacer(Modifier.height(16.dp))
            Text(stringResource(R.string.suppression_title), style = MaterialTheme.typography.titleMedium, color = Gold)
            if (!me.isOwner) Text(stringResource(R.string.owner_only))
            else SuppressionPanel(client)
        }
    }
}

@Composable
fun Kpi(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
        Text(label, modifier = Modifier.weight(1f))
        Text(value, fontWeight = FontWeight.Bold, color = Gold)
    }
}

@Composable
fun SuppressionPanel(client: ApiClient) {
    var text by remember { mutableStateOf<String?>(null) }
    val keyLabel = stringResource(R.string.suppression_key_state)
    val rowsLabel = stringResource(R.string.suppression_rows)
    LaunchedEffect(client) {
        text = try {
            val k = client.suppressionKeyStatus()
            val rows = client.suppressions()
            val byScope = rows.groupingBy { "${it.scope}/${it.channel}" }.eachCount()
            "$keyLabel: ${k.state}" + (k.source?.let { " ($it)" } ?: "") + "\n" +
                "$rowsLabel: ${rows.size}" +
                (if (byScope.isEmpty()) "" else "\n" + byScope.entries.joinToString("\n") { "  ${it.key}: ${it.value}" })
        } catch (e: Throwable) { errorText(e) }
    }
    Text(text ?: "…")
}

// -------------------------------------------------------------- settings

@Composable
fun SettingsScreen(
    settings: Settings,
    me: Me,
    session: SessionManager,
    onSignOut: (revoked: Boolean) -> Unit,
    onLanguageChanged: () -> Unit,
) {
    var url by remember { mutableStateOf(settings.baseUrl) }
    var status by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val okText = stringResource(R.string.connection_ok)
    val badUrl = stringResource(R.string.bad_url)
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(12.dp)) {
        Text(stringResource(R.string.tab_settings), style = MaterialTheme.typography.titleLarge, color = Gold)
        Card(Modifier.fillMaxWidth().padding(vertical = 8.dp).testTag("account_card")) {
            Column(Modifier.padding(12.dp)) {
                Text(stringResource(R.string.account_title), fontWeight = FontWeight.Bold)
                Text(stringResource(R.string.signed_in_as, me.label, me.role))
                Text(stringResource(R.string.username) + ": " + me.username, fontSize = 12.sp)
                Text(stringResource(R.string.role_from_server), fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(8.dp))
                Button(enabled = !busy, modifier = Modifier.testTag("sign_out"), onClick = {
                    busy = true
                    scope.launch {
                        val revoked = session.logout(Format.normalizeBaseUrl(settings.baseUrl))
                        busy = false
                        onSignOut(revoked)
                    }
                }) { Text(stringResource(R.string.sign_out)) }
            }
        }
        OutlinedTextField(url, { url = it }, label = { Text(stringResource(R.string.backend_url)) },
            singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
            modifier = Modifier.fillMaxWidth().testTag("base_url"))
        Text(stringResource(R.string.backend_url_change_note), fontSize = 11.sp)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = {
                val norm = Format.normalizeBaseUrl(url)
                if (norm == null) { status = badUrl; return@Button }
                if (norm != Format.normalizeBaseUrl(settings.baseUrl)) {
                    // The session belongs to the old server: sign out there first.
                    busy = true
                    scope.launch {
                        val revoked = session.logout(Format.normalizeBaseUrl(settings.baseUrl))
                        settings.baseUrl = norm
                        busy = false
                        onSignOut(revoked)
                    }
                } else status = null
            }) { Text(stringResource(R.string.save)) }
            OutlinedButton(onClick = {
                val norm = Format.normalizeBaseUrl(url)
                if (norm == null) { status = badUrl; return@OutlinedButton }
                scope.launch {
                    status = try {
                        val h = ApiClient(norm, NoAuth).health()
                        okText + " (" + h.optString("product") + ")"
                    } catch (e: Throwable) { errorText(e) }
                }
            }) { Text(stringResource(R.string.test_connection)) }
        }
        status?.let { Text(it, modifier = Modifier.padding(top = 8.dp)) }
        Spacer(Modifier.height(12.dp))
        LanguagePicker(settings, onLanguageChanged)
        Spacer(Modifier.height(16.dp))
        Text(stringResource(R.string.about_test_only), fontSize = 11.sp)
        Text("v" + BuildConfig.VERSION_NAME + " · " + BuildConfig.GIT_SHA, fontSize = 11.sp,
            color = Gold, modifier = Modifier.padding(top = 4.dp).testTag("build_id"))
    }
}

@Composable
fun languageName(l: String) = when (l) {
    "en" -> "English"; "es" -> "Español"; "pt" -> "Português"; "ht" -> "Kreyòl ayisyen"; else -> l
}
