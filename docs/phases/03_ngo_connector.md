# Phase 03 — NGO connector (verify → match → helpline banner)

## Goal
Curated, trustworthy NGO referrals by disability type + location, with national helplines
always on top. Spec target: 5 different disabilities matched to relevant orgs.

## Entry criteria
- `data/ngo.csv` (12 rows, exact schema `name,disability_focus,location,phone,email,website,description`).
- `src/ngo.py` lookup + fuzzy match already working (`visually impaired` → NAB verified).

## Steps
1. **Verify every contact** against the official site in the row's `website` column.
   Known placeholders: 5 phones (`0803 000 0000`-style) + several emails were guessed —
   replace with published contacts or mark the row `unverified` and exclude it from results.
   Rule: no unverified phone number ever reaches a user.
2. **Extend the test matrix**: 5+ disabilities × 2+ locations (Lagos, Abuja, Kano, rural),
   including misspellings (`hearing impared`, `binness`) to exercise the fuzzy path.
3. **Helpline banner contract**: DRAC Toll-Free `08000-3000-100` + DRAC WhatsApp `08000-3000-10`
   returned FIRST by every lookup function, before any CSV rows. Test asserts their presence.
4. **Empty-result behavior**: unknown disability/location → helplines + JONAPWD umbrella referral,
   never an empty list.

## Exit criteria
- [ ] All 12 rows verified (or pruned); verification date recorded per row in the journal.
- [ ] 5 disabilities × locations return the correct org in the top result.
- [ ] Helpline banner present in every response shape (function test, later UI test).

## Record results in
`LEARNING_JOURNAL.md` → verification table (org, source URL, date, changed fields);
`data/ngo.csv` itself is the deliverable — commit it clean.

## Status (2026-09-08 — DONE, reviewer ship-with-notes)
- All 10 rows verified 2026-09-08 (sources in LEARNING_JOURNAL.md); Leprosy Mission + Sightsavers pruned
  (unverifiable phone); NAB/NNAD medium-confidence, RECHECK-stamped.
- 6 disabilities × Lagos/Abuja/Kano/rural correct top-1 (incl. misspellings); helplines first everywhere;
  unknown → helplines + JONAPWD, never empty. Matrix 16/16 + statics 7/7, exit 0.
- Exit criteria: [x] rows verified/pruned + dated · [x] 5+ disabilities × locations top-1 · [x] banner everywhere.
- Residual: single-token death/blend misroutes → Phase 04 confirms on fuzzy flag; top-k display (L2).

## Traps
- NGO sites move and numbers change; verification has an expiry — stamp the date.
- Fuzzy matching can misroute (`deaf` vs `death`, `blind` vs `blend` cutoffs) — keep the
  `difflib` cutoff at 0.5+ and log every fuzzy fallback so misroutes surface in tests.
