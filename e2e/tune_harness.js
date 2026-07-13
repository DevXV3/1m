#!/usr/bin/env node
/**
 * tune_harness.js — multi-turn conversational tester for sales/marketing tuning.
 *
 * Runs each scenario as a real multi-turn chat (history carried), prints every
 * assistant turn + computed signal flags, and a heuristic verdict. Sequential
 * (gentle on the shared brain 4-slot); busy/empty = transient retry.
 *
 *   node tune_harness.js <creds.json> <scenarios.json> <out.json>
 *
 * creds.json: { "base": "...", "users": { "sales1@..": "pw", ... } }
 * scenarios.json: [ { name, model, email, turns:[{user, expect}] } ]
 *   expect (optional hints, harness computes signals regardless):
 *     "ask" | "quote" | "quote+ship" | "quote-noship" | "recommend" | "refuse-pivot" | "plan"
 */
const fs = require('fs');
const [credsPath, scenPath, outPath] = process.argv.slice(2);
const creds = JSON.parse(fs.readFileSync(credsPath, 'utf8'));
const scenarios = JSON.parse(fs.readFileSync(scenPath, 'utf8'));
const BASE = creds.base || 'http://127.0.0.1:3000';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const tokenCache = {};
async function signin(email) {
  if (tokenCache[email]) return tokenCache[email];
  const r = await fetch(`${BASE}/api/v1/auths/signin`, { method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password: creds.users[email] }) });
  const j = await r.json();
  tokenCache[email] = j.token;
  return j.token;
}
async function chat(token, model, messages) {
  for (let a = 1; a <= 5; a++) {
    try {
      const r = await fetch(`${BASE}/api/chat/completions`, { method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ model, stream: false, messages }) });
      const j = await r.json();
      const c = j?.choices?.[0]?.message?.content || '';
      const err = j?.detail || '';
      if (c.trim()) return c;
      if (/busy/i.test(err)) { await sleep(45000 * a); continue; }
      if (!c.trim()) { await sleep(30000 * a); continue; } // 0-token transient
    } catch (e) { await sleep(20000 * a); }
  }
  return '(empty after retries)';
}

// ---- signal detectors ----
const S = {
  isAsk: (t) => /PINGZY_ASK/i.test(t) ||
    (/เงินสด/.test(t) && /เครดิต/.test(t) && !/📋\s*ใบเสนอราคา/.test(t)) ||
    (/(ปลายทาง|สถานที่จัดส่ง|จัดส่งที่ไหน|ส่งที่ไหน)/.test(t) && /\?/.test(t) && !/📋/.test(t)),
  isQuote: (t) => /📋\s*ใบเสนอราคา/.test(t) || /ยอดรวม\s*[:：]/.test(t),
  shipLine: (t) => {
    const m = t.match(/ค่าขนส่ง[^\n]*\n?[^\n]*/);
    return m ? m[0].replace(/\s+/g, ' ').trim() : '';
  },
  shipHasNumber: (t) => {
    const m = t.match(/ค่าขนส่ง[\s\S]{0,80}/);
    if (!m) return false;
    const seg = m[0];
    if (/ไม่มีค่าขนส่ง|คิดตามระยะทาง|แจ้งปลายทาง|ยังไม่ระบุ/.test(seg.split('\n').slice(0,2).join(' '))) {
      // still might have a number if "คิดตามระยะทาง 2500" — check digits before ยอดรวม
    }
    const seg2 = seg.split('ยอดรวม')[0];
    return /[\d,]{3,}\s*บาท/.test(seg2.replace(/ค่าขนส่ง/, ''));
  },
  doubleVat: (t) => /vat|ภาษี/i.test(t) && /\+.*7\s*%|บวก.*7/.test(t),
  badClaim: (t) => /(ส่งฟรี|ฟรีค่าส่ง|ขนส่งฟรี|จัดส่งฟรี|บริการติดตั้ง|ติดตั้งฟรี|ติดตั้งให้|ค่าติดตั้ง|ทน.{0,3}\d+\s*ปี|ไม่แตกร้าว|ไม่บวม)/.test(t),
  fakePhone: (t) => {
    const phones = (t.match(/0\d[\d\- ]{7,}/g) || []).map((p) => p.replace(/[\s\-]/g, ''));
    return phones.some((p) => p !== '0614362825');
  },
  isPlan: (t) => /(แผน|วันนี้|to-?do|สิ่งที่ต้องทำ|ประจำวัน)/i.test(t),
  refusesOffTopic: (t) => /(ขออภัย|ไม่สามารถ|เป็นผู้ช่วยฝ่าย)/.test(t),
};
function signals(t) {
  return {
    ask: S.isAsk(t), quote: S.isQuote(t),
    shipLine: S.shipLine(t), shipNum: S.shipHasNumber(t),
    doubleVat: S.doubleVat(t), badClaim: S.badClaim(t), fakePhone: S.fakePhone(t),
    plan: S.isPlan(t), refuse: S.refusesOffTopic(t),
  };
}

(async () => {
  const results = [];
  for (const sc of scenarios) {
    const token = await signin(sc.email);
    const messages = [];
    const turns = [];
    for (const turn of sc.turns) {
      messages.push({ role: 'user', content: turn.user });
      const a = await chat(token, sc.model, messages);
      messages.push({ role: 'assistant', content: a });
      const sig = signals(a);
      turns.push({ user: turn.user, expect: turn.expect || '', a, sig });
      console.log(`[${sc.name}] "${turn.user.slice(0,40)}" -> ask=${sig.ask} quote=${sig.quote} shipNum=${sig.shipNum} bad=${sig.badClaim} vat2=${sig.doubleVat} phone=${sig.fakePhone}`);
    }
    results.push({ name: sc.name, model: sc.model, turns });
  }
  fs.writeFileSync(outPath, JSON.stringify(results, null, 2), 'utf8');
  console.log('WROTE', outPath);
})();
