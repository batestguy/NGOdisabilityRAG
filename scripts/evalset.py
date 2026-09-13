"""Shared loader for data/eval/questions.json -- the canonical question set.

Two sets live in that one file, and the distinction is the point of Phase 09:

  frozen10 : the 10 questions every artifact since Phase 01 was measured on.
             FROZEN. New questions may be added to the file; these ten are
             never edited, never reordered, and never merged with heldout --
             editing one to move a metric would destroy comparability with
             every bench, eval, ablation and transcript in the repo.
  heldout  : questions authored in Phase 09 that NOTHING has been tuned on.

WHY THE SPLIT EXISTS
--------------------
recall 0.925 was measured on the same 10 questions the synonym map was fitted
to -- an `education` key was deleted because it cost Q7, others were kept
because they lifted Q5/Q8/Q9. With n=10 a single question is worth 10 points,
so that number cannot distinguish generalisation from memorisation. Phase 09
step 3 (BM25 re-rank + offline thesaurus) would otherwise be tuned on the same
10 points, which is exactly the contamination this file exists to stop.

frozen10 rows were GENERATED ONCE from bench_phase01.load_questions() and
eval_phase06.EXPECTED by a throwaway script, never retyped, so the canonical
file could not disagree with its sources on the day it was created.
assert_frozen10_matches_notebook() is what keeps that true afterwards.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_PATH = ROOT / "data" / "eval" / "questions.json"

SETS = ("frozen10", "heldout")
GATES = ("answer", "refuse")
DOC_IDS = ("act2018", "constitution1999", "factsheet2020")


def load_eval_set(which: str | None = None) -> list[dict]:
    """Rows from questions.json, `expected` normalised to {doc_id: set[int]}.

    which=None returns every row; "frozen10"/"heldout" filter.
    """
    if which is not None and which not in SETS:
        raise ValueError("unknown set %r (expected one of %s)" % (which, SETS))
    raw = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    rows, seen = [], set()
    for r in raw:
        # Schema is checked on every load, not in a separate linter nobody
        # runs. A malformed row must fail loudly here rather than quietly
        # score 0.0 recall and look like a retrieval regression.
        for field in ("id", "set", "class", "expect_gate", "text", "expected",
                      "note"):
            assert field in r, "row %r missing field %r" % (r.get("id"), field)
        assert r["set"] in SETS, "%s: bad set %r" % (r["id"], r["set"])
        assert r["expect_gate"] in GATES, (
            "%s: bad expect_gate %r" % (r["id"], r["expect_gate"]))
        assert r["id"] not in seen, "duplicate id %r" % r["id"]
        seen.add(r["id"])
        assert r["text"].strip(), "%s: empty text" % r["id"]
        assert r["note"].strip(), "%s: empty note (where was truth read?)" % r["id"]
        exp = {}
        for doc_id, nums in r["expected"].items():
            assert doc_id in DOC_IDS, "%s: unknown doc_id %r" % (r["id"], doc_id)
            assert nums, "%s: empty number list for %s" % (r["id"], doc_id)
            exp[doc_id] = {int(n) for n in nums}
        # An off-corpus question expects nothing; anything else expects
        # something. A "refuse" row carrying expected refs is a contradiction,
        # and an "answer" row with none would silently divide by zero.
        if r["expect_gate"] == "refuse":
            assert not exp, "%s: expect_gate=refuse must have expected {}" % r["id"]
        else:
            assert exp, "%s: expect_gate=answer needs expected refs" % r["id"]
        if which is None or r["set"] == which:
            rows.append({**r, "expected": exp})
    return rows


def expected_map(rows: list[dict]) -> dict:
    """{id: {doc_id: set[int]}} -- the exact shape eval_phase06.EXPECTED has."""
    return {r["id"]: r["expected"] for r in rows}


def ref_nums(ref: str) -> set:
    """Numbers carried by a chunk ref ('cl. 16,17' -> {16, 17}).

    A local twin of eval_phase06.ref_nums, because eval_phase06 imports THIS
    module -- importing back would be circular. Same one-line definition.
    """
    return {int(n) for n in re.findall(r"\d+", ref)}


def verify_expected(rows: list[dict], docs: dict) -> int:
    """Every expected number must occur in some chunk's ref, in its own doc.

    Same rule as eval_phase06.verify_ground_truth, generalised to take rows
    instead of reading a module global. That twin is deliberately left in place
    this session: the whole claim of the M2 refactor is that eval_phase06's
    output is byte-identical across the move, and the smallest way to keep that
    claim checkable is to change exactly one literal in it and nothing else.

    This is a HARD failure, not a metric. An expected number that no chunk
    carries is a ground-truth bug -- the question would score 0.0 recall
    forever and look like a retrieval problem.
    """
    have = {doc_id: set().union(*(ref_nums(c.ref) for c in chunks)) if chunks
            else set() for doc_id, chunks in docs.items()}
    bad = []
    for r in rows:
        for doc_id, nums in r["expected"].items():
            missing = nums - have.get(doc_id, set())
            if missing:
                bad.append("%s %s: %s absent from corpus (note: %s)"
                           % (r["id"], doc_id, sorted(missing), r["note"][:80]))
    assert not bad, "ground truth does not match the corpus:\n  " + "\n  ".join(bad)
    return sum(len(ns) for r in rows for ns in r["expected"].values())


def assert_frozen10_matches_notebook() -> None:
    """frozen10 texts, IN ORDER, must equal bench_phase01.load_questions().

    This is why load_questions() is KEPT rather than retired. It parses the
    question literal straight out of notebooks/01_foundation.ipynb, so it is an
    INDEPENDENT source: two sources that must agree is a real invariant, one
    source nobody checks is just a file. If the notebook is edited, or a
    frozen10 row is reworded to help a metric, this fails immediately and
    loudly instead of quietly shifting the yardstick under every historical
    number in the repo.
    """
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from bench_phase01 import load_questions

    rows = load_eval_set("frozen10")
    ids = [r["id"] for r in rows]
    assert ids == ["Q%d" % i for i in range(1, 11)], (
        "frozen10 ids must be Q1..Q10 in order, got %s" % ids)
    notebook = load_questions()
    assert len(notebook) == 10, "load_questions() returned %d" % len(notebook)
    for row, text in zip(rows, notebook):
        assert row["text"] == text, (
            "frozen10 %s has drifted from the notebook source:\n"
            "  questions.json: %r\n  load_questions(): %r"
            % (row["id"], row["text"], text))
    for r in rows:
        assert r["expect_gate"] == "answer", (
            "%s: every frozen10 question is answerable" % r["id"])
