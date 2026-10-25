"""Shared Streamlit render helpers for DRLCA's chat UI (H8b, 2026-10-22).

Moved verbatim out of app.py: the helpers here render a turn the same way
whether it is being computed (app.render_turn) or replayed from a stored
TurnPayload (app.replay_turn). Nothing here retrieves, routes or calls a
model; the compute halves (render_legal, render_help, the AI expander and its
_run_ai_turn) stay in app.py, next to the loaders and the quota log they use.

Import-safe like app.py: every Streamlit call happens inside a function, and
this module never imports app (app imports it). app.py re-exports every name
below, so `app.<name>` and inspect.getsource(app.<name>) keep working.
"""

import html
import sys
from pathlib import Path

import chat  # history_for_prompt, for the prompt-version caption
import telemetry  # H7: counts-only stdout lines; no network, no file
from ui_i18n import LAW_IN_ENGLISH, T, current_lang  # chrome only, never the law


def _st():
    # Same as app._st(): both return the one `streamlit` module object, so
    # session_state written through either is the state read here.
    import streamlit as st
    return st


def _switch_label(primary: str) -> str:
    return "help" if primary == "legal" else "legal"


def _requeue_last(route: str):
    """Re-ask the LAST turn on `route`: pop it, re-queue it, rerun.

    Scoped to the last turn, which is both the only turn whose fixed-key
    controls are rendered and the only turn it is safe to re-answer: every
    later turn was contextualised against this one (chat.contextualise), so
    re-answering a mid-conversation turn would silently invalidate answers the
    user has already read.
    """
    st = _st()
    turns = st.session_state.get("turns") or []
    question = turns[-1].question if turns else st.session_state.get("last_q", "")
    if turns:
        turns.pop()
    st.session_state["explicit"] = route
    st.session_state["submitted"] = True
    st.session_state["pending"] = question
    st.rerun()


def render_routing_trap(mode: str):
    """'I treated this as X [switch to Y]' -- a misroute costs one click.

    Last turn only. The key is fixed (switch-legal / switch-help) and Streamlit
    keys are page-global, so one per page is all the widget system allows --
    and re-answering an older turn is wrong anyway (see _requeue_last).
    """
    st = _st()
    other = _switch_label(mode)
    st.caption("I treated this as a **%s** question." % mode.upper())
    if st.button("Switch to %s" % other, key="switch-%s" % mode,
                 help="Re-answer the same question via the other route"):
        _requeue_last(other)


GREETING_TEXT = (
    "Hello! I'm DRLCA — I answer questions about Nigerian disability rights "
    "(Disability Act 2018 + 1999 Constitution, always with citations) and help "
    "find verified organisations and helplines near you. Ask your question in "
    "the box at the bottom of the page, then just keep replying — I follow the "
    "conversation.")


def render_greeting():
    st = _st()
    st.success("👋 " + GREETING_TEXT)


def render_clarify(clarify_text: str, live: bool = True):
    """The clarifying question, plus its two one-click answers on the last turn.

    Clarify is now ALSO just a turn: the user can ignore the buttons and simply
    reply. The buttons stay because one click is cheaper than retyping, and
    because their keys are asserted -- but they are rendered only for the
    newest turn, where re-asking is safe.
    """
    st = _st()
    st.warning("❓ " + clarify_text)
    if not live:
        return
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Legal info about my rights", key="clarify-legal"):
            _requeue_last("legal")
    with c2:
        if st.button("Find help near me", key="clarify-help"):
            _requeue_last("help")
    st.caption("…or just reply in the box below — a clarification is only a turn.")


# How many excerpt cards render inline before the rest fold into one expander.
# A DISPLAY split and nothing else: retrieval still returns the same twelve
# chunks ask() sees, and a generated answer may still cite all twelve. Pool
# depth moved 6 -> 12 in Phase E1b (2026-09-20), in the same commit as the
# harnesses that measure it, exactly as this comment promised. INLINE_EXCERPTS
# itself did NOT move: the display is 3 inline + 9 folded.
INLINE_EXCERPTS = 3


def _render_excerpt(e):
    st = _st()
    st.markdown("`%s` (relevance %.3f)" % (e["tag"], e["score"]))
    # lang='en': the law is quoted in its official English text whatever the
    # interface language, so a screen reader keeps an English voice here.
    st.markdown("<div class='drlca-answer' lang='en'>%s…</div>"
                % html.escape(e["text"][:700]), unsafe_allow_html=True)


