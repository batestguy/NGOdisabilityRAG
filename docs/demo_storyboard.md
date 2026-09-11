# DRLCA — demo storyboard (Phase 08, M5)

Five frames captured from the **live deployment** at
<https://ngodisabilityrag.onrender.com>, driven through Chrome DevTools.
Frames live in `docs/demo/`. The owner does the frames-to-GIF encode and the
README embed — this file is the shot list and the captions.

## Capture conditions (so the frames can be reproduced or re-shot)

| | |
|---|---|
| Date | 2026-09-11 |
| Source | live Render deployment, **not** a local `streamlit run` |
| Commit live at capture time | **`db3a1fc`** — see the honesty note below |
| Viewport | 1283 x 587 CSS px at devicePixelRatio 1.5 |
| Frame size | **1925 x 881 px**, uniform across all five |
| Accessibility defaults | high contrast OFF, text size 18 (frames 01–04); frame 05 varies these deliberately |

### Honesty note — what these frames do and do not show

`main` was at `db3a1fc` when these were captured, which is the **M0 baseline**.
So the live app here is running **pre-Phase-08 retrieval**: no synonym map (M1),
no ref-based citation check (M2), no answer cache (M4).

What the frames *do* show is the **UX contract** — helplines-first, citation
tags, offline-by-default, routing, accessibility controls — and none of M1–M4
changes any of that. What they *do not* show is the improved retrieval. Q5-style
vocabulary-mismatch questions would still miss in these frames.

Re-shooting after the M6 merge is optional and would change ranking/scores, not
layout. If re-shot, update the commit hash above rather than leaving it stale.

## Frame order

### 01 — `01_landing_helplines_banner.png`
**Caption:** Helplines before anything else.

Landing state, nothing typed. The DRAC Toll-Free `08000-3000-100` and DRAC
WhatsApp `08000-3000-10` banner sits directly under the title, before the input.
This is the project's first invariant: **helplines render above every answer and
lead every NGO result**, so a user in distress never has to parse a legal answer
to reach a human. The placeholder shows both supported intents
("What are my education rights?" / "Find blind support in Lagos").

### 02 — `02_legal_query_citation_tags.png`
**Caption:** Every legal claim carries a citation tag — and it works offline.

Question: *"Are public buildings required to be accessible?"*, submitted with
**⚖️ Ask about my rights**. Shows, top to bottom: the helplines banner repeated
above the answer · `Plain-language mode: OFF (prompt: cite-strict-v2)` ·
`Retrieved excerpts (offline, citations kept):` · the tag **`[Act cl. 6,7]`
(relevance 0.281)** followed by its verbatim chunk text (the five-year transitory
period for modifying inaccessible public buildings).

Two things worth pointing at in the GIF caption: the excerpt is **quoted, not
paraphrased**, and this whole result is produced with **zero network calls** —
Gemini generation sits behind an opt-in expander further down that defaults OFF.

*Full tag set for this query (below the fold): `[Act cl. 6,7]`,
`[Constitution s. 4]`, `[Act cl. 3,4,5]`, `[Factsheet Section 6,7]`,
`[Constitution s. 4]`, `[Factsheet Section 7]` — three documents, three distinct
numbering schemes, never conflated.*

### 03 — `03_help_query_helplines_first.png`
**Caption:** Verified contacts, helplines first, and it admits when it is guessing.

Question: *"Where can I find help for my deaf child in Abuja?"*, submitted with
**🤝 Find help near me**. Shows `Showing 3 contact(s) (helplines first, then
top-1 organisations — never top-1-only):`, then the approximate-match alert:

> 🔍 Just to confirm — did you mean 'Nigerian National Association of the Deaf
> (NNAD)'? Your words matched our list approximately ('deaf'), so please confirm
> or browse the full top-3 list below rather than relying on the first result
> alone.

Then the NNAD entry, flagged *⚠️ please confirm this matches your need*, with a
real phone, email and site. The calibrated-uncertainty language is the point:
the connector never presents a fuzzy match as a confident one, and never returns
top-1 only.

### 04 — `04_greeting_path.png`
**Caption:** "hello" gets a greeting, not a wall of refusal.

Question typed: **`hello`**. Button pressed: **⚖️ Ask about my rights** —
deliberately the *wrong* one. The app still returns the greeting, because
`run()` routes through `resolve_mode()` so `is_greeting()` wins over a forced
button (fix `dd5aeb1`). Without it, "hello" hit the legal path, scored under
`MIN_SCORE`, and answered a first-time user with a refusal.

*Framing note:* the input box holding `hello` sits just above the visible area —
the typed text and the full greeting cannot both clear Streamlit's sticky header
in one 587px viewport. Frame 05 shows the same `hello` still in the box. The
greeting reply and all three routing buttons are visible here.

### 05 — `05_accessibility_high_contrast_text_scale.png`
**Caption:** Accessibility is a requirement, not a polish pass.

Both sidebar controls exercised at once: **High contrast mode ON** (dark
surfaces, green-checked box) and **Text size 28** (the max; body font computes to
`28px`). Everything reflows — the question box, the `hello` still in it, the
helplines number, the captions — with no clipping and no horizontal scroll.

Worth noting in the caption: this is a real user control, not a screenshot
filter, and it sits beside keyboard-navigable routing, a linear screen-reader-safe
layout, voice input and read-aloud.

## Encoding notes for the owner

- Frames are uniform **1925 x 881**. If the encoder wants an even width,
  crop one pixel rather than rescaling, so the text stays sharp:
  `ffmpeg -i %02d*.png -vf "crop=1924:880:0:0" ...`
- Suggested dwell: ~2.5s on 01 and 04, ~4s on 02, 03 and 05 (more text to read).
- Order is 01 → 05 as numbered; it walks banner → legal → help → greeting →
  accessibility, which mirrors how the README describes the app.
- Not captured, and owner-gated by design: NVDA screen-reader pass, physical
  keyboard pass, live mic capture and read-aloud audio. Those need a human at a
  real machine and are tracked in `STATUS.md` / `HANDOFF.md`.
