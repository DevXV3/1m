// Replay the leaked production payload (typo'd close + two single-question markers)
// and verify the v0.7.1 pipeline: no raw marker, merged 2-question stepper,
// "อื่นๆ (พิมพ์เอง)" free-text option, REVIEW step (no auto-submit), single turn.
// Run: node ask_real_check.js <adminEmail> <adminPw>
const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:3000';
const [email, password] = process.argv.slice(2);
const DIR = process.env.OUTDIR || __dirname + '/runs';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 950 } });
  let fail = 0, completions = 0;
  page.on('request', (r) => {
    if (r.url().includes('/api/chat/completions') && r.method() === 'POST') completions++;
  });
  const log = (...a) => console.log('[real]', ...a);
  try {
    await page.goto(`${BASE}/auth`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(4000);
    for (let i = 0; i < 4; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(200); }
    await page.goto(`${BASE}/?models=spike_real`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2500);
    for (let i = 0; i < 3; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(200); }
    const input = page.locator('#chat-input, div[contenteditable="true"], textarea').last();
    await input.click();
    await page.keyboard.type('เริ่ม');
    await page.keyboard.press('Enter');
    log('sent, waiting for stepper…');

    let root = null;
    for (let a = 0; a < 20 && !root; a++) {
      await page.waitForTimeout(1500);
      const r = page.locator('[data-pzset-root]');
      if (await r.count().catch(() => 0)) root = r.last();
    }
    let body = await page.evaluate(() => document.body.innerText);
    console.log('stepper           :', !!root);
    console.log('raw_marker_leaked :', /\[\[\/?PINGZY_A?ASK\]\]/.test(body));
    console.log('merged_1of2       :', body.includes('ข้อ 1/2'));
    console.log('other_option      :', body.includes('อื่นๆ (พิมพ์เอง)'));
    if (!root) throw new Error('stepper not found');
    const before = completions;

    // Q1: pick a province -> should advance to Q2, NOT submit
    await root.locator('button', { hasText: 'ศรีสะเกษ' }).first().click();
    await page.waitForTimeout(700);
    body = await page.evaluate(() => document.body.innerText);
    console.log('q2_advanced       :', body.includes('ข้อ 2/2'), '| turns:', completions - before, '(must be 0)');

    // Q2: use "อื่นๆ (พิมพ์เอง)" instead of the listed options
    await root.locator('button', { hasText: 'อื่นๆ (พิมพ์เอง)' }).first().click();
    await page.waitForTimeout(400);
    await root.locator('input').fill('โอนก่อนส่งของ 50%');
    await page.waitForTimeout(300);
    await root.locator('button', { hasText: 'ถัดไป' }).click();
    await page.waitForTimeout(700);

    // REVIEW step: nothing sent yet; both answers listed; submit is the only send
    body = await page.evaluate(() => document.body.innerText);
    const review = body.includes('สรุปคำตอบ');
    console.log('review_step       :', review, '| turns:', completions - before, '(must be 0)');
    console.log('review_shows_q1   :', body.includes('สถานที่ส่ง: ศรีสะเกษ'));
    console.log('review_shows_q2   :', body.includes('ช่องทางชำระเงิน: โอนก่อนส่งของ 50%'));
    await page.screenshot({ path: `${DIR}/askreal_review.png`, fullPage: true });

    await root.locator('button', { hasText: 'ส่งคำตอบ' }).click();
    await page.waitForTimeout(10000);
    const after = await page.evaluate(() => document.body.innerText);
    const oneTurn = after.includes('สถานที่ส่ง: ศรีสะเกษ') && after.includes('ช่องทางชำระเงิน: โอนก่อนส่งของ 50%');
    const echoed = after.includes('REAL_ANSWER:');
    console.log('combined_answer   :', oneTurn, '| echoed:', echoed, '| total_turns:', completions - before, '(must be 1)');
    await page.screenshot({ path: `${DIR}/askreal_after.png`, fullPage: true });
    if (/\[\[\/?PINGZY_A?ASK\]\]/.test(body) || !review || !oneTurn || !echoed ||
        completions - before !== 1) fail = 1;
  } catch (e) {
    console.error('[real] ERROR:', e.message);
    try { await page.screenshot({ path: `${DIR}/askreal_err.png`, fullPage: true }); } catch {}
    fail = 1;
  } finally {
    await browser.close();
  }
  console.log(fail ? '[real] FAIL' : '[real] PASS');
  process.exitCode = fail;
})();