def dedupe_excerpts(excerpts) -> list:
    """Drop an excerpt whose (doc_id, ref, text) equals one already kept; keep the first.

    The corpus holds at least one byte-identical chunk pair ([Constitution s. 4],
    recorded 2026-09-20), so a turn could show the same card twice. H1b fixes it
    HERE, at display, rather than in the corpus: a corpus change re-keys the OOV
    bridge and every pinned digest, while every retrieval metric scores the
    retrieved set, which this leaves untouched. Applied before the inline/fold
    split, so INLINE_EXCERPTS still means "3 distinct".
    """
    seen, out = set(), []
    for e in excerpts:
        key = (e.get("doc_id"), e.get("ref"), e.get("text"))
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def render_excerpts(excerpts, turn_index: int):
    """One turn's excerpt cards: INLINE_EXCERPTS inline, the rest behind one fold.

    Shared by the live path and the replay path so a turn looks the same
    however it got on screen. In a single-turn UI the cards were the page; in a
    conversation they sit between the user and their next question -- which is
    why the fold exists, and why E1b's move from 6 to 12 retrieved chunks
    changed what is BEHIND the fold and not what is in front of it.
    """
    st = _st()
    st.markdown(T("**Retrieved excerpts (offline, citations kept):**"))
    if current_lang() in LAW_IN_ENGLISH:
        st.caption(LAW_IN_ENGLISH[current_lang()])
    excerpts = dedupe_excerpts(excerpts)
    for e in excerpts[:INLINE_EXCERPTS]:
        _render_excerpt(e)
    rest = excerpts[INLINE_EXCERPTS:]
    if rest:
        with st.expander("📄 %d more excerpt(s) retrieved for this turn"
                         % len(rest), expanded=False):
            for e in rest:
                _render_excerpt(e)


def _multi_turn(prior) -> bool:
    """Will this turn's history actually REACH the prompt?

    The real condition ask() branches on -- rag._render_history() non-empty --
    not a proxy like `turn_index > 0`. chat.history_for_prompt() applies
    CARRY_WINDOW and drops blank turns, so a turn can have predecessors and
    still render a single-turn prompt. Asking the same two functions ask() asks
    is what makes the caption below track the prompt builder instead of merely
    agreeing with it today.
    """
    from rag import _render_history
    return bool(_render_history(chat.history_for_prompt(prior)))


def _prompt_id(plain: bool, multi_turn: bool) -> str:
    """The prompt version a turn uses, READ FROM rag rather than hardcoded.

    Mirrors the single line in ask() that picks between the two versions --
    given a `multi_turn` computed by _multi_turn(), which evaluates the same
    condition rather than approximating it. It replaces Phase 05's probe, which
    cost a SECOND full ask() per turn purely to display this string --
    affordable once per page, not once per turn per rerun. That the plain flag
    really threads through is proven where proof belongs: the answer_legal
    asserts in scripts/test_phase05.py.
    """
    from rag import CHAT_PROMPT_VERSION, PROMPT_VERSION
    return ((CHAT_PROMPT_VERSION if multi_turn else PROMPT_VERSION)
            + ("-plain" if plain else ""))


def render_plain_caption(plain: bool, prior=None):
    st = _st()
    st.caption("Plain-language mode: **%s** (prompt: `%s`)"
               % ("ON" if plain else "OFF",
                  _prompt_id(plain, _multi_turn(prior))))


def render_context_note(payload):
    """Why this turn searched for what it searched for -- carried context, visible.

    chat.contextualise() can quietly change the query behind a two-word
    follow-up. Saying so is the difference between a system that resolves
    ellipsis and one that appears to read minds.
    """
    st = _st()
    meta = payload.ctx_meta or {}
    if not meta.get("carried"):
        return
    st.caption("🔗 Read as a follow-up (%s) — I searched using the previous "
               "turn as well as this one." % meta.get("reason", "context carried"))


def render_defects(payload):
    """Citation failures and cross-turn drift, in the OPEN -- never behind a fold.

    chat.cross_turn_drift() names the chat-only failure mode: the model
    re-cited a tag it saw in an EARLIER turn that this turn did not retrieve.
    The response is never to widen the citable set to absorb it. It is shown to
    the user, on the turn, as a defect in the text they are reading.
    """
    st = _st()
    bad = [c["tag"] for c in (payload.cite_check or []) if not c.get("number_ok")]
    if bad:
        st.warning("⚠️ %d citation(s) in the AI text name a section number this "
                   "turn did not retrieve: %s. Trust the excerpts above."
                   % (len(bad), ", ".join(bad)))
    if payload.drift:
        st.warning("⚠️ Cross-turn citation drift: %s. The AI re-used evidence "
                   "from an earlier turn that this turn did not retrieve. "
                   "Earlier turns are context, not evidence." % ", ".join(payload.drift))


NGO_ANY_TYPE, NGO_ANY_STATE = "Any type", "Any state"
NGO_SORTS = {"Relevance to your question": "relevance", "Name (A to Z)": "name"}


