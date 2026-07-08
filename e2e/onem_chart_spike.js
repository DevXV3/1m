// Spike: prove OWUI renders a self-contained interactive HTML chart as an artifact.
// Run: node onem_chart_spike.js <email> <FROM_SETUP|password>
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = 'http://127.0.0.1:3000';
let [email, password] = process.argv.slice(2);
if (password === 'FROM_SETUP') {
  const src = fs.readFileSync('C:/Users/AiMiniX/open-webui/setup_rag_channels.py', 'utf8');
  password = (src.match(/ADMIN_PASSWORD\s*=\s*"([^"]+)"/) || [])[1];
}
const DIR = 'C:/Users/AiMiniX/AppData/Local/Temp/claude/C--Users-AiMiniX/962c19a7-f6e5-4098-931c-e1e4d48bf058/scratchpad';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 950 } });
  const log = (...a) => console.log('[chart]', ...a);
  try {
    await page.goto(`${BASE}/auth`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(4000);
    for (let i = 0; i < 4; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(300); }

    await page.goto(`${BASE}/?models=spike_chart`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2500);
    for (let i = 0; i < 3; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(300); }

    let input = null;
    for (const sel of ['#chat-input', 'div[contenteditable="true"]', 'textarea']) {
      const el = page.locator(sel).last();
      if (await el.count().catch(() => 0)) { try { await el.waitFor({ state: 'visible', timeout: 4000 }); input = el; break; } catch {} }
    }
    await input.click();
    await page.keyboard.type('แสดง dashboard');
    await page.keyboard.press('Enter');
    log('sent, waiting for artifact…');
    await page.waitForTimeout(9000);

    // switch the artifact from Code view to Preview (rendered) — it's a text toggle
    for (const t of ['Preview', 'พรีวิว']) {
      const b = page.getByText(t, { exact: true }).last();
      if (await b.count().catch(() => 0)) { try { await b.click({ timeout: 3000 }); log('clicked Preview'); break; } catch {} }
    }
    await page.waitForTimeout(4000);

    const frames = page.frames();
    log('frames on page:', frames.length);
    await page.screenshot({ path: `${DIR}/chart_open.png`, fullPage: true });

    // find the frame that contains our chart and prove interactivity (toggle a legend series)
    let chartFrame = null;
    for (const f of frames) {
      try { if (await f.locator('#onem-chart').count()) { chartFrame = f; break; } } catch {}
    }
    console.log('\n===== RESULT =====');
    console.log('artifact_iframe_found:', !!chartFrame);
    if (chartFrame) {
      const bars = await chartFrame.locator('rect.bar').count();
      const legends = await chartFrame.locator('.legend span').count();
      console.log('bars_rendered   :', bars, '| legend_series:', legends);
      // toggle 3rd series off to prove interactivity
      await chartFrame.locator('.legend span').nth(2).click().catch(() => {});
      await page.waitForTimeout(800);
      const barsAfter = await chartFrame.locator('rect.bar').count();
      console.log('bars_after_toggle:', barsAfter, '(น้อยลง = legend toggle ทำงาน)');
      await page.screenshot({ path: `${DIR}/chart_interact.png`, fullPage: true });
    }
  } catch (e) {
    console.error('[chart] ERROR:', e.message);
    try { await page.screenshot({ path: `${DIR}/chart_error.png`, fullPage: true }); } catch {}
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
