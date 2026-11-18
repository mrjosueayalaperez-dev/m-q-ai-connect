package com.mq.crm.data

import org.json.JSONArray
import org.json.JSONObject

/** Plain models mirroring the CRM API (Batch 008d). Unknown fields ignored. */

private fun JSONObject.str(k: String): String? =
    if (!has(k) || isNull(k)) null else optString(k)

private fun JSONObject.intOrNull(k: String): Int? =
    if (!has(k) || isNull(k)) null else optInt(k)

data class Customer(
    val id: Int,
    val name: String,
    val phone: String?,
    val email: String?,
    val language: String,
    val consentMarketing: Boolean,
    val marketingOptOutAt: String?,
    val lastServiceAt: String?,
) {
    companion object {
        fun from(o: JSONObject) = Customer(
            id = o.getInt("id"),
            name = o.optString("name"),
            phone = o.str("phone"),
            email = o.str("email"),
            language = o.optString("language", "en"),
            consentMarketing = o.optInt("consent_marketing", 0) == 1,
            marketingOptOutAt = o.str("marketing_opt_out_at"),
            lastServiceAt = o.str("last_service_at"),
        )
    }
}

data class Message(
    val id: Int,
    val customerId: Int,
    val direction: String,
    val channel: String,
    val text: String,
    val translatedText: String?,
    val lang: String?,
    val status: String,
    val purpose: String?,
    val holdReason: String?,
    val approvedBy: String?,
    val optOutEventId: Int?,
    val createdAt: String?,
) {
    val isOptOutConfirmation get() = purpose == "opt_out_confirmation"
    val needsHumanAction get() = direction == "out" && status in setOf("held", "draft", "approved")

    companion object {
        fun from(o: JSONObject) = Message(
            id = o.getInt("id"),
            customerId = o.getInt("customer_id"),
            direction = o.optString("direction", "out"),
            channel = o.optString("channel", "sms"),
            text = o.optString("original_text"),
            translatedText = o.str("translated_text"),
            lang = o.str("original_lang"),
            status = o.optString("status"),
            purpose = o.str("purpose"),
            holdReason = o.str("hold_reason"),
            approvedBy = o.str("approved_by"),
            optOutEventId = o.intOrNull("opt_out_event_id"),
            createdAt = o.str("created_at"),
        )
    }
}

data class ChannelOptOut(
    val id: Int,
    val channel: String,
    val source: String?,
    val optedOutAt: String,
    val revokedAt: String?,
) {
    val active get() = revokedAt == null

    companion object {
        fun from(o: JSONObject) = ChannelOptOut(
            id = o.getInt("id"),
            channel = o.optString("channel"),
            source = o.str("source"),
            optedOutAt = o.optString("opted_out_at"),
            revokedAt = o.str("revoked_at"),
        )
    }
}

data class Summary(
    val customers: Int?,
    val lapsedCustomers: Int?,
    val upcomingBookings: Int?,
    val averageRating: Double?,
    val openInvoices: List<Pair<String, Long>>,
    val paymentsReceived: List<Pair<String, Long>>,
) {
    companion object {
        fun from(o: JSONObject): Summary {
            fun money(arr: JSONArray?, key: String) = buildList {
                if (arr != null) for (i in 0 until arr.length()) {
                    val r = arr.getJSONObject(i)
                    add(r.optString("currency") to r.optLong(key))
                }
            }
            return Summary(
                customers = o.intOrNull("customers"),
                lapsedCustomers = o.intOrNull("lapsed_customers"),
                upcomingBookings = o.intOrNull("upcoming_bookings"),
                averageRating = if (o.isNull("average_rating") || !o.has("average_rating")) null
                                else o.optDouble("average_rating"),
                openInvoices = money(o.optJSONArray("open_invoices"), "total_minor"),
                paymentsReceived = money(o.optJSONArray("payments_received"), "paid_minor"),
            )
        }
    }
}

data class SuppressionKeyStatus(val state: String, val source: String?, val suppressions: Int?) {
    companion object {
        fun from(o: JSONObject) = SuppressionKeyStatus(
            o.optString("state"), o.str("source"), o.intOrNull("suppressions"))
    }
}

data class SuppressionRow(val id: Int, val contactType: String, val channel: String,
                          val scope: String, val suppressedAt: String) {
    companion object {
        fun from(o: JSONObject) = SuppressionRow(o.getInt("id"), o.optString("contact_type"),
            o.optString("channel"), o.optString("scope"), o.optString("suppressed_at"))
    }
}

fun <T> JSONArray.mapObjects(f: (JSONObject) -> T): List<T> =
    (0 until length()).map { f(getJSONObject(it)) }
