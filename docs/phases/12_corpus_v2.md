# Phase D — Corpus v2 (planned 2026-09-16)

> **Supersedes M3 of `docs/phases/10_corpus_rebuild_and_dense.md`.** That milestone was written
> 2026-09-13, before anything in Phase 10 was built. Three of its premises were checked on
> 2026-09-16 and **two are false**. This playbook exists because the false ones are currently
> load-bearing — in code (`scripts/audit_corpus.py:80`), in `HANDOFF.md`'s standing facts, and in
> a published `LEARNING_JOURNAL.md` claim the project acted on for three days.

**Branch (next session):** `phase10/corpus-v2`, off `phase10/chat-ui`.
**Quota: zero.** No Gemini call anywhere in this phase. No new packages.

## Goal

Make the project's central invariant — *every legal claim carries a citation tag copied verbatim
from the chunk header* — structurally true on the Act. Today 25 of 62 Act chunks (40%) are
uncitable and 16 of 62 carry packed refs. Exit gate: `ref=="general"` ≤1% per doc, packed refs 0,
58/58 Act clauses citable, false refusals no worse than v1.

---

## Findings that reshaped this phase (all measured 2026-09-16)

### Finding 1 — the Act gap is a SOURCING failure, not an OCR failure. cl.38 and cl.40 are recoverable.

The owner downloaded the one untested lead to `D:\NGORAG\6document.pdf` (14,108,117 bytes).
Verified this session:

```
Extraordinary Federal Republic of Nigeria Official Gazette No.10 Lagos 21st January, 2019
Vol.106 ... Act No. 2  Discrimination against Persons with Disabilities (Prohibition) Act, 2018
A97-122
```

That is the authoritative gazette publication, pages **A97–A122**. (Note: the old M3 guessed
*"Official Gazette No. 11 Vol. 106"* — the real citation is **No. 10, Vol. 106**, Act **No. 2 of
2019**.) Like the existing copy it is **27 pages with 0 embedded text characters** — a scan. But
it has **no duplicate adjacent page pair**, where the existing copy does.

Targeted OCR (`rapidocr_onnxruntime`, dpi 200) recovered both "missing" clauses in full:

| gazette page | printed page | recovered |
|---|---|---|
| 13 | A109 | `38.TheCommissionshall-` + marginal note `Functions of the Commission.`, running into `(a) formulate and implement policies…` |
| 14 | A110 | `(e)…(r) procure assistive devices for all disability types.`, then `39.-(1) The Commission shall have power to do any lawful thing…` |
| 15 | A111 | `PART VIII—APPOINTMENT AND DUTIES OF THE EXECUTIVE SECRETARY AND OTHER STAFF` then `40.—(1) There` |

**Then the sharper correction.** Grepping the *existing* `data/processed/disability_act_2018_full.txt`
shows both bodies were **there all along**:

| clause | gazette says | v1 processed text says | why `act_ref()` missed it |
|---|---|---|---|
| 38 | `38.TheCommissionshall-` | `(1)TheCommissionshall--` (**L614**) | OCR read the numeral `38.` as `(1)` |
| 40 | `40.—(1) There shall be an Executive Secretary…` | `(1) There shall be an Executive Secretary for the Commission who shall-` (**L545**) | OCR dropped the numeral entirely |

So the 2026-09-13 conclusion — *"the missing page carries cl.38's opening and cl.40 … no OCR and
no VLM can recover pixels that were never captured"* — **is wrong.** The duplicate page is real;
it did not cost cl.38 or cl.40.

**This retires, by name:**

- `ACT_KNOWN_ABSENT = {38, 40}` at **`scripts/audit_corpus.py:80`** — a false constant currently
  excusing two clauses from the coverage gate.
- The matching `LEARNING_JOURNAL.md` 2026-09-13 claim and the `HANDOFF.md` standing fact.
- `audit_corpus.py`'s printed line *"the pixels do not exist"* (`:215`).

