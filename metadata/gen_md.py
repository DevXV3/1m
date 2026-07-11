"""Generate per-department 1MPRO "system knowledge" markdown from onem_meta.duckdb,
for the PingZy WebUI department AI assistants.

One file per department (that has an OWUI assistant): what the department does, its
workflow, the screens/menus staff use, the API endpoints + DB tables behind them,
the business rules, the enum-code translations, and the curated AI data-needs.
Written in Thai, sentence-per-fact (small-model-friendly), grounded ENTIRELY in the
warehouse — no invented facts, no customer PII (schema/enums/rules only).

Run:  python metadata/gen_md.py
Out:  open-webui/company-kb/onem-sys-<dept>.md  (sales/accounting/production/stock/
      delivery/marketing/exec) + onem-sys-overview.md
"""
import datetime
import os

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "onem_meta.duckdb")
OUT = r"C:\Users\AiMiniX\open-webui\company-kb"
TODAY = datetime.date.today().strftime("%Y-%m-%d")
con = duckdb.connect(DB, read_only=True)

# OWUI assistant dept -> which metadata dept(s) feed it
DEPT_MAP = {
    "sales":      ["sales", "general"],
    "accounting": ["accounting"],
    "production": ["production"],
    "delivery":   ["delivery", "stock"],
    "marketing":  ["reports", "general"],
    "exec":       ["reports", "general", "admin"],
}
DEPT_TH = {"sales": "ฝ่ายขาย", "accounting": "ฝ่ายบัญชี", "production": "ฝ่ายผลิต",
           "delivery": "ฝ่ายจัดส่งและบริการ", "marketing": "ฝ่ายการตลาด",
           "exec": "ผู้บริหาร"}

# status-code translations harvested from enums + doc (codes are opaque in the API)
CODE_NOTES = (
    "## การแปลรหัสสถานะ (API คืนเป็นตัวเลข ต้องแปลก่อนสื่อสารกับคน)\n"
    "- ระบบใช้รหัสสถานะ 3 ชุดแยกกัน: สถานะออเดอร์ · สถานะการชำระเงิน · สถานะการส่ง "
    "(แต่ละชุดเป็นเลข 1–6)\n"
    "- ประเภทลูกค้า (cus_type): GENERAL=ทั่วไป · SHOP=ร้านค้าวัสดุ · COMPANY=บริษัทรับเหมา · "
    "CONTRACTOR=ผู้รับเหมา\n"
    "- อย่าคาดเดาความหมายรหัสเอง ถ้าไม่แน่ใจให้ยึดข้อมูลในระบบ/ถามหัวหน้างาน\n"
)
HEADER = (lambda th: f"# ระบบงาน 1MPRO — {th} (สำหรับผู้ช่วย AI)\n\n"
          f"> อ้างอิงจากระบบ ERP 1MPRO จริงของบริษัทวันเอ็ม (แกะจากเอกสาร+โค้ด+ฐานข้อมูล+API)\n"
          f"> ข้อมูล ณ {TODAY} — ยึดข้อมูลนี้ประกอบการตอบ ไม่แต่งข้อมูลระบบเอง\n")


def rows(sql, args=None):
    return con.execute(sql, args or []).fetchall()


def section_workflow(depts):
    out = []
    for name, docs, rules in rows(
            "SELECT name_th, documents, rules_th FROM workflow "
            f"WHERE dept IN ({','.join('?'*len(depts))}) ORDER BY id", depts):
        wid = rows("SELECT id FROM workflow WHERE name_th=?", [name])
        steps = rows("SELECT step_th FROM workflow_step WHERE workflow_id=? ORDER BY seq",
                     [wid[0][0]]) if wid else []
        out.append(f"### โฟลว์: {name}")
        if steps:
            out.append(" → ".join(s[0] for s in steps))
        if docs:
            out.append(f"- เอกสารที่เกี่ยวข้อง: {docs}")
        if rules:
            for r in rules.split(" | "):
                out.append(f"- {r}")
        out.append("")
    return "\n".join(out)


def section_rules(depts):
    out = []
    for dept, fact, detail in rows(
            "SELECT dept, fact_th, detail_th FROM doc_fact "
            f"WHERE dept IN ({','.join('?'*len(depts))}) AND confidence='likely-current' "
            "ORDER BY dept, id", depts):
        line = f"- {fact}"
        if detail:
            line += f" — {detail}"
        out.append(line)
    return "\n".join(out)


def section_screens(depts):
    out = []
    for menu, route, purpose, ui in rows(
            "SELECT menu_th, route, purpose_th, ui_type FROM screen "
            f"WHERE dept IN ({','.join('?'*len(depts))}) ORDER BY menu_th", depts):
        out.append(f"- {menu or route} ({ui or 'จอ'}) — {purpose or ''}".rstrip(" —"))
    return "\n".join(out)


