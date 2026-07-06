package com.onem.apptransport.ui

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.MyLocation
import androidx.compose.material.icons.filled.Public
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.onem.apptransport.map.MapAssets
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.maplibre.android.camera.CameraPosition
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.location.LocationComponentActivationOptions
import org.maplibre.android.location.modes.CameraMode
import org.maplibre.android.location.modes.RenderMode
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.Style

// Live OpenFreeMap style, used only when the user switches to online mode
private const val ONLINE_STYLE = "https://tiles.openfreemap.org/styles/liberty"

// Ubon Ratchathani city center as the default camera position
private val DEFAULT_CENTER = LatLng(15.2287, 104.8564)
private const val DEFAULT_ZOOM = 12.0

@Composable
fun MapScreen() {
    val context = LocalContext.current
    val mapView = rememberMapViewWithLifecycle()
    var mapLibreMap by remember { mutableStateOf<MapLibreMap?>(null) }
    var offline by remember { mutableStateOf(true) }
    val snackbarHostState = remember { SnackbarHostState() }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { grants ->
        if (grants.values.any { it }) {
            mapLibreMap?.let { enableUserLocation(context, it) }
        }
    }

    LaunchedEffect(mapView) {
        mapView.getMapAsync { map ->
            mapLibreMap = map
            map.cameraPosition = CameraPosition.Builder()
                .target(DEFAULT_CENTER)
                .zoom(DEFAULT_ZOOM)
                .build()
        }
    }

    // (Re)apply the style whenever the offline/online mode changes
    LaunchedEffect(mapLibreMap, offline) {
        val map = mapLibreMap ?: return@LaunchedEffect
        val builder = if (offline) {
            // Copying the bundled archive to disk on first run is blocking I/O
            val json = withContext(Dispatchers.IO) { MapAssets.offlineStyleJson(context) }
            Style.Builder().fromJson(json)
        } else {
            Style.Builder().fromUri(ONLINE_STYLE)
        }
        map.setStyle(builder) {
            map.uiSettings.isCompassEnabled = true
            if (hasLocationPermission(context)) {
                enableUserLocation(context, map)
            }
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        floatingActionButton = {
            Column(
                horizontalAlignment = Alignment.End,
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                ExtendedFloatingActionButton(
                    onClick = { offline = !offline },
                    icon = {
                        Icon(
                            if (offline) Icons.Filled.CloudOff else Icons.Filled.Public,
                            contentDescription = null,
                        )
                    },
                    text = { Text(if (offline) "ออฟไลน์" else "ออนไลน์") },
                )
                FloatingActionButton(
                    onClick = {
                        val map = mapLibreMap ?: return@FloatingActionButton
                        if (hasLocationPermission(context)) {
                            enableUserLocation(context, map)
                            recenterOnUser(map)
                        } else {
                            permissionLauncher.launch(
                                arrayOf(
                                    Manifest.permission.ACCESS_FINE_LOCATION,
                                    Manifest.permission.ACCESS_COARSE_LOCATION,
                                )
                            )
                        }
                    },
                ) {
                    Icon(Icons.Filled.MyLocation, contentDescription = "ตำแหน่งของฉัน")
                }
            }
        },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding)) {
            AndroidView(factory = { mapView }, modifier = Modifier.fillMaxSize())
        }
    }
}

/** Keeps the MapView in sync with the host lifecycle (required by MapLibre). */
@Composable
private fun rememberMapViewWithLifecycle(): MapView {
    val context = LocalContext.current
    val mapView = remember { MapView(context) }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_CREATE -> mapView.onCreate(null)
                Lifecycle.Event.ON_START -> mapView.onStart()
                Lifecycle.Event.ON_RESUME -> mapView.onResume()
                Lifecycle.Event.ON_PAUSE -> mapView.onPause()
                Lifecycle.Event.ON_STOP -> mapView.onStop()
                Lifecycle.Event.ON_DESTROY -> mapView.onDestroy()
                else -> {}
            }
        }
        lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer) }
    }
    return mapView
}

private fun hasLocationPermission(context: Context): Boolean =
    ContextCompat.checkSelfPermission(
        context, Manifest.permission.ACCESS_FINE_LOCATION
    ) == PackageManager.PERMISSION_GRANTED ||
        ContextCompat.checkSelfPermission(
            context, Manifest.permission.ACCESS_COARSE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

@SuppressLint("MissingPermission")
private fun enableUserLocation(context: Context, map: MapLibreMap) {
    val style: Style = map.style ?: return
    val component = map.locationComponent
    if (!component.isLocationComponentActivated) {
        component.activateLocationComponent(
            LocationComponentActivationOptions.builder(context, style)
                .useDefaultLocationEngine(true)
                .build()
        )
    }
    component.isLocationComponentEnabled = true
    component.renderMode = RenderMode.COMPASS
}

@SuppressLint("MissingPermission")
private fun recenterOnUser(map: MapLibreMap) {
    val component = map.locationComponent
    if (!component.isLocationComponentActivated) return
    component.cameraMode = CameraMode.TRACKING
    component.lastKnownLocation?.let { location ->
        map.animateCamera(
            CameraUpdateFactory.newLatLngZoom(
                LatLng(location.latitude, location.longitude), 15.0
            )
        )
    }
}
