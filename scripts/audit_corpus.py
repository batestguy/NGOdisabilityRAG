"""Corpus shape audit -- the gate that Phase 10 C has to pass.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\audit_corpus.py  (from D:\\NGORAG)
     ... --json=<path>    also write the table as JSON for diffing

WHY THIS EXISTS
---------------
The single most important finding of Phase 09 was not a ranking number, it was
that **25 of 62 Act chunks carry ref=="general"** and are therefore uncitable.
The project's central invariant is *every legal claim carries a citation tag
copied verbatim from the chunk header*. With 40% of the Act uncitable that
invariant is structurally broken on the app's most important document, and a
better ranking over uncitable chunks is a better-ranked list of things you are
not allowed to cite.

That number had never been measured anywhere in the repo -- it took an ad-hoc
session to find it. This script makes it reproducible, then makes it a gate.

TWO MODES, SELECTED BY rag.CORPUS_VERSION
-----------------------------------------
v1  Regression tripwire. v1's corpus shape is KNOWN BAD and is pinned here
    exactly as measured. It fails if the shape MOVES -- because v1 is the
    corpus every published baseline in this repo was measured on, and a silent
    change to it would invalidate all of them without anyone noticing. It does
    NOT fail for being bad; that is the recorded state of the world.
v2  Quality gate, thresholds below. This is what Phase 10 C must clear before
    corpus v2 can be called done.

WHAT IT CANNOT CHECK YET
------------------------
The Act clause manifest is derived here from the corpus itself (which clause
numbers 1..58 appear in some ref), not from an independent parse of the
Arrangement of Sections. That makes it a coverage report, not a cross-check.
Phase 10 C builds the real manifest by parsing the Arrangement, at which point
`act_ref()` is demoted to a validator and this script asserts the two AGREE --
two independent sources that must match, the same discipline as
evalset.assert_frozen10_matches_notebook(). Until then the ACT MANIFEST section
says plainly that it is single-source.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from evalset import ref_nums  # noqa: E402
from rag import (  # noqa: E402
    ACT_SIZE,
    CONST_SIZE,
    CORPUS_VERSION,
    FACT_SIZE,
    build_corpus,
)

# Size cap per doc, for the "at the cap" histogram column. A chunk sitting ON
# the cap was cut by length rather than by structure, which in v2 is only
# legitimate for a subsection split.
SIZE_CAP = {"act2018": ACT_SIZE, "constitution1999": CONST_SIZE,
            "factsheet2020": FACT_SIZE}

# The Act has 58 clauses. Source: the Arrangement of Sections in
# data/processed/disability_act_2018_full.txt.
ACT_CLAUSES = range(1, 59)

# Clause bodies confirmed ABSENT FROM THE SOURCE PDF, not merely unparsed
# (LEARNING_JOURNAL.md 2026-09-13, re-confirmed 2026-09-15). The scan is 27
# pages with 0 embedded text chars; raw OCR pages 5 and 6 are the same physical
# page twice, so 27 raw pages cover 26 distinct pages of a 27-page instrument.
# The missing page carries cl.38's opening and cl.40. No OCR and no VLM can
# recover pixels that were never captured. Phase 10 C makes one targeted
# attempt at a second source (ncpwd.gov.ng) and then records the gap.
#
# THESE ARE EXCLUDED FROM THE COVERAGE GATE AND MUST NEVER BE "FIXED" BY
# WRITING A STUB CHUNK. A citation tag in front of a generation model is
# precisely how a gap becomes a hallucinated provision that passes
# verify_citations() mechanically.
ACT_KNOWN_ABSENT = {38, 40}

# ---- v1 recorded shape. A tripwire, not an aspiration. ------------------
# Measured 2026-09-13, reproduced independently 2026-09-15. Any drift here
# means the corpus moved under every published baseline in the repo.
V1_EXPECTED = {
    "act2018": {"n": 62, "general": 25, "packed": 16},
    "constitution1999": {"n": 2104, "general": 99, "packed": 0},
    "factsheet2020": {"n": 48, "general": 9, "packed": 19},
}

# ---- v2 gate (Phase 10 C exit criteria). --------------------------------
V2_MAX_GENERAL_PCT = 1.0   # uncitable chunks, per doc
V2_MAX_PACKED = 0          # packed refs must be gone: one clause, one chunk


def audit_doc(doc_id: str, chunks: list) -> dict:
    cap = SIZE_CAP[doc_id]
    lens = sorted(len(c.text) for c in chunks)
    n = len(chunks)
    general = [c for c in chunks if c.ref == "general"]
    packed = [c for c in chunks if len(ref_nums(c.ref)) > 1]
    return {
        "doc_id": doc_id,
        "n": n,
        "size_cap": cap,
        "general": len(general),
        "general_pct": 100.0 * len(general) / n if n else 0.0,
        "packed": len(packed),
        "packed_pct": 100.0 * len(packed) / n if n else 0.0,
        "len_min": lens[0] if lens else 0,
        "len_med": lens[n // 2] if lens else 0,
        "len_max": lens[-1] if lens else 0,
        "at_cap": sum(1 for x in lens if x >= cap),
        "over_cap": sum(1 for x in lens if x > cap),
        "refs": sorted({c.ref for c in chunks}),
    }


def length_histogram(doc_id: str, chunks: list) -> None:
    """Decile buckets against the size cap. Reveals whether the splitter is
    cutting on structure or on length -- a spike in the top bucket means
    length, which is what makes chunk size (and therefore every cosine, and
    therefore MIN_SCORE) an artifact of the splitter rather than the text."""
    cap = SIZE_CAP[doc_id]
    edges = [int(cap * f / 5) for f in range(1, 6)]
    buckets = [0] * (len(edges) + 1)
    for c in chunks:
        for i, e in enumerate(edges):
            if len(c.text) <= e:
                buckets[i] += 1
                break
        else:
            buckets[-1] += 1
    lo = 0
    for i, e in enumerate(edges):
        print("    %5d-%-5d %5d  %s" % (lo, e, buckets[i],
                                        "#" * min(60, buckets[i])))
        lo = e + 1
    print("    %5d+%-6s %5d  %s" % (lo, "", buckets[-1],
                                    "#" * min(60, buckets[-1])))


def act_manifest_coverage(chunks: list) -> dict:
    """Which of the Act's 58 clauses are reachable by number from some ref."""
    have = set()
    for c in chunks:
        if c.ref != "general":
            have |= ref_nums(c.ref)
    have &= set(ACT_CLAUSES)
    missing = sorted(set(ACT_CLAUSES) - have)
    return {
        "citable": sorted(have),
        "missing": missing,
        "missing_recoverable": [n for n in missing if n not in ACT_KNOWN_ABSENT],
        "missing_absent_from_source": [n for n in missing
                                       if n in ACT_KNOWN_ABSENT],
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    json_out = next((a.split("=", 1)[1] for a in argv
                     if a.startswith("--json=")), None)

    docs = build_corpus()
    print("== CORPUS AUDIT (CORPUS_VERSION=%s) ==" % CORPUS_VERSION)
    print("  mode: %s" % ("v1 regression tripwire -- pinned to the recorded "
                          "shape, does NOT fail for being bad"
                          if CORPUS_VERSION == "v1"
                          else "v2 quality gate"))

    stats = {d: audit_doc(d, c) for d, c in docs.items()}

    print("\n== PER DOC ==")
    print("  %-18s %-6s %-14s %-14s %-22s" % (
        "doc", "chunks", "uncitable", "packed refs", "length min/med/max"))
    for d in ("act2018", "constitution1999", "factsheet2020"):
        s = stats[d]
        print("  %-18s %-6d %-14s %-14s %d/%d/%d (cap %d)" % (
            d, s["n"], "%d (%.1f%%)" % (s["general"], s["general_pct"]),
            "%d (%.1f%%)" % (s["packed"], s["packed_pct"]),
            s["len_min"], s["len_med"], s["len_max"], s["size_cap"]))
    print("  uncitable   = ref==\"general\": retrievable, but no legal claim")
    print("                may be cited from it under the project invariant.")
    print("  packed refs = one chunk answering >1 expected number (`cl. 16,17`).")
    print("                These inflate plain recall; see")
    print("                evalset.strict_covered and recall_strict.")

    print("\n== LENGTH HISTOGRAMS (vs size cap) ==")
    for d in ("act2018", "constitution1999", "factsheet2020"):
        s = stats[d]
        print("  %s (cap %d, %d at cap, %d OVER cap):"
              % (d, s["size_cap"], s["at_cap"], s["over_cap"]))
        length_histogram(d, docs[d])
    print("  Phase 10 C reads this table before touching chunk sizes: short")
    print("  chunks concentrate term mass and INFLATE cosine, so any shift here")
    print("  silently recalibrates MIN_SCORE and can manufacture false")
    print("  refusals -- the worst failure mode this project has.")

    cov = act_manifest_coverage(docs["act2018"])
    print("\n== ACT CLAUSE MANIFEST COVERAGE (1-58) ==")
    print("  SINGLE-SOURCE for now: derived from the corpus's own refs, not")
    print("  from an independent parse of the Arrangement of Sections. It is a")
    print("  coverage report, not a cross-check. Phase 10 C parses the")
    print("  Arrangement and asserts the two sources AGREE.")
    print("  citable now:            %d/58" % len(cov["citable"]))
    print("  NOT citable, parseable: %s" % (
        ", ".join(str(n) for n in cov["missing_recoverable"]) or "none"))
    print("    ^ bodies present in the text, invisible only because act_ref()")
    print("      infers refs from heading SHAPE and the gazette's marginal-note")
    print("      column is spliced into the body. Recoverable by parsing, free.")
    print("      This is the Phase 10 C target.")
    print("  NOT citable, ABSENT from source: %s" % (
        ", ".join(str(n) for n in cov["missing_absent_from_source"]) or "none"))
    print("    ^ the pixels do not exist. No stub, no paraphrase, no model")
    print("      knowledge -- record the gap and tell the user to call DRAC.")

    report = {"corpus_version": CORPUS_VERSION, "docs": stats,
              "act_manifest": cov}
    if json_out:
        Path(json_out).write_text(json.dumps(report, indent=2) + "\n",
                                  encoding="utf-8")
        print("\nwrote %s" % json_out)

    # ---- the gate -------------------------------------------------------
    fails: list[str] = []
    if CORPUS_VERSION == "v1":
        print("\n== V1 REGRESSION TRIPWIRE ==")
        for d, exp in V1_EXPECTED.items():
            got = stats[d]
            for key in ("n", "general", "packed"):
                ok = got[key] == exp[key]
                print("  %-18s %-8s recorded %-6d measured %-6d %s"
                      % (d, key, exp[key], got[key], "ok" if ok else "DRIFT"))
                if not ok:
                    fails.append(
                        "%s.%s: recorded %d, measured %d -- corpus v1 moved "
                        "under every published baseline in the repo"
                        % (d, key, exp[key], got[key]))
    else:
        print("\n== V2 QUALITY GATE ==")
        for d in stats:
            s = stats[d]
            ok = s["general_pct"] <= V2_MAX_GENERAL_PCT
            print("  %-18s uncitable %.1f%% <= %.1f%%: %s"
                  % (d, s["general_pct"], V2_MAX_GENERAL_PCT,
                     "PASS" if ok else "FAIL"))
            if not ok:
                fails.append("%s: %.1f%% uncitable exceeds %.1f%%"
                             % (d, s["general_pct"], V2_MAX_GENERAL_PCT))
            ok = s["packed"] <= V2_MAX_PACKED
            print("  %-18s packed refs %d <= %d: %s"
                  % (d, s["packed"], V2_MAX_PACKED, "PASS" if ok else "FAIL"))
            if not ok:
                fails.append("%s: %d packed refs, must be %d"
                             % (d, s["packed"], V2_MAX_PACKED))
        unreached = cov["missing_recoverable"]
        print("  act clauses citable or in the gap manifest: %s"
              % ("PASS" if not unreached else
                 "FAIL (%s)" % ", ".join(str(n) for n in unreached)))
        if unreached:
            fails.append("act clauses %s are neither citable nor recorded as "
                         "absent from the source"
                         % ", ".join(str(n) for n in unreached))

    if fails:
        print("\nAUDIT_CORPUS: FAIL")
        for f in fails:
            print("  - %s" % f)
        return 1
    print("\nAUDIT_CORPUS: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
