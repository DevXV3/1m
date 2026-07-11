"""Pull the 1MPRO reference/master tables (the system's controlled vocabulary) from
MariaDB into ref_data.json — READ-ONLY, whitelist-only, no customer PII.

Only pure master/taxonomy tables are pulled (product taxonomy, units, factories/
branches, plants/warehouses, roles, commission config). Transactional tables that
reference customers/orders are NEVER touched. Selected columns only (ids + names +
flags); free-text/address columns kept only for the COMPANY's own branches.

This gives the AI real code->name translation (ProductType 5 = 'แผ่นพื้น', Factory
'SD' = 'สาขาสีดา', etc.) instead of opaque numbers.

Run:  python metadata/extract/extract_refdata.py
Out:  metadata/extract/ref_data.json
"""
import json
import os
import subprocess

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref_data.json")
SCHEMA = "test_api"

# table -> columns to pull (None = a sensible default set). Master/taxonomy only.
WHITELIST = {
    "Factory": ["id", "fac_id", "fac_name", "branch_name", "address", "tel", "isUse"],
    "Building": ["id", "building_id", "building_name", "fac_id", "isUse"],
    "Store": ["id", "store_id", "store_name", "fac_id", "isUse"],
    "ProductMainType": ["id", "pmtype_id", "pmtype_name", "isUse", "priority_index"],
    "ProductType": ["id", "ptype_id", "ptype_name", "pm_type", "isUse", "priority_index"],
    "Units": ["id", "unit_name", "isUse"],
    "UserType": ["id", "user_type", "user_type_th", "isUse"],
    "CommissionCostType": None,
    "CommissionUnitType": None,
    # the real product catalog: name + specs + PUBLIC unit_price (not cost_price)
    "Product": ["id", "product_id", "p_name", "ptype_name", "p_size", "p_thickness",
                "p_area", "unit_price", "unit_name", "isUse"],
}


def cols_of(table):
    rows = q(f"SELECT column_name FROM information_schema.columns "
             f"WHERE table_schema='{SCHEMA}' AND table_name='{table}' ORDER BY ordinal_position")
    return [r[0] for r in rows]


def q(sql):
    cmd = ["docker", "exec", "ai1m-mariadb", "sh", "-c",
           f'mysql -uroot -p"$MARIADB_ROOT_PASSWORD" -N -B -e "{sql}"']
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                         errors="replace", check=True).stdout
    return [line.split("\t") for line in out.splitlines() if line]


def main():
    data = {"schema": SCHEMA, "note": "master/reference tables only — no customer PII",
            "tables": {}}
    for table, want in WHITELIST.items():
        have = cols_of(table)
        if not have:
            print(f"  [skip] {table} not found")
            continue
        cols = [c for c in (want or have) if c in have]
        # Product can be large-ish (880) — cap it, keep active + priced first
        limit = "" if table != "Product" else " ORDER BY isUse DESC, id LIMIT 400"
        rows = q(f"SELECT {','.join(cols)} FROM {SCHEMA}.{table}{limit}")
        data["tables"][table] = {
            "columns": cols,
            "row_count": len(rows),
            "rows": [dict(zip(cols, r)) for r in rows],
        }
        print(f"  [ok] {table}: {len(rows)} rows, cols={cols}")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    tot = sum(t["row_count"] for t in data["tables"].values())
    print(f"[ok] {OUT}: {len(data['tables'])} ref tables, {tot} rows")


if __name__ == "__main__":
    main()
