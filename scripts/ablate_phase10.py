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
#
# ---------------------------------------------------------------------------
# PHASE E1 (2026-09-20) -- THE NO-CUT LADDER, AND WHY POOL WIDTH IS A RED
# HERRING ONCE top_n == 3k.
#
# Phase E's playbook (docs/phases/13_retrieval_quality.md) sized E1 as "widen
# the candidate pool to k=20/doc (60 candidates)" with a separate prompt budget
# of "10-12 chunks, <=4/doc". Measured here, that sizing does not survive:
#
#   k=20 n=12  (the playbook's arm)    test 0.471 = +0.000 vs shipping
#   k=4  n=12  (this ladder)           test 0.529 = +0.058 vs shipping
#
# Both show 12 chunks, so they ARE comparable. The difference is entirely the
# per-doc allocation. When top_n == 3k the budget is spent evenly -- four from
# each doc -- and select_top returns every candidate it was given, so the
# invalid cross-doc cosine comparison never happens. When top_n < 3k the
# leftover slots go to the global top, and the Constitution (2037 of 2134
# chunks) takes them. Read it off the DISPLAYED CHUNKS PER DOC table below --
# the Act's share of displayed chunks goes 36% (ship k=3 n=6) -> 28% (k=10 n=6)
# -> 25% (k=20 n=12), while every top_n == 3k arm holds 33%. And k=10 n=6, the
# arm that widens the pool at an unchanged budget, is the one arm that loses
# recall on ALL THREE sets (0.633/0.473/0.471 -> 0.622/0.453/0.426). That is
# precisely the flooding PerDocRetriever was built to prevent, re-introduced by
# widening; min_per_doc=1 is too weak a guarantee at 30-60 candidates.
#
# CONSEQUENCE, AND IT IS WHAT MAKES E1 CHEAP: a `max_per_doc` ceiling was
# prototyped and is UNNECESSARY. "k=20/doc capped at <=4/doc" is bit-identical
# to plain "k=4/doc, top_n=12" on every cell of every set -- within a doc,
# global score order IS that doc's own order, so taking each doc's best 4 out
# of 20 is taking its best 4 out of 4. The wide pool contributes nothing once
# the allocation is fixed. So E1 ships ONE number (k) and no new select_top
# parameter. Arms `k=8 n=12 cap<=4` and `k=20 n=12 cap<=4` were measured and
# both reproduce `k=4 n=12` exactly; they are not kept here because an arm that
# is provably identical to another is noise in the table.
#
# WHY k=4 AND NOT k=6. frozen-10 and dev plateau at k=5 (0.748 / 0.587); only
# test keeps climbing (0.529 -> 0.559 at k=6). Paying 6 more excerpts of
# screen-reader burden for a gain visible on one set is not a trade this
# project takes -- accessibility is a requirement, not polish (CLAUDE.md). k=6
# is kept in the table as the DECLINED arm, so the next session does not repeat
# the experiment.
#
# NOT A FITTED NUMBER, and the check is in this file's output. An even 4/4/4
# allocation is not the eval set's prior: expected refs run ~50% Act / ~20%
# Constitution / ~30% Factsheet (frozen 59/8/33, dev 50/25/25, test 47/15/38).
# The even split therefore UNDER-serves the Act, which owns half the answers --
# the gain was not bought by matching the set's shape. And it replicates on
# test (+0.058), which has never been tuned against.
# ---------------------------------------------------------------------------
ARMS = [
    ("ship  k=3  n=6   (today)", 3, 6),
    ("      k=3  n=12", 3, 12),
    ("      k=10 n=6", 10, 6),
    ("  B?  k=10 n=12", 10, 12),
    ("      k=10 n=30  (no cut)", 10, 30),
    ("      k=20 n=12", 20, 12),
    ("      k=20 n=60  (no cut)", 20, 60),
    # --- E1's no-cut ladder: top_n == 3k, so nothing retrieved is discarded ---
    ("  E1  k=4  n=12  (CHOSEN)", 4, 12),
    ("      k=5  n=15", 5, 15),
    ("      k=6  n=18  (declined)", 6, 18),
]

