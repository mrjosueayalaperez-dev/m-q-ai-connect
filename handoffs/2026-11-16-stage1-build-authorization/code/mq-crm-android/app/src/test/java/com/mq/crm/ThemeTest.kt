package com.mq.crm

import com.mq.crm.ui.BrandPalette as P
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** v0.3.0 black-and-gold restyle: palette parity with the web and WCAG AA contrast. */
class ThemeTest {
    private fun aa(fg: Long, bg: Long, min: Double = 4.5) {
        val r = P.contrast(fg, bg)
        assertTrue("contrast %.2f < %.1f".format(r, min), r >= min)
    }

    @Test fun paletteMatchesWebDashboardTokens() {
        // values copied from web/styles.css :root (Batch 009c/009d)
        assertEquals(0xFF0E0E10, P.BG); assertEquals(0xFFC9A54C, P.GOLD)
        assertEquals(0xFFF4F2EC, P.TEXT); assertEquals(0xFFA9A59C, P.MUTED)
        assertEquals(0xFF1B1B1E, P.CARD); assertEquals(0xFF111111, P.ON_GOLD)
    }

    @Test fun bodyAndMutedTextMeetAaOnEveryBackground() {
        for (bg in listOf(P.BG, P.SURFACE, P.CARD, P.CARD_2)) {
            aa(P.TEXT, bg); aa(P.MUTED, bg); aa(P.GOLD, bg); aa(P.GOLD_SOFT, bg); aa(P.ERROR, bg)
        }
    }

    @Test fun goldButtonTextMeetsAa() {
        aa(P.ON_GOLD, P.GOLD); aa(P.BG, P.GOLD); aa(P.ON_GOLD, P.GOLD_HI)
    }

    @Test fun fieldOutlineMeetsNonTextContrast() {
        // WCAG 1.4.11: input boundaries need 3:1 against the field/card background
        for (bg in listOf(P.CARD, P.CARD_2)) aa(P.FIELD_BORDER, bg, 3.0)
    }

    @Test fun contrastHelperIsCorrect() {
        assertEquals(21.0, P.contrast(0xFF000000, 0xFFFFFFFF), 0.01)
        assertEquals(1.0, P.contrast(0xFFC9A54C, 0xFFC9A54C), 1e-9)
    }

    @Test fun launcherAndWindowColoursUseTheSamePalette() {
        val themes = File("src/main/res/values/themes.xml").readText()
        assertTrue(themes.contains("#FF0E0E10")); assertTrue(themes.contains("#FFC9A54C"))
        assertTrue(!themes.contains("#FFD4AF37"))
    }

    @Test fun allFourLanguagesHaveTheSameStringKeys() {
        fun keys(dir: String) = Regex("""<string name="([^"]+)"(?![^>]*translatable="false")""")
            .findAll(File("src/main/res/$dir/strings.xml").readText()).map { it.groupValues[1] }.toSet()
        val en = keys("values")
        for (d in listOf("values-es", "values-pt", "values-ht")) assertEquals(d, en, keys(d))
    }

    @Test fun testOnlyLabelStillPresentInEveryLanguage() {
        for (d in listOf("values", "values-es", "values-pt", "values-ht")) {
            val s = File("src/main/res/$d/strings.xml").readText()
            // translated labels keep the warning in capitals (e.g. "VERSIÓN DE PRUEBA")
            val m = Regex("""name="test_only_banner">([^<]+)<""").find(s)
            assertTrue(d, m != null)
            val head = m!!.groupValues[1].substringBefore("·").trim()
            assertTrue(d, head.length >= 6 && head == head.uppercase())
        }
    }
}
