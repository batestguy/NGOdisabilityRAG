"""Phase 04 intent router: keyword baseline (legal vs help), offline, no LLM.

Stdlib only for the scoring itself (re/pathlib); this module *wires* the
pinned Phase 02 (rag.ask) and Phase 03 (ngo.find_ngo_with_meta) subsystems
but never calls Gemini -- legal paths use ask(use_llm=False), so the whole
router runs offline on the free-tier-exhausted quota.

Scoring: each cue counts once (presence, not frequency); multi-word cues
weight 2, single-word cues weight 1. Route the higher score; TIE or
both-zero -> clarifying question (never guess -- a confident wrong route
is worse than asking).

Dual route: a query with BOTH legal and help signals (e.g. "my employer
fired me, who can help?") returns primary + secondary so the caller serves
a legal answer AND an NGO referral.

Help-signal tiers (why Q4 "sacked ... wheelchair" stays pure-legal):
HELP entity mentions alone (disability/location names, no help-seeking
verb) do NOT trigger the help route -- effective help is 0 without at
least one HELP_INTENT cue. Entity-only queries ("deaf" alone) therefore
clarify instead of guessing.

PHASE 05 UI GUIDANCE (top-k, not top-1):
- Always render the FULL top-k NGO list with the DRAC helpline banner
  first; never present meta["top1"] as a definitive single answer.
- When needs_confirmation is True (fuzzy fallback), show confirm_prompt
  ("did you mean ...?") and require explicit user confirmation before
  any contact/deep-link action.
"""

import re
import sys
from pathlib import Path

# Make `import ngo` / `import rag` work whether src/ is on sys.path or not.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# --- Cue lists ---------------------------------------------------------------
# Single-word cue -> weight 1; multi-word cue (contains a space) -> weight 2.

LEGAL_CUES = [
    r"\brights?\b", r"\blaws?\b", r"\bsections?\b", r"\bclauses?\b", r"\bact\b",
    r"\bconstitution\w*", r"\bdiscriminat\w*", r"\bpenalt\w*", r"\bemploy\w*",
    r"\bpunish\w*", r"\bfines?\b", r"\bimprison\w*", r"\beducation\b",
    r"\baccessib\w*", r"\bcommission\b", r"\bequal\w*",
    r"\bsacks?\b", r"\bsacked\b", r"\bfire\b", r"\bfired\b",
    r"\bdismiss\w*", r"\bterminat\w*",
    # Multi-word (weight 2): exact phrases that strongly signal legal intent.
    "free education", r"my rights?",
]

HELP_INTENT_CUES = [  # help-seeking language; at least one required to route help
    "need help", "who can help", "find help", "near me",  # multi-word -> 2
    r"\bhelps?\b", r"\bneed\b", r"\bwhere\b", r"\bcontacts?\b",
    r"\borganizations?\b", r"\borganisations?\b", r"\bhelplines?\b",
    r"\bphones?\b", r"\baddress\w*\b", r"\bsupports?\b",
]

HELP_ENTITY_CUES = [  # disability/location names; alone they never route help
    "down syndrome", "mental health",  # multi-word -> 2
    r"\bblinds?\b", r"\bdeafs?\b", r"\balbin\w*", r"\bspinals?\b",
    r"\bwheelcha\w*", r"\bprosth\w*", r"\bamput\w*", r"\blimbs?\b",
    r"\bhearings?\b", r"\bvisual\w*\b", r"\bdisab\w*",
    r"\blagos\b", r"\babuja\b", r"\bkano\b", r"\bkaduna\b",
]

# Bare generic singletons carry no routable intent ("help" alone could mean
# either subsystem) -> clarify with a targeted question. Content-bearing
# singletons ("discrimination", "albinism") still route on their cue.
_SINGLETON_CLARIFY = frozenset(
    {"help", "need", "where", "info", "contact", "support", "hello", "hi"}
)

CLARIFY_QUESTION = (
    "I want to point you the right way -- do you need (a) legal information "
    "about disability rights under the Act or Constitution, or (b) help finding "
    "an organisation or helpline near you?"
)

# Pure greetings ("hello", "hey, good morning!") are not questions at all --
# answering them with the refusal wall is a UX bug (2026-09-10). A greeting is
# ONLY greeting words; any content ("hello, what are my rights?") routes
# normally on its cues, and unknown words ("hello there") still clarify.
_GREETING_WORDS = frozenset({
    "hi", "hey", "hello", "greetings", "howdy", "yo",
    "morning", "afternoon", "evening", "good",
})
_GREETING_PAIRS = frozenset({"morning", "afternoon", "evening"})


