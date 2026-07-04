# One M / 1MPRO — Handoff & Metadata

> Read this first. It is written so a fresh AI (or dev) can pick up work with full context.
> Last verified: 2026-07-04. Working dir on this machine: `C:\Users\AiMiniX\DevXV3\one-m`.

---

## 1. The Company

- **Legal name:** บริษัท วันเอ็ม จำกัด — **One M Co., Ltd.**
- **Brand / public name:** **One M Concrete** ("eoncrete")
- **Business:** Manufacturer & wholesale distributor of **precast concrete products** (มอก. / Thai Industrial Standard certified). Factory prices, made-to-order + stock.
- **Head office / factory:** 290 หมู่ 1 ต.กระโสม อ.เมือง จ.**อุบลราชธานี** 34000 (Ubon Ratchathani, NE Thailand / Isan).
- **Production:** **3 plants** in operation + a **4th planned in Korat (นครราชสีมา)**. Multi-branch company (each branch sees only its own data; executives see all).
- **Service area:** ทั่วภาคอีสาน — Ubon Ratchathani, Amnat Charoen, Yasothon, Sisaket, Surin, Udon Thani, Nakhon Ratchasima (+ occasional Bangkok).
- **Contact (public):** Tel 061-436-2825 · Line ID **@eoncrete** · Mon–Sat 08:00–17:00.
- **Public websites:** `onemcon.com`, `eoncrete.com` (marketing/catalog — products, installation examples, knowledge base, contact).

### Product lines (precast concrete)
- **Piles:** เสาเข็มไอ (I-beam), เสาเข็มสี่เหลี่ยมตัน (square solid), ไมโครไพล์ (micro pile)
- **Fencing:** เสารั้วลวดหนาม (barbed-wire fence posts), รั้วสำเร็จรูป (precast panels), รั้วคาวบอย (cowboy fence)
- **Infrastructure:** กำแพงกันดิน (retaining walls), แผ่นพื้นสำเร็จรูป (floor slabs — top seller), แผ่นปูพื้นทางเท้า (pavers), รางระบายน้ำ (drainage channels)
- **Utilities:** เสาไฟฟ้า (electric poles), แบริเออร์ (barriers), ขอบคันหิน (curb stones), ฟุตติ้ง (footings)
- **Services:** design consultation, free BOQ material calc, retaining-wall engineering, free floor-slab towing, installation, free on-site material stacking.

### Scale (SME — from live ERP data, 2026-07-04)
- Cumulative sales shown ≈ **46.2M ฿**; **191 sale orders** in the current period; **~80 orders + 66 customers / month**; single orders range **3.8k–15M ฿**.
- Database: **121 tables, ~1.4M rows**, data spanning **2024–2026**.
- Staff organized into ~**12 roles/departments** (see role list in §4).
- **4 customer types:** ลูกค้าทั่วไป, ร้านค้าวัสดุ, บริษัทรับเหมา, ผู้รับเหมา. Cash **and** credit customers (credit-clearing workflow).

---

## 2. The Program (1MPRO)

Custom, full-scope **ERP** covering the whole operation: quotation → sales → production → inventory → delivery → accounting/credit → returns → reporting.

**Architecture:** `web` (Nuxt 3 SPA) → `api` (Fastify + Prisma + zod + JWT) → **MariaDB 10.6**.
Standard API response: `{ status, message, result, meta?, sum? }`. Auth = JWT stored in `localStorage`; role in `user_type`.

### Repo / folder layout on this machine
```
one-m/                         git repo (remote github.com/DevXV3/1m) — orchestration/docs only
├── HANDOFF.md                 <- this file
├── README.md                  <- projects table + setup notes
├── e2e/                       <- full-system Playwright test & action-logger (see §6)
├── Ai1/                       <- company AI project (scaffold, TBD)
└── backoffice/                <- 1MPRO system (a plain container folder, NOT a git repo)
    ├── web/                   frontend — Nuxt 3 · repo thanaautho/1mpro_v2 · runs :3000
    └── api/                   backend  — Fastify · repo thanaautho/1mpro_api_v3 · runs :8080
```
> `web/` and `api/` are each their own git repo (own remotes). `backoffice/` is just a folder.
> ⚠️ Folder names vs content were crossed during manual moves then fixed & git-verified (2026-07-04): `web/`=Nuxt, `api/`=Fastify, each with its correct `.git`.

