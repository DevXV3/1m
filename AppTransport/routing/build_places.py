"""One-time build of the geocode place index from the Thailand .pbf.

Usage:
    python build_places.py [pbf_path] [out_dir]
"""
import sys
import time
from pathlib import Path

from apptransport_routing.geocode import build_place_index

DEFAULT_PBF = Path(__file__).resolve().parents[1] / "mapdata" / "data" / "sources" / "thailand.osm.pbf"
DEFAULT_OUT = Path(__file__).resolve().parent / "cache"


def main() -> None:
    pbf = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PBF
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    if not pbf.exists():
        raise SystemExit(f"pbf not found: {pbf}")

    t0 = time.time()
    n = build_place_index(pbf, out / "places.json")
    print(f"[done] indexed {n:,} places in {time.time()-t0:.1f}s -> {out/'places.json'}")


if __name__ == "__main__":
    main()
