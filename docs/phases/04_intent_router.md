# Phase 04 — Intent router (legal vs help)

## Goal
Detect whether the user needs legal information or NGO connections and route to the
right subsystem. Spec target: 8/10 queries routed correctly.

## Entry criteria
- Phase 02 retrieval contract and Phase 03 lookup both callable as functions.

## Steps
1. **Keyword baseline** (`src/router.py`): legal cues (`right`, `law`, `section`, `act`,
   `constitution`, `discriminat*`, `penalt*`, `employer`) vs help cues (`need help`,
   `where`, `contact`, `near me`, `organization`, `helpline`, disability/location names).
   Score both, route to the higher; ties → ask one clarifying question (never guess).
2. **Test set**: 10 queries covering pure-legal (4), pure-help (4), mixed/ambiguous (2).
   Mixed queries (e.g. "my employer fired me, who can help?") → legal answer + NGO referral
   both; the router returns a *primary + secondary* route, not a single label.
3. **LLM router (optional stretch)**: only if keyword accuracy < 8/10. Prompt Gemini with
   the same cue lists; compare cost/latency honestly in the journal before adopting.

## Exit criteria
- [ ] 8/10 test queries routed correctly (mixed count if both routes fire).
- [ ] Ambiguous queries produce a clarifying question, never a wrong-subsystem answer.
- [ ] Router latency negligible vs LLM call (keyword path) — measured, not assumed.

## Record results in
`LEARNING_JOURNAL.md` → cue lists, test table, keyword-vs-LLM decision with numbers.

## Status (2026-09-08 — DONE, reviewer ship-with-notes + fixes applied)
- Keyword baseline 10/10 (exit 8); ties/zero/singleton-generics → clarifying question; dual primary+secondary.
  Latency mean ~0.6ms (« 50ms). LLM-router stretch rejected on numbers.
- Post-review fixes: cue anchoring (lawyers/bright/defines), singleton-clarify guard, explicit tie-clarifies
  policy. Matrix re-run 10/10 ALL PASS.
- Exit criteria: [x] 8/10 routed (10/10) · [x] ambiguous clarifies, never wrong-subsystem · [x] latency measured.
- Phase 03 residual wired: needs_confirmation + did-you-mean on fuzzy; top-k guidance for UI.

## Traps
- Pidgin and Nigerian-language queries (`"wetin be my right?"`) break keyword lists —
  seed the test set with at least 2 non-standard-English queries from the start.
- Routing is a UX decision as much as ML: a wrong route that *looks* confident is worse
  than a clarifying question. Bias to asking.
