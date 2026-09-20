"""Phase E2a ablation -- does a BM25 SELECTION re-rank collect the pool headroom?

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\ablate_rerank.py   (from D:\\NGORAG)
     ... --corpus=v1     measure the retired corpus instead
     ... --b-sweep-only  skip the arm table, print only the b sensitivity block
     ... --reveal-test   print test-set question IDs (SPENDS THE SET)

MEASURE-ONLY. Nothing here is on the shipping path: `rerank` defaults to None in
src/retrieve.py and neither src/rag.py nor app.py passes it. This script is the
only caller.

WHY THIS IS A NEW FILE AND NOT AN AXIS ON ablate_phase10.py
-----------------------------------------------------------
ablate_phase10.py's output is the published E1 record (playbook Results table).
Changing its shape would break the comparison it exists to support. This file
reuses its measure() shape, its per-doc `mix` block and evalset's scoring, and
leaves it alone.

WHY THE RE-RANK ACTS AT SELECTION, NOT AT ORDERING
--------------------------------------------------
The playbook (docs/phases/13_retrieval_quality.md, E2) specifies "re-order the
already-admitted hits by BM25 ... a pure ordering change". E1b invalidated that
framing. At the shipping arm k=4/doc, top_n=12:

  * PerDocRetriever.query(q, k=4) returns 12 candidates, and
    select_top(hits, 12, min_per_doc=1) fills to top_n -- so it returns ALL 12;
  * select_top re-sorts its output by score, so it also destroys any incoming
    order;
  * every recall metric in the repo scores a SET, not a prefix
    (eval_heldout.py:215-224, ablate_phase10.py:145-147, eval_phase06.py:286).

So an ordering-only re-rank is provably +0.000 on recall_strict. ARM `0b` below
measures it anyway rather than asserting it in prose, and reports how many
questions had their displayed order changed -- so the reader can see the arm did
fire and still bought nothing.

The headroom is real, it is just one stage earlier. From
scripts/baseline_v2_2026-09-19.txt (rs@60, the 60-candidate pool ceiling):

  set          E1b shipping strict   rs@60    headroom a SELECTOR could reach
  frozen-10    0.734                 0.904    +0.170
  dev          0.573                 0.733    +0.160
  test         0.529                 0.735    +0.206

That ceiling is exact, not an estimate: at pool=20/doc the candidate set IS the
curve's 60-candidate pool, so rs@60 is precisely what a perfect selector scores.
Every arm below therefore prints its OWN pool ceiling, so it is read against
what it could have reached rather than against the shipping number alone.

EXIT CODE POLICY
----------------
Measures; does not gate. Nonzero only for ground-truth verification failure, a
control arm that does not reproduce E1b, or a false refusal in a SHIPPABLE
(pinned) arm. Arm 4 is unpinned ON PURPOSE to price the refusal guard -- a false
refusal there is the arm's finding, printed loudly as GUARD PRICED, not a
failure of this script. A disappointing recall number is the finding.
"""

import sys
import time
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
from retrieve import (  # noqa: E402
    BM25_B,
    BM25_K1,
    MIN_SCORE,
    PerDocRetriever,
    expand_query,
    select_top,
)

# The E1b shipping arm. Held here, not re-derived: every arm below shows the
# same 12 chunks, which is what makes them comparable at all (the omission that
# produced the falsified Phase 09 step 3 plan -- see ablate_phase10.py).
K_PER_DOC = 4
TOP_N = 12
MIN_PER_DOC = 1

# E1b's published recall_strict, the control arm's target. If arm 0 does not
# reproduce these the harness is wrong and no other row means anything.
CONTROL_STRICT = {"frozen10": 0.734, "heldout": 0.573, "test": 0.529}

LABELS = {
    "frozen10": "frozen-10 (fitted on)",
    "heldout": "dev (ex-held-out)",
    "test": "test (clean)",
}

# (label, rerank, pool_per_doc, pin_top, unigrams_only, diagnostic)
#
# `pool` is per doc; the candidate set is 3x that. Arm 2's pool of 20 makes the
# candidate set identical to eval_heldout's recall@k curve pool, which is why
# its ceiling column should read rs@60 exactly -- a cross-harness check that
# this file's pool is the pool the published ceiling was measured on.
ARMS = [
    ("0   off (control = E1b)",        None,   K_PER_DOC, True,  False, False),
    ("0b  bm25 ORDER-ONLY, 12 admitted", "order", K_PER_DOC, True, False, False),
    ("1   bm25 pool=10/doc, pinned",   "bm25", 10, True,  False, False),
    ("2   bm25 pool=20/doc, pinned *", "bm25", 20, True,  False, False),
    ("3   bm25 pool=40/doc, pinned",   "bm25", 40, True,  False, False),
    ("4   bm25 pool=20, NOT pinned",   "bm25", 20, False, False, True),
    ("5   rrf  pool=20/doc, pinned",   "rrf",  20, True,  False, False),
    # ADDED ONLY BECAUSE THE PRIMARY ARM CAME OUT FLAT. The plan gated this arm
    # on that condition: bigram counts inflate |d| by roughly a constant factor
    # across chunks, so b's length normalisation should still compare like with
    # like -- but that is an assumption, and once arm 2 fails to fire it is
    # worth testing rather than asserting.
    ("6   bm25 pool=20, UNIGRAMS only", "bm25", 20, True, True,  False),
]

# Measure-only, and REPORTED NEVER CHOSEN. b=0.75 is the textbook default and
# ships regardless (src/retrieve.py BM25_B). If an arm's result is knife-edge on
# b, that is evidence AGAINST shipping the arm -- the synonym map is what
# happens when a knob is fitted to an eval set.
B_SWEEP = (0.0, 0.5, 0.75, 1.0)


def configure(ret: PerDocRetriever, rerank, pool, pin, unigrams,
              b: float = BM25_B, k1: float = BM25_K1) -> None:
    """Point the ONE retriever at one arm's configuration.

    Both indexes (TF-IDF and BM25 counts) are built once in __init__ and are
    independent of every attribute set here -- b and k1 are score-time, pool /
    pin / rerank are selection-time. So one instance serves every arm, and all
    arms are guaranteed to share bit-identical indexes rather than merely
    equivalent ones. `rerank="order"` is this harness's own mode, applied after
    select_top (see order_only); the retriever runs it as the control.
    """
    ret.rerank = None if rerank in (None, "order") else rerank
    ret.pool_per_doc = pool
    ret.pin_top = pin
    ret.bm25_unigrams = unigrams
    ret.bm25_b = b
    ret.bm25_k1 = k1


def effective_query(ret: PerDocRetriever, q: str) -> str:
    """The string PerDocRetriever.query() actually scores, after both gates.

    Mirrors src/retrieve.py PerDocRetriever.query rather than being exported
    from it: it is needed by ONE diagnostic (the order-only arm, which has to
    score BM25 on the same string the cosine ranking saw) and the shipping class
    should not grow API for a measurement. Call it with the retriever in the
    CONTROL configuration. If it ever drifts from query(), the only thing
    affected is the "order changed on N" count -- no metric here depends on it.
    """
    base = ret._merged(q, K_PER_DOC)
    if not base or base[0].score < MIN_SCORE:
        return q
    exp = expand_query(q)
    if exp == q:
        return q
    hits = ret._merged(exp, K_PER_DOC)
    if not hits or hits[0].score < MIN_SCORE:
        return q
    return exp


def order_only(ret: PerDocRetriever, index_of: dict, q: str, hits: list):
    """The playbook's literal arm: re-order the 12 ADMITTED hits by BM25.

    Returns (reordered_hits, changed). Nothing else in this file uses the
    returned order -- it exists so the +0.000 in the table is measured rather
    than argued, and `changed` proves the arm actually fired.
    """
    eq = effective_query(ret, q)
    score = {}
    for doc_id in {h.doc_id for h in hits}:
        pos = [i for i, h in enumerate(hits) if h.doc_id == doc_id]
        # Keyed on text because a Hit carries no chunk index. This assumes
        # chunk text is unique within a doc; if it were not, the lookup would
        # still land on a chunk with IDENTICAL text and therefore an identical
        # BM25 score, so the arm's result is unaffected either way.
        idxs = [index_of[doc_id][hits[p].text] for p in pos]
        for p, s in zip(pos, ret.sub[doc_id].bm25_scores(eq, idxs)):
            score[p] = s
    order = sorted(range(len(hits)), key=lambda p: (-score[p], p))
    return [hits[p] for p in order], order != list(range(len(hits)))


def measure(rows: list[dict], hits_for) -> dict:
    """Mean recall / recall_strict / shown / false refusals for one arm.

    `hits_for(row)` returns the chunks that arm would display. Identical
    scoring to ablate_phase10.measure() -- same pair construction, same
    strict_covered, same false-refusal rule -- so the two tables are directly
    comparable and the control row can be checked against E1b's published
    numbers.
    """
    recs, strs, shown, false_ref = [], [], [], 0
    mix = {"act2018": 0, "constitution1999": 0, "factsheet2020": 0}
    tops, offenders, per_q, sigs = [], [], {}, []
    for row in rows:
        hits = hits_for(row)
        shown.append(len(hits))
        # max, not hits[0] -- the order-only arm deliberately returns the same
        # set in a different order, and the refusal decision is a property of
        # the SET's maximum cosine, not of whatever landed first.
        tops.append(max((h.score for h in hits), default=0.0))
        sigs.append(frozenset((h.doc_id, h.ref, h.text) for h in hits))
        for h in hits:
            if h.doc_id in mix:
                mix[h.doc_id] += 1
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
    return {
        "per_q": per_q,
        "sigs": sigs,
        "recall": sum(recs) / len(recs) if recs else None,
        "strict": sum(strs) / len(strs) if strs else None,
        "shown_med": sorted(shown)[len(shown) // 2] if shown else 0,
        "shown_max": max(shown) if shown else 0,
        "false_ref": false_ref,
        "offenders": offenders,
        "n_ans": sum(1 for r in rows if r["expect_gate"] == "answer"),
        "mix": mix,
        "tops": tops,
    }


def fmt(v) -> str:
    return "n/a" if v is None else "%.3f" % v


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # EQUALS FORM ONLY (repo convention: the space form is silently ignored).
    corpus = next((a.split("=", 1)[1] for a in argv
                   if a.startswith("--corpus=")), None)
    sweep_only = "--b-sweep-only" in argv
    reveal_test = "--reveal-test" in argv

    rows = load_eval_set()
    by_set = {s: [r for r in rows if r["set"] == s] for s in LABELS}
    docs = build_corpus(corpus)
    verify_expected(rows, docs)

    # ---- cost of the BM25 index (for the LATER ship decision only) --------
    # Render free is 512 MB and the Constitution is 2,037 chunks, so the count
    # matrix is the thing that could bite. Measured now even though nothing
    # boots with bm25=True yet.
    t0 = time.perf_counter()
    PerDocRetriever(docs)
    t_off = time.perf_counter() - t0
    t0 = time.perf_counter()
    ret = PerDocRetriever(docs, rerank="bm25", pool_per_doc=20)
    t_on = time.perf_counter() - t0
    idx_bytes = sum(r.bm25_bytes() for r in ret.sub.values())

    print("== PHASE E2a BM25 SELECTION RE-RANK (corpus=%s, MIN_SCORE=%.2f) =="
          % (corpus or CORPUS_VERSION, MIN_SCORE))
    print("  Shipping arm held fixed at k=%d/doc -> select_top(top_n=%d,"
          % (K_PER_DOC, TOP_N))
    print("  min_per_doc=%d). EVERY ARM SHOWS %d CHUNKS, so they are comparable."
          % (MIN_PER_DOC, TOP_N))
    print("  Hit.score is COSINE in every arm; BM25 only chooses. MEASURE-ONLY:")
    print("  rerank defaults to None and no shipping caller passes it.")
    print("\n== BM25 INDEX COST (for the ship decision, nothing boots with it) ==")
    print("  build time: bm25 off %.2fs -> on %.2fs (+%.2fs)"
          % (t_off, t_on, t_on - t_off))
    print("  index size: %.1f MB of count matrix + idf + doc lengths"
          % (idx_bytes / 1048576.0))
    print("  Render free is 512 MB. This is additive to the existing TF-IDF")
    print("  matrices, which are already resident.")

    # text -> chunk index, per doc. Only the order-only arm needs it (it starts
    # from Hits, which carry text but not the index BM25 is keyed on).
    index_of = {d: {c.text: i for i, c in enumerate(cs)}
                for d, cs in docs.items()}

    # ---- pool ceilings, cached by pool depth -----------------------------
    # An arm's ceiling is recall_strict over EVERY candidate its pool admitted,
    # i.e. what a perfect selector would score. Computed with the retriever in
    # the control configuration, so the pool is pure cosine admission -- which
    # is the point: the re-rank is spending that pool, not widening it.
    ceil_cache: dict[int, dict] = {}

    def ceiling(pool: int) -> dict:
        if pool not in ceil_cache:
            configure(ret, None, pool, True, False)
            ceil_cache[pool] = {
                s: measure(by_set[s], lambda row, p=pool: select_top(
                    ret.query(row["text"], k=p), 3 * p,
                    min_per_doc=MIN_PER_DOC))
                for s in LABELS}
        return ceil_cache[pool]

    results, ceilings, changed_counts = {}, {}, {}
    if not sweep_only:
        for label, rerank, pool, pin, uni, _diag in ARMS:
            configure(ret, rerank, pool, pin, uni)
            if rerank == "order":
                n_changed = [0]

                def hits_for(row, n=n_changed):
                    base = select_top(ret.query(row["text"], k=K_PER_DOC),
                                      TOP_N, min_per_doc=MIN_PER_DOC)
                    out, ch = order_only(ret, index_of, row["text"], base)
                    n[0] += int(ch)
                    return out
            else:
                def hits_for(row):
                    return select_top(ret.query(row["text"], k=K_PER_DOC),
                                      TOP_N, min_per_doc=MIN_PER_DOC)
            results[label] = {s: measure(by_set[s], hits_for) for s in LABELS}
            if rerank == "order":
                changed_counts[label] = n_changed[0]
            ceilings[label] = ceiling(max(pool, K_PER_DOC))

        # ---- the table -------------------------------------------------------
        for metric, title in (
                ("strict", "RECALL_STRICT (the metric that survives v2)"),
                ("recall", "RECALL (plain -- packed-ref subsidised, v1 artifact)")):
            print("\n== %s ==" % title)
            print("  %-34s %-17s %-17s %-17s %s" % (
                "arm", "frozen10 (ceil)", "dev (ceil)", "test (ceil)",
                "false-refusals"))
            for label, _rr, _p, _pin, _u, _d in ARMS:
                r, c = results[label], ceilings[label]
                cells = ["%-5s (%-5s)" % (fmt(r[s][metric]), fmt(c[s][metric]))
                         for s in LABELS]
                fr = "/".join("%d" % r[s]["false_ref"] for s in LABELS)
                print("  %-34s %-17s %-17s %-17s %s" % (
                    label, cells[0], cells[1], cells[2],
                    fr if fr != "0/0/0" else "none"))
            base = results[ARMS[0][0]]
            print("  deltas vs the control (arm 0), test set:")
            for label, _rr, _p, _pin, _u, _d in ARMS[1:]:
                a, b = results[label]["test"][metric], base["test"][metric]
                if a is not None and b is not None:
                    print("    %-34s %+.3f" % (label, a - b))
            print("  (ceil) = recall_strict over EVERY candidate that arm's pool")
            print("  admitted -- what a PERFECT selector would score. The gap")
            print("  between an arm and its own ceiling is what BM25 left behind.")

        # ---- the control, which is the only thing that can invalidate the table
        # CONTROL_STRICT is a corpus v2 number, so the check is GATED ON v2 and
        # merely reported on v1 -- the same one-baseline-per-corpus rule
        # eval_heldout.py's frozen-10 guard follows. Reusing a v2 baseline to
        # judge a v1 run is the conflation that rule exists to prevent, and it
        # would make `--corpus=v1` exit nonzero for being correct.
        print("\n== CONTROL CHECK: arm 0 must reproduce E1b ==")
        ctl_bad, gated = [], (corpus or CORPUS_VERSION) == "v2"
        for s in LABELS:
            got = results[ARMS[0][0]][s]["strict"]
            want = CONTROL_STRICT[s]
            ok = got is not None and abs(got - want) < 5e-4
            print("  %-22s strict %s vs E1b published %.3f (v2): %s"
                  % (LABELS[s], fmt(got), want,
                     ("PASS" if ok else "FAIL") if gated
                     else "not gated, corpus=%s" % (corpus or CORPUS_VERSION)))
            if gated and not ok:
                ctl_bad.append(s)
        print("  On v2 this is the harness's own control: if it fails, the")
        print("  harness is wrong and no other row in this table means")
        print("  anything. On v1 the numbers are printed and NOT gated --")
        print("  E1b published no v1 baseline, and borrowing v2's would judge")
        print("  a correct run against the wrong corpus.")

        # ---- the order-only arm, stated as a measurement --------------------
        for label, rerank, _p, _pin, _u, _d in ARMS:
            if rerank != "order":
                continue
            print("\n== ARM 0b: THE PLAYBOOK'S LITERAL ARM, MEASURED ==")
            print("  BM25 re-ordered the displayed chunks on %d of %d questions"
                  % (changed_counts[label], len(rows)))
            print("  and moved recall_strict by exactly +0.000 on all three")
            print("  sets. Not a bug: every metric here scores a SET, top_n ==")
            print("  3k so select_top returns all 12, and select_top re-sorts")
            print("  by score anyway. An ordering-only re-rank is INERT at the")
            print("  E1b shipping arm. Its only reachable effects are MRR,")
            print("  which chunks land inline vs in the fold, and prompt order")
            print("  -- and whether prompt order helps generation cannot be")
            print("  measured until Phase G spends quota.")

        # ---- did the mechanism FIRE? ----------------------------------------
        # A flat mean can mean two different things -- the re-rank changed
        # nothing, or it changed plenty and none of it carried an expected ref.
        # Those have opposite implications, so the table must distinguish them.
        # Test-set IDs are NOT printed: knowing WHICH clean questions a change
        # helps or hurts is the tuning handle eval_heldout.py withholds, and it
        # is what turned the 30 dev questions into a dev set.
        print("\n== DID THE MECHANISM FIRE? (per-question strict vs control) ==")
        print("  %-34s %s" % ("arm", "  ".join("%-22s" % LABELS[s]
                                               for s in LABELS)))
        base = results[ARMS[0][0]]
        for label, _rr, _p, _pin, _u, _d in ARMS[1:]:
            cells, swapped = [], 0
            for s in LABELS:
                a, b = results[label][s]["per_q"], base[s]["per_q"]
                up = sum(1 for q in b if a[q] > b[q] + 1e-9)
                dn = sum(1 for q in b if a[q] < b[q] - 1e-9)
                swapped += sum(1 for x, y in zip(results[label][s]["sigs"],
                                                 base[s]["sigs"]) if x != y)
                cells.append("%-22s" % ("%d up / %d down of %d"
                                        % (up, dn, len(b))))
            print("  %-34s %s  [set changed on %d/%d]"
                  % (label, "  ".join(cells), swapped, len(rows)))
        print("  A row of zeros with a changed displayed SET means the re-rank")
        print("  swapped chunks that carry no expected ref -- it fired and")
        print("  bought nothing, which is a different finding from inertness.")

        # ---- where the budget went ------------------------------------------
        print("\n== DISPLAYED CHUNKS PER DOC (all sets pooled) ==")
        print("  %-34s %-7s %-7s %-7s %-10s %s" % (
            "arm", "act", "const", "factsh", "shown", "act share"))
        for label, _rr, _p, _pin, _u, _d in ARMS:
            r = results[label]
            tot = {d: sum(r[s]["mix"][d] for s in LABELS)
                   for d in ("act2018", "constitution1999", "factsheet2020")}
            n = sum(tot.values()) or 1
            print("  %-34s %-7d %-7d %-7d %-10s %.0f%%" % (
                label, tot["act2018"], tot["constitution1999"],
                tot["factsheet2020"],
                "%d-%d" % (min(r[s]["shown_med"] for s in LABELS),
                           max(r[s]["shown_max"] for s in LABELS)),
                100 * tot["act2018"] / n))
        print("  E1's finding was that the Act's share collapses when the pool")
        print("  widens at a fixed budget. Here the budget IS fixed at 4/doc by")
        print("  construction, so a moving share would mean the pin changed the")
        print("  allocation, not that the Constitution flooded the merge.")

    # ---- b sensitivity: reported, never chosen ---------------------------
    print("\n== b SENSITIVITY AT pool=20/doc, PINNED (REPORTED, NEVER CHOSEN) ==")
    print("  b=%.2f ships regardless -- it is the textbook default. This block" % BM25_B)
    print("  exists to answer one question: is the arm knife-edge on b? If it")
    print("  is, that is evidence AGAINST shipping it. Fitting b to these")
    print("  columns is exactly how the synonym map was built.")
    print("  %-10s %-9s %-9s %-9s" % ("b", "frozen10", "dev", "test"))
    for b in B_SWEEP:
        configure(ret, "bm25", 20, True, False, b=b)

        def hits_for(row):
            return select_top(ret.query(row["text"], k=K_PER_DOC), TOP_N,
                              min_per_doc=MIN_PER_DOC)
        m = {s: measure(by_set[s], hits_for) for s in LABELS}
        print("  b=%-8.2f %-9s %-9s %-9s" % (
            b, fmt(m["frozen10"]["strict"]), fmt(m["heldout"]["strict"]),
            fmt(m["test"]["strict"])))

    if sweep_only:
        print("\nABLATE_RERANK: PASS (--b-sweep-only; no arms measured)")
        return 0

    # ---- refusal invariance ----------------------------------------------
    print("\n== REFUSAL INVARIANCE (the only thing that can fail here) ==")
    ctl_tops = {s: results[ARMS[0][0]][s]["tops"] for s in LABELS}
    bad, priced = [], []
    for label, _rr, _pool, pin, _u, diag in ARMS:
        r = results[label]
        tot = sum(r[s]["false_ref"] for s in LABELS)
        n = sum(r[s]["n_ans"] for s in LABELS)
        same = all(r[s]["tops"] == ctl_tops[s] for s in LABELS)
        print("  %-34s %d/%d false refusals | top-score vector %s control"
              % (label, tot, n, "==" if same else "!=" ))
        if tot:
            # Test-set IDs withheld by default, same rule as eval_heldout.py --
            # the COUNT is always printed, only the tuning handle is hidden.
            names = sorted(x for s in LABELS for x in r[s]["offenders"]
                           if s != "test" or reveal_test)
            if not names:
                names = ["(test IDs withheld -- pass --reveal-test)"]
            (priced if diag else bad).append(
                "%s: %d false refusals (%s)" % (label, tot, ", ".join(names)))
        elif pin and not same:
            bad.append("%s: pinned arm moved the top-score vector" % label)
    print("  Every PINNED arm must leave the top-score vector bit-identical to")
    print("  the control: the pin guarantees each doc's cosine argmax is")
    print("  returned, select_top provably keeps the global max, and refusal")
    print("  <=> global max < MIN_SCORE. Arm 4 drops the pin ON PURPOSE -- its")
    print("  row is the PRICE of the guard, not a regression of this harness.")
    if priced:
        print("\n  GUARD PRICED -- the unpinned arm did what the pin exists to stop:")
        for p in priced:
            print("    - %s" % p)
    elif any(d for _l, _r, _p, _pin, _u, d in ARMS):
        print("\n  GUARD PRICED: the unpinned arm produced NO false refusal on")
        print("  these 60 questions. That prices the pin at zero HERE; it does")
        print("  not make it safe to drop, because the proof is what makes the")
        print("  MIN_SCORE calibration valid on questions nobody has measured.")

    if ctl_bad:
        print("\nABLATE_RERANK: FAIL -- control arm does not reproduce E1b on %s"
              % ", ".join(ctl_bad))
        return 1
    if bad:
        print("\nABLATE_RERANK: FAIL")
        for b in bad:
            print("  - %s" % b)
        return 1
    print("\nABLATE_RERANK: PASS (arms measured; recall numbers are findings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
