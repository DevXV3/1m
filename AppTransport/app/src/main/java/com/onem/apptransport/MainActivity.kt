package com.onem.apptransport

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.onem.apptransport.ui.MapScreen
import com.onem.apptransport.ui.theme.AppTransportTheme
import org.maplibre.android.MapLibre

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // MapLibre must be initialized before any MapView is created
        MapLibre.getInstance(this)
        enableEdgeToEdge()
        setContent {
            AppTransportTheme {
                MapScreen()
            }
        }
    }
}
