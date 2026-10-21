# DRLCA accessibility — WCAG 2.2 AA verification (H2)

Step H2 of `docs/phases/16_post_launch_roadmap.md`. Branch `phase11/h2-a11y`, audited 2026-10-15
against Streamlit 1.63.0 in Chromium 151. Zero Gemini quota: the AI expander and the "AI-answer
every new turn" switch stayed OFF for every run.

**Short version.** The agent-side part is done. axe reports **0 serious, 0 moderate and 0 minor**
findings across the matrix, plus **one critical rule on one Streamlit-internal node**
(`aria-allowed-attr` on the sidebar `<section>`). That node cannot be fixed from app code, and
a fix is available upstream in Streamlit 1.66.0, which DRLCA (pinned at 1.63.0) has not taken (justified below). The owner checklist at the end is **not
signed yet**, so the H2 exit gate as a whole is **not met** until the owner signs it.

---

## 1. How it was audited

Tooling is a pinned Playwright script, `tools/a11y_audit/audit.mjs`, with `playwright@1.62.1` and
`@axe-core/playwright@4.13.0` pinned in `package.json` and the lockfile. Lighthouse is
`npx lighthouse@13.4.1`. **This deviates from the playbook**, which suggested clicking through the
chrome-devtools MCP and injecting axe from a CDN. A committed script can be re-run and diffed;
manual clicking cannot.

| Mode | What it does |
|---|---|
| `matrix` | axe with tags `wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa`, iframes included. 11 cells × 3 states (below) = 33 scans. Each state is a fresh browser context, so it is also a fresh Streamlit session. Writes `axe_<cell>_<state>.json` + a screenshot. |
| `contrast` | axe cannot judge text over a background **image** (the watermark photo), so it files those nodes as *incomplete*, not as violations. This mode measures them from pixels: it screenshots the node with its text and without it, keeps only the pixels in the element's text colour (so colour emoji and children's own paint are excluded), and compares the text colour with the background behind the glyphs. The verdict is the 2nd percentile ≥ 4.5:1 (3:1 for large text). |
| `keyboard` | Tabs from the top of the page until focus cycles. For every stop it records the accessible name, role, whether a visible focus indicator exists (computed outline / box-shadow / border / background of the element and 4 ancestors, focused vs blurred), and whether the stop is on screen and uncovered (2.4.11). It also checks that the folded expanders open from the keyboard. |
| `geometry` | The `ui-geometry-audit` method. It brings every content element into view the way focus does (scroll-padding honoured), samples its footprint and asks the DOM what is on top. The watermark and veil are made hit-testable for the measurement only. It also checks the sidebar states. **Break-tests** re-inject each fixed defect and require the check to name it. |

**Matrix cells.** Widths 360 / 768 / 1280 × themes light / dark / high-contrast, plus two extra
cells. `360_zoom200_light` emulates 200 % browser zoom at 360 px (a 180 CSS-px viewport at
deviceScaleFactor 2). `360_textmax_light` puts the app's own Text size slider at its maximum
(28 px). **States:**
* (a) the empty page;
* (b) one legal turn, "What are the penalties under the Act?";
* (c) one help turn, "I need an organisation that can help me in Lagos". The script asserts that
  this turn rendered helplines + NGO records (5 contacts) and not the clarify prompt.

Themes are set through Streamlit's main menu (System / Light / Dark). The script checks that the
rendered `.stApp` background really changed (`#ffffff` / `#0d1117`). High contrast is the app's own
sidebar checkbox "High contrast mode".

**Before/after.** The same matrix ran against the pre-H2 code (`git worktree` at `9ade6ca`, port 8502).

## 2. Results

### axe, rule violations per cell (critical / serious / moderate / minor)

