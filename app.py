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
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import chat  # noqa: E402  (contextualise / merge_help_slots / drift -- offline, free)
from chat import TurnPayload  # noqa: E402  (the stored unit of conversation)
import telemetry  # noqa: E402  (H7: counts-only stdout lines; no network, no file)
from ngo import DRAC_TOLLFREE, N_HELPLINES  # noqa: E402
# Interface-language switcher (owner 2026-10-25): chrome only, never the law.
from ui_i18n import (  # noqa: E402
    LANG_CODES, LANG_KEY, LANG_LABEL, LANG_NAMES, UI_TRANSLATION_CAVEAT, T,
    current_lang)
# H8b (2026-10-22): the shared render helpers live in src/ui_render.py. Every
# moved name is re-exported here so `app.<name>` (scripts, test_phase05) and
# inspect.getsource(app.<name>) keep working. ui_render never imports app.
from ui_render import (  # noqa: E402,F401
    GREETING_TEXT, HELPFUL_PRIVACY_NOTE, INLINE_EXCERPTS, NGO_ANY_STATE,
    NGO_ANY_TYPE, NGO_SORTS, _helpful_changed, _import_mic_recorder,
    _multi_turn, _prompt_id, _render_excerpt, _requeue_last, _switch_label,
    dedupe_excerpts, render_clarify, render_context_note, render_defects,
    render_excerpts, render_greeting, render_help_records, render_helpful,
    render_plain_caption, render_routing_trap, render_voice_draft,
    spoken_status_note, status_note, status_note_index, try_voice_input)

# ---------------------------------------------------------------------------
# Pure helpers (import-safe, unit-assertable without a browser)
# ---------------------------------------------------------------------------

HELPLINE_BANNER_TEXT = (
    "National helpline (always first): DRAC Toll-Free %s" % DRAC_TOLLFREE
)


def helpline_banner_markdown() -> str:
    """Banner text; the DRAC toll-free number must appear BEFORE any answer text."""
    return (
        "**%s** DRAC Toll-Free `%s`" % (T("National helpline:"), DRAC_TOLLFREE)
    )


# H6-S.1 (docs/phases/19_zero_cost_self_review.md): no lawyer has reviewed
# DRLCA, so the page says so -- once, directly AFTER the helpline banner
# (helplines stay first), and again inside the AI expander. Never claim review.
LEGAL_INFO_NOTICE = (
    "This site gives general information from the text of Nigerian law. "
    "It is not legal advice, and no lawyer has checked it yet. For help with "
    "your own situation, call DRAC on the number above."
)

# The same notice in Hausa, Igbo and Yoruba (owner request 2026-10-25). Written
# by the project, NOT checked by a native speaker (that is funded phase F2), and
# labelled so on the page. Each renders with its own `lang` so screen readers
# switch voice. Fixed text only: no answer is ever translated (H5b stays deferred).
LEGAL_INFO_NOTICE_TRANSLATIONS = (
    ("ha", "Hausa",
     "Wannan shafin yana ba da bayanai na gaba ɗaya daga rubutun dokokin "
     "Najeriya. Ba shawarar shari'a ba ce, kuma har yanzu babu wani lauya da "
     "ya duba shi. Don neman taimako game da halin da kuke ciki, ku kira DRAC "
     "a lambar da ke sama."),
    ("ig", "Igbo",
     "Weebụsaịtị a na-enye ozi n'ozuzu site n'ederede iwu Naịjirịa. Ọ bụghị "
     "ndụmọdụ iwu, ọ dịbeghịkwa onye ọka iwu nyochara ya. Maka enyemaka "
     "gbasara ọnọdụ gị, kpọọ DRAC na nọmba dị n'elu."),
    ("yo", "Yorùbá",
     "Ojú-òpó yìí ń pèsè ìmọ̀ gbogbogbò láti inú ọ̀rọ̀ òfin Nàìjíríà. Kì í ṣe "
     "ìmọ̀ràn òfin, kò sì tíì sí agbẹjọ́rò kankan tó ṣàyẹ̀wò rẹ̀. Fún "
     "ìrànlọ́wọ́ nípa ipò tìrẹ, pe DRAC lórí nọ́mbà tó wà lókè."),
)
TRANSLATION_CAVEAT = (
    "Translated by this project and not yet checked by a native speaker. "
    "If a translation and the English differ, follow the English."
)


