# Post-launch roadmap (2026-10-15): what "complete" means for DRLCA, H0–H8

**Status: PLANNED. Docs only: no code, zero quota.** Written the day of launch (`ab5a0b6`, deployed
and live-smoked 2026-10-15), after every phase in the E → G → F order closed. Each H step below
carries its own branch, its gate written **in advance**, its quota cost, the parts only the owner can
do, and a "do not" list. A fresh session should be able to run any step from this file plus
`CLAUDE.md` alone.

**Standing rule for every step: a push to `main` redeploys to real users on Render. That is the
user's call, every time.** Each H step ends at "merged to local `main`" at most, unless the user
says otherwise in that session. Prior authorisations do not carry forward.

## Assessment (2026-10-15)

### What is strong, with the evidence

| Strength | Evidence |
|---|---|
| Live, $0, offline by default | Render free tier; retrieval, excerpts, NGO lookup and router make zero network calls (`test_phase09_ops.py` 51/51, zero network). Gemini sits behind an opt-in expander that defaults OFF. |
| Evaluation discipline | Blind held-out sets (`test`, then `test2` authored and committed before any arm touched it, E5.2); every ship gate fixed before the number was seen; four retrieval upgrades measured and three declined (E2a, E3a, F0), with declined code archived off `main`. |
| Refusal safety | `calibrate_refusal.py` 0 disagreements on 212 probes; 0 false refusals on frozen-10 / dev / test / test2. G6: 10/10 lay and Pidgin generator probes answered, 0 refusals, 0 fabricated tags. |
| Citation integrity | G2 `cite-strict-v3`: 0 unretrieved tags, faithfulness_audited 1.000; judge 10/10 relevancy and faithfulness; G4 0 cross-turn drift. |
| Helplines-first invariant | Asserted on source adjacency in `test_phase05.py` (137/137); seen live on the 2026-10-15 smoke. |
| Corpus provenance | Act OCR corrections are evidence-carrying and human-signed (`act2018_v2_corrections.json`, cl.1 / cl.12 / cl.20, verified by Jerry); the corpus sha is pinned; the OOV bridge hard-fails on a stale corpus. |

### Where it is incomplete, with the evidence

| Gap | Evidence | Step |
|---|---|---|
| **No CI before an auto-deploy** | No `.github/` directory exists. Every suite is run by hand; a push to `main` deploys whether or not anything was run. | H0 |
| Known small bugs | The relative "that" in "an organisation that can help me" is read as an unbound pronoun (seen on the live smoke, 2026-10-15). A byte-identical duplicate excerpt pair (`[Constitution s. 4]`) is shown twice (recorded 2026-09-20). | H1 |
| **Accessibility never tested with real assistive tech** | It is a spec requirement, but no NVDA run, no keyboard-only run and no live microphone check has been recorded since Phase 05. Only script-level asserts exist. | H2 |
| NGO connector under spec | `data/ngo.csv` holds **10 orgs** (11 lines with header), the spec minimum. There are no filter or sort controls (spec Feature 2). | H3 |
| **The offline path does not refuse off-topic questions** | `MIN_SCORE = 0.10` is a weak-overlap floor: off-corpus questions clear it 8/8 on test2 (E5.3), as designed. Only the opt-in LLM layer refuses semantically, so a default-path user asking something the law does not cover gets excerpts anyway. | H4 |
| No language support beyond English | Spec Feature 1 names Yoruba / Hausa / Igbo. Pidgin is measured only by 20 report-only probes (`register_probes.json`, 0.650 shipping). | H5 |
| **No legal-expert review** | Every "correct" in the record is a corpus-ref match or an LLM judge. No lawyer or DPO advocate has read an answer. | H6 |
| No real-user signal | No telemetry and no feedback control. M2 (dense) and F2 (fine-tune) were both deferred to "post-launch query logs" that nothing collects. | H7 |
| Retrieval ceiling, corpus breadth, maintainability | recall_strict 0.734 / 0.613 / test 0.647 / test2 0.629; term-level lexical levers are exhausted (E2, E3, E4a, F0). Three documents only. `app.py` is large, and `CLAUDE.md` / `STATUS.md` carry long history. | H8 |

