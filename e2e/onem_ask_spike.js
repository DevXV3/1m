// Spike: prove an artifact BUTTON submits back into chat (unified picker via postMessage).
// Run: node onem_ask_spike.js <email> <FROM_SETUP|password>
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = 'http://127.0.0.1:3000';
let [email, password] = process.argv.slice(2);
if (password === 'FROM_SETUP') {
  const src = fs.readFileSync('C:/Users/AiMiniX/open-webui/setup_rag_channels.py', 'utf8');
  password = (src.match(/ADMIN_PASSWORD\s*=\s*"([^"]+)"/) || [])[1];
}
const DIR = 'C:/Users/AiMiniX/AppData/Local/Temp/claude/C--Users-AiMiniX/962c19a7-f6e5-4098-931c-e1e4d48bf058/scratchpad';

async function findWidgetFrame(page) {
  for (const f of page.frames()) {
    try { if (await f.locator('#ask').count()) return f; } catch {}
  }
  return null;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 950 } });
  const log = (...a) => console.log('[ask]', ...a);
  try {
    await page.goto(`${BASE}/auth`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(4000);
    for (let i = 0; i < 4; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(250); }

    await page.goto(`${BASE}/?models=spike_ask`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2500);
    for (let i = 0; i < 3; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(250); }

    let input = null;
    for (const sel of ['#chat-input', 'div[contenteditable="true"]', 'textarea']) {
      const el = page.locator(sel).last();
      if (await el.count().catch(() => 0)) { try { await el.waitFor({ state: 'visible', timeout: 4000 }); input = el; break; } catch {} }
    }
    await input.click();
    await page.keyboard.type('เริ่ม');
    await page.keyboard.press('Enter');
    log('sent, waiting for artifact widget…');
    await page.waitForTimeout(8000);

    // ensure artifact is in Preview so the widget iframe mounts; retry toggling
    let frame = await findWidgetFrame(page);
    for (let attempt = 0; attempt < 6 && !frame; attempt++) {
      for (const t of ['Preview', 'พรีวิว']) {
        const b = page.getByText(t, { exact: true }).last();
        if (await b.count().catch(() => 0)) { try { await b.click({ timeout: 2500 }); } catch {} }
      }
      await page.waitForTimeout(2500);
      frame = await findWidgetFrame(page);
      log(`attempt ${attempt}: frames=${page.frames().length} widget=${!!frame}`);
    }
    await page.screenshot({ path: `${DIR}/ask_widget_open.png`, fullPage: true });
    if (!frame) throw new Error('widget frame not found (artifact not in preview / not same-origin)');

    const btns = await frame.locator('button.opt').count();
    log('option buttons rendered:', btns);
    // click "ร้านค้าวัสดุ" (index 1)
    await frame.locator('button.opt').nth(1).click();
    log('clicked option button → should postMessage input:prompt:submit');
    await page.waitForTimeout(9000);
    await page.screenshot({ path: `${DIR}/ask_widget_after.png`, fullPage: true });

    const body = await page.evaluate(() => document.body.innerText);
    console.log('\n===== RESULT =====');
    console.log('option_buttons        :', btns);
    console.log('choice_submitted_asMsg:', /เลือกประเภทลูกค้า: ร้านค้าวัสดุ/.test(body));
    console.log('brain_received_choice :', /ปุ่ม→submit สำเร็จ|ได้รับตัวเลือก.*ร้านค้าวัสดุ/.test(body));
    console.log('\n----- page tail -----\n' + body.slice(-500));
  } catch (e) {
    console.error('[ask] ERROR:', e.message);
    try { await page.screenshot({ path: `${DIR}/ask_widget_error.png`, fullPage: true }); } catch {}
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