def is_greeting(question: str) -> bool:
    """True iff the whole input is a bare greeting (zero legal/help cues)."""
    toks = re.findall(r"[a-zA-Z]+", (question or "").lower())
    if not toks or any(t not in _GREETING_WORDS for t in toks):
        return False
    if toks == ["good"]:
        return False  # bare "good" is content-free, not a greeting
    if "good" in toks and not any(p in toks for p in _GREETING_PAIRS):
        return False  # "good" must pair with morning/afternoon/evening
    s = score(" ".join(toks))
    return s["legal"] == 0 and s["help"] == 0

_MULTI_WEIGHT = 2
_SINGLE_WEIGHT = 1


def _weight(cue: str) -> int:
    return _MULTI_WEIGHT if " " in cue else _SINGLE_WEIGHT


def _hits(question: str, cues: list) -> list:
    """Cue patterns (regex) that match the question, in cue-list order.

    No double-counting: a multi-word hit consumes its span (blanked before
    single-word cues are matched), so e.g. "my right" scores "my rights?"
    (2) but not "rights?" again -- otherwise the Pidgin mixed query ties
    3-3 and wrongly clarifies instead of dual-routing.
    """
    multi = [c for c in cues if " " in c]
    single = [c for c in cues if " " not in c]
    masked = question
    hits = []
    for c in multi:
        m = re.search(c, masked, re.IGNORECASE)
        if m:
            hits.append(c)
            masked = masked[:m.start()] + " " * (m.end() - m.start()) + masked[m.end():]
    hits.extend(c for c in single if re.search(c, masked, re.IGNORECASE))
    # Restore cue-list order for stable matched_cues output.
    return [c for c in cues if c in hits]


def score(question: str) -> dict:
    """Raw weighted scores + matched cues + help-intent flag (no routing)."""
    legal_hits = _hits(question, LEGAL_CUES)
    intent_hits = _hits(question, HELP_INTENT_CUES)
    entity_hits = _hits(question, HELP_ENTITY_CUES)
    legal = sum(_weight(c) for c in legal_hits)
    help_raw = sum(_weight(c) for c in intent_hits + entity_hits)
    intent = bool(intent_hits)
    # Entity-only help mentions carry no routing weight (see module docstring).
    help_eff = help_raw if intent else 0
    return {
        "legal": legal, "help": help_eff, "help_raw": help_raw,
        "help_intent": intent,
        "legal_cues": legal_hits, "help_cues": intent_hits + entity_hits,
    }


def route_question(question: str) -> dict:
    """Keyword route -> {primary, secondary, scores, matched_cues, ...}.

    primary: 'legal' | 'help' | 'clarify'. Mixed-signal queries return
    primary + secondary (dual route); ties and no-signal queries return
    primary 'clarify' with clarify_question (secondary None).
    """
    s = score(question or "")
    scores = {"legal": s["legal"], "help": s["help"]}
    matched = {"legal": s["legal_cues"], "help": s["help_cues"]}
    base = {"scores": scores, "matched_cues": matched}

    toks = re.findall(r"[a-zA-Z]+", (question or "").lower())
    if len(toks) == 1 and toks[0] in _SINGLETON_CLARIFY:
        # Bare "help"/"where"/... carries no routable intent (review 2026-09-08).
        return {"primary": "clarify", "secondary": None,
                "clarify_question": CLARIFY_QUESTION, **base}
    if s["legal"] == 0 and s["help"] == 0:
        return {"primary": "clarify", "secondary": None,
                "clarify_question": CLARIFY_QUESTION, **base}
    if s["legal"] == s["help"]:
        # Tie WITH signal on both sides: never guess which the user meant.
        # Deliberate policy (review 2026-09-08): a 2-2 near-dual like
        # "deaf + sacked + where" clarifies rather than dual-routes, because
        # a confident-looking wrong route costs more than one question.
        return {"primary": "clarify", "secondary": None,
                "clarify_question": CLARIFY_QUESTION, **base}
    if s["legal"] > 0 and s["help"] > 0:
        primary = "legal" if s["legal"] > s["help"] else "help"
        secondary = "help" if primary == "legal" else "legal"
        return {"primary": primary, "secondary": secondary, **base}
    primary = "legal" if s["legal"] > s["help"] else "help"
    return {"primary": primary, "secondary": None, **base}


