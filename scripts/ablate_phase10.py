"""Phase 10 ablation harness -- width arms now, dense/synonym arms in Phase D.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\ablate_phase10.py  (from D:\\NGORAG)
     ... --reveal-test    print per-question test detail (SPENDS THE SET)

WHAT THIS IS FOR
----------------
Phase 09 step 3 was planned on a diagnostic that compared arms at DIFFERENT
widths and read the difference as an ordering win. It was not: 0.460 / 0.627 /
0.700 / 0.773 were measured while showing 9, 18, 30 and 60 chunks. Every arm
here therefore declares, in its own row, how many chunks it SHOWS -- because
two arms showing different numbers of chunks are not comparable, and that
single omission cost a whole milestone.

Each arm is (k_per_doc, top_n). recall and recall_strict are both reported;
only recall_strict survives the Phase C corpus rebuild.

EXIT CODE POLICY
----------------
This script measures; it does not gate. It exits nonzero only if ground-truth
verification fails or an arm breaks refusal invariance on an answerable
question (a false refusal introduced by a width change is a real regression,
not a metric). A disappointing recall number is the finding.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from evalset import (  # noqa: E402
    load_eval_set,
    ref_nums,
    strict_covered,
    verify_expected,
)
from rag import CORPUS_VERSION, build_corpus  # noqa: E402
from retrieve import MIN_SCORE, PerDocRetriever, select_top  # noqa: E402

MIN_PER_DOC = 1

# (label, k_per_doc, top_n). The shipping arm is first and is the reference.
#
# Arms are chosen to separate the two budgets Phase 10 B wants to split:
# how WIDE the candidate pool is (k) and how many chunks reach the prompt
# (top_n). The k=3/top_n=12 arm is the one that isolates top_n, because k=3
# only yields 9 candidates -- it shows that asking for 12 cannot invent
# candidates the pool never had.
ARMS = [
    ("ship  k=3  n=6   (today)", 3, 6),
    ("      k=3  n=12", 3, 12),
    ("      k=10 n=6", 10, 6),
    ("  B?  k=10 n=12", 10, 12),
    ("      k=10 n=30  (no cut)", 10, 30),
    ("      k=20 n=12", 20, 12),
    ("      k=20 n=60  (no cut)", 20, 60),
]

LABELS = {
    "frozen10": "frozen-10 (fitted on)",
    "heldout": "dev (ex-held-out)",
    "test": "test (clean)",
}


def measure(ret, rows, k, top_n) -> dict:
    """Mean recall / recall_strict / shown / false refusals for one arm."""
    recs, strs, shown, false_ref = [], [], [], 0
    for row in rows:
        hits = select_top(ret.query(row["text"], k=k), top_n,
                          min_per_doc=MIN_PER_DOC)
        shown.append(len(hits))
        kept = [h for h in hits if h.score >= MIN_SCORE]
        if row["expect_gate"] == "answer" and not kept:
            false_ref += 1
        exp = row["expected"]
        if not exp:
            continue
        exp_pairs = {(d, n) for d, ns in exp.items() for n in ns}
        got = {(h.doc_id, n) for h in hits for n in ref_nums(h.ref)}
        recs.append(len(exp_pairs & got) / len(exp_pairs))
        strs.append(strict_covered(hits, exp) / len(exp_pairs))
    n_ans = sum(1 for r in rows if r["expect_gate"] == "answer")
    return {
        "recall": sum(recs) / len(recs) if recs else None,
        "strict": sum(strs) / len(strs) if strs else None,
        "shown_med": sorted(shown)[len(shown) // 2] if shown else 0,
        "shown_max": max(shown) if shown else 0,
        "false_ref": false_ref,
        "n_ans": n_ans,
    }


def fmt(v) -> str:
    return "n/a" if v is None else "%.3f" % v


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    rows = load_eval_set()
    by_set = {s: [r for r in rows if r["set"] == s] for s in LABELS}
    docs = build_corpus()
    verify_expected(rows, docs)
    ret = PerDocRetriever(docs)

    print("== PHASE 10 WIDTH ABLATION (CORPUS_VERSION=%s, MIN_SCORE=%.2f) =="
          % (CORPUS_VERSION, MIN_SCORE))
    print("  Every arm declares how many chunks it SHOWS. Two arms showing")
    print("  different counts are NOT comparable -- omitting that is exactly")
    print("  what produced the falsified Phase 09 step 3 plan.")

    results = {}
    for label, k, top_n in ARMS:
        results[(label, k, top_n)] = {
            s: measure(ret, by_set[s], k, top_n) for s in LABELS}

    for metric, title in (("recall", "RECALL (plain -- v1 only, packed-ref subsidised)"),
                          ("strict", "RECALL_STRICT (survives the v2 rebuild)")):
        print("\n== %s ==" % title)
        print("  %-28s %-9s %-9s %-9s %-7s %s" % (
            "arm", "frozen10", "dev", "test", "shown", "false-refusals"))
        for label, k, top_n in ARMS:
            r = results[(label, k, top_n)]
            fr = "/".join("%d" % r[s]["false_ref"] for s in LABELS)
            print("  %-28s %-9s %-9s %-9s %-7s %s" % (
                label, fmt(r["frozen10"][metric]), fmt(r["heldout"][metric]),
                fmt(r["test"][metric]),
                "%d-%d" % (min(r[s]["shown_med"] for s in LABELS),
                           max(r[s]["shown_max"] for s in LABELS)),
                fr if fr != "0/0/0" else "none"))
        base = results[(ARMS[0][0], ARMS[0][1], ARMS[0][2])]
        print("  deltas vs the shipping arm, test set:")
        for label, k, top_n in ARMS[1:]:
            a, b = results[(label, k, top_n)]["test"][metric], base["test"][metric]
            if a is not None and b is not None:
                print("    %-28s %+.3f" % (label, a - b))

    # ---- the only failure condition -------------------------------------
    print("\n== REFUSAL INVARIANCE (the only thing that can fail here) ==")
    bad = []
    for label, k, top_n in ARMS:
        r = results[(label, k, top_n)]
        tot = sum(r[s]["false_ref"] for s in LABELS)
        n = sum(r[s]["n_ans"] for s in LABELS)
        print("  %-28s %d/%d answerable questions retrieve NOTHING"
              % (label, tot, n))
        if tot:
            bad.append("%s: %d false refusals" % (label, tot))
    print("  A width change must never deny an answerable question. False")
    print("  refusals deny help to PWDs (CLAUDE.md); that is a regression, not")
    print("  a metric to trade off.")
    if bad:
        print("\nABLATE_PHASE10: FAIL")
        for b in bad:
            print("  - %s" % b)
        return 1
    print("\nABLATE_PHASE10: PASS (arms measured; recall numbers are findings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
