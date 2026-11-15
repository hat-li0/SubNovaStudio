package com.subtitlepro.studio.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val DarkBackground = Color(0xFF0D1117)
val DarkSurface = Color(0xFF161B22)
val DarkCard = Color(0xFF21262D)
val DarkBorder = Color(0xFF30363D)

val NeonCyan = Color(0xFF00E5FF)
val NeonGreen = Color(0xFF00E676)
val AmberAccent = Color(0xFFFFD600)
val DangerRed = Color(0xFFFF5252)

val TextPrimary = Color(0xFFF0F6FC)
val TextSecondary = Color(0xFF8B949E)
val TextTertiary = Color(0xFF6E7681)

private val AppDarkColorScheme = darkColorScheme(
    primary = NeonCyan,
    onPrimary = Color.Black,
    primaryContainer = Color(0xFF00363D),
    onPrimaryContainer = NeonCyan,
    secondary = NeonGreen,
    onSecondary = Color.Black,
    secondaryContainer = Color(0xFF00381B),
    onSecondaryContainer = NeonGreen,
    tertiary = AmberAccent,
    background = DarkBackground,
    surface = DarkSurface,
    surfaceVariant = DarkCard,
    outline = DarkBorder,
    error = DangerRed,
    onBackground = TextPrimary,
    onSurface = TextPrimary
)

@Composable
fun SubtitleProTheme(
    darkTheme: Boolean = true,
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = AppDarkColorScheme,
        content = content
    )
}
