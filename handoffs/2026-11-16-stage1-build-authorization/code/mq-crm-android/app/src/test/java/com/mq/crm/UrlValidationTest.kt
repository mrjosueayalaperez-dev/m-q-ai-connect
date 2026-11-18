package com.mq.crm

import com.mq.crm.data.Format
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** v0.3.1: server URL field - HTTPS required except emulator/localhost http in debug. */
class UrlValidationTest {
    private fun ok(u: String, debug: Boolean = true) = Format.normalizeBaseUrl(u, debug)

    @Test fun anyHttpsServerIsAcceptedIncludingTunnelUrls() {
        assertEquals("https://abc-def-ghi.trycloudflare.com", ok(" https://abc-def-ghi.trycloudflare.com/ "))
        assertEquals("https://crm.example.test:8443", ok("https://crm.example.test:8443"))
        assertEquals("https://crm.example.test", ok("https://crm.example.test", debug = false))
        assertEquals("HTTPS://CRM.EXAMPLE.TEST", ok("HTTPS://CRM.EXAMPLE.TEST"))
    }

    @Test fun plainHttpOnlyForEmulatorOrLocalhostInDebug() {
        assertEquals("http://10.0.2.2:8000", ok("http://10.0.2.2:8000"))
        assertEquals("http://localhost:8000", ok("http://localhost:8000"))
        assertEquals("http://127.0.0.1:8810", ok("http://127.0.0.1:8810/"))
        assertNull(ok("http://crm.example.test"))
        assertNull(ok("http://abc.trycloudflare.com"))
        assertNull(ok("http://192.168.1.20:8000"))
        assertNull(ok("http://10.0.2.2.evil.test"))
        assertNull(ok("http://localhost.evil.test:8000"))
    }

    @Test fun releaseBehaviourRefusesAllPlainHttp() {
        assertNull(ok("http://10.0.2.2:8000", debug = false))
        assertNull(ok("http://localhost", debug = false))
    }

    @Test fun malformedUrlsAreRefused() {
        for (u in listOf("", "   ", "crm.example.test", "ftp://x", "https://", "https:///path",
                "https://user:pw@crm.example.test", "https://crm.example.test:abc",
                "https://crm.example.test:0", "https://crm.example.test:70000", "https://crm .example.test",
                "https://.example.test", "https://crm.example.test:", "javascript:alert(1)")) {
            assertNull(u, ok(u))
        }
    }

    @Test fun debugBuildNetworkConfigOnlyAllowsLocalCleartext() {
        val x = File("src/debug/res/xml/network_security_config.xml").readText()
        assertTrue(x.contains("""<base-config cleartextTrafficPermitted="false" />"""))
        for (h in Format.LOCAL_HTTP_HOSTS) assertTrue(h, x.contains(">$h</domain>"))
        val main = File("src/main/res/xml/network_security_config.xml").readText()
        assertTrue(main.contains("""cleartextTrafficPermitted="false""""))
        assertTrue(!main.contains("domain-config"))
    }
}
