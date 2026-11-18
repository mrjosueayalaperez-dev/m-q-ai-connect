package com.mq.crm.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// v0.3.0: black-and-gold look matching the web sign-in and dashboard.
// Presentation only: no auth, session or data change.
val Gold = Color(BrandPalette.GOLD)
val GoldHi = Color(BrandPalette.GOLD_HI)
val GoldSoft = Color(BrandPalette.GOLD_SOFT)
val GoldDim = Color(0xFF8C7322)
val Ink = Color(BrandPalette.BG)
val TopBar = Color(BrandPalette.SURFACE)
val Panel = Color(BrandPalette.CARD)
val Panel2 = Color(BrandPalette.CARD_2)
val Line = Color(BrandPalette.BORDER)
val FieldLine = Color(BrandPalette.FIELD_BORDER)
val TextMain = Color(BrandPalette.TEXT)
val Muted = Color(BrandPalette.MUTED)
val Warn = Color(BrandPalette.ERROR)
val Cream = Color(BrandPalette.MUTED)

private val scheme = darkColorScheme(
    primary = Gold, onPrimary = Color(BrandPalette.ON_GOLD),
    primaryContainer = Panel2, onPrimaryContainer = GoldHi,
    secondary = GoldHi, onSecondary = Color(BrandPalette.ON_GOLD),
    secondaryContainer = Color(0x33C9A54C), onSecondaryContainer = GoldHi,
    background = Ink, onBackground = TextMain,
    surface = Panel, onSurface = TextMain,
    surfaceVariant = Panel2, onSurfaceVariant = Muted,
    surfaceContainerLowest = Ink, surfaceContainerLow = TopBar, surfaceContainer = Panel,
    surfaceContainerHigh = Panel, surfaceContainerHighest = Panel,
    outline = FieldLine, outlineVariant = Line,
    error = Warn, onError = Color(BrandPalette.ON_GOLD),
)

// System font (no downloaded or CDN fonts), with the web's weights and tracking.
private val type = Typography().let { t ->
    t.copy(
        headlineSmall = t.headlineSmall.copy(fontWeight = FontWeight.SemiBold, letterSpacing = (-0.2).sp),
        titleLarge = t.titleLarge.copy(fontWeight = FontWeight.SemiBold, fontSize = 20.sp),
        titleMedium = t.titleMedium.copy(fontWeight = FontWeight.SemiBold),
        labelSmall = t.labelSmall.copy(letterSpacing = 0.6.sp),
    )
}

private val shapes = Shapes(
    small = RoundedCornerShape(8.dp), medium = RoundedCornerShape(12.dp), large = RoundedCornerShape(14.dp),
)

/** Small-caps style card heading, like the web's uppercase card titles. */
val CardLabel = TextStyle(fontSize = 11.sp, fontWeight = FontWeight.SemiBold, letterSpacing = 0.8.sp)

@Composable
fun MQTheme(content: @Composable () -> Unit) =
    MaterialTheme(colorScheme = scheme, typography = type, shapes = shapes, content = content)

/** Graphite card with a thin border; `accent` = the gold-bordered highlight card. */
@Composable
fun MQCard(modifier: Modifier = Modifier, accent: Boolean = false, content: @Composable ColumnScope.() -> Unit) =
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = Panel, contentColor = TextMain),
        border = BorderStroke(1.dp, if (accent) Gold.copy(alpha = 0.7f) else Line),
        content = content,
    )
