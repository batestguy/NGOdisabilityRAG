"""Interface-language switcher: English, Hausa, Igbo, Yoruba (owner request 2026-10-25).

Scope, on purpose: the interface chrome only (sidebar headings and control
labels, the banner wording, instructions, answer section headings). The law is
NEVER translated -- excerpts stay in the official English text, citation tags
and helpline numbers stay byte-identical, and no answer is machine-translated
(H5b stays deferred; docs/phases/19_zero_cost_self_review.md).

The translations are the project's own, NOT checked by a native speaker
(funded phase F2), and the page says so whenever a non-English language is on.

Keys are the English strings themselves, so app.py keeps its English literals
in place (its source-text asserts read them) and a missing translation falls
back to English rather than to a blank.

Import-safe: no Streamlit call at import time.
"""

LANG_KEY = "ui-lang"
LANG_CODES = ("en", "ha", "ig", "yo")
LANG_NAMES = {"en": "English", "ha": "Hausa", "ig": "Igbo", "yo": "Yorùbá"}
# Stable, multilingual widget label: it never changes with the language, so
# the selector never remounts and keyboard focus stays on it (.claude/rules/ui.md).
LANG_LABEL = "🌐 Language · Harshe · Asụsụ · Èdè"

STRINGS = {
    "♿ Accessibility": {
        "ha": "♿ Sauƙin amfani",
        "ig": "♿ Ịnweta ohere",
        "yo": "♿ Ìrọ̀rùn ìlò"},
    "High contrast mode": {
        "ha": "Launuka masu bambanci sosai",
        "ig": "Agba dị iche nke ukwuu",
        "yo": "Àwọ̀ tó yàtọ̀ gidigidi"},
    "Text size": {
        "ha": "Girman rubutu",
        "ig": "Nha mkpụrụedemede",
        "yo": "Ìtóbi ọ̀rọ̀"},
    "Explain in plain language": {
        "ha": "Bayyana da harshe mai sauƙi",
        "ig": "Kọwaa n'asụsụ dị mfe",
        "yo": "Ṣàlàyé ní èdè tó rọrùn"},
    "💬 Conversation": {
        "ha": "💬 Tattaunawa",
        "ig": "💬 Mkparịta ụka",
        "yo": "💬 Ìjíròrò"},
    "Clear conversation": {
        "ha": "Share tattaunawa",
        "ig": "Hichapụ mkparịta ụka",
        "yo": "Pa ìjíròrò rẹ́"},
    "How should I handle your next question?": {
        "ha": "Ta yaya zan amsa tambayarku ta gaba?",
        "ig": "Kedu ka m ga-esi zaa ajụjụ gị ọzọ?",
        "yo": "Báwo ni kí n ṣe ìbéèrè rẹ tó kàn?"},
    "⚖️ Ask about my rights": {
        "ha": "⚖️ Tambaya game da haƙƙoƙina",
        "ig": "⚖️ Jụọ maka ikike m",
        "yo": "⚖️ Béèrè nípa ẹ̀tọ́ mi"},
    "🤝 Find help near me": {
        "ha": "🤝 Nemo taimako kusa da ni",
        "ig": "🤝 Chọta enyemaka dị m nso",
        "yo": "🤝 Wá ìrànlọ́wọ́ nítòsí mi"},
    "✨ Auto-route": {
        "ha": "✨ Bari shafin ya zaɓa",
        "ig": "✨ Ka saịtị ahụ họrọ",
        "yo": "✨ Jẹ́ kí ojú-òpó yàn"},
    "🤖 AI answers": {
        "ha": "🤖 Amsoshin AI",
        "ig": "🤖 Azịza AI",
        "yo": "🤖 Ìdáhùn AI"},
    "AI-answer every new turn": {
        "ha": "Amsar AI ga kowace sabuwar tambaya",
        "ig": "Azịza AI maka ajụjụ ọhụrụ ọ bụla",
        "yo": "Ìdáhùn AI fún ìbéèrè tuntun kọ̀ọ̀kan"},
    "📊 Help improve this service": {
        "ha": "📊 Taimaka a inganta wannan sabis",
        "ig": "📊 Nyere aka melite ọrụ a",
        "yo": "📊 Ràn wá lọ́wọ́ láti mú iṣẹ́ yìí dára sí i"},
    "Also share the words of my questions": {
        "ha": "Kuma raba kalmomin tambayoyina",
        "ig": "Kesaakwa okwu dị n'ajụjụ m",
        "yo": "Pín ọ̀rọ̀ inú ìbéèrè mi pẹ̀lú"},
    "National helpline:": {
        "ha": "Layin taimako na ƙasa:",
        "ig": "Nọmba enyemaka mba:",
        "yo": "Nọ́mbà ìrànlọ́wọ́ orílẹ̀-èdè:"},
    "Ask your question in the box at the bottom of the page "
    "(keyboard: Tab to it, Enter to send). No answer yet.": {
        "ha": "Rubuta tambayarku a akwatin da ke ƙasan shafin (madannai: Tab don "
              "zuwa wurin, Enter don aikawa). Har yanzu babu amsa. A yanzu, "
              "tambayoyi da Turanci sun fi aiki.",
        "ig": "Dee ajụjụ gị n'igbe dị n'ala peeji a (kiibọọdụ: Tab iji ruo ya, "
              "Enter iji zipu ya). Enweghị azịza ugbu a. Ugbu a, ajụjụ n'asụsụ "
              "Bekee na-arụ ọrụ kacha mma.",
        "yo": "Kọ ìbéèrè rẹ sínú àpótí tó wà nísàlẹ̀ ojú-ìwé (kọ́kọ́rọ́: Tab láti dé "
              "ibẹ̀, Enter láti fi ránṣẹ́). Kò sí ìdáhùn síbẹ̀. Fún báyìí, ìbéèrè ní "
              "èdè Gẹ̀ẹ́sì ló ń ṣiṣẹ́ jù."},
    "Type your question here": {
        "ha": "Rubuta tambayarku a nan",
        "ig": "Dee ajụjụ gị ebe a",
        "yo": "Kọ ìbéèrè rẹ síbí"},
    "🎤 Voice input (optional)": {
        "ha": "🎤 Shigar da murya (na zaɓi)",
        "ig": "🎤 Ntinye olu (nhọrọ)",
        "yo": "🎤 Ìfọ̀rọ̀sílẹ̀ ohùn (àṣàyàn)"},
    "⚖️ Your rights (offline excerpts)": {
        "ha": "⚖️ Haƙƙoƙinku (ɓangarori daga doka)",
        "ig": "⚖️ Ikike gị (akụkụ sitere n'iwu)",
        "yo": "⚖️ Ẹ̀tọ́ rẹ (àyọkà láti inú òfin)"},
    "🤝 Help near you (offline directory)": {
        "ha": "🤝 Taimako kusa da ku (jerin ƙungiyoyi)",
        "ig": "🤝 Enyemaka dị gị nso (ndepụta otu)",
        "yo": "🤝 Ìrànlọ́wọ́ nítòsí rẹ (àkójọ àwọn àjọ)"},
    "**Retrieved excerpts (offline, citations kept):**": {
        "ha": "**Ɓangarorin doka da aka samo (tare da bayanin tushensu):**",
        "ig": "**Akụkụ iwu achọtara (na ntụaka ha):**",
        "yo": "**Àwọn àyọkà òfin tí a rí (pẹ̀lú ìtọ́kasí wọn):**"},
}

