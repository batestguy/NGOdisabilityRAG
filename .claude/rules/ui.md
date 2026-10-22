---
paths:
  - "app.py"
  - "src/ui_render.py"
  - ".streamlit/**"
  - "static/**"
  - "tools/a11y_audit/**"
  - "docs/accessibility.md"
---

# UI, CSS and accessibility — the silent-damage rules

Moved from root `CLAUDE.md` by H8c (2026-10-22), plus the H2/a11y lessons that were only in
`HANDOFF.md`. Full a11y record: `docs/accessibility.md`.

## CSS / Streamlit gotchas (learned the hard way)

- Brand colors live **only** in `.streamlit/config.toml`. `accessibility_css()` in `app.py` handles
  spacing/typography/watermark/overrides — and dark-mode surfaces, which need the `body.drlca-dark`
  class set by the `theme_watch_html()` iframe (Streamlit exposes no server-side theme hook).
- The watermark divs sit **inside** the block container, so they paint over its scrim; H2 fixed this by
  scrimming each top-level column block. The sidebar sits above the header's z-index (999991 since H2;
  it was 2, which let the header cover its close button at 360 px). Streamlit's own section rules beat
  un-`!important` ones.
- `components.html(..., height=0)` never mounts — use `height=1`. `srcdoc` scripts race `<body>`, so
  wrap them in a DOMContentLoaded-ready guard.
- Restart the Streamlit server after CSS edits; browser reload alone is not enough.
- **Streamlit pin is 1.63.0.** Bumping to 1.66 moves the sidebar's `aria-expanded` to `data-collapsed`:
  migrate every `[aria-expanded]` selector in **both** the H2 CSS and `A11Y_BRIDGE_JS` (`app.py`), and in
  `tools/a11y_audit/audit.mjs`, in its own branch, then re-audit. Never combine it with another change.

## Focus and widgets

- **A widget whose label or `key=` changes remounts and drops keyboard focus.** Prefer native widgets
  (the route choice is a native radio for this reason) and **test focus behaviour** (activeElement
  after Enter/arrow keys) in a browser, not only state. The first 2026-10-21 a11y fix passed 178
  string asserts and broke focus; only a behavioural check caught it.
- `replay_turn()` must never call retrieval, the router or the network; Streamlit reruns the whole
  script on every interaction.
- "Clear conversation" must drop per-turn widget keys (helpful, NGO filters) or a new turn 0 inherits
  the old one's state.

## Audit tooling

- **Never kill NVDA**: a killed NVDA leaves Windows' screen-reader flag on and PowerShell autocomplete
  breaks. Quit it with NVDA+Q → OK. `nvda_probe.mjs` + `oskeys.py` send OS keys to the FOCUSED window
  (`oskeys.py` refuses unless the DRLCA window is focused): never run them while the user is typing
  elsewhere.
- `app.offline_legal_hits()` carries the retrieval budget and must match `ask()` exactly (see
  `.claude/rules/retrieval.md`); do not slice excerpts differently in the display.

- `tools/a11y_audit/audit.mjs` (pinned Playwright + axe, lockfile committed) runs the matrix
  360/768/1280 × light/dark/HC (+ 200% zoom, max text size); `--mode=contrast` measures text over the
  photo, which axe reports only as *incomplete*. Outputs go to `runs\h2_*`.
- Earlier axe baselines used **WCAG tags only**; best-practice findings (`region`, `heading-order`)
  are not regressions against them. Compare like with like.
- Live smokes (`tools/a11y_audit/live_smoke_*.mjs`) must **wait for elements**, never fixed sleeps:
  the free instance paints the turn slowly. A smoke that asks a question writes production
  telemetry; count attempts and record the ids to discount.
- The remaining known axe node is Streamlit-internal (`aria-allowed-attr` on the sidebar section,
  streamlit/streamlit#17126, fixed upstream in 1.66).
