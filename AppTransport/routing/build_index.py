"""One-time build of the routing graph cache from the Thailand .pbf.

Usage:
    python build_index.py [pbf_path] [out_dir]
"""
import sys
import time
from pathlib import Path

from apptransport_routing.graph import build_graph

DEFAULT_PBF = Path(__file__).resolve().parents[1] / "mapdata" / "data" / "sources" / "thailand.osm.pbf"
DEFAULT_OUT = Path(__file__).resolve().parent / "cache"


def main() -> None:
    pbf = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PBF
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    if not pbf.exists():
        raise SystemExit(f"pbf not found: {pbf}")

    t0 = time.time()
    graph = build_graph(pbf)
    cache = out / "thailand_graph.npz"
    graph.save(cache)
    size_mb = cache.stat().st_size / (1024 * 1024)
    print(f"[done] saved {cache} ({size_mb:.0f} MB), "
          f"{graph.n_nodes:,} nodes / {graph.n_edges:,} edges, "
          f"total {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
