"""H8a.3 -- measure corpus v3 (v2 + Accessibility Regulations) against the shipping v2.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\eval_h8a3.py                 (dev stage)
     ... --read-blind=v3-12 | --read-blind=v3-16                          (ONCE, at the end)
     ... --self-test   (gates must fail on a v2-as-v3 stand-in; computes no v3 number)

Zero LLM, zero quota, zero network, writes nothing except the blind-read marker.
The ship gate below is copied from docs/phases/17_h8_corpus_expansion.md H8a.3 and
was committed in this file BEFORE any v3 number was seen.

ARMS (all k=4/doc, min_per_doc=1, MIN_SCORE unchanged)
  control  v2, top_n=12   -- the shipping system
  v3-12    v3, top_n=12   -- 16 candidates, so select_top cuts again (F1)
  v3-16    v3, top_n=16   -- top_n == 4k, no cut, display ceiling +1/3

SETS
  dev stage   frozen10, heldout (= dev), accessregs-dev, status. `test` is NEVER
              loaded (its cleanliness is an open owner decision, 2026-10-21).
  blind stage test2 (control + the chosen arm) and test3 (chosen arm only). Read
              once: the stage writes runs/h8a3/BLIND_READ and refuses to run again.

SHIP GATE -- all must hold for one v3 arm, else H8a is declined
  G1 no regression on existing law: recall_strict on frozen10, dev, test2 each
     >= control, AND no existing question loses an expected (doc, ref) pair that
     control covered (per question, not just the mean).
  G2 false refusals 0 on frozen10, dev, accessregs-dev, status, test2, test3
     (expect_gate=answer rows with zero hits >= MIN_SCORE).
  G3 new-doc reach: mean recall_strict over accessregs-dev >= 0.60 (all expected
     pairs of those rows, Act refs included); test3 reported once, not gated.
  G4 refusal calibration: select_top refusal invariance holds on every probe for
     the arm (0 disagreements); MIN_SCORE is still 0.10. Off-corpus answered
     count reported against control. Probe set differs from calibrate_refusal's
     106: the `test` rows are left out (not to be read) and the accessregs-dev +
     status rows are added -- recorded here as the reason the count moves.
  G5 status probes: every status row's expected pairs are all covered in the
     arm's shown hits; AR_S04 (no numbered ref) passes iff [Regs general] -- the
     enacting formula carrying the commencement date -- is shown.
  G6 if both v3 arms pass, prefer v3-12; v3-16 only if v3-12 fails G1.

Do not: read `test`; tune anything after the blind stage; change SYNONYMS.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import retrieve  # noqa: E402
from ablate_phase08 import OFF_CORPUS  # noqa: E402
from eval_heldout import K_PER_DOC, MIN_PER_DOC  # noqa: E402
from evalset import (load_accessregs_set, load_eval_set, ref_nums,  # noqa: E402
                     strict_covered, verify_expected)
from rag import build_corpus  # noqa: E402
from retrieve import PerDocRetriever, cite_tag, select_top  # noqa: E402

ARMS = {"control": ("v2", 12), "v3-12": ("v3", 12), "v3-16": ("v3", 16)}
V3_ARMS = ("v3-12", "v3-16")
REACH_MIN = 0.60
BLIND_MARK = ROOT / "runs" / "h8a3" / "BLIND_READ"


def shown(ret, text: str, top_n: int):
    """The shipping merge (ask() / offline_legal_hits) at the arm's top_n."""
    return select_top(ret.query(text, k=K_PER_DOC), top_n, min_per_doc=MIN_PER_DOC)


def measure(ret, row: dict, top_n: int) -> dict:
    hits = shown(ret, row["text"], top_n)
    exp = row["expected"]
    pairs = {(d, n) for d, ns in exp.items() for n in ns}
    covered = {(d, n) for d, n in pairs
               if any(h.doc_id == d and n in ref_nums(h.ref) for h in hits)}
    return {
        "id": row["id"],
        "strict": strict_covered(hits, exp) / len(pairs) if pairs else None,
        "covered": covered,
        "pairs": pairs,
        "n_kept": sum(1 for h in hits if h.score >= retrieve.MIN_SCORE),
        "tags": [cite_tag(h.doc_id, h.ref) for h in hits],
    }


def mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def run_sets(rets: dict, sets: dict, arms) -> dict:
    """{arm: {set: [measure...]}}"""
    return {a: {s: [measure(rets[ARMS[a][0]], r, ARMS[a][1]) for r in rows]
                for s, rows in sets.items()} for a in arms}


def false_refusals(ms: list) -> list:
    return [m["id"] for m in ms if m["n_kept"] == 0]


def losses(ctrl: list, arm: list) -> list:
    """(id, lost pairs) where the arm drops a pair control covered."""
    out = []
    for c, a in zip(ctrl, arm):
        assert c["id"] == a["id"]
        lost = c["covered"] - a["covered"]
        if lost:
            out.append((c["id"], sorted("%s:%d" % p for p in lost)))
    return out


