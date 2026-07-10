// Anti-loop check: quote request -> answer the FULL set via the stepper ->
// the next assistant turn must NOT re-ask the set (no new stepper / "ขอข้อมูล"),
// it should proceed with the quote instead.
// Run: node ask_loop_check.js <email> <pw>
const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:3000';
const [email, password] = process.argv.slice(2);
const DIR = process.env.OUTDIR || __dirname + '/runs';

async function settleAssistant(page, ms = 240000) {
  let prev = 0, stable = 0, grew = false, t0 = Date.now();
  while (Date.now() - t0 < ms) {
    await page.waitForTimeout(3000);
    const len = (await page.evaluate(() => document.body.innerText.length)) || 0;
    if (len > prev) { grew = true; stable = 0; }
    else if (grew && Date.now() - t0 > 25000) stable++;
    if (grew && stable >= 4) break;
    prev = len;
  }
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 950 } });
  let fail = 0;
  const log = (...a) => console.log('[loop]', ...a);
  try {
    await page.goto(`${BASE}/auth`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(4000);
    for (let i = 0; i < 4; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(200); }
    await page.goto(`${BASE}/?models=pingzy-sales`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2500);
    for (let i = 0; i < 3; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(200); }
    const input = page.locator('#chat-input, div[contenteditable="true"], textarea').last();
    await input.click();
    await page.keyboard.type('ทำใบเสนอราคาเสารั้ว 2 เมตร 2 ไร่');
    await page.keyboard.press('Enter');
    log('sent quote request, waiting for the ask set…');

    let root = null;
    for (let a = 0; a < 30 && !root; a++) {
      await page.waitForTimeout(2000);
      const r = page.locator('[data-pzset-root]');
      if (await r.count().catch(() => 0)) root = r.last();
    }
    if (!root) throw new Error('stepper not found on first turn');
    const askCount1 = (await page.evaluate(() => document.body.innerText)).split('ขอข้อมูล').length - 1;
    log('stepper up, answering every question with the first option…');

    // walk the whole set: free-text -> type; single -> tap first; multi -> tap first + next
    for (let step = 0; step < 12; step++) {
      const bodyTxt = await page.evaluate(() => document.body.innerText);
      if (bodyTxt.includes('สรุปคำตอบ')) break;
      const inp = root.locator('input');
      if (await inp.count().catch(() => 0)) {
        await inp.fill('2 ไร่');
        await root.locator('button', { hasText: 'ถัดไป' }).click().catch(async () => {
          await root.locator('button', { hasText: 'ส่งคำตอบ' }).click().catch(() => {});
        });
      } else {
        const opt = root.locator('button', { hasText: /[○☐]/ }).first();
        if (!(await opt.count().catch(() => 0))) break;
        await opt.click();
        const next = root.locator('button', { hasText: 'ถัดไป' });
        if (await next.count().catch(() => 0)) await next.click().catch(() => {});
      }
      await page.waitForTimeout(500);
    }
    const reviewTxt = await page.evaluate(() => document.body.innerText);
    log('review reached:', reviewTxt.includes('สรุปคำตอบ'));
    await root.locator('button', { hasText: 'ส่งคำตอบ' }).click();
    log('answers submitted — waiting for the follow-up assistant turn…');
    await settleAssistant(page);

    const after = await page.evaluate(() => document.body.innerText);
    const askCount2 = after.split('ขอข้อมูล').length - 1;
    const steppers = await page.locator('[data-pzset-root]').count();
    const reasked = askCount2 > askCount1 || steppers > 1;
    const quoteish = /ใบเสนอราคา|ราคา|บาท|รวม/.test(after.slice(-1500));
    console.log('ask_sets_before   :', askCount1, '| after:', askCount2);
    console.log('steppers_on_page  :', steppers, '(must stay 1)');
    console.log('re_asked          :', reasked, '(must be false)');
    console.log('quote_content     :', quoteish);
    await page.screenshot({ path: `${DIR}/ask_loop.png`, fullPage: true });
    log('screenshot ->', `${DIR}/ask_loop.png`);
    if (reasked || !quoteish) fail = 1;
  } catch (e) {
    console.error('[loop] ERROR:', e.message);
    try { await page.screenshot({ path: `${DIR}/ask_loop_err.png`, fullPage: true }); } catch {}
    fail = 1;
  } finally {
    await browser.close();
  }
  console.log(fail ? '[loop] FAIL' : '[loop] PASS');
  process.exitCode = fail;
})();
