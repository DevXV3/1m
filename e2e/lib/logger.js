// SystemLogger — attaches to a Playwright page and records EVERY action across web + api
// into a per-run folder: UI actions, network (web<->api) req/res, console, page errors,
// screenshots, and a Playwright trace. Produces summary.json + report.md at the end.
const fs = require('fs');
const path = require('path');

function nowIso() { return new Date().toISOString(); }
function truncate(s, n = 2000) {
  if (s == null) return s;
  s = typeof s === 'string' ? s : String(s);
  return s.length > n ? s.slice(0, n) + `…<+${s.length - n} chars>` : s;
}

class SystemLogger {
  constructor(page, { runDir, apiUrl }) {
    this.page = page;
    this.runDir = runDir;
    this.apiUrl = apiUrl;
    this.shotDir = path.join(runDir, 'screenshots');
    fs.mkdirSync(this.shotDir, { recursive: true });
    this.streams = {
      actions: fs.createWriteStream(path.join(runDir, 'actions.jsonl')),
      network: fs.createWriteStream(path.join(runDir, 'network.jsonl')),
      console: fs.createWriteStream(path.join(runDir, 'console.jsonl')),
    };
    this.counts = { actions: 0, apiCalls: 0, webRequests: 0, console: 0, errors: 0, failedApi: 0 };
    this.timeline = [];
    this.stepNo = 0;
    this.t0 = Date.now();
    this._wireEvents();
  }

  _rel() { return ((Date.now() - this.t0) / 1000).toFixed(2) + 's'; }
  _emit(stream, obj) {
    obj.t = nowIso(); obj.rel = this._rel();
    this.streams[stream].write(JSON.stringify(obj) + '\n');
  }

  _wireEvents() {
    const p = this.page;
    // console
    p.on('console', (msg) => {
      this.counts.console++;
      const rec = { type: msg.type(), text: truncate(msg.text(), 1000) };
      this._emit('console', rec);
      if (msg.type() === 'error') this.timeline.push({ kind: 'console-error', rel: this._rel(), text: rec.text });
    });
    p.on('pageerror', (err) => {
      this.counts.errors++;
      const rec = { kind: 'pageerror', message: truncate(err.message, 1000) };
      this._emit('console', rec);
      this.timeline.push({ kind: 'pageerror', rel: this._rel(), text: rec.message });
    });
    // network requests
    p.on('request', (req) => {
      const isApi = req.url().startsWith(this.apiUrl);
      if (isApi) this.counts.apiCalls++; else this.counts.webRequests++;
      let postData;
      try { postData = req.postData(); } catch { /* ignore */ }
      this._emit('network', {
        phase: 'request', isApi, method: req.method(), url: req.url(),
        resourceType: req.resourceType(), postData: truncate(postData),
      });
    });
    // network responses
    p.on('response', async (res) => {
      const req = res.request();
      const isApi = req.url().startsWith(this.apiUrl);
      const rec = {
        phase: 'response', isApi, method: req.method(), url: req.url(),
        status: res.status(), statusText: res.statusText(),
      };
      if (isApi) {
        const ct = (res.headers()['content-type'] || '');
        if (/json|text|xml|urlencoded/.test(ct)) {
          try { rec.body = truncate(await res.text()); } catch { rec.body = '<unreadable>'; }
        } else { rec.body = `<${ct || 'binary'}>`; }
        if (res.status() >= 400) this.counts.failedApi++;
        this.timeline.push({
          kind: 'api', rel: this._rel(), method: req.method(),
          url: req.url().replace(this.apiUrl, ''), status: res.status(),
        });
      }
      this._emit('network', rec);
    });
  }

  // Log + perform a UI action. `fn` is the async operation; label describes it.
  async step(label, fn, { shot = true } = {}) {
    this.stepNo++;
    const n = String(this.stepNo).padStart(3, '0');
    const started = Date.now();
    this._emit('actions', { step: this.stepNo, label, status: 'start' });
    this.timeline.push({ kind: 'action', rel: this._rel(), label, step: this.stepNo });
    let error = null;
    try {
      if (fn) await fn();
    } catch (e) {
      error = e; this.counts.errors++;
      this._emit('actions', { step: this.stepNo, label, status: 'error', message: truncate(e.message, 800) });
      this.timeline.push({ kind: 'action-error', rel: this._rel(), label, text: truncate(e.message, 300) });
    }
    let shotPath = null;
    if (shot) {
      shotPath = path.join(this.shotDir, `${n}-${label.replace(/[^a-z0-9]+/gi, '_').slice(0, 40)}.png`);
      try { await this.page.screenshot({ path: shotPath, fullPage: false }); } catch { shotPath = null; }
    }
    this.counts.actions++;
    this._emit('actions', {
      step: this.stepNo, label, status: error ? 'failed' : 'ok',
      ms: Date.now() - started, screenshot: shotPath ? path.basename(shotPath) : null,
    });
    if (error) throw error;
  }

  // Record a direct (non-browser) api call, e.g. via Playwright APIRequestContext.
  async apiDirect(method, url, res) {
    const status = res.status();
    let body; try { body = truncate(await res.text()); } catch { body = '<unreadable>'; }
    this.counts.apiCalls++;
    if (status >= 400) this.counts.failedApi++;
    this._emit('network', { phase: 'response', isApi: true, direct: true, method, url, status, body });
    this.timeline.push({ kind: 'api', rel: this._rel(), method, url: url.replace(this.apiUrl, ''), status });
    return { status, body };
  }

  async finalize({ scenario, status, note }) {
    for (const s of Object.values(this.streams)) s.end();
    const summary = {
      scenario, status, note: note || null,
      startedAt: new Date(this.t0).toISOString(), durationSec: ((Date.now() - this.t0) / 1000).toFixed(1),
      counts: this.counts,
    };
    fs.writeFileSync(path.join(this.runDir, 'summary.json'), JSON.stringify(summary, null, 2));
    fs.writeFileSync(path.join(this.runDir, 'report.md'), this._report(summary));
    return summary;
  }

  _report(summary) {
    const L = [];
    L.push(`# E2E run — ${summary.scenario}`);
    L.push('');
    L.push(`- **status:** ${summary.status}`);
    L.push(`- started ${summary.startedAt} · duration ${summary.durationSec}s`);
    L.push(`- actions: ${summary.counts.actions} · api calls: ${summary.counts.apiCalls} (failed ${summary.counts.failedApi}) · web requests: ${summary.counts.webRequests} · console: ${summary.counts.console} · errors: ${summary.counts.errors}`);
    if (summary.note) L.push(`- note: ${summary.note}`);
    L.push('');
    L.push('## Timeline (UI actions + api calls interleaved)');
    L.push('');
    L.push('| t | kind | detail |');
    L.push('|---|------|--------|');
    for (const e of this.timeline) {
      let detail = '';
      if (e.kind === 'action') detail = `**${e.step}. ${e.label}**`;
      else if (e.kind === 'action-error') detail = `⛔ action failed: ${e.label} — ${e.text}`;
      else if (e.kind === 'api') detail = `\`${e.method} ${e.url}\` → **${e.status}**`;
      else if (e.kind === 'console-error') detail = `console.error: ${e.text}`;
      else if (e.kind === 'pageerror') detail = `page error: ${e.text}`;
      L.push(`| ${e.rel} | ${e.kind} | ${detail} |`);
    }
    L.push('');
    L.push('_Full detail: actions.jsonl · network.jsonl · console.jsonl · screenshots/ · trace.zip_');
    return L.join('\n');
  }
}

module.exports = { SystemLogger, truncate };