# Shown under the excerpts heading when the interface is not English: the law
# itself is quoted in its official English text, never translated.
LAW_IN_ENGLISH = {
    "ha": "Ana nakalto dokar da rubutunta na Turanci na hukuma.",
    "ig": "E dere iwu ahụ n'asụsụ Bekee gọọmentị ji bipụta ya.",
    "yo": "A fa òfin yọ ní èdè Gẹ̀ẹ́sì tí ìjọba fi tẹ̀ ẹ́ jáde.",
}

# Shown once near the top whenever a non-English interface is on.
UI_TRANSLATION_CAVEAT = {
    "ha": "Wannan fassarar aikin wannan shafin ce, kuma har yanzu wani mai "
          "magana da harshen bai duba ta ba.",
    "ig": "Ọ bụ ndị saịtị a sụgharịrị nke a; onye na-asụ asụsụ ahụ elebabeghị ya "
          "anya.",
    "yo": "Àwa ni a túmọ̀ èyí, ẹni tí èdè náà jẹ́ èdè abínibí rẹ̀ kò tíì yẹ̀ ẹ́ wò.",
}


def current_lang() -> str:
    """The session's interface language; English outside a Streamlit run."""
    try:
        import streamlit as st
        lang = st.session_state.get(LANG_KEY, "en")
    except Exception:
        return "en"
    return lang if lang in LANG_CODES else "en"


def T(text: str, lang: str | None = None) -> str:
    """`text` in the interface language; the English text when none exists."""
    lang = lang or current_lang()
    if lang == "en":
        return text
    return STRINGS.get(text, {}).get(lang, text)
