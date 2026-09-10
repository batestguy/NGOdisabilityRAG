# Learning Journal — DRLCA Foundation (2026-09-06)

## Decisions
- Env: `ds-general` (Py 3.12, numpy 1.26, pandas 2.2, sklearn 1.9, Streamlit 1.60 all present, zero installs). Local embeddings deferred — no torch in ds-general; API path keeps Colab compat.
- Embeddings: TF-IDF (1–2-gram, English stopwords) offline baseline; `embed_gemini()` opt-in behind `GOOGLE_API_KEY` (key confirmed present, 39 chars, unused this slice).
- UI: Streamlit (preinstalled 1.60); not built yet.

## Benchmarks (SAMPLE text, 783 chars — indicative only, not citable)
- Chunks: recursive 500/50 → 2 (avg ~390 chars); section-aware 800 → 3 (one per Section heading).
- Retrieval over 10 sample questions: 6/10 nonzero top-1 (scores 0.17–0.41); 4 zeros (`penalties`, `education`, `dignity/equality`, `legal aid`) — expected: 3-chunk placeholder lacks those topics. Re-run after real Act lands.
- NGO: 12 rows, exact schema validated; fuzzy match works (`visually impaired` → NAB).

## What worked / didn't
- Worked: prefix-env activation, stdlib+sklearn-only `src/` (Colab-safe), section-aware splitting on `Section N` headings.
- Didn't / gaps: real legal PDFs not downloaded (manual step, `SOURCES.md`); 5 NGO phone fields are `0803 000 0000`-style placeholders + 5 emails guessed — MUST re-verify before any deploy; no FAISS/Chroma/LangChain in ds-general (install when needed, not now).

## Next
Replace SAMPLE with real Act text → re-run notebook → wire citation prompt + intent router → Streamlit stub → RAGAS.

## 2026-09-06 update — heavy work moved to Colab (SUPERSEDED same day, see update 2 below)
- Local `ds-general` is for light editing/verification only. OCR, embeddings, eval run in `notebooks/02_ocr_act_colab.ipynb` (Drive-checkpointed, survives Gemini free-tier quota pauses).

## 2026-09-06 update 2 — Colab abandoned, isolated env built, OCR DONE locally
- New env `C:\conda-envs\drlca-rag` (py 3.11.16, see `requirements-rag.txt`, handoff in `HANDOFF.md`).
  RapidOCR (ONNX CPU) did 27/27 pages in 681 s, avg conf 0.95–0.97, zero lines below 0.6 → no Gemini
  correction needed. Full Act text complete: clauses 1–58 continuous, PARTs I–X.
- Retrieval benchmark on real corpus (864 chunks): 10/10 nonzero (was 6/10 on SAMPLE placeholder).
  Constitution queries weak (~0.16) → chapter-aware chunking is the next retrieval task.
- Artefacts to handle: joined words from justified text ("Apersonwith"), duplicate scan pages (p.5/6).
- `paddlepaddle` unusable on this box (no py3.11+ Windows CPU path that installs cleanly); RapidOCR wins.
- ds-general pollution incident + restore: rapidocr install bumped numpy 1.26→2.5 (broke catboost/numba);
  restored via pip uninstall of additions + `pip install numpy==1.26.4`; verified catboost/numba/streamlit/mlflow.
  Residue: protobuf 5.29.6 (was 7.35.1), grpcio kept. Rule going forward: all installs in `drlca-rag` only.

## 2026-09-08 — Phase 01 DONE (bench PASS, reviewer: ship-with-notes)
- Cleanup: Act 27 pages, only dup pair p5→p6 (difflib 0.819 / line-contain 0.44; next-best pair 0.084).
  Playbook's literal >0.85 threshold MISSES it (OCR spacing noise) → used 0.75 with margin, kept cleaner
  p.6, salvaged 1 unique line, sidecar 27 entries. Raw file untouched; markers stripped at load time.
- `repair_joins()` (src/load.py): full-segmentation into allowlist only; 290 distinct tokens fixed
  (e.g. `Apersonwith→A person with`, `PARTVI→PART VI`, `thisAct→this Act`), 0 observed false splits;
  16 residual camel tokens left as-is (misspellings `Partiipation`, fragments `eStaffofthe`, digit mixes).
  Also fixed latent `section_aware_split` preamble-drop bug (was losing ~90% of Act → 9 chunks; now 62).
- Constitution chunking (src/chunk.py `constitution_aware_split`): chapter→section split, `Constitution, {heading} §N:`
  prefix, priority Ss.14,17,33–46 never merged, all ≤ cap. Grid (joint corpus): size 800 → Q9 0.113 FAIL;
  500 → 0.139 FAIL; **400 → Q9 0.167 PASS**, mean 0.275. Recommended const size = 400 (≤800 cap, compliant).
- Chunk stats (after): Act 62 (avg 632, max 800) · Constitution 2104 @400 (max 400) · Factsheet 48 (avg 483).
  Joint total 2214; before total 1295 (avg 499).
- Before→after top-1: Q1 0.133→0.187, Q2 0.197→0.186, Q3 0.463→0.401, Q4 0.418→0.672 (Act cl.31),
  Q5 0.105→0.141, Q6 0.147→0.168, Q7 0.314→0.340, Q8 0.122→0.176, **Q9 0.133→0.167 (S17, PASS)**,
  Q10 0.182→0.310. Mean 0.221→0.275; 10/10 nonzero both; clause 1–58 continuous 58/58.
