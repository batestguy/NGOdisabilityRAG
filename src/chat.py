"""Conversation state for DRLCA: contextualisation, slot memory, turn storage.

Pure functions over plain data. No Streamlit, no network, no LLM, no disk. The
default user path stays fully offline (CLAUDE.md invariant), and everything in
this module runs on the free tier at zero cost because none of it calls
anything.

WHY THIS MODULE EXISTS, AND WHY IT IS NOT IN router.py
------------------------------------------------------
A follow-up like "so can they fire me?" carries no disability term and no
statutory term. TF-IDF over the Act cannot answer it, not because ranking is
bad but because the query does not contain the question. So ellipsis is a
RETRIEVAL problem, not a UI problem, and it has to be fixed before retrieval is
tuned -- otherwise Phases D-F optimise a query distribution the chatbot never
issues.

src/router.py is STATELESS and stays that way. Every routing decision there
depends only on the current string, which is what makes each turn independently
testable and what lets test_phase04.py assert on 10 fixed inputs. Conversation
state lives here and in the UI; the router is called, never mutated.

WHAT CONTEXTUALISATION CAN COST YOU
-----------------------------------
Carrying prior turns into the retrieval query means a TOPIC SHIFT can inherit
legal vocabulary from the turns before it and clear MIN_SCORE on words the user
never wrote. That turns an off-corpus question into a confident cited answer --
a genuinely new failure mode that single-turn DRLCA could not have. It is
measured, not assumed: scripts/eval_chat.py reports the
`off-corpus-after-legal` class separately and the `topic-shift` gate is "not
worse than naive", never "better".

THRESHOLDS WERE CHOSEN ON chat_dev AND NOTHING ELSE
---------------------------------------------------
THIN_MAX / MARKER_MAX / CARRY_WINDOW / QUESTION_WEIGHT below were set against
data/eval/conversations.json's chat_dev split. chat_test was authored blind
before this file existed and is read once. Selecting any of these on chat_test
would destroy the only clean multi-turn yardstick the project has.
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Same flat-module convention as router.py / rag.py: `import retrieve` must work
# whether or not src/ is already on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS  # noqa: E402

import router  # noqa: E402
from retrieve import stem  # noqa: E402  (the SAME stemmer the index was built with)

# --- Offline signals ---------------------------------------------------------

# Leading discourse markers. A turn that OPENS with one of these is continuing
# the previous turn rather than starting a new topic -- that is what the word is
# for. Matched only at the start, so "what about" fires on "what about trains?"
# but not on "tell me what about this act is enforceable".
_MARKERS = (
    "what about", "and what about", "how about", "and how about",
    "so what about", "what if", "and what if", "so what if",
    "so", "and", "then", "but", "also", "ok", "okay", "plus",
)

# Referring expressions with no antecedent inside the turn. First and second
# person are deliberately EXCLUDED: "I", "me", "my", "you" are bound by the
# speaking situation, not by earlier text, so they are not evidence of ellipsis.
# Every pronoun here is third-person or demonstrative.
_UNBOUND = frozenset({
    "it", "its", "they", "them", "their", "theirs", "he", "him", "his",
    "she", "her", "hers", "that", "this", "those", "these", "one", "ones",
})

# Content stems: alphabetic tokens, minus English stopwords, minus the unbound
# pronouns themselves (a turn is not "about" its pronouns), stemmed with the
# SAME stem() the TF-IDF index uses -- so "how many content words is this
# question carrying?" is measured in the retriever's own units, not in a second
# tokenisation that could drift from it.
_STOP = frozenset(ENGLISH_STOP_WORDS) | _UNBOUND


def content_stems(text: str) -> set:
    """Stemmed content tokens of `text` (stopwords and pronouns removed)."""
    toks = re.findall(r"[a-zA-Z]+", (text or "").lower())
    return {stem(t) for t in toks if t not in _STOP and len(t) > 1}


def leading_marker(text: str) -> str:
    """The discourse marker this turn opens with, or '' if none.

    Longest match wins, so "what about" is reported rather than the bare "what"
    that is not in the list anyway, and "and what about" beats "and".
    """
    low = (text or "").strip().lower()
    best = ""
    for m in _MARKERS:
        if re.match(r"%s\b" % re.escape(m), low) and len(m) > len(best):
            best = m
    return best


def unbound_pronouns(text: str) -> list:
    """Third-person/demonstrative pronouns present, in order of appearance."""
    toks = re.findall(r"[a-zA-Z]+", (text or "").lower())
    seen, out = set(), []
    for t in toks:
        if t in _UNBOUND and t not in seen:
            seen.add(t)
            out.append(t)
    return out


# --- Carry policy ------------------------------------------------------------
# Tuned on chat_dev (see the module docstring). Each constant answers a
# different question, which is why there are four of them and not one score.

CARRY_WINDOW = 2      # how many PRIOR user turns may enter the retrieval query
THIN_MAX = 3          # <= this many content stems: the turn cannot stand alone
MARKER_MAX = 4        # with a leading discourse marker, allow a slightly fuller turn
QUESTION_WEIGHT = 2   # times the current question is repeated in the merged query


def _should_carry(n_content: int, marker: str, pronouns: list) -> tuple:
    """(carry?, reason). The whole decision, in one auditable place.

    Three independent triggers, ORed, because they are evidence of different
    things:

      pronoun  an unbound referring expression is direct evidence that the
               antecedent is somewhere else. Fires regardless of length --
               "does anyone check how they spend it?" is a long turn and still
               unresolvable alone.
      thin     a turn with <= THIN_MAX content stems has too little signal to
               retrieve on at all ("what percentage?" is two words, one stem).
      marker   a leading "so"/"and"/"what about" is the user explicitly marking
               continuation. Allowed a slightly fuller turn than `thin`, but
               NOT an unlimited one -- and that bound is what protects the
               topic-shift and off-corpus-after-legal classes. "and what does
               the law say about maritime shipping insurance?" opens with a
               marker and still does not carry, because five content stems is a
               question that stands on its own feet.
    """
    if pronouns:
        return True, "unbound-pronoun:%s" % ",".join(pronouns)
    if n_content <= THIN_MAX:
        return True, "thin:%d<=%d" % (n_content, THIN_MAX)
    if marker and n_content <= MARKER_MAX:
        return True, "marker:%r,%d<=%d" % (marker, n_content, MARKER_MAX)
    return False, ("self-sufficient:%d content stems, marker=%r"
                   % (n_content, marker or ""))


def contextualise(turns, question: str) -> tuple:
    """(retrieval_query, meta) -- decide whether prior turns enter the query.

    `turns` is the conversation so far, oldest first: TurnPayload objects, or
    plain dicts/objects exposing a `question` (or `text`) attribute/key. Only
    the USER text of prior turns is ever carried -- never a generated answer.
    Two reasons, both load-bearing: on the default offline path there IS no
    generated answer (ask(use_llm=False) returns answer=None meaning pending),
    and an answer carries citation tags that would leak an earlier turn's
    evidence into this turn's query and then into its prompt.

    The merged query repeats the current question QUESTION_WEIGHT times before
    appending the carried window. TF-IDF is a bag of words, so repetition is
    weighting: the user's actual question keeps the larger share of the query
    vector and the carried context adds terms without taking the query over.
    Without that, a two-word follow-up would be outvoted by its own history.

    `meta` records WHAT was carried and WHY, including the rejected case, so
    every decision this module makes is inspectable in the UI and in the eval
    rather than being a number that appeared.
    """
    question = question or ""
    stems = content_stems(question)
    marker = leading_marker(question)
    pronouns = unbound_pronouns(question)
    prior = [t for t in (_turn_text(t) for t in (turns or [])) if t.strip()]
    window = prior[-CARRY_WINDOW:]
    win_stems = set().union(*(content_stems(t) for t in window)) if window else set()
    overlap = (len(stems & win_stems) / len(stems)) if stems else 0.0

    carry, reason = _should_carry(len(stems), marker, pronouns)
    if not window:
        # First turn of a conversation: nothing to carry, and the eval must see
        # naive and contextualised produce the SAME query here or it would be
        # crediting contextualisation for turns it never touched.
        carry, reason = False, "no-history"

    meta = {
        "carried": carry,
        "reason": reason,
        "marker": marker,
        "pronouns": pronouns,
        "n_content": len(stems),
        "window_size": len(window) if carry else 0,
        "carried_text": list(window) if carry else [],
        # Stem overlap between this turn and the window. Not a trigger -- it is
        # reported so a human can see, after the fact, whether a carry that
        # fired was picking up related vocabulary or importing a foreign topic.
        "window_overlap": round(overlap, 3),
        # router.score() is reused rather than re-derived, so the legal/help
        # signal recorded here is EXACTLY the signal resolve_mode() will route on.
        "scores": {k: v for k, v in router.score(question).items()
                   if k in ("legal", "help", "help_raw", "help_intent")},
    }
    if not carry:
        return question, meta
    merged = " ".join([question] * QUESTION_WEIGHT + window)
    meta["query_stems_added"] = sorted(win_stems - stems)
    return merged, meta


def _turn_text(t) -> str:
    """User text of a stored turn, accepting TurnPayload / dict / duck type."""
    if isinstance(t, dict):
        return t.get("question") or t.get("text") or ""
    return getattr(t, "question", None) or getattr(t, "text", "") or ""


# --- Slot memory -------------------------------------------------------------


def merge_help_slots(turns, question: str) -> dict:
    """Accumulated {disability, location} across the conversation.

    "I'm deaf" ... "anywhere in Kano?" is the case this exists for.
    router.extract_help_slots() on that second turn alone returns
    disability='' -- so the NGO connector would silently drop the deafness
    filter and answer a question the user did not ask. Slots therefore persist
    across turns, oldest to newest, and the CURRENT turn always wins: saying
    "actually, Lagos" must replace Kano, not be ignored because a slot was
    already filled.

    A slot is only ever overwritten by a NON-EMPTY value, so a later turn that
    mentions neither ("and their phone number?") keeps both filters rather than
    clearing them.

    Offline and free: this is router's own keyword scan, called once per turn.
    """
    slots = {"disability": "", "location": ""}
    for t in (turns or []):
        for key, val in router.extract_help_slots(_turn_text(t)).items():
            if val:
                slots[key] = val
    for key, val in router.extract_help_slots(question or "").items():
        if val:
            slots[key] = val
    return slots


# --- The stored unit of conversation -----------------------------------------


@dataclass
class TurnPayload:
    """One completed turn, everything needed to RE-RENDER it without recomputing.

    Streamlit re-executes the whole script on every interaction. A UI that
    looped over history and re-queried each turn would pay N retrievals per
    rerun -- per keystroke, per button, per theme flip -- and N times that again
    once the dense arm lands. So a turn is computed once and stored; Phase C
    replays these.

    NEVER WRITTEN TO DISK. This population discloses abuse and coercion. History
    lives in st.session_state for the life of the browser session and nowhere
    else. The on-disk prompt cache is safe by construction -- src/rag.py's
    _cache_write stores only prompt.rsplit("Question: ", 1)[-1], the current
    question line -- which is exactly why build_prompt() renders history BEFORE
    that final line and why the suite asserts it.
    """

    question: str                      # what the user typed, verbatim
    retrieval_query: str = ""          # what retrieval actually saw (may differ)
    mode: str = ""                     # greeting | legal | help | clarify
    excerpts: list = field(default_factory=list)  # [{tag, doc_id, ref, text, score}]
    answer: str | None = None          # None means PENDING, never "no answer"
    routing: dict = field(default_factory=dict)   # router.route_question() output
    cite_check: list = field(default_factory=list)  # rag.verify_citations() output
    ctx_meta: dict = field(default_factory=dict)  # contextualise() meta
    slots: dict = field(default_factory=dict)     # merge_help_slots() output
    refused: bool = False

    @property
    def tags(self) -> list:
        """Citation tags of this turn's evidence -- the ONLY citable set for it."""
        return [e["tag"] for e in self.excerpts]


