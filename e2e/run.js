// Full-system E2E runner: drives web + api, logs every action into runs/<timestamp>/.
// Usage: node run.js [scenario]   (default: login-smoke)   e.g. node run.js api-smoke
const fs = require('fs');
const path = require('path');
const { chromium, request } = require('playwright');
const cfg = require('./config');
const { SystemLogger } = require('./lib/logger');

function stamp() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

async function main() {
  const scenarioName = process.argv[2] || 'login-smoke';
  const scenarioPath = path.join(__dirname, 'scenarios', `${scenarioName}.js`);
  if (!fs.existsSync(scenarioPath)) {
    console.error(`scenario not found: ${scenarioName} (${scenarioPath})`);
    console.error('available:', fs.readdirSync(path.join(__dirname, 'scenarios')).map((f) => f.replace('.js', '')).join(', '));
    process.exit(2);
  }
  const scenario = require(scenarioPath);

  const runDir = path.join(__dirname, 'runs', `${stamp()}_${scenarioName}`);
  fs.mkdirSync(runDir, { recursive: true });
  console.log(`▶ scenario "${scenarioName}"  web=${cfg.WEB_URL} api=${cfg.API_URL}`);
  console.log(`  run dir: ${runDir}`);

  const browser = await chromium.launch({ headless: cfg.HEADLESS });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  await context.tracing.start({ screenshots: true, snapshots: true, sources: true });
  const page = await context.newPage();
  const log = new SystemLogger(page, { runDir, apiUrl: cfg.API_URL });

  // API request context (for direct api calls, logged into the same network stream via a light wrapper)
  const api = await request.newContext({ baseURL: cfg.API_URL, ignoreHTTPSErrors: true });

  let status = 'passed', note = null;
  try {
    await scenario({ page, log, cfg, api, expect: makeExpect() });
  } catch (e) {
    status = 'failed';
    note = e.message;
    console.error('✖ scenario error:', e.message);
  } finally {
    try { await context.tracing.stop({ path: path.join(runDir, 'trace.zip') }); } catch {}
    // snapshot api server log for correlation
    try {
      if (fs.existsSync(cfg.API_LOG)) {
        const buf = fs.readFileSync(cfg.API_LOG);
        fs.writeFileSync(path.join(runDir, 'api-server.log'), buf);
      }
    } catch {}
    await api.dispose().catch(() => {});
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
  }

  const summary = await log.finalize({ scenario: scenarioName, status, note });
  console.log(`\n■ ${status.toUpperCase()} — actions:${summary.counts.actions} apiCalls:${summary.counts.apiCalls} failedApi:${summary.counts.failedApi} errors:${summary.counts.errors}`);
  console.log(`  report: ${path.join(runDir, 'report.md')}`);
  console.log(`  trace : npx playwright show-trace "${path.join(runDir, 'trace.zip')}"`);
  process.exit(status === 'passed' ? 0 : 1);
}

// minimal assertion helper that records failures instead of throwing hard where possible
function makeExpect() {
  return (cond, msg) => { if (!cond) throw new Error('assertion failed: ' + msg); };
}

main().catch((e) => { console.error(e); process.exit(1); });
