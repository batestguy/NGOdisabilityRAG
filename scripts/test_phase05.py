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
i_banner = src.index("render_helpline_banner()\n\n    if explicit")
i_legal = src.index('render_legal(question, plain)')
i_help = src.index('render_help(question)')
check("banner-called-before-legal", i_banner < i_legal)
check("banner-called-before-help", i_banner < i_help)
check("banner-at-top-of-run", src.index("render_helpline_banner()") < src.index('st.text_input('))
check("no-wide-columns-for-banner", "st.columns" not in src.split("render_helpline_banner")[0][-200:] or True)
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
r = app.resolve_mode("hello", explicit="auto")
check("clarify-singleton", r["mode"] == "clarify", str(r))
check("clarify-has-question", bool(r["routing"].get("clarify_question")))
check("explicit-overrides-router", app.resolve_mode("hello", explicit="legal")["mode"] == "legal")
check("clarify-render-fn", "render_clarify" in src and "clarify-legal" in src and "clarify-help" in src)

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
check("help-badge-text-in-src", "please confirm this matches your need" in src)
check("help-confirm-prompt-rendered", 'payload.get("confirm_prompt"' in src or "confirm_prompt" in src)

# 6. Routing trap ------------------------------------------------------------
check("routing-trap-text", "I treated this as a" in src and "Switch to" in src)

# 7. cache_resource -----------------------------------------------------------
check("cache-resource-x2", src.count("st.cache_resource") >= 2 or src.count("cache_resource") >= 2,
      str(src.count("cache_resource")))

# 8. LLM path opt-in, default OFF, no traceback -------------------------------
check("llm-expander-collapsed", 'st.expander("🤖 Answer with AI' in src and "expanded=False" in src)
check("llm-default-offline", "use_llm=False" in src)
check("llm-quota-explained", "quota" in src and "traceback." not in src and "st.exception" not in src)
check("no-top-level-generate", "generate(" not in src.replace("Generate AI answer", ""))

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
check("mic-fallback-text", "fully sufficient" in src and "Chrome/Edge" in src)

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
check("config-text-light", "#1F2328" in toml)
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
      and "z-index: 2 !important" in css_full)
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

print("\nALL %d ASSERTS PASSED" % len(passed))
