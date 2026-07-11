// PingZy WebUI e2e — report tool + dashboard embed (sales pilot).
// Scenario A: ask for a report -> model calls onem_report.get_report -> chart artifact
// Scenario B: ask to open the dashboard -> [[PINGZY_DASH]] -> iframe wrapper artifact
// Run: node onem_report_e2e.js <email> <password> [scenario A|B|AB]
const { chromium } = require('playwright');

const BASE = 'http://127.0.0.1:3000';
const MODEL = process.env.MODEL || 'pingzy-sales';
const [email, password, which = 'AB'] = process.argv.slice(2);
const OUTDIR = process.env.OUTDIR || __dirname + '/runs';

async function findInput(page) {
  for (const sel of ['#chat-input', 'div[contenteditable="true"]', 'textarea']) {
    const el = page.locator(sel).last();
    if (await el.count().catch(() => 0)) {
      try { await el.waitFor({ state: 'visible', timeout: 4000 }); return el; } catch {}
    }
  }
  return null;
}

async function settle(page, ms = 240000) {
  // wait for the response to finish: some growth observed AND stable for 4 polls,
  // with a minimum elapsed time (tool call + generation can idle before output).
  let base = (await page.evaluate(() => document.body.innerText.length)) || 0;
  let prev = base, stable = 0, grew = false, t0 = Date.now();
  while (Date.now() - t0 < ms) {
    await page.waitForTimeout(3000);
    const len = (await page.evaluate(() => document.body.innerText.length)) || 0;
    if (len > prev) { grew = true; stable = 0; }
    else if (grew && Date.now() - t0 > 30000) { stable++; }
    if (grew && stable >= 4) break;
    prev = len;
  }
  return ((Date.now() - t0) / 1000).toFixed(0);
}

async function ask(page, q) {
  await page.goto(`${BASE}/?models=${encodeURIComponent(MODEL)}`,
    { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2500);
  const input = await findInput(page);
  if (!input) throw new Error('chat input not found');
  await input.click();
  await page.keyboard.type(q, { delay: 8 });
  await page.waitForTimeout(300);
  await page.keyboard.press('Enter');
  console.log('[e2e] sent:', q, '— settled after', await settle(page), 's');
}

function frameStats(page) {
  return {
    frames: page.frames().map(f => (f.url() || '').slice(0, 120)),
    count: page.frames().length,
  };
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const log = (...a) => console.log('[e2e]', ...a);
  let fail = 0;
  try {
    page.on('request', (req) => {
      if (req.url().includes('/api/chat/completions') && req.method() === 'POST') {
        try {
          const b = JSON.parse(req.postData() || '{}');
          console.log('[req] chat/completions tool_ids:', JSON.stringify(b.tool_ids),
            'model:', b.model, 'msg:', String((b.messages || []).slice(-1)[0]?.content || '').slice(0, 60));
        } catch {}
      }
    });
    log('login', email);
    await page.goto(`${BASE}/auth`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(4000);

    if (which.includes('A')) {
      log('--- scenario A: in-chat report chart ---');
      await ask(page, 'ขอรายงานยอดขายรายวัน แสดงเป็นกราฟ');
      // the model may first ask a clarifying question via follow-up chips (wizard) —
      // click the first chip and let it continue (max 2 rounds)
      let chartFrame = false, chartTitle = '';
      for (let round = 0; round < 3; round++) {
        for (const f of page.frames()) {
          try {
            if (await f.locator('#pz-chart').count()) {
              chartTitle = await f.locator('#pz-chart h3').first().innerText().catch(() => '');
              // an empty spec renders the widget with no <h3> — only count a titled chart
              chartFrame = !!chartTitle.trim();
              break;
            }
          } catch {}
        }
        if (chartFrame || round === 2) break;
        const chip = page.locator('button', { hasText: /ย้อนหลัง|วัน|เดือน/ }).first();
        if (!(await chip.count().catch(() => 0))) break;
        log('clicking follow-up chip:', (await chip.innerText().catch(() => '?')).trim());
        await chip.click();
        console.log('[e2e] chip round settled after', await settle(page), 's');
      }
      const body = await page.evaluate(() => document.body.innerText);
      const rawMarker = body.includes('[[PINGZY_CHART]]');
      const fs = frameStats(page);
      console.log('A.raw_marker_leak :', rawMarker);
      console.log('A.chart_widget    :', chartFrame, chartTitle ? `(title: ${chartTitle})` : '');
      console.log('A.frames          :', fs.count);
      await page.screenshot({ path: `${OUTDIR}/report_chart.png`, fullPage: true });
      log('screenshot ->', `${OUTDIR}/report_chart.png`);
      if (rawMarker || !chartFrame) fail = 1;
    }

    if (which.includes('B')) {
      log('--- scenario B: dashboard embed ---');
      await ask(page, process.env.DASH_Q || 'เปิดแดชบอร์ดของแผนกให้หน่อย');
      const body = await page.evaluate(() => document.body.innerText);
      const rawMarker = body.includes('[[PINGZY_DASH]]');
      const hasLink = body.includes('เปิดแดชบอร์ดในแท็บใหม่');
      let dashWrapper = false, innerSrc = '';
      for (const f of page.frames()) {
        try {
          if (await f.locator('#pz-dash').count()) {
            dashWrapper = true;
            innerSrc = await f.locator('#pz-dash-frame').getAttribute('src').catch(() => '');
            break;
          }
        } catch {}
      }
      // the inner embed page loads async — poll for its frame before asserting
      let innerLoaded = false;
      for (let i = 0; i < 10 && !innerLoaded; i++) {
        innerLoaded = page.frames().some(f => (f.url() || '').includes('/embed/dashboard/'));
        if (!innerLoaded) await page.waitForTimeout(1500);
      }
      console.log('B.raw_marker_leak :', rawMarker);
      console.log('B.open_tab_link   :', hasLink);
      console.log('B.dash_wrapper    :', dashWrapper, innerSrc ? `(src: ${innerSrc.slice(0, 90)}...)` : '');
      console.log('B.inner_embed_up  :', innerLoaded);
      await page.waitForTimeout(3000); // let the inner embed render charts
      await page.screenshot({ path: `${OUTDIR}/report_dash.png`, fullPage: true });
      log('screenshot ->', `${OUTDIR}/report_dash.png`);
      if (rawMarker || !dashWrapper || !innerLoaded) fail = 1;
    }
  } catch (e) {
    console.error('[e2e] ERROR:', e.message);
    try { await page.screenshot({ path: `${OUTDIR}/report_error.png`, fullPage: true }); } catch {}
    fail = 1;
  } finally {
    await browser.close();
  }
  process.exitCode = fail;
  console.log(fail ? '[e2e] FAIL' : '[e2e] PASS');
})();
