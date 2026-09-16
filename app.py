"""Phase 05 accessible Streamlit UI for DRLCA (Disability Rights Legal & Connection Assistant).

Free-tier-deployable (Render/Streamlit Cloud): no local binaries, secrets only via env (GOOGLE_API_KEY read
by src/rag.py at call time), lean imports. Default user path is FULLY OFFLINE
(retrieval excerpts + citations + NGO records); Gemini generation sits behind an
explicit opt-in expander that defaults OFF (free-tier quota is reserved).

Import-safe: all Streamlit calls live inside run()/render helpers. `python -c
"import app"` must never boot a server or call Gemini -- the guard at the
bottom only runs the UI under `streamlit run` / `__main__`.
"""

import html
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import chat  # noqa: E402  (contextualise / merge_help_slots / drift -- offline, free)
from chat import TurnPayload  # noqa: E402  (the stored unit of conversation)
from ngo import DRAC_TOLLFREE, DRAC_WHATSAPP  # noqa: E402

# ---------------------------------------------------------------------------
# Pure helpers (import-safe, unit-assertable without a browser)
# ---------------------------------------------------------------------------

HELPLINE_BANNER_TEXT = (
    "National helplines (always first): DRAC Toll-Free %s | DRAC WhatsApp %s"
    % (DRAC_TOLLFREE, DRAC_WHATSAPP)
)


def helpline_banner_markdown() -> str:
    """Banner text; both DRAC numbers must appear BEFORE any answer text."""
    return (
        "**National helplines:** DRAC Toll-Free `%s` | DRAC WhatsApp `%s`"
        % (DRAC_TOLLFREE, DRAC_WHATSAPP)
    )


WATERMARK_IMAGE_URL = "app/static/watermark.jpg"
# NOTE: this MUST stay a # comment -- a bare string literal here would be
# rendered as visible text by Streamlit's magic (bug seen 2026-09-08).

WATERMARK_ATTRIBUTION = (
    "Background photo: Onwuka Glory, Wikimedia Commons (CC BY 4.0)"
)