- Reviewer notes (Phase 02 follow-ups): constitution is 95% of joint index (S36→21 chunks) so Act-specific
  Qs (Q1/Q5/Q6/Q8/Q10) now top-1 to Constitution with higher absolute scores — add per-doc routing or
  score norm + k=3/5 hit-rate; propagate (doc_id, ref) into production retriever; consider two-tier const size.

## 2026-09-08 — Phase 02 IN PROGRESS (executor + review + fix round; blocked on quota reset)
- Executor (ml-builder): model `gemini-2.5-flash` re-resolved via live list-models (2.0-flash gone, confirmed);
  PerDocRetriever (option b, k/doc merged) — Act represented despite 95% constitution index; MIN_SCORE=0.10
  calibrated as weak-overlap floor (in-corpus min 0.169 per-doc / 0.141 joint; same-vocab junk 0.249-0.306
  sits ABOVE good hits → band inverted, semantic refusal lives in LLM layer); PROMPT cite-strict-v1;
  full 12-call run: 8/10 answered, 0 hallucinations, refusal demo fired (R1/R2), Q5+Q10 refused.
- Main-session diagnosis (probe05): Q5 = retrieval miss (penalty/fine clauses rank out; "penalties/violating"
  matched nothing pre-stem); Q10 s.46 legal-aid chunk IS present (0.202) — LLM false refusal / variance.
