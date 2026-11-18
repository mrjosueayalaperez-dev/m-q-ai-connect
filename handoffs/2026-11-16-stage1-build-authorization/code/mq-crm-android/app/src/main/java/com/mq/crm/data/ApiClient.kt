package com.mq.crm.data

import com.mq.crm.auth.AuthProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/** The backend refused (HTTP status + its own `detail` text, shown verbatim). */
class ApiException(val status: Int, val detail: String) : IOException("HTTP $status: $detail")

/** One HTTP exchange; swappable so tests can inspect exactly what is sent. */
data class HttpRequest(val method: String, val url: String, val headers: Map<String, String>, val body: String?)
data class HttpResponse(val status: Int, val body: String)

fun interface HttpTransport {
    fun execute(req: HttpRequest, timeoutMs: Int): HttpResponse
}

class UrlConnectionTransport : HttpTransport {
    override fun execute(req: HttpRequest, timeoutMs: Int): HttpResponse {
        val conn = (URL(req.url).openConnection() as HttpURLConnection).apply {
            requestMethod = req.method
            connectTimeout = timeoutMs
            readTimeout = timeoutMs
            useCaches = false
            req.headers.forEach { (k, v) -> setRequestProperty(k, v) }
            if (req.body != null) doOutput = true
        }
        try {
            if (req.body != null) conn.outputStream.use { it.write(req.body.toByteArray()) }
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            return HttpResponse(code, stream?.bufferedReader()?.use { it.readText() } ?: "")
        } finally {
            conn.disconnect()
        }
    }
}

/**
 * Thin client for the SAME M&Q CRM FastAPI backend the web UI uses. There
 * is no local copy of CRM data: every screen reads the backend live and
 * every action is a backend call, so all server-side gates (role, purpose,
 * consent, channel opt-out, suppression list, approval, privacy register)
 * keep applying. Errors carry the server's own reason.
 *
 * Batch 009: the only credential is the bearer token from [auth]. The
 * request interceptor below drops any X-Role / X-Actor header, so this
 * client can never assert a role or an audit identity. A 401 on an
 * authenticated call means the session is expired or revoked:
 * [onUnauthorized] signs the app out.
 */
class ApiClient(
    private val baseUrl: String,
    private val auth: AuthProvider,
    private val transport: HttpTransport = UrlConnectionTransport(),
    private val timeoutMs: Int = 10_000,
    private val onUnauthorized: () -> Unit = {},
) {
    /** The interceptor: builds the final header set for every request. */
    internal fun headersFor(hasBody: Boolean): Map<String, String> {
        val h = linkedMapOf("Accept" to "application/json")
        auth.headers().forEach { (k, v) -> h[k] = v }
        if (hasBody) h["Content-Type"] = "application/json"
        return h.filterKeys { it.lowercase() !in FORBIDDEN_HEADERS }
    }

    private suspend fun call(method: String, path: String, body: JSONObject? = null,
                             signOutOn401: Boolean = true): String =
        withContext(Dispatchers.IO) {
            val res = transport.execute(
                HttpRequest(method, baseUrl + path, headersFor(body != null), body?.toString()),
                timeoutMs)
            if (res.status == 401 && signOutOn401) onUnauthorized()
            if (res.status !in 200..299) throw ApiException(res.status, detailOf(res.body))
            res.body
        }

    /** POST /api/auth/login (token mode). A 401 here is a wrong password, not a sign-out. */
    suspend fun login(username: String, password: String): String {
        val body = JSONObject().put("username", username).put("password", password).put("mode", "token")
        val o = JSONObject(call("POST", "/api/auth/login", body, signOutOn401 = false))
        return o.getString("token")
    }

    suspend fun me(): com.mq.crm.auth.Me = com.mq.crm.auth.Me.from(JSONObject(call("GET", "/api/auth/me")))

    suspend fun logout() { call("POST", "/api/auth/logout", signOutOn401 = false) }

    suspend fun health(): JSONObject = JSONObject(call("GET", "/api/health", signOutOn401 = false))

    suspend fun customers(): List<Customer> =
        JSONArray(call("GET", "/api/customers")).mapObjects(Customer::from)

    suspend fun messages(customerId: Int? = null): List<Message> =
        JSONArray(call("GET", "/api/messages" + (customerId?.let { "?customer_id=$it" } ?: "")))
            .mapObjects(Message::from)

    suspend fun channelOptOuts(customerId: Int): List<ChannelOptOut> =
        JSONArray(call("GET", "/api/customers/$customerId/channel-opt-outs"))
            .mapObjects(ChannelOptOut::from)

    suspend fun pendingOptOutConfirmations(): List<Int> =
        JSONArray(call("GET", "/api/opt-out-confirmations")).mapObjects { it.getInt("id") }

    suspend fun summary(): Summary = Summary.from(JSONObject(call("GET", "/api/reports/summary")))

    suspend fun suppressionKeyStatus(): SuppressionKeyStatus =
        SuppressionKeyStatus.from(JSONObject(call("GET", "/api/admin/suppression-key/status")))

    suspend fun suppressions(): List<SuppressionRow> =
        JSONArray(call("GET", "/api/admin/suppressions")).mapObjects(SuppressionRow::from)

    suspend fun approve(id: Int) = call("POST", "/api/messages/$id/approve")
    suspend fun withdraw(id: Int) = call("POST", "/api/messages/$id/withdraw")
    suspend fun send(id: Int) = call("POST", "/api/messages/$id/send")
    suspend fun dispatch(id: Int) = call("POST", "/api/messages/$id/dispatch")
    suspend fun classify(id: Int, purpose: String) =
        call("POST", "/api/messages/$id/classify", JSONObject().put("purpose", purpose))
    suspend fun releaseHold(id: Int, reason: String) =
        call("POST", "/api/messages/$id/release-hold", JSONObject().put("reason", reason))

    companion object {
        /** Never sent: the role and the audit name come from the server session. */
        val FORBIDDEN_HEADERS = setOf("x-role", "x-actor")

        /** FastAPI errors look like {"detail": "..."}; fall back to raw text. */
        fun detailOf(text: String): String = try {
            val d = JSONObject(text).opt("detail")
            when (d) {
                null -> text
                is String -> d
                else -> d.toString()
            }
        } catch (e: Exception) {
            text.ifBlank { "(no response body)" }
        }
    }
}
