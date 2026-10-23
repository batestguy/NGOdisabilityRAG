"""H8a-R -- the reopened v3 measurement (owner reopened H8a on 2026-10-23).

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\eval_h8aR.py               (dev stage)
     ... --self-test   (gates must fail on a v2-as-v3 stand-in; no v3 number)
     ... --read-blind=R-a | --read-blind=R-b                               (ONCE, at the end)

Zero LLM, zero quota, zero network; writes only the blind-read marker. The gate
below is copied from docs/phases/17_h8_corpus_expansion.md "H8a-R" and was
committed in this file BEFORE any number on accessregs-dev2 existed.

WHY A REOPENING, NOT A RE-RUN. H8a.3 declined both v3 arms (scripts/eval_h8a3.py,
scripts/h8a3_dev_stage_2026-10-23.txt). v3-16 held existing law exactly; it
failed reach (0.583 < 0.60) and status evidence (G5). A rank diagnostic on the
READ dev set split the misses into "just below the k=4 cut" (ranks 4-9) and
"vocabulary gap" (ranks 17-30). The reopening adds one lever for the first kind
(per-doc k for the 221-chunk Regulations index) and moves status facts to a
fixed note (rag.DOC_STATUS_NOTES). The vocabulary gap gets NO lever: that is
the E2/E3/F0 family, declined three times, and SYNONYMS stays frozen. Because
those ideas came from reading accessregs-dev, selection uses the FRESH
accessregs-dev2 (data/eval/questions_accessregs_dev2.json, committed a41606b
before any arm existed). accessregs-dev is reported, never gated.

ARMS (MIN_SCORE unchanged, min_per_doc=1)
  control  v2, k=4/doc, top_n=12                       -- shipping
  R-a      v3, k=4/doc, top_n=16                       -- 16 candidates, no cut
  R-b      v3, k=4/doc but accessregs2023 k=6, top_n=18 -- 18 candidates, no cut

SHIP GATE -- all must hold for one arm, else H8a stays declined
  G1  no regression on existing law: recall_strict on frozen10, dev, test2 each
      >= control, and no question loses a (doc, ref) pair control covered.
  G2  false refusals 0 on frozen10, dev, accessregs-dev, accessregs-dev2,
      status, test2, test3.
  G3  reach: mean recall_strict over accessregs-dev2 >= 0.60. accessregs-dev and
      test3 reported, not gated.
  G4  refusal invariance 0 disagreements on every probe for the arm; MIN_SCORE
      still 0.10. Off-corpus answered count reported against control.
  G5' status: (a) rag.DOC_STATUS_NOTES["accessregs2023"] states S.I. No. 51 of
      2023, section 56, 22 May 2023, N 500,000 and N 2,000,000; (b) every tag
      in it matches rag.CITE_TAG_RE and names a ref that exists in corpus v3;
      (c) every status probe is answered (no refusal). Status-probe recall is
      REPORTED, no longer gated -- this is the deliberate change from H8a.3 G5,
      made before any reopened number, because the note now carries the facts.
  G6  prefer R-a (smaller display). R-b only if R-a fails G3 and R-b passes all.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import rag  # noqa: E402
import retrieve  # noqa: E402
from ablate_phase08 import OFF_CORPUS  # noqa: E402
from eval_h8a3 import false_refusals, fmt, losses, mean  # noqa: E402
from eval_heldout import MIN_PER_DOC  # noqa: E402
from evalset import (load_accessregs_set, load_eval_set, ref_nums,  # noqa: E402
                     strict_covered, verify_expected)
from rag import build_corpus  # noqa: E402
from retrieve import PerDocRetriever, cite_tag, select_top  # noqa: E402

ARMS = {
    "control": ("v2", 4, None, 12),
    "R-a": ("v3", 4, None, 16),
    "R-b": ("v3", 4, {"accessregs2023": 6}, 18),
}
CAND = ("R-a", "R-b")
REACH_MIN = 0.60
NOTE_FACTS = ("S.I. No. 51 of 2023", "section 56", "22 May 2023",
              "N 500,000", "N 2,000,000")
BLIND_MARK = ROOT / "runs" / "h8a3" / "BLIND_READ"


def shown(rets, arm, text):
    v, k, kbd, top_n = ARMS[arm]
    return select_top(rets[v].query(text, k=k, k_by_doc=kbd), top_n,
                      min_per_doc=MIN_PER_DOC)


def measure(rets, arm, row):
    hits = shown(rets, arm, row["text"])
    exp = row["expected"]
    pairs = {(d, n) for d, ns in exp.items() for n in ns}
    return {
        "id": row["id"],
        "strict": strict_covered(hits, exp) / len(pairs) if pairs else None,
        "covered": {(d, n) for d, n in pairs
                    if any(h.doc_id == d and n in ref_nums(h.ref) for h in hits)},
        "pairs": pairs,
        "n_kept": sum(1 for h in hits if h.score >= retrieve.MIN_SCORE),
        "tags": [cite_tag(h.doc_id, h.ref) for h in hits],
    }


def note_check(v3_docs) -> list:
    """G5'(a)+(b): the fixed note's facts and tags, checked against corpus v3."""
    out = []
    note = rag.DOC_STATUS_NOTES.get("accessregs2023", "")
    for fact in NOTE_FACTS:
        if fact not in note:
            out.append("G5' note lacks %r" % fact)
    refs = {(d, n) for d, cs in v3_docs.items() for c in cs for n in ref_nums(c.ref)}
    prefix = {"Act": "act2018", "Constitution": "constitution1999",
              "Factsheet": "factsheet2020", "Regs": "accessregs2023"}
    tags = re.findall(r"\[[^\]]+\]", note)
    if not tags:
        out.append("G5' note carries no tag")
    for t in tags:
        if not rag.CITE_TAG_RE.fullmatch(t):
            out.append("G5' note tag %s fails CITE_TAG_RE" % t)
            continue
        d = prefix[t[1:].split(" ", 1)[0]]
        for n in map(int, re.findall(r"\d+", t)):
            if (d, n) not in refs:
                out.append("G5' note tag %s: no %s ref %d in v3" % (t, d, n))
    return out


def dev_stage(rets, verbose=True, self_test=False):
    existing = [r for r in load_eval_set() if r["set"] in ("frozen10", "heldout")]
    assert not any(r["set"] == "test" for r in existing)
    sets = {
        "frozen10": [r for r in existing if r["set"] == "frozen10"],
        "dev": [r for r in existing if r["set"] == "heldout"],
        "accessregs-dev": load_accessregs_set("accessregs-dev"),
        "accessregs-dev2": load_accessregs_set("accessregs-dev2"),
        "status": load_accessregs_set("status"),
    }
    if not self_test:
        for s in ("accessregs-dev", "accessregs-dev2", "status"):
            verify_expected(sets[s], rets["v3"].docs)
    ans = {s: [r for r in rows if r["expect_gate"] == "answer"] for s, rows in sets.items()}
    res = {a: {s: [measure(rets, a, r) for r in rows] for s, rows in ans.items()}
           for a in ARMS}
    off_rows = [r for r in existing if r["expect_gate"] == "refuse"]
    off = ([(r["id"], r["text"]) for r in off_rows]
           + [("OFF%02d" % (i + 1), q) for i, q in enumerate(OFF_CORPUS)])
    probes = ([(r["id"], r["text"]) for rows in sets.values() for r in rows]
              + off[len(off_rows):]
              + [("SYN:%s" % k, k) for k in sorted(retrieve.SYNONYMS)])
    assert abs(retrieve.MIN_SCORE - 0.10) < 1e-12, "MIN_SCORE moved"
    note_fails = note_check(rets["v3"].docs)

    fails = {a: list(note_fails) for a in CAND}
    for a in CAND:
        f = fails[a]
        for s in ("frozen10", "dev"):
            mc = mean(m["strict"] for m in res["control"][s])
            ma = mean(m["strict"] for m in res[a][s])
            if ma is None or mc is None or ma < mc - 1e-12:
                f.append("G1 %s mean %s < control %s" % (s, fmt(ma), fmt(mc)))
            for qid, lost in losses(res["control"][s], res[a][s]):
                f.append("G1 %s %s loses %s" % (s, qid, ", ".join(lost)))
        for s in ans:
            fr = false_refusals(res[a][s])
            if fr:
                f.append("G2 %s false refusals: %s" % (s, fr))
        reach = mean(m["strict"] for m in res[a]["accessregs-dev2"])
        if reach is None or reach < REACH_MIN:
            f.append("G3 accessregs-dev2 recall_strict %s < %.2f" % (fmt(reach), REACH_MIN))
        v, k, kbd, top_n = ARMS[a]
        bad = []
        for lab, text in probes:
            raw = rets[v].query(text, k=k, k_by_doc=kbd)
            lhs = any(h.score >= retrieve.MIN_SCORE
                      for h in select_top(raw, top_n, MIN_PER_DOC))
            if lhs != (bool(raw) and raw[0].score >= retrieve.MIN_SCORE):
                bad.append(lab)
        if bad:
            f.append("G4 refusal invariance disagreements: %s" % bad)

    if verbose:
        print("== H8a-R DEV STAGE (MIN_SCORE=%.2f) ==" % retrieve.MIN_SCORE)
        print("   %-16s %8s %8s %8s" % ("recall_strict", *ARMS))
        for s in ans:
            print("   %-16s %8s %8s %8s" % (s, *(fmt(mean(m["strict"] for m in res[a][s]))
                                                 for a in ARMS)))
        print("   (accessregs-dev was read at H8a.3: reported, never gated; status recall reported)")
        print("\n   G4 probes: %d (frozen10, dev, accessregs-dev, -dev2, status rows + %d "
              "OFF_CORPUS + %d SYNONYMS keys; `test` left out)"
              % (len(probes), len(OFF_CORPUS), len(retrieve.SYNONYMS)))
        print("   off-corpus answered (of %d): %s" % (len(off), "  ".join(
            "%s %d" % (a, sum(1 for _, t in off if any(
                h.score >= retrieve.MIN_SCORE for h in shown(rets, a, t))))
            for a in ARMS)))
        print("   G5' note check: %s" % ("PASS" if not note_fails else note_fails))
        print("\n== PER QUESTION, existing law (only rows that move) ==")
        for s in ("frozen10", "dev"):
            for i, c in enumerate(res["control"][s]):
                cells = []
                for a in CAND:
                    m = res[a][s][i]
                    if m["covered"] != c["covered"] or m["strict"] != c["strict"]:
                        cells.append("%s %s->%s lost=%s" % (a, fmt(c["strict"]), fmt(m["strict"]),
                                     sorted("%s:%d" % p for p in c["covered"] - m["covered"])))
                if cells:
                    print("   %-6s %s" % (c["id"], " | ".join(cells)))
        print("\n== PER QUESTION, accessregs-dev2 / accessregs-dev / status ==")
        for s in ("accessregs-dev2", "accessregs-dev", "status"):
            for i, c in enumerate(res["control"][s]):
                print("   %-7s %s" % (c["id"], " | ".join(
                    "%s %s miss=%s" % (a, fmt(res[a][s][i]["strict"]), sorted(
                        "%s:%d" % p for p in res[a][s][i]["pairs"] - res[a][s][i]["covered"]))
                    for a in CAND)))
        print("\n== DEV-STAGE GATES ==")
        for a in CAND:
            print("   %s: %s" % (a, "PASS" if not fails[a] else "FAIL"))
            for x in fails[a]:
                print("      - %s" % x)
    return fails


def choose(fails):
    if not fails["R-a"]:
        return "R-a"
    g3_only = all(x.startswith("G3") for x in fails["R-a"])
    if not fails["R-b"] and g3_only:
        return "R-b"
    return None


def blind_stage(rets, arm):
    if BLIND_MARK.exists():
        print("REFUSED: blind sets already read:\n%s" % BLIND_MARK.read_text(encoding="utf-8"))
        return 2
    fails = dev_stage(rets, verbose=False)
    if choose(fails) != arm:
        print("REFUSED: %s is not the G6 choice at the dev stage (choice: %s)"
              % (arm, choose(fails)))
        return 2
    BLIND_MARK.parent.mkdir(parents=True, exist_ok=True)
    BLIND_MARK.write_text("read for H8a-R arm %s\n" % arm, encoding="utf-8")
    t2 = [r for r in load_eval_set("test2") if r["expect_gate"] == "answer"]
    t3 = load_accessregs_set("test3")
    c2 = [measure(rets, "control", r) for r in t2]
    a2 = [measure(rets, arm, r) for r in t2]
    a3 = [measure(rets, arm, r) for r in t3]
    out = []
    mc, ma = mean(m["strict"] for m in c2), mean(m["strict"] for m in a2)
    if ma is None or mc is None or ma < mc - 1e-12:
        out.append("G1 test2 mean %s < control %s" % (fmt(ma), fmt(mc)))
    for qid, lost in losses(c2, a2):
        out.append("G1 test2 %s loses %s" % (qid, ", ".join(lost)))
    for s, ms in (("test2", a2), ("test3", a3)):
        fr = false_refusals(ms)
        if fr:
            out.append("G2 %s false refusals: %s" % (s, fr))
    print("== H8a-R BLIND STAGE, arm %s (read once) ==" % arm)
    print("   test2 recall_strict  control %s  %s %s" % (fmt(mc), arm, fmt(ma)))
    print("   test3 recall_strict  %s %s   (reported, not gated)"
          % (arm, fmt(mean(m["strict"] for m in a3))))
    print("   VERDICT %s: %s" % (arm, "SHIP GATE MET" if not out else "DECLINED"))
    for x in out:
        print("      - %s" % x)
    return 0 if not out else 1


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--self-test"]:
        # v2 stands in for v3, so no v3 number exists: G1 must hold for R-a
        # (== control's retrieval at a wider ceiling over the same 12 candidates),
        # G3 must fail (no Regs chunks), G5' must fail (no Regs refs for the
        # note's tags), and nothing may be chosen.
        ret = PerDocRetriever(build_corpus("v2"))
        fails = dev_stage({"v2": ret, "v3": ret}, verbose=False, self_test=True)
        ok = (not any(x.startswith("G1") for x in fails["R-a"])
              and any(x.startswith("G3") for x in fails["R-a"])
              and any(x.startswith("G5'") for x in fails["R-a"])
              and choose(fails) is None)
        print("SELF-TEST %s" % ("PASS" if ok else "FAIL"))
        for x in fails["R-a"]:
            print("   R-a(=v2) %s" % x)
        return 0 if ok else 1
    blind = next((a.split("=", 1)[1] for a in argv if a.startswith("--read-blind=")), None)
    if [a for a in argv if not a.startswith("--read-blind=")] or (blind and blind not in CAND):
        print("usage: eval_h8aR.py [--self-test | --read-blind=R-a|R-b]")
        return 2
    rets = {v: PerDocRetriever(build_corpus(v)) for v in ("v2", "v3")}
    if blind:
        return blind_stage(rets, blind)
    fails = dev_stage(rets)
    print("\n   G6 choice for the blind stage: %s" % choose(fails))
    return 0 if choose(fails) else 1


if __name__ == "__main__":
    sys.exit(main())