def accessibility_css(high_contrast: bool = False, font_size: int = 18) -> str:
    """Layout/typography/watermark CSS only — colors live in config.toml.

    Pure: returns the string; run() injects it via st.markdown. The text-size
    slider drives the root px value and every component sizes in rem off that
    root, so scaling behaves identically in light and dark mode. The
    high-contrast toggle is an overlay marker (.drlca-hc-on) + :has scope that
    composes ON TOP of either theme via !important (see composition note in
    the overlay block below).
    """
    size = max(14, min(int(font_size), 28))
    base = (
        "<style>\n"
        "/* DRLCA Phase 05: colors owned by .streamlit/config.toml -- this\n"
        "   block is spacing, type, watermark and responsive only, so it\n"
        "   stays correct in both light and dark mode. */\n"
        ".block-container { max-width: 46rem; margin-left: auto;\n"
        "  margin-right: auto; padding-top: 2rem; padding-bottom: 3rem; }\n"
        "html { font-size: %dpx; }\n"
        "[class*='stApp'] { font-size: 1rem; }\n"
        ".drlca-answer { font-size: 1rem; line-height: 1.7;\n"
        "  margin: 0.75rem 0; padding: 0.75rem 1rem; border-radius: 8px; }\n"
        ".drlca-banner { font-size: 1rem; font-weight: 600; line-height: 1.5;\n"
        "  margin: 0.5rem 0 1rem; padding: 0.75rem 1rem 0.75rem 1.25rem;\n"
        "  border-left-width: 4px; border-left-style: solid;\n"
        "  border-radius: 8px; }\n"
        "section h1, section h2, section h3 { margin-top: 1.5rem;\n"
        "  margin-bottom: 0.75rem; line-height: 1.3; }\n"
        "div[data-testid='stButton'] > button { font-weight: 600;\n"
        "  padding: 0.6rem 1.2rem; border-radius: 8px; border-width: 1px; }\n"
        ".drlca-watermark { position: fixed; inset: 0; z-index: 0;\n"
        "  pointer-events: none; background-image: url(\"%s\");\n"
        "  background-size: cover; background-position: center;\n"
        "  background-repeat: no-repeat; opacity: 0.24; }\n"
        "/* z-index 0 (not -1): Streamlit ancestors create stacking contexts\n"
        "   that trap negative-z layers behind opaque fills. Content is lifted\n"
        "   above instead (block-container + sidebar get position/z-index). */\n"
        "[data-testid='stAppViewContainer'] { background: transparent; }\n"
        "/* Structural stacking broadband: the watermark div lives INSIDE\n"
        "   stMainBlockContainer (position:relative, z-index:1), so its z-0 is\n"
        "   local to the MAIN context -- which paints above the sidebar by DOM\n"
        "   order. The sidebar therefore needs z-index:2 to sit above the\n"
        "   full-viewport photo (element-screenshot proof of bleed-through,\n"
        "   2026-09-09). !important: Streamlit's own section rules otherwise\n"
        "   win the cascade. */\n"
        ".block-container { position: relative !important; z-index: 1 !important; }\n"
        "section[data-testid='stSidebar'] {\n"
        "  position: relative !important; z-index: 2 !important; }\n"
        ".drlca-veil { position: fixed; inset: 0; z-index: 0;\n"
        "  pointer-events: none; background:\n"
        "  linear-gradient(rgba(255, 255, 255, 0.10),\n"
        "    rgba(255, 255, 255, 0.10)),\n"
        "  linear-gradient(rgba(0, 0, 0, 0.18), rgba(0, 0, 0, 0.18)); }\n"
        "@media (max-width: 480px) {\n"
        "  .block-container { padding-left: 1rem; padding-right: 1rem; }\n"
        "  div[data-testid='column'] { min-width: 100%%; }\n"
        "  div[data-testid='stButton'] > button { width: 100%%; } }\n"
        "</style>"
        "<div class='drlca-watermark' aria-hidden='true'></div>"
        "<div class='drlca-veil' aria-hidden='true'></div>"
        % (size, WATERMARK_IMAGE_URL)
    )
    if high_contrast:
        base += (
            "\n<style>\n"
            "/* DRLCA high-contrast overlay: composes ON TOP of the light or\n"
            "   dark theme in BOTH modes -- every rule carries !important so\n"
            "   it beats config.toml tokens. Scoped via the .drlca-hc-on\n"
            "   marker rendered alongside (body:has fallback: where :has is\n"
            "   unsupported the base theme simply still applies). */\n"
            "body:has(.drlca-hc-on) [class*='stApp'] {\n"
            "  background-color: #000 !important; color: #fff !important; }\n"
            "body:has(.drlca-hc-on) .drlca-answer,\n"
            "body:has(.drlca-hc-on) .drlca-banner,\n"
            "body:has(.drlca-hc-on) p, body:has(.drlca-hc-on) li,\n"
            "body:has(.drlca-hc-on) span, body:has(.drlca-hc-on) div {\n"
            "  color: #fff !important; font-weight: 600; }\n"
            "body:has(.drlca-hc-on) a {\n"
            "  color: #ffd700 !important; text-decoration: underline; }\n"
            "body:has(.drlca-hc-on) button {\n"
            "  border: 2px solid #fff !important; font-weight: 700;\n"
            "  background-color: #000 !important; color: #fff !important; }\n"
            "/* HC button labels are p/span (already forced white above); the\n"
            "   background was still themed, so light-theme white buttons went\n"
            "   white-on-white (Brave report, 2026-09-09). Same for alert\n"
            "   surfaces, which are translucent by theme. */\n"
            "body:has(.drlca-hc-on) [data-testid='stAlert'] > div:first-child {\n"
            "  background-color: #000 !important; border-color: #fff !important; }\n"
            "/* Scrim sheets (below) would paint light in HC mode -- pin them\n"
            "   black here so the forced palette stays intact. */\n"
            "body:has(.drlca-hc-on) .block-container,\n"
            "body:has(.drlca-hc-on) section[data-testid='stSidebar'],\n"
            "body:has(.drlca-hc-on) .drlca-answer {\n"
            "  background-color: #000 !important; }\n"
            "</style>"
            "<div class='drlca-hc-on' style='display:none;'></div>"
        )
    # DRLCA dark-theme alert solidifier (2026-09-09): Streamlit paints alert
    # surfaces translucent (measured: rgba(255,255,18,0.2) with #ffffc2 text).
    # Over our watermark photo that washes out in the dark theme (white text
    # on olive, screenshot-verified) while light mode is fine. Scoped to
    # body.drlca-dark -- toggled by the client-side theme watch in
    # read_aloud_html() -- so light mode is byte-identical. Colors: opaque
    # blend of the 0.2 amber alert tint over config.toml [theme.dark]
    # secondaryBackgroundColor (#161b22) = #45491f; text #ffffc2 mirrors the
    # dark warning text; pair contrast 9.1:1 (AAA). Border mirrors [theme.dark]
    # borderColor (#30363d). Covers warning/success/info (one stAlert family).
    base += (
        "\n<style>\n"
        "body.drlca-dark [data-testid='stAlert'] > div:first-child {\n"
        "  background-color: #45491f; border-color: #30363d; }\n"
        "body.drlca-dark [data-testid='stAlert'] p,\n"
        "body.drlca-dark [data-testid='stAlert'] li {\n"
        "  color: #ffffc2; }\n"
        "</style>"
    )
    # DRLCA readability scrims (2026-09-09): body text sits on the watermark
    # photo, and bright patches (faces/sky) wash out white dark-theme text and
    # fade light-theme sidebar labels (screenshot-verified in Brave). Content
    # columns get translucent theme-colored backdrops so text contrast holds
    # wherever the photo falls; the photo stays visible at the margins.
    # Values derive from .streamlit/config.toml backgrounds (light #ffffff /
    # sidebar #f6f8fa; dark app #0d1117 / sidebar #010409). Light rules live
    # here (after the HC gate) so the token-only base check still passes.
    # Spec prioritizes accessibility over aesthetics. Font is unchanged
    # (system sans-serif; no downloads allowed) -- contrast, not typeface,
    # was the defect.
    base += (
        "\n<style>\n"
        "/* Sidebar opaque in both modes (same stacking reason as above). */\n"
        "section[data-testid='stSidebar'] {\n"
        "  background-color: #f6f8fa !important; }\n"
        ".block-container { background-color: rgba(255, 255, 255, 0.88);\n"
        "  border-radius: 12px; }\n"
        "/* Excerpt cards fully opaque (config bg tokens): long-form legal\n"
        "   text must never sit on photo texture. */\n"
        ".drlca-answer { background-color: #ffffff; }\n"
        "body.drlca-dark section[data-testid='stSidebar'] {\n"
        "  background-color: #010409 !important; }\n"
        "body.drlca-dark .block-container {\n"
        "  background-color: rgba(13, 17, 23, 0.88); }\n"
        "body.drlca-dark .drlca-answer { background-color: #0d1117; }\n"
        "</style>"
    )
    return base


