"""Retrieval: TF-IDF baseline (offline, sklearn) + optional Gemini hook.

Foundation runs fully offline on TF-IDF. Gemini embeddings / generation are
opt-in: they need GOOGLE_API_KEY and an explicit call. No key = no network.

Numbering is never conflated: every chunk carries (doc_id, ref) metadata with
doc_id in {'act2018', 'constitution1999', 'factsheet2020'}:
  - Act clause N vs Constitution section N vs Factsheet Section N are
    different things; the doc_id on every hit keeps them apart.

Retrieval strategy (Phase 02, option b -- per-doc retrievers):
  The joint index is ~95% Constitution chunks (S36 alone splits into 21),
  so Act-specific queries top-1 to Constitution in a joint retriever
  (Phase 01 bench: Q1/Q5/Q6/Q8/Q10 all top-1 constitution1999 after the
  pipeline upgrade, with HIGHER absolute scores than before). Per-doc
  retrievers fix the flooding structurally: each doc contributes its own
  top-k, so the Act is always represented however large the Constitution
  index grows. Cross-doc score ordering is best-effort (separate TF-IDF
  spaces have different IDFs, so raw cosines are not strictly comparable),
  but the MIN_SCORE refusal gate is applied per-hit identically.
"""
from collections import namedtuple

import numpy as np
from sklearn.feature_extraction.text import (
    ENGLISH_STOP_WORDS,
    CountVectorizer,
    TfidfVectorizer,
)
from sklearn.metrics.pairwise import cosine_similarity

# ---------------------------------------------------------------------------
# Refusal threshold.
#
# RE-DERIVED AGAINST CORPUS v2 ON 2026-09-19 (Phase 10 D5). D2/D3/D4 replaced
# all three documents, so every cosine in the system moved and this table could
# not simply be inherited -- longer v2 chunks lower every score, and a lower
# score can manufacture a FALSE REFUSAL. The re-derivation is a committed,
# re-runnable script:
#
#     C:\conda-envs\drlca-rag\python.exe scripts\calibrate_refusal.py
#
# 106 probes (60 eval rows + 12 off-corpus + 34 bare synonym keys) x both
# corpus versions, built in ONE process on the shipping arm (k=3/doc,
# select_top(top_n=6, min_per_doc=1)). Every number below is its output; rerun
# it rather than trusting this comment.
#
# THE SHIPPING ARM MOVED TO k=4/doc, select_top(top_n=12, min_per_doc=1) IN
# PHASE E1b, 2026-09-20. The table above was measured at 3/6 and is NOT
# re-measured here, because it does not need to be: the refusal decision is
# invariant to k and top_n. select_top always keeps the global best candidate,
# so the top score of every query -- the only input to the MIN_SCORE decision --
# is byte-identical from k=3 through k=20 (measured over all 60 eval rows, E1a).
# D5's conclusions therefore carry unchanged, and calibrate_refusal.py re-derives
# the whole table at the CURRENT arm on every run because it IMPORTS
# eval_heldout's constants rather than copying them. The in-corpus minima and
# off-corpus maxima printed by a fresh run are the authority; this block is the
# 3/6-era record of them.
#
# CALIBRATION, v1-era (historical) and v2 (current):
#   in-corpus minima, lowest top score over expect_gate=answer rows
#                        v1                      v2
#     frozen10      0.1696 (Q6)             0.2287 (Q10)
#     dev           0.1359 (H11)            0.1369 (H11)
#     test          0.1285 (T1)             0.1209 (T9)
#   off-corpus maxima -- these are FALSE ANSWERS clearing the floor
#     12 probes     0.3180 (maritime)       0.3180 (maritime)   9/12 clear both
#     8 refuse rows 0.4193 (H23)            0.4195 (H23)        8/8 -> 7/8
#
# THE BAND IS STILL INVERTED, and that conclusion is re-measured, not
# inherited: weakest in-corpus 0.1285 vs strongest off-corpus 0.4193 on v1,
# 0.1209 vs 0.4195 on v2. No single cosine value separates "shares legal words"
# from "on-topic" on EITHER corpus. (TF-IDF scores word overlap, not meaning;
# "law"/"Act" carry junk high.)
#
# A NOTE ON THE FIGURES THIS BLOCK USED TO CARRY (measured 2026-09-08, per-doc
# merged top-1, k=2/doc): in-corpus 10Q minima Q8 0.1690 / Q2 0.1744 /
# Q6 0.1751; joint-corpus Phase 01 minima Q5 0.141 / Q9 0.167; off-corpus
# maxima sourdough 0.124, quantum 0.150, visa 0.161, maritime 0.249-0.306.
# They are kept as v1-era history, but they were measured on a DIFFERENT arm
# (k=2/doc, no select_top) and one of them is unreproducible: no `visa` probe
# exists anywhere in this repo -- the only "visa" in the tree is Constitution
# item 42 ("Passports and visas"), i.e. corpus text, not a query. That is why
# D5 replaced the anecdote with an imported, committed probe list.
#
# So MIN_SCORE = 0.10 is a weak-overlap FLOOR, not a semantic filter: it sits
# below every in-corpus minimum on both corpora while still refusing
# zero-overlap queries. Semantic refusal is the strict LLM layer (exact
# no-answer sentence -> REFUSAL_MESSAGE in src/rag.py).
#
# D5's verdict: the floor HELD. False refusals stayed at 0/10, 0/25 and 0/17 on
# frozen10/dev/test across BOTH corpora, so v2 is owed no change here and none
# was made. THE NUMBER MAY MOVE DOWN ON EVIDENCE AND MAY NEVER MOVE UP --
# calibrate_refusal.py gate 3 enforces exactly that. False refusals deny help
# to PWDs, so the gate errs low by design; failures are logged, not hidden.
# Revisit only with a discriminative signal (e.g. query-term coverage), never
# by nudging this number into the inverted band -- the table above shows there
# is no value up there that would work.
# ---------------------------------------------------------------------------
MIN_SCORE = 0.10

