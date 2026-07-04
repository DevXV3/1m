# one-m E2E — full-system test & action logger

Drives the **web** (Nuxt, `:3000`) and **api** (Fastify, `:8080`) and records **every action**
of a run into `runs/<timestamp>_<scenario>/`:

| file | what |
|------|------|
| `actions.jsonl` | each UI step (start / ok / failed, duration, screenshot) |
| `network.jsonl` | every request+response; `isApi:true` flags web↔api calls (with bodies) |
| `console.jsonl` | browser console messages + page errors |
| `report.md` | human-readable timeline: UI actions + api calls interleaved |
| `summary.json` | counts + pass/fail |
| `screenshots/` | one per UI step |
| `trace.zip` | Playwright trace — open with `npx playwright show-trace <file>` |
| `api-server.log` | snapshot of the api's stdout during the run (for correlation) |

## Prereqs
- web running: `cd ../backoffice/web && npm run dev` → http://localhost:3000
- api running: `cd ../backoffice/api && npm run dev` → http://localhost:8080
- one-time: `npm install` then `npx playwright install chromium`

## Run
```bash
npm run api        # api-smoke: hit backend directly, log every call+response
npm run login      # login-smoke: drive the web login flow
node run.js <scenario>
```

### Config (env vars)
| var | default |
|-----|---------|
| `WEB_URL` | http://localhost:3000 |
| `API_URL` | http://localhost:8080 |
| `E2E_USER` / `E2E_PASS` | _(empty)_ — set to exercise a real login |
| `E2E_HEADFUL` | unset (headless); set `1` to watch the browser |
| `API_LOG` | path to the api dev stdout log (snapshotted per run) |

Example authed run:
```bash
E2E_USER=someuser E2E_PASS=secret npm run login
```

## Add a scenario
Drop `scenarios/<name>.js` exporting `async ({ page, log, cfg, api, expect }) => { ... }`.
Wrap each user action in `await log.step('label', async () => { ... })` so it's logged +
screenshotted; browser network is captured automatically. For direct api calls use
`await log.apiDirect(method, url, res)`.
