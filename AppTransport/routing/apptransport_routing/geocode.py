"""Tiny offline geocoder built from OSM named places and POIs.

Extracts place/POI names (Thai + English) into a JSON index, then answers
substring/fuzzy name lookups. Good enough to turn a name an AI was given into a
coordinate; not a full address geocoder.
"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import osmium

# OSM place ranks we index, most prominent first (for tie-breaking).
PLACE_RANK = {
    "city": 0, "town": 1, "municipality": 1, "suburb": 2, "village": 3,
    "neighbourhood": 4, "hamlet": 5, "quarter": 4,
}
# POI tags worth indexing for delivery destinations.
POI_KEYS = ("amenity", "shop", "office", "industrial", "building", "tourism")


@dataclass
class Place:
    name: str
    lat: float
    lon: float
    kind: str
    name_en: str = ""


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip().lower()


class _PlaceCollector(osmium.SimpleHandler):
    def __init__(self) -> None:
        super().__init__()
        self.places: list[dict] = []

    def _add(self, name, name_en, lat, lon, kind):
        self.places.append({"name": name, "name_en": name_en or "",
                            "lat": round(lat, 6), "lon": round(lon, 6), "kind": kind})

    def node(self, n: "osmium.osm.Node") -> None:
        tags = n.tags
        name = tags.get("name")
        if not name or not n.location.valid():
            return
        name_en = tags.get("name:en", "")
        place = tags.get("place")
        if place in PLACE_RANK:
            self._add(name, name_en, n.location.lat, n.location.lon, f"place:{place}")
            return
        for key in POI_KEYS:
            if key in tags:
                self._add(name, name_en, n.location.lat, n.location.lon,
                          f"{key}:{tags.get(key)}")
                return


def build_place_index(pbf_path: str | Path, out_path: str | Path) -> int:
    col = _PlaceCollector()
    col.apply_file(str(pbf_path), locations=True)
    Path(out_path).write_text(
        json.dumps(col.places, ensure_ascii=False), encoding="utf-8"
    )
    return len(col.places)


class Geocoder:
    def __init__(self, places: list[dict]):
        self._places = places
        for p in self._places:
            p["_n"] = _norm(p["name"])
            p["_ne"] = _norm(p.get("name_en", ""))

    @classmethod
    def from_index(cls, index_path: str | Path) -> "Geocoder":
        return cls(json.loads(Path(index_path).read_text(encoding="utf-8")))

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Return best-matching places as dicts sorted by relevance."""
        q = _norm(query)
        scored = []
        for p in self._places:
            name, name_en = p["_n"], p["_ne"]
            if q in name or (name_en and q in name_en):
                # exact substring: rank by place prominence then name length
                rank = PLACE_RANK.get(p["kind"].split(":")[-1], 9)
                score = 1000 - rank * 10 - len(name)
            else:
                ratio = max(
                    SequenceMatcher(None, q, name).ratio(),
                    SequenceMatcher(None, q, name_en).ratio() if name_en else 0,
                )
                if ratio < 0.6:
                    continue
                score = ratio * 100
            scored.append((score, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for _, p in scored[:limit]:
            out.append({"name": p["name"], "name_en": p["name_en"],
                        "lat": p["lat"], "lon": p["lon"], "kind": p["kind"]})
        return out