def legal_info_translations_html() -> str:
    """The translated notices as one HTML block, each paragraph in its own lang."""
    import html as _html
    return "".join(
        '<p lang="%s"><strong>%s:</strong> %s</p>'
        % (code, _html.escape(name), _html.escape(text))
        for code, name, text in LEGAL_INFO_NOTICE_TRANSLATIONS)


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
        "   win the cascade.\n"
        "   H2 (2026-10-15): the value was 2, which also put the OPEN sidebar\n"
        "   below Streamlit's fixed header (z 999990), so at 360 px the header\n"
        "   covered the sidebar's close button (Playwright, live site too).\n"
        "   999991 is above the header and still above the main context (1). */\n"
        ".block-container { position: relative !important; z-index: 1 !important; }\n"
        "section[data-testid='stSidebar'] {\n"
        "  position: relative !important; z-index: 999991 !important; }\n"
        ".drlca-veil { position: fixed; inset: 0; z-index: 0;\n"
        "  pointer-events: none; background:\n"
        "  linear-gradient(rgba(255, 255, 255, 0.10),\n"
        "    rgba(255, 255, 255, 0.10)),\n"
        "  linear-gradient(rgba(0, 0, 0, 0.18), rgba(0, 0, 0, 0.18)); }\n"
        "/* H2 (2026-10-15, WCAG 2.4.7 / 2.4.11). A collapsed sidebar is slid\n"
        "   off-canvas but stayed in the tab order: 13 invisible tab stops before\n"
        "   the main content at 360-768 px. visibility:hidden removes them.\n"
        "   Descendants too: the close button and the 'Help for ...' tooltip\n"
        "   icons set their own visibility and stayed focusable otherwise. */\n"
        "section[data-testid='stSidebar'][aria-expanded='false'],\n"
        "section[data-testid='stSidebar'][aria-expanded='false'] * {\n"
        "  visibility: hidden !important; }\n"
        "/* Below 768 px the OPEN sidebar is a drawer over the page (measured:\n"
        "   overlay at <= 767, side-by-side at >= 768) and Tab walked into the\n"
        "   covered page behind it. The page is already hidden by the drawer,\n"
        "   so hide it properly: out of the tab order and the reading order.\n"
        "   Descendants too (geometry pass, 2026-10-15): Streamlit's markdown\n"
        "   wrapper declares visibility:visible, so the banner and answer text\n"
        "   escaped a parent-only rule and stayed readable behind the drawer. */\n"
        "@media (max-width: 767.98px) {\n"
        "  body:has(section[data-testid='stSidebar'][aria-expanded='true'])\n"
        "    section.stMain,\n"
        "  body:has(section[data-testid='stSidebar'][aria-expanded='true'])\n"
        "    section.stMain *,\n"
        "  body:has(section[data-testid='stSidebar'][aria-expanded='true'])\n"
        "    [data-testid='stBottom'],\n"
        "  body:has(section[data-testid='stSidebar'][aria-expanded='true'])\n"
        "    [data-testid='stBottom'] * { visibility: hidden !important; } }\n"
        "/* Focus scrolling stopped at the scroll container's edge, which runs\n"
        "   UNDER Streamlit's fixed chat bar: a focused control could be 100%%\n"
        "   hidden (the Voice input expander was). scroll-padding is a\n"
        "   RESERVATION, measured not guessed (Playwright, 2026-10-15): the bar\n"
        "   is 8.11rem at 360-1280 px and 11.61rem at 360 px zoomed 200%%\n"
        "   (placeholder wraps), so it covers the tallest case; the header is\n"
        "   68px = 3.78rem. Changes scroll stops only, never layout. */\n"
        "[data-testid='stAppScrollToBottomContainer'], html {\n"
        "  scroll-padding-top: 4rem; scroll-padding-bottom: 11.75rem; }\n"
        "/* H2 (2026-10-15, WCAG 2.4.7). Chrome makes a scrollable region with\n"
        "   no focusable child a tab stop, so Streamlit's main scroll container\n"
        "   takes focus between the header and the first link -- with no visible\n"
        "   indicator (scripted keyboard pass, 360 + 1280 px). Give it one. No\n"
        "   colour literal: the outline takes the text colour of whatever theme\n"
        "   (or high-contrast overlay) is active. */\n"
        "[data-testid='stAppScrollToBottomContainer']:focus-visible {\n"
        "  outline: 3px solid currentColor !important;\n"
        "  outline-offset: -3px !important; }\n"
        "@media (max-width: 480px) {\n"
        "  /* H2 (2026-10-15): at 360 px and the largest text size, avatar column\n"
        "     + message padding + alert icon left ~100 px for text and words broke\n"
        "     mid-word. Stack the avatar ABOVE the message (DOM and reading order\n"
        "     unchanged) and trim the padding. */\n"
        "  [data-testid='stChatMessage'] { flex-direction: column;\n"
        "    padding-left: 0.5rem; padding-right: 0.5rem; }\n"
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
            "body:has(.drlca-hc-on) .drlca-answer,\n"
            "body:has(.drlca-hc-on) .block-container > [data-testid='stVerticalBlock']\n"
            "  > :not(:has(.drlca-watermark)) {\n"
            "  background-color: #000 !important; }\n"
            "/* H2 (2026-10-15): text fields kept the themed #f6f8fa surface while\n"
            "   their text was forced white -- axe measured 1.06:1 on the chat box,\n"
            "   so typed questions were invisible. Pin fields (and the fixed chat\n"
            "   bar around them) to the same black/white pair. */\n"
            "body:has(.drlca-hc-on) textarea,\n"
            "body:has(.drlca-hc-on) input[type='text'],\n"
            "body:has(.drlca-hc-on) [data-testid='stChatInput'],\n"
            "body:has(.drlca-hc-on) [data-testid='stChatInput'] > div,\n"
            "body:has(.drlca-hc-on) [data-testid='stBottom'] > div {\n"
            "  background-color: #000 !important; color: #fff !important;\n"
            "  caret-color: #fff !important; }\n"
            "body:has(.drlca-hc-on) textarea::placeholder,\n"
            "body:has(.drlca-hc-on) input::placeholder {\n"
            "  color: #fff !important; opacity: 1 !important; }\n"
            "body:has(.drlca-hc-on) [data-testid='stChatInput'] {\n"
            "  border: 2px solid #fff !important; }\n"
            "/* Owner report 2026-10-25 (screenshot, Brave). Measured in Playwright:\n"
            "   (1) the 'Help for ...' tooltip kept the themed #f6f8fa surface under\n"
            "   forced-white text -- white on white; (2) the '?' icon SVGs stroke\n"
            "   rgba(13,17,23,0.6) -- dark on black, so the icons vanished; (3) the\n"
            "   expander header kept a themed/translucent surface that can go light.\n"
            "   Pin all three to the black/white pair, in every interaction state. */\n"
            "body:has(.drlca-hc-on) [data-testid='stTooltipContent'],\n"
            "body:has(.drlca-hc-on) [data-baseweb='tooltip'] > div {\n"
            "  background-color: #000 !important; color: #fff !important;\n"
            "  border: 2px solid #fff !important; }\n"
            "body:has(.drlca-hc-on) svg.icon,\n"
            "body:has(.drlca-hc-on) svg.icon * {\n"
            "  stroke: #fff !important; }\n"
            "body:has(.drlca-hc-on) [data-testid='stExpander'] details,\n"
            "body:has(.drlca-hc-on) [data-testid='stExpander'] summary,\n"
            "body:has(.drlca-hc-on) [data-testid='stExpander'] summary:hover,\n"
            "body:has(.drlca-hc-on) [data-testid='stExpander'] summary:focus,\n"
            "body:has(.drlca-hc-on) [data-testid='stExpander'] summary:active {\n"
            "  background-color: #000 !important; color: #fff !important; }\n"
            "body:has(.drlca-hc-on) [data-testid='stExpander'] details {\n"
            "  border: 2px solid #fff !important; }\n"
            "/* Captions (incl. the not-legal-advice notice) sat at opacity 0.6, so\n"
            "   forced white rendered as grey. HC means full strength. */\n"
            "body:has(.drlca-hc-on) [data-testid='stCaptionContainer'] {\n"
            "  opacity: 1 !important; }\n"
            "/* The user's chat bubble kept a themed grey surface under forced white\n"
            "   text (README capture, 2026-10-25); axe could not see it over the photo. */\n"
            "body:has(.drlca-hc-on) [data-testid='stChatMessage'] {\n"
            "  background-color: #000 !important; border: 1px solid #fff !important; }\n"
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
        "/* H2 (2026-10-15): the .block-container scrim above never reached the\n"
        "   photo. The watermark/veil divs are emitted INSIDE .block-container,\n"
        "   which is their stacking context, so they paint over its background.\n"
        "   Pixel-measured over the photo (tools/a11y_audit --mode=contrast):\n"
        "   NGO record links 10th-percentile 2.65:1 and the empty-page caption\n"
        "   3.66:1 median in light, under AA 4.5. So the scrim moves onto each\n"
        "   top-level block of the column: positioned, it joins the photo's\n"
        "   layer AFTER it in tree order, so its background lands above the\n"
        "   photo and below its own text. The block holding the watermark is\n"
        "   skipped (it must not scrim itself). position:relative only, no\n"
        "   z-index: no new stacking context. The photo stays visible in the\n"
        "   margins and the gaps between blocks, where there is no text. */\n"
        ".block-container > [data-testid='stVerticalBlock']\n"
        "  > :not(:has(.drlca-watermark)) { position: relative;\n"
        "  background-color: rgba(255, 255, 255, 0.88); }\n"
        "body.drlca-dark .block-container > [data-testid='stVerticalBlock']\n"
        "  > :not(:has(.drlca-watermark)) {\n"
        "  background-color: rgba(13, 17, 23, 0.88); }\n"
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