LABELS = {
    "frozen10": "frozen-10 (fitted on)",
    "heldout": "dev (ex-held-out)",
    "test": "test (clean)",
}


def measure(ret, rows, k, top_n) -> dict:
    """Mean recall / recall_strict / shown / false refusals for one arm.

    `mix` counts displayed chunks per doc across the whole set. It is what makes
    the Constitution-flooding claim in the ARMS comment readable from output
    rather than asserted in prose: compare `k=20 n=6` against `k=3 n=6` and the
    Act loses slots the Constitution gains.
    """
    recs, strs, shown, false_ref = [], [], [], 0
    mix = {"act2018": 0, "constitution1999": 0, "factsheet2020": 0}
    for row in rows:
        hits = select_top(ret.query(row["text"], k=k), top_n,
                          min_per_doc=MIN_PER_DOC)
        shown.append(len(hits))
        for h in hits:
            if h.doc_id in mix:
                mix[h.doc_id] += 1
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
        "mix": mix,
    }


def fmt(v) -> str:
    return "n/a" if v is None else "%.3f" % v


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # EQUALS FORM ONLY (repo convention: the space form is silently ignored).
    corpus = next((a.split("=", 1)[1] for a in argv
                   if a.startswith("--corpus=")), None)

    rows = load_eval_set()
    by_set = {s: [r for r in rows if r["set"] == s] for s in LABELS}
    docs = build_corpus(corpus)
    verify_expected(rows, docs)
    ret = PerDocRetriever(docs)

    print("== PHASE 10 WIDTH ABLATION (CORPUS_VERSION=%s, MIN_SCORE=%.2f) =="
          % (corpus or CORPUS_VERSION, MIN_SCORE))
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

    # ---- WHERE THE BUDGET GOES (the flooding claim, from output) ---------
    # An arm's recall cannot be read without knowing which doc spent its slots.
    # k=20 n=6 vs k=3 n=6 is the pair to look at: same budget, wider pool, and
    # the Act's share falls while the Constitution's rises.
    print("\n== DISPLAYED CHUNKS PER DOC (all sets pooled) ==")
    print("  %-28s %-7s %-7s %-7s %s" % (
        "arm", "act", "const", "factsh", "act share"))
    for label, k, top_n in ARMS:
        r = results[(label, k, top_n)]
        tot = {d: sum(r[s]["mix"][d] for s in LABELS)
               for d in ("act2018", "constitution1999", "factsheet2020")}
        n = sum(tot.values()) or 1
        print("  %-28s %-7d %-7d %-7d %.0f%%" % (
            label, tot["act2018"], tot["constitution1999"],
            tot["factsheet2020"], 100 * tot["act2018"] / n))
    print("  Widening the pool WITHOUT fixing the allocation spends the extra")
    print("  slots on the Constitution (2037 of 2134 chunks). top_n == 3k is")
    print("  what stops that, and it needs no max_per_doc ceiling.")

    # ---- IS AN EVEN SPLIT JUST THIS SET'S PRIOR? ------------------------
    # Asked because every top_n == 3k arm allocates evenly, and an even split
    # that happened to match the eval set's own doc distribution would be a
    # free win rather than a real one. It does not match: the Act owns about
    # half the expected refs and gets a third of the slots.
    print("\n== EXPECTED-REF DOC DISTRIBUTION (prior check, not a gate) ==")
    for s in LABELS:
        tally = {}
        for row in by_set[s]:
            for d, ns in row["expected"].items():
                tally[d] = tally.get(d, 0) + len(ns)
        tot = sum(tally.values()) or 1
        print("  %-28s %s  (n_refs=%d)" % (
            LABELS[s], "  ".join("%s %d (%.0f%%)" % (d[:5], c, 100 * c / tot)
                                 for d, c in sorted(tally.items())), tot))
    print("  Nowhere near 33/33/33, so the even 4/4/4 allocation UNDER-serves")
    print("  the Act -- the E1 gain was not bought by matching this shape.")

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
