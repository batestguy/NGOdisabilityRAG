"""Phase E3a ablation -- hand map vs corpus-derived map vs no expansion at all.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\ablate_synonyms.py  (from D:\\NGORAG)
     ... --corpus=v1     measure the retired corpus instead
     ... --reveal-test   print test-set question IDs (SPENDS THE SET)

MEASURE-ONLY. Nothing here is on the shipping path: expand_query and the
two-sided gate in PerDocRetriever.query() are untouched, SYNONYMS is not
edited, and expand_query_auto has no caller outside this file. src/rag.py and
app.py are not edited by this step at all.

THE QUESTION, from docs/phases/13_retrieval_quality.md E3
---------------------------------------------------------
The hand-written SYNONYMS map was curated by keeping and deleting entries
according to their effect on Q1..Q10 -- an `education` key was deleted because
it cost Q7, others were kept because they lifted Q5/Q8/Q9. That is why frozen-10
reads 0.925 and the first held-out measurement read 0.420. So: does a map built
WITHOUT SIGHT OF ANY EVAL QUESTION beat the map fitted to them, and does either
beat turning expansion off?

The playbook writes "be willing to ship NEITHER" into the step. Arm C is not a
formality: a win for C means shipping LESS code than we have today.

WHY E2a's NEGATIVE DOES NOT PRE-EMPT THIS
------------------------------------------
E2a declined BM25 because it is the same lexical family as TF-IDF cosine -- it
REWEIGHTS terms the query already has, so where cosine fails because the query
and the chunk do not share words, BM25 fails the same way. Synonym expansion is
a different mechanism: it ADDS terms the query lacks. It is the one arm in this
playbook that can cross a vocabulary gap without a semantic model, which is why
it is worth measuring even after E2a.

It is also why the `vocab-mismatch` class is broken out below. That class is the
worst one in the diagnosis (dev strict 0.375, n=8) and it is what E3 exists to
move -- and E4's ship gate reads it.

WHY FOUR ARMS AND NOT THREE
---------------------------
6 of the hand map's 34 keys -- fined, fired, jail, job, lawyer, sack -- DO NOT
OCCUR IN THE CORPUS AT ALL (scripts/build_synonyms.py prints this). They are the
user-register keys, the ones bridging "can they sack me" to "terminate the
employment of". No corpus-derived generator can emit them at any parameter
setting, so if arm B loses to arm A it may be losing on 18% of the hand map that
the method structurally cannot contain, rather than on the method. Arm D is the
only shippable combination in that case, and without it the table cannot tell
those two explanations apart.

WHY THIS IS A NEW FILE
----------------------
Same reason ablate_rerank.py was: ablate_phase08.py's output is the published
Phase 08 record and ablate_phase10.py's is the published E1 record. This file
reuses evalset's scoring and ablate_rerank's measure() shape and leaves both
records alone.

SELECTION DISCIPLINE
--------------------
DEV IS THE SELECTOR; TEST IS A CHECK, NOT A CHOOSER. Every arm's test column is
printed because this harness is measure-only and publishing a column is not the
same as selecting on it -- but any ship decision that follows must be justified
on dev, with test read once as corroboration. Sample sizes are attached to every
delta: n = 10 / 25 / 17 answerable rows, so one test question is worth 0.059 and
a one-question swing is not a trend.

EXIT CODE POLICY
----------------
Measures; does not gate. Nonzero only for ground-truth verification failure, a
control arm that does not reproduce E1b on v2, or a false refusal in any arm
(the gate makes that impossible in principle, so it would be a real defect). A
disappointing recall number is the finding.
"""

import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import retrieve  # noqa: E402
from evalset import (  # noqa: E402
    load_eval_set,
    ref_nums,
    strict_covered,
    verify_expected,
)
from rag import CORPUS_VERSION, build_corpus  # noqa: E402
from retrieve import (  # noqa: E402
    AUTO_MAX_TERMS,
    MIN_SCORE,
    PerDocRetriever,
    select_top,
)

