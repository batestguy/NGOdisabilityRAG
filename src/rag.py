"""Phase 02 citation-RAG: strict with refusal.

Pipeline: build_corpus() (reuses src/load + src/chunk) -> PerDocRetriever
-> ask(): retrieval gate (MIN_SCORE) -> Gemini generation with a
citation-forcing prompt. Weak/empty retrieval NEVER reaches the LLM:
the caller gets the fixed refusal message (+ DRAC helplines) instead.

Locked decision: answer ONLY from retrieved chunks with section cites;
refuse when retrieval is weak. The LLM must cite chunk text VERBATIM --
even with OCR quirks -- never "clean up" section numbers.
"""
import json
import os
import re
from pathlib import Path

from chunk import (
    CHAPTER_RE,
    constitution_aware_split,
    recursive_split,
    section_aware_split,
)
from load import build_clean_text, clean_text, repair_joins
from retrieve import MIN_SCORE, Chunk, PerDocRetriever, cite_tag, select_top

# Resolved 2026-09-08 via client.models.list(): `models/gemini-2.5-flash`
# exists ("Gemini 2.5 Flash"); `gemini-2.0-flash` is gone (retired).
# Short id "gemini-2.5-flash" is the API-usable form of the same model.
MODEL_NAME = "gemini-2.5-flash"
# Failover target. The 2026-09-11 judge run is the evidence: it spent 30
# attempts on `gemini-2.5-flash-lite` (21 verdicts, 9 lost to a misread 429)
# on a day when `gemini-2.5-flash` was ALSO available -- the generator model
# recorded 0 calls and was never starved. The two models therefore draw from
# SEPARATE free-tier pools, so the real daily budget is 40 calls, not 20.
# Failing over is opt-in (see generate_with_meta) because a flash-lite answer
# is not a flash answer and must never be recorded as one.
FALLBACK_MODEL = "gemini-2.5-flash-lite"
PROMPT_VERSION = "cite-strict-v2"

# Identifies WHICH corpus produced a number, stamped into every artifact
# header from Phase 10 A onward. "v1" is the corpus every published baseline in
# this repo was measured on: OCR'd Act TXT split section-aware at 800 with refs
# INFERRED from heading shape (hence 25/62 Act chunks uncitable), Constitution
# and factsheet re-chunked from their processed TXT. Phase 10 C introduces
# "v2" -- manifest-anchored Act parsing, re-extraction from the PDF text
# layers -- alongside v1, never replacing it, so v1 numbers stay reproducible
# from the same commit. A recall number without this stamp is unattributable.
CORPUS_VERSION = "v1"

# Sizes pinned from Phase 01: Act section-aware 800; Constitution
# chapter-aware RECOMMENDED 400 (Q9 needs <=400 to pass 0.16);
# Factsheet recursive 500/50.
#
# Phase 10 C hazard, recorded here because this is where the numbers live:
# these sizes were measured with TF-IDF only, against the CORRUPTED Act text,
# and short chunks concentrate term mass and inflate cosine. Longer v2 chunks
# lower every cosine and can therefore manufacture false refusals. The
# MIN_SCORE calibration must be RE-DERIVED against v2, not inherited.
ACT_SIZE = 800
CONST_SIZE = 400
FACT_SIZE = 500
FACT_OVERLAP = 50

# v2 Act only. A NEW constant, deliberately NOT a change to ACT_SIZE: the v1
# path must keep its 800 or every published baseline in this repo detaches.
# 1100 is the playbook's number (docs/phases/12_corpus_v2.md, D2) and is NOT
# tuned in D2. Longer chunks lower every cosine, so a size chosen here against
# the refusal floor -- which D5 re-derives -- would leave both fitted to
# nothing. D5 measures; D2 uses the number as given.
ACT_V2_SIZE = 1100

# v2 Factsheet only. Same discipline as ACT_V2_SIZE: FACT_SIZE/FACT_OVERLAP are
# the byte-identical v1 path and must not move. 900 is a CAP, not a target --
# v2 cuts on the S/N table's rows, so 22 of 27 rows emit one chunk each and the
# number only decides how the five long rows sub-split. Chosen from the measured
# sweep (700 -> 39 chunks, 900 -> 32, 1200 -> 28, 1800 -> 27, all with 0 over
# cap): 900 keeps the longest rows (row 20 / Section 32 is 1,491 chars) from
# dominating an index of 27 mostly-short ones without cutting the median row at
# all. Like ACT_V2_SIZE it is NOT tuned against the refusal floor -- D5
# re-derives MIN_SCORE and owns that trade.
FACT_V2_SIZE = 900

# National helplines -- ALWAYS shown on refusal (spec requirement).
HELPLINE_TOLLFREE = "08000-3000-100"
HELPLINE_WHATSAPP = "08000-3000-10"

REFUSAL_MESSAGE = (
    "I can't answer this from the Disability Act 2018, the 1999 Constitution, "
    "or the factsheet I have. For help with your question, please contact the "
    "DRAC Toll-Free helpline " + HELPLINE_TOLLFREE + " or DRAC WhatsApp "
    + HELPLINE_WHATSAPP + "."
)

# Exact no-answer sentence the prompt orders when excerpts lack the answer.
# Detected as a substring (LLM may append whitespace) and mapped to a
# gate-style refusal: junk that clears the TF-IDF floor on shared words
# ("law", "Act") is still refused here instead of answered.
NO_ANSWER_SENTENCE = "I can't answer this from the available excerpts."

ROOT = Path(__file__).resolve().parent.parent
ACT_PATH = ROOT / "data" / "processed" / "disability_act_2018_full.txt"
CONST_PATH = ROOT / "data" / "processed" / "constitution_1999_NHRC.txt"
FACT_PATH = ROOT / "data" / "processed" / "disability_act_factsheet_PLAC.txt"
# The OCR/parse -> runtime seam. See _act_chunks_v2().
ACT_V2_PATH = ROOT / "data" / "processed" / "act2018_v2_clauses.json"

SECTION_RE = re.compile(r"(Section \d+)", re.IGNORECASE)
CONST_REF_RE = re.compile(r"\u00a7\u00a7?(\d+)")
# v2 Constitution only: the enacting words that open the Preamble, and the cut
# point for the Arrangement-of-Sections exclusion. The marker is the PREAMBLE,
# not the operative body's first chapter heading -- see _const_chunks_v2() for
# why that distinction is the whole of D4's correctness argument. Matched as a
# regex and asserted to occur exactly once; the character offset is never
# written down, because an offset silently rots the moment the TXT is re-cleaned.
CONST_PREAMBLE_RE = re.compile(
    r"We the people of the Federal Republic of Nigeria")