def resolve_mode(question: str, explicit: str = "auto", route_fn=None) -> dict:
    """Explicit buttons override the router; 'auto' delegates to route_question.

    explicit: 'auto' | 'legal' | 'help'. Returns {mode, routing} where mode is
    the effective route ('legal' | 'help' | 'clarify' | 'greeting'). Pure
    greetings ("hello") greet back instead of hitting a subsystem (2026-09-10)
    and win even over forced legal/help buttons, which carry no content.
    """
    from router import is_greeting
    if is_greeting(question or ""):
        return {"mode": "greeting", "routing": {"primary": "greeting",
                                                "secondary": None,
                                                "greeted": True}}
    if explicit in ("legal", "help"):
        return {"mode": explicit, "routing": {"primary": explicit,
                                              "secondary": None,
                                              "overridden": True}}
    if route_fn is None:
        from router import route_question as route_fn
    routing = route_fn(question or "")
    return {"mode": routing["primary"], "routing": routing}


def answer_legal(question: str, retriever=None, plain: bool = False,
                 use_llm: bool = False, history=None,
                 retrieval_query: str | None = None) -> dict:
    """Thin wrapper over rag.ask so the plain-language flag threads through.

    Offline default: use_llm=False (retrieval excerpts + citation tags, no
    Gemini call). plain=True appends the Phase 02 plain suffix to the prompt
    and is recorded in result['route']['plain'] / ['prompt'].

    `history` and `retrieval_query` (Phase 10 C) pass STRAIGHT THROUGH to
    ask(), which is where both are documented. Nothing is reinterpreted here --
    the UI and the eval harness therefore drive exactly the same contract, and
    omitting both leaves every pre-chat caller byte-identical.
    """
    from rag import ask
    return ask(question, retriever=retriever, plain=plain, use_llm=use_llm,
               history=history, retrieval_query=retrieval_query)


def offline_legal_hits(question: str, retriever, k: int = 3,
                       top_n: int = 6, min_per_doc: int = 1,
                       min_score: float = 0.10,
                       retrieval_query: str | None = None) -> dict:
    """Offline legal display payload: gated excerpts WITH citation tags.

    Never strips citations -- each hit carries cite_tag(doc_id, ref) built by
    Phase 02's own cite_tag(). weak/empty retrieval -> refused with the fixed
    refusal message (+ helplines are rendered by the caller, above this).

    The merge to top_n is select_top(), the same call ask() makes, so the
    offline excerpt path and the LLM path show the same six chunks. A display
    path that sliced differently from ask() would be showing the user a system
    nobody measures.

    `retrieval_query` mirrors ask()'s own parameter of the same name, for the
    same reason and with the same default: chat.contextualise() may hand
    retrieval a merged query while `question` stays what the USER asked. Omit
    it and behaviour is byte-identical to the pre-chat path.
    """
    from retrieve import MIN_SCORE, cite_tag, select_top
    from rag import REFUSAL_MESSAGE
    floor = MIN_SCORE if min_score is None else min_score
    query = retrieval_query if retrieval_query is not None else question
    merged = select_top(retriever.query(query, k=k), top_n,
                        min_per_doc=min_per_doc, floor=floor)
    hits = [h for h in merged if h.score >= floor]
    if not hits:
        return {"refused": True, "answer": REFUSAL_MESSAGE,
                "excerpts": [], "citations": []}
    excerpts = [{"tag": cite_tag(h.doc_id, h.ref), "doc_id": h.doc_id,
                 "ref": h.ref, "score": round(h.score, 4),
                 "text": h.text} for h in hits]
    return {"refused": False, "answer": None, "excerpts": excerpts,
            "citations": [e["tag"] for e in excerpts]}


def help_display(question: str, df=None, k: int = 3, slots=None) -> dict:
    """Offline help payload via router._help_payload (helplines-first, top-k).

    Returns {records, meta, slots, needs_confirmation, confirm_prompt}.
    records[0:2] are the DRAC banner rows; the rest are the TOP-K org rows
    (never top-1-only). When needs_confirmation, the caller must show
    confirm_prompt + badge contacts as 'please confirm this matches your need'.

    `slots` (Phase 10 C) carries chat.merge_help_slots()' accumulated
    {disability, location} so "I'm deaf" ... "anywhere in Kano?" keeps BOTH
    filters. slots=None reproduces the single-turn scan exactly.
    """
    from router import _help_payload
    return _help_payload(question, df=df, k=k, slots=slots)


