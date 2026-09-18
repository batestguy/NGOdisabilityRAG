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

from chunk import constitution_aware_split, recursive_split, section_aware_split
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
    sections ('Sections 28-30', S/N rows) -> member-list label."""
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


def build_corpus(version: str | None = None) -> dict[str, list[Chunk]]:
    """Load + chunk all three docs. Raw files are never modified.

    version defaults to CORPUS_VERSION ("v1" until D6), so every existing
    no-arg caller is unchanged. The default no-arg path is v1 and is
    byte-identical to every published baseline.

    "v2" is a PARTIAL-v2 state on purpose: the Act is v2, the Constitution and
    the Factsheet are still v1, because D3 (Factsheet S/N table) and D4
    (Constitution Arrangement exclusion) have not been done yet. It exists so
    D2's Act gate is measurable now. Their rows in audit_corpus.py --corpus=v2
    therefore still read v1 shape (99 general / 9 general + 19 packed) and that
    is correct at this step. See docs/phases/12_corpus_v2.md D3/D4.

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
    docs["constitution1999"] = _const_chunks_v1()
    docs["factsheet2020"] = _fact_chunks_v1()
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
