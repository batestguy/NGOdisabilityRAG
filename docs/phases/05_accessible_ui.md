# Phase 05 — Accessible Streamlit UI

## Goal
A simple interface the people it serves can actually use: screen-reader compatible,
voice input/output, keyboard navigable, high contrast + font scaling. Accessibility is
mandatory per spec, not polish. `streamlit 1.63` is already in `drlca-rag`.

## Entry criteria
- Phase 02 RAG function + Phase 03 lookup + Phase 04 router all callable.
- Helpline banner contract from Phase 03 (test it again at UI level).

## Steps
1. **Skeleton**: one text box + two explicit buttons ("Ask about my rights", "Find help near me")
   plus automatic routing underneath. Explicit buttons matter: they make the router's decision
   visible and overridable (see trap).
2. **Helplines pinned**: DRAC Toll-Free `08000-3000-100` + WhatsApp `08000-3000-10` rendered
   above every answer, every time. Sidebar or header — never below the fold.
3. **Accessibility pass**: semantic HTML via Streamlit primitives, every control labelled;
   high-contrast theme + font-size control in the sidebar; full keyboard path
   (tab order: input → mode buttons → submit → answer); test with NVDA if available,
   else at minimum a screen-reader-safe linear layout (no information in color alone).
4. **Voice**: input via browser speech recognition (Streamlit component or
   `streamlit-mic-recorder`, free); output via a "read aloud" button (Web Speech API
   client-side — no server cost). Degrade gracefully when the browser denies mic access.
5. **Plain-language toggle**: checkbox that re-renders the last answer simplified
   (reuse the Phase 02 toggle, don't rebuild it).

## Exit criteria
- [ ] Keyboard-only run completes ask → answer → referral with zero mouse.
- [ ] Helplines visible without scrolling on a 360px-wide viewport.
- [ ] Voice input and read-aloud work in Chrome/Edge; failure states are explanatory text, not silence.
- [ ] Legal answers in the UI still show their citations (no cite-stripping in templates).

## Record results in
`LEARNING_JOURNAL.md` → accessibility checklist results, components evaluated and rejected,
NVDA test notes if performed.

## Status (2026-09-08 — DONE, reviewer ship-with-notes + fixes applied; dark-alert residual FIXED 2026-09-09)
- app.py built + live-verified (legal/help flows, routing trap, citations, helplines; 360px banner OK).
  scripts/test_phase05.py 80/80 (was 44→69→80); boot HTTP 200; no src/ regressions.
- 2026-09-09 residual fix: dark-theme stAlert text (#ffffc2 on rgba-yellow 0.2 over photo)
  washed out → client-side theme watch (luminance gate) + dark-only opaque override
  (#45491f, 9.1:1 AAA, tokens mirrored from config [theme.dark]); light verified
  byte-identical (translucent amber + dark text, bodyDark=false). Details: journal.
- app.py built + live-verified (legal/help flows, routing trap, citations, helplines; 360px banner OK).
  scripts/test_phase05.py 44/44; boot HTTP 200; no src/ regressions.
- Exit criteria: [x] keyboard path exists (tab order in markup; physical run = human check) ·
  [x] helplines without scroll at 360px (screenshot) · [~] voice works (code + fallback verified;
  live mic/read-aloud = human check) · [x] citations shown in UI.
- Human checklist before deploy: NVDA, keyboard-only run, live mic/denial states, Spaces cold-start.

## Traps
- Never auto-route silently in the UI: show "I treated this as a legal question [switch to help]"
  so a misroute costs one click, not a dead end.
- Streamlit reruns the script on every interaction — cache the retriever/LLM client with
  `st.cache_resource` or every keystroke pays a reload.
- This app must stay deployable on Hugging Face Spaces free tier: no local binaries
  (Tesseract), no GPU deps, secrets via Spaces Secrets, never hardcoded.