def render_help_records(payload, turn_index: int = 0):
    """Render a help payload -- shared by the live path and the replay path.

    H3a: an optional, collapsed filter/sort over the payload's STORED
    `directory` (no lookup, no router: replay rules). Keys carry the turn
    index so turns never share filter state. The default view is unchanged.

    The controls render AFTER the results (screen-reader users meet the
    answer first, H3 review); their current values are read from
    session_state, which Streamlit fills before the script reaches them.

    Returns the payload AS DISPLAYED (filtered/sorted records, confirm flag)
    so read-aloud speaks what is on screen. The stored payload is untouched.
    """
    st = _st()
    from ngo import filter_options, filter_records
    records = (payload or {}).get("records", [])
    directory = payload.get("directory") or records[2:]
    types, states = filter_options(directory)
    k_type, k_state, k_sort = ("ngo-type-%d" % turn_index, "ngo-state-%d" % turn_index,
                               "ngo-sort-%d" % turn_index)
    dtype = st.session_state.get(k_type, NGO_ANY_TYPE)
    state = st.session_state.get(k_state, NGO_ANY_STATE)
    sort = NGO_SORTS.get(st.session_state.get(k_sort), "relevance")
    narrowed = dtype not in (None, NGO_ANY_TYPE) or state not in (None, NGO_ANY_STATE)
    if narrowed:
        records = filter_records(
            directory, "" if dtype in (None, NGO_ANY_TYPE) else dtype,
            "" if state in (None, NGO_ANY_STATE) else state, sort)
        st.markdown("**Filtered: %s · %s · sorted by %s. Showing %d contact(s), "
                    "helplines first:**"
                    % (dtype, state, sort, len(records)))
        if len(records) <= 2:
            st.info("No organisation in this list matches those filters. The "
                    "national helplines above can refer you.")
    else:
        if sort == "name":  # sort alone reorders THIS answer's top-k, nothing more
            records = filter_records(records[2:], sort="name")
        st.markdown("**Showing %d contact(s) (helplines first, then top-%d "
                    "organisations -- never top-1-only):**"
                    % (len(records), max(len(records) - 2, 0)))
    confirm = payload.get("needs_confirmation") and not narrowed
    if confirm:
        st.warning("🔍 " + payload.get("confirm_prompt", ""))
    for r in records[2:]:  # org rows; banner rows live in the pinned banner
        badge = " ⚠️ *please confirm this matches your need*" if confirm else ""
        st.markdown("**%s**%s" % (r.get("name", "?"), badge))
        contact = "📞 %s" % r.get("phone", "")
        if r.get("email"):
            contact += " | ✉️ %s" % r["email"]
        lines = ["Focus: %s | Location: %s" % (r.get("disability_focus", ""),
                                               r.get("location", "")), contact,
                 r.get("website", ""), r.get("description", "")]
        st.markdown("\n".join("- " + x for x in lines if x))
    with st.expander("🔎 Filter or sort these organisations", expanded=False):
        st.selectbox("Disability type", [NGO_ANY_TYPE] + types, key=k_type)
        st.selectbox("State", [NGO_ANY_STATE] + states, key=k_state)
        st.radio("Sort organisations by", list(NGO_SORTS), key=k_sort)
        st.caption("National and all-disability organisations always stay "
                   "in the list. The helplines always come first.")
    return dict(payload or {}, records=records, needs_confirmation=bool(confirm))


HELPFUL_PRIVACY_NOTE = (
    "Your yes/no is counted with: which route answered (law or help), whether "
    "it was refused, a score band, and how many excerpts or contacts were "
    "shown. Not your question and not your conversation, unless you switch "
    "on \"Also share the words of my questions\" in the sidebar.")


def _helpful_changed(key: str, signal_id: str) -> None:
    st = _st()
    telemetry.emit(telemetry.helpful_record(signal_id, st.session_state.get(key)))


def render_helpful(payload, turn_index: int) -> None:
    """H7: optional "Was this answer helpful?" per assistant turn.

    A native radio group (fieldset + legend), so keyboard and screen readers
    get it for free. Nothing is selected until the user picks. The privacy
    note sits next to it. The line is emitted from on_change, which runs once
    per actual change, never on a plain rerun.
    """
    st = _st()
    key = "helpful-%d" % turn_index
    st.radio("Was this answer helpful?", list(telemetry.HELPFUL_VALUES), index=None,
             horizontal=True, key=key, on_change=_helpful_changed,
             args=(key, payload.signal_id or ""))
    st.caption(HELPFUL_PRIVACY_NOTE)


