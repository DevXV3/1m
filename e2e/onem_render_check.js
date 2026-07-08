// Minimal: send trivial msg to a model, check if the #pz-ask widget renders (outlet filter worked).
// Run: node onem_render_check.js <email> <FROM_SETUP|pw> <modelId> <label> [clickSubmit]
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = 'http://127.0.0.1:3000';
let [email, password, modelId, label, clickSubmit] = process.argv.slice(2);
if (password === 'FROM_SETUP') {
  const src = fs.readFileSync('C:/Users/AiMiniX/open-webui/setup_rag_channels.py', 'utf8');
  password = (src.match(/ADMIN_PASSWORD\s*=\s*"([^"]+)"/) || [])[1];
}
label = label || modelId;
const DIR = 'C:/Users/AiMiniX/AppData/Local/Temp/claude/C--Users-AiMiniX/962c19a7-f6e5-4098-931c-e1e4d48bf058/scratchpad';
const frameOf = async (page) => { for (const f of page.frames()) { try { if (await f.locator('#pz-ask').count()) return f; } catch {} } return null; };

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 950 } });
  const log = (...a) => console.log(`[${label}]`, ...a);
  try {
    if (process.env.THEME) {
      await page.addInitScript((t) => { try { localStorage.setItem('theme', t); } catch {} }, process.env.THEME);
    }
    await page.goto(`${BASE}/auth`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.fill('input[type="email"]', email); await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]'); await page.waitForTimeout(4000);
    for (let i = 0; i < 4; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(250); }
    await page.goto(`${BASE}/?models=${encodeURIComponent(modelId)}`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2500);
    for (let i = 0; i < 3; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(250); }
    let input = null;
    for (const sel of ['#chat-input', 'div[contenteditable="true"]', 'textarea']) {
      const el = page.locator(sel).last();
      if (await el.count().catch(() => 0)) { try { await el.waitFor({ state: 'visible', timeout: 4000 }); input = el; break; } catch {} }
    }
    await input.click(); await page.keyboard.type(process.env.MSG || 'เริ่ม'); await page.keyboard.press('Enter');
    log('sent, waiting…'); await page.waitForTimeout(35000);
    let frame = await frameOf(page);
    for (let a = 0; a < 6 && !frame; a++) {
      for (const t of ['Preview', 'พรีวิว']) { const b = page.getByText(t, { exact: true }).last(); if (await b.count().catch(() => 0)) { try { await b.click({ timeout: 2000 }); } catch {} } }
      await page.waitForTimeout(2500); frame = await frameOf(page);
    }
    const body1 = await page.evaluate(() => document.body.innerText);
    await page.screenshot({ path: `${DIR}/render_${label}.png`, fullPage: true });
    console.log(`\n===== ${label} =====`);
    console.log('widget_rendered   :', !!frame);
    console.log('raw_marker_leaked :', body1.includes('[[PINGZY_ASK]]'));
    if (frame) {
      console.log('options           :', await frame.locator('.opt').count(), '| header:', JSON.stringify(await frame.locator('.chip').first().textContent().catch(() => '')));
      if (clickSubmit) {
        const picked = (await frame.locator('.opt .l').first().textContent() || '').trim();
        await frame.locator('.opt').first().click(); log('clicked option:', picked.slice(0, 50));
        await page.waitForTimeout(1200);
        // multi/wizard: press the explicit submit button if it exists
        const sb = frame.locator('button.submit');
        if (await sb.count().catch(() => 0)) { await sb.click().catch(() => {}); log('clicked ส่งคำตอบ'); }
        await page.waitForTimeout(3000);
        const sentTag = await frame.locator('.sent-tag').isVisible().catch(() => false);
        console.log('postMessage_fired :', sentTag, '(.sent-tag visible)');
        await page.waitForTimeout(15000);  // let OWUI submit + persist + Claude start replying
        await page.screenshot({ path: `${DIR}/render_${label}_after.png`, fullPage: true });
      }
    }
  } catch (e) { console.error(`[${label}] ERROR:`, e.message); try { await page.screenshot({ path: `${DIR}/render_${label}_err.png`, fullPage: true }); } catch {} process.exitCode = 1; }
  finally { await browser.close(); }
})();
