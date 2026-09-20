"""Phase E3a -- derive a synonym map from the CORPUS, without looking at the eval.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\build_synonyms.py  (from D:\\NGORAG)
     ... --corpus=v1      build the retired corpus's map instead
     ... --out=<path>     override the output path
     ... --show=N         print the first N emitted keys (inspection only)

Writes data/processed/synonyms_auto.json (v1 -> synonyms_auto_v1.json).

WHAT THIS IS FOR
----------------
src/retrieve.py's SYNONYMS map is hand-written, and it was curated by keeping
and deleting entries according to their effect on Q1..Q10 -- which is exactly
why frozen-10 reads 0.925 and held-out read 0.420. The playbook
(docs/phases/13_retrieval_quality.md, E3) asks the obvious question: does a map
derived from corpus text ALONE, with no sight of any eval question, beat the map
that was fitted to them -- and does either beat turning expansion off?

This script is the "derived from corpus text alone" half. It never reads
data/eval/questions.json, and nothing below is conditioned on any eval number.
scripts/ablate_synonyms.py is the measuring half.

METHOD: PPMI + truncated SVD over term-chunk co-occurrence
----------------------------------------------------------
  CountVectorizer(stem_preprocess, stemmed stopwords, unigrams, binary)
  X (chunks x terms)  ->  C = X.T @ X          term-term chunk co-occurrence
  PPMI(i,j) = max(0, log( p(i,j) / (p(i)p(j)) ))
  TruncatedSVD(150) -> term vectors -> neighbours by cosine

Pure sklearn/numpy, already in the pinned env. ZERO new packages, ZERO network,
and nothing here touches requirements.txt -- the artifact is a JSON dict and the
runtime cost of consuming it is a dict lookup.

TERM-LEVEL ON PURPOSE. Embeddings are E4. Keeping E3 at the term level is what
makes the two steps separately attributable, which is the playbook's "one arm
per commit" trap.

THE WINDOW IS THE CHUNK (400-1100 chars), so this measures TOPICAL ASSOCIATION,
not strict synonymy. That is the right target: the hand map's own curation rule
is "expand toward the corpus, never away" (src/retrieve.py:239-246), and its
entries are associations too ("dignity" -> degrading/inhuman/torture is not
synonymy, it is the register Constitution s.34 actually uses).

EVERY FILTER BELOW IS DECLARED A PRIORI, BY PRINCIPLE
-----------------------------------------------------
This is the one rule the whole step exists to respect. None of these values was
chosen by its effect on frozen-10, dev or test; each has a stated reason that
does not mention a metric. If a future session wants to move one, it must move
it for a reason of the same kind -- otherwise the auto map becomes the hand map
with extra arithmetic, and E3 will have measured nothing.

  MIN_DF = 5          fewer occurrences give no usable co-occurrence statistics
  MAX_DF = 0.20       drops person/act/section/shall boilerplate, which would
                      otherwise be everyone's nearest neighbour
  MIN_LEN = 4, alpha  numbers are citation refs, not vocabulary
  N_NEIGHBOURS = 4    the hand map's own median entry size
  MIN_COS = 0.50      weak keys emit NOTHING rather than noise -- this is what
                      keeps the map sparse
  N_COMPONENTS = 150  standard truncation for a ~1k term space

KNOWN STRUCTURAL LIMIT, RECORDED BEFORE MEASURING
-------------------------------------------------
6 of the hand map's 34 keys -- fined, jail, sack, fired, job, lawyer -- DO NOT
OCCUR IN THE CORPUS AT ALL. They are precisely the user-register keys, the ones
bridging "can they sack me" to the Act's "terminate the employment of". A
generator over corpus vocabulary can only emit keys the corpus contains, so it
CANNOT reproduce that 18% of the hand map. This is a property of the method,
known in advance, and it is why the ablation carries a hand-union-auto arm.

DETERMINISM
-----------
Re-running on the same corpus MUST produce a byte-identical file or the ablation
is not reproducible. SVD random_state is fixed, neighbour ties break on the term
string, and keys are written sorted. `_meta.built` is the one field that would
otherwise move: it is PRESERVED from the existing file whenever the corpus
sha256 is unchanged, so it records when the MAP was derived rather than when the
script was last run.
"""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, CountVectorizer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rag import CORPUS_VERSION, build_corpus  # noqa: E402
from retrieve import stem, stem_preprocess  # noqa: E402

