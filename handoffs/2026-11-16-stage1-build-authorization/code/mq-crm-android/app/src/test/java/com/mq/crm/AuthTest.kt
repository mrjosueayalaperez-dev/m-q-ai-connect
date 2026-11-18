package com.mq.crm

import com.mq.crm.auth.AesGcmCodec
import com.mq.crm.auth.AuthProvider
import com.mq.crm.auth.BearerAuthProvider
import com.mq.crm.auth.EncryptedTokenStore
import com.mq.crm.auth.KeyValue
import com.mq.crm.auth.Me
import com.mq.crm.auth.SessionManager
import com.mq.crm.data.ApiClient
import com.mq.crm.data.ApiException
import com.mq.crm.data.HttpRequest
import com.mq.crm.data.HttpResponse
import com.mq.crm.data.HttpTransport
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey

/** In-memory stand-in for SharedPreferences. */
class MapKv : KeyValue {
    val m = linkedMapOf<String, String>()
    override fun get(key: String) = m[key]
    override fun put(key: String, value: String) { m[key] = value }
    override fun remove(key: String) { m.remove(key) }
}

/** Records every request; answers from a script. */
class FakeTransport(private val answer: (HttpRequest) -> HttpResponse) : HttpTransport {
    val sent = mutableListOf<HttpRequest>()
    override fun execute(req: HttpRequest, timeoutMs: Int): HttpResponse { sent += req; return answer(req) }
}

private fun aesKey(): SecretKey = KeyGenerator.getInstance("AES").apply { init(256) }.generateKey()

private const val TOKEN = "synthetic-token-AbCdEf0123456789_-xyz"
private val ME_OWNER = """{"user":{"username":"syn-owner","display_name":"Synthetic Owner","role":"owner"},
    "session":{"kind":"bearer","absolute_expires_at":"2026-11-18T09:00:00.000000Z","idle_minutes":30}}"""
private val ME_VIEWER = """{"user":{"username":"syn-viewer","display_name":null,"role":"viewer"},
    "session":{"kind":"bearer"}}"""

private fun backend(meJson: String = ME_OWNER, meStatus: Int = 200, customersStatus: Int = 401) = FakeTransport { r ->
    when {
        r.url.endsWith("/api/auth/login") -> {
            val b = JSONObject(r.body!!)
            if (b.getString("password") == "Right-password-123")
                HttpResponse(200, """{"token":"$TOKEN","token_type":"bearer","user":{}}""")
            else HttpResponse(401, """{"detail":"invalid username or password"}""")
        }
        r.url.endsWith("/api/auth/me") -> HttpResponse(meStatus,
            if (meStatus == 200) meJson else """{"detail":"login required"}""")
        r.url.endsWith("/api/auth/logout") -> HttpResponse(200, """{"ok":true}""")
        r.url.endsWith("/api/customers") -> if (customersStatus == 200) HttpResponse(200, "[]")
            else HttpResponse(customersStatus, """{"detail":"login required"}""")
        else -> HttpResponse(404, """{"detail":"nope"}""")
    }
}

class AuthTest {

    // ------------------------------------------------ token storage

    @Test fun tokenStoreRoundTripStoresOnlyCiphertext() {
        val key = aesKey()
        val kv = MapKv()
        val store = EncryptedTokenStore(kv, AesGcmCodec { key })
        assertNull(store.load())
        store.save(TOKEN)
        val stored = kv.m[EncryptedTokenStore.KEY]!!
        assertTrue(stored.startsWith("v1:"))
        assertFalse(stored.contains(TOKEN))                 // never plaintext at rest
        assertEquals(TOKEN, store.load())
        // a second store over the same storage + key (= app restart) reads it back
        assertEquals(TOKEN, EncryptedTokenStore(kv, AesGcmCodec { key }).load())
        store.clear()
        assertNull(store.load()); assertTrue(kv.m.isEmpty())
    }

