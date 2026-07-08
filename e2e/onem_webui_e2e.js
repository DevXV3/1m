// PingZy WebUI e2e — login as a dept user, send a real query, capture the answer.
// Run: node onem_webui_e2e.js <email> <password> <modelId> "<question>"
// (playwright resolves from this dir's node_modules)
const { chromium } = require('playwright');

const BASE = 'http://127.0.0.1:3000';
const [email, password, modelId, question] = process.argv.slice(2);
const OUT = process.env.OUT || 'C:/Users/AiMiniX/AppData/Local/Temp/claude/C--Users-AiMiniX/962c19a7-f6e5-4098-931c-e1e4d48bf058/scratchpad/webui_e2e.png';

async function findInput(page) {
  for (const sel of ['#chat-input', 'div[contenteditable="true"]', 'textarea']) {
    const el = page.locator(sel).last();
    if (await el.count().catch(() => 0)) {
      try { await el.waitFor({ state: 'visible', timeout: 4000 }); return el; } catch {}
    }
  }
  return null;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const log = (...a) => console.log('[e2e]', ...a);
  try {
    log('goto auth');
    await page.goto(`${BASE}/auth`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    log('submitted login, waiting for app…');
    await page.waitForTimeout(4000);

    log('open model', modelId);
    await page.goto(`${BASE}/?models=${encodeURIComponent(modelId)}`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2500);

    const input = await findInput(page);
    if (!input) throw new Error('chat input not found');
    await input.click();
    await page.keyboard.type(question, { delay: 8 });
    await page.waitForTimeout(300);
    await page.keyboard.press('Enter');
    log('question sent, waiting for response to settle…');

    // poll: wait until page text stops growing (stream done) or 150s
    let prev = 0, stable = 0, t0 = Date.now();
    while (Date.now() - t0 < 150000) {
      await page.waitForTimeout(3000);
      const len = (await page.evaluate(() => document.body.innerText.length)) || 0;
      if (len === prev) { if (++stable >= 3) break; } else { stable = 0; }
      prev = len;
    }
    log(`settled after ${((Date.now() - t0) / 1000).toFixed(0)}s`);

    await page.screenshot({ path: OUT, fullPage: true });
    log('screenshot ->', OUT);

    // dump assistant-side text + markers
    const body = await page.evaluate(() => document.body.innerText);
    const tail = body.slice(-2500);
    console.log('\n===== PAGE TAIL (last 2500 chars) =====\n' + tail);
    console.log('\n===== MARKERS =====');
    console.log('has_98(price)  :', /98/.test(body));
    console.log('has_ศรีสะเกษ    :', /ศรีสะเกษ/.test(body));
    console.log('has_ใบเสนอราคา  :', /เสนอราคา/.test(body));
    console.log('has_think_leak :', /<think>|<\/think>/.test(body));
    console.log('has_raw_json   :', /\{\s*"model"|choices/.test(body));
  } catch (e) {
    console.error('[e2e] ERROR:', e.message);
    try { await page.screenshot({ path: OUT, fullPage: true }); console.log('[e2e] error screenshot ->', OUT); } catch {}
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