# --- the a priori filters. See the docstring; do not tune these on an eval set.
MIN_DF = 5
MAX_DF = 0.20
MIN_LEN = 4
N_COMPONENTS = 150
N_NEIGHBOURS = 4
MIN_COS = 0.50
RANDOM_STATE = 0

OUT_DEFAULT = {
    "v2": ROOT / "data" / "processed" / "synonyms_auto.json",
    "v1": ROOT / "data" / "processed" / "synonyms_auto_v1.json",
}


def corpus_sha256(docs: dict) -> str:
    """Hash of the exact chunk stream the map is derived from.

    Keyed on (doc_id, ref, text) in build_corpus()'s insertion order, so it
    moves if the corpus, the chunker or the doc order moves -- all three of
    which would invalidate the map. The consumer and the ablation both print
    this, so a stale artifact is visible rather than silently measured.
    """
    h = hashlib.sha256()
    for doc_id, chunks in docs.items():
        for c in chunks:
            h.update(doc_id.encode("utf-8"))
            h.update(b"\x00")
            h.update(c.ref.encode("utf-8"))
            h.update(b"\x00")
            h.update(c.text.encode("utf-8"))
            h.update(b"\x00")
    return h.hexdigest()


def term_matrix(texts: list[str]):
    """Binary chunk x term matrix over the SAME term space the index uses.

    Same preprocessor and same stemmed stopword list as TfidfRetriever, for the
    reason E2a reused the TF-IDF vocabulary for BM25: a term space that agrees
    by construction cannot silently diverge from the one the retriever scores
    in. It differs deliberately in exactly two ways, both required by the
    method:

      * unigrams only -- the map's VALUES are appended to a query as single
        words, and a bigram key could not be matched by _surface_forms();
      * binary -- co-occurrence asks "did these two terms appear in the same
        chunk", not "how often". Raw counts would let one chunk repeating a
        term dominate its own PPMI row.

    Returns (X, terms) with the alphabetic / MIN_LEN filter already applied.
    Filtering columns AFTER the fit is equivalent to filtering before it: df is
    a per-column property, so min_df/max_df admit exactly the same columns
    either way.
    """
    cv = CountVectorizer(
        preprocessor=stem_preprocess,
        stop_words=[stem(w) for w in ENGLISH_STOP_WORDS],
        ngram_range=(1, 1),
        binary=True,
        min_df=MIN_DF,
        max_df=MAX_DF,
        dtype=np.float64,
    )
    X = cv.fit_transform(texts)
    vocab = cv.get_feature_names_out()
    keep = [i for i, t in enumerate(vocab)
            if t.isalpha() and len(t) >= MIN_LEN]
    return X[:, keep], [str(vocab[i]) for i in keep]


def ppmi(X) -> np.ndarray:
    """Positive pointwise mutual information over term-term co-occurrence.

    C = X.T @ X counts the chunks in which terms i and j both occur (the
    diagonal is term i's document frequency). PPMI then measures how much more
    often that happens than independence predicts, which is what strips the
    "both are common" signal that a raw count carries. The clip at zero is the
    standard positive variant: negative PMI on a 2k-chunk corpus is mostly
    sampling noise, and keeping it would make co-occurrence counts of 0 and 1
    differ by an unbounded amount.
    """
    C = np.asarray((X.T @ X).todense(), dtype=np.float64)
    total = C.sum()
    marg = C.sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        M = np.log((C * total) / np.outer(marg, marg))
    M[~np.isfinite(M)] = 0.0
    return np.maximum(M, 0.0)


