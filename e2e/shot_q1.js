// Grab a screenshot of the stepper's FIRST question (mode labels + radio marks).
// Run: node shot_q1.js <email> <pw> <model> <outfile>
const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:3000';
const [email, password, model, out] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch({ headless: true });
  const p = await b.newPage({ viewport: { width: 1400, height: 950 } });
  await p.goto(`${BASE}/auth`, { waitUntil: 'networkidle' });
  await p.fill('input[type="email"]', email);
  await p.fill('input[type="password"]', password);
  await p.click('button[type="submit"]');
  await p.waitForTimeout(3500);
  for (let i = 0; i < 4; i++) { await p.keyboard.press('Escape'); await p.waitForTimeout(200); }
  await p.goto(`${BASE}/?models=${model}`, { waitUntil: 'networkidle' });
  await p.waitForTimeout(2000);
  for (let i = 0; i < 3; i++) { await p.keyboard.press('Escape'); await p.waitForTimeout(200); }
  const input = p.locator('#chat-input, div[contenteditable="true"], textarea').last();
  await input.click(); await p.keyboard.type('เริ่ม'); await p.keyboard.press('Enter');
  for (let a = 0; a < 20; a++) {
    await p.waitForTimeout(1500);
    if (await p.locator('[data-pzset-root]').count().catch(() => 0)) break;
  }
  await p.waitForTimeout(800);
  await p.screenshot({ path: out, fullPage: true });
  console.log('->', out);
  await b.close();
})();