    @Test fun freshIvPerSealAndTamperOrWrongKeyIsRejected() {
        val key = aesKey()
        val codec = AesGcmCodec { key }
        val a = codec.seal(TOKEN); val b = codec.seal(TOKEN)
        assertNotEquals(a, b)                                // random IV each time
        assertEquals(12, java.util.Base64.getDecoder().decode(a.split(":")[1]).size)
        val parts = a.split(":")
        val ct = java.util.Base64.getDecoder().decode(parts[2]); ct[0] = (ct[0].toInt() xor 1).toByte()
        val tampered = parts[0] + ":" + parts[1] + ":" + java.util.Base64.getEncoder().encodeToString(ct)
        assertNull(codec.open(tampered))
        assertNull(AesGcmCodec { aesKey() }.open(a))           // other device key
        assertNull(codec.open("garbage"))
        // a store holding an unreadable value drops it (treated as signed out)
        val kv = MapKv().apply { put(EncryptedTokenStore.KEY, tampered) }
        assertNull(EncryptedTokenStore(kv, codec).load()); assertTrue(kv.m.isEmpty())
    }

    // ------------------------------------------------ headers sent

    @Test fun interceptorNeverSendsRoleOrActorHeaders() = runBlocking {
        val t = backend()
        val sneaky = object : AuthProvider {   // even a provider that tries is filtered
            override fun headers() = mapOf("Authorization" to "Bearer $TOKEN", "X-Role" to "owner",
                "x-actor" to "mallory", "X-ROLE" to "owner")
        }
        ApiClient("http://h", sneaky, t).me()
        val h = t.sent.single().headers
        assertEquals("Bearer $TOKEN", h["Authorization"])
        assertTrue(h.keys.none { it.lowercase() in setOf("x-role", "x-actor") })
    }

    @Test fun everyRequestFromSessionCarriesOnlyTheBearerToken() = runBlocking {
        val t = backend(customersStatus = 200)
        val store = EncryptedTokenStore(MapKv(), AesGcmCodec(aesKey().let { k -> { k } }))
        val s = SessionManager(store, t)
        s.login("http://h", " syn-owner ", "Right-password-123")
        assertTrue(s.client("http://h").customers().isEmpty())
        s.logout("http://h")
        assertEquals(4, t.sent.size)                         // login, me, customers, logout
        for (r in t.sent) {
            assertTrue(r.headers.keys.none { it.lowercase() in setOf("x-role", "x-actor") })
            if (!r.url.endsWith("/login")) assertEquals("Bearer $TOKEN", r.headers["Authorization"])
        }
        val login = t.sent.first()
        assertNull(login.headers["Authorization"])
        val body = JSONObject(login.body!!)
        assertEquals("token", body.getString("mode")); assertEquals("syn-owner", body.getString("username"))
        assertFalse(body.has("role"))
    }

    // ------------------------------------------------ login / me / logout

    @Test fun loginStoresTokenAndRoleComesFromMe() = runBlocking {
        val store = EncryptedTokenStore(MapKv(), AesGcmCodec(aesKey().let { k -> { k } }))
        val me = SessionManager(store, backend(ME_VIEWER)).login("http://h", "syn-viewer", "Right-password-123")
        assertEquals("viewer", me.role); assertFalse(me.canWrite); assertFalse(me.isOwner)
        assertEquals("syn-viewer", me.label)
        assertEquals(TOKEN, store.load())
    }

    @Test fun wrongPasswordIs401WithoutStoringOrSigningOut() = runBlocking {
        var signedOut = false
        val store = EncryptedTokenStore(MapKv(), AesGcmCodec(aesKey().let { k -> { k } }))
        val s = SessionManager(store, backend(), onUnauthorized = { signedOut = true })
        val e = runCatching { s.login("http://h", "syn-owner", "wrong") }.exceptionOrNull()
        assertTrue(e is ApiException && e.status == 401)
        assertNull(store.load()); assertFalse(signedOut)
    }