def build_speech_text(legal: dict | None, help_payload: dict | None,
                      clarify: str = "", greeting: str = "") -> str:
    """Plain-text answer snapshot for the client-side read-aloud button."""
    parts = [HELPLINE_BANNER_TEXT]
    if greeting:
        parts.append("Greeting. " + greeting)
    if clarify:
        parts.append("Clarification needed. " + clarify)
    if legal is not None:
        if legal.get("refused"):
            parts.append(str(legal.get("answer", "")))
        elif legal.get("answer"):
            parts.append(str(legal["answer"]))
        else:
            tags = ", ".join(legal.get("citations", []) or ["no citations yet"])
            parts.append("Legal excerpts retrieved. Citations: %s. "
                         "Open the AI expander for a generated answer." % tags)
    if help_payload is not None:
        names = [r.get("name", "") for r in help_payload.get("records", [])]
        parts.append("Help contacts: " + "; ".join(names))
        if help_payload.get("needs_confirmation"):
            parts.append("Please confirm this matches your need. "
                         + str(help_payload.get("confirm_prompt", "")))
    return "\n".join(parts)


def theme_watch_html() -> str:
    """Client-side theme detector (shared snippet, see run() + read_aloud_html).

    Streamlit exposes no theme hook to CSS and server-side Python never sees
    the user's theme choice, so a same-origin iframe samples the `.stApp`
    background luminance and toggles `body.drlca-dark` on the PARENT document
    (dark #0d1117 -> lum ~0.07; light #ffffff -> 1.0; gate 0.4). Try/catch +
    1s interval: sandbox denial or a missed remount degrades to status quo
    (dark-only overrides stay off), never a crash.
    """
    return (
        "<script>"
        "(function(){"
        "function ready(fn){"
        "if(document.body){fn();}else{"
        "document.addEventListener('DOMContentLoaded',fn);}}"
        "ready(function(){"
        "try{"
        "document.body.style.background='transparent';"
        "var apply=function(){"
        "try{"
        "var app=window.parent.document.querySelector('.stApp');"
        "if(!app)return;"
        "var m=(window.parent.getComputedStyle(app).backgroundColor||'').match(/[\\d.]+/g);"
        "if(!m)return;"
        "var lum=(0.2126*+m[0]+0.7152*+m[1]+0.0722*+m[2])/255;"
        "window.parent.document.body.classList.toggle('drlca-dark',lum<0.4);"
        "}catch(e){}"
        "};"
        "apply();"
        "setInterval(apply,1000);"
        "}catch(e){}"
        "});"
        "})();"
        "</script>"
    )


def read_aloud_html(speech_text: str, button_label: str = "🔊 Read answer aloud") -> str:
    """Few-lines Web Speech API button (client-side synthesis, zero server cost).

    The iframe body is transparent (no white strip on dark app backgrounds);
    the shared theme watch (theme_watch_html) keeps body.drlca-dark correct so
    the dark-only alert override in accessibility_css() applies exactly when
    the user picks the dark theme.
    """
    safe = html.escape(speech_text or "No answer yet.", quote=True)
    return (
        ("<div><button type='button' id='drlca-speak' aria-label='%s'>%s</button>"
         + theme_watch_html() +
         "<script>"
         "document.getElementById('drlca-speak').onclick=function(){"
         "try{var u=new SpeechSynthesisUtterance("
         "document.getElementById('drlca-speech').textContent);"
         "u.lang='en-NG';speechSynthesis.cancel();speechSynthesis.speak(u);}"
         "catch(e){alert('Read-aloud needs a browser with speech synthesis (Chrome/Edge).');}"
         "};"
         "</script>"
         "<div id='drlca-speech' style='display:none;'>%s</div></div>")
        % (html.escape(button_label, quote=True), html.escape(button_label),
           safe)
    )


# ---------------------------------------------------------------------------
# Quota readout (Phase 10 C) -- COUNTS ONLY, never a word of the conversation
# ---------------------------------------------------------------------------
#
# The free tier is 20 calls/day/model and the UI now has a "AI-answer every new
# turn" switch, so a user can spend the day's pool without noticing. A readout
# is the cheapest guard.
#
# What is stored is the whole design: {"YYYY-MM-DD": {"gemini-2.5-flash": 3}} --
# a date, a model name, an integer. No question, no answer, no citation, no
# session id. This population discloses abuse and coercion; a usage log is not
# worth the risk of holding any of it, and a log that holds none cannot leak
# any.
#
# The label is "this instance since restart", never "today". On Render the free
# instance has an EPHEMERAL filesystem and sleeps after 15 minutes idle, so the
# file is routinely empty at boot even when quota was spent an hour ago. The
# date key is structure, not a claim about completeness.

QUOTA_LOG_PATH = Path(__file__).resolve().parent / "scripts" / ".quota_log.json"


def quota_log_record(model: str, path=None) -> None:
    """Count one COMPLETED LLM call. Fails open, exactly like rag._cache_write.

    Called only where a model actually answered -- a log entry is evidence that
    quota was spent, so writing one for a failed call would make the readout
    lie in the direction that matters (over-reporting spend is annoying;
    under-reporting it strands a user mid-conversation).
    """
    p = QUOTA_LOG_PATH if path is None else Path(path)
    try:
        import datetime as _dt
        import json as _json
        data = {}
        if p.exists():
            try:
                data = _json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                data = {}  # corrupt file: start over rather than fail the call
        day = _dt.date.today().isoformat()
        bucket = data.setdefault(day, {})
        bucket[model] = int(bucket.get(model, 0)) + 1
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(_json.dumps(data, indent=1), encoding="utf-8")
        tmp.replace(p)  # atomic-ish: never leaves a half-written file
    except Exception:
        pass  # a log we cannot write is still a working assistant


