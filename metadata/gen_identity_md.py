"""Synthesize the company IDENTITY doc (onem-identity.md) for the OWUI assistants
from the public-web extracts: web_onemcon.json + web_eoncrete.json + company_social
.json. Brand character, products/services, public presence, contact, reputation.

Grounded in the extracts only; every non-obvious claim keeps its source. Thai.
No customer PII (this is all public company info).

Run:  python metadata/gen_identity_md.py
Out:  open-webui/company-kb/onem-identity.md
"""
import datetime
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "extract")
OUT = r"C:\Users\AiMiniX\open-webui\company-kb\onem-identity.md"
TODAY = datetime.date.today().strftime("%Y-%m-%d")


def load(name):
    p = os.path.join(EX, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def bullets(items, prefix="- "):
    return "\n".join(f"{prefix}{x}" for x in items if x)


def main():
    onem = load("web_onemcon.json")
    eon = load("web_eoncrete.json")
    soc = load("company_social.json")
    L = [f"# ตัวตนและแบรนด์ บริษัทวันเอ็ม / One M Concrete (สำหรับผู้ช่วย AI)\n",
         f"> รวบรวมจากเว็บบริษัท (onemcon.com, eoncrete.com), Facebook, Google Maps, "
         f"และแหล่งสาธารณะ · ข้อมูล ณ {TODAY}\n"
         f"> ใช้ประกอบการสื่อสารกับลูกค้า/สร้างคอนเทนต์ให้ตรงตัวตนแบรนด์\n"]

    # brand character
    brand = onem.get("brand") or eon.get("brand") or {}
    L.append("## ตัวตน/บุคลิกแบรนด์")
    if brand.get("name_th"):
        L.append(f"- ชื่อแบรนด์: {brand.get('name_th')}")
    if brand.get("tagline_th"):
        L.append(f"- สโลแกน: {brand.get('tagline_th')}")
    if brand.get("voice_th"):
        L.append(f"- โทนการสื่อสาร: {brand.get('voice_th')}")
    for v in (eon.get("brand", {}).get("voice_th"),):
        if v and v != brand.get("voice_th"):
            L.append(f"- โทน (eoncrete): {v}")
    L.append(bullets(brand.get("values_th") or []))
    syn = soc.get("identity_synthesis_th") or []
    if syn:
        L.append("\n### สรุปตัวตนจากภาพรวมสาธารณะ")
        L.append(bullets(syn))

    # about
    about = onem.get("about_th") or eon.get("about_th")
    if about:
        L.append("\n## เกี่ยวกับบริษัท\n" + about)

    # scale / branches / reputation from social
    gm = soc.get("google_maps") or {}
    fb = soc.get("facebook") or {}
    L.append("\n## สถานะและการมีตัวตนสาธารณะ")
    if fb.get("followers"):
        L.append(f"- Facebook (@Eoncrete): ผู้ติดตาม {fb.get('followers')} · หมวด "
                 f"{fb.get('category_th','วัสดุก่อสร้าง')}")
    if gm.get("rating"):
        L.append(f"- Google Maps: คะแนน {gm.get('rating')} · {gm.get('category_th','')}")
    for r in (soc.get("web_reputation") or [])[:8]:
        L.append(f"- {r.get('claim_th')}" + (f" (ที่มา: {r.get('source_url')})"
                                             if r.get("source_url") else ""))

    # products (concise — the detailed SKU doc is onem-products.md)
    prods = (onem.get("products") or []) + (eon.get("products") or [])
    if prods:
        L.append("\n## กลุ่มสินค้า (ภาพรวม — รายละเอียด SKU ดูเอกสารสินค้า)")
        seen = set()
        for p in prods:
            cat = p.get("category") or p.get("name_th", "")
            if cat and cat not in seen:
                seen.add(cat)
                price = f" ~{p['price']}" if p.get("price") else ""
                L.append(f"- {cat}{price}")

    # services
    svcs = (onem.get("services") or []) + (eon.get("services") or [])
    if svcs:
        L.append("\n## บริการ")
        seen = set()
        for s in svcs:
            n = s.get("name_th", "")
            if n and n not in seen:
                seen.add(n)
                L.append(f"- {n}" + (f" — {s['detail_th']}" if s.get("detail_th") else ""))

    # contact (authoritative)
    c = onem.get("contact") or eon.get("contact") or {}
    L.append("\n## ช่องทางติดต่อ (ทางการ — ให้ลูกค้าได้เท่านี้)")
    L.append(f"- โทร: {c.get('tel') or '061-436-2825'}")
    L.append(f"- Line: {c.get('line') or '@eoncrete'}")
    if c.get("address_th"):
        L.append(f"- ที่อยู่: {c.get('address_th')}")
    if gm.get("address_th") and gm.get("address_th") != c.get("address_th"):
        L.append(f"- สาขา/ที่ตั้งเพิ่ม: {gm.get('address_th')}")
    L.append(f"- เวลาทำการ: {c.get('hours_th') or 'จ.–ส. 08:00–17:00'}")
    L.append("- เว็บไซต์: onemcon.com, eoncrete.com")

    # delivery footprint
    facts = (onem.get("notable_facts_th") or []) + (eon.get("notable_facts_th") or [])
    if facts:
        L.append("\n## ข้อเท็จจริงเด่นที่ควรรู้")
        L.append(bullets(facts[:15]))

    L.append("\n## กติกาการใช้ข้อมูลนี้")
    L.append("- ราคาที่แน่นอนให้ยึดตารางราคา/ระบบ 1MPRO เสมอ ตัวเลขในหน้าเว็บอาจเป็นราคาโปรฯ/เก่า")
    L.append("- ช่องทางติดต่อให้ลูกค้าได้เฉพาะ โทร 061-436-2825 และ Line @eoncrete")
    L.append("- ห้ามกล่าวอ้างรีวิว/รางวัลที่ไม่มีในข้อมูลนี้")

    body = "\n".join(L) + "\n"
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    print(f"[ok] {OUT} ({len(body):,} chars)")


if __name__ == "__main__":
    main()