# Clause headings sit at line starts ("16.\n(1)A person shall not-") or
# mid-line glued by two-column OCR ("40.Appointment and duties...").
# Parenthesized subsection markers ("(2)Every public vehicle...") are NOT
# clauses -- the old first_number_anywhere regex mislabeled the cl.10+11
# vehicle chunk as "cl. 2" (Q6 evidence 2026-09-08). Both heading shapes
# require a capital letter after the dot ("40.A", "16. (1)A"); "(2)E" is
# excluded by the "(" guard, "section 1(2)"/"N1,00o,000" lack the dot.
CLAUSE_LINE_RE = re.compile(r"(?m)^\s*(\d{1,2})\.\s")
CLAUSE_GLUED_RE = re.compile(r"(?<!\()(?<!\d)(\d{1,2})\.(?=[A-Z])")
# Fallback only (arrangement-line chunks with no line-start heading):
# first inline "N." / "N)" marker -- with the "(" guard, so subsection
# "(2)" can never leak back in (review 2026-09-08).
CLAUSE_INLINE_RE = re.compile(r"(?<!\()(?<!\d)(\d{1,2})(?!\d)\s*[\.\)]")
SECTION_RANGE_RE = re.compile(
    r"[Ss]ections?\s+(\d{1,2})\s*[-–]\s*(\d{1,2})"
)
SECTION_ANY_RE = re.compile(r"[Ss]ection\s+(\d{1,2})")

# ---- Factsheet S/N table (v2 only; see fact_v2_rows). --------------------
# The PLAC factsheet is one three-column table -- S/N | Highlighted Sections |
# Provisions -- and these three regexes are the only structure it has.
#
# FACT_ROW_RE is the S/N anchor line, on its own line by itself. BOTH the
# dotted and undotted forms occur in the source ("1. Section 1" at L34, "2
# Section 2" at L52), which is why the dot is optional. It doubles as the
# row_spanning defect metric in scripts/audit_corpus.py: a chunk whose BODY
# still contains one of these lines was cut across a row boundary.
FACT_ROW_RE = re.compile(r"(?m)^\s*(\d{1,2})\.?\s+Section\s+(\d{1,2})\s*$")
# Page furniture: the "| 4 |" page number, the repeated column header, and the
# PLAC running footer. Dropped INSIDE rows as well as between them -- rows 5,
# 15, 22 and 25 each span a page break, so their provisions column is
# interrupted mid-sentence by all three.
FACT_FURN_RE = re.compile(
    r"^\s*(\|\s*\d+\s*\||S/N\s+Highlighted|Policy and Legal Advocacy Centre)")
# End of the table: the PLAC address block and the About/Supported-by matter.
FACT_TAIL_RE = re.compile(
    r"(?m)^\s*(Plot\s+\d|Website:|About PLAC|Supported by:)")
# The title column is physically narrower than the provisions column, so a
# title line is short and is not a sentence. Verified correct on all 27 rows.
FACT_TITLE_MAX = 40


def _dedup(nums: list[int]) -> list[int]:
    return list(dict.fromkeys(nums))


def act_ref(chunk: str) -> str:
    """Clause ref for an Act chunk. Line-start + glued mid-line headings
    (never a Constitution §N, never a parenthesized subsection).
    Multi-clause chunks get member-list labels ('cl. 16,17'); arrangement
    chunks spanning >4 clauses are 'general' (overview, not a cite)."""
    hits: list[tuple[int, int]] = []  # (position, number)
    for m in CLAUSE_LINE_RE.finditer(chunk):
        hits.append((m.start(), int(m.group(1))))
    for m in CLAUSE_GLUED_RE.finditer(chunk):
        hits.append((m.start(), int(m.group(1))))
    hits.sort()
    nums = _dedup([n for _, n in hits if 1 <= n <= 58])
    if not nums:  # no heading shape at all: first inline marker fallback
        m = CLAUSE_INLINE_RE.search(chunk)
        return "cl. %s" % m.group(1) if m else "general"
    if len(nums) > 4:
        return "general"
    return "cl. %s" % ",".join(str(n) for n in nums)


def const_ref(chunk: str) -> str:
    """Section ref from the chunk's §N/§§a,b prefix ('s. 17').

    TOC-only fragments (section-title listings with no body text) are
    'general': citable for topic, never for a section number. Added
    2026-09-09 (Phase 06 fix A): the '33. Right to life. 34 Right to
    dignity...' TOC line was labeled 's. 33', letting the LLM cite
    dignity content to s.33 (correct: s.34) -- Q9 evidence. Ranking is
    untouched (text identical); only the cite tag changes, so answer-level
    confirmation awaits the next LLM run."""
    m = CONST_REF_RE.search(chunk[:160])
    if not m:
        return "general"
    body = chunk[m.end():]
    first = int(m.group(1).split(",")[0])
    # The section number is passed down so the TOC test can ask the question
    # that actually separates a listing from body text: does this chunk's
    # visible heading belong to some OTHER section? See _is_toc_fragment.
    if _is_toc_fragment(body, first):
        return "general"
    return "s. %s" % first


# A section headline: number + Title-case words ("34 Right to dignity...").
# Parenthesized subsection markers ("(2) In furtherance") also match, so the
# word-count guard below does the real work: genuine chunks carry body text,
# TOC fragments are bare title listings (<40 words in the 2026-09-09 corpus
# scan: 17 fragments, all title listings, max 39 words).
TOC_HEAD_RE = re.compile(r"(?<!\d)(\d{1,3})(?!\d)\s*\.?\s*[A-Z]")


def _is_toc_fragment(body: str, sec: int | None = None) -> bool:
    """True for section-title listings with no body text.

    Two rules, because the arrangement-of-sections listing gets cut by the
    splitter and the tail end of it does not look like the head end.

    1. >=2 headings in under 40 words -- the original fix A rule, which
       catches a listing caught mid-stride ("33. Right to life. 34 Right to
       dignity...").

    2. ORPHAN LIST ENTRY (Phase 08 fix B, 2026-09-11). When the split leaves
       only ONE heading, rule 1 misses it. This is what produced the Q10
       misattribution: the chunk

           §39: "ion from fundamental human rights. 46 Special jurisdiction
                 of High Court and Legal aid."

       is the tail of the Chapter IV arrangement listing, but it carried only
       the single head "46", so it kept ref "s. 39" -- and the LLM, reading
       "Special jurisdiction of High Court and Legal aid" under a header that
       said [Constitution s. 39], duly wrote "The High Court has special
       jurisdiction and provides legal aid [Constitution s. 39]". Both
       mechanical checks passed: the digits "39" were in the pooled text and
       the phrase "high court" was in the cited chunk. Only a human caught it,
       which is why it needed a hand-written MANUAL_FLAGS entry.

       The giveaway is that the heading belongs to a DIFFERENT section: a
       genuine body chunk of section N does not consist of a title listing for
       section M. So a short body whose every visible heading is foreign to
       its own section number is a listing, not text worth citing by number.

    Measured blast radius before adoption (hazard check, because
    eval_phase06.verify_ground_truth asserts every EXPECTED number still
    occurs in some ref, and demoting refs to "general" REMOVES numbers):
    12 of 2,104 Constitution chunks change, no section number disappears from
    the corpus, and s.17/s.34/s.46 keep 17/6/6 chunks respectively. Eleven of
    the twelve are Chapter VIII schedule/form boilerplate ("......." dotted
    rules); the twelfth is the Q10 trap chunk.

    D4 DEMOTES THIS TO A LINT -- it is kept, not weakened. _const_chunks_v2()
    deletes the Arrangement of Sections outright, so the listing fragments this
    heuristic was written to catch CEASE TO EXIST: on v2 it fires 26 times and
    all 26 are Chapter VIII Schedule/Rules items, a different and legitimate
    class where `general` is the correct ref because a Schedule item number is
    not a section number. The arrangement-tail firings drop from 7 (v1, the
    seventh being the Q10 trap chunk itself) to 0, which is exactly the
    measurement audit_corpus.py's `toc-gen` column publishes: the heuristic is
    now the INSTRUMENT that proves D4's cure held, rather than the mitigation
    that stood in for it. Deleting it would remove that instrument AND restore
    the misattribution class for any listing text D4 does not reach.
    """
    heads = {int(n) for n in TOC_HEAD_RE.findall(body) if 1 <= int(n) <= 320}
    words = re.findall(r"[A-Za-z]+", body)
    if len(heads) >= 2 and len(words) < 40:
        return True
    if heads and len(words) < 40 and sec is not None and sec not in heads:
        return True
    return False


