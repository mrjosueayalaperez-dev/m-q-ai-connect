package com.mq.crm.auth

/**
 * How the app identifies the operator to the CRM backend.
 *
 * Every API call asks the active provider for its request headers. Real
 * login (e.g. a session or bearer token issued by the backend) will be a
 * new implementation of this interface; screens and the API client do not
 * change when it arrives.
 */
interface AuthProvider {
    /** Headers added to every request. */
    fun headers(): Map<String, String>

    /** True while the identity is self-asserted (no real authentication). */
    val isTestOnly: Boolean

    /** Who the app says the operator is, for display only. */
    val displayName: String

    /** The role the backend will apply (owner | staff | viewer). */
    val role: String
}

/**
 * TEST-ONLY. The CRM backend currently trusts a self-asserted `X-Role` and
 * `X-Actor` header (Batch 008 deny-by-default). Anyone who can reach the
 * backend can claim any role. This provider exists only until real login
 * is approved and built.
 */
class TestHeaderAuthProvider(
    override val role: String,
    private val actor: String,
) : AuthProvider {
    init {
        require(role in ROLES) { "role must be one of $ROLES" }
    }

    override val isTestOnly: Boolean = true
    override val displayName: String get() = actor.ifBlank { "(no name)" }

    override fun headers(): Map<String, String> {
        val h = linkedMapOf("X-Role" to role)
        if (actor.isNotBlank()) h["X-Actor"] = actor.trim()
        return h
    }

    companion object {
        val ROLES = listOf("owner", "staff", "viewer")
        val WRITE_ROLES = setOf("owner", "staff")
    }
}
