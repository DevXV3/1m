"""Extract the 1MPRO MariaDB schema (test_api) into db_schema.json — READ-ONLY.

Pulls information_schema metadata + row counts + FK graph via `docker exec
ai1m-mariadb mysql` (root creds live in the container env; nothing is stored
here). No table data is exported — schema, counts and comments only.

Run:  python metadata/extract/extract_db.py
Out:  metadata/extract/db_schema.json
"""
import json
import os
import subprocess

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_schema.json")
SCHEMA = "test_api"


def q(sql: str) -> list[list[str]]:
    """Run SQL in the mariadb container, return rows of columns (tab-separated)."""
    cmd = ["docker", "exec", "ai1m-mariadb", "sh", "-c",
           f'mysql -uroot -p"$MARIADB_ROOT_PASSWORD" -N -B -e "{sql}"']
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                         errors="replace", check=True).stdout
    return [line.split("\t") for line in out.splitlines() if line]


def main():
    tables = [{"table": r[0], "rows_estimate": int(r[1] or 0), "comment": r[2]}
              for r in q(
        f"SELECT table_name, table_rows, table_comment FROM information_schema.tables "
        f"WHERE table_schema='{SCHEMA}' AND table_type='BASE TABLE' ORDER BY table_name")]

    # exact row counts (estimates lie on InnoDB) — cheap enough at this scale.
    # NOTE: no backticks — the SQL rides inside sh double quotes (backtick = subshell)
    for t in tables:
        t["rows"] = int(q(f"SELECT COUNT(*) FROM {SCHEMA}.{t['table']}")[0][0])

    # NOTE: this DB has NO @@map in prisma/schema.prisma — table names == PascalCase
    # Prisma model names (e.g. Orders, StockList). api_endpoints.json prisma_tables use
    # those exact names, so metadata joins on table_name work without case-mapping.
    columns = [{"table": r[0], "column": r[1], "type": r[2], "nullable": r[3] == "YES",
                "key": r[4], "default": None if r[5] == "NULL" else r[5], "extra": r[6],
                "comment": r[7]}
               for r in q(
        f"SELECT table_name, column_name, column_type, is_nullable, column_key, "
        f"COALESCE(column_default,'NULL'), extra, column_comment "
        f"FROM information_schema.columns WHERE table_schema='{SCHEMA}' "
        f"ORDER BY table_name, ordinal_position")]

    fks = [{"table": r[0], "column": r[1], "ref_table": r[2], "ref_column": r[3],
            "constraint": r[4]}
           for r in q(
        f"SELECT table_name, column_name, referenced_table_name, referenced_column_name, "
        f"constraint_name FROM information_schema.key_column_usage "
        f"WHERE table_schema='{SCHEMA}' AND referenced_table_name IS NOT NULL "
        f"ORDER BY table_name")]

    data = {"schema": SCHEMA,
            "n_tables": len(tables), "n_columns": len(columns), "n_fks": len(fks),
            "total_rows": sum(t["rows"] for t in tables),
            "tables": tables, "columns": columns, "fks": fks}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"[ok] {OUT}: {len(tables)} tables, {len(columns)} columns, "
          f"{len(fks)} FKs, {data['total_rows']:,} rows")


if __name__ == "__main__":
    main()