def fact_ref(chunk: str) -> str:
    """Section ref(s) for a factsheet chunk. Arrangement chunks span
    sections ('Sections 28-30', S/N rows) -> member-list label.

    v1 ONLY, and it stays that way. Do NOT promote this to a v2 validator the
    way act_ref() was promoted (scripts/audit_corpus.py::act_ref_validator).
    Under v2's full-row-ref rule every sub-chunk of a row carries the WHOLE
    row's ref, so a sub-chunk legitimately names sections its own 900 chars do
    not mention -- disagreement is the designed behaviour, not a defect, and a
    "validator" built on it would measure the split point and nothing else.
    That is D2's lesson about act_ref_validator applied before the fact instead
    of after. The real v2 defect metric is `row_spanning`, which is measured
    from the chunk TEXT against FACT_ROW_RE and can genuinely fail.
    """
    nums: list[int] = []
    for m in SECTION_RANGE_RE.finditer(chunk):
        a, b = int(m.group(1)), int(m.group(2))
        nums.extend(range(a, b + 1) if 0 < b - a <= 5 else (a, b))
    nums.extend(int(n) for n in SECTION_ANY_RE.findall(chunk))
    nums = _dedup(nums)
    if not nums:
        return "general"
    if len(nums) > 4:  # arrangement/overview chunk, not a citable section
        return "general"
    return "Section %s" % ",".join(str(n) for n in nums)


def _act_chunks_v1() -> list[Chunk]:
    """v1 Act chunks. Relocated verbatim from build_corpus() at D1.

    NB "section-aware 800" is misleading: chunk.SECTION_RE matches only 4 times
    in the cleaned Act text and all four sit past 89.8% of the document, so for
    clauses 1-58 this is effectively recursive_split(text, 800). That is part of
    the byte-identical v1 path, not a bug to fix -- D's clause-aligned chunking
    is a total replacement of this splitter, not a refinement.
    """
    raw_act = ACT_PATH.read_text(encoding="utf-8", errors="replace")
    act_text, _, _ = build_clean_text(raw_act, repair=True, dedupe=True)
    act_text = clean_text(act_text)
    return [
        Chunk("act2018", act_ref(c), c)
        for c in section_aware_split(act_text, size=ACT_SIZE)
    ]


def _const_chunks_v1() -> list[Chunk]:
    """v1 Constitution chunks. Relocated verbatim from build_corpus() at D1."""
    raw_const = CONST_PATH.read_text(encoding="utf-8", errors="replace")
    const_text = clean_text(repair_joins(raw_const))
    return [
        Chunk("constitution1999", const_ref(c), c)
        for c in constitution_aware_split(const_text, size=CONST_SIZE)
    ]


def _fact_chunks_v1() -> list[Chunk]:
    """v1 Factsheet chunks. Relocated verbatim from build_corpus() at D1."""
    raw_fact = FACT_PATH.read_text(encoding="utf-8", errors="replace")
    fact_text = clean_text(repair_joins(raw_fact))
    return [
        Chunk("factsheet2020", fact_ref(c), c)
        for c in recursive_split(fact_text, size=FACT_SIZE, overlap=FACT_OVERLAP)
    ]


def _act_chunks_v2() -> list[Chunk]:
    """v2 Act chunks: one clause per chunk, refs taken from the parser.

    THE SEAM. This function reads ONE artifact -- the clause manifest JSON at
    ACT_V2_PATH -- with stdlib json and nothing else. That is deliberate and
    architectural, not convenience: requirements.txt is the slim Render runtime
    and forbids pymupdf / rapidocr_onnxruntime / onnxruntime / FAISS, while the
    corpus ships prebuilt and is never re-OCRed at boot. OCR lives in
    scripts/ocr_gazette.py, the parse in scripts/parse_act_v2.py, and the JSON
    is the wire format between them and here. If src/ ever needs an OCR import
    to build a chunk, the slim runtime is gone. Keep it that way.

    `ref` is "cl. %d" % n straight from the manifest -- NEVER inferred from the
    chunk text. That is what makes packed refs (`cl. 3,4,5`) structurally
    impossible rather than merely unlikely: a chunk belongs to exactly one
    clause by construction, so there is no path that can produce one. act_ref()
    is demoted to a validator against this (scripts/audit_corpus.py).

    EVERY sub-chunk carries the clause header, not just the first. A long clause
    (cl.57 Interpretation., 5,311 chars; cl.38, 2,290) splits into several
    pieces, and a headerless piece would resolve under act_ref() to "general" or
    to a stray number from the body -- which would both break the general<=1%
    gate and make the validator disagree with the parser for a reason that has
    nothing to do with the parse. Repeating the header costs a few duplicated
    characters and makes every chunk self-identifying, which is exactly the
    property the citation invariant needs.

    The header is the statutory heading ("38. Functions of the Commission."):
    the gazette's marginal note restored to the position the printer moved it
    out of, not deleted. `path` records HOW the ref was obtained -- "manifest",
    against v1's "" (inferred from heading shape).
    """
    manifest = json.loads(ACT_V2_PATH.read_text(encoding="utf-8"))
    chunks: list[Chunk] = []
    for clause in manifest["clauses"]:
        ref = "cl. %d" % clause["n"]
        header = clause["header"]
        body = clause["text"]
        if len(header) + 1 + len(body) <= ACT_V2_SIZE:
            pieces = [body]
        else:
            # Budget the header out of the size cap so no chunk exceeds it,
            # the same idiom constitution_aware_split._emit() uses for its
            # "Constitution, ... §N: " prefix.
            budget = max(ACT_V2_SIZE - len(header) - 1, 100)
            pieces = recursive_split(body, size=budget)
        chunks.extend(
            Chunk("act2018", ref, "%s\n%s" % (header, p), "manifest")
            for p in pieces
        )
    return chunks


