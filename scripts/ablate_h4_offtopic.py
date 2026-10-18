"""H4 offline off-topic guard -- dev-first measurement harness (zero quota).

Playbook: docs/phases/16_post_launch_roadmap.md, H4. The signal is FIXED in
advance (one retreat allowed only if it catches 0/5 on dev):

  coverage(q) = share of the query's content stems that the corpus already
                knows -- a stem counts as known if it is in the corpus
                vocabulary, or if the SHIPPING expansion (hand map + OOV bridge,
                retrieve.expand_query) maps that word to corpus vocabulary.
  The guard fires when coverage(q) < THETA.

THETA is chosen on DEV ONLY (heldout off-corpus 5 + heldout answerable 25) as
the largest value that fires on NO dev answerable question, then frozen.

  ... ablate_h4_offtopic.py                      dev numbers + the chosen THETA
  ... ablate_h4_offtopic.py --read-heldout --theta=X
        ALSO read test, test2 and data/eval/offtopic_h4.json, ONCE, with the
        frozen THETA, plus the 0-new-refusal sweep over every answerable set.

Pass --read-heldout once. Re-reading after seeing those numbers and moving
THETA is the protocol break the playbook's "Do not" line forbids.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import chat  # noqa: E402
import retrieve  # noqa: E402
from evalset import load_eval_set  # noqa: E402
from rag import build_corpus  # noqa: E402
from retrieve import ENGLISH_STOP_WORDS, expand_query, stem, stem_preprocess  # noqa: E402

EVAL = ROOT / "data" / "eval"
STOP = {stem(w) for w in ENGLISH_STOP_WORDS}


def corpus_vocab(version: str) -> set:
    """Unigram stems of every chunk, the same preprocessing retrieval uses."""
    docs = build_corpus(version, check_bridge=(version == "v2"))
    vocab = set()
    for chunks in docs.values():
        for c in chunks:
            vocab.update(stem_preprocess(c.text).split())
    return vocab - STOP


def content_tokens(q: str) -> list:
    return [t for t in re.findall(r"[a-z]+", q.lower())
            if len(t) > 2 and stem(t) not in STOP]


def coverage(q: str, vocab: set) -> tuple:
    """(share of content stems known to the corpus, [unknown words])."""
    toks = content_tokens(q)
    if not toks:
        return 1.0, []          # nothing to judge: never fire
    unknown = []
    for t in toks:
        if stem(t) in vocab:
            continue
        added = set(stem_preprocess(expand_query(t)).split()) - {stem(t)} - STOP
        if added & vocab:
            continue
        unknown.append(t)
    return 1 - len(unknown) / len(toks), unknown


def choose_theta(answerable_cov: list) -> float:
    """Largest THETA that fires on no dev answerable row (fire = cov < THETA)."""
    return min(answerable_cov)


def show(rows, vocab, theta=None, label=""):
    out = []
    for r in rows:
        cov, unk = coverage(r["text"], vocab)
        fired = theta is not None and cov < theta
        out.append((r, cov, fired))
        print("  %-7s %-14s cov=%.3f %s %s | %s" % (
            r["id"], r.get("class", "")[:14], cov, "FIRE" if fired else "    ",
            ",".join(unk)[:40], r["text"][:70]))
    return out


def main() -> int:
    read = "--read-heldout" in sys.argv
    th_arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--theta=")), None)
    if read and th_arg is None:
        print("--read-heldout needs --theta=<the frozen dev value>")
        return 2

    v2 = corpus_vocab("v2")
    print("v2 corpus vocabulary: %d stems" % len(v2))
    dev = load_eval_set("heldout")
    dev_off = [r for r in dev if r["class"] == "off-corpus"]
    dev_ans = [r for r in dev if r["class"] != "off-corpus"]
    print("\n== DEV answerable (%d) ==" % len(dev_ans))
    ans = show(dev_ans, v2)
    theta = choose_theta([c for _, c, _ in ans])
    print("\n== DEV off-corpus (%d), THETA chosen on dev = %.4f (fire if cov < THETA) =="
          % (len(dev_off), theta))
    off = show(dev_off, v2, theta)
    caught = sum(f for _, _, f in off)
    print("\nDEV GATE: caught %d/%d off-corpus (need >= 3), dev answerable fired 0/%d"
          % (caught, len(dev_off), len(dev_ans)))
    if not read:
        print("\n(stop here: held-out sets NOT read. Freeze THETA, then pass "
              "--read-heldout --theta=%.4f once, and only if the dev gate passed.)" % theta)
        return 0 if caught >= 3 else 1

    theta = float(th_arg)
    print("\n================ HELD-OUT READ (once), frozen THETA = %.4f ================" % theta)
    t1 = load_eval_set("test")
    t2 = load_eval_set("test2")
    h4 = json.loads((EVAL / "offtopic_h4.json").read_text(encoding="utf-8"))["questions"]
    results = {}
    for name, rows in [("test off-corpus", [r for r in t1 if r["class"] == "off-corpus"]),
                       ("test2 off-corpus", [r for r in t2 if r["class"] == "off-corpus"]),
                       ("H4 blind off-corpus", [r for r in h4 if r["class"] == "off-corpus"])]:
        print("\n== %s (%d) ==" % (name, len(rows)))
        o = show(rows, v2, theta)
        results[name] = (sum(f for _, _, f in o), len(rows))
    print("\n== H4 near-misses (reported; a FIRE here is a would-be false refusal) ==")
    nm = show([r for r in h4 if r["class"] == "near-miss"], v2, theta)

    # --- 0 new refusals: every answerable text the gate lists -----------------
    sweep = []
    for r in load_eval_set():
        if r["class"] != "off-corpus":
            sweep.append(("eval:%s:%s" % (r["set"], r["id"]), r["text"]))
    sweep += [("test2:%s" % r["id"], r["text"]) for r in t2 if r["class"] != "off-corpus"]
    reg = json.loads((EVAL / "register_probes.json").read_text(encoding="utf-8"))["probes"]
    sweep += [("register:%s" % p["id"], p["text"]) for p in reg]
    smk = json.loads((EVAL / "smoke_user_register.json").read_text(encoding="utf-8"))["queries"]
    sweep += [("smoke:%s" % s["id"], s["text"]) for s in smk]
    convs = json.loads((EVAL / "conversations.json").read_text(encoding="utf-8"))
    for c in convs:
        prior = []
        for i, t in enumerate(c["turns"]):
            sweep.append(("conv:%s.t%d:raw" % (c["id"], i + 1), t["text"]))
            q, _ = chat.contextualise(prior, t["text"])
            sweep.append(("conv:%s.t%d:ctx" % (c["id"], i + 1), q))
            prior.append({"question": t["text"]})
    syn = [("SYN:%s" % k, k) for k in sorted(retrieve.SYNONYMS)]
    v1 = corpus_vocab("v1")
    fired = []
    for label, text in sweep + syn:
        for ver, vocab in (("v2", v2), ("v1", v1)):
            cov, unk = coverage(text, vocab)
            if cov < theta:
                fired.append((ver, label, round(cov, 3), unk, text[:70]))
    n = (len(sweep) + len(syn)) * 2
    print("\n== 0-NEW-REFUSAL SWEEP: %d answerable texts x 2 corpus versions = %d checks =="
          % (len(sweep) + len(syn), n))
    for f in fired:
        print("  FIRED", f)
    print("  fired on %d answerable checks" % len(fired))

    print("\n================ H4 GATE ================")
    ok = True
    for name, (c, t) in results.items():
        p = c * 2 >= t
        ok &= p
        print("  %-22s caught %d/%d  (need >= half)  %s" % (name, c, t, "PASS" if p else "FAIL"))
    p = not fired
    ok &= p
    print("  0 new refusals          %s  (%d fired)" % ("PASS" if p else "FAIL", len(fired)))
    print("  near-misses fired       %d/%d (reported)" % (sum(f for _, _, f in nm), len(nm)))
    print("H4: %s" % ("PASS -- eligible to ship" if ok else "FAIL -- decline per playbook"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