def section_api(depts):
    out = []
    for path, purpose, tables in rows(
            "SELECT e.path, e.purpose_th, e.prisma_tables FROM api_endpoint e "
            "JOIN api_module m USING(module) "
            f"WHERE m.dept IN ({','.join('?'*len(depts))}) ORDER BY e.path", depts):
        t = f" [ตาราง: {tables}]" if tables else ""
        out.append(f"- `{path}` — {purpose or ''}{t}".rstrip())
    return "\n".join(out)


def section_tables(depts):
    # tables referenced by this dept's endpoints, with row counts
    tabs = rows(
        "SELECT DISTINCT t.table_name, t.rows FROM api_endpoint e "
        "JOIN api_module m USING(module) "
        "JOIN db_table t ON lower(t.table_name) = ANY(string_split(lower(e.prisma_tables),' ')) "
        f"WHERE m.dept IN ({','.join('?'*len(depts))}) ORDER BY t.rows DESC", depts)
    return "\n".join(f"- {n} (~{r:,} แถว)" for n, r in tabs[:25])


def section_needs(depts):
    out = []
    for need, api, table, note in rows(
            "SELECT need_th, source_api, source_table, note_th FROM ai_data_need "
            f"WHERE dept IN ({','.join('?'*len(depts))}) ORDER BY dept", depts):
        out.append(f"- **{need}** — ดึงจาก {api} (ตาราง {table}); {note}")
    return "\n".join(out)


def build(dept_key, metas):
    th = DEPT_TH[dept_key]
    parts = [HEADER(th)]
    n = section_needs(metas)
    if n:
        parts.append("## ข้อมูลที่ผู้ช่วยแผนกนี้ต้องใช้ (สำคัญสุด)\n" + n + "\n")
    w = section_workflow(metas)
    if w.strip():
        parts.append("## โฟลว์การทำงาน\n" + w)
    r = section_rules(metas)
    if r:
        parts.append("## กฎ/เงื่อนไขธุรกิจที่ต้องรู้\n" + r + "\n")
    parts.append(CODE_NOTES)
    s = section_screens(metas)
    if s:
        parts.append("## จอ/เมนูที่พนักงานแผนกนี้ใช้ในระบบ 1MPRO\n" + s + "\n")
    a = section_api(metas)
    if a:
        parts.append("## API/ข้อมูลเบื้องหลัง (สำหรับผู้ช่วยที่ต่อระบบในอนาคต)\n" + a + "\n")
    t = section_tables(metas)
    if t:
        parts.append("## ตารางข้อมูลหลักที่เกี่ยวข้อง (พร้อมปริมาณข้อมูลจริง)\n" + t + "\n")
    return "\n".join(parts)


def build_overview():
    parts = [HEADER("ภาพรวมระบบ")]
    parts.append("## บริษัทและระบบ")
    parts.append("- บริษัทวันเอ็ม (One M Concrete) — ผู้ผลิตคอนกรีตสำเร็จรูป มอก. จ.อุบลราชธานี")
    parts.append("- ระบบ ERP ชื่อ 1MPRO: web (Nuxt3) → api (Fastify+Prisma) → MariaDB")
    tot = rows("SELECT count(*), sum(rows) FROM db_table")[0]
    parts.append(f"- ฐานข้อมูล: {tot[0]} ตาราง ~{tot[1]:,} แถว (ข้อมูล 2024–2026)")
    parts.append(f"- API {rows('SELECT count(*) FROM api_endpoint')[0][0]} endpoint / "
                 f"จอ {rows('SELECT count(*) FROM screen')[0][0]} จอ\n")
    parts.append("## แผนกและขอบเขต")
    for code, name, summ in rows("SELECT code, name_th, summary_th FROM dept "
                                 "WHERE code NOT IN ('shared') ORDER BY code"):
        parts.append(f"- **{name}** ({code}): {summ}")
    parts.append("\n" + CODE_NOTES)
    parts.append("## กฎธุรกิจหลักทั้งบริษัท")
    parts.append(section_rules(["general", "sales", "accounting", "production",
                                "stock", "delivery"]))
    return "\n".join(parts)


def main():
    os.makedirs(OUT, exist_ok=True)
    written = []
    for dept_key, metas in DEPT_MAP.items():
        body = build(dept_key, metas)
        fn = f"onem-sys-{dept_key}.md"
        with open(os.path.join(OUT, fn), "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        written.append((fn, len(body)))
    ov = build_overview()
    with open(os.path.join(OUT, "onem-sys-overview.md"), "w", encoding="utf-8",
              newline="\n") as f:
        f.write(ov)
    written.append(("onem-sys-overview.md", len(ov)))
    for fn, n in written:
        print(f"[ok] {fn} ({n:,} chars)")
    print("DONE")


if __name__ == "__main__":
    main()
