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

    /** Trim, drop trailing slashes; only http(s) URLs are accepted. */
    fun normalizeBaseUrl(raw: String): String? {
        val t = raw.trim().trimEnd('/')
        if (t.isEmpty()) return null
        val lower = t.lowercase(Locale.ROOT)
        if (!(lower.startsWith("http://") || lower.startsWith("https://"))) return null
        if (t.contains(' ')) return null
        return t
    }
}
