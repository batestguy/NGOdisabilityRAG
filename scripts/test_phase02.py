"""Phase 02 end-to-end test: SAME 10 questions as bench_phase01 through ask().

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts/test_phase02.py [--no-llm] [--out FILE]
  --no-llm : TF-IDF-only dry run (no network; LLM rows stay pending=None).
  --out    : results path (default scripts/test_phase02_results.json).
             RULE (review 2026-09-08): LLM runs go to VERSIONED files
             (test_phase02_results_<prompt>_<date>.json); a --no-llm dry
             run must never overwrite an LLM transcript -- pass --out.

Per question records: prompt version, resolved model, top chunks + scores,
refused?, answer excerpt, mechanical cite check; the MANUAL verdict
(correct cite? hallucinated sections?) is done by reading answers vs chunks.
Ends with the refusal demo: one same-vocabulary off-corpus query (passes the
TF-IDF floor, must be refused by the LLM no-answer layer) + one generic
off-corpus query. Sleeps between LLM calls (free-tier rate limits).
Writes results JSON to scripts/test_phase02_results.json. Never fakes LLM
output: LLM-backed rows are 'pending' when quota/key fails.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from bench_phase01 import load_questions  # noqa: E402 -- SAME 10Q set
from rag import (  # noqa: E402
    MODEL_NAME,
    PROMPT_VERSION,
    REFUSAL_MESSAGE,
    ask,
    build_corpus,
)
from retrieve import MIN_SCORE, PerDocRetriever  # noqa: E402

SLEEP_S = 6  # free-tier rate-limit spacing between LLM calls
OFF_CORPUS_SAME_VOCAB = "What does the Act say about maritime shipping insurance?"
OFF_CORPUS_GENERIC = "How do I bake sourdough bread?"


def one_line(s: str, n: int = 220) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n] + "..."


def run_question(ret: PerDocRetriever, q: str, use_llm: bool) -> dict:
    res = ask(q, retriever=ret, use_llm=use_llm)
    rec = {
        "question": q,
        "model": res["route"]["model"],
        "prompt": res["route"]["prompt"],
        "min_score": res["route"]["min_score"],
        "scores": res["scores"],
        "refused": res["refused"],
        "refusal_layer": res.get("refusal_layer", "gate" if res["refused"] else None),
        "llm_used": res["llm_used"],
        # The answer cache is a quota saver, never evidence. A warm cache would
        # otherwise let a REPLAYED answer land in a versioned transcript looking
        # exactly like a fresh generation -- retrieval and prompt building are
        # deterministic, so the replay is invisible downstream. Persisting the
        # flag is what makes "never fake an LLM row" true in the durable record
        # and not just in ask()'s in-memory return value.
        "cached": res.get("cached"),
        "llm_error": res.get("llm_error"),
        "citations": res["citations"],
        "cite_check": res.get("cite_check"),
        "answer_excerpt": one_line(res["answer"], 600) if res["answer"] else None,
        "answer_full": res["answer"],
    }
    return rec


def main() -> None:
    use_llm = "--no-llm" not in sys.argv
    questions = load_questions()
    assert len(questions) == 10, "expected 10 questions, got %d" % len(questions)
    print("model=%s prompt=%s min_score=%.2f llm=%s" % (
        MODEL_NAME, PROMPT_VERSION, MIN_SCORE, use_llm))
    print("Q9=%r" % questions[8])

    docs = build_corpus()
    print("corpus: %s" % {k: len(v) for k, v in docs.items()})
    ret = PerDocRetriever(docs)

    records = []
    for i, q in enumerate(questions, 1):
        rec = run_question(ret, q, use_llm)
        rec["id"] = "Q%d" % i
        records.append(rec)
        top = rec["scores"][0] if rec["scores"] else {}
        print("Q%-3d top=%.3f %s/%s refused=%s cites=%s err=%s" % (
            i, top.get("score", -1), top.get("doc_id"), top.get("ref"),
            rec["refused"], rec["citations"], rec["llm_error"]))
        print("      A: %s" % (rec["answer_excerpt"] or "PENDING (no LLM)"))
        if use_llm and i < 10:
            time.sleep(SLEEP_S)

    print("\n== REFUSAL DEMO ==")
    if use_llm:
        time.sleep(SLEEP_S)
    demo_vocab = run_question(ret, OFF_CORPUS_SAME_VOCAB, use_llm)
    demo_vocab["id"] = "R1-same-vocab"
    if use_llm:
        time.sleep(SLEEP_S)
    demo_generic = run_question(ret, OFF_CORPUS_GENERIC, use_llm)
    demo_generic["id"] = "R2-generic"
    for d in (demo_vocab, demo_generic):
        records.append(d)
        print("%s refused=%s layer=%s llm=%s" % (
            d["id"], d["refused"], d["refusal_layer"], d["llm_used"]))
        print("  scores=%s" % [(s["score"], s["doc_id"], s["ref"]) for s in d["scores"]])
        print("  A: %s" % (d["answer_excerpt"] or "PENDING (no LLM)"))
        if d["refused"] and d["answer_full"] != REFUSAL_MESSAGE:
            print("  !! refusal text is NOT the fixed message -- investigate")

    out = ROOT / "scripts" / "test_phase02_results.json"
    for a in sys.argv[1:]:
        if a.startswith("--out="):
            out = Path(a[len("--out="):])
            if not out.is_absolute():
                out = ROOT / out
    out.write_text(json.dumps(records, indent=1), encoding="utf-8")
    print("\nwrote %s (%d records)" % (out, len(records)))


if __name__ == "__main__":
    main()
