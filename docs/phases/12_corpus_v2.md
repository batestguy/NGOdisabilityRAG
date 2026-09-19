# Phase D — Corpus v2 (planned 2026-09-16)

> **Supersedes M3 of `docs/phases/10_corpus_rebuild_and_dense.md`.** That milestone was written
> 2026-09-13, before anything in Phase 10 was built. Three of its premises were checked on
> 2026-09-16 and **two are false**. This playbook exists because the false ones are currently
> load-bearing — in code (`scripts/audit_corpus.py:80`), in `HANDOFF.md`'s standing facts, and in
> a published `LEARNING_JOURNAL.md` claim the project acted on for three days.

**Branch (next session):** `phase10/corpus-v2`, off `phase10/chat-ui`.
**Quota: zero.** No Gemini call anywhere in this phase. No new packages.

> **STATUS: COMPLETE — D0–D6 all DONE 2026-09-19.** `CORPUS_VERSION = "v2"` is the default
> (`src/rag.py:48`); v1 is retired as the default but **not deleted** — every harness takes
> `--corpus=v1` and reproduces its published numbers. Baseline:
> `scripts/baseline_v2_2026-09-19.txt`, all five harnesses green. **Zero Gemini calls across the
> whole phase, as scoped.** The branch is **UNMERGED** — merging auto-deploys to Render and that
> decision is the user's. Per-step results are in the D0–D6 sections below; **read D6's results
> first**, because it corrected premises the earlier steps were written under.
> **Next: Phase E — `docs/phases/13_retrieval_quality.md`** (two D6 findings are carried into its
> amendment box).

## Goal

Make the project's central invariant — *every legal claim carries a citation tag copied verbatim
from the chunk header* — structurally true on the Act. Today 25 of 62 Act chunks (40%) are
uncitable and 16 of 62 carry packed refs. Exit gate: `ref=="general"` ≤1% per doc, packed refs 0,
58/58 Act clauses citable, false refusals no worse than v1.

---

## Findings that reshaped this phase (all measured 2026-09-16)

### Finding 1 — the Act gap is a SOURCING failure, not an OCR failure. cl.38 and cl.40 are recoverable.

> ## ⚠ CORRECTED 2026-09-17 — Finding 1's cl.38 row was WRONG, and it was load-bearing
>
> The version of this finding committed in `4bcc763` claimed **cl.38's body was in the v1 text at
> L614 all along**. It is not. L614 is **clause 48**. Re-verified line by line 2026-09-17:
>
> | clause | 2026-09-13 claim | `4bcc763` claim | **verified truth (2026-09-17)** |
> |---|---|---|---|
> | 38 | absent + unrecoverable | present at L614, numeral OCR'd as `(1)` | **ABSENT from v1.** L612 reads `48.`; the Arrangement at **L74** says `48.Annual estimate and expenditure.` — exactly the marginal note wrapped around L614 at L613 (`Annual estimate`) / L615 (`and expenditure.`). v1 continues `(a) cause tobekept accounts and records` (cl.**48**) where the gazette continues `(a) formulate and implement policies` (cl.38). `grep "formulate and implement"` returns **nothing** in v1. |
> | 40 | absent + unrecoverable | present at L545, numeral dropped | **CORRECT.** Bounded by `39.` (L524) and `41.` (L555); the marginal note at L544/546/547/549/551 (`Appointment` / `and duties of the` / `Executive` / `Secretary of the` / `Commission.`) matches Arrangement L66 verbatim. |
>
> **The error:** `(1)TheCommissionshall--` was matched to the gazette's `38.TheCommissionshall-` on
> string similarity **without reading the next line** — which is the same failure the journal entry
> this finding sits in was written to warn about. A correct measurement next to a plausible story,
> again, one day later.
>
> **The conclusion survives, for changed reasons.** `ACT_KNOWN_ABSENT = {38, 40}` still retires:
> **cl.40** because it was never absent, **cl.38** because the *gazette* recovers it (A109–A110),
> not because v1 had it. All 58 clauses are still reachable in v2. The 2026-09-13 claim was
> **right about cl.38's absence** and wrong only about its **irrecoverability** — re-scoped below.
>
> Three further facts fell out of the re-check; they are **Findings 1a–1c** below and every one of
> them strengthens the case for v2.

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

**Then the state of the v1 text, clause by clause** (corrected 2026-09-17 — the `4bcc763` version
of this table claimed both bodies were present; only cl.40's is):

| clause | gazette says | v1 processed text | verdict |
|---|---|---|---|
| 38 | `38.TheCommissionshall-` then `(a) formulate and implement policies…` | **opening + (a)–(i) ABSENT.** `grep "formulate and implement"` → no match. Its `(j)`–`(r)` tail *is* present at **L501–522**, misfiled (Finding 1b) | **absent from v1, recovered from the gazette** |
| 40 | `40.—(1) There shall be an Executive Secretary…` | `(1) There shall be an Executive Secretary for the Commission who shall-` (**L545**), numeral dropped by OCR | **never absent — only unreffed** |

So the 2026-09-13 conclusion — *"the missing page carries cl.38's opening and cl.40 … no OCR and
no VLM can recover pixels that were never captured"* — is **half right and wholly unusable**:

- **Right:** a physical page *is* missing, and it *does* carry cl.38's opening. Finding 1a below
  pins the exact boundary.
- **Wrong about cl.40:** it was never on that page. It is at L545, bounded by `39.` (L524) and
  `41.` (L555).
- **Wrong about recoverability, which is the part that mattered:** the gazette captured cl.38 in
  full at A109–A110. "No OCR can recover it" was a claim about the *world*, made from one scan.

**This retires, by name:**

- `ACT_KNOWN_ABSENT = {38, 40}` at **`scripts/audit_corpus.py:90`** (was `:80` before D1 added the
  explanatory comment block above it — corrected 2026-09-18) — a false constant currently
  excusing two clauses from the coverage gate. **Both entries go, for different reasons:** 40 was
  never absent; 38 is absent from v1 but present in the gazette v2 is built from.
- The matching `LEARNING_JOURNAL.md` 2026-09-13 claim (**only its irrecoverability half** — its
  claim that cl.38 is absent from v1 stands) and the `HANDOFF.md` standing fact.
- `audit_corpus.py`'s printed line *"the pixels do not exist"* (`:215`).

**Consequence: all 58 clauses are reachable in v2, and the gap manifest may end up empty.** The
**no stub / no paraphrase / no model knowledge** rule stays in this playbook regardless — it is
about what to do *if* a gap is ever real, and it is the worst output this codebase can produce.

**Note for D2:** because cl.38's recovery now depends on the *gazette* and not on the v1 text,
`ACT_KNOWN_ABSENT` cannot be retired on the strength of a re-parse alone. It retires when the
gazette re-OCR lands — which is already D2's job, and is why D6, not D2, deletes the constant.

### Finding 1a — v1's cl.37 is silently corrupted by the genuinely missing page

Measured 2026-09-17 from `data/processed/disability_act_2018_rapidocr.json` and the assembled TXT:

- raw OCR **page 13 ends** at cl.37(b) `…make rules and regulations for the effective running of the / Commission;`
- raw OCR **page 14 opens** mid-list at cl.38(j) `()establish and promote inclusive schools,vocational and`
- in the TXT that boundary is **L499 → L500 (`===== PAGE 14 =====`) → L501**

So the physical page lost to the p5/p6 duplicate is the one carrying **cl.37's tail, the PART VII
heading region, and cl.38's opening through (i)**. The duplicate page cost something real after
all — just not what 2026-09-13 said, and not cl.40.

### Finding 1b — a LIVE citation-integrity defect: cl.38's text is retrievable under `[Act cl. 39]`

This is not cosmetic. Measured on `rag.build_corpus()` 2026-09-17:

| chunk | ref | carries |
|---|---|---|
| 31 | `cl. 36,37` | cl.36 + cl.37 through `(b)` — **clean** |
| 32 | `general` | cl.38 `(j)`–`(o)` — uncitable |
| **33** | **`cl. 39`** | **cl.38 `(o)`–`(r)`**, incl. `(r) procure assistive devicesfor all disability types.`, **then** `39.` and cl.39's body |

A user asking about assistive devices today can be served cl.38(r) **carrying the tag
`[Act cl. 39]`** — a wrong citation that passes `verify_citations()` mechanically, because the
number in the tag really is the chunk's `ref`. That is the exact failure mode the project's
central invariant exists to prevent, live in `main`, and it is Phase D's strongest single
justification.

> **Recorded because the plan for this session predicted the wrong clause.** The session plan said
> cl.38's tail was *"absorbed into cl.37's chunk"* and that the app *"can retrieve cl.38's text
> under a cl.37 citation"*. It cannot: chunk 31 (`cl. 36,37`) stops at cl.37(b). The
> misattribution is under **`cl. 39`**, via chunk 33. Reproduce with
> `[(i, c.ref) for i, c in enumerate(build_corpus()["act2018"][29:35], 29)]`.

### Finding 1c — two more v1 defects found while re-checking

- **v1 L542 reads `PARTVII-APPOINTMENTANDDUTIESOFTHEEXECUTIVESECRETARYAND`** where both the
  Arrangement (**L64**) and the gazette (A111) say **PART VIII**. The body text misnumbers the Part.
- **v1's Arrangement truncates at L77, `51.Power to acquire land.`** (L78 is `===== PAGE 4 =====`;
  raw OCR page 3 ends on that same entry and page 4 opens `ABill`). `scripts/audit_corpus.py:64-66`
  cites the Arrangement as the source of `ACT_CLAUSES = range(1, 59)` — but it does **not** contain
  52–58. **The number 58 is right; the cited source is wrong.**

  Consequence for D2, and it is a real one: **the Arrangement go/no-go gate cannot be run against
  the v1 text.** It must run against the *gazette's* Arrangement pages — which **have not been
  OCRed yet** (only gazette pages 1, 13, 14, 15 were read). Whether the gazette's Arrangement
  yields a clean `1..58` is **unknown and must be checked first**, because the whole
  manifest-anchored parse is built on it. See the go/no-go gate in D2's implementation notes.

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

#### Implementation notes (designed 2026-09-16, verified 2026-09-17)

**Capture the baselines before the first edit.** Phase 10 C's *only* reason it could claim
byte-identical stdout is that it captured baselines first (`HANDOFF.md:8-12`). Write them to a
scratch dir **outside the repo** (so `git status` stays clean and nothing can be committed by
accident) and `Compare-Object` after every commit:

```powershell
$B = "$env:TEMP\drlca_d1_baseline"; New-Item -ItemType Directory -Force $B | Out-Null
C:\conda-envs\drlca-rag\python.exe scripts\audit_corpus.py      > $B\audit.txt
C:\conda-envs\drlca-rag\python.exe scripts\eval_heldout.py      > $B\heldout.txt
C:\conda-envs\drlca-rag\python.exe scripts\eval_chat.py         > $B\chat.txt
C:\conda-envs\drlca-rag\python.exe scripts\ablate_phase08.py    > $B\ablate08.txt
C:\conda-envs\drlca-rag\python.exe scripts\eval_phase06.py --out=$B\eval.json
(Get-FileHash $B\eval.json -Algorithm SHA256).Hash   # must be CE716FB3…5F19
```

**The `Chunk` field addition — what is and is not risky.** `Chunk` becomes:

```python
Chunk = namedtuple("Chunk", ["doc_id", "ref", "text", "path"], defaults=("",))
```

**Verified 2026-09-17: `defaults=` preserves 3-arg positional construction.** `Chunk("act2018",
"cl. 1", "body")` works and yields `path=''`, so `src/rag.py:228,235,242` are **untouched** — do
not rewrite them to pass a fourth argument. What *does* change, and is the real risk surface:

| what changes | measured |
|---|---|
| `len(chunk)` | 3 → **4** |
| `[*chunk]` / `list(chunk)` | 3 → **4** elements |
| `a, b, c = chunk` | **raises `ValueError: too many values to unpack (expected 3)`** |

So sweep for the six patterns before touching anything — `rg` for `len\(.*chunk`, `\*chunk`,
`, *\w+ *= *chunk\b`, `for .*, .*, .* in `, `zip\(\*`, and `Chunk\(\*`. **Known near-miss:**
`scripts/bench_phase01.py:244,246,250` are three-tuple unpacks (`nb, ab, xb = chunk_stats(...)`),
but they unpack `chunk_stats()`'s `(n, avg, max)` **numbers**, and the `c` in the surrounding
comprehensions is a raw `str`, not a `Chunk` — inspect, confirm, leave alone.

> *(Line numbers corrected 2026-09-17 after review: this note first cited `:159,251,253`, which
> are `sum(...)` comprehensions and an `assert`, not unpacks. Cited in a section about verifying
> line references. Noted rather than quietly fixed.)*

**`build_corpus(version=None)` is a pure relocation.** **Move** the three existing blocks
(`src/rag.py:224-244`) into `_act_chunks_v1()` / `_const_chunks_v1()` / `_fact_chunks_v1()`
**verbatim, never retyped**; `git diff -w` must read as relocation and nothing else. Three things
that must **not** be smuggled into a zero-change commit:

- **No memoization.** Caching the corpus is a behaviour change (identity, mutation exposure,
  first-call latency) dressed as a refactor. If it is wanted, it is its own commit with its own
  argument.