**Reading.** Retrieval is no longer the binding gap. Four rounds of lexical and static-semantic
levers have produced one ship (E4a, +2 test questions), and the next real lever (dense, or a
fine-tune) is gated on real-user data the system does not collect. The items that most limit
whether the system can be **trusted and recommended** are credibility items: a CI gate before
deploy, real assistive-tech testing, and a lawyer's read. That is why H0–H2 lead and H6 starts
early in parallel, ahead of further retrieval work.

## Recommended order

**H0 → H1 → H2 → H3 → H4 → H6 (starts in parallel, it is owner time) → H5 → H7 → H8.**

H0 is first because it protects every later deploy. H6 needs weeks of someone else's calendar, so
the agent-side preparation should happen as soon as H1 has landed, because H1 changes what the
reviewer would see.

---

## H0 — CI gate (offline suites on every PR and push)

**Goal.** No change reaches `main` without the zero-network suites going green on a clean machine.
**Branch** `phase11/h0-ci`. **Quota** zero. **Owner-only:** merging, any push to `main`, and
(optionally) turning on GitHub branch protection for `main`.

**Files.** New `.github/workflows/offline-suites.yml`; possibly new `requirements-ci.txt`.

**Steps.**
1. **Find out what the suites need on disk.** Read `.gitignore` and each script's inputs. `runs\`
   is gitignored, and `data/raw/` PDFs may be too. List, per suite, whether it runs on a fresh
   clone. A suite that needs a gitignored artifact is **either** dropped from CI with the reason
   written in the workflow file, **or** its artifact is shown to be committed already. **Never
   commit the GloVe file or `runs\` captures to make CI pass.**
2. **Pick the install.** First try `requirements-rag.txt` on `ubuntu-latest` + Python 3.11. If the
   OCR/ONNX/FAISS/opencv pins fail to install or make the job slow (> ~5 min install), write
   `requirements-ci.txt` = `requirements.txt` + exactly what the suites import beyond it (expected
   to be little more than `numpy`; check with a clean venv, not by guessing). Note that
   `requirements.txt` itself is never touched to satisfy CI.
3. **Workflow.** Triggers: `pull_request` and `push` (all branches). One job, steps in this order,
   each a separate step so a failure names itself:
   `python -c "import app"` → `scripts/test_phase03.py` → `scripts/test_phase04.py` →
   `scripts/test_phase05.py` → `scripts/test_phase09_ops.py` → `scripts/audit_corpus.py` →
   `scripts/bench_phase01.py`. Use `pip` caching. All scripts already exit nonzero on failure.
4. **Zero network, enforced.** No `GOOGLE_API_KEY` secret is defined for the workflow, and none is
   referenced. `test_phase02.py`, `judge_phase06`, `transcript_chat.py` and `probe_embed_quota.py`
   are **never** in CI. Add a comment in the workflow saying so and why (quota).
5. Open a PR from `phase11/h0-ci` (pushing a topic branch does not deploy) and watch the run.
   Opening the PR needs the user's OK, because it is outward-facing.

**Exit gate (written in advance).** The workflow is green on a PR, and a deliberately broken
commit on a throwaway branch (for example, an `assert False` added to `test_phase04.py`) turns it red
and is then deleted. Both runs are linked in Results. Merging is the user's call.

**Do not.** Add a deploy step. Add Gemini-backed suites. Change any script so it passes in CI
(fix the environment instead). Add OCR/ONNX/FAISS to `requirements.txt`. Treat a green CI as
authorisation to push `main`.

---

## H1 — Quick-win bugs

**Branch** `phase11/h1-bugs`. **Quota** zero. **Owner-only:** merge.

### H1a — relative "that" read as an unbound pronoun (`src/chat.py` `contextualise()`)
Seen on the live smoke (2026-10-15): "an organisation that can help me" was contextualised against
the previous legal turn. It was harmless there, but it pulls unrelated context into a help turn.

1. **Write the regression case first**: add one conversation to `data/eval/conversations.json`,
   **in the dev split only, never `chat_test`**, that reproduces it (legal turn, then a help turn
   using a relative "that"). Also add a behavioural assert to `scripts/test_phase09_ops.py` that
   `contextualise()` leaves that turn unchanged, plus a control assert that a genuinely unbound
   "that" (for example, "what about that?") is still resolved.
2. Fix narrowly: treat "that" directly after a noun phrase and followed by a verb or modal as a
   relative pronoun. Keep the change to that word; don't rewrite the resolver.
3. Re-run `eval_chat.py`.

**Gate.** The new asserts pass, every existing `test_phase09_ops` assert passes, and `eval_chat`
strict recall shows **no drop on any split** against the pre-change capture (take the capture
first, to `runs\h1_before\`). `chat_test` numbers are reported, not tuned against.

### H1b — duplicate byte-identical excerpt pair (`[Constitution s. 4]`)
**Prefer display-level dedupe in `render_excerpts`** (`app.py:605`): drop a hit whose
`(doc_id, ref, text)` equals one already shown, keeping the first. It is applied to the excerpt
list before the 3-inline / rest-folded split, so `INLINE_EXCERPTS` still means "3 distinct".

* A **corpus-level** fix changes the chunk stream sha, which forces `build_oov_bridge.py` (needs
  GloVe in `runs\e4_vectors\`), re-pinning `V2_CORPUS_SHA256`, and a full re-measure on every set.
  Do it only if display dedupe turns out insufficient, and document why.
* Display dedupe changes no retrieval number (metrics score the retrieved set, not the shown list).
  Confirm that by re-running `eval_heldout.py` and diffing against `runs\cl1_after\` / the latest capture.
* Add a `test_phase05.py` assert with a synthetic duplicate pair. Keep every banner-adjacency
  and 4-space call-site assert intact.

**Gate.** `test_phase05` green including the new assert, `eval_heldout` byte-identical apart from
timing lines, and the penalties query shows the duplicate once in a local `streamlit run` check.

**Do not.** Change `MIN_SCORE`, `k`, `top_n`, or chunking. Edit `SYNONYMS`.

---

## H2 — Accessibility verification

**Goal.** Turn "accessibility is a requirement" from asserted to tested, against **WCAG 2.2 AA**.
**Branch** `phase11/h2-a11y`. **Quota** zero (keep the AI expander OFF during audits).

### Automated part (the agent can do this)
1. `C:\conda-envs\drlca-rag\python.exe -m streamlit run app.py`, then audit `http://localhost:8501`
   with the chrome-devtools MCP (`lighthouse_audit` for accessibility, plus an axe-core run injected
   via `evaluate_script` from a pinned CDN build).
