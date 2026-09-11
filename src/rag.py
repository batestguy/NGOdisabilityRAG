"""Phase 02 citation-RAG: strict with refusal.

Pipeline: build_corpus() (reuses src/load + src/chunk) -> PerDocRetriever
-> ask(): retrieval gate (MIN_SCORE) -> Gemini generation with a
citation-forcing prompt. Weak/empty retrieval NEVER reaches the LLM:
the caller gets the fixed refusal message (+ DRAC helplines) instead.

Locked decision: answer ONLY from retrieved chunks with section cites;
refuse when retrieval is weak. The LLM must cite chunk text VERBATIM --
even with OCR quirks -- never "clean up" section numbers.
"""
import os
import re
from pathlib import Path

from chunk import constitution_aware_split, recursive_split, section_aware_split
from load import build_clean_text, clean_text, repair_joins
from retrieve import MIN_SCORE, Chunk, PerDocRetriever, cite_tag

# Resolved 2026-09-08 via client.models.list(): `models/gemini-2.5-flash`
# exists ("Gemini 2.5 Flash"); `gemini-2.0-flash` is gone (retired).
# Short id "gemini-2.5-flash" is the API-usable form of the same model.
MODEL_NAME = "gemini-2.5-flash"
PROMPT_VERSION = "cite-strict-v2"

# Sizes pinned from Phase 01: Act section-aware 800; Constitution
# chapter-aware RECOMMENDED 400 (Q9 needs <=400 to pass 0.16);
# Factsheet recursive 500/50.
ACT_SIZE = 800
CONST_SIZE = 400
FACT_SIZE = 500
FACT_OVERLAP = 50

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


def build_corpus() -> dict[str, list[Chunk]]:
    """Load + chunk all three docs. Raw files are never modified."""
    docs: dict[str, list[Chunk]] = {}

    raw_act = ACT_PATH.read_text(encoding="utf-8", errors="replace")
    act_text, _, _ = build_clean_text(raw_act, repair=True, dedupe=True)
    act_text = clean_text(act_text)
    docs["act2018"] = [
        Chunk("act2018", act_ref(c), c)
        for c in section_aware_split(act_text, size=ACT_SIZE)
    ]

    raw_const = CONST_PATH.read_text(encoding="utf-8", errors="replace")
    const_text = clean_text(repair_joins(raw_const))
    docs["constitution1999"] = [
        Chunk("constitution1999", const_ref(c), c)
        for c in constitution_aware_split(const_text, size=CONST_SIZE)
    ]

    raw_fact = FACT_PATH.read_text(encoding="utf-8", errors="replace")
    fact_text = clean_text(repair_joins(raw_fact))
    docs["factsheet2020"] = [
        Chunk("factsheet2020", fact_ref(c), c)
        for c in recursive_split(fact_text, size=FACT_SIZE, overlap=FACT_OVERLAP)
    ]
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


def build_prompt(question: str, hits, plain: bool = False) -> str:
    """Assemble system instruction + cited excerpts + question."""
    lines = [SYSTEM_PROMPT]
    if plain:
        lines.append(PLAIN_SUFFIX)
    lines.append("\nRetrieved excerpts (cite VERBATIM, quirks included):")
    for h in hits:
        lines.append(
            "\n%s (relevance %.3f):\n%s" % (cite_tag(h.doc_id, h.ref), h.score, h.text)
        )
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


def generate(prompt: str, model: str = MODEL_NAME) -> str:
    """Single Gemini generation via the new `google.genai` SDK (not the
    retired `google.generativeai` package, not the retired 2.0-flash)."""
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_API_KEY/GEMINI_API_KEY not set")
    from google import genai
    client = genai.Client(api_key=key)
    resp = client.models.generate_content(model=model, contents=prompt)
    return (resp.text or "").strip()


def ask(
    question: str,
    retriever: PerDocRetriever | None = None,
    plain: bool = False,
    k: int = 3,
    top_n: int = 6,
    min_score: float = MIN_SCORE,
    model: str = MODEL_NAME,
    use_llm: bool = True,
) -> dict:
    """Ask one question. Returns {answer, citations, refused, scores, route}.

    Depth (k=3/doc, top_n=6): Q5's penalty clauses rank below generic
    preamble at top-4 (retrieval miss, not corpus gap); fragmented
    Constitution sections (s.46 split across chunks) need fuller context.
    Tuned 2026-09-08; still cheap for the free tier (6 short chunks).

    refused=True (answer = REFUSAL_MESSAGE, no LLM call) when nothing clears
    min_score. With use_llm=False (or no key) the retrieval half still runs
    and answer=None marks the LLM row pending -- never faked.
    """
    if retriever is None:
        retriever = PerDocRetriever(build_corpus())
    merged = retriever.query(question, k=k)[:top_n]
    per_doc_top = {}
    for h in merged:
        per_doc_top.setdefault(h.doc_id, round(h.score, 4))
    hits = [h for h in merged if h.score >= min_score]
    scores = [
        {"doc_id": h.doc_id, "ref": h.ref, "score": round(h.score, 4)} for h in merged
    ]
    route = {
        "model": model,
        "prompt": PROMPT_VERSION + ("-plain" if plain else ""),
        "min_score": min_score,
        "per_doc_top": per_doc_top,
        "plain": plain,
    }
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
        answer = generate(build_prompt(question, hits, plain=plain), model=model)
    except Exception as e:  # quota/network: report pending, never fake
        return {
            "question": question,
            "answer": None,
            "citations": [],
            "refused": False,
            "scores": scores,
            "route": route,
            "llm_used": False,
            "llm_error": "%s: %s" % (type(e).__name__, e),
        }
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
        "cite_check": verify_citations(answer, hits),
    }
