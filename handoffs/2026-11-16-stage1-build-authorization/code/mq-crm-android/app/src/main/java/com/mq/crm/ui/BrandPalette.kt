package com.mq.crm.ui

/**
 * Black-and-gold palette shared with the web CRM (Batch 009c/009d:
 * web/styles.css :root). Plain ARGB values with no Compose types, so the JVM unit
 * tests can check contrast without a device. Presentation only.
 */
object BrandPalette {
    const val BG = 0xFF0E0E10          // --mq-bg
    const val SURFACE = 0xFF141416     // --mq-surface (top bar, nav bar)
    const val CARD = 0xFF1B1B1E        // --mq-card
    const val CARD_2 = 0xFF222226      // --mq-card-2
    const val BORDER = 0xFF34312B      // --mq-border (decorative dividers)
    const val FIELD_BORDER = 0xFF78736A // input outline (>=3:1 on card and field fill)
    const val GOLD = 0xFFC9A54C        // --mq-gold
    const val GOLD_HI = 0xFFD9B865     // --mq-gold-hi
    const val GOLD_SOFT = 0xFFE9D6A6   // test-data chip text
    const val ON_GOLD = 0xFF111111     // --mq-on-gold
    const val TEXT = 0xFFF4F2EC        // --mq-text
    const val MUTED = 0xFFA9A59C       // --mq-muted
    const val ERROR = 0xFFF3B1A8       // error text on dark (web .is-error)

    /** WCAG 2.x relative luminance of an opaque ARGB colour. */
    fun luminance(argb: Long): Double {
        fun ch(shift: Int): Double {
            val c = ((argb shr shift) and 0xFF).toDouble() / 255.0
            return if (c <= 0.03928) c / 12.92 else Math.pow((c + 0.055) / 1.055, 2.4)
        }
        return 0.2126 * ch(16) + 0.7152 * ch(8) + 0.0722 * ch(0)
    }

    /** WCAG contrast ratio, 1.0 .. 21.0. */
    fun contrast(a: Long, b: Long): Double {
        val la = luminance(a); val lb = luminance(b)
        return (maxOf(la, lb) + 0.05) / (minOf(la, lb) + 0.05)
    }
}