def fact_v2_rows() -> list[dict]:
    """Parse the PLAC factsheet's S/N table into one struct per row.

    NO MANIFEST, AND THAT IS DELIBERATE. The Act needed one because its source
    is a scanned gazette and pymupdf/rapidocr must never reach the slim Render
    runtime, so a JSON file is the wire format across that process boundary.
    The factsheet has no such boundary: its source is already a clean TXT in the
    repo that v1 parses at boot with stdlib, so a manifest here would be a
    second artifact to keep in sync for no benefit. Symmetry is not a reason.
    This function and _fact_chunks_v2() are therefore in-process, stdlib `re`.

    The parse is a REGION plus three line classes. The region is [first
    FACT_ROW_RE match, first FACT_TAIL_RE match after it): everything before is
    the cover page, the intro preamble and the Arrangement of Sections block,
    everything after is the PLAC address and About matter -- all excluded from
    retrieval per the playbook, the factsheet twin of the Constitution TOC trap.
    Inside the region each row is [its anchor line, the next anchor line), minus
    FACT_FURN_RE page furniture, split into a short TITLE prefix and a BODY.

    The audit reads the same rows this chunker does (scripts/audit_corpus.py),
    so the report and the corpus can never drift into describing different
    parses -- the failure mode act_manifest_flags() exists to prevent on the Act.

    `flags` follows the Act manifest's discipline: TITLE_EMPTY, TITLE_LONG
    (>4 title lines -- the widest genuine title is 4) and SN_OUT_OF_SEQUENCE are
    recorded per row and printed by the audit. All 27 are clean today. The point
    is that a future degraded parse cannot be promoted to fully-citable chunks
    with no signal anywhere.

    Text handling is v1's exactly -- clean_text(repair_joins(raw)) -- because
    D3 replaces the SPLITTER, not the text. Measured: that pipeline changes one
    token in the whole document ("Free Healthcare" -> "Free Health care") and
    leaves all 430 lines and all 27 anchors intact.
    """
    raw = FACT_PATH.read_text(encoding="utf-8", errors="replace")
    text = clean_text(repair_joins(raw))
    anchors = list(FACT_ROW_RE.finditer(text))
    if not anchors:
        raise ValueError(
            "factsheet S/N table not found in %s -- FACT_ROW_RE matched "
            "nothing, so the source shape has changed" % FACT_PATH)
    tail = FACT_TAIL_RE.search(text, anchors[-1].end())
    region_end = tail.start() if tail else len(text)

    rows: list[dict] = []
    for i, m in enumerate(anchors):
        stop = anchors[i + 1].start() if i + 1 < len(anchors) else region_end
        lines = [ln for ln in text[m.end():stop].splitlines()
                 if not FACT_FURN_RE.match(ln)]
        title_parts: list[str] = []
        k = 0
        while k < len(lines):
            s = lines[k].strip()
            if len(s) > FACT_TITLE_MAX or s.endswith("."):
                break
            if s:
                title_parts.append(s)
            k += 1
        title = " ".join(title_parts)
        body = "\n".join(lines[k:]).strip()
        sn, sec = int(m.group(1)), int(m.group(2))

        # Sections this row DISCUSSES but is not anchored on. Same two regexes
        # v1's fact_ref() uses, so v2 changes which TEXT a number is attached
        # to, never the vocabulary for spotting one. Confining the scan to the
        # row body is what makes it safe: row 17's provisions end on a truncated
        # "- section" with its number lost to the page cut, and only the row
        # boundary stops that from swallowing the next row's "18".
        nums: list[int] = []
        for mm in SECTION_RANGE_RE.finditer(body):
            a, b = int(mm.group(1)), int(mm.group(2))
            nums.extend(range(a, b + 1) if 0 < b - a <= 5 else (a, b))
        nums.extend(int(n) for n in SECTION_ANY_RE.findall(body))

        flags: list[str] = []
        if not title:
            flags.append("TITLE_EMPTY")
        if len(title_parts) > 4:
            flags.append("TITLE_LONG")
        if sn != i + 1:
            flags.append("SN_OUT_OF_SEQUENCE")

        rows.append({
            "sn": sn,
            "sec": sec,
            "title": title,
            "text": body,
            "xrefs": sorted(set(nums) - {sec}),
            "flags": flags,
        })
    return rows


def _fact_chunks_v2() -> list[Chunk]:
    """v2 Factsheet chunks: one table row per chunk, ref from the table itself.

    v1 ran recursive_split(fact_text, 500, 50) over the whole document, which
    cuts a three-column table on a character budget that knows nothing about
    rows -- hence 9 uncitable chunks and 19 packed refs, and hence those packed
    refs being DISORDERED (`Section 51,40`, `Section 50,45,54`) rather than
    consecutive runs like the Act's. That disorder is the tell: this was table
    damage, not over-run, so D2's Act fix does not transfer even though its
    idiom does.

    THE REF CARRIES THE ROW'S ANCHOR PLUS THE SECTIONS THAT ROW DISCUSSES, and
    that was forced by measurement rather than chosen. Eight sections -- 11, 13,
    15, 23, 34, 35, 46, 53 -- are never row anchors; they exist only as
    cross-references inside another row's provisions ("...may also accept a gift
    of land, money or property... - section 46"). frozen10/Q6 expects 11, and
    frozen10 may not be edited under any circumstances; heldout and test expect
    the other seven. evalset.verify_expected() is a HARD assert, not a metric,
    so an anchor-only ref would drop those eight numbers out of the corpus and
    crash eval_heldout.py, eval_phase06.py and audit_corpus.py outright.
    Measured both ways: anchor-only leaves a coverage gap of exactly those
    eight; anchor + cross-references leaves none.

    The consequence is that `packed` cannot reach 0 on this document, and D3
    RE-SCOPES that metric rather than tuning it away. A multi-number factsheet
    ref is a declared non-defect: it is the table's own content. The real defect
    is a chunk cut ACROSS rows, which is measured from the chunk text as
    `row_spanning` in scripts/audit_corpus.py -- v1 scores 26 of 48 on it, v2
    scores 0. See the D6 warning in docs/phases/12_corpus_v2.md.

    ANCHOR FIRST, cross-references ascending. v1's refs came out in whatever
    order recursive_split's cut happened to expose the numbers, which is what
    made `Section 51,40` possible; a v2 ref always leads with the section the
    row is actually about.

    EVERY sub-chunk carries the FULL row ref and the row header, exactly as
    every Act v2 sub-chunk carries its clause number. The alternative --
    per-piece cross-references -- was considered and rejected: it makes
    coverage depend on where recursive_split happens to cut, so a cut through
    the literal string "section 46" would silently drop a frozen expectation.
    The header is budgeted out of the cap (FACT_V2_SIZE - len(header) - 1, floor
    100), the same idiom as _act_chunks_v2() and constitution_aware_split._emit,
    so no chunk exceeds FACT_V2_SIZE.

    `path` records HOW the ref was obtained: "table", against v1's "" (inferred
    from prose) and the Act's "manifest".
    """
    chunks: list[Chunk] = []
    for row in fact_v2_rows():
        ref = "Section %s" % ",".join(
            str(n) for n in [row["sec"]] + row["xrefs"])
        header = "Section %d %s" % (row["sec"], row["title"])
        body = row["text"]
        if len(header) + 1 + len(body) <= FACT_V2_SIZE:
            pieces = [body]
        else:
            budget = max(FACT_V2_SIZE - len(header) - 1, 100)
            pieces = recursive_split(body, size=budget)
        chunks.extend(
            Chunk("factsheet2020", ref, "%s\n%s" % (header, p), "table")
            for p in pieces
        )
    return chunks