DOC_IDS = ("act2018", "constitution1999", "factsheet2020")

# A chunk of citable text. ref examples: Act "cl. 31", Constitution "s. 17",
# Factsheet "Section 19" (or "general" when no section marker was found).
#
# `path` (Phase 10 D1) records HOW the ref was obtained -- "" for v1, where refs
# are INFERRED from heading shape, and a provenance label under v2's
# manifest-anchored parse (e.g. "manifest", "marginal_note"). It is defaulted so
# every existing 3-arg construction site keeps working untouched; what it does
# change is arity, so `len(chunk)` is 4 and `a, b, c = chunk` now raises. Both
# were swept for at D1 and neither pattern occurs on a Chunk (the near-miss,
# scripts/bench_phase01.py:244-250, unpacks chunk_stats()'s (n, avg, max)
# numbers from a list[str] -- not a Chunk).
Chunk = namedtuple("Chunk", ["doc_id", "ref", "text", "path"], defaults=("",))

# A retrieved hit: (doc_id, ref, text, score). Score is cosine similarity
# in [0, 1] within that doc's TF-IDF space.
Hit = namedtuple("Hit", ["doc_id", "ref", "text", "score"])


def _stem_once(word: str) -> str:
    """One pass of suffix stripping. Rules are ordered longest-first so a
    single pass usually suffices; stem() loops to a fixpoint for stacked
    suffixes ('violations' -> 'violation' -> 'violat')."""
    if len(word) <= 3:
        return word
    if word.endswith("ies") and len(word) > 5:  # penalties -> penalty
        return word[:-3] + "y"
    # NOTE: strip "ion", not "ation": "violation" -> "violat" converges
    # with "violating" -> "violat", and "discrimination" -> "discriminat"
    # converges with "discriminating" -> "discriminat". Stripping "ation"
    # instead ("discrimin") would break that convergence (2026-09-08).
    if word.endswith("ion") and len(word) > 6:  # violation -> violat
        return word[:-3]
    if word.endswith("ing") and len(word) > 6:  # violating -> violat
        return word[:-3]
    if word.endswith("ed") and len(word) > 5:
        return word[:-2]
    if word.endswith("es") and len(word) > 5:  # charges -> charg
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 4:
        return word[:-1]
    return word


def stem(word: str) -> str:
    """Tiny rule-based stemmer for retrieval ONLY (never shown to users).

    Why: TfidfVectorizer has no stemming, so Q5 "penalties" matched
    nothing ("penalty" in corpus) and the query reduced to "Act" ->
    preamble won. Rules align common inflections on BOTH sides
    (query and chunks go through the same preprocessor, so over-stemming
    only merges consistently). Guards: words <=3 chars untouched.
    """
    for _ in range(3):  # fixpoint for stacked suffixes
        nxt = _stem_once(word)
        if nxt == word:
            return word
        word = nxt
    return word


def stem_preprocess(text: str) -> str:
    """Lowercase + alpha-only + stem each token. Used as the
    TfidfVectorizer preprocessor so fit() and transform() match."""
    import re as _re
    toks = _re.findall(r"[a-zA-Z]+", text.lower())
    return " ".join(stem(t) for t in toks)


