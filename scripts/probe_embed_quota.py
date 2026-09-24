"""Phase E5.5 -- what does the free tier give `gemini-embedding-001`? SPENDS QUOTA.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\probe_embed_quota.py
         prints the plan and exits. ZERO calls.
     ... --i-understand-this-spends-quota [--out=<path>]
         runs it: at most 60 embedding REQUESTS, then writes
         scripts/probe_embed_quota_<date>.json (or --out=).

WHY (playbook 13, E5.5). M2 (dense retrieval) needs a query-time embed, and the
free-tier limit for the embedding model is unpublished. M2 cannot be costed
without it. This script answers only that question.

BEFORE RUNNING: check HANDOFF.md for the day's spend. Embedding and generation
are BELIEVED to be separate per-model pools; that is unverified, so treat a run
as possibly drawing on generation quota and never run it on a day Phase G needs.

DESIGN, fixed by the box:
  * Inputs are short FIXED strings below -- never user questions, never eval
    questions (M2's privacy concern starts at the first real question sent).
  * Requests go one at a time with no deliberate delay, so a per-minute limit
    below 60 is what trips first -- that is the recoverable kind.
  * Hard cap: 60 requests. STOP AT THE FIRST 429 of either kind, and record it:
    per-minute vs per-day (rag.is_per_minute_429, the project's single source of
    truth), plus quotaId / quotaValue if the RESOURCE_EXHAUSTED detail carries
    them -- that is the limit itself, stated by the server.
  * Phase 1: requests 1-30 embed ONE string each. Phase 2: requests 31-60 embed
    a batch of BATCH strings each (`contents=[...]`). Whether a batch counts as 1
    request or N is read off where (and whether) the 429 lands, and off the
    quota metric the server names.
  * Latency per request is recorded; it decides whether a query-time embed is
    viable on the user path at all.
  * Other errors (503, network) are recorded and retried with backoff, up to 3
    times per request; retries count toward the 60.
Nothing is imported from google.genai until the consent flag is present.
"""

import datetime as _dt
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

MODEL = "gemini-embedding-001"
MAX_REQUESTS = 60
SINGLE_PHASE = 30
BATCH = 5
CONSENT = "--i-understand-this-spends-quota"
PROBES = ["quota probe string %02d: the quick brown fox" % i for i in range(1, 11)]


def plan() -> str:
    return ("probe_embed_quota: model %s, <= %d requests (1-%d single, %d-%d batches of %d), "
            "stop at first 429.\n  Pass %s to spend quota. Check HANDOFF.md's day spend first."
            % (MODEL, MAX_REQUESTS, SINGLE_PHASE, SINGLE_PHASE + 1, MAX_REQUESTS, BATCH, CONSENT))


def quota_detail(err: str) -> dict:
    out = {}
    for field in ("quotaId", "quotaMetric", "quotaValue", "retryDelay"):
        m = re.search(r"['\"]?%s['\"]?:\s*['\"]?([^'\",}]+)" % field, err)
        if m:
            out[field] = m.group(1).strip()
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if CONSENT not in argv:
        print(plan())
        print("  (no calls made)")
        return 0
    out = next((a.split("=", 1)[1] for a in argv if a.startswith("--out=")), None)
    date = _dt.date.today().isoformat()
    out = Path(out) if out else ROOT / "scripts" / ("probe_embed_quota_%s.json" % date)

    from rag import is_per_minute_429, retry_delay  # noqa: E402  (no network on import)
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        print("GOOGLE_API_KEY/GEMINI_API_KEY not set -- no calls made")
        return 2
    from google import genai
    client = genai.Client(api_key=key)

    calls, stop, t0 = [], None, time.time()
    i = 0
    while len(calls) < MAX_REQUESTS and stop is None:
        i += 1
        batch = i > SINGLE_PHASE
        contents = [PROBES[(i + j) % len(PROBES)] for j in range(BATCH)] if batch \
            else PROBES[i % len(PROBES)]
        for attempt in range(3):
            if len(calls) >= MAX_REQUESTS:
                break
            rec = {"n": len(calls) + 1, "logical": i, "kind": "batch" if batch else "single",
                   "strings": BATCH if batch else 1, "t": round(time.time() - t0, 2)}
            s = time.perf_counter()
            try:
                r = client.models.embed_content(model=MODEL, contents=contents)
                rec.update(ok=True, ms=round((time.perf_counter() - s) * 1000),
                           vectors=len(r.embeddings), dim=len(r.embeddings[0].values))
                calls.append(rec)
                break
            except Exception as e:  # noqa: BLE001 -- every failure is data here
                msg = str(e)
                rec.update(ok=False, ms=round((time.perf_counter() - s) * 1000),
                           error=msg[:600])
                calls.append(rec)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    stop = {"at_request": rec["n"], "kind": rec["kind"],
                            "per_minute": is_per_minute_429(msg),
                            "per_day": not is_per_minute_429(msg), **quota_detail(msg)}
                    break
                time.sleep(retry_delay(msg, attempt))
        print("  req %3d %-6s %s" % (calls[-1]["n"], calls[-1]["kind"],
                                     "ok %dms" % calls[-1]["ms"] if calls[-1]["ok"]
                                     else "ERR " + calls[-1]["error"][:80]))

    ok = [c for c in calls if c["ok"]]
    lat = sorted(c["ms"] for c in ok if c["kind"] == "single")
    result = {
        "date": date, "model": MODEL, "requests": len(calls), "ok": len(ok),
        "strings_embedded": sum(c["strings"] for c in ok),
        "single_ok": sum(1 for c in ok if c["kind"] == "single"),
        "batch_ok": sum(1 for c in ok if c["kind"] == "batch"),
        "elapsed_s": round(time.time() - t0, 1),
        "single_latency_ms": {"min": lat[0], "median": lat[len(lat) // 2], "max": lat[-1]}
        if lat else None,
        "first_429": stop,
        "reading": ("no 429 within %d requests in %.0fs: RPM and RPD are both >= %d"
                    % (len(calls), time.time() - t0, len(ok))) if stop is None else
                   "429 at request %d -- see first_429" % stop["at_request"],
        "calls": calls,
    }
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "calls"}, indent=2))
    print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