def offline_legal_hits(question: str, retriever, k: int = 4,
                       top_n: int | None = None, min_per_doc: int = 1,
                       min_score: float = 0.10,
                       retrieval_query: str | None = None) -> dict:
    """Offline legal display payload: gated excerpts WITH citation tags.

    Never strips citations -- each hit carries cite_tag(doc_id, ref) built by
    Phase 02's own cite_tag(). weak/empty retrieval -> refused with the fixed
    refusal message (+ helplines are rendered by the caller, above this).

    The merge to top_n is select_top(), the same call ask() makes, so the
    offline excerpt path and the LLM path show the same twelve chunks (k=4/doc,
    top_n=12 since Phase E1b, 2026-09-20; was 3/6). A display path that sliced
    differently from ask() would be showing the user a system nobody measures --
    and it would break the user's only way to check an AI citation against a
    visible excerpt. INLINE_EXCERPTS stays 3, so the display is 3 inline + 9
    folded.

    `retrieval_query` mirrors ask()'s own parameter of the same name, for the
    same reason and with the same default: chat.contextualise() may hand
    retrieval a merged query while `question` stays what the USER asked. Omit
    it and behaviour is byte-identical to the pre-chat path.

    H8a.4: `top_n=None` takes rag.default_top_n(retriever), the same default
    ask() takes -- 12 on v1/v2 (unchanged), 16 on v3 -- so the two paths can
    never disagree on the budget. Since H8a.5 (2026-10-23) the shipping corpus
    is v3, so the default ceiling is 16 (still 3 inline, the rest folded).
    """
    from retrieve import MIN_SCORE, cite_tag, select_top
    from rag import REFUSAL_MESSAGE, default_top_n
    if top_n is None:
        top_n = default_top_n(retriever)
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
            # The tags of the cards actually shown: H1's dedupe dropped the
            # byte-identical pair from the cards but not from `citations`, so
            # read-aloud spoke 10 tags against 9 cards (H2 owner pre-run).
            shown_ex = dedupe_excerpts(legal.get("excerpts") or [])
            shown = [e["tag"] for e in shown_ex]
            # H8a.4: a status note is spoken once, where the page shows it --
            # just before its doc's first card (the first such tag here).
            firsts = sorted((i, d) for d, i in status_note_index(shown_ex).items())
            if not firsts:
                tags = ", ".join(shown or legal.get("citations", [])
                                 or ["no citations yet"])
                parts.append("Legal excerpts retrieved. Citations: %s. "
                             "Open the AI expander for a generated answer." % tags)
            else:
                said, cuts = ["Legal excerpts retrieved."], [i for i, _ in firsts]
                bounds = [0] + cuts + [len(shown)]
                for j in range(len(bounds) - 1):
                    seg = shown[bounds[j]:bounds[j + 1]]
                    if j > 0:
                        said.append(spoken_status_note(firsts[j - 1][1]))
                    if seg:
                        said.append("%s: %s." % ("More citations" if bounds[j] else
                                                 "Citations", ", ".join(seg)))
                said.append("Open the AI expander for a generated answer.")
                parts.append(" ".join(said))
    if help_payload is not None:
        names = [r.get("name", "") for r in help_payload.get("records", [])]
        parts.append("Help contacts: " + "; ".join(names))
        if help_payload.get("needs_confirmation"):
            parts.append("Please confirm this matches your need. "
                         + str(help_payload.get("confirm_prompt", "")))
    return "\n".join(parts)