| Cell | before: empty | before: legal | before: help | **after: empty** | **after: legal** | **after: help** |
|---|---|---|---|---|---|---|
| 360 light | 1/0/0/0 | 1/0/0/0 | 1/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| 360 dark | 1/0/0/0 | 1/0/0/0 | 1/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| 360 high-contrast | 1/1/0/0 | 1/1/0/0 | 1/1/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| 768 light | 1/0/0/0 | 1/0/0/0 | 1/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| 768 dark | 1/0/0/0 | 1/0/0/0 | 1/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| 768 high-contrast | 1/1/0/0 | 1/1/0/0 | 1/1/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| 1280 light | 1/1/0/0 | 1/1/0/0 | 1/1/0/0 | 1/0/0/0 | 1/0/0/0 | 1/0/0/0 |
| 1280 dark | 1/0/0/0 | 1/0/0/0 | 1/0/0/0 | 1/0/0/0 | 1/0/0/0 | 1/0/0/0 |
| 1280 high-contrast | 1/1/0/0 | 1/1/0/0 | 1/1/0/0 | 1/0/0/0 | 1/0/0/0 | 1/0/0/0 |
| 360 @ 200 % zoom | 1/0/0/0 | 1/0/0/0 | 1/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |
| 360, text size max | 1/0/0/0 | 1/0/0/0 | 1/0/0/0 | 0/0/0/0 | 0/0/0/0 | 0/0/0/0 |

**Totals over 33 scans: before 33 critical + 12 serious; after 9 critical + 0 serious, 0
moderate, 0 minor.**

* Before, the critical was `aria-allowed-attr` on the sidebar (every scan). The serious was
  `color-contrast`, in two forms. The high-contrast chat box had typed text at 1.06:1 (white on
  `#f6f8fa`). At 1280 light, captions measured 4.16:1 (`#75787c`).
* After, the only finding left is `aria-allowed-attr` on the sidebar `<section>`, and only at 1280,
  where the sidebar is open. At 360/768 the sidebar starts collapsed, and the H2 fix takes it out
  of the accessibility tree, so axe no longer sees the node. **Opening the drawer on a phone would
  surface the same node**, so this is one finding, not a width-specific one. The matrix does not scan the
  open-drawer state below 1280; the reviewer scanned it at 360 and 768 (light, help turn) and got the same
  single `aria-allowed-attr` critical, 0 serious and no new rules. Dark/HC with the drawer open are unscanned.

### Contrast over the background photo (`--mode=contrast`)

| | nodes axe could not judge (measured) | failing AA |
|---|---|---|
| before (pre-H2 tree, `9ade6ca`) | 213 | **20**, all of them the auto-linked e-mail/web addresses in NGO records on help turns: light 2nd percentile 2.17–2.20:1, dark 3.56–3.78:1 (minimum 3.14) |
| after | 152 | **0** |

The failures were real. The auto-linked e-mail and web addresses in NGO records sat directly on
the photo. The column scrim meant to prevent that never reached the photo (fix 6 below).

### Lighthouse accessibility (reported, not gated)

| | 1280 light, empty | 360 light, empty |
|---|---|---|
| before | 90 (`aria-allowed-attr`, `color-contrast`) | 94 (`aria-allowed-attr`) |
| after | **94** (`aria-allowed-attr`, the Streamlit sidebar) | **100** |

`npx lighthouse@13.4.1 --only-categories=accessibility`. 1280 used `--preset=desktop`; 360 used
mobile emulation at deviceScaleFactor 2.

### Keyboard (`keyboard_*.json`, light theme, after one legal turn)

| Pass | Stops until cycle | Trap | Stops with no focus indicator | Stops obscured |
|---|---|---|---|---|
| 1280 | 25 | no | 0 | 0 |
| 360 (sidebar collapsed) | 13 | no | 0 | 0 |
| 360 (drawer open) | 16 | no | 0 | 1: Streamlit's **Deploy** button, partly under the drawer (local dev only, see section 4) |

The order at 1280 is: sidebar (collapse button → High contrast → its help icon → Text size help →
Text size → Plain language → help → Clear conversation → Ask about my rights → Find help near me →
Auto-route → AI-answer every new turn → help) → header (Deploy, Main menu) → main scroll region →
"Link to heading" anchors → **6 more excerpt(s)** expander → **Answer with AI** expander → Switch
to help → **Read answer aloud** (inside its iframe) → **Voice input** expander → **chat input** →
document → back to the top. At 360 the sidebar is collapsed and contributes only its open button.

* Every required control is reached: chat input, voice input, read-aloud, the AI expander, the
  folded-excerpts expander, and the sidebar controls (at 1280, or after opening the drawer at 360).
* Enter opens the folded-excerpts expander and the voice expander. Inside the voice expander Tab
  reaches **🎤 Record question** (iframe) → help icon → **Type your question here** → **Send this
  question**.
* With the drawer open at 360, Tab stays in the drawer and the header. The page behind the drawer
  is out of the tab order.

