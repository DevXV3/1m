# 1MPRO Metadata & Company-Data — HANDOFF (สำหรับ agent อื่นทำต่อ/ใช้ร่วม)

> อ่านไฟล์นี้ก่อน. งานนี้ = แกะระบบ ERP 1MPRO ของบริษัทวันเอ็ม + เก็บข้อมูลบริษัทจากสาธารณะ
> → รวมเป็น **`onem_meta.duckdb`** → เจน **md ลง Open WebUI** ให้ผู้ช่วย AI รายแผนก + ป้อน BI/model
> โฟลเดอร์: `C:\Users\AiMiniX\DevXV3\one-m\metadata\` · สร้าง/อัปเดต 2026-07-11

## 0. TL;DR — ของที่ส่งมอบ
- **`onem_meta.duckdb`** — คลัง metadata ทั้งระบบ (19 ตาราง + 7 view) จัดตาม **แผนก / โฟลว์ / ข้อมูล-AI / รหัส / สินค้า**
- **`open-webui/company-kb/onem-sys-<dept>.md`** (7 ไฟล์) — ความรู้ระบบรายแผนก → import คลังความรู้ OWUI แล้ว
- **`open-webui/company-kb/onem-products.md`** — สินค้าระดับ SKU + สเปก/ติดตั้ง/ใช้งาน
- **`open-webui/company-kb/onem-identity.md`** — ตัวตน/แบรนด์/ช่องทาง/ชื่อเสียงสาธารณะ
- ทุกอย่าง rebuild ได้ (สคริปต์ครบ) · ไม่มี PII ลูกค้า (schema/enum/master/ราคา public เท่านั้น)

## 1. แหล่งข้อมูล 6+3 ทาง (ยืนยันข้ามกัน)
| ทาง | สคริปต์ | ผล (`extract/`) |
|---|---|---|
| เอกสาร spec (2 PDF+web.txt) | (subagent) | `doc_facts.json` — 95 facts, 10 workflows |
| โค้ด API (Fastify) | (subagent) | `api_endpoints.json` — 290 endpoints / 32 modules |
| โค้ด web (Nuxt) | (subagent) | `web_screens.json` — 92 screens / 65 menu |
| DB schema (MariaDB test_api) | `extract_db.py` | `db_schema.json` — 121 tables / 3125 cols / 347 FK / 1.42M rows |
| เล่นเว็บจริง (Playwright) | `digest_webplay.py` | `web_observations.json` — 56 obs (จาก e2e/runs เดิม) |
| ดึงผ่าน API จริง (read-only) | `pull_api_samples.py` | `api_samples.json` — 26 endpoints, 74 enum fields |
| master/reference (read-only) | `extract_refdata.py` | `ref_data.json` — 10 ตาราง + Product 400 SKU |
| แคตตาล็อกสินค้า | (inline) | `products_catalog.json` — 400 SKU / 16 type |
| เว็บบริษัท + social | (subagent) | `web_onemcon.json`, `web_eoncrete.json`, `company_social.json` |
| วิจัยสินค้า (เน็ตไทย) | (subagent) | `research/{slabs,piles,fence,infra}.json` |

## 2. Pipeline (รัน rebuild ตามลำดับ)
```
1) extract (6 ตัวอัตโนมัติ/subagent) → extract/*.json          # แกะดิบ
2) python metadata/build_meta.py                               # รวมเป็น DuckDB (19 ตาราง)
3) python metadata/bi_views.py                                 # เพิ่ม 7 view สำหรับ BI/AI
4) python metadata/gen_md.py                                   # md ระบบรายแผนก (onem-sys-*.md)
5) python metadata/gen_products_md.py                          # md สินค้า SKU (onem-products.md)
6) python metadata/gen_identity_md.py                          # md ตัวตนแบรนด์ (onem-identity.md)
7) docker cp company-kb + python open-webui/import_sys_kb.py   # เข้า OWUI knowledge
```
- extract ที่ต่อ DB/API: ต้อง container `ai1m-mariadb` รัน (creds ใน container env) + test API `https://test.1mpro.com` (login `thana3`/`1234567`, ต้องมี UA header ไม่งั้น WAF 403)

## 3. onem_meta.duckdb — ตาราง & view
**ตาราง (19):** dept · role · doc_fact · workflow/workflow_step · api_module/api_endpoint ·
menu/screen · db_table/db_column/db_fk · api_observation · api_sample · enum_value ·
ai_data_need · **ref_table/ref_value** (แปลรหัส 144) · **status_dict** (35: order/payment/send status + cus_type + เอกสาร 12 ตัว) · **product_type/product_sku** (400 SKU + ราคา public) · meta_source

**View (BI/AI):** `v_endpoint` (endpoint+dept+tables) · `v_screen` · `v_dept_summary` (นับต่อแผนก) ·
`v_product` (SKU flat + ราคา) · `v_code` (รหัส→ไทยทุกชนิดรวมกัน) · `v_table_usage` (ตาราง+แผนกที่ใช้) · `v_ai_brief` (ผู้ช่วยแต่ละแผนกต้องรู้อะไร)

**ตัวอย่าง query สำหรับ agent อื่น:**
```sql
SELECT * FROM v_dept_summary;                          -- ภาพรวมแต่ละแผนก
SELECT code,name_th FROM v_code WHERE domain='doc_code';-- รหัสเอกสาร→ไทย
SELECT * FROM v_product WHERE ptype_name LIKE 'แผ่นพื้น%';
SELECT need_th,source_api,source_table FROM v_ai_brief WHERE dept='sales';
```

## 4. ข้อค้นพบสำคัญ (อัปเดตจากของเดิม)
- **สาขาสีดา (นครราชสีมา) เป็น branch จริงแล้ว** (Factory SD, ที่อยู่ 153 ต.โพนทอง อ.สีดา 30430) — ไม่ใช่แค่ "โรงที่ 4 ที่วางแผน" ตามเอกสารเก่า. HQ = อุบล (290 ม.1 ต.กระโสบ/กระโสม)
- **DB ไม่มี `@@map`** → ชื่อตาราง = ชื่อ Prisma model (PascalCase: `Orders`, `StockList`) → join metadata ตรง ๆ ได้
- **Role gating เป็น menu-only** (ไม่มี route guard) — ใครยิง URL ตรงก็เข้าได้; สิทธิ์จริงอยู่ที่ backend
- **นิยามยอดขาย = payment_total ไม่ใช่ order_total** (กับดัก report — sum keys แยก payment_ai/hs/iv/re/dr/sr)
- รหัสสถานะเป็นเลข 1–6 opaque → ใช้ `status_dict`/`v_code` แปล
- FB @Eoncrete ~110k followers (ad-driven, engagement ต่ำ) · Google Maps 5.0 · จดทะเบียน ~2555 · TikTok @one_m2021 · ในทะเบียน SME-GP (พร้อมงานราชการ)
- สินค้าขายดี: แผ่นพื้น 35 (107 SKU) + 30 (71) · เสาเข็มไอ/สี่เหลี่ยม/ตีนช้าง (167) · ราคา public จาก unit_price (ไม่ใช่ cost_price)

## 5. ขอบเขต/ข้อควรระวัง
- **ไม่มี PII ลูกค้าในคลังนี้** — ตั้งใจ pull เฉพาะ schema/enum/master/ราคา public. ถ้าต่อยอดต้องดึง transactional (orders/customers) ให้แยก PII vault แบบโปรเจค Xchat
- ราคาในเว็บ/เอกสาร = อ้างอิง; ราคาจริงยึดระบบ 1MPRO (`Product.unit_price` สด)
- api_samples แค่ 26 endpoint (ที่เล่นเว็บเห็น); ถ้าต้องการ shape ครบ 290 → ต่อ `pull_api_samples.py` ด้วย body ที่ valid ต่อ zod (ดู `api_endpoints.json` body_fields)
- research/*.json = ข้อมูลจากเน็ตไทย (cite sources) — สเปกทั่วไปของอุตสาหกรรม ไม่ใช่สเปกเฉพาะรุ่นบริษัท 100% (สเปกจริงยึดแคตตาล็อก/มอก. บริษัท)

## 6. ต่อยอดได้ (ยังไม่ทำ)
- text-to-SQL/BI: ชี้ Vanna/Cube มาที่ view (`v_*`) ของ onem_meta.duckdb ([[ai1m-vanna-setup]])
- ดึง transactional จริงเข้า warehouse (แยก PII) เพื่อ AI ตอบด้วยข้อมูลสด (ตอนนี้ผู้ช่วยรู้ "โครงระบบ+วิธี" แต่ยังไม่ query ข้อมูลสดผ่าน tool — ต้อง wire `onem_erp_query` endpoints จริง ดู [[pingzy-webui-departments]])
- gen md เพิ่ม: การจัดการ/admin, จัดซื้อ (ยังไม่มีผู้ช่วย OWUI แผนกนี้)
