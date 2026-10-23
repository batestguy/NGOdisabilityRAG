"""Phase E4a ablation -- hand map (control = E1b) vs hand map + OOV bridge.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\ablate_oov_bridge.py            (frozen-10 + dev)
     ... --read-test     ALSO score `test`. Pass it ONCE, only after the dev gate
                         (playbook E4 re-scope box, point 6, lines 1-4) has passed.
     ... --bridge=<path> alternative artifact (the one allowed dev-only retreat)

SHIPPED 2026-09-23 (phase10/ship-e4a). This harness MEASURED E4a with src/
untouched; the arm is now the shipping expander. Two things changed with the port:
  * arm A is retrieve.expand_query_hand -- the hand map alone, i.e. E1b's expander;
  * PORT CHECK: before measuring, the harness asserts that the shipping
    retrieve.expand_query equals this file's measured bridge_expand on every eval
    question and every off-corpus probe. If that fails the port is not the measured
    arm and no number below means anything.
Arms are installed by monkeypatching retrieve.expand_query (PerDocRetriever.query()
resolves it as a module global). SYNONYMS and the two-sided gate are untouched, so
calibrate_refusal.py stays at 106 probes / 212 runs.

THE ARM. bridge_expand(q) = expand_query(q) plus, for each query token that is out
of the corpus AND not already bridged by a SYNONYMS key, its bridge neighbours --
at most MAX_BRIDGE_TERMS appended in total (E3a's lesson: the auto map failed at a
median of 8 appended terms). The bridge is last and additive: it never removes or
reorders a hand-map term.

REFUSALS. The two-sided gate in PerDocRetriever.query() scores the ORIGINAL query
first and discards any expansion that cannot clear MIN_SCORE, so no expander can
change a refusal decision in either direction. The false-refusal and refuse-row
columns below are a confirmation of that property, not a live risk.

EXIT CODE. Measures, does not gate. Nonzero only if the control arm fails to
reproduce E1b, the artifact's corpus digest does not match the corpus, or any arm
shows a false refusal / a refuse-row flip (the gate forbids both).
"""

import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import retrieve  # noqa: E402
from ablate_phase08 import OFF_CORPUS  # noqa: E402
from build_oov_bridge import OUT as BRIDGE_PATH  # noqa: E402
from evalset import load_eval_set, strict_covered, verify_expected  # noqa: E402
from rag import build_corpus  # noqa: E402
from retrieve import (MIN_SCORE, SYNONYMS, PerDocRetriever, corpus_sha256,  # noqa: E402
                      select_top, stem)

# H8a.5 (2026-10-23): a v2-ONLY measurement harness. main() builds
# build_corpus("v2") explicitly and TOP_N=12 is v2's budget; the shipping corpus
# is now v3 (top_n=16), which this file deliberately does not measure -- its arms
# monkeypatch the one-argument expand_query that v3's retriever does not call.
K_PER_DOC, TOP_N, MIN_PER_DOC = 4, 12, 1          # E1b (v2) budget, held fixed
MAX_BRIDGE_TERMS = 4                              # playbook point 4, fixed a priori
CONTROL_STRICT = {"frozen10": 0.734, "heldout": 0.573, "test": 0.529}
LABELS = {"frozen10": "frozen-10 (tripwire)", "heldout": "dev (SELECTOR)",
          "test": "test (check, read once)"}

HAND = retrieve.expand_query_hand
_HAND_KEYS = set(SYNONYMS) | {stem(k) for k in SYNONYMS}


def load_bridge(path: Path = BRIDGE_PATH, docs=None) -> dict[str, list[str]]:
    """The bridge dict. Hard-fails if built against a different corpus."""
    blob = json.loads(Path(path).read_text(encoding="utf-8"))
    if docs is not None and blob["_meta"]["corpus_sha256"] != corpus_sha256(docs):
        raise SystemExit("oov_bridge.json was built against a different corpus -- "
                         "rebuild it with scripts/build_oov_bridge.py")
    return blob["bridge"]