- Fix round (correct layer, all inDocs): (1) stem()/stem_preprocess() in src/retrieve.py (ies→y, ion, ing, ed,
  es/s; fixpoint loop; stemmed stopwords) — penalties→penalty, violating/violation/violations→violat,
  discriminating/discrimination→discriminat; (2) ask() k=2→3, top_n=4→6 (fragment context);
  (3) act_ref/fact_ref rewritten (line-start + glued mid-line headings, subsection "(2)" excluded,
  member-list labels e.g. cl. 10,11 / Section 19,17,20, >4-clause arrangements → "general") — fixes Q6's
  "section 11(1)"@[cl.2] mislabel → cl.11; (4) prompt cite-strict-v2 (claim-number==tag-number, merged-tag
  ban with examples, subsections-aren't-clauses); CITE_TAG_RE accepts comma lists.
- Manual verdicts (v1 answers): Q2/Q3/Q4 PASS (Q3's 5%-quota truncation fixed by deeper context);
  Q6 FAIL (wrong tag, fixed), Q7 FAIL ("[Act cl. 16 cl. 17 (1)]" + "Section 18"@[S19] + double tag),
  Q9 PARTIAL (3× s.17 genuine equality text PASS; dignity@[s.33] misattributes s.34 TOC-line chunk),
  Q1 open (N100k "section 1(2)" needs chunk-quote proof at re-run), Q5 refusal = correct strict behavior
  on a retrieval miss → Phase 06 (dense/hybrid or query-expansion; no synonym hack = test-set tuning).
- Reviewer (ship-review, NOT-SHIPPABLE pending evidence): confirmed units (stem pairs, cl.11 fix, tag
  regex), blast radius (Act 33/62, Fact 27/48 labels changed; cl.31 stable), traps clean (no key in repo,
  raws untouched, SAMPLE never loaded); caught stemmer non-convergence (fixed: single ion rule + fixpoint)
  + inline-fallback "(" guard (fixed) + LOST v1 JSON (my --no-llm overwrote transcript — recovered text
  dump to scripts/test_phase02_results_cite-strict-v1_2026-09-08.txt; RULE: LLM runs → versioned files,
  dry runs → --out). Phase 01 bench still PASS post-stem (mean 0.293, Q9 0.178).
- BLOCKED: free-tier 20/day exhausted (executor 12 + main 8). Q8/Q10/R1/R2 PENDING (honest, never faked).
  After reset: `C:\conda-envs\drlca-rag\python.exe scripts\test_phase02.py --out=scripts/test_phase02_results_cite-strict-v2_<date>.json`
  (12 calls, 6s spacing) → manual verdict table (Q1 N100k proof, Q9 dignity, Q5 refusal layer) → exit call.

## 2026-09-08 — Phase 03 DONE (verify + implement + review; ship-with-notes)
- Verification (all official sites, 2026-09-08): 10/10 rows VERIFIED with corrections; 4 website values were
  wrong (DRAC dracnigeria.org→drac-ng.org DEAD; TAF →tafafrica.co; DSFN →downsyndrome.org.ng; NAB/NNAD/SCIAN
  had umbrella jonapwd.org.ng → own sites nigeriaassociationoftheblind.org / nnadeafhq.org / scianigeria.com).
  Changed phones: JONAPWD +234-(0)9063322622, 09115970958; CCD +234 815 720 5555 + toll-free 0800 2236 443;
  TAF 0806 673 1702, 0806 789 8481; NAB +2348038078210 et al; NNAD +2348030820991 (SMS/WhatsApp only);
  Irede +2347003106060; DSFN +234-803-228-5545, +234-913-712-1182; SCIAN 08072914207;
  MANI 08091116264, 08111680686 + crisis WhatsApp. Changed emails: DRAC info@drac-ng.org, JONAPWD
  info@jonapwd.org, TAF info@tafafrica.co, NAB/NNAD/SCIAN own-domain, DSFN Hello@downsyndrome.org.ng,
  MANI info@mentallyaware.org. PRUNED: Leprosy Mission (nothing confirmable on official pages),
  Sightsavers (no Nigeria phone published). NAB/NNAD medium-confidence (contact pages 404'd fetch day;
  agreeing official-domain snippets) — RECHECK stamp in test output, 3-month re-verify.
  Lesson: domain freshness must be checked, not assumed — "verify against the row's website" alone misses moves.
- Implement: with_helplines() on ALL paths (banner first, byte-exact numbers); load-time placeholder guard
  (empty/0803-style/0000-000 → ValueError); unknown → helplines+JONAPWD, never empty; FUZZY_CUTOFF 0.6
  (0.5 let gibberish "martian" 0.588 route to Irede; genuine misspellings score 0.75-1.0); substring hits
  suppress fuzzy rows (flag means fuzzy-decided); location-priority L2 (visual+Abuja→TAF over Lagos NAB).
- Matrix: 16/16 cells + 7/7 statics PASS (6 disabilities × Lagos/Abuja/Kano/rural + 5 misspellings +
  2 unknowns). Reviewer confirmed + adversarial: Pidgin "blind pikin Kano"→NAB no crash; Kano-only→JONAPWD.
- Residual (fast-follow, Phase 04): single-token "death"→MANI (0.667) and "blend"→NAB (0.8) still clear 0.6 —
  the playbook's named trap. Mitigation designed: router confirms whenever meta.fuzzy_fallback is True;
  display top-k not top-1 (L2: blind Abuja user should see NAB second).

## 2026-09-08 — Phase 04 DONE (keyword router 10/10, reviewer fixes applied)
- Router (src/router.py): LEGAL_CUES vs HELP_INTENT_CUES + HELP_ENTITY_CUES (entity-only never routes;
  multi-word ×2; multi-hit blanks span against double-count). Tie/zero → clarifying question, never guess;
  both-signal unequal → dual primary+secondary. needs_confirmation + did-you-mean whenever
  ngo meta.fuzzy_fallback (Phase 03 residual wired); top-k-not-top-1 docstring for Phase 05 UI.
- Matrix 10/10 (exit 8): 4 pure-legal, 4 pure-help, 2 mixed/dual (incl. Pidgin "wetin be my right...").
  Latency mean ~0.6ms (budget 50ms) — keyword-vs-LLM decision: keyword suffices, LLM stretch rejected,
  Gemini quota preserved for Phase 02 re-run.
- Reviewer (ship-with-notes) + main-session fixes: (1) anchored ALL single-word cues (\blaws?\b etc.) —
  "kill all lawyers"→clarify (was confident legal via "law" in "lawyers"); same fix caught latent
  "bright"→rights and "defines"→fines; (2) bare generic singletons (help/where/...)→clarify while content
  singletons ("discrimination") still route; (3) tie policy explicit: any tie clarifies (documented —
  confident misroute costs more than one question). 10/10 retained after all fixes.
- Phase 05 notes: render primary/secondary literally ("treated as X [switch to Y]"), full top-k + banner,
  gate contact actions on needs_confirmation; "hearing impared Kano"-style typos reach fuzzy only with
  an intent cue — UX copy should nudge intent words.

## 2026-09-08 — Phase 05 DONE (app.py + live browser verify + review fixes)
- App (repo-root app.py, ~490 lines, Spaces-lean: import-time only stdlib+pandas; sklearn/streamlit/mic
  deferred; no rapidocr/onnx/faiss in answer path; secrets env-only): labeled input + 3 buttons
  (Legal / Help / Auto-route; explicit overrides router) + plain-language checkbox (threads Phase 02
  plain flag; caption shows prompt version) + sidebar contrast/font-size CSS + linear layout.
  Helplines banner at top AND above every answer (clarify/refusal/LLM paths incl.).
  Routing trap "treated as X [switch to Y]" (misroute = one click). Help renders full top-k with fuzzy
  confirm prompt + "please confirm" badge; legal renders excerpts with citation tags + scores, never stripped.
  LLM strictly in collapsed default-OFF expander with quota-error explanation (no traceback).
  Voice: read-aloud via Web Speech API (client-side, zero server cost); mic via streamlit-mic-recorder
  (installed in drlca-rag only) with graceful text-fallback. st.cache_resource on module-level loaders.
- Verified live (Chromium via Playwright, main session): legal Q → LEGAL trap + [Act cl. 16,17] excerpts;
  "Find blind support in Lagos" → NAB org card; 360px viewport screenshot: banner without scrolling.
  scripts/test_phase05.py 44/44 (banner order, tags, refusal, clarify, plain threading, top-k, trap,
  cache, LLM shape, voice helpers, CSS/labels); boot HTTP 200; bench/03/04 suites + Phase02 dry-run green.
- Reviewer (ship-with-notes) + fixes: mic-fallback missing return (would TypeError without package);
  cache on inner fn → module-level loaders; dead llm_opt_in key removed. Accepted deviations: 3 buttons
  (auto-route explicit), fuzzy shown-with-badge (no contact actions exist to gate).
- Human-only left: NVDA pass, physical keyboard-only run, live mic/read-aloud + denial states, Spaces
  cold-start timing. Plain nuance: checkbox affects generation prompt, not offline excerpt wording.

## 2026-09-08 — Phase 05 styling pass (dark-mode fix + watermark + skill install)
- Skill: `developing-with-streamlit` copied Claude→opencode global
  (`C:\Users\TOSHIBA\.config\opencode\skills\`; discover.py can't see prefix envs — read version-matched
  refs directly from the installed package `.agents/skills/.../references/theme.md` + design.md).
  Ruling applied: colors/fonts/radius in `.streamlit/config.toml` (light+dark+sidebar, Nigerian green
  #1a7f37/#3fb950, system fonts only), custom CSS = spacing/type/watermark/responsive only.
- Dark-mode bug (user screenshot): hardcoded light CSS vs auto dark theme → invisible button/sidebar text.
  Fixed by moving ALL color to config.toml; dark render re-verified by screenshot.
- Leaked-UI bugs found in dark screenshot: (1) bare-string "docstring" after WATERMARK_IMAGE_URL rendered
  as paragraph by Streamlit magic → must stay a # comment; (2) split `<div>`/`</div>` markdown calls leaked
  "(" via sanitizer → single-call banner wrapper with **/backtick→HTML conversion (markdown dies inside
  block HTML); (3) watermark invisible: z-index:-1 trapped by Streamlit stacking contexts → z-index:0 +
  content lifted (block-container/sidebar z-1); (4) static serving opt-in (enableStaticServing, off by
  default in 1.63) → enabled; (5) veil too heavy (0.55/0.30 → image contributed ~3%) → 0.10/0.18.
- Watermark: "Physically challenged basketball players" (Onwuka Glory, CC BY 4.0, Wikimedia Commons;
  empowering framing chosen over begging photos), bundled at static/watermark.jpg (1280px, 360KB —
  deterministic offline + Spaces; hotlink dropped after sandbox fetch fail). Sidebar attribution caption.
- Suite now 69 asserts (config sections, hex-scan gate, watermark/veil/attribution/mobile); all PASS.
  Light-mode final look left for user eyeball (their browser is light); veil is symmetric-safe.

## 2026-09-09 — Phase 02 FULL v2 re-run DONE (quota reset, 12/12 LLM calls OK)
- Preflight: key present (39 chars, value never printed); live list-models confirms
  `models/gemini-2.5-flash` still valid (54 models; no new retirement); 1-token probe
  QUOTA_OK (37 tokens total). Bench PASS (mean 0.293, Q9 0.178, 58/58 clauses).
  Dry-run `--no-llm` to versioned `test_phase02_dryrun_cite-strict-v2_2026-09-09.json`
  (transcript rule kept: dry runs never overwrite LLM files).
- Full run: `scripts/test_phase02_results_cite-strict-v2_2026-09-09.json` (12 records,
  0 llm_errors, 6s spacing). 8/10 answered with cites; Q5+Q10 refused (llm-no-answer);
  R1/R2 refused (llm-no-answer, byte-exact REFUSAL_MESSAGE ×4 total).
- Manual verdicts (answers read vs retrieved chunk text):
  Q1 PASS — N100k chunk-quote PROVEN (factsheet Section 1 chunk: "an individual is liable
  to pay a N100,000 fine… section 1(2)"; Act cl.1 chunk holds "(2)…liable on conviction…",
  N100k tail in cl.2 chunk). Q2/Q3/Q4 PASS. Q6 PASS — fix confirmed ("Section 11(1)"
  now `[Act cl. 11]`, v1's cl.2 mislabel gone; factsheet `Section 10,11` whole-tags).
  Q7 PASS w/ note — merged-tag ban holds (no `[Act cl. 16 cl. 17 (1)]`); sentence numbers
  drawn from within whole tags (`Section 17…[Factsheet Section 19,17,20]`);
  `Section 18/19…[Act general]` leans on the 0.440 multi-clause arrangement chunk.
  Q8 PASS (first LLM answer, `[Factsheet Section 6,7]`).
  Q9 PARTIAL — 3× s.17 equality claims genuine (chunk holds "equality of rights…",
  "sanctity of the human person…dignity"); dignity claim STILL misattributed:
  "Right to dignity…[Constitution s. 33]" but chunk is a TOC line ("33. Right to life.
  34 Right to dignity…") — correct tag is s.34. The one citation-accuracy miss.
  Q5 = correct refusal (above-gate hits all off-topic: s.36/s.143/s.188/fact-general;
  penalty clauses don't surface → Phase 06 retrieval material, no synonym hack).
  Q10 = FALSE refusal (LLM variance, 2nd occurrence): s.46 chunk at 0.219 DOES hold
  legal-aid text ("indigent citizen…legal practitioner…legal aid is real") yet the
  strict layer refused. Retrieval OK → prompt/LLM layer follow-up (retry-once variance
  check belongs to Phase 06, not a Phase 02 blocker).
- Mechanical: all cite_check number_ok=True; 0 merged tags (regex scan); 0 invented
  section numbers; no key material in transcript. Exit: [~] 8/10 cited (Q5 correct,
  Q10 false refusal logged) · [x] 0 hallucinations (1 misattribution, not invention) ·
  [x] refusal demo (gate + LLM layers both exercised: R1/R2 via LLM layer; gate layer
  proven by design/MIN_SCORE calibration).

## 2026-09-09 — Dark-mode residual FIXED (alert surfaces opaque in dark theme)
- Repro (Chromium, live app :8501, in-menu theme switch): walked initial, legal answer,
  LLM expander closed/open/generated, help org cards, clarify, refusal. All readable
  EXCEPT stAlert boxes: clarify ❓ + refusal 🚫 rendered pale-yellow #ffffc2 text on
  translucent rgba(255,255,18,0.2) over bright photo patches — washed out (screenshot).
  Mic-recorder/expander/slider/tooltip/caption/code/links all readable; no primary
  buttons exist (all secondary), so the white-on-#3fb950 note stays precautionary.
- Root cause: Streamlit themes alerts translucent assuming a solid app bg; our
  watermark photo breaks the assumption in dark theme only (light: dark text on
  light-amber, fine). Veil (0.10 white/0.18 black) can't mute bright spots without
  hurting light mode — fix is alert-scoped, not global.
- Fix (token/CSS layer, no light hardcodes): (1) client-side theme watch inside the
  read-aloud components.html iframe — samples `.stApp` bg luminance, toggles
  `body.drlca-dark` (lum<0.4; dark #0d1117→0.065, light→1.0), try/catch + 1s interval
  so menu switches apply without iframe remount (parent access is same-origin;
  denial degrades to status quo). (2) dark-only override: alert surfaces opaque
  #45491f (= 0.2 amber over config [theme.dark] secondary #161b22) + text #ffffc2
  (pair 9.1:1 AAA) + border #30363d (dark borderColor). Light mode byte-identical
  (override scoped to body.drlca-dark). Bonus: iframe body transparent — the white
  strip behind "Read answer aloud" in dark mode is gone.
- Verified live: dark clarify + refusal alerts compute to rgb(69,73,31) opaque with
  screenshots; light refusal back to rgba(255,255,18,0.1)/dark text + bodyDark=false.
  Suite 69→80 asserts (theme-watch marker/gate/guard, transparent body, override
  scope/tokens/lineage, base-CSS hex gate still clean, veil unchanged). No src/
  changes → bench/03/04 unaffected (untouched code paths).
- Leftovers: stToast shares the translucency but was not triggered/verified — same
  one-line pattern if ever observed; toasts are transient, alerts were the complaint.

## 2026-09-09 — Phase 06 custom eval DONE (RAGAS-judge deferred to quota reset)
- `ragas` NOT installed (import fails) — per playbook, its langchain/openai tree
  stays out of drlca-rag; custom path taken (also $0 quota: judge needs ~30+ calls).
  New: `scripts/eval_phase06.py` (frozen design in docstring) + EXPECTED ground truth
  for all 10Q, runtime-verified against the corpus (never copied from answers;
  s.33 explicitly excluded for dignity; Act cl.10 excluded for vehicles — corpus
  says it's awareness-programmes).
- Baseline (`eval_phase06_results_2026-09-09.json`): recall 0.800 PASS (>0.75) ·
  faithfulness_audited 0.875 PASS (>0.85) · precision 0.333 diagnostic (per-doc
  merging trades it by design — reported, never gated) · coverage 0.723 FAIL and
  reverse_rel 0.667 FAIL, BOTH diagnosed as metric artifacts, kept visible:
  coverage punishes paraphrase on correct answers (transitional/transitory,
  long/five-years, exist/protect; filler 'say/does/guarantee'); reverse_rel punishes
  answers for retrieving chunks they legitimately cite but truth can't name
  ([Act/Factsheet general] have no numbers — Q1/Q4 self-cited generals missed).
  Stopped at two proxies rather than tuning a third yardstick into a pass:
  true aboutness goes to the RAGAS judge (quota reset) alongside the two-run
  flakiness check and the manual-100% re-confirmation.
- Fix A (retrieval/corpus layer, offline-verified): Constitution TOC-only fragments
  (section-title listings, no body) demoted to 'general' in `const_ref`
  (`_is_toc_fragment`: >=2 headlines + <40 body words; corpus scan: 17 fragments,
  all title-listings, 14 relabeled). Kills Q9's s.33 trap at the source — the
  '33. Right to life. 34 Right to dignity...' line can no longer be cited as s.33.
  Blast radius: ranking untouched (text identical); recall per-Q identical;
  Q9 faith_auto 1.000→0.750 now AGREES with the audit (mechanical check caught up);
  means unchanged (0.800/0.875). Post-fix file: `eval_phase06_results_fixA_2026-09-09.json`.
  Answer-level effect (dignity re-cites to s.17, which genuinely holds dignity text,
  or drops) awaits the next LLM run — predicted, never claimed.
- Misses by layer (all 10Q accounted): Q5 retrieval (penalty clauses exist at Act
  cl.1/2/8/9,10/13/29,30 — verified in corpus — but rank out; dense/hybrid or
  query-expansion queued, no synonym hack) · Q9 corpus/ref (fix A applied) ·
  Q10 LLM variance (s.46 holds legal-aid text at 0.219, strict layer refused 2nd
  time; retry-once queued) · Q8 retrieval-partial (Act cl.6,7 just under gate;
  answer PASS via factsheet — documented, no action) · Q2/Q3/Q4/Q6/Q7 PASS,
  Q1 PASS (N100k proven).
- Regressions: bench PASS, 03 (16/16+7/7), 04 PASS, 05 (80/80) — all green post-fix.
- Exit: [x] recall>0.75 recorded · [x] audited faithfulness>0.85 · [~] answer
  relevancy: custom mixed (judge pending) · [ ] manual-100% re-confirm (needs LLM
  rerun post-fix-A) · [ ] two consecutive runs (quota). Phase 06 IN PROGRESS.

## 2026-09-09 — Post-fix-A LLM run: 8/12 answered, quota died mid-run (20/day CONFIRMED)
- File: `scripts/test_phase02_results_cite-strict-v2-fixA_2026-09-09.json`. The API
  429 names the limit verbatim: GenerateRequestsPerDayPerProjectPerModel-FreeTier,
  quotaValue 20, gemini-2.5-flash. Q1-Q7 answered, Q8+Q9 hit 429 (PENDING, honest),
  Q10 answered, R1/R2 429-pending. Budget lesson: full 12-call passes must start
  the day (probe + pass = 13); judge runs (~30) need a dedicated quota day.
- Verdicts (8 answered, all cite_checks True, 0 invented numbers): Q1 PASS (N100k +
  s.1(2), tighter than v2) · Q2 PASS · Q3 PASS · Q4 PASS + padding note (core
  cl.31/Presidency stable; run adds cited-but-unasked certificate S22/cl.21,22 +
  powers S39 — verbosity variance, no hallucination) · Q5 correct refusal (3rd run
  running: retrieval miss confirmed again, Phase 06 dense/hybrid material) ·
  Q6 PASS (cl.11 stable 3 runs) · Q7 PASS (merged-tag ban holds 3 runs) ·
  Q10 PASS — VARIANCE RESOLVED: quotes verbatim from the s.46 chunk ("indigent
  citizen…legal practitioner", "legal aid is real"); s.39 tag grounded in that
  chunk's s.46 TOC-overflow line. Refuse,refuse→answer across 3 identical contexts
  = LLM-layer flakiness proven and now settled correct.
- Two-run check (v2 vs fix-A, 7 overlapping answered): verdicts stable; only
  variance is Q4 padding + Q10 flip-to-correct.
- Still pending (next reset): Q8/Q9/R1/R2 retry (4 calls — Q9 is the fix-A answer
  confirmation) + RAGAS-judge day. Eval script stays pointed at the complete v2
  transcript until a complete post-fix transcript exists (no partial re-pointing).

## 2026-09-09 — White-text/sidebar readability FIXED (Brave report, scrims + stacking)
- Report: white text unreadable + side panel text unreadable (Brave). Reproduced in
  Chromium dark+light. Two defects, one root area:
  (1) Bright photo patches behind translucent surfaces: white dark-theme body text
  (esp. long excerpt paragraphs) and all sidebar labels sat on faces/sky.
  (2) REAL BUG underneath: sidebar photo bleed-through despite an opaque computed
  bg. Root-caused via DOM walk: the watermark div lives INSIDE stMainBlockContainer
  (position:relative, z-index:1), so its z-0 is local to the MAIN stacking context
  -- which paints above the sidebar by DOM order. My z-1 sidebar rule never had a
  chance; Streamlit's own section rules also beat my position rule in the cascade.
- Fix (app.py CSS only, tokens mirrored from config.toml): sidebar z-index 2
  !important (above the main context) + opaque sidebar bg per theme (#f6f8fa /
  #010409) + main sheet .block-container (0.88 alpha white/dark) + fully opaque
  excerpt cards (.drlca-answer #ffffff/#0d1117). HC overlay pins all three black
  (else light sheet + forced-white text). Photo survives at the margins; spec
  prioritizes accessibility over aesthetics. Font UNCHANGED by design (system
  sans-serif, no downloads; contrast -- not typeface -- was the defect).
- Incidents while verifying: (a) height=0 iframe never mounts -- watcher moved to
  height=1 top-of-run iframe so body.drlca-dark exists on the initial screen too;
  (b) srcdoc race: script ran before <body> parsed (console TypeError, dark
  overrides silently dead) -- wrapped in DOMContentLoaded-ready + try/catch;
  (c) first verification round ran against a STALE server (mixed-version CSS) --
  restarted :8501, re-verified everything after.
- Verified live: dark sidebar element-shot solid black, labels crisp; dark cards
  opaque (#0d1117) with white text; light sidebar #f6f8fa + white cards; HC mode
  coherent (black sheets/cards, white bold text, no white-on-white). Suite 80→94.
  Note: in HC mode the black app bg trips the luminance gate (bodyDark=true) --
  harmless: dark rules + HC !important compose to the same AAA palette.
- Server restarted on :8501 with current code; user's Brave tab needs a reload.

## 2026-09-09 — HC buttons white-on-white FIXED (Brave screenshot report)
- Report: circled mode buttons showed emoji-only on white (labels invisible) in
  high-contrast mode. Cause: HC overlay forced all text white but button
  BACKGROUNDS stayed themed -- light-theme white buttons went white-on-white
  (same gap for translucent alert surfaces). Fix in the HC overlay block:
  buttons → black bg + white text (border was already white); alert surfaces →
  black bg + white border. Verified live in HC+light (user's combo): black
  buttons/borders/labels, black clarify alert, computed bg/text pairs all
  #000/#fff. Suite 94→96. Server restarted; Brave tab needs reload.

## 2026-09-09 — Watermark more visible (user request; readability preserved)
- Bumped `.drlca-watermark` opacity 0.14 → 0.24 (~70% stronger photo presence).
  Safe because text no longer sits on raw photo: opaque sidebar + 0.88 main sheet
  + opaque excerpt cards (previous session). Screenshot-verified both modes: light
  shows players/court/wheelchairs clearly with crisp dark text; dark shows the
  photo with crisp white text; sidebar solid + labels sharp in both. Suite still
  94/94 (opacity assert updated). Server restarted; Brave tab needs reload.

## 2026-09-09 — Phase 07 deploy prep (no quota needed)
- requirements.txt slimmed to runtime (streamlit/pandas/sklearn/google-genai/
  mic-recorder/SpeechRecognition; faiss/onnx/rapidocr/pymupdf REMOVED — grep
  proves zero imports in src/ + app.py). Clean-venv proof (Python 3.11, temp dir):
  pip install clean + all imports OK (1.63.0/3.0.5/1.9.0) + offline legal smoke
  (6 excerpts) + help smoke (3 records, helplines first) + `streamlit run` boot
  HTTP 200 on :8503. Spaces needs Python >=3.10 (pandas 3 floor) — noted in README.
- NAB/NNAD RECHECK (were medium-confidence): NAB site live + active 2026 news;
  Contact page confirms byte-exact email info@nigeriaassociationoftheblind.org,
  phones +2348038078210/+2348026615415/+2348080502407, Lagos (NERDC Jibowu) +
  Abuja offices → HIGH. NNAD footer confirms +2348030820991 (SMS/WhatsApp),
  nnadeaf@nnadeafhq.org, Jabi Abuja address → HIGH. CSV unchanged (values already
  matched). Full directory: 10/10 verified, re-verify ~3 months (stamped 2026-09-09).
- README rewritten (setup/usage/deploy/status/architecture/data-verification);
  ASCII architecture in-repo (diagram image deferred — ASCII satisfies playbook).
- Spec Quick-Reference audit (RAGNGO.txt): free-platforms [x] · docs loaded+chunked
  [x] · NGO 10+ orgs [x] · RAG+citations [x] (8/10 + logged misses) · connector
  [x] · router [x] 10/10 · accessible UI [x] (NVDA/mic-live = human checks open) ·
  RAGAS [~] custom done, judge queued · Spaces deploy [ ] repo prepped, push+smoke
  need owner creds · demo video [ ] owner records · README [x] · journal [x] ·
  LinkedIn [ ] owner posts. Stretch (Pidgin/Yoruba/Hausa/Igbo, offline, feedback,
  WhatsApp): all deferred-with-reason (quota/scope) — none silent.
- Git: initialized, .gitignore (caches, venvs, secrets, traces, _SAMPLE excluded
  from tracking? NO — _SAMPLE stays tracked as dev artifact, app never loads it;
  raw PDFs tracked for reproducibility), full `git log` + content key audit clean
  (no secret values; key lives in env only). Committed locally; push + Space
  creation + smoke + video are owner-side (need account creds / mic / voice).

## 2026-09-10 — fixA2 COMPLETE 12/12 (agentic: explore→general→reviewer→ship)
- Probe QUOTA_OK, full 12-pass → 10/12 (Q3+R2 transient 503 high-demand, not 429), targeted retry → both first-attempt OK. File `scripts/test_phase02_results_cite-strict-v2-fixA2_2026-09-10.json`, ~13/20 quota, no judge same day.
- Verdicts: Q9 fix-A CONFIRMED (s.17 x3+general, zero s.33) · Q3 cl.29,30 5% · Q8 five-years [Factsheet 6,7] · Q10 PASS s.46 x2+s.39 note · R1/R2 verbatim DRAC (08000-3000-100 / 08000-3000-10) · Q5 correct-refusal x4 (top s.36 0.14, penalty clauses absent).
- Reviewer: SHIP (12 genuine rows, pointer still at v2 until verdict table). Notes: Q3 thin 2-cite, Q8 single-sentence, Q10 extra s.39 outside EXPECTED, Q8 top-hit s.308 but answer correctly Factsheet — strict-prompt win. Provenance: full-pass+patch, not 12-fresh (HANDOFF asked whole-pass; document in verdict table).
- Re-review SEND-BACK (honest dispositions): Q10 3rd claim `[s.39]` misattributes s.46 High-Court jurisdiction text — s.39 corpus is freedom-of-expression + trailing "46 Special jurisdiction" TOC line, so mechanical overlap passes but semantics fail (same class as Q9 s.33 trap). Verdict Q10 PARTIAL. Q9 s.33 removed but s.34-body still unretrieved (recall 0.5, dignity sentence cites general). reverse_rel 0.630 FAIL gated>0.80 recorded as FAIL (drivers Q3/Q8/Q10 concise answers; proxy punishes short-correct) — RAGAS judge arbiter on separate quota day, not dismissed.
- Next: verdict table → swap eval pointer → two-run check + manual-100% → RAGAS-judge day (~30 calls, separate day). Owner-side unchanged: HF Space + demo GIF + human gates.

## 2026-09-10 — Render LIVE via CLI (HF Spaces dropped)
- `winget install Render.CLI` (v2.27.0; binary was missing, only stale `~/.render/cli.yaml` with expired token) → user ran `render login` (browser) → `render services create --name NGOdisabilityRAG --type web_service --repo ... --branch main --runtime python --plan free --build-command "pip install -r requirements.txt" --start-command "streamlit run app.py --server.port $PORT --server.address 0.0.0.0" --env-var PYTHON_VERSION=3.11.0 + GOOGLE_API_KEY (from env, never printed/committed)` → `srv-dah26opt0dsc73e9a350`, https://ngodisabilityrag.onrender.com, first deploy live ~1 min on `fe618ab`.
- HF finding (web-verified): Streamlit SDK deprecated 2025-04-30, now Docker template = compute = PRO required; Static free but can't run Python; Gradio free only ≤2 ZeroGPU (rewrite cost). Render free (750h/mo, 15-min sleep, ephemeral FS — fine, corpus prebuilt) is the spec-compliant $0 variety link; Streamlit Cloud still optional 2nd.
- Live smoke (browser, zero quota): HTTP 200, banner both helplines, "blind Lagos" help query → helplines-first + NAB + fuzzy-confirm + contacts + HELP-route note. 3-legal live smoke queued (excerpts offline-safe; AI expander = quota day).

## 2026-09-10 — Session wrap: everything green committed, quota + owner gates left
- Progress today: fixA2 12/12 (probe + full pass 10/12 on transient 503s + targeted Q3/R2 retry first-try OK, ~13/20 quota) → verdict table (Q10 s.39 PARTIAL caught by reviewer) → flagged eval (recall 0.800 / faith 0.967 / reverse 0.630 FAIL recorded) → pointer swap → suites re-verified (05 now 96/96) → Render CLI installed, service created free, live-verified in browser → README link → pushed `b2b8dbc`, tree clean, latest deploy live.
- What's left: (1) QUOTA — RAGAS-judge day (~30 calls, fresh day; decides reverse_rel + s.39 + s.34) + AI-expander/3-legal live smoke; (2) OWNER — demo GIF, NVDA/keyboard/mic gates, LinkedIn, optional Streamlit Cloud 2nd link; (3) CODE (post-judge) — fix-B decision on TOC-trap cites (constrain cites to retrieved refs?) vs documented PARTIALs. Nothing else blocked.

## 2026-09-10 — Full stale-sweep amended (explore audit → edits → ship-with-fixes review → pytest proof)
- 30+ stale lines fixed across spec + docs + code comments: HF Spaces → Render everywhere (spec, README deploy, STATUS, HANDOFF, 03/05/06/07 playbooks, AGENTS.md non-negotiables, requirements.txt, app.py + config.toml comments); video → GIF; 05 80/94 → 96/96 (pytest proof this session: 96 asserts, 03 16/16+7/7, 04 ALL PASS); eval pointer + exit boxes current; STATUS corpus-dupe removed; 05 playbook dup paragraph removed.
- Reviewer notes honored: cold-wake explicitly "not yet observed"; HANDOFF carries NAB/NNAD HIGH tag; 06 remaining = judge run only. Left as dated history (frozen): old journal entries mentioning Spaces/video. No secrets in diff; no spec relaxation (purpose/free-tier/citations/NGO/a11y intact).

## 2026-09-10 — Free-tier upgrade plan documented (`docs/phases/08_retrieval_upgrades.md`)
- Research synthesis (2026 industry consensus, multi-source): RAG quality = retrieval engineering — chunking → hybrid → rerank → query transform → eval-gated iteration. Long context did NOT kill RAG (125x cost gap, ~60% multi-fact recall past 32–128k, silent failures); chunk-level citations are a retrieval artifact — our legal spec makes RAG the only compliant architecture. Thin-orchestration trend validates custom `src/`; RAGAS-offline + live-tracing is standard (our custom-proxies-first is defensible, not a hack). Contextual retrieval (−49% failures) maps to our TOC-trap class.
- Plan: synonyms (0 quota) → cite-constrain fix-B (0 quota) → judge (fresh day ~30 calls) → local ONNX rerank (0 quota) → dense hybrid via Colab (runtime offline) → cache + rule-prefixes. Frozen 10Q + unchanged eval throughout; quota ledger per run. Full detail in the playbook.
- Offered to execute Step 1 (synonym map) on go-ahead.

## 2026-09-10 — Hello-bug fixed (greeting path, live-verified)
- Report: "hello" → refusal wall (reproduced live on Render via Legal button). Cause: no greeting handling anywhere; forced buttons bypass the router's clarify fallback straight into refusal.
- Fix (offline, zero quota): `is_greeting()` in `src/router.py` (bare greeting words only; content like "hello, what are my rights?" routes normally) → `resolve_mode()` returns `greeting` (wins over explicit buttons) → `run()` renders greeting panel + read-aloud, no retrieval/LLM. Lesson: first fix attempt tested `resolve_mode` but `run()` had inlined routing — live browser test caught it; routing now flows through the single seam.
- Proof: 04 ALL PASS (+12 greeting probes), 05 104/104, 03 green; pushed `dd5aeb1`, Render live, browser-verified greeting panel with helplines above, zero console errors.