# ---------------------------------------------------------------------------
# Query-side legal synonym expansion (Phase 08 step 1, added 2026-09-11).
#
# The problem it solves is vocabulary mismatch, not ranking. Phase 06 Q5
# ("What are the penalties for violating the Act?") scored recall 0.000: the
# Act never uses the word "penalty" for its penalty clauses. It says "a fine
# of N100,000 or six months imprisonment" (cl.2), "N5,000 damages payable
# ... each day of default" (cl.9,10), "liable to N50,000 damages" (cl.29,30).
# TF-IDF scores word overlap, so a query built from the wrong register scores
# zero against the right clauses and the generic preamble wins instead.
#
# WHERE THIS RUNS MATTERS. Expansion is applied ONCE PER QUERY in
# PerDocRetriever.query(), NOT in stem_preprocess(). stem_preprocess is the
# TfidfVectorizer preprocessor, so it runs over INDEXED CHUNKS too: expanding
# there would inject synonyms into the corpus side, inflate document frequency
# for every expansion term, and silently invalidate the MIN_SCORE calibration
# recorded at the top of this file. Query-side only keeps the index -- and
# therefore that calibration -- byte-identical.
#
# CURATION RULE: every expansion term below was verified to occur in the
# stemmed corpus before being added (probe 2026-09-11). Terms that sound right
# but are absent were REJECTED, not kept as dead weight: "terminate",
# "reserve", "unfair", "entitlement", "healthcare", "moratorium", "sight",
# "curriculum". This is legal vocabulary the documents actually use, not a
# thesaurus and not a score hack. MIN_SCORE (0.10) is untouched: expansion
# raises coverage, it does not move the refusal floor's meaning.
#
# Keys are matched after stemming, so "penalty"/"penalties" both fire from the
# single key "penalty". Multi-word keys are matched as raw substrings.
# ---------------------------------------------------------------------------
SYNONYMS: dict[str, tuple[str, ...]] = {
    # -- penalties: the Q5 blind spot. The Act's register is offence/fine/
    #    imprisonment/damages, never "penalty". "prison" is Constitution-only
    #    vocabulary but genuine, so it rides along harmlessly for Act queries
    #    (an out-of-vocabulary term is simply dropped by transform()).
    #    MEASURED 2026-09-11: adding "liable"/"damages"/"payable" on top of
    #    these five made Q5 WORSE, not better -- they are the register of the
    #    employment clause cl.28 ("liable on conviction") and of cl.29,30
    #    ("damages payable"), so the Act index reordered to cl.28 + general and
    #    pushed cl.1/cl.2 (the actual N100,000 fine / six months imprisonment
    #    clauses) down. Five terms: act top-3 = cl.2, cl.1, cl.16,17. Eight
    #    terms: act top-3 = cl.28, general, cl.13. Wider is not better; the
    #    expansion must stay on the penalty register, not all of legal English.
    "penalty": ("offence", "fine", "imprisonment", "prison", "conviction"),
    "punishment": ("offence", "fine", "imprisonment", "conviction"),
    "sanction": ("offence", "fine", "penalty", "prosecution"),
    "fine": ("damages", "payable", "liable", "offence"),
    "fined": ("fine", "damages", "payable", "liable"),
    "jail": ("imprisonment", "prison", "conviction"),
    # -- employment. "sacked" is NOT a separate key: it stems to "sack" and
    #    would silently shadow it in _SYN_WORD (the collision assert below
    #    catches exactly this). _surface_forms() already routes "sacked" here.
    "sack": ("dismiss", "employment", "employ", "labour"),
    "fired": ("dismiss", "employment", "employ"),
    "job": ("employment", "employ", "work", "labour"),
    "quota": ("employment", "employ", "percent", "labour"),
    # -- premises and physical access
    "house": ("building", "premises", "structure"),
    "toilet": ("facility", "accessibility", "premises"),
    "lift": ("elevator", "accessibility", "building"),
    "ramp": ("accessibility", "access", "building", "facility"),
    "wheelchair": ("mobility", "physical", "access", "ramp"),
    "accessible": ("accessibility", "access", "facility", "premises"),
    # -- transport
    "bus": ("vehicle", "transport", "road"),
    "car": ("vehicle", "transport", "parking", "road"),
    "transport": ("vehicle", "transportation", "road"),
    # -- education. ONE DIRECTION ONLY: the user says "school", the Act says
    #    "education". The reverse key ("education" -> school, student,
    #    learning) was written, measured, and DELETED: Q7 already retrieved
    #    perfectly on its own words, and expanding it cost recall 1.000 ->
    #    0.500 by promoting cl.18 ("free education to secondary SCHOOL") over
    #    the expected cl.16,17 and cl.20. There was no vocabulary mismatch to
    #    fix, so the entry was pure dilution -- a thesaurus entry, which the
    #    curation rule above forbids. Expand toward the corpus, never away.
    "school": ("education", "institution"),
    # -- impairments (the words a user brings vs the words the Act uses)
    "blind": ("visual", "impairment", "braille"),
    "deaf": ("hearing", "speech", "impairment", "interpreter"),
    "sign language": ("deaf", "hearing", "interpreter", "speech"),
    # -- health
    "hospital": ("health", "medical", "treatment"),
    "doctor": ("health", "medical", "treatment"),
    # -- money and remedy
    "money": ("fine", "damages", "payable", "naira", "compensation"),
    "compensation": ("damages", "payable", "liable"),
    "lawyer": ("counsel", "representation", "court", "aid"),
    "court": ("tribunal", "judicial", "justice", "proceedings"),
    # -- dignity: Q9 expects Constitution s.34, whose body text is
    #    "torture ... inhuman or degrading treatment", not the word "dignity".
    "dignity": ("degrading", "inhuman", "torture", "respect"),
    "abuse": ("degrading", "inhuman", "torture"),
    "begging": ("alms", "destitute"),
    # -- transition period: Q8 expects Act cl.6,7. The Act and factsheet say
    #    "transitory"; only the Constitution says "transitional".
    "transitional": ("transitory", "period", "years", "comply"),
    "compliance": ("comply", "conform", "transitory"),
}

# Single-word keys are matched against a normalised token set (see
# _surface_forms); phrase keys keep their raw form and match as substrings.
_SYN_WORD = {k: v for k, v in SYNONYMS.items() if " " not in k}
_SYN_PHRASE = {k: v for k, v in SYNONYMS.items() if " " in k}

# stem() is shared with the INDEX, so it must not be retuned to make keys fire
# -- changing it would rebuild every TF-IDF vocabulary and invalidate the
# MIN_SCORE calibration. Instead the collision check below keeps the map
# honest: two keys that reduce to the same stem would silently shadow each
# other in a dict comprehension, and a future edit giving them different
# synonym lists would lose one with no warning.
_stems: dict[str, str] = {}
for _k in _SYN_WORD:
    _s = stem(_k)
    assert _s not in _stems, (
        "synonym keys %r and %r collide on stem %r -- one would shadow the "
        "other; merge them" % (_stems[_s], _k, _s))
    _stems[_s] = _k
