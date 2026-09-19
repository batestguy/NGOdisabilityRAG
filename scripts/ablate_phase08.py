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
from evalset import strict_covered  # noqa: E402
from rag import CORPUS_VERSION, build_corpus  # noqa: E402
from retrieve import MIN_SCORE, PerDocRetriever, select_top  # noqa: E402

K_PER_DOC = 3   # ask() / eval_phase06 depth
TOP_N = 6       # ask() / eval_phase06 merge width
MIN_PER_DOC = 1  # ask() default -- the doc-quota merge, Phase 09 step 3 M2

# ---- the absolute recall gate, re-scoped per corpus at D6 (2026-09-19).
# 0.75 was a corpus v1 PLAIN-recall threshold on the frozen 10, and it kept
# that meaning silently when --corpus=v2 was added: ablate_v2.txt:28 reads
# "gate recall>0.75: before FAIL, after FAIL" and the run exits FAIL, on a
# comparison that is not legitimate. Corpus v2 splits packed refs, so plain
# recall falls for reasons that have nothing to do with expansion -- which is
# the ONLY thing this harness varies. Exactly the defect eval_heldout.py's
# frozen-10 guard had, on the same 10 questions.
#
# So: v1 keeps gating plain recall at 0.75; v2 gates recall_strict, the only
# recall comparison legitimate across corpus versions. Each arm PRINTS the
# metric it does not gate.
#
# The v2 floor is NOT a quality target -- it is the D5-measured value recorded
# as a tripwire, so a future expansion change that degrades the shipping arm
# cannot pass unnoticed. Raising it is a Phase E result, never a D6 edit.
ABLATE_MIN_RECALL_V1 = 0.75
ABLATE_MIN_STRICT_V2 = 0.632738   # NOT 0.633: see eval_heldout.py's note
ABLATE_EPS = 1e-6

# The v2 arm compares with >= and a tolerance, NOT the bare > the v1 arm uses.
# The constant is the true value 0.63273809... TRUNCATED to six places, so a
# bare > passed only because truncation happened to fall below the measured
# number. Rounding to 0.632738 the other way would have failed the run it was
# derived from. The tolerance makes that independent of which way it rounds.

# Off-corpus battery. The first version of this harness only asked "does
# expansion starve a GOOD question below the floor?" and never asked the
# opposite -- whether it pushes a BAD one above it. It does, or did: review
# 2026-09-11 found "my job interview went badly" going 0 hits -> 6 hits
# because the "job" entry fired. MIN_SCORE's one documented job is refusing
# zero-overlap queries, and app.py's "Ask a Legal Question" button forces the
# legal route, so that was reachable in one click by any user.
#
# Every probe below is off-corpus BUT deliberately carries a word that is a
# SYNONYMS trigger (job, car, house, bus, money, court, school, compliance,
# doctor, hospital). The existing regression probe in test_phase05.py
# ("quantum teleportation zebra unleaded gasoline") cannot catch this class:
# it avoids every key, so it gives false confidence.
#
# NOTE on the two expected non-zero baselines: "sourdough" (0.125) and
# "maritime shipping insurance law" (0.318) already cleared the floor BEFORE
# any of this work. That is the inverted-band limitation documented in the
# MIN_SCORE calibration block -- pre-existing, not caused here. The assertion
# is therefore not "these score zero" but the sharper, testable one: expansion
# must not flip ANY query from refused to answered.
OFF_CORPUS = [
    "my job interview went badly",
    "my car broke down on the way home",
    "I want to buy a house in Lagos",
    "I have no money for the bus",
    "which school did Messi go to",
    "how do I bake sourdough bread",
    "quantum computing entanglement",
    "maritime shipping insurance law",
    "the tennis court surface at Wimbledon",
    "book me a doctor appointment at the hospital",
    "regulatory compliance for crypto exchanges",
    "quantum teleportation zebra unleaded gasoline",
]


