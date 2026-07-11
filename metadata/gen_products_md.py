"""Synthesize the SKU-level product knowledge doc (onem-products.md) for the OWUI
sales/marketing assistants: the REAL 1MPRO catalog (from products_catalog.json —
authoritative names/specs/prices) enriched with Thai-internet research on specs /
installation / usage (metadata/extract/research/*.json).

Catalog numbers are authoritative (never overwritten by research). Research adds
มอก. standards, load/spec explanations, install steps, usage, FAQ — cited.

Run:  python metadata/gen_products_md.py
Out:  open-webui/company-kb/onem-products.md
"""
import datetime
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "extract")
RES = os.path.join(EX, "research")
OUT = r"C:\Users\AiMiniX\open-webui\company-kb\onem-products.md"
TODAY = datetime.date.today().strftime("%Y-%m-%d")

# research file -> the catalog ptype_names it covers
GROUP_TYPES = {
    "slabs": ["แผ่นพื้นสำเร็จรูป 35", "แผ่นพื้นสำเร็จรูป 30"],
    "piles": ["เสาเข็มไอ", "เสาเข็มสี่เหลี่ยม", "เสาตีนช้าง"],
    "fence": ["เสารั้วรูปตัวไอ", "เสารั้วลวดหนาม", "เสารั้วคาวบอย", "ลวดหนาม",
              "แผ่นรั้วคอนกรีตสำเร็จรูป", "ทับหลังรั้วคอนกรีตสำเร็จรูป"],
    "infra": ["เสาไฟฟ้า", "ขอบคันหิน", "ฟุตติ้งสำเร็จรูป"],
}


def load(path):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}


def price_line(td):
    lo, hi = td.get("price_min"), td.get("price_max")
    u = td.get("unit", "")
    if lo is None:
        return ""
    return f" — ราคา {lo:,.0f}–{hi:,.0f} บาท/{u}" if lo != hi else f" — ราคา {lo:,.0f} บาท/{u}"


def sku_table(skus, limit=40):
    rows = ["| รหัส | ชื่อ/สเปก | ราคา/หน่วย |", "|---|---|---|"]
    for s in skus[:limit]:
        price = f"{float(s['price']):,.0f}" if s.get("price") else "-"
        rows.append(f"| {s['product_id']} | {s['name']} | {price}/{s.get('unit','')} |")
    if len(skus) > limit:
        rows.append(f"| ... | (อีก {len(skus)-limit} รายการ — ดูราคาเต็มในระบบ 1MPRO) | |")
    return "\n".join(rows)


def main():
    cat = load(os.path.join(EX, "products_catalog.json"))
    bt = cat.get("by_type", {})
    L = [f"# รายละเอียดสินค้า วันเอ็มคอนกรีต — ระดับ SKU + สเปก + การติดตั้ง (สำหรับผู้ช่วย AI)\n",
         f"> แคตตาล็อกจริงจากระบบ 1MPRO ({cat.get('total_sku','?')} SKU / {cat.get('n_types','?')} หมวด) "
         f"+ ความรู้สเปก/การติดตั้ง/การใช้งานจากแหล่งไทย · ข้อมูล ณ {TODAY}\n"
         f"> ⚠️ ราคาในเอกสารนี้เป็นราคาโรงงานอ้างอิง — ยืนยันราคาปัจจุบันในระบบ 1MPRO ก่อนออกใบเสนอราคาเสมอ\n"]

    covered = set()
    for grp, types in GROUP_TYPES.items():
        r = load(os.path.join(RES, f"{grp}.json"))
        # section title from the research group or the types
        gt = r.get("group_th") or " / ".join(types)
        L.append(f"\n---\n\n# หมวด: {gt}\n")
        if r.get("overview_th"):
            L.append(r["overview_th"] + "\n")
        if r.get("standard_th"):
            L.append(f"**มาตรฐาน:** {r['standard_th']}\n")
        if r.get("subtypes_th"):
            L.append("## ชนิดย่อยและการเลือกใช้")
            st = r["subtypes_th"]
            if isinstance(st, dict):
                for k, v in st.items():
                    L.append(f"- **{k}**: {v}")
            else:
                L.append(str(st))
            L.append("")
        if r.get("spec_explained_th"):
            L.append("## อธิบายสเปก\n" + r["spec_explained_th"] + "\n")
        if r.get("how_to_choose_th"):
            L.append("## วิธีเลือกให้เหมาะกับงาน\n" + r["how_to_choose_th"] + "\n")
        if r.get("load_table_th"):
            L.append("## การรับน้ำหนัก/ตาราง\n" + r["load_table_th"] + "\n")
        if r.get("spacing_calc_th"):
            L.append("## การคำนวณจำนวน (เสา/ลวด/ต่อไร่)\n" + r["spacing_calc_th"] + "\n")
        steps = r.get("installation_steps_th") or []
        if steps:
            L.append("## ขั้นตอนการติดตั้ง")
            # research sometimes prefixes its own "N. " — strip it so we don't double-number
            clean = [re.sub(r"^\s*\d+[\.\)]\s*", "", str(s)) for s in steps]
            L.append("\n".join(f"{i}. {s}" for i, s in enumerate(clean, 1)) + "\n")
        # infra has nested per-product install
        for pname, pd in (r.get("products") or {}).items():
            L.append(f"### {pname}")
            if pd.get("spec_explained_th"):
                L.append(pd["spec_explained_th"])
            if pd.get("usage_th"):
                L.append(f"- การใช้งาน: {pd['usage_th']}")
            if pd.get("installation_steps_th"):
                L.append("- ติดตั้ง: " + " → ".join(pd["installation_steps_th"]))
            L.append("")
        if r.get("usage_th"):
            L.append("## การใช้งาน\n" + r["usage_th"] + "\n")
        if r.get("common_mistakes_th"):
            L.append("## ข้อควรระวังหน้างาน\n" + "\n".join(f"- {m}" for m in r["common_mistakes_th"]) + "\n")
        if r.get("faq_th"):
            L.append("## คำถามพบบ่อย")
            for qa in r["faq_th"]:
                L.append(f"- **ถาม:** {qa.get('q')}\n  **ตอบ:** {qa.get('a')}")
            L.append("")

        # real SKU tables per type in this group
        L.append("## รายการสินค้าจริง (SKU) พร้อมราคาโรงงาน")
        for tp in types:
            if tp in bt:
                covered.add(tp)
                td = bt[tp]
                L.append(f"\n### {tp} ({td['sku_count']} รายการ){price_line(td)}")
                L.append(sku_table(td.get("skus", [])))
        if r.get("sources"):
            L.append(f"\n*ที่มาข้อมูลสเปก/ติดตั้ง: {', '.join(r['sources'][:8])}*")

    # any catalog types not covered by a research group -> list plainly
    rest = [tp for tp in bt if tp not in covered]
    if rest:
        L.append("\n---\n\n# หมวดอื่น ๆ (SKU จากระบบ)\n")
        for tp in rest:
            td = bt[tp]
            L.append(f"### {tp} ({td['sku_count']} รายการ){price_line(td)}")
            L.append(sku_table(td.get("skus", []), limit=20))
            L.append("")

    body = "\n".join(L) + "\n"
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    print(f"[ok] {OUT} ({len(body):,} chars, {len(covered)} researched types)")


if __name__ == "__main__":
    main()
