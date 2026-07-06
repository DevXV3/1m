"""Command-line interface for the routing + cost engine.

Examples:
    python cli.py geocode "อุบลราชธานี"
    python cli.py route 15.2287 104.8564 14.9799 102.0977 --vehicle 10wheel
    python cli.py plan "เมืองอุบลราชธานี" "เมืองนครราชสีมา" --vehicle mixer --round-trip
    python cli.py vehicles
"""
import argparse
import json
from pathlib import Path

from apptransport_routing.tools import ToolRunner

CACHE = Path(__file__).resolve().parent / "cache"


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description="One M offline transport routing")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("geocode", help="ค้นพิกัดจากชื่อสถานที่")
    g.add_argument("query")
    g.add_argument("--limit", type=int, default=5)

    r = sub.add_parser("route", help="เส้นทางจากพิกัด")
    r.add_argument("olat", type=float)
    r.add_argument("olon", type=float)
    r.add_argument("dlat", type=float)
    r.add_argument("dlon", type=float)
    r.add_argument("--vehicle", default="6wheel")
    r.add_argument("--round-trip", action="store_true")
    r.add_argument("--optimize", choices=["time", "distance"], default="time")

    p = sub.add_parser("plan", help="เส้นทาง+ค่าขนส่งจากชื่อสถานที่")
    p.add_argument("origin")
    p.add_argument("destination")
    p.add_argument("--vehicle", default="6wheel")
    p.add_argument("--round-trip", action="store_true")
    p.add_argument("--fuel", type=float, default=0.0)
    p.add_argument("--optimize", choices=["time", "distance"], default="time")

    sub.add_parser("vehicles", help="รายการประเภทรถ+อัตรา")

    args = ap.parse_args()
    runner = ToolRunner.from_cache(CACHE)

    if args.cmd == "geocode":
        _print(runner.dispatch("geocode_place",
                               {"query": args.query, "limit": args.limit}))
    elif args.cmd == "route":
        _print(runner.dispatch("plan_transport", {
            "origin": {"lat": args.olat, "lon": args.olon},
            "destination": {"lat": args.dlat, "lon": args.dlon},
            "vehicle_type": args.vehicle,
            "round_trip": args.round_trip,
            "optimize": args.optimize,
        }))
    elif args.cmd == "plan":
        _print(runner.dispatch("plan_transport", {
            "origin": args.origin,
            "destination": args.destination,
            "vehicle_type": args.vehicle,
            "round_trip": args.round_trip,
            "fuel_surcharge_pct": args.fuel,
            "optimize": args.optimize,
        }))
    elif args.cmd == "vehicles":
        _print(runner.dispatch("list_vehicle_types", {}))


if __name__ == "__main__":
    main()
