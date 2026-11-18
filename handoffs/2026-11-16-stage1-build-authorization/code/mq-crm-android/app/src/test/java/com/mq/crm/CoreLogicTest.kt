package com.mq.crm

import com.mq.crm.data.ApiClient
import com.mq.crm.data.Customer
import com.mq.crm.data.Format
import com.mq.crm.data.Message
import com.mq.crm.data.Summary
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class CoreLogicTest {

    @Test fun allFourLanguagesSelectablePtHtFlaggedPendingReview() {
        assertEquals(listOf("en", "es", "pt", "ht"), com.mq.crm.data.Settings.LANGUAGES)
        assertEquals(setOf("pt", "ht"), com.mq.crm.data.Settings.PENDING_NATIVE_REVIEW)
    }

    @Test fun missingKpisShowDashNotZero() {
        val s = Summary.from(JSONObject("""{"customers": 0, "lapsed_customers": 0,
            "upcoming_bookings": 0, "average_rating": null,
            "open_invoices": [], "payments_received": []}"""))
        assertEquals("0", Format.count(s.customers))          // a real zero stays 0
        assertEquals("—", Format.rating(s.averageRating))     // no reviews -> dash
        assertEquals("—", Format.money(s.openInvoices))
        assertEquals("—", Format.money(s.paymentsReceived))
        assertEquals("—", Format.count(null))
        assertEquals("4.50 / 5", Format.rating(4.5))
        assertEquals("USD 12.05", Format.money(listOf("USD" to 1205L)))
        assertEquals("USD -0.50", Format.money(listOf("USD" to -50L)))
        assertEquals("USD -12.05", Format.money(listOf("USD" to -1205L)))
    }

    @Test fun baseUrlNormalization() {
        assertEquals("http://10.0.2.2:8000", Format.normalizeBaseUrl(" http://10.0.2.2:8000/ "))
        assertEquals("https://crm.example.test", Format.normalizeBaseUrl("https://crm.example.test"))
        assertNull(Format.normalizeBaseUrl(""))
        assertNull(Format.normalizeBaseUrl("crm.example.test"))
        assertNull(Format.normalizeBaseUrl("ftp://x"))
    }

    @Test fun serverRefusalTextIsKeptVerbatim() {
        assertEquals("send refused: contact is on the do-not-message list for SMS",
            ApiClient.detailOf("""{"detail":"send refused: contact is on the do-not-message list for SMS"}"""))
        assertEquals("plain", ApiClient.detailOf("plain"))
    }

    @Test fun parsesBackendRowsIncludingOptOutAndHoldState() {
        val c = Customer.from(JSONObject("""{"id":3,"name":"Synthetic Ana","phone":"5550100",
            "email":null,"language":"es","consent_marketing":0,
            "marketing_opt_out_at":"2026-11-17T19:00:00Z"}"""))
        assertFalse(c.consentMarketing); assertNull(c.email)
        assertEquals("2026-11-17T19:00:00Z", c.marketingOptOutAt)
        val m = Message.from(JSONObject("""{"id":9,"customer_id":3,"direction":"out",
            "channel":"sms","original_text":"Su carro sale a las 3","status":"held",
            "purpose":"transactional","hold_reason":"promotional_content_in_transactional",
            "opt_out_event_id":null}"""))
        assertTrue(m.needsHumanAction); assertFalse(m.isOptOutConfirmation)
        assertEquals("promotional_content_in_transactional", m.holdReason)
        val conf = Message.from(JSONObject("""{"id":10,"customer_id":3,"direction":"out",
            "original_text":"x","status":"draft","purpose":"opt_out_confirmation","opt_out_event_id":4}"""))
        assertTrue(conf.isOptOutConfirmation); assertEquals(4, conf.optOutEventId)
    }

    @Test fun buildIsMarkedTestOnly() {
        assertTrue(BuildConfig.TEST_ONLY)
        assertTrue(BuildConfig.VERSION_NAME.contains("TEST-ONLY"))
        assertTrue(BuildConfig.VERSION_NAME.startsWith("0.3.0"))
    }
}