### Run it
- **api:** `cd backoffice/api && npm install && npx prisma generate && npm run dev` → http://localhost:8080 (Swagger `/docs`). Needs `.env` (see §5).
- **web:** `cd backoffice/web && npm run dev` → http://localhost:3000.
- Node 24 on this machine (Nuxt 3.2 warns "unsupported" but works — user chose to stay on 24).

### Gotchas (must-know to make it run — full detail in README.md)
- **web:** `oneMFunction/config.ts` is gitignored (only `config_DF.ts` template ships) — `cp oneMFunction/config_DF.ts oneMFunction/config.ts`; 45 files import it. `urlApi()` = API base (set to `http://localhost:8080` to use local api, or `https://test.1mpro.com` for hosted test). Also needs `.env` `VITE_API_URL` matching. Do NOT downgrade Vue below 3.4 (tree needs it); v-model-on-const in cherry* scratch pages was fixed with `ref()`. Don't push the local `@esbuild/linux-x64` removal upstream (Linux build needs it).
- **api:** dev runs `--transpile-only` (skips ~1,200 pre-existing strict type errors — that's expected tech debt, not your bug). Prisma client postinstall is blocked by allow-scripts → run `npx prisma generate` manually.

---

## 3. Test env & credentials
- Hosted test API: `https://test.1mpro.com` (CORS `*`). App login: `POST /api/user/login {username,password}` → `{status, result, accessToken}`.
- A full-access `dev`-role test account exists (maps to factory "บริษัท วันเอ็ม จำกัด" / branch "สำนักงานใหญ่"). **Credentials are intentionally kept out of this repo — get current test login from the project owner.**

---

## 4. Feature map (top nav — horizontal, role-gated)
Roles seen: `admin, dev, sale, headofsales, accounting, manager, special, saleandproduction, production, stock, mixconcrete, shippingplan`.

1. **ภาพรวม** (Dashboard) — sales/production KPIs, top customers/products, YoY compare (`/api/report/summary-*`)
2. **ขายสินค้า** — customers · quotation/sales (`/sale/qoutation`) · orders waiting/complete · **return/claim/exchange (RCX)**
3. **จัดซื้อสินค้า** (admin/dev) — PO · receipt · supplier
4. **บัญชี** — deposit/payment (AI) · debit/credit note (SR) · expenses · installment · credit clearing (invoice IV / receipt RE)
5. **ผลิตสินค้า** — production plan (day-by-day, per plant) · produce · list · product conversion
6. **สต๊อกสินค้า** — check-in · stock list · temp stock · defective · moving · history · withdraw/barcode
7. **ส่งสินค้า** — delivery notes · plan · success · shipping reports
8. **รายงาน** — sales/production/stock/defective/conversion/quotation/return
9. **รายงานผู้บริหาร** (admin/dev/manager) — sales by period/channel/salesperson · YoY/MoM · shipping-vs-product cost split · production/conversion/defective summaries · **contractor wages + commission**
10. **การจัดการ** — products/types/units · plant(แพ)/warehouse · contractor-wage & commission config · date edits · transport
11. **Admin** — users · employees · factory · LOG

**Sizes:** web = **401 .vue pages**; api = **25 modules** (activitylogs, building, commission, conversion, customer, factory, movingorders, orders, payment, paymentcredit, plant, product, production, productiondetail, productplant, rcx, report, shipping, stockbystore, stockinout, stocklist, stores, timeline, user, usertype). Per-module API docs live in `backoffice/api/docs/*.md` — read the relevant one before changing a feature.

### Core document/business workflow
`ใบเสนอราคา (QT) → ออเดอร์ขาย (SO, OR-number auto) → ผลิต (per-plant, "แพ" numbering restarts per plant; plan → controller approves capacity → produce → QC into stock) → สต๊อก (good vs defective; barcode per-product not per-piece) → เบิก/ส่งของ (DR delivery note doubles as stock-withdraw) → วางบิล/ใบเสร็จ (IV / RE / BI) with cash vs credit (credit-clearing queue) → คืน/เคลม/เปลี่ยน (RCX; refund 80%/100% rules keyed on paid × in-stock state).`
Every order & production doc has an **edit timeline** (`/api/timeline` + `ActivityLogs` table: before/after + reason). Document types: QT, AI, HS, SO, DR, SR, IV, BI, RE, PO, MO, MV.

### UX/UI
Vuetify 3 "Modernize" admin theme, blue accent, horizontal top-nav, **dense data-table-centric** screens (vue3-easy-data-table) with inline per-row action icons (print/copy/pay/cart/edit/delete). Thai UI, Buddhist-era dates. Optimized for fast staff data entry (type-to-search + inline table select). Mature, consistent, actively used in production.

---

## 5. Data & database (⚠️ safety-critical)
- **api `.env` (`backoffice/api/.env`, gitignored)** holds `DATABASE_URL` (the shared **dev MariaDB 10.6**) + Telegram tokens. **Never commit or echo these** — copy `.env.example` and get real values from the project owner. The dev DB is directly reachable from this machine (no SSH tunnel).
- ⚠️ **This is a shared dev DB. READ/USE ONLY. NEVER run `prisma migrate` / `db push` / `db pull`** — it would alter the schema others depend on. Access DB only through `src/utils/prisma.ts`. Production DB is view-only. Scripts in `src/cronjob/` named `migrate_`/`fix_`/`remove_` mutate real data — do not run without understanding impact.
- **Backup for rollback:** full logical dump at `C:\Users\AiMiniX\DevXV3\1m-db-backups\test_api_<timestamp>.sql` (~333MB, 121 tables, restorable; made with `…scratchpad/dbbackup/dump.js` since no mysqldump/docker on this machine). Re-run that script to refresh.
- SSH dev/pro server details (hosts, users, ports) are documented in `backoffice/api/CLAUDE.md`; aliases go in your local `~/.ssh/config` (not committed).

---

## 6. E2E test harness (`one-m/e2e/`)
Playwright (chromium) drives web+api and logs **every action** per run to `runs/<ts>_<scenario>/`: `report.md` (interleaved UI+api timeline), `actions/network/console.jsonl`, full-page `screenshots/`, `trace.zip`, `api-server.log` snapshot.
- `node run.js api-smoke` — direct api calls.
- `node run.js login-smoke` — web login (set `E2E_USER`/`E2E_PASS`).
- `E2E_USER=<user> E2E_PASS=<pass> node run.js explore` — full 18-page workflow tour (evidence of the analysis lives in `runs/20260704_222707_explore/`).
- Add scenarios in `scenarios/<name>.js`; wrap actions in `await log.step(...)`.

---

## 7. Doc vs reality
`โปรแกรม 1MPRO.docx` (in Downloads) = early/mid dev **spec + task tracker** (team: ติ่ง=backend, บิ๊ม/บิ๋ม/เอก/เกม=frontend, พี่ตั้ม=design). **Its later task-status table is badly outdated** — the live system is far more complete (RCX, barcode, conversion, production planning, purchasing, print docs all done; huge exec-report suite exists that the doc doesn't mention). Use the doc for **business rules & scope**, NOT for "what's done". **Genuine gap vs doc:** raw-material stock (สต๊อกวัตถุดิบ) — only partial `/material/*` pages, report menu commented out, no dedicated api module.

## 8. Known live issues (minor, non-blocking)
- `GET /api/report/last-update-report` → 500.
- Dashboard chart data-race: "Cannot read properties of undefined (reading 'data')".

## 9. Rules & conventions
- **Code/identifiers in English only**; Thai allowed in comments/docs.
- Don't commit `.env` / `node_modules`; no secrets in source (env only).
- api: TS avoid `any`; validate with zod; when an API contract changes, update the matching `docs/*.md` in the same task; keep `api/CLAUDE.md` and `api/AGENTS.md` in sync.
- Don't push local machine-specific tweaks upstream (see §2 gotchas).

## 10. Pointers
- Deployment/run state & history → memory `one-m-company-projects`.
- Deep system analysis → memory `onem-1mpro-system-analysis`.
- Per-feature API contracts → `backoffice/api/docs/*.md`.
- Live evidence (screens, api log) → `e2e/runs/20260704_222707_explore/`.
