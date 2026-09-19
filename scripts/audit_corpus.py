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
    CONST_REF_RE,
    CONST_SIZE,
    CORPUS_VERSION,
    FACT_ROW_RE,
    FACT_SIZE,
    FACT_V2_SIZE,
    act_ref,
    build_corpus,
    fact_v2_rows,
)


# Size cap per doc, for the "at the cap" histogram column. A chunk sitting ON
# the cap was cut by length rather than by structure, which in v2 is only
# legitimate for a subsection split.
#
# The Act's and the Factsheet's caps are VERSION-DEPENDENT: v1 splits the Act at
# ACT_SIZE (800) and the factsheet at FACT_SIZE (500); v2 splits them at
# ACT_V2_SIZE (1100) and FACT_V2_SIZE (900). Auditing v2 against v1's cap would
# report most v2 chunks as OVER cap; auditing v1 against v2's cap would silently
# widen the tripwire. The Constitution takes CONST_SIZE in BOTH versions and
# always will: D4 excludes the Arrangement REGION and deliberately does not touch
# the splitter or its size, so there is no CONST_V2_SIZE to key on here.
def size_caps(version: str) -> dict:
    return {"act2018": ACT_SIZE if version == "v1" else ACT_V2_SIZE,
            "constitution1999": CONST_SIZE,
            "factsheet2020": FACT_SIZE if version == "v1" else FACT_V2_SIZE}


# The Act has 58 clauses. Source: the Arrangement of Sections in
# data/processed/disability_act_2018_full.txt.
ACT_CLAUSES = range(1, 59)

# ACT_KNOWN_ABSENT = {38, 40} WAS HERE AND IS DELETED, NOT EMPTIED (D6,
# 2026-09-19). An empty set would read as "we checked and nothing is absent",
# which is a different claim from "this exclusion no longer exists" -- and it
# would be an invitation to re-add a clause. A deleted name is a NameError.
#
# It claimed both clauses were ABSENT FROM THE SOURCE PDF, unrecoverable by any
# OCR, and it EXCLUDED THEM FROM THE COVERAGE GATE. Both entries were false, for
# different reasons, and D2 established that as fact rather than hope:
#   cl.38  absent from the v1 PROCESSED TEXT only. The v1 scan has one physical
#          page recorded twice, so the page carrying cl.38's opening is missing.
#          The gazette has it: "formulate and implement policies" is present in
#          v2's clause 38 and absent from v1 (grep, D2 Finding 1).
#   cl.40  never absent at all -- body at v1 L545, the numeral was OCR'd away.
# v2 locates 58/58 clauses with zero degradation flags, so the exclusion covers
# nothing and is gone. What it must NOT become is a stub: a citation tag in
# front of a generation model is precisely how a gap becomes a hallucinated
# provision that passes verify_citations() mechanically.
#
# v1's report keeps ONE honest distinction, scoped to v1 and gating nothing.
# Without it, v1 would print cl.38 as "recoverable by parsing, free", which is
# false -- its text is not in the v1 corpus at any price. This is v1-descriptive
# only: the v2 gate does not read it, so it cannot soften anything shipping.
V1_ACT_ABSENT_FROM_TEXT = {38}

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

# The same tripwire for v2, pinned at D6 in the commit that flips the default.
# Without it the SHIPPING corpus would be less protected than the retired one,
# which is the exact inversion the fingerprint was introduced to prevent: the
# per-doc integers are a SHAPE check and cannot see text moving between chunks
# at constant count. Measured 2026-09-19 on the same build D6 re-baselines
# against; corpus_sha256() was validated in the same run by reproducing the v1
# digest above byte-for-byte.
V2_CORPUS_SHA256 = "56e3e434cdfe7cf09fc28caeed337629d3fb3263d45071097929be2e76b9cef4"


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

