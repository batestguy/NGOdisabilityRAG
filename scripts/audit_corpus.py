"""Corpus shape audit -- the gate that Phase 10 C has to pass.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\audit_corpus.py  (from D:\\NGORAG)
     ... --json=<path>    also write the table as JSON for diffing
     ... --corpus=<ver>   audit a specific corpus version instead of the
                          rag.CORPUS_VERSION default. EQUALS FORM ONLY.

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
Phase D builds the real manifest by parsing the Arrangement, at which point
`act_ref()` is demoted to a validator and this script reports whether the two
AGREE. Until then the ACT MANIFEST section says plainly that it is single-source.

**Amended 2026-09-18 (D2 review).** The sentence above used to promise "two
independent sources that must match, the same discipline as
evalset.assert_frozen10_matches_notebook()". That overstated it, and the v2
report now says so in place: the header act_ref() reads is written by the parser
from the same clause number the ref is built from, so for a single-clause chunk
the comparison is close to a tautology. The two sources differ in INFERENCE, not
in upstream -- which is not the frozen10 discipline, where the notebook and the
JSON really are authored separately. See act_ref_validator()'s docstring for what
it can and cannot still catch, and re-scope it before D6 asserts on it.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from evalset import ref_nums  # noqa: E402
from rag import (  # noqa: E402
    ACT_SIZE,
    ACT_V2_PATH,
    ACT_V2_SIZE,
    CONST_SIZE,
    CORPUS_VERSION,
    FACT_SIZE,
    act_ref,
    build_corpus,
)


# Size cap per doc, for the "at the cap" histogram column. A chunk sitting ON
# the cap was cut by length rather than by structure, which in v2 is only
# legitimate for a subsection split.
#
# The Act's cap is VERSION-DEPENDENT: v1 splits at ACT_SIZE (800), v2 at
# ACT_V2_SIZE (1100). Auditing v2 against v1's cap would report most v2 chunks
# as OVER cap; auditing v1 against v2's cap would silently widen the tripwire.
# The other two docs are unaffected -- D3/D4 have not happened yet.
def size_caps(version: str) -> dict:
    return {"act2018": ACT_SIZE if version == "v1" else ACT_V2_SIZE,
            "constitution1999": CONST_SIZE,
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
#
# 2026-09-17 (Phase 10 D0): the gazette scan is now filed at
# data/raw/disability_act_2018_gazette_FGP.pdf and is the authoritative source
# corpus v2 is rebuilt from. If the D2 re-OCR recovers cl.38's body, this set is
# DELETED by D6 -- not emptied, not left as `set()`. An empty set here would
# read as "we checked and nothing is absent", which is a different claim from
# "this exclusion no longer exists". Until D6 lands, it stays exactly as is.
#
# 2026-09-18 (Phase 10 D2): THAT CONDITION IS NOW SATISFIED -- recorded as fact,
# not as a hope. The gazette re-OCR recovered cl.38's body: "formulate and
# implement policies" is PRESENT in v2's clause 38 and ABSENT from v1 (grep,
# Finding 1). cl.40 was never absent (body at v1 L545, numeral OCR'd away). Both
# entries are therefore false, for different reasons. The set nonetheless STAYS
# until D6 deletes it: removing it here would make this script's v1-tripwire
# stdout diverge from the sealed baseline for no gain, and being comparable is
# the tripwire's whole job. A comment costs no stdout.
ACT_KNOWN_ABSENT = {38, 40}

# ---- v1 recorded shape. A tripwire, not an aspiration. ------------------
# Measured 2026-09-13, reproduced independently 2026-09-15. Any drift here
# means the corpus moved under every published baseline in the repo.
V1_EXPECTED = {
    "act2018": {"n": 62, "general": 25, "packed": 16},
    "constitution1999": {"n": 2104, "general": 99, "packed": 0},
    "factsheet2020": {"n": 48, "general": 9, "packed": 19},
}

# Content digest of the whole corpus. The nine integers above are a SHAPE check:
# they cannot see text MOVING BETWEEN CHUNKS at constant count -- which is
# exactly what a splitter change does. This closes that hole. Pinned 2026-09-17
# at D1, against the same build the published baselines were measured on.
V1_CORPUS_SHA256 = "25650238c3f2daf0523297680b41b3bd2318425c9690d9fa8a1e1caf1b42e89a"


def corpus_sha256(docs: dict[str, list]) -> str:
    """sha256 over (doc_id, ref, text) of every chunk, in iteration order.

    Order is part of the digest on purpose: PerDocRetriever breaks score ties by
    the insertion order of this dict (src/retrieve.py:331-338), so a reordering
    that leaves all nine shape numbers identical can still move published
    rankings. NUL separators cannot occur in the corpus text, so no (ref, text)
    boundary is ambiguous.
    """
    h = hashlib.sha256()
    for doc_id, chunks in docs.items():
        for c in chunks:
            h.update(("%s\0%s\0%s\0" % (doc_id, c.ref, c.text)).encode("utf-8"))
    return h.hexdigest()

# ---- v2 gate (Phase 10 C exit criteria). --------------------------------
V2_MAX_GENERAL_PCT = 1.0   # uncitable chunks, per doc
V2_MAX_PACKED = 0          # packed refs must be gone: one clause, one chunk


def audit_doc(doc_id: str, chunks: list, caps: dict) -> dict:
    cap = caps[doc_id]
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


def length_histogram(doc_id: str, chunks: list, caps: dict) -> None:
    """Decile buckets against the size cap. Reveals whether the splitter is
    cutting on structure or on length -- a spike in the top bucket means
    length, which is what makes chunk size (and therefore every cosine, and
    therefore MIN_SCORE) an artifact of the splitter rather than the text."""
    cap = caps[doc_id]
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


def act_manifest_flags() -> dict:
    """Degradation flags recorded by the D2 parser, read from the manifest.

    v2 only. The parser flags a clause TITLE_WEAK / NUMERAL_MISSING when it
    located it on a degraded anchor, and today all 58 are clean. But nothing
    downstream looks: _act_chunks_v2() does not inspect `flags`, so a manifest
    regenerated with degraded acceptances would be promoted to fully-citable
    chunks with no signal anywhere -- and D6 deletes ACT_KNOWN_ABSENT on the
    strength of this manifest. Surfacing the count is what keeps that honest.
    Added 2026-09-18 on a review finding, before D6 hardens the gate.
    """
    man = json.loads(ACT_V2_PATH.read_text(encoding="utf-8"))
    flagged = [(c["n"], c["flags"]) for c in man["clauses"] if c.get("flags")]
    return {
        "located": man.get("located"),
        "missing": man.get("missing", []),
        "title_source": man.get("title_source"),
        "flagged": flagged,
    }


def act_ref_validator(chunks: list) -> dict:
    """Cross-check the parser's refs against act_ref()'s heading-shape inference.

    v2 only. `chunk.ref` comes from the gazette Arrangement manifest
    (src/rag.py::_act_chunks_v2, path=="manifest"); act_ref() reads the chunk
    text and infers a ref from heading shape.

    *** READ THIS BEFORE D6 PROMOTES IT TO AN ASSERT. ***
    2026-09-18 review finding: for a SINGLE-CLAUSE chunk this is very close to a
    TAUTOLOGY, and the 100% rate below is worth much less than it looks. The two
    sources are not independent: the parser writes header = "%d. %s" % (n, title)
    from the same `n` it builds the ref from, _act_chunks_v2() prefixes that
    header to every sub-chunk, and act_ref() then recovers the leading `\\d+\\.`
    from that very string. So it mostly checks the parser's numeral against the
    parser's own field -- true by construction, not by two derivations meeting.
    They are independent in their INFERENCE (manifest lookup vs heading-shape
    regex) but share an UPSTREAM.

    What it can still genuinely catch: a stray line-start "NN." in body text
    flipping act_ref() to a multi-number member list, and a header/ref mismatch
    introduced by future chunking changes. That is real but narrow. D6 should
    either validate against the Arrangement TITLE text (which does not share the
    numeral's upstream) or scope the assert to those cases -- NOT promote this
    rate as-is and call it a cross-source gate.

    D2 MEASURES AND REPORTS ONLY. No assert, and act_ref() is NOT adjusted to
    make the numbers meet -- tuning the validator against the thing it validates
    would destroy what value it has.
    """
    rows = []
    for i, c in enumerate(chunks):
        got = act_ref(c.text)
        if got != c.ref:
            rows.append((i, c.ref, got))
    n = len(chunks)
    return {
        "n": n,
        "agree": n - len(rows),
        "rate": (n - len(rows)) / n if n else 0.0,
        "disagree": rows,
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    json_out = next((a.split("=", 1)[1] for a in argv
                     if a.startswith("--json=")), None)
    # EQUALS FORM ONLY, matching --json= above. The space form is silently
    # ignored repo-wide; a "--corpus v2" that quietly measured v1 and published
    # the number as v2 is the exact failure this stamp exists to prevent.
    corpus = next((a.split("=", 1)[1] for a in argv
                   if a.startswith("--corpus=")), None)

    docs = build_corpus(corpus)
    version = corpus or CORPUS_VERSION
    print("== CORPUS AUDIT (CORPUS_VERSION=%s) ==" % version)
    print("  mode: %s" % ("v1 regression tripwire -- pinned to the recorded "
                          "shape, does NOT fail for being bad"
                          if version == "v1"
                          else "v2 quality gate"))

    caps = size_caps(version)
    stats = {d: audit_doc(d, c, caps) for d, c in docs.items()}

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
        length_histogram(d, docs[d], caps)
    print("  Phase 10 C reads this table before touching chunk sizes: short")
    print("  chunks concentrate term mass and INFLATE cosine, so any shift here")
    print("  silently recalibrates MIN_SCORE and can manufacture false")
    print("  refusals -- the worst failure mode this project has.")

    cov = act_manifest_coverage(docs["act2018"])
    val = act_ref_validator(docs["act2018"]) if version != "v1" else None
    print("\n== ACT CLAUSE MANIFEST COVERAGE (1-58) ==")
    if version == "v1":
        print("  SINGLE-SOURCE for now: derived from the corpus's own refs, not")
        print("  from an independent parse of the Arrangement of Sections. It is a")
        print("  coverage report, not a cross-check. Phase 10 C parses the")
        print("  Arrangement and asserts the two sources AGREE.")
    else:
        print("  CROSS-CHECK, AND ITS LIMIT (read before trusting the number):")
        print("  refs come from the gazette Arrangement manifest; act_ref()")
        print("  infers them from heading SHAPE. But the header act_ref() reads")
        print("  is built BY THE PARSER from the same clause number the ref uses,")
        print("  so for a single-clause chunk this is close to a TAUTOLOGY -- the")
        print("  two differ in inference, not in upstream. It catches a stray")
        print("  line-start \"NN.\" in body text and header/ref drift from future")
        print("  chunking changes; it is NOT the cross-source gate the playbook")
        print("  once described. D2 MEASURES and REPORTS only; D6 must re-scope")
        print("  it before asserting. act_ref() is not adjusted to make them meet.")
        print("  act_ref() agreement:    %d/%d (%.1f%%)"
              % (val["agree"], val["n"], 100.0 * val["rate"]))
        print("    ^ discounted per the limit above -- not a 100% correctness"
              " claim.")
        fl = act_manifest_flags()
        print("  manifest: located %s/58, title_source %s, missing %s"
              % (fl["located"], fl["title_source"],
                 ", ".join(str(n) for n in fl["missing"]) or "none"))
        print("  clauses carrying a DEGRADATION flag: %s"
              % (", ".join("%d %s" % (n, f) for n, f in fl["flagged"])
                 or "none"))
        print("    ^ _act_chunks_v2() does not inspect flags, so a degraded")
        print("      manifest would chunk silently. D6 deletes ACT_KNOWN_ABSENT")
        print("      on this manifest's word -- check this line before it does.")
        if val["disagree"]:
            print("  DISAGREEMENTS (chunk index: manifest ref vs act_ref):")
            for i, ref, got in val["disagree"]:
                print("    %-5d %-12s vs %s" % (i, ref, got))
        else:
            print("  DISAGREEMENTS:          none")
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

    report = {"corpus_version": version, "docs": stats,
              "act_manifest": cov}
    if val is not None:
        report["act_ref_validator"] = val
    if json_out:
        Path(json_out).write_text(json.dumps(report, indent=2) + "\n",
                                  encoding="utf-8")
        print("\nwrote %s" % json_out)

    # ---- the gate -------------------------------------------------------
    fails: list[str] = []
    if version == "v1":
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
        got_sha = corpus_sha256(docs)
        ok = got_sha == V1_CORPUS_SHA256
        print("  %-18s %-8s recorded %s" % ("CORPUS", "sha256",
                                            V1_CORPUS_SHA256))
        print("  %-18s %-8s measured %s %s" % ("", "", got_sha,
                                               "ok" if ok else "DRIFT"))
        if not ok:
            fails.append(
                "corpus sha256: recorded %s, measured %s -- chunk CONTENT "
                "moved even though the nine shape numbers above may still "
                "match. A splitter change that shifts text between chunks at "
                "constant count looks exactly like this."
                % (V1_CORPUS_SHA256, got_sha))
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