- **No dict reordering.** `PerDocRetriever._merged()` iterates `self.docs.items()` in insertion
  order and sorts by score only (`src/retrieve.py:331-338`), so **insertion order breaks ties**.
  Reordering the dict silently reorders equal-scoring hits and moves published numbers.
- **No `version=` on `ask()`.** A corpus switch must not be reachable from the user path.

**Caller policy, in three tiers** (**14** call sites, enumerated 2026-09-17):

| tier | call sites | policy |
|---|---|---|
| **never flagged** | `app.py:458` · `src/router.py:221` · **`src/rag.py:642`** · `scripts/test_phase05.py:73` · `scripts/test_phase09_ops.py:218` | no flag, ever |
| **`--corpus=` flag** | `scripts/audit_corpus.py:165` · `eval_heldout.py:337` · `eval_chat.py:367` · `ablate_phase08.py:111` · `ablate_phase10.py:105` · `eval_phase06.py:248` | **equals form only** |
| **untouched (quota-bound)** | `scripts/test_phase02.py:103` · `judge_phase06.py:359,448` | do not open |

**`src/rag.py:642` is `ask()`'s own fallback** — `retriever = PerDocRetriever(build_corpus())`
when no retriever is passed in. It is the reason *"no `version` on `ask()`"* is stated as a rule
rather than left implicit: this line is the user path's default corpus build, and threading a
version through it is exactly the change that must not happen.

`src/router.py` is the one that bites: its `_retriever` global (`src/router.py:212`, built at
`:216-222`) is **unkeyed** — `if _retriever is None` and nothing else. A `version` argument
reaching it would serve whichever corpus happened to be built first for the rest of the process.
Leave it alone; the router has no business choosing a corpus.

> *(Corrected 2026-09-17 after review: this table first said "13 call sites", omitted
> `src/rag.py:642` entirely, and cited `app.py:457` / `src/router.py:220` — which are the
> `from rag import …` lines, not the calls. The omitted one was `ask()`'s. Noted rather than
> quietly fixed, since a caller-policy table that misses a caller is the failure it exists to
> prevent.)*

**Two prose claims become real gates.** Both exist because the current guards cannot see the
failure they are supposed to catch:

1. **`corpus_sha256()`.** `V1_EXPECTED` (`scripts/audit_corpus.py:85-89`) is nine integers —
   `n`/`general`/`packed` per doc. Nine integers **cannot see text moving between chunks at
   constant count**, which is precisely what a splitter change does. Fingerprint the concatenated
   `(doc_id, ref, text)` of every chunk in order and pin the digest alongside the counts.
2. **The `CE716FB3…` assert moves into `eval_phase06.py`.** It is quoted in four docs today and
   enforced in none. **Read the file back from disk after writing it** — `out.write_text(...)`
   (`scripts/eval_phase06.py:300`) translates `\n` → `\r\n` on Windows, and the published digest
   is of the **CRLF bytes** (verified 2026-09-17: 594 CRLF pairs in the 10-record output, digest
   `CE716FB3C1EA139B5E3A6885D732C5EBBD3F1B57981635F7D97DA5911EDF5F19`). Hashing the in-memory
   string gives a different, wrong answer.

   Disclose both costs in the commit message: the assert is **Windows-specific** as written (a
   Linux run produces LF bytes and a different digest — fail with that explanation, not a bare
   `AssertionError`), and it adds **one line, ` sha256=…`, to stdout**, so the Phase 10 C
   byte-identical-stdout claim is re-baselined at that commit rather than broken silently.

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

#### Implementation notes (designed 2026-09-16, verified 2026-09-17)

**Three layers, so only the top one imports `pymupdf`/`rapidocr`.** This is the whole mechanism
that keeps `requirements.txt` honest — not a style preference:

| layer | file | imports | ships to Render |
|---|---|---|---|
| OCR | `scripts/ocr_gazette.py` | pymupdf, rapidocr | **no** (dev-only) |
| parse | `scripts/parse_act_v2.py` | **stdlib only** | **no** (dev-only) |
| runtime | `src/rag.py::_act_chunks_v2()` | reads the emitted **JSON** | yes |

If `src/rag.py` ever needs `pymupdf` to build a chunk, the slim runtime is gone. The JSON artifact
is the seam.

> **`scripts/ocr_local.py` is a trap — do not import it.** Verified 2026-09-17: it calls `main()`
> **at module scope** (last line of the file, no `__main__` guard) and `main()` unconditionally
> does `TXT_OUT.write_text(...)` at `:59` where `TXT_OUT = data/processed/disability_act_2018_full.txt`
> — **the v1 corpus every published baseline in this repo is measured against.** A bare
> `import ocr_local` to reuse a helper destroys it, on import, silently.
>
> Extract `scripts/ocrlib.py` instead, and while extracting:
> - **keep the `box` coordinates.** v1's assembler does `"\n".join(l["text"] for l in ...)` and
>   throws the geometry away — which is exactly the information the marginal-note problem needs.
> - add a `__main__` guard and a **`--force` gate** on the overwrite.

**Marginal notes: geometry primary, title as validator.** Measured 2026-09-17 on the v1 OCR JSON,
page 13:

| column | x0 range |
|---|---|
| body | **107.4 – 363.6** |
| marginal notes | **1448.5 – 1466.2** |

A ~1,100px gap. Geometry separates them cleanly; **pure title-anchoring does not**, because notes
**wrap across OCR lines**: `Cessation of` (y0 903.5) and `office.` (y0 937.6) are two separate
lines and **neither matches the Arrangement title *Cessation of office.* on its own**. Same for
`Power of the` / `Council.`. So:

1. take the note column by `x0` threshold, **detected per page** — gazettes alternate verso/recto,
   so the note side flips and a hardcoded side silently drops half the notes;
2. **group note lines by y-adjacency first**, then join;
3. only then compare the joined string to the Arrangement title, as a **validator**.

**`dedupe_pages()` must NOT run on v2.** Its salvage branch (`src/load.py:347-363`) appends any
line of the dropped twin that fails a `difflib` similarity threshold **onto the kept twin**. On a
genuinely duplicated page that is salvage; on a **clean** source it is a corruption mechanism that
splices unrelated text into a page. The gazette has no duplicate (Finding 1). So it becomes an
**assertion** — `assert detect_duplicate_pages(...) == []` — not a processing step.

**Clause locator: a monotonic cursor plus two required anchors.**

- **Monotonic cursor.** Only consider candidates for clause `n` *after* the accepted anchor for
  `n-1`. This kills the `section 27 of the Interpretation Act` false-positive class **structurally,
  with no heuristic and no stop-list** — that string sits at 89.8% of the document, long past where
  the cursor for any low clause number is looking.
- **Two anchors required**: the numeral **and** the title (via the note column or the statutory
  heading). One anchor is a guess.
- **Degraded acceptances are flagged, never silent**: `TITLE_WEAK` (numeral found, title match
  below threshold) and `NUMERAL_MISSING` (title found, numeral unreadable — cl.40's exact case in
  v1). They land in the manifest and print in the D2 report.
- **Neither anchor → hard failure.** No guessing, no interpolation between neighbours.

**Arrangement go/no-go gate — and it has a live problem.** Assert the parsed Arrangement yields
`1..58` with no holes. **Finding 1c means this cannot be run against the v1 text at all** (v1's
Arrangement stops at `51.Power to acquire land.`), and the gazette's Arrangement pages have **not
been OCRed yet**. So D2 starts by OCRing the gazette's front matter and checking it, *before*
building anything on top of it.

**Written-in-advance fallback, so the decision is not made under pressure:** if the gazette's
Arrangement does not yield a clean `1..58`, take titles from the **marginal notes** instead,
record `"title_source": "marginal_note"` per clause in the manifest, and report every discrepancy
between the two sources. **Never author a title.** A hand-written title is indistinguishable from
a real one three commits later.

**Cross-check predictions, written before the first run.** The point is that the output is
**falsifiable** rather than interpretable after the fact. v2-vs-v1 `difflib` must show:

| region | prediction |
|---|---|
| cl.38 opening + (a)–(i) | **large disagreement** — absent from v1 (Finding 1) |
| cl.37 | **large disagreement** — v1's chunk runs into cl.38's tail (Finding 1a) |
| cl.38 (p)–(r) vs v1's `cl. 39` chunk | **disagreement** — v1 misfiles them (Finding 1b) |
| cl.40 | **agrees** — v1 has the body, only the numeral was lost |
| PART VII / VIII heading | **disagrees** — v1 L542 misnumbers it (Finding 1c) |
| everything else | **agrees** |

**Anything outside that set is a parser bug, not a discovery.** And because the two editions
paginate differently, **the cross-check is text-level only — never page position.**

**Chunking and refs.**

- **`ACT_V2_SIZE = 1100`**, a **new constant**, explicitly **not** a change to `ACT_SIZE`. The v1
  path must keep its 800 or every published baseline detaches.
- **Do not tune it in D2.** Longer chunks lower every cosine; that is D5's recalibration to
  measure, not D2's to pre-empt. Tuning a size in D2 and a floor in D5 against each other is how
  both end up fitted to nothing.
- **`ref = "cl. %d" % n` comes from the parser**, never inferred from chunk text. This makes
  **packed refs structurally impossible** — a chunk belongs to exactly one clause by construction,
  so there is no path by which `cl. 3,4,5` can be produced.
- **The chunk header is the statutory heading**, `38. Functions of the Commission.` The marginal
  note is **not deleted — it is restored to the position the printer moved it out of.** Payoff:
  `act_ref()` then resolves v2 chunks **natively**, which turns step 7's validator from a loose
  comparison into a tight **equality** check.

**Leave `ACT_KNOWN_ABSENT` in place through D2; D6 deletes it.** Removing it early makes
`audit_corpus.py`'s v1-tripwire stdout diverge from the sealed baseline for no gain — and the
tripwire's whole job is to be comparable. Add a dated note beside it in D2 instead:

```python
# 2026-09-17: FALSE — cl.40 was never absent (body at L545); cl.38 is absent
# from v1 but present in the gazette at A109-A110. Deleted (not emptied) in D6,
# once the v2 corpus that recovers cl.38 actually exists. See 12_corpus_v2.md.
ACT_KNOWN_ABSENT = {38, 40}
```

### D3 — Factsheet: parse the S/N table

One table row = one `Section N`. Exclude the cover page, the Arrangement block and the PLAC
boilerplate/footer from retrieval.

**Target (amended 2026-09-18, before implementation, on measurement):**
`general` ≤1% · **`row_spanning` 0** · `packed` **re-scoped, not gated**.

> ## ⚠ THE ORIGINAL `packed 0` TARGET IS UNREACHABLE, AND MEASUREMENT SAYS SO
>
> This step was written as *"`general` ≤1% · `packed` 0"*, by analogy with D2's Act gate.
> Measuring the factsheet **before writing anything** showed that **`packed 0` and
> `evalset.verify_expected()` cannot both hold.**
>
> Eight sections are **never row anchors**. They exist only as cross-references inside another
> row's provisions — *"…may also accept a gift of land, money or property… - section 46"*:
>
> | section | lives in row | expected by |
> |---|---|---|
> | 11 | 7 (Section 10) | **frozen10/Q6**, heldout/H26 |
> | 13, 15 | 9 (Section 14) | test/T2, test/T3 |
> | 23 | 15 (Section 22) | heldout/H28 |
> | 34, 35 | 20 (Section 32) | heldout/H13, test/T7 |
> | 46, 53 | 25 (Section 45) | heldout/H12, test/T17 |
>
> `scripts/evalset.py:161` `verify_expected()` is a **hard assert, not a metric** — *"an expected
> number that no chunk carries is a ground-truth bug"*. An anchor-only ref would drop those eight
> numbers out of the corpus and crash `eval_heldout.py`, `eval_phase06.py` and `audit_corpus.py`.
> The only escapes are editing **frozen10**, which this repo forbids outright, or deleting
> held-out/test expectations — i.e. moving the yardstick to make the number pass.
>
> **So the ref carries the row's anchor PLUS the sections that row genuinely discusses.** Measured
> both ways against frozen10 ∪ heldout ∪ test: anchor-only leaves a coverage gap of exactly
> `[11,13,15,23,34,35,46,53]`; anchor+cross-reference leaves `[]`.
>
> **A multi-number factsheet ref is therefore a declared NON-DEFECT** — it is the table's own
> content, not damage. `packed` stays reported, unchanged and unhidden, and is **not** tuned away
> (`V2_MAX_PACKED` is untouched). The real defect — a chunk cut **across** rows — gets its own
> metric, `row_spanning`, measured from the chunk TEXT so it can actually fail: **v1 scores 26 of
> 48, v2 scores 0 of 32.**
>
> This is the same lesson D2 learned about the `act_ref` validator, applied before the fact instead
> of after: a target written before measurement, which measurement shows was aimed at the wrong
> thing.

### D4 — Constitution: exclude the Arrangement pages, and nothing else

Keep `constitution_aware_split`. Keep **`CONST_SIZE = 400`** (`src/rag.py:55`).

`_is_toc_fragment` (**`src/rag.py:201-246`**) is **kept and demoted to a lint assertion**.
**Do not delete the heuristic.** It is the Fix-B widening that made `MANUAL_FLAGS == []`, and
deleting it would silently restore the Q10 s.39 misattribution class.

**Record explicitly, with Finding 2's measurement, that the section-unit re-extract (2104 → ~500)
is deferred to Phase E, and why** — it is not needed for the gate, and it is the riskiest change
in the original plan.

