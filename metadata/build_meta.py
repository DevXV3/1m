"""Build onem_meta.duckdb — the 1MPRO system-metadata warehouse.

Merges every extract under metadata/extract/ into one DuckDB, organized so an AI
assistant (or a human writing OWUI KB docs) can answer "what does department X do,
through what screens/APIs/tables, following what workflow, using what data":

  dept                 department reference (code, name, roles, summary)
  doc_fact             business rules / data facts from the spec docs (confidence-tagged)
  workflow / _step     document-lifecycle workflows per dept
  api_module / api_endpoint   the Fastify API surface (endpoint -> tables, filters, roles)
  menu / screen        the Nuxt web surface (menu tree + screens -> api calls)
  db_table / db_column / db_fk   the MariaDB schema (121 tables, counts, FKs)
  api_observation      screen -> live API call evidence (played the real web)
  api_sample           per-endpoint response shape / meta / sum (pulled live, read-only)
  enum_value           field -> distinct enum vocabulary (status/type/... only, no PII)
  ai_data_need         curated: per dept, the data an AI assistant needs + where it lives

Idempotent (drops+recreates). Read-only inputs. No customer PII (schema/enums only).

Run:  python metadata/build_meta.py
Out:  metadata/onem_meta.duckdb
"""
import json
import os

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "extract")
DB = os.path.join(HERE, "onem_meta.duckdb")


