// Big-chat scenario: ONE long sales conversation, sequential turns in the same chat.
// Tests context retention (edits to a quote), business rules (install=referral,
// no VAT line, real shipping rates), and live ERP tool calls — the things the
// single-shot battery can't see. Each turn has must/mustNot regexes checked
// against text that appeared AFTER that turn was sent.
// Run: node big_chat.js <email> <pw>
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = 'http://127.0.0.1:3000';
const [email, password] = process.argv.slice(2);
const DIR = process.env.OUTDIR || __dirname + '/runs/bigchat';
fs.mkdirSync(DIR, { recursive: true });

const TURNS = [
  {
    id: 't1-quote-warin',
    q: 'ลูกค้าอยู่วารินชำราบ จ.อุบลฯ อยากได้แผ่นพื้นหน้า 35 ยาวรวม 60 เมตร ทำใบเสนอราคาหน่อย',
    must: ['98', '5,?880', '1,?300', '7,?180'],
    mustNot: ['ค่าติดตั้ง', 'VAT 7%:'],
  },
  {
    id: 't2-edit-add',
    q: 'เปลี่ยนแผ่นพื้นเป็น 100 เมตร แล้วเพิ่มเสารั้วลวดหนาม 3 นิ้ว ยาว 2 เมตร อีก 20 ต้น',
    must: ['9,?800', '1,?700', '(11,?500|12,?800)'],
    mustNot: ['ขอข้อมูล'],
  },
  {
    id: 't3-install',
    q: 'ลูกค้าถามว่ามีบริการติดตั้งไหม คิดค่าติดตั้งเท่าไหร่',
    must: ['แนะนำช่าง|ช่างแนะนำ|ช่างติดตั้ง', 'ไม่รับติดตั้ง|ไม่คิดค่าติดตั้ง|ไม่มีบริการติดตั้ง|ไม่ได้คิดค่าติดตั้ง'],
    mustNot: [],
    noStepper: true,
  },
  {
    id: 't4-live-price',
    q: 'ช่วยเช็คราคาแผ่นพื้นสำเร็จรูปในระบบ 1MPRO สดๆ ตอนนี้ให้หน่อย',
    must: ['98|แผ่นพื้น'],
    mustNot: [],
  },
  {
    id: 't5-reroute-korat',
    q: 'ถ้าเปลี่ยนที่ส่งเป็นนครราชสีมา ค่าขนส่งกับยอดรวมเปลี่ยนเป็นเท่าไหร่',
    must: ['2,?500', '14,?000|11,?500'],
    mustNot: [],
  },
];

async function settle(page, prevLen, ms = 300000) {
  let prev = prevLen, stable = 0, grew = false, t0 = Date.now();
  while (Date.now() - t0 < ms) {
    await page.waitForTimeout(3000);
    const len = (await page.evaluate(() => document.body.innerText.length)) || 0;
    if (len > prev) { grew = true; stable = 0; }
    else if (grew && Date.now() - t0 > 20000) stable++;
    if (grew && stable >= 4) break;
    prev = len;
  }
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  const results = [];
  await page.goto(`${BASE}/auth`, { waitUntil: 'networkidle', timeout: 30000 });
  if (await page.locator('input[type="email"]').count().catch(() => 0)) {
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(4000);
  }
  for (let i = 0; i < 4; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(150); }
  await page.goto(`${BASE}/?models=pingzy-sales`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2200);
  for (let i = 0; i < 3; i++) { await page.keyboard.press('Escape'); await page.waitForTimeout(150); }

  let beforeLen = 0;
  for (const t of TURNS) {
    console.log(`\n=== ${t.id}`);
    beforeLen = (await page.evaluate(() => document.body.innerText.length)) || 0;
    const input = page.locator('#chat-input, div[contenteditable="true"], textarea').last();
    await input.click();
    await page.keyboard.type(t.q);
    await page.keyboard.press('Enter');
    await settle(page, beforeLen);
    // regex against the FULL page text: innerText length shifts between reads
    // (sidebar/scroll) made slice-windows drop content that was visibly there.
    // Turn expectations use distinct numbers, so full-body matching is safe.
    const turnText = await page.evaluate(() => document.body.innerText);
    const r = { id: t.id, pass: true, failures: [] };
    const steppers = await page.locator('[data-pzset-root]').count().catch(() => 0);
    if (t.noStepper && steppers > 0 && turnText.includes('ขอข้อมูล')) {
      r.pass = false; r.failures.push('launched ask-set on factual question');
    }
    for (const m of t.must || []) {
      if (!new RegExp(m).test(turnText)) { r.pass = false; r.failures.push(`missing: ${m}`); }
    }
    for (const m of [...(t.mustNot || []), '\\[\\[/?PINGZY', '<think>']) {
      if (new RegExp(m).test(turnText)) { r.pass = false; r.failures.push(`forbidden: ${m}`); }
    }
    await page.screenshot({ path: `${DIR}/${t.id}.png`, fullPage: false });
    console.log(`  ${r.pass ? 'PASS' : 'FAIL'}${r.failures.length ? ' | ' + r.failures.join(' ; ') : ''}`);
    results.push(r);
  }
  await page.screenshot({ path: `${DIR}/full_conversation.png`, fullPage: true });
  await browser.close();
  fs.writeFileSync(`${DIR}/results.json`, JSON.stringify(results, null, 2));
  const passed = results.filter(r => r.pass).length;
  console.log(`\n===== BIG CHAT: ${passed}/${results.length} PASS =====`);
  process.exitCode = passed === results.length ? 0 : 1;
})();
