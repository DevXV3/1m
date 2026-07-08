// Spike: prove OWUI renders an interactive select picker via __event_call__.
// Run: node onem_picker_spike.js <email> <password>
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = 'http://127.0.0.1:3000';
let [email, password] = process.argv.slice(2);
// avoid putting the admin password on the command line: read it from the existing
// setup script at runtime (not embedded anywhere new).
if (password === 'FROM_SETUP') {
  const src = fs.readFileSync('C:/Users/AiMiniX/open-webui/setup_rag_channels.py', 'utf8');
  password = (src.match(/ADMIN_PASSWORD\s*=\s*"([^"]+)"/) || [])[1];
  if (!password) throw new Error('could not read ADMIN_PASSWORD from setup script');
}
const DIR = 'C:/Users/AiMiniX/AppData/Local/Temp/claude/C--Users-AiMiniX/962c19a7-f6e5-4098-931c-e1e4d48bf058/scratchpad';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const log = (...a) => console.log('[spike]', ...a);
  try {
    await page.goto(`${BASE}/auth`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(4000);
    // dismiss admin "What's New"/changelog startup modal if present
    for (let i = 0; i < 4; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(300); }

    log('open spike_picker model');
    await page.goto(`${BASE}/?models=spike_picker`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2500);
    for (let i = 0; i < 3; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(300); }

    // send any message to trigger pipe()
    let input = null;
    for (const sel of ['#chat-input', 'div[contenteditable="true"]', 'textarea']) {
      const el = page.locator(sel).last();
      if (await el.count().catch(() => 0)) { try { await el.waitFor({ state: 'visible', timeout: 4000 }); input = el; break; } catch {} }
    }
    if (!input) throw new Error('chat input not found (model may be inaccessible)');
    await input.click();
    await page.keyboard.type('เริ่ม');
    await page.keyboard.press('Enter');
    log('message sent, waiting for picker dialog…');

    // the ConfirmDialog with a NativeSelect should appear
    await page.waitForSelector('select', { timeout: 30000 });
    log('✅ SELECT PICKER APPEARED');
    await page.screenshot({ path: `${DIR}/spike_picker_open.png`, fullPage: true });

    // read the options rendered
    const opts = await page.$$eval('select option', os => os.map(o => ({ v: o.value, t: o.textContent.trim() })));
    log('options rendered:', JSON.stringify(opts, null, 0));

    // pick the 2nd real option (material_shop)
    const pick = opts.find(o => o.v === 'material_shop') || opts[1] || opts[0];
    await page.selectOption('select', pick.v);
    log('selected:', pick.v);

    // click the confirm button in the dialog
    const btn = page.locator('button:has-text("Confirm"), button:has-text("ยืนยัน"), button:has-text("ตกลง"), button:has-text("OK"), button:has-text("Submit")').last();
    await btn.click({ timeout: 5000 }).catch(async () => { await page.keyboard.press('Enter'); });
    log('confirmed choice, waiting for model to receive it…');

    await page.waitForTimeout(6000);
    await page.screenshot({ path: `${DIR}/spike_picker_result.png`, fullPage: true });
    const body = await page.evaluate(() => document.body.innerText);
    console.log('\n===== RESULT MARKERS =====');
    console.log('picker_appeared     :', true);
    console.log('choice_reached_model:', /material_shop|picker ทำงาน|ค่าที่ผู้ใช้เลือก/.test(body));
    console.log('\n----- page tail -----\n' + body.slice(-600));
  } catch (e) {
    console.error('[spike] ERROR:', e.message);
    try { await page.screenshot({ path: `${DIR}/spike_picker_error.png`, fullPage: true }); } catch {}
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
