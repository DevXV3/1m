"""AI tool definitions for the routing + cost engine.

`TOOLS` follows the Anthropic tool-use schema (name / description / input_schema)
and works unchanged with the Claude API or any LLM that accepts JSON-schema tool
definitions. `dispatch()` executes a tool call and returns a plain dict, so the
same layer drives Claude, a local model (Qwythos via Ollama), or a plain script.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .cost import TARIFFS
from .geocode import Geocoder
from .router import Router

_VEHICLE_ENUM = sorted(TARIFFS.keys())

TOOLS: list[dict[str, Any]] = [
    {
        "name": "geocode_place",
        "description": (
            "ค้นหาพิกัด (lat/lon) ของสถานที่ในประเทศไทยจากชื่อ เช่น อำเภอ ตำบล "
            "หรือชื่อสถานที่/ร้าน. Use this to turn a place name into coordinates "
            "before planning a route."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Place name to search for"},
                "limit": {"type": "integer", "description": "Max results (default 5)"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "plan_transport",
        "description": (
            "หาเส้นทางขับรถระหว่างต้นทาง-ปลายทาง (offline) แล้วคำนวณระยะทาง เวลา "
            "และค่าขนส่งตามประเภทรถ. Origin and destination may each be either a "
            "place name (string) or explicit coordinates {lat, lon}. Returns "
            "distance, duration, a cost breakdown, and the route geometry."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {
                    "description": "Start point: a place-name string or {lat, lon}",
                    "oneOf": [
                        {"type": "string"},
                        {
                            "type": "object",
                            "properties": {
                                "lat": {"type": "number"},
                                "lon": {"type": "number"},
                            },
                            "required": ["lat", "lon"],
                        },
                    ],
                },
                "destination": {
                    "description": "End point: a place-name string or {lat, lon}",
                    "oneOf": [
                        {"type": "string"},
                        {
                            "type": "object",
                            "properties": {
                                "lat": {"type": "number"},
                                "lon": {"type": "number"},
                            },
                            "required": ["lat", "lon"],
                        },
                    ],
                },
                "vehicle_type": {
                    "type": "string",
                    "enum": _VEHICLE_ENUM,
                    "description": "Vehicle class for the cost estimate",
                },
                "round_trip": {
                    "type": "boolean",
                    "description": "Charge for the return trip too (default false)",
                },
                "fuel_surcharge_pct": {
                    "type": "number",
                    "description": "Optional fuel surcharge percent on the distance cost",
                },
                "optimize": {
                    "type": "string",
                    "enum": ["time", "distance"],
                    "description": "Optimize the route for travel time or distance",
                },
            },
            "required": ["origin", "destination"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_vehicle_types",
        "description": "แสดงประเภทรถและอัตราค่าขนส่งที่มีให้เลือกทั้งหมด.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
]


class ToolRunner:
    """Holds the loaded router + geocoder and executes tool calls."""

    def __init__(self, router: Router, geocoder: Geocoder | None = None):
        self.router = router
        self.geocoder = geocoder

    @classmethod
    def from_cache(cls, cache_dir: str | Path) -> "ToolRunner":
        cache_dir = Path(cache_dir)
        router = Router.from_cache(cache_dir / "thailand_graph.npz")
        geo_path = cache_dir / "places.json"
        geocoder = Geocoder.from_index(geo_path) if geo_path.exists() else None
        return cls(router, geocoder)

    def _resolve(self, point: Any) -> tuple[float, float]:
        """Turn a place-name string or {lat, lon} into a (lat, lon) tuple."""
        if isinstance(point, dict):
            return float(point["lat"]), float(point["lon"])
        if isinstance(point, str):
            if self.geocoder is None:
                raise ValueError("geocoder not available; pass coordinates instead")
            hits = self.geocoder.search(point, limit=1)
            if not hits:
                raise ValueError(f"ไม่พบสถานที่: {point!r}")
            return hits[0]["lat"], hits[0]["lon"]
        raise ValueError(f"invalid point: {point!r}")

    def dispatch(self, name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        if name == "geocode_place":
            if self.geocoder is None:
                return {"error": "geocoder index not built"}
            return {"results": self.geocoder.search(
                tool_input["query"], limit=tool_input.get("limit", 5))}

        if name == "list_vehicle_types":
            return {"vehicles": [
                {"code": code, "label": t.label, "rate_per_km": t.rate_per_km,
                 "base_fee": t.base_fee, "min_charge": t.min_charge,
                 "capacity": t.capacity_desc}
                for code, t in TARIFFS.items()
            ]}

        if name == "plan_transport":
            origin = self._resolve(tool_input["origin"])
            dest = self._resolve(tool_input["destination"])
            route, cost = self.router.route_with_cost(
                origin, dest,
                vehicle_type=tool_input.get("vehicle_type", "6wheel"),
                round_trip=tool_input.get("round_trip", False),
                fuel_surcharge_pct=tool_input.get("fuel_surcharge_pct", 0.0),
                optimize=tool_input.get("optimize", "time"),
            )
            out: dict[str, Any] = {"route": route.as_dict(include_geometry=False)}
            if cost is not None:
                out["cost"] = cost.as_dict()
            # geometry can be large; expose a compact polyline separately
            out["geometry"] = route.geometry
            return out

        return {"error": f"unknown tool: {name}"}