### Geometry (`geometry.json`)

Checked at 360 / 480 / 481 / 767 / 768 / 1280. Each width is chosen where the layout flips:
480/481 is the avatar-stack query, and 767/768 is where the drawer becomes side-by-side. Each
width ran with a legal turn, with the sidebar both as loaded and toggled, and in light at every
width plus high-contrast at 360. **All 14 checks report nothing covered.** That covers the
watermark/veil, the fixed chat bar, the header over the sidebar's close button, the open sidebar
over the main column (≥ 768), and the page behind the drawer (< 768).

Break-tests (each must be named by the check):

| Re-introduced defect | 360 | 1280 |
|---|---|---|
| `scroll-padding: 0` (chat bar covers focused content) | **detected** (banner, helplines, headings 100 % under the chat bar) | **detected** |
| veil above content | **detected** | **detected** |
| sidebar back at `z-index: 2` (header over the close button) | **detected** (close button 100 % under `stHeader`) | not detected: expected, the header does not overlap the sidebar at 1280 |
| page behind the drawer visible again via a descendant | **detected** | not detected: expected, there is no drawer at 1280 |

Screenshots looked at: 360 light legal turn, 360 high-contrast legal turn, and 1280 dark legal and
help turns, before and after the scrim fix. Probe screenshots are under `runs\h2_after\`.

## 3. What was fixed

First pass, commit `40c3629`:

| # | Fix | File | Finding it closes |
|---|---|---|---|
| 1 | Light `textColor` `#1F2328` → `#0d1117` | `.streamlit/config.toml` | Captions 4.24:1 → 4.96:1 (1.4.3) |
| 2 | Sidebar `z-index` 2 → 999991 | `app.py` `accessibility_css()` | The header covered the sidebar's close button at 360 px (2.4.11 / 2.5.8) |
| 3 | Collapsed sidebar and descendants `visibility:hidden` | same | 13 invisible tab stops (2.4.7 / 2.4.11) |
| 4 | Open drawer < 768 px hides the page behind it | same | Tab walked into the covered page |
| 5 | `scroll-padding` reserves the fixed chat bar and header | same | Focused controls were 100 % hidden under the chat bar (2.4.11) |
| — | High-contrast text fields pinned black/white; component iframes titled or `aria-hidden`; iframe follows the Text size slider; read-aloud padding; avatar stacks at ≤ 480 px | `app.py` | High-contrast chat box 1.06:1; unnamed `st.iframe` frames; reflow at max text size (1.4.10) |

This step (second pass):

| # | Fix | File | Finding it closes |
|---|---|---|---|
| 6 | The scrim moves from `.block-container` onto each top-level column block (`position:relative` + the same 0.88 rgba literals the old `.block-container` scrim used; high contrast pins them black). The block holding the watermark is skipped. | `app.py` `accessibility_css()`, scrim block (`app.py:264-282`) and HC block (`app.py:196-199`) | Root cause: the watermark/veil divs are emitted **inside** `.block-container`, its own stacking context, so they painted *over* its scrim background, and every text in the column sat on the photo. NGO links measured 2.17:1 (light) and 3.56:1 (dark) at the 2nd percentile, 20 of 213 nodes failing. After: 0 of 152 fail (1.4.3). |
| 7 | Drawer hide extended to **descendants** (`section.stMain *`, `stBottom *`) | `app.py:117-132` | Streamlit's markdown wrapper declares `visibility:visible`, so the banner and answer text escaped fix 4 and stayed readable behind the drawer (found by the geometry pass) |
| 8 | Visible focus ring (`outline: 3px solid currentColor`) on the main scroll container | `app.py:142-150` | Chrome makes that scroll region a tab stop, and it had no focus indicator (2.4.7, keyboard pass) |

**Fix 6 is visible:** the column now reads as a translucent panel. The photo still shows in the
margins and in the gaps between blocks, but no longer behind text. This is what the Phase 05
scrim comment always said it did. The owner should look at it on the live site before merging.

Three asserts were added to `scripts/test_phase05.py` (140 → 143), one per new rule. **They are string
matches: they prove the rule text exists, not that it works** (that is how the original scrim went
unnoticed). The behavioural proof is `tools/a11y_audit`, which is not in CI, so 143/143 is not evidence
that the scrim, drawer hide or focus ring render. No colour
moved out of `config.toml`. The new rules either carry no colour literal (fixes 7, 8) or sit after
the high-contrast gate and reuse the existing scrim rgba literals (fix 6), so the "base CSS is
token-only" assert still holds. Layout stays linear: no `st.columns` were added, and
`render_turn` is untouched.

