"""Phase F0 -- offline static-embedding arm: reach, then S vs D. Measure-only.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\ablate_static.py               (frozen-10 + dev + probes)
     ... --model=<dir>   static model dir (default D:\\NGORAG\\runs\\f0_static\\potion-base-8M)
     ... --read-test2    ALSO score test2. Refused unless the dev gate PASSES (playbook F0:
                         "if dev fails, decline without reading test2"). Pass it once.

ARMS (docs/phases/15_phase_f_reexamined.md, F0 + its pre-measurement amendment):
  S  ship    PerDocRetriever.query(q, k=4) -> select_top(12)   (hand map + OOV bridge)
  D  static  per doc, RRF 1/(60+r_tfidf) + 1/(60+r_static) over the WHOLE doc index,
             top 4/doc, ties by TF-IDF rank. TF-IDF side = S's effective query; static
             side = the RAW user query through potion-base-8M. Hits keep TF-IDF scores.
  Refusal: D refuses iff S refuses (decision copied, so invariance holds by identity).

GATE (fixed before measurement): dev recall_strict net >= +2 questions AND 0 questions
down on frozen-10; then test2 once: net >= +1 question, vocab-mismatch not down. The
harness prints the verdict; it ships nothing. Exit nonzero only if S fails to reproduce
the published 0.734 / 0.613.

Needs model2vec (dev env only; never requirements.txt). src/ is not modified.
"""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import retrieve  # noqa: E402
from ablate_oov_bridge import K_PER_DOC, MIN_PER_DOC, TOP_N, effective_query  # noqa: E402
from evalset import load_eval_set, strict_covered, verify_expected  # noqa: E402
from rag import build_corpus  # noqa: E402
from retrieve import MIN_SCORE, Hit, PerDocRetriever, select_top  # noqa: E402

MODEL_DIR = Path(r"D:\NGORAG\runs\f0_static\potion-base-8M")
PROBES = ROOT / "data" / "eval" / "register_probes.json"
RRF_K = 60
SHIP_STRICT = {"frozen10": 0.734, "heldout": 0.613}
LABELS = {"frozen10": "frozen-10 (tripwire)", "heldout": "dev (SELECTOR)",
          "probes": "register probes (report-only)", "test2": "test2 (check, read once)"}


class StaticArm:
    def __init__(self, docs, ret, model_dir):
        from model2vec import StaticModel
        self.model = StaticModel.from_pretrained(str(model_dir))
        self.docs, self.ret = docs, ret
        self.emb = {d: self._norm(self.model.encode([c.text for c in ch]))
                    for d, ch in docs.items()}

    @staticmethod
    def _norm(m):
        m = np.asarray(m, dtype=np.float32)
        return m / np.maximum(np.linalg.norm(m, axis=-1, keepdims=True), 1e-12)

    def static_rank(self, q, doc_id):
        qv = self._norm(self.model.encode([q]))[0]
        sims = self.emb[doc_id] @ qv
        return sorted(range(len(sims)), key=lambda i: (-float(sims[i]), i))

    def tfidf_rank(self, eff, doc_id):
        sub = self.ret.sub[doc_id]
        res = sub.query(eff, k=len(sub.chunks))
        return [i for i, _, _ in res], {i: s for i, s, _ in res}

    def hits(self, q, k=K_PER_DOC):
        eff = effective_query(self.ret, q, retrieve.expand_query)
        out = []
        for d, chunks in self.docs.items():
            t_order, t_score = self.tfidf_rank(eff, d)
            rt = {i: r for r, i in enumerate(t_order, 1)}
            rd = {i: r for r, i in enumerate(self.static_rank(q, d), 1)}
            fused = sorted(rt, key=lambda i: (-(1 / (RRF_K + rt[i]) + 1 / (RRF_K + rd[i])), rt[i]))
            for i in fused[:k]:
                c = chunks[i]
                out.append(Hit(c.doc_id, c.ref, c.text, t_score[i]))
        return select_top(out, TOP_N, min_per_doc=MIN_PER_DOC)

    def static_only(self, q, k=K_PER_DOC):
        out = []
        for d, chunks in self.docs.items():
            for i in self.static_rank(q, d)[:k]:
                c = chunks[i]
                out.append(Hit(c.doc_id, c.ref, c.text, 0.0))
        return out


def load_probes():
    raw = json.loads(PROBES.read_text(encoding="utf-8"))["probes"]
    return [{"id": p["id"], "set": "probes", "class": p["lang"], "expect_gate": "answer",
             "text": p["text"], "expected": {d: set(v) for d, v in p["expected"].items()}}
            for p in raw]