def quota_log_counts(path=None) -> dict:
    """{model: calls} for the current date key, or {} if there is no log yet."""
    p = QUOTA_LOG_PATH if path is None else Path(path)
    try:
        import datetime as _dt
        import json as _json
        data = _json.loads(p.read_text(encoding="utf-8"))
        return dict(data.get(_dt.date.today().isoformat(), {}))
    except Exception:
        return {}  # missing/corrupt/unreadable: report nothing, never raise


# ---------------------------------------------------------------------------
# Cached resources (the performance trap: never rebuild per keystroke)
# ---------------------------------------------------------------------------

def _st():
    import streamlit as st
    return st


def _load_retriever_uncached():
    from rag import PerDocRetriever, build_corpus
    return PerDocRetriever(build_corpus())


def _load_ngo_df_uncached():
    from pathlib import Path as _P
    import sys as _sys
    _sys.path.insert(0, str(_P(__file__).resolve().parent / "src"))
    from ngo import load_ngo
    return load_ngo(str(Path(__file__).resolve().parent / "data" / "ngo.csv"))


def load_retriever():
    """Phase 02 retriever, cached for the session (st.cache_resource).

    The decorator lives on a module-level loader (stable across reruns);
    the inner-function pattern would re-register every rerun and cache
    only by source-hash luck (review 2026-09-08).
    """
    st = _st()
    cached = st.cache_resource(show_spinner="Loading legal index (one-time)…")(
        _load_retriever_uncached
    )
    return cached()


def load_ngo_df():
    """Verified NGO frame, cached for the session (st.cache_resource)."""
    st = _st()
    cached = st.cache_resource(show_spinner="Loading NGO directory (one-time)…")(
        _load_ngo_df_uncached
    )
    return cached()


# ---------------------------------------------------------------------------
# Streamlit UI (only runs under `streamlit run app.py`)
# ---------------------------------------------------------------------------

def _switch_label(primary: str) -> str:
    return "help" if primary == "legal" else "legal"


def render_helpline_banner():
    # Single markdown call: banner hook + content together. A lone
    # st.markdown("</div>") leaks a visible "(" via the sanitizer
    # (bug seen 2026-09-08), so the wrapper is never split across calls.
    # Markdown syntax is NOT processed inside a block-HTML div, so the
    # **bold**/backticks of helpline_banner_markdown() are converted here.
    st = _st()
    html = helpline_banner_markdown().replace("**", "@@B@@")
    parts = html.split("@@B@@")
    html = "".join(p if i % 2 == 0 else "<strong>%s</strong>" % p
                   for i, p in enumerate(parts))
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
    st.markdown("<div class='drlca-banner'>📞 %s</div>" % html,
                unsafe_allow_html=True)


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
# A DISPLAY split and nothing else: retrieval still returns the same six chunks
# ask() sees, and a generated answer may still cite all six. Pool depth is a
# Phase E change and moves in the same commit as the harnesses that measure it.
INLINE_EXCERPTS = 3


def _render_excerpt(e):
    st = _st()
    st.markdown("`%s` (relevance %.3f)" % (e["tag"], e["score"]))
    st.markdown("<div class='drlca-answer'>%s…</div>"
                % html.escape(e["text"][:700]), unsafe_allow_html=True)


def render_excerpts(excerpts, turn_index: int):
    """One turn's excerpt cards: INLINE_EXCERPTS inline, the rest behind one fold.

    Shared by the live path and the replay path so a turn looks the same
    however it got on screen. In a single-turn UI six cards were the page; in a
    conversation they are six cards between the user and their next question.
    """
    st = _st()
    st.markdown("**Retrieved excerpts (offline, citations kept):**")
    for e in excerpts[:INLINE_EXCERPTS]:
        _render_excerpt(e)
    rest = excerpts[INLINE_EXCERPTS:]
    if rest:
        with st.expander("📄 %d more excerpt(s) retrieved for this turn"
                         % len(rest), expanded=False):
            for e in rest:
                _render_excerpt(e)


class _HitRef:
    """(doc_id, ref) duck type for verify_citations / chat.cross_turn_drift.

    Both read only those two attributes. Rebuilding them from the stored
    excerpts keeps a REPLAYED turn checkable without pinning retriever Hit
    objects -- and their full chunk text -- in session state for the whole
    session.
    """

    __slots__ = ("doc_id", "ref")

    def __init__(self, doc_id, ref):
        self.doc_id, self.ref = doc_id, ref


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


