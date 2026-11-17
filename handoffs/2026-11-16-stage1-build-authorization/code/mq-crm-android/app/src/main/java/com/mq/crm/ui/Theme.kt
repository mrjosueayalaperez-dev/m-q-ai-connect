package com.mq.crm.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val Gold = Color(0xFFD4AF37)
val GoldDim = Color(0xFF8C7322)
val Ink = Color(0xFF0B0B0B)
val Panel = Color(0xFF1A1A1A)
val Warn = Color(0xFFB3261E)
val Cream = Color(0xFFE8E0C8)

private val scheme = darkColorScheme(
    primary = Gold, onPrimary = Ink, secondary = GoldDim, onSecondary = Ink,
    background = Ink, onBackground = Color(0xFFEDEDED),
    surface = Panel, onSurface = Color(0xFFEDEDED),
    surfaceVariant = Color(0xFF242424), onSurfaceVariant = Color(0xFFCFCFCF),
    error = Warn,
)

@Composable
fun MQTheme(content: @Composable () -> Unit) =
    MaterialTheme(colorScheme = scheme, content = content)
