"""Phase 09 M1 test: quota classifiers, model failover, cache bypass. ZERO network.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\test_phase09_ops.py  (from D:\\NGORAG)

WHY THIS IS AN INJECTION TEST, NOT A LIVE ONE
---------------------------------------------
The failover path cannot be proven by spending quota. A successful live call
proves only the happy path -- failover never fires -- and the ONLY way to make
it fire for real is to exhaust a daily cap, which costs a day of budget and
leaves the repo unable to run anything else. So the error is injected instead:
the genai client is monkeypatched to raise the 429s we have actually seen, and
the assertions are about what rag.py does with them.

PROVENANCE OF THE ERROR STRINGS (this matters -- an invented 429 would test the
classifier against the test author's idea of a 429, not Google's):

  DAILY CAP  : read verbatim at runtime from
               scripts/test_phase02_results_cite-strict-v2-fixA_2026-09-09.json,
               a real transcript from the day the generator's 20/day ran out.
               It carries quotaId `GenerateRequestsPerDayPerProjectPerModel-
               FreeTier`. Loaded from the file, never pasted, so it cannot rot.

  PER MINUTE : RECONSTRUCTED, and flagged as such. The 2026-09-11 judge run hit
               it, but its checkpoint file (the only place the raw text lived)
               was deleted after the run, and the surviving
               judge_phase06_results_*.json records verdicts only -- it contains
               no error strings at all. What the repo did durably record is the
               two fields the classifier keys on: quotaId
               `GenerateRequestsPerMinutePerProjectPerModel-FreeTier` and
               retryDelay ~37s (docs/phases/06_ragas_eval.md, LEARNING_JOURNAL
               2026-09-11). Those are spliced into the real daily-cap envelope
               above, so everything except the two recorded fields is genuine.
               If a per-minute 429 is ever captured verbatim again, swap it in.

Asserts:
  1. is_per_minute_429 / retry_delay classify the real strings correctly.
  2. daily-cap 429 + failover=True  -> fails over ONCE, model_used == FALLBACK.
  3. per-minute 429 + failover=True -> propagates (never failed over); ask()
     records llm_error and leaves the row PENDING.
  4. daily-cap 429 + failover=False (the default) -> stays pending. Opt-in is
     opt-in: a flash-lite answer is never served as flash by accident.
  5. use_cache=False -> no cache read AND no cache write.
  6. the cache keys on the model that ANSWERED, so a failover answer cannot be
     replayed later as an answer from the model that was asked.

Exits nonzero on ANY failure.
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import google.genai as genai  # noqa: E402
import rag  # noqa: E402
from bench_phase01 import load_questions  # noqa: E402 (SAME frozen 10Q set)
from rag import (  # noqa: E402
    FALLBACK_MODEL,
    MODEL_NAME,
    ask,
    build_corpus,
    generate_with_meta,
    is_per_minute_429,
    retry_delay,
)
from retrieve import PerDocRetriever  # noqa: E402

DAILY_SOURCE = (ROOT / "scripts"
                / "test_phase02_results_cite-strict-v2-fixA_2026-09-09.json")


def load_daily_429() -> str:
    """The real daily-cap 429, read out of a real transcript."""
    rows = json.loads(DAILY_SOURCE.read_text(encoding="utf-8"))
    for r in rows:
        err = r.get("llm_error") or ""
        if "429" in err and "PerDayPerProjectPerModel" in err:
            return err
    raise AssertionError("no daily-cap 429 found in %s" % DAILY_SOURCE)


def make_per_minute_429(daily: str) -> str:
    """Real envelope + the two fields the repo recorded for the RPM limit."""
    out = daily.replace("GenerateRequestsPerDayPerProjectPerModel-FreeTier",
                        "GenerateRequestsPerMinutePerProjectPerModel-FreeTier")
    out = out.replace("'retryDelay': '18s'", "'retryDelay': '37s'")
    out = out.replace("'retryDelay': '11s'", "'retryDelay': '37s'")
    out = out.replace("'retryDelay': '54s'", "'retryDelay': '37s'")
    assert out != daily, "per-minute splice did not change the string"
    return out


# ---------------------------------------------------------------------------
# Fake genai client. Records every (model) it is asked for, then does whatever
# the installed script says -- return text, or raise a recorded 429.
# ---------------------------------------------------------------------------
CALLS: list[str] = []
PROMPTS: list[str] = []  # H8a.4: the prompt text each call was given
SCRIPT = [None]  # callable(model) -> str, or raises


class _Resp:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    def generate_content(self, model, contents):  # noqa: ARG002
        CALLS.append(model)
        PROMPTS.append(contents)
        return _Resp(SCRIPT[0](model))


class _FakeClient:
    def __init__(self, api_key=None, **kw):  # noqa: ARG002
        self.models = _FakeModels()


def install(script) -> None:
    """Arm the fake client with a per-model behaviour and clear the log."""
    CALLS.clear()
    PROMPTS.clear()
    SCRIPT[0] = script


def fail_then_ok(err: str):
    """MODEL_NAME raises `err`; FALLBACK_MODEL answers."""
    def _script(model):
        if model == MODEL_NAME:
            raise RuntimeError(err)
        return "FALLBACK ANSWER [Act cl. 1]"
    return _script


def always_fail(err: str):
    def _script(model):  # noqa: ARG001
        raise RuntimeError(err)
    return _script


def main() -> int:
    failures: list[str] = []

    def check(ok: bool, label: str) -> None:
        print("[%s] %s" % ("PASS" if ok else "FAIL", label))
        if not ok:
            failures.append(label)

    daily = load_daily_429()
    per_min = make_per_minute_429(daily)

    # No real key is needed (the client is fake), but generate_with_meta checks
    # for one before it builds a client. A dummy keeps the test independent of
    # whether the machine happens to have credentials configured.
    import os
    os.environ["GOOGLE_API_KEY"] = "test-key-never-used-fake-client"

    # Every cache read/write in this run goes to a throwaway file. The real
    # scripts/.answer_cache.json must not be read (stale hits would mask a
    # failover) and must not be written (a fake answer must never leak into it).
    tmpdir = tempfile.TemporaryDirectory()
    rag.CACHE_PATH = Path(tmpdir.name) / "answer_cache.json"
    genai.Client = _FakeClient

    print("== 1. QUOTA CLASSIFIERS (real error strings) ==")
    check(is_per_minute_429(daily) is False,
          "daily-cap 429 classified as NOT per-minute")
    check(is_per_minute_429(per_min) is True,
          "per-minute 429 classified as per-minute")
    check("429" in daily and "RESOURCE_EXHAUSTED" in daily,
          "daily string is a genuine 429 envelope")
    # The server's own hint wins over blind backoff; 18s was the recorded value.
    check(abs(retry_delay(daily, 0) - 21.0) < 1e-9,
          "retry_delay honours the server hint (18s -> 21.0s incl. slack)")
    check(abs(retry_delay(per_min, 0) - 40.0) < 1e-9,
          "retry_delay honours the 37s RPM hint (-> 40.0s)")
    check(abs(retry_delay("503 UNAVAILABLE", 2) - 32.0) < 1e-9,
          "retry_delay falls back to exponential backoff with no hint")
    check(abs(retry_delay("503 UNAVAILABLE", 9) - 60.0) < 1e-9,
          "retry_delay backoff is capped at 60s")

    print("\n== 2. DAILY-CAP 429 + failover=True -> FAILS OVER ONCE ==")
    install(fail_then_ok(daily))
    answer, cached, model_used = generate_with_meta(
        "PROMPT-A", model=MODEL_NAME, use_cache=False, failover=True)
    check(answer == "FALLBACK ANSWER [Act cl. 1]", "failover returned an answer")
    check(model_used == FALLBACK_MODEL,
          "model_used == FALLBACK_MODEL (%s)" % FALLBACK_MODEL)
    check(cached is False, "failover answer is not marked cached")
    check(CALLS == [MODEL_NAME, FALLBACK_MODEL],
          "exactly one failover attempt, in order: %s" % CALLS)

    # ...and it can never fail over twice: if the fallback also 429s, that
    # propagates rather than looping.
    install(always_fail(daily))
    try:
        generate_with_meta("PROMPT-B", model=MODEL_NAME, use_cache=False,
                           failover=True)
        check(False, "fallback also failing must propagate")
    except RuntimeError:
        check(CALLS == [MODEL_NAME, FALLBACK_MODEL],
              "fallback failure propagates after exactly 2 calls: %s" % CALLS)

    print("\n== 3. PER-MINUTE 429 -> PROPAGATES, NEVER FAILS OVER ==")
    install(fail_then_ok(per_min))
    try:
        generate_with_meta("PROMPT-C", model=MODEL_NAME, use_cache=False,
                           failover=True)
        check(False, "per-minute 429 must propagate, not fail over")
    except RuntimeError as e:
        check(is_per_minute_429("%s" % e), "the propagated error is the RPM one")
        check(CALLS == [MODEL_NAME],
              "no fallback call was made (%s) -- RPM is retried, not dodged"
              % CALLS)

    print("\n== 4. ask() BEHAVIOUR (real retrieval, injected LLM) ==")
    docs = build_corpus()
    print("  corpus: %s" % {k: len(v) for k, v in docs.items()})
    ret = PerDocRetriever(docs)
    q = load_questions()[0]  # a frozen question, so it clears MIN_SCORE
    print("  question: %r" % q)

    # 4a. per-minute 429 -> pending row, never faked.
    install(fail_then_ok(per_min))
    res = ask(q, retriever=ret, use_cache=False, failover=True)
    check(res["answer"] is None, "RPM 429: answer is None (row PENDING)")
    check(res["llm_used"] is False, "RPM 429: llm_used False")
    check("llm_error" in res and "429" in res["llm_error"],
          "RPM 429: llm_error recorded")
    check(res["model_used"] is None and res["route"]["model_used"] is None,
          "RPM 429: model_used is None -- nothing answered")
    check(res["refused"] is False,
          "RPM 429: not reported as a refusal (pending != refused)")
    check(CALLS == [MODEL_NAME], "RPM 429: no failover from ask() either")

    # 4b. daily-cap + failover=False (the DEFAULT) -> still pending.
    install(fail_then_ok(daily))
    res = ask(q, retriever=ret, use_cache=False)
    check(res["answer"] is None, "default (no failover): answer None (PENDING)")
    check(res["model_used"] is None, "default: model_used None")
    check(CALLS == [MODEL_NAME],
          "default: fallback model NOT called -- opt-in is opt-in (%s)" % CALLS)

    # 4c. daily-cap + failover=True -> answered, and the row says by whom.
    install(fail_then_ok(daily))
    res = ask(q, retriever=ret, use_cache=False, failover=True)
    check(res["answer"] == "FALLBACK ANSWER [Act cl. 1]",
          "failover=True: answer returned")
    check(res["llm_used"] is True, "failover=True: llm_used True")
    check(res["model_used"] == FALLBACK_MODEL,
          "failover=True: top-level model_used == FALLBACK_MODEL")
    check(res["route"]["model_used"] == FALLBACK_MODEL,
          "failover=True: route.model_used == FALLBACK_MODEL")
    check(res["route"]["model"] == MODEL_NAME,
          "failover=True: route.model still records what was REQUESTED")

    # 4d. the happy path still reports the model that answered.
    install(lambda model: "PLAIN ANSWER [Act cl. 1]")
    res = ask(q, retriever=ret, use_cache=False)
    check(res["model_used"] == MODEL_NAME,
          "happy path: model_used == MODEL_NAME")

    print("\n== 5. use_cache=False: NO READ, NO WRITE ==")
    rag.CACHE_PATH.unlink(missing_ok=True)
    # Seed a sentinel under the exact key a cached read would hit.
    rag._cache_write(rag._cache_key("PROMPT-D", MODEL_NAME), "PROMPT-D",
                     MODEL_NAME, "SENTINEL FROM CACHE")
    before = rag.CACHE_PATH.read_text(encoding="utf-8")
    install(lambda model: "FRESH ANSWER")
    answer, cached, model_used = generate_with_meta(
        "PROMPT-D", model=MODEL_NAME, use_cache=False)
    check(answer == "FRESH ANSWER" and cached is False,
          "use_cache=False did not READ the seeded entry")
    check(CALLS == [MODEL_NAME], "use_cache=False made the real call")
    check(rag.CACHE_PATH.read_text(encoding="utf-8") == before,
          "use_cache=False did not WRITE (cache file byte-identical)")
    # Control: with the cache ON the same prompt is served from it, no call.
    install(lambda model: "SHOULD NOT BE CALLED")
    answer, cached, model_used = generate_with_meta(
        "PROMPT-D", model=MODEL_NAME, use_cache=True)
    check(answer == "SENTINEL FROM CACHE" and cached is True and CALLS == [],
          "control: use_cache=True DOES read the same entry (cache works)")

    print("\n== 6. CACHE KEYS ON THE MODEL THAT ANSWERED ==")
    rag.CACHE_PATH.unlink(missing_ok=True)
    install(fail_then_ok(daily))
    answer, cached, model_used = generate_with_meta(
        "PROMPT-E", model=MODEL_NAME, use_cache=True, failover=True)
    check(model_used == FALLBACK_MODEL, "failover answer produced with cache on")
    data = json.loads(rag.CACHE_PATH.read_text(encoding="utf-8"))
    models = {e["model"] for e in data.values()}
    check(models == {FALLBACK_MODEL},
          "cache stored the answer under %s only, not %s (%s)"
          % (FALLBACK_MODEL, MODEL_NAME, sorted(models)))
    check(rag._cache_read(rag._cache_key("PROMPT-E", MODEL_NAME)) is None,
          "a flash-lite answer is NOT replayable as a flash answer")
    check(rag._cache_read(rag._cache_key("PROMPT-E", FALLBACK_MODEL))
          == answer, "it IS replayable as a flash-lite answer")

    # Guard on the redirect itself: if a future edit drops the tmpdir line,
    # every assertion above would start reading and writing the real cache.
    check(rag.CACHE_PATH.parent != (ROOT / "scripts"),
          "the real answer cache was never touched by this run")
    tmpdir.cleanup()

    # -----------------------------------------------------------------------
    # 7. CHAT PROMPT INVARIANTS (Phase 10 B). Zero network, zero corpus --
    #    synthetic Hits, because what is under test is the prompt STRING.
    # -----------------------------------------------------------------------
    print("\n== 7. CHAT: history=None IS BYTE-IDENTICAL, AND STAYS OUT OF THE CACHE ==")
    from retrieve import Hit  # noqa: E402

    hits = [Hit("act2018", "cl. 28", "28. (1) A person with disability has the "
                "right to work on an equal basis with others.", 0.4213),
            Hit("constitution1999", "s. 42", "42. (1) A citizen of Nigeria ...",
                0.2011)]

    # The pre-chat recipe, spelled out. This is deliberately a SECOND copy of
    # the old assembly order rather than a call into rag: the claim being tested
    # is that build_prompt still produces exactly this, so deriving the
    # expectation from build_prompt itself would test nothing.
    def pre_chat_prompt(question, hits, plain=False):
        lines = [rag.SYSTEM_PROMPT]
        if plain:
            lines.append(rag.PLAIN_SUFFIX)
        lines.append("\nRetrieved excerpts (cite VERBATIM, quirks included):")
        for h in hits:
            lines.append("\n%s (relevance %.3f):\n%s"
                         % (rag.cite_tag(h.doc_id, h.ref), h.score, h.text))
        lines.append("\nQuestion: %s" % question)
        lines.append("Answer (every factual claim cited, or the exact "
                     "no-answer sentence):")
        return "\n".join(lines)

    Q = "What does the Act say about my right to work?"
    for plain in (False, True):
        want = pre_chat_prompt(Q, hits, plain=plain)
        for label, hist in (("None", None), ("empty list", []),
                            ("blank-question turns", [{"question": "  ",
                                                       "answer": None}])):
            check(rag.build_prompt(Q, hits, plain=plain, history=hist) == want,
                  "history=%s, plain=%s -> byte-identical to the pre-chat prompt"
                  % (label, plain))
    # Why this one matters more than it looks: the answer cache keys on
    # sha256(model + NUL + the WHOLE rendered prompt). One stray newline here
    # and every cached answer silently misses, and every published transcript
    # stops describing a prompt this code can still produce.

    hist = [{"question": Q, "answer": "You have the right to work on an equal "
                                      "basis with others. [Act cl. 28]"}]
    chat_prompt = rag.build_prompt("so can they fire me?", hits, history=hist)
    check(chat_prompt != pre_chat_prompt("so can they fire me?", hits),
          "history that HAS content does change the prompt (control)")
    check("Earlier in this conversation" in chat_prompt,
          "history is rendered when present")
    check(chat_prompt.index("Earlier in this conversation")
          < chat_prompt.rindex("\nQuestion: "),
          "history renders BEFORE the final 'Question: ' line")

    # THE PRIVACY ASSERT. _cache_write stores prompt.rsplit("Question: ", 1)[-1]
    # -- the current question line and nothing else. If history ever moves after
    # that split point, scripts/.answer_cache.json starts recording whole
    # conversations to disk, from a population that discloses abuse and
    # coercion. This assertion is the thing standing between those two states.
    cached_line = chat_prompt.rsplit("Question: ", 1)[-1].split("\n", 1)[0]
    check(cached_line == "so can they fire me?",
          "the cache would store ONLY the current question line")
    check("right to work" not in cached_line and "[Act cl. 28]" not in cached_line,
          "no prior turn and no prior citation leaks into the cached line")

    check("You may cite ONLY the retrieved excerpts in THIS turn."
          in chat_prompt,
          "the chat-only per-turn citation rule is in the prompt")
    check(rag.CHAT_PROMPT_VERSION == "chat-cite-strict-v2"
          and rag.PROMPT_VERSION == "cite-strict-v3",
          "chat gets its OWN prompt version, so single-turn transcripts stay "
          "comparable and the two can never share a cache key")
    check("8. If the question asks broadly" in rag.SYSTEM_PROMPT
          and 'Tags ending in "general" do not count' in rag.SYSTEM_PROMPT
          and "8. If the question asks broadly" in chat_prompt,
          "rule 8 (answer-shape floor, numbered tags only) is in BOTH the "
          "single-turn and the chat prompt (Phase G0)")

    print("\n== 8. CHAT: cross_turn_drift ACTUALLY FIRES (behavioural, zero network) ==")
    # Until Phase G0 this function compared "Act cl. 28" (extract_citations'
    # regex group) with "[Act cl. 28]" (cite_tag) and returned [] for EVERY
    # answer; the only prior test checked that the call existed in app.py's
    # source. G4's drift metric would have read 0 by construction.
    import chat  # noqa: E402
    prior = [{"question": Q, "answer": "x", "tags": [rag.cite_tag("act2018", "cl. 28")]}]
    now = [Hit("act2018", "cl. 1", "", 0.3)]
    check(chat.cross_turn_drift("You can't be fired. [Act cl. 28]", prior, now)
          == ["[Act cl. 28]"],
          "a tag shown in an EARLIER turn but not this one is reported as drift")
    check(chat.cross_turn_drift("Fines apply. [Act cl. 1]", prior, now) == [],
          "a tag this turn DID retrieve is not drift")
    check(chat.cross_turn_drift("Something. [Act cl. 50]", prior, now) == [],
          "a tag no turn retrieved is not drift (verify_citations owns that case)")
    check(chat.cross_turn_drift(None, prior, now) == [],
          "a pending answer (None) has no drift")

    print("\n== 8b. CITATIONS: [Regs reg. N] ROUND-TRIPS (H8a.2 F3, zero network) ==")
    # Corpus v3 adds accessregs2023. Its tag shape must be visible to every
    # citation check in the SAME commit as the corpus, or a fabricated regulation
    # number would pass verify_citations silently. Synthetic Hits: under test is
    # the tag plumbing (cite_tag -> CITE_TAG_RE -> doc_of -> drift), not retrieval.
    regs_hits = [Hit("accessregs2023", "reg. 24", "", 0.3),
                 Hit("accessregs2023", "general", "", 0.2),
                 Hit("act2018", "cl. 56", "", 0.2)]
    check(rag.cite_tag("accessregs2023", "reg. 24") == "[Regs reg. 24]"
          and rag.cite_tag("accessregs2023", "general") == "[Regs general]",
          "cite_tag builds [Regs reg. N] / [Regs general]")
    ans = "Parking is reserved [Regs reg. 24], made under [Act cl. 56] ([Regs general])."
    check(rag.extract_citations(ans) == ["Regs reg. 24", "Act cl. 56", "Regs general"],
          "CITE_TAG_RE extracts the Regs shapes alongside the old ones")
    check([c["number_ok"] for c in rag.verify_citations(ans, regs_hits)] == [True] * 3,
          "verify_citations passes Regs tags whose ref was retrieved")
    check([c["number_ok"] for c in rag.verify_citations("[Regs reg. 25]", regs_hits)]
          == [False], "a Regs number nobody retrieved fails (fabrication caught)")
    check([c["number_ok"] for c in rag.verify_citations(
               "[Regs reg. 56] [Act cl. 24]", regs_hits)] == [False, False],
          "doc_of keeps the numbering schemes apart: Act cl. 56 cannot satisfy "
          "[Regs reg. 56], nor Regs reg. 24 satisfy [Act cl. 24]")
    old = "[Act cl. 28] [Constitution s. 42] [Factsheet Section 19] [Act general]"
    old_hits = [Hit("act2018", "cl. 28", "", 0.3), Hit("constitution1999", "s. 42", "", 0.3),
                Hit("factsheet2020", "Section 19", "", 0.3)]
    check([c["number_ok"] for c in rag.verify_citations(old, old_hits)] == [True] * 4
          and [c["number_ok"] for c in rag.verify_citations(old, [])] == [False] * 3 + [True],
          "the pre-existing tag shapes verify exactly as before")
    regs_prior = [{"question": Q, "answer": "x",
                   "tags": [rag.cite_tag("accessregs2023", "reg. 24")]}]
    check(chat.cross_turn_drift("Parking. [Regs reg. 24]", regs_prior, now)
          == ["[Regs reg. 24]"],
          "cross_turn_drift reports a Regs tag re-cited from an earlier turn")

    print("\n== 8c. BUDGET BY CORPUS VERSION (H8a.4 F1, zero network) ==")
    # top_n == K_PER_DOC x n_docs per version (the E1b "no cut" rule), and both
    # shipping callers (ask, app.offline_legal_hits) take it from the corpus in use.
    import inspect as _inspect
    import retrieve as _retrieve
    sys.path.insert(0, str(ROOT))
    import app as _app
    docs3 = build_corpus("v3")
    ret3 = PerDocRetriever(docs3)
    for v, d in (("v1", build_corpus("v1")), ("v2", docs), ("v3", docs3)):
        check(rag.TOP_N_BY_VERSION[v] == rag.K_PER_DOC * len(d)
              == rag.K_PER_DOC * rag.N_DOCS_BY_VERSION[v],
              "%s: top_n %d == 4 x %d docs" % (v, rag.TOP_N_BY_VERSION[v], len(d)))
    check(rag.CORPUS_VERSION == "v2" and rag.default_top_n() == 12
          and rag.default_top_n(ret) == 12 and rag.default_top_n(ret3) == 16,
          "default_top_n: shipping v2 -> 12, v2 retriever -> 12, v3 retriever -> 16")
    seen_n: list[int] = []
    orig_rag_st, orig_ret_st = rag.select_top, _retrieve.select_top

    def spy(cands, top_n, **kw):
        seen_n.append(top_n)
        return orig_ret_st(cands, top_n, **kw)

    rag.select_top = _retrieve.select_top = spy
    try:
        ask(q, retriever=ret, use_llm=False)
        _app.offline_legal_hits(q, ret)
        ask(q, retriever=ret3, use_llm=False)
        _app.offline_legal_hits(q, ret3)
        ask(q, retriever=ret, use_llm=False, top_n=7)
    finally:
        rag.select_top, _retrieve.select_top = orig_rag_st, orig_ret_st
    check(seen_n == [12, 12, 16, 16, 7],
          "ask/offline_legal_hits budget v2 12/12, v3 16/16, explicit kept: %s" % seen_n)

    print("\n== 8d. LLM CONTEXT EXCLUDES accessregs2023 UNTIL H8a.6 (zero network) ==")
    note = rag.DOC_STATUS_NOTES["accessregs2023"]
    qr = "Is there a fine for not following the accessibility regulations?"
    shown3 = _app.offline_legal_hits(qr, ret3)["excerpts"]
    check(any(e["doc_id"] == "accessregs2023" for e in shown3)
          and any(e["doc_id"] != "accessregs2023" for e in shown3),
          "v3 offline display still shows Regs cards (and others) for %r" % qr)
    install(lambda model: "Fines apply [Act cl. 56] [Regs reg. 168].")
    res = ask(qr, retriever=ret3, use_cache=False)
    check(len(PROMPTS) == 1 and "[Regs" not in PROMPTS[0]
          and "Retrieved excerpts" in PROMPTS[0] and "[Act cl." in PROMPTS[0],
          "v3 single-turn prompt carries no [Regs tag (other docs kept)")
    # Every sentence of the note, not a bare figure: the Act's own cl. 28 text
    # says "N500,000" and legitimately reaches the prompt.
    note_sents = [s.strip() for s in note.split(". ") if len(s.strip()) > 20]
    check(len(note_sents) >= 5 and not any(s in PROMPTS[0] for s in note_sents)
          and "About this source" not in PROMPTS[0],
          "v3 prompt carries no status-note text (%d sentences checked)"
          % len(note_sents))
    check([c["tag"] for c in res["cite_check"] if not c["number_ok"]] == ["Regs reg. 168"],
          "cite check runs on the LLM hits only: a [Regs] tag fails as unretrieved")
    hist = [{"question": "Can my employer sack me?", "answer": "No [Act cl. 28]."}]
    install(lambda model: "CHAT ANSWER [Act cl. 56]")
    ask(qr, retriever=ret3, use_cache=False, history=hist, failover=True)
    check(len(PROMPTS) == 1 and "[Regs" not in PROMPTS[0]
          and "S.I. No. 51" not in PROMPTS[0]
          and "Earlier in this conversation" in PROMPTS[0],
          "v3 chat prompt (failover on) carries no [Regs tag and no note")
    install(fail_then_ok(daily))
    res = ask(qr, retriever=ret3, use_cache=False, failover=True)
    check(CALLS == [MODEL_NAME, FALLBACK_MODEL] and len(PROMPTS) == 2
          and all("[Regs" not in p for p in PROMPTS),
          "failover re-sends the same Regs-free prompt to the fallback model")

    class _RegsOnly:
        docs = {"accessregs2023": []}

        def query(self, text, k=4):  # noqa: ARG002
            return [Hit("accessregs2023", "reg. 168", "Penalty text", 0.4)]

    install(lambda model: "SHOULD NOT BE CALLED")
    res = ask(qr, retriever=_RegsOnly(), use_cache=False)
    check(CALLS == [] and res["answer"] is None and res["refused"] is False
          and "llm_error" in res and res["model_used"] is None,
          "only-Regs hits: no model call, row PENDING with llm_error (never faked)")
    install(lambda model: "PLAIN ANSWER [Act cl. 1]")
    res = ask(q, retriever=ret, use_cache=False)
    v2_hits = [h for h in rag.select_top(ret.query(q, k=4), 12, min_per_doc=1,
                                         floor=rag.MIN_SCORE)
               if h.score >= rag.MIN_SCORE]
    check(PROMPTS == [rag.build_prompt(q, v2_hits)]
          and rag.llm_context_hits(v2_hits) == v2_hits,
          "v2: prompt byte-identical to build_prompt(all hits) -- a no-op by construction")
    ai_src = _inspect.getsource(_app._run_ai_turn)
    check("hits = llm_context_hits(" in ai_src
          and "verify_citations(res[\"answer\"], hits)" in ai_src
          and "cross_turn_drift(res[\"answer\"], prior, hits)" in ai_src,
          "app._run_ai_turn verifies citations/drift against llm_context_hits")

    print("\n== 9. CHAT: relative 'that' is NOT an unbound pronoun (H1a, zero network) ==")
    # Seen on the live smoke after the 2026-10-15 deploy: "an organisation that
    # can help me" was read as unbound 'that' and carried the previous legal
    # turn into a help query. Regression conversation: CD13 (chat_dev).
    legal = [{"question": "What does the Act say about discrimination?"}]
    help_q = "I am deaf and I live in Lagos, is there an organisation that can help me?"
    q_out, meta = chat.contextualise(legal, help_q)
    check(q_out == help_q and meta["carried"] is False,
          "relative 'that' (noun + that + modal) leaves the help turn unchanged: %r"
          % meta["reason"])
    check("that" not in chat.unbound_pronouns(help_q),
          "unbound_pronouns() skips relative 'that'")
    # Controls: a genuinely unbound 'that' must still resolve.
    for q in ("what about that?", "is that legal?",
              "do I need a certificate for that?",       # CD5.t2
              "where do I take a case like that?",       # CD6.t3
              "does that cover forced labour too?"):     # CT3.t2
        _, m = chat.contextualise(legal, q)
        check(m["carried"] and "that" in m["pronouns"],
              "unbound 'that' still carries: %r -> %r" % (q, m["reason"]))

    # --- H7: counts-only telemetry (docs/phases/16 H7) ----------------------
    print("\n== H7. TELEMETRY: STDOUT ONLY, NO TEXT WITHOUT OPT-IN ==")
    import contextlib
    import inspect
    import io
    import json as _json
    import telemetry
    secret = "My boss beat me because I am blind, what can I do?"

    def captured(rec):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            telemetry.emit(rec)
        return buf.getvalue()

    out_off = captured(telemetry.turn_record("abc123", "legal", False, 0.27, 9, 0,
                                             False, secret, share_text=False))
    check(out_off.startswith(telemetry.PREFIX) and out_off.count("\n") == 1,
          "telemetry is one prefixed stdout line")
    rec_off = _json.loads(out_off[len(telemetry.PREFIX):])
    check(secret not in out_off and "boss" not in out_off and "q" not in rec_off,
          "no question text in the line without the opt-in")
    check(set(rec_off) <= telemetry.TURN_FIELDS and rec_off["top"] == "0.20-0.30",
          "turn line carries only allowed fields, score as a band: %s" % sorted(rec_off))
    out_on = captured(telemetry.turn_record("abc123", "legal", False, 0.27, 9, 0,
                                            False, secret, share_text=True))
    check(_json.loads(out_on[len(telemetry.PREFIX):]).get("q") == secret,
          "with the explicit opt-in, that turn's question text is included")
    long_q = "x" * 1000
    check(len(telemetry.turn_record("i", "legal", False, None, 0, 0, False, long_q,
                                    True)["q"]) == telemetry.QUESTION_MAX,
          "opted-in text is truncated to %d chars" % telemetry.QUESTION_MAX)
    h = _json.loads(captured(telemetry.helpful_record("abc123", "Yes"))[len(telemetry.PREFIX):])
    check(set(h) <= telemetry.HELPFUL_FIELDS and h["helpful"] == "yes",
          "helpful line carries only allowed fields")
    tsrc = inspect.getsource(telemetry).split('"""', 2)[2]  # code, not the docstring
    check(not any(w in tsrc for w in ("import requests", "urllib", "http.client",
                                      "socket", "open(", "session_state")),
          "telemetry module: no network, no file, never reads session_state")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import app
    run_src = inspect.getsource(app.run)
    hist_src = inspect.getsource(app.render_history)
    replay_src = inspect.getsource(app.replay_turn)
    check("emit_turn_signal(" in run_src and "emit_turn_signal(" not in hist_src
          and "emit_turn_signal(" not in replay_src,
          "a turn line is emitted for a NEW turn only, never on replay")
    check("render_helpful(stored, i)" in hist_src and "render_helpful(turn" in run_src,
          "the helpful control renders on new and replayed turns alike")
    check('key="share_text"' in run_src and "value=False" in run_src.split('key="share_text"')[0][-400:],
          "text sharing is a separate sidebar opt-in, OFF by default")
    check("TURN_WIDGET_PREFIXES" in run_src and "helpful-" in app.TURN_WIDGET_PREFIXES
          and "ngo-" in app.TURN_WIDGET_PREFIXES,
          "Clear conversation drops per-turn widget keys (helpful, NGO filters)")

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print("  - %s" % f)
        return 1
    print("\nALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
