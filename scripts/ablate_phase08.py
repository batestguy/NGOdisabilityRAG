"""Phase 08 ablation harness -- retrieval-only, zero quota, zero LLM.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\ablate_phase08.py   (from D:\\NGORAG)

Answers the one question every Phase 08 PR body has to answer: what did this
step do to RETRIEVAL, measured on the frozen 10Q set, with everything else held
identical?

It deliberately does NOT touch answers or the LLM. eval_phase06.py is the full
picture (it re-scores the frozen transcript); this is the fast inner loop that
isolates the retrieval half, so a synonym-map edit can be judged in ~20s
without re-reading a transcript whose answers did not change.

Reuse, not reimplementation:
  - questions   <- bench_phase01.load_questions()  (the single frozen 10Q source)
  - ground truth<- eval_phase06.EXPECTED           (corpus-verified, never from answers)
  - recall      <- same (doc, ref-number) pair definition as eval_phase06
so the numbers printed here are directly comparable to the eval's recall column.

The ablation is done by swapping retrieve.expand_query for the identity
function, which is exactly what "before" means: the map absent, the index and
the MIN_SCORE calibration unchanged.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import retrieve  # noqa: E402
from bench_phase01 import load_questions  # noqa: E402 (SAME 10Q set)
from eval_phase06 import EXPECTED, ref_nums  # noqa: E402 (SAME ground truth)
from rag import build_corpus  # noqa: E402
from retrieve import MIN_SCORE, PerDocRetriever  # noqa: E402

K_PER_DOC = 3   # ask() / eval_phase06 depth
TOP_N = 6       # ask() / eval_phase06 merge width


def measure(ret, questions, expand: bool) -> list[dict]:
    """Per-question recall + score profile with expansion on or off."""
    real = retrieve.expand_query
    if not expand:
        retrieve.expand_query = lambda q: q
    try:
        rows = []
        for i, q in enumerate(questions):
            qid = "Q%d" % (i + 1)
            hits = ret.query(q, k=K_PER_DOC)[:TOP_N]
            exp = EXPECTED[qid]
            exp_pairs = {(d, n) for d, ns in exp.items() for n in ns}
            ret_pairs = {(h.doc_id, n) for h in hits for n in ref_nums(h.ref)}
            kept = [h for h in hits if h.score >= MIN_SCORE]
            rows.append({
                "id": qid,
                "recall": len(exp_pairs & ret_pairs) / len(exp_pairs),
                "top": hits[0].score if hits else 0.0,
                # The floor is a REFUSAL gate: if nothing clears it the user is
                # declined. Expansion must never push a good question under it.
                "n_kept": len(kept),
                "docs": "".join(sorted({h.doc_id[0] for h in kept})),
                "missed": sorted("%s:%s" % p for p in exp_pairs - ret_pairs),
            })
        return rows
    finally:
        retrieve.expand_query = real


def main() -> None:
    questions = load_questions()
    assert len(questions) == 10
    docs = build_corpus()
    print("corpus: %s" % {k: len(v) for k, v in docs.items()})
    # ONE retriever for both arms: the index is identical by construction, so
    # any delta below is attributable to the query side and nothing else.
    ret = PerDocRetriever(docs)

    before = {r["id"]: r for r in measure(ret, questions, expand=False)}
    after = {r["id"]: r for r in measure(ret, questions, expand=True)}

    print("\n== EXPANSION FIRED (query -> appended terms) ==")
    for i, q in enumerate(questions):
        ex = retrieve.expand_query(q)
        added = ex[len(q):].strip()
        print("  Q%-3d %s" % (i + 1, added if added else "(no expansion)"))

    print("\n== RETRIEVAL ABLATION (k=%d/doc, top_n=%d, MIN_SCORE=%.2f) =="
          % (K_PER_DOC, TOP_N, MIN_SCORE))
    print("  %-4s %-16s %-16s %-7s %s" % (
        "id", "recall before", "recall after", "delta", "still-missed (after)"))
    for i in range(len(questions)):
        qid = "Q%d" % (i + 1)
        b, a = before[qid], after[qid]
        d = a["recall"] - b["recall"]
        print("  %-4s %-16.3f %-16.3f %-+7.3f %s" % (
            qid, b["recall"], a["recall"], d, ",".join(a["missed"]) or "-"))

    mb = sum(r["recall"] for r in before.values()) / len(before)
    ma = sum(r["recall"] for r in after.values()) / len(after)
    print("  %-4s %-16.3f %-16.3f %-+7.3f" % ("MEAN", mb, ma, ma - mb))
    print("  gate recall>0.75: before %s, after %s"
          % ("PASS" if mb > 0.75 else "FAIL", "PASS" if ma > 0.75 else "FAIL"))

    print("\n== REFUSAL-FLOOR SAFETY (hits surviving MIN_SCORE) ==")
    print("  Expansion must not starve a good question below the floor.")
    bad = []
    for i in range(len(questions)):
        qid = "Q%d" % (i + 1)
        b, a = before[qid], after[qid]
        flag = "" if a["n_kept"] else "  <-- WOULD NOW REFUSE"
        if not a["n_kept"]:
            bad.append(qid)
        print("  %-4s kept %d->%-2d  top %.4f->%.4f  docs %s->%s%s" % (
            qid, b["n_kept"], a["n_kept"], b["top"], a["top"],
            b["docs"] or "-", a["docs"] or "-", flag))
    print("  refusal regressions: %s" % (", ".join(bad) if bad else "none"))


if __name__ == "__main__":
    main()
