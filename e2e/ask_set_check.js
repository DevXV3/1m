// Chips-SET (CLI-style) check — loader.js takeover of follow-up chips.
// A: spike_multi  -> multi question: toggle 2 options (no turn fired), submit once -> "pytest, unittest"
// B: spike_wizard -> 2 questions: answer Q1 (single tap, local advance, NO model call),
//                    toggle 2 CI options, submit -> "Lang: Python\nCI: GitHub Actions, GitLab"
// Run: node ask_set_check.js <adminEmail> <adminPw> [A|B|AB]
const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:3000';
const [email, password, which = 'AB'] = process.argv.slice(2);
const DIR = process.env.OUTDIR || __dirname + '/runs';

async function login(page) {
  await page.goto(`${BASE}/auth`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(4000);
  for (let i = 0; i < 4; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(200); }
}

async function openModel(page, model) {
  await page.goto(`${BASE}/?models=${model}`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2500);
  for (let i = 0; i < 3; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(200); }
  const input = page.locator('#chat-input, div[contenteditable="true"], textarea').last();
  await input.click();
  await page.keyboard.type('เริ่ม');
  await page.keyboard.press('Enter');
}

async function waitStepper(page) {
  for (let a = 0; a < 20; a++) {
    const root = page.locator('[data-pzset-root]');
    if (await root.count().catch(() => 0)) return root.last();
    await page.waitForTimeout(1500);
  }
  return null;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 950 } });
  let fail = 0;
  let completions = 0;
  page.on('request', (r) => {
    if (r.url().includes('/api/chat/completions') && r.method() === 'POST') completions++;
  });
  const log = (...a) => console.log('[set]', ...a);
  try {
    await login(page);

    if (which.includes('A')) {
      log('--- A: multi toggle + single submit ---');
      await openModel(page, 'spike_multi');
      const root = await waitStepper(page);
      const body0 = await page.evaluate(() => document.body.innerText);
      console.log('A.stepper         :', !!root);
      console.log('A.sentinel_hidden :', !body0.includes('PZSET'));
      console.log('A.progress_line   :', body0.includes('ข้อ 1/1'));
      if (!root) throw new Error('stepper not found (A)');
      const before = completions;
      await root.locator('button', { hasText: 'pytest' }).first().click();
      await page.waitForTimeout(400);
      await root.locator('button', { hasText: 'unittest' }).first().click();
      await page.waitForTimeout(600);
      const checked = await root.locator('button', { hasText: '☑' }).count();
      console.log('A.checked         :', checked, '| turns_during_pick:', completions - before, '(must be 0)');
      await root.locator('button', { hasText: 'ส่งคำตอบ' }).click();
      await page.waitForTimeout(10000);
      const after = await page.evaluate(() => document.body.innerText);
      const oneTurn = after.includes('pytest, unittest');
      const echoed = after.includes('ANSWER_RECEIVED: pytest, unittest');
      console.log('A.answer_one_turn :', oneTurn, '| echoed:', echoed);
      await page.screenshot({ path: `${DIR}/askset_multi.png`, fullPage: true });
      if (checked !== 2 || completions - before !== 1 || !oneTurn || !echoed) fail = 1;
    }

    if (which.includes('B')) {
      log('--- B: 2-question wizard, local advance ---');
      await openModel(page, 'spike_wizard');
      const root = await waitStepper(page);
      console.log('B.stepper         :', !!root);
      if (!root) throw new Error('stepper not found (B)');
      let body = await page.evaluate(() => document.body.innerText);
      console.log('B.q1_progress     :', body.includes('ข้อ 1/2'));
      const before = completions;
      await root.locator('button', { hasText: 'Python' }).first().click(); // single -> auto advance
      await page.waitForTimeout(800);
      body = await page.evaluate(() => document.body.innerText);
      const advanced = body.includes('ข้อ 2/2');
      console.log('B.q2_advanced     :', advanced, '| turns_so_far:', completions - before, '(must be 0)');
      await root.locator('button', { hasText: 'GitHub Actions' }).first().click();
      await page.waitForTimeout(300);
      await root.locator('button', { hasText: 'GitLab' }).first().click();
      await page.waitForTimeout(500);
      const backOk = await root.locator('button', { hasText: 'ย้อนกลับ' }).count();
      console.log('B.back_button     :', backOk > 0);
      await root.locator('button', { hasText: 'ส่งคำตอบ' }).click();
      await page.waitForTimeout(10000);
      const after = await page.evaluate(() => document.body.innerText);
      const combined = after.includes('Lang: Python') && after.includes('CI: GitHub Actions, GitLab');
      const echoed = after.includes('WIZARD_ANSWER:');
      console.log('B.combined_answer :', combined, '| echoed:', echoed,
        '| total_turns:', completions - before, '(must be 1)');
      await page.screenshot({ path: `${DIR}/askset_wizard.png`, fullPage: true });
      if (!advanced || !combined || !echoed || completions - before !== 1) fail = 1;
    }
  } catch (e) {
    console.error('[set] ERROR:', e.message);
    try { await page.screenshot({ path: `${DIR}/askset_err.png`, fullPage: true }); } catch {}
    fail = 1;
  } finally {
    await browser.close();
  }
  console.log(fail ? '[set] FAIL' : '[set] PASS');
  process.exitCode = fail;
})();