def _const_chunks_v2() -> list[Chunk]:
    """v2 Constitution chunks: the same splitter, minus the Arrangement pages.

    THE SPLITTER DOES NOT MOVE. constitution_aware_split at CONST_SIZE stays
    exactly as v1 calls it, and so does const_ref(). D4 removes TEXT that was
    never citable in the first place -- the Arrangement of Sections, i.e. the
    printed table of contents -- and changes nothing about how the remainder is
    cut. That is the narrowest change that can fix the defect, which matters
    because the Constitution is ~95% of the joint index and every cosine in the
    project moves when it is re-chunked.

    WHY THE PREAMBLE AND NOT THE FIRST CHAPTER HEADING. Chapters I-VIII occur
    TWICE in the source: once as the Arrangement listing, then again as the
    operative body. The obvious cut is the body's second `Chapter I` heading --
    and it is wrong. The real Preamble ("We the people of the Federal Republic
    of Nigeria ... Do hereby make, enact and give to ourselves the following
    Constitution:-") sits BETWEEN the two, so cutting at the heading silently
    deletes the enacting words of the instrument. Measured at D4: cut@Preamble
    keeps it (2037 chunks, 34 general); cut@2nd-Chapter-I loses it (2035, 32).
    Losing text and calling it a smaller `general` count is the failure mode this
    whole phase exists to avoid.

    THE MARKER IS ASSERTED, NEVER ASSUMED -- the same discipline as the Act
    manifest's flags and fact_v2_rows()'s FACT_ROW_RE guard. A missing or
    duplicated Preamble means the source TXT changed shape, and the one thing
    this function must never do in that case is fall back to chunking the whole
    document: that would quietly restore the 99-general corpus under a v2 label.
    The two structural asserts -- exactly one Preamble, and a cut that lands
    after the Arrangement's last chapter heading and before the body's first --
    are what make a degraded parse fail loudly instead of being consumed.

    WHY THE SCHEDULES STAY, AND WHY `general` IS CORRECT FOR THEM. "Exclude the
    Arrangement pages, and nothing else" is the instruction, so the Second and
    Third Schedules and the Fundamental Rights (Enforcement Procedure) Rules are
    kept: the legislative lists are operative law and the Rules are the mechanism
    a PWD actually uses to enforce Chapter IV. Their items are numbered -- "8.
    Census", "63. Traffic", "ORDER 6" -- but a Schedule ITEM number is not a
    SECTION number. Item 8 is not s.8. Labelling those `s. N` would deliberately
    re-create the Q10 misattribution class, so const_ref()/_is_toc_fragment
    demote them to `general` and that is the right answer, not a defect. It does
    mean `general` bottoms out at 34 (1.67%) here and the <=1% gate is
    unreachable by exclusion alone; D4 reports that and does NOT tune it. A
    citable `Sch. N item M` ref means a FOURTH numbering scheme through
    cite_tag(), the citation invariant and the prompt -- Phase E work, named as
    such in docs/phases/12_corpus_v2.md D4.
    """
    raw_const = CONST_PATH.read_text(encoding="utf-8", errors="replace")
    const_text = clean_text(repair_joins(raw_const))

    marks = list(CONST_PREAMBLE_RE.finditer(const_text))
    if len(marks) != 1:
        raise ValueError(
            "Constitution Preamble marker matched %d times in %s (expected "
            "exactly 1) -- the source shape has changed and the Arrangement "
            "cut point can no longer be located" % (len(marks), CONST_PATH))
    cut = marks[0].start()

    # The listing and the body both open on chapter headings, so the cut is
    # valid iff it separates the two runs: every Arrangement heading before it,
    # every body heading after it. Chapter VIII is the listing's last and
    # Chapter I is the body's first -- if either side reads otherwise, the cut
    # has landed inside the listing or past the start of the operative text.
    heads = list(CHAPTER_RE.finditer(const_text))
    before = [m.group(1) for m in heads if m.start() < cut]
    after = [m.group(1) for m in heads if m.start() >= cut]
    if not before or not after or before[-1] != "VIII" or after[0] != "I":
        raise ValueError(
            "Constitution Arrangement cut at char %d is not between the two "
            "chapter runs (last before: %s, first after: %s) -- refusing to "
            "chunk a document whose structure is not the one D4 measured"
            % (cut, before[-1] if before else None,
               after[0] if after else None))

    return [
        Chunk("constitution1999", const_ref(c), c)
        for c in constitution_aware_split(const_text[cut:], size=CONST_SIZE)
    ]


def build_corpus(version: str | None = None) -> dict[str, list[Chunk]]:
    """Load + chunk all three docs. Raw files are never modified.

    version defaults to CORPUS_VERSION ("v1" until D6), so every existing
    no-arg caller is unchanged. The default no-arg path is v1 and is
    byte-identical to every published baseline.

    All three docs are v2 as of D4: the Act (D2, manifest-anchored), the
    Factsheet (D3, row-aligned) and the Constitution (D4, Arrangement excluded).
    CORPUS_VERSION is still "v1" -- D6 flips it, after D5 re-derives MIN_SCORE
    against the shorter, differently-weighted v2 index.

    audit_corpus.py --corpus=v2 still exits 1, and both remaining FAILs are
    RECORDED, not outstanding work: the factsheet's `packed 16` (a multi-number
    ref is the S/N table's own content -- D3) and the Constitution's `uncitable
    1.7%` (8 structurally unnumbered chunks plus 26 Chapter VIII Schedule/Rules
    chunks where `general` is the correct answer -- D4). D6 re-scopes both gates;
    neither may be closed by deleting text. See docs/phases/12_corpus_v2.md.

    Deliberately NOT memoized. Insertion order of the returned dict is load-
    bearing -- PerDocRetriever iterates it in order and sorts hits by score
    alone (src/retrieve.py:331-338), so insertion order breaks ties and
    reordering these three blocks silently moves published numbers. It is the
    same order in both versions for that reason.
    """
    version = version or CORPUS_VERSION
    if version not in ("v1", "v2"):
        raise ValueError(
            "unknown corpus version %r (only 'v1' and 'v2' exist)" % version
        )

    docs: dict[str, list[Chunk]] = {}
    docs["act2018"] = _act_chunks_v1() if version == "v1" else _act_chunks_v2()
    docs["constitution1999"] = (
        _const_chunks_v1() if version == "v1" else _const_chunks_v2())
    docs["factsheet2020"] = (
        _fact_chunks_v1() if version == "v1" else _fact_chunks_v2())
    return docs


