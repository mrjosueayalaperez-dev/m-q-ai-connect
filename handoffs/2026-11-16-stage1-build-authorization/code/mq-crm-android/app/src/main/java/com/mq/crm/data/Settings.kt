package com.mq.crm.data

import android.content.Context
import com.mq.crm.BuildConfig

/**
 * Device settings: the backend URL and the UI language. No CRM data, no
 * role and no audit identity are stored (those come from the server
 * session). The session token is stored separately, encrypted
 * (see auth/TokenStore.kt).
 */
class Settings(context: Context) {
    private val p = context.getSharedPreferences("mq_crm_settings", Context.MODE_PRIVATE)

    init {
        // v0.1 kept a self-asserted role and name here; real login replaces them.
        if (p.contains("role") || p.contains("actor")) p.edit().remove("role").remove("actor").apply()
    }

    var baseUrl: String
        get() = p.getString("base_url", null) ?: BuildConfig.DEFAULT_BASE_URL
        set(v) = p.edit().putString("base_url", v).apply()

    var language: String
        get() = p.getString("language", "en") ?: "en"
        set(v) = p.edit().putString("language", v).commit().let { }

    companion object {
        /** All four are selectable. */
        val LANGUAGES = listOf("en", "es", "pt", "ht")
        /** Complete strings, but NOT yet reviewed by a native speaker. */
        val PENDING_NATIVE_REVIEW = setOf("pt", "ht")
    }
}
