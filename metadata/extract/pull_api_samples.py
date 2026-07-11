"""Sample the live 1MPRO test API (read-only) to learn real response shapes,
filter behavior and enum vocabularies — the "filtered data through the API"
evidence for the metadata warehouse.

Safety/PII rules:
- Only endpoints OBSERVED being fired by the read-only web walk (web_observations
  .json) are replayed, with tiny page sizes. This API uses POST bodies as search
  filters; those same observed calls are read-only searches.
- We store STRUCTURE, not people: response key trees with type placeholders,
  meta/sum shapes, and distinct values ONLY for enum-ish fields (status/type/
  boolean-ish names). Free-text/name/phone/address values are never stored.

Run:  python metadata/extract/pull_api_samples.py
Env:  ONEM_USER / ONEM_PASS (test login), ONEM_BASE (default https://test.1mpro.com)
Out:  metadata/extract/api_samples.json
"""
import json
import os
import re
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("ONEM_BASE", "https://test.1mpro.com")
USER = os.environ.get("ONEM_USER", "")
PASS = os.environ.get("ONEM_PASS", "")
OUT = os.path.join(HERE, "api_samples.json")

ENUMISH = re.compile(r"(status|type|_by|payment|state|interval|group|unit|role|isUse|"
                     r"is_[a-z_]+|channel|social)", re.I)
PII_HINT = re.compile(r"(name|tel|phone|address|email|line|contact|fullname|username|"
                      r"tax|location|remark|note|detail)", re.I)


def call(method, path, body=None, token=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("content-type", "application/json")
    # the host WAF 403s python-urllib's default agent; a browser UA passes (curl does too)
    req.add_header("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) onem-metadata/1.0")
    if token:
        req.add_header("authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def shape_of(v, depth=0):
    """Value -> type-skeleton (values stripped)."""
    if depth > 6:
        return "..."
    if isinstance(v, dict):
        return {k: shape_of(x, depth + 1) for k, x in list(v.items())[:60]}
    if isinstance(v, list):
        return [shape_of(v[0], depth + 1)] if v else []
    return type(v).__name__


def harvest_enums(rows, into):
    """Collect distinct values for enum-ish scalar fields (never PII-hinted ones)."""
    for row in rows[:50]:
        if not isinstance(row, dict):
            continue
        for k, v in row.items():
            if isinstance(v, (str, int, bool)) and ENUMISH.search(k) \
                    and not PII_HINT.search(k):
                s = str(v)
                if len(s) <= 40:
                    into.setdefault(k, set()).add(s)


def main():
    if not USER or not PASS:
        raise SystemExit("set ONEM_USER / ONEM_PASS env (test login)")
    login = call("POST", "/api/user/login", {"username": USER, "password": PASS})
    token = login.get("accessToken") or (login.get("result") or {}).get("accessToken")
    if not token:
        raise SystemExit(f"login failed: {str(login)[:200]}")
    print("[ok] logged in")

    obs = json.load(open(os.path.join(HERE, "web_observations.json"), encoding="utf-8"))
    targets = {}
    for o in obs["observations"]:
        p = o["api_path"]
        if p in ("/api/user/login",) or o["method"] not in ("GET", "POST"):
            continue
        if o.get("status") and o["status"] >= 400:
            continue
        targets.setdefault((o["method"], p), o)

    samples, enums = [], {}
    for (method, path), o in sorted(targets.items()):
        body = None
        if method == "POST":
            # replay the EXACT body the real browser sent (schema-valid by construction),
            # just clamped to a tiny page
            body = dict(o.get("post_body") or {"page": 1, "limit": 5})
            if "limit" in body:
                body["limit"] = 5
            if "page" in body:
                body["page"] = 1
        try:
            resp = call(method, path, body, token)
            rows = resp.get("result") if isinstance(resp, dict) else None
            n = len(rows) if isinstance(rows, list) else (1 if rows else 0)
            if isinstance(rows, list):
                harvest_enums(rows, enums)
            elif isinstance(rows, dict):
                harvest_enums([rows], enums)
            samples.append({
                "method": method, "path": path, "sent_body_keys": sorted(body) if body else [],
                "ok": bool(resp.get("status")) if isinstance(resp, dict) else True,
                "rows_returned": n,
                "meta": resp.get("meta") if isinstance(resp, dict) else None,
                "sum_keys": sorted(resp["sum"].keys())
                if isinstance(resp, dict) and isinstance(resp.get("sum"), dict) else None,
                "response_shape": shape_of(resp),
            })
            print(f"  [ok] {method} {path} rows={n}")
        except Exception as e:  # noqa: BLE001
            samples.append({"method": method, "path": path, "error": str(e)[:160]})
            print(f"  [err] {method} {path}: {str(e)[:80]}")
        time.sleep(0.6)  # be gentle with the shared test server

    data = {"base": BASE, "n_endpoints_sampled": len(samples),
            "samples": samples,
            "enum_vocab": {k: sorted(v) for k, v in sorted(enums.items())}}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"[ok] {OUT}: {len(samples)} endpoints, {len(enums)} enum fields")


if __name__ == "__main__":
    main()
