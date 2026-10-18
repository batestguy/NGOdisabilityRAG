"""H5a -- Pidgin register-routed static arm. Measure-only, zero quota.

Playbook: docs/phases/16_post_launch_roadmap.md H5a. Router, arm and gate were
frozen in data/eval/pidgin_h5a.json (commit cda437a) before any number.

  S  ship    PerDocRetriever.query(q, k=4) -> select_top(12)
  R  routed  F0 arm D (scripts/ablate_static.py, reproduced from 27ed13d) when
             the router fires, else S unchanged. Refusal = S's decision.

  ... ablate_h5a_pidgin.py              Pidgin-dev + router-firing sweep (text only)
  ... ablate_h5a_pidgin.py --read-test  ALSO Pidgin-test, ONCE, only if dev passed

Firing on test/test2 rows is found from TEXT ONLY; their scores are read only
for rows the router fires on, and only under --read-test.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from ablate_static import MODEL_DIR, StaticArm, mean  # noqa: E402
from ablate_oov_bridge import K_PER_DOC, MIN_PER_DOC, TOP_N  # noqa: E402
from evalset import load_eval_set, strict_covered, verify_expected  # noqa: E402
from rag import build_corpus  # noqa: E402
from retrieve import PerDocRetriever, select_top  # noqa: E402

SET = ROOT / "data" / "eval" / "pidgin_h5a.json"
MARKERS = {"dey", "wetin", "abeg", "wey", "dem", "una", "sabi", "comot", "pikin",
           "wahala", "abi", "oya", "wan", "sef", "sha", "gree", "oga", "na", "di"}


def router_fires(q: str) -> bool:
    return bool(set(re.findall(r"[a-z]+", q.lower())) & MARKERS)


def load_pidgin(which: str) -> list:
    raw = json.loads(SET.read_text(encoding="utf-8"))["questions"]
    return [dict(r, expected={d: set(v) for d, v in r["expected"].items()})
            for r in raw if r["set"] == which]


def compare(rows, ret, arm):
    """{id: (S recall_strict, R recall_strict, fired)}"""
    out = {}
    for r in rows:
        n = sum(len(v) for v in r["expected"].values())
        s_hits = select_top(ret.query(r["text"], k=K_PER_DOC), TOP_N, min_per_doc=MIN_PER_DOC)
        fired = router_fires(r["text"])
        r_hits = arm.hits(r["text"]) if fired else s_hits
        out[r["id"]] = (strict_covered(s_hits, r["expected"]) / n,
                        strict_covered(r_hits, r["expected"]) / n, fired)
    return out


def net(res):
    up = [k for k, (s, r, _) in res.items() if r > s + 1e-9]
    dn = [k for k, (s, r, _) in res.items() if r < s - 1e-9]
    return up, dn


def show(name, res):
    up, dn = net(res)
    print("\n== %s (n=%d) ==" % (name, len(res)))
    for k, (s, r, f) in res.items():
        print("  %-5s fired=%s  S %.2f  R %.2f %s" % (k, "Y" if f else "n", s, r,
              "UP" if k in up else "DOWN" if k in dn else ""))
    print("  mean S %.3f  R %.3f | up %d %s | down %d %s | net %+d"
          % (mean(v[0] for v in res.values()), mean(v[1] for v in res.values()),
             len(up), up, len(dn), dn, len(up) - len(dn)))
    return len(up) - len(dn)


def main() -> int:
    read_test = "--read-test" in sys.argv
    docs = build_corpus("v2")
    ret = PerDocRetriever(docs)
    arm = StaticArm(docs, ret, MODEL_DIR)
    size_mb = sum(p.stat().st_size for p in MODEL_DIR.rglob("*") if p.is_file()) / 2**20
    print("== H5a routed static arm == model %s (%.1f MB on disk)" % (MODEL_DIR.name, size_mb))

    dev = load_pidgin("pidgin_dev")
    verify_expected(dev, docs)
    dev_net = show("Pidgin-dev (SELECTOR)", compare(dev, ret, arm))

    # Router sweep over the gated sets: TEXT ONLY here.
    gated = {s: load_eval_set(s) for s in ("frozen10", "heldout", "test", "test2")}
    fired = {s: [r for r in rows if router_fires(r["text"])] for s, rows in gated.items()}
    print("\n== Router firing on gated sets (text only) ==")
    for s, rows in fired.items():
        print("  %-9s fires on %d/%d %s" % (s, len(rows), len(gated[s]),
                                            [(r["id"], r["text"][:50]) for r in rows]))
    # frozen-10 and dev rows may be scored now; test/test2 only under --read-test.
    drops = []
    for s in ("frozen10", "heldout"):
        rows = [r for r in fired[s] if sum(len(v) for v in r["expected"].values())]
        if rows:
            res = compare(rows, ret, arm)
            drops += [(s, k) for k in net(res)[1]]
            show("fired %s rows" % s, res)

    dev_pass = dev_net >= 2 and not drops
    print("\n== DEV GATE == Pidgin-dev net %+d (need >= +2); fired frozen-10/dev rows down: %s -> %s"
          % (dev_net, drops or "none", "PASS" if dev_pass else "FAIL"))
    print("  serving artifact %.1f MB (need <= 40); refusal = S by identity (0/212 holds)" % size_mb)
    if not read_test:
        print("  " + ("dev passed: re-run with --read-test ONCE." if dev_pass
                      else "VERDICT: DECLINE (dev failed). Pidgin-test stays unread."))
        return 0
    if not dev_pass:
        print("  --read-test REFUSED: the dev gate failed.")
        return 1
    test = load_pidgin("pidgin_test")
    verify_expected(test, docs)
    t_net = show("Pidgin-test (read once)", compare(test, ret, arm))
    for s in ("test", "test2"):
        rows = [r for r in fired[s] if sum(len(v) for v in r["expected"].values())]
        if rows:
            res = compare(rows, ret, arm)
            drops += [(s, k) for k in net(res)[1]]
            show("fired %s rows" % s, res)
    ok = t_net >= 1 and not drops and size_mb <= 40
    print("\n== H5a GATE == test net %+d (need >= +1); fired gated rows down: %s; artifact %.1f MB -> %s"
          % (t_net, drops or "none", size_mb, "PASS (eligible; serving needs F1 port + parity)"
             if ok else "FAIL -> decline"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
