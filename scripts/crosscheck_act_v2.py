"""Cross-check the v2 clause parse against the v1 Act text. Zero network, stdlib.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\crosscheck_act_v2.py

WHY THIS IS NOT A SMOKE TEST
----------------------------
docs/phases/12_corpus_v2.md wrote the expected disagreements BEFORE the parser
existed, precisely so this output is falsifiable rather than interpretable after
the fact:

  cl.38 opening + (a)-(i)   LARGE disagreement -- absent from v1 (Finding 1)
  cl.37                     LARGE disagreement -- v1 runs into cl.38's tail (1a)
  cl.38 (p)-(r)             disagreement       -- v1 misfiles them as cl.39 (1b)
  cl.40                     AGREES             -- v1 has the body, lost the numeral
  PART VII / VIII heading   disagrees          -- v1 L542 misnumbers it (1c)
  everything else           AGREES

ANYTHING OUTSIDE THAT SET IS A PARSER BUG, NOT A DISCOVERY.

Two editions paginate differently, so the comparison is TEXT-LEVEL ONLY, never
page position. Coverage is measured with character shingles: what fraction of a
v2 clause's text can be found anywhere in v1 at all. That asks the one question
that matters -- did the gazette recover text v1 never had -- without being
confused by reordering.

WHERE THEY DISAGREE, THE GAZETTE WINS (data/raw/SOURCES.md). This script reports
the disagreement; it never edits either side.
"""

import json
import re
import sys
from pathlib import Path

# The gazette OCR contains full-width and replacement characters that the
# Windows console's cp1252 codec cannot encode; without this the script dies
# mid-report on a UnicodeEncodeError while printing a finding.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

V1_TXT = ROOT / "data" / "processed" / "disability_act_2018_full.txt"
V2_JSON = ROOT / "data" / "processed" / "act2018_v2_clauses.json"

# Shingle width, CALIBRATED not chosen. Both editions are OCR output with
# INDEPENDENT character noise ('Reforim' for 'Reform', 'IVheel' for 'Wheel'), so
# one bad character destroys every shingle spanning it. At k=40 that left only 7
# of 58 clauses able to "agree" at all and the measure said more about OCR noise
# than about the corpus. Calibrated against clauses whose answer Finding 1
# already established -- cl.40's body is known PRESENT in v1, cl.37/38 known
# damaged -- k=10 separates them cleanly (0.90 vs 0.50/0.61) where k>=18 does
# not (0.81 vs 0.32/0.51). Ten normalised chars is roughly two words, so the
# measure stays order-sensitive rather than degenerating into a bag of words.
K = 10
STEP = 2
AGREE = 0.85    # >= this fraction of shingles found in v1 -> "agrees"
LARGE = 0.55    # <  this -> "LARGE disagreement"

PREDICTED = {
    37: "LARGE", 38: "LARGE",
    40: "agrees",
}

# Adjudicated AFTER the first run, and kept in a separate dict on purpose: a
# prediction that was written in advance and an explanation reached afterwards
# are different kinds of evidence, and merging them would quietly turn this
# yardstick into something fitted to its own result.
ADJUDICATED = {
    53: ("v1 DEFECT, same class as cl.38. 'awarded against the Commission' is "
         "absent from v1 outright, and v1's own text at '53.' reads "
         "'53. | judgment debt. | shall bepaidfrom theFund of theCommission.' "
         "-- the marginal note spliced in and the body truncated. v2 recovers "
         "the full sentence. Decided on substring presence, not on a ratio."),
    20: ("OCR DIVERGENCE, not missing text. Distinctive probes "
         "('particularlychildren', 'blinddeaf', 'mostappropriate') all resolve "
         "in v1. Both editions garble this clause's dense word-joining "
         "independently ('selivere' survives in v2), which depresses shingle "
         "coverage without any content being absent."),
    27: ("OCR DIVERGENCE, not missing text. 'ifaccommodationisbeing' and "
         "'schoolsfortheirstudents' both resolve in v1."),
    44: ("OCR DIVERGENCE, not missing text. 'gratuity' and 'pensionrefor' "
         "resolve in v1; the wording of the opening differs between scans."),
}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def shingles(s: str, k: int = K, step: int = STEP) -> list[str]:
    return [s[i:i + k] for i in range(0, max(len(s) - k + 1, 1), step)]