# The E1b shipping budget. Held fixed across every arm: expansion is a
# QUERY-side change, so letting the budget move too would make the rows
# unattributable -- the mistake that produced the falsified Phase 09 step 3
# plan (see ablate_phase10.py).
K_PER_DOC = 4
TOP_N = 12
MIN_PER_DOC = 1

# E1b's published recall_strict, measured WITH the hand map on. Arm A must
# reproduce it exactly; if it does not, this harness is wrong and no other row
# means anything.
CONTROL_STRICT = {"frozen10": 0.734, "heldout": 0.573, "test": 0.529}

# A SECOND check against a number this harness did not produce, and against a
# DIFFERENT arm than the control. scripts/ablate_phase08.py has measured
# expansion on/off on frozen-10 since Phase 08 and prints "MEAN 0.634 -> 0.734
# (strict)"; its "before" is exactly arm C. So arm A must land on 0.734 and arm
# C on 0.634, reproducing both ends of an independently published pair. Arm A
# alone could be reproduced by a harness that ignored the arm argument entirely
# -- which is the specific bug this file had in draft.
#
# ablate_phase08 has never measured expansion-off on dev or test: it is a
# frozen-10 harness. Arm C's dev and test columns are therefore NEW numbers,
# and they are the first held-out evidence about whether expansion is worth
# having at all.
ARM_C_FROZEN10 = 0.634

LABELS = {
    "frozen10": "frozen-10 (fitted on)",
    "heldout": "dev (THE SELECTOR)",
    "test": "test (check only)",
}

# Ordered so the table reads worst-case-first for the class E3 targets.
CLASSES = ("vocab-mismatch", "odd-wording", "cross-document", "toc-trap",
           "direct")

AUTO_PATHS = {
    "v2": ROOT / "data" / "processed" / "synonyms_auto.json",
    "v1": ROOT / "data" / "processed" / "synonyms_auto_v1.json",
}

# The hand expander, captured BEFORE any monkeypatching so arm A and the union
# arm always mean the shipping function rather than whatever is installed.
HAND = retrieve.expand_query


def hand_terms(q: str) -> tuple[str, ...]:
    """The terms expand_query() appends, without touching expand_query().

    expand_query returns either `q` unchanged or exactly `q + " " + terms`
    (src/retrieve.py), so slicing is exact rather than a parse. Done this way
    because the playbook requires expand_query itself to stay untouched, and
    the union arm needs its terms separately from its output string.
    """
    e = HAND(q)
    return () if e == q else tuple(e[len(q) + 1:].split())


def make_arms(auto_path: str):
    """(label, expander, blurb) for each arm. The expander has expand_query's
    exact contract: original query in, original query plus appended terms out."""

    def auto(q: str) -> str:
        return retrieve.expand_query_auto(q, auto_path)

    def union(q: str) -> str:
        # Hand terms first, then auto terms the hand map did not already give.
        # Order matters only for determinism here -- TF-IDF scores a bag -- but
        # it must BE deterministic for the ablation to be reproducible.
        extra = list(hand_terms(q))
        seen = set(extra)
        for t in retrieve.auto_terms(q, auto_path):
            if t not in seen:
                seen.add(t)
                extra.append(t)
        return q + " " + " ".join(extra) if extra else q

    return [
        ("A  hand map (control = E1b)", HAND,
         "the shipping map, fitted to Q1..Q10"),
        ("B  auto map (corpus-derived)", auto,
         "PPMI+SVD, built without sight of any eval question"),
        ("C  NO EXPANSION", lambda q: q,
         "the playbook's third arm -- is expansion worth having?"),
        ("D  hand UNION auto", union,
         "the only shippable combination if B loses alone"),
    ]


