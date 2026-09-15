"""Multi-turn retrieval baseline: naive vs contextualised. Zero LLM, zero network.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\eval_chat.py   (from D:\\NGORAG)
     ... --reveal-test        (see TEST-SET PROTECTION)

WHAT THIS MEASURES AND WHY IT COMES BEFORE THE CHAT UI
------------------------------------------------------
"so can they fire me?" has no disability term and no statutory term. No amount
of re-ranking, no encoder and no corpus rebuild can retrieve an answer to a
query that does not contain the question. So ellipsis is a RETRIEVAL problem,
and if Phases D-F tune retrieval against single-turn questions only they
optimise a query distribution the chatbot never issues and the chat inherits
none of the gains. Hence: the multi-turn set is measured before the UI, before
the corpus rebuild and before the dense arm. Measure first -- this project's
own style.

TWO ARMS, ONE RETRIEVER
-----------------------
  naive           the raw turn text is the retrieval query. What DRLCA does
                  today; src/router.py is stateless and nothing in the stack
                  resolves ellipsis.
  contextualised  chat.contextualise() decides per turn whether prior turns
                  enter the query, and the merged string is retrieved on.

Everything else is held identical -- same corpus, same PerDocRetriever, same
k=3/doc, same select_top(top_n=6, min_per_doc=1), same MIN_SCORE. The only
independent variable is the query string, which is what makes the delta
attributable.

REUSE, NOT REIMPLEMENTATION
---------------------------
  recall / recall_strict   evalset.strict_covered and the same pair-set
                           construction eval_heldout.measure_one uses, so a
                           chat number is directly comparable to a single-turn
                           number rather than merely similar-looking.
  select_top               the shipping merge, never a bare [:TOP_N] slice.
  ground truth             data/eval/conversations.json via scripts/chatset.py,
                           corpus-verified at runtime.

THE GAIN AND THE COST ARE MEASURED ON THE SAME RUN
--------------------------------------------------
Contextualisation is not free and this harness refuses to report only its wins:

  gain   ellipsis / pronoun / narrowing should improve. That is the point.
  cost   `topic-shift` is the trap -- carrying prior turns can drag the old
         topic into a new question. The gate is "NOT WORSE than naive", never
         "better".
  cost   `off-corpus-after-legal` is the genuinely NEW failure mode chat
         creates. Carrying legal vocabulary into an off-corpus question can
         clear MIN_SCORE on words the user never wrote, turning a refusal into
         a confident cited answer. Reported ungated with the same caveat
         eval_heldout attaches, and the number that matters is the DELTA vs
         naive, because single-turn DRLCA already clears the floor on 5/5
         off-corpus questions (HANDOFF.md).

WHAT IT DELIBERATELY DOES NOT MEASURE
-------------------------------------
CROSS-TURN CITATION DRIFT. Detecting a tag re-cited from an earlier turn needs
a generated answer to read, so it costs quota; chat.cross_turn_drift() exists
and is wired, but no transcript exists to run it against. It is omitted rather
than approximated, exactly as eval_heldout omits faithfulness. Phase G's
multi-turn transcript (3 conversations x 3 turns ~ 9 calls) is what makes it
measurable.

TEST-SET PROTECTION
-------------------
chat_test's per-turn detail is withheld by default, for the reason the 30
single-turn held-out questions stopped being held out: reading which refs a
clean set misses is the tuning handle. Class and set means are always printed
in full -- the number is never hidden, only the handle. --reveal-test prints it
and says what it costs.

EXIT CODE POLICY
----------------
Nonzero ONLY for:
  - ground-truth verification failure (an expected number no chunk carries --
    a bug in the set, not a measurement), or
  - a CONTEXTUALISATION-INDUCED FALSE REFUSAL: a turn the naive arm answers and
    the contextualised arm refuses. That is not a disappointing number, it is
    our code denying help to a PWD who would have been helped without it.
NEVER for a recall number on either set. A harness that failed when chat_test
looked bad would create pressure to tune it, which is the contamination
chatset.py exists to prevent. A disappointing number is the finding.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import chat  # noqa: E402
import router  # noqa: E402
from chatset import (  # noqa: E402
    SETS,
    load_chat_set,
    summary,
    verify_expected,
)
from evalset import ref_nums, strict_covered  # noqa: E402
from rag import CORPUS_VERSION, build_corpus  # noqa: E402
from retrieve import MIN_SCORE, PerDocRetriever, select_top  # noqa: E402

# Held identical to eval_heldout.py / ask() / eval_phase06 / ablate_phase08.
K_PER_DOC = 3
TOP_N = 6
MIN_PER_DOC = 1

# One wide pool read at prefixes, same construction as eval_heldout.measure_curve.
K_CURVE = 20
CURVE_DEPTHS = (3, 6, 10, 20, 60)

ARMS = ("naive", "contextualised")

LABELS = {
    "chat_dev": "chat_dev (tuning allowed)",
    "chat_test": "chat_test (authored blind, never tuned against)",
}

# Classes contextualisation is SUPPOSED to help, and the ones it must not harm.
GAIN_CLASSES = ("ellipsis", "pronoun")
NOHARM_CLASSES = ("direct", "topic-shift")


def query_for(arm: str, turn: dict, history: list) -> tuple:
    """(retrieval_query, ctx_meta) for one arm. The ONLY difference between arms."""
    if arm == "naive":
        return turn["text"], {"carried": False, "reason": "naive-arm"}
    # history entries are {'question': ...} -- user text only, never an answer.
    # The offline default path has no answer to carry (ask(use_llm=False)
    # returns answer=None meaning pending), so an arm that depended on one
    # could not run at all without spending quota.
    prior = [{"question": h["text"]} for h in history]
    return chat.contextualise(prior, turn["text"])


def measure_turn(ret, turn: dict, history: list, arm: str) -> dict:
    """Retrieval profile for one turn under one arm. No LLM, no generation."""
    query, meta = query_for(arm, turn, history)
    hits = select_top(ret.query(query, k=K_PER_DOC), TOP_N,
                      min_per_doc=MIN_PER_DOC)
    kept = [h for h in hits if h.score >= MIN_SCORE]
    exp = turn["expected"]
    exp_pairs = {(d, n) for d, ns in exp.items() for n in ns}
    ret_pairs = {(h.doc_id, n) for h in hits for n in ref_nums(h.ref)}

    # recall@k from ONE wide pool read at prefixes: every depth scores the same
    # ordering, so the curve is monotone by construction and a violation is a
    # harness bug rather than a finding.
    pool = select_top(ret.query(query, k=K_CURVE), max(CURVE_DEPTHS),
                      min_per_doc=MIN_PER_DOC)
    curve, rank = {}, None
    if exp_pairs:
        for d in CURVE_DEPTHS:
            got = {(h.doc_id, n) for h in pool[:d] for n in ref_nums(h.ref)}
            curve["r@%d" % d] = len(exp_pairs & got) / len(exp_pairs)
        rank = next((i + 1 for i, h in enumerate(pool)
                     if ref_nums(h.ref) & exp.get(h.doc_id, set())), None)

    out = {
        "turn_id": turn["turn_id"], "class": turn["class"],
        "expect_gate": turn["expect_gate"], "arm": arm,
        "text": turn["text"], "query": query, "carried": meta.get("carried"),
        "reason": meta.get("reason", ""),
        # Off-corpus and help turns expect nothing, so recall is UNDEFINED
        # rather than zero -- scoring them 0.0 would drag every mean down with
        # a number that has no meaning. evalset.py's argument, same shape.
        "recall": (len(exp_pairs & ret_pairs) / len(exp_pairs)
                   if exp_pairs else None),
        "recall_strict": (strict_covered(hits, exp) / len(exp_pairs)
                          if exp_pairs else None),
        "top": hits[0].score if hits else 0.0,
        "n_kept": len(kept),          # 0 on an `answer` turn == REFUSAL
        "missed": sorted("%s:%s" % p for p in exp_pairs - ret_pairs),
        "rank": rank,
        "rr": (1.0 / rank) if rank else (0.0 if exp_pairs else None),
        **curve,
    }
    if turn["expect_gate"] == "help":
        # Help turns are scored on SLOTS, not recall. naive = router's stateless
        # scan of this turn alone (what ships today); contextualised =
        # chat.merge_help_slots across the conversation.
        got = (router.extract_help_slots(turn["text"]) if arm == "naive"
               else chat.merge_help_slots([{"question": h["text"]}
                                           for h in history], turn["text"]))
        want = turn["expect_slots"]
        out["slots_got"] = got
        out["slots_ok"] = all(got.get(k, "") == want[k] for k in want)
    return out


def mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def fmt(v, spec="%.3f"):
    return "n/a" if v is None else spec % v


def delta(a, b) -> str:
    """b - a, or 'n/a' when either side is undefined."""
    return "n/a" if (a is None or b is None) else "%+.3f" % (b - a)


def class_table(label: str, by_arm: dict) -> None:
    """Per class, both arms side by side, with the delta. The headline shape."""
    print("\n== %s -- RECALL BY TURN CLASS, naive vs contextualised ==" % label)
    print("  %-24s %-4s %-8s %-8s %-8s %-8s %-8s %s" % (
        "class", "n", "naive", "ctx", "delta", "n-strict", "c-strict", "d-strict"))
    classes = sorted({r["class"] for r in by_arm["naive"]})
    for cls in classes:
        n_rows = [r for r in by_arm["naive"] if r["class"] == cls]
        c_rows = [r for r in by_arm["contextualised"] if r["class"] == cls]
        scored = [r for r in n_rows if r["recall"] is not None]
        if not scored:
            # help / off-corpus classes have no recall by construction; they get
            # their own tables rather than a misleading 0.000 here.
            print("  %-24s %-4d %s" % (cls, len(n_rows),
                                       "(no legal ground truth -- see the "
                                       "slots / off-corpus tables)"))
            continue
        nr, cr = mean(r["recall"] for r in n_rows), mean(r["recall"] for r in c_rows)
        ns, cs = (mean(r["recall_strict"] for r in n_rows),
                  mean(r["recall_strict"] for r in c_rows))
        mark = ""
        if cls in GAIN_CLASSES and nr is not None and cr is not None:
            mark = "  <-- gain class" if cr > nr else "  <-- GAIN CLASS DID NOT IMPROVE"
        if cls in NOHARM_CLASSES and nr is not None and cr is not None and cr < nr:
            mark = "  <-- NO-HARM CLASS REGRESSED"
        print("  %-24s %-4d %-8s %-8s %-8s %-8s %-8s %s%s" % (
            cls, len(scored), fmt(nr), fmt(cr), delta(nr, cr),
            fmt(ns), fmt(cs), delta(ns, cs), mark))


def curve_table(label: str, by_arm: dict) -> None:
    print("\n== %s -- RECALL@K (pool k=%d/doc -> %d candidates, select_top order) =="
          % (label, K_CURVE, max(CURVE_DEPTHS)))
    print("  NOT the shipping arm (k=%d/doc -> top_n=%d). This answers 'is the"
          % (K_PER_DOC, TOP_N))
    print("  right chunk in the pool at all, and how deep?' -- a wide @6-to-@60")
    print("  gap means a re-ranker could reach it; a flat curve means it is absent.")
    hdr = "  %-16s" % "arm"
    for d in CURVE_DEPTHS:
        hdr += " %-7s" % ("r@%d" % d)
    print(hdr + " %-7s %-7s %s" % ("MRR", "med-rk", "found"))
    for arm in ARMS:
        rows = [r for r in by_arm[arm] if r["rr"] is not None]
        if not rows:
            continue
        line = "  %-16s" % arm
        for d in CURVE_DEPTHS:
            line += " %-7s" % fmt(mean(r.get("r@%d" % d) for r in rows))
        ranks = sorted(r["rank"] for r in rows if r["rank"])
        med = ranks[len(ranks) // 2] if ranks else None
        print(line + " %-7s %-7s %d/%d" % (
            fmt(mean(r["rr"] for r in rows)),
            "n/a" if med is None else str(med), len(ranks), len(rows)))


def slots_table(label: str, by_arm: dict) -> None:
    """The narrowing/handoff story: 'I'm deaf' ... 'anywhere in Kano?'."""
    rows = {arm: [r for r in by_arm[arm] if "slots_ok" in r] for arm in ARMS}
    if not rows["naive"]:
        return
    print("\n== %s -- HELP SLOTS (handoff + narrowing turns) ==" % label)
    print("  naive = router.extract_help_slots() on this turn ALONE, which is")
    print("  what ships today. contextualised = chat.merge_help_slots() across")
    print("  the conversation. A narrowing turn like 'anywhere in Kano?' has no")
    print("  disability in it, so the stateless scan drops the filter and the")
    print("  connector answers a question the user did not ask.")
    for arm in ARMS:
        ok = sum(1 for r in rows[arm] if r["slots_ok"])
        print("  %-16s %d/%d turns with BOTH slots correct"
              % (arm, ok, len(rows[arm])))
    for n, c in zip(rows["naive"], rows["contextualised"]):
        flag = "" if c["slots_ok"] else "  <-- STILL WRONG"
        print("    %-10s %-34s naive=%s ctx=%s%s" % (
            n["turn_id"], "%r" % n["text"][:32],
            "%(disability)r/%(location)r" % n["slots_got"],
            "%(disability)r/%(location)r" % c["slots_got"], flag))


