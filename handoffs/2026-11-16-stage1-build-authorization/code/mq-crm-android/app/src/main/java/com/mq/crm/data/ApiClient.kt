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

/**
 * Thin client for the SAME M&Q CRM FastAPI backend the web UI uses. There
 * is no local copy of CRM data: every screen reads the backend live and
 * every action is a backend call, so all server-side gates (purpose,
 * consent, channel opt-out, suppression list, approval, privacy register)
 * keep applying. Errors carry the server's own reason.
 */
class ApiClient(
    private val baseUrl: String,
    private val auth: AuthProvider,
    private val timeoutMs: Int = 10_000,
) {
    private suspend fun call(method: String, path: String, body: JSONObject? = null): String =
        withContext(Dispatchers.IO) {
            val conn = (URL(baseUrl + path).openConnection() as HttpURLConnection).apply {
                requestMethod = method
                connectTimeout = timeoutMs
                readTimeout = timeoutMs
                setRequestProperty("Accept", "application/json")
                auth.headers().forEach { (k, v) -> setRequestProperty(k, v) }
                if (body != null) {
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json")
                }
            }
            try {
                if (body != null) conn.outputStream.use { it.write(body.toString().toByteArray()) }
                val code = conn.responseCode
                val stream = if (code in 200..299) conn.inputStream else conn.errorStream
                val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
                if (code !in 200..299) throw ApiException(code, detailOf(text))
                text
            } finally {
                conn.disconnect()
            }
        }

    suspend fun health(): JSONObject = JSONObject(call("GET", "/api/health"))

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
