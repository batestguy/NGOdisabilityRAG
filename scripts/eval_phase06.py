"""Phase 06 custom eval -- zero-LLM proxies for the three RAGAS spec metrics.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\eval_phase06.py [--out=FILE]
  (from D:\\NGORAG; default out scripts/eval_phase06_results_<date>.json)
  ... --corpus=<ver>  evaluate a specific corpus version. EQUALS FORM ONLY.

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

import hashlib
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
from evalset import (  # noqa: E402
    assert_frozen10_matches_notebook,
    expected_map,
    load_eval_set,
)
from rag import CITE_TAG_RE, CORPUS_VERSION, build_corpus  # noqa: E402
from retrieve import PerDocRetriever, select_top, stem  # noqa: E402

TRANSCRIPT = (ROOT / "scripts"
              / "test_phase02_results_cite-strict-v2-fixA2_2026-09-10.json")

# Ground truth from CORPUS inspection (runtime-verified below, never from answers):
#  Q1 fines live in Act cl.1 (+N100k tail cl.2) and factsheet Section 1/1(2)/2.
#  Q5 penalty clauses found by corpus hunt: cl.1/2 (N100k/N1M), cl.8(3)
#    (approval offence), cl.9,10 (N5,000/day), cl.13 (parking), cl.29,30 (N50k).
#  Q6 Act cl.10 is awareness-programmes (NOT vehicles) -- expected is cl.11 only.
#  Q9 s.33 is a bare TOC line ("33. Right to life. 34 Right to dignity..."),
#    explicitly NOT expected for dignity; s.34 (body) + s.17 are.
#  Q10 s.46 holds the legal-aid provision; factsheet S39 is commission powers.
#
# The literal moved to data/eval/questions.json in Phase 09 (M2). It was
# GENERATED from the literal that used to sit here, not retyped, and every line
# of the provenance block above is mirrored into that file's per-question
# `note` field so the reasoning travels with the data instead of living only in
# this comment. The values are unchanged: this module's output is byte-identical
# across the move, which is the refactor's proof.
#
# The point of the move is that ground truth now has ONE home shared with the
# held-out set, so eval_phase06 (frozen 10) and eval_heldout (held-out) cannot
# drift into measuring recall two different ways.
EXPECTED = expected_map(load_eval_set("frozen10"))

# Audited overrides from Phase 02 manual verdicts (qid, tag-sub, claim-word).
#
# EMPTY as of Phase 08 fix B (2026-09-11), and that is the point of fix B.
# Both entries existed because mechanical checks could not see TOC-line
# misattribution, so a human had to hand-write the verdict -- which meant
# faithfulness_audited 0.967 was only as trustworthy as this list, and a new
# misattribution of the same shape would have scored as faithful.
#
#   ("Q9",  "Constitution s. 33", "dignity")    -- already dead before fix B:
#       Phase 06 fix A demoted the "33. Right to life. 34 Right to dignity..."
#       TOC line to ref "general", so the fixA2 transcript stopped emitting
#       [Constitution s. 33]. Measured at baseline: Q9 faithA was already
#       1.000, i.e. this entry was suppressing nothing.
#   ("Q10", "Constitution s. 39", "high court") -- the live one. Now caught
#       MECHANICALLY: widening _is_toc_fragment demotes the orphan listing
#       chunk "46 Special jurisdiction of High Court and Legal aid" from
#       "s. 39" to "general", so no retrieved chunk carries ref 39, the
#       claim's cited-ref context is empty, and overlap falls to 0.0.
#
# Keep this list empty. If a future run needs an entry, that is a signal the
# mechanical layer has a hole -- fix the layer, do not grow the list.
MANUAL_FLAGS: list[tuple[str, str, str]] = []

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
    # min_per_doc=0 ON PURPOSE. This is a metric probe, not the user path: with
    # 3 slots and 3 docs a quota would force exactly one hit per doc and turn
    # reverse_rel into a different measurement. min_per_doc=0 makes select_top
    # fall straight through to global order, i.e. bit-identical to the [:3]
    # slice it replaces -- written as a call rather than a slice so the one
    # site that legitimately wants raw global order says so.
    rev = select_top(ret.query(answer, k=3), 3, min_per_doc=0)
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


# Digest of the results JSON this script writes on the v1 corpus. Phase 10 C
# claimed byte-identical eval output in prose; this makes the claim a gate.
#
# WINDOWS-SPECIFIC, deliberately. Path.write_text() opens in TEXT mode, so every
# "\n" json.dumps produced lands on disk as "\r\n" (594 CRLF pairs). The pinned
# digest is of THOSE BYTES. Hashing the in-memory string, or running on a
# platform that does not translate, gives a different and equally correct
# answer -- which is why the failure below explains itself instead of raising a
# bare AssertionError. Re-pin it only with a recorded reason.
#
# BOTH DIGESTS RE-PINNED AT PHASE E1b, 2026-09-20, AND THE REASON IS ANNOUNCED
# RATHER THAN DISCOVERED. E1b widened the shipping retrieval budget from
# k=3/doc, top_n=6 to k=4/doc, top_n=12 (see ask() in src/rag.py). The retrieval
# call in main() below is the one this script scores its context columns from, so
# every row's `recall` / `precision` / `exp_missed` changed and the results file
# necessarily hashes differently. That is the intended effect of the commit, not
# drift, and the gate did exactly its job: it FIRED on both corpora before these
# lines were touched.
#
# WHAT MOVED IS THE BUDGET, NOT THE CORPUS. audit_corpus.py's stdout is
# byte-identical across this commit; V2_CORPUS_SHA256 still measures
# 56e3e434...cef4 and v1's 25650238...e89a is equally untouched.
# The v1 arm's PUBLISHED numbers still reproduce exactly -- at the old budget.
# Its digest moved only because v1 and v2 share this one code path and the path
# changed; re-running this file at k=3/top_n=6 on --corpus=v1 returns
# ce716fb3...df5f19. So the v1 digest is not a v1 regression, it is v1 measured
# on the new instrument, and the old value is kept below so that distinction
# stays readable.
#
# Old values, superseded 2026-09-20 (both measured at k=3/doc, top_n=6):
#   v1  ce716fb3c1ea139b5e3a6885d732c5ebbd3f1b57981635f7d97da5911edf5f19
#   v2  10751076faa65a300d366932b8cdc7ef2e57bd2ce862cab950999313ed97e057
V1_RESULTS_SHA256 = ("12BDEBA001D21E838A3747281A108BCB8C77A165EFA8932A4500D573"
                     "516E444D").lower()

# The same gate for v2, pinned at D6 when the default flipped. Without it the
# check below would have gone quiet on the SHIPPING corpus the moment v2
# became the default, leaving only the retired corpus guarded -- the same
# inversion V2_CORPUS_SHA256 exists to prevent in audit_corpus.py. Re-measured
# twice at E1b's budget and identical both times; same CRLF caveat as above.
V2_RESULTS_SHA256 = ("2429CAFCD1385047385F7E990B931ECC81B9F40C5A0F5C9849D1FEF8"
                     "4EEDC0B9").lower()

RESULTS_SHA256 = {"v1": V1_RESULTS_SHA256, "v2": V2_RESULTS_SHA256}


def main() -> None:
    # EQUALS FORM ONLY (repo convention: the space form is silently ignored).
    corpus = next((a.split("=", 1)[1] for a in sys.argv[1:]
                   if a.startswith("--corpus=")), None)
    questions = load_questions()
    assert len(questions) == 10
    # Two independent sources of the frozen 10 must agree: the notebook literal
    # and data/eval/questions.json. Checked BEFORE any measurement, so a drifted
    # yardstick can never silently produce a number.
    assert_frozen10_matches_notebook()
    docs = build_corpus(corpus)
    print("corpus: %s" % {k: len(v) for k, v in docs.items()})
    verify_ground_truth(docs)
    ret = PerDocRetriever(docs)
    recs = {r["id"]: r for r in json.loads(
        TRANSCRIPT.read_text(encoding="utf-8")) if r["id"].startswith("Q")}

    # select_top, not [:12] -- the same merge ask() ships. A harness that slices
    # differently from ask() is measuring a system nobody ships. k=4/doc,
    # top_n=12 since Phase E1b (2026-09-20); was k=3, 6. The reverse_rel probe
    # above (k=3, 3, min_per_doc=0) is a DIFFERENT measurement on the generated
    # answer and is deliberately NOT moved with the shipping arm.
    rows = [eval_question("Q%d" % (i + 1), q, recs["Q%d" % (i + 1)],
                          select_top(ret.query(q, k=4), 12), ret)
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
    # Read BACK FROM DISK as bytes -- see V1_RESULTS_SHA256. The digest is of
    # the CRLF-translated file, not of the string we just serialised.
    got = hashlib.sha256(out.read_bytes()).hexdigest()
    print("wrote %s (%d records) sha256=%s" % (out, len(rows), got))
    stamp = corpus or CORPUS_VERSION
    want = RESULTS_SHA256.get(stamp)
    if want is None:
        raise SystemExit(
            "no results digest pinned for corpus %r. Every corpus version this "
            "script can run gets its own -- pin one, do not skip the gate."
            % stamp)
    if got != want:
        raise SystemExit(
            "eval_phase06 results digest DRIFT on corpus %s\n"
            "  recorded %s\n  measured %s\n" % (stamp, want, got) +
            "Every Phase 06 number published in this repo came from the "
            "recorded file. If you changed retrieval, this is a real "
            "regression -- do not re-pin to silence it.\n"
            "NOTE: this digest is WINDOWS-SPECIFIC. Path.write_text() writes "
            "CRLF here and the digest covers those bytes, so a Linux/macOS run "
            "will differ for that reason alone and is not evidence of drift.")


if __name__ == "__main__":
    main()