## 4. Remaining findings

**Critical, Streamlit-internal, justified: `aria-allowed-attr` on `section[data-testid=stSidebar]`.**
Streamlit puts `aria-expanded` on the sidebar's `<section>`, a role that does not support it. App
code cannot remove the attribute. A DOM patch would fight React, and the app's own CSS keys on that
attribute. Upstream issue: **https://github.com/streamlit/streamlit/issues/17126** (opened, read and
confirmed; closed as completed 2026-10-06 by PRs #17293 and #17294, which move `aria-expanded` onto
the collapse/expand buttons). **A fix is available to bump to in Streamlit 1.66.0** (PyPI, 2026-10-14); the pinned 1.63.0 still has the defect. DRLCA pins
1.63.0 in both requirements files. Upgrading is a dependency bump outside H2's scope, and 1.66.0 was
one day old at audit time. **Recommended follow-up:** bump to ≥ 1.66 in its own branch, re-run
`audit.mjs` and the suites, then re-check this row.

**The bump is not a free follow-up (review, 2026-10-15):** PR #17293 removes `aria-expanded` from the sidebar `<section>` and uses `data-collapsed` instead. Every H2 selector keyed on `[aria-expanded=...]` (`app.py` collapsed-sidebar hide and drawer hide) and `tools/a11y_audit/audit.mjs` (`sidebarExpanded` / `openSidebar`) would silently stop matching, and `test_phase05` would still pass because its asserts are string matches. The bump branch must migrate those selectors and add a behavioural check (collapsed sidebar = zero focusable controls) before it is re-audited.

**Not axe findings, recorded:**
* *Incomplete, `aria-prohibited-attr` (2 nodes on every turn).* These are Streamlit's
  `stChatMessageContent` divs, which carry `aria-label="Chat message from user/assistant"` but no
  role, so the label may be ignored. axe could not decide. Streamlit-internal. Whether NVDA
  announces "Chat message from assistant" is part of owner check A.
* *Streamlit's "Deploy" button* is partly under the open drawer at 360 px. It exists only on
  localhost: with the default `toolbarMode = "auto"`, developer options are not shown to remote
  viewers. Not verified on the live Render site in this session.
* *Repeated "Link to heading" names.* Streamlit adds an anchor to `st.title` and markdown headings,
  so several links share one name. These are minor and Streamlit-internal, and axe does not flag them.
* *The read-aloud button uses the browser's default button style* inside its iframe (light grey in
  every theme, including dark and high contrast). Its contrast is fine (dark on light). It is
  cosmetic only.
* *The chat input's focus indicator* is a border-colour change on its container, not an outline. It
  is visible (detected by the keyboard pass), but whether it is visible *enough* is a human
  judgement: see the owner checklist.