2. Matrix: widths **360 / 768 / 1280** × themes **light / dark / high-contrast** (plus 200% font
   scaling at 360). For each cell, audit the **empty page, one legal turn and one help turn**,
   since findings differ by state.
3. Use the `ui-geometry-audit` skill to check the watermark, sidebar and banner don't cover
   content at each width.
4. Fix what is flagged. Colors change **only** in `.streamlit/config.toml`; spacing and overrides
   go in `accessibility_css()`. Restart Streamlit after CSS edits.
5. Write `docs/accessibility.md`: a WCAG 2.2 AA criterion table (pass / fail / not applicable /
   owner-verified), the audit matrix with scores, and what was fixed.

### Owner part (the agent writes the script; the owner runs it)
Put the checklist in `docs/accessibility.md` with a sign-off line per item:
* **NVDA + Chrome**: the reading order is helplines → question → answer → excerpts; every control
  has a name; new turns are announced; the folded excerpts expander is operable.
* **Keyboard-only**: tab order reaches chat input, voice, read-aloud, the AI expander and the
  sidebar; focus is always visible; no traps.
* **Live microphone** (Chrome/Edge): dictate a legal question end to end; denied permission
  degrades to text gracefully.
* **Read-aloud** on a legal turn and a help turn: helplines are read first.
* Ideally one session with a blind or low-vision user (for example via a JONAPWD contact), recorded
  as notes rather than audio.