> **MEASURED 2026-09-18, BEFORE WRITING ANY CODE — Finding 2's "`general` → ≈0" IS WRONG, AND
> THE ≤1% GATE IS UNREACHABLE BY ARRANGEMENT EXCLUSION ALONE.** This is D3's lesson for the
> second time: a target written before measurement, aimed at the wrong thing. **Re-scope it
> honestly; do not tune the yardstick, and do not delete text to hit a number.**
>
> Arrangement exclusion takes the Constitution **2104 → 2037 chunks** and `general`
> **99 (4.71%) → 34 (1.67%)**. `V2_MAX_GENERAL_PCT = 1.0` therefore still **FAILS**, and 1.67% is
> the floor for this step. The residual 34 is **two classes, neither of which is a defect**:
>
> | class | n | what it is | why `general` is CORRECT |
> |---|---|---|---|
> | `general_unnumbered` (no `§` prefix) | **8** | Preamble ×2, chapter-divider headings ×6 (`Chapter III - Citizenship: Citizenship`) | has no section number at all; any label would be fabrication |
> | `general_toc` (`§` present, `_is_toc_fragment` demoted it) | **26** | **all 26 in Chapter VIII** — Second/Third/Seventh Schedule legislative-list *items* (`8. Census`, `63. Traffic`) and the Fundamental Rights (Enforcement Procedure) Rules (`ORDER 6`, `FORM NO. 4`, dotted-rule boilerplate) | Schedule **item** N is a different numbering scheme from **section** N. Item 8 "Census" is not s.8. Labelling these `s. N` would be the Q10 misattribution class, deliberately re-created |
>
> **Deleting the Schedules to pass the gate is forbidden** — the Second Schedule is operative law
> and the Enforcement Procedure Rules are the mechanism a PWD uses to enforce Chapter IV. "Exclude
> the Arrangement pages, **and nothing else**" is the instruction.

#### The cut point — keep the Preamble

Chapters I–VIII appear **twice** in `constitution_1999_NHRC.txt`: the first pass (chars
124–14,791) is the Arrangement listing, the operative body starts at the **second** `Chapter I`
(char 18,535). The naive cut is that second heading — and it is **wrong**: the real Preamble
(*"We the people of the Federal Republic of Nigeria … Do hereby make, enact and give to ourselves
the following Constitution:-"*, char **17,917**) sits between the two and would be silently
deleted. **Cut at the Preamble, not at the second chapter heading.** Measured: cut@Preamble keeps
it (2037 chunks, `general` 34); cut@2nd-Chapter-I loses it (2035, 32).

#### The re-scoped gate: `toc_general` outside the Schedules

Same construction as D3's `row_spanning`, and for the same reason — **a metric measured from
construction restates the code and is worth nothing as a gate.** Count, from each emitted chunk's
**text**, the chunks that carry a `§` prefix *and* were demoted by `_is_toc_fragment`, split by
whether they sit in Chapter VIII:

- **Gate: `toc_general` outside Chapter VIII == 0.**
- **Demonstrated discriminating power: v1 scores 7, D4 scores 0.** Not assumed — measured.
- The 7 v1 chunks are the Arrangement tails, and **the 7th is the Q10 trap chunk itself**:
  `Chapter IV - Fundamental Rights §39: "ion from fundamental human rights. 46 Special
  jurisdiction of High Court and Legal aid."` So **D4 cures the Q10 class at source** — the
  chunk ceases to exist — where `_is_toc_fragment` only ever *mitigated* it by relabelling.
  The heuristic survives as the lint that proves the cure held.
- **Also pin the inventory**: `general == 34`, decomposing as 8 unnumbered + 26 Chapter VIII, so a
  new `general` chunk anywhere becomes visible rather than averaging away.
- **Stated limitation, not to be papered over:** "in the Schedules" is proxied by the
  `Chapter VIII` label that `constitution_aware_split` prepends. Chapter VIII also holds operative
  sections 297–320, so a genuine Ch VIII *body* chunk demoted by the heuristic would be invisible
  to this gate. The pinned inventory above is what covers that hole.

#### Coverage — the D3 trap does NOT fire here, and that is measured

`evalset.verify_expected()` is a hard assert and exclusion **removes** text, so this was checked
first, exactly as D3 was: **sections reachable from a Constitution ref are 318 before and 318
after — 0 lost, 0 gained.** The 17 numbers the evalsets expect
(`6,16,17,18,34,35,36,40,42,45,46,65,66,77,85,117,251`) are all still reachable. No frozen10,
held-out or test expectation is at risk. Unlike D3, **no ref-shape change is needed.**

#### Deferred to Phase E, by name

**Schedule/Rules chunks get no citable ref of their own in D4.** Giving them one
(`Sch. 2 item 8`) means a **fourth numbering scheme** through `cite_tag()`, the citation
invariant and the LLM prompt — real work, and out of scope here. It is the honest fix for the 26,
and it is why the ≤1% gate should be re-scoped rather than chased.

#### Shape of the change

Mirror D2/D3: a new `_const_chunks_v2()` beside `_const_chunks_v1()`, wired only in
`build_corpus()`'s v2 branch. **`CONST_SIZE` does not move. `CORPUS_VERSION` stays `"v1"`.
`docs` insertion order does not change** (`src/retrieve.py:331-338` breaks score ties by it).
`audit_corpus.py` changes are **reporting only** — `V1_EXPECTED`, `V2_MAX_GENERAL_PCT` and
`V2_MAX_PACKED` all stay untouched, so the 1.67% FAIL stays visible in stdout until **D6**
re-scopes it, exactly as D3 left the factsheet's `packed 16` FAIL visible.

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

#### D5 RESULTS — 2026-09-19. **`MIN_SCORE` did not move. Measurement discharged the step.**

Zero Gemini calls. One new file (`scripts/calibrate_refusal.py`) plus three comment blocks
rewritten; **no behaviour changed anywhere**, which is why the entire regression sweep reproduces
byte-identically.

| measured | v1 | v2 |
|---|---|---|
| false refusals, frozen10 / dev / test | 0/10 · 0/25 · 0/17 | **0/10 · 0/25 · 0/17** |
| off-corpus clearing the floor, dev / test | 5/5 · 3/3 | **4/5 · 3/3** (H25 0.1032 → refused) |
| in-corpus minima, frozen10 / dev / test | 0.1696 (Q6) · 0.1359 (H11) · 0.1285 (T1) | **0.2287 (Q10) · 0.1369 (H11) · 0.1209 (T9)** |
| off-corpus maxima, 12 probes / 8 refuse rows | 0.3180 · 0.4193 (H23) | **0.3180 · 0.4195 (H23)** |
| band | INVERTED | **INVERTED** (0.1209 vs 0.4195) |
| `ablate_phase08` refusal regressions · floor-defeat flips · 34-key flips | none · none · none | **none · none · none** |
| recall_strict frozen10 / dev / test | 0.701 · 0.407 · 0.338 | **0.633 · 0.473 · 0.471** |

**`MIN_SCORE` stays `0.10`.** The hazard D5 exists to catch — longer v2 chunks pulling cosines
down into false refusals — **did not materialise on any set**. v2 is marginally *better* on the
false-answer side (one fewer off-corpus row clears the floor), and the band is still inverted on
**both** corpora, so no value above 0.10 would buy semantic discrimination anyway. That stays the
strict-prompt `NO_ANSWER_SENTENCE` layer's job.

**The escape hatch is DECLINED, because its trigger never fired.** A second frozen v1 index for
the answer/refuse decision is warranted only by an actual false refusal; there were **zero across
52 answerable rows × 2 corpora**. Paying for two indexes to solve a problem measurement says does
not exist is cost with no purchase.

**The 212-probe invariance result retires a caveat in the source.** `src/retrieve.py` said the
refusal-invariance proof rested on "a run nobody can reproduce" and asked Phase 10 D for the
battery as a committed script. It now exists: 106 probes (60 eval rows + 12 `OFF_CORPUS` + 34 bare
`SYNONYMS` keys, all **imported**, never copied) × both corpus versions, built in one process on
the shipping arm — **212 probe-runs, 0 disagreements.**

**All three gates are negative-tested by injection**, not by reading (`--negative-test`):

- **Gate 2** — v2's floor → 0.30 **asymmetrically** (raising both arms together could push them
  under as a pair and still satisfy `v2 ≤ v1`, proving nothing). Fires, naming 38 offenders.
