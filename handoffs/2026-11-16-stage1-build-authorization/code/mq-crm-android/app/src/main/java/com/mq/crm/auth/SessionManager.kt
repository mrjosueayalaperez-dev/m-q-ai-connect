package com.mq.crm.auth

import com.mq.crm.data.ApiClient
import com.mq.crm.data.ApiException
import com.mq.crm.data.HttpTransport
import com.mq.crm.data.UrlConnectionTransport

/**
 * Login / restore / logout against the PR #3 backend:
 *   POST /api/auth/login {username, password, mode:"token"} -> bearer token
 *   GET  /api/auth/me   -> the role and name the UI shows
 *   POST /api/auth/logout -> server-side revoke
 * The token is never logged; it lives only in [store] (encrypted).
 */
class SessionManager(
    private val store: TokenStore,
    private val transport: HttpTransport = UrlConnectionTransport(),
    private val onUnauthorized: () -> Unit = {},
) {
    val auth: AuthProvider = BearerAuthProvider(store)

    fun hasToken(): Boolean = store.load() != null

    /** An API client for [baseUrl]; any 401 clears the token and signs out. */
    fun client(baseUrl: String): ApiClient =
        ApiClient(baseUrl, auth, transport, onUnauthorized = {
            store.clear()
            onUnauthorized()
        })

    /** Sign in; on success the token is stored and the server's /me returned. */
    suspend fun login(baseUrl: String, username: String, password: String): Me {
        val token = ApiClient(baseUrl, NoAuth, transport).login(username.trim(), password)
        store.save(token)
        return try {
            client(baseUrl).me()
        } catch (e: Exception) {
            store.clear()
            throw e
        }
    }

    /** Restore a saved session after an app restart; null if signed out. */
    suspend fun restore(baseUrl: String): Me? {
        if (!hasToken()) return null
        return try {
            client(baseUrl).me()
        } catch (e: ApiException) {
            if (e.status == 401) null else throw e
        }
    }

    /** Revoke on the server first, then always wipe the local token. */
    suspend fun logout(baseUrl: String?): Boolean {
        var revoked = false
        try {
            if (baseUrl != null && hasToken()) {
                ApiClient(baseUrl, auth, transport).logout()
                revoked = true
            }
        } catch (e: Exception) {
            // Server unreachable or session already gone: still sign out locally.
        } finally {
            store.clear()
        }
        return revoked
    }
}
