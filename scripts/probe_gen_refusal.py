"""Pre-launch generator-refusal probe (2026-10-15, after Phase G closed).

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\probe_gen_refusal.py
         DRY RUN (the default): selects the probes offline and prints the call plan. ZERO calls.
     ... --i-understand-this-spends-quota
         runs it: <= 10 calls on rag.MODEL_NAME, no failover, no cache, written after EVERY
         call to scripts/probe_gen_refusal_<prompt>_<date>.json. The first failed call stops
         the run; its row stays PENDING (llm_error), never faked.

WHY. G's exploratory CD1.t2 ("so can they fire me?") was refused by the LLM layer with
[Act cl. 28] in context. calibrate_refusal (0/212) measures the RETRIEVAL floor only; nothing
has measured how often the GENERATOR refuses when the evidence is in front of it.

SELECTION, fixed before any call (docs/phases/14_generation_eval.md, "G6"): the register
probes (data/eval/register_probes.json, lay + Pidgin, Act-verified refs), keeping ONLY those
whose expected clause is in the PROMPT context -- the hits ask() actually passes to the model
(select_top, then the per-hit MIN_SCORE trim). A refusal with the clause absent is correct
behaviour, not a finding, so those probes are excluded rather than counted. Ordered by id,
capped at 10. Single-turn ask(), the shipping prompt (cite-strict-v3).
"""

import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import rag  # noqa: E402
from evalset import strict_covered  # noqa: E402
from retrieve import MIN_SCORE, PerDocRetriever, select_top  # noqa: E402

PROBES = ROOT / "data" / "eval" / "register_probes.json"
CONSENT = "--i-understand-this-spends-quota"
CAP = 10
SLEEP_S = 7  # 10/min/model free tier


def prompt_hits(ret, q):
    """Exactly ask()'s context: select_top(k=4, top_n=12), then the per-hit floor."""
    merged = select_top(ret.query(q, k=4), 12, min_per_doc=1)
    return [h for h in merged if h.score >= MIN_SCORE]


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    live = CONSENT in argv
    probes = json.loads(PROBES.read_text(encoding="utf-8"))["probes"]
    ret = PerDocRetriever(rag.build_corpus())
    plan = []
    print("== probe_gen_refusal (%s) prompt=%s model=%s failover=False ==" % (
        "LIVE" if live else "DRY RUN, zero calls", rag.PROMPT_VERSION, rag.MODEL_NAME))
    for p in probes:
        exp = {d: set(v) for d, v in p["expected"].items()}
        hits = prompt_hits(ret, p["text"])
        inctx = strict_covered(hits, exp) == sum(len(v) for v in exp.values())
        sel = inctx and len(plan) < CAP
        print("  %s %-6s in-context=%-5s ctx=%-2d %s" % (p["id"], p["lang"], inctx, len(hits),
                                                     "SELECTED" if sel else "-"))
        if sel:
            plan.append(p)
    print("\nplanned generation calls: %d (<= %d)" % (len(plan), CAP))
    if not live:
        print("Pass %s to spend them." % CONSENT)
        return 0

    out = ROOT / "scripts" / ("probe_gen_refusal_%s_%s.json"
                              % (rag.PROMPT_VERSION, date.today().isoformat()))
    rows = []
    for n, p in enumerate(plan):
        if n:
            time.sleep(SLEEP_S)
        r = rag.ask(p["text"], retriever=ret, use_llm=True, use_cache=False, failover=False)
        row = {"id": p["id"], "lang": p["lang"], "text": p["text"], "expected": p["expected"],
               "answer": r.get("answer"), "refused": r.get("refused"),
               "refusal_layer": r.get("refusal_layer"), "model_used": r.get("model_used"),
               "llm_error": r.get("llm_error"), "cite_check": r.get("cite_check", []),
               "citations": r.get("citations", [])}
        rows.append(row)
        bad = [c for c in row["cite_check"] if not c.get("number_ok")]
        print("  %s %s  %s" % (p["id"], "PENDING " + row["llm_error"][:60] if row["llm_error"]
                               else ("REFUSED (%s)" % row["refusal_layer"] if row["refused"]
                                     else "answered, %d tags, %d not number_ok"
                                     % (len(row["cite_check"]), len(bad))), ""))
        out.write_text(json.dumps({"date": date.today().isoformat(),
                                   "prompt_version": rag.PROMPT_VERSION,
                                   "model": rag.MODEL_NAME, "rows": rows},
                                  indent=1, ensure_ascii=False), encoding="utf-8")
        if row["llm_error"]:
            print("STOPPED on the first failed call; the row stays PENDING.")
            break
    answered = [r for r in rows if not r["llm_error"]]
    refusals = [r["id"] for r in answered if r["refused"]]
    fab = [r["id"] for r in answered for c in r["cite_check"] if not c.get("number_ok")]
    print("\nanswered %d/%d | LLM-layer refusals with the clause in context: %d %s | "
          "unretrieved tags: %d %s" % (len(answered), len(plan), len(refusals), refusals,
                                       len(fab), fab))
    print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
