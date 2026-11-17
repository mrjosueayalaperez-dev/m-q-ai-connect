package com.mq.crm.auth

/**
 * How the app authenticates to the CRM backend.
 *
 * Batch 009 (PR #3 backend): real login. The only credential the app sends
 * is `Authorization: Bearer <token>` from POST /api/auth/login. The role,
 * name and permissions shown come only from GET /api/auth/me; the backend
 * still enforces every permission on every call. The app never sends a
 * role or an audit identity (X-Role / X-Actor); those headers are also
 * stripped by ApiClient as a guard.
 */
interface AuthProvider {
    /** Headers added to every authenticated request. */
    fun headers(): Map<String, String>
}

/** Sends the stored bearer token, nothing else. */
class BearerAuthProvider(private val store: TokenStore) : AuthProvider {
    override fun headers(): Map<String, String> =
        store.load()?.let { mapOf("Authorization" to "Bearer $it") } ?: emptyMap()
}

/** No credentials (health check and the login call itself). */
object NoAuth : AuthProvider {
    override fun headers(): Map<String, String> = emptyMap()
}

/** The signed-in user exactly as GET /api/auth/me reports it. */
data class Me(
    val username: String,
    val displayName: String?,
    val role: String,
    val sessionKind: String?,
    val absoluteExpiresAt: String?,
) {
    val canWrite: Boolean get() = role in WRITE_ROLES
    val isOwner: Boolean get() = role == "owner"
    val label: String get() = displayName?.takeIf { it.isNotBlank() } ?: username

    companion object {
        val WRITE_ROLES = setOf("owner", "staff")

        fun from(o: org.json.JSONObject): Me {
            val u = o.getJSONObject("user")
            val s = o.optJSONObject("session")
            return Me(
                username = u.getString("username"),
                displayName = if (u.isNull("display_name")) null else u.optString("display_name"),
                role = u.getString("role"),
                sessionKind = s?.optString("kind"),
                absoluteExpiresAt = s?.optString("absolute_expires_at"),
            )
        }
    }
}