SYSTEM_PROMPT = """You are DRLCA, a Nigerian disability-rights legal assistant. \
Answer the user's question STRICTLY from the retrieved excerpts below.

Rules (no exceptions):
1. Every factual claim MUST end with its citation tag, copied EXACTLY as given \
in the excerpt header: [Act cl. N], [Constitution s. N], or [Factsheet Section N].
2. Copy section/clause numbers VERBATIM from the excerpt text. Never renumber, \
"clean up", or invent a section number -- even if the text has OCR quirks.
3. Factsheet §N, Act clause N, and Constitution section N are DIFFERENT numbering \
schemes. Never relabel one as another.
4. If the excerpts do not contain the answer, reply with EXACTLY this sentence \
and nothing else: "I can't answer this from the available excerpts."
5. Do not use any outside knowledge. No citation -> no claim.
6. The number in your sentence MUST equal the tag number. Never merge two \
tags into one -- "[Act cl. 16 cl. 17 (1)]" and "[Factsheet Section 19 \
Section 20]" are FORBIDDEN; write one tag per claim instead.
7. Parenthesized subsection numbers like (1) or (2) are NOT clause numbers. \
Cite the chunk's header tag (e.g. a chunk headed [Act cl. 10,11] is cited \
exactly as [Act cl. 10,11]). Multi-number tags are cited whole, verbatim."""

PLAIN_SUFFIX = """\nWrite in plain, simple language for low-literacy readers: short \
sentences, common words, one idea per sentence. Same facts, same citations."""

# ---------------------------------------------------------------------------
# Chat mode (Phase 10 B). Appended ONLY when build_prompt() is given history,
# so a single-turn prompt is byte-identical to every one this project has ever
# sent and every transcript and cache entry keeps its meaning.
#
# Rule 8 is the whole citation-safety story for multi-turn. Prior turns enter
# the prompt so the model can UNDERSTAND an elliptical question ("so can they
# fire me?"); they are not evidence. The citable set stays exactly this turn's
# retrieved excerpts. verify_citations() is unchanged and therefore already
# fails a tag re-cited from an earlier turn -- chat.cross_turn_drift() names
# that specific case so it can be counted instead of merely failing.
# ---------------------------------------------------------------------------
CHAT_PROMPT_VERSION = "chat-cite-strict-v1"

CHAT_SUFFIX = """
8. This is an ongoing conversation. Earlier turns are shown below for CONTEXT \
ONLY -- to resolve what the user means by "it", "they" or "that". They are NOT \
evidence. You may cite ONLY the retrieved excerpts in THIS turn. Never re-cite \
a tag from an earlier turn that does not appear in this turn's excerpts, and \
never restate an earlier claim as though it were retrieved now."""


def _render_history(history) -> list:
    """Prior turns as prompt lines. Empty list when there is no history."""
    lines = []
    for turn in history or []:
        q = (turn.get("question") or "").strip() if isinstance(turn, dict) else ""
        if not q:
            continue
        lines.append("User: %s" % q)
        a = turn.get("answer") if isinstance(turn, dict) else None
        # answer=None means PENDING (offline path, quota exhausted, or an
        # error), never "the assistant said nothing". Saying so is more honest
        # than rendering an empty assistant turn the model would try to explain.
        lines.append("Assistant: %s" % (
            a.strip() if a and a.strip() else "(no AI answer was generated for that turn)"))
    return lines


def build_prompt(question: str, hits, plain: bool = False, history=None) -> str:
    """Assemble system instruction + cited excerpts + question.

    `history` is an optional list of {question, answer} dicts (see
    chat.history_for_prompt). Two hard requirements, both asserted in
    scripts/test_phase09_ops.py:

    1. history=None (or empty) renders a BYTE-IDENTICAL prompt to the one this
       function produced before chat existed. The answer cache is keyed on
       sha256(model + NUL + whole rendered prompt), so a single stray newline
       would silently invalidate every cached answer and every published
       transcript would stop describing a prompt the code can still produce.

    2. History renders BEFORE the final "\\nQuestion: %s" line. This is a
       PRIVACY requirement, not a formatting preference. _cache_write() stores
       prompt.rsplit("Question: ", 1)[-1] -- the current question line only. Put
       history after that split point and the on-disk cache starts recording
       whole conversations, including disclosures of abuse and coercion, from a
       population that makes them.
    """
    lines = [SYSTEM_PROMPT]
    if plain:
        lines.append(PLAIN_SUFFIX)
    hist = _render_history(history)
    if hist:
        lines.append(CHAT_SUFFIX)
    lines.append("\nRetrieved excerpts (cite VERBATIM, quirks included):")
    for h in hits:
        lines.append(
            "\n%s (relevance %.3f):\n%s" % (cite_tag(h.doc_id, h.ref), h.score, h.text)
        )
    if hist:
        lines.append("\nEarlier in this conversation (context ONLY, NOT citable):")
        lines.extend(hist)
    lines.append("\nQuestion: %s" % question)
    lines.append("Answer (every factual claim cited, or the exact no-answer sentence):")
    return "\n".join(lines)


CITE_TAG_RE = re.compile(
    r"\[(Act cl\. [\d,]+|Act general|Constitution s\. [\d,]+|"
    r"Constitution general|Factsheet [Ss]ection [\d,]+|Factsheet general)\]"
)


def extract_citations(answer: str) -> list[str]:
    """Citation tags present in an answer, in order."""
    return CITE_TAG_RE.findall(answer)


def verify_citations(answer: str, hits) -> list[dict]:
    """Mechanical pre-check per cited tag: was a chunk with that REF actually
    retrieved? Returns [{tag, number_ok}].

    Phase 08 fix B (2026-09-11) changed what "number_ok" means. It used to ask
    whether the cited digits appeared anywhere in the matching doc's POOLED
    TEXT, which is far too weak to be worth much: section numbers are dense in
    legal prose (cross-references, subsection markers, the injected chunk
    headers themselves), so almost any plausible number "occurs in the pool"
    and passes. That is precisely how Q10's "[Constitution s. 39]" survived
    while attributing s.46's High-Court legal-aid provision to s.39 -- the
    digits 39 were in the pool because a chunk header said so.

    It now asks the question a citation actually makes: is there a retrieved
    chunk from that doc whose OWN ref carries the cited number? A tag may only
    name a chunk that was really in front of the model, under the label it was
    really given. Invented numbers and borrowed-from-the-neighbour numbers
    both fail; the check is no longer satisfiable by coincidence.

    'general' tags (no number) still pass mechanically -- there is nothing to
    match -- and still need the human verdict on whether the cited chunk
    supports the claim. Multi-number tags ("cl. 9,10") require EVERY number to
    be present in some retrieved ref, which is the same rule the prompt
    enforces when it tells the model to copy multi-number tags whole.
    """
    doc_of = {"Act": "act2018", "Constitution": "constitution1999",
              "Factsheet": "factsheet2020"}
    out = []
    for tag in extract_citations(answer):
        m = re.match(r"(Act|Constitution|Factsheet) (.+)", tag)
        assert m is not None  # tags come from CITE_TAG_RE, always match
        doc_id, refbit = m.group(1), m.group(2)
        nums = re.findall(r"\d+", refbit)
        if not nums:  # 'general' -- nothing mechanical to check
            out.append({"tag": tag, "number_ok": True})
            continue
        retrieved_refs: set[str] = set()
        for h in hits:
            if h.doc_id == doc_of[doc_id]:
                retrieved_refs |= set(re.findall(r"\d+", h.ref))
        out.append({"tag": tag,
                    "number_ok": all(n in retrieved_refs for n in nums)})
    return out


