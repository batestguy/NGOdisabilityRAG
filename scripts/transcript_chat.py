"""Phase G4 -- multi-turn generation transcript: measures cross-turn citation drift.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\transcript_chat.py
         DRY RUN (the default): the offline half of every turn -- contextualised
         query, gate, excerpt tags -- and the call plan. ZERO calls.
     ... --i-understand-this-spends-quota
         runs it: <= 9 generation calls on rag.MODEL_NAME, checkpointed after each
         SUCCESSFUL call, written to scripts/transcript_chat_<chat prompt>_<date>.json.

WHY (docs/phases/14_generation_eval.md, G0.3 / G4). chat.cross_turn_drift() has
been wired into the UI since Phase 10 C and never measured: drift is a property
of a GENERATED answer, so it costs quota. This is the one run that measures it.

THE SET, fixed here in G0 before any call: three chat_dev conversations (never
chat_test, which stays blind), chosen for the turn classes where re-citing an
earlier turn's evidence is most tempting --
  CD1   direct -> ellipsis -> pronoun      ("so can they fire me?")
  CD3   direct -> pronoun -> topic-shift   (earlier tags stop being current)
  CD10  direct -> ellipsis -> off-corpus-after-legal (a refusal must not re-cite)

EACH TURN IS THE APP'S TURN, not a re-derivation:
  chat.contextualise(prior, text)                 -> retrieval_query
  app.offline_legal_hits(text, ret, retrieval_query=...) -> the excerpts shown
  gate refused -> NO call (the app shows no AI expander on a refused turn)
  rag.ask(text, history=chat.history_for_prompt(prior), retrieval_query=...,
          use_llm=True, use_cache=False, failover=False)
  rag.verify_citations(answer, shown) and chat.cross_turn_drift(answer, prior,
  shown) against THIS turn's shown excerpts -- exactly app._run_ai_turn.
The router is not re-run: every turn in the set is a legal turn by
construction (eval_chat routes and scores them).

NO FAILOVER, on purpose: the judge model (flash-lite) must not generate.
use_cache=False: this is a fresh generation pass; resumability comes from the
checkpoint, which stores completed turns and is refused if the chat prompt
version or the conversation set has changed. The first failed call (quota,
network) STOPS the run -- the row stays PENDING, never faked -- and a later run
resumes from that turn.
"""

import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))  # app.py lives at the repo root

CONVERSATIONS = ("CD1", "CD3", "CD10")
CONSENT = "--i-understand-this-spends-quota"
CHECKPOINT = ROOT / "scripts" / ".transcript_chat_checkpoint.json"
SLEEP_S = 7  # 10/min/model free tier


class _Hit:
    """(doc_id, ref) duck type -- the same shape app._HitRef passes."""

    def __init__(self, doc_id, ref):
        self.doc_id, self.ref = doc_id, ref