**Exit gate.** **0 axe "critical" and 0 "serious"** findings across the matrix (or each remaining
one justified in writing as a Streamlit-internal limitation with an issue link), and the owner
checklist signed. Lighthouse scores are reported, not gated.

**Do not.** Move brand colors out of `config.toml`. Break the linear layout (no `st.columns` for
answer content). Rename or reorder `render_turn` internals that `test_phase05` asserts on.

---

## H3 — NGO connector completion (spec Feature 2)

**Branch** `phase11/h3-ngo`. **Quota** zero. **Owner-only:** spot-checking verification evidence
and the merge.

### H3a — filter and sort controls
* Filters for **disability type** and **state**, and a sort by **name / relevance**, rendered in
  `render_help_records` (`app.py:791`), **after** the helplines banner and in linear order (no columns).
* **Replay rule:** the stored `TurnPayload` holds the records; changing a filter on an old turn
  re-filters the stored records and **never** re-runs `route()` or `find_ngo_with_meta()`
  (`replay_turn()` makes no retrieval, router or network call, and that is asserted). Widget keys
  carry the turn index so turns don't share state.
* Every filtered view still goes through `ngo.with_helplines()`: an empty filter result shows the
  helplines and a "no organisation matches; the helplines above can refer you" line, never a blank.
* Extend `test_phase05.py`: filter on a stored payload with no recompute (monkeypatch the router and
  ngo lookups to raise), helplines lead every filtered view, and the empty-result path. **Keep
  every existing banner-adjacency and call-site assert unchanged.**

### H3b — grow `data/ngo.csv` from 10 orgs to about 30
* Coverage target: **all 6 geopolitical zones**, and **at least 5 disability types** (visual,
  hearing, physical/mobility, intellectual/developmental, psychosocial; albinism where possible).
* **Every row is verified against the organisation's official site or official social channel**,
  with two new columns: `source_url` and `verified_on` (ISO date). A phone that can't be found on
  an official source is not added. Third-party directories are leads, not sources.
* **Pruned orgs listed in the `src/ngo.py` docstring are not re-added** without fresh verification
  recorded the same way, and the docstring is updated if one returns.
* `ngo.load_ngo()` must pass, since it hard-fails on placeholder or blank phones. Extend the
  `test_phase03.py` matrix to cover the new zones and types (16/16 + 7/7 today; add cases, don't
  edit existing expectations without a written reason).

**Exit gate.** `test_phase03` and `test_phase05` green with the new cases; ≥ 6 zones and ≥ 5 types
present in the CSV (assert it in `test_phase03`); every new row has `source_url` and `verified_on`;
the owner has spot-checked at least 5 rows.

**Do not.** Add an org without an official-source phone. Bypass `with_helplines()`. Recompute on
replay.

---

## H4 — Offline off-topic guard

**Problem.** On the default (offline) path, an off-corpus question gets excerpts, because
`MIN_SCORE = 0.10` is a weak-overlap floor that 100% of off-corpus questions clear (test2 8/8, by
design). The in-corpus and off-corpus cosine bands are **inverted** (see the calibration comment
in `src/retrieve.py`), so no cosine threshold can fix this. **Do not raise `MIN_SCORE`.**

**Branch** `phase11/h4-offtopic`. **Quota** zero.

