# 1MPRO System Metadata — `onem_meta.duckdb`

> คลัง metadata ของระบบ ERP **1MPRO** (บริษัทวันเอ็ม คอนกรีตสำเร็จรูป อุบลฯ) —
> แกะจาก **เอกสาร spec + โค้ด web/api + ฐานข้อมูลจริง + การเล่นเว็บ + การดึงข้อมูลผ่าน API**
> เพื่อทำ **md ลง Open WebUI** และป้อน **AI ผู้ช่วยรายแผนก** ของบริษัท
> สร้าง 2026-07-11 · `python metadata/build_meta.py` (idempotent, read-only inputs, ไม่มี PII ลูกค้า)

## แหล่งข้อมูลที่แกะ (6 ทาง — ยืนยันข้ามกัน)

| ทาง | ได้อะไร | สคริปต์ / ผล |
|---|---|---|
| 📄 เอกสาร spec | business rules, สูตร, รหัสเอกสาร | `extract/doc_facts.json` (95 facts, 10 workflows จาก 2 PDF + web.txt) |
| ⚙️ โค้ด API (Fastify) | endpoint ทั้งหมด → ตาราง/filter/role | `extract/api_endpoints.json` (**290 endpoints / 32 modules**) |
| 🖥️ โค้ด web (Nuxt) | เมนู + จอ → API ที่เรียก | `extract/web_screens.json` (**92 screens / 65 menu**) |
| 🗄️ ฐานข้อมูล (MariaDB `test_api`) | schema จริง + row count + FK | `extract/db_schema.json` (**121 tables / 3,125 cols / 347 FK / 1.42M rows**) — `extract_db.py` |
| 🎬 เล่นเว็บจริง (Playwright) | จอ → API call + filter ที่ยิงจริง | `extract/web_observations.json` (56 obs, 26 endpoints) — `digest_webplay.py` |
| 🔌 ดึงผ่าน API จริง (read-only) | response shape + sum + enum จริง | `extract/api_samples.json` (26 endpoints, 74 enum fields) — `pull_api_samples.py` |

## ตารางใน DuckDB (จัดตาม แผนก / โฟลว์ / ข้อมูล-AI)

| ตาราง | แถว | ใช้ทำอะไร |
|---|---|---|
| `dept` | 10 | แผนก (spine): sales/purchasing/accounting/production/stock/delivery/reports/admin/general |
| `doc_fact` | 95 | กฎธุรกิจ+ข้อมูล (confidence: likely-current 90 / doc-only 5) |
| `workflow` + `workflow_step` | 10 | โฟลว์เอกสารต่อแผนก (QT→SO→ผลิต→สต๊อก→DR→IV/RE→RCX) |
| `api_module` / `api_endpoint` | 32 / 290 | API surface → prisma_tables, filters, roles ต่อ endpoint |
| `menu` / `screen` | 65 / 92 | web surface → api_calls, ui_type, roles ต่อจอ |
| `db_table` / `db_column` / `db_fk` | 121 / 3125 / 347 | schema จริง + จำนวนแถว + กราฟ FK |
| `api_observation` | 56 | หลักฐาน "จอ → API จริง + filter" จากการเล่นเว็บ |
| `api_sample` | 26 | response shape + meta + sum ต่อ endpoint (ดึงสด) |
| `enum_value` | 201 | คำศัพท์ enum จริง (order_status/status_payment/cus_type...) — ไม่มี PII |
| `ai_data_need` | 12 | **curated**: ผู้ช่วย AI แต่ละแผนกต้องรู้อะไร + ข้อมูลอยู่ที่ endpoint/table ไหน |

## ข้อมูลรวมที่ยืนยันแล้ว (จากหลายแหล่งตรงกัน)

- **แผนก endpoint หนาสุด**: ขาย 75 · สต๊อก 48 · บัญชี 41 · ผลิต 29
- **ตารางใหญ่สุด**: ActivityLogs 360k · Timeline 158k · OrderDetail 89k (timeline/log = แกนของระบบ ตรงกับ business rule "ทุกเอกสารมี timeline ก่อน/หลัง+เหตุผล")
- **enum จริง**: cus_type = GENERAL/SHOP/COMPANY/CONTRACTOR (4 ประเภทตรง doc) · order/payment/send status เป็นรหัสตัวเลข → ต้องแปลเป็นภาษาคนก่อนป้อน AI
- **business rules สำคัญ** (ดู doc_fact): มัดจำขั้นต่ำ 30% · ค่าปรับคืน 20% · คืนเงิน 80/100% ตามออก-สต๊อก · รหัสเอกสาร 12 ตัว (AI/HS/IV/BI/RE/RT/SR/CL/CO/EX/EO/DR) · **ยอดขาย=เงินรับจริง(payment_total) ไม่ใช่ order_total**

## วิธี query (ตัวอย่าง)

```sql
-- ผู้ช่วยแผนกขายต้องรู้อะไร + ดึงจากไหน
SELECT need_th, source_api, source_table, note_th FROM ai_data_need WHERE dept='sales';
-- endpoint ของแผนกบัญชี พร้อมตารางที่แตะ
SELECT e.path, e.purpose_th, e.prisma_tables FROM api_endpoint e
  JOIN api_module m USING(module) WHERE m.dept='accounting';
-- กฎธุรกิจที่ยัง likely-current เท่านั้น
SELECT dept, fact_th, detail_th FROM doc_fact WHERE confidence='likely-current' ORDER BY dept;
```

## ต่อยอด (งานถัดไป)
- **gen_md.py**: อ่าน DuckDB → md รายแผนก (`onem-sys-<dept>.md`) ลงคลังความรู้ Open WebUI แต่ละแผนก
- rebuild เมื่อโค้ด/ระบบเปลี่ยน: รัน extract 6 ตัวใหม่ → `build_meta.py`