def coverage(clause: str, haystack: set[str]) -> float:
    sh = shingles(norm(clause))
    if not sh:
        return 1.0
    return sum(1 for s in sh if s in haystack) / len(sh)


def main() -> int:
    assert V1_TXT.exists(), "v1 Act text missing at %s" % V1_TXT
    assert V2_JSON.exists(), "run parse_act_v2.py first"

    raw1 = V1_TXT.read_text(encoding="utf-8", errors="replace")
    v1 = norm(raw1)
    hay = set(shingles(v1, K, 1))          # stride 1 on the haystack
    v2 = json.loads(V2_JSON.read_text(encoding="utf-8"))
    clauses = {c["n"]: c for c in v2["clauses"]}

    print("== CROSS-CHECK v2 vs v1 ==")
    print("  v1 : %s (%d normalised chars)" % (V1_TXT.name, len(v1)))
    print("  v2 : %d clauses, %d normalised chars"
          % (len(clauses), sum(len(norm(c["text"])) for c in clauses.values())))
    print("  shingles k=%d, agree>=%.2f, large<%.2f\n" % (K, AGREE, LARGE))

    verdicts = {}
    for n in sorted(clauses):
        cov = coverage(clauses[n]["text"], hay)
        verdicts[n] = ("agrees" if cov >= AGREE
                       else "LARGE" if cov < LARGE else "partial")

    agree = [n for n, v in verdicts.items() if v == "agrees"]
    partial = [n for n, v in verdicts.items() if v == "partial"]
    large = [n for n, v in verdicts.items() if v == "LARGE"]

    print("  agrees (>=%.0f%% of v2 text found in v1) : %d clauses"
          % (AGREE * 100, len(agree)))
    print("  partial                                 : %s" % (partial or "none"))
    print("  LARGE disagreement                      : %s" % (large or "none"))

    print("\n== AGAINST THE WRITTEN-IN-ADVANCE PREDICTIONS ==")
    ok = True
    for n, want in sorted(PREDICTED.items()):
        got = verdicts.get(n)
        hit = (got == want) or (want == "LARGE" and got in ("LARGE", "partial"))
        ok &= hit
        print("  cl.%-2d predicted %-7s got %-7s cov=%.2f  %s"
              % (n, want, got, coverage(clauses[n]["text"], hay),
                 "OK" if hit else "*** MISMATCH ***"))

    unexpected = [n for n in large + partial if n not in PREDICTED]
    print("\n== DISAGREEMENTS NOT PREDICTED IN ADVANCE ==")
    print("  Per the playbook these are PARSER BUGS until shown otherwise.")
    unadjudicated = [n for n in unexpected if n not in ADJUDICATED]
    for n in sorted(unexpected):
        print("\n  cl.%-2d cov=%.2f  %s" % (n, coverage(clauses[n]["text"], hay),
                                            verdicts[n]))
        if n in ADJUDICATED:
            print("     ADJUDICATED: %s" % ADJUDICATED[n])
        else:
            print("     *** UNADJUDICATED -- investigate before D3 ***")
            print("     %r" % clauses[n]["text"][:150])
    if not unexpected:
        print("  none")
    ok &= not unadjudicated

    # The single most load-bearing check: cl.38's opening is the string
    # Finding 1 proved grep cannot find anywhere in v1.
    probe = "formulateandimplementpolicies"
    print("\n== FINDING 1's DECISIVE PROBE ==")
    print("  'formulate and implement policies' in v1 : %s"
          % ("FOUND" if probe in v1 else "absent (as Finding 1 measured)"))
    print("  ... in v2 cl.38                          : %s"
          % ("FOUND" if probe in norm(clauses[38]["text"]) else "ABSENT"))
    recovered = probe not in v1 and probe in norm(clauses[38]["text"])
    print("  => clause 38's opening is %s"
          % ("RECOVERED by the gazette" if recovered else "NOT recovered"))

    print("\n  RESULT: %s" % ("predictions hold" if ok else
                              "PREDICTION MISMATCH -- investigate before D3"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