def build_announcement(legal: dict | None, help_payload: dict | None,
                       clarify: str = "", greeting: str = "") -> str:
    """Short live-region summary of a NEW turn (WCAG 4.1.3, H2 owner pre-run).

    NVDA said nothing when a turn arrived: focus stays in the chat box and the
    page had no live region. This is the summary a screen-reader user hears
    without moving; the turn itself, and Read aloud, carry the full text.
    """
    parts = ["New answer below.", HELPLINE_BANNER_TEXT + "."]
    if greeting:
        parts.append("Greeting.")
    if clarify:
        parts.append("One question first: " + clarify)
    if legal is not None:
        if legal.get("refused"):
            parts.append(str(legal.get("answer", "")))
        else:
            n = len(dedupe_excerpts(legal.get("excerpts") or []))
            if n:
                parts.append("%d legal excerpt%s with citations."
                             % (n, "" if n == 1 else "s"))
            if legal.get("answer"):
                parts.append("An AI answer is included.")
    if help_payload is not None:
        n = len(help_payload.get("records", []))
        parts.append("%d help contact%s." % (n, "" if n == 1 else "s"))
    return " ".join(parts)


def _js_str(value) -> str:
    """A JS string literal that is also safe inside an HTML <script>.

    In memory only. JSONEncoder rather than the json module's dump helpers:
    test_phase05's only-writer guard flags those names as possible disk
    writes, and that guard should stay broad.
    """
    # Every "<" as <, not just "</": "<!--" + "<script" would otherwise
    # change how the HTML parser finds the closing tag.
    return json.JSONEncoder().encode(value).replace("<", "\\u003c")


