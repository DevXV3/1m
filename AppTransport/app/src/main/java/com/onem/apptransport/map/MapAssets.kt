package com.onem.apptransport.map

import android.content.Context
import java.io.File

/**
 * Prepares the offline map resources.
 *
 * MapLibre's PMTiles reader needs random access to the archive. Reading a large
 * archive straight from `asset://` returns wrong bytes on some devices (the gzip
 * directory fails with "incorrect header check"), so the archive is copied once
 * into the app's private files dir and referenced via `file://`.
 */
object MapAssets {

    private const val PMTILES_ASSET = "thailand.pmtiles"
    private const val STYLE_ASSET = "style/offline.json"

    /** Copies the bundled PMTiles archive to internal storage once, returns its file. */
    private fun ensurePmtiles(context: Context): File {
        val dst = File(context.filesDir, PMTILES_ASSET)
        val expectedSize = context.assets.openFd(PMTILES_ASSET).use { it.length }
        if (dst.exists() && dst.length() == expectedSize) return dst
        context.assets.open(PMTILES_ASSET).use { input ->
            dst.outputStream().use { output -> input.copyTo(output, bufferSize = 1 shl 20) }
        }
        return dst
    }

    /**
     * Returns the offline style JSON with the PMTiles source pointed at the
     * on-disk copy. Glyphs and sprite stay on `asset://` (small files read fine).
     */
    fun offlineStyleJson(context: Context): String {
        val pmtiles = ensurePmtiles(context)
        val fileUrl = "pmtiles://file://${pmtiles.absolutePath}"
        val json = context.assets.open(STYLE_ASSET).bufferedReader().use { it.readText() }
        return json.replace("pmtiles://asset://thailand.pmtiles", fileUrl)
    }
}
