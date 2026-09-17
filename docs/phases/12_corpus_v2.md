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

- `ACT_KNOWN_ABSENT = {38, 40}` at **`scripts/audit_corpus.py:80`** — a false constant currently
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

### Next session starts here

D2's clause locator and the 27-page body OCR, then `_act_chunks_v2()` / `ACT_V2_SIZE`. The
Arrangement manifest is already on disk at `data/processed/gazette_arrangement.json` — 58 entries,
`"title_source": "arrangement"`. Do not re-derive it.