def _import_mic_recorder():
    """Import mic_recorder without letting repo src/ shadow stdlib `chunk`.

    Chain: streamlit-mic-recorder -> SpeechRecognition -> stdlib aifc ->
    `from chunk import Chunk` (stdlib). With src/ first on sys.path that
    resolves to our src/chunk.py and raises ImportError. So: drop the src
    entry from sys.path for the duration of the import, then restore the
    path AND sys.modules['chunk'] (otherwise the cached stdlib module would
    shadow our src/chunk.py for every later `from chunk import ...`).

    Returns the mic_recorder callable, or None (caller degrades gracefully).
    """
    # This file lives IN src/, so its own directory is the src entry (in
    # app.py this read `Path(__file__).resolve().parent / "src"`: same path).
    src_entry = str(Path(__file__).resolve().parent)
    saved_path = list(sys.path)
    saved_mods = {k: v for k, v in sys.modules.items()
                  if k == "chunk" or k.startswith("chunk.")}
    try:
        sys.path = [p for p in saved_path
                    if Path(p or ".").resolve() != Path(src_entry).resolve()]
        for k in saved_mods:
            del sys.modules[k]
        from streamlit_mic_recorder import mic_recorder
        return mic_recorder
    except Exception:
        return None
    finally:
        sys.path = saved_path
        for k in [k for k in sys.modules if k == "chunk" or k.startswith("chunk.")]:
            del sys.modules[k]
        sys.modules.update(saved_mods)


def try_voice_input():
    """Optional mic button; graceful fallback keeps the text box primary."""
    st = _st()
    mic_recorder = _import_mic_recorder()
    if mic_recorder is None:
        st.info("🎤 Voice input unavailable (`streamlit-mic-recorder` not "
                "installed or not importable). The text box above is fully "
                "sufficient. Voice input needs Chrome/Edge + microphone "
                "permission.")
        return  # graceful degradation: text box stays primary (review 2026-09-08)
    # Disclosure BEFORE recording (H2 review 2026-10-18): until the WAV fix
    # no clip ever reached recognize_google, so no audio ever left the browser.
    # Now it does, and this population may be describing abuse.
    st.caption("🔒 Recording sends your voice to Google's speech service to be "
               "turned into text. Typing sends nothing anywhere.")
    audio = mic_recorder(start_prompt="🎤 Record question",
                         stop_prompt="⏹ Stop recording",
                         format="wav",  # sr.AudioFile reads WAV/AIFF/FLAC, never the webm default
                         key="drlca-mic")
    if not audio or not audio.get("bytes"):
        st.caption("🎤 Optional: record your question (Chrome/Edge + mic "
                   "permission). Or type in the box above.")
        return
    sig = (len(audio["bytes"]), hash(audio["bytes"]) % 10**8)
    if st.session_state.get("mic_sig") == sig:
        return  # already transcribed this clip; don't redo every rerun
    try:
        import io
        import speech_recognition as sr
        rec = sr.Recognizer()
        with sr.AudioFile(io.BytesIO(audio["bytes"])) as src:
                    heard = rec.recognize_google(rec.record(src))
        # Writes `voice_draft`, NOT `q`. Streamlit forbids mutating a
        # widget-keyed session_state value after that widget has rendered in
        # the same run, and the draft box below owns `q`; render_voice_draft()
        # copies voice_draft -> q BEFORE instantiating it.
        st.session_state["voice_draft"] = heard
        st.session_state["mic_sig"] = sig
        st.success("Heard: “%s” -- review/edit it below, then press Send." % heard)
    except Exception as exc:
        st.warning("🎤 Could not transcribe that clip (%s). The text box "
                   "above is fully sufficient -- please type your question. "
                   "Mic needs Chrome/Edge + permission + internet."
                   % type(exc).__name__)


def render_voice_draft():
    """Mic -> editable draft -> Send. The review step is the whole point.

    st.chat_input cannot be pre-filled programmatically, so a transcript can
    never land in it. Routing the mic through a draft box the user can correct
    is the safer half of that trade anyway: without a review step a
    mis-transcription becomes a submitted turn, and here the question decides
    which law gets searched and which contacts get shown.
    """
    st = _st()
    with st.expander(T("🎤 Voice input (optional)"), expanded=False):
        try_voice_input()
        # Seeding and clearing both happen BEFORE the widget is instantiated.
        # Streamlit forbids mutating a widget-keyed session_state value once
        # its widget has rendered in the same run, so Send asks for the clear
        # and the NEXT run performs it.
        if st.session_state.pop("voice_clear", False):
            st.session_state["q"] = ""
        if st.session_state.get("voice_draft"):
            st.session_state["q"] = st.session_state.pop("voice_draft")
        draft = st.text_input("Type your question here", key="q",
                              placeholder="e.g. What are my education rights? / "
                                          "Find blind support in Lagos",
                              help="A voice transcript lands here for review. "
                                   "Edit it, then press Send.")
        if st.button("Send this question", key="voice-send"):
            if (draft or "").strip():
                st.session_state["pending"] = draft.strip()
                st.session_state["voice_clear"] = True
                st.rerun()
            st.warning("Please record or type a question first.")