def invariance(ret, top_n: int, probes: list) -> list:
    """calibrate_refusal gate 1, at this arm: shown clears <=> global max clears."""
    bad = []
    for label, text in probes:
        raw = ret.query(text, k=K_PER_DOC)
        lhs = any(h.score >= retrieve.MIN_SCORE
                  for h in select_top(raw, top_n, MIN_PER_DOC))
        rhs = bool(raw) and raw[0].score >= retrieve.MIN_SCORE
        if lhs != rhs:
            bad.append(label)
    return bad


def fmt(v):
    return "  n/a" if v is None else "%.3f" % v


def dev_stage(rets: dict, verbose: bool = True, self_test: bool = False) -> dict:
    """Returns {arm: [failure strings]} for the dev-stage gates (G1 part, G2-G5)."""
    existing = [r for r in load_eval_set() if r["set"] in ("frozen10", "heldout")]
    assert not any(r["set"] == "test" for r in existing)
    sets = {
        "frozen10": [r for r in existing if r["set"] == "frozen10"],
        "dev": [r for r in existing if r["set"] == "heldout"],
        "accessregs-dev": load_accessregs_set("accessregs-dev"),
        "status": load_accessregs_set("status"),
    }
    if not self_test:
        for s in ("accessregs-dev", "status"):
            verify_expected(sets[s], rets["v3"].docs)
    answerable = {s: [r for r in rows if r["expect_gate"] == "answer"]
                  for s, rows in sets.items()}
    res = run_sets(rets, answerable, ARMS)
    off_rows = [r for r in existing if r["expect_gate"] == "refuse"]
    off_probes = ([(r["id"], r["text"]) for r in off_rows]
                  + [("OFF%02d" % (i + 1), q) for i, q in enumerate(OFF_CORPUS)])
    probes = ([(r["id"], r["text"]) for rows in sets.values() for r in rows]
              + off_probes[len(off_rows):]
              + [("SYN:%s" % k, k) for k in sorted(retrieve.SYNONYMS)])

    if verbose:
        print("== H8a.3 DEV STAGE (k=%d/doc, min_per_doc=%d, MIN_SCORE=%.2f) =="
              % (K_PER_DOC, MIN_PER_DOC, retrieve.MIN_SCORE))
        print("   %-16s %8s %8s %8s" % ("recall_strict", *ARMS))
        for s in answerable:
            print("   %-16s %8s %8s %8s" % (s, *(fmt(mean(m["strict"] for m in res[a][s]))
                                                 for a in ARMS)))

    fails = {a: [] for a in V3_ARMS}
    assert abs(retrieve.MIN_SCORE - 0.10) < 1e-12, "MIN_SCORE moved"
    for a in V3_ARMS:
        f = fails[a]
        for s in ("frozen10", "dev"):
            mc = mean(m["strict"] for m in res["control"][s])
            ma = mean(m["strict"] for m in res[a][s])
            if ma is None or mc is None or ma < mc - 1e-12:
                f.append("G1 %s mean %.3f < control %.3f" % (s, ma, mc))
            for qid, lost in losses(res["control"][s], res[a][s]):
                f.append("G1 %s %s loses %s" % (s, qid, ", ".join(lost)))
        for s in answerable:
            fr = false_refusals(res[a][s])
            if fr:
                f.append("G2 %s false refusals: %s" % (s, fr))
        reach = mean(m["strict"] for m in res[a]["accessregs-dev"])
        if reach is None or reach < REACH_MIN:
            f.append("G3 accessregs-dev recall_strict %s < %.2f" % (fmt(reach), REACH_MIN))
        bad = invariance(rets["v3"], ARMS[a][1], probes)
        if bad:
            f.append("G4 refusal invariance disagreements: %s" % bad)
        for m in res[a]["status"]:
            if m["pairs"]:
                if m["covered"] != m["pairs"]:
                    f.append("G5 %s misses %s" % (m["id"], sorted(
                        "%s:%d" % p for p in m["pairs"] - m["covered"])))
            elif "[Regs general]" not in m["tags"]:
                f.append("G5 %s: [Regs general] not shown" % m["id"])

    if verbose:
        print("\n   probes for G4: %d (frozen10+dev+accessregs-dev+status rows, %d "
              "OFF_CORPUS, %d SYNONYMS keys; `test` rows left out)"
              % (len(probes), len(OFF_CORPUS), len(retrieve.SYNONYMS)))
        print("   off-corpus answered (of %d):" % len(off_probes), "  ".join(
            "%s %d" % (a, sum(1 for _, t in off_probes
                              if any(h.score >= retrieve.MIN_SCORE
                                     for h in shown(rets[ARMS[a][0]], t, ARMS[a][1]))))
            for a in ARMS))
        print("\n== PER QUESTION, existing law (control -> arm; lost/gained pairs) ==")
        for s in ("frozen10", "dev"):
            for i, c in enumerate(res["control"][s]):
                cells = []
                for a in V3_ARMS:
                    m = res[a][s][i]
                    lost = c["covered"] - m["covered"]
                    gained = m["covered"] - c["covered"]
                    cells.append("%s %s->%s%s%s%s" % (
                        a, fmt(c["strict"]), fmt(m["strict"]),
                        " LOST " + ",".join("%s:%d" % p for p in sorted(lost)) if lost else "",
                        " +" + ",".join("%s:%d" % p for p in sorted(gained)) if gained else "",
                        " [Regs general]" if "[Regs general]" in m["tags"] else ""))
                print("   %-8s %s" % (c["id"], " | ".join(cells)))
        print("\n== PER QUESTION, accessregs-dev + status (dev sets: shown) ==")
        for s in ("accessregs-dev", "status"):
            for i, c in enumerate(res["control"][s]):
                print("   %-7s %s" % (c["id"], " | ".join(
                    "%s %s miss=%s" % (a, fmt(res[a][s][i]["strict"]), sorted(
                        "%s:%d" % p for p in res[a][s][i]["pairs"] - res[a][s][i]["covered"]))
                    for a in V3_ARMS)))
        print("\n== DEV-STAGE GATES ==")
        for a in V3_ARMS:
            print("   %s: %s" % (a, "PASS" if not fails[a] else "FAIL"))
            for x in fails[a]:
                print("      - %s" % x)
    return fails


