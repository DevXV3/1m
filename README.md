# One M (วันเอ็ม)

Company projects root for One M. Each task/sub-project lives in its own folder.

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

| Folder | Description | Stack | Status |
|--------|-------------|-------|--------|
| `backoffice/` | 1MPRO back-office (buy/sell + production management). Clone of [thanaautho/1mpro_v2](https://github.com/thanaautho/1mpro_v2). API base: `https://test.1mpro.com`. | Nuxt 3 / Vue 3 / Vuetify (SPA) | Runs locally (`npm run dev` → http://localhost:3000) |
| `website/` | Company website | _TBD_ | Planned |
| `Ai1/` | Company AI project | _TBD_ | Scaffold |
| `api/` | 1MPRO backend API (the server `backoffice` talks to). Clone of [thanaautho/1mpro_api_v3](https://github.com/thanaautho/1mpro_api_v3). | Fastify + Prisma (MySQL) + zod + JWT, TypeScript | Installed; boots on `:8080`, needs MySQL to be functional |

> `backoffice/` and `api/` are each their own git repo (own remote); they are not tracked inside this root repo.
>
> **api backend setup:** `npm install` → `npx prisma generate` → copy `.env.example` to `.env` and set a real `DATABASE_URL` (MySQL). Dev: `npm run dev` (port 8080), Swagger at `/docs`. Boots without a DB (Prisma connects lazily; Bull/Redis is currently commented out in `src/app.ts`), but any DB-backed endpoint 500s until MySQL is reachable. Runs on Node 24. Read `api/CLAUDE.md` / `api/AGENTS.md` before editing (keep them in sync); DB access only via `src/utils/prisma.ts`; ~1,200 pre-existing type errors under strict, dev runs `--transpile-only`.
>
**Backoffice local setup (required to run):**
> 1. `oneMFunction/config.ts` is **gitignored** (only the `config_DF.ts` template ships). Copy it: `cp oneMFunction/config_DF.ts oneMFunction/config.ts`. 45 files import `~~/oneMFunction/config`; without it the whole app fails to load config (API base `urlApi()` → `https://test.1mpro.com`).
> 2. `backoffice/.env` (gitignored) with `VITE_API_URL=https://test.1mpro.com` — used by `utils/helpers/fetch-wrapper.ts` to attach the Bearer auth header.
> 3. Windows-only: removed the Linux-only `@esbuild/linux-x64` pin from `package.json` (do NOT push upstream — Linux shared-hosting build needs it).
>
> **Vue version note:** repo ships no lockfile, so `npm install` resolves `vue@^3.3.4` → 3.5.x. Vue 3.4+ makes `v-model` on a `const` a hard compile error; the dev scratch pages `cherryBtn.vue` / `cherryBtnAction.vue` / `cherryGraph.vue` used that pattern, so those consts were wrapped in `ref()`. Do not downgrade Vue to 3.3.x — the rest of the freshly-installed tree needs 3.4+ compiler APIs (`extractRuntimeEmits`).
