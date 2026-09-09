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

    def query(self, q: str, k: int | None = None) -> list[Hit]:
        """Top-k hits from EACH doc, merged and sorted by score desc."""
        k = self.k_default if k is None else k
        hits: list[Hit] = []
        for doc_id, chunks in self.docs.items():
            for i, s, _ in self.sub[doc_id].query(q, k=k):
                hits.append(Hit(chunks[i].doc_id, chunks[i].ref, chunks[i].text, s))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits

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