**Consequence: all 58 clauses are reachable, and the gap manifest may end up empty.** The
**no stub / no paraphrase / no model knowledge** rule stays in this playbook regardless — it is
about what to do *if* a gap is ever real, and it is the worst output this codebase can produce.

> **Honest scope limit.** Only pages **1, 13, 14, 15** of 27 were OCRed this session (a prior
> pass covered 1, 2 and 13–19). Fewer than half the document has been read. **"All 58 clauses
> present" is a D2 verification task, not a finding.**

#### The verification recipe, so the *method* survives and a sceptic can re-run it

```powershell
# 1. page count + embedded text layer (a scan has 0 chars)
C:\conda-envs\drlca-rag\python.exe -c "import pymupdf; d=pymupdf.open('6document.pdf'); print(d.page_count, sum(len(p.get_text()) for p in d))"

# 2. duplicate-page detection: render dpi=100 grayscale, mean-pool to a 16x16
#    signature, MEAN-CENTRE it, L2-normalise, cosine between ADJACENT pages.
#    Centring is not optional -- on mostly-white scans the uncentred cosine
#    saturates at 1.000 for every pair and detects nothing.

# 3. targeted OCR of the disputed pages
#    rapidocr_onnxruntime, dpi 200, ~33 s/page

# 4. grep the v1 processed TXT for the recovered body text
#    -- this is the step that attributed the failure correctly
```

Measured adjacent-page cosines under that recipe:

| file | top adjacent pairs |
|---|---|
| `data/raw/disability_act_2018_full.pdf` | **0.978 p5–p6**, 0.794 p19–p20, 0.787 p6–p7 |
| `6document.pdf` (gazette) | 0.868 p13–p14, 0.840 p18–p19, 0.826 p9–p10 |

The v1 duplicate is a clear outlier (0.978 against a 0.794 runner-up). The gazette's maximum sits
inside its own distribution — **no duplicate**.

#### Why the gazette is the better source on every axis

Correct numerals (`35.—(1)`, `38.`, `39.—(1)`, `40.—(1)`) · gazette page numbers A97–A122 usable
as provenance · no duplicate page · marginal notes emitted as visually separate lines rather than
spliced mid-sentence. Re-OCR is ~33 s/page × 27 ≈ **15 minutes, one-time, offline, dev-only**.
`rapidocr_onnxruntime` is already in `requirements-rag.txt` and **must never reach
`requirements.txt`**.

### Finding 2 — the Constitution needs only the cheap fix to clear the gate

Measured via `rag.build_corpus()`: **all 99 uncitable Constitution chunks are
Arrangement-of-Sections material.** 88 are under 60 words. Every one of the 11 that is ≥60 words
is *also* a numbered title listing:

```
'Constitution, Chapter V - The Legislature: \ninvestigations \n89 Power as to matters of \nevi…'
'Constitution, Chapter VII - The Judicature: determinations \n236 Practice and procedure \n…'
'Constitution, Chapter VII - The Judicature: . \n267 Jurisdiction. \n268 Constitution. 269 Pr…'
```

**Zero substantive body text is uncitable.** Excluding the Arrangement pages therefore takes
`general` 99 (4.7%) → ≈0, clears the ≤1% gate **without touching `CONST_SIZE = 400`**, and deletes
the `toc-trap` class.

M3's 2104 → ~500 section-unit re-extract — **the riskiest change in the whole plan** — is *not
needed for the gate*. It defers to Phase E, where the dense arm actually wants it.

### Finding 3 — M3's milestone order is backwards

M3 runs **M1 (width) → M2 (dense) → M3 (corpus)**. M2 ships `data/embed/chunks_gemini.f16.npy`,
a **per-chunk** artifact keyed on a corpus sha256. Rebuilding the corpus afterwards invalidates
every vector and forces a full re-embed.

**Corpus must come first.** `HANDOFF.md` already assumes this by putting D before E — the
playbook never said why. It does now.

### Two more measured facts

**Act — all 16 packed refs are consecutive runs**, i.e. pure 800-char cutting across clause
boundaries, fixable mechanically by clause-aligned chunking:

```
cl. 3,4,5 · cl. 6,7 · cl. 9,10 · cl. 16,17 · cl. 21,22 · cl. 23,24 · cl. 25,26,27 · cl. 29,30
cl. 33,34 · cl. 36,37 · cl. 41,42 · cl. 44,45 · cl. 46,47,48 · cl. 50,51,52 · cl. 54,55 · cl. 56,57
```

**Factsheet — 19 packed and 9 uncitable, one cause.** `recursive_split(500/50)` cuts the S/N table
mid-row, producing *disordered* refs — `Section 51,40`, `Section 50,45,54`, `Section 19,17,20`,
`Section 53,48` — which is the tell that this is table damage, not consecutive over-run. The 9
`general` chunks are the cover page, intro prose, the Arrangement block (×2), one mid-table
fragment, and PLAC boilerplate/footer (×4).

---

## Steps

### D0 — source hunt: **DONE**, verified above

Nothing left to do but the filing. The verification recipe is recorded above so the method
survives, not just the answer.

**First task in D1:** move `D:\NGORAG\6document.pdf` out of the repo root into `data/raw/` under a
descriptive name (e.g. `disability_act_2018_gazette_FGP.pdf`) and add a `data/raw/SOURCES.md`
entry with the full gazette citation (*Official Gazette No. 10, Vol. 106, Lagos, 21 January 2019,
Act No. 2, pages A97–A122*).

> **DECIDED by the owner 2026-09-16: commit the PDF to `data/raw/`.** Raw PDFs are already
> **tracked** — `git ls-files data/raw/` lists the 5.2 MB Act and the 8.5 MB PLAC Constitution —
> so this is consistent with existing practice, and `data/raw/` is never read at boot, so the slim
> Render runtime is untouched. The accepted cost: a **14 MB blob permanently in git history**,
> which is hard to remove later. The benefit that decided it: the authoritative source stays
> reproducible from a clone, rather than depending on an `ncpwd.gov.ng` link that may rot.
>
> Practical note for D1: commit it in its **own commit**, separate from the parser work, so the
> large blob is easy to identify in history.

### D1 — versioned scaffolding

`build_corpus(version=None)` defaulting to `CORPUS_VERSION` (`src/rag.py:42`), which **stays
`"v1"` until D6**.

- **The v1 path stays byte-identical** — same paths, same splitters, same ref functions — so every
  published baseline remains reproducible from the same commit.
- `data/processed/*.txt` are **not** touched. v2 writes new files.
- `Chunk` (`src/retrieve.py:51`) gains a **defaulted** subsection-path field, so `cite_tag()`
  (`src/retrieve.py:530`), `CITE_TAG_RE` (`src/rag.py:349`), `verify_citations()`
  (`src/rag.py:360`) and every historical transcript's tag grammar are untouched.
- **`ref` grammar stays `cl. N`** — number only.

### D2 — Act: re-OCR the gazette, then manifest-anchored parse

1. **Re-OCR all 27 gazette pages** to a new processed TXT carrying gazette page provenance
   (A97–A122).
2. **`dedupe_pages()` should find nothing — assert that, do not assume it.** Finding 1 measured no
   duplicate; the parse should fail loudly if a future source has one.
3. **Parse the Arrangement into `{1..58 → title}`**, then locate each body by `N.` near a
   `difflib.SequenceMatcher` match of its known title — already the idiom in `src/load.py`.
   Anchoring on (number, expected title) rather than heading *shape* is what makes `19.1`,
   `35.(1)`, `37.The` and `54.A` all resolve.
