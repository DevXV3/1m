"""High-level routing wrapper: coordinates in, route + cost out."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .cost import CostBreakdown, estimate_cost
from .graph import RoadGraph, load_graph


@dataclass
class Route:
    found: bool
    distance_km: float
    duration_min: float
    geometry: list[list[float]] = field(default_factory=list)  # [[lat, lon], ...]
    origin_snap_m: float = 0.0
    dest_snap_m: float = 0.0
    message: str = ""

    def as_dict(self, include_geometry: bool = True) -> dict:
        d = {
            "found": self.found,
            "distance_km": round(self.distance_km, 2),
            "duration_min": round(self.duration_min, 1),
            "origin_snap_m": round(self.origin_snap_m, 1),
            "dest_snap_m": round(self.dest_snap_m, 1),
            "message": self.message,
        }
        if include_geometry:
            d["geometry"] = self.geometry
        return d


class Router:
    """Loads a cached RoadGraph and answers route/cost queries."""

    def __init__(self, graph: RoadGraph):
        self.g = graph

    @classmethod
    def from_cache(cls, cache_path: str | Path) -> "Router":
        return cls(load_graph(cache_path))

    def _snap_distance_m(self, idx: int, lat: float, lon: float) -> float:
        import math
        dlat = (self.g.lat[idx] - lat) * 111_320
        dlon = (self.g.lon[idx] - lon) * 111_320 * math.cos(math.radians(lat))
        return math.hypot(dlat, dlon)

    def route(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        optimize: str = "time",
    ) -> Route:
        """origin/destination are (lat, lon). optimize: 'time' or 'distance'."""
        o_lat, o_lon = origin
        d_lat, d_lon = destination
        src = self.g.nearest_node(o_lat, o_lon)
        dst = self.g.nearest_node(d_lat, d_lon)
        o_snap = self._snap_distance_m(src, o_lat, o_lon)
        d_snap = self._snap_distance_m(dst, d_lat, d_lon)

        cost, path = self.g.shortest_path(src, dst, weight=optimize)
        if not path or cost == float("inf"):
            return Route(False, 0.0, 0.0, message="ไม่พบเส้นทางที่เชื่อมถึงกัน",
                         origin_snap_m=o_snap, dest_snap_m=d_snap)

        # Sum true distance + time along the path (cost may be time or distance).
        dist_m, time_s = self._measure_path(path)
        geometry = [[float(self.g.lat[i]), float(self.g.lon[i])] for i in path]
        return Route(
            found=True,
            distance_km=dist_m / 1000.0,
            duration_min=time_s / 60.0,
            geometry=geometry,
            origin_snap_m=o_snap,
            dest_snap_m=d_snap,
        )

    def _measure_path(self, path: list[int]) -> tuple[float, float]:
        g = self.g
        dist_m = 0.0
        time_s = 0.0
        for a, b in zip(path, path[1:]):
            # find the edge a->b in CSR
            for e in range(g.indptr[a], g.indptr[a + 1]):
                if g.neighbors[e] == b:
                    dist_m += float(g.edge_dist[e])
                    time_s += float(g.edge_time[e])
                    break
        return dist_m, time_s

    def route_with_cost(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        vehicle_type: str = "6wheel",
        *,
        round_trip: bool = False,
        fuel_surcharge_pct: float = 0.0,
        optimize: str = "time",
    ) -> tuple[Route, CostBreakdown | None]:
        r = self.route(origin, destination, optimize=optimize)
        if not r.found:
            return r, None
        cost = estimate_cost(
            r.distance_km, vehicle_type,
            round_trip=round_trip, fuel_surcharge_pct=fuel_surcharge_pct,
        )
        return r, cost