# D6 RE-SCOPE, 2026-09-19. Both thresholds above are right for the Act and
# each is wrong for exactly one other document -- measured at D3/D4, left
# FAILing in stdout with the reason beside it rather than tuned away, and
# resolved here:
#
#   constitution1999  general_pct <= 1.0 is UNREACHABLE. Arrangement exclusion
#                     is the whole of the available fix (99 -> 34 general) and
#                     the residual 34 is 8 structurally unnumbered chunks plus
#                     26 Chapter VIII Schedule/Rules chunks where `general` is
#                     the CORRECT answer -- a Schedule ITEM number is not a
#                     SECTION number, and labelling it `s. N` re-creates the
#                     Q10 misattribution class on purpose. Gated instead on
#                     toc_general_out_ch8 == 0, measured from chunk TEXT, with
#                     demonstrated discriminating power (v1 7, v2 0).
#   factsheet2020     packed <= 0 is UNREACHABLE and wrong. A multi-number ref
#                     is the S/N table's own content; eight of those numbers
#                     exist nowhere else in the document and
#                     evalset.verify_expected() -- a HARD assert -- needs every
#                     one. Gated instead on row_spanning == 0 (v1 26/48, v2 0).
#
# EVERY DOC STILL PRINTS BOTH ORIGINAL COLUMNS, gated or not. A re-scope that
# stops printing the superseded metric is indistinguishable from tuning the
# yardstick, so the numbers stay visible and only the GATING changes.
V2_GENERAL_PCT_GATED = frozenset({"act2018", "factsheet2020"})
V2_PACKED_GATED = frozenset({"act2018", "constitution1999"})
V2_MAX_TOC_GENERAL_OUT_CH8 = 0   # constitution1999
V2_MAX_ROW_SPANNING = 0          # factsheet2020

# The pinned inventory that covers the STATED Chapter VIII proxy hole (see the
# toc_general() note): "in the Schedules" is proxied by the "Chapter VIII"
# label, and Chapter VIII also holds operative sections 297-320, so a genuine
# body chunk wrongly demoted would land in the in-Ch-VIII bucket and be
# invisible to the gate above. A new demotion anywhere changes one of these
# two integers, which is what makes the proxy safe to rely on.
V2_CONST_GENERAL_INVENTORY = {"general_unnumbered": 8, "toc_general_in_ch8": 26}


# The factsheet's REAL defect metric, added at D3. `packed` cannot express it:
# a v2 factsheet ref legitimately carries several numbers, because the table row
# it is cut from genuinely discusses several sections and eight of those numbers
# exist nowhere else in the document (see rag._fact_chunks_v2). So `packed`
# stays reported and unhidden as the count it always was, and THIS is the number
# that says whether the S/N table was cut on its own rows.
#
# It is measured from the chunk TEXT, never from construction. "We emit one row
# per chunk, therefore 0" would restate the code and gate nothing; re-scanning
# the emitted text for a row-start line can actually fail. Its discriminating
# power is demonstrated, not assumed: v1 scores 26 of 48 factsheet chunks.
#
# v2's header line ("Section 45 Funds of the Commission") carries no leading S/N
# numeral, so FACT_ROW_RE cannot match it -- verified, not assumed. If a future
# header shape ever did match, the fix is the header, not an exemption here.
def row_spanning(chunks: list) -> int:
    """Chunks whose BODY still contains an S/N row-start line: cut across rows."""
    return sum(1 for c in chunks if FACT_ROW_RE.search(c.text))


# The Constitution's REAL defect metric, added at D4, and the exact twin of
# row_spanning above. `general` cannot express it either: after the Arrangement
# exclusion the Constitution still carries 34 uncitable chunks and NONE of them
# is a defect -- 8 have no section number at all (the Preamble, chapter-divider
# headings) and 26 are Chapter VIII Schedule / Enforcement-Procedure-Rules items
# where `general` is the CORRECT ref, because a Schedule ITEM number is not a
# SECTION number and labelling "8. Census" as `s. 8` would deliberately re-create
# the Q10 misattribution class. So `general` stays reported as the count it
# always was, and THIS is the number that says whether Arrangement-of-Sections
# listing text is still being chunked as though it were the body.
#
# Measured from the chunk TEXT, never from construction. "We excluded the
# Arrangement, therefore 0" would restate rag._const_chunks_v2() and gate
# nothing; asking each emitted chunk whether it carries a §N prefix that
# const_ref()/_is_toc_fragment then DEMOTED can actually fail. Its discriminating
# power is demonstrated, not assumed: **v1 scores 7 outside Chapter VIII, v2
# scores 0** -- and the 7th v1 chunk is the Q10 trap chunk itself,
# `Chapter IV ... §39: "ion from fundamental human rights. 46 Special
# jurisdiction of High Court and Legal aid."`. D4 deletes it from existence
# where _is_toc_fragment only ever relabelled it.
#
# STATED LIMITATION, not to be papered over: "in the Schedules" is PROXIED by the
# "Chapter VIII" label that constitution_aware_split() prepends, because the
# Schedules and the Rules physically sit inside that chapter's block. Chapter
# VIII also holds OPERATIVE sections 297-320, so a genuine Chapter VIII body
# chunk wrongly demoted by the heuristic would land in the in-Ch-VIII bucket and
# be invisible to the gate. The pinned 8 + 26 inventory printed below is what
# covers that hole -- a new demotion anywhere changes one of those two integers.
#
# The 160-char window is const_ref()'s own (src/rag.py), so this asks exactly the
# question const_ref() asked. Act and factsheet chunks carry no §N prefix at all,
# so they score 0/0 on it by nature rather than by exemption.
def toc_general(chunks: list) -> tuple[int, int]:
    """(outside Chapter VIII, inside Chapter VIII) TOC-demoted uncitable chunks."""
    out = inside = 0
    for c in chunks:
        if c.ref != "general" or not CONST_REF_RE.search(c.text[:160]):
            continue
        if "Chapter VIII" in c.text[:160]:
            inside += 1
        else:
            out += 1
    return out, inside


