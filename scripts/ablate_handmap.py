"""Phase E5.3 -- is the hand-written SYNONYMS map worth having? S vs B vs N.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\ablate_handmap.py              (frozen-10 + dev)
     ... --read-test2    ALSO score `test2`. Pass it ONCE, after the dev numbers are
                         recorded -- it is the first read of the clean set.

ARMS (playbook E5 box, E5.3, fixed before test2 existed):
  S  ship         retrieve.expand_query        = hand map, then OOV bridge
  B  bridge only  expand_query_hand -> identity, bridge unchanged
  N  none         no expansion at all
B is the box's literal definition: the bridge still skips tokens a SYNONYMS key
owns (retrieve._HAND_KEYS). Deleting SYNONYMS would also empty that skip set, so
the harness reports B' (skip set emptied) as a CHECK: if B' expands any scored
question differently from B, the B column does not describe "ship less code" and
the difference is printed.

THE RULE, verbatim in substance from the box: ship less code (B or N) only if it
is >= S on dev AND >= S on test2 (recall_strict), with no more questions down
than up on test2. A tie favours less code. Otherwise S stays. The harness prints
the verdict mechanically; it does not ship anything.

Arms are installed by monkeypatching retrieve.expand_query, which
PerDocRetriever.query() resolves as a module global -- so both the set-recall
path (ablate_oov_bridge.measure) and the page path (eval_heldout.measure_shown,
through app.offline_legal_hits) see the same arm. src/ is not modified.

EXIT CODE. Nonzero only if arm S fails to reproduce the published shipping
numbers (0.734 / 0.613 on frozen-10 / dev) or any arm shows a false refusal or a
refuse-row flip. The verdict itself is a finding, not a pass/fail.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import retrieve  # noqa: E402
from ablate_oov_bridge import measure  # noqa: E402
from eval_heldout import measure_shown  # noqa: E402
from evalset import load_eval_set, verify_expected  # noqa: E402
from rag import build_corpus  # noqa: E402
from retrieve import PerDocRetriever  # noqa: E402

SHIP_STRICT = {"frozen10": 0.734, "heldout": 0.613}   # E4a shipping, published
LABELS = {"frozen10": "frozen-10 (tripwire)", "heldout": "dev (SELECTOR)",
          "test2": "test2 (check, read once)"}
ONE_Q = {"frozen10": 0.100, "heldout": 0.040, "test2": 1 / 42}

SHIP = retrieve.expand_query


def bridge_only(q: str) -> str:
    extra = [w for w in retrieve.oov_bridge_terms(q) if w not in set(q.lower().split())]
    return q + " " + " ".join(extra) if extra else q


def bridge_only_no_skip(q: str) -> str:
    saved = retrieve._HAND_KEYS
    retrieve._HAND_KEYS = set()
    try:
        return bridge_only(q)
    finally:
        retrieve._HAND_KEYS = saved


def identity(q: str) -> str:
    return q


ARMS = [("S", "S  ship (hand + bridge)", SHIP),
        ("B", "B  bridge only", bridge_only),
        ("N", "N  no expansion", identity)]


def shown_with(rows, ret, expander) -> list[dict]:
    installed = retrieve.expand_query
    retrieve.expand_query = expander
    try:
        return [measure_shown(ret, r) for r in rows]
    finally:
        retrieve.expand_query = installed


def mean(v):
    v = [x for x in v if x is not None]
    return sum(v) / len(v) if v else None


def fmt(v, spec="%.3f"):
    return "n/a" if v is None else spec % v


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    read_t2 = "--read-test2" in argv
    sets = [s for s in LABELS if read_t2 or s != "test2"]

    rows = load_eval_set() + (load_eval_set("test2") if read_t2 else [])
    docs = build_corpus("v2")
    verify_expected(rows, docs)
    ret = PerDocRetriever(docs)
    by_set = {s: [r for r in rows if r["set"] == s] for s in sets}

    res = {a: {s: measure(by_set[s], ret, ex) for s in sets} for a, _, ex in ARMS}
    shown = {a: {s: shown_with(by_set[s], ret, ex) for s in sets} for a, _, ex in ARMS}
    S = res["S"]

    print("== PHASE E5.3 HAND-MAP ABLATION (corpus=v2, k=4/doc top_n=12) ==")
    print("  sets scored: %s%s" % (", ".join(sets), "" if read_t2 else
          "   (test2 NOT scored -- pass --read-test2 once, after dev is recorded)"))

    scored = [r["text"] for s in sets for r in by_set[s]]
    diff = [q for q in scored if bridge_only(q) != bridge_only_no_skip(q)]
    print("\n== CHECK: B (bridge skips hand keys) vs B' (skip set emptied) ==")
    print("  %d / %d scored questions expand differently" % (len(diff), len(scored)))
    for q in diff if "test2" not in sets else diff[:0]:
        print("    %r\n      B : %r\n      B': %r" % (q, bridge_only(q), bridge_only_no_skip(q)))
    if diff and "test2" in sets:
        print("  (texts withheld: the list includes test2 rows)")

    print("\n== RECALL_STRICT ==")
    print("  %-26s %s" % ("arm", " ".join("%-26s" % LABELS[s] for s in sets)))
    for a, lab, _ in ARMS:
        print("  %-26s %s" % (lab, " ".join("%-26s" % fmt(res[a][s]["strict"]) for s in sets)))
    for a in ("B", "N"):
        print("  %-26s %s" % ("delta %s - S" % a, " ".join(
            "%-26s" % ("%+.3f" % (res[a][s]["strict"] - S[s]["strict"])) for s in sets)))
    print("  one question = %s" % " / ".join("%.3f %s" % (ONE_Q[s], s) for s in sets))

    print("\n== VOCAB-MISMATCH (strict) ==")
    for a, lab, _ in ARMS:
        print("  %-26s %s" % (lab, " ".join(
            "%-26s" % fmt(res[a][s]["by_class"].get("vocab-mismatch")) for s in sets)))

    print("\n== PER-QUESTION MOVEMENT vs S (strict) ==")
    moves = {}
    for a in ("B", "N"):
        for s in sets:
            up = sorted(q for q in S[s]["per_q"] if res[a][s]["per_q"][q] > S[s]["per_q"][q] + 1e-9)
            dn = sorted(q for q in S[s]["per_q"] if res[a][s]["per_q"][q] < S[s]["per_q"][q] - 1e-9)
            moves[(a, s)] = (len(up), len(dn))
            show = s != "test2"
            print("  %s %-26s %d up %s / %d down %s of %d" % (
                a, LABELS[s], len(up), up if show else "", len(dn), dn if show else "",
                len(S[s]["per_q"])))

    print("\n== USER-FACING VIEW per arm (E5.1 columns, through app.offline_legal_hits) ==")
    print("  %-4s %-26s %-7s %-9s %-7s %-7s %-4s %s" % (
        "arm", "set", "hit@3", "strict@3", "MRR", "shown", "min", "rows<=2"))
    for a, _, _ in ARMS:
        for s in sets:
            ans = [r for r in shown[a][s] if r["hit3"] is not None]
            for lab, sub in ((LABELS[s], ans), ("  vocab-mismatch",
                             [r for r in ans if r["class"] == "vocab-mismatch"])):
                if not sub:
                    continue
                print("  %-4s %-26s %-7s %-9s %-7s %-7s %-4d %d/%d" % (
                    a, lab, fmt(mean(r["hit3"] for r in sub)),
                    fmt(mean(r["strict3"] for r in sub)),
                    fmt(mean(r["rr_shown"] for r in sub)),
                    fmt(mean(r["n_shown"] for r in sub), "%.2f"),
                    min(r["n_shown"] for r in sub),
                    sum(1 for r in sub if r["n_shown"] <= 2), len(sub)))

    print("\n== REFUSAL INVARIANCE (the two-sided gate forbids any change) ==")
    bad = []
    for s in sets:
        for a in ("B", "N"):
            flips = [q for q in S[s]["kept_refuse"]
                     if (S[s]["kept_refuse"][q] > 0) != (res[a][s]["kept_refuse"][q] > 0)]
            fr = res[a][s]["false_ref"]
            print("  %s %-26s false refusals %d (S: %d) | refuse-row flips %d"
                  % (a, LABELS[s], len(fr), len(S[s]["false_ref"]), len(flips)))
            if fr or flips or S[s]["false_ref"]:
                bad.append("%s/%s" % (a, s))

    print("\n== CONTROL: arm S must reproduce the published shipping numbers ==")
    ctl = []
    for s in SHIP_STRICT:
        ok = abs(S[s]["strict"] - SHIP_STRICT[s]) < 5e-4
        ctl += [] if ok else [s]
        print("  %-26s %s vs %.3f: %s" % (LABELS[s], fmt(S[s]["strict"]), SHIP_STRICT[s],
                                          "PASS" if ok else "FAIL"))

    print("\n== VERDICT under the E5.3 rule (declared before test2 existed) ==")
    if "test2" not in sets:
        for a in ("B", "N"):
            d = res[a]["heldout"]["strict"] - S["heldout"]["strict"]
            print("  %s on dev: %+.3f -> %s" % (a, d, "clears the dev half" if d >= -1e-9
                                                  else "FAILS the dev half: S stays vs %s" % a))
        print("  test2 half not evaluated (not read).")
    else:
        winners = []
        for a in ("B", "N"):
            d_dev = res[a]["heldout"]["strict"] - S["heldout"]["strict"]
            d_t2 = res[a]["test2"]["strict"] - S["test2"]["strict"]
            up, dn = moves[(a, "test2")]
            ok = d_dev >= -1e-9 and d_t2 >= -1e-9 and dn <= up
            print("  %s: dev %+.3f, test2 %+.3f, test2 %d up / %d down -> %s"
                  % (a, d_dev, d_t2, up, dn, "QUALIFIES" if ok else "does not qualify"))
            if ok:
                winners.append(a)
        if not winners:
            print("  => S STAYS, now with held-out evidence.")
        else:
            # Tie favours less code: N is less code than B.
            pick = "N" if "N" in winners else "B"
            print("  => %s qualifies; ship-less-code candidate is %s. It needs a re-derived"
                  " calibrate_refusal before it can ship." % (", ".join(winners), pick))

    if ctl or bad:
        print("\nABLATE_HANDMAP: FAIL (%s)" % ", ".join(ctl + bad))
        return 1
    print("\nABLATE_HANDMAP: PASS (arms measured; the verdict is a finding)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
