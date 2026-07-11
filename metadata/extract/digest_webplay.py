"""Digest the e2e explore run (Playwright walk of the live 1MPRO web) into
web_observations.json — which API calls each screen fired and with what filters.

This is the "played the real web and watched the wire" evidence: per action step
(= screen/interaction), the API requests observed (path + query params + status),
so the metadata DB can map screen -> live API usage -> filter vocabulary.

Run:  python metadata/extract/digest_webplay.py [run_dir]
Out:  metadata/extract/web_observations.json
"""
import json
import os
import sys
from collections import defaultdict
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RUN = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, "e2e", "runs", "20260704_222707_explore")
OUT = os.path.join(HERE, "web_observations.json")


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    actions = load_jsonl(os.path.join(RUN, "actions.jsonl"))
    network = load_jsonl(os.path.join(RUN, "network.jsonl"))

    # action windows: step label + [start_t, end_t)
    windows = []
    for a in actions:
        if a.get("status") == "start":
            windows.append({"step": a["step"], "label": a["label"],
                            "t0": a["t"], "t1": None})
        elif a.get("status") in ("ok", "error") and windows:
            for w in reversed(windows):
                if w["step"] == a["step"] and w["t1"] is None:
                    w["t1"] = a["t"]
                    w["screenshot"] = a.get("screenshot")
                    break

    def window_for(t):
        for w in windows:
            if w["t0"] <= t and (w["t1"] is None or t <= w["t1"]):
                return w
        return None

    # collect API request/response pairs
    responses = {}
    for ev in network:
        if ev.get("phase") == "response" and ev.get("isApi"):
            responses[(ev["method"], ev["url"])] = ev.get("status")

    observations = []
    seen = set()
    for ev in network:
        if ev.get("phase") != "request" or not ev.get("isApi"):
            continue
        u = urlparse(ev["url"])
        params = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(u.query).items()}
        w = window_for(ev["t"])
        key = (w["step"] if w else 0, ev["method"], u.path, tuple(sorted(params)))
        if key in seen:
            continue
        seen.add(key)
        post_body = None
        if ev.get("postData") and str(ev["postData"]).startswith("{"):
            try:
                post_body = json.loads(ev["postData"])
            except ValueError:
                post_body = None
        observations.append({
            "step": w["step"] if w else None,
            "screen_label": w["label"] if w else "(outside steps)",
            "method": ev["method"],
            "api_path": u.path,
            "query_params": params,
            "post_data_keys": sorted(post_body.keys()) if post_body else [],
            # exact browser body — lets the sampler replay schema-valid requests
            "post_body": post_body if u.path != "/api/user/login" else None,
            "status": responses.get((ev["method"], ev["url"])),
        })

    # per-endpoint filter vocabulary across the whole run — this app's list
    # endpoints filter via POST body, so merge query + body keys
    filter_vocab = defaultdict(set)
    for o in observations:
        for k in o["query_params"]:
            filter_vocab[o["api_path"]].add(k)
        for k in o["post_data_keys"]:
            filter_vocab[o["api_path"]].add(k)

    data = {"run_dir": os.path.basename(RUN),
            "n_steps": len(windows), "n_api_observations": len(observations),
            "steps": [{"step": w["step"], "label": w["label"],
                       "screenshot": w.get("screenshot")} for w in windows],
            "observations": observations,
            "endpoint_filter_vocab": {k: sorted(v) for k, v in sorted(filter_vocab.items())}}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"[ok] {OUT}: {len(windows)} steps, {len(observations)} api observations, "
          f"{len(filter_vocab)} endpoints seen live")


if __name__ == "__main__":
    main()
