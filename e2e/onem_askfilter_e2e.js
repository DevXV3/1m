// e2e: real model emits [[PINGZY_ASK]] marker → global filter → picker widget → click → answer submitted.
// Run: node onem_askfilter_e2e.js <email> <FROM_SETUP|pw> <modelId> <label>
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = 'http://127.0.0.1:3000';
let [email, password, modelId, label] = process.argv.slice(2);
if (password === 'FROM_SETUP') {
  const src = fs.readFileSync('C:/Users/AiMiniX/open-webui/setup_rag_channels.py', 'utf8');
  password = (src.match(/ADMIN_PASSWORD\s*=\s*"([^"]+)"/) || [])[1];
}
label = label || modelId;
const DIR = 'C:/Users/AiMiniX/AppData/Local/Temp/claude/C--Users-AiMiniX/962c19a7-f6e5-4098-931c-e1e4d48bf058/scratchpad';

const spec = { question: "เลือกฐานข้อมูลสำหรับโปรเจค?", header: "Database", options: ["Postgres", "SQLite", "MySQL"] };
const marker = "[[PINGZY_ASK]]" + JSON.stringify(spec) + "[[/PINGZY_ASK]]";
const msg = "ตอบกลับด้วยข้อความต่อไปนี้เป๊ะ ๆ ทั้งบรรทัด ห้ามเพิ่มหรือแก้ไขอะไรเลย: " + marker;

async function findFrame(page) {
  for (const f of page.frames()) { try { if (await f.locator('#pz-ask').count()) return f; } catch {} }
  return null;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 950 } });
  const log = (...a) => console.log(`[${label}]`, ...a);
  try {
    await page.goto(`${BASE}/auth`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(4000);
    for (let i = 0; i < 4; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(250); }
    await page.goto(`${BASE}/?models=${encodeURIComponent(modelId)}`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2500);
    for (let i = 0; i < 3; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(250); }

    let input = null;
    for (const sel of ['#chat-input', 'div[contenteditable="true"]', 'textarea']) {
      const el = page.locator(sel).last();
      if (await el.count().catch(() => 0)) { try { await el.waitFor({ state: 'visible', timeout: 4000 }); input = el; break; } catch {} }
    }
    await input.click();
    await page.keyboard.type(msg, { delay: 3 });
    await page.keyboard.press('Enter');
    log('sent echo-marker instruction, waiting for model + filter…');
    await page.waitForTimeout(14000);

    let frame = await findFrame(page);
    for (let a = 0; a < 6 && !frame; a++) {
      for (const t of ['Preview', 'พรีวิว']) { const b = page.getByText(t, { exact: true }).last(); if (await b.count().catch(() => 0)) { try { await b.click({ timeout: 2000 }); } catch {} } }
      await page.waitForTimeout(2500); frame = await findFrame(page);
    }
    const rawMarkerVisible = (await page.evaluate(() => document.body.innerText)).includes('[[PINGZY_ASK]]');
    await page.screenshot({ path: `${DIR}/askfilter_${label}_widget.png`, fullPage: true });
    console.log(`\n===== ${label} =====`);
    console.log('widget_frame_found  :', !!frame);
    console.log('raw_marker_leaked   :', rawMarkerVisible, '(ต้องเป็น false = filter ซ่อน marker)');
    if (!frame) { console.log('!! widget not rendered'); return; }

    const opts = await frame.locator('.opt').count();
    const header = await frame.locator('.chip').first().textContent().catch(() => '');
    console.log('options_rendered    :', opts, '| header_chip:', JSON.stringify(header));
    // single-select → click "Postgres" → immediate submit
    await frame.locator('.opt').first().click();
    log('clicked Postgres (single-select → submit)');
    await page.waitForTimeout(9000);
    await page.screenshot({ path: `${DIR}/askfilter_${label}_after.png`, fullPage: true });
    const body = await page.evaluate(() => document.body.innerText);
    console.log('answer_submitted    :', /(^|\n)\s*Postgres\s*($|\n)/.test(body) || body.includes('\nPostgres'));
    console.log('----- tail -----\n' + body.slice(-350));
  } catch (e) {
    console.error(`[${label}] ERROR:`, e.message);
    try { await page.screenshot({ path: `${DIR}/askfilter_${label}_error.png`, fullPage: true }); } catch {}
    process.exitCode = 1;
  } finally { await browser.close(); }
})();
