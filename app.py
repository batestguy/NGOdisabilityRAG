"""Phase 05 accessible Streamlit UI for DRLCA (Disability Rights Legal & Connection Assistant).

Spaces-compatible: no local binaries, secrets only via env (GOOGLE_API_KEY read
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

from ngo import DRAC_TOLLFREE, DRAC_WHATSAPP

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
    the effective route ('legal' | 'help' | 'clarify').
    """
    if explicit in ("legal", "help"):
        return {"mode": explicit, "routing": {"primary": explicit,
                                              "secondary": None,
                                              "overridden": True}}
    if route_fn is None:
        from router import route_question as route_fn
    routing = route_fn(question or "")
    return {"mode": routing["primary"], "routing": routing}


def answer_legal(question: str, retriever=None, plain: bool = False,
                 use_llm: bool = False) -> dict:
    """Thin wrapper over rag.ask so the plain-language flag threads through.

    Offline default: use_llm=False (retrieval excerpts + citation tags, no
    Gemini call). plain=True appends the Phase 02 plain suffix to the prompt
    and is recorded in result['route']['plain'] / ['prompt'].
    """
    from rag import ask
    return ask(question, retriever=retriever, plain=plain, use_llm=use_llm)


def offline_legal_hits(question: str, retriever, k: int = 3,
                       top_n: int = 6, min_score: float = 0.10) -> dict:
    """Offline legal display payload: gated excerpts WITH citation tags.

    Never strips citations -- each hit carries cite_tag(doc_id, ref) built by
    Phase 02's own cite_tag(). weak/empty retrieval -> refused with the fixed
    refusal message (+ helplines are rendered by the caller, above this).
    """
    from retrieve import MIN_SCORE, cite_tag
    from rag import REFUSAL_MESSAGE
    floor = MIN_SCORE if min_score is None else min_score
    merged = retriever.query(question, k=k)[:top_n]
    hits = [h for h in merged if h.score >= floor]
    if not hits:
        return {"refused": True, "answer": REFUSAL_MESSAGE,
                "excerpts": [], "citations": []}
    excerpts = [{"tag": cite_tag(h.doc_id, h.ref), "doc_id": h.doc_id,
                 "ref": h.ref, "score": round(h.score, 4),
                 "text": h.text} for h in hits]
    return {"refused": False, "answer": None, "excerpts": excerpts,
            "citations": [e["tag"] for e in excerpts]}


def help_display(question: str, df=None, k: int = 3) -> dict:
    """Offline help payload via router._help_payload (helplines-first, top-k).

    Returns {records, meta, slots, needs_confirmation, confirm_prompt}.
    records[0:2] are the DRAC banner rows; the rest are the TOP-K org rows
    (never top-1-only). When needs_confirmation, the caller must show
    confirm_prompt + badge contacts as 'please confirm this matches your need'.
    """
    from router import _help_payload
    return _help_payload(question, df=df, k=k)


def build_speech_text(legal: dict | None, help_payload: dict | None,
                      clarify: str = "") -> str:
    """Plain-text answer snapshot for the client-side read-aloud button."""
    parts = [HELPLINE_BANNER_TEXT]
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


def render_routing_trap(mode: str):
    """'I treated this as X [switch to Y]' -- a misroute costs one click."""
    st = _st()
    other = _switch_label(mode)
    st.caption("I treated this as a **%s** question." % mode.upper())
    if st.button("Switch to %s" % other, key="switch-%s" % mode,
                 help="Re-answer the same question via the other route"):
        st.session_state["explicit"] = other
        st.session_state["submitted"] = True
        st.rerun()


def render_clarify(clarify_text: str):
    st = _st()
    st.warning("❓ " + clarify_text)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Legal info about my rights", key="clarify-legal"):
            st.session_state["explicit"] = "legal"
            st.session_state["submitted"] = True
            st.rerun()
    with c2:
        if st.button("Find help near me", key="clarify-help"):
            st.session_state["explicit"] = "help"
            st.session_state["submitted"] = True
            st.rerun()


def render_legal(question: str, plain: bool):
    st = _st()
    retriever = load_retriever()
    payload = offline_legal_hits(question, retriever)
    # Prove the plain flag threads through (Phase 02 toggle reuse, offline).
    probe = answer_legal(question, retriever=retriever, plain=plain,
                         use_llm=False)
    st.caption("Plain-language mode: **%s** (prompt: `%s`)"
               % ("ON" if plain else "OFF",
                  probe.get("route", {}).get("prompt", "?")))
    if payload["refused"]:
        st.warning("🚫 " + str(payload["answer"]))
        return payload
    st.markdown("**Retrieved excerpts (offline, citations kept):**")
    for e in payload["excerpts"]:
        st.markdown("`%s` (relevance %.3f)" % (e["tag"], e["score"]))
        st.markdown("<div class='drlca-answer'>%s…</div>"
                    % html.escape(e["text"][:700]), unsafe_allow_html=True)
    with st.expander("🤖 Answer with AI (needs internet + quota)", expanded=False):
        st.caption("Optional. Off by default -- the excerpts above are the "
                   "complete offline answer. Generation uses your Gemini quota.")
        if st.button("Generate AI answer", key="llm-go"):
            try:
                res = answer_legal(question, retriever=retriever,
                                   plain=plain, use_llm=True)
            except Exception as exc:  # quota/network: explain, never traceback
                st.warning("⚠️ AI answer unavailable (%s). Your quota may be "
                           "exhausted or the network unreachable. The offline "
                           "excerpts above remain fully usable."
                           % type(exc).__name__)
            else:
                if res.get("answer") is None:
                    err = res.get("llm_error", "quota or network error")
                    st.warning("⚠️ AI answer unavailable (%s). The offline "
                               "excerpts above remain fully usable." % err)
                else:
                    st.markdown(res["answer"])
                    if res.get("citations"):
                        st.caption("Citations: " + ", ".join(res["citations"]))
    return payload


