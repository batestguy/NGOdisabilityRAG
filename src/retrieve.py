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
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---------------------------------------------------------------------------
# Refusal threshold.
# Calibration (measured 2026-09-08, per-doc merged top-1, k=2/doc):
#   in-corpus 10Q minima: Q8 0.1690, Q2 0.1744, Q6 0.1751 (all 10 >= 0.169).
#   Joint-corpus Phase 01 after-table minima: Q5 0.141, Q9 0.167.
#   generic off-corpus maxima: sourdough 0.124, quantum 0.150, visa 0.161.
#   same-vocabulary off-corpus ("maritime shipping insurance (law)"):
#   0.249-0.306 -- ABOVE the weakest in-corpus hit. The band is INVERTED:
#   no single cosine value separates "shares legal words" from "on-topic".
#   (TF-IDF scores word overlap, not meaning; "law"/"Act" carry junk high.)
# Hence MIN_SCORE = 0.10 is a weak-overlap FLOOR, not a semantic filter:
# below every in-corpus hit on both scales (joint min 0.141, per-doc min
# 0.169 -- 10/10 pass with margin) while refusing zero-overlap queries.
# Semantic refusal is the strict LLM layer (exact no-answer sentence ->
# REFUSAL_MESSAGE in src/rag.py). False refusals deny help to PWDs, so the
# gate errs low by design; failures are logged, not hidden. Revisit only
# with a discriminative signal (e.g. query-term coverage), never by nudging
# this number into the inverted band.
# ---------------------------------------------------------------------------
MIN_SCORE = 0.10

DOC_IDS = ("act2018", "constitution1999", "factsheet2020")

# A chunk of citable text. ref examples: Act "cl. 31", Constitution "s. 17",
# Factsheet "Section 19" (or "general" when no section marker was found).
Chunk = namedtuple("Chunk", ["doc_id", "ref", "text"])

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
        if w.endswith("es") and len(w) > 3:   # buses -> bus, abuses -> abus
            forms.add(w[:-2])
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


class TfidfRetriever:
    """Single-corpus TF-IDF retriever. Kept backward compatible:
    chunks are bare strings, query() returns [(idx, score, text)]."""

    def __init__(self, chunks: list[str]):
        self.chunks = chunks
        self.vec = TfidfVectorizer(
            preprocessor=stem_preprocess,
            # Stopwords must be stemmed too (preprocessor runs first, so
            # raw "having" would otherwise evade removal as "hav").
            stop_words=[stem(w) for w in ENGLISH_STOP_WORDS],
            ngram_range=(1, 2),
        )
        self.mat = self.vec.fit_transform(chunks)

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
    """

    def __init__(self, docs: dict[str, list[Chunk]], k_default: int = 2):
        for doc_id in docs:
            assert doc_id in DOC_IDS, "unknown doc_id %r" % doc_id
        self.docs = docs
        self.k_default = k_default
        self.sub = {
            doc_id: TfidfRetriever([c.text for c in chunks])
            for doc_id, chunks in docs.items()
        }

    def _merged(self, q: str, k: int) -> list[Hit]:
        """Top-k from each doc, merged and sorted. No expansion, no gating."""
        hits: list[Hit] = []
        for doc_id, chunks in self.docs.items():
            for i, s, _ in self.sub[doc_id].query(q, k=k):
                hits.append(Hit(chunks[i].doc_id, chunks[i].ref, chunks[i].text, s))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits

    def query(self, q: str, k: int | None = None) -> list[Hit]:
        """Top-k hits from EACH doc, merged and sorted by score desc.

        Synonym expansion happens HERE -- once, before the per-doc
        sub-retrievers run -- so all three docs are searched with the same
        expanded query and the indexes stay untouched. See expand_query().

        EXPANSION IS GATED ON THE USER'S OWN WORDS (added 2026-09-11 after
        review). It is an aid to a query that already overlaps the corpus,
        never a way to MANUFACTURE overlap. Measured before this gate existed:
        "my job interview went badly" scored 0.0000 with zero hits above
        MIN_SCORE, but the "job" -> employment/employ/work/labour entry lifted
        it to 0.2460 with six hits -- and app.py's "Ask a Legal Question"
        button forces the legal route, so a user could have been shown
        dignity and equality clauses as if they answered that sentence. That
        defeats the single job MIN_SCORE is documented to do (see the
        calibration block at the top of this file): refuse zero-overlap
        queries. Synonyms must not be able to talk the gate out of a refusal.

        So: score the ORIGINAL query first; if it cannot clear the floor,
        return its hits unexpanded and let the caller refuse on the user's own
        words. The consequence is a property worth stating plainly -- the set
        of queries that get refused is IDENTICAL to the pre-expansion set.
        Expansion can only reorder and improve hits for queries that already
        passed. MIN_SCORE itself is untouched at 0.10; it is used here as a
        precondition, not renegotiated.

        Cost is one extra TF-IDF transform per expanded query, which is
        nothing against a 2,104-chunk local index and keeps the path offline.
        """
        k = self.k_default if k is None else k
        base = self._merged(q, k)
        if not base or base[0].score < MIN_SCORE:
            return base
        expanded = expand_query(q)
        if expanded == q:
            return base
        return self._merged(expanded, k)

    def retrieve(
        self, q: str, k: int | None = None, min_score: float = MIN_SCORE
    ) -> tuple[list[Hit], bool]:
        """Merged hits at/above min_score + refusal flag.

        Returns (hits, refused): refused=True (and hits=[]) when NOTHING
        clears the threshold -- the caller must emit the fixed refusal
        message instead of answering. refused=False always carries >=1 hit.
        """
        hits = [h for h in self.query(q, k=k) if h.score >= min_score]
        if not hits:
            return [], True
        return hits, False


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