del _stems, _k, _s


def _surface_forms(q: str) -> set[str]:
    """Every form of a query token a SYNONYMS key could legitimately match.

    stem() is a deliberately tiny rule set with length guards (len > 4 / > 5),
    which means short nouns do NOT reduce to their singular: "jobs" stems to
    "jobs", "cars" to "cars", "buses" to "buse", "houses" to "hous". Matching
    keys on stems alone therefore left several curated entries DEAD against the
    plural a user would actually type ("Are there job quotas?" fires, "What
    about accessible buses?" does not). Found in review 2026-09-11.

    The fix is on the key-matching side only -- naive singularisation here is
    safe because a false match costs at most a few extra query terms, whereas
    the same rule inside stem() would rewrite the corpus index.
    """
    import re as _re
    raw = set(_re.findall(r"[a-z]+", q.lower()))
    forms = set(raw) | set(stem_preprocess(q).split())
    for w in raw:
        forms.add(stem(w))
        # "-es" is only a plural marker after a sibilant (bus->buses,
        # box->boxes, church->churches). Without that guard the rule is a
        # false-positive generator: it stripped "cares" -> "car" and injected
        # vehicle/transport/parking/road into "nobody cares what happens
        # next" (found in review 2026-09-11).
        if w.endswith("es") and len(w) > 3 and w[:-2].endswith(
                ("s", "x", "z", "ch", "sh")):
            forms.add(w[:-2])                 # buses -> bus
        if w.endswith("s") and len(w) > 2:    # jobs -> job, houses -> house
            forms.add(w[:-1])
    return forms


def expand_query(q: str) -> str:
    """Append curated legal synonyms for terms the query actually contains.

    Returns the ORIGINAL query plus appended terms, never a replacement: the
    user's own wording keeps its weight and expansion only adds mass on the
    corpus's register. Order is deterministic (dict insertion order) and
    duplicates are dropped, so the same question always expands identically --
    the ablation stays reproducible.

    NOTE: PerDocRetriever.query() applies this to whatever it is given, and the
    Phase 06 eval's reverse-retrieval step passes a whole generated ANSWER, not
    a short question. Long inputs can fire many keys at once. Measured
    2026-09-11: reverse_rel is bit-identical per question before and after, so
    the map as it stands is stable there -- but it is tuned against short
    questions only, so re-check the reverse_rel column when adding entries.
    """
    import re as _re
    forms = _surface_forms(q)
    low = " ".join(_re.findall(r"[a-z]+", q.lower()))
    extra: list[str] = []
    for key, syns in _SYN_PHRASE.items():
        if key in low:
            extra.extend(syns)
    for key, syns in _SYN_WORD.items():
        if key in forms or stem(key) in forms:
            extra.extend(syns)
    if not extra:
        return q
    return q + " " + " ".join(dict.fromkeys(extra))


# ---------------------------------------------------------------------------
# BM25 -- a SELECTION signal, never a score (Phase E2a, added 2026-09-20).
#
# TEXTBOOK DEFAULTS. These are Robertson's original values and they are NOT to
# be tuned against the eval sets. The hand-written SYNONYMS map above is what
# happens when a knob is fitted to frozen-10: it reads +0.061 on the ten
# questions it was fitted to and is carried by two of them (playbook
# docs/phases/13_retrieval_quality.md). A b chosen because it moved `test` would
# be the same mistake with a nicer name. scripts/ablate_rerank.py DOES sweep b,
# and reports it as a sensitivity check only -- if an arm's result depends on b,
# that is evidence against shipping the arm, not a knob to turn.
BM25_K1 = 1.5
BM25_B = 0.75

# Reciprocal-rank fusion constant (Cormack et al. 2009's 60). RRF fuses two
# RANKINGS, so it sidesteps the scale incomparability that forbids mixing a
# cosine with a BM25 score directly -- there is no weight to fit.
RRF_K = 60