def refusal_tables(label: str, by_arm: dict, show_detail: bool) -> list:
    """False refusals (the number that matters most) + inherited-context answers.

    Returns the list of contextualisation-INDUCED false refusals, which is the
    only retrieval number in this harness that can fail the run.
    """
    print("\n== %s -- FALSE-REFUSAL RATE (answerable turns) ==" % label)
    print("  CLAUDE.md: false refusals deny help to PWDs. This is the number")
    print("  that matters most, and chat can create new ones -- appending")
    print("  absent terms dilutes the query-vector norm and can drop a turn")
    print("  below MIN_SCORE that the raw question cleared.")
    induced = []
    for arm in ARMS:
        ans = [r for r in by_arm[arm] if r["expect_gate"] == "answer"]
        fr = [r for r in ans if r["n_kept"] == 0]
        print("  %-16s %d/%d = %.1f%% retrieve NOTHING"
              % (arm, len(fr), len(ans), 100 * len(fr) / len(ans) if ans else 0.0))
        if fr and show_detail:
            print("    offenders: %s" % ", ".join(
                "%s (%s, top %.4f)" % (r["turn_id"], r["class"], r["top"])
                for r in fr))
    for n, c in zip(by_arm["naive"], by_arm["contextualised"]):
        if (n["expect_gate"] == "answer" and n["n_kept"] > 0
                and c["n_kept"] == 0):
            induced.append(c)
    print("  CONTEXTUALISATION-INDUCED: %d turn(s) the naive arm answered and"
          % len(induced))
    print("  the contextualised arm refuses. This is the one retrieval number")
    print("  here that FAILS the run -- it is our code denying help to someone")
    print("  who would have been helped without it, not a disappointing metric.")
    for r in induced:
        print("    %s (%s): %r" % (r["turn_id"], r["class"], r["text"][:60]))

    print("\n== %s -- INHERITED-CONTEXT FALSE ANSWERS (off-corpus turns) ==" % label)
    print("  The genuinely NEW failure mode chat creates: carrying prior turns")
    print("  lets an off-corpus question inherit legal vocabulary and clear")
    print("  MIN_SCORE on words the user never wrote.")
    for arm in ARMS:
        ref = [r for r in by_arm[arm] if r["expect_gate"] == "refuse"]
        if not ref:
            continue
        fa = [r for r in ref if r["n_kept"] > 0]
        print("  %-16s %d/%d = %.1f%% clear MIN_SCORE=%.2f"
              % (arm, len(fa), len(ref), 100 * len(fa) / len(ref), MIN_SCORE))
        if show_detail:
            for r in ref:
                print("    %-10s carried=%-5s top %.4f  %r" % (
                    r["turn_id"], r["carried"], r["top"], r["text"][:52]))
    print("  CAVEAT, load-bearing and identical to eval_heldout's: a bad number")
    print("  here is EXPECTED and is NOT a reason to touch MIN_SCORE. It is a")
    print("  weak-overlap FLOOR, not a semantic filter, and the in-corpus /")
    print("  off-corpus cosine bands are INVERTED (src/retrieve.py:26-44) --")
    print("  single-turn DRLCA already clears it on 5/5 off-corpus questions.")
    print("  The only chat-attributable number is the DELTA between the arms.")
    return induced


