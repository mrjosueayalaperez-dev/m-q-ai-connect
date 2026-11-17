package com.mq.crm.auth

import android.content.Context

/** SharedPreferences-backed [KeyValue]; holds only the sealed token. Not backed up (allowBackup=false). */
class PrefsKeyValue(context: Context) : KeyValue {
    private val p = context.getSharedPreferences("mq_crm_auth", Context.MODE_PRIVATE)
    override fun get(key: String): String? = p.getString(key, null)
    override fun put(key: String, value: String) { p.edit().putString(key, value).commit() }
    override fun remove(key: String) { p.edit().remove(key).commit() }
}