def make_bridge_expand(bridge: dict[str, list[str]]):
    def bridge_terms(q: str) -> list[str]:
        out: list[str] = []
        for t in re.findall(r"[a-z]+", q.lower()):
            if {t, stem(t), t[:-1]} & _HAND_KEYS:
                continue                  # the hand map owns this word
            nb = bridge.get(t) or (bridge.get(t[:-1]) if t.endswith("s") else None)
            for w in nb or ():
                if w not in out:
                    out.append(w)
        return out[:MAX_BRIDGE_TERMS]

    def bridge_expand(q: str) -> str:
        e = HAND(q)
        have = set(e.lower().split())
        extra = [w for w in bridge_terms(q) if w not in have]
        return e + " " + " ".join(extra) if extra else e

    return bridge_expand, bridge_terms


def effective_query(ret, q, expander) -> str:
    """The string PerDocRetriever.query() actually scores, after both gates."""
    base = ret._merged(q, K_PER_DOC)
    if not base or base[0].score < MIN_SCORE:
        return q
    exp = expander(q)
    if exp == q:
        return q
    hits = ret._merged(exp, K_PER_DOC)
    return q if not hits or hits[0].score < MIN_SCORE else exp


def measure(rows, ret, expander) -> dict:
    per_q, by_class, sigs, tops = {}, {}, [], []
    false_ref, kept_refuse, fired, appended = [], {}, 0, []
    installed = retrieve.expand_query
    retrieve.expand_query = expander
    try:
        for row in rows:
            q = row["text"]
            eff = effective_query(ret, q, expander)
            if eff != q:
                fired += 1
                appended.append(len(eff.split()) - len(q.split()))
            hits = select_top(ret.query(q, k=K_PER_DOC), TOP_N, min_per_doc=MIN_PER_DOC)
            tops.append(max((h.score for h in hits), default=0.0))
            sigs.append(frozenset((h.doc_id, h.ref, h.text) for h in hits))
            kept = [h for h in hits if h.score >= MIN_SCORE]
            if row["expect_gate"] == "refuse":
                kept_refuse[row["id"]] = len(kept)
            elif not kept:
                false_ref.append(row["id"])
            exp = row["expected"]
            if not exp:
                continue
            n = sum(len(v) for v in exp.values())
            per_q[row["id"]] = strict_covered(hits, exp) / n
            by_class.setdefault(row["class"], []).append(per_q[row["id"]])
    finally:
        retrieve.expand_query = installed
    vals = list(per_q.values())
    return {"per_q": per_q, "strict": sum(vals) / len(vals) if vals else None,
            "by_class": {c: sum(v) / len(v) for c, v in by_class.items()},
            "class_n": {c: len(v) for c, v in by_class.items()},
            "sigs": sigs, "tops": tops, "false_ref": false_ref,
            "kept_refuse": kept_refuse, "fired": fired, "n": len(rows),
            "app_med": statistics.median(appended) if appended else 0,
            "app_max": max(appended) if appended else 0}