def effective_query(ret: PerDocRetriever, q: str, expander) -> str:
    """The string PerDocRetriever.query() actually scores, after BOTH gates.

    Mirrors src/retrieve.py PerDocRetriever.query rather than being exported
    from it -- the shipping class should not grow API for a measurement. This
    is what makes "expansion applied" a POST-GATE count: a query whose
    expansion was discarded by the exit gate did not expand, however many terms
    the map offered it. Reporting the pre-gate count would overstate every
    arm's firing rate.
    """
    base = ret._merged(q, K_PER_DOC)
    if not base or base[0].score < MIN_SCORE:
        return q
    exp = expander(q)
    if exp == q:
        return q
    hits = ret._merged(exp, K_PER_DOC)
    if not hits or hits[0].score < MIN_SCORE:
        return q
    return exp


def measure(rows: list[dict], ret: PerDocRetriever, expander) -> dict:
    """Recall / recall_strict / per-class / firing / false refusals for one arm.

    Identical scoring to ablate_rerank.measure() and ablate_phase10.measure() --
    same pair construction, same strict_covered, same false-refusal rule -- so
    the control row can be checked against E1b's published numbers and the
    three tables are directly comparable.

    THE ARM IS SWAPPED BY MONKEYPATCHING retrieve.expand_query, the technique
    ablate_phase08.py:118-149 already uses. It has to be done this way round:
    PerDocRetriever.query() resolves expand_query as a module global, so
    passing the expander in here and calling ret.query() would silently measure
    the SHIPPING map four times while printing four different arm labels. The
    patch is restored in a finally, so an exception mid-arm cannot leave the
    module holding a test double.
    """
    recs, strs, false_ref = [], [], 0
    tops, offenders, per_q, sigs = [], [], {}, []
    by_class: dict[str, list[float]] = {}
    fired, appended = 0, []
    installed = retrieve.expand_query
    retrieve.expand_query = expander
    try:
        for row in rows:
            q = row["text"]
            eff = effective_query(ret, q, expander)
            if eff != q:
                fired += 1
                appended.append(len(eff.split()) - len(q.split()))
            hits = select_top(ret.query(q, k=K_PER_DOC), TOP_N,
                              min_per_doc=MIN_PER_DOC)
            tops.append(max((h.score for h in hits), default=0.0))
            sigs.append(frozenset((h.doc_id, h.ref, h.text) for h in hits))
            kept = [h for h in hits if h.score >= MIN_SCORE]
            if row["expect_gate"] == "answer" and not kept:
                false_ref += 1
                offenders.append(row["id"])
            exp = row["expected"]
            if not exp:
                continue
            exp_pairs = {(d, n) for d, ns in exp.items() for n in ns}
            got = {(h.doc_id, n) for h in hits for n in ref_nums(h.ref)}
            recs.append(len(exp_pairs & got) / len(exp_pairs))
            strs.append(strict_covered(hits, exp) / len(exp_pairs))
            per_q[row["id"]] = strs[-1]
            by_class.setdefault(row["class"], []).append(strs[-1])
    finally:
        retrieve.expand_query = installed
    return {
        "per_q": per_q,
        "sigs": sigs,
        "recall": sum(recs) / len(recs) if recs else None,
        "strict": sum(strs) / len(strs) if strs else None,
        "by_class": {c: sum(v) / len(v) for c, v in by_class.items()},
        "class_n": {c: len(v) for c, v in by_class.items()},
        "fired": fired,
        "n_rows": len(rows),
        "app_med": statistics.median(appended) if appended else 0,
        "app_max": max(appended) if appended else 0,
        "false_ref": false_ref,
        "offenders": offenders,
        "n_ans": sum(1 for r in rows if r["expect_gate"] == "answer"),
        "tops": tops,
    }