def render_help(question: str):
    st = _st()
    df = load_ngo_df()
    payload = help_display(question, df=df, k=3)
    records = payload["records"]
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
    if st.session_state.get("mic_sig") == sig and st.session_state.get("q"):
        return  # already transcribed this clip; don't redo every rerun
    try:
        import io
        import speech_recognition as sr
        rec = sr.Recognizer()
        with sr.AudioFile(io.BytesIO(audio["bytes"])) as src:
                    heard = rec.recognize_google(rec.record(src))
        st.session_state["q"] = heard
        st.session_state["mic_sig"] = sig
        st.success("Heard: “%s” -- review/edit above, then submit." % heard)
    except Exception as exc:
        st.warning("🎤 Could not transcribe that clip (%s). The text box "
                   "above is fully sufficient -- please type your question. "
                   "Mic needs Chrome/Edge + permission + internet."
                   % type(exc).__name__)


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

    for k, v in {"explicit": "auto", "submitted": False,
                 "last_q": ""}.items():
        st.session_state.setdefault(k, v)

    # --- Sidebar: accessibility controls ----------------------------------
    st.sidebar.header("♿ Accessibility")
    high_contrast = st.sidebar.checkbox("High contrast mode", value=False,
                                        help="Black background, white text, "
                                             "underlined links")
    font_size = st.sidebar.slider("Text size", min_value=14, max_value=28,
                                   value=18, step=1,
                                   help="Scales answer and banner text")
    st.sidebar.caption(WATERMARK_ATTRIBUTION)
    st.markdown(accessibility_css(high_contrast, font_size),
                unsafe_allow_html=True)

    # --- Helplines pinned at the very top (never below the fold) -----------
    st.title("DRLCA — Disability Rights & Help Finder")
    render_helpline_banner()  # compact single-column banner, no wide columns

    # --- Input (tab order: input -> mode buttons -> submit -> answer) -------
    st.text_input("Type your question here", key="q",
                  placeholder="e.g. What are my education rights? / "
                              "Find blind support in Lagos",
                  help="Primary input. Voice recording below is optional.")
    try_voice_input()

    st.markdown("**How should I handle your question?**")
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("⚖️ Ask about my rights", key="mode-legal",
                     help="Force the legal route (overrides auto-routing)"):
            st.session_state["explicit"] = "legal"
            st.session_state["submitted"] = True
    with b2:
        if st.button("🤝 Find help near me", key="mode-help",
                     help="Force the help route (overrides auto-routing)"):
            st.session_state["explicit"] = "help"
            st.session_state["submitted"] = True
    with b3:
        if st.button("✨ Auto-route", key="mode-auto",
                     help="Let the router decide (legal / help / clarify)"):
            st.session_state["explicit"] = "auto"
            st.session_state["submitted"] = True

    plain = st.checkbox("Explain in plain language", value=False,
                        help="Re-renders the answer in simple words "
                             "(same facts, same citations)")

    if not st.session_state.get("submitted"):
        st.caption("Press one of the three buttons above (keyboard: Tab to "
                   "the button, Enter to submit). No answer yet.")
        return

    question = (st.session_state.get("q") or "").strip()
    if not question:
        st.warning("Please type a question first (or record one above).")
        return
    explicit = st.session_state.get("explicit", "auto")

    # --- Answer: helplines re-asserted ABOVE every answer -------------------
    st.divider()
    render_helpline_banner()

    if explicit in ("legal", "help"):
        mode, routing = explicit, {"primary": explicit, "secondary": None,
                                   "overridden": True}
    else:
        from router import route_question
        routing = route_question(question)
        mode = routing["primary"]
    st.session_state["last_q"] = question

    legal_payload, help_payload, clarify_text = None, None, ""
    if mode == "clarify":
        clarify_text = routing.get("clarify_question", "")
        render_clarify(clarify_text)
    else:
        secondary = routing.get("secondary")
        wants_legal = mode == "legal" or secondary == "legal"
        wants_help = mode == "help" or secondary == "help"
        if wants_legal:
            st.subheader("⚖️ Your rights (offline excerpts)")
            legal_payload = render_legal(question, plain)
        if wants_help:
            st.subheader("🤝 Help near you (offline directory)")
            help_payload = render_help(question)
        render_routing_trap(mode)

    # --- Read aloud (client-side Web Speech API, zero server cost) ---------
    speech = build_speech_text(legal_payload, help_payload, clarify_text)
    components.html(read_aloud_html(speech), height=60)


def _running_under_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner_utils.script_run_context import (
            get_script_run_ctx)
        return get_script_run_ctx() is not None
    except Exception:
        return False


if __name__ == "__main__" or _running_under_streamlit():
    run()
