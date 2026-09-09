"""Phase 04 test: keyword intent router (legal vs help vs clarify), offline.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts/test_phase04.py
Stdlib + pandas only. ZERO LLM/network calls (quota exhausted by design):
legal paths call ask(use_llm=False); the script also statically asserts
router.py contains no Gemini hookup ("genai"/"generate_content").

Asserts per playbook 04_intent_router.md:
  - >= 8/10 queries routed correctly (mixed counts iff BOTH routes fire),
  - ambiguous low-signal query -> clarifying question (unit check, separate),
  - keyword routing latency negligible vs an LLM call (mean < 50 ms).
Exits nonzero on ANY failure.
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import router  # noqa: E402
from ngo import DRAC_TOLLFREE, DRAC_WHATSAPP  # noqa: E402
from router import extract_help_slots, get_ngo_df, get_retriever, route, route_question  # noqa: E402

# query, expected primary ("legal"/"help"), kind ("pure"/"mixed")
QUERIES = [
    ("What are my rights to free education under the Act?", "legal", "pure"),
    ("What penalty applies for discrimination?", "legal", "pure"),
    ("Does the Constitution guarantee equality?", "legal", "pure"),
    ("Can my employer sack me because I use a wheelchair?", "legal", "pure"),
    ("Where can I find help for my deaf child in Abuja?", "help", "pure"),
    ("I need a prosthetic limb for my son in Lagos, who do I contact?", "help", "pure"),
    ("Which organisation supports people with albinism near me?", "help", "pure"),
    ("Mental health helpline in Kano", "help", "pure"),
    ("My employer fired me because of my disability, who can help me?",
     "dual", "mixed"),
    ("wetin be my right for work? I need person wey fit help me for Lagos",
     "dual", "mixed"),
]

VAGUE_QUERY = "tell me something"  # tie/both-zero probe, reported separately
TIE_QUERY = "rights help"  # 1-1 positive tie -> clarify, reported separately
LATENCY_BUDGET_MS = 50.0


def main() -> int:
    failures = []

    # --- static: router must be LLM-free (quota exhausted; keyword path only)
    src = (ROOT / "src" / "router.py").read_text(encoding="utf-8")
    for token in ("genai", "generate_content", "GOOGLE_API_KEY", "GEMINI_API_KEY"):
        ok = token not in src
        print("[%s] static: router.py has no %r" % ("PASS" if ok else "FAIL", token))
        if not ok:
            failures.append("static:router references %s" % token)

    # --- shared fixtures built once (corpus build is slow; not timed)
    df = get_ngo_df()
    retriever = get_retriever()
    print("fixtures: ngo rows=%d corpus docs built OK" % len(df))

    # --- 10-query matrix (times the KEYWORD path only, not corpus build)
    print("\n%-3s %-58s %-7s %-7s %-14s %-6s %-4s" % (
        "#", "query", "L", "H", "route", "exp", "res"))
    latencies = []
    n_correct = 0
    for i, (q, expected, kind) in enumerate(QUERIES, 1):
        t0 = time.perf_counter()
        routing = route_question(q)
        latencies.append((time.perf_counter() - t0) * 1000.0)

        primary, secondary = routing["primary"], routing["secondary"]
        if kind == "pure":
            correct = primary == expected and secondary is None
        else:  # mixed counts iff BOTH routes fire
            correct = (primary, secondary) in (("legal", "help"), ("help", "legal"))
        n_correct += correct

        # --- wire-up proofs per route (offline subsystem calls)
        payload = route(q, df=df, retriever=retriever)
        if routing["primary"] == "clarify":
            wire_ok = payload.get("clarify_question") == routing["clarify_question"]
        else:
            wire_ok = True
            if routing["primary"] == "legal" or secondary == "legal":
                leg = payload["legal"]
                # Retrieval ran offline: no LLM used; answer None (pending)
                # or refusal text -- both prove the path without Gemini.
                wire_ok &= leg is not None and leg.get("llm_used") is False \
                    and (leg.get("answer") is None or leg.get("refused") is True)
            if routing["primary"] == "help" or secondary == "help":
                hlp = payload["help"]
                recs = hlp["records"] if hlp else []
                wire_ok &= bool(recs) and recs[0]["phone"] == DRAC_TOLLFREE \
                    and recs[1]["phone"] == DRAC_WHATSAPP
                # Phase 03 residual: fuzzy flag visible + confirm prompt set.
                wire_ok &= hlp["needs_confirmation"] == hlp["meta"]["fuzzy_fallback"]
                if hlp["meta"]["fuzzy_fallback"]:
                    wire_ok &= "did you mean" in hlp["confirm_prompt"].lower()
        ok = correct and wire_ok
        print("%-3d %-58s %-7d %-7d %-14s %-6s %-4s  L=%s H=%s%s" % (
            i, q[:58], routing["scores"]["legal"], routing["scores"]["help"],
            "%s%s" % (primary, "+%s" % secondary if secondary else ""),
            expected, "PASS" if ok else "FAIL",
            routing["matched_cues"]["legal"][:3],
            routing["matched_cues"]["help"][:4],
            " slots=%s" % (extract_help_slots(q)
                            if (primary == "help" or secondary == "help") else "")))
        if not ok:
            failures.append("q%d=%r primary=%s secondary=%s wire_ok=%s" % (
                i, q, primary, secondary, wire_ok))

    mean_ms = sum(latencies) / len(latencies)
    print("\nrouting latency (keyword path, n=10): mean %.3f ms, max %.3f ms "
          "(budget < %.0f ms)" % (mean_ms, max(latencies), LATENCY_BUDGET_MS))
    lat_ok = mean_ms < LATENCY_BUDGET_MS
    print("[%s] latency negligible vs LLM call" % ("PASS" if lat_ok else "FAIL"))
    if not lat_ok:
        failures.append("latency mean=%.3fms over budget" % mean_ms)

    print("matrix: %d/10 correct (exit needs >= 8)" % n_correct)
    if n_correct < 8:
        failures.append("accuracy %d/10 < 8" % n_correct)

    # --- tie/clarify unit checks (separate from the 8/10 exit count)
    for label, probe in (("vague", VAGUE_QUERY), ("positive-tie", TIE_QUERY)):
        r = route_question(probe)
        p = route(probe, df=df, retriever=retriever)
        ok = r["primary"] == "clarify" and "clarify_question" in r \
            and p.get("clarify_question") == r["clarify_question"] \
            and p["legal"] is None and p["help"] is None
        print("[%s] %s probe %r -> clarify (L=%d H=%d, no subsystem call)" % (
            "PASS" if ok else "FAIL", label, probe,
            r["scores"]["legal"], r["scores"]["help"]))
        if not ok:
            failures.append("%s probe did not clarify: %s" % (label, r))

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print("  - %s" % f)
        return 1
    print("\nALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