**Steps.**
1. **Author a new blind off-corpus set first**: `data/eval/offtopic_h4.json`, about 20 questions
   that are plausible from a Nigerian user but outside the three documents (tenancy, land, tax,
   divorce, police bail, unrelated health questions), plus 5 near-misses that *are* in the corpus
   in disguise. Commit it **before** any measurement.
2. **Design a separate signal**, computed after expansion and before display. Candidate (fixed
   now; one retreat allowed): the **share of the query's content stems present in the corpus
   vocabulary after the shipping expansion** (hand map + OOV bridge). The threshold is chosen on
   **dev off-corpus + dev answerable only**, then frozen. The one retreat: if that signal catches
   0/5 on dev, it may be replaced once by the share of the query's content stems that occur in the
   **top hit's chunk**, under the same gate.
3. **Behaviour when it fires.** The UI shows "No matching law found for this question." Then the
   helplines (already leading the turn) and the NGO path offer. Excerpts are folded behind a
   "show closest passages anyway" expander, not deleted: a false positive must still let the user
   reach the law.

**Pre-declared gate (all required).**
* Catch **≥ 3 of 5** on the dev off-corpus rows (`questions.json`, `set == "heldout"`,
  `class == "off-corpus"`). Only then read, once each: `test` off-corpus (3), `test2` off-corpus
  (8) and the new H4 set, which must each catch **≥ half**;
* **0 new refusals** on: `calibrate_refusal`'s 212 probes, every answerable held-out question
  (frozen-10, dev, test, test2), `register_probes.json`, `smoke_user_register.json`, and every
  `conversations.json` turn.

**If the gate fails, decline**: record the numbers, archive the code on the branch, and keep the
current behaviour. False refusals deny help to PWDs; this gate leans that way on purpose.

**Do not.** Touch `MIN_SCORE` or the strict-prompt `NO_ANSWER_SENTENCE` path. Tune the threshold
after reading test or test2. Hide the excerpts entirely when the guard fires.

---

## H5 — Language support (spec Feature 1)

**Branch** `phase11/h5a-pidgin`, `phase11/h5b-lang`.

### H5a — Pidgin: register-routed arm (zero quota)
Builds on the F0 lead: the static arm took the lay/Pidgin probes 0.650 → 0.750 but lost on the
gated sets, so the hypothesis is a **routed** use (static arm only when the query is Pidgin or
OOV-heavy).
1. **Write a fresh blind Pidgin set (~20) first**, with a dev/test split and corpus-verified
   expected refs. `register_probes.json` is not reused as a gate, because it has already been read.
2. Router rule (Pidgin marker words and/or OOV share) and arm parameters are fixed in writing
   before any number. The F0 harness lives on `phase10/f0-static` at `27ed13d`; reproduce from there.
