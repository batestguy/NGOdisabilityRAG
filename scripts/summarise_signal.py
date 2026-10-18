"""Summarise H7 DRLCA_SIGNAL lines copied out of Render's logs (docs/telemetry.md).

    ... summarise_signal.py <file-with-pasted-log-lines>
    ... summarise_signal.py < pasted.txt

Reads text, prints counts. No network, no file written. Opted-in question text
(`q`) is counted, never printed.
"""
import collections
import json
import sys

PREFIX = "DRLCA_SIGNAL "


def parse(lines):
    for ln in lines:
        i = ln.find(PREFIX)
        if i < 0:
            continue
        try:
            yield json.loads(ln[i + len(PREFIX):].strip())
        except ValueError:
            continue


def main() -> int:
    src = open(sys.argv[1], encoding="utf-8") if len(sys.argv) > 1 else sys.stdin
    recs = list(parse(src))
    turns = {r["id"]: r for r in recs if r.get("kind") == "turn"}
    helpful = {r["id"]: r["helpful"] for r in recs if r.get("kind") == "helpful"}  # last wins
    print("turns: %d   helpful answers: %d   text opted in: %d"
          % (len(turns), len(helpful), sum("q" in t for t in turns.values())))
    for field in ("route", "refused", "top"):
        c = collections.Counter(str(t.get(field)) for t in turns.values())
        print("%-8s %s" % (field, dict(c.most_common())))
    print("\nhelpful by route (yes / no / not answered):")
    for route in sorted({t["route"] for t in turns.values()}):
        ids = [i for i, t in turns.items() if t["route"] == route]
        yes = sum(helpful.get(i) == "yes" for i in ids)
        no = sum(helpful.get(i) == "no" for i in ids)
        print("  %-9s %3d / %3d / %3d" % (route, yes, no, len(ids) - yes - no))
    legal = [t for t in turns.values() if t["route"] == "legal" and not t["refused"]]
    if legal:
        print("\nlegal: mean excerpts shown %.1f" % (sum(t["shown"] for t in legal) / len(legal)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
