// Central config — override via env vars.
module.exports = {
  WEB_URL: process.env.WEB_URL || 'http://localhost:3000',
  API_URL: process.env.API_URL || 'http://localhost:8080',
  // App login creds for UI scenarios (no default — set in env to exercise authed flows)
  USER: process.env.E2E_USER || '',
  PASS: process.env.E2E_PASS || '',
  HEADLESS: process.env.E2E_HEADFUL ? false : true,
  // Path to the running api server's stdout log, snapshotted into each run for correlation.
  API_LOG: process.env.API_LOG ||
    'C:/Users/AiMiniX/AppData/Local/Temp/claude/C--Users-AiMiniX/69bbd909-08f1-40ce-8990-51e438835926/scratchpad/api-dev4.log',
};