3. **Gate:** Pidgin-dev net ≥ +2, then Pidgin-test read once with net ≥ +1; the router fires on
   **0** frozen-10 / dev / test / test2 questions (or, if it fires, those questions don't drop);
   0/212; serving numpy-only, artifact ≤ 40 MB. Static-arm serving still needs F1's port and parity
   test (`docs/phases/15`).

### H5b — Yoruba / Hausa / Igbo: opt-in LLM path only (quota)
* Behind its own opt-in control, default OFF. Gemini translates the question **in** to English, the
  normal pipeline answers, and Gemini translates the answer **out**. **Citation tags are never
  translated**: they are masked before translation and restored verbatim, and the cite check runs
  on the restored text.
* The default path stays English and fully offline. **`requirements.txt` takes no translation
  model.**
* Quota: a small blind set (~5 per language, ~15 questions × 2 calls = ~30) is planned across Pacific days
  and both pools **before** the first call, with day spend logged in `HANDOFF.md`. Never fake a row:
  quota failures record `llm_error`.
* **Owner:** a native speaker spot-checks each language (≥ 5 answers each), on a sheet with
  columns meaning-preserved / partially / wrong.

**Do not.** Translate tags or helpline numbers. Make translation default-on. Add an offline
translation model to the runtime.

---

## H6 — Legal-expert review (owner-led; the agent prepares)

**Goal.** The first human legal read of DRLCA's output. **Quota:** ~0 if existing transcripts
cover it; otherwise a planned ≤ 20 calls.

1. **Agent:** export 20–30 Q&A pairs to `docs/review/h6_review_sheet.csv` (and a printable
   `.md`). Each has the question, the offline excerpts with tags, and the AI answer (from the
   versioned G2 / G4 / G6 transcripts where they exist). Spread: Act, Constitution, Factsheet,
   cross-document, lay/Pidgin, and 2 off-corpus. Columns: `correct` / `partially` / `wrong` /
   `harmful`, plus a free-text note and "what should it have said".
2. **Owner:** recruit the reviewer (a JONAPWD or DRAC contact, or a Nigerian lawyer), send the
   sheet, and collect it. **Nothing goes to an external party without the owner.**
3. **Agent:** write results into this playbook's Results. Route each `wrong` or `harmful` row: a
   corpus text error goes to the corrections-file route (human-signed), an answer-shape error goes
   to a new prompt version (never edit a frozen prompt in place), and a retrieval miss becomes a
   candidate eval question (dev split).

**Exit.** The sheet is returned, results are recorded, every `harmful` row has a fix or a written
decision, and the AI expander's "recommendable" status is re-confirmed or withdrawn in writing.

---

## H7 — Real-user signal (privacy first)

**Goal.** Collect the data that the M2 (dense) and F2 (fine-tune) revisits were deferred on.
**Branch** `phase11/h7-signal`. **Quota** zero.

* An opt-in **"Was this helpful?"** control (yes / no) per assistant turn, keyboard and
  screen-reader operable.
* **Counts-only telemetry** per turn: route (legal / help / greeting / clarify), refused yes/no,
  top-score bucket, excerpts shown, helpful yes/no/none. **Never the query text unless the user
  ticks a separate, explicit opt-in. Conversation history is never logged.**
* **Sink.** Render's filesystem is ephemeral. First choice: structured lines to stdout, read from
  Render logs (zero new services). If a durable free sink is wanted, evaluate one in writing
  (retention, region, terms) and get the owner's sign-off before sending anything off-box.
* A plain-language privacy note in the UI, next to the control, says exactly what is and isn't
  recorded.
* Extend `test_phase09_ops.py`: the default path still makes **zero network calls** (stdout only),
  and no log line contains question text without the opt-in flag.

**Exit.** Asserts green, the privacy note reviewed by the owner, and a first week of counts read
and summarised in Results. Then re-open the M2 / F2 / H5a questions with real data, each with a new
pre-declared gate.

**Do not.** Log text by default. Add analytics SDKs. Log `st.session_state` history.

---

## H8 — Corpus expansion and maintainability

### H8a — new legal sources
* Candidates: **NCPWD regulations**, and the **Lagos State Special People's Law 2011** (state-level,
  so answers need a jurisdiction note).
* Before any ingest: verify the **source** (official gazette or government site) and the
  **licence/reuse** position in writing.
* A new `doc_id` and its own citation scheme, built **only** in `cite_tag()`; never conflated with
  Act clause / Constitution section / Factsheet Section numbering. Decide where it sits in
  `build_corpus()`'s dict order (insertion order breaks ties) and record the decision.
* A corpus change means `build_oov_bridge.py` rebuild, `V2_CORPUS_SHA256` re-pin, and **a full
  re-measure on every set** (frozen-10, dev, test, test2, 0/212, every suite). New eval questions
  for the new doc are authored before measuring.

### H8b — split `app.py`'s render helpers into a module
Move the `render_*` helpers into e.g. `src/ui_render.py`; keep `run()`, `render_turn()` and
`replay_turn()` where the source-text asserts expect them, or update those asserts **deliberately
and in the same commit**, with the reason. `import app` must stay import-safe.

