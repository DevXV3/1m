#!/usr/bin/env node
/**
 * load_test.js — light concurrent load test for Open WebUI (:3000)
 *
 * Drives /api/chat/completions directly (no browser), same web-origin path
 * the frontend uses, as N department test users in parallel.
 *
 * Usage:
 *   node load_test.js <plan.json> [outFile.json]
 *
 * plan.json (NOT committed — pass a local file, creds never hardcoded here):
 *   {
 *     "base": "http://127.0.0.1:3000",
 *     "users": [
 *       { "email": "...", "password": "...", "model": "pingzy-sales",
 *         "questions": ["q1", "q2"] },
 *       ...
 *     ]
 *   }
 *
 * Rules honored:
 *  - "server busy" / empty (0-token) responses are transient -> retry with backoff
 *  - never restarts anything; read-only against the stack
 */
const fs = require('fs');

const planPath = process.argv[2];
if (!planPath) {
  console.error('usage: node load_test.js <plan.json> [outFile.json]');
  process.exit(2);
}
const outPath = process.argv[3] || null;
const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
const BASE = plan.base || 'http://127.0.0.1:3000';
const REQ_TIMEOUT_MS = plan.timeoutMs || 240000;
const MAX_ATTEMPTS = plan.maxAttempts || 3;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function fetchJson(url, opts, timeoutMs) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...opts, signal: ctrl.signal });
    const text = await res.text();
    let json = null;
    try { json = JSON.parse(text); } catch (_) { /* keep raw */ }
    return { status: res.status, json, text };
  } finally {
    clearTimeout(t);
  }
}

async function signin(user) {
  for (let i = 1; i <= 5; i++) {
    try {
      const r = await fetchJson(`${BASE}/api/v1/auths/signin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: user.email, password: user.password }),
      }, 20000);
      if (r.status === 200 && r.json && r.json.token) return r.json.token;
      throw new Error(`signin ${r.status}: ${r.text.slice(0, 120)}`);
    } catch (e) {
      if (i === 5) throw e;
      await sleep(2000 * i); // transient ConnectionReset right after container recreate
    }
  }
}

function isTransient(errText) {
  return /busy|timeout|ECONNRESET|fetch failed|aborted|503|502/i.test(errText);
}

async function askOnce(token, model, question) {
  const r = await fetchJson(`${BASE}/api/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      model,
      stream: false,
      messages: [{ role: 'user', content: question }],
    }),
  }, REQ_TIMEOUT_MS);
  if (r.status !== 200) throw new Error(`HTTP ${r.status}: ${r.text.slice(0, 200)}`);
  const content =
    r.json?.choices?.[0]?.message?.content ??
    r.json?.choices?.[0]?.text ?? '';
  if (!content || !content.trim()) throw new Error('EMPTY (0-token transient)');
  return content;
}

async function ask(token, model, question, tag, results) {
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    const t0 = Date.now();
    try {
      const content = await askOnce(token, model, question);
      const ms = Date.now() - t0;
      const rec = { tag, model, question, ok: true, attempt, ms, chars: content.length };
      results.push(rec);
      console.log(`[OK ] ${tag} attempt=${attempt} ${(ms / 1000).toFixed(1)}s chars=${content.length}`);
      return;
    } catch (e) {
      const ms = Date.now() - t0;
      const msg = String(e.message || e);
      console.log(`[ERR] ${tag} attempt=${attempt} ${(ms / 1000).toFixed(1)}s ${msg.slice(0, 140)}`);
      if (attempt < MAX_ATTEMPTS && (isTransient(msg) || /EMPTY/.test(msg))) {
        // brain slots are held for 30-100s per request — busy needs a long backoff
        const backoff = /busy/i.test(msg) ? 45000 * attempt : 8000 * attempt;
        await sleep(backoff);
        continue;
      }
      results.push({ tag, model, question, ok: false, attempt, ms, error: msg.slice(0, 300) });
      return;
    }
  }
}

async function runUser(user, idx, results) {
  await sleep(Math.floor(Math.random() * 5000)); // stagger 0-5s
  let token;
  try {
    token = await signin(user);
  } catch (e) {
    const msg = `signin failed: ${String(e.message || e).slice(0, 200)}`;
    console.log(`[ERR] u${idx}:${user.model} ${msg}`);
    user.questions.forEach((q, qi) =>
      results.push({ tag: `u${idx}q${qi + 1}`, model: user.model, question: q, ok: false, error: msg }));
    return;
  }
  console.log(`[LOGIN] u${idx} ${user.email} -> ${user.model}`);
  for (let qi = 0; qi < user.questions.length; qi++) {
    await ask(token, user.model, user.questions[qi], `u${idx}q${qi + 1}:${user.model}`, results);
  }
}

(async () => {
  const started = new Date().toISOString();
  console.log(`load_test start ${started} base=${BASE} users=${plan.users.length}`);
  const results = [];
  const t0 = Date.now();
  await Promise.all(plan.users.map((u, i) => runUser(u, i + 1, results)));
  const wallMs = Date.now() - t0;

  const ok = results.filter((r) => r.ok);
  const fail = results.filter((r) => !r.ok);
  const lat = ok.map((r) => r.ms).sort((a, b) => a - b);
  const summary = {
    started,
    wallSec: Math.round(wallMs / 1000),
    total: results.length,
    ok: ok.length,
    fail: fail.length,
    latencySec: lat.length
      ? {
          min: +(lat[0] / 1000).toFixed(1),
          median: +(lat[Math.floor(lat.length / 2)] / 1000).toFixed(1),
          max: +(lat[lat.length - 1] / 1000).toFixed(1),
        }
      : null,
    retriesUsed: ok.filter((r) => r.attempt > 1).length,
    failures: fail,
  };
  console.log('=== SUMMARY ===');
  console.log(JSON.stringify(summary, null, 2));
  if (outPath) fs.writeFileSync(outPath, JSON.stringify({ summary, results }, null, 2));
  process.exit(fail.length ? 1 : 0);
})();
