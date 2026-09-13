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
SCRIPT = [None]  # callable(model) -> str, or raises


class _Resp:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    def generate_content(self, model, contents):  # noqa: ARG002
        CALLS.append(model)
        return _Resp(SCRIPT[0](model))


class _FakeClient:
    def __init__(self, api_key=None, **kw):  # noqa: ARG002
        self.models = _FakeModels()


def install(script) -> None:
    """Arm the fake client with a per-model behaviour and clear the log."""
    CALLS.clear()
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

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print("  - %s" % f)
        return 1
    print("\nALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