def fmt(v) -> str:
    return "n/a" if v is None else "%.3f" % v


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # EQUALS FORM ONLY (repo convention: the space form is silently ignored).
    corpus = next((a.split("=", 1)[1] for a in argv
                   if a.startswith("--corpus=")), None)
    reveal_test = "--reveal-test" in argv
    version = corpus or CORPUS_VERSION
    auto_path = str(AUTO_PATHS[version])

    rows = load_eval_set()
    by_set = {s: [r for r in rows if r["set"] == s] for s in LABELS}
    docs = build_corpus(corpus)
    verify_expected(rows, docs)
    ret = PerDocRetriever(docs)
    arms = make_arms(auto_path)

    amap = retrieve.load_auto_synonyms(auto_path)
    print("== PHASE E3a SYNONYM MAP ABLATION (corpus=%s, MIN_SCORE=%.2f) =="
          % (version, MIN_SCORE))
    print("  Budget held at E1b's shipping arm: k=%d/doc -> select_top("
          % K_PER_DOC)
    print("  top_n=%d, min_per_doc=%d). Only the QUERY changes between arms."
          % (TOP_N, MIN_PER_DOC))
    print("  MEASURE-ONLY: expand_query, the two-sided gate and SYNONYMS are")
    print("  all untouched; expand_query_auto has no caller but this file.")

    print("\n== MAP SIZE (a first-class number, not a footnote) ==")
    print("  %-28s %-8s %s" % ("map", "keys", "terms"))
    print("  %-28s %-8d %d" % ("hand (src/retrieve.py)", len(retrieve.SYNONYMS),
                               sum(len(v) for v in retrieve.SYNONYMS.values())))
    print("  %-28s %-8d %d" % ("auto (%s)" % Path(auto_path).name, len(amap),
                               sum(len(v) for v in amap.values())))
    if not amap:
        print("  !! AUTO MAP IS EMPTY -- run scripts/build_synonyms.py%s first;"
              % ("" if version == "v2" else " --corpus=v1"))
        print("  !! arms B and D below are identical to C and A respectively.")
    print("  The auto map is ~30x the hand map's key count by construction: it")
    print("  covers the whole corpus vocabulary, where the hand map covers 34")
    print("  curated user-register words. retrieve.AUTO_MAX_TERMS=%d caps the"
          % AUTO_MAX_TERMS)
    print("  consumer side. If a large map is DILUTIVE, that is the finding.")

    results = {label: {s: measure(by_set[s], ret, exp) for s in LABELS}
               for label, exp, _b in arms}

    # ---- the table -------------------------------------------------------
    for metric, title in (
            ("strict", "RECALL_STRICT (the metric that survives v2)"),
            ("recall", "RECALL (plain -- packed-ref subsidised, v1 artifact)")):
        print("\n== %s ==" % title)
        print("  %-30s %-12s %-12s %-12s %s" % (
            "arm", "frozen10", "dev", "test", "false-refusals"))
        for label, _e, _b in arms:
            r = results[label]
            fr = "/".join("%d" % r[s]["false_ref"] for s in LABELS)
            print("  %-30s %-12s %-12s %-12s %s" % (
                label, fmt(r["frozen10"][metric]), fmt(r["heldout"][metric]),
                fmt(r["test"][metric]), fr if fr != "0/0/0" else "none"))
        base = results[arms[0][0]]
        print("  deltas vs the hand map (arm A):")
        print("  %-30s %-12s %-12s %s"
              % ("", "frozen10 n=10", "dev n=25", "test n=17"))
        for label, _e, _b in arms[1:]:
            cells = []
            for s in LABELS:
                a, b = results[label][s][metric], base[s][metric]
                cells.append("n/a" if a is None or b is None
                             else "%+.3f" % (a - b))
            print("  %-30s %-12s %-12s %s"
                  % (label, cells[0], cells[1], cells[2]))
        print("  n is ANSWERABLE rows. One test question is worth 0.059, one")
        print("  dev question 0.040, one frozen-10 question 0.100 -- read every")
        print("  delta above against those before calling it a trend.")

    # ---- the control, which is the only thing that can invalidate the table
    # CONTROL_STRICT is a corpus v2 number, so the check is GATED ON v2 and
    # merely reported on v1 -- the same one-baseline-per-corpus rule
    # eval_heldout.py's frozen-10 guard and ablate_rerank.py both follow.
    print("\n== CONTROL CHECK: arm A must reproduce E1b ==")
    ctl_bad, gated = [], version == "v2"
    for s in LABELS:
        got = results[arms[0][0]][s]["strict"]
        want = CONTROL_STRICT[s]
        ok = got is not None and abs(got - want) < 5e-4
        print("  %-22s strict %s vs E1b published %.3f (v2): %s"
              % (LABELS[s], fmt(got), want,
                 ("PASS" if ok else "FAIL") if gated
                 else "not gated, corpus=%s" % version))
        if gated and not ok:
            ctl_bad.append(s)
    got_c = results[arms[2][0]]["frozen10"]["strict"]
    ok_c = got_c is not None and abs(got_c - ARM_C_FROZEN10) < 5e-4
    print("  %-22s strict %s vs ablate_phase08's 'before' %.3f (v2): %s"
          % ("arm C on frozen-10", fmt(got_c), ARM_C_FROZEN10,
             ("PASS" if ok_c else "FAIL") if gated
             else "not gated, corpus=%s" % version))
    if gated and not ok_c:
        ctl_bad.append("arm C frozen10")
    print("  Arm A is the shipping path with nothing changed, so on v2 it must")
    print("  land on E1b's published numbers exactly, and arm C must land on")
    print("  ablate_phase08.py's independently published expansion-off figure.")
    print("  Checking BOTH ends matters: a harness that silently ignored its")
    print("  arm argument would still pass the arm A check alone. On v1 the")
    print("  numbers are printed and NOT gated -- E1b published no v1 baseline,")
    print("  and borrowing v2's would judge a correct run against the wrong")
    print("  corpus.")

    # ---- per class, pooled ----------------------------------------------
    print("\n== RECALL_STRICT PER CLASS (all three sets pooled) ==")
    pooled = {}
    for label, _e, _b in arms:
        agg: dict[str, list] = {}
        for s in LABELS:
            for c, v in results[label][s]["by_class"].items():
                agg.setdefault(c, []).append((v, results[label][s]["class_n"][c]))
        pooled[label] = {c: sum(v * n for v, n in xs) / sum(n for _v, n in xs)
                         for c, xs in agg.items()}
    ns = {}
    for c in CLASSES:
        ns[c] = sum(results[arms[0][0]][s]["class_n"].get(c, 0) for s in LABELS)
    print("  %-30s %s" % ("arm", " ".join("%-16s" % ("%s n=%d" % (c, ns[c]))
                                          for c in CLASSES)))
    for label, _e, _b in arms:
        print("  %-30s %s" % (label, " ".join(
            "%-16s" % fmt(pooled[label].get(c)) for c in CLASSES)))
    print("  off-corpus rows carry no expected refs, so they have no strict")
    print("  score; they are counted in the false-refusal column instead.")

    # ---- the class this step exists to move ------------------------------
    print("\n== VOCAB-MISMATCH, BROKEN OUT PER SET (the class E3 targets) ==")
    print("  %-30s %-12s %-12s %s"
          % ("arm", "frozen10 n=2", "dev n=8", "test n=8"))
    for label, _e, _b in arms:
        print("  %-30s %-12s %-12s %s" % (label, *(
            fmt(results[label][s]["by_class"].get("vocab-mismatch"))
            for s in LABELS)))
    print("  This is the worst class in the diagnosis and the one a synonym")
    print("  map is supposed to fix -- expansion ADDS terms the query lacks,")
    print("  where E2a's BM25 could only reweight terms it already had. At")
    print("  n=2/8/8 a single question moves a column by 0.500/0.125/0.125,")
    print("  so this block is a MECHANISM check, not a ship criterion.")

    # ---- did the mechanism fire, and how much mass did it add? -----------
    # A flat mean has two very different causes: the arm changed nothing, or it
    # changed plenty and none of it carried an expected ref. The table has to
    # separate them, and for expansion the firing rate must be POST-GATE --
    # PerDocRetriever.query() discards an expansion that cannot clear the floor.
    print("\n== DID THE MECHANISM FIRE? (post-gate, and how much it appended) ==")
    print("  %-30s %-22s %-14s %s"
          % ("arm", "expansion applied", "terms added", "displayed set changed"))
    base = results[arms[0][0]]
    for label, _e, _b in arms:
        fired = sum(results[label][s]["fired"] for s in LABELS)
        swapped = sum(1 for s in LABELS
                      for x, y in zip(results[label][s]["sigs"],
                                      base[s]["sigs"]) if x != y)
        print("  %-30s %-22s %-14s %s"
              % (label,
                 "%d/%d questions" % (fired, len(rows)),
                 "med %d max %d" % (max(results[label][s]["app_med"]
                                        for s in LABELS),
                                    max(results[label][s]["app_max"]
                                        for s in LABELS)),
                 "%d/%d vs arm A" % (swapped, len(rows))))
    print("  'expansion applied' counts questions where the expanded query")
    print("  survived BOTH gates and was the string actually scored. A pre-gate")
    print("  count would overstate every arm's reach.")

    print("\n== PER-QUESTION MOVEMENT vs arm A (strict) ==")
    print("  %-30s %s" % ("arm", "  ".join("%-22s" % LABELS[s] for s in LABELS)))
    for label, _e, _b in arms[1:]:
        cells = []
        for s in LABELS:
            a, b = results[label][s]["per_q"], base[s]["per_q"]
            up = sum(1 for q in b if a[q] > b[q] + 1e-9)
            dn = sum(1 for q in b if a[q] < b[q] - 1e-9)
            cells.append("%-22s" % ("%d up / %d down of %d" % (up, dn, len(b))))
        print("  %-30s %s" % (label, "  ".join(cells)))
    print("  Test-set IDs are withheld by default (--reveal-test): knowing")
    print("  WHICH clean questions an arm helps is the tuning handle that")
    print("  turned the 30 dev questions into a dev set.")

    # ---- refusal invariance ----------------------------------------------
    print("\n== REFUSAL INVARIANCE (the only thing that can fail here) ==")
    ctl_tops = {s: base[s]["tops"] for s in LABELS}
    bad = []
    for label, _e, _b in arms:
        r = results[label]
        tot = sum(r[s]["false_ref"] for s in LABELS)
        n = sum(r[s]["n_ans"] for s in LABELS)
        same = all(r[s]["tops"] == ctl_tops[s] for s in LABELS)
        print("  %-30s %d/%d false refusals | top-score vector %s arm A"
              % (label, tot, n, "==" if same else "!="))
        if tot:
            names = sorted(x for s in LABELS for x in r[s]["offenders"]
                           if s != "test" or reveal_test)
            if not names:
                names = ["(test IDs withheld -- pass --reveal-test)"]
            bad.append("%s: %d false refusals (%s)"
                       % (label, tot, ", ".join(names)))
    print("  0 false refusals in EVERY arm is the expected result and it is a")
    print("  property of the GATE, not of any map: the original query is scored")
    print("  first, an expansion that cannot clear the floor is discarded, so")
    print("  expansion never turns a refusal into an answer or an answer into a")
    print("  refusal whatever is appended. A failure here would mean the gate")
    print("  itself broke. The top-score vector MAY differ between arms --")
    print("  expansion re-ranks within the answered set by design (Q6 drops")
    print("  0.1759 -> 0.1696 and stays correct); only the refusal DECISION is")
    print("  invariant, which is what the false-refusal column measures.")
    print("  scripts/calibrate_refusal.py is unaffected: SYNONYMS is not")
    print("  edited, so its probe set stays at 106 probes / 212 runs.")

    if ctl_bad:
        print("\nABLATE_SYNONYMS: FAIL -- arm A does not reproduce E1b on %s"
              % ", ".join(ctl_bad))
        return 1
    if bad:
        print("\nABLATE_SYNONYMS: FAIL")
        for b in bad:
            print("  - %s" % b)
        return 1
    print("\nABLATE_SYNONYMS: PASS (arms measured; recall numbers are findings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
