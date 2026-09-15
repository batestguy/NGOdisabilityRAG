"""Shared loader for data/eval/conversations.json -- the multi-turn question set.

WHY A SECOND FILE AND NOT MORE ROWS IN questions.json
-----------------------------------------------------
questions.json has one shape (a flat row per question) and one loader whose
output every harness in the repo already consumes. A conversation is a
different shape -- an ordered list of turns, where a turn's meaning depends on
the turns before it -- and folding it in would have meant changing
evalset.load_eval_set(). That loader is imported by eval_phase06.py,
judge_phase06.py, ablate_phase08.py, ablate_phase10.py and eval_heldout.py, and
the claim that every published v1 number is reproducible from this commit rests
on it staying byte-stable. So: new shape, new file, same discipline.

TWO SETS, SAME RULES AS THE SINGLE-TURN SPLIT
---------------------------------------------
  chat_dev   12 conversations / 35 turns. Tuning is allowed here. The
             contextualisation thresholds in src/chat.py may be chosen against
             this set and nothing else.
  chat_test  10 conversations / 27 turns. AUTHORED BLIND on 2026-09-15 from the
             corpus text only, BEFORE src/chat.py existed and before any
             contextualisation had been measured -- the same protocol that
             produced the clean single-turn `test` set. Read once. Never tuned
             against. If a chat_test number disappoints, that is the finding.

The ordering was not a nicety. A contextualiser authored first would have fixed
the query distribution its own eval set was then written to reward, and the
number it produced would have measured nothing.

TURN CLASSES, AND WHY EACH ONE IS HERE
--------------------------------------
Each class breaks a DIFFERENT mechanism, which is why the eval reports them
separately rather than as one mean:

  direct        a self-contained question. The control: contextualisation must
                not make these worse.
  ellipsis      "so can they fire me?" -- no disability term, no statutory term.
                Unanswerable by retrieval in isolation. The reason chat is a
                retrieval problem and not a UI problem.
  pronoun       "do they have to pay for it?" -- referring expressions with no
                antecedent in the turn.
  narrowing     "and in Kano?" -- a filter, not a question. Scored on SLOTS, not
                recall: router.extract_help_slots() on this turn alone loses the
                disability, and merge_help_slots() is what must carry it.
  topic-shift   THE CONTEXTUALISATION TRAP. Carrying prior turns into the
                retrieval query can drag the old topic into a new question. The
                gate is "not worse than naive", never "better".
  handoff       legal -> help. Scored on routing and slots; legal recall is
                undefined for it, not zero.
  off-corpus-   the inherited-context FALSE-ANSWER trap, and the one genuinely
  after-legal   new failure mode chat creates. An off-corpus question asked
                after two legal turns can inherit enough legal vocabulary to
                clear MIN_SCORE and draw a confident answer. Measured, never
                assumed.

THREE GATES, NOT TWO
--------------------
evalset.GATES is ("answer", "refuse"). This set needs a third, "help", and the
reason is the same one evalset gives for scoring an off-corpus row None instead
of 0.0: a help turn has no legal ground truth, so scoring its legal recall as
0.0 would drag a mean down with a number that has no meaning. "help" turns
carry expect_slots instead of expected refs.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from evalset import DOC_IDS, ref_nums  # noqa: E402  (shared, never re-implemented)

CONVERSATIONS_PATH = ROOT / "data" / "eval" / "conversations.json"

SETS = ("chat_dev", "chat_test")
GATES = ("answer", "refuse", "help")
TURN_CLASSES = ("direct", "ellipsis", "pronoun", "narrowing", "topic-shift",
                "handoff", "off-corpus-after-legal")

# A conversation cannot OPEN with a turn that depends on an earlier turn. If it
# could, the "naive vs contextualised" comparison would be meaningless for that
# turn -- there is no history to carry either way -- and a set that allowed it
# would quietly credit contextualisation for turns it never touched.
_NEEDS_HISTORY = ("ellipsis", "pronoun", "narrowing", "topic-shift",
                  "off-corpus-after-legal")

SLOT_KEYS = ("disability", "location")


def load_chat_set(which: str | None = None) -> list[dict]:
    """Conversations from conversations.json, validated, `expected` normalised.

    which=None returns every conversation; any member of SETS filters to it.
    Each turn gains `expected` as {doc_id: set[int]} and an `index` (0-based),
    so callers never have to re-derive turn position from enumerate() and get it
    subtly different from the next caller.
    """
    if which is not None and which not in SETS:
        raise ValueError("unknown set %r (expected one of %s)" % (which, SETS))
    raw = json.loads(CONVERSATIONS_PATH.read_text(encoding="utf-8"))
    convs, seen = [], set()
    for c in raw:
        # Schema is checked on every load, not in a separate linter nobody runs
        # -- evalset.py's argument, applied to the multi-turn shape. A malformed
        # turn must fail loudly here rather than quietly score 0.0 and look like
        # a contextualisation regression.
        for field in ("id", "set", "topic", "note", "turns"):
            assert field in c, "conversation %r missing field %r" % (
                c.get("id"), field)
        assert c["set"] in SETS, "%s: bad set %r" % (c["id"], c["set"])
        assert c["id"] not in seen, "duplicate conversation id %r" % c["id"]
        seen.add(c["id"])
        assert c["note"].strip(), (
            "%s: empty note (where was truth read?)" % c["id"])
        assert c["turns"], "%s: no turns" % c["id"]
        turns = []
        for i, t in enumerate(c["turns"]):
            tid = "%s.t%d" % (c["id"], i + 1)
            for field in ("text", "class", "expect_gate", "expected", "note"):
                assert field in t, "%s missing field %r" % (tid, field)
            assert t["class"] in TURN_CLASSES, (
                "%s: bad class %r" % (tid, t["class"]))
            assert t["expect_gate"] in GATES, (
                "%s: bad expect_gate %r" % (tid, t["expect_gate"]))
            assert t["text"].strip(), "%s: empty text" % tid
            assert t["note"].strip(), (
                "%s: empty note (where was truth read?)" % tid)
            if i == 0:
                assert t["class"] not in _NEEDS_HISTORY, (
                    "%s: a conversation cannot OPEN with class %r -- there is "
                    "no history to resolve it against, so naive and "
                    "contextualised would be identical and the turn would "
                    "credit contextualisation for nothing" % (tid, t["class"]))
            exp = {}
            for doc_id, nums in t["expected"].items():
                assert doc_id in DOC_IDS, "%s: unknown doc_id %r" % (tid, doc_id)
                assert nums, "%s: empty number list for %s" % (tid, doc_id)
                exp[doc_id] = {int(n) for n in nums}
            if t["expect_gate"] == "answer":
                assert exp, "%s: expect_gate=answer needs expected refs" % tid
                assert "expect_slots" not in t, (
                    "%s: expect_slots belongs to a help turn" % tid)
            else:
                assert not exp, (
                    "%s: expect_gate=%s must have expected {}"
                    % (tid, t["expect_gate"]))
            if t["expect_gate"] == "help":
                assert "expect_slots" in t, (
                    "%s: a help turn is scored on slots, so it must declare "
                    "expect_slots -- otherwise it is unscoreable" % tid)
                for key in SLOT_KEYS:
                    assert key in t["expect_slots"], (
                        "%s: expect_slots missing %r" % (tid, key))
                assert set(t["expect_slots"]) == set(SLOT_KEYS), (
                    "%s: unknown slot keys %s"
                    % (tid, sorted(set(t["expect_slots"]) - set(SLOT_KEYS))))
            elif "expect_slots" in t:
                raise AssertionError(
                    "%s: expect_slots is only meaningful on a help turn" % tid)
            turns.append({**t, "expected": exp, "index": i, "turn_id": tid})
        if which is None or c["set"] == which:
            convs.append({**c, "turns": turns})
    return convs


def iter_turns(convs: list[dict]):
    """Yield (conv, turn, history) for every turn, in order.

    `history` is the list of PRECEDING turn dicts -- the exact thing a
    contextualiser is allowed to see. Callers never slice conv["turns"]
    themselves, so no harness can accidentally give a turn access to its own
    future, which is the one bug that would make every number in this set look
    wonderful and mean nothing.
    """
    for c in convs:
        for t in c["turns"]:
            yield c, t, c["turns"][:t["index"]]


def verify_expected(convs: list[dict], docs: dict) -> int:
    """Every expected number must occur in some chunk's ref, in its own doc.

    Same rule and same failure mode as evalset.verify_expected: a HARD failure,
    not a metric. An expected number no chunk carries is a ground-truth bug --
    the turn would score 0.0 forever and read as a contextualisation problem.

    TWO THINGS THIS DELIBERATELY DOES NOT PROVE (found in review, 2026-09-15 --
    read them before trusting a 0.000 on any single turn):

    1. It checks that the expected NUMBER appears in SOME chunk's ref in that
       doc, not that the chunk actually carrying the relevant TEXT is reffed
       with it. CT7.t2 is the live example: the Act's First Schedule list
       ("Crutches, guide canes etc") sits in a chunk reffed 'general', and
       ref_nums('general') is empty, so that turn can never score above 0.000 --
       yet this function passes it, because an unrelated 'cl. 3,4,5' header
       chunk does carry a 5. The turn is UNSCOREABLE on corpus v1, not missed.
       Same class as the recorded "Act cl.19 is uncitable" gap; corpus v2's
       audit gate (ref=='general' <= 1% per doc) is what removes it.

    2. Constitution section numbers COLLIDE across chapters -- s.36 is both the
       Chapter IV fair-hearing section and a Chapter VIII provision, and s.18,
       s.34, s.40 and s.42 have the same property. Matching on (doc_id, number)
       pairs cannot tell them apart in principle. Verified 2026-09-15 that no
       turn in either set is currently affected (TF-IDF surfaces the intended
       chapter for CT3.t1 and CT10.t1), but a future turn could hit it and would
       score a false POSITIVE, which is the more dangerous direction. This is a
       pre-existing property of eval_heldout.py's convention, shared here on
       purpose so the two stay comparable -- not a new defect.
    """
    have = {doc_id: set().union(*(ref_nums(c.ref) for c in chunks)) if chunks
            else set() for doc_id, chunks in docs.items()}
    bad = []
    for c in convs:
        for t in c["turns"]:
            for doc_id, nums in t["expected"].items():
                missing = nums - have.get(doc_id, set())
                if missing:
                    bad.append("%s %s: %s absent from corpus (note: %s)"
                               % (t["turn_id"], doc_id, sorted(missing),
                                  t["note"][:80]))
    assert not bad, ("chat ground truth does not match the corpus:\n  "
                     + "\n  ".join(bad))
    return sum(len(ns) for c in convs for t in c["turns"]
               for ns in t["expected"].values())


def summary(convs: list[dict]) -> dict:
    """{set: {'conversations': n, 'turns': n, 'by_class': {...}}} for printing."""
    out = {}
    for c in convs:
        s = out.setdefault(c["set"], {"conversations": 0, "turns": 0,
                                      "by_class": {}})
        s["conversations"] += 1
        for t in c["turns"]:
            s["turns"] += 1
            s["by_class"][t["class"]] = s["by_class"].get(t["class"], 0) + 1
    return out
