// Web UI smoke: open the app, attempt login, land on the dashboard.
// Every UI action + every web<->api request/response is captured by the logger.
// Set E2E_USER / E2E_PASS to exercise a real authenticated flow; without them it
// still loads the login page and logs the failed/blocked attempt.
module.exports = async function loginSmoke({ page, log, cfg }) {
  await log.step('open web root', async () => {
    await page.goto(cfg.WEB_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
  });

  await log.step('go to /auth/login', async () => {
    await page.goto(cfg.WEB_URL + '/auth/login', { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(1500); // let the SPA hydrate
  });

  // Fill credentials defensively (selectors vary; try several).
  const userSel = 'input[name="username"], input[type="text"], input#username';
  const passSel = 'input[type="password"], input[name="password"]';

  if (cfg.USER && cfg.PASS) {
    await log.step('fill username', async () => {
      await page.locator(userSel).first().fill(cfg.USER, { timeout: 15000 });
    });
    await log.step('fill password', async () => {
      await page.locator(passSel).first().fill(cfg.PASS, { timeout: 15000 });
    });
    await log.step('submit login', async () => {
      const btn = page.getByRole('button', { name: /login|เข้าสู่ระบบ|sign in/i }).first();
      if (await btn.count()) await btn.click();
      else await page.locator(passSel).first().press('Enter');
      // wait for the login api call to resolve
      await page.waitForResponse((r) => r.url().includes('/api/user/login'), { timeout: 20000 }).catch(() => {});
      await page.waitForTimeout(2000);
    });
    await log.step('post-login navigation', async () => {
      await page.waitForTimeout(1500);
    });
  } else {
    await log.step('no creds provided — capture login page only', async () => {
      await page.waitForTimeout(1000);
    }, { shot: true });
  }
};
