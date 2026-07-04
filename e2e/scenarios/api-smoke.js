// API smoke: hit the backend directly (no browser) and log every call + response.
// Verifies the api is up, reachable, and talking to its database.
module.exports = async function apiSmoke({ log, cfg, api }) {
  const call = async (label, method, urlPath, data) => {
    await log.step(label, async () => {
      const opts = data ? { data } : undefined;
      const res = await api.fetch(urlPath, { method, ...opts });
      const { status, body } = await log.apiDirect(method, cfg.API_URL + urlPath, res);
      console.log(`    ${method} ${urlPath} -> ${status} ${String(body).slice(0, 80)}`);
    }, { shot: false });
  };

  await call('swagger docs reachable', 'GET', '/docs');
  // login validation path (short pw -> zod 400)
  await call('login validation (short pw)', 'POST', '/api/user/login', { username: 'probe', password: 'x' });
  // login reaches DB (valid-length but bogus creds -> 401 if DB connected, 500 if DB down)
  await call('login hits DB (bogus creds)', 'POST', '/api/user/login', { username: '__e2e_probe__', password: 'probe123' });
  // a protected GET without token (expect 401/403/404 depending on route guard)
  await call('protected endpoint w/o token', 'GET', '/api/user');
};