# H2 owner pre-run (2026-10-18): fixes Streamlit's DOM cannot take from Python.
# theme_watch_html() injects this ONCE into the PARENT document as a real
# <script> (so it lives in the page's realm and outlives the iframe that
# carried it). Every part re-applies from a MutationObserver because Streamlit
# re-renders freely. The drawer test reads the sidebar's aria-expanded, the
# same hook as the H2 CSS: the Streamlit 1.66 bump must migrate both.
A11Y_BRIDGE_JS = r"""
(function () {
  var D = document;
  /* A2 / WCAG 4.1.3: one polite region, created at page load so it already
     exists (empty) when the first announcement lands. */
  var live = D.createElement('div');
  live.id = 'drlca-live';
  live.setAttribute('role', 'status');
  live.setAttribute('aria-live', 'polite');
  live.setAttribute('aria-atomic', 'true');
  live.style.cssText = 'position:absolute;width:1px;height:1px;margin:-1px;' +
    'padding:0;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;';
  D.body.appendChild(live);
  window.drlcaAnnounce = function (id, text) {
    if (window.drlcaLastAnnounce === id) return;
    window.drlcaLastAnnounce = id;
    live.textContent = '';
    setTimeout(function () { live.textContent = text; }, 150);
  };

  /* A7 / WCAG 1.1.1: Material icons are ligature TEXT, so NVDA read
     "keyboard_arrow_right", "smart_toy", "face". Hide them; name what they
     were standing in for. */
  var ICON_NAMES = { keyboard_double_arrow_left: 'Close sidebar',
                     keyboard_double_arrow_right: 'Open sidebar' };
  function icons() {
    D.querySelectorAll('[data-testid="stIconMaterial"]:not([aria-hidden])')
      .forEach(function (e) {
        e.setAttribute('aria-hidden', 'true');
        var b = e.closest('button');
        var name = ICON_NAMES[e.textContent.trim()];
        if (b && name && !b.getAttribute('aria-label')) b.setAttribute('aria-label', name);
      });
    D.querySelectorAll('[data-testid^="stChatMessageAvatar"]:not([aria-label])')
      .forEach(function (a) {
        a.setAttribute('role', 'img');
        a.setAttribute('aria-label', /User$/.test(a.getAttribute('data-testid'))
          ? 'You asked' : 'Assistant answered');
      });
  }

  /* C2: a blocked microphone only reached the console. Say it on the page. */
  var micState = null;
  function micNote() {
    var note = D.getElementById('drlca-mic-note');
    var frame = D.querySelector('iframe[title*="mic_recorder"]');
    if (micState !== 'denied' || !frame) { if (note) note.remove(); return; }
    var box = frame.closest('[data-testid="stElementContainer"]') || frame;
    if (note && note.previousElementSibling === box) return;
    if (note) note.remove();
    note = D.createElement('p');
    note.id = 'drlca-mic-note';
    note.setAttribute('role', 'alert');
    note.style.cssText = 'margin:0.25rem 0 0.5rem;font-weight:600;';
    note.textContent = 'Voice input is unavailable: microphone access is ' +
      'blocked for this site. Type your question in the box below, or allow ' +
      'the microphone in your browser’s site settings and reload.';
    box.insertAdjacentElement('afterend', note);
  }
  /* The Permissions API alone misses a dismissed prompt (state stays
     'prompt' while Record fails), so also catch the real rejection inside
     the same-origin mic iframe; re-hooked whenever that frame reloads. */
  function hookMic() {
    var frame = D.querySelector('iframe[title*="mic_recorder"]');
    if (!frame) return;
    if (!frame.drlcaHooked) {
      frame.drlcaHooked = true;
      frame.addEventListener('load', hookMic);
    }
    try {
      var md = frame.contentWindow.navigator.mediaDevices;
      if (!md || md.drlcaWrapped) return;
      var orig = md.getUserMedia.bind(md);
      md.getUserMedia = function (c) {
        return orig(c).catch(function (e) {
          if (e && (e.name === 'NotAllowedError' || e.name === 'SecurityError')) {
            micState = 'denied'; micNote();
          }
          throw e;
        });
      };
      md.drlcaWrapped = true;
    } catch (e) {}
  }
  try {
    navigator.permissions.query({ name: 'microphone' }).then(function (p) {
      micState = p.state; micNote();
      p.onchange = function () { micState = p.state; micNote(); };
    }).catch(function () {});
  } catch (e) {}

  /* WCAG 4.1.2: Streamlit's range input carries aria-label AND an
     aria-labelledby naming itself plus its group (also labelled), so NVDA
     said "Text size Text size". The aria-label alone is the right name. */
  function sliders() {
    D.querySelectorAll('[data-testid="stSlider"] input[type="range"][aria-labelledby]')
      .forEach(function (i) {
        if (i.getAttribute('aria-label')) i.removeAttribute('aria-labelledby');
      });
  }

  /* WCAG 2.4.1 / 1.3.1: the sidebar precedes main in Streamlit's DOM and the
     page had no main landmark, so at desktop width a screen reader met every
     setting before the title. Reordering the DOM would fight React; instead
     name both landmarks and put a skip link first in the page. */
  function landmarks() {
    var s = sidebar();
    if (s && !s.getAttribute('aria-label')) s.setAttribute('aria-label', 'Settings');
    var m = D.querySelector('[data-testid="stMainBlockContainer"]');
    if (m && !m.getAttribute('role')) {
      m.setAttribute('role', 'main');
      m.setAttribute('aria-label', 'Helplines and answers');
      m.id = 'drlca-main';  /* a real in-page target makes this a skip link to axe */
    }
    /* The chat box is pinned in its own container, outside main. */
    var q = D.querySelector('[data-testid="stBottom"]');
    if (q && !q.getAttribute('role')) {
      q.setAttribute('role', 'region');
      q.setAttribute('aria-label', 'Ask a question');
    }
    if (D.getElementById('drlca-skip')) return;
    var a = D.createElement('a');
    a.id = 'drlca-skip';
    a.href = '#drlca-main';
    a.textContent = 'Skip to helplines and answers';
    /* Above Streamlit's header (z-index 999990), and !important so the
       high-contrast link colour (gold) cannot land it on white (WCAG 2.4.7 /
       2.4.11 / 1.4.3). White on black, gold ring: visible in every theme. */
    a.style.cssText = 'position:fixed;left:-10000px;top:0.5rem;' +
      'z-index:2147483647 !important;padding:0.6rem 1rem;font-weight:700;' +
      'background:#000 !important;color:#fff !important;' +
      'outline:3px solid #ffd700 !important;outline-offset:2px;' +
      'text-decoration:underline;';
    a.addEventListener('focus', function () { a.style.left = '0.5rem'; });
    a.addEventListener('blur', function () { a.style.left = '-10000px'; });
    a.addEventListener('click', function (ev) {
      ev.preventDefault();
      var h = D.querySelector('[data-testid="stMainBlockContainer"] h1');
      if (!h) return;
      h.setAttribute('tabindex', '-1');
      h.focus();
      h.scrollIntoView();
    });
    D.body.insertBefore(a, D.body.firstChild);
  }

  var queued = false;
  function sweep() { queued = false; icons(); sliders(); landmarks(); hookMic(); micNote(); }
  new MutationObserver(function () {
    if (!queued) { queued = true; requestAnimationFrame(sweep); }
  }).observe(D.body, { childList: true, subtree: true });
  sweep();

  /* B3 / WCAG 2.1.2 + 2.4.3: below 768 px the open sidebar is a drawer over
     the page. Esc closes it; Tab and Shift+Tab stay inside it. */
  function sidebar() { return D.querySelector('section[data-testid="stSidebar"]'); }
  function drawerOpen() {
    var s = sidebar();
    return !!s && window.innerWidth < 768 && s.getAttribute('aria-expanded') === 'true';
  }
  function tabbable(s) {
    return Array.prototype.filter.call(
      s.querySelectorAll('a[href],button,input,select,textarea,summary,[tabindex]'),
      function (e) {
        return e.tabIndex >= 0 && !e.disabled && e.getClientRects().length &&
          getComputedStyle(e).visibility !== 'hidden';
      });
  }
  D.addEventListener('keydown', function (ev) {
    if (ev.isComposing || !drawerOpen()) return;
    var s = sidebar();
    if (ev.key === 'Escape') {
      var close = s.querySelector('[data-testid="stSidebarCollapseButton"] button,' +
                                  '[data-testid="stSidebarHeader"] button');
      if (!close) return;
      ev.preventDefault();
      close.click();
      setTimeout(function () {
        var open = D.querySelector('[data-testid="stExpandSidebarButton"],' +
                                   '[data-testid="stSidebarCollapsedControl"] button');
        if (open) open.focus();
      }, 400);
      return;
    }
    if (ev.key !== 'Tab') return;
    var f = tabbable(s);
    if (!f.length) return;
    var i = f.indexOf(D.activeElement);
    if (i < 0) { ev.preventDefault(); f[ev.shiftKey ? f.length - 1 : 0].focus(); }
    else if (!ev.shiftKey && i === f.length - 1) { ev.preventDefault(); f[0].focus(); }
    else if (ev.shiftKey && i === 0) { ev.preventDefault(); f[f.length - 1].focus(); }
  }, true);
})();
"""


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
        # H2 (2026-10-15): Streamlit names every component iframe "st.iframe".
        # A frame with no control in it (the standalone 1px theme watch) is
        # taken out of the tab order and the accessibility tree; a frame with
        # one (read-aloud) is named after its button.
        "var f=window.frameElement;"
        "if(f){var c=document.querySelector('button,a,input,textarea,select');"
        "if(c){f.setAttribute('title',c.getAttribute('aria-label')||c.textContent);}"
        "else{f.setAttribute('tabindex','-1');f.setAttribute('aria-hidden','true');"
        "f.setAttribute('title','Theme detector (no content)');}}"
        # H2 owner pre-run: install A11Y_BRIDGE_JS into the parent, once.
        "try{var P=window.parent.document;"
        "if(P.body&&!P.getElementById('drlca-a11y-bridge')){"
        "var s=P.createElement('script');s.id='drlca-a11y-bridge';"
        "s.textContent=" + _js_str(A11Y_BRIDGE_JS) + ";"
        "P.head.appendChild(s);}}catch(e){}"
        "var apply=function(){"
        "try{"
        "var app=window.parent.document.querySelector('.stApp');"
        "if(!app)return;"
        "var m=(window.parent.getComputedStyle(app).backgroundColor||'').match(/[\\d.]+/g);"
        "if(!m)return;"
        "var lum=(0.2126*+m[0]+0.7152*+m[1]+0.0722*+m[2])/255;"
        "window.parent.document.body.classList.toggle('drlca-dark',lum<0.4);"
        # H2: follow the app's Text size slider (the frame has its own root).
        # Language switcher: <html lang> follows the #drlca-lang marker run() writes.
        "var L=window.parent.document.getElementById('drlca-lang');"
        "if(L){window.parent.document.documentElement.lang=L.getAttribute('data-lang')||'en';}"
        "document.documentElement.style.fontSize=window.parent.getComputedStyle("
        "window.parent.document.documentElement).fontSize;"
        "}catch(e){}"
        "};"
        "apply();"
        "setInterval(apply,1000);"
        "}catch(e){}"
        "});"
        "})();"
        "</script>"
    )