> **2026-10-21: the four H2/H3 leftover minor items are FIXED and DEPLOYED (branch `phase11/a11y-minor`, `883fefe` +
> `e0fdf0d`; reviewer BLOCK on the first pass, then SHIP; merged as PR #19 → `0eb8959`; live smoke `live_smoke_a11y.mjs` passed).**
> * **Read-aloud now follows the NGO filter.** `render_help_records` returns the payload as displayed, and the replay speaks
>   that. Browser: after an FCT filter it speaks exactly the 9 contacts on screen. The stored payload is unchanged.
> * **The route choice is a native radio group**, "How should I handle your next question?". It has a checked state, arrow keys and stable
>   focus. The first attempt, buttons with a changing "(selected)" label, **dropped keyboard focus to `<body>`** on every
>   press. The reviewer caught it (WCAG 2.4.3), so it was replaced. A used-up override now resets *before* the sidebar draws,
>   so the control and the "Next question" caption are never stale.
> * **The slider is announced once ("Text size").** The bridge drops the range input's redundant `aria-labelledby`.
> * **Sidebar before H1:** the DOM is not reordered, because that would fight React. Instead there is a **skip link as the first Tab stop**
>   ("Skip to helplines and answers" → focuses H1). It is fixed above Streamlit's header, white on black with a gold ring, `!important`,
>   so high contrast cannot turn it gold-on-white. There are also named landmarks: `main` "Helplines and answers", region "Settings"
>   (sidebar), and region "Ask a question" (the pinned chat box). The page previously had no `main` landmark.
> * Verified by `tools/a11y_audit/minor_check.mjs` and the reviewer's own probes:
>   * focus stays on the radio after arrow keys or a click;
>   * the skip link is topmost when focused at 1280 and 390, in dark and in high contrast;
>   * the B3 drawer trap and Esc are unaffected;
>   * the routing trap and Clear behave;
>   * axe (WCAG tags) finds 0 violations;
>   * best-practice axe finds only the pre-existing `heading-order` (H1 → H3 "Conversation so far").
>
>   `test_phase05` 179/179.
> * **Not verified:** NVDA/JAWS announcements of the radio group and the skip link (automation and axe only), and a voice-path turn that
>   exercises an override. **New minor:** `heading-order` (best-practice, not WCAG). The skip link overlays the sidebar toggle
>   while it holds focus (normal for skip links).

## 5. WCAG 2.2 AA criteria

Pass = automated evidence above. Owner-verified = needs a human (screen reader, real microphone,
judgement about meaning), so it stays open until signed. N/A = no such content.

| SC | Name | Status | Evidence / note |
|---|---|---|---|
| 1.1.1 | Non-text content | Pass (auto) + owner-verified | no axe violation in 33 scans (the saved JSON keeps pass *counts*, not pass IDs, so `image-alt` and `frame-title` are not shown to have applied; `button-name` was in the pass list of the reviewer's drawer-open scan); the watermark and veil are `aria-hidden`. Whether emoji labels read sensibly is for NVDA. |
| 1.2.1–1.2.5 | Audio / video | N/A | No time-based media. |
| 1.3.1 | Info and relationships | Pass (auto) + owner-verified | Headings, lists, labels pass axe; reading order under NVDA is in the checklist. |
| 1.3.2 | Meaningful sequence | Owner-verified | DOM order is helplines → question → answer → excerpts (asserted in `test_phase05`), but the reading order must be heard. |
| 1.3.3 | Sensory characteristics | Pass | Instructions name controls by label, not by shape or position alone. |
| 1.3.4 | Orientation | Pass | No orientation lock; 360 portrait works. |
| 1.3.5 | Identify input purpose | N/A | No personal-data fields. |
| 1.4.1 | Use of colour | Pass | Links are underlined; state is not colour-only. |
| 1.4.2 | Audio control | Pass | Read-aloud plays only on request; re-pressing cancels the previous utterance. |
| 1.4.3 | Contrast (minimum) | **Pass** | axe 0 `color-contrast` in 33 scans + 0 of 152 failing pixel measurements over the photo. |
| 1.4.4 | Resize text | Pass | 200 % zoom cell and max Text size cell: 0 axe findings, geometry clean. |
| 1.4.5 | Images of text | Pass | None. |
| 1.4.10 | Reflow | Pass | 180 CSS-px (200 % at 360) has no horizontal page scroll and 0 findings. |
| 1.4.11 | Non-text contrast | Pass (auto) + owner-verified | Control borders are the theme tokens; the focus ring uses `currentColor`. A human should confirm the chat-input focus border. |
| 1.4.12 | Text spacing | Owner-verified | Not tested with a text-spacing bookmarklet. |
| 1.4.13 | Content on hover or focus | Owner-verified | The sidebar close button is revealed on hover **and** on keyboard focus (measured). Whether Streamlit's help tooltips are dismissable with Esc was not tested. |
| 2.1.1 | Keyboard | **Pass** | Every control is reached; expanders operate on Enter. |
| 2.1.2 | No keyboard trap | **Pass** | Focus cycles at 360 and 1280; no trap. |
| 2.1.4 | Character key shortcuts | Owner-verified | Streamlit's "R" (rerun) and "C" (clear cache) shortcuts appear in its menu on localhost. Check whether they exist for remote viewers. |
| 2.2.1 / 2.2.2 | Timing / pause | N/A | No time limits or moving content. |
| 2.3.1 | Three flashes | Pass | Nothing flashes. |
| 2.4.1 | Bypass blocks | Pass (auto) + owner-verified | axe `bypass` passes (headings/landmarks exist). There is no skip link, and at 1280 the sidebar's 13 stops come before the main content. Judge with NVDA whether heading navigation is enough. |
| 2.4.2 | Page titled | Pass | "DRLCA — Disability Rights Assistant". |
| 2.4.3 | Focus order | Pass (auto) + owner-verified | Sequence above; NVDA confirmation in the checklist. |
| 2.4.4 | Link purpose (in context) | Pass | NGO links are the URL/e-mail in a record that names the organisation. |
| 2.4.5 | Multiple ways | N/A | Single-page app. |
| 2.4.6 | Headings and labels | Pass | Every control has a name (axe `label`, `button-name`). |
| 2.4.7 | Focus visible | **Pass** | 0 of 54 stops lack an indicator (the scroll-region one was fixed in this step). |
| 2.4.11 | Focus not obscured (minimum) | **Pass** | 0 obscured stops in the main UI. The only one is the localhost-only Deploy button behind the drawer. The geometry break-test proves the check sees the chat bar. |
| 2.5.1 / 2.5.2 | Pointer gestures / cancellation | Pass | Single-click controls, activation on up-event (browser default). |
| 2.5.3 | Label in name | Pass | Visible labels are the accessible names. |
| 2.5.4 | Motion actuation | N/A | |
| 2.5.7 | Dragging movements | Pass | The Text size slider also works by arrow / Home / End (the audit sets it with End). |
| 2.5.8 | Target size (minimum) | Pass (auto) | axe `target-size` is a pass (not inapplicable) and has no violation in any of the 33 scans. |
| 3.1.1 | Language of page | Pass | `<html lang="en">`; axe `html-has-lang` / `html-lang-valid` pass. |
| 3.1.2 | Language of parts | Owner-verified | Pidgin/Hausa questions are not marked up as such. Judge whether that matters with real users. |
| 3.2.1 / 3.2.2 | On focus / on input | Pass | No context change on focus. A checkbox changes a setting only. |
| 3.2.3 / 3.2.4 | Consistent navigation / identification | Pass | Single page; the same controls everywhere. |
| 3.2.6 | Consistent help | Pass | Helplines in the same place: page top and leading every turn. |
| 3.3.1 | Error identification | Owner-verified | "Please record or type a question first" is text; check that it is announced. |
| 3.3.2 | Labels or instructions | Pass | Chat input and draft box have labels and placeholder instructions. |
| 3.3.3 / 3.3.4 | Error suggestion / prevention | N/A | No legal or financial transactions. |
| 3.3.7 | Redundant entry | Pass | The voice draft carries the transcript into the box; nothing has to be retyped. |
| 3.3.8 | Accessible authentication | N/A | No login. |
| 4.1.2 | Name, role, value | **Fail (Streamlit-internal)** | The sidebar `aria-expanded` on a `<section>`; see section 4. Everything app-controlled passes. |
| 4.1.3 | Status messages | Owner-verified | Whether NVDA announces new turns and the "Heard: …" voice message is in the checklist. |

## 6. How to re-run

```powershell
cd D:\NGORAG\tools\a11y_audit
npm ci                                   # pinned versions from package-lock.json
# in another terminal:
C:\conda-envs\drlca-rag\python.exe -m streamlit run app.py --server.headless true --server.port 8501
node audit.mjs --base=http://localhost:8501 --out=D:/NGORAG/runs/h2_after                  # all modes
node audit.mjs --base=http://localhost:8501 --out=D:/NGORAG/runs/h2_after --mode=matrix --cells=360_hc,1280_dark
$env:CHROME_PATH = "$env:LOCALAPPDATA\ms-playwright\chromium-1234\chrome-win64\chrome.exe"
npx -y lighthouse@13.4.1 http://localhost:8501/ --only-categories=accessibility --preset=desktop --output=json --output-path=D:\NGORAG\runs\h2_after\lighthouse\lh_1280.json
```

* The script uses `CHROME_PATH`, else the cached `chromium-1234` build, else Playwright's own
  Chromium.
* `--cells=` re-runs merge into `summary.json`.
* Restart Streamlit after any CSS or config edit; a browser reload is not enough.
* For a before/after, run it from a `git worktree` of the old commit on port 8502.
* Outputs go to `runs\` (gitignored).

---

## 7. OWNER CHECKLIST (the human half of the H2 gate)

Use the live site or a local run. Keep the AI expander OFF unless a step says otherwise. Write
notes under each item, then sign it.

> **Agent pre-run, 2026-10-18 (local `phase11/h2-a11y` @ `b59a160` + the mic fix below). Not a sign-off.**
> Tooling: `tools/a11y_audit/nvda_probe.mjs` (NVDA 2024 started with `--log-level=12`, Playwright
> Chrome, NVDA gestures sent as OS keys by `oskeys.py`, speech read back from the IO log) and
> `owner_checks.mjs` (B/C/D; C uses a fake mic fed a TTS WAV). Zero Gemini calls.
> * **A1** pass with a caveat: helplines come right after H1, but at 1280 the **sidebar is read
>   first** (it precedes main in Streamlit's DOM), then Deploy / Main menu, then H1.
> * **A2 FAIL (known 4.1.3 item):** after Send, NVDA only re-announces the empty chat input. The
>   page has no live region at all.
> * **A3** pass: `face` question → `smart_toy` **helplines** → Your rights → tagged excerpts → fold →
>   AI expander → Switch → Read aloud (tail confirmed by Tab order).
> * **A4, A5, A6** pass. A5: every sidebar control speaks name + role + state. Minor: the slider
>   says "Text size Text size", and the route buttons expose no selected state.
> * **A7: NVDA speaks `keyboard_arrow_right`, `smart_toy` and `face`.** Expander summaries are
>   announced as e.g. "keyboard_arrow_right 📄 6 more excerpt(s)… button collapsed".
> * **B1** pass (real Tab reaches the Read-aloud button inside its iframe; voice expander → mic,
>   draft, Send). **B2** pass with the noted weak cue: the chat input's 1 px border turns green.
>   **B3 partial:** the close button works and main is not reachable, but **Esc does not close the
>   drawer** and Tab escapes to the header's Deploy / Main menu before wrapping.
> * **C1 was FAIL on every build since Phase 06 and is fixed here:** `mic_recorder` defaulted to
>   `format="webm"`, which `sr.AudioFile` cannot read, so every clip ended in "Could not transcribe
>   (ValueError)". With `format="wav"` the clip transcribes, lands in the draft, is edited and sent,
>   and a legal turn answers, in Chrome and Edge. **C2 partial:** denied permission gives no error
>   page and the text box still answers, but **the app never says voice is unavailable** (the error
>   only reaches the console: `NotAllowedError`).
> * **D1** pass on order (helplines first) but it speaks **10 tags against 9 cards**:
>   `build_speech_text` reads `legal["citations"]`, which skips H1's `dedupe_excerpts`. **D2** pass.
> * Automation-only quirk: in Playwright windows the mic iframe sizes to 0 px (real Chrome 155:
>   38 px, live site the same as local), so the script presses Record from inside the frame.
>
> **Fixed the same day on this branch, then re-verified.** C1 fix `4a07e8b`. The rest:
> `build_speech_text` now speaks the tags of the deduped cards (**D1**: 9 tags / 9 cards), and
> `A11Y_BRIDGE_JS`, which `theme_watch_html()` installs once into the parent document, adds:
> * **A2:** a polite `role=status` live region. Only `render_turn` (a NEW turn) posts to it,
>   never a replay. NVDA, focus still in the chat box: *"New answer below. National helplines
>   (always first): DRAC Toll-Free … 9 legal excerpts with citations."*
> * **A7:** `aria-hidden` on every `stIconMaterial`. Icon-only buttons are named ("Close
>   sidebar" / "Open sidebar") and avatars are `role=img` "You asked" / "Assistant answered".
>   NVDA now says "📄 6 more excerpt(s)… button collapsed", and Chrome's AX tree
>   (`ax_names.mjs`) shows 0 ligature leaks at 1280 and 360.
> * **B3:** at < 768 px Esc closes the drawer (focus goes to "Open sidebar"), and Tab / Shift+Tab
>   loop inside it. Measured: 25/25 Tab stops stay inside.
> * **C2:** a blocked microphone (Permissions API) puts a visible `role=alert` note in the voice
>   expander saying voice input is unavailable and to type instead. Verified in Chrome and Edge.
>
> **H2 review (reviewer agent, SHIP WITH CAVEATS) taken:** a voice-to-Google disclosure before
> Record (the WAV fix made `recognize_google` live for the first time); `_js_str` escapes every
> `<`; a test that the bridge has no `%`; Esc ignores IME composition; no "0 excerpts" wording; and
> the dismissed-prompt case for C2.
>
> axe after: unchanged (0 serious / 0 moderate / 0 minor, plus the 9 known Streamlit-internal
> critical nodes at 1280). `test_phase05` 152/152. Still open, minor: the slider is announced
> "Text size Text size", the route buttons expose no selected state, and the sidebar is read
> before H1 at 1280. **A6 needs a clean NVDA re-run:** the 2026-10-18 run was invalidated when
> NVDA's usage-data dialog moved focus to another window. Never run `nvda_probe.mjs` while you
> are typing elsewhere, because OS keys go to the focused window.

**A. NVDA + Chrome (Windows).** NVDA on, browse mode, Chrome.
1. Load the page. The reading order is: page title → **helplines banner** → instructions → voice
   expander → chat input.
2. Ask "What are the penalties under the Act?". Without moving focus, is the new turn announced? If
   not, record it: it is the 4.1.3 open item.
3. Read the turn: **helplines → your question → "Your rights" → excerpts with their citation tags →
   "6 more excerpt(s)" expander → AI expander → Switch button → Read answer aloud**.
4. Open "6 more excerpt(s)" with Enter. Its excerpts are read; close it again.
5. Tab through the sidebar (open it first on a narrow window). Every control announces a name and
   state: High contrast (checkbox), Text size (slider with value), Plain language, Clear
   conversation, the three route buttons, AI-answer every new turn.
6. Ask a help question ("I need an organisation that can help me in Lagos"): helplines are read
   before the organisations.
7. Listen for icon ligature text: the chat avatars expose `face` / `smart_toy` as text, and the sidebar
   toggle and expander summaries may read `keyboard_double_arrow_left` / `keyboard_arrow_right`. Record
   whether NVDA speaks these words.

Signed: Agent-run (Claude Opus 5.5) on the owner's instruction, NVDA IO log, not a human listening session. Date: 2026-10-18. Notes: A1–A7 pass after `7692a40` (A6 clean re-run with the focus guard). Open minor: sidebar read before H1 at 1280; slider name doubled.

**B. Keyboard only** (no mouse).
1. From the address bar, Tab reaches the chat input, the voice expander (Enter opens it; Tab reaches
   Record, the draft box, Send), Read answer aloud, the AI expander, the folded-excerpts expander
   and the sidebar controls.
2. Focus is always visible. Look at the chat input in particular: its focus cue is a border colour
   change.
3. No trap. At 360 px (or a narrow window), with the drawer open, Tab stays in the drawer, and Esc
   or the close button returns you to the page.

Signed: Agent-run (Claude Opus 5.5) on the owner's instruction. Date: 2026-10-18. Notes: B1/B2 pass (chat-input cue is a thin border, weak but present); B3 pass after fix (Esc closes, Tab loops). The trap is not announced as a dialog, so nothing tells an SR user that Esc exits (H2 review caveat).

**C. Live microphone** (Chrome, then Edge).
1. Open Voice input, press Record, dictate "What are my rights to education?", stop. "Heard: …"
   appears and the draft box holds the transcript. Edit it, then Send: a legal turn answers.
2. Deny microphone permission (site settings → block), reload, and try again. The app must say
   voice is unavailable and leave the text box fully usable, with no error page.

Signed: Agent-run (Claude Opus 5.5) on the owner's instruction, using a fake microphone fed a TTS WAV, not a human voice. Date: 2026-10-18. Notes: C1 pass in Chrome and Edge after `4a07e8b` (was broken since Phase 06). C2 pass: a visible alert on blocked OR dismissed permission (the getUserMedia rejection is caught). A disclosure that recording goes to Google's speech service is shown before Record.

**D. Read-aloud.**
1. Legal turn: press **Read answer aloud**. The helplines are spoken **first**, then the
   citations.
2. Help turn: same. The helplines come first, then the organisation names.

Signed: Agent-run (Claude Opus 5.5) on the owner's instruction (speech text intercepted, not heard). Date: 2026-10-18. Notes: D1/D2 helplines first; D1 9 tags = 9 cards.

**E. Optional: one session with a blind or low-vision user** (for example via a JONAPWD contact),
recorded as written notes, not audio. Note what they tried, where they got stuck and what they
said.

Signed: ____________________  Date: __________  Notes:
