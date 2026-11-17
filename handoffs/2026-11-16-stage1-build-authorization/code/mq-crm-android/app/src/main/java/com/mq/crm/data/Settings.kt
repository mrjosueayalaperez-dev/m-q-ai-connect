package com.mq.crm.data

import android.content.Context
import com.mq.crm.BuildConfig

/**
 * Operator settings kept on the device: backend URL, the TEST-ONLY role and
 * display name, and the UI language. No CRM data and no secrets are stored.
 */
class Settings(context: Context) {
    private val p = context.getSharedPreferences("mq_crm_settings", Context.MODE_PRIVATE)

    var baseUrl: String
        get() = p.getString("base_url", null) ?: BuildConfig.DEFAULT_BASE_URL
        set(v) = p.edit().putString("base_url", v).apply()

    var role: String
        get() = p.getString("role", "viewer") ?: "viewer"
        set(v) = p.edit().putString("role", v).apply()

    var actor: String
        get() = p.getString("actor", "") ?: ""
        set(v) = p.edit().putString("actor", v).apply()

    var language: String
        get() = p.getString("language", "en") ?: "en"
        set(v) = p.edit().putString("language", v).commit().let { }

    companion object {
        /** User-selectable now. */
        val ENABLED_LANGUAGES = listOf("en", "es")
        /** Resources exist; pending native-speaker validation, not selectable. */
        val PENDING_LANGUAGES = listOf("pt", "ht")
    }
}
