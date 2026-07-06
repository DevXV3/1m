"""Transport-cost model (THB).

Distance-based tariff with a per-vehicle rate, a base dispatch fee and a minimum
charge. Values are editable defaults for a Thai regional carrier (concrete /
building-material delivery); override per deployment via `load_tariffs()`.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Tariff:
    label: str            # ชื่อประเภทรถ
    rate_per_km: float    # THB per km
    base_fee: float       # THB fixed dispatch fee
    min_charge: float     # THB minimum per trip
    capacity_desc: str    # human note on capacity


# Default vehicle tariffs. Rates are illustrative; tune to real company pricing.
TARIFFS: dict[str, Tariff] = {
    "pickup":       Tariff("รถกระบะ", 12.0, 200.0, 400.0, "≤ 1 ตัน"),
    "6wheel":       Tariff("รถ 6 ล้อ", 22.0, 400.0, 900.0, "≤ 7 ตัน"),
    "10wheel":      Tariff("รถ 10 ล้อ", 32.0, 600.0, 1500.0, "≤ 15 ตัน"),
    "mixer":        Tariff("รถโม่ปูน", 40.0, 800.0, 2000.0, "คอนกรีตผสมเสร็จ ~5-6 คิว"),
    "trailer":      Tariff("รถเทรลเลอร์", 55.0, 1200.0, 3500.0, "≤ 30 ตัน"),
}


@dataclass
class CostBreakdown:
    vehicle_type: str
    vehicle_label: str
    distance_km: float
    round_trip: bool
    billable_km: float
    base_fee: float
    distance_cost: float
    fuel_surcharge: float
    subtotal: float
    min_charge: float
    total_thb: float
    currency: str = "THB"

    def as_dict(self) -> dict:
        return asdict(self)


def load_tariffs(path: str | Path) -> dict[str, Tariff]:
    """Load tariff overrides from JSON: {code: {label, rate_per_km, ...}}."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {code: Tariff(**vals) for code, vals in data.items()}


def estimate_cost(
    distance_km: float,
    vehicle_type: str = "6wheel",
    *,
    round_trip: bool = False,
    fuel_surcharge_pct: float = 0.0,
    tariffs: dict[str, Tariff] | None = None,
) -> CostBreakdown:
    """Compute a transport cost breakdown for a one-way distance in km.

    round_trip doubles the billable distance. fuel_surcharge_pct (e.g. 8 for 8%)
    is applied on the distance cost.
    """
    tariffs = tariffs or TARIFFS
    if vehicle_type not in tariffs:
        raise ValueError(
            f"unknown vehicle_type {vehicle_type!r}; "
            f"choose one of {sorted(tariffs)}"
        )
    t = tariffs[vehicle_type]
    billable_km = distance_km * (2 if round_trip else 1)
    distance_cost = billable_km * t.rate_per_km
    fuel = distance_cost * (fuel_surcharge_pct / 100.0)
    subtotal = t.base_fee + distance_cost + fuel
    total = max(subtotal, t.min_charge)
    return CostBreakdown(
        vehicle_type=vehicle_type,
        vehicle_label=t.label,
        distance_km=round(distance_km, 2),
        round_trip=round_trip,
        billable_km=round(billable_km, 2),
        base_fee=t.base_fee,
        distance_cost=round(distance_cost, 2),
        fuel_surcharge=round(fuel, 2),
        subtotal=round(subtotal, 2),
        min_charge=t.min_charge,
        total_thb=round(total, 2),
    )