- **Gate 3** — `MIN_SCORE` → 0.11. Fires.
- **Gate 1** — **the prescribed injection does not falsify it, and that is recorded rather than
  glossed.** Passing `floor=0.0` to `select_top` while still filtering at `MIN_SCORE` — the
  "latent inconsistency" its own docstring describes — leaves invariance **intact**, because the
  global maximum is in the output at *every* floor (at 0.0 the quota phase takes each doc's best
  hit, and the global max *is* some doc's best hit). The inconsistency is real but changes *which
  six chunks are shown*, not the refusal decision. The gate is proven live instead by a mutant
  selector that drops the global max: **2 disagreements, fires.**

**Frozen-10 attribution (the bounded diagnosis).** The 0.925 → 0.666 plain-recall drop is the
**packed-ref subsidy** being withdrawn, not a ranking regression. Packed chunks retrieved across
the 10 questions fall **14 → 5**, and all 12 lost expected refs sit in the 7 questions that had
them — Q2 alone loses `act 5,6,7` + `fact 6,7`, which v1 satisfied from three packed chunks.
`recall_strict`, which never granted that subsidy, moves only **0.701 → 0.633**, and per question
is *flat or better* on 6 of 10 (Q8 improves 0.500 → 0.750). Top scores largely rise (Q6 0.1696 →
0.2459, Q8 0.3049 → 0.5416). **Nothing was tuned on this** — the block is marked report-only in
the script, for the contamination reason `evalset.py` exists.

#### Handed to D6 by D5

> **⚠ `eval_heldout.py:438`'s v1 guard reads the WRONG VARIABLE — D5 finding, 2026-09-19.**
> `assert CORPUS_VERSION == "v1"` tests the **module constant** imported from `rag.py`, not the
> **effective** version selected by `--corpus=`. Under `--corpus=v2` the constant is still `"v1"`,
> so the assertion **never fires**, and the run instead trips the frozen-10 recall guard it was
> written to pre-empt (`0.666 vs 0.925: FAIL`). The symptom is the recorded v2 exit 1; the cause is
> this. `main()` *does* parse the effective value into a local `corpus` and uses it correctly two
> lines later (`print("CORPUS_VERSION=%s" % (corpus or CORPUS_VERSION))`) — the guard simply reads
> the wrong one of the two.
>
> **Second symptom, same cause:** the guard line also *stamps* itself from the constant, so a
> `--corpus=v2` run prints `frozen-10 recall 0.666 vs recorded baseline 0.925 (corpus v1): FAIL`
> — **mislabelling a v2 number as v1**, which directly contradicts the file's own docstring
> ("Every table is stamped with `CORPUS_VERSION`… a recall number that lacks that stamp is a v1
> number"). Fix both occurrences, not just the assert. **Recorded, not fixed in D5** — D5's scope
> is the floor. **D6's fix:** compare against the
> *effective* version (the parsed `--corpus=` value), and gate v2 on **`recall_strict`** against a
> **separate constant** (`FROZEN10_RECALL_STRICT_BASELINE_V2 = 0.633`), leaving
> `FROZEN10_RECALL_BASELINE_V1 = 0.925` guarding v1 — exactly the split `eval_heldout.py:131-136`
> already argues for and stops short of implementing.

> **⚠ `SYN:car` — the one v1→v2 refusal flip, and it is NOT a false refusal. D5 finding,
> 2026-09-19.** Bare `car` goes 0.1141 → 0.0794 and is refused under v2. It *looks* like a false
> refusal (v2 Act cl. 12 **is** "Reserved spaces … public parking lots", so `car` is on-corpus),
> but **v1 never answered it correctly**: 0.1141 just cleared the floor, which let
> `PerDocRetriever.query`'s **entry gate** admit it to expansion, and the expanded query
> (`car vehicle transport parking road`) top-1'd **Constitution s. 40** (assembly and association)
> at 0.2126 — a junk answer produced by expansion manufacturing overlap, the exact defect that
> entry gate is documented to prevent. v2 refuses, and its best *bare* hit is the **correct** chunk
> (Factsheet "Section 12 Reserved Places"). **Real sentences are unaffected and improve**: "is
> there accessible parking for people with disabilities" 0.2157 → 0.2802; "do I have a right to
> accessible public transport" 0.3180 → 0.3174.
>
> **The floor is not the thing to change** — clearing 0.0794 means dropping `MIN_SCORE` by ~25%
> while the band is inverted, admitting more off-corpus junk to rescue one bare word. The open
> question is that **a one-word query is too thin to reach its own correct chunk**, which is a
> *ranking* problem for D6/E, not a *floor* problem. `calibrate_refusal.py` therefore **reports
> the 34 bare keys with every flip named, but does not gate them** — see `classify()` for the
> argument. Note that `ablate_phase08`'s "34-key flips: none" measures a **different axis**
> (expansion on/off *within* one corpus) and is not contradicted by this.

### D6 — re-baseline, zero quota

> **⚠ PREMISES CORRECTED BEFORE D6 STARTS — planning pass 2026-09-19, nothing executed.**
> Three things were found by diffing the surviving D5 baselines in `D:\d5_baseline\` rather than
> by reading code. They are written here with their evidence paths so the next session can
> **re-derive them rather than trust them** — every line number below is a line in those two
> files, which are plain stdout captures and can be re-read at any time.
>
> **(1) The stamp bug is FIVE sites, not one.** D5's handoff recorded `eval_heldout.py:438`.
> The same wrong read is at **`eval_heldout.py:244`, `:373`** and **`eval_chat.py:344`, `:411`** —
> every per-set and headline table interpolates the module constant `CORPUS_VERSION` instead of
> the effective `--corpus=` value. Only the two banner lines (`eval_heldout.py:341`,
> `eval_chat.py:371`) get it right, and they do it with `(corpus or CORPUS_VERSION)` — which is
> the one-token fix for the other five. **Evidence:** `chat_v2.txt:1` prints `CORPUS_VERSION=v2`
> and `:2` prints the v2 corpus shape
> (`act2018 65 · constitution1999 2037 · factsheet2020 32`, vs v1's `62 · 2104 · 48` at
> `chat_v1.txt:2`), and then **`:10`, `:110` and `:197` of the SAME FILE all print
> `(corpus=v1, …)`**. Note `eval_heldout.py:438` is not quite the same animal — it is the
> frozen-10 `assert CORPUS_VERSION == "v1"` guard, which fails *open* rather than mislabelling —
> but it reads the same wrong variable and is fixed by the same change.
>
> **(2) `eval_chat --corpus=v2` exits PASS, and THAT IS THE PROBLEM.** `chat_v2.txt:218` reads
> `EVAL_CHAT: PASS`, identically to `chat_v1.txt:218`. All 51 refs still verify (`:3` in both).
> The Phase B gates (`:206-208`) are computed on **`chat_dev`**, the tuning set, and all three
> still pass. Underneath, on the blind set:
>
> | `chat_test`          | v1 (`chat_v1.txt`)            | v2 (`chat_v2.txt`)            |
> |----------------------|-------------------------------|-------------------------------|
> | ellipsis (n=5)       | `0.200 → 0.600  +0.400` **gain class** (`:146`) | `0.000 → 0.000  +0.000` **DID NOT IMPROVE** (`:146`) |
> | pronoun (n=5)        | `0.400 → 0.400  +0.000` **DID NOT IMPROVE** (`:150`) | `0.400 → 0.600  +0.200` **gain class** (`:150`) |
> | topic-shift (n=3)    | `0.000 → 0.333  +0.333` (`:151`) | `0.667 → 0.667  +0.000` (`:151`) |
> | headline             | `0.435 → 0.565  +0.130` (`:200`) | `0.478 → 0.522  +0.043` (`:200`) |
>
> The `n-strict`/`c-strict` columns are **identical to the plain ones in every row above**, on
> both corpora — so this is **not** the packed-ref subsidy. It is a real ranking move.
> Per turn, three ellipsis turns lost their contextualised hit — `CT2.t2` (`1.000/1.000 →
> 0.000/0.000`), `CT2.t3` and `CT4.t3` (both `0.000/1.000 → 0.000/0.000`) — while `CT1.t3` went
> `0.000/0.000 → 1.000/1.000` and `CT4.t2` went `0.000/1.000 → 1.000/1.000`. The net on the blind
> set is roughly flat; the **class structure underneath it inverted**, and the harness said PASS.
>
> **The sharpest instance is on the tuning set, where the gate looks straight at it.**
> `chat_dev`'s pronoun row is `0.571 → 0.714 (+0.143)` in v1 (`chat_v1.txt:55`) and
> `0.143 → 0.286 (+0.143)` in v2 (`chat_v2.txt:55`). **The delta is byte-identical; the level
> fell by a factor of four.** The Phase B gate is phrased "ctx BEATS naive", so it reads the
> delta and passes both times (`chat_v1.txt:207` `0.571 -> 0.714 PASS`; `chat_v2.txt:207`
> `0.143 -> 0.286 PASS`). A gate on a delta cannot see the level move underneath it.
> **D6 must not read that PASS as permission to flip.**
>
> **(3) Two playbook predictions already came true** — confirm them, do not re-guess them.
> `CT1.t1` carries `<-- FALSE REFUSAL` at `chat_v1.txt:112` and **the marker is absent from
> `chat_v2.txt:112`** (the recall is still `0.000/0.000`, so the refusal is fixed and the ranking
> is not — both halves matter). `CT7.t2`, recorded below as "unscoreable, not missed", goes
> `0.000 → 0.000` at `chat_v1.txt:130` and **`0.000 → 1.000` at `chat_v2.txt:130`**: now
> scoreable, exactly as this playbook predicted.

> **⚠ ORDER OF OPERATIONS — the stamp fix lands BEFORE the `CORPUS_VERSION` flip.**
> This is invisible in a diff, so it is written down. While `src/rag.py:48` still reads
> `CORPUS_VERSION = "v1"`, the stamp fix is **provable**: a `--corpus=v2` run's tables must flip
> from `corpus=v1` to `corpus=v2` while the plain `--corpus=v1` run stays **stdout
> byte-identical**. That is a two-sided check — it catches both a missed site and an
> over-eager one.
>
> **After the flip, both readings are `v2` and the proof is gone**: the buggy expression and the
> correct one return the same string, forever. Fix the five sites, demonstrate the flip in
> stdout, commit that; then flip the constant in a separate commit.

> **⚠ BLAST RADIUS OF THE ONE-LINE FLIP.** `src/rag.py:48` is one line, and three suites change
> what they test the moment it moves, silently, because they call `build_corpus()` with **no
> argument**: **`app.py:458`** (`return PerDocRetriever(build_corpus())` — the user path),
> **`scripts/test_phase05.py:73`** (the 137-assert UI suite) and
> **`scripts/test_phase09_ops.py:218`** (the 51-assert ops suite, which then feeds a frozen
> question through real retrieval). Add `src/rag.py:642`, `ask()`'s own fallback build, from the
> D1 caller-policy table.
>
> These are correct as written — the user path *should* follow the default. The hazard is that
> nothing announces the change. **Any assert that fails there is pinned to v1 chunk content, and
> that is a FINDING to record, not a number to relax.**

- Flip `CORPUS_VERSION` to `"v2"`. **Keep the v1 tripwire runnable** so the published shape stays
  provable.
- **Add `V2_CORPUS_SHA256`, mirroring the v1 pin.** `audit_corpus.py:141` defines
  `V1_CORPUS_SHA256` and `:586-597` checks it; v2 has **no equivalent**. After the flip the
  **shipping** corpus would be less protected than the retired one — the exact inversion the
  fingerprint was introduced to prevent, since `V1_EXPECTED`'s integers cannot see text moving
  between chunks at constant count. Pin it in the same commit as the flip.
- **`audit_corpus.py` becomes the gate**: ≤1% general, 0 packed, 58/58 clauses citable, `act_ref`
  validator agrees — **and `ACT_KNOWN_ABSENT` is DELETED, not emptied**, so nobody can re-add a
  clause to it. Its "SINGLE-SOURCE for now" caveat (`:202-205`) and the "the pixels do not exist"
  line (`:215`) go with it.

> **⚠ D6 MUST GATE THE FACTSHEET ON `row_spanning == 0`, NOT ON `packed == 0` — D3 finding,
> 2026-09-18.** `V2_MAX_PACKED = 0` is correct for the Act and the Constitution and **wrong for the
> factsheet**, where a multi-number ref is the table's own content rather than damage. Eight
> sections (11, 13, 15, 23, 34, 35, 46, 53) are never row anchors and exist only as cross-references
> inside another row's provisions; `evalset.verify_expected()` — a **hard assert** — needs every one
> of them, and **frozen10/Q6 expects 11**, so an anchor-only ref is not available at any price. See
> the boxed evidence under **D3**.
>
> D3 left the threshold alone deliberately, so `audit_corpus.py --corpus=v2` prints
> `factsheet2020 packed refs 16 <= 0: FAIL` with the explanation next to it and the collision stays
> **visible in stdout** until D6 resolves it. D6 must make `V2_MAX_PACKED` per-doc (or exempt the
> factsheet by name, with this reasoning in the code) **and** assert
> `stats["factsheet2020"]["row_spanning"] == 0`. Do NOT close the gate by deleting or weakening the
> `packed` column — it is still the right metric for the other two docs, and the factsheet's real
> defect count is `row_spanning`, which is measured from chunk TEXT and has demonstrated
> discriminating power (**v1 26/48, v2 0/32**).

> **⚠ D6 MUST ALSO RE-SCOPE THE CONSTITUTION'S `general` GATE — D4 finding, 2026-09-18.**
> `V2_MAX_GENERAL_PCT = 1.0` is **unreachable for the Constitution** and D4 left it untouched on
> purpose, so `--corpus=v2` keeps printing `constitution1999 uncitable 1.7% <= 1.0%: FAIL` with the
> reason beside it. Arrangement exclusion is the whole of the available fix (99 → 34 general);
> the residual 34 is **8 structurally unnumbered** chunks (Preamble, chapter dividers) and
> **26 Chapter VIII Schedule/Rules** chunks where `general` is the *correct* answer, because a
> Schedule **item** number is not a **section** number and labelling it `s. N` re-creates the Q10
> misattribution class on purpose. **Do not close this gate by deleting the Schedules** — the
> Second Schedule is operative law and the Enforcement Procedure Rules are how a PWD enforces
> Chapter IV. D6 should gate the Constitution on **`toc_general` outside Chapter VIII == 0**
> (measured from chunk text; **v1 scores 7, v2 scores 0**) plus the pinned 8+26 inventory, and
> record the `Sch. N item M` fourth-numbering-scheme fix as Phase E work. See the boxed evidence
> under **D4**.

> **⚠ D6 MUST RE-SCOPE THE `act_ref` VALIDATOR BEFORE ASSERTING ON IT — review finding 2026-09-18.**
> D2 measured **65/65 = 100% agreement**, and that number is worth much less than it looks.
> The two "independent sources" **share an upstream**: the parser writes
> `header = "%d. %s" % (n, title)` from the same `n` it builds `ref` from, `_act_chunks_v2()`
> prefixes that header to every sub-chunk, and `act_ref()` then recovers the leading `\d+\.` from
> that very string. For a single-clause chunk the comparison is therefore **close to a tautology** —
> the sources differ in *inference* (manifest lookup vs heading-shape regex), **not in upstream**.
> This is **not** the `evalset.assert_frozen10_matches_notebook()` discipline it was written up as;
> there, the notebook and the JSON really are authored separately.
>
> It still genuinely catches two things: a stray line-start `NN.` in body text flipping `act_ref()`
> to a multi-number member list, and header/ref drift introduced by future chunking changes.
> **So D6 should either validate against the Arrangement TITLE text** (which does not share the
> numeral's upstream) **or scope the assert to those two cases — never promote the raw rate as a
> cross-source gate.** The v2 stdout now states this limit in place, next to the number.
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
  should make it scoreable; check it explicitly rather than assuming. **Now confirmed:
  `0.000 → 1.000` at `chat_v2.txt:130`.** Record it as a prediction that held, and drop the
  "unscoreable" caveat from the set's notes at the same time.

**The mechanical half of this step is already done, and that is the trap.**
`chat ground truth verified against corpus: 51 expected refs` prints at **`chat_v2.txt:3`** —
`verify_expected()` passes on v2 unchanged. Every one of the 51 refs still resolves to some chunk.
So D6's real work here is **not** re-verification; it is **triage of every turn that moved**:

- **Ground truth now wrong under v2** → `"status": "retired-v2"`, stays in the file, excluded from
  means. This is the `questions.json` discipline, applied unchanged.
- **Ground truth still right, ranking got worse** → **record it and hand it to Phase E.** Do not
  retire a turn because it got harder. Retiring a regression is how a corpus rebuild launders
  itself into a win.
- **Use the `recall_strict` columns to tell those apart.** `eval_chat` already publishes
  `n-strict`/`c-strict` beside `naive`/`ctx` — the same separation D5 used on frozen-10. In the
  D5 baselines the strict and plain columns are **identical on every `chat_test` class row on both
  corpora**, which is what rules the packed-ref subsidy out and makes the ellipsis collapse a real
  move rather than a scoring artifact. If a future row shows them diverging, the plain column is
  the one lying.
- **The concrete triage list**, from the baselines, so the next session starts from evidence:
  regressions **`CT2.t2`, `CT2.t3`, `CT4.t3`** (all ellipsis, all lost the contextualised hit);
  improvements **`CT1.t3`, `CT4.t2`** (topic-shift) and **`CT7.t2`** (now scoreable); and
  **`CT1.t1`**, whose false-refusal marker is gone while its recall is still `0.000` — a fixed
  refusal and an unfixed ranking, which must be reported as both.

> **⚠ `chat_dev` IS THE TUNING SET. Re-tuning on v2 numbers SPENDS `chat_test`.**
> `CARRY_WINDOW=2 / THIN_MAX=3 / MARKER_MAX=4 / QUESTION_WEIGHT=2` (`chat_v1.txt:8`, unchanged at
> `chat_v2.txt:8`) were chosen on `chat_dev` **only**. `chat_test` is the last blind set in this
> project — the 30 held-out single-turn questions were already spent on 2026-09-13 by reading
> which refs they missed.
>
> v2 will make re-tuning look attractive, because `chat_dev`'s pronoun level fell `0.571 → 0.143`
> while its delta held. **Resist it.** Touching those four constants in response to a v2 number
> converts `chat_test` from a blind set into a second tuning set, and no later number from it
> means anything. If the thresholds genuinely need to move, that is **Phase E with a newly
> authored set**, not a D6 side-effect.

#### D6's gate re-scopes, as a checklist

Each of these has a ⚠ box above with the evidence; this is the executable summary, against line
numbers already identified.

- [ ] **Factsheet: assert `row_spanning == 0`**, make `V2_MAX_PACKED` per-doc (or exempt the
      factsheet by name, with the reasoning in the code). **Keep printing `packed`** — it is still
      the right metric for the other two docs. Gate block at `audit_corpus.py:628-643`, which
      already names the re-scope in place.
- [ ] **Constitution: assert `toc_general_out_ch8 == 0`** plus the **pinned 8 + 26 inventory**
      (a new demotion anywhere changes one of those two integers — that inventory is what covers
      the stated Chapter VIII proxy hole). Gate block at `audit_corpus.py:602-627`. **Do not close
      it by deleting the Schedules.**
- [ ] **`act_ref`: scope the assert to the two cases it genuinely catches** — a stray line-start
      `NN.` in body text, and header/ref drift from future chunking changes.
      **Never promote the raw 65/65 rate as a cross-source gate**; the sources share an upstream.
      `act_ref_validator()` at `audit_corpus.py:346-377`.
- [ ] **`ACT_KNOWN_ABSENT` DELETED, not emptied** — `audit_corpus.py:126`, with its readers at
      `:295`, `:297`, `:308`, `:452`, `:482` and its caveats at `:202-205` and `:215`. An empty set
      is an invitation to re-add a clause; a deleted name is a `NameError`.
- [ ] **`V2_CORPUS_SHA256` pinned**, mirroring `V1_CORPUS_SHA256` (`audit_corpus.py:141`,
      checked at `:586-597`).
- [ ] **The five stamp sites fixed** — `eval_heldout.py:244`, `:373`, `:438`; `eval_chat.py:344`,
      `:411` — **before** the flip, using the `(corpus or CORPUS_VERSION)` form already at
      `eval_heldout.py:341` / `eval_chat.py:371`.
- [ ] **`ablate_phase08`'s `recall > 0.75` gate re-scoped**, per the D5 handoff.

#### D6 exit criteria

So the next session can check itself rather than argue:

1. **Every gate green on its re-scoped metric, with the OLD metric still printed beside it.**
   A re-scope that deletes the superseded column is indistinguishable from tuning the yardstick.
2. **v1 fully reproducible from the same commit via `--corpus=v1`** — `eval_heldout`,
   `eval_chat`, `ablate_phase08`, `audit_corpus` **stdout byte-identical** to the D5 captures in
   `D:\d5_baseline\`, and `eval_phase06.py` still hashing **`CE716FB3…5F19`** (to a
   `--out=` path, **equals form only**).
3. **Every new guard negative-tested by injection** — D5's standard, and D5's own gate 1 is the
   reason it is non-negotiable: a gate whose prescribed injection could not falsify it had been
   passing for free. A guard that has never been made to fail has not been shown to work.
4. **`MIN_SCORE` still `0.10`.** D5 re-derived it against v2 and it did not move; D6 re-baselines
   retrieval and must not quietly relitigate the floor. **Do not re-open the `SYN:car` question.**
5. **Every moved chat turn triaged and dispositioned in writing** — retired-v2, or handed to E.
   Silence on a moved turn is a failed exit.
6. `scripts/baseline_v2_<date>.txt` archived, so D7+ has a "before" set on disk the way D5 left
   one for D6. **That is the only reason these findings exist** — see the journal entry.

---

## Claims Phase D retires by name

| claim | status |
|---|---|
| `ACT_KNOWN_ABSENT = {38, 40}` and *"no OCR can recover it"* | **FALSE** (Finding 1) — cl.40 was never absent; cl.38 is absent from v1 but present in the gazette |
| *"cl.38's body is present in v1 at L614"* (published in `4bcc763`) | **FALSE** (corrected 2026-09-17) — L614 is **clause 48** |
| *"the duplicate page did not cost cl.38 or cl.40"* (published in `4bcc763`) | **FALSE** — it cost cl.38's opening and (a)–(i) (Finding 1a). It did not cost cl.40 |
| *"v1's Arrangement is the source of `ACT_CLAUSES = range(1, 59)`"* (`audit_corpus.py:64-66`) | **FALSE source, right number** — v1's Arrangement stops at 51 (Finding 1c) |
| *"Act chunks are section-aware 800"* (`CLAUDE.md`) | **misleading** — `SECTION_RE` matches 4× in the whole Act TXT, all in the Schedules, so the operative body is plain `recursive_split(…, 800)` |
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
git diff main -- data/processed/disability_act_2018_full.txt    # must stay EMPTY
```

> **Why the second guard exists.** The playbook has always guarded `requirements.txt` and never
> guarded the v1 Act TXT — yet that file is the one artifact `scripts/ocr_local.py` can **silently
> clobber on import** (see D2's implementation notes), and it is the text every published baseline
> in this repo is measured against. v2 writes **new** files; v1's TXT is never touched by any step
> of Phase D. If this diff is ever non-empty, stop and restore before running anything else — the
> baselines are gone, not just different.

## Results

### Session 2026-09-17 — D0 filed, D1 landed, D2's gate answered **GO**

Scope was deliberately D0 + D1 + D2's go/no-go gate, stopping before the parser. Zero Gemini
quota spent. No new packages. `requirements.txt` and the v1 Act TXT both ended the session with
an **empty** diff vs `main`.

Preceded by two housekeeping commits: the orphaned 2026-09-17 doc pass (740 lines, including the
Finding 1 correction that **v1 L614 is clause 48, not clause 38**) was committed rather than left
to die on a `git checkout`, and the Phase 10 A/B/C stack shipped as PR #12 → merged to `main` →
auto-deployed to Render. That deploy is the first time users get the chatbot instead of the
single-turn form.

**D0 — gazette filed.** `data/raw/disability_act_2018_gazette_FGP.pdf`, verified from its cover
page before filing: *Official Gazette No. 10, Vol. 106, Lagos, 21 January 2019, Act No. 2, pages
A97–A122*, Federal Government Printer (FGP 007/12019/700). 27 pages, **no text layer**. Recorded
in `data/raw/SOURCES.md` as the authoritative source: where the free web transcriptions v1 was
built from disagree with the gazette, the gazette wins. Its own commit, per plan.

**D1 — versioned scaffolding.** Exactly one corpus version still exists and it is the
byte-identical v1 path.

| Item | Outcome |
|---|---|
| `Chunk` gains defaulted `path` | Done. All three 3-arg construction sites untouched, as predicted. |
| Arity sweep | Clean. No `len(chunk)`, `[*chunk]`, `zip(*)`, `Chunk(*)` or 3-way unpack on a `Chunk`. |
| Known near-miss | Confirmed harmless: `bench_phase01.py:244-250` unpacks `chunk_stats()`'s `(n, avg, max)` from a `list[str]`. Left alone. |
| `build_corpus(version=None)` | Pure relocation — the three loading bodies do not appear in `git diff -w` at all. No memoization, no dict reordering, no `version=` on `ask()`. |
| Caller policy, 14 sites | 6 got `--corpus=` (**equals form only**), 5 left bare, 3 quota-bound files not opened. `router._retriever` left unkeyed. |

**Two prose claims became real gates, and both were negative-tested** — a gate that cannot fail is
worthless:

- `corpus_sha256()` pinned at `25650238…e89a`. Shifting **one character between two adjacent Act
  chunks** leaves the count at 62 and all nine shape integers identical; the digest catches it.
  Reordering the docs dict — which silently moves published rankings via `PerDocRetriever`'s
  insertion-order tie-break — is also caught.
- `eval_phase06.py` asserts its results digest `ce716fb3…5f19`. **Windows-specific by
  construction**: `Path.write_text()` writes CRLF (594 pairs) and the published digest is of those
  bytes, so it reads the file back from disk as bytes. It fails with that explanation rather than a
  bare `AssertionError`.

**Stdout re-baselined, not broken silently:** `audit_corpus.py` gains two sha256 lines,
`eval_phase06.py` appends ` sha256=…`. Both pure additions; every other line of all five harnesses
reproduces byte-identically against baselines captured *before* the first edit.

### D2 GO/NO-GO GATE — **GO**

> **The gazette's Arrangement of Sections yields a clean `1..58` — no holes, no duplicates, nothing
> out of range.** D2's manifest-anchored parser is unblocked and titles come from the Arrangement.
> The written-in-advance **marginal-note fallback is not needed and was not used. No title was
> authored.**

Pages 2–4 (A97–A99) OCRed at dpi 200, ~12 s/page, average confidence 0.978–0.984. Finding 1c was
right that this could not be settled against v1: v1's Arrangement truncates at L77 because it lost
the page carrying 52–58. That page is present and legible in the gazette.

**The near-miss worth recording.** The first parse read **23 of 58** and looked exactly like a
truncated source. It was not. RapidOCR emits the clause number and its title as **separate boxes**
(`"3."` | `"Right of access to public premises."`) whose vertical centres differ by a few pixels —
often enough that the title sorts *before its own number*. A text-only, line-at-a-time parse cannot
see this. Grouping boxes into visual rows by vertical overlap, then ordering left-to-right, recovers
all 58. **This is the same class of failure that left 25/62 v1 Act chunks uncitable**, and it is the
concrete vindication of keeping the geometry `ocr_local.py`'s assembler threw away.

Reported, not patched: clause 26 parses as `"S Service at queues."` — OCR duplicated the title's
first letter into the number's box. Flagged for D2's parser to decide.

One clause-38 caution: its **title** is present in the Arrangement, which says **nothing** about
whether its **body** is in this scan. `ACT_KNOWN_ABSENT = {38, 40}` is untouched and **D6 still
owns deleting it** — after the re-OCR that actually recovers the body.

### A live hazard found and fixed

`scripts/ocr_local.py` had a bare `main()` at module scope with no `__main__` guard, and `main()`
unconditionally overwrites `data/processed/disability_act_2018_full.txt` — the v1 Act corpus every
published baseline is measured against. **`import ocr_local` destroyed it, silently.** Added the
guard plus a `--force` gate and verified both: importing is now inert, `main()` without `--force`
refuses, and the file's sha256 was unchanged across the test. Reusable helpers now live in
`scripts/ocrlib.py` (geometry preserved; `pymupdf`/`rapidocr` imports are function-local, so
importing it pulls in no ONNX). `assemble_v1()` is preserved verbatim so v1 stays reproducible.

`dedupe_pages()` was **not** run. `detect_duplicate_pages()` is asserted `== []` instead — scope is
the 3 front-matter pages, and the script says so; the full 27-page check belongs with D2's body OCR.

### Verification at session end

`audit_corpus` 9/9 + digest ok · `eval_heldout` · `eval_chat` · `ablate_phase08` all byte-identical ·
`eval_phase06` digest assert passes with its recorded FAILs (reverse_rel 0.630) **preserved untuned**
· `bench_phase01` PASS · phase03 16/16+7/7 · phase04 10/10 · phase05 137 · phase09_ops 51 ·
`import app` clean · both git guards empty.

### Session 2026-09-17 (later) — D2's body OCR + clause locator + cross-check

Zero Gemini quota. No new packages. Both git guards empty at session end; the v1 Act TXT still
hashes `940657A48C69B4E4…`.

**Body OCR — 27/27 pages**, dpi 200, 340 s, confidence 0.967–0.981, **zero low-confidence lines**.
Pages 2–4 were seeded from the front-matter checkpoint rather than re-OCRed, so the Arrangement
bytes in `data/processed/gazette_rapidocr.json` are the exact bytes the gate answered GO on.

**The deferred duplicate check is discharged at full scope.** `detect_duplicate_pages()` over all
27 pages finds **none** — top adjacent pair **0.219**, against v1's **0.978** outlier. Finding 1's
"the gazette has no duplicate page" now holds for the whole document, not 3 pages of it.
`dedupe_pages()` was not run and must not be.

**Two guards added to `ocr_gazette.py`, because the obvious next command was destructive.**
`--pages=1-27` would have parsed 27 body pages as Arrangement entries and written the result over
the verified 58-entry manifest. Now `--ocr-only` stops after the checkpoint, and the manifest write
**refuses to replace a clean manifest with a dirty parse** — the downgrade requires deleting the
file by hand. `rows()` moved to `ocrlib` for the second caller; the gate was re-run after the move
and still answers 58/58 with byte-identical manifest output.

#### Clause locator — **58/58, zero `TITLE_WEAK`, zero `NUMERAL_MISSING`**

Every clause anchored on **both** required anchors. Titles came from the Arrangement manifest;
**none was authored**. Clause text stops at the First Schedule — without that bound,
`58. Citation.`, a one-sentence clause, absorbed **5,480 characters** of Schedule text.

**Three geometry failures on the way, each of which produced a plausible wrong answer rather than
an error.** They are recorded because the wrong answers were the convincing kind:

| # | failure | cost |
|---|---|---|
| 1 | split columns on the widest horizontal **gap** | reintroduced the verso/recto asymmetry the design existed to avoid — recto gap ~418px fired, verso ~154px did not, so verso notes stayed in the body and `rows()` welded them onto the body row (`"Accessibility 5. Road side-walks…"`), which no numeral regex anchored at the start can match. **First run: 16/58.** |
| 2 | body extent as **min/max** over wide lines | broke on single outliers. p11: one OCR box merged a note into the body line and swallowed all 13 notes. p13: the margin clipped `"Functions of"` and `"Commission."` — **clause 38's own title** — into the body. |
| 3 | `FURNITURE_RE` under global `IGNORECASE` | `"Parti"` matches `PART` + `[IVX]`, so **`"Participation"` was deleted as a Part heading**. Clause 30 was left matching on `"in politics."` alone, scored 0.61, came out `TITLE_WEAK`. |

Marginal notes are matched by a **window over consecutive note lines**, not pre-grouped by a y-gap:
within a wrapped note the gap measures about **−2 px**, but two *different* notes on p13
(`Allowances of members.` / `Powers of the Council.`) sit **28 px** apart, so any threshold loose
enough to join a wrapped note also welds neighbouring clause titles together.

#### Cross-check vs v1 — **all three written-in-advance predictions hold**

| clause | predicted | got | coverage |
|---|---|---|---|
| 37 | LARGE | LARGE | 0.50 |
| 38 | LARGE | partial | 0.61 |
| 40 | agrees | agrees | 0.90 |

**52 of 58 clauses agree.** And the decisive probe: *"formulate and implement policies"* is
**absent from v1** (as Finding 1 measured by grep) and **present in v2's clause 38**.
**Clause 38's opening is recovered by the gazette.**

**The yardstick was wrong first, and was fixed before anything was read into it.** At k=40 only
**7 of 58** clauses could agree at all — both editions are OCR output with *independent* character
noise, so one bad character destroys every shingle spanning it, and the measure described OCR noise
rather than the corpus. k=10 was **calibrated against clauses whose answer Finding 1 had already
settled** (cl.40 known present, cl.37/38 known damaged) and separates them 0.90 vs 0.50/0.61, where
k≥18 does not (0.81 vs 0.32/0.51). A second, uncalibrated local-alignment measure was written and
**discarded**: it scored cl.40 at 0.18 against the calibrated 0.90 — it was simply broken, and
adjudicating a validated measure with an unvalidated one is how a wrong result gets confirmed.

**Four disagreements were not predicted.** Per this playbook they are parser bugs until shown
otherwise, so they are adjudicated in a dict kept **separate from the predictions** — a prediction
made in advance and an explanation reached afterwards are different kinds of evidence:

- **cl.53 — a NEW v1 defect, same class as cl.38.** *"awarded against the Commission"* is absent
  from v1 outright, and v1's own text at `53.` reads
  `53. | judgment debt. | shall bepaidfrom theFund of theCommission.` — the marginal note spliced
  in and the body truncated. v2 recovers the full sentence. Decided on **substring presence, not a
  ratio**. This was not previously known and belongs alongside Findings 1a–1c.
- **cl.20 / 27 / 44 — OCR divergence, not missing text.** Distinctive probes resolve in v1
  (`particularlychildren`, `ifaccommodationisbeing`, `gratuity`). Coverage is depressed by dense
  word-joining garbled independently in both scans. **Not claimed as a recovery.**

#### Verification

`audit_corpus` **byte-identical to baseline (0 diff lines)** · `eval_heldout` 0 · `eval_chat` 0 ·
`ablate_phase08` 0 · `eval_phase06` still hashes `ce716fb3…5f19` · `bench_phase01` PASS ·
phase03 16/16+7/7 · phase04 10/10 · phase05 137 · phase09_ops 51 · `import app` clean ·
`requirements.txt` diff **empty** · v1 Act TXT diff **empty**.

### Session 2026-09-18 — `_act_chunks_v2()`: **D2's Act exit criteria are MET**

Zero Gemini quota. No new packages. `requirements.txt` and the v1 Act TXT both still diff **empty**
against `main`.

**The Act half of corpus v2 exists and clears its gate.** `audit_corpus.py --corpus=v2`:

| doc | chunks | uncitable | packed | len min/med/max |
|---|---|---|---|---|
| **act2018 (v2)** | **65** | **0 (0.0%)** | **0** | 117 / 410 / **1100** (cap 1100, 0 over) |
| constitution1999 (still v1) | 2104 | 99 (4.7%) | 0 | 52/400/400 |
| factsheet2020 (still v1) | 48 | 9 (18.8%) | 19 | 64/500/500 |

**All three D2 Act criteria met: `general` 0.0% ≤ 1% · `packed` 0 · 58/58 citable.** The script
still exits 1, on the Constitution and Factsheet rows — those are **unchanged v1 numbers** and are
D3's and D4's to fix. Exiting 1 is correct at this step; nothing should shell out expecting 0 until
D4 lands.

**The uncitable-chunk class is closed on the Act.** v1 carried **25 of 62 uncitable** and 16 packed
refs; v2 carries **0 and 0**. That class was named three separate times before this phase (Act
cl.19, `CT7.t2`, the 25/62 measurement) and `ref = "cl. %d" % n` from the parser now makes packed
refs *structurally* impossible rather than merely absent.

**Implementation, as designed in D1/D2 — no deviation from the pinned decisions.**
`ACT_V2_SIZE = 1100` is a **new** constant (`ACT_SIZE` untouched at 800) and **was not tuned**;
`_act_chunks_v2()` reads **only** the manifest JSON via stdlib `json`, keeping the three-layer seam
that lets `requirements.txt` stay slim; every chunk carries `path == "manifest"`;
`CORPUS_VERSION` is still `"v1"` and `build_corpus("v2")` is reachable **only** via `--corpus=`,
never from `ask()`, `router._retriever` or `app.py`.

**Two deviations, both disclosed and both accepted:**

1. **The header is budgeted out of the cap** (`ACT_V2_SIZE - len(header) - 1`, floor 100) rather
   than added on top of it. Taken literally, "prefix the header to every sub-chunk of a 1100-char
   split" produces chunks **over** 1100 and an `OVER cap` count > 0. Budgeting mirrors
   `constitution_aware_split._emit()`'s handling of its own `§N` prefix (`src/chunk.py:125-132`).
   `ACT_V2_SIZE` itself is untouched. Verified by reconstruction: every sub-chunk join contains
   every 50-char window of the original clause body, **zero dropped text**; the surplus is exactly
   `recursive_split`'s overlap. The floor-100 branch is currently **unreachable** (longest header 84
   chars) — defensive, not dead-by-accident.
2. **`SIZE_CAP` (module constant) became `size_caps(version)`**, with `audit_doc()` /
   `length_histogram()` taking `caps` explicitly rather than reading a global that `main()` mutates.
   Swept independently: **no external importer** of `SIZE_CAP`, `audit_doc` or `length_histogram`.

**Only two clauses split at all:** cl.38 → 3 chunks, cl.57 (`Interpretation.`, 5,311 chars) → 6.
The other 56 are one chunk each. cl.57's length is the definitions section, not Schedule bleed —
the First Schedule bound holds, and cl.58 is a clean 103 chars.

#### The headline number that was talked *down*, not up

**`act_ref()` validator agreement: 65/65 = 100%** — and the review established it is **worth much
less than it looks**. See the boxed warning in **D6** above: the parser writes the header from the
same `n` it writes the ref from, so for single-clause chunks the check is close to a tautology.
The number is now printed **with that limit stated next to it**, and the script's own module
docstring — which had promised "two independent sources that must match, the same discipline as
`evalset.assert_frozen10_matches_notebook()`" — is **amended in place**, because that comparison
was simply wrong.

**A degradation-flag report was added** (`act_manifest_flags()`): `_act_chunks_v2()` does not
inspect `clause["flags"]`, so a manifest regenerated with `TITLE_WEAK` / `NUMERAL_MISSING`
acceptances would be promoted to fully-citable chunks with **no signal anywhere** — while D6 deletes
`ACT_KNOWN_ABSENT` on that manifest's word. Today it reads `located 58/58 · missing none ·
degradation flags none`.

#### Verification

v1 stdout compared against the **pristine stashed code**, not a saved baseline: `audit_corpus`
**0 diff lines**. `eval_heldout` · `eval_chat` · `ablate_phase08` all exit 0 and unchanged ·
`eval_phase06` still hashes **`ce716fb3…5f19`** · v1 `corpus_sha256` still `25650238…e89a` ·
9/9 v1 tripwire ok · `bench_phase01` PASS · phase03 16/16+7/7 · phase04 10/10 · phase05 **137** ·
phase09_ops **51** · `import app` clean (no server) · both git guards **empty**.

**Fresh-eyes review: verdict ship.** It independently reproduced every harness, rebuilt the v2
corpus and checked all 65 chunks against the manifest by hand, confirmed the insertion order in
both `build_corpus` branches, and confirmed v2 is unreachable from the user path. Its one
substantive finding — the validator circularity — was taken and is recorded above and in D6.

### Session 2026-09-18 (later) — `_fact_chunks_v2()`: **D3's Factsheet gate is MET, on a re-scoped metric**

Zero Gemini quota. No new packages. `requirements.txt`, the v1 Act TXT and the v1 factsheet TXT all
diff **empty** against `main`.

**The factsheet is now row-aligned.** `audit_corpus.py --corpus=v2`:

| doc | chunks | uncitable | packed | row-span | len min/med/max |
|---|---|---|---|---|---|
| act2018 (v2) | 65 | 0 (0.0%) | 0 | 0 | 117 / 410 / 1100 (cap 1100, 0 over) |
| constitution1999 (still v1) | 2104 | 99 (4.7%) | 0 | 0 | 52/400/400 |
| **factsheet2020 (v2)** | **32** | **0 (0.0%)** | 16 (declared non-defect) | **0** | 130 / 473 / **900** (cap 900, **0 over**) |

v1's factsheet was **48 chunks, 9 uncitable (18.8%), 19 packed, row-span 26 of 48**. The uncitable
class is closed on this document too, and the 9 `general` chunks split two ways — checked
individually, not assumed:

- **7 excluded by region**: the cover page (chunk 0), the intro prose (1), the *Arrangement of
  Sections* block (2, 3) and the PLAC address/About/Supported-by boilerplate (45, 46, 47). v2 drops
  these by **where they are**, not by classifying them after the fact.
- **2 absorbed and made citable**: chunk 28 is row 17's tail (*"…at least 5% of persons with
  disabilities in their employment- section"*, its number lost to the page cut) and chunk 36 is
  page furniture welded onto row 22's continuation. v2 puts both back inside their own row, under
  `Section 28` and `Section 38`.

**27 rows parse, S/N 1–27, contiguous, zero degradation flags.** Titles read correctly against the
source on all 27 (`Section 45 | Funds of the Commission`).

#### The metric was re-scoped, and the old one was left visible rather than tuned

The playbook's target was `packed 0`. **Measuring first showed `packed 0` and
`evalset.verify_expected()` cannot both hold** — see the boxed evidence under **D3** above and the
warning under **D6**. Eight sections (11, 13, 15, 23, 34, 35, 46, 53) are never row anchors, and
**frozen10/Q6 expects 11**, so the only ways to reach `packed 0` were editing frozen10 (forbidden)
or deleting held-out/test expectations (moving the yardstick).

So the ref carries the row's **anchor first, cross-references ascending**, and `packed` reads **16**
(11 of 27 rows carry a multi-number ref; 5 of those 11 exceed the cap and emit two chunks each).
`V2_MAX_PACKED` was **not** touched: the script still prints
`factsheet2020 packed refs 16 <= 0: FAIL`, with the reason printed directly underneath, so the
collision stays in stdout until D6 resolves it properly.

**The replacement metric is anti-tautological by construction.** `row_spanning` is measured by
re-scanning each **emitted chunk's text** for `FACT_ROW_RE`, never from "we emit one row per chunk,
therefore 0" — which would restate the code and gate nothing. **Its discriminating power is
demonstrated, not assumed: v1 scores 26 of 48, v2 scores 0 of 32.** Verified rather than assumed:
a v2 header line (`Section 45 Funds of the Commission`) carries no leading S/N numeral, so
`FACT_ROW_RE` cannot match it and the metric is not self-poisoning.

**Predicted 13, measured 16 — recorded, not reconciled by a code change.** The plan's estimate
counted rows under a slightly wider cross-reference regex. D3 reuses **exactly** the two regexes
v1's `fact_ref()` already uses (`SECTION_RANGE_RE`, `SECTION_ANY_RE`), so v2 changes which *text* a
number is attached to and never the vocabulary for spotting one. The cost is visible and accepted:
*"sections 4 and 5"* (row 3) and *"sections 26 and 27"* (row 16) are plural-with-`and` forms neither
regex matches, so 4/5/26/27 stay non-anchors — exactly as they were in v1, and no eval expects them.

#### Implementation — one production file, and deliberately no manifest

`src/rag.py` only. **No JSON manifest and no new script**, which is the one place D3 diverges from
D2's idiom on purpose: the Act needed a manifest because OCR (`pymupdf`/`rapidocr`) must stay out of
the slim Render runtime, so JSON is the wire format across that process boundary. The factsheet's
source is already a clean TXT in the repo that v1 parses at boot with stdlib. A manifest here would
be a second artifact to keep in sync for no benefit — **symmetry is not a reason.**

- `FACT_V2_SIZE = 900`, a **new** constant. `FACT_SIZE`/`FACT_OVERLAP` untouched (byte-identical v1
  path). Not tuned against the refusal floor — D5 owns that. Cap sweep recorded in the code
  comment: 700→39 chunks, 900→32, 1200→28, 1800→27, **0 over cap at every one**.
- `fact_v2_rows()` — region = `[first FACT_ROW_RE match, first FACT_TAIL_RE match)`, which excludes
  **1,880 chars** of cover/intro/*Arrangement of Sections* at the head and **894 chars** of PLAC
  address/About at the tail. `FACT_FURN_RE` drops page numbers, the repeated column header and the
  PLAC running footer **inside** rows as well as between them — rows 5, 15, 22 and 25 each span a
  page break. Per-row `flags` (`TITLE_EMPTY`, `TITLE_LONG`, `SN_OUT_OF_SEQUENCE`) follow the Act
  manifest's discipline; the audit prints them, so a degraded parse cannot be promoted silently.
- `_fact_chunks_v2()` — one row per chunk, sub-split only over the cap, **every** sub-chunk
  carrying the full row ref and the row header. Per-piece cross-references were considered and
  rejected: they make coverage depend on where `recursive_split` happens to cut, and a cut through
  the literal string `section 46` would silently drop a frozen expectation. Header budgeted out of
  the cap (`FACT_V2_SIZE - len(header) - 1`, floor 100), same idiom as `_act_chunks_v2()`.
  `path == "table"`.
- **`fact_ref()` is NOT promoted to a v2 validator**, and its docstring now says why: under the
  full-row-ref rule a sub-chunk legitimately names sections its own 900 chars do not mention, so
  disagreement is the designed behaviour and a "validator" would measure the split point. D2's
  lesson applied before the fact.

#### Verification

**v1 did not move.** v1 `corpus_sha256` still **`25650238…e89a`**, `eval_phase06` still hashes
**`ce716fb3…5f19`**, the 9/9 tripwire integers unchanged (48/9/19 on the factsheet row included).
`eval_heldout` · `eval_chat` · `ablate_phase08` · `bench_phase01` · `test_phase03` ·
`test_phase09_ops` stdout **0 diff lines** against the **pristine stashed code**; `test_phase04`
2 lines (wall-clock latency) and `test_phase05` 4 lines (timestamped Streamlit
`missing ScriptRunContext!`), both benign and both predicted. bench PASS · 03 16/16+7/7 ·
04 10/10 · 05 **137** · 09 **51** · `import app` clean · both git guards **empty**.

> **DISCLOSED: `audit_corpus.py`'s v1 stdout is NOT byte-identical — it is re-baselined, as at D1.**
> The pristine-vs-modified diff is **13 lines**, and every one is the new `row-span` column: the
> PER DOC header, its three data rows, and 5 legend lines. **Every pre-existing number is
> unchanged** (62/25/16, 2104/99/0, 48/9/19, all caps and lengths). This is unavoidable: the
> playbook requires `row_spanning` reported for **both** corpus versions precisely so v1's 26/48
> demonstrates the metric can fail, and a metric printed only on v2 would have no shown
> discriminating power. The D3 verification plan asked for 0 diff lines on this script; that and
> the anti-tautology requirement are mutually exclusive, and the metric won.

**The hard assert that drove the design passes in the real harness, not in simulation.**
`evalset.verify_expected()` runs clean against a **v2** `docs` dict for frozen10 (39 pairs),
heldout (48), test (34) and all-121. And the stronger check: the set of factsheet section numbers
reachable from some `ref` is **identical in v1 and v2** — the same 43 numbers,
`[1,2,3,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,28,30,31,32,34,35,37,38,39,40,45,46,47,48,49,50,51,52,53,54]`.
Nothing was lost by the rebuild and nothing was invented.

**Nothing dropped by the splitter.** Reconstruction check, the same one D2 ran: every 50-char
window of every row body survives the sub-chunk split (**0 rows with a gap**), and **0** in-region
source lines fail to appear in some row (i.e. the furniture filter deleted no provisions text).

**`audit_corpus.py --corpus=v2` still exits 1, on TWO rows now, not one.** The Constitution's 99
`general` (D4's) **and** the factsheet's `packed 16 <= 0` (re-scoped above, D6's to resolve). The
plan predicted the Constitution alone; the factsheet `packed` FAIL is the visible, deliberate
consequence of not tuning `V2_MAX_PACKED`. Nothing should expect exit 0 until D6.

### Session 2026-09-18 (later still) — `_const_chunks_v2()`: **D4's gate is MET, on a re-scoped metric**

Zero Gemini quota. No new packages. `requirements.txt` and all three v1 processed TXT files diff
**empty** against `main`. **All three docs are now v2.**

**The Constitution's Arrangement of Sections is gone from the retrievable corpus.**
`audit_corpus.py --corpus=v2`:

| doc | chunks | uncitable | packed | row-span | toc-gen (out/in Ch VIII) | len min/med/max |
|---|---|---|---|---|---|---|
| act2018 (v2) | 65 | 0 (0.0%) | 0 | 0 | 0/0 | 117 / 410 / 1100 (cap 1100, 0 over) |
| **constitution1999 (v2)** | **2037** | **34 (1.7%)** | 0 | 0 | **0/26** | 52 / 400 / **400** (cap 400, 0 over) |
| factsheet2020 (v2) | 32 | 0 (0.0%) | 16 (declared non-defect) | 0 | 0/0 | 130 / 473 / 900 (cap 900, 0 over) |

v1's Constitution was **2104 chunks, 99 uncitable (4.71%), `toc_general` 7 outside Chapter VIII**.

#### The target was wrong for the second phase running, and measurement said so first

Finding 2 promised `general` **→ ≈0**. Measured before a line was written: the floor for
Arrangement exclusion is **34 (1.67%)**, so `V2_MAX_GENERAL_PCT = 1.0` is **unreachable** on this
document — the boxed evidence under **D4** above and the warning under **D6**. The residual 34
decomposes, and **neither class is a defect**:

- **8 `general_unnumbered`** — the Preamble (2 chunks) and six chapter-divider headings
  (`Constitution, Chapter III - Citizenship: Citizenship`). They carry no section number at all;
  any `s. N` here would be invented.
- **26 `general_toc`** — **all 26 in Chapter VIII**: Second/Third/Seventh Schedule legislative-list
  items (`8. Census`, `63. Traffic`) and the Fundamental Rights (Enforcement Procedure) Rules
  (`ORDER 6`, `FORM NO. 4`, dotted-rule boilerplate). A Schedule **item** number is not a
  **section** number — item 8 "Census" is not s.8 — so labelling them `s. N` would deliberately
  re-create the Q10 misattribution class.

**`V2_MAX_GENERAL_PCT` was NOT touched.** `--corpus=v2` still prints
`constitution1999 uncitable 1.7% <= 1.0%: FAIL` with the reason printed directly underneath, and
the script **still exits 1** — now on the Constitution's 1.7% *and* the factsheet's `packed 16`.
D6 owns both. Exactly the discipline D3 used, for exactly the same reason: a threshold quietly
widened to fit a measurement reads, three commits later, like one that was always right.

#### The replacement metric, and its demonstrated discriminating power

`toc_general` is measured from each **emitted chunk's text** — does it carry a `§N` prefix inside
`const_ref()`'s own 160-char window that `_is_toc_fragment` then demoted? — split by whether the
chunk sits in Chapter VIII. Never from construction: *"we excluded the Arrangement, therefore 0"*
would restate `_const_chunks_v2()` and gate nothing.

**v1 scores 7 outside Chapter VIII; v2 scores 0.** Measured, not assumed. The 7 are Arrangement
tails, and **the 7th is the Q10 trap chunk itself**:

```
Constitution, Chapter IV - Fundamental Rights §39: "ion from
fundamental human rights. 46 Special jurisdiction of High Court and Legal aid."
```

**So D4 cures the Q10 class at source — that chunk ceases to exist.** `_is_toc_fragment` only ever
*mitigated* it by relabelling. The heuristic is **kept**, its docstring now records the inversion,
and it survives as the **instrument that proves the cure held**.

#### The cut point ate the Preamble in the obvious design, and only measurement caught it

The naive cut is the operative body's second `Chapter I` heading (char 18,535). The Preamble —
*"We the people of the Federal Republic of Nigeria … Do hereby make, enact and give to ourselves
the following Constitution:-"*, char **17,917**, 616 chars — sits **between** the two runs and
would have been silently deleted. Cut@Preamble: **2037 / 34**. Cut@2nd-Chapter-I: **2035 / 32** —
a *better-looking* `general` number bought by deleting the enacting words of the instrument.

**The cut is at the Preamble, located by `CONST_PREAMBLE_RE` and asserted, never by an offset.**
Two structural guards, the same flag discipline D2's manifest and D3's row parse use: the marker
must match **exactly once**, and the cut must separate the two chapter runs (last heading before
it `VIII`, first after it `I`). A silent fallback to chunking the whole document would produce a
v2 corpus identical to v1 and the gate would "pass" for the wrong reason — so it raises instead.

**An incidental fix worth recording:** in v1 the Preamble sat *inside* the Arrangement's Chapter
VIII block, so its three chunks were labelled
`Constitution, Chapter VIII - Federal Capital Territory, Abuja and General Supplementary
Provisions:`. In v2 it precedes the first chapter heading and `constitution_aware_split` labels it
`Constitution, Preamble:` — which is both correct and shorter, so the same 616 chars now fit in
**2** chunks instead of 3.

#### Implementation — one production file, and the narrowest possible change

`src/rag.py` only, plus reporting in `audit_corpus.py`.

- `_const_chunks_v2()` runs **v1's own text pipeline** — `clean_text(repair_joins(raw))` — and
  v1's own splitter at **`CONST_SIZE`**, unchanged. **There is no `CONST_V2_SIZE`**, deliberately:
  a new constant would imply the size moved, and it did not. D4 replaces the **region**, not the
  text and not the cut. Refs come from `const_ref()` exactly as v1 builds them; **no ref-shape
  change** (unlike D3).
- **`_const_chunks_v1()` and `const_ref()` are untouched.** `build_corpus()`'s v2 branch gains one
  line; **insertion order is unchanged** (`src/retrieve.py:331-338` breaks score ties by it).
- **How narrow, measured:** **2035 of v2's 2037 chunks are byte-identical in `(ref, text)` to v1's
  last 2035.** The only two that differ are the relabelled Preamble chunks above. The operative
  body is not re-chunked at all.

#### The excluded region contains no operative text, and that is measured rather than asserted

The cut discards `text[:17917]` — **3.44%** of the document, **690 non-empty lines**. Its character
is unambiguous: **zero** of those lines contain the word `shall`, the longest line carries **14**
words, and only **one** line exceeds 12. It is a title listing end to end
(`19. Foreign policy objectives. 20. Environmental objectives.`, `233 Appellate jurisdiction.`).
The last 300 chars excluded are the Arrangement's Seventh-Schedule oath *titles*; the first 300
kept are the Preamble's opening words.

#### Coverage — the D3 trap did not fire, checked first rather than after

`evalset.verify_expected()` is a **hard assert** and exclusion **removes** text, so this was
measured before writing code: **sections reachable from a Constitution ref are 318 before and 318
after — set difference empty in BOTH directions, 0 lost and 0 gained.** The 17 numbers the
evalsets expect (`6,16,17,18,34,35,36,40,42,45,46,65,66,77,85,117,251`) all remain reachable, and
`verify_expected()` passes against a **v2** `docs` dict in the real harness for frozen10 (39
pairs), heldout (48), test (34) and all-121.

#### Deferred to Phase E, by name

The **2104 → ~500 section-unit re-extract** (old M3, Finding 2) is **not needed for this gate and
is not attempted** — it is the riskiest change in the original plan and the dense arm is what
actually wants it. Giving Schedule/Rules chunks a citable `Sch. N item M` ref is the honest fix for
the 26, and it is a **fourth numbering scheme** through `cite_tag()`, the citation invariant and
the LLM prompt: Phase E, not here.

#### Verification

**v1 did not move.** v1 `corpus_sha256` still **`25650238…e89a`**, `eval_phase06` still hashes
**`ce716fb3…5f19`**, 9/9 tripwire ok. `eval_heldout` · `eval_chat` · `ablate_phase08` ·
`bench_phase01` · `test_phase03` · `test_phase09_ops` stdout **0 diff lines** against the
**pristine stashed code**; `test_phase04` **2** lines (wall-clock latency) and `test_phase05` **4**
lines (timestamped Streamlit `missing ScriptRunContext!`), both benign and both predicted.
bench PASS · 03 16/16+7/7 · 04 10/10 · 05 **137** · 09 **51** · `import app` clean (one expected
`missing ScriptRunContext!` warning, no server) · `requirements.txt` and all three v1 TXT files
**EMPTY** diff vs `main`.

> **DISCLOSED, exactly as at D3: `audit_corpus.py`'s v1 stdout is RE-BASELINED, not byte-identical.**
> The pristine-vs-modified diff is **37 entries — 33 `=>`, 4 `<=`**. The 4 removed and 4 of the
> added are the same lines: the PER DOC header and its three data rows, which gain the `toc-gen`
> column. The other 29 added are **8 legend lines** and the **21-line `CONSTITUTION general
> INVENTORY` section** (blank separator included). **Every pre-existing number is
> unchanged** (62/25/16, 2104/99/0, 48/9/19, row-span 0/0/26, all caps and length stats). Same
> trade-off D3 made and for the same reason: the metric must print on **both** versions or v1's 7
> is not available as proof that it can fail.

**The Constitution's v1 `general` inventory is published alongside v2's**, because 99 = 66
unnumbered + 33 TOC-demoted is what makes 34 = 8 + 26 legible. Note the v1 unnumbered class is
*not* only Preamble and dividers — it also holds unprefixed Arrangement chunks, which is why it
drops 66 → 8; the audit says so in place rather than overstating the symmetry.

**Addendum 2026-09-19 — the two guards are now EMPIRICALLY negative-tested, not just reasoned
about.** The paragraphs above describe designed behaviour; review then injected three degradation
modes against **mutated copies in a temp dir (the real TXT untouched)** and **all three raise**:
duplicated Preamble marker → `ValueError` "matched 2 times"; deleted marker → "matched 0 times";
marker relocated ahead of the first `Chapter` heading (clears guard 1, must fail guard 2) →
"cut … is not between the two chapter runs". **None silently falls back to a v1-shaped corpus.**
That was the one open risk D4 shipped with; it is closed. The same review re-derived the cut
offset (byte before the cut is `\n`, byte at the cut starts *"We the people"* — no off-by-one) and
independently reproduced the 2035/2035 byte-identical `(ref, text)` match against v1.

**Recorded, not fixed here: `--corpus=v2` on `eval_heldout` and `ablate_phase08` exits 1.**
frozen-10 recall reads **0.666** against the pinned v1 baseline of 0.925. **This pre-dates D4** —
verified by re-running both at HEAD (`6a5f5d9`, D3 state) with `--corpus=v2`: identical failure,
identical 0.666. It is the corpus change the whole phase is about, and **D5 (refusal floor) and D6
(re-baseline) own it**; `eval_heldout.py` fails on the *frozen* yardstick by design. The v2
direction of travel is not bad — held-out **0.420 → 0.473**, test **0.338 → 0.471**, and
`eval_chat --corpus=v2` answers **19/23** where D3's v2 answered 18/23, i.e. **one fewer refusal**.
Nothing here was tuned against those numbers.

### Session 2026-09-19 — **D6 EXECUTED. Corpus v2 is the default.**

Seven commits, `02f42f8` → `5838beb`, on `phase10/corpus-v2`. **Zero Gemini calls.** Branch
still unmerged — the deploy decision is the user's.

#### The order held, and it paid for itself immediately

The stamp fix landed **first**, while `CORPUS_VERSION` still read `"v1"`, exactly as the ⚠ ORDER
OF OPERATIONS box required. That made it a two-sided proof, and the second side is what mattered:

| run | result |
|---|---|
| `eval_heldout.py` | **byte-identical** to `D:\d5_baseline\heldout_v1.txt` |
| `eval_chat.py` | **byte-identical** to `chat_v1.txt` |
| `eval_chat.py --corpus=v2` | exactly **3 lines** differ (`:10`, `:110`, `:197`), all `corpus=v1` → `corpus=v2`, **no number moved** |
| `eval_heldout.py --corpus=v2` | 3 stamp lines flip — and then the frozen-10 guard **fires** |

**That fifth site was a guard that had been failing open.** `eval_heldout.py:438` asserts the run
is on v1 *because* `FROZEN10_RECALL_BASELINE_V1` is a v1 number and plain recall is not comparable
across corpus versions — but it read the constant, so under `--corpus=v2` it saw `"v1"` and let
the comparison through. So D5's published line

```
frozen-10 recall 0.666 vs recorded baseline 0.925 (corpus v1): FAIL
```

**is a v2 number compared against a v1 baseline, labelled v1, by the guard written to refuse
exactly that.** The legitimate comparison is the strict one D5 also published (0.701 → 0.633).
The plain-recall FAIL should never have printed. Every gate below was then given a **v2 arm on
the metric legitimate for it**, each printing the metric it does *not* gate:

| gate | v1 arm | v2 arm |
|---|---|---|
| `eval_heldout` frozen-10 | plain recall ≥ 0.925 | **strict ≥ 0.632738** |
| `ablate_phase08` | plain recall > 0.75 | **strict ≥ 0.632738** |
| `audit_corpus` constitution | `general_pct ≤ 1.0` | **`toc_general_out_ch8 == 0`** + pinned 8+26 |
| `audit_corpus` factsheet | `packed ≤ 0` | **`row_spanning == 0`** |

`0.632738`, **not** the `0.633` the table prints: the value is `0.63273809523809521` and 3dp
display rounds it **up**, so pinning the printed number would have failed the run it was derived
from. Any baseline pinned off a printed table has that bug.

#### Everything new was negative-tested, and one injection *passed*

| injection | result |
|---|---|
| frozen-10 v2 baseline 0.632738 → 0.700 | FAIL, rc=1 |
| frozen-10 v1 baseline 0.925 → 0.990 | FAIL, rc=1 |
| corpus stamp forced to `v3` | AssertionError |
| `toc_general_out_ch8` cap → −1 · `row_spanning` cap → −1 | FAIL, rc=1 |
| inventory pins 8→7 · 26→25 | DRIFT, rc=1 |
| `V2_CORPUS_SHA256` one nibble flipped | DRIFT, rc=1 |
| `V2_RESULTS_SHA256` flipped · pin removed | SystemExit, both |
| ablate v2 floor 0.632738 → 0.800 | FAIL, rc=1 |
| retirement: reason removed · blank · bogus status | AssertionError, all three |
| **`act_ref` contradiction injected** | **PASSED — and that was a defect in the gate** |

The `act_ref` injection not firing was **my bug, not the test's**: I had added a second
`act_ref_validator()` call in the gate while the report already made one, so the validator ran
twice over 65 chunks and the first pass absorbed the injected contradiction. Deduplicated — 65
calls, not 130 — and it then fails the run. **An injection that passes is a result to
investigate, not a box to tick.** Threshold injections only test the comparison, so both new
metrics were also run against real defective data: `toc_general_out_ch8` **v1 7 / v2 0**,
`row_spanning` **v1 26/48 / v2 0/32**.

#### The chat-set triage inverted its own premise

The premise handed to D6 was that `chat_test`'s ellipsis gain class collapsed **+0.400 → 0.000**
and a green harness was hiding it. Three turns carried that entire gain. **All three of v1's hits
are artifacts**, established by reading the corpus rather than reasoning about it:

- **`CT2.t2` / `CT2.t3` — ground truth FALSIFIED. Retired.** Both expect `act2018:[8]`, authored
  from v1's `[Act cl. 8]` chunk, which **carried clause SEVEN's subsection (3)** — *"An officer
  who approves or directs the approval of a building plan … is liable on conviction"*. v2 puts
  that text under `[Act cl. 7]`; v2's cl.8 is *Complaint of inaccessibility*, whose liability
  falls on *"a relevant authority in charge"*, not an approving officer. **This is the same defect
  class as cl.38's tail served under `[Act cl. 39]` — the one this whole phase exists to fix —
  found inside the eval set, where it had been scoring turns correct against mis-attributed law
  since 2026-09-15.**
- **`CT4.t3` — ground truth CORRECT, v1's hit was a packed-chunk artifact. Kept.** v1 scored 1.000
  because cl.25 sat in an 800-char `cl. 25,26,27` chunk containing *"queue"* and *"accommodation"*,
  carried in by contextualisation from turns 1–2. **The chunk was retrieved for its neighbours'
  words and credited to clause 25.** v2's 305-char cl.25 chunk contains neither. Naive rank **40
  (v1) vs 41 (v2)** — the rebuild did not hurt; contextualised rank **5 vs 104**.

> **⚠ STRICT RECALL DOES NOT NEUTRALISE THE PACKED SUBSIDY IN THE `ctx` ARM.** D5 read
> `strict == plain` on every `chat_test` class row as ruling the packed-ref subsidy out. That holds
> for **scoring** — `strict_covered` stops one chunk satisfying two expected refs — but **not for
> retrieval**: it cannot see that a chunk was *retrieved* because of text belonging to a different
> clause. The subsidy was in the `ctx` arm, invisible to the metric built to catch it.

So the blind set's gain class **did not degrade; v1's was never earned.** On the same 3 surviving
turns: v1 `0.000 → 0.333` (that 0.333 *is* `CT4.t3`, the artifact), v2 `0.000 → 0.000`. Once both
artifacts are accounted for, chat_test ellipsis gain is **zero on both corpora**.

**0 turns were retired for getting harder.** `CT7.t2`'s prediction held exactly — unscoreable on
v1, now `0.000 → 1.000` with the correct chunk at pool rank **2** where v1 had it at 9.

#### The v2 baseline

`scripts/baseline_v2_2026-09-19.txt`, all five harnesses, **all green**:

```
audit_corpus  PASS     eval_heldout  PASS     eval_chat  PASS     ablate  PASS
eval_phase06  sha256 10751076…ed97e057 (v2)   ·  ce716fb3…edf5f19 still holds on --corpus=v1
heldout   frozen-10 0.666 / strict 0.633   dev 0.473   test 0.471
chat_test 0.524 -> 0.571 (+0.048, n=21)    chat_dev 0.500 -> 0.607 (+0.107, n=28)
test_phase05 137/137 · test_phase09_ops ALL PASS · import app clean   (all UNCHANGED under v2)
```

#### Exit criteria, checked

1. ✅ Every gate green on its re-scoped metric, **old metric still printed** beside it.
2. ⚠️ **Partially — deliberately, and enumerated.** `eval_heldout --corpus=v1` and
   `eval_phase06 --corpus=v1` are byte-identical / hash-identical. **Three files diverge on
   purpose**: `audit_corpus` v1 (2 hunks — cl.40 moves to *"NOT citable, parseable"* where it
   belongs and cl.38 stops claiming *"the pixels do not exist"*, which was false);
   `ablate_phase08` v1 (+2 lines — it had **no corpus stamp at all**, a sixth site of the stamp
   class and worse than a wrong one, plus the ungated strict column); `eval_chat` v1 (the two
   retired turns). **No number moved in the first two and no exit code changed.** The third is a
   real number change and it is the honest one — the retired turns' expected refs name the wrong
   clause **of the Act**, not merely of v2, so the retirement is global by construction.
3. ✅ Every new guard negative-tested by injection — see the table, including the one that failed
   to fire.
4. ✅ `MIN_SCORE` still `0.10`, untouched. `SYN:car` not re-opened.
5. ✅ Every moved turn dispositioned in writing: 2 retired, 2 handed to E, 1 prediction confirmed.
6. ✅ `scripts/baseline_v2_2026-09-19.txt` archived.

#### Handed to Phase E, by name

- **`CT4.t3`** — cl.25 is **outside the 60-candidate pool entirely** (rank 104 at k=200).
  **E1's `k=20/doc` widening does not reach it**, which is worth knowing *before* E1 is judged.
  The mechanism is length: v2's clause-aligned chunks are short (305 chars here), and TF-IDF's
  length handling now works against specific short clauses — which is precisely **E2's (BM25)
  rationale, now with direct evidence behind it.**
- **`CT1.t1`** — false-refusal marker gone under v2, recall still `0.000`, naive rank 20 → 22.
  A fixed refusal and an unfixed ranking; both get reported.
- **`chat_test`'s ellipsis class is now THIN at 3 scoreable turns.** A real limit on what it can
  support, recorded rather than smoothed over.
- **The Phase B gates are still computed on `chat_dev`**, so `eval_chat` exits PASS while
  `chat_test`'s marker reads `GAIN CLASS DID NOT IMPROVE`. **That critique stands** — it is a
  harness-design question, not a D6 edit, and D6 deliberately did not touch it.

### Superseded — D5's "next session starts here"

**D5 — the refusal floor. Mandatory, not conditional.** All three docs are v2 now, so the cosine
space has moved for real: the Act's chunks run to 1,100 chars, the factsheet's to 900, and the
Constitution lost 67 chunks and 17,917 characters of high-frequency listing vocabulary from its
IDF space. In order: (1) re-derive the calibration table at `src/retrieve.py:26-44` **against v2**
and write the new numbers in; (2) **`MIN_SCORE` may move down, never up**; (3) gate on
`false_refusal_v2 ≤ false_refusal_v1` (currently 0/10 frozen, 0/25 dev, 0/17 test); (4) the small
frozen-v1-index escape hatch is the hatch, **not** the default. Then **D6** (re-baseline, flip
`CORPUS_VERSION`, re-scope all three gates, re-verify `conversations.json`'s 51 refs).

Reminders that still bind: `CORPUS_VERSION` stays `"v1"` until D6 · `ACT_KNOWN_ABSENT = {38, 40}`
stays until D6 **deletes** it · `MIN_SCORE` may move **down** in D5, never up · do not re-derive any
manifest in `data/processed/` and do not re-run the OCR · `ACT_V2_SIZE` and `FACT_V2_SIZE` are
**not** re-tuned before D5 · `CONST_SIZE` does **not** move and there is no `CONST_V2_SIZE` ·
`audit_corpus.py --corpus=v2` exits **1** until D6 re-scopes the Constitution's `general` gate
**and** the factsheet's `packed` gate, by design.

> **✅ ALL OF THE ABOVE IS DISCHARGED — D5 and D6 are both DONE (2026-09-19).** `CORPUS_VERSION`
> is `"v2"`, `ACT_KNOWN_ABSENT` is deleted, `MIN_SCORE` held at `0.10`, both gates are re-scoped
> and `audit_corpus.py --corpus=v2` exits **0**. Kept unedited because the constraints explain the
> sequencing the phase actually followed. **Phase D is complete. Next: Phase E —
> `docs/phases/13_retrieval_quality.md`.**
