"""Phase E4a -- build the OOV bridge: pretrained-vector neighbours for query words the corpus never uses.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\build_oov_bridge.py  (from D:\\NGORAG)
     ... --vectors=<path>   GloVe file (default D:\\NGORAG\\runs\\e4_vectors\\glove-wiki-gigaword-100.gz)
     ... --corpus=<ver>     v2 (default) -> data/processed/oov_bridge.json,
                            v3 -> data/processed/oov_bridge_v3.json. EQUALS FORM ONLY.

VERSION-KEYED (H8a.2 / F7). Each corpus version has its own artifact, registered in
src/retrieve.py OOV_BRIDGE_PATHS; PerDocRetriever picks the one whose corpus_sha256
matches the chunk stream it indexes. Building v3 never touches oov_bridge.json, so v2
keeps reproducing its published numbers from the same commit. The fixed parameters
below apply unchanged to every version: "the v2 index" in the SPEC lines means "the
index of the corpus being built".

SHIPPING ARTIFACT (since Phase E4a, 2026-09-23). Writes data/processed/oov_bridge.json,
which src/retrieve.py loads at import and expand_query() consults on every query.
rag.build_corpus("v2") hard-fails if the artifact's corpus digest no longer matches,
so a corpus change forces a rebuild AND a re-measurement (scripts/ablate_oov_bridge.py).
Re-running this on the same corpus and vector file is deterministic.

SPEC: docs/phases/13_retrieval_quality.md, the E4 re-scope box (2026-09-23), point 4.
The parameters below were FIXED THERE BEFORE THIS FILE EXISTED -- do not tune them
here. The playbook allows one dev-only retreat (R=5000 or TAU=0.65), passed on the
command line and recorded as a second look.

  keys   : GloVe words at frequency rank (R, KEY_MAX_RANK] whose stem is ABSENT from
           the v2 index vocabulary and which never occur as a corpus token. The rank
           floor is the content filter: GloVe 6B is frequency-ordered, and the top R
           are where `somebody` / `says` / `near` live.
  values : at most M nearest neighbours by cosine, restricted to words that DO occur
           in the corpus (surface form present, stem in the index), cosine >= TAU.

BUILT WITHOUT READING data/eval/questions.json -- inputs are the corpus and the
vector file only. The vector file is a build-time input, never in the repo, and no
vector ships: the artifact is a plain dict, a lookup like SYNONYMS.
"""

import gzip
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rag import build_corpus  # noqa: E402
from retrieve import (ENGLISH_STOP_WORDS, OOV_BRIDGE_PATHS,  # noqa: E402
                      corpus_sha256, stem, stem_preprocess)

DEFAULT_VECTORS = Path(r"D:\NGORAG\runs\e4_vectors\glove-wiki-gigaword-100.gz")
OUT = ROOT / "data" / "processed" / "oov_bridge.json"

# Fixed a priori in the playbook (E4 re-scope box, point 4).
R = 2000
M = 2
TAU = 0.55
KEY_MAX_RANK = 50000
SIZE_CAP_BYTES = 2 * 1024 * 1024

WORD = re.compile(r"^[a-z]{3,}$")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    opt = dict(a[2:].split("=", 1) for a in argv if a.startswith("--") and "=" in a)
    vec_path = Path(opt.get("vectors", DEFAULT_VECTORS))
    r_floor = int(opt.get("R", R))
    tau = float(opt.get("tau", TAU))
    corpus = opt.get("corpus", "v2")
    if corpus not in OOV_BRIDGE_PATHS:
        print("BUILD_OOV_BRIDGE: FAIL -- no bridge path registered for corpus %r" % corpus)
        return 1
    out = Path(opt.get("out", OOV_BRIDGE_PATHS[corpus]))

    docs = build_corpus(corpus, check_bridge=False)
    stems, tokens = set(), set()
    for chunks in docs.values():
        for c in chunks:
            stems |= set(stem_preprocess(c.text).split())
            tokens |= set(re.findall(r"[a-z]+", c.text.lower()))
    stop = set(ENGLISH_STOP_WORDS)

    key_words, key_vecs, tgt_words, tgt_vecs = [], [], [], []
    with gzip.open(vec_path, "rt", encoding="utf-8") as f:
        first = f.readline().split()
        if len(first) != 2:              # headerless GloVe text: first line is a vector
            f.seek(0)
        for rank, line in enumerate(f, start=1):
            w, rest = line.split(" ", 1)
            if not WORD.match(w) or w in stop:
                continue
            in_corpus = w in tokens and stem(w) in stems
            is_key = (r_floor < rank <= KEY_MAX_RANK and w not in tokens
                      and stem(w) not in stems)
            if not (in_corpus or is_key):
                continue
            v = np.array(rest.split(), dtype=np.float32)
            if in_corpus:
                tgt_words.append(w)
                tgt_vecs.append(v)
            if is_key:
                key_words.append(w)
                key_vecs.append(v)

    K = np.vstack(key_vecs)
    T = np.vstack(tgt_vecs)
    K /= np.linalg.norm(K, axis=1, keepdims=True)
    T /= np.linalg.norm(T, axis=1, keepdims=True)

    bridge = {}
    for i in range(0, len(K), 4096):
        S = K[i:i + 4096] @ T.T
        top = np.argsort(-S, axis=1)[:, :M]
        for j, row in enumerate(top):
            nb = [tgt_words[t] for t in row if S[j, t] >= tau]
            if nb:
                bridge[key_words[i + j]] = nb

    meta = {
        "corpus": corpus,
        "corpus_sha256": corpus_sha256(docs),
        "vectors": vec_path.name,
        "R": r_floor, "M": M, "tau": tau, "key_max_rank": KEY_MAX_RANK,
        "candidate_keys": len(key_words), "targets": len(tgt_words),
        "keys": len(bridge),
    }
    text = json.dumps({"_meta": meta, "bridge": bridge}, ensure_ascii=True,
                      sort_keys=True, separators=(",", ":"))
    out.write_text(text + "\n", encoding="utf-8")
    size = out.stat().st_size

    print("== E4a OOV BRIDGE BUILD ==")
    for k, v in meta.items():
        print("  %-16s %s" % (k, v))
    print("  %-16s %d bytes (cap %d)" % ("artifact", size, SIZE_CAP_BYTES))
    for w in ("sack", "fired", "jail", "lawyer", "boss", "beg", "locked",
              "illness", "reachable", "differently", "football", "pizza"):
        print("  probe %-12s -> %s" % (w, bridge.get(w, "(no key)")))
    if size > SIZE_CAP_BYTES:
        print("BUILD_OOV_BRIDGE: FAIL -- artifact exceeds the 2 MB cap")
        return 1
    print("BUILD_OOV_BRIDGE: OK -> %s" % out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
