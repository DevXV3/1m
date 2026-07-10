// Hybrid multi-select ask check: spike_multi pipe emits a multi:true marker ->
// expect the checkbox-card widget (NOT chips), pick 2 options, press submit,
// assert the answer lands as ONE user turn "pytest, unittest" and the pipe echoes it.
// Run: node ask_multi_check.js <adminEmail> <adminPw>
const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:3000';
const [email, password] = process.argv.slice(2);
const DIR = process.env.OUTDIR || __dirname + '/runs';

const frameOf = async (page) => {
  for (const f of page.frames()) { try { if (await f.locator('#pz-ask').count()) return f; } catch {} }
  return null;
};

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 950 } });
  let fail = 0;
  const log = (...a) => console.log('[multi]', ...a);
  try {
    await page.goto(`${BASE}/auth`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(4000);
    for (let i = 0; i < 4; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(250); }

    await page.goto(`${BASE}/?models=spike_multi`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2500);
    for (let i = 0; i < 3; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(250); }
    const input = page.locator('#chat-input, div[contenteditable="true"], textarea').last();
    await input.click();
    await page.keyboard.type('เริ่ม');
    await page.keyboard.press('Enter');
    log('sent, waiting for widget…');

    let frame = null;
    for (let a = 0; a < 15 && !frame; a++) { await page.waitForTimeout(2000); frame = await frameOf(page); }
    const body = await page.evaluate(() => document.body.innerText);
    const chipsShown = /Follow up/i.test(body);
    console.log('widget_rendered   :', !!frame);
    console.log('raw_marker_leaked :', body.includes('[[PINGZY_ASK]]'));
    console.log('chips_emitted     :', chipsShown, '(must be false for multi)');
    if (!frame) throw new Error('widget frame not found');

    const optCount = await frame.locator('.opt').count();
    const isMulti = await frame.locator('.opt.multi').count();
    console.log('options           :', optCount, '| multi styling:', isMulti > 0);

    // pick pytest + unittest (accumulate — must NOT auto-submit)
    await frame.locator('.opt', { hasText: 'pytest' }).click();
    await page.waitForTimeout(400);
    await frame.locator('.opt', { hasText: 'unittest' }).click();
    await page.waitForTimeout(400);
    const selCount = await frame.locator('.opt.sel').count();
    const sentEarly = await frame.locator('#pz-ask.sent').count();
    console.log('selected_count    :', selCount, '| auto_submitted early:', sentEarly > 0, '(must be false)');

    const sb = frame.locator('button.submit');
    const enabled = await sb.isEnabled();
    console.log('submit_enabled    :', enabled);
    await sb.click();
    log('clicked ส่งคำตอบ, waiting for round-trip…');
    await page.waitForTimeout(12000);

    const after = await page.evaluate(() => document.body.innerText);
    const answerTurn = after.includes('pytest, unittest');
    const echoed = after.includes('ANSWER_RECEIVED: pytest, unittest');
    console.log('answer_user_turn  :', answerTurn, '("pytest, unittest" as one message)');
    console.log('pipe_echoed_back  :', echoed);
    await page.screenshot({ path: `${DIR}/ask_multi.png`, fullPage: true });
    log('screenshot ->', `${DIR}/ask_multi.png`);

    if (!frame || chipsShown || selCount !== 2 || sentEarly || !enabled || !answerTurn || !echoed) fail = 1;
  } catch (e) {
    console.error('[multi] ERROR:', e.message);
    try { await page.screenshot({ path: `${DIR}/ask_multi_err.png`, fullPage: true }); } catch {}
    fail = 1;
  } finally {
    await browser.close();
  }
  console.log(fail ? '[multi] FAIL' : '[multi] PASS');
  process.exitCode = fail;
})();