def score(rows, ret, arm):
    res = {"S": {}, "D": {}, "S_shown": {}, "D_shown": {}, "flip": [], "false_ref": [],
           "cls": {}, "reach": [], "oracle": {}, "n_shown": {"S": [], "D": []}}
    for r in rows:
        s_hits = select_top(ret.query(r["text"], k=K_PER_DOC), TOP_N, min_per_doc=MIN_PER_DOC)
        refused = not any(h.score >= MIN_SCORE for h in s_hits)
        d_hits = arm.hits(r["text"])
        if r["expect_gate"] == "answer" and refused:
            res["false_ref"].append(r["id"])
        exp = r["expected"]
        n = sum(len(v) for v in exp.values())
        if not n:
            continue
        s_cov, d_cov = strict_covered(s_hits, exp), strict_covered(d_hits, exp)
        res["S"][r["id"]], res["D"][r["id"]] = s_cov / n, d_cov / n
        s_sh = [h for h in s_hits if h.score >= MIN_SCORE] if not refused else []
        d_sh = [h for h in d_hits if h.score >= MIN_SCORE] if not refused else []
        res["S_shown"][r["id"]] = strict_covered(s_sh, exp) / n
        res["D_shown"][r["id"]] = strict_covered(d_sh, exp) / n
        res["n_shown"]["S"].append(len(s_sh))
        res["n_shown"]["D"].append(len(d_sh))
        res["cls"].setdefault(r["class"], []).append(r["id"])
        if s_cov < n:
            u = strict_covered(s_hits + arm.static_only(r["text"]), exp)
            if u > s_cov:
                res["reach"].append(r["id"])
            res["oracle"][r["id"]] = u / n
        else:
            res["oracle"][r["id"]] = 1.0
    return res


def mean(v):
    v = list(v)
    return sum(v) / len(v) if v else float("nan")


def updown(res, a="S", b="D"):
    up = [q for q in res[a] if res[b][q] > res[a][q] + 1e-9]
    dn = [q for q in res[a] if res[b][q] < res[a][q] - 1e-9]
    return up, dn


def report(name, res):
    up, dn = updown(res)
    print("\n== %s ==" % LABELS[name])
    print("  recall_strict  S %.3f   D %.3f   (n=%d)   up %d %s   down %d %s"
          % (mean(res["S"].values()), mean(res["D"].values()), len(res["S"]),
             len(up), up, len(dn), dn))
    print("  shown (trimmed) S %.3f   D %.3f   mean shown S %.2f  D %.2f   [report-only]"
          % (mean(res["S_shown"].values()), mean(res["D_shown"].values()),
             mean(res["n_shown"]["S"]), mean(res["n_shown"]["D"])))
    for c, ids in sorted(res["cls"].items()):
        print("    %-22s n=%-3d S %.3f  D %.3f" % (c, len(ids), mean(res["S"][i] for i in ids),
                                                  mean(res["D"][i] for i in ids)))
    fails = [q for q in res["S"] if res["S"][q] < 1]
    print("  reach: %d of %d S-failing questions gain from static top-4 %s; oracle ceiling %.3f"
          % (len(res["reach"]), len(fails), res["reach"], mean(res["oracle"].values())))
    print("  false refusals: %s" % (res["false_ref"] or "none"))
    return up, dn


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    mdir = next((Path(a.split("=", 1)[1]) for a in argv if a.startswith("--model=")), MODEL_DIR)
    rows = load_eval_set()
    docs = build_corpus("v2")
    verify_expected(rows, docs)
    ret = PerDocRetriever(docs)
    arm = StaticArm(docs, ret, mdir)
    print("== F0 ablate_static == model %s  RRF k=%d  budget k=%d/doc top_n=%d"
          % (mdir.name, RRF_K, K_PER_DOC, TOP_N))
    out, bad = {}, 0
    for s in ("frozen10", "heldout"):
        out[s] = score([r for r in rows if r["set"] == s], ret, arm)
        got = mean(out[s]["S"].values())
        if abs(got - SHIP_STRICT[s]) > 0.0015:
            print("CONTROL FAILED: S %s %.3f != published %.3f" % (s, got, SHIP_STRICT[s]))
            bad = 1
    ud = {s: report(s, out[s]) for s in out}
    probes = score(load_probes(), ret, arm)
    report("probes", probes)
    for pid in sorted(probes["S"]):
        print("    %s S %.0f D %.0f" % (pid, probes["S"][pid], probes["D"][pid]))

    f_dn = ud["frozen10"][1]
    dev_net = len(ud["heldout"][0]) - len(ud["heldout"][1])
    dev_pass = dev_net >= 2 and not f_dn
    print("\n== GATE (fixed in advance) ==")
    print("  dev net questions %+d (need >= +2) | frozen-10 down %d (need 0) -> DEV %s"
          % (dev_net, len(f_dn), "PASS" if dev_pass else "FAIL"))
    if "--read-test2" in argv:
        if not dev_pass:
            print("  test2 NOT READ: dev failed, and the playbook forbids reading it.")
        else:
            t2 = load_eval_set("test2")
            verify_expected(t2, docs)
            out["test2"] = score(t2, ret, arm)
            up, dn = report("test2", out["test2"])
            vm = out["test2"]["cls"].get("vocab-mismatch", [])
            vm_ok = mean(out["test2"]["D"][i] for i in vm) >= mean(out["test2"]["S"][i] for i in vm)
            t_pass = len(up) - len(dn) >= 1 and vm_ok
            print("  test2 net %+d (need >= +1), vocab-mismatch not down: %s -> TEST2 %s"
                  % (len(up) - len(dn), vm_ok, "PASS" if t_pass else "FAIL"))
    elif dev_pass:
        print("  dev passed: re-run with --read-test2 for the one test2 read.")
    else:
        print("  VERDICT: DECLINE (dev failed). test2 stays unread.")
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