    @Test fun any401ClearsTokenAndSignsOut() = runBlocking {
        var signedOut = 0
        val store = EncryptedTokenStore(MapKv(), AesGcmCodec(aesKey().let { k -> { k } }))
        val s = SessionManager(store, backend(), onUnauthorized = { signedOut++ })
        s.login("http://h", "syn-owner", "Right-password-123")
        val e = runCatching { s.client("http://h").customers() }.exceptionOrNull()
        assertTrue(e is ApiException && e.status == 401)
        assertNull(store.load()); assertEquals(1, signedOut)
    }

    @Test fun restoreAfterRestartUsesStoredTokenAndExpiredOneSignsOut() = runBlocking {
        val key = aesKey(); val kv = MapKv()
        SessionManager(EncryptedTokenStore(kv, AesGcmCodec { key }), backend())
            .login("http://h", "syn-owner", "Right-password-123")
        val restored = SessionManager(EncryptedTokenStore(kv, AesGcmCodec { key }), backend()).restore("http://h")
        assertEquals("owner", restored!!.role); assertTrue(restored.isOwner && restored.canWrite)
        val expired = EncryptedTokenStore(kv, AesGcmCodec { key })
        assertNull(SessionManager(expired, backend(meStatus = 401)).restore("http://h"))
        assertNull(expired.load())
    }

    @Test fun logoutRevokesOnServerThenClearsEvenIfServerFails() = runBlocking {
        val key = aesKey()
        val t = backend()
        val store = EncryptedTokenStore(MapKv(), AesGcmCodec { key })
        val s = SessionManager(store, t)
        s.login("http://h", "syn-owner", "Right-password-123")
        assertTrue(s.logout("http://h"))
        assertTrue(t.sent.last().url.endsWith("/api/auth/logout") && t.sent.last().method == "POST")
        assertNull(store.load())
        val down = FakeTransport { throw java.io.IOException("unreachable") }
        store.save(TOKEN)
        assertFalse(SessionManager(store, down).logout("http://h"))
        assertNull(store.load())
    }

    @Test fun logoutClearsLocalSessionWhenRevokeFailsByNetworkErrorTimeoutOrServerError() = runBlocking {
        val failures: List<HttpTransport> = listOf(
            FakeTransport { throw java.io.IOException("network unreachable") },
            FakeTransport { throw java.net.SocketTimeoutException("timed out") },
            FakeTransport { throw java.net.UnknownHostException("no dns") },
            FakeTransport { HttpResponse(500, """{"detail":"boom"}""") },
            FakeTransport { HttpResponse(401, """{"detail":"login required"}""") },
        )
        for (t in failures) {
            val kv = MapKv()
            val store = EncryptedTokenStore(kv, AesGcmCodec(aesKey().let { k -> { k } }))
            store.save(TOKEN)
            assertFalse(SessionManager(store, t).logout("http://h"))   // not revoked...
            assertNull(store.load()); assertTrue(kv.m.isEmpty())        // ...but always cleared locally
            assertTrue((t as FakeTransport).sent.single().url.endsWith("/api/auth/logout"))
        }
        // no backend URL at all: still cleared, nothing sent
        val store = EncryptedTokenStore(MapKv(), AesGcmCodec(aesKey().let { k -> { k } }))
        store.save(TOKEN)
        assertFalse(SessionManager(store, FakeTransport { error("must not be called") }).logout(null))
        assertNull(store.load())
    }

    @Test fun bearerProviderSendsNothingWhenSignedOut() {
        val store = EncryptedTokenStore(MapKv(), AesGcmCodec(aesKey().let { k -> { k } }))
        assertEquals(emptyMap<String, String>(), BearerAuthProvider(store).headers())
    }

    @Test fun meParsesServerRoleAndPermissions() {
        val o = Me.from(JSONObject(ME_OWNER))
        assertEquals("Synthetic Owner", o.label); assertTrue(o.isOwner)
        val staff = Me.from(JSONObject("""{"user":{"username":"s","display_name":"","role":"staff"}}"""))
        assertTrue(staff.canWrite); assertFalse(staff.isOwner); assertEquals("s", staff.label)
    }
}