# --- Help-slot extraction (keyword scan for the Phase 03 lookup) -------------

_DISABILITY_SCAN = [  # ordered: multi-word / specific forms first
    ("down syndrome", "Down syndrome"), ("mental health", "mental health"),
    ("hearing", "hearing impairment"), ("deaf", "deaf"),
    ("visual", "visual impairment"), ("blind", "blindness"),
    ("albin", "albinism"), ("prosthetic", "prosthetic"),
    ("prosthesis", "prosthesis"), ("amput", "amputation"),
    ("limb", "limb loss"), ("spinal", "spinal cord injury"),
    ("wheelchair", "wheelchair"),
]
_LOCATION_SCAN = ["lagos", "abuja", "kano", "kaduna"]


def extract_help_slots(question: str) -> dict:
    """Disability/location slot strings for find_ngo_with_meta ("" = no filter)."""
    q = (question or "").lower()
    disability = next((v for k, v in _DISABILITY_SCAN if k in q), "")
    location = next((loc for loc in _LOCATION_SCAN if loc in q), "")
    return {"disability": disability, "location": location}


# --- Wired dispatch (offline: ask(use_llm=False), find_ngo_with_meta) --------

ROOT = Path(__file__).resolve().parent.parent
NGO_CSV = ROOT / "data" / "ngo.csv"

_retriever = None
_ngo_df = None


def get_retriever():
    """Lazily built Phase 02 retriever (corpus build is slow; reuse it)."""
    global _retriever
    if _retriever is None:
        from rag import PerDocRetriever, build_corpus
        _retriever = PerDocRetriever(build_corpus())
    return _retriever


def get_ngo_df():
    """Lazily loaded verified NGO frame."""
    global _ngo_df
    if _ngo_df is None:
        from ngo import load_ngo
        _ngo_df = load_ngo(str(NGO_CSV))
    return _ngo_df


def _help_payload(question: str, df=None, k: int = 3) -> dict:
    """Helplines-first NGO records via find_ngo_with_meta (never bare find_ngo).

    Phase 03 residual: meta.fuzzy_fallback stays visible; when True the
    payload carries needs_confirmation=True + a "did you mean ...?" prompt
    so the UI asks instead of presenting an approximate top-1 as fact.
    """
    from ngo import find_ngo_with_meta
    df = get_ngo_df() if df is None else df
    slots = extract_help_slots(question)
    frame, meta = find_ngo_with_meta(
        df, disability=slots["disability"], location=slots["location"], k=k)
    payload = {"records": frame.to_dict("records"), "meta": meta,
               "slots": slots, "needs_confirmation": bool(meta["fuzzy_fallback"]),
               "confirm_prompt": ""}
    if meta["fuzzy_fallback"]:
        payload["confirm_prompt"] = (
            "Just to confirm -- did you mean '%s'? Your words matched our "
            "list approximately ('%s'), so please confirm or browse the full "
            "top-%d list below rather than relying on the first result alone."
            % (meta.get("top1") or "one of these organisations",
               slots["disability"] or slots["location"] or question[:60], k))
    return payload


def route(question: str, df=None, retriever=None, k: int = 3) -> dict:
    """Full dispatch: routing + subsystem payloads, zero LLM calls.

    - 'legal' -> retrieval-ready (ask with use_llm=False; answer None means
      retrieval passed and the LLM row is pending, never faked).
    - 'help' -> helplines-first NGO records (+ fuzzy confirm prompt if set).
    - dual (secondary set) -> both payloads.
    - 'clarify' -> the clarifying question, no subsystem call.
    """
    from rag import ask
    routing = route_question(question)
    out = {"question": question, "routing": routing,
           "legal": None, "help": None}
    if routing["primary"] == "clarify":
        out["clarify_question"] = routing["clarify_question"]
        return out
    retriever = get_retriever() if retriever is None else retriever
    wants_legal = routing["primary"] == "legal" or routing["secondary"] == "legal"
    wants_help = routing["primary"] == "help" or routing["secondary"] == "help"
    if wants_legal:
        # Offline proof of the retrieval path: no key, no network, no Gemini.
        out["legal"] = ask(question, retriever=retriever, use_llm=False)
    if wants_help:
        out["help"] = _help_payload(question, df=df, k=k)
    return out
