// Dept-assistant QA battery — generic version of sales_battery.js: drives real
// conversations through the WebUI against any dept model. Cases come from a JSON
// file (same shape as sales_cases.json: q, must[], mustNot[], mustNotAsk, noReask,
// answers._freetext). If an ask-set stepper appears it answers every question and
// submits once. Empty response (known 0-token transient) retries once.
// Run: node dept_battery.js <email> <pw> <modelId> <casesFile> [caseId ...]
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = 'http://127.0.0.1:3000';
const [email, password, MODEL, casesFile, ...onlyIds] = process.argv.slice(2);
const DIR = process.env.OUTDIR || __dirname + '/runs';
const CASES = JSON.parse(fs.readFileSync(__dirname + '/' + casesFile, 'utf8'))
  .filter(c => !onlyIds.length || onlyIds.includes(c.id));
const GLOBAL_MUSTNOT = ['\\[\\[/?PINGZY', '<think>'];

async function settle(page, ms = 240000) {
  let prev = 0, stable = 0, grew = false, t0 = Date.now();
  while (Date.now() - t0 < ms) {
    await page.waitForTimeout(3000);
    const len = (await page.evaluate(() => document.body.innerText.length)) || 0;
    if (len > prev) { grew = true; stable = 0; }
    else if (grew && Date.now() - t0 > 25000) stable++;
    if (grew && stable >= 4) break;
    prev = len;
  }
  return grew;
}

async function walkStepper(page, root, kase) {
  for (let step = 0; step < 14; step++) {
    const txt = await page.evaluate(() => document.body.innerText);
    if (txt.includes('สรุปคำตอบ')) break;
    const inp = root.locator('input');
    if (await inp.count().catch(() => 0)) {
      await inp.fill((kase.answers && kase.answers._freetext) || 'ตามที่แจ้งไว้');
      const next = root.locator('button', { hasText: /ถัดไป|ส่งคำตอบ/ }).first();
      await next.click().catch(() => {});
    } else {
      const opt = root.locator('button', { hasText: /[○☐]/ }).first();
      if (!(await opt.count().catch(() => 0))) break;
      await opt.click();
      const next = root.locator('button', { hasText: 'ถัดไป' });
      if (await next.count().catch(() => 0)) await next.click().catch(() => {});
    }
    await page.waitForTimeout(500);
  }
  await root.locator('button', { hasText: 'ส่งคำตอบ' }).click().catch(() => {});
}

async function runCase(browser, kase, attempt) {
  const page = await browser.newPage({ viewport: { width: 1400, height: 950 } });
  const r = { id: kase.id, attempt, pass: true, asked: false, reasked: false,
              failures: [], empty: false };
  try {
    await page.goto(`${BASE}/auth`, { waitUntil: 'networkidle', timeout: 30000 });
    if (await page.locator('input[type="email"]').count().catch(() => 0)) {
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]', password);
      await page.click('button[type="submit"]');
      await page.waitForTimeout(4000);
    }
    for (let i = 0; i < 4; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(150); }
    await page.goto(`${BASE}/?models=${MODEL}`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2200);
    for (let i = 0; i < 3; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(150); }
    const input = page.locator('#chat-input, div[contenteditable="true"], textarea').last();
    await input.click();
    await page.keyboard.type(kase.q);
    await page.keyboard.press('Enter');
    await settle(page);

    let root = page.locator('[data-pzset-root]');
    if (await root.count().catch(() => 0)) {
      r.asked = true;
      root = root.last();
      await walkStepper(page, root, kase);
      await settle(page);
    }
    const body = await page.evaluate(() => document.body.innerText);
    const askSets = body.split('ขอข้อมูล').length - 1;
    const steppers = await page.locator('[data-pzset-root]').count();
    if (r.asked && (askSets > 1 || steppers > 1)) r.reasked = true;
    if (kase.noReask && r.reasked) { r.pass = false; r.failures.push('re-asked after answering'); }
    if (kase.mustNotAsk && r.asked) { r.pass = false; r.failures.push('asked a set for a factual question (should answer directly)'); }

    const tail = body.slice(-3500);
    if (!tail.replace(kase.q, '').trim() || body.length < kase.q.length + 120) r.empty = true;

    for (const m of kase.must || []) {
      if (!new RegExp(m).test(body)) { r.pass = false; r.failures.push(`missing: ${m}`); }
    }
    for (const m of [...(kase.mustNot || []), ...GLOBAL_MUSTNOT]) {
      if (new RegExp(m).test(body)) { r.pass = false; r.failures.push(`forbidden: ${m}`); }
    }
    await page.screenshot({ path: `${DIR}/dept_${MODEL}_${kase.id}.png`, fullPage: true });
    r.textTail = tail.slice(-900);
  } catch (e) {
    r.pass = false; r.failures.push('ERROR: ' + e.message);
    try { await page.screenshot({ path: `${DIR}/dept_${MODEL}_${kase.id}_err.png`, fullPage: true }); } catch {}
  } finally {
    await page.close();
  }
  return r;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const results = [];
  for (const kase of CASES) {
    console.log(`\n=== ${kase.id} — ${kase.note}`);
    let r = await runCase(browser, kase, 1);
    if ((r.empty || r.failures.some(f => f.startsWith('ERROR'))) && !r.pass) {
      console.log('  (empty/transient — retrying once)');
      r = await runCase(browser, kase, 2);
    }
    console.log(`  ${r.pass ? 'PASS' : 'FAIL'} | asked_first=${r.asked} reasked=${r.reasked}` +
      (r.failures.length ? ` | ${r.failures.join(' ; ')}` : ''));
    results.push(r);
  }
  await browser.close();
  fs.writeFileSync(`${DIR}/dept_${MODEL}_results.json`, JSON.stringify(results, null, 2));
  const passed = results.filter(r => r.pass).length;
  console.log(`\n===== ${MODEL} BATTERY: ${passed}/${results.length} PASS =====`);
  process.exitCode = passed === results.length ? 0 : 1;
})();
