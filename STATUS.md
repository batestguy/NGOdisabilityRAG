# STATUS — current state (updated 2026-10-25)

Current state only. Replace lines; do not append history. Dated history to 2026-10-22:
`docs/history/status_history.md`. Phase records: `docs/phases/`. Narrative: `LEARNING_JOURNAL.md`.

## Live

- **https://ngodisabilityrag.onrender.com** (Render free, `srv-dah26opt0dsc73e9a350`), `main` = `94db479`
  (PR #20: H8 playbook + H8c + H8b; deployed and live-smoked 2026-10-22).
- Multi-turn chat; helplines first on the page and on every turn; offline by default; Gemini AI expander
  opt-in, default OFF (`cite-strict-v3` / `chat-cite-strict-v2`, "recommendable" per Phase G).
- Corpus v2 (Act gazette-OCR, clause-aligned, cl.1/12/20 corrections signed; Constitution; Factsheet).
  Retrieval `k=4/doc, top_n=12`, hand `SYNONYMS` + OOV bridge, `MIN_SCORE = 0.10`.
- NGO directory: 20 verified orgs, 6 zones, filter/sort (H3). Cedar Foundation = RECHECK (website blank).
- Accessibility: WCAG 2.2 AA audit (H2) + leftovers fixed (skip link, landmarks, native route radio,
  single-name slider, read-aloud follows NGO filter). Axe WCAG matrix 0 (local, 2026-10-22).
- H7 counts-only "Was this answer helpful?" signal in Render logs (`DRLCA_SIGNAL`).
- CI: `.github/workflows/offline-suites.yml` on every PR and push.

## Numbers (current)

- Retrieval (`scripts/baseline_phaseE_2026-09-24.txt`): recall_strict frozen-10 0.734 · dev 0.613 ·
  test 0.647 · test2 0.629. False refusals 0 on every set. `calibrate_refusal` 0/212.
- Generation (Phase G, 2026-10-15): judge 23/23, G4 0 cross-turn drift, G6 10/10 answered, 0 fabricated tags.
- Suites (2026-10-22): `test_phase03` matrix 24/24 + statics 16/16 · `test_phase04` ALL PASS ·
  `test_phase05` 179/179 on `main` (193/193 on the v3 branch) · `test_phase09_ops` ALL PASS · `import app` + `import ui_render` OK.
- UI code: `app.py` (run / render_turn / replay_turn / history / banner / loaders) 1,352 lines +
  `src/ui_render.py` (shared render helpers, re-exported by `app`) 437 lines (H8b).

## Open

- **Active: H8 — `docs/phases/17_h8_corpus_expansion.md` (H8a-R passed; H8a.4 done; H8a.5 next).** H8c + H8b DONE and live. H8a.0 DONE: the owner
  chose + signed the **Accessibility Regulations 2023 (S.I. 51)** (`docs/h8a_source_dossier.md`; PDF in `data/raw/`).
  H8a.1 DONE 2026-10-23: `data/eval/questions_accessregs.json` (dev 8 / blind `test3` 12 / status 6), committed
  before any parser as `af3129e`. H8a.2 DONE 2026-10-23 (reviewed): corpus v3 = v2 + `accessregs2023` (221 chunks, `[Regs reg. N]`, pin
  `f13b9678…`, version-keyed OOV bridge); v2 proven bit-identical; `CORPUS_VERSION` still v2. H8a.3 declined at the dev stage; owner reopened → **H8a-R SHIP GATE MET for R-a** (v3, k=4, top_n=16 + fixed status
  note): existing law identical (frozen-10/dev/test2), fresh dev2 0.800, blind test3 0.875, 0 false refusals; off-corpus
  answered 13 → 14/17. H8a.4 DONE (note renders once before the first Regs card;
  v3 budget 16; Regs excluded from the LLM; v2 byte-identical). **H8a.5 DONE** (reviewed 2026-10-25; `CORPUS_VERSION = "v3"`; `scripts/baseline_v3_2026-10-23.txt` + errata; OFF12 answered on v3 is open and pinned). H6-S.2 PASS (`scripts/audit_fixed_text.py`, in CI; one interpretive phrase for the owner). **Next:** H6-S.3, H8a.6 on booked free quota days, H8a.7.
- **⚠ Helpline check (2026-10-25):** DRAC Toll-Free verified on drac-ng.org; **WhatsApp `08000-3000-10` not found there** (only office `08115326607`). Owner decision pending (`HANDOFF.md`).
- **Owner rule (2026-10-25): zero cost, self-review first** (`docs/phases/19_zero_cost_self_review.md`). External legal
  and language review deferred to a grant-funded phase F. **H6-S** (disclosure line, fixed-text traceability, agent
  self-review of the H6 sheet) replaces H6 as the gate. H6-S.1 (the "not legal advice" line, + Hausa/Igbo/Yorùbá versions, not native-checked) is built on `phase11/h6s-disclosure`, awaiting the owner's merge word.
- **Queued: H9 deterministic follow-ups** (`docs/phases/18_h9_deterministic_followups.md`): H9a suggested questions
  (low risk, can run while H8a waits on H6); H9b extractive key lines (after H6 + the H7 read). Owner approval pending.
- **H7 week-1 read on/after 2026-10-28** (command in `HANDOFF.md`; discount 4 smoke ids).
- **Owner:** is `test` still clean? · H6 sheet kept ready for F1 (funded) · H5b deferred to F2 (native speakers, funded)
- **Deferred:** NGO directory growth past 20 (no Facebook route). Old owner items (demo GIF encode, LinkedIn) are in `docs/history/status_history.md`; still wanted?
- **Small:** NVDA listen-through of radio + skip link · best-practice `heading-order` (H1 → H3) ·
  Cedar RECHECK · Streamlit 1.66 bump (`aria-expanded` migration).
- **Unmerged branches:** `phase11/h8a-sources` (dossier + Regs PDF + H9 playbook) and `phase11/h8a-accessregs` (built on it;
  + H8a.1 questions + H8a.2 v3 corpus). Both pushed; merging redeploys, so bundle with the H8a code.