def measure(ret, questions, expand: bool) -> list[dict]:
    """Per-question recall + score profile with expansion on or off."""
    real = retrieve.expand_query
    if not expand:
        retrieve.expand_query = lambda q: q
    try:
        rows = []
        for i, q in enumerate(questions):
            qid = "Q%d" % (i + 1)
            hits = select_top(ret.query(q, k=K_PER_DOC), TOP_N,
                              min_per_doc=MIN_PER_DOC)
            exp = EXPECTED[qid]
            exp_pairs = {(d, n) for d, ns in exp.items() for n in ns}
            ret_pairs = {(h.doc_id, n) for h in hits for n in ref_nums(h.ref)}
            kept = [h for h in hits if h.score >= MIN_SCORE]
            rows.append({
                "id": qid,
                "recall": len(exp_pairs & ret_pairs) / len(exp_pairs),
                # Each chunk counts at most ONCE, so a packed `cl. 16,17` ref
                # cannot satisfy two expected refs from one slot. The only
                # recall comparison legitimate across corpus versions.
                "recall_strict": strict_covered(hits, exp) / len(exp_pairs),
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


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    # EQUALS FORM ONLY (repo convention: the space form is silently ignored).
    corpus = next((a.split("=", 1)[1] for a in argv
                   if a.startswith("--corpus=")), None)

    # D6 found this harness had NO corpus stamp at all -- worse than the five
    # wrong ones, since the shape dict below is the only thing that identified
    # the corpus and nothing named the version. Sixth site, same class.
    stamp = corpus or CORPUS_VERSION

    questions = load_questions()
    assert len(questions) == 10
    docs = build_corpus(corpus)
    print("CORPUS_VERSION=%s" % stamp)
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
    sb = sum(r["recall_strict"] for r in before.values()) / len(before)
    sa = sum(r["recall_strict"] for r in after.values()) / len(after)
    print("  %-4s %-16.3f %-16.3f %-+7.3f" % ("MEAN", mb, ma, ma - mb))
    if stamp == "v1":
        gate_ok = ma > ABLATE_MIN_RECALL_V1
        print("  gate recall>0.75: before %s, after %s"
              % ("PASS" if mb > ABLATE_MIN_RECALL_V1 else "FAIL",
                 "PASS" if gate_ok else "FAIL"))
        print("  strict %.3f -> %.3f (%+.3f) -- printed, not gated on v1"
              % (sb, sa, sa - sb))
    else:
        # v2 gates the strict column. Plain recall stays PRINTED above,
        # ungated: it is not comparable across corpus versions.
        gate_ok = sa >= ABLATE_MIN_STRICT_V2 - ABLATE_EPS
        print("  %-4s %-16.3f %-16.3f %-+7.3f  (strict)"
              % ("MEAN", sb, sa, sa - sb))
        print("  gate strict>=%.3f: before %s, after %s"
              % (ABLATE_MIN_STRICT_V2,
                 "PASS" if sb >= ABLATE_MIN_STRICT_V2 - ABLATE_EPS else "FAIL",
                 "PASS" if gate_ok else "FAIL"))
        print("    ^ plain recall above is PRINTED, NOT GATED: v2 splits")
        print("      packed refs, so it falls for reasons unrelated to the")
        print("      one thing this harness varies. v1's 0.75 is not a")
        print("      threshold a v2 run can be measured against.")

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

    print("\n== OFF-CORPUS FLOOR INTEGRITY (the direction the first harness missed) ==")
    print("  Expansion must not flip any query from refused to answered.")
    print("  %-46s %-14s %-14s %s" % ("query", "before", "after", ""))
    flips = []
    for p in OFF_CORPUS:
        b = measure_one(ret, p, expand=False)
        a = measure_one(ret, p, expand=True)
        flipped = b["n_kept"] == 0 and a["n_kept"] > 0
        if flipped:
            flips.append(p)
        print("  %-46s %.4f/%-6d %.4f/%-6d %s" % (
            p[:45], b["top"], b["n_kept"], a["top"], a["n_kept"],
            "<== FLOOR DEFEATED" if flipped else ""))
    print("  refused -> answered flips: %s" % (", ".join(flips) if flips else "none"))

    # The mirror image, and the case the first two arms both missed. A bare
    # trigger word is the SHORTEST possible on-topic query, so it has the least
    # mass to lose when expansion appends terms that are absent from the
    # best-matching chunk -- appending dilutes the query vector's norm without
    # adding numerator mass, so the cosine can DROP below the floor. Measured
    # 2026-09-11: "blind" scored 0.1367 on Act cl.20 and expanded to 0.0821,
    # i.e. a legitimate question about blindness would have been REFUSED.
    # CLAUDE.md: false refusals deny help to PWDs. Every curated key is probed
    # bare, so the harness can never again be blind to "blind".
    print("\n== FALSE-REFUSAL INTEGRITY (every SYNONYMS key, queried bare) ==")
    print("  Expansion must not flip any answerable query to refused.")
    false_ref = []
    for key in retrieve.SYNONYMS:
        b = measure_one(ret, key, expand=False)
        a = measure_one(ret, key, expand=True)
        if b["n_kept"] > 0 and a["n_kept"] == 0:
            false_ref.append(key)
            print("  %-16s %.4f/%-3d -> %.4f/%-3d  <== FALSE REFUSAL"
                  % (key, b["top"], b["n_kept"], a["top"], a["n_kept"]))
    print("  probed %d keys; answered -> refused flips: %s"
          % (len(retrieve.SYNONYMS), ", ".join(false_ref) if false_ref else "none"))

    ok = not bad and not flips and not false_ref and gate_ok
    print("\nABLATION: %s" % ("PASS" if ok else "FAIL"))
    if not ok:
        raise SystemExit(1)


def measure_one(ret, q: str, expand: bool) -> dict:
    """Score profile for a single free-text query (off-corpus battery)."""
    real = retrieve.expand_query
    if not expand:
        retrieve.expand_query = lambda x: x
    try:
        hits = select_top(ret.query(q, k=K_PER_DOC), TOP_N,
                          min_per_doc=MIN_PER_DOC)
        kept = [h for h in hits if h.score >= MIN_SCORE]
        return {"top": hits[0].score if hits else 0.0, "n_kept": len(kept)}
    finally:
        retrieve.expand_query = real


if __name__ == "__main__":
    main()
