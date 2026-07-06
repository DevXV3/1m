"""Rewrite the OpenFreeMap Liberty style into a fully offline style.

- Points the vector source at the bundled thailand.pmtiles asset.
- Drops the online natural-earth raster (ne2_shaded) source and its layers.
- Redirects glyphs and sprite to bundled assets.
"""
import json
import sys

src = sys.argv[1]
dst = sys.argv[2]

with open(src, encoding="utf-8") as fh:
    style = json.load(fh)

# Offline asset endpoints (served from the app's assets/ folder)
style["glyphs"] = "asset://glyphs/{fontstack}/{range}.pbf"
style["sprite"] = "asset://sprite/ofm"

# Replace the remote OpenMapTiles vector source with the local PMTiles archive
style["sources"] = {
    "openmaptiles": {
        "type": "vector",
        "url": "pmtiles://asset://thailand.pmtiles",
    }
}

# Drop any layer that referenced the removed ne2_shaded raster source
kept = [ly for ly in style["layers"] if ly.get("source") != "ne2_shaded"]
dropped = len(style["layers"]) - len(kept)
style["layers"] = kept

style["name"] = "One M Transport (offline)"

with open(dst, "w", encoding="utf-8") as fh:
    json.dump(style, fh, ensure_ascii=False, separators=(",", ":"))

fonts = set()
for ly in kept:
    tf = ly.get("layout", {}).get("text-font")
    if isinstance(tf, list):
        for f in tf:
            if isinstance(f, str):
                fonts.add(f)
print(f"dropped {dropped} raster layers, kept {len(kept)} layers")
print("fonts:", sorted(fonts))
