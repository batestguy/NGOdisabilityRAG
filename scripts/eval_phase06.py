"""Phase 06 custom eval -- zero-LLM proxies for the three RAGAS spec metrics.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\eval_phase06.py [--out FILE]
  (from D:\\NGORAG; default out scripts/eval_phase06_results_<date>.json)

Why custom first: RAGAS itself calls LLMs (~30+ calls for 10Q x 3 metrics),
which exceeds the Gemini free-tier daily budget, and `ragas` is NOT installed
(installing its langchain/openai dependency tree into drlca-rag risks the
pinned env). The spec explicitly wants the framework trade-off documented --
this script IS the custom side of that comparison; the RAGAS-judge run is
queued for after a quota reset (see TRADE-OFFS below + playbook).

Design (no circularity):
  - EXPECTED refs are ground truth from CORPUS inspection (verified at runtime:
    every expected number must occur in some chunk of that doc), never copied
    from LLM answers. s.33 is explicitly EXCLUDED for dignity (TOC-line trap).
  - Retrieval half re-queries live (deterministic, offline -- same code path
    ask() uses). Answer half reads the frozen v2 transcript (never re-faked).

Proxies (floors, not equivalents -- see TRADE-OFFS):
  - context recall ~= NEEDLES side: expected (doc, number) pairs retrieved /
    expected pairs. GATED (>0.75): matches the PerDocRetriever design goal
    (every doc represented; coverage over precision, locked Phase 02 decision).
  - context precision (diagnostic only): retrieved hits sharing an expected
    number / retrieved hits. Per-doc merging trades this away BY DESIGN, so it
    is reported but never gated -- gating it would contradict the locked
    architecture. The RAGAS judge (deferred) is the real arbiter.
  - faithfulness ~= supported claims / total claims. Claim = answer segment per
    citation tag. Supported = cited numbers occur in cited-doc pooled text AND
    stemmed content-word overlap(claim, cited-ref chunks) >= 0.12. Refusals:
    faithful=1.0 iff NO expected numbers were retrieved (correct decline),
    else 0.0 (decline despite context holding the answer). Manual verdicts from
    Phase 02 apply as audited overrides (TOC-line misattribution is invisible
    to mechanical checks -- itself a finding: see TRADE-OFFS). GATED (>0.85)
    on the AUDITED value.
  - answer relevancy ~= question content-word coverage in the answer
    (stemmed, stopwords removed). Floor check: catches off-topic answers, not
    true aboutness. Refused Qs excluded (n/a). REPORTED with caveat, ungated:
    it punishes correct answers that paraphrase (transitional/transitory,
    long/five-years) -- diagnosed 2026-09-09, kept visible, not deleted.
  - answer relevancy (gated proxy) ~= REVERSE retrieval: query the corpus with
    the ANSWER text; fraction of top-3 hits landing in the expected ref set.
    An on-topic answer retrieves its own support (deterministic mirror of
    RAGAS's reverse-generation idea). GATED (>0.80). Refused Qs excluded;
    refusal-correctness is reported separately (decline-empty-hands vs
    decline-while-holding).

TRADE-OFFS (custom vs RAGAS -- spec research deliverable):
  custom: $0, deterministic, re-runnable offline, but blind to subtle
    misattribution (Q9 dignity@[s.33] passes every mechanical check -- the
    number AND the word both occur in the cited TOC-line chunk) and blind to
    true aboutness (coverage is a floor). Needs hand-built ground truth.
  RAGAS: LLM judge catches the above (it reads chunk semantics), needs no
    ground truth, but costs ~30+ metered calls per 10Q pass, is nondeterministic
    across runs (Q10 already refused twice on identical context -- judge
    variance compounds), and drags heavy deps into the env.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS  # noqa: E402

from bench_phase01 import load_questions  # noqa: E402 (SAME 10Q set)
from rag import CITE_TAG_RE, build_corpus  # noqa: E402
from retrieve import PerDocRetriever, stem  # noqa: E402

TRANSCRIPT = (ROOT / "scripts"
              / "test_phase02_results_cite-strict-v2_2026-09-09.json")

# Ground truth from CORPUS inspection (runtime-verified below, never from answers):
#  Q1 fines live in Act cl.1 (+N100k tail cl.2) and factsheet Section 1/1(2)/2.
#  Q5 penalty clauses found by corpus hunt: cl.1/2 (N100k/N1M), cl.8(3)
#    (approval offence), cl.9,10 (N5,000/day), cl.13 (parking), cl.29,30 (N50k).
#  Q6 Act cl.10 is awareness-programmes (NOT vehicles) -- expected is cl.11 only.
#  Q9 s.33 is a bare TOC line ("33. Right to life. 34 Right to dignity..."),
#    explicitly NOT expected for dignity; s.34 (body) + s.17 are.
#  Q10 s.46 holds the legal-aid provision; factsheet S39 is commission powers.
EXPECTED = {
    "Q1": {"act2018": {1}, "factsheet2020": {1, 2}},
    "Q2": {"act2018": {3, 4, 5, 6, 7}, "factsheet2020": {6, 7}},
    "Q3": {"act2018": {29, 30}},
    "Q4": {"act2018": {31}, "factsheet2020": {30, 31}},
    "Q5": {"act2018": {1, 2, 8, 9, 10, 13, 29, 30}},
    "Q6": {"act2018": {11}, "factsheet2020": {10, 11}},
    "Q7": {"act2018": {16, 17, 20}, "factsheet2020": {17, 19, 20}},
    "Q8": {"act2018": {6, 7}, "factsheet2020": {6, 7}},
    "Q9": {"constitution1999": {17, 34}},
    "Q10": {"constitution1999": {46}},
}

# Audited overrides from Phase 02 manual verdicts (qid, tag-sub, claim-word):
# mechanical checks cannot see TOC-line misattribution -- documented, not hidden.
MANUAL_FLAGS = [("Q9", "Constitution s. 33", "dignity")]

OVERLAP_FLOOR = 0.12
STOP = {stem(w) for w in ENGLISH_STOP_WORDS}
NUM_RE = re.compile(r"\d+")
WORD_RE = re.compile(r"[a-zA-Z]+")


def ref_nums(ref: str) -> set:
    return {int(n) for n in NUM_RE.findall(ref)}


def content_stems(text: str) -> set:
    return {stem(w) for w in WORD_RE.findall(text.lower())
            if len(w) > 2 and stem(w) not in STOP}


def verify_ground_truth(docs) -> None:
    """Every expected number must occur in some chunk of its doc."""
    for qid, per_doc in EXPECTED.items():
        for doc_id, nums in per_doc.items():
            have = set()
            for c in docs[doc_id]:
                have |= ref_nums(c.ref)
            missing = set(nums) - have
            assert not missing, "%s %s: expected %s absent from corpus" % (
                qid, doc_id, sorted(missing))
    print("ground truth verified against corpus (%d questions)" % len(EXPECTED))


def split_claims(answer: str) -> list:
    """[(claim_text, tag_inner)] per citation-tag occurrence."""
    out, prev = [], 0
    for m in CITE_TAG_RE.finditer(answer):
        out.append((answer[prev:m.start()], m.group(1)))
        prev = m.end()
    return out


DOC_OF = {"Act": "act2018", "Constitution": "constitution1999",
          "Factsheet": "factsheet2020"}


def eval_question(qid, question, rec, hits, ret) -> dict:
    exp = EXPECTED[qid]
    exp_pairs = {(d, n) for d, ns in exp.items() for n in ns}
    ret_pairs = {(h.doc_id, n) for h in hits for n in ref_nums(h.ref)}
    recall = len(exp_pairs & ret_pairs) / len(exp_pairs)
    rel_hits = sum(1 for h in hits
                   if ref_nums(h.ref) & exp.get(h.doc_id, set()))
    precision = rel_hits / len(hits) if hits else 0.0

    out = {"id": qid, "recall": round(recall, 3),
           "precision": round(precision, 3),
           "exp_found": sorted("%s:%s" % p for p in exp_pairs & ret_pairs),
           "exp_missed": sorted("%s:%s" % p for p in exp_pairs - ret_pairs)}
    if rec["refused"]:
        # Strict-prompt faithfulness: declining with empty hands is faithful;
        # declining while holding the answer is not.
        out.update({"refused": True,
                    "faithfulness_auto": 1.0 if not (exp_pairs & ret_pairs) else 0.0,
                    "faithfulness_audited": 1.0 if not (exp_pairs & ret_pairs) else 0.0,
                    "coverage": None, "claims": []})
        return out

    answer = rec["answer_full"] or ""
    claims = []
    for text, tag in split_claims(answer):
        m = re.match(r"(Act|Constitution|Factsheet) (.+)", tag)
        assert m is not None  # tags come from CITE_TAG_RE, always match
        doc_id, refbit = m.group(1), m.group(2)
        doc_id = DOC_OF[doc_id]
        num_strs = NUM_RE.findall(refbit)
        nums = {int(n) for n in num_strs}
        pool = " ".join(h.text for h in hits if h.doc_id == doc_id)
        numbers_ok = all(n in pool for n in num_strs) if nums else True
        if nums:
            ctx = " ".join(h.text for h in hits
                           if h.doc_id == doc_id and ref_nums(h.ref) & nums)
        else:  # 'general' tag: whole-doc context, overlap only
            ctx = pool
        cw, xw = content_stems(text[-400:]), content_stems(ctx)
        overlap = round(len(cw & xw) / len(cw), 3) if cw else 1.0
        supported = bool(numbers_ok and (not cw or overlap >= OVERLAP_FLOOR))
        flagged = any(f[0] == qid and f[1] in tag and f[2] in text.lower()
                      for f in MANUAL_FLAGS)
        claims.append({"tag": tag, "numbers_ok": numbers_ok,
                       "overlap": overlap, "supported_auto": supported,
                       "manual_flag": flagged,
                       "supported_audited": supported and not flagged,
                       "claim_tail": " ".join(text.split())[-120:]})
    fa = sum(c["supported_auto"] for c in claims) / len(claims) if claims else 1.0
    fu = sum(c["supported_audited"] for c in claims) / len(claims) if claims else 1.0
    ans_words = content_stems(CITE_TAG_RE.sub(" ", answer))
    q_words = content_stems(question)
    cov = len(q_words & ans_words) / len(q_words) if q_words else 1.0
    # Reverse retrieval: the answer as a query must land on its own support.
    rev = ret.query(answer, k=3)[:3]
    rev_rel = (sum(1 for h in rev
                   if ref_nums(h.ref) & exp.get(h.doc_id, set()))
               / len(rev)) if rev else 0.0
    out.update({"refused": False, "claims": claims,
                "faithfulness_auto": round(fa, 3),
                "faithfulness_audited": round(fu, 3),
                "coverage": round(cov, 3),
                "reverse_rel": round(rev_rel, 3),
                "cov_missed": sorted(q_words - ans_words)})
    return out


def main() -> None:
    questions = load_questions()
    assert len(questions) == 10
    docs = build_corpus()
    print("corpus: %s" % {k: len(v) for k, v in docs.items()})
    verify_ground_truth(docs)
    ret = PerDocRetriever(docs)
    recs = {r["id"]: r for r in json.loads(
        TRANSCRIPT.read_text(encoding="utf-8")) if r["id"].startswith("Q")}

    rows = [eval_question("Q%d" % (i + 1), q, recs["Q%d" % (i + 1)],
                          ret.query(q, k=3)[:6], ret)
            for i, q in enumerate(questions)]
    print("\n== PER-QUESTION (retrieval live/offline; answers frozen v2) ==")
    print("  %-4s %-6s %-6s %-6s %-6s %-6s %-6s  missed-expected" % (
        "id", "recall", "prec", "faith", "faithA", "cover", "revrel"))
    for r in rows:
        cov = ("%.3f" % r["coverage"]) if r["coverage"] is not None else "n/a(ref)"
        rev = ("%.3f" % r["reverse_rel"]) if r.get("reverse_rel") is not None else "n/a(ref)"
        print("  %-4s %-6.3f %-6.3f %-6.3f %-6.3f %-6s %-6s  %s" % (
            r["id"], r["recall"], r["precision"], r["faithfulness_auto"],
            r["faithfulness_audited"], cov, rev,
            ",".join(r["exp_missed"]) or "-"))
    print("\n== COVERAGE-MISS WORDS (artifact diagnosis: paraphrase, not off-topic) ==")
    for r in rows:
        if r.get("cov_missed"):
            print("  %s missing from answer: %s" % (r["id"], sorted(r["cov_missed"])))
    answered = [r for r in rows if not r["refused"]]
    mean = lambda k: sum(r[k] for r in answered) / len(answered)
    m_recall = sum(r["recall"] for r in rows) / len(rows)
    m_fa = sum(r["faithfulness_audited"] for r in rows) / len(rows)
    m_cov = mean("coverage")
    m_rev = mean("reverse_rel")
    print("\n== MEANS vs SPEC TARGETS ==")
    print("  recall>0.75 (context):            %.3f %s" % (
        m_recall, "PASS" if m_recall > 0.75 else "FAIL"))
    print("  faithfulness_audited>0.85:        %.3f %s" % (
        m_fa, "PASS" if m_fa > 0.85 else "FAIL"))
    print("  reverse_rel>0.80 (answer relev.): %.3f %s" % (
        m_rev, "PASS" if m_rev > 0.80 else "FAIL"))
    print("  (coverage floor, ungated: %.3f -- punishes paraphrase, "
          "diagnosed metric artifact)" % m_cov)
    print("  (precision diagnostic, ungated: %.3f -- per-doc merging "
          "trades it away by design)" % (
              sum(r["precision"] for r in rows) / len(rows)))

    out = ROOT / "scripts" / ("eval_phase06_results_%s.json"
                              % date.today().isoformat())
    for a in sys.argv[1:]:
        if a.startswith("--out="):
            out = Path(a[len("--out="):])
            if not out.is_absolute():
                out = ROOT / out
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print("wrote %s (%d records)" % (out, len(rows)))


if __name__ == "__main__":
    main()
