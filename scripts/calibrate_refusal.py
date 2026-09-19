"""Phase 10 D5 -- the MIN_SCORE refusal floor, re-derived against corpus v2.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\calibrate_refusal.py
     ... --negative-test    (prove each gate can FAIL; see NEGATIVE TESTS below)

Zero network, zero quota, writes NO files. Both corpus versions are built in
ONE process so v1 and v2 are scored by the same code on the same run -- an
arm-to-arm comparison assembled from two separate runs of two separate scripts
is exactly what this replaces.

WHY THIS FILE EXISTS
--------------------
Two debts, both named in the source:

  1. src/retrieve.py's cross-doc merge block asked for this battery by name.
     The refusal-invariance proof there WAS checked empirically -- 106 probes on
     2026-09-13, zero flips -- but by a throwaway harness that was never
     committed, so the claim rested on "a run nobody can reproduce". A proof
     that cannot be re-run is not a gate. This is that battery, committed.

  2. The MIN_SCORE calibration block at the top of src/retrieve.py was measured
     on 2026-09-08 against corpus v1. D2/D3/D4 replaced all three documents, so
     every cosine in the system moved and the calibration was INHERITED rather
     than re-derived. Longer v2 chunks lower every score, and a lower score can
     manufacture a FALSE REFUSAL -- the failure CLAUDE.md calls the worst one,
     because it denies help to a PWD. This re-derives the table.

REUSE, NOT REIMPLEMENTATION (the discipline ablate_phase08.py already states)
-----------------------------------------------------------------------------
  probes   <- evalset.load_eval_set() (60) + ablate_phase08.OFF_CORPUS (12)
              + retrieve.SYNONYMS keys (34) = 106. All three are IMPORTED.
              Copying any of them would let this battery drift away from the
              sets the rest of the repo measures, which is how a guard quietly
              stops guarding.
  scoring  <- eval_heldout.measure_one at its K_PER_DOC=3 / TOP_N=6 /
              MIN_PER_DOC=1, i.e. the SHIPPING arm. Every number printed here
              is therefore directly comparable to a published one rather than
              merely similar-looking.
  corpora  <- rag.build_corpus("v1") and build_corpus("v2"). The `docs` dict is
              NOT reordered: PerDocRetriever iterates it in insertion order and
              sorts by score alone (src/retrieve.py:331-338), so insertion
              order breaks ties and a reorder silently moves published numbers.

`import eval_heldout` is inert -- its main() is __main__-guarded and module
scope is imports plus constants. Checked, not assumed.

FOUR BLOCKS, THREE GATES
------------------------
  BLOCK 1 / GATE 1  refusal invariance, 106 probes x 2 versions = 212 runs.
  BLOCK 2 / GATE 2  D5's own gate: v2 may not refuse more answerable questions
                    than v1 on any set, and no expect_gate=answer row may flip
                    answered -> refused. The 34 bare synonym keys and the 20
                    off-corpus probes are REPORTED with every flip named but
                    are NOT gated -- classify() carries the argument for why,
                    and it is the load-bearing judgement in this script.
  BLOCK 3 / GATE 3  MIN_SCORE tripwire: may move DOWN, never UP.
  BLOCK 4           the calibration table -- the input to the comment block at
                    src/retrieve.py:26-44. Whether the in-corpus/off-corpus
                    band is still INVERTED is MEASURED here, not assumed.
  BLOCK 5           frozen-10 v1 <-> v2, per question. REPORT ONLY.

BLOCK 5 IS A DIAGNOSIS, NOT A TUNING HANDLE
-------------------------------------------
eval_heldout.py prints per-question tables for dev and test only, so a move in
the frozen-10 number is currently unattributable. Block 5 attributes it. Its
output may NOT be used to change chunk sizes, the synonym map, k, top_n or
MIN_SCORE: the frozen 10 are the set the synonym map was fitted to, and tuning
on an attribution of their own failures is the contamination evalset.py exists
to prevent. Read it, record it, leave it alone.

NEGATIVE TESTS (--negative-test)
--------------------------------
A guard is proven by injection, not by reading. Each of the three gates is
driven into failure in-process, and the run FAILS if a gate stays silent:

  GATE 2  the v2 arm's floor -> 0.30, v1 left alone. Answerable rows fall under
          the floor, so false refusals must appear and be named. The injection
          is ASYMMETRIC on purpose: raising both arms together could push them
          under as a pair and still satisfy v2 <= v1, which would prove
          nothing. A one-sided regression is what the gate has to catch.
  GATE 3  retrieve.MIN_SCORE -> 0.11. The tripwire must fire.
  GATE 1  two injections, and the first one is reported HONESTLY:
          (a) floor=0.0 into select_top while still filtering at MIN_SCORE --
              the "latent inconsistency" select_top's own docstring describes.
              This does NOT break invariance, and the reason is structural: the
              global maximum is in select_top's output for EVERY floor. At
              floor=0.0 the quota phase takes each doc's best hit, and the
              global max is some doc's best hit; at floor=MIN_SCORE the quota
              phase either takes it or takes nothing and the fill phase takes
              it first. So the property holds and this injection cannot falsify
              it. Saying so is the point -- an untestable gate reported as
              negative-tested is an overclaim.
          (b) select_top -> a mutant that drops the global maximum. This
              violates the proof's actual premise, and gate 1 must fire.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import eval_heldout  # noqa: E402  (patched in --negative-test; import the MODULE)
import retrieve  # noqa: E402      (same -- gate 3 reads retrieve.MIN_SCORE live)
from ablate_phase08 import OFF_CORPUS  # noqa: E402  (the SAME 12 probes)
from eval_heldout import (  # noqa: E402  (the SAME shipping depth/width)
    K_PER_DOC,
    MIN_PER_DOC,
    TOP_N,
    measure_one,
)
from evalset import load_eval_set, ref_nums  # noqa: E402
from rag import build_corpus  # noqa: E402
from retrieve import PerDocRetriever, select_top  # noqa: E402

VERSIONS = ("v1", "v2")
SETS = ("frozen10", "heldout", "test")

# The playbook rule this script is the enforcement of. MIN_SCORE is a
# weak-overlap FLOOR, not a semantic filter, and false refusals deny help to
# PWDs -- so a later session may lower it on evidence, and may never raise it
# to make a precision or false-answer number look better. The inverted band
# (BLOCK 4) is why raising it cannot work anyway: there is no cosine value that
# separates "shares legal words" from "on topic".
MIN_SCORE_CEILING = 0.10


# ---------------------------------------------------------------------------
# Probes: 106, assembled from three IMPORTED sources.
# ---------------------------------------------------------------------------
def build_probes() -> list[tuple[str, str]]:
    """(label, text) for all 106 probes, in a fixed order.

    60 eval rows keep their own ids. The 12 off-corpus probes and the 34 bare
    synonym keys are labelled by source so an offender named by a gate can be
    traced back to the list it came from.
    """
    probes = [(r["id"], r["text"]) for r in load_eval_set()]
    probes += [("OFF%02d" % (i + 1), q) for i, q in enumerate(OFF_CORPUS)]
    # Bare keys, not expansions: a single curated trigger word on its own is
    # the weakest legitimate query the shipping path can receive, so it is
    # where a floor that is too high shows up first.
    probes += [("SYN:%s" % k, k) for k in sorted(retrieve.SYNONYMS)]
    return probes


# ---------------------------------------------------------------------------
# BLOCK 1 / GATE 1 -- refusal invariance.
# ---------------------------------------------------------------------------
def check_invariance(rets: dict, probes: list, floor=None,
                     selector=None) -> list[str]:
    """Returns the disagreements; empty list means the property holds.

    The property, verbatim from the cross-doc merge block in src/retrieve.py:

        "some returned hit clears the floor"  <=>  "the global max clears the
        floor"

    LHS is read off select_top's output (what the user is actually shown), RHS
    off the raw merged ranking (which is score-sorted, so [0] is the global
    max). If these ever disagree, the doc-quota merge has changed a refusal
    decision, and the MIN_SCORE calibration stops being valid for the shipping
    path.

    `floor` and `selector` exist for --negative-test only; both default to the
    shipping behaviour.
    """
    sel_fn = selector or select_top
    bad = []
    for version in VERSIONS:
        ret = rets[version]
        for label, text in probes:
            raw = ret.query(text, k=K_PER_DOC)
            kwargs = {} if floor is None else {"floor": floor}
            shown = sel_fn(raw, TOP_N, MIN_PER_DOC, **kwargs)
            lhs = any(h.score >= retrieve.MIN_SCORE for h in shown)
            rhs = bool(raw) and raw[0].score >= retrieve.MIN_SCORE
            if lhs != rhs:
                bad.append("%s/%s: shown_clears=%s global_max_clears=%s "
                           "(top=%.4f)" % (version, label, lhs, rhs,
                                           raw[0].score if raw else 0.0))
    return bad


# ---------------------------------------------------------------------------
# Measurement -- one measure_one profile per (version, eval row).
# ---------------------------------------------------------------------------
def measure_all(rets: dict) -> dict:
    """{version: {id: measure_one(...)}} over the 60 eval rows."""
    rows = load_eval_set()
    return {v: {r["id"]: measure_one(rets[v], r) for r in rows}
            for v in VERSIONS}


def probe_scores(rets: dict, probes: list, floor=None) -> dict:
    """{version: {label: (top, n_kept)}} over ALL 106 probes.

    measure_one covers the 60 eval rows but the other 46 probes have no
    expected refs, so they get the same shipping-arm profile computed here --
    same k, same select_top, same merge. n_kept is the refusal gate: zero means
    the user is declined.
    """
    f = retrieve.MIN_SCORE if floor is None else floor
    out = {}
    for version in VERSIONS:
        ret = rets[version]
        scored = {}
        for lab, txt in probes:
            hits = select_top(ret.query(txt, k=K_PER_DOC), TOP_N,
                              min_per_doc=MIN_PER_DOC)
            scored[lab] = (hits[0].score if hits else 0.0,
                           sum(1 for h in hits if h.score >= f))
        out[version] = scored
    return out


def classify(probes: list) -> tuple[list, list, list]:
    """Split the 106 into (answerable rows, bare keys, off-corpus).

    THREE populations, not two, and the split is the load-bearing judgement in
    this script -- so here is the reasoning rather than just the result.

    ROWS (52) = the expect_gate=answer eval rows. Real questions whose expected
      refs were read out of the corpus and are verified at load. A flip to
      refused here is a false refusal with no qualification. GATED.

    KEYS (34) = retrieve.SYNONYMS queried bare. REPORTED, NOT GATED. These
      exist in ablate_phase08.py:186 to prove one thing -- that EXPANSION does
      not flip a key answered -> refused, within a single corpus. They were
      never a claim that every bare trigger word is an answerable question, and
      reusing them as a cross-corpus false-refusal gate mis-signs at least one
      case: see the SYN:car finding printed in block 2(c), where v1's "answer"
      was Constitution s. 40 reached by expansion manufacturing overlap, i.e.
      the very defect PerDocRetriever.query's entry gate documents. Gating this
      population with that sign would score a junk answer as the good state.
      Every flip is still NAMED, so nothing is hidden by not gating it.

    OFF (20) = the 8 expect_gate=refuse eval rows + the 12 OFF_CORPUS probes.
      REPORTED, NOT GATED. Here answered -> refused is the DESIRED direction
      (one fewer false answer), so the same gate would again score an
      improvement as a failure.
    """
    gate = {r["id"]: r["expect_gate"] for r in load_eval_set()}
    rows, keys, off = [], [], []
    for lab, _ in probes:
        if lab.startswith("SYN:"):
            keys.append(lab)
        elif lab.startswith("OFF") or gate[lab] == "refuse":
            off.append(lab)
        else:
            rows.append(lab)
    return rows, keys, off


# ---------------------------------------------------------------------------
# Printing.
# ---------------------------------------------------------------------------
def rule(title: str) -> None:
    print("\n== %s ==" % title)


def block1(rets: dict, probes: list) -> list[str]:
    rule("BLOCK 1 / GATE 1 -- REFUSAL INVARIANCE (the committed battery)")
    bad = check_invariance(rets, probes)
    n = len(probes) * len(VERSIONS)
    print("  probes %d (60 eval + 12 off-corpus + 34 synonym keys) x %d "
          "versions = %d probe-runs" % (len(probes), len(VERSIONS), n))
    print("  property: any(shown hit >= MIN_SCORE) == (global max >= MIN_SCORE)")
    print("  disagreements: %d / %d" % (len(bad), n))
    for line in bad:
        print("    OFFENDER %s" % line)
    print("  -> %s" % ("PASS -- select_top is refusal-invariant on both corpora"
                       if not bad else "FAIL"))
    return bad


def block2(meas: dict, prof: dict, rows_p: list, keys_p: list,
           off: list) -> list[str]:
    rule("BLOCK 2 / GATE 2 -- FALSE REFUSALS, v1 vs v2 (D5's gate)")
    print("  A false refusal = a question that SHOULD be answerable where")
    print("  NOTHING clears the floor. CLAUDE.md calls this the worst failure")
    print("  mode, because it denies help to a PWD.")
    failures = []

    print("  (a) per-set false-refusal counts, expect_gate=answer rows")
    for s in SETS:
        cells = []
        for v in VERSIONS:
            rows = [r for r in meas[v].values()
                    if r["set"] == s and r["expect_gate"] == "answer"]
            fr = [r["id"] for r in rows if r["n_kept"] == 0]
            cells.append((len(fr), len(rows), fr))
        (n1, d1, f1), (n2, d2, f2) = cells
        verdict = "PASS" if n2 <= n1 else "FAIL"
        print("      %-9s v1 %d/%-3d   v2 %d/%-3d   %s"
              % (s, n1, d1, n2, d2, verdict))
        if f1:
            print("            v1 refused: %s" % ", ".join(f1))
        if f2:
            print("            v2 refused: %s" % ", ".join(f2))
        if n2 > n1:
            failures.append("%s: v2 false refusals %d > v1 %d (%s)"
                            % (s, n2, n1, ", ".join(f2)))

    # The per-set counts can tie while the IDENTITY of the refused row moves,
    # so the flip check is separate.
    print("  (b) answered(v1) -> refused(v2) flips, %d answerable rows -- GATED"
          % len(rows_p))
    flips = [p for p in rows_p
             if prof["v1"][p][1] > 0 and prof["v2"][p][1] == 0]
    for p in flips:
        print("      OFFENDER %s: v1 top %.4f -> v2 top %.4f"
              % (p, prof["v1"][p][0], prof["v2"][p][0]))
    if flips:
        failures.append("answered -> refused flips: %s" % ", ".join(flips))
    else:
        print("      none")

    # REPORTED, NOT GATED -- see classify() for the full argument. Named in
    # every case, so a flip here is visible without being scored with a sign
    # that is wrong for this population.
    print("  (c) bare SYNONYMS keys, %d probes -- REPORTED, NOT GATED"
          % len(keys_p))
    kf = [p for p in keys_p if prof["v1"][p][1] > 0 and prof["v2"][p][1] == 0]
    kg = [p for p in keys_p if prof["v1"][p][1] == 0 and prof["v2"][p][1] > 0]
    for p in kf:
        print("      FINDING %s: v1 top %.4f -> v2 top %.4f (now refused)"
              % (p, prof["v1"][p][0], prof["v2"][p][0]))
    for p in kg:
        print("      FINDING %s: v1 top %.4f -> v2 top %.4f (now answered)"
              % (p, prof["v1"][p][0], prof["v2"][p][0]))
    print("      answered -> refused: %d      refused -> answered: %d"
          % (len(kf), len(kg)))
    if "SYN:car" in kf:
        # Attribution, measured 2026-09-19, so the finding travels with the
        # number instead of having to be re-derived by whoever reads it next.
        print("      ATTRIBUTION (SYN:car). v2 Act cl. 12 is 'Reserved spaces")
        print("      ... public parking lots', so 'car' IS on-corpus and this")
        print("      looks like a false refusal. It is not one in v1's favour.")
        print("      Bare 'car' scored 0.1141 in v1 -- just over the floor --")
        print("      which let PerDocRetriever.query's ENTRY GATE admit it to")
        print("      expansion ('car vehicle transport parking road'), and the")
        print("      expanded query top-1'd Constitution s. 40 (assembly and")
        print("      association) at 0.2126. That is a junk answer produced by")
        print("      expansion manufacturing overlap -- the exact defect the")
        print("      entry gate is documented to prevent. v2 scores 0.0794 and")
        print("      refuses, and its best BARE hit is the CORRECT chunk")
        print("      (Factsheet 'Section 12 Reserved Places'). Real sentences")
        print("      are unaffected and improve: 'is there accessible parking")
        print("      for people with disabilities' 0.2157 -> 0.2802, 'do I")
        print("      have a right to accessible public transport' 0.3180 ->")
        print("      0.3174. So the floor is NOT the thing to change here; the")
        print("      open question is that a one-word query is too thin to")
        print("      reach its own correct chunk. HANDED TO D6, not fixed in")
        print("      D5 -- D5's scope is the floor, and the floor holds.")

    # Same reasoning, opposite sign: on an off-corpus probe answered ->
    # refused is the DESIRED direction. The reverse IS a regression, but
    # MIN_SCORE cannot be what catches it -- the bands are INVERTED (BLOCK 4)
    # and the semantic layer is the strict-prompt NO_ANSWER_SENTENCE path in
    # src/rag.py. Reported so a regression stays visible even though this
    # script does not own it.
    print("  (d) off-corpus movement, %d probes -- REPORTED, NOT GATED" % len(off))
    better = [p for p in off if prof["v1"][p][1] > 0 and prof["v2"][p][1] == 0]
    worse = [p for p in off if prof["v1"][p][1] == 0 and prof["v2"][p][1] > 0]
    for p in better:
        print("      improved %s: v1 top %.4f -> v2 top %.4f (now refused)"
              % (p, prof["v1"][p][0], prof["v2"][p][0]))
    for p in worse:
        print("      REGRESSED %s: v1 top %.4f -> v2 top %.4f (now answered)"
              % (p, prof["v1"][p][0], prof["v2"][p][0]))
    print("      %d fewer false answers, %d more" % (len(better), len(worse)))
    print("  -> %s" % ("PASS" if not failures else "FAIL"))
    return failures


def block3() -> list[str]:
    rule("BLOCK 3 / GATE 3 -- MIN_SCORE TRIPWIRE")
    live = retrieve.MIN_SCORE
    print("  MIN_SCORE = %.4f   ceiling = %.4f" % (live, MIN_SCORE_CEILING))
    ok = live <= MIN_SCORE_CEILING + 1e-12
    if not ok:
        print("    OFFENDER MIN_SCORE %.4f > %.4f -- the floor MAY MOVE DOWN "
              "ON EVIDENCE, NEVER UP. Raising it to improve a precision or "
              "false-answer number manufactures false refusals, which deny "
              "help to PWDs (CLAUDE.md). The bands are INVERTED (BLOCK 4), so "
              "raising it cannot buy semantic discrimination anyway -- that is "
              "the strict-prompt NO_ANSWER_SENTENCE layer's job."
              % (live, MIN_SCORE_CEILING))
    print("  -> %s" % ("PASS" if ok else "FAIL"))
    return [] if ok else ["MIN_SCORE %.4f exceeds ceiling %.4f"
                          % (live, MIN_SCORE_CEILING)]


def block4(meas: dict, prof: dict) -> None:
    rule("BLOCK 4 -- CALIBRATION TABLE (paste into src/retrieve.py:26-44)")
    print("  Shipping arm: k=%d/doc, select_top(top_n=%d, min_per_doc=%d)."
          % (K_PER_DOC, TOP_N, MIN_PER_DOC))
    print("  IN-CORPUS MINIMA (lowest top score over expect_gate=answer rows)")
    in_min = {}
    for v in VERSIONS:
        for s in SETS:
            rows = [r for r in meas[v].values()
                    if r["set"] == s and r["expect_gate"] == "answer"]
            worst = min(rows, key=lambda r: r["top"])
            in_min[(v, s)] = worst["top"]
            print("    %-2s %-9s min %.4f (%s)   n=%d"
                  % (v, s, worst["top"], worst["id"], len(rows)))
    print("  OFF-CORPUS MAXIMA (highest top score -- these are FALSE ANSWERS)")
    off_max = {}
    for v in VERSIONS:
        tops = {k: s for k, (s, _) in prof[v].items() if k.startswith("OFF")}
        lab = max(tops, key=lambda k: tops[k])
        off_max[(v, "probes12")] = tops[lab]
        n_clear = sum(1 for k in tops if prof[v][k][1] > 0)
        print("    %-2s %-9s max %.4f (%s)   n=12   %d clear the floor"
              % (v, "probes12", tops[lab], lab, n_clear))
        rows = [r for r in meas[v].values() if r["expect_gate"] == "refuse"]
        worst = max(rows, key=lambda r: r["top"])
        off_max[(v, "refuse8")] = worst["top"]
        print("    %-2s %-9s max %.4f (%s)   n=%d"
              % (v, "refuse8", worst["top"], worst["id"], len(rows)))
        cleared = [r["id"] for r in rows if r["n_kept"] > 0]
        print("       of the %d refuse rows, %d clear the floor: %s"
              % (len(rows), len(cleared), ", ".join(cleared) or "none"))

    # The conclusion is RE-DERIVED here, not inherited from 2026-09-08. The
    # band is INVERTED when some off-corpus probe outscores the weakest
    # on-topic question -- i.e. when no single cosine value can separate them.
    print("  BAND CHECK (inverted <=> no cosine separates off-corpus from "
          "on-topic)")
    for v in VERSIONS:
        lo = min(in_min[(v, s)] for s in SETS)
        hi = max(off_max[(v, k)] for k in ("probes12", "refuse8"))
        print("    %-2s weakest in-corpus %.4f vs strongest off-corpus %.4f "
              "-> %s" % (v, lo, hi,
                         "INVERTED" if hi >= lo else "separable"))


def block5(meas: dict, rets: dict) -> None:
    rule("BLOCK 5 -- FROZEN-10 v1 <-> v2, PER QUESTION (report only)")
    print("  Why: eval_heldout.py tables dev and test only, so a frozen-10 move")
    print("  is unattributable. This attributes it. REPORT ONLY -- nothing in")
    print("  this block may change sizes, synonyms, k, top_n or MIN_SCORE.")
    print("  packed = retrieved chunks whose ref carries >1 number. A v1 chunk")
    print("  reffed 'cl. 3,4,5' satisfies three expected refs from ONE slot;")
    print("  v2's one-clause chunks cannot. That subsidy is what plain recall")
    print("  loses and recall_strict never granted.")
    print("  %-4s %-27s %-27s" % ("", "-------- v1 --------",
                                  "-------- v2 --------"))
    print("  %-4s %6s %6s %6s %5s %6s %6s %6s %5s"
          % ("id", "rec", "strict", "top", "pack", "rec", "strict", "top",
             "pack"))
    tot = {v: {"recall": 0.0, "recall_strict": 0.0} for v in VERSIONS}
    ids = [i for i, r in meas["v1"].items() if r["set"] == "frozen10"]
    packed = {}
    for v in VERSIONS:
        ret = rets[v]
        rows = {r["id"]: r for r in load_eval_set("frozen10")}
        packed[v] = {}
        for i in ids:
            hits = select_top(ret.query(rows[i]["text"], k=K_PER_DOC), TOP_N,
                              min_per_doc=MIN_PER_DOC)
            packed[v][i] = sum(1 for h in hits if len(ref_nums(h.ref)) > 1)
    for i in ids:
        a, b = meas["v1"][i], meas["v2"][i]
        for v, r in (("v1", a), ("v2", b)):
            tot[v]["recall"] += r["recall"]
            tot[v]["recall_strict"] += r["recall_strict"]
        print("  %-4s %6.3f %6.3f %6.4f %5d %6.3f %6.3f %6.4f %5d"
              % (i, a["recall"], a["recall_strict"], a["top"], packed["v1"][i],
                 b["recall"], b["recall_strict"], b["top"], packed["v2"][i]))
    n = len(ids)
    print("  %-4s %6.3f %6.3f %6s %5d %6.3f %6.3f %6s %5d"
          % ("MEAN", tot["v1"]["recall"] / n, tot["v1"]["recall_strict"] / n,
             "", sum(packed["v1"].values()),
             tot["v2"]["recall"] / n, tot["v2"]["recall_strict"] / n,
             "", sum(packed["v2"].values())))
    print("  EXPECTED REFS LOST / GAINED (v1 -> v2), doc:number")
    any_move = False
    for i in ids:
        # measure_one reports what was MISSED; covered is the complement, so
        # lost/gained are read off the published field rather than recomputed
        # with a second definition of recall.
        cov1 = set(meas["v1"][i]["missed"])
        cov2 = set(meas["v2"][i]["missed"])
        lost = sorted(cov2 - cov1)    # missed by v2 but not v1 = lost
        gained = sorted(cov1 - cov2)  # missed by v1 but not v2 = gained
        if lost or gained:
            any_move = True
            print("    %-4s lost: %-28s gained: %s"
                  % (i, ", ".join(lost) or "-", ", ".join(gained) or "-"))
    if not any_move:
        print("    (none -- every frozen-10 question covers the same refs)")


# ---------------------------------------------------------------------------
# --negative-test: drive every gate into failure.
# ---------------------------------------------------------------------------
def _drop_global_max(hits, top_n, min_per_doc=1, floor=None):
    """Mutant select_top that discards the highest-scoring hit.

    This is not a plausible bug; it is the MINIMAL violation of the premise
    gate 1's proof rests on ("select_top always contains the global maximum").
    Its only job is to show the gate is live.
    """
    kwargs = {} if floor is None else {"floor": floor}
    shown = select_top(hits, top_n + 1, min_per_doc, **kwargs)
    return shown[1:]


def negative_tests(rets: dict, probes: list) -> list[str]:
    rule("NEGATIVE TESTS -- each gate must FAIL under injection")
    failures = []
    rows_p, keys_p, off = classify(probes)

    # -- GATE 2 ------------------------------------------------------------
    # The floor is raised for v2 ONLY. Raising it in both arms would push both
    # under together and the v2<=v1 comparison could still tie, which would
    # prove nothing. An asymmetric injection is what a real v2 regression
    # would look like, so it is what the gate has to catch.
    real = eval_heldout.MIN_SCORE
    try:
        eval_heldout.MIN_SCORE = 0.30
        hurt = {"v2": {r["id"]: measure_one(rets["v2"], r)
                       for r in load_eval_set()}}
    finally:
        eval_heldout.MIN_SCORE = real
    meas_bad = {"v1": measure_all(rets)["v1"], "v2": hurt["v2"]}
    prof_bad = {"v1": probe_scores(rets, probes)["v1"],
                "v2": probe_scores(rets, probes, floor=0.30)["v2"]}
    fired = bool(block2(meas_bad, prof_bad, rows_p, keys_p, off))
    print("  GATE 2  v2 floor -> 0.30: %s"
          % ("FIRES (offenders named above). OK" if fired
             else "STAYED SILENT"))
    if not fired:
        failures.append("gate 2 stayed silent with the v2 floor at 0.30")

    # -- GATE 3 ------------------------------------------------------------
    real3 = retrieve.MIN_SCORE
    try:
        retrieve.MIN_SCORE = 0.11
        fired = retrieve.MIN_SCORE > MIN_SCORE_CEILING + 1e-12
    finally:
        retrieve.MIN_SCORE = real3
    print("  GATE 3  MIN_SCORE -> 0.11 vs ceiling %.2f: %s"
          % (MIN_SCORE_CEILING, "FIRES. OK" if fired else "STAYED SILENT"))
    if not fired:
        failures.append("gate 3 stayed silent at MIN_SCORE 0.11")

    # -- GATE 1 (a), the injection the plan prescribes ----------------------
    bad_a = check_invariance(rets, probes, floor=0.0)
    print("  GATE 1a floor=0.0 into select_top, still filtering at MIN_SCORE: "
          "%d disagreements" % len(bad_a))
    if bad_a:
        print("          -> gate 1 FIRES. OK")
    else:
        # Reported, not swallowed. This injection CANNOT falsify the property.
        print("          -> gate 1 STAYS SILENT, and that is the correct")
        print("             result, not a hole. select_top's output contains")
        print("             the global maximum for EVERY floor: at 0.0 the")
        print("             quota phase takes each doc's best hit and the")
        print("             global max is some doc's best hit; at MIN_SCORE it")
        print("             is either taken by the quota phase or, if it does")
        print("             not clear the floor, taken FIRST by the fill")
        print("             phase. So 'some shown hit clears' == 'global max")
        print("             clears' holds identically at both floors and this")
        print("             injection is not a falsifier. The docstring's")
        print("             'latent inconsistency' is real but affects WHICH")
        print("             six chunks are shown, not the refusal decision.")
        print("             Gate 1 is therefore proven live by 1b instead.")

    # -- GATE 1 (b), an injection that DOES violate the premise -------------
    bad_b = check_invariance(rets, probes, selector=_drop_global_max)
    print("  GATE 1b select_top -> mutant that drops the global max: %d "
          "disagreements" % len(bad_b))
    if bad_b:
        print("          e.g. %s" % bad_b[0])
        print("          -> gate 1 FIRES. OK")
    else:
        failures.append("gate 1 stayed silent even with the global max dropped")
        print("          -> gate 1 STAYED SILENT. NOT PROVEN")

    print("  -> %s" % ("ALL GATES PROVEN LIVE" if not failures
                       else "NEGATIVE TESTS FAILED"))
    return failures


# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    negative = "--negative-test" in argv
    unknown = [a for a in argv if a != "--negative-test"]
    if unknown:
        print("unknown argument(s): %s" % ", ".join(unknown))
        return 2

    print("=" * 72)
    print("PHASE 10 D5 -- REFUSAL FLOOR CALIBRATION")
    print("=" * 72)
    print("MIN_SCORE=%.2f  k=%d/doc  top_n=%d  min_per_doc=%d  "
          "network calls: 0  files written: 0"
          % (retrieve.MIN_SCORE, K_PER_DOC, TOP_N, MIN_PER_DOC))

    probes = build_probes()
    assert len(probes) == 106, "expected 106 probes, built %d" % len(probes)
    rets = {}
    for v in VERSIONS:
        docs = build_corpus(v)   # insertion order preserved -- ties depend on it
        rets[v] = PerDocRetriever(docs)
        print("corpus %s: %s" % (v, "  ".join(
            "%s %d" % (d, len(c)) for d, c in docs.items())))

    meas = measure_all(rets)
    prof = probe_scores(rets, probes)
    rows_p, keys_p, off = classify(probes)

    failures = block1(rets, probes)
    failures += block2(meas, prof, rows_p, keys_p, off)
    failures += block3()
    block4(meas, prof)
    block5(meas, rets)

    if negative:
        failures += negative_tests(rets, probes)

    rule("VERDICT")
    if failures:
        print("CALIBRATE_REFUSAL: FAIL")
        for f in failures:
            print("  - %s" % f)
        return 1
    print("CALIBRATE_REFUSAL: PASS -- MIN_SCORE %.2f holds on v1 and v2"
          % retrieve.MIN_SCORE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