### H8c — slim `STATUS.md` and `CLAUDE.md`
Use the `claude-md-lifecycle` skill: durable rules stay in `CLAUDE.md` (under ~200 lines), dated
history moves to `LEARNING_JOURNAL.md`, and `STATUS.md` becomes current state only. No invariant
is dropped; each one is checked off against the old file.

---

## Invariants that bind every H step (from `CLAUDE.md`, restated)
* **Helplines first, always**: DRAC Toll-Free `08000-3000-100`, WhatsApp `08000-3000-10`, above
  every answer and leading every NGO result, via `ngo.with_helplines()`.
* **Every legal claim carries a verbatim citation tag**; OCR quirks in section numbers are never
  cleaned up except through the human-signed corrections file.
* **Both refusal layers preserved**; `MIN_SCORE` is not raised.
* **The default path is fully offline**; `ask(use_llm=False)` returns `answer=None` (pending).
* **Never fake an LLM row**; LLM runs write to versioned files.
* **Verified contacts only**; pruned orgs stay out without fresh verification.
* **The OOV bridge is corpus-keyed**: any corpus change means a rebuild and a re-measure.
* `requirements.txt` stays slim: no OCR/ONNX/FAISS, no translation or embedding model.
* **Accessibility is a requirement.**
* **A push to `main` deploys. It is the user's decision, every time.**

## Results

> **H0 — 2026-10-15, EXIT GATE MET (branch `phase11/h0-ci`, PR #13 open, NOT merged; zero quota).**
> * **Step 1 (what the suites need on disk):** every input of the six CI suites is committed:
>   `data/processed/*` (incl. `act2018_v2_clauses.json`, `oov_bridge.json`), `data/eval/*`,
>   `data/ngo.csv`. None reads `runs\` or the GloVe file. Verified empirically, not by reading:
>   fresh `git clone` of the branch + clean venv (Python 3.11.16, no site-packages) →
>   `import app` and test_phase03 / 04 / 05 (137/137) / 09_ops / audit_corpus / bench_phase01 **all exit 0**,
>   with no API key set, and the clone's `git status` is clean afterwards (no suite writes tracked files).
> * **Step 2 (install):** `requirements.txt` alone is sufficient, so **no `requirements-ci.txt`** was
>   written and `requirements.txt` is untouched. The local Windows install took ~4m50s cold; on the
>   ubuntu runner it took **30 s** (first run, cold pip cache), and the whole job **51 s**.
> * **Step 3–4:** `.github/workflows/offline-suites.yml`: `pull_request` + `push` (all branches), one job,
>   one step per suite in the playbook's order, pip cache keyed on `requirements.txt`,
>   `permissions: contents: read`, no secret referenced, no deploy step. The file's header records why
>   the Gemini scripts and the measurement harnesses are excluded.
> * **Step 5 + exit gate: PENDING the user's OK** to push the topic branch and open the PR (outward-facing).
>   **Done on the user's OK ("proceed"):**
>   * **Green**: PR [#13](https://github.com/batestguy/NGOdisabilityRAG/pull/13), `pull_request` run
>     [38675503148](https://github.com/batestguy/NGOdisabilityRAG/actions/runs/38675503148) (plus push run
>     [38675499933](https://github.com/batestguy/NGOdisabilityRAG/actions/runs/38675499933)): all 7 suite steps succeed.
>   * **Red**: throwaway branch `h0-ci-red-check` (`95cf21b`, one line `assert False` after `import router` in
>     `test_phase04.py`), run [38675517320](https://github.com/batestguy/NGOdisabilityRAG/actions/runs/38675517320):
>     **failure at the `test_phase04` step** with that `AssertionError`; the four later steps are skipped. The
>     branch was then deleted on `origin` and locally.
> * **Still the owner's:** merging PR #13 (that is a push to `main`, so it redeploys) and, optionally, branch
>   protection on `main` requiring the `offline` check.
