"""Phase E5 optional arm -- the `beg` -> `begging` surface-form gap. S vs S+F.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\ablate_surface.py     (frozen-10 + dev ONLY)

THE GAP (E4.0 point 3, E5 box after E5.3). The hand key `begging` is dead on the
query word `beg`: stem("begging") == "begg" and _surface_forms("beg") never
contains "begging" or "begg". The E4a bridge happens to map beg -> begging, so
the query reaches the corpus word, but the hand key's own terms (alms,
destitute) never fire.

ARM F (key-side only; stem() and the index are untouched, the bridge is
byte-identical): a single-word key also matches when its stem, with a trailing
doubled consonant collapsed, is among the query's surface forms
("begg" -> "beg"). Measured 2026-09-24: this changes the match form of exactly
ONE of the 34 keys (`begging`), and its reach over every eval set is 1 dev
question (H2) + 1 test2 question.

THE RULE, declared before this script was first run (2026-09-24):
  F ships only if, on dev (the selector), recall_strict is STRICTLY above S,
  with 0 questions down; frozen-10 unchanged; no false refusal or refuse-row
  flip; and a re-run calibrate_refusal shows 0 disagreements (count stays 212).
  A tie does NOT ship: the evidence would be one question, and ties favour less
  code (the E5.3 convention). test2 is NOT read -- the box says this arm is
  judged on dev, and test2 has already been spent once.
The harness prints the verdict mechanically; it does not change src/.

Arms are installed by monkeypatching retrieve.expand_query, exactly as
ablate_handmap.py does, so set recall and the page view see the same arm.
EXIT CODE: nonzero only if S fails to reproduce 0.734 / 0.613 or any arm shows
a false refusal or a refuse-row flip. The verdict is a finding.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import retrieve  # noqa: E402
from ablate_handmap import SHIP_STRICT, fmt, mean, shown_with  # noqa: E402
from ablate_oov_bridge import measure  # noqa: E402
from evalset import load_eval_set, verify_expected  # noqa: E402
from rag import build_corpus  # noqa: E402
from retrieve import PerDocRetriever  # noqa: E402

SETS = {"frozen10": "frozen-10 (tripwire)", "heldout": "dev (SELECTOR)"}
SHIP = retrieve.expand_query


def _dedouble(s: str) -> str:
    return s[:-1] if len(s) > 2 and s[-1] == s[-2] and s[-1] not in "aeiousl" else s


def hand_fixed(q: str) -> str:
    """expand_query_hand with the one key-side change described above."""
    forms = retrieve._surface_forms(q)
    low = " ".join(re.findall(r"[a-z]+", q.lower()))
    extra: list[str] = []
    for key, syns in retrieve._SYN_PHRASE.items():
        if key in low:
            extra.extend(syns)
    for key, syns in retrieve._SYN_WORD.items():
        st = retrieve.stem(key)
        if key in forms or st in forms or _dedouble(st) in forms:
            extra.extend(syns)
    if not extra:
        return q
    return q + " " + " ".join(dict.fromkeys(extra))


def ship_fixed(q: str) -> str:
    e = hand_fixed(q)
    have = set(e.lower().split())
    extra = [w for w in retrieve.oov_bridge_terms(q) if w not in have]
    return e + " " + " ".join(extra) if extra else e


ARMS = [("S", "S    ship", SHIP), ("F", "S+F  surface-form fix", ship_fixed)]


def main() -> int:
    rows = load_eval_set()
    docs = build_corpus("v2")
    verify_expected(rows, docs)
    ret = PerDocRetriever(docs)
    by_set = {s: [r for r in rows if r["set"] == s] for s in SETS}

    affected = [k for k in retrieve._SYN_WORD
                if _dedouble(retrieve.stem(k)) != retrieve.stem(k)]
    changed = [(s, r["id"], r["text"]) for s in SETS for r in by_set[s]
               if ship_fixed(r["text"]) != SHIP(r["text"])]
    print("== PHASE E5 SURFACE-FORM ARM (corpus=v2, k=4/doc top_n=12; test2 NOT read) ==")
    print("  keys whose match form changes: %s" % affected)
    print("  scored questions whose expansion changes: %d" % len(changed))
    for s, qid, q in changed:
        print("    %s %s %r\n      S  : %r\n      S+F: %r" % (s, qid, q, SHIP(q), ship_fixed(q)))

    res = {a: {s: measure(by_set[s], ret, ex) for s in SETS} for a, _, ex in ARMS}
    shown = {a: {s: shown_with(by_set[s], ret, ex) for s in SETS} for a, _, ex in ARMS}
    S, F = res["S"], res["F"]

    print("\n== RECALL_STRICT ==")
    for a, lab, _ in ARMS:
        print("  %-24s %s" % (lab, "  ".join("%s %s" % (SETS[s], fmt(res[a][s]["strict"]))
                                            for s in SETS)))
    moves = {}
    for s in SETS:
        up = sorted(q for q in S[s]["per_q"] if F[s]["per_q"][q] > S[s]["per_q"][q] + 1e-9)
        dn = sorted(q for q in S[s]["per_q"] if F[s]["per_q"][q] < S[s]["per_q"][q] - 1e-9)
        moves[s] = (up, dn)
        print("  %-24s %d up %s / %d down %s" % (SETS[s], len(up), up, len(dn), dn))
    for s, qid, _ in changed:
        print("  %s %s strict: S %.3f -> S+F %.3f" % (
            s, qid, S[s]["per_q"][qid], F[s]["per_q"][qid]))

    print("\n== USER-FACING VIEW (E5.1 columns) ==")
    print("  %-4s %-22s %-7s %-9s %-7s %-7s %s" % ("arm", "set", "hit@3", "strict@3", "MRR",
                                                  "shown", "min"))
    for a, _, _ in ARMS:
        for s in SETS:
            ans = [r for r in shown[a][s] if r["hit3"] is not None]
            print("  %-4s %-22s %-7s %-9s %-7s %-7s %d" % (
                a, SETS[s], fmt(mean(r["hit3"] for r in ans)),
                fmt(mean(r["strict3"] for r in ans)), fmt(mean(r["rr_shown"] for r in ans)),
                fmt(mean(r["n_shown"] for r in ans), "%.2f"), min(r["n_shown"] for r in ans)))

    print("\n== REFUSAL INVARIANCE ==")
    bad = []
    for s in SETS:
        flips = [q for q in S[s]["kept_refuse"]
                 if (S[s]["kept_refuse"][q] > 0) != (F[s]["kept_refuse"][q] > 0)]
        fr = F[s]["false_ref"]
        print("  F %-22s false refusals %d (S: %d) | refuse-row flips %d"
              % (SETS[s], len(fr), len(S[s]["false_ref"]), len(flips)))
        if fr or flips or S[s]["false_ref"]:
            bad.append(s)

    print("\n== CONTROL ==")
    ctl = []
    for s in SHIP_STRICT:
        ok = abs(S[s]["strict"] - SHIP_STRICT[s]) < 5e-4
        ctl += [] if ok else [s]
        print("  %-22s %s vs %.3f: %s" % (SETS[s], fmt(S[s]["strict"]), SHIP_STRICT[s],
                                          "PASS" if ok else "FAIL"))

    print("\n== VERDICT (rule declared in the docstring before the first run) ==")
    d_dev = F["heldout"]["strict"] - S["heldout"]["strict"]
    d_f10 = F["frozen10"]["strict"] - S["frozen10"]["strict"]
    ok = d_dev > 1e-9 and not moves["heldout"][1] and abs(d_f10) < 1e-9 and not bad
    print("  dev %+.3f (%d up / %d down), frozen-10 %+.3f -> %s" % (
        d_dev, len(moves["heldout"][0]), len(moves["heldout"][1]), d_f10,
        "F QUALIFIES (still needs calibrate_refusal 0/212 before it ships)" if ok
        else "F DOES NOT SHIP; S stays"))

    if ctl or bad:
        print("\nABLATE_SURFACE: FAIL (%s)" % ", ".join(ctl + bad))
        return 1
    print("\nABLATE_SURFACE: PASS (arms measured; the verdict is a finding)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