def read_aloud_html(speech_text: str, button_label: str = "🔊 Read answer aloud",
                    announce: str = "") -> str:
    """Few-lines Web Speech API button (client-side synthesis, zero server cost).

    The iframe body is transparent (no white strip on dark app backgrounds);
    the shared theme watch (theme_watch_html) keeps body.drlca-dark correct so
    the dark-only alert override in accessibility_css() applies exactly when
    the user picks the dark theme.

    `announce` is passed ONLY by render_turn(), i.e. for the newly computed
    turn: it posts that text to the parent's live region (A11Y_BRIDGE_JS).
    Replayed turns never announce, so a rerun does not repeat old answers.
    """
    safe = html.escape(speech_text or "No answer yet.", quote=True)
    notify = ""
    if announce:
        import uuid
        notify = (
            "<script>(function(){var t=%s,id=%s,n=0;"
            "function go(){try{var w=window.parent;"
            "if(w.drlcaAnnounce){w.drlcaAnnounce(id,t);}"
            "else if(n++<20){setTimeout(go,300);}}catch(e){}}"
            "setTimeout(go,300);})();</script>"
            % (_js_str(announce), _js_str(uuid.uuid4().hex)))
    return notify + (
        ("<div><button type='button' id='drlca-speak' aria-label='%s'"
         " style='font-size:1rem;padding:0.3rem 0.8rem;'>%s</button>"
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


def _run_ai_turn(payload, turn_index: int, plain: bool) -> bool:
    """The ONE place an LLM call happens. True when an answer actually landed.

    History reaches the prompt only through chat.history_for_prompt(), which
    trims prior turns to {question, answer}: no excerpts, no tags, no scores.
    Under CHAT_PROMPT_VERSION rule 9 those turns are context, not evidence, and
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
    from rag import llm_context_hits, verify_citations
    # H8a.5: only the hits ask() put in the prompt (LLM_EXCLUDED_DOCS dropped).
    hits = llm_context_hits(
        [_HitRef(e["doc_id"], e["ref"]) for e in payload.excerpts])
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
        st.caption(LEGAL_INFO_NOTICE)
        # H8a.4 review: say so when the AI cannot see some excerpts above
        # (rag.LLM_EXCLUDED_DOCS, lifted at H8a.6). A caption, not a widget, so
        # no label or key changes and no focus moves. A no-op on corpus v2.
        from rag import LLM_EXCLUDED_DOCS
        if any(e.get("doc_id") in LLM_EXCLUDED_DOCS
               for e in (payload.excerpts or [])):
            st.caption("The AI answer does not yet use the Accessibility "
                       "Regulations excerpts above; read those excerpts "
                       "directly.")
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


def help_directory(df, slots) -> list:
    """The whole directory, ranked for this turn's slots, for H3a filtering.

    Called ONLY by render_help() (a live turn). The result is stored in the
    payload, so a replay re-filters stored rows and never looks anything up.
    Rows the lookup ranked come first, then every other row in CSV order.
    """
    from ngo import N_HELPLINES, SCHEMA, find_ngo_with_meta
    frame, _ = find_ngo_with_meta(df, disability=(slots or {}).get("disability", ""),
                                  location=(slots or {}).get("location", ""),
                                  k=len(df))
    ranked = frame.to_dict("records")[N_HELPLINES:]
    seen = {r["name"] for r in ranked}
    rest = [{c: r[c] for c in SCHEMA} for r in df.to_dict("records")
            if r["name"] not in seen]
    return ranked + rest


# Widget-key prefixes that carry a turn index; "Clear conversation" drops them.
TURN_WIDGET_PREFIXES = ("ngo-", "helpful-")


def emit_turn_signal(payload, share_text: bool = False) -> None:
    """H7: one counts-only line for a NEW turn. Called from run() only, never
    on replay, so a rerun cannot double-count a turn."""
    payload.signal_id = telemetry.new_id()
    shown = dedupe_excerpts(payload.excerpts or [])
    hp = payload.help_payload or {}
    telemetry.emit(telemetry.turn_record(
        payload.signal_id, payload.mode or "", payload.refused,
        max((e.get("score", 0.0) for e in shown), default=None),
        len(shown), max(len(hp.get("records", [])) - N_HELPLINES, 0),
        bool(payload.answer), payload.question, share_text))


def render_help(question: str, turn_index: int = 0, slots=None):
    """Compute AND render one turn's help half. Returns the replayable payload.

    `slots` is chat.merge_help_slots()' accumulation across the conversation,
    passed as an argument so src/router.py acquires no state of its own.
    """
    df = load_ngo_df()
    payload = help_display(question, df=df, k=3, slots=slots)
    payload["directory"] = help_directory(df, payload.get("slots"))
    render_help_records(payload, turn_index)
    return payload


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
        components.html(read_aloud_html(
            speech, announce=build_announcement(None, None, greeting=GREETING_TEXT)),
            height=60)
        return payload
    if mode == "clarify":
        clarify_text = routing.get("clarify_question", "")
        render_clarify(clarify_text)
    else:
        secondary = routing.get("secondary")
        wants_legal = mode == "legal" or secondary == "legal"
        wants_help = mode == "help" or secondary == "help"
        if wants_legal:
            st.subheader(T("⚖️ Your rights (offline excerpts)"))
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
            st.subheader(T("🤝 Help near you (offline directory)"))
            help_view = render_help(question, turn_index, slots=slots)
            payload.help_payload = help_view
        render_routing_trap(mode)
        render_context_note(payload)

    # --- Read aloud (client-side Web Speech API, zero server cost) ---------
    speech = build_speech_text(legal_view, help_view, clarify_text)
    components.html(read_aloud_html(
        speech, announce=build_announcement(legal_view, help_view, clarify_text)),
        height=60)
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
            st.subheader(T("⚖️ Your rights (offline excerpts)"))
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
            st.subheader(T("🤝 Help near you (offline directory)"))
            # Speak the records as DISPLAYED, so an active filter is honoured.
            help_view = render_help_records(payload.help_payload, turn_index)
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
            render_helpful(stored, i)


ROUTE_BUTTONS = (
    ("legal", "⚖️ Ask about my rights", "Force the legal route (overrides auto-routing)"),
    ("help", "🤝 Find help near me", "Force the help route (overrides auto-routing)"),
    ("auto", "✨ Auto-route", "Let the router decide (legal / help / clarify)"),
)


ROUTE_KEY = "route-choice"
_ROUTE_BY_LABEL = {label: route for route, label, _ in ROUTE_BUTTONS}
_LABEL_BY_ROUTE = {route: label for route, label, _ in ROUTE_BUTTONS}


def _route_changed() -> None:
    st = _st()
    st.session_state["explicit"] = _ROUTE_BY_LABEL.get(st.session_state.get(ROUTE_KEY), "auto")


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
    # An override is per-turn. Take this turn's route and reset the NEXT
    # question's to auto BEFORE the sidebar draws, so the route buttons and
    # the "Next question" caption never show a choice that has been used up.
    # Every submit path (chat box, voice Send, routing trap) reruns first.
    turn_route = st.session_state["explicit"]
    if (st.session_state.get("pending") or "").strip():
        st.session_state["explicit"] = "auto"
    # `explicit` is the source of truth (the routing trap and Clear write it,
    # then rerun); the radio is synced from it here, before it is drawn.
    st.session_state[ROUTE_KEY] = _LABEL_BY_ROUTE.get(st.session_state["explicit"],
                                                      _LABEL_BY_ROUTE["auto"])

    # --- Sidebar: interface language (first, so it is found first) --------
    # Stable multilingual label + stable option codes: switching never
    # remounts this radio, so keyboard focus stays on it. Every other control
    # below carries an explicit key= so its translated label keeps its state.
    st.sidebar.radio(LANG_LABEL, list(LANG_CODES), key=LANG_KEY,
                     format_func=LANG_NAMES.get, horizontal=True)
    lang = current_lang()

    # --- Sidebar: accessibility controls ----------------------------------
    st.sidebar.header(T("♿ Accessibility"))
    high_contrast = st.sidebar.checkbox(T("High contrast mode"), value=False,
                                        key="hc",
                                        help="Black background, white text, "
                                             "underlined links")
    font_size = st.sidebar.slider(T("Text size"), min_value=14, max_value=28,
                                   value=18, step=1, key="font-size",
                                   help="Scales answer and banner text")
    plain = st.sidebar.checkbox(T("Explain in plain language"), value=False,
                                key="plain",
                                help="Renders AI answers in simple words "
                                     "(same facts, same citations)")
    st.sidebar.caption(WATERMARK_ATTRIBUTION)

    # --- Sidebar: conversation controls ------------------------------------
    st.sidebar.header(T("💬 Conversation"))
    if st.sidebar.button(T("Clear conversation"), key="clear-convo",
                         help="Forget every turn. Nothing was stored on disk."):
        st.session_state["turns"] = []
        st.session_state["pending"] = ""
        st.session_state["explicit"] = "auto"
        st.session_state["submitted"] = False
        # Per-turn widget keys are indexed by turn number, so a new turn 0
        # would inherit the old turn 0's NGO filter and helpful answer.
        for k in [k for k in st.session_state
                  if str(k).startswith(TURN_WIDGET_PREFIXES)]:
            del st.session_state[k]
        st.rerun()
    # A native radio group: checked state, arrow keys and stable focus for
    # free (WCAG 4.1.2 / 2.4.3). Three buttons whose label changed on select
    # remounted on every press and dropped keyboard focus to <body>.
    st.sidebar.radio(T("How should I handle your next question?"),
                     [label for _, label, _ in ROUTE_BUTTONS], key=ROUTE_KEY,
                     format_func=T,  # values stay English: routing state
                     on_change=_route_changed,
                     help=" · ".join(tip for _, _, tip in ROUTE_BUTTONS))
    st.sidebar.caption("Next question: **%s**. An override lasts one turn, "
                       "then resets." % st.session_state["explicit"].upper())

    # --- Sidebar: AI + quota readout ---------------------------------------
    st.sidebar.header(T("🤖 AI answers"))
    st.sidebar.checkbox(T("AI-answer every new turn"), value=False,
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

    # --- Sidebar: H7 improvement signal (text sharing is a separate opt-in) --
    st.sidebar.header(T("📊 Help improve this service"))
    st.sidebar.checkbox(T("Also share the words of my questions"), value=False,
                        key="share_text",
                        help="OFF by default. When off, only counts are "
                             "recorded (see the note under each answer). When "
                             "on, the text of each NEW question is also "
                             "recorded, never your conversation history.")

    st.markdown(accessibility_css(high_contrast, font_size),
                unsafe_allow_html=True)

    # --- Helplines pinned at the very top (never below the fold) -----------
    st.title("DRLCA — Disability Rights & Help Finder")
    render_helpline_banner()  # compact single-column banner, no wide columns
    st.caption("ℹ️ " + LEGAL_INFO_NOTICE)  # H6-S.1: after the banner, never before
    if lang != "en":
        _name, _text = {c: (n, t) for c, n, t in LEGAL_INFO_NOTICE_TRANSLATIONS}[lang]
        st.markdown('<p lang="%s">ℹ️ %s</p><p lang="%s"><em>%s</em></p>'
                    % (lang, html.escape(_text), lang,
                       html.escape(UI_TRANSLATION_CAVEAT[lang])),
                    unsafe_allow_html=True)
    st.markdown("<div id='drlca-lang' data-lang='%s' style='display:none;'></div>"
                % lang, unsafe_allow_html=True)
    with st.expander("This notice in Hausa, Igbo and Yorùbá", expanded=False):
        st.caption(TRANSLATION_CAVEAT)
        st.markdown(legal_info_translations_html(), unsafe_allow_html=True)

    # --- The conversation ---------------------------------------------------
    pending = (st.session_state.pop("pending", "") or "").strip()
    render_history(live_last=not pending)
    if pending:
        history = list(st.session_state["turns"])
        with st.chat_message("user"):
            st.markdown(pending)
        with st.chat_message("assistant"):
            turn = render_turn(pending, turn_route, plain, history, len(history))
            emit_turn_signal(turn, bool(st.session_state.get("share_text")))
            render_helpful(turn, len(history))
        st.session_state["turns"].append(turn)
        st.session_state["submitted"] = True
    elif not st.session_state["turns"]:
        st.caption(T("Ask your question in the box at the bottom of the page "
                     "(keyboard: Tab to it, Enter to send). No answer yet."))

    # --- Input: optional voice draft, then the chat box ---------------------
    render_voice_draft()
    typed = st.chat_input(T("Type your question here"), key="chat-in")
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