class TfidfRetriever:
    """Single-corpus TF-IDF retriever. Kept backward compatible:
    chunks are bare strings, query() returns [(idx, score, text)].

    `bm25=True` additionally builds an Okapi BM25 index over the SAME term
    space and exposes bm25_scores(). It changes nothing about query(): cosine
    is still the only thing this class scores or orders by. The flag DEFAULTS
    TO FALSE so that every existing construction site -- scripts/bench_phase01.py
    builds `TfidfRetriever(chunks)` directly and asserts on raw cosines -- is
    byte-identical with the flag present.
    """

    def __init__(self, chunks: list[str], bm25: bool = False):
        self.chunks = chunks
        self.vec = TfidfVectorizer(
            preprocessor=stem_preprocess,
            # Stopwords must be stemmed too (preprocessor runs first, so
            # raw "having" would otherwise evade removal as "hav").
            stop_words=[stem(w) for w in ENGLISH_STOP_WORDS],
            ngram_range=(1, 2),
        )
        self.mat = self.vec.fit_transform(chunks)
        self.cnt = self.bm25_idf = self.bm25_dl = None
        self.bm25_avgdl = 0.0
        if bm25:
            self._build_bm25()

    def _build_bm25(self) -> None:
        """Raw term counts + BM25 idf over the TF-IDF vocabulary.

        The vocabulary is REUSED rather than re-fitted (`vocabulary=` below),
        so the BM25 term space is identical to the cosine one BY CONSTRUCTION
        instead of by coincidence -- same preprocessor, same stemmed stopword
        list, same (1,2) n-grams, same columns in the same order. A separately
        fitted CountVectorizer would agree today and could silently diverge on
        the next `min_df`-shaped edit.
        """
        cv = CountVectorizer(
            preprocessor=stem_preprocess,
            stop_words=[stem(w) for w in ENGLISH_STOP_WORDS],
            ngram_range=(1, 2),
            vocabulary=self.vec.vocabulary_,
        )
        self.cnt = cv.fit_transform(self.chunks).tocsr().astype(np.float64)
        n_docs = self.cnt.shape[0]
        df = np.asarray((self.cnt > 0).sum(axis=0)).ravel()
        # Robertson/Sparck Jones idf in its non-negative ("plus-one") form:
        # ln(1 + (N - df + 0.5) / (df + 0.5)). The bare form goes negative for
        # terms in more than half the corpus, which would let a common term
        # PENALISE a chunk that contains it.
        self.bm25_idf = np.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
        # Document length counts every term occurrence in the vocabulary,
        # bigrams included. Bigram counts inflate |d| by roughly a constant
        # factor across chunks, so b's length normalisation still compares
        # like with like; the unigram-only variant is an ablation arm, not an
        # assumption baked in here.
        self.bm25_dl = np.asarray(self.cnt.sum(axis=1)).ravel()
        self.bm25_avgdl = float(self.bm25_dl.mean()) if n_docs else 0.0

    def bm25_scores(
        self,
        q: str,
        idxs: list[int],
        k1: float = BM25_K1,
        b: float = BM25_B,
        unigrams_only: bool = False,
    ) -> list[float]:
        """Okapi BM25 of query `q` against the chunks at `idxs`.

        Query analysis goes through `self.vec.build_analyzer()`, i.e. the exact
        analyzer the cosine side uses, so the two signals see the same tokens.
        Repeated query terms are summed once per occurrence (rank_bm25's
        convention); after expand_query()'s dict.fromkeys dedup the query is
        almost always term-unique anyway.

        Returns 0.0 for every idx when no query term is in the vocabulary --
        the caller must treat an all-zero vector as "no opinion", which is why
        every arm that uses this keeps a cosine tie-break.
        """
        assert self.cnt is not None, "TfidfRetriever built without bm25=True"
        if not idxs:
            return []
        vocab = self.vec.vocabulary_
        terms = self.vec.build_analyzer()(q)
        if unigrams_only:
            terms = [t for t in terms if " " not in t]
        cols = [vocab[t] for t in terms if t in vocab]
        if not cols:
            return [0.0] * len(idxs)
        tf = self.cnt[idxs][:, cols].toarray()            # (n_cand, n_terms)
        dl = self.bm25_dl[idxs]
        norm = k1 * (1.0 - b + b * dl / (self.bm25_avgdl or 1.0))
        denom = tf + norm[:, None]
        sat = np.divide(tf * (k1 + 1.0), denom,
                        out=np.zeros_like(tf), where=denom > 0)
        return (sat @ self.bm25_idf[cols]).tolist()

    def bm25_bytes(self) -> int:
        """In-memory size of the BM25 index only. Reported by ablate_rerank.py
        because Render free is 512 MB and the Constitution is 2,037 chunks."""
        if self.cnt is None:
            return 0
        return int(self.cnt.data.nbytes + self.cnt.indices.nbytes
                   + self.cnt.indptr.nbytes + self.bm25_idf.nbytes
                   + self.bm25_dl.nbytes)

    def query(self, q: str, k: int = 3) -> list[tuple[int, float, str]]:
        sims = cosine_similarity(self.vec.transform([q]), self.mat)[0]
        top = sims.argsort()[::-1][:k]
        return [(int(i), float(sims[i]), self.chunks[i]) for i in top]


