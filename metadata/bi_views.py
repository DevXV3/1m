"""Add BI-friendly + AI-friendly VIEWS to onem_meta.duckdb so other agents, BI tools,
and text-to-SQL can query the 1MPRO metadata without knowing the join graph.

Run AFTER build_meta.py (and re-run any time). Idempotent (CREATE OR REPLACE VIEW).

Run:  python metadata/bi_views.py
"""
import os

import duckdb

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "onem_meta.duckdb")

VIEWS = {
    # one row per endpoint with its department + which screens use it
    "v_endpoint": """
        SELECT e.id, coalesce(m.dept,'shared') AS dept, e.method, e.path, e.purpose_th,
               e.prisma_tables, e.filters_th, e.roles
        FROM api_endpoint e LEFT JOIN api_module m USING(module)
    """,
    # screen -> api -> tables, flattened for "what does this screen touch"
    "v_screen": """
        SELECT s.id, s.dept, s.menu_th, s.route, s.purpose_th, s.ui_type, s.api_calls, s.roles
        FROM screen s
    """,
    # department cockpit: counts per department
    "v_dept_summary": """
        SELECT d.code AS dept, d.name_th, d.summary_th,
               (SELECT count(*) FROM api_endpoint e JOIN api_module m USING(module)
                  WHERE m.dept=d.code) AS n_endpoints,
               (SELECT count(*) FROM screen s WHERE s.dept=d.code) AS n_screens,
               (SELECT count(*) FROM doc_fact f WHERE f.dept=d.code) AS n_rules,
               (SELECT count(*) FROM ai_data_need a WHERE a.dept=d.code) AS n_ai_needs
        FROM dept d WHERE d.code <> 'shared'
    """,
    # product catalog flat (real SKU + price + type) — the sales/BI workhorse
    "v_product": """
        SELECT s.product_id, s.ptype_name, s.name_th, s.size, s.thickness, s.area,
               s.price, s.unit, t.price_min AS type_price_min, t.price_max AS type_price_max
        FROM product_sku s LEFT JOIN product_type t USING(ptype_name)
    """,
    # code translation: every opaque code -> Thai (status + doc + master refs)
    "v_code": """
        SELECT field AS domain, code, meaning_th AS name_th FROM status_dict
        UNION ALL
        SELECT ref_table AS domain, code, name_th FROM ref_value
    """,
    # tables ranked by size with the department(s) whose endpoints touch them
    "v_table_usage": """
        SELECT t.table_name, t.rows,
               (SELECT string_agg(DISTINCT coalesce(m.dept,'shared'), ',')
                  FROM api_endpoint e JOIN api_module m USING(module)
                  WHERE lower(t.table_name) = ANY(string_split(lower(e.prisma_tables),' ')))
                AS used_by_depts
        FROM db_table t ORDER BY t.rows DESC
    """,
    # everything an AI assistant for a dept should load (needs + rules + codes hint)
    "v_ai_brief": """
        SELECT a.dept, a.need_th, a.source_api, a.source_table, a.note_th
        FROM ai_data_need a
    """,
}


def main():
    con = duckdb.connect(DB)
    for name, sql in VIEWS.items():
        con.execute(f"CREATE OR REPLACE VIEW {name} AS {sql}")
        n = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        print(f"  [ok] {name:18} {n} rows")
    con.close()
    print(f"[ok] BI views added to {DB}")


if __name__ == "__main__":
    main()
