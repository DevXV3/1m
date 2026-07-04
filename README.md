# One M (วันเอ็ม)

Company projects root for One M. Each task/sub-project lives in its own folder.

> 📌 **New here (human or AI)? Read [`HANDOFF.md`](HANDOFF.md) first** — full company + 1MPRO program metadata, run instructions, DB safety rules, and pointers.

## Structure

```
one-m/
├── README.md      <- this file
└── <task-name>/   <- one folder per task (added as work comes in)
```

## Conventions

- Code and identifiers in English only (Thai allowed in comments/docs).
- Each sub-project keeps its own README with setup/run instructions.

## Projects

The 1MPRO system lives under `backoffice/` as two sibling repos:

```
one-m/
├── Ai1/                 <- company AI project (scaffold)
├── e2e/                 <- full-system test harness (Playwright) — logs every web+api action
└── backoffice/          <- 1MPRO system (container; not a repo itself)
    ├── web/             <- frontend (Nuxt)   — repo thanaautho/1mpro_v2
    └── api/             <- backend  (Fastify) — repo thanaautho/1mpro_api_v3
```

> **api database:** `backoffice/api/.env` `DATABASE_URL` points at the shared **dev MariaDB at `15.220.242.10` / db `test_api`** (reachable directly). Treat it **read/use only — never run prisma migrate/db push/db pull** (shared schema). A restorable logical backup lives outside the repos at `C:\Users\AiMiniX\DevXV3\1m-db-backups\test_api_<timestamp>.sql` (~333MB).
>
> **E2E harness (`e2e/`):** `cd e2e && npm run api` (api-smoke) or `npm run login` (login-smoke, set `E2E_USER`/`E2E_PASS`). Each run writes `runs/<ts>_<scenario>/` with an interleaved `report.md` timeline, `network.jsonl` (web↔api, `isApi:true`), screenshots, and a Playwright `trace.zip`. See `e2e/README.md`.

| Folder | Description | Stack | Status |
|--------|-------------|-------|--------|
| `backoffice/web/` | 1MPRO web client / back-office UI (buy/sell + production management). Clone of [thanaautho/1mpro_v2](https://github.com/thanaautho/1mpro_v2). API base: `https://test.1mpro.com`. | Nuxt 3 / Vue 3 / Vuetify (SPA) | Runs locally (`npm run dev` → http://localhost:3000) |
| `backoffice/api/` | 1MPRO backend API (the server `web` talks to). Clone of [thanaautho/1mpro_api_v3](https://github.com/thanaautho/1mpro_api_v3). | Fastify + Prisma (MySQL) + zod + JWT, TypeScript | Installed; runs on `:8080`, needs MySQL to be functional |
| `Ai1/` | Company AI project | _TBD_ | Scaffold |

> `backoffice/web/` and `backoffice/api/` are each their own git repo (own remote); `backoffice/` itself is just a container and is **not** a git repo. Neither is tracked inside the one-m root repo.

**`backoffice/web/` — frontend (Nuxt) local setup (required to run):**
> 1. `oneMFunction/config.ts` is **gitignored** (only the `config_DF.ts` template ships). Copy it: `cp oneMFunction/config_DF.ts oneMFunction/config.ts`. 45 files import `~~/oneMFunction/config`; without it the whole app fails to load config (API base `urlApi()` → `https://test.1mpro.com`; point it at `http://localhost:8080` to use the local `api`).
> 2. `.env` (gitignored) with `VITE_API_URL=https://test.1mpro.com` — used by `utils/helpers/fetch-wrapper.ts` to attach the Bearer auth header.
> 3. Windows-only: removed the Linux-only `@esbuild/linux-x64` pin from `package.json` (do NOT push upstream — Linux shared-hosting build needs it).
> 4. **Vue version note:** repo ships no lockfile, so `npm install` resolves `vue@^3.3.4` → 3.5.x. Vue 3.4+ makes `v-model` on a `const` a hard compile error; the dev scratch pages `cherryBtn.vue` / `cherryBtnAction.vue` / `cherryGraph.vue` used that pattern, so those consts were wrapped in `ref()`. Do not downgrade Vue to 3.3.x — the rest of the freshly-installed tree needs 3.4+ compiler APIs (`extractRuntimeEmits`).

**`backoffice/api/` — backend API (Fastify) setup:**
> `npm install` → `npx prisma generate` → copy `.env.example` to `.env` and set a real `DATABASE_URL` (MySQL). Dev: `npm run dev` (port 8080), Swagger at `/docs`. Boots without a DB (Prisma connects lazily; Bull/Redis is currently commented out in `src/app.ts`), but any DB-backed endpoint 500s until MySQL is reachable. Runs on Node 24. Read `CLAUDE.md` / `AGENTS.md` before editing (keep them in sync); DB access only via `src/utils/prisma.ts`; ~1,200 pre-existing type errors under strict, dev runs `--transpile-only`.
