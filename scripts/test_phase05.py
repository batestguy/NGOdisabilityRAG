"""Phase 05 script-level asserts (no browser, no LLM, no network).

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\test_phase05.py  (from repo root)
Verifies banner ordering, citation passthrough, clarify, plain-flag
threading, help contract, routing trap, caching, LLM opt-in shape, voice
helpers, and accessibility CSS/labels. Browser checks (keyboard-only run,
360px viewport, NVDA, live mic/read-aloud) remain human-only.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import app  # noqa: E402  (must import without booting UI / calling Gemini)

passed = []


def check(name, cond, extra=""):
    assert cond, "FAIL: %s %s" % (name, extra)
    passed.append(name)
    print("ok - %s %s" % (name, extra))


# 1. Helplines-first ordering ---------------------------------------------
md = app.helpline_banner_markdown()
check("banner-has-tollfree", "08000-3000-100" in md)
check("banner-has-whatsapp", "08000-3000-10" in md)
src = (ROOT / "app.py").read_text(encoding="utf-8")
# H8b (2026-10-22): the shared render helpers moved to src/ui_render.py. Asserts
# about CONTENT that now lives there read ui_src; every PLACEMENT assert (banner
# order inside render_turn/replay_turn/run, 4-space banner call sites) still
# reads app.py, where those functions stayed. NEGATIVE asserts (no writer, no
# st.form, no traceback, no generate) read src + ui_src so the move cannot hide
# a violation in the new module.
ui_src = (ROOT / "src" / "ui_render.py").read_text(encoding="utf-8")
# --- Phase 10 C RESCOPE (2026-09-16) ------------------------------------------
# The five asserts below used to .index() into the WHOLE module. That was only
# ever correct because run() held the entire answer flow. The flow now lives in
# render_turn(), and in file order `def render_helpline_banner` sits AFTER
# `def render_help` -- so a module-wide `i_banner < i_help` would fail on source
# layout alone while the RENDERED order is exactly what it always was. Scoped to
# render_turn()'s body: same property, asserted where it is actually true.
turn_body = src.split("def render_turn")[1].split("\ndef ")[0]
run_body = src.split("def run()")[1].split("\ndef ")[0]
i_banner = turn_body.index("render_helpline_banner()\n\n    # Single routing seam")
i_greet_branch = turn_body.index('if mode == "greeting":')
# was 'render_legal(question, plain)' -- the call gained turn_index/retrieval_query
i_legal = turn_body.index("render_legal(question, plain")
# was 'render_help(question)' -- the call gained turn_index/slots
i_help = turn_body.index("render_help(question")
check("banner-called-before-legal", i_banner < i_legal)
check("banner-called-before-greeting", i_banner < i_greet_branch)
check("seam-routes-all-modes", 'resolved = resolve_mode(question, explicit)' in src)
check("banner-called-before-help", i_banner < i_help)
# was: src.index("render_helpline_banner()") < src.index("st.text_input(") --
# module-wide, so it compared two `def` lines and was very nearly vacuous.
# Scoped to run(), where the claim is real; the single-turn form is gone, so the
# input the banner must precede is now st.chat_input.
check("banner-at-top-of-run",
      run_body.index("render_helpline_banner()") < run_body.index("st.chat_input("))
# Was: `"st.columns" not in src.split("render_helpline_banner")[0][-200:] or True`
# -- the trailing `or True` made it pass unconditionally, so it asserted nothing
# (flagged in review 2026-09-16). Replaced with the property its NAME claims,
# in a form that can fail: every render_helpline_banner() CALL sits at function
# top level (4-space indent) and is never nested inside a `with col:` block,
# which is how a banner ends up squeezed into a narrow column at 360px.
_banner_calls = re.findall(r"^( *)render_helpline_banner\(\)", src, re.M)
check("no-wide-columns-for-banner",
      len(_banner_calls) >= 3 and all(len(i) == 4 for i in _banner_calls),
      str([len(i) for i in _banner_calls]))
# banner function body must not use st.columns
banner_body = src.split("def render_helpline_banner")[1].split("def ")[0]
check("banner-single-column", "columns" not in banner_body)

# 2. Citation passthrough (offline, no LLM) --------------------------------
from rag import PerDocRetriever, build_corpus
retr = PerDocRetriever(build_corpus())
pay = app.offline_legal_hits("What are my education rights under the Act?", retr)
check("legal-hits-nonempty", len(pay["excerpts"]) >= 1, str(len(pay["excerpts"])))
tag_re = re.compile(r"\[(Act cl\. [\d,]+|Act general|Constitution s\. [\d,]+|"
                    r"Constitution general|Factsheet [Ss]ection [\d,]+|Factsheet general)\]")
check("legal-tags-valid", all(tag_re.fullmatch(e["tag"]) for e in pay["excerpts"]),
      str([e["tag"] for e in pay["excerpts"]][:6]))
check("legal-citations-mirror-tags", pay["citations"] == [e["tag"] for e in pay["excerpts"]])
ref = app.offline_legal_hits("quantum teleportation zebra unleaded gasoline", retr)
check("legal-refusal", ref["refused"] and "08000-3000-100" in ref["answer"])

# 3. Clarify rendering ------------------------------------------------------
r = app.resolve_mode("where", explicit="auto")
check("clarify-singleton", r["mode"] == "clarify", str(r))
check("clarify-has-question", bool(r["routing"].get("clarify_question")))
check("explicit-overrides-router", app.resolve_mode("where", explicit="legal")["mode"] == "legal")
# H8b: the call stays in app.py (render_turn); the keyed buttons moved to ui_render.
check("clarify-render-fn", "render_clarify" in src and "clarify-legal" in ui_src and "clarify-help" in ui_src)

# 3b. Greeting path (2026-09-10 hello fix: greet, never the refusal wall) ----
g = app.resolve_mode("hello", explicit="auto")
check("greeting-auto", g["mode"] == "greeting", str(g))
check("greeting-beats-explicit",
      app.resolve_mode("hello", explicit="legal")["mode"] == "greeting"
      and app.resolve_mode("hi", explicit="help")["mode"] == "greeting")
check("greeting-content-not-question",
      app.resolve_mode("hello, what are my rights?", explicit="auto")["mode"] == "legal")
# H8b: the def moved to ui_render; app.py still USES GREETING_TEXT (render_turn, replay_turn).
check("greeting-render-fn", "def render_greeting" in ui_src and "GREETING_TEXT" in src)
check("greeting-text-guidance", "citations" in app.GREETING_TEXT and "helplines" in app.GREETING_TEXT)
check("greeting-speech", "greeting" in src and "Greeting. " in src)

# 4. Plain-flag threading (offline) -----------------------------------------
p0 = app.answer_legal("What are my education rights?", retriever=retr, plain=False, use_llm=False)
p1 = app.answer_legal("What are my education rights?", retriever=retr, plain=True, use_llm=False)
check("plain-false-threads", p0["route"]["plain"] is False and not p0["route"]["prompt"].endswith("-plain"))
check("plain-true-threads", p1["route"]["plain"] is True and p1["route"]["prompt"].endswith("-plain"))
check("plain-offline-no-llm", p1["llm_used"] is False and p1["answer"] is None)

# 5. Help contract: top-k + fuzzy confirm ------------------------------------
hp = app.help_display("find blind support in Lagos")
check("help-location-narrowed", len(hp["records"]) == 3, str(len(hp["records"])))  # 2 banner + 1 Lagos org
hp_full = app.help_display("find help near me")
check("help-topk", len(hp_full["records"]) == 5, str(len(hp_full["records"])))  # 2 banner + full top-3
check("help-banner-first", hp["records"][0]["phone"] == "08000-3000-100"
      and hp["records"][1]["phone"] == "08000-3000-10")
check("help-confirm-gated-or-clean", (not hp["needs_confirmation"]) or bool(hp["confirm_prompt"]))
# H8b: the badge is rendered by render_help_records, now in ui_render.
check("help-badge-text-in-src", "please confirm this matches your need" in ui_src)
check("help-confirm-prompt-rendered", 'payload.get("confirm_prompt"' in src or "confirm_prompt" in src)

# 6. Routing trap ------------------------------------------------------------
# H8b: render_routing_trap moved to ui_render (its call sites stay in app.py).
check("routing-trap-text", "I treated this as a" in ui_src and "Switch to" in ui_src)

# 7. cache_resource -----------------------------------------------------------
check("cache-resource-x2", src.count("st.cache_resource") >= 2 or src.count("cache_resource") >= 2,
      str(src.count("cache_resource")))

# 8. LLM path opt-in, default OFF, no traceback -------------------------------
check("llm-expander-collapsed", 'st.expander("🤖 Answer with AI' in src and "expanded=False" in src)
check("llm-default-offline", "use_llm=False" in src)
# H8b: negatives widened to src + ui_src (stricter, never weaker).
check("llm-quota-explained", "quota" in src and "traceback." not in src + ui_src
      and "st.exception" not in src + ui_src)
check("no-top-level-generate", "generate(" not in (src + ui_src).replace("Generate AI answer", ""))

# 9. Voice read-aloud (Web Speech API, client-side) -----------------------------
speech = app.build_speech_text(pay, hp, "")
check("speech-has-helplines", "08000-3000-100" in speech and "08000-3000-10" in speech)
rae = app.read_aloud_html("test answer")
check("readaloud-webspeech", "SpeechSynthesisUtterance" in rae and "speechSynthesis.speak" in rae)
check("readaloud-no-server", "components.html" in src or "components.v1" in src)
mr = app._import_mic_recorder()
check("mic-recorder-imports", mr is not None)
if mr is not None:
    import chunk as _ck
    check("mic-import-keeps-repo-chunk",
          hasattr(_ck, "constitution_aware_split") or hasattr(_ck, "recursive_split"),
          str(getattr(_ck, "__file__", "?")))
# H8b: try_voice_input (the fallback text) moved to ui_render.
check("mic-fallback-text", "fully sufficient" in ui_src and "Chrome/Edge" in ui_src)

# 10. Accessibility + theme architecture ---------------------------------------
css = app.accessibility_css(high_contrast=True, font_size=22)
css_plain = app.accessibility_css(high_contrast=False, font_size=18)
# The two stale hardcoded-color asserts are REPLACED (not deleted) with
# config-based equivalents: colors now owned by .streamlit/config.toml.
toml = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
check("config-primary-light", "#1a7f37" in toml)
check("config-primary-dark", "#3fb950" in toml)
# Forced HC palette + slider-driven scale coverage retained under new names:
check("css-hc-palette", "#000" in css and "#fff" in css and "#ffd700" in css)
check("css-rem-scale", "1rem" in css_plain and "html" in css_plain)
for label in ["Type your question here", "Ask about my rights", "Find help near me",
              "Explain in plain language", "High contrast mode", "Text size"]:
    check("labeled:" + label, label in src)

# 11. Theme config + watermark (no hardcoded color theming in CSS) -------------
import inspect
check("config-exists", (ROOT / ".streamlit" / "config.toml").is_file())
check("config-has-light", "[theme.light]" in toml)
check("config-has-dark", "[theme.dark]" in toml)
check("config-has-light-sidebar", "[theme.light.sidebar]" in toml)
check("config-has-dark-sidebar", "[theme.dark.sidebar]" in toml)
check("config-base-light", 'base = "light"' in toml)
check("config-widget-border", "showWidgetBorder = true" in toml)
check("config-sidebar-border", "showSidebarBorder = true" in toml)
# H2 (2026-10-15): #1F2328 -> #0d1117 on purpose; Streamlit's 60% caption tint of
# #1F2328 was 4.24:1 on white (axe color-contrast, fails AA). See config.toml.
check("config-text-light", "#0d1117" in toml and "#1F2328" not in toml)
check("config-text-dark", "#e6edf3" in toml)
check("config-no-remote-fonts", "fonts.googleapis" not in toml
      and "fonts.google.com" not in toml)
# accessibility_css body: hex colors allowed ONLY after the HC overlay gate.
fn_src = inspect.getsource(app.accessibility_css)
gate = fn_src.index("\n    if high_contrast")
hex_re = re.compile(r"#[0-9a-fA-F]{3,8}\b")
check("css-no-hardcoded-colors", not hex_re.search(fn_src[:gate]),
      str(hex_re.findall(fn_src[:gate])[:5]))
check("css-hc-palette-in-fn", all(h in fn_src[gate:]
                                  for h in ("#000", "#fff", "#ffd700")))
check("css-watermark-url", app.WATERMARK_IMAGE_URL in css_plain
      and "app/static/watermark.jpg" in css_plain)
check("css-watermark-file", (ROOT / "static" / "watermark.jpg").is_file())
check("css-watermark-div", "drlca-watermark" in css_plain
      and "opacity: 0.24" in css_plain)
check("css-veil", "drlca-veil" in css_plain and "linear-gradient" in css_plain)
check("css-no-img-tag", "<img" not in css_plain)
check("css-max-width", "46rem" in css_plain)
check("css-mobile", "480px" in css_plain and "width: 100%" in css_plain)
check("css-banner-accent", "drlca-banner" in css_plain
      and "border-left-width" in css_plain)
check("attribution-in-src", app.WATERMARK_ATTRIBUTION in src
      and "CC BY 4.0" in src)
check("attribution-in-sidebar", "WATERMARK_ATTRIBUTION" in src
      and "st.sidebar.caption" in src)

# 12. Dark-theme alert solidifier (residual fix 2026-09-09) --------------------
# Streamlit alerts are translucent (rgba(255,255,18,0.2)); over the watermark
# photo the dark-theme text (#ffffc2 on olive) washed out (screenshot).
# Fix: client-side theme watch toggles body.drlca-dark; a dark-only override
# paints alert surfaces opaque. Light mode must stay byte-identical.
check("theme-watch-in-readaloud", "drlca-dark" in rae
      and "setInterval" in rae and "window.parent" in rae)
check("theme-watch-luminance-gate", "lum<0.4" in rae or "lum < 0.4" in rae)
check("theme-watch-guarded", "try{" in rae and "catch(e){}" in rae)
check("readaloud-transparent-body", "background='transparent'" in rae
      or 'background="transparent"' in rae or "background:transparent" in rae)
css_full = app.accessibility_css(high_contrast=False, font_size=18)
check("dark-alert-scope", "body.drlca-dark" in css_full
      and "[data-testid='stAlert']" in css_full)
check("dark-alert-opaque-bg", "#45491f" in css_full)
check("dark-alert-text-pair", "#ffffc2" in css_full)
check("dark-alert-border-token", "#30363d" in css_full)
# The opaque bg is the 0.2-amber-over-#161b22 blend; both inputs documented:
check("dark-alert-token-lineage", "#161b22" in toml and "#30363d" in toml)
# Base CSS (before the HC gate) still carries no literal colors: the dark
# override lives AFTER the gate alongside the HC overlay, like-for-like.
check("css-base-still-token-only", not hex_re.search(fn_src[:gate]),
      str(hex_re.findall(fn_src[:gate])[:5]))
# Veil untouched by this fix (symmetric-safe values from the styling pass):
check("veil-unchanged", "rgba(255, 255, 255, 0.10)" in css_full
      and "rgba(0, 0, 0, 0.18)" in css_full)

# 13. Readability scrims (white-text/sidebar fix 2026-09-09) -------------------
# Bright photo patches washed out dark-theme body text and faded light sidebar
# labels (Brave screenshots). Fix: translucent theme-colored backdrops on the
# content columns; photo stays at the margins. Font deliberately UNCHANGED
# (system sans-serif, no downloads) -- contrast was the defect, not typeface.
# Structural stacking (!important): Streamlit's own section rules otherwise win
# the cascade and the photo paints OVER content backgrounds (element-screenshot
# proof: opaque computed bg yet photo visible). A zero-height top-of-run iframe
# carries the theme watch so body.drlca-dark exists on the initial screen too.
check("scrim-sidebar-light", "section[data-testid='stSidebar']" in css_full
      and "#f6f8fa" in css_full)
check("scrim-main-light", ".block-container" in css_full
      and "rgba(255, 255, 255, 0.88)" in css_full)
check("answer-card-opaque", ".drlca-answer" in css_full
      and ".drlca-answer { background-color: #ffffff; }" in css_full
      and "body.drlca-dark .drlca-answer { background-color: #0d1117; }"
      in css_full)
check("scrim-sidebar-dark", "body.drlca-dark section[data-testid='stSidebar']"
      in css_full and "#010409" in css_full)
check("scrim-main-dark", "body.drlca-dark .block-container" in css_full
      and "rgba(13, 17, 23, 0.88)" in css_full)
check("scrim-token-lineage", "#f6f8fa" in toml and "#010409" in toml
      and "#ffffff" in toml and "#0d1117" in toml)
check("stacking-important", "position: relative !important" in css_plain
      and "z-index: 1 !important" in css_plain)
check("sidebar-above-main-context",
      "section[data-testid='stSidebar']" in css_full
      # H2 (2026-10-15): 2 -> 999991, above Streamlit's header (999990) as well
      # as the main context (1); at 2 the header covered the sidebar close button.
      and "z-index: 999991 !important" in css_full)
check("sidebar-bg-important", "#f6f8fa !important" in css_full
      and "#010409 !important" in css_full)
check("theme-watch-helper", "def theme_watch_html" in src
      and "theme_watch_html()" in src)
check("theme-watch-on-every-run", "components.html(theme_watch_html()" in src
      and "height=1" in src)
# HC overlay must pin the scrims black (else a light sheet + forced-white text):
check("hc-pins-scrims", "body:has(.drlca-hc-on) .block-container" in css
      and "body:has(.drlca-hc-on) section[data-testid='stSidebar']" in css
      and "body:has(.drlca-hc-on) .drlca-answer" in css)
# HC buttons/alerts (Brave report 2026-09-09: light-theme white buttons went
# white-on-white under forced-white text; translucent alerts likewise):
check("hc-button-opaque", "body:has(.drlca-hc-on) button" in css
      and "background-color: #000 !important; color: #fff !important" in css)
check("hc-alert-opaque", "body:has(.drlca-hc-on) [data-testid='stAlert']"
      in css and "border-color: #fff !important" in css)
# Font unchanged by design:
check("font-still-system-sans", 'font = "sans-serif"' in toml
      and "fontFaces" not in toml)
# Base CSS before the HC gate still token-only (scrims live after the gate):
check("css-base-still-token-only-2", not hex_re.search(fn_src[:gate]),
      str(hex_re.findall(fn_src[:gate])[:5]))
# H2 (2026-10-15, geometry pass): behind the open drawer (< 768 px) the page is
# hidden INCLUDING descendants -- Streamlit's markdown wrapper re-declares
# visibility:visible and escaped a parent-only rule (banner + answer stayed
# readable behind the drawer). tools/a11y_audit break-test drawer_descendant_leak.
check("drawer-hides-main-descendants",
      "[aria-expanded='true'])\n    section.stMain *," in css_plain
      and "[aria-expanded='true'])\n    [data-testid='stBottom'] *" in css_plain)
# H2 (2026-10-15, keyboard pass, WCAG 2.4.7): Chrome makes the main scroll
# container a tab stop; it had no focus indicator. currentColor keeps the base
# block colour-free (the token-only check above still holds).
# H2 (2026-10-15, contrast-over-image pass, WCAG 1.4.3): the .block-container
# scrim never reached the photo (the watermark is emitted inside it). The scrim
# rides on each top-level column block instead, skipping the watermark's own
# block; HC pins the same blocks black. tools/a11y_audit --mode=contrast.
check("column-blocks-scrimmed-above-photo",
      "> :not(:has(.drlca-watermark)) { position: relative;\n"
      "  background-color: rgba(255, 255, 255, 0.88); }" in css_full
      and "body.drlca-dark .block-container > [data-testid='stVerticalBlock']"
      in css_full
      and "body:has(.drlca-hc-on) .block-container > [data-testid='stVerticalBlock']"
      in css)
check("scroll-container-focus-visible",
      "[data-testid='stAppScrollToBottomContainer']:focus-visible" in css_plain
      and "outline: 3px solid currentColor !important" in css_plain)

# 14. Phase 10 C: the multi-turn chat UI ---------------------------------------
# src/chat.py was built and measured headless in Phase B (+0.107 strict recall
# on chat_dev, +0.130 on chat_test). These asserts cover the UI contract that
# spends that gain. Still zero LLM, zero network, zero quota.
replay_body = src.split("def replay_turn")[1].split("\ndef ")[0]
hist_body = src.split("def render_history")[1].split("\ndef ")[0]
ai_body = src.split("def render_ai_expander")[1].split("\ndef ")[0]

# The Phase B engine is actually wired, and contextualisation happens BEFORE the
# routing seam (a follow-up's retrieval query is decided before anything else).
check("turn-contextualises-before-seam",
      turn_body.index("chat.contextualise(history, question)") < i_banner
      and turn_body.index("chat.merge_help_slots(history, question)") < i_banner)
check("turn-threads-retrieval-query", "retrieval_query=retrieval_query" in turn_body
      and "slots=slots" in turn_body)
check("ai-turn-uses-history-for-prompt", "chat.history_for_prompt(prior)" in src
      and "chat.cross_turn_drift(" in src)
# H8b: render_defects (the drift warning) moved to ui_render.
check("drift-surfaced-not-absorbed", "Cross-turn citation drift" in ui_src
      and "context, not evidence" in ui_src)

# Replay must NOT recompute. Streamlit reruns the whole script on every
# interaction; a history loop that re-queried each turn would cost N retrievals
# per keystroke, and several times that again once the dense arm lands.
check("replay-no-recompute",
      not any(s in replay_body for s in ("load_retriever", "offline_legal_hits",
                                         "resolve_mode", "help_display",
                                         "route_question")),
      "replay_turn renders from the stored TurnPayload only")
check("replay-reads-stored-routing", "payload.routing.get" in replay_body
      and "payload.excerpts" in replay_body)

# Helplines first on EVERY turn -- live and replayed alike -- and above history.
check("banner-in-render-turn", "render_helpline_banner()" in turn_body)
check("banner-in-replay-turn", "render_helpline_banner()" in replay_body)
check("banner-above-history-in-run",
      run_body.index("render_helpline_banner()") < run_body.index("render_history("))

# Read-aloud is PER TURN (it speaks that turn's own text), not one page-level
# button that would read whichever answer happened to render last.
check("readaloud-per-turn", "read_aloud_html" in turn_body
      and "read_aloud_html" in replay_body and "read_aloud_html" not in run_body)

# Both AI opt-ins default OFF: the per-turn expander and the every-turn switch.
check("ai-expander-collapsed-per-turn",
      'st.expander("🤖 Answer with AI' in ai_body and "expanded=False" in ai_body)
check("ai-button-keyed-per-turn", 'key="llm-go-%d" % turn_index' in ai_body)
check("ai-every-turn-defaults-off", '"ai_every_turn": False' in run_body
      and 'st.sidebar.checkbox("AI-answer every new turn", value=False' in run_body)

# Chat surface: chat_input in, the single-turn form out.
check("chat-input-present", 'st.chat_input("Type your question here"' in src)
check("no-form-widget", "st.form" not in src + ui_src)  # H8b: both modules
check("chat-message-bubbles", 'st.chat_message("user")' in hist_body
      and 'st.chat_message("assistant")' in hist_body)
check("clear-conversation-control",
      'st.sidebar.button("Clear conversation"' in run_body
      and '"turns"] = []' in run_body)
check("history-uses-turnpayload", "from chat import TurnPayload" in src
      and "TurnPayload(question=question" in turn_body
      and 'st.session_state["turns"].append(turn)' in run_body)

# --- PRIVACY: the conversation reaches no file --------------------------------
# History lives in st.session_state for the life of the browser session and
# nowhere else. This population discloses abuse and coercion; a log that holds
# none of it cannot leak any of it.
import json as _json  # noqa: E402
import tempfile as _tf  # noqa: E402
from datetime import date as _date  # noqa: E402

from chat import TurnPayload as _TP  # noqa: E402

_sentinel = "SENTINEL-my-husband-locked-me-in-do-not-persist"
_qlog = Path(_tf.mkdtemp()) / ".quota_log.json"


class _FakeSt:
    """Stand-in for streamlit carrying a conversation full of sentinel text."""

    session_state = {"turns": [_TP(question=_sentinel, answer=_sentinel)],
                     "last_q": _sentinel}


# H8b: two modules now look streamlit up (app._st, ui_render._st); fake both, so
# ANY streamlit access during the quota write still sees only sentinel text.
import ui_render as _ui  # noqa: E402
_orig_st, _orig_ui_st = app._st, _ui._st
app._st = _ui._st = lambda: _FakeSt()
try:
    app.quota_log_record("gemini-2.5-flash", path=_qlog)
    app.quota_log_record("gemini-2.5-flash", path=_qlog)
finally:
    app._st, _ui._st = _orig_st, _orig_ui_st
_blob = _qlog.read_text(encoding="utf-8")
check("quota-log-holds-no-conversation", _sentinel not in _blob, _blob.strip())
check("quota-log-counts-only",
      _json.loads(_blob) == {_date.today().isoformat(): {"gemini-2.5-flash": 2}},
      _blob.strip())
# Fails open like rag._cache_write: a log we cannot write is still a working
# assistant. (Path under a FILE, so mkdir cannot succeed on any platform.)
_bad = Path(__file__) / "nested" / "x.json"
check("quota-log-fails-open",
      app.quota_log_record("gemini-2.5-flash", path=_bad) is None
      and app.quota_log_counts(path=_bad) == {})
# The ONLY writer in app.py is quota_log_record, and its body never sees turns.
_qbody = src.split("def quota_log_record")[1].split("\ndef ")[0]
# H8b: also scans ui_render, so the split cannot open a second writer unseen.
check("only-writer-is-quota-log",
      not re.search(r"write_text\(|json\.dump|to_csv\(|to_json\(|pickle\.",
                    src.replace(_qbody, "") + ui_src))
check("quota-log-never-sees-turns",
      "turns" not in _qbody and "session_state" not in _qbody)
check("history-is-session-state-only", 'st.session_state["turns"]' in src)
check("quota-readout-labelled-honestly", "THIS INSTANCE SINCE RESTART" in src
      and "quota_log_counts()" in run_body)

# --- Plumbing byte-identity ----------------------------------------------------
# Every new parameter is defaulted, and omitting it must change nothing. This is
# what lets test_phase03/04 and every Phase 08-10 eval number stand unmoved.
import router as _router  # noqa: E402

_q = "What are my education rights under the Act?"
check("help-payload-slots-none-identical",
      _router._help_payload("find blind support in Lagos", df=None, k=3)
      == _router._help_payload("find blind support in Lagos", df=None, k=3,
                               slots=None))
_hp_c = app.help_display("and their phone number?",
                         slots={"disability": "blind", "location": "lagos"})
check("help-payload-slots-honoured",
      _hp_c["slots"] == {"disability": "blind", "location": "lagos"}
      and len(_hp_c["records"]) == 3, str(len(_hp_c["records"])))
check("retrieval-query-default-identical",
      app.offline_legal_hits(_q, retr)
      == app.offline_legal_hits(_q, retr, retrieval_query=_q))
check("retrieval-query-separates-query-from-question",
      app.offline_legal_hits(_q, retr, retrieval_query="employment dismissal")
      != app.offline_legal_hits(_q, retr))
check("turnpayload-new-fields-defaulted",
      _TP(question="x").drift == [] and _TP(question="x").help_payload == {})
# The prompt-version caption must EVALUATE ask()'s condition, not approximate
# it with `turn_index > 0` (review 2026-09-16). history_for_prompt() applies
# CARRY_WINDOW and drops blank turns, so a turn can have predecessors and still
# render a single-turn prompt.
import rag as _rag  # noqa: E402

check("prompt-id-reads-rag-constants",
      app._prompt_id(False, False) == _rag.PROMPT_VERSION
      and app._prompt_id(True, True) == _rag.CHAT_PROMPT_VERSION + "-plain")
check("multi-turn-is-asks-own-condition",
      app._multi_turn(None) is False
      and app._multi_turn([_TP(question="   ")]) is False   # blank -> no history
      and app._multi_turn([_TP(question="what are my rights?")]) is True)
check("plain-caption-takes-prior-not-index",
      "render_plain_caption(plain, prior)" in src  # call sites stay in app.py
      and "from rag import _render_history" in ui_src)  # H8b: _multi_turn moved

# H1b (2026-10-15): a byte-identical chunk pair ([Constitution s. 4]) used to
# render as two identical cards. Dedupe is display-level, keyed on
# (doc_id, ref, text), keeps the first, and runs BEFORE the inline/fold split.
_e = lambda ref, text, score: {"tag": "[Constitution s. %s]" % ref, "doc_id": "constitution1999",  # noqa: E731
                               "ref": "s. %s" % ref, "text": text, "score": score}
_dup = [_e("4", "Legislative powers.", 0.31), _e("4", "Legislative powers.", 0.31),
        _e("4", "Different text, same ref.", 0.20), _e("13", "Fundamental objectives.", 0.19)]
_dd = app.dedupe_excerpts(_dup)
check("dedupe-drops-byte-identical-pair-keeps-first",
      len(_dd) == 3 and _dd[0] is _dup[0] and _dd[1] is _dup[2] and _dd[2] is _dup[3])
check("dedupe-keeps-same-ref-different-text", any(e["text"].startswith("Different") for e in _dd))
_re_src = inspect.getsource(app.render_excerpts)
check("dedupe-runs-before-inline-fold-split",
      _re_src.index("dedupe_excerpts(excerpts)") < _re_src.index("excerpts[:INLINE_EXCERPTS]"))

# H2 owner pre-run (2026-10-18): mic_recorder defaults to webm, which
# sr.AudioFile cannot read, so every clip since Phase 06 ended in ValueError.
check("mic-recorder-asks-for-wav",
      'format="wav"' in inspect.getsource(app.try_voice_input))
# D1: read-aloud speaks the tags of the cards shown, so the dropped pair is not spoken.
_sp = app.build_speech_text({"refused": False, "answer": None, "excerpts": _dup,
                             "citations": [e["tag"] for e in _dup]}, None)
check("speech-tags-follow-deduped-cards", _sp.count("[Constitution s. 4]") == 2
      and "[Constitution s. 13]" in _sp)
# A2 / 4.1.3: a NEW turn posts a summary to a parent live region; replays never do.
_an = app.build_announcement({"refused": False, "answer": None, "excerpts": _dup}, None)
check("announcement-helplines-and-shown-count",
      _an.startswith("New answer below.") and "08000-3000-100" in _an
      and "3 legal excerpts" in _an)
check("announce-only-from-render-turn", "announce=build_announcement" in turn_body
      and "announce=" not in replay_body
      and "drlcaAnnounce" in app.read_aloud_html("x", announce="y")
      and "drlcaAnnounce(" not in app.read_aloud_html("x").split("drlca-a11y-bridge")[0])
# A7 / B3 / C2 live in the bridge the theme watch installs into the parent.
_bj = app.A11Y_BRIDGE_JS
check("bridge-installed-by-theme-watch", "drlca-a11y-bridge" in app.theme_watch_html()
      and "</script" not in app._js_str(_bj))
check("bridge-live-region", "aria-live', 'polite'" in _bj and "role', 'status'" in _bj)
check("bridge-hides-icon-ligatures", 'stIconMaterial"]:not([aria-hidden])' in _bj
      and "'Close sidebar'" in _bj and "stChatMessageAvatar" in _bj)
check("bridge-drawer-escape-and-tab-loop", "ev.key === 'Escape'" in _bj
      and "ev.key !== 'Tab'" in _bj and "window.innerWidth < 768" in _bj)
check("bridge-mic-denied-note", "micState !== 'denied'" in _bj
      and "Voice input is unavailable" in _bj
      and "NotAllowedError" in _bj and "md.getUserMedia = function" in _bj)
# H2 review: the bridge rides inside read_aloud_html's %-formatted string, so a
# single "%" in it would raise on every read-aloud render.
check("bridge-has-no-percent", "%" not in _bj)
check("js-str-escapes-every-lt", "<" not in app._js_str("<!--<script></script>"))
check("voice-disclosed-before-recording",
      "Google's speech service" in (_tv := inspect.getsource(app.try_voice_input))
      and _tv.index("Google's speech service") < _tv.index("audio = mic_recorder("))

# H3a (2026-10-18): filter/sort re-filters a turn's STORED directory. A replay
# with every lookup patched to raise must still render, filters included.
import ngo as _ngo  # noqa: E402
_dir = _ngo.load_ngo(str(ROOT / "data" / "ngo.csv")).to_dict("records")
_hl = [h["phone"] for h in _ngo.HELPLINES]
_types, _states = _ngo.filter_options(_dir)
check("h3a-options-from-stored-rows", "Hearing" in _types and "Lagos" in _states)
_views = [_ngo.filter_records(_dir, t, s, o) for t in [""] + _types
          for s in [""] + _states for o in ("relevance", "name")]
check("h3a-helplines-lead-every-filtered-view",
      all([r["phone"] for r in v[:2]] == _hl for v in _views), str(len(_views)))
check("h3a-umbrella-and-national-never-filtered-out",
      all(any("JONAPWD" in r["name"] for r in v) for v in _views))
_local = [r for r in _dir if "*" not in _ngo.record_states(r)]
_empty = _ngo.filter_records(_local, "Hearing", "Lagos")
check("h3a-empty-result-is-helplines-only", [r["phone"] for r in _empty] == _hl)
_byname = [r["name"] for r in _ngo.filter_records(_dir, sort="name")[2:]]
check("h3a-sort-by-name", _byname == sorted(_byname, key=str.casefold))
_hear = _ngo.filter_records(_dir, "Hearing")[2:]
check("h3a-specialist-before-umbrella", "Deaf" in _hear[0]["name"], _hear[0]["name"])


def _boom(*a, **k):
    raise AssertionError("replay recomputed a lookup")


_saved = (app.help_display, _ngo.find_ngo_with_meta, _router.route, _router._help_payload)
app.help_display = _ngo.find_ngo_with_meta = _router.route = _router._help_payload = _boom
try:
    app.render_help_records({"records": _ngo.with_helplines(
        _ngo.pd.DataFrame(_dir[:3])).to_dict("records"), "directory": _dir,
        "needs_confirmation": False}, turn_index=7)
    _replay_ok = True
except AssertionError:
    _replay_ok = False
finally:
    app.help_display, _ngo.find_ngo_with_meta, _router.route, _router._help_payload = _saved
check("h3a-replay-filters-without-recompute", _replay_ok)
_rhr = inspect.getsource(app.render_help_records)
check("h3a-render-path-has-no-lookup", "find_ngo" not in _rhr and "help_display" not in _rhr
      and "help_directory" not in _rhr and "route(" not in _rhr)
check("h3a-directory-stored-only-by-live-turn",
      "help_directory(" in inspect.getsource(app.render_help)
      and "help_directory(" not in replay_body)
check("h3a-filter-keys-carry-turn-index", '"ngo-type-%d" % turn_index' in _rhr
      and '"ngo-state-%d" % turn_index' in _rhr and '"ngo-sort-%d" % turn_index' in _rhr)
check("h3a-replay-passes-turn-index",
      "render_help_records(payload.help_payload, turn_index)" in replay_body)
# H3 review (2026-10-18): regressions it found.
_psy = [r["name"] for r in _ngo.filter_records(_dir, "Psychosocial / mental health")[2:]]
check("h3-review-psychosocial-not-developmental",
      all("Mentally Aware" in n or "*" in _ngo.record_types(next(r for r in _dir if r["name"] == n))
          for n in _psy) and any("Mentally Aware" in n for n in _psy), "; ".join(_psy))
check("h3-review-specific-slot-beats-aid",
      _router.extract_help_slots("I have cerebral palsy and need a wheelchair")["disability"]
      == "cerebral palsy"
      and _router.extract_help_slots("my son has autism and is deaf")["disability"] == "autism")
check("h3-review-location-word-boundary",
      _router.extract_help_slots("is a buyout legal")["location"] == ""
      and _router.extract_help_slots("help in Uyo please")["location"] == "uyo")
check("h3-review-sort-alone-keeps-top-k",
      'filter_records(records[2:], sort="name")' in _rhr and "confirm = payload.get" in _rhr)
check("h3-review-controls-after-results",
      _rhr.index("for r in records[2:]") < _rhr.index('st.expander("🔎 Filter or sort'))

# H2/H3 leftover minor items (2026-10-21).
# 1. Read-aloud honours the active NGO filter: render_help_records returns the
#    payload AS DISPLAYED, and the replay speaks that, not the stored payload.
# H8b: app._st() and ui_render._st() return the same streamlit module object, so
# state written here is what the moved render_help_records reads.
_st_mod = app._st()
_full = _ngo.with_helplines(_ngo.pd.DataFrame(_dir[:3])).to_dict("records")
_hp = {"records": _full, "directory": _dir, "needs_confirmation": False}
_shown = app.render_help_records(_hp, turn_index=8)
check("minor-help-returns-displayed-default", _shown["records"] == _full
      and _hp["records"] is _full and _shown is not _hp)
_filter_set = False
try:
    _st_mod.session_state["ngo-state-9"] = "Lagos"
    _filter_set = True
except Exception:  # noqa: BLE001 -- bare mode may not allow session writes
    pass
if _filter_set:
    _shown_f = app.render_help_records(_hp, turn_index=9)
    _want = _ngo.filter_records(_dir, "", "Lagos", "relevance")
    check("minor-help-returns-filtered-records", _shown_f["records"] == _want
          and app.build_speech_text(None, _shown_f).count("; ") == len(_want) - 1)
    del _st_mod.session_state["ngo-state-9"]
check("minor-replay-speaks-displayed-help",
      "help_view = render_help_records(payload.help_payload, turn_index)" in replay_body
      and replay_body.index("help_view = render_help_records")
      < replay_body.index("build_speech_text(legal_view, help_view"))
# 2. The route choice is a native radio group (checked state, arrow keys,
#    stable focus). The earlier buttons-with-"(selected)" remounted on every
#    press and dropped keyboard focus to <body> (reviewer BLOCK, 2026-10-21).
_run_src = inspect.getsource(app.run)
check("minor-route-is-radio",
      [r for r, _, _ in app.ROUTE_BUTTONS] == ["legal", "help", "auto"]
      and "st.sidebar.radio(\"How should I handle your next question?\"" in _run_src
      and "on_change=_route_changed" in _run_src
      and "st.sidebar.button(label" not in _run_src and "(selected)" not in _run_src)
check("minor-route-radio-maps-back",
      all(app._ROUTE_BY_LABEL[app._LABEL_BY_ROUTE[r]] == r for r in ("legal", "help", "auto")))
# 3. A used-up override resets, and the radio is synced from `explicit`,
#    BEFORE the sidebar draws; the turn is answered on the route taken first.
check("minor-override-reset-before-sidebar",
      _run_src.index('turn_route = st.session_state["explicit"]')
      < _run_src.index('st.session_state["explicit"] = "auto"')
      < _run_src.index("st.session_state[ROUTE_KEY] = _LABEL_BY_ROUTE")
      < _run_src.index("st.sidebar.radio(")
      and "render_turn(pending, turn_route," in _run_src
      and _run_src.count('st.session_state["explicit"] = "auto"') == 2)  # + Clear conversation
# 4. Slider name not doubled; skip link + named landmarks (bridge, no "%").
check("minor-bridge-slider-single-name",
      "removeAttribute('aria-labelledby')" in _bj and 'stSlider"] input[type="range"]' in _bj)
check("minor-bridge-skip-link-and-landmarks",
      "Skip to helplines and answers" in _bj and "setAttribute('role', 'main')" in _bj
      and "'Settings'" in _bj and "D.body.insertBefore(a, D.body.firstChild)" in _bj
      and "a.href = '#drlca-main'" in _bj and "m.id = 'drlca-main'" in _bj
      and "'Ask a question'" in _bj and "z-index:2147483647 !important" in _bj
      and "color:#fff !important" in _bj and "outline:3px solid #ffd700 !important" in _bj
      and "sliders(); landmarks();" in _bj and "%" not in _bj)

print("\nALL %d ASSERTS PASSED" % len(passed))