def load(name, default=None):
    path = os.path.join(EX, name)
    if not os.path.exists(path):
        print(f"  [warn] missing {name} — skipping its tables")
        return default if default is not None else {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---- department reference (the organizing spine) ----
DEPTS = [
    ("general", "ภาพรวม/ทั่วไป", "dashboard KPI ยอดขาย/ผลิต ภาพรวมบริษัท"),
    ("sales", "ขายสินค้า", "ลูกค้า ใบเสนอราคา ออเดอร์ขาย คืน/เคลม/เปลี่ยน (RCX)"),
    ("purchasing", "จัดซื้อสินค้า", "ใบสั่งซื้อ รับสินค้า ผู้ขาย (admin/dev)"),
    ("accounting", "บัญชี", "มัดจำ/รับเงิน ลด/เพิ่มหนี้ ค่าใช้จ่าย ผ่อน เครดิต IV/RE/BI"),
    ("production", "ผลิตสินค้า", "แผนผลิตรายวันต่อโรง ผลิต แปลงสินค้า QC เข้าสต๊อก"),
    ("stock", "สต๊อกสินค้า", "รับเข้า รายการ ชั่วคราว ของเสีย ย้าย ประวัติ เบิก/บาร์โค้ด"),
    ("delivery", "ส่งสินค้า", "ใบส่งของ(DR) แผนส่ง ส่งสำเร็จ รายงานการส่ง"),
    ("reports", "รายงาน/ผู้บริหาร", "รายงานขาย/ผลิต/สต๊อก + รายงานผู้บริหาร YoY/MoM ค่าคอม"),
    ("admin", "การจัดการ/Admin", "สินค้า/ประเภท/หน่วย โรง/คลัง ผู้ใช้ พนักงาน LOG ค่าจ้าง"),
    ("shared", "ใช้ร่วม", "endpoint/ตารางที่หลายแผนกใช้ร่วมกัน"),
]

ROLES = ["admin", "dev", "sale", "headofsales", "accounting", "manager", "special",
         "saleandproduction", "production", "stock", "mixconcrete", "shippingplan"]

# ---- curated status-code dictionary (API returns opaque numbers; doc gives meanings) ----
# derived from doc_facts + observed enum vocab; lets the AI translate codes to Thai.
STATUS_DICT = [
    ("order_status", "1", "รอยืนยัน/ร่าง"),
    ("order_status", "2", "ยืนยันแล้ว/รอดำเนินการ"),
    ("order_status", "3", "กำลังดำเนินการ"),
    ("order_status", "4", "รอส่ง/พร้อมส่ง"),
    ("order_status", "5", "สำเร็จ"),
    ("order_status", "6", "ยกเลิก"),
    ("status_payment", "1", "รอชำระ"),
    ("status_payment", "2", "ชำระมัดจำ"),
    ("status_payment", "3", "ชำระบางส่วน"),
    ("status_payment", "4", "ชำระเรียบร้อย"),
    ("status_payment", "5", "ชำระครบ/ปิดยอด"),
    ("status_payment", "6", "ยกเลิก"),
    ("status_send", "1", "รอส่ง"),
    ("status_send", "2", "กำลังส่ง/ส่งบางส่วน"),
    ("status_send", "5", "ส่งสำเร็จ"),
    ("cus_type", "GENERAL", "ลูกค้าทั่วไป"),
    ("cus_type", "SHOP", "ร้านค้าวัสดุ"),
    ("cus_type", "COMPANY", "บริษัทรับเหมา"),
    ("cus_type", "CONTRACTOR", "ผู้รับเหมา"),
    ("order_payment_type", "CASH", "เงินสด"),
    ("order_payment_type", "CREDIT", "เครดิต"),
    ("doc_code", "AI", "ใบมัดจำ/รับเงินล่วงหน้า (มัดจำขั้นต่ำ 30%)"),
    ("doc_code", "HS", "ใบเสร็จรับเงิน (ลูกค้าเงินสด)"),
    ("doc_code", "IV", "ใบแจ้งหนี้ (ลูกค้าเครดิต)"),
    ("doc_code", "BI", "ใบวางบิล"),
    ("doc_code", "RE", "ใบเสร็จรับเงินของใบวางบิล (เคลียร์เครดิต)"),
    ("doc_code", "RT", "ใบคืนสินค้า (Return)"),
    ("doc_code", "SR", "ใบลด/เพิ่มหนี้ (ออกอัตโนมัติตอนอนุมัติคืน)"),
    ("doc_code", "CL", "ใบเคลม (Claim)"),
    ("doc_code", "CO", "ใบเปลี่ยนสินค้า (Exchange order)"),
    ("doc_code", "EX", "เอกสารการเปลี่ยนสินค้า"),
    ("doc_code", "EO", "ออเดอร์เปลี่ยนสินค้า"),
    ("doc_code", "DR", "ใบส่งของ = เอกสารตัดสต๊อกด้วย / ใบเพิ่มหนี้ตอนเปลี่ยนสินค้า"),
    ("doc_code", "SO", "ออเดอร์ขาย (เลข OR- อัตโนมัติ)"),
    ("doc_code", "QT", "ใบเสนอราคา (ค้าง >31 วัน auto-cancel)"),
]

# ---- curated AI data-needs per dept (what an assistant must know + where it lives) ----
AI_NEEDS = [
    ("sales", "ราคาสินค้าปัจจุบันต่อหน่วย/ต่อประเภทลูกค้า", "/api/product, /api/producttype", "product, producttype", "ทำใบเสนอราคา — ต้องได้ราคาสด ไม่ใช้ราคาในเอกสารเก่า"),
    ("sales", "สถานะออเดอร์ (order/payment/send) ของลูกค้า", "/api/orders", "sale_order", "รหัสสถานะ 3 ชุด — ต้องแปลรหัสเป็นภาษาคน"),
    ("sales", "ประเภทลูกค้า 4 แบบ + เงื่อนไขราคา/เครดิต", "/api/customer", "customer", "GENERAL/SHOP/COMPANY/CONTRACTOR เงื่อนไขต่างกัน"),
    ("sales", "กติกาคืน/เคลม/เปลี่ยน (RCX) คืน 80/100% + ค่าปรับ 20%", "/api/rcx/*", "rcx_*", "ต้องตอบลูกค้าเรื่องเคลมได้"),
    ("accounting", "ยอดค้างชำระ/เครดิต/มัดจำ", "/api/payment, /api/orders(sum)", "payment, sale_order", "มัดจำขั้นต่ำ 30%; เครดิตต้องมีวงเงิน"),
    ("accounting", "รหัสเอกสารการเงิน 12 ตัว (AI/HS/IV/BI/RE/SR/...)", "doc_fact", "-", "แต่ละรหัสหมายถึงเอกสารอะไร ออกเมื่อไหร่"),
    ("production", "แผนผลิตรายวันต่อโรง + เลขแพ", "/api/production", "production_*", "แพเริ่มนับ 1 ใหม่ทุกโรง; 3 โรง+โคราช"),
    ("stock", "ของพร้อมขาย vs จอง vs ของเสีย ต่อสินค้า/โรง", "/api/stocklist", "stock_*", "available/reserve/defective แยกกัน"),
    ("delivery", "แผนส่ง/สถานะส่ง + ค่าขนส่งตามระยะทาง", "/api/shipping, /api/moving/*", "shipping_*", "DR = ตัดสต๊อกด้วย"),
    ("reports", "นิยาม 'ยอดขาย' = เงินรับจริง ไม่ใช่ order_total", "/api/report/summary-sale", "-", "กับดักสำคัญ — payment_total ไม่ใช่ order_total"),
    ("reports", "โครง sum ของรายงาน (payment_ai/hs/iv/re/dr/sr...)", "/api/report/summary-*", "-", "แต่ละ field คือเงินจากเอกสารชนิดใด"),
    ("general", "โครงองค์กร: 3 โรง+โคราช, สาขาเห็นเฉพาะตัวเอง", "doc_fact", "factory", "multi-branch data isolation"),
]


def main():
    doc = load("doc_facts.json", {})
    api = load("api_endpoints.json", {})
    web = load("web_screens.json", {})
    db = load("db_schema.json", {})
    obs = load("web_observations.json", {})
    smp = load("api_samples.json", {})
    ref = load("ref_data.json", {})
    cat = load("products_catalog.json", {})

    con = duckdb.connect(DB)
    con.execute("BEGIN")
    for t in ("dept", "role", "doc_fact", "workflow", "workflow_step", "api_module",
              "api_endpoint", "menu", "screen", "db_table", "db_column", "db_fk",
              "api_observation", "api_sample", "enum_value", "ai_data_need", "meta_source",
              "ref_table", "ref_value", "status_dict", "product_sku", "product_type"):
        con.execute(f"DROP TABLE IF EXISTS {t}")

    con.execute("CREATE TABLE dept(code TEXT, name_th TEXT, summary_th TEXT)")
    con.executemany("INSERT INTO dept VALUES (?,?,?)", DEPTS)
    con.execute("CREATE TABLE role(name TEXT)")
    con.executemany("INSERT INTO role VALUES (?)", [(r,) for r in ROLES])

    # doc facts + workflows
    con.execute("CREATE TABLE doc_fact(id TEXT, topic TEXT, dept TEXT, fact_th TEXT, "
                "detail_th TEXT, source TEXT, confidence TEXT)")
    con.executemany("INSERT INTO doc_fact VALUES (?,?,?,?,?,?,?)",
                    [(f.get("id"), f.get("topic"), f.get("dept"), f.get("fact_th"),
                      f.get("detail_th"), f.get("source"), f.get("confidence"))
                     for f in doc.get("facts", [])])
    con.execute("CREATE TABLE workflow(id INTEGER, name_th TEXT, dept TEXT, "
                "documents TEXT, rules_th TEXT)")
    con.execute("CREATE TABLE workflow_step(workflow_id INTEGER, seq INTEGER, step_th TEXT)")
    for i, w in enumerate(doc.get("workflows", []), 1):
        con.execute("INSERT INTO workflow VALUES (?,?,?,?,?)",
                    [i, w.get("name_th"), w.get("dept"),
                     " | ".join(w.get("documents") or []),
                     " | ".join(w.get("rules_th") or [])])
        for j, s in enumerate(w.get("steps") or [], 1):
            con.execute("INSERT INTO workflow_step VALUES (?,?,?)", [i, j, s])

    # api surface
    con.execute("CREATE TABLE api_module(module TEXT, file TEXT, purpose_th TEXT, dept TEXT)")
    con.executemany("INSERT INTO api_module VALUES (?,?,?,?)",
                    [(m.get("module"), m.get("file"), m.get("purpose_th"), m.get("dept"))
                     for m in api.get("modules", [])])
    con.execute("CREATE TABLE api_endpoint(id TEXT, module TEXT, method TEXT, path TEXT, "
                "purpose_th TEXT, auth TEXT, roles TEXT, query_params TEXT, body_fields TEXT, "
                "prisma_tables TEXT, response_keys TEXT, filters_th TEXT)")
    con.executemany("INSERT INTO api_endpoint VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(e.get("id"), e.get("module"), e.get("method"), e.get("path"),
                      e.get("purpose_th"), e.get("auth"),
                      " ".join(e.get("roles") or []), " ".join(e.get("query_params") or []),
                      " ".join(e.get("body_fields") or []),
                      " ".join(e.get("prisma_tables") or []),
                      " ".join(e.get("response_keys") or []),
                      e.get("filters_supported_th"))
                     for e in api.get("endpoints", [])])

    # web surface: flatten menu tree + screens
    con.execute("CREATE TABLE menu(menu_th TEXT, parent_th TEXT, route TEXT, dept TEXT, "
                "roles TEXT, menu_order INTEGER)")
    for m in web.get("menu_tree", []):
        con.execute("INSERT INTO menu VALUES (?,?,?,?,?,?)",
                    [m.get("menu_th"), None, None, m.get("dept"),
                     " ".join(m.get("roles") or []), m.get("order")])
        for c in m.get("children") or []:
            con.execute("INSERT INTO menu VALUES (?,?,?,?,?,?)",
                        [c.get("title_th"), m.get("menu_th"), c.get("route"), m.get("dept"),
                         " ".join(c.get("roles") or []), m.get("order")])
    con.execute("CREATE TABLE screen(id TEXT, route TEXT, file TEXT, menu_th TEXT, "
                "dept TEXT, purpose_th TEXT, api_calls TEXT, ui_type TEXT, roles TEXT)")
    con.executemany("INSERT INTO screen VALUES (?,?,?,?,?,?,?,?,?)",
                    [(s.get("id"), s.get("route"), s.get("file"), s.get("menu_th"),
                      s.get("dept"), s.get("purpose_th"), " ".join(s.get("api_calls") or []),
                      s.get("ui_type"), " ".join(s.get("roles") or []))
                     for s in web.get("screens", [])])

    # db schema
    con.execute("CREATE TABLE db_table(table_name TEXT, rows BIGINT, comment TEXT)")
    con.executemany("INSERT INTO db_table VALUES (?,?,?)",
                    [(t["table"], t.get("rows", 0), t.get("comment"))
                     for t in db.get("tables", [])])
    con.execute("CREATE TABLE db_column(table_name TEXT, column_name TEXT, type TEXT, "
                "nullable BOOLEAN, key TEXT, dflt TEXT, extra TEXT, comment TEXT)")
    con.executemany("INSERT INTO db_column VALUES (?,?,?,?,?,?,?,?)",
                    [(c["table"], c["column"], c["type"], c["nullable"], c["key"],
                      c.get("default"), c.get("extra"), c.get("comment"))
                     for c in db.get("columns", [])])
    con.execute("CREATE TABLE db_fk(table_name TEXT, column_name TEXT, ref_table TEXT, "
                "ref_column TEXT, constraint_name TEXT)")
    con.executemany("INSERT INTO db_fk VALUES (?,?,?,?,?)",
                    [(f["table"], f["column"], f["ref_table"], f["ref_column"],
                      f.get("constraint")) for f in db.get("fks", [])])

    # observations (played web)
    con.execute("CREATE TABLE api_observation(step INTEGER, screen_label TEXT, method TEXT, "
                "api_path TEXT, filters TEXT, status INTEGER)")
    con.executemany("INSERT INTO api_observation VALUES (?,?,?,?,?,?)",
                    [(o.get("step"), o.get("screen_label"), o.get("method"), o.get("api_path"),
                      " ".join(sorted(set(list(o.get("query_params", {})) +
                                          list(o.get("post_data_keys") or [])))),
                      o.get("status")) for o in obs.get("observations", [])])

    # api samples (pulled live)
    con.execute("CREATE TABLE api_sample(method TEXT, path TEXT, ok BOOLEAN, rows_returned "
                "INTEGER, sum_keys TEXT, response_shape TEXT, error TEXT)")
    con.executemany("INSERT INTO api_sample VALUES (?,?,?,?,?,?,?)",
                    [(s.get("method"), s.get("path"), s.get("ok"), s.get("rows_returned"),
                      " ".join(s.get("sum_keys") or []),
                      json.dumps(s.get("response_shape"), ensure_ascii=False)[:4000]
                      if s.get("response_shape") else None, s.get("error"))
                     for s in smp.get("samples", [])])
    con.execute("CREATE TABLE enum_value(field TEXT, value TEXT)")
    con.executemany("INSERT INTO enum_value VALUES (?,?)",
                    [(k, v) for k, vs in smp.get("enum_vocab", {}).items() for v in vs])

    # reference/master data (controlled vocabulary) + flattened code->name values
    con.execute("CREATE TABLE ref_table(table_name TEXT, row_count INTEGER, columns TEXT)")
    con.execute("CREATE TABLE ref_value(ref_table TEXT, code TEXT, name_th TEXT, extra TEXT)")
    NAMECOL = {"Factory": ("fac_id", "fac_name"), "ProductType": ("ptype_id", "ptype_name"),
               "ProductMainType": ("pmtype_id", "pmtype_name"), "Units": ("unit_name", "unit_name"),
               "UserType": ("user_type", "user_type_th"), "Store": ("id", "store_name"),
               "Building": ("id", "building_name"), "CommissionCostType": ("id", "commission_type_name"),
               "CommissionUnitType": ("id", "commission_unit_type_name")}
    for tname, tdata in (ref.get("tables") or {}).items():
        con.execute("INSERT INTO ref_table VALUES (?,?,?)",
                    [tname, tdata.get("row_count", 0), " ".join(tdata.get("columns", []))])
        ck, nk = NAMECOL.get(tname, (None, None))
        if ck:
            for row in tdata.get("rows", []):
                if str(row.get("isUse", "1")) in ("0", "False", "false"):
                    continue
                # Factory: prefer the distinguishing branch_name as the display name
                name = row.get(nk, "")
                if tname == "Factory" and row.get("branch_name"):
                    name = row["branch_name"]
                extra = row.get("fac_id") or row.get("commission_price") or ""
                con.execute("INSERT INTO ref_value VALUES (?,?,?,?)",
                            [tname, str(row.get(ck, "")), str(name), str(extra)])

    # product catalog: types + SKU (real names/specs/PUBLIC price)
    con.execute("CREATE TABLE product_type(ptype_name TEXT, sku_count INTEGER, unit TEXT, "
                "price_min DOUBLE, price_max DOUBLE)")
    con.execute("CREATE TABLE product_sku(product_id TEXT, ptype_name TEXT, name_th TEXT, "
                "size TEXT, thickness TEXT, area TEXT, price DOUBLE, unit TEXT)")
    for tp, td in (cat.get("by_type") or {}).items():
        con.execute("INSERT INTO product_type VALUES (?,?,?,?,?)",
                    [tp, td.get("sku_count"), td.get("unit"),
                     td.get("price_min"), td.get("price_max")])
        for s in td.get("skus", []):
            try:
                price = float(s.get("price")) if s.get("price") not in (None, "") else None
            except (TypeError, ValueError):
                price = None
            con.execute("INSERT INTO product_sku VALUES (?,?,?,?,?,?,?,?)",
                        [s.get("product_id"), tp, s.get("name"), str(s.get("size") or ""),
                         str(s.get("thickness") or ""), str(s.get("area") or ""), price,
                         s.get("unit")])

    # status/document code dictionary (opaque API numbers -> Thai meaning)
    con.execute("CREATE TABLE status_dict(field TEXT, code TEXT, meaning_th TEXT)")
    con.executemany("INSERT INTO status_dict VALUES (?,?,?)", STATUS_DICT)

    # curated AI needs
    con.execute("CREATE TABLE ai_data_need(dept TEXT, need_th TEXT, source_api TEXT, "
                "source_table TEXT, note_th TEXT)")
    con.executemany("INSERT INTO ai_data_need VALUES (?,?,?,?,?)", AI_NEEDS)

    # provenance
    con.execute("CREATE TABLE meta_source(kind TEXT, detail TEXT)")
    con.executemany("INSERT INTO meta_source VALUES (?,?)", [
        ("docs", f"{len(doc.get('facts', []))} facts from spec PDFs + web.txt"),
        ("api_code", f"{len(api.get('endpoints', []))} endpoints / "
                     f"{len(api.get('modules', []))} modules (Fastify)"),
        ("web_code", f"{len(web.get('screens', []))} screens / "
                     f"{len(web.get('menu_tree', []))} top menus (Nuxt)"),
        ("db", f"{db.get('n_tables', 0)} tables / {db.get('total_rows', 0)} rows (MariaDB test_api)"),
        ("web_play", f"{len(obs.get('observations', []))} live API observations"),
        ("api_pull", f"{len(smp.get('samples', []))} endpoints sampled, "
                     f"{len(smp.get('enum_vocab', {}))} enum fields"),
    ])

    con.execute("COMMIT")

    # summary
    print("\n== onem_meta.duckdb built ==")
    for t in ("dept", "doc_fact", "workflow", "api_module", "api_endpoint", "menu",
              "screen", "db_table", "db_column", "db_fk", "api_observation",
              "api_sample", "enum_value", "ai_data_need", "ref_table", "ref_value",
              "product_type", "product_sku", "status_dict"):
        n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"  {t:18} {n}")
    con.close()
    print(f"\n[ok] {DB}")


if __name__ == "__main__":
    main()
