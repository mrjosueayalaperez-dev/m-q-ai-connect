package com.mq.crm.data

import java.util.Locale

/**
 * Honesty rules for displayed numbers: a value the backend did not supply
 * (null) or a money list with no rows is shown as an em dash, never as a
 * made-up 0 or a placeholder figure. Real counts (including a real 0) are
 * shown as reported.
 */
object Format {
    const val NO_DATA = "—"

    fun count(v: Int?): String = v?.toString() ?: NO_DATA

    fun rating(v: Double?): String =
        if (v == null || v.isNaN()) NO_DATA else String.format(Locale.US, "%.2f / 5", v)

    fun money(rows: List<Pair<String, Long>>): String =
        if (rows.isEmpty()) NO_DATA
        else rows.joinToString("  ·  ") { (cur, minor) ->
            val sign = if (minor < 0) "-" else ""
            val abs = Math.abs(minor)
            String.format(Locale.US, "%s %s%d.%02d", cur, sign, abs / 100, abs % 100)
        }

    /** Hosts that may use plain http, and only in debug builds (emulator / same machine). */
    val LOCAL_HTTP_HOSTS = setOf("10.0.2.2", "localhost", "127.0.0.1")

    /**
     * Trim and drop trailing slashes. v0.3.1: https:// is required for every
     * server (e.g. a hosted test URL); plain http:// is accepted only for
     * 10.0.2.2 / localhost / 127.0.0.1 and only when [allowLocalHttp] (debug
     * builds). Credentials in the URL (user@host) are refused.
     */
    fun normalizeBaseUrl(raw: String, allowLocalHttp: Boolean = com.mq.crm.BuildConfig.DEBUG): String? {
        val t = raw.trim().trimEnd('/')
        if (t.isEmpty() || t.any { it.isWhitespace() }) return null
        val lower = t.lowercase(Locale.ROOT)
        val https = lower.startsWith("https://")
        if (!https && !lower.startsWith("http://")) return null
        val rest = lower.substringAfter("://")
        val authority = rest.substringBefore('/').substringBefore('?').substringBefore('#')
        if (authority.isEmpty() || '@' in authority) return null
        val host = if (authority.startsWith("[")) authority.substringBefore(']') + "]"
                   else authority.substringBefore(':')
        if (host.isEmpty() || host.startsWith(".") || host.endsWith(".")) return null
        val port = authority.removePrefix(host).removePrefix(":")
        if (authority.length > host.length && (port.isEmpty() || port.any { !it.isDigit() } ||
                port.toIntOrNull()?.let { it !in 1..65535 } != false)) return null
        if (!https && !(allowLocalHttp && host in LOCAL_HTTP_HOSTS)) return null
        return t
    }
}