def _run_ai_turn(payload, turn_index: int, plain: bool) -> bool:
    """The ONE place an LLM call happens. True when an answer actually landed.

    History reaches the prompt only through chat.history_for_prompt(), which
    trims prior turns to {question, answer}: no excerpts, no tags, no scores.
    Under CHAT_PROMPT_VERSION rule 8 those turns are context, not evidence, and
    the citable set stays this turn's hits alone -- which is exactly what
    verify_citations() and cross_turn_drift() are checked against below.

    A refusal from the strict prompt comes back as REFUSAL_MESSAGE and is
    stored verbatim. Both refusal layers survive; nothing is ever substituted
    for an answer the model declined to give.
    """
    st = _st()
    prior = list((st.session_state.get("turns") or [])[:turn_index])
    try:
        res = answer_legal(payload.question, retriever=load_retriever(),
                           plain=plain, use_llm=True,
                           history=chat.history_for_prompt(prior),
                           retrieval_query=payload.retrieval_query or None)
    except Exception as exc:  # quota/network: explain, never a traceback
        st.warning("⚠️ AI answer unavailable (%s). Your quota may be "
                   "exhausted or the network unreachable. The offline "
                   "excerpts above remain fully usable." % type(exc).__name__)
        return False
    if res.get("answer") is None:
        err = res.get("llm_error", "quota or network error")
        st.warning("⚠️ AI answer unavailable (%s). The offline excerpts above "
                   "remain fully usable." % err)
        return False
    route = res.get("route", {})
    if not route.get("cached"):
        # A cache replay spends no quota, so counting it would over-report.
        quota_log_record(route.get("model_used") or route.get("model") or "?")
    from rag import verify_citations
    hits = [_HitRef(e["doc_id"], e["ref"]) for e in payload.excerpts]
    payload.answer = res["answer"]
    payload.cite_check = verify_citations(res["answer"], hits)
    payload.drift = chat.cross_turn_drift(res["answer"], prior, hits)
    return True


def render_ai_expander(payload, turn_index: int, plain: bool):
    """The opt-in Gemini expander for ONE turn. Collapsed, and OFF by default.

    Shared by render_turn and replay_turn so a live turn and a replayed turn
    are the same pixels. The button key carries the turn index because
    Streamlit keys are page-global and a conversation renders N of these.
    """
    st = _st()
    with st.expander("🤖 Answer with AI (needs internet + quota)", expanded=False):
        st.caption("Optional. Off by default -- the excerpts above are the "
                   "complete offline answer. Generation uses your Gemini quota.")
        if payload.answer:
            st.markdown(payload.answer)
            if payload.cite_check:
                st.caption("Citations: "
                           + ", ".join(c["tag"] for c in payload.cite_check))
        elif st.button("Generate AI answer", key="llm-go-%d" % turn_index):
            if _run_ai_turn(payload, turn_index, plain):
                st.rerun()  # stored once; the replay above renders it from now on


def render_legal(question: str, plain: bool, turn_index: int = 0,
                 retrieval_query=None, prior=None):
    """Compute AND render one turn's legal half. Returns the offline payload."""
    st = _st()
    retriever = load_retriever()
    payload = offline_legal_hits(question, retriever,
                                 retrieval_query=retrieval_query)
    render_plain_caption(plain, prior)
    if payload["refused"]:
        st.warning("🚫 " + str(payload["answer"]))
        return payload
    render_excerpts(payload["excerpts"], turn_index)
    return payload


def render_help_records(payload):
    """Render a help payload -- shared by the live path and the replay path."""
    st = _st()
    records = (payload or {}).get("records", [])
    st.markdown("**Showing %d contact(s) (helplines first, then top-%d "
                "organisations -- never top-1-only):**"
                % (len(records), max(len(records) - 2, 0)))
    if payload.get("needs_confirmation"):
        st.warning("🔍 " + payload.get("confirm_prompt", ""))
    for r in records[2:]:  # org rows; banner rows live in the pinned banner
        badge = (" ⚠️ *please confirm this matches your need*"
                 if payload.get("needs_confirmation") else "")
        st.markdown("**%s**%s" % (r.get("name", "?"), badge))
        st.markdown("- Focus: %s | Location: %s\n- 📞 %s | ✉️ %s\n- %s\n- %s"
                    % (r.get("disability_focus", ""), r.get("location", ""),
                       r.get("phone", ""), r.get("email", ""),
                       r.get("website", ""), r.get("description", "")))


