"""E4.0 reach gate -- can pretrained-vector query expansion reach anything? DEV SET ONLY.

Written 2026-09-23 to re-scope Phase E step E4 (docs/phases/13_retrieval_quality.md).
E4's only mechanism that is not inert at the shipping budget is EXPANSION of query terms
the corpus never uses. This lists, per answerable dev question, the query terms that are
out-of-corpus (stem absent from the v2 index vocabulary) and NOT already bridged by a
SYNONYMS key. A failing question with no content-bearing term in that list is out of E4's
reach by construction, whatever vectors are used.

Reads the `heldout` (dev) set only -- dev is already spent (see evalset.py) and is the
selector. It never reads `test`. Zero network, zero quota, touches nothing on the
shipping path.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from evalset import load_eval_set  # noqa: E402
from rag import build_corpus  # noqa: E402
from retrieve import (ENGLISH_STOP_WORDS, SYNONYMS, _surface_forms,  # noqa: E402
                      stem, stem_preprocess)


def main() -> int:
    vocab = set()
    for chunks in build_corpus("v2").values():
        for c in chunks:
            vocab |= set(stem_preprocess(c.text).split())
    stop = {stem(w) for w in ENGLISH_STOP_WORDS} | set(ENGLISH_STOP_WORDS)
    keys = set(SYNONYMS) | {stem(k) for k in SYNONYMS}
    rows = [r for r in load_eval_set("heldout") if r["expect_gate"] == "answer"]
    n_hit, by_class = 0, {}
    for r in rows:
        toks = [w for w in re.findall(r"[a-z]+", r["text"].lower())
                if w not in stop and len(w) > 2]
        fired = bool(_surface_forms(r["text"]) & keys)
        oov = [w for w in toks if stem(w) not in vocab and w not in vocab]
        unbridged = [w for w in oov if not ({w, stem(w), w[:-1]} & keys)]
        n_hit += bool(unbridged)
        c = by_class.setdefault(r["class"], [0, 0])
        c[0] += 1
        c[1] += bool(unbridged)
        print("%-6s %-15s handmap=%s oov=%s unbridged=%s"
              % (r["id"], r["class"], "Y" if fired else "-", oov, unbridged))
    print("\nv2 index vocab = %d stems; dev answerable = %d; "
          "with >=1 unbridged OOV term = %d" % (len(vocab), len(rows), n_hit))
    for k, (n, h) in by_class.items():
        print("  %-15s %d/%d" % (k, h, n))
    print("NOTE: raw count includes function words (somebody, says, near ...);"
          " the content-bearing reading is in the playbook E4 re-scope box.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
