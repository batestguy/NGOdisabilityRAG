"""Held-out retrieval baseline -- zero LLM, zero quota, zero network.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\eval_heldout.py   (from D:\\NGORAG)

WHAT THIS IS FOR
----------------
recall 0.925 was measured on the same 10 questions the synonym map was fitted
to: an `education` key was deleted because it cost Q7, others kept because they
lifted Q5/Q8/Q9. With n=10 one question is worth 10 points, so that number
cannot tell generalisation from memorisation. This harness measures the same
retrieval on questions NOTHING has been tuned on, and always prints the two
side by side. The gap -- whatever its sign -- is the finding.

WHAT IT DELIBERATELY DOES NOT MEASURE
-------------------------------------
The held-out set has no answer transcript, so faithfulness, coverage and
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

EXIT CODE POLICY (this is a deliberate design decision, not laxity)
-------------------------------------------------------------------
Nonzero ONLY for:
  - ground-truth verification failure (an expected number no chunk carries --
    a bug in the question set, not a measurement), or
  - a FROZEN-10 recall regression below the recorded baseline.
NEVER for a held-out number. These are a first baseline; a harness that failed
when they looked bad would create pressure to tune them, which is precisely the
contamination this file exists to prevent. Held-out numbers are reported
whatever they say.
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
    verify_expected,
)
from rag import build_corpus  # noqa: E402
from retrieve import MIN_SCORE, PerDocRetriever  # noqa: E402

K_PER_DOC = 3   # ask() / eval_phase06 / ablate_phase08 depth
TOP_N = 6       # ask() / eval_phase06 / ablate_phase08 merge width

# Recorded frozen-10 mean recall: Phase 08 M1 (synonym map), confirmed by
# eval_phase06.py on 2026-09-13 and by docs/phases/06_ragas_eval.md. The guard
# is a REGRESSION tripwire on the frozen set only -- this harness must never be
# able to report a held-out baseline while the frozen yardstick has silently
# moved underneath it.
FROZEN10_RECALL_BASELINE = 0.925
EPS = 1e-6


def measure_one(ret, row: dict) -> dict:
    """Retrieval profile for one question. No LLM, no answer, no generation."""
    hits = ret.query(row["text"], k=K_PER_DOC)[:TOP_N]
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
        "precision": (rel_hits / len(hits)) if (hits and exp_pairs) else None,
        "top": hits[0].score if hits else 0.0,
        # n_kept is the REFUSAL gate: zero kept hits means the user is declined.
        "n_kept": len(kept),
        "missed": sorted("%s:%s" % p for p in exp_pairs - ret_pairs),
    }


def mean(vals) -> float | None:
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def fmt(v, spec: str = "%.3f") -> str:
    return "n/a" if v is None else spec % v


def main() -> int:
    assert_frozen10_matches_notebook()
    rows = load_eval_set()
    frozen = [r for r in rows if r["set"] == "frozen10"]
    held = [r for r in rows if r["set"] == "heldout"]

    docs = build_corpus()
    print("corpus: %s" % {k: len(v) for k, v in docs.items()})
    n_refs = verify_expected(rows, docs)
    print("ground truth verified against corpus: %d questions, %d expected refs"
          % (len(rows), n_refs))
    print("sets: frozen10=%d  heldout=%d" % (len(frozen), len(held)))
    if not held:
        print("\nNo held-out questions in data/eval/questions.json yet.")
        return 0

    ret = PerDocRetriever(docs)
    f_rows = [measure_one(ret, r) for r in frozen]
    h_rows = [measure_one(ret, r) for r in held]

    print("\n== HELD-OUT, PER QUESTION (k=%d/doc, top_n=%d, MIN_SCORE=%.2f) =="
          % (K_PER_DOC, TOP_N, MIN_SCORE))
    print("  retrieval only -- no answers exist for this set, so faithfulness /")
    print("  coverage / reverse_rel are structurally unavailable without quota.")
    print("  %-6s %-16s %-7s %-7s %-7s %-6s %s" % (
        "id", "class", "gate", "recall", "prec", "kept", "still-missed"))
    for r in h_rows:
        flag = ""
        if r["expect_gate"] == "answer" and r["n_kept"] == 0:
            flag = "  <-- FALSE REFUSAL"
        elif r["expect_gate"] == "refuse" and r["n_kept"] > 0:
            flag = "  <-- cleared the floor"
        print("  %-6s %-16s %-7s %-7s %-7s %-6d %s%s" % (
            r["id"], r["class"], r["expect_gate"], fmt(r["recall"]),
            fmt(r["precision"]), r["n_kept"],
            ",".join(r["missed"]) or "-", flag))

    print("\n== MEANS BY CLASS (held-out) ==")
    print("  %-16s %-5s %-8s %-8s %s" % ("class", "n", "recall", "prec", "kept=0"))
    for cls in sorted({r["class"] for r in h_rows}):
        sub = [r for r in h_rows if r["class"] == cls]
        zero = sum(1 for r in sub if r["n_kept"] == 0)
        print("  %-16s %-5d %-8s %-8s %d/%d" % (
            cls, len(sub), fmt(mean(r["recall"] for r in sub)),
            fmt(mean(r["precision"] for r in sub)), zero, len(sub)))

    # The headline comparison. Both numbers, always, on one line -- a held-out
    # figure quoted on its own is the thing this phase exists to prevent.
    f_recall = mean(r["recall"] for r in f_rows)
    h_recall = mean(r["recall"] for r in h_rows)
    n_h_scored = sum(1 for r in h_rows if r["recall"] is not None)
    print("\n== GENERALISATION: FROZEN 10 vs HELD-OUT (the headline) ==")
    print("  frozen-10 mean recall : %s  (n=%d)  <- the set the synonym map was "
          "fitted on" % (fmt(f_recall), len(f_rows)))
    print("  held-out  mean recall : %s  (n=%d)  <- nothing has been tuned on "
          "these" % (fmt(h_recall), n_h_scored))
    if f_recall is not None and h_recall is not None:
        d = h_recall - f_recall
        print("  delta                 : %+.3f" % d)
        print("  A drop here is THE FINDING, not a bug to tune away: it is the")
        print("  first measurement able to separate generalisation from fitting")
        print("  to 10 points. Do not edit a question to move this number.")

    # ---- false refusals. The number that matters most in this project.
    ans = [r for r in h_rows if r["expect_gate"] == "answer"]
    fr = [r for r in ans if r["n_kept"] == 0]
    print("\n== FALSE-REFUSAL RATE (held-out, answerable questions) ==")
    print("  CLAUDE.md: false refusals deny help to PWDs. This is the number")
    print("  that matters most here, and it has been almost unmeasured until now.")
    print("  %d/%d = %.1f%% of answerable held-out questions retrieve NOTHING"
          % (len(fr), len(ans), 100 * len(fr) / len(ans) if ans else 0.0))
    if fr:
        print("  offenders: %s" % ", ".join(
            "%s (%s, top %.4f)" % (r["id"], r["class"], r["top"]) for r in fr))
    f_ans = [r for r in f_rows if r["expect_gate"] == "answer"]
    f_fr = sum(1 for r in f_ans if r["n_kept"] == 0)
    print("  frozen-10 comparison: %d/%d = %.1f%%"
          % (f_fr, len(f_ans), 100 * f_fr / len(f_ans) if f_ans else 0.0))

    # ---- gate-level false answers. Reported UNGATED, caveat attached.
    ref = [r for r in h_rows if r["expect_gate"] == "refuse"]
    fa = [r for r in ref if r["n_kept"] > 0]
    print("\n== GATE-LEVEL FALSE-ANSWER RATE (held-out, off-corpus questions) ==")
    if ref:
        print("  %d/%d = %.1f%% of off-corpus questions clear MIN_SCORE=%.2f"
              % (len(fa), len(ref), 100 * len(fa) / len(ref), MIN_SCORE))
        if fa:
            print("  cleared: %s" % ", ".join(
                "%s (top %.4f)" % (r["id"], r["top"]) for r in fa))
    else:
        print("  no expect_gate=refuse questions in the held-out set")
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
    ok = f_recall is not None and f_recall >= FROZEN10_RECALL_BASELINE - EPS
    print("  frozen-10 recall %s vs recorded baseline %.3f: %s"
          % (fmt(f_recall), FROZEN10_RECALL_BASELINE, "PASS" if ok else "FAIL"))
    print("  (held-out numbers above can never fail this script, by design)")
    if not ok:
        print("\nEVAL_HELDOUT: FAIL -- the frozen yardstick moved.")
        return 1
    print("\nEVAL_HELDOUT: PASS (frozen yardstick intact; held-out reported as measured)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