def render_help(question: str, turn_index: int = 0, slots=None):
    """Compute AND render one turn's help half. Returns the replayable payload.

    `slots` is chat.merge_help_slots()' accumulation across the conversation,
    passed as an argument so src/router.py acquires no state of its own.
    """
    df = load_ngo_df()
    payload = help_display(question, df=df, k=3, slots=slots)
    render_help_records(payload)
    return payload


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
    src_entry = str(Path(__file__).resolve().parent / "src")
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
    audio = mic_recorder(start_prompt="🎤 Record question",
                         stop_prompt="⏹ Stop recording",
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
    with st.expander("🎤 Voice input (optional)", expanded=False):
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


def render_turn(question: str, explicit: str, plain: bool, history,
                turn_index: int) -> TurnPayload:
    """Compute AND render one NEW turn. Returns the TurnPayload to store.

    Compute and render are deliberately not split. "Helplines first, always" is
    asserted on the literal adjacency of render_helpline_banner() and the
    routing seam below; separate the two and the project's most load-bearing
    invariant becomes unassertable at the one place it is actually true.

    The body sits at 4-space indent and run() calls it from inside
    `with st.chat_message("assistant")`. A Streamlit context manager applies to
    st.* calls made in nested frames, so every line below lands in the bubble.
    """
    st = _st()
    import streamlit.components.v1 as components

    # Contextualisation FIRST. This turn's RETRIEVAL query may carry prior user
    # turns (chat.contextualise), and help slots accumulate across the whole
    # conversation (chat.merge_help_slots). Both are pure, offline and free,
    # and both were measured headless in Phase B before this UI existed:
    # +0.107 strict recall on chat_dev, +0.130 on chat_test.
    retrieval_query, ctx_meta = chat.contextualise(history, question)
    slots = chat.merge_help_slots(history, question)
    st.session_state["last_q"] = question

    render_helpline_banner()

    # Single routing seam
    resolved = resolve_mode(question, explicit)
    mode, routing = resolved["mode"], resolved["routing"]
    payload = TurnPayload(question=question, retrieval_query=retrieval_query,
                          mode=mode, routing=dict(routing), ctx_meta=ctx_meta,
                          slots=slots)

    legal_view, help_view, clarify_text = None, None, ""
    if mode == "greeting":
        # Pure greeting: friendly panel + guidance, no retrieval/LLM calls.
        render_greeting()
        speech = build_speech_text(None, None, greeting=GREETING_TEXT)
        components.html(read_aloud_html(speech), height=60)
        return payload
    if mode == "clarify":
        clarify_text = routing.get("clarify_question", "")
        render_clarify(clarify_text)
    else:
        secondary = routing.get("secondary")
        wants_legal = mode == "legal" or secondary == "legal"
        wants_help = mode == "help" or secondary == "help"
        if wants_legal:
            st.subheader("⚖️ Your rights (offline excerpts)")
            legal_view = render_legal(question, plain, turn_index,
                                      retrieval_query=retrieval_query,
                                      prior=history)
            payload.excerpts = legal_view["excerpts"]
            payload.refused = bool(legal_view["refused"])
            payload.answer = legal_view["answer"]
            if not payload.refused:
                if st.session_state.get("ai_every_turn"):
                    _run_ai_turn(payload, turn_index, plain)
                render_defects(payload)
                render_ai_expander(payload, turn_index, plain)
        if wants_help:
            st.subheader("🤝 Help near you (offline directory)")
            help_view = render_help(question, turn_index, slots=slots)
            payload.help_payload = help_view
        render_routing_trap(mode)
        render_context_note(payload)

    # --- Read aloud (client-side Web Speech API, zero server cost) ---------
    speech = build_speech_text(legal_view, help_view, clarify_text)
    components.html(read_aloud_html(speech), height=60)
    return payload


def replay_turn(payload, turn_index: int, live: bool = False):
    """Re-render a STORED turn. No retrieval, no router, no network, no LLM.

    Streamlit re-executes the whole script on every interaction -- every
    keystroke, every checkbox, every theme flip. A history loop that re-queried
    each turn would pay N retrievals per rerun, and several times that again
    once the dense arm lands in Phase E. Everything below is read out of the
    TurnPayload, which is why TurnPayload stores what it stores.

    `live` is True only for the newest turn: the routing trap and the clarify
    buttons use page-global fixed keys, and the newest turn is also the only
    one that can safely be re-answered.
    """
    st = _st()
    import streamlit.components.v1 as components
    plain = bool(st.session_state.get("plain"))
    # Reading stored turns, not recomputing any: this is the same slice
    # _run_ai_turn() would pass to chat.history_for_prompt(), so the caption and
    # a regeneration can never disagree about which prompt version applies.
    prior = list((st.session_state.get("turns") or [])[:turn_index])
    render_helpline_banner()

    legal_view, help_view, clarify_text, greeting = None, None, "", ""
    if payload.mode == "greeting":
        render_greeting()
        greeting = GREETING_TEXT
    elif payload.mode == "clarify":
        clarify_text = payload.routing.get("clarify_question", "")
        render_clarify(clarify_text, live=live)
    else:
        secondary = payload.routing.get("secondary")
        # Read off the STORED routing dict -- no router call, no re-decision.
        wants_legal = payload.mode == "legal" or secondary == "legal"
        wants_help = payload.mode == "help" or secondary == "help"
        if wants_legal:
            st.subheader("⚖️ Your rights (offline excerpts)")
            legal_view = {"refused": payload.refused, "answer": payload.answer,
                          "excerpts": payload.excerpts,
                          "citations": payload.tags}
            render_plain_caption(plain, prior)
            if payload.refused:
                st.warning("🚫 " + str(payload.answer or ""))
            else:
                render_excerpts(payload.excerpts, turn_index)
                render_defects(payload)
                render_ai_expander(payload, turn_index, plain)
        if wants_help and payload.help_payload:
            st.subheader("🤝 Help near you (offline directory)")
            help_view = payload.help_payload
            render_help_records(help_view)
        if live:
            render_routing_trap(payload.mode)
        render_context_note(payload)

    speech = build_speech_text(legal_view, help_view, clarify_text, greeting)
    components.html(read_aloud_html(speech), height=60)


def render_history(live_last: bool = True):
    """The conversation so far, oldest first, replayed from session state.

    `live_last=False` while a NEW turn is being rendered below: the newest
    stored turn must not paint its fixed-key controls in the same run as the
    turn that is about to replace it at the end of the thread.
    """
    st = _st()
    turns = st.session_state.get("turns") or []
    if not turns:
        return
    st.markdown("### Conversation so far (%d turn%s)"
                % (len(turns), "" if len(turns) == 1 else "s"))
    last = len(turns) - 1
    for i, stored in enumerate(turns):
        with st.chat_message("user"):
            st.markdown(stored.question)
        with st.chat_message("assistant"):
            replay_turn(stored, i, live=(live_last and i == last))


def run():
    import streamlit as st
    import streamlit.components.v1 as components

    st.set_page_config(page_title="DRLCA — Disability Rights Assistant",
                       layout="centered")

    # Theme watch on EVERY run (including the initial screen, which has no
    # answer yet and therefore no read-aloud iframe). Height 1 (not 0:
    # Streamlit does not mount zero-height iframes) -- a 1px sliver at the
    # very top, invisible in practice.
    components.html(theme_watch_html(), height=1, scrolling=False)

    # The conversation lives HERE and nowhere else: st.session_state, for the
    # life of the browser session. It is never written to disk. This population
    # discloses abuse and coercion, and a file that holds none of it cannot
    # leak any of it.
    for k, v in {"explicit": "auto", "submitted": False, "last_q": "",
                 "turns": [], "pending": "", "ai_every_turn": False}.items():
        st.session_state.setdefault(k, v)

    # --- Sidebar: accessibility controls ----------------------------------
    st.sidebar.header("♿ Accessibility")
    high_contrast = st.sidebar.checkbox("High contrast mode", value=False,
                                        help="Black background, white text, "
                                             "underlined links")
    font_size = st.sidebar.slider("Text size", min_value=14, max_value=28,
                                   value=18, step=1,
                                   help="Scales answer and banner text")
    plain = st.sidebar.checkbox("Explain in plain language", value=False,
                                key="plain",
                                help="Renders AI answers in simple words "
                                     "(same facts, same citations)")
    st.sidebar.caption(WATERMARK_ATTRIBUTION)

    # --- Sidebar: conversation controls ------------------------------------
    st.sidebar.header("💬 Conversation")
    if st.sidebar.button("Clear conversation", key="clear-convo",
                         help="Forget every turn. Nothing was stored on disk."):
        st.session_state["turns"] = []
        st.session_state["pending"] = ""
        st.session_state["explicit"] = "auto"
        st.session_state["submitted"] = False
        st.rerun()
    st.sidebar.markdown("**How should I handle your next question?**")
    if st.sidebar.button("⚖️ Ask about my rights", key="mode-legal",
                         help="Force the legal route (overrides auto-routing)"):
        st.session_state["explicit"] = "legal"
    if st.sidebar.button("🤝 Find help near me", key="mode-help",
                         help="Force the help route (overrides auto-routing)"):
        st.session_state["explicit"] = "help"
    if st.sidebar.button("✨ Auto-route", key="mode-auto",
                         help="Let the router decide (legal / help / clarify)"):
        st.session_state["explicit"] = "auto"
    st.sidebar.caption("Next question: **%s**. An override lasts one turn, "
                       "then resets." % st.session_state["explicit"].upper())

    # --- Sidebar: AI + quota readout ---------------------------------------
    st.sidebar.header("🤖 AI answers")
    st.sidebar.checkbox("AI-answer every new turn", value=False,
                        key="ai_every_turn",
                        help="OFF by default. When off, every turn is answered "
                             "offline from retrieved excerpts and the AI "
                             "expander stays a per-turn opt-in.")
    counts = quota_log_counts()
    st.sidebar.caption(
        "Gemini calls recorded by THIS INSTANCE SINCE RESTART: %s. Free tier "
        "is 20/day/model. On the free host the filesystem is wiped on restart, "
        "so this is a floor, never a day's total."
        % (", ".join("`%s` %d" % (m, n) for m, n in sorted(counts.items()))
           or "none"))

    st.markdown(accessibility_css(high_contrast, font_size),
                unsafe_allow_html=True)

    # --- Helplines pinned at the very top (never below the fold) -----------
    st.title("DRLCA — Disability Rights & Help Finder")
    render_helpline_banner()  # compact single-column banner, no wide columns

    # --- The conversation ---------------------------------------------------
    pending = (st.session_state.pop("pending", "") or "").strip()
    render_history(live_last=not pending)
    if pending:
        history = list(st.session_state["turns"])
        with st.chat_message("user"):
            st.markdown(pending)
        with st.chat_message("assistant"):
            turn = render_turn(pending, st.session_state["explicit"], plain,
                               history, len(history))
        st.session_state["turns"].append(turn)
        st.session_state["explicit"] = "auto"  # an override is per-turn
        st.session_state["submitted"] = True
    elif not st.session_state["turns"]:
        st.caption("Ask your question in the box at the bottom of the page "
                   "(keyboard: Tab to it, Enter to send). No answer yet.")

    # --- Input: optional voice draft, then the chat box ---------------------
    render_voice_draft()
    typed = st.chat_input("Type your question here", key="chat-in")
    if typed and typed.strip():
        # Queue and rerun so the new turn paints in position at the end of the
        # thread rather than below the input Streamlit pins to the viewport.
        st.session_state["pending"] = typed.strip()
        st.rerun()


def _running_under_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner_utils.script_run_context import (
            get_script_run_ctx)
        return get_script_run_ctx() is not None
    except Exception:
        return False


if __name__ == "__main__" or _running_under_streamlit():
    run()
