"""Frozen / dev / test retrieval baselines -- zero LLM, zero quota, zero network.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\eval_heldout.py   (from D:\\NGORAG)
     ... --reveal-test        (see the TEST-SET PROTECTION note below)

WHAT THIS IS FOR
----------------
recall 0.925 was measured on the same 10 questions the synonym map was fitted
to: an `education` key was deleted because it cost Q7, others kept because they
lifted Q5/Q8/Q9. With n=10 one question is worth 10 points, so that number
cannot tell generalisation from memorisation. This harness measures the same
retrieval on questions NOTHING has been tuned on, and always prints every set
side by side. The gap -- whatever its sign -- is the finding.

THREE SETS, AND WHY THE MIDDLE ONE CHANGED MEANING (2026-09-13)
---------------------------------------------------------------
  frozen10          the historical yardstick, fitted on. Regression tripwire.
  heldout = DEV     30 questions, first measured 0.420. The owner then read
                    their per-question misses to design the Phase 09 step 3
                    retrieval fix, which spent them: they are now a DEV set.
                    Still reported, still frozen, no longer clean.
  test              ~20 questions authored AFTER that inspection and BEFORE
                    any retrieval change, from the corpus only. The clean one.
The file name is kept as eval_heldout.py deliberately -- renaming it would
break every doc, PR body and journal entry that points at it. See the header of
scripts/evalset.py for the full argument.

TEST-SET PROTECTION
-------------------
The `test` per-question MISSED-REFS column is withheld by default. Knowing
which refs a clean set misses is exactly the knowledge that turns it into a dev
set -- that is how the 30 were spent. Recall, precision, gate and class means
are always printed in full, so the number is never hidden; only the tuning
handle is. `--reveal-test` prints it and says plainly what it costs.

WHAT IT DELIBERATELY DOES NOT MEASURE
-------------------------------------
Neither the dev nor the test set has an answer transcript, so faithfulness, coverage and
reverse_rel are STRUCTURALLY UNAVAILABLE without spending quota: each needs a
generated answer to score. They are omitted rather than approximated. This is
the retrieval half only, and it says so everywhere it prints a number.

Reuse, not reimplementation (modelled on ablate_phase08.py, which already does
this shape of work):
  - k=3/doc, top_n=6              -- ask() / eval_phase06 / ablate depth
  - recall = (doc, ref-number) pairs found / expected, the SAME definition
    eval_phase06 uses, so held-out recall is directly comparable to the eval's
    recall column rather than merely similar-looking
  - ground truth <- data/eval/questions.json, corpus-verified at runtime

FOUR METRICS, AND WHICH ONE SURVIVES A CORPUS REBUILD (Phase 10 A)
------------------------------------------------------------------
  recall         pair-set overlap. The historical number. NOT comparable
                 across corpus versions: a chunk reffed `cl. 16,17` satisfies
                 two expected refs from one slot, and 16/62 Act chunks carry
                 such packed refs. Corpus v2 splits them, so v2 scores lower
                 at identical quality.
  recall_strict  same, but each retrieved chunk may satisfy at most ONE
                 expected ref (maximum bipartite matching, see
                 evalset.strict_covered). THIS is the v1 -> v2 migration
                 metric, and it is published here before v2 exists so that
                 correct v2 work cannot read as a regression.
  recall@k       one wide pool (k=20/doc -> 60 candidates) read at prefix
                 depths 3/6/10/20/60. Separates "the chunk is ranked too low"
                 from "the chunk is not there", which is the exact question
                 the falsified Phase 09 step 3 plan answered by accident.
                 Its @6 column is NOT the shipping number -- see K_CURVE.
  MRR / rank     rank_of_first_expected in that pool, and 1/rank. Tells you
                 how far a re-ranker would have to lift a miss.

Every table is stamped with CORPUS_VERSION. A recall number in this project's
history that lacks that stamp is a v1 number.

EXIT CODE POLICY (this is a deliberate design decision, not laxity)
-------------------------------------------------------------------
Nonzero ONLY for:
  - ground-truth verification failure (an expected number no chunk carries --
    a bug in the question set, not a measurement), or
  - a FROZEN-10 recall regression below the recorded baseline.
NEVER for a dev or test number. A harness that failed when they looked bad
would create pressure to tune them, which is precisely the contamination this
file exists to prevent. Dev and test numbers are reported whatever they say.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from evalset import (  # noqa: E402
    assert_frozen10_matches_notebook,
    load_eval_set,
    ref_nums,
    strict_covered,
    verify_expected,
)
from rag import CORPUS_VERSION, build_corpus  # noqa: E402
from retrieve import MIN_SCORE, PerDocRetriever, select_top  # noqa: E402

K_PER_DOC = 3   # ask() / eval_phase06 / ablate_phase08 depth
TOP_N = 6       # ask() / eval_phase06 / ablate_phase08 merge width
MIN_PER_DOC = 1  # ask() default -- the doc-quota merge, Phase 09 step 3 M2

# ---- the recall@k curve (Phase 10 A) -------------------------------------
# One wide pool, measured at prefix depths. K_CURVE=20/doc gives 60 candidates,
# which is the deepest arm in the Phase 09 falsification table, so the curve's
# last point is directly comparable to the 0.765 recorded there.
#
# READ THIS BEFORE QUOTING recall@6 FROM THE CURVE. It is NOT the shipping
# number. The shipping arm is k=3/doc -> select_top(6); the curve is
# k=20/doc -> select_top(60) sliced at 6. Those differ, and the difference is
# the whole point of Phase 09's finding: a wider pool at a fixed cut of 6 is
# neutral-to-HARMFUL (k=10 pool + [:6] dropped frozen-10 from 0.925 to 0.867),
# because wider retrieval floods the cut with near-misses. The headline table
# stays on the shipping arm. The curve answers a different question -- "is the
# right chunk in the pool at all, and how deep?" -- and its answer is what
# makes Phase 10 D a re-ranking problem with a measured ceiling rather than a
# hope. Not having this curve is what let the falsified plan confuse ranking
# with width.
K_CURVE = 20
CURVE_DEPTHS = (3, 6, 10, 20, 60)

# Recorded frozen-10 mean recall: Phase 08 M1 (synonym map), confirmed by
# eval_phase06.py on 2026-09-13 and by docs/phases/06_ragas_eval.md. The guard
# is a REGRESSION tripwire on the frozen set only -- this harness must never be
# able to report a held-out baseline while the frozen yardstick has silently
# moved underneath it.
#
# _V1 SUFFIX (Phase 10 A): this number is a property of CORPUS v1, not of the
# retriever. Corpus v2 splits packed refs, so plain recall moves for reasons
# that have nothing to do with retrieval quality and this guard would fire on
# correct work. When v2 lands, the v2 guard is a SEPARATE constant compared
# against recall_strict, and this one keeps guarding v1. Renaming it now, while
# v1 is the only corpus, is what stops the two being silently conflated later.
FROZEN10_RECALL_BASELINE_V1 = 0.925
EPS = 1e-6


def measure_one(ret, row: dict) -> dict:
    """Retrieval profile for one question. No LLM, no answer, no generation."""
    # select_top, not [:TOP_N] -- the same merge ask() ships.
    hits = select_top(ret.query(row["text"], k=K_PER_DOC), TOP_N,
                      min_per_doc=MIN_PER_DOC)
    kept = [h for h in hits if h.score >= MIN_SCORE]
    exp = row["expected"]
    exp_pairs = {(d, n) for d, ns in exp.items() for n in ns}
    ret_pairs = {(h.doc_id, n) for h in hits for n in ref_nums(h.ref)}
    rel_hits = sum(1 for h in hits if ref_nums(h.ref) & exp.get(h.doc_id, set()))
    return {
        "id": row["id"],
        "set": row["set"],
        "class": row["class"],
        "expect_gate": row["expect_gate"],
        # Off-corpus rows expect nothing, so recall/precision are undefined
        # rather than zero. Scoring them 0.0 would drag the mean down with a
        # number that has no meaning.
        #
        # RECALL is identical to eval_phase06.eval_question() -- same pair-set
        # construction, same k/top_n -- which is what makes the frozen-vs-
        # held-out comparison legitimate. PRECISION is NOT directly comparable:
        # the eval scores a refused row 0.0 (eval_phase06.py:170) where this
        # returns None. Only recall was ever claimed comparable; do not quote
        # the two precision columns against each other.
        "recall": (len(exp_pairs & ret_pairs) / len(exp_pairs)
                   if exp_pairs else None),
        # recall_strict: one expected ref per chunk, max. See
        # evalset.strict_covered for why plain recall cannot survive the
        # Phase 10 C rebuild as a comparison metric. On v1 the two differ only
        # where a packed ref ('cl. 16,17') is retrieved against >=2 expected
        # numbers, so the gap between these columns IS the packed-ref subsidy
        # that v2 removes -- publish it now or v2 reads as regression.
        "recall_strict": (strict_covered(hits, exp) / len(exp_pairs)
                          if exp_pairs else None),
        "precision": (rel_hits / len(hits)) if (hits and exp_pairs) else None,
        "top": hits[0].score if hits else 0.0,
        # n_kept is the REFUSAL gate: zero kept hits means the user is declined.
        "n_kept": len(kept),
        "missed": sorted("%s:%s" % p for p in exp_pairs - ret_pairs),
    }


def measure_curve(ret, row: dict) -> dict:
    """recall@{3,6,10,20,60}, rank_of_first_expected and RR from ONE wide pool.

    Retrieves k=K_CURVE per doc, merges with the shipping select_top, then reads
    prefixes of that single ordering. One retrieval, not five, so every depth
    scores the same candidate list in the same order and the curve is monotone
    by construction -- a non-monotone curve would mean a bug, which is a useful
    thing to be able to assert.

    `rank_of_first_expected` is the 1-based position of the first chunk
    carrying any expected (doc, number) pair, or None if the pool never
    contains one. RR is 1/rank, scored 0.0 when absent, so MRR = mean(RR) is
    defined over answerable questions rather than silently over a subset.
    """
    exp = row["expected"]
    exp_pairs = {(d, n) for d, ns in exp.items() for n in ns}
    pool = select_top(ret.query(row["text"], k=K_CURVE),
                      max(CURVE_DEPTHS), min_per_doc=MIN_PER_DOC)
    if not exp_pairs:
        return {"id": row["id"], "set": row["set"], "class": row["class"],
                "expect_gate": row["expect_gate"], "n_pool": len(pool),
                "rank": None, "rr": None,
                **{"r@%d" % d: None for d in CURVE_DEPTHS},
                **{"rs@%d" % d: None for d in CURVE_DEPTHS}}
    out = {"id": row["id"], "set": row["set"], "class": row["class"],
           "expect_gate": row["expect_gate"], "n_pool": len(pool)}
    for d in CURVE_DEPTHS:
        pre = pool[:d]
        got = {(h.doc_id, n) for h in pre for n in ref_nums(h.ref)}
        out["r@%d" % d] = len(exp_pairs & got) / len(exp_pairs)
        out["rs@%d" % d] = strict_covered(pre, exp) / len(exp_pairs)
    rank = next((i + 1 for i, h in enumerate(pool)
                 if ref_nums(h.ref) & exp.get(h.doc_id, set())), None)
    out["rank"] = rank
    out["rr"] = (1.0 / rank) if rank else 0.0
    return out


def mean(vals) -> float | None:
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def fmt(v, spec: str = "%.3f") -> str:
    return "n/a" if v is None else spec % v


# Display labels. The `set` strings in questions.json are NOT renamed -- the
# 0.420 baseline published in STATUS.md, the playbook and LEARNING_JOURNAL.md
# is a "heldout" number, and renaming the key would silently break that link.
# The relabelling is presentation only, and it says what happened.
LABELS = {
    "frozen10": "frozen-10 (fitted on)",
    "heldout": "dev (ex-held-out, inspected 2026-09-13)",
    "test": "test (clean, never tuned against)",
}


def per_question_table(label: str, rows: list[dict], show_missed: bool) -> None:
    print("\n== %s, PER QUESTION (corpus=%s, k=%d/doc, top_n=%d, MIN_SCORE=%.2f) =="
          % (label.upper(), CORPUS_VERSION, K_PER_DOC, TOP_N, MIN_SCORE))
    print("  retrieval only -- no answers exist for this set, so faithfulness /")
    print("  coverage / reverse_rel are structurally unavailable without quota.")
    print("  %-6s %-16s %-7s %-7s %-7s %-7s %-6s %s" % (
        "id", "class", "gate", "recall", "strict", "prec", "kept",
        "still-missed"))
    for r in rows:
        flag = ""
        if r["expect_gate"] == "answer" and r["n_kept"] == 0:
            flag = "  <-- FALSE REFUSAL"
        elif r["expect_gate"] == "refuse" and r["n_kept"] > 0:
            flag = "  <-- cleared the floor"
        missed = (",".join(r["missed"]) or "-") if show_missed else "(withheld)"
        print("  %-6s %-16s %-7s %-7s %-7s %-7s %-6d %s%s" % (
            r["id"], r["class"], r["expect_gate"], fmt(r["recall"]),
            fmt(r["recall_strict"]), fmt(r["precision"]), r["n_kept"],
            missed, flag))


def class_table(label: str, rows: list[dict]) -> None:
    print("\n== MEANS BY CLASS (%s) ==" % label)
    print("  %-16s %-5s %-8s %-8s %-8s %s" % (
        "class", "n", "recall", "strict", "prec", "kept=0"))
    for cls in sorted({r["class"] for r in rows}):
        sub = [r for r in rows if r["class"] == cls]
        zero = sum(1 for r in sub if r["n_kept"] == 0)
        print("  %-16s %-5d %-8s %-8s %-8s %d/%d" % (
            cls, len(sub), fmt(mean(r["recall"] for r in sub)),
            fmt(mean(r["recall_strict"] for r in sub)),
            fmt(mean(r["precision"] for r in sub)), zero, len(sub)))


def curve_table(curves: dict) -> None:
    """The @k curve, every set, plus MRR and the rank distribution."""
    print("\n== RECALL@K CURVE (pool k=%d/doc -> %d candidates, select_top order) =="
          % (K_CURVE, max(CURVE_DEPTHS)))
    print("  NOT the shipping arm. Shipping is k=%d/doc -> top_n=%d and is"
          % (K_PER_DOC, TOP_N))
    print("  reported in the headline block below. This answers a DIFFERENT")
    print("  question: is the right chunk in the pool at all, and how deep?")
    print("  A large gap between @%d and @%d means the miss is RANKING, and a"
          % (CURVE_DEPTHS[1], CURVE_DEPTHS[-1]))
    print("  re-ranker can reach it. A flat curve would mean the chunk is")
    print("  simply absent, and only a corpus or encoder change could help.")
    hdr = "  %-40s" % "set"
    for d in CURVE_DEPTHS:
        hdr += " %-7s" % ("r@%d" % d)
    print(hdr + " %-7s %-7s %s" % ("MRR", "med-rk", "found"))
    for s in LABELS:
        rows = [r for r in curves[s] if r["rr"] is not None]
        if not rows:
            continue
        line = "  %-40s" % LABELS[s]
        for d in CURVE_DEPTHS:
            line += " %-7s" % fmt(mean(r["r@%d" % d] for r in rows))
        ranks = sorted(r["rank"] for r in rows if r["rank"])
        med = ranks[len(ranks) // 2] if ranks else None
        print(line + " %-7s %-7s %d/%d" % (
            fmt(mean(r["rr"] for r in rows)),
            "n/a" if med is None else str(med), len(ranks), len(rows)))
    print("\n  same curve, recall_strict (one expected ref per chunk):")
    hdr = "  %-40s" % "set"
    for d in CURVE_DEPTHS:
        hdr += " %-7s" % ("rs@%d" % d)
    print(hdr)
    for s in LABELS:
        rows = [r for r in curves[s] if r["rr"] is not None]
        if not rows:
            continue
        line = "  %-40s" % LABELS[s]
        for d in CURVE_DEPTHS:
            line += " %-7s" % fmt(mean(r["rs@%d" % d] for r in rows))
        print(line)
    # Monotonicity is a property of reading prefixes of ONE ordering, so a
    # violation is a bug in this harness, not a finding about retrieval.
    for s in LABELS:
        for r in curves[s]:
            if r["rr"] is None:
                continue
            vals = [r["r@%d" % d] for d in CURVE_DEPTHS]
            assert vals == sorted(vals), (
                "%s: recall@k is not monotone (%s) -- harness bug, not a "
                "retrieval finding" % (r["id"], vals))


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    reveal_test = "--reveal-test" in argv

    assert_frozen10_matches_notebook()
    rows = load_eval_set()
    by_set = {s: [r for r in rows if r["set"] == s] for s in LABELS}

    docs = build_corpus()
    print("CORPUS_VERSION=%s" % CORPUS_VERSION)
    print("corpus: %s" % {k: len(v) for k, v in docs.items()})
    n_refs = verify_expected(rows, docs)
    print("ground truth verified against corpus: %d questions, %d expected refs"
          % (len(rows), n_refs))
    print("sets: %s" % "  ".join("%s=%d" % (s, len(by_set[s])) for s in LABELS))

    ret = PerDocRetriever(docs)
    measured = {s: [measure_one(ret, r) for r in by_set[s]] for s in LABELS}
    curves = {s: [measure_curve(ret, r) for r in by_set[s]] for s in LABELS}

    for s in ("heldout", "test"):
        if not measured[s]:
            print("\nNo %r questions in data/eval/questions.json yet." % s)
            continue
        # The clean set's missed-refs column is the tuning handle, so it is the
        # one thing withheld by default. See TEST-SET PROTECTION in the header.
        per_question_table(LABELS[s], measured[s],
                           show_missed=(s != "test") or reveal_test)
        if s == "test" and not reveal_test:
            print("  still-missed withheld: reading which refs a CLEAN set misses")
            print("  is what turned the 30 dev questions into a dev set. Pass")
            print("  --reveal-test to print it, and record in the journal that")
            print("  you did -- it spends the set.")
        class_table(LABELS[s], measured[s])

    # The headline. Every set, always, in one block -- a single number quoted
    # on its own is the thing this phase exists to prevent.
    recalls = {s: mean(r["recall"] for r in measured[s]) for s in LABELS}
    stricts = {s: mean(r["recall_strict"] for r in measured[s]) for s in LABELS}
    print("\n== GENERALISATION: ALL SETS SIDE BY SIDE (the headline) ==")
    print("  corpus=%s, shipping arm k=%d/doc -> select_top(top_n=%d)"
          % (CORPUS_VERSION, K_PER_DOC, TOP_N))
    for s in LABELS:
        n_scored = sum(1 for r in measured[s] if r["recall"] is not None)
        print("  %-40s recall %s  strict %s  (n=%d)"
              % (LABELS[s], fmt(recalls[s]), fmt(stricts[s]), n_scored))
    print("  strict = evalset.strict_covered, one expected ref per chunk. The")
    print("  recall-minus-strict gap is the PACKED-REF SUBSIDY that v1 enjoys")
    print("  and corpus v2 removes by design. Across corpus versions compare")
    print("  STRICT only; plain recall is not comparable v1 -> v2.")
    f_recall = recalls["frozen10"]
    for s in ("heldout", "test"):
        if f_recall is not None and recalls[s] is not None:
            print("  delta vs frozen-10 (%s): %+.3f" % (s, recalls[s] - f_recall))
    print("  A drop here is THE FINDING, not a bug to tune away: it is the")
    print("  measurement able to separate generalisation from fitting to 10")
    print("  points. Do not edit a question to move any of these numbers.")

    curve_table(curves)

    # ---- false refusals. The number that matters most in this project.
    print("\n== FALSE-REFUSAL RATE (answerable questions, every set) ==")
    print("  CLAUDE.md: false refusals deny help to PWDs. This is the number")
    print("  that matters most here, and it was almost unmeasured before Phase 09.")
    for s in LABELS:
        ans = [r for r in measured[s] if r["expect_gate"] == "answer"]
        fr = [r for r in ans if r["n_kept"] == 0]
        print("  %-40s %d/%d = %.1f%% retrieve NOTHING"
              % (LABELS[s], len(fr), len(ans),
                 100 * len(fr) / len(ans) if ans else 0.0))
        if fr and (s != "test" or reveal_test):
            print("    offenders: %s" % ", ".join(
                "%s (%s, top %.4f)" % (r["id"], r["class"], r["top"]) for r in fr))

    # ---- gate-level false answers. Reported UNGATED, caveat attached.
    print("\n== GATE-LEVEL FALSE-ANSWER RATE (off-corpus questions, every set) ==")
    any_refuse = False
    for s in LABELS:
        ref = [r for r in measured[s] if r["expect_gate"] == "refuse"]
        if not ref:
            continue
        any_refuse = True
        fa = [r for r in ref if r["n_kept"] > 0]
        print("  %-40s %d/%d = %.1f%% clear MIN_SCORE=%.2f"
              % (LABELS[s], len(fa), len(ref), 100 * len(fa) / len(ref),
                 MIN_SCORE))
        if fa:
            print("    cleared: %s" % ", ".join(
                "%s (top %.4f)" % (r["id"], r["top"]) for r in fa))
    if not any_refuse:
        print("  no expect_gate=refuse questions in any set")
    print("  CAVEAT, and it is load-bearing -- a bad number here is EXPECTED and")
    print("  is NOT a reason to touch MIN_SCORE:")
    print("    * MIN_SCORE is a weak-overlap FLOOR, not a semantic filter, and")
    print("      the in-corpus/off-corpus cosine bands are INVERTED")
    print("      (src/retrieve.py:26-44). 'sourdough' scored 0.125 and 'maritime")
    print("      shipping insurance' 0.318 before any of this work existed.")
    print("    * The SEMANTIC refusal layer is the strict-prompt")
    print("      NO_ANSWER_SENTENCE path in src/rag.py, which this harness")
    print("      cannot reach -- measuring it costs quota. This measures the")
    print("      floor only; it is half the refusal story by construction.")
    print("    * Both layers are preserved on purpose. The gate errs LOW because")
    print("      false refusals deny help to PWDs.")

    # ---- the only failure condition.
    print("\n== FROZEN-10 REGRESSION GUARD (the only thing that can fail here) ==")
    assert CORPUS_VERSION == "v1", (
        "FROZEN10_RECALL_BASELINE_V1 is a CORPUS v1 number and this run is on "
        "corpus %r. Plain recall is not comparable across corpus versions "
        "(packed refs): add a v2 guard on recall_strict instead of relaxing "
        "this one." % CORPUS_VERSION)
    ok = f_recall is not None and f_recall >= FROZEN10_RECALL_BASELINE_V1 - EPS
    print("  frozen-10 recall %s vs recorded baseline %.3f (corpus %s): %s"
          % (fmt(f_recall), FROZEN10_RECALL_BASELINE_V1, CORPUS_VERSION,
             "PASS" if ok else "FAIL"))
    print("  frozen-10 recall_strict %s -- published now, BEFORE v2 exists, so"
          % fmt(stricts["frozen10"]))
    print("  the v2 rebuild has an honest yardstick to be compared against.")
    print("  (dev and test numbers above can never fail this script, by design)")
    if not ok:
        print("\nEVAL_HELDOUT: FAIL -- the frozen yardstick moved.")
        return 1
    print("\nEVAL_HELDOUT: PASS (frozen yardstick intact; dev/test reported as measured)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