def neighbours(M: np.ndarray, terms: list[str]) -> dict:
    """{term: [(neighbour, cosine), ...]} -- at most N_NEIGHBOURS, >= MIN_COS.

    SVD is what turns "co-occurs with" into "behaves like": two terms that
    never share a chunk can still land close if they co-occur with the same
    third terms, which is the only way this method can cross a vocabulary gap
    at all. Ties break on the term string so the artifact is byte-stable.
    """
    svd = TruncatedSVD(n_components=N_COMPONENTS, random_state=RANDOM_STATE)
    V = svd.fit_transform(M)
    norms = np.linalg.norm(V, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    V = V / norms
    sims = V @ V.T
    np.fill_diagonal(sims, -np.inf)          # never a neighbour of itself
    out = {}
    for i, t in enumerate(terms):
        cand = [(terms[j], float(sims[i, j]))
                for j in np.nonzero(sims[i] >= MIN_COS)[0]]
        cand.sort(key=lambda p: (-p[1], p[0]))
        if cand:
            out[t] = cand[:N_NEIGHBOURS]
    return out, float(svd.explained_variance_ratio_.sum())


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # EQUALS FORM ONLY (repo convention: the space form is silently ignored).
    corpus = next((a.split("=", 1)[1] for a in argv
                   if a.startswith("--corpus=")), None)
    out_arg = next((a.split("=", 1)[1] for a in argv
                    if a.startswith("--out=")), None)
    show = int(next((a.split("=", 1)[1] for a in argv
                     if a.startswith("--show=")), "0"))
    version = corpus or CORPUS_VERSION
    out = Path(out_arg) if out_arg else OUT_DEFAULT[version]

    docs = build_corpus(corpus)
    texts = [c.text for chunks in docs.values() for c in chunks]
    sha = corpus_sha256(docs)

    print("== PHASE E3a: CORPUS-DERIVED SYNONYM MAP (corpus=%s) ==" % version)
    print("  Built from corpus text ONLY. data/eval/questions.json is not read")
    print("  by this script and no filter below was chosen by its effect on an")
    print("  eval set -- see the docstring's table of principles.")
    print("  chunks %d (%s)" % (len(texts), ", ".join(
        "%s %d" % (d, len(c)) for d, c in docs.items())))
    print("  corpus sha256 %s" % sha[:16])

    X, terms = term_matrix(texts)
    print("\n== TERM SPACE ==")
    print("  min_df=%d, max_df=%.2f, alphabetic, len>=%d -> %d terms"
          % (MIN_DF, MAX_DF, MIN_LEN, len(terms)))

    M = ppmi(X)
    nn, evr = neighbours(M, terms)
    n_vals = sum(len(v) for v in nn.values())
    print("\n== NEIGHBOURS ==")
    print("  SVD %d components, explained variance %.3f" % (N_COMPONENTS, evr))
    print("  keys emitted %d of %d terms (%.0f%%); %d total neighbour terms"
          % (len(nn), len(terms), 100.0 * len(nn) / max(len(terms), 1), n_vals))
    print("  A key with no neighbour at cosine >= %.2f emits NOTHING. If this"
          % MIN_COS)
    print("  map is large it will fire on nearly every query and append far")
    print("  more mass than the 34-key hand map ever does -- that dilution is a")
    print("  FINDING for the ablation to price (retrieve.AUTO_MAX_TERMS caps")
    print("  the consumer side at 8 terms per query), not a threshold to tune.")

    # --- overlap with the hand map, reported because the union arm needs it ---
    # TWO DIFFERENT ABSENCES, and conflating them would overstate the method's
    # structural limit. A hand key can be missing from the emitted map because
    # the corpus never uses the word at all (unreachable by ANY corpus-derived
    # method, at any parameter setting), or because it uses it too rarely / in
    # too few characters to survive the a priori filters (unreachable by THIS
    # parameterisation). Only the first is a property of the approach.
    from retrieve import SYNONYMS  # noqa: E402  (local: keeps import cost off)
    corpus_tokens = set()
    for t in texts:
        corpus_tokens.update(stem_preprocess(t).split())
    hand_keys = {stem(k) for k in SYNONYMS if " " not in k}
    emitted = sorted(hand_keys & set(nn))
    never = sorted(k for k in hand_keys if k not in corpus_tokens)
    filtered = sorted(k for k in hand_keys
                      if k in corpus_tokens and k not in nn)
    print("\n== AGAINST THE HAND MAP ==")
    print("  hand keys (single word, stemmed): %d" % len(hand_keys))
    print("  emitted here                      %d: %s"
          % (len(emitted), ", ".join(emitted)))
    print("  in the corpus but filtered out    %d: %s"
          % (len(filtered), ", ".join(filtered)))
    print("    (below min_df=%d, above max_df=%.2f, or under %d chars)"
          % (MIN_DF, MAX_DF, MIN_LEN))
    print("  NOT IN THE CORPUS AT ALL          %d: %s"
          % (len(never), ", ".join(never)))
    print("  That last row is the structural limit: those are USER-REGISTER")
    print("  words -- what a person types, not what the Act writes -- and NO")
    print("  corpus-derived generator can emit them at any parameter setting.")
    print("  It is the whole reason ablate_synonyms.py carries a union arm.")

    # --- write, preserving `built` when the corpus has not moved -------------
    prev = {}
    if out.exists():
        try:
            prev = json.loads(out.read_text(encoding="utf-8")).get("_meta", {})
        except (ValueError, OSError):
            prev = {}
    if prev.get("corpus_sha256") == sha and prev.get("built"):
        built = prev["built"]
    else:
        from datetime import date
        built = date.today().isoformat()

    payload = {
        "_meta": {
            "generator": "scripts/build_synonyms.py",
            "method": "PPMI + TruncatedSVD over binary term-chunk co-occurrence",
            "corpus_version": version,
            "corpus_sha256": sha,
            "n_chunks": len(texts),
            "n_terms": len(terms),
            "n_keys": len(nn),
            "n_neighbour_terms": n_vals,
            "explained_variance_ratio": round(evr, 6),
            "built": built,
            "params": {
                "min_df": MIN_DF,
                "max_df": MAX_DF,
                "min_len": MIN_LEN,
                "n_components": N_COMPONENTS,
                "n_neighbours": N_NEIGHBOURS,
                "min_cos": MIN_COS,
                "random_state": RANDOM_STATE,
            },
        },
        # Neighbour cosines are kept, not just the terms: the consumer's cap
        # (AUTO_MAX_TERMS) takes the highest-cosine terms across every key a
        # query fires, which is not expressible from rank order alone once two
        # keys fire at once.
        "map": {k: [[t, round(c, 6)] for t, c in v]
                for k, v in sorted(nn.items())},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1, sort_keys=False) + "\n",
                   encoding="utf-8")
    print("\n  wrote %s (%.1f KB)"
          % (out.relative_to(ROOT), out.stat().st_size / 1024.0))
    print("  built=%s (preserved across re-runs while corpus sha256 is"
          % built)
    print("  unchanged, so a re-run is byte-identical)")

    if show:
        print("\n== FIRST %d KEYS ==" % show)
        for k in sorted(nn)[:show]:
            print("  %-16s %s" % (k, " ".join(
                "%s(%.2f)" % (t, c) for t, c in nn[k])))

    print("\nBUILD_SYNONYMS: PASS (%d keys; measured by "
          "scripts/ablate_synonyms.py)" % len(nn))
    return 0


if __name__ == "__main__":
    sys.exit(main())
