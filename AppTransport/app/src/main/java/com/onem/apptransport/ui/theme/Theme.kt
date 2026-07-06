package com.onem.apptransport.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Color(0xFF1565C0),
    onPrimary = Color.White,
    secondary = Color(0xFF00897B),
    onSecondary = Color.White,
)

@Composable
fun AppTransportTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = LightColors, content = content)
}
