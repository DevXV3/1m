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

> `backoffice/` is its own git repo (own remote); it is not tracked inside this root repo.
>
> Local-machine tweaks to run on Windows: removed the Linux-only `@esbuild/linux-x64` pin from `backoffice/package.json`, and added `backoffice/.env` with `VITE_API_URL=https://test.1mpro.com`. Do not push the package.json change upstream (it would remove the dep the Linux shared-hosting build relies on).
