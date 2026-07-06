"""Build and query a compact driving graph from an OSM .pbf extract.

The graph is stored as CSR-style numpy arrays (small memory footprint, fast to
load) instead of a networkx object. Routing uses a bidirectional Dijkstra over
edge travel time or distance.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from heapq import heappop, heappush
from pathlib import Path

import numpy as np
import osmium

# Driving speed (km/h) assumed per OSM highway class when no maxspeed tag exists.
HIGHWAY_SPEED_KMH = {
    "motorway": 100, "motorway_link": 60,
    "trunk": 90, "trunk_link": 50,
    "primary": 70, "primary_link": 45,
    "secondary": 60, "secondary_link": 40,
    "tertiary": 50, "tertiary_link": 35,
    "unclassified": 40,
    "residential": 30,
    "living_street": 15,
    "service": 20,
    "road": 40,
}

# Highway classes that are implicitly one-way in the OSM driving model.
IMPLICIT_ONEWAY = {"motorway", "motorway_link", "trunk_link"}

EARTH_RADIUS_M = 6_371_000.0


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _parse_maxspeed(value: str) -> float | None:
    """Best-effort parse of an OSM maxspeed tag into km/h."""
    if not value:
        return None
    value = value.strip().lower()
    try:
        if value.endswith("mph"):
            return float(value.replace("mph", "").strip()) * 1.60934
        return float(value.split()[0])
    except (ValueError, IndexError):
        return None


class _WayCollector(osmium.SimpleHandler):
    """First/only pass: collect drivable edges with inline node locations."""

    def __init__(self) -> None:
        super().__init__()
        self.edges_u: list[int] = []
        self.edges_v: list[int] = []
        self.edges_len: list[float] = []
        self.edges_time: list[float] = []
        self.node_lat: dict[int, float] = {}
        self.node_lon: dict[int, float] = {}
        self.ways = 0

    def way(self, w: "osmium.osm.Way") -> None:
        hw = w.tags.get("highway")
        if hw not in HIGHWAY_SPEED_KMH:
            return
        if w.tags.get("access") in ("no", "private"):
            return

        speed = _parse_maxspeed(w.tags.get("maxspeed", "")) or HIGHWAY_SPEED_KMH[hw]

        oneway = w.tags.get("oneway", "")
        forward = backward = True
        if oneway in ("yes", "true", "1") or hw in IMPLICIT_ONEWAY \
                or w.tags.get("junction") == "roundabout":
            backward = False
        if oneway == "-1":
            forward, backward = False, True

        prev_id = None
        prev_lat = prev_lon = 0.0
        for n in w.nodes:
            if not n.location.valid():
                prev_id = None
                continue
            nid = n.ref
            lat, lon = n.location.lat, n.location.lon
            self.node_lat[nid] = lat
            self.node_lon[nid] = lon
            if prev_id is not None:
                dist = _haversine_m(prev_lat, prev_lon, lat, lon)
                if dist > 0:
                    t = dist / (speed / 3.6)  # seconds
                    if forward:
                        self.edges_u.append(prev_id)
                        self.edges_v.append(nid)
                        self.edges_len.append(dist)
                        self.edges_time.append(t)
                    if backward:
                        self.edges_u.append(nid)
                        self.edges_v.append(prev_id)
                        self.edges_len.append(dist)
                        self.edges_time.append(t)
            prev_id, prev_lat, prev_lon = nid, lat, lon
        self.ways += 1


@dataclass
class RoadGraph:
    """Compact CSR driving graph. Arrays are indexed by contiguous node index."""

    node_ids: np.ndarray      # int64[n]   original OSM node id
    lat: np.ndarray           # float32[n]
    lon: np.ndarray           # float32[n]
    indptr: np.ndarray        # int64[n+1] CSR row pointers
    neighbors: np.ndarray     # int32[m]   destination node index per edge
    edge_time: np.ndarray     # float32[m] seconds
    edge_dist: np.ndarray     # float32[m] meters

    @property
    def n_nodes(self) -> int:
        return len(self.lat)

    @property
    def n_edges(self) -> int:
        return len(self.neighbors)

    def nearest_node(self, lat: float, lon: float) -> int:
        """Index of the graph node closest to (lat, lon), fast numpy scan."""
        dlat = self.lat - lat
        dlon = (self.lon - lon) * math.cos(math.radians(lat))
        return int(np.argmin(dlat * dlat + dlon * dlon))

    def shortest_path(self, src: int, dst: int, weight: str = "time"):
        """A* over the directed graph. Returns (cost, node_index_path) or (inf, [])."""
        return _astar(self, src, dst, weight)

    def save(self, path: str | Path) -> None:
        np.savez_compressed(
            path,
            node_ids=self.node_ids, lat=self.lat, lon=self.lon,
            indptr=self.indptr, neighbors=self.neighbors,
            edge_time=self.edge_time, edge_dist=self.edge_dist,
        )


# Fastest driving speed used to make the time heuristic admissible (km/h -> m/s).
_MAX_SPEED_MS = 120.0 / 3.6


def _astar(g: "RoadGraph", src: int, dst: int, weight: str):
    """Forward A* with a haversine heuristic. Correct on directed graphs."""
    if src == dst:
        return 0.0, [src]
    indptr, neighbors = g.indptr, g.neighbors
    w = g.edge_time if weight == "time" else g.edge_dist
    lat, lon = g.lat, g.lon
    dst_lat, dst_lon = float(lat[dst]), float(lon[dst])
    time_weight = weight == "time"

    def h(node: int) -> float:
        # straight-line lower bound to dst; for time, divide by top speed
        d = _haversine_m(float(lat[node]), float(lon[node]), dst_lat, dst_lon)
        return d / _MAX_SPEED_MS if time_weight else d

    n = len(indptr) - 1
    INF = float("inf")
    gscore = np.full(n, INF, dtype=np.float64)
    prev = np.full(n, -1, dtype=np.int64)
    closed = np.zeros(n, dtype=bool)
    gscore[src] = 0.0
    pq = [(h(src), 0.0, src)]

    while pq:
        _, gu, u = heappop(pq)
        if u == dst:
            break
        if closed[u]:
            continue
        closed[u] = True
        for e in range(indptr[u], indptr[u + 1]):
            v = int(neighbors[e])
            if closed[v]:
                continue
            ng = gu + w[e]
            if ng < gscore[v]:
                gscore[v] = ng
                prev[v] = u
                heappush(pq, (ng + h(v), ng, v))

    if gscore[dst] == INF:
        return INF, []
    path = []
    x = dst
    while x != -1:
        path.append(int(x))
        x = prev[x]
    path.reverse()
    return float(gscore[dst]), path


def build_graph(pbf_path: str | Path, verbose: bool = True) -> RoadGraph:
    """Parse the .pbf and build a RoadGraph."""
    pbf_path = Path(pbf_path)
    t0 = time.time()
    if verbose:
        print(f"[graph] reading {pbf_path.name} ...", flush=True)
    col = _WayCollector()
    # locations=True fills node coordinates while streaming ways
    col.apply_file(str(pbf_path), locations=True)
    if verbose:
        print(f"[graph] {col.ways:,} drivable ways, "
              f"{len(col.edges_u):,} directed edges, "
              f"{len(col.node_lat):,} nodes in {time.time()-t0:.1f}s", flush=True)

    # Map original OSM node ids -> contiguous indices, keeping only used nodes.
    used = sorted(col.node_lat.keys())
    id_to_idx = {nid: i for i, nid in enumerate(used)}
    n = len(used)
    lat = np.fromiter((col.node_lat[i] for i in used), dtype=np.float32, count=n)
    lon = np.fromiter((col.node_lon[i] for i in used), dtype=np.float32, count=n)
    node_ids = np.asarray(used, dtype=np.int64)

    u_idx = np.fromiter((id_to_idx[i] for i in col.edges_u), dtype=np.int64,
                        count=len(col.edges_u))
    v_idx = np.fromiter((id_to_idx[i] for i in col.edges_v), dtype=np.int32,
                        count=len(col.edges_v))
    e_time = np.asarray(col.edges_time, dtype=np.float32)
    e_dist = np.asarray(col.edges_len, dtype=np.float32)

    # Build CSR by sorting edges on source index.
    order = np.argsort(u_idx, kind="stable")
    u_sorted = u_idx[order]
    neighbors = v_idx[order]
    edge_time = e_time[order]
    edge_dist = e_dist[order]
    indptr = np.zeros(n + 1, dtype=np.int64)
    counts = np.bincount(u_sorted, minlength=n)
    indptr[1:] = np.cumsum(counts)

    if verbose:
        print(f"[graph] built CSR: {n:,} nodes / {len(neighbors):,} edges "
              f"in {time.time()-t0:.1f}s", flush=True)
    return RoadGraph(node_ids, lat, lon, indptr, neighbors, edge_time, edge_dist)


def load_graph(cache_path: str | Path) -> RoadGraph:
    d = np.load(cache_path)
    return RoadGraph(
        d["node_ids"], d["lat"], d["lon"], d["indptr"],
        d["neighbors"], d["edge_time"], d["edge_dist"],
    )