# ---------------------------------------------------------------------------
# Quota classifiers (moved here from scripts/judge_phase06.py, Phase 09 M1).
#
# They used to live in the judge script, which meant the ONE distinction the
# whole quota discipline rests on -- retryable rate limit vs exhausted daily
# cap -- was defined in a script and unavailable to the library that actually
# makes the calls. ask() could not tell the two apart, so it treated every 429
# identically. They are the single source of truth now; judge_phase06.py
# imports them rather than keeping a second copy that could drift.
# ---------------------------------------------------------------------------


def is_per_minute_429(err: str) -> bool:
    """Distinguish a transient RPM limit from the daily cap.

    This distinction is the whole reason a run can be honest about what it
    did: an RPM 429 deserves a retry, a daily-cap 429 must leave the row
    PENDING rather than pretend the answer was unobtainable for a trivial
    reason. Guessing wrong in the lenient direction would mean hammering a
    exhausted daily quota; guessing wrong in the strict direction would mean
    abandoning work that a 40-second wait would have completed.
    """
    return "PerMinute" in err or "RequestsPerMinute" in err


def retry_delay(err: str, attempt: int) -> float:
    m = re.search(r"retryDelay['\"]?:\s*['\"]?(\d+(?:\.\d+)?)s", err)
    if m:
        return float(m.group(1)) + 3.0        # the server's own hint + slack
    return min(60.0, 8.0 * (2 ** attempt))    # else exponential backoff


# ---------------------------------------------------------------------------
# Answer cache (Phase 08 step 6a, 2026-09-11). A quota saver, NOT evidence.
#
# The free tier is 20 calls/day/model (and 10/MINUTE -- measured 2026-09-11),
# so re-running an eval used to cost a full day's budget to get answers that
# were already known. Cached replies make repeat runs free.
#
# KEYED ON THE WHOLE PROMPT, NOT ON THE QUESTION. This is a deliberate
# departure from the Phase 08 plan, which proposed keying on
# (question, PROMPT_VERSION, model). That key is unsafe, and this project has
# already been bitten by exactly the failure it would cause: the prompt embeds
# the RETRIEVED EXCERPTS, and M1's synonym map changed what Q5 retrieves (from
# no Act clauses at all to cl.1 and cl.2). A question-keyed cache would have
# happily replayed the pre-M1 refusal against post-M1 context -- manufacturing
# the same stale-transcript problem the M1 eval flagged, except silently and
# inside the app. Hashing the prompt covers the question, the excerpts, the
# prompt version (it is literally in SYSTEM_PROMPT) and the plain-language
# suffix, all at once. Context changes -> key changes -> no stale replay.
#
# TRANSPARENCY IS THE POINT. Every hit sets cached=True on the way back out to
# ask(), so no transcript can present replayed text as a fresh call. The
# versioned test_phase02/judge transcripts remain the durable record; this file
# is scratch and is gitignored.
#
# It must never be able to break an answer. Every cache read and write is
# wrapped: a corrupt, unreadable or unwritable cache degrades to "no cache",
# never to an error reaching the user.
# ---------------------------------------------------------------------------
CACHE_PATH = ROOT / "scripts" / ".answer_cache.json"


def _cache_key(prompt: str, model: str) -> str:
    import hashlib
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"\x00")
    h.update(prompt.encode("utf-8"))
    return h.hexdigest()


def _cache_read(key: str):
    try:
        if not CACHE_PATH.exists():
            return None
        import json as _json
        entry = _json.loads(CACHE_PATH.read_text(encoding="utf-8")).get(key)
        return entry["answer"] if entry else None
    except Exception:  # corrupt/unreadable cache is a miss, never an error
        return None


def _cache_write(key: str, prompt: str, model: str, answer: str) -> None:
    try:
        import json as _json
        data = {}
        if CACHE_PATH.exists():
            try:
                data = _json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            except Exception:
                data = {}  # corrupt file: start over rather than fail the call
        # question//prompt_version are stored for human readability when
        # debugging the cache; they are NOT part of the key.
        q = prompt.rsplit("Question: ", 1)[-1].split("\n", 1)[0]
        data[key] = {"answer": answer, "model": model, "question": q,
                     "prompt_version": PROMPT_VERSION,
                     "prompt_sha256": key,
                     "at": __import__("datetime").datetime.now().isoformat(
                         timespec="seconds")}
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_PATH.with_suffix(".tmp")
        tmp.write_text(_json.dumps(data, indent=1), encoding="utf-8")
        tmp.replace(CACHE_PATH)  # atomic-ish: never leaves a half-written file
    except Exception:
        pass  # a cache we cannot write is still a working assistant


def generate_with_meta(
    prompt: str, model: str = MODEL_NAME, use_cache: bool = True,
    failover: bool = False,
) -> tuple[str, bool, str]:
    """Single Gemini generation. Returns (answer, cached, model_used).

    `cached` is what keeps the cache honest: it rides back through ask() into
    the result dict, so a replayed answer can never be written into a
    transcript as though it had been freshly generated. `model_used` does the
    same job for failover -- the caller records which model actually spoke,
    not which one it asked for.

    FAILOVER (Phase 09 M1) is opt-in and fires at most once, only for a
    DAILY-cap 429. Three guards, each load-bearing:

      - `failover` off by default. A flash-lite answer is a different answer,
        and an eval that silently mixed two models would be measuring neither.
        Opting in is the caller saying it will record the difference.
      - a PER-MINUTE 429 re-raises instead. It carries its own retryDelay
        (~37s) and clears on its own; burning the fallback model's daily pool
        to dodge a 37-second wait would trade a scarce resource for a cheap
        one. The caller retries it -- see is_per_minute_429.
      - `model != FALLBACK_MODEL`, so a failover can never itself fail over.
        The recursive call also passes failover=False, belt and braces.

    Cache reads AND writes key on the model actually used (_cache_key hashes
    the model), so a flash-lite answer can never be replayed as a flash one.
    """
    if use_cache:
        hit = _cache_read(_cache_key(prompt, model))
        if hit is not None:
            return hit, True, model
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_API_KEY/GEMINI_API_KEY not set")
    from google import genai
    client = genai.Client(api_key=key)
    try:
        resp = client.models.generate_content(model=model, contents=prompt)
    except Exception as e:
        msg = "%s" % e
        if not (failover and "429" in msg and not is_per_minute_429(msg)
                and model != FALLBACK_MODEL):
            raise
        return generate_with_meta(prompt, model=FALLBACK_MODEL,
                                  use_cache=use_cache, failover=False)
    answer = (resp.text or "").strip()
    if use_cache and answer:  # never cache an empty reply
        _cache_write(_cache_key(prompt, model), prompt, model, answer)
    return answer, False, model