def audit_doc(doc_id: str, chunks: list, caps: dict) -> dict:
    cap = caps[doc_id]
    lens = sorted(len(c.text) for c in chunks)
    n = len(chunks)
    general = [c for c in chunks if c.ref == "general"]
    packed = [c for c in chunks if len(ref_nums(c.ref)) > 1]
    toc_out, toc_in = toc_general(chunks)
    return {
        "doc_id": doc_id,
        "n": n,
        "size_cap": cap,
        "general": len(general),
        "general_pct": 100.0 * len(general) / n if n else 0.0,
        # The `general` count decomposed, so a NEW uncitable chunk is visible
        # rather than averaging away inside a percentage that is already failing.
        "general_unnumbered": len(general) - toc_out - toc_in,
        "general_toc": toc_out + toc_in,
        "toc_general_out_ch8": toc_out,
        "toc_general_in_ch8": toc_in,
        "packed": len(packed),
        "packed_pct": 100.0 * len(packed) / n if n else 0.0,
        "row_spanning": row_spanning(chunks),
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
    # No exclusion set. Every missing clause counts against the gate; the v1
    # split below is descriptive reporting, not a carve-out (see
    # V1_ACT_ABSENT_FROM_TEXT).
    return {
        "citable": sorted(have),
        "missing": missing,
        "missing_recoverable": [n for n in missing
                                if n not in V1_ACT_ABSENT_FROM_TEXT],
        "missing_absent_from_text": [n for n in missing
                                     if n in V1_ACT_ABSENT_FROM_TEXT],
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


def fact_row_flags() -> dict:
    """Degradation flags recorded by the D3 row parse, read from rag.

    v2 only, and the exact twin of act_manifest_flags(): _fact_chunks_v2() does
    not inspect `flags`, so a row whose title failed to parse would still be
    promoted to a fully-citable chunk with no signal anywhere. The audit reads
    fact_v2_rows() -- the SAME function the chunker calls -- so the report and
    the corpus cannot drift into describing different parses.

    The S/N sequence is reported for the same reason the Act's `located 58/58`
    is: a silently truncated table would otherwise look like a clean small one.
    """
    rows = fact_v2_rows()
    sns = [r["sn"] for r in rows]
    return {
        "n": len(rows),
        "sn_first": sns[0] if sns else None,
        "sn_last": sns[-1] if sns else None,
        "sn_contiguous": sns == list(range(1, len(sns) + 1)),
        "flagged": [(r["sn"], r["flags"]) for r in rows if r["flags"]],
        "multi_number_refs": sum(1 for r in rows if r["xrefs"]),
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
    introduced by future chunking changes. That is real but narrow.

    D6 SCOPED IT TO EXACTLY THOSE TWO CASES (2026-09-19) and did NOT promote
    the rate. The v2 gate asserts `disagree` is EMPTY -- a chunk whose heading
    shape contradicts its manifest ref -- and says nothing about the 65/65
    figure, which remains reported and explicitly discounted. The alternative
    the review offered, validating against the Arrangement TITLE, was NOT
    taken: the manifest's titles come from the Arrangement too, so it would
    have swapped one shared upstream for another while looking independent.
    A narrow gate that is honest about its reach beats a broad one that is not.

    act_ref() is NOT adjusted to make the numbers meet -- tuning the validator
    against the thing it validates would destroy what value it has.
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
    print("  %-18s %-6s %-14s %-14s %-9s %-9s %-22s" % (
        "doc", "chunks", "uncitable", "packed refs", "row-span", "toc-gen",
        "length min/med/max"))
    for d in ("act2018", "constitution1999", "factsheet2020"):
        s = stats[d]
        print("  %-18s %-6d %-14s %-14s %-9d %-9s %d/%d/%d (cap %d)" % (
            d, s["n"], "%d (%.1f%%)" % (s["general"], s["general_pct"]),
            "%d (%.1f%%)" % (s["packed"], s["packed_pct"]), s["row_spanning"],
            "%d/%d" % (s["toc_general_out_ch8"], s["toc_general_in_ch8"]),
            s["len_min"], s["len_med"], s["len_max"], s["size_cap"]))
    print("  uncitable   = ref==\"general\": retrievable, but no legal claim")
    print("                may be cited from it under the project invariant.")
    print("  packed refs = one chunk answering >1 expected number (`cl. 16,17`).")
    print("                These inflate plain recall; see")
    print("                evalset.strict_covered and recall_strict.")
    print("  row-span    = chunks whose TEXT still holds a factsheet S/N")
    print("                row-start line, i.e. cut ACROSS table rows. Act and")
    print("                Constitution score 0 on it; the factsheet is what it")
    print("                measures, and on v2 it -- not `packed` -- is the")
    print("                factsheet's real defect count. Added at D3.")
    print("  toc-gen     = uncitable chunks that DO carry a Constitution")
    print("                section marker, i.e. _is_toc_fragment demoted")
    print("                them, shown OUTSIDE/INSIDE Chapter VIII. Outside")
    print("                is Arrangement-of-Sections listing text and is the")
    print("                Constitution's real defect count (v1 7, v2 0);")
    print("                inside is Schedule / Rules items, where `general`")
    print("                is the CORRECT ref. Act and factsheet carry no")
    print("                section marker and score 0/0. Added at D4.")

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
        print("      manifest would chunk silently. D6 DELETED ACT_KNOWN_ABSENT")
        print("      on this manifest's word, having checked this line first;")
        print("      it read 58/58 located, title_source arrangement, no flags.")
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
    print("  NOT citable, ABSENT from this corpus's text: %s" % (
        ", ".join(str(n) for n in cov["missing_absent_from_text"]) or "none"))
    print("    ^ v1 only, and NOT 'the pixels do not exist' -- that claim was")
    print("      false. The v1 scan repeats one physical page, so cl.38's")
    print("      opening is missing from the v1 TEXT; the gazette has it and v2")
    print("      carries it. Gates nothing: ACT_KNOWN_ABSENT is deleted and the")
    print("      v2 gate reads the raw missing list. No stub, no paraphrase, no")
    print("      model knowledge -- a gap is recorded, never written.")

    # Printed for BOTH versions, deliberately: the inventory only means anything
    # next to the number it replaced (v1 99 = 66 + 33), and a metric shown on v2
    # alone has no demonstrated ability to fail. Same argument as D3's row-span.
    cs = stats["constitution1999"]
    print("\n== CONSTITUTION `general` INVENTORY (D4) ==")
    print("  uncitable total:        %d of %d (%.2f%%)"
          % (cs["general"], cs["n"], cs["general_pct"]))
    print("    structurally unnumbered (no section marker at all): %d"
          % cs["general_unnumbered"])
    print("      ^ no section number reached const_ref() at all, so there is")
    print("        nothing to cite by number and any `s. N` would be invented.")
    print("        On v2 this class is exactly the Preamble (2) and the six")
    print("        chapter-divider headings; on v1 it also holds unprefixed")
    print("        Arrangement-listing chunks, which is why it drops 66 -> 8.")
    print("    section marker present, _is_toc_fragment DEMOTED it: %d"
          % cs["general_toc"])
    print("      in Chapter VIII (Schedules + Enforcement Procedure Rules): %d"
          % cs["toc_general_in_ch8"])
    print("      OUTSIDE Chapter VIII (Arrangement listing text):           %d"
          % cs["toc_general_out_ch8"])
    print("  The OUTSIDE count is the defect one and it is D4's gate: v1 scores")
    print("  7, v2 scores 0. The 7th v1 chunk is the Q10 trap itself -- Chapter")
    print("  IV s.39 carrying \"46 Special jurisdiction of High Court and")
    print("  Legal aid.\" -- which v2 deletes at source, not by relabelling.")
    print("  The two integers above are PINNED (8 + 26 on v2), because the")
    print("  Chapter VIII split is only a PROXY for \"in the Schedules\": that")
    print("  chapter also holds operative sections 297-320, so a genuine body")
    print("  chunk demoted there would hide inside the in-Ch-VIII bucket. A new")
    print("  demotion anywhere moves one of these numbers.")

    rowfl = fact_row_flags() if version != "v1" else None
    if rowfl is not None:
        print("\n== FACTSHEET S/N TABLE (v2 row parse) ==")
        print("  rows parsed:            %d (S/N %s-%s, contiguous: %s)"
              % (rowfl["n"], rowfl["sn_first"], rowfl["sn_last"],
                 "yes" if rowfl["sn_contiguous"] else "NO"))
        print("  rows carrying a DEGRADATION flag: %s"
              % (", ".join("%d %s" % (n, f) for n, f in rowfl["flagged"])
                 or "none"))
        print("    ^ _fact_chunks_v2() does not inspect flags, so a row whose")
        print("      title failed to parse would still become a citable chunk.")
        print("      Same discipline as the Act manifest's flags above.")
        print("  rows with a MULTI-NUMBER ref: %d of %d"
              % (rowfl["multi_number_refs"], rowfl["n"]))
        print("    ^ NOT a defect, and `packed` is the wrong gate for it. Eight")
        print("      sections (11,13,15,23,34,35,46,53) are never row anchors --")
        print("      they exist only as cross-references inside another row's")
        print("      provisions -- and evalset.verify_expected(), a HARD assert,")
        print("      needs every one. An anchor-only ref would delete them from")
        print("      the corpus and crash eval_heldout/eval_phase06/this script.")
        print("      So the ref carries the anchor PLUS what the row discusses,")
        print("      and `packed` cannot reach 0 on this document. The metric")
        print("      that can is `row-span` above (v1 26/48, v2 %d/%d). D6 gates"
              % (stats["factsheet2020"]["row_spanning"],
                 stats["factsheet2020"]["n"]))
        print("      the factsheet on row-span == 0, NOT on packed == 0.")

    report = {"corpus_version": version, "docs": stats,
              "act_manifest": cov}
    if val is not None:
        report["act_ref_validator"] = val
    if rowfl is not None:
        report["factsheet_rows"] = rowfl
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
            # --- uncitable %. Gated on the Act and the factsheet only.
            gated = d in V2_GENERAL_PCT_GATED
            ok = s["general_pct"] <= V2_MAX_GENERAL_PCT
            print("  %-18s uncitable %.1f%% <= %.1f%%: %s"
                  % (d, s["general_pct"], V2_MAX_GENERAL_PCT,
                     ("PASS" if ok else "FAIL") if gated
                     else "%s (PRINTED, NOT GATED -- see below)"
                          % ("meets" if ok else "exceeds")))
            if gated and not ok:
                fails.append("%s: %.1f%% uncitable exceeds %.1f%%"
                             % (d, s["general_pct"], V2_MAX_GENERAL_PCT))
            if d == "constitution1999":
                # D4's finding, resolved at D6. The threshold is unreachable
                # for this doc and closing the gate by deleting the Schedules
                # is forbidden -- the Second Schedule is operative law and the
                # Enforcement Procedure Rules are how a PWD enforces Ch IV.
                print("      ^ %d of the %d uncitable are structurally"
                      % (s["general_unnumbered"], s["general"]))
                print("        unnumbered and %d are Chapter VIII Schedule/"
                      % s["toc_general_in_ch8"])
                print("        Rules items where `general` is the CORRECT ref")
                print("        -- a Schedule ITEM number is not a SECTION")
                print("        number. Gated on toc-gen outside Ch VIII below.")
                ok = s["toc_general_out_ch8"] <= V2_MAX_TOC_GENERAL_OUT_CH8
                print("  %-18s toc-gen outside Ch VIII %d <= %d: %s"
                      % (d, s["toc_general_out_ch8"],
                         V2_MAX_TOC_GENERAL_OUT_CH8, "PASS" if ok else "FAIL"))
                if not ok:
                    fails.append(
                        "%s: %d TOC-demoted uncitable chunks outside Chapter "
                        "VIII, must be %d -- a §N prefix that const_ref() then "
                        "demoted is an Arrangement fragment that v2 excludes"
                        % (d, s["toc_general_out_ch8"],
                           V2_MAX_TOC_GENERAL_OUT_CH8))
                # The proxy hole above is only covered while this holds.
                for key, want in V2_CONST_GENERAL_INVENTORY.items():
                    ok = s[key] == want
                    print("  %-18s %-22s pinned %-4d measured %-4d %s"
                          % (d, key, want, s[key], "ok" if ok else "DRIFT"))
                    if not ok:
                        fails.append(
                            "%s.%s: pinned %d, measured %d -- the Chapter VIII "
                            "gate above is a PROXY, and this inventory is what "
                            "covers its stated hole. A demotion moving either "
                            "integer can hide inside that proxy."
                            % (d, key, want, s[key]))
            # --- packed refs. Gated on the Act and the Constitution only.
            gated = d in V2_PACKED_GATED
            ok = s["packed"] <= V2_MAX_PACKED
            print("  %-18s packed refs %d <= %d: %s"
                  % (d, s["packed"], V2_MAX_PACKED,
                     ("PASS" if ok else "FAIL") if gated
                     else "%s (PRINTED, NOT GATED -- see below)"
                          % ("meets" if ok else "exceeds")))
            if gated and not ok:
                fails.append("%s: %d packed refs, must be %d"
                             % (d, s["packed"], V2_MAX_PACKED))
            if d == "factsheet2020":
                # D3's finding, resolved at D6. packed==0 and
                # evalset.verify_expected() cannot both hold on this document.
                print("      ^ a multi-number ref is the S/N table's own")
                print("        content here, and 8 of those numbers exist")
                print("        nowhere else -- verify_expected() needs them.")
                print("        Gated on row-span below, the real defect count.")
                ok = s["row_spanning"] <= V2_MAX_ROW_SPANNING
                print("  %-18s row-spanning chunks %d <= %d: %s"
                      % (d, s["row_spanning"], V2_MAX_ROW_SPANNING,
                         "PASS" if ok else "FAIL"))
                if not ok:
                    fails.append(
                        "%s: %d chunks span S/N table rows, must be %d -- a "
                        "chunk cut across rows serves one section's text under "
                        "another's number" % (d, s["row_spanning"],
                                              V2_MAX_ROW_SPANNING))
        got_sha = corpus_sha256(docs)
        ok = got_sha == V2_CORPUS_SHA256
        print("  %-18s %-8s recorded %s" % ("CORPUS", "sha256",
                                            V2_CORPUS_SHA256))
        print("  %-18s %-8s measured %s %s" % ("", "", got_sha,
                                               "ok" if ok else "DRIFT"))
        if not ok:
            fails.append(
                "corpus sha256: recorded %s, measured %s -- chunk CONTENT "
                "moved. The per-doc numbers above are a SHAPE check and cannot "
                "see text moving between chunks at constant count."
                % (V2_CORPUS_SHA256, got_sha))
        # act_ref cross-check, SCOPED to contradictions only. NOT a rate: the
        # two sources share an upstream, so 65/65 is close to a tautology for a
        # single-clause chunk and is reported discounted, never gated.
        # Reuses the `val` computed for the report at :500 -- do NOT call
        # act_ref_validator() again here. It was called twice in the first cut
        # of this gate, and the duplicate silently ate an injection test.
        print("  act_ref contradicts manifest ref: %s"
              % ("PASS (none)" if not val["disagree"] else
                 "FAIL (%s)" % ", ".join(
                     "chunk %d: %s vs %s" % r for r in val["disagree"])))
        if val["disagree"]:
            fails.append(
                "act_ref() and the manifest disagree on %d chunk(s): a stray "
                "line-start 'NN.' in body text, or header/ref drift from a "
                "chunking change. The AGREEMENT RATE is not gated and is not "
                "evidence here -- only the contradictions are."
                % len(val["disagree"]))

        # `missing`, NOT `missing_recoverable`. The v2 gate reads the raw list
        # so that no descriptive v1 split can ever soften what ships: every one
        # of the 58 clauses must be citable, with no exclusion available.
        unreached = cov["missing"]
        print("  act clauses citable (all 58, no exclusion set): %s"
              % ("PASS" if not unreached else
                 "FAIL (%s)" % ", ".join(str(n) for n in unreached)))
        if unreached:
            fails.append("act clauses %s are not citable -- ACT_KNOWN_ABSENT is "
                         "deleted, so there is no manifest to record them in "
                         "and no exclusion to grant them"
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