def turn_table(label: str, by_arm: dict, show_missed: bool) -> None:
    print("\n== %s -- PER TURN (corpus=%s, k=%d/doc, top_n=%d, MIN_SCORE=%.2f) =="
          % (label, CORPUS_VERSION, K_PER_DOC, TOP_N, MIN_SCORE))
    print("  %-10s %-22s %-7s %-7s %-7s %-6s %s" % (
        "turn", "class", "gate", "naive", "ctx", "carry", "why / still-missed"))
    for n, c in zip(by_arm["naive"], by_arm["contextualised"]):
        why = c["reason"] if not show_missed else "%s | %s" % (
            c["reason"], ",".join(c["missed"]) or "-")
        flag = ""
        if n["expect_gate"] == "answer":
            if c["n_kept"] == 0:
                flag = "  <-- FALSE REFUSAL"
            elif (n["recall"] is not None and c["recall"] is not None
                  and c["recall"] < n["recall"]):
                flag = "  <-- ctx WORSE"
        print("  %-10s %-22s %-7s %-7s %-7s %-6s %s%s" % (
            n["turn_id"], n["class"], n["expect_gate"], fmt(n["recall"]),
            fmt(c["recall"]), str(c["carried"]), why[:58], flag))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    reveal_test = "--reveal-test" in argv

    convs = load_chat_set()
    docs = build_corpus()
    print("CORPUS_VERSION=%s" % CORPUS_VERSION)
    print("corpus: %s" % {k: len(v) for k, v in docs.items()})
    n_refs = verify_expected(convs, docs)   # HARD failure on a ground-truth bug
    print("chat ground truth verified against corpus: %d expected refs" % n_refs)
    for s, stat in summary(convs).items():
        print("  %-10s %2d conversations, %2d turns  %s"
              % (s, stat["conversations"], stat["turns"],
                 " ".join("%s=%d" % kv for kv in sorted(stat["by_class"].items()))))
    print("\n  contextualisation thresholds (chat.py, chosen on chat_dev ONLY):")
    print("    CARRY_WINDOW=%d  THIN_MAX=%d  MARKER_MAX=%d  QUESTION_WEIGHT=%d"
          % (chat.CARRY_WINDOW, chat.THIN_MAX, chat.MARKER_MAX,
             chat.QUESTION_WEIGHT))

    ret = PerDocRetriever(docs)
    measured = {}
    for s in SETS:
        rows = {arm: [] for arm in ARMS}
        for c in [c for c in convs if c["set"] == s]:
            for t in c["turns"]:
                history = c["turns"][:t["index"]]
                for arm in ARMS:
                    rows[arm].append(measure_turn(ret, t, history, arm))
        measured[s] = rows

    induced_total = []
    for s in SETS:
        label = LABELS[s]
        detail = (s != "chat_test") or reveal_test
        turn_table(label, measured[s], show_missed=detail)
        if s == "chat_test" and not reveal_test:
            print("  still-missed withheld: reading which refs a CLEAN set misses")
            print("  is what turned the 30 single-turn held-out questions into a")
            print("  dev set. --reveal-test prints it, and spends the set.")
        class_table(label, measured[s])
        curve_table(label, measured[s])
        slots_table(label, measured[s])
        induced_total += refusal_tables(label, measured[s], show_detail=detail)

    # ---- the headline, both sets, both arms, one block.
    print("\n== HEADLINE: ALL SETS, BOTH ARMS (corpus=%s, shipping arm k=%d/doc "
          "-> select_top(%d)) ==" % (CORPUS_VERSION, K_PER_DOC, TOP_N))
    print("  %-46s %-8s %-8s %-8s %s" % ("set", "naive", "ctx", "delta", "n"))
    for s in SETS:
        nr = mean(r["recall"] for r in measured[s]["naive"])
        cr = mean(r["recall"] for r in measured[s]["contextualised"])
        n = sum(1 for r in measured[s]["naive"] if r["recall"] is not None)
        print("  %-46s %-8s %-8s %-8s %d"
              % (LABELS[s], fmt(nr), fmt(cr), delta(nr, cr), n))
    print("  Means over ANSWERABLE turns only. help and off-corpus turns have")
    print("  no legal ground truth and are scored in their own tables, never as")
    print("  0.000 -- see the class table for the per-class split, which is the")
    print("  number that actually says whether contextualisation works.")

    # ---- the Phase B gates, reported as PASS/FAIL, failing only where honest.
    print("\n== PHASE B GATES ==")
    dev = measured["chat_dev"]
    for cls in GAIN_CLASSES:
        nr = mean(r["recall"] for r in dev["naive"] if r["class"] == cls)
        cr = mean(r["recall"] for r in dev["contextualised"] if r["class"] == cls)
        ok = nr is not None and cr is not None and cr > nr
        print("  ctx BEATS naive on %-14s %s -> %s   %s"
              % (cls, fmt(nr), fmt(cr), "PASS" if ok else "FAIL"))
    nr = mean(r["recall"] for r in dev["naive"] if r["class"] == "topic-shift")
    cr = mean(r["recall"] for r in dev["contextualised"]
              if r["class"] == "topic-shift")
    ok = nr is not None and cr is not None and cr >= nr - 1e-9
    print("  topic-shift NOT WORSE than naive  %s -> %s   %s"
          % (fmt(nr), fmt(cr), "PASS" if ok else "FAIL"))
    n_slots = [r for r in dev["naive"] if "slots_ok" in r]
    c_slots = [r for r in dev["contextualised"] if "slots_ok" in r]
    print("  help slots naive %d/%d -> ctx %d/%d"
          % (sum(1 for r in n_slots if r["slots_ok"]), len(n_slots),
             sum(1 for r in c_slots if r["slots_ok"]), len(c_slots)))
    print("  cross-turn citation drift: STRUCTURALLY UNAVAILABLE here -- it")
    print("  needs a generated answer to read. chat.cross_turn_drift() is wired")
    print("  and unmeasured; Phase G's multi-turn transcript is what runs it.")

    print("\n== FAILURE CONDITION (the only retrieval number that can fail) ==")
    if induced_total:
        print("  %d contextualisation-induced false refusal(s):" % len(induced_total))
        for r in induced_total:
            print("    %s (%s)" % (r["turn_id"], r["class"]))
        print("\nEVAL_CHAT: FAIL -- contextualisation denied help that the raw")
        print("question would have retrieved. Fix chat.py, do not edit the set.")
        return 1
    print("  0 contextualisation-induced false refusals on either set.")
    print("\nEVAL_CHAT: PASS (ground truth verified; all numbers reported as measured)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
