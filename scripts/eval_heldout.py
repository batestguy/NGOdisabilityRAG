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
    verify_expected,
)
from rag import build_corpus  # noqa: E402
from retrieve import MIN_SCORE, PerDocRetriever, select_top  # noqa: E402

K_PER_DOC = 3   # ask() / eval_phase06 / ablate_phase08 depth
TOP_N = 6       # ask() / eval_phase06 / ablate_phase08 merge width
MIN_PER_DOC = 1  # ask() default -- the doc-quota merge, Phase 09 step 3 M2

# Recorded frozen-10 mean recall: Phase 08 M1 (synonym map), confirmed by
# eval_phase06.py on 2026-09-13 and by docs/phases/06_ragas_eval.md. The guard
# is a REGRESSION tripwire on the frozen set only -- this harness must never be
# able to report a held-out baseline while the frozen yardstick has silently
# moved underneath it.
FROZEN10_RECALL_BASELINE = 0.925
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
    print("\n== %s, PER QUESTION (k=%d/doc, top_n=%d, MIN_SCORE=%.2f) =="
          % (label.upper(), K_PER_DOC, TOP_N, MIN_SCORE))
    print("  retrieval only -- no answers exist for this set, so faithfulness /")
    print("  coverage / reverse_rel are structurally unavailable without quota.")
    print("  %-6s %-16s %-7s %-7s %-7s %-6s %s" % (
        "id", "class", "gate", "recall", "prec", "kept", "still-missed"))
    for r in rows:
        flag = ""
        if r["expect_gate"] == "answer" and r["n_kept"] == 0:
            flag = "  <-- FALSE REFUSAL"
        elif r["expect_gate"] == "refuse" and r["n_kept"] > 0:
            flag = "  <-- cleared the floor"
        missed = (",".join(r["missed"]) or "-") if show_missed else "(withheld)"
        print("  %-6s %-16s %-7s %-7s %-7s %-6d %s%s" % (
            r["id"], r["class"], r["expect_gate"], fmt(r["recall"]),
            fmt(r["precision"]), r["n_kept"], missed, flag))


def class_table(label: str, rows: list[dict]) -> None:
    print("\n== MEANS BY CLASS (%s) ==" % label)
    print("  %-16s %-5s %-8s %-8s %s" % ("class", "n", "recall", "prec", "kept=0"))
    for cls in sorted({r["class"] for r in rows}):
        sub = [r for r in rows if r["class"] == cls]
        zero = sum(1 for r in sub if r["n_kept"] == 0)
        print("  %-16s %-5d %-8s %-8s %d/%d" % (
            cls, len(sub), fmt(mean(r["recall"] for r in sub)),
            fmt(mean(r["precision"] for r in sub)), zero, len(sub)))


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    reveal_test = "--reveal-test" in argv

    assert_frozen10_matches_notebook()
    rows = load_eval_set()
    by_set = {s: [r for r in rows if r["set"] == s] for s in LABELS}

    docs = build_corpus()
    print("corpus: %s" % {k: len(v) for k, v in docs.items()})
    n_refs = verify_expected(rows, docs)
    print("ground truth verified against corpus: %d questions, %d expected refs"
          % (len(rows), n_refs))
    print("sets: %s" % "  ".join("%s=%d" % (s, len(by_set[s])) for s in LABELS))

    ret = PerDocRetriever(docs)
    measured = {s: [measure_one(ret, r) for r in by_set[s]] for s in LABELS}

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
    print("\n== GENERALISATION: ALL SETS SIDE BY SIDE (the headline) ==")
    for s in LABELS:
        n_scored = sum(1 for r in measured[s] if r["recall"] is not None)
        print("  %-40s recall %s  (n=%d)"
              % (LABELS[s], fmt(recalls[s]), n_scored))
    f_recall = recalls["frozen10"]
    for s in ("heldout", "test"):
        if f_recall is not None and recalls[s] is not None:
            print("  delta vs frozen-10 (%s): %+.3f" % (s, recalls[s] - f_recall))
    print("  A drop here is THE FINDING, not a bug to tune away: it is the")
    print("  measurement able to separate generalisation from fitting to 10")
    print("  points. Do not edit a question to move any of these numbers.")

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
    ok = f_recall is not None and f_recall >= FROZEN10_RECALL_BASELINE - EPS
    print("  frozen-10 recall %s vs recorded baseline %.3f: %s"
          % (fmt(f_recall), FROZEN10_RECALL_BASELINE, "PASS" if ok else "FAIL"))
    print("  (dev and test numbers above can never fail this script, by design)")
    if not ok:
        print("\nEVAL_HELDOUT: FAIL -- the frozen yardstick moved.")
        return 1
    print("\nEVAL_HELDOUT: PASS (frozen yardstick intact; dev/test reported as measured)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