def history_for_prompt(turns, max_turns: int = CARRY_WINDOW) -> list:
    """The last `max_turns` turns as [{question, answer}] for rag.build_prompt().

    Trimmed to questions and answers only: no excerpts, no scores, no tags. A
    prior turn is context for UNDERSTANDING the current question, never evidence
    for answering it, and the cheapest way to keep that true is to not put the
    earlier evidence in the prompt at all.
    """
    out = []
    for t in (turns or [])[-max_turns:]:
        q = _turn_text(t)
        if not q.strip():
            continue
        a = t.get("answer") if isinstance(t, dict) else getattr(t, "answer", None)
        out.append({"question": q, "answer": a})
    return out


def cross_turn_drift(answer: str, turns, hits) -> list:
    """Tags cited in `answer` that THIS turn did not retrieve but an earlier one did.

    rag.verify_citations() already fails a tag no current hit carries, so drift
    is caught either way. This names the specific, chat-only reason it happened:
    the model re-cited evidence it saw in an earlier turn of the same
    conversation. Reported per turn and counted as a metric; the allowed set is
    NOT widened to accommodate it. Drift stays visible as a defect.
    """
    import rag  # local import: rag is heavy and this is a reporting path only

    current = {rag.cite_tag(h.doc_id, h.ref) for h in (hits or [])}
    earlier = set()
    for t in (turns or []):
        tags = t.get("tags") if isinstance(t, dict) else getattr(t, "tags", None)
        earlier |= set(tags or [])
    return [tag for tag in rag.extract_citations(answer or "")
            if tag not in current and tag in earlier]