def fmt(v) -> str:
    return "n/a" if v is None else "%.3f" % v


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    read_test = "--read-test" in argv
    bpath = next((Path(a.split("=", 1)[1]) for a in argv if a.startswith("--bridge=")),
                 BRIDGE_PATH)
    sets = [s for s in LABELS if read_test or s != "test"]

    rows = load_eval_set()
    docs = build_corpus("v2")
    verify_expected(rows, docs)
    ret = PerDocRetriever(docs)
    bridge = load_bridge(bpath, docs)
    bx, bterms = make_bridge_expand(bridge)
    arms = [("A  hand map (control = E1b)", HAND), ("E  hand + OOV bridge", bx)]
    probes = [r["text"] for r in rows] + [p for p in OFF_CORPUS]
    probes = [p if isinstance(p, str) else p[-1] for p in probes]
    port_bad = [p for p in probes if retrieve.expand_query(p) != bx(p)]
    by_set = {s: [r for r in rows if r["set"] == s] for s in sets}
    res = {lab: {s: measure(by_set[s], ret, ex) for s in sets} for lab, ex in arms}
    A, E = (res[lab] for lab, _ in arms)

    print("== PHASE E4a OOV BRIDGE ABLATION (corpus=v2, MIN_SCORE=%.2f) ==" % MIN_SCORE)
    print("  artifact %s: %d keys; budget k=%d/doc top_n=%d; <= %d bridge terms/query"
          % (bpath.name, len(bridge), K_PER_DOC, TOP_N, MAX_BRIDGE_TERMS))
    print("  sets scored: %s%s" % (", ".join(sets),
          "" if read_test else "   (test NOT scored -- pass --read-test once)"))

    print("\n== RECALL_STRICT ==")
    print("  %-30s %s" % ("arm", " ".join("%-24s" % LABELS[s] for s in sets)))
    for lab, _ in arms:
        print("  %-30s %s" % (lab, " ".join("%-24s" % fmt(res[lab][s]["strict"]) for s in sets)))
    print("  %-30s %s" % ("delta E - A", " ".join(
        "%-24s" % ("%+.3f" % (E[s]["strict"] - A[s]["strict"])) for s in sets)))
    print("  one question = 0.100 frozen-10 / 0.040 dev / 0.059 test")

    print("\n== VOCAB-MISMATCH PER SET (strict) ==")
    for lab, _ in arms:
        print("  %-30s %s" % (lab, " ".join(
            "%-24s" % fmt(res[lab][s]["by_class"].get("vocab-mismatch")) for s in sets)))

    print("\n== PER-QUESTION MOVEMENT E vs A (strict) ==")
    for s in sets:
        up = sorted(q for q in A[s]["per_q"] if E[s]["per_q"][q] > A[s]["per_q"][q] + 1e-9)
        dn = sorted(q for q in A[s]["per_q"] if E[s]["per_q"][q] < A[s]["per_q"][q] - 1e-9)
        show = s != "test"
        print("  %-24s %d up %s / %d down %s of %d" % (
            LABELS[s], len(up), up if show else "", len(dn), dn if show else "",
            len(A[s]["per_q"])))

    print("\n== DID THE BRIDGE FIRE? (post-gate) ==")
    for lab, _ in arms:
        print("  %-30s applied %s | appended med %s max %s | displayed set changed %d/%d"
              % (lab, "/".join("%d" % res[lab][s]["fired"] for s in sets),
                 max(res[lab][s]["app_med"] for s in sets),
                 max(res[lab][s]["app_max"] for s in sets),
                 sum(1 for s in sets for x, y in zip(res[lab][s]["sigs"], A[s]["sigs"]) if x != y),
                 sum(res[lab][s]["n"] for s in sets)))
    bridged = [(r["id"], bterms(r["text"])) for s in sets if s != "test"
               for r in by_set[s] if bterms(r["text"])]
    print("  bridge terms offered (pre-gate), frozen-10 + dev:")
    for qid, t in bridged:
        print("    %-5s %s" % (qid, t))

    print("\n== REFUSAL INVARIANCE (confirmation -- the gate forbids any change) ==")
    bad = []
    for s in sets:
        fr = E[s]["false_ref"] + A[s]["false_ref"]
        flips = [q for q in A[s]["kept_refuse"]
                 if (A[s]["kept_refuse"][q] > 0) != (E[s]["kept_refuse"][q] > 0)]
        print("  %-24s false refusals A=%d E=%d | refuse-row kept>0 flips: %d"
              % (LABELS[s], len(A[s]["false_ref"]), len(E[s]["false_ref"]), len(flips)))
        if fr or flips:
            bad.append(s)

    print("\n== PORT CHECK: shipping retrieve.expand_query == measured bridge_expand ==")
    print("  %d / %d probes identical%s" % (len(probes) - len(port_bad), len(probes),
          "" if not port_bad else "  !! first mismatch: %r" % port_bad[0]))
    bad += ["port"] if port_bad else []

    ctl = [s for s in sets if abs(A[s]["strict"] - CONTROL_STRICT[s]) >= 5e-4]
    print("\n== CONTROL: arm A must reproduce E1b ==")
    for s in sets:
        print("  %-24s %s vs %.3f: %s" % (LABELS[s], fmt(A[s]["strict"]), CONTROL_STRICT[s],
                                          "FAIL" if s in ctl else "PASS"))
    if ctl or bad:
        print("\nABLATE_OOV_BRIDGE: FAIL (%s)" % ", ".join(ctl + bad))
        return 1
    print("\nABLATE_OOV_BRIDGE: PASS (arms measured; recall numbers are findings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