def choose(fails: dict) -> str | None:
    """G6: prefer v3-12; v3-16 only if v3-12 fails G1."""
    if not fails["v3-12"]:
        return "v3-12"
    if not fails["v3-16"] and any(x.startswith("G1") for x in fails["v3-12"]):
        return "v3-16"
    return None


def blind_stage(rets: dict, arm: str) -> int:
    if BLIND_MARK.exists():
        print("REFUSED: the blind sets were already read (%s):\n%s"
              % (BLIND_MARK, BLIND_MARK.read_text(encoding="utf-8")))
        return 2
    fails = dev_stage(rets, verbose=False)
    if fails[arm] or choose(fails) != arm:
        print("REFUSED: %s is not the G6 choice at the dev stage (choice: %s)"
              % (arm, choose(fails)))
        return 2
    BLIND_MARK.parent.mkdir(parents=True, exist_ok=True)
    BLIND_MARK.write_text("read for arm %s\n" % arm, encoding="utf-8")
    t2 = [r for r in load_eval_set("test2") if r["expect_gate"] == "answer"]
    t3 = load_accessregs_set("test3")
    res = run_sets(rets, {"test2": t2}, ("control", arm))
    r3 = run_sets(rets, {"test3": t3}, (arm,))[arm]["test3"]
    out = []
    mc = mean(m["strict"] for m in res["control"]["test2"])
    ma = mean(m["strict"] for m in res[arm]["test2"])
    if ma is None or mc is None or ma < mc - 1e-12:
        out.append("G1 test2 mean %.3f < control %.3f" % (ma, mc))
    for qid, lost in losses(res["control"]["test2"], res[arm]["test2"]):
        out.append("G1 test2 %s loses %s" % (qid, ", ".join(lost)))
    for s, ms in (("test2", res[arm]["test2"]), ("test3", r3)):
        fr = false_refusals(ms)
        if fr:
            out.append("G2 %s false refusals: %s" % (s, fr))
    print("== H8a.3 BLIND STAGE, arm %s (read once) ==" % arm)
    print("   test2 recall_strict  control %s  %s %s" % (fmt(mc), arm, fmt(ma)))
    print("   test3 recall_strict  %s %s   (G3: reported, not gated)"
          % (arm, fmt(mean(m["strict"] for m in r3))))
    print("   VERDICT %s: %s" % (arm, "SHIP GATE MET" if not out else "DECLINED"))
    for x in out:
        print("      - %s" % x)
    return 0 if not out else 1


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--self-test"]:
        # Gates must be able to FAIL. v2 stands in for v3, so no v3 number is
        # computed: G1 must pass (arm == control at top_n=12), G3 and G5 must fail
        # (no Regs chunks exist), and the dev-stage choice must be None.
        ret = PerDocRetriever(build_corpus("v2"))
        fails = dev_stage({"v2": ret, "v3": ret}, verbose=False, self_test=True)
        ok = (not any(x.startswith("G1") for x in fails["v3-12"])
              and any(x.startswith("G3") for x in fails["v3-12"])
              and any(x.startswith("G5") for x in fails["v3-12"])
              and choose(fails) is None)
        print("SELF-TEST %s" % ("PASS" if ok else "FAIL"))
        for x in fails["v3-12"]:
            print("   v3-12(=v2) %s" % x)
        return 0 if ok else 1
    blind = next((a.split("=", 1)[1] for a in argv if a.startswith("--read-blind=")), None)
    unknown = [a for a in argv if not a.startswith("--read-blind=")]
    if unknown or (blind is not None and blind not in V3_ARMS):
        print("usage: eval_h8a3.py [--read-blind=v3-12|v3-16]")
        return 2
    rets = {}
    for v in ("v2", "v3"):
        docs = build_corpus(v)
        rets[v] = PerDocRetriever(docs)
    if blind:
        return blind_stage(rets, blind)
    fails = dev_stage(rets)
    print("\n   G6 choice for the blind stage: %s" % choose(fails))
    return 0 if choose(fails) else 1


if __name__ == "__main__":
    sys.exit(main())