4. **Strip marginal notes title-anchored**, keeping them as metadata. This is the subtle part:
   the marginal note text **is that clause's Arrangement title** (A109 puts `Functions of the
   Commission.` beside clause 38, whose Arrangement title is the same string). That is *precisely*
   why `act_ref()`'s heading-*shape* inference fails, and precisely why title-anchoring works.
5. **One clause = one chunk**, split over ~1,100 chars on `(1)`,`(2)` then `(a)`,`(b)`.
6. **Exclude the Arrangement pages** from the retrievable corpus — the Act-side twin of the
   Constitution TOC trap.
7. **Demote `act_ref()` (`src/rag.py:105`) to a validator**: `audit_corpus.py` asserts the two
   sources agree. Two independent sources that must match — the same discipline as
   `evalset.assert_frozen10_matches_notebook()`.
8. **Verify all 58 clause bodies are present** (this is where the Finding 1 scope limit is
   discharged), and **cross-check the new OCR against the v1 text with `difflib` on a sample**.
   Two independent scans agreeing is strong evidence. **Where they disagree, the gazette wins and
   the disagreement gets recorded.**

**Target:** `general` ≤1% · `packed` 0 · **58/58 citable**.

### D3 — Factsheet: parse the S/N table

One table row = one `Section N`. Exclude the cover page, the Arrangement block and the PLAC
boilerplate/footer from retrieval.

**Target:** `general` ≤1% · `packed` 0.

### D4 — Constitution: exclude the Arrangement pages, and nothing else

Keep `constitution_aware_split`. Keep **`CONST_SIZE = 400`** (`src/rag.py:54`).

`_is_toc_fragment` (**`src/rag.py:156-203`**) is **kept and demoted to a lint assertion** — after
exclusion it should fire ≈0 times. **Assert the count; do not delete the heuristic.** It is the
Fix-B widening that made `MANUAL_FLAGS == []`, and deleting it would silently restore the Q10
s.39 misattribution class.

**Record explicitly, with Finding 2's measurement, that the section-unit re-extract (2104 → ~500)
is deferred to Phase E, and why** — it is not needed for the gate, and it is the riskiest change
in the original plan.

### D5 — the refusal floor. **Mandatory, not conditional.**

State plainly: **even the "cheap" changes move cosines.** Dropping ~99 TOC chunks changes the
Constitution's IDF space, and clause-aligned Act chunks run longer than 800 chars. Longer chunks
lower every cosine, which manufactures **false refusals** — the failure `CLAUDE.md` names as the
worst one, because a false refusal denies help to a PWD.

In order:

1. **Re-derive the calibration table at `src/retrieve.py:26-44` against v2** and write the new
   numbers in — in-corpus minima on the answerable questions vs off-corpus maxima on the same
   probes (`sourdough` / `quantum` / `visa` / `maritime shipping insurance (law)`).
2. **`MIN_SCORE` may move down. It may not move up.** The gate is documented to err low.
3. **Gate on `false_refusal_v2 ≤ false_refusal_v1`** — currently **0/10** frozen, **0/25** dev,
   **0/17** test.
4. **Escape hatch, only if a false refusal appears:** a small frozen v1 index used *only* for the
   answer/refuse decision, while ranking and display use v2. **Present it as the hatch, not the
   default** — two indexes is real cost.

### D6 — re-baseline, zero quota

- Flip `CORPUS_VERSION` to `"v2"`. **Keep the v1 tripwire runnable** so the published shape stays
  provable.
- **`audit_corpus.py` becomes the gate**: ≤1% general, 0 packed, 58/58 clauses citable, `act_ref`
  validator agrees — **and `ACT_KNOWN_ABSENT` is DELETED, not emptied**, so nobody can re-add a
  clause to it. Its "SINGLE-SOURCE for now" caveat (`:202-205`) and the "the pixels do not exist"
  line (`:215`) go with it.
- **`eval_heldout.py` publishes `recall_strict`** — the only comparison legitimate across corpus
  versions, which is exactly why M0 published v1's first — plus the recall@k curve, MRR and
  false-refusal, per set.
- **`test` is read once, at the end, never tuned against.** A disappointing test number is the
  finding.
- **`eval_phase06.py` must still hash `CE716FB3…5F19` under `CORPUS_VERSION="v1"`.** v2 goes to a
  new `--out=` path. (`--out=` **equals form only** — the space form is silently ignored.)
- Archive `scripts/baseline_v2_<date>.txt`.

#### The thing M3 never anticipated: the chat set

`data/eval/conversations.json`'s **51 corpus-verified refs were verified against v1** and must be
re-verified against v2 in D6, **exactly as `questions.json` is**. M3 predates Phase 10 B and does
not mention them at all.

- **Retire, never edit.** A question or turn whose truth changed gets `"status": "retired-v2"` and
  **stays in the file for provenance**, excluded from means. Rewording to survive the rebuild
  would destroy everything the eval discipline bought.
- **New questions go to a new set, authored before v2 retrieval is measured.**
- Clauses **19/35/37/38/40/54** become newly citable and deserve coverage.
- Known trap from the Phase 10 B review addendum: `CT7.t2` is **unscoreable, not missed** — it
  expects `act2018:[5]` but the chunk carrying the First Schedule list is reffed `general`. v2
  should make it scoreable; check it explicitly rather than assuming.

---

## Claims Phase D retires by name

| claim | status |
|---|---|
| `ACT_KNOWN_ABSENT = {38, 40}` and *"no OCR can recover it"* | **FALSE** (Finding 1) |
| `frozen-10 0.925` / `dev 0.420` / `test 0.338` | become **v1-corpus-only** |
| `context precision 0.333 is by design` | the **reasoning** survives, the **number** does not |
| Phase 01 Act chunk-size pinning (800) | measured against the **corrupted** text |
| the `MIN_SCORE` calibration table | **re-derived**, not inherited |
| `Act cl.19 is uncitable` | fixed by the parse |
| `audit_corpus.py`'s *"SINGLE-SOURCE for now"* caveat | becomes a real cross-check |

## Out of scope for Phase D

Any Gemini call · width / pool depth · dense retrieval · the Constitution section-unit re-extract
(deferred to Phase E, see D4) · editing an eval question · touching `requirements.txt` · the stray
`D:NGORAG_review_judge.diff` (owner removes by hand).

## Traps

- **No stub chunk, no paraphrase, no model knowledge** for any clause that does turn out to be
  missing. A citation tag in front of a generation model is precisely how a gap becomes a
  hallucinated provision that passes `verify_citations()` mechanically.
- **Never strip or "clean up" OCR quirks in section numbers at generation time.** A verified,
  human-signed corpus re-extraction is a *different act* from that, and only the first is allowed.
- **`verify_expected` gets easier, which is a trap** — v2 has strictly more citable numbers, so
  passing it stops being evidence. Add the reverse check: every corpus `ref` must be reachable
  from the manifest, so a parser bug that *invents* refs also fails.
- `verify_ground_truth` **hard-crashes before printing** if an expected number is missing from
  every `ref`. Measure the blast radius of any ref-grammar change in isolation first.
- **Retire questions, never edit them. Never merge new questions into an existing set.**

## Verification

```powershell
C:\conda-envs\drlca-rag\python.exe scripts\audit_corpus.py      # v1 tripwire, then the v2 gate
C:\conda-envs\drlca-rag\python.exe scripts\eval_heldout.py      # recall + recall_strict + @k
C:\conda-envs\drlca-rag\python.exe scripts\eval_chat.py         # the 51 chat refs, re-verified
C:\conda-envs\drlca-rag\python.exe scripts\bench_phase01.py
C:\conda-envs\drlca-rag\python.exe scripts\test_phase03.py
C:\conda-envs\drlca-rag\python.exe scripts\test_phase04.py
C:\conda-envs\drlca-rag\python.exe scripts\test_phase05.py
C:\conda-envs\drlca-rag\python.exe scripts\test_phase09_ops.py
C:\conda-envs\drlca-rag\python.exe scripts\ablate_phase08.py
C:\conda-envs\drlca-rag\python.exe -c "import app"
C:\conda-envs\drlca-rag\python.exe scripts\eval_phase06.py --out=scripts\eval_p12.json
git diff --stat main -- requirements.txt                        # must stay EMPTY
```

## Results

*(none yet — planned 2026-09-16, no step started)*