class PerDocRetriever:
    """One TfidfRetriever per doc_id; query merges top-k of EACH doc.

    Guarantees every doc (esp. the small Act index) is represented in the
    merged ranking no matter how large the Constitution index gets.
    query() returns Hit tuples sorted by score desc. retrieve() applies
    the MIN_SCORE gate and returns a refusal signal instead of weak hits.

    ------------------------------------------------------------------------
    OPT-IN SELECTION RE-RANK (Phase E2a, 2026-09-20). `rerank` DEFAULTS TO
    None, which is the shipping path and is byte-identical to the code that
    preceded this parameter. Nothing in src/rag.py or app.py passes it; the
    only caller today is scripts/ablate_rerank.py.

    WHY IT ACTS AT SELECTION AND NOT AT ORDERING. E2 was written as "re-order
    the already-admitted hits". At the E1b shipping arm that is provably inert:
    top_n == 3k, so select_top returns every candidate retrieved, and it
    re-sorts by score anyway -- an ordering-only re-rank cannot change which
    chunks are returned OR the order they are returned in. Every recall metric
    in the repo scores a SET. So the re-rank is moved one stage earlier:

        cosine over all chunks   -> top `pool` per doc    ADMISSION, unchanged
        bm25/rrf over that pool  -> top `k` per doc       SELECTION, new
        pin the doc's cosine #1  -> into those k          REFUSAL GUARD, new
        re-sort the k by cosine  -> then append           tie-break convention
        select_top(top_n)        -> unchanged

    HIT.SCORE STAYS COSINE. BM25 is unbounded and not comparable to a cosine;
    returning it would silently invalidate the calibration block at the top of
    this file. BM25 chooses; cosine still scores, orders and gates.

    WHY `pin_top`, AND WHY IT IS ON BY DEFAULT. Without it a doc's cosine-best
    chunk can be demoted out of its k slots. If that chunk is the GLOBAL max
    and it is dropped, the max over returned hits falls and can cross
    MIN_SCORE -- a manufactured FALSE REFUSAL, the failure CLAUDE.md names as
    the worst one. With it, the refusal-invariance proof under select_top
    carries verbatim: every doc's cosine argmax is returned (k >= 1), so the
    global max is; select_top provably keeps the global max; refusal <=> global
    max < MIN_SCORE. Bit-identical, question for question. It also pins
    query()'s expansion gates, which read base[0].score -- so expansion fires
    on exactly the same queries as today and E2 does not entangle itself with
    E3. `pin_top=False` exists so scripts/ablate_rerank.py can PRICE the guard.
    ------------------------------------------------------------------------
    """

    def __init__(
        self,
        docs: dict[str, list[Chunk]],
        k_default: int = 2,
        rerank: str | None = None,
        pool_per_doc: int = 20,
        pin_top: bool = True,
        bm25_k1: float = BM25_K1,
        bm25_b: float = BM25_B,
        bm25_unigrams: bool = False,
    ):
        for doc_id in docs:
            assert doc_id in DOC_IDS, "unknown doc_id %r" % doc_id
        assert rerank in (None, "bm25", "rrf"), "unknown rerank %r" % rerank
        self.docs = docs
        self.k_default = k_default
        self.rerank = rerank
        self.pool_per_doc = pool_per_doc
        self.pin_top = pin_top
        self.bm25_k1 = bm25_k1
        self.bm25_b = bm25_b
        self.bm25_unigrams = bm25_unigrams
        self.sub = {
            doc_id: TfidfRetriever([c.text for c in chunks],
                                   bm25=rerank is not None)
            for doc_id, chunks in docs.items()
        }

    def _doc_candidates(
        self, doc_id: str, q: str, k: int
    ) -> list[tuple[int, float, str]]:
        """This doc's k contributions, in cosine order. See the class docstring.

        `rerank is None` is the shipping path and must stay a plain call to the
        sub-retriever -- no pool, no extra transform, no behaviour to argue
        about. When the pool cannot be deeper than k (a caller asking k=20 at
        pool_per_doc=20, e.g. eval_heldout's recall@k curve) the re-rank has
        nothing to choose between and is a no-op by construction.
        """
        if self.rerank is None:
            return self.sub[doc_id].query(q, k=k)
        cand = self.sub[doc_id].query(q, k=max(self.pool_per_doc, k))
        if len(cand) <= k:
            return cand
        n = len(cand)
        # cand is cosine-desc, so the index j IS the cosine rank. Using j as
        # the tie-break keeps every ordering below deterministic and makes an
        # all-zero BM25 vector ("no query term in vocabulary") degrade to the
        # cosine order rather than to an arbitrary one.
        bm = self.sub[doc_id].bm25_scores(
            q, [i for i, _, _ in cand], k1=self.bm25_k1, b=self.bm25_b,
            unigrams_only=self.bm25_unigrams)
        bm_order = sorted(range(n), key=lambda j: (-bm[j], j))
        if self.rerank == "bm25":
            order = bm_order
        else:                                   # "rrf"
            bm_rank = [0] * n
            for r, j in enumerate(bm_order):
                bm_rank[j] = r
            order = sorted(range(n), key=lambda j: (
                -(1.0 / (RRF_K + 1 + j) + 1.0 / (RRF_K + 1 + bm_rank[j])), j))
        chosen = order[:k]
        if self.pin_top and 0 not in chosen:    # 0 == this doc's cosine argmax
            chosen = [0] + chosen[:k - 1]
        return [cand[j] for j in sorted(chosen)]

    def _merged(self, q: str, k: int) -> list[Hit]:
        """Top-k from each doc, merged and sorted. No expansion, no gating."""
        hits: list[Hit] = []
        for doc_id, chunks in self.docs.items():
            for i, s, _ in self._doc_candidates(doc_id, q, k):
                hits.append(Hit(chunks[i].doc_id, chunks[i].ref, chunks[i].text, s))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits

    def query(
        self, q: str, k: int | None = None, min_score: float | None = None
    ) -> list[Hit]:
        """Top-k hits from EACH doc, merged and sorted by score desc.

        min_score is the floor the EXPANSION GATE below consults; it does not
        filter the returned hits (retrieve() does that). It is threaded
        through so a caller using a non-default floor gates expansion on the
        same number it will later filter on, rather than on the module
        constant. No caller passes a non-default today -- this closes the
        latent inconsistency rather than leaving it to be discovered later.

        Synonym expansion happens HERE -- once, before the per-doc
        sub-retrievers run -- so all three docs are searched with the same
        expanded query and the indexes stay untouched. See expand_query().

        EXPANSION MAY NOT CHANGE A REFUSAL DECISION, IN EITHER DIRECTION.
        That is the whole guard, and it needs both halves -- the first version
        of it shipped only the first half and was caught in review.

        Entry side (expansion must not MANUFACTURE overlap). Measured before
        any gate existed: "my job interview went badly" scored 0.0000 with
        zero hits above MIN_SCORE, but the "job" entry lifted it to 0.2460
        with six hits. app.py's "Ask a Legal Question" button forces the legal
        route, so a user could have been shown dignity and equality clauses as
        if they answered that sentence. That defeats the single job MIN_SCORE
        is documented to do (calibration block at the top of this file):
        refuse zero-overlap queries.

        Exit side (expansion must not CREATE a false refusal). Appending terms
        that are absent from the best-matching document dilutes the query
        vector's norm without adding numerator mass, so a cosine can DROP.
        Measured: the bare query "blind" -- itself one of the curated keys --
        scored 0.1367 on Act cl.20, and expanding it to "blind visual
        impairment braille" pushed it to 0.0821, under the floor. A real,
        on-topic question about blindness would have been refused. CLAUDE.md
        is explicit that false refusals deny help to PWDs and that the gate
        errs low on purpose, so this direction matters at least as much as
        the first.

        So: score the ORIGINAL query. If it cannot clear the floor, return it
        unexpanded and let the caller refuse on the user's own words. If it
        can, expand -- but if the expanded query cannot clear the floor, fall
        back to the original hits. The honest statement of the property is
        therefore narrower than "expansion only helps":

          expansion never turns a refusal into an answer, and never turns an
          answer into a refusal. It only re-ranks within the answered set.

        It is NOT claimed that every expanded top score is higher than its
        base (Q6 drops 0.1759 -> 0.1696 and stays correct). Re-ranking that
        lowers the top hit while improving coverage deeper in the merged list is
        legitimate -- recall is measured over all of select_top's output, not
        the first hit. (That output was six chunks when this was written and is
        twelve since Phase E1b, 2026-09-20; the argument does not depend on the
        number.)

        MIN_SCORE itself is untouched at 0.10. It is used here as a
        precondition, not renegotiated. Cost is one extra TF-IDF transform per
        expanded query against a 2,104-chunk local index -- negligible, and
        the path stays fully offline.
        """
        k = self.k_default if k is None else k
        floor = MIN_SCORE if min_score is None else min_score
        base = self._merged(q, k)
        if not base or base[0].score < floor:
            return base                      # entry gate
        expanded = expand_query(q)
        if expanded == q:
            return base
        hits = self._merged(expanded, k)
        if not hits or hits[0].score < floor:
            return base                      # exit gate
        return hits

    def retrieve(
        self, q: str, k: int | None = None, min_score: float = MIN_SCORE
    ) -> tuple[list[Hit], bool]:
        """Merged hits at/above min_score + refusal flag.

        Returns (hits, refused): refused=True (and hits=[]) when NOTHING
        clears the threshold -- the caller must emit the fixed refusal
        message instead of answering. refused=False always carries >=1 hit.
        """
        hits = [h for h in self.query(q, k=k, min_score=min_score)
                if h.score >= min_score]
        if not hits:
            return [], True
        return hits, False