def load_set() -> list:
    convs = json.loads((ROOT / "data" / "eval" / "conversations.json")
                       .read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in convs}
    out = [by_id[c] for c in CONVERSATIONS]
    assert all(c["set"] == "chat_dev" for c in out), "chat_test must stay blind"
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    live = CONSENT in argv
    import app  # import-safe by contract (no server)
    import chat
    import rag

    key = {"chat_prompt_version": rag.CHAT_PROMPT_VERSION,
           "prompt_version": rag.PROMPT_VERSION, "model": rag.MODEL_NAME,
           "conversations": list(CONVERSATIONS)}
    done = {}
    if live and CHECKPOINT.exists():
        blob = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        if blob.get("key") != key:
            raise SystemExit("checkpoint key %s != %s -- the prompt or the set "
                             "changed; a transcript must not straddle two systems"
                             % (blob.get("key"), key))
        done = blob["turns"]

    from retrieve import PerDocRetriever
    ret = PerDocRetriever(rag.build_corpus())  # what app.load_retriever caches

    print("== transcript_chat (%s) prompt=%s model=%s failover=False ==" % (
        "LIVE" if live else "DRY RUN, zero calls", rag.CHAT_PROMPT_VERSION, rag.MODEL_NAME))
    calls, stopped, records = 0, None, []
    for conv in load_set():
        prior = []
        for i, turn in enumerate(conv["turns"]):
            tid = "%s.t%d" % (conv["id"], i + 1)
            rq, meta = chat.contextualise(prior, turn["text"])
            view = app.offline_legal_hits(turn["text"], ret, retrieval_query=rq)
            shown = [_Hit(e["doc_id"], e["ref"]) for e in view["excerpts"]]
            rec = {"id": tid, "class": turn["class"], "expect_gate": turn["expect_gate"],
                   "question": turn["text"], "retrieval_query": rq,
                   "carried": bool(meta.get("carried")),
                   "gate_refused": bool(view["refused"]),
                   "shown_tags": [e["tag"] for e in view["excerpts"]],
                   "answer": None, "llm_used": False}
            if tid in done:
                rec = done[tid]
            elif view["refused"]:
                rec["note"] = "gate refused: no AI expander, no call"
            elif not live:
                rec["note"] = "PLANNED CALL"
                calls += 1
            elif stopped is None:
                if calls:
                    time.sleep(SLEEP_S)
                res = rag.ask(turn["text"], retriever=ret, use_llm=True, use_cache=False,
                              failover=False, history=chat.history_for_prompt(prior),
                              retrieval_query=rq or None)
                calls += 1
                ans = res.get("answer")
                rec.update(answer=ans, llm_used=bool(res.get("llm_used")),
                           llm_error=res.get("llm_error"),
                           refusal_layer=res.get("refusal_layer"),
                           model_used=res.get("route", {}).get("model_used"),
                           prompt=res.get("route", {}).get("prompt"),
                           citations=rag.extract_citations(ans or ""),
                           cite_check=rag.verify_citations(ans, shown) if ans else [],
                           drift=chat.cross_turn_drift(ans, prior, shown) if ans else [])
                if ans is None:
                    stopped = "%s: %s" % (tid, rec.get("llm_error"))
                else:
                    done[tid] = rec
                    CHECKPOINT.write_text(json.dumps({"key": key, "turns": done}, indent=1),
                                          encoding="utf-8")
            records.append(rec)
            print("  %-8s %-24s gate=%-7s shown=%-2d %s" % (
                tid, turn["class"], "REFUSED" if rec["gate_refused"] else "pass",
                len(rec["shown_tags"]),
                rec.get("note") or ("drift=%s" % rec.get("drift") if rec.get("answer")
                                    else "PENDING")))
            # What the NEXT turn sees: the user text, the answer (None = pending),
            # and this turn's shown tags -- the set cross_turn_drift calls "earlier".
            prior.append({"question": turn["text"], "answer": rec.get("answer"),
                          "tags": rec["shown_tags"]})

    if not live:
        print("\nplanned generation calls: %d (<= 9). Pass %s to spend them."
              % (calls, CONSENT))
        return 0
    answered = [r for r in records if r.get("answer")]
    drifted = [r["id"] for r in answered if r.get("drift")]
    bad_cites = [r["id"] for r in answered
                 if any(not c.get("number_ok") for c in r.get("cite_check") or [])]
    summary = {"date": date.today().isoformat(), "key": key, "calls_this_run": calls,
               "answered": len(answered), "pending": [r["id"] for r in records
                                                      if not r["gate_refused"]
                                                      and not r.get("answer")],
               "turns_with_drift": drifted, "turns_failing_verify_citations": bad_cites,
               "stopped": stopped}
    out = ROOT / "scripts" / ("transcript_chat_%s_%s.json"
                              % (rag.CHAT_PROMPT_VERSION, date.today().isoformat()))
    out.write_text(json.dumps({"summary": summary, "turns": records}, indent=1),
                   encoding="utf-8")
    print(json.dumps(summary, indent=1))
    print("wrote %s" % out)
    return 1 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