def generate(prompt: str, model: str = MODEL_NAME, use_cache: bool = True,
             failover: bool = False) -> str:
    """Single Gemini generation via the new `google.genai` SDK (not the
    retired `google.generativeai` package, not the retired 2.0-flash).

    Back-compatible wrapper over generate_with_meta() for callers that do not
    care whether the answer was replayed."""
    return generate_with_meta(prompt, model=model, use_cache=use_cache,
                              failover=failover)[0]


def ask(
    question: str,
    retriever: PerDocRetriever | None = None,
    plain: bool = False,
    k: int = 3,
    top_n: int = 6,
    min_per_doc: int = 1,
    min_score: float = MIN_SCORE,
    model: str = MODEL_NAME,
    use_llm: bool = True,
    use_cache: bool = True,
    failover: bool = False,
    history=None,
    retrieval_query: str | None = None,
) -> dict:
    """Ask one question. Returns {answer, citations, refused, scores, route}.

    Depth (k=3/doc, top_n=6): Q5's penalty clauses rank below generic
    preamble at top-4 (retrieval miss, not corpus gap); fragmented
    Constitution sections (s.46 split across chunks) need fuller context.
    Tuned 2026-09-08; still cheap for the free tier (6 short chunks).

    The merge to those six is select_top(), NOT a `[:top_n]` slice (Phase 09
    step 3 M2). The slice sorted candidates from three separate TF-IDF spaces
    by raw cosine -- a comparison PerDocRetriever's own docstring says is
    invalid -- and so re-introduced the Constitution flooding that per-doc
    retrieval exists to prevent. min_per_doc reserves each doc's best
    above-floor candidate; the budget stays six, only WHICH six changes. The
    refusal decision is provably unchanged -- see the block above select_top
    in src/retrieve.py.

    refused=True (answer = REFUSAL_MESSAGE, no LLM call) when nothing clears
    min_score. With use_llm=False (or no key) the retrieval half still runs
    and answer=None marks the LLM row pending -- never faked.

    Every LLM-backed result carries `cached` (True when the answer was
    replayed from the prompt-keyed answer cache rather than generated). It is
    reported at the top level AND in `route`, so any transcript written from
    this dict records whether the call was real. See the cache block above
    generate_with_meta().

    `route["model"]` keeps its existing meaning -- the model REQUESTED -- so no
    field in any historical transcript changes meaning. `model_used` is the new
    key and records what actually ran: the same value normally, FALLBACK_MODEL
    when failover fired, and None when no model ran at all (gate refusal,
    use_llm=False, or an error). Opting into `failover` without recording
    `model_used` would be exactly the "fake an LLM row" failure this project
    forbids, so the two ship together.

    CHAT (Phase 10 B), both parameters defaulted so every existing caller is
    untouched:

    `retrieval_query` is what RETRIEVAL sees; `question` stays what the USER
    asked and is the only thing that reaches the prompt, the citation check and
    the transcript. Separating them is what lets chat.contextualise() repeat and
    extend a query without the model ever seeing the mangled string -- and it
    keeps the refusal gate honest, because the gate is computed on whatever was
    actually retrieved on. `route["retrieval_query"]` records it whenever it
    differs, so a run can never hide that it searched for something other than
    what was asked.

    `history` is passed straight to build_prompt(). history=None renders a
    byte-identical prompt to the pre-chat one; see build_prompt's docstring for
    why that is load-bearing for both the cache and privacy.
    """
    if retriever is None:
        retriever = PerDocRetriever(build_corpus())
    query = retrieval_query if retrieval_query is not None else question
    merged = select_top(retriever.query(query, k=k), top_n,
                        min_per_doc=min_per_doc, floor=min_score)
    per_doc_top = {}
    for h in merged:
        per_doc_top.setdefault(h.doc_id, round(h.score, 4))
    hits = [h for h in merged if h.score >= min_score]
    scores = [
        {"doc_id": h.doc_id, "ref": h.ref, "score": round(h.score, 4)} for h in merged
    ]
    # A chat turn is a different prompt, so it gets a different version string
    # and therefore a different cache key -- single-turn transcripts stay
    # comparable to each other and can never be mixed with multi-turn ones.
    prompt_version = CHAT_PROMPT_VERSION if _render_history(history) else PROMPT_VERSION
    route = {
        "model": model,
        "model_used": None,  # set only when a model actually answered
        "prompt": prompt_version + ("-plain" if plain else ""),
        "min_score": min_score,
        "per_doc_top": per_doc_top,
        "plain": plain,
    }
    if query != question:
        route["retrieval_query"] = query
    if not hits:
        return {
            "question": question,
            "answer": REFUSAL_MESSAGE,
            "citations": [],
            "refused": True,
            "scores": scores,
            "route": route,
            "llm_used": False,
        }
    if not use_llm:
        return {
            "question": question,
            "answer": None,
            "citations": [],
            "refused": False,
            "scores": scores,
            "route": route,
            "llm_used": False,
        }
    try:
        answer, cached, model_used = generate_with_meta(
            build_prompt(question, hits, plain=plain, history=history),
            model=model, use_cache=use_cache, failover=failover)
    except Exception as e:  # quota/network: report pending, never fake
        return {
            "question": question,
            "answer": None,
            "citations": [],
            "refused": False,
            "scores": scores,
            "route": route,
            "llm_used": False,
            "cached": False,
            "model_used": None,  # nothing answered -- the row stays pending
            "llm_error": "%s: %s" % (type(e).__name__, e),
        }
    route["cached"] = cached
    route["model_used"] = model_used
    if NO_ANSWER_SENTENCE in answer:
        # Second refusal layer: retrieval passed the floor on shared words,
        # but the strict prompt found nothing supporting an answer.
        return {
            "question": question,
            "answer": REFUSAL_MESSAGE,
            "citations": [],
            "refused": True,
            "scores": scores,
            "route": route,
            "llm_used": True,
            "cached": cached,
            "model_used": model_used,
            "refusal_layer": "llm-no-answer",
        }
    return {
        "question": question,
        "answer": answer,
        "citations": extract_citations(answer),
        "refused": False,
        "scores": scores,
        "route": route,
        "llm_used": True,
        "cached": cached,
        "model_used": model_used,
        "cite_check": verify_citations(answer, hits),
    }