# ---------------------------------------------------------------------------
# Cross-doc merge (Phase 09 step 3 M2, added 2026-09-13).
#
# THE DEFECT THIS FIXES. PerDocRetriever exists because the Constitution is
# 2,104 of 2,214 chunks and floods a joint index; the class docstring above
# says in as many words that cross-doc cosines "are not strictly comparable"
# (separate TF-IDF spaces, different IDFs). Both shipping call sites then did
# exactly that comparison anyway: `retriever.query(q, k=k)[:top_n]` sorted the
# 9 candidates (3 docs x k=3) by raw cross-doc cosine and cut to 6. THE CUT
# RE-INTRODUCED THE FLOODING PER-DOC RETRIEVAL WAS BUILT TO PREVENT.
#
# WHAT IT BUYS, MEASURED: NOTHING. Say this first, because the comment that
# shipped in the draft of this block said the opposite. `min_per_doc=1`
# reproduces the baseline to three decimals on ALL THREE sets -- frozen-10
# 0.925, dev 0.420, test 0.338 -- while changing WHICH six chunks are shown on
# 7 of 60 questions. The 0.460 figure the draft quoted as "four points of
# recall thrown away by the slice" was measured with NO CUT AT ALL, i.e. while
# showing 9 chunks instead of 6. It was a top_n effect, not an ordering effect,
# and attributing it to this function was the error that produced the falsified
# Phase 09 step 3 plan (LEARNING_JOURNAL.md 2026-09-13).
#
# So this lands on correctness grounds only: it stops doing a comparison the
# class docstring calls invalid, it is provably refusal-invariant, and it is
# the merge a dense arm needs once fused ranks exist (Phase 10 D). H7 remains
# the clearest illustration of the DEFECT -- Act cl.24 ranked second in the
# Act's own index and never reached the user because six Constitution chunks
# outscored it on a scale the two indexes do not share -- but fixing it did not
# move the mean. Do not write this up as a recall win.
#
# REFUSAL INVARIANCE -- this is the property that keeps the MIN_SCORE
# calibration at the top of this file valid, and it is provable rather than
# hopeful. Callers refuse when nothing in the returned list clears the floor.
# `hits` is score-sorted, so the old top_n slice always contained the global
# maximum. select_top also always contains it: the quota phase takes it first
# if it clears the floor, and if it does not clear the floor the quota phase
# takes nothing at all and the fill phase takes it first. So in both cases
#   "some returned hit clears the floor"  <=>  "the global max clears the floor"
# and the refusal decision is bit-identical, question for question, on every
# set.
#
# That proof is checked empirically by a COMMITTED script, as of Phase 10 D5
# (2026-09-19): `scripts/calibrate_refusal.py`, block 1. The same 106 probes
# the 2026-09-13 throwaway harness used (60 eval questions + 12 off-corpus + 34
# bare synonym keys) but imported from their sources rather than copied, run
# against BOTH corpus versions in one process: 212 probe-runs, ZERO
# disagreements. The earlier note here -- that the claim rested on "a run
# nobody can reproduce" -- is discharged, and so is the draft reference to a
# `scripts/ablate_phase09.py` that never existed.
#
# The battery also records what CANNOT falsify this property, so the next
# reader does not mistake a silent test for a passing one. Passing floor=0.0
# to select_top (the "latent inconsistency" its docstring describes) leaves the
# invariance intact, because the global maximum is in the output at EVERY
# floor: at 0.0 the quota phase takes each doc's best hit and the global max is
# some doc's best hit. The gate is instead proven live by a mutant selector
# that drops the global max, which does fire. Both are in the script's
# --negative-test path.
#
# This is the gate that lets a dense arm widen admission without moving the
# refusal decision, so re-run it after any change to select_top.
#
# WHY A QUOTA AND NOT JUST A WIDER CUT. Showing more than six excerpts changes
# what the user reads and what the LLM is billed for. The quota keeps the
# budget at six and changes only WHICH six -- the Act is guaranteed its best
# candidate even when the Constitution owns the whole global top of the list.
#
# POINTER, 2026-09-20 (Phase E1b) -- everything above is the 2026-09-13 record
# and is kept as history, numbers and all. Two facts have since moved out from
# under its prose:
#   * "3 docs x k=3 = 9 candidates cut to 6" and "the budget stays six" describe
#     the OLD shipping arm. The arm is now k=4/doc -> select_top(top_n=12), i.e.
#     12 candidates and a budget of 12, so top_n == 3k and THERE IS NO CUT: this
#     function returns every candidate retrieved and the quota phase decides
#     ordering only. The invalid cross-doc comparison it exists to avoid is
#     therefore not merely mitigated at the shipping arm, it is unreachable.
#   * That widening was priced, not guessed: E1a's ladder
#     (scripts/ablate_phase10.py) measured frozen-10 / dev / test recall_strict
#     0.633/0.473/0.471 -> 0.734/0.573/0.529 on corpus v2, and the E1a finding
#     that "pool width is inert once top_n == 3k" is exactly the corrected form
#     of the "it was a top_n effect, not an ordering effect" note above.
# REFUSAL INVARIANCE IS UNAFFECTED, and that is the paragraph to re-read before
# doubting it: the proof is about the global maximum being present, which holds
# at every k and every top_n.
# ---------------------------------------------------------------------------
def select_top(
    hits: list[Hit],
    top_n: int,
    min_per_doc: int = 1,
    floor: float = MIN_SCORE,
) -> list[Hit]:
    """Merge cross-doc candidates to at most `top_n`, reserving per-doc slots.

    Reserves up to `min_per_doc` slots for each doc's best hits, but ONLY for
    hits that already clear `floor` -- never spend a guaranteed slot on
    something the caller's gate is about to drop anyway. Remaining slots are
    filled by global score. The result is returned in global score order, so
    every existing consumer (per_doc_top, excerpt display, the eval harnesses)
    sees the same shape it saw before.

    Deterministic: ordering is (-score, original index) throughout, so equal
    scores never reorder run to run and an ablation is reproducible.

    `floor` is threaded through rather than read from the module constant so a
    caller passing a non-default min_score reserves slots on the same number it
    will later filter on. This is the same latent inconsistency
    PerDocRetriever.query() already closes for the expansion gate.
    """
    if top_n <= 0 or not hits:
        return []
    order = sorted(range(len(hits)), key=lambda i: (-hits[i].score, i))
    chosen: list[int] = []
    seen: set[int] = set()
    if min_per_doc > 0:
        quota: dict[str, int] = {}
        for i in order:
            if len(chosen) >= top_n:
                break
            if hits[i].score < floor:
                continue
            used = quota.get(hits[i].doc_id, 0)
            if used < min_per_doc:
                quota[hits[i].doc_id] = used + 1
                chosen.append(i)
                seen.add(i)
    for i in order:
        if len(chosen) >= top_n:
            break
        if i not in seen:
            chosen.append(i)
            seen.add(i)
    return [hits[i] for i in sorted(chosen, key=lambda i: (-hits[i].score, i))]


def cite_tag(doc_id: str, ref: str) -> str:
    """Canonical citation tag for a hit, e.g. '[Act cl. 31]'."""
    if doc_id == "act2018":
        return "[Act %s]" % ref
    if doc_id == "constitution1999":
        return "[Constitution %s]" % ref
    if doc_id == "factsheet2020":
        return "[Factsheet %s]" % ref
    return "[%s %s]" % (doc_id, ref)


def embed_gemini(texts: list[str], model: str = "models/gemini-embedding-001") -> list[list[float]]:
    """Opt-in Gemini embeddings via the new `google.genai` SDK. Raises if
    key/package missing. NOTE: previously used the deprecated
    `google.generativeai` package -- migrated (env has google-genai 2.22)."""
    import os
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_API_KEY/GEMINI_API_KEY not set")
    from google import genai
    client = genai.Client(api_key=key)
    out: list[list[float]] = []
    for t in texts:
        resp = client.models.embed_content(model=model, contents=[t])
        out.append(list(resp.embeddings[0].values))
    return out
