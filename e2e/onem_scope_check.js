// Scoping check — login as a dept user, list accessible models/prompts/tools/skills
// via in-page API (uses the session token). No model is fired.
// Run: node onem_scope_check.js <email> <password>
const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:3000';
const [email, password] = process.argv.slice(2);

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  try {
    await page.goto(`${BASE}/auth`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(4000);

    const data = await page.evaluate(async (base) => {
      const tok = localStorage.getItem('token');
      const h = { Authorization: 'Bearer ' + tok };
      const j = async (p) => { try { const r = await fetch(base + p, { headers: h }); return await r.json(); } catch (e) { return { err: String(e) }; } };
      const models = await j('/api/models');
      const prompts = await j('/api/v1/prompts/');
      const tools = await j('/api/v1/tools/');
      const skills = await j('/api/v1/skills/');
      const ids = (x) => Array.isArray(x) ? x.map(o => o.id) : (x?.data ? x.data.map(o => o.id) : x);
      return {
        models: ids(models?.data || models),
        prompts: (Array.isArray(prompts) ? prompts : prompts?.data || []).map(o => o.command),
        tools: ids(tools),
        skills: ids(skills),
      };
    }, BASE);

    console.log('user      :', email);
    console.log('models    :', (data.models || []).filter(m => String(m).startsWith('pingzy')));
    console.log('prompts   :', data.prompts);
    console.log('tools     :', data.tools);
    console.log('skills    :', data.skills);
  } catch (e) {
    console.error('ERROR:', e.message);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
