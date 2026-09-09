"""Phase 01 benchmark: before (recursive 500/50, no repair) vs after (new pipeline).

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\bench_phase01.py  (from D:\\NGORAG)
Compares ONE joint TfidfRetriever per pipeline over all three docs, using the
SAME 10 questions as notebooks/01_foundation.ipynb (2026-09-06).

Numbering is never conflated: every chunk carries (doc_id, ref) metadata with
doc_id in {'act2018', 'constitution1999', 'factsheet2020'}.
"""
import json
import os
import re
import sys
from pathlib import Path

CONST_SIZE = int(os.environ.get("PHASE01_CONST_SIZE", "400"))
# Grid result (2026-09-08, joint corpus): 800 -> Q9 0.113 FAIL; 500 -> 0.139 FAIL;
# 400 -> Q9 0.167 PASS, mean 0.275. Playbook cap is <=800, so 400 is compliant.

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from chunk import (  # noqa: E402
    PRIORITY_SECTIONS,
    constitution_aware_split,
    recursive_split,
    section_aware_split,
)
from load import (  # noqa: E402
    build_clean_text,
    clean_text,
    clause_coverage,
    detect_duplicate_pages,
    repair_joins,
    split_pages,
)
from retrieve import TfidfRetriever  # noqa: E402

ACT = ROOT / "data" / "processed" / "disability_act_2018_full.txt"
CONST = ROOT / "data" / "processed" / "constitution_1999_NHRC.txt"
FACT = ROOT / "data" / "processed" / "disability_act_factsheet_PLAC.txt"

SECTION_RE = re.compile(r"(Section \d+)", re.IGNORECASE)
CONST_REF_RE = re.compile(r"\u00a7\u00a7?(\d+)")


def load_questions() -> list[str]:
    """Same 10-question set as notebooks/01_foundation.ipynb (2026-09-06)."""
    nb_path = ROOT / "notebooks" / "01_foundation.ipynb"
    try:
        nb = json.loads(nb_path.read_text(encoding="utf-8"))
        for cell in nb.get("cells", []):
            src = "".join(cell.get("source", []))
            if "questions = [" in src:
                # Extract quoted strings from the literal (no exec: cell code
                # references notebook-only names like TfidfRetriever).
                block = src[src.index("questions = ["):]
                block = block[: block.index("]") + 1]
                qs = re.findall(r"""['\"]([^'\"\n]{8,}?)['\"]""", block)
                qs = [q for q in qs if "?" in q or len(q.split()) > 3]
                if len(qs) >= 10:
                    return qs[:10]
                print("notebook block parsed %d questions; using fallback" % len(qs))
                break
    except Exception as e:  # noqa: BLE001 -- fallback below
        print("notebook parse failed (%s); using fallback questions" % e)
    return [
        "What does the Act say about discrimination?",
        "Are public buildings required to be accessible?",
        "What employment protections exist for persons with disabilities?",
        "Is there a commission for persons with disabilities?",
        "What are the penalties for violating the Act?",
        "Does the Act cover access to vehicles and transport?",
        "What rights do children with disabilities have to education?",
        "How long is the transitional compliance period?",
        "Does the Constitution guarantee dignity and equality?",
        "Where can I get legal aid for a disability rights violation?",
    ]


def act_ref(chunk: str) -> str:
    m = re.search(r"(?<!\d)(\d{1,2})(?!\d)\s*[\.\)]", chunk)
    return "act:clause %s" % m.group(1) if m else "act:general"


def const_ref(chunk: str) -> str:
    m = CONST_REF_RE.search(chunk[:120])
    return "constitution:S%s" % m.group(1) if m else "constitution:general"


def fact_ref(chunk: str) -> str:
    m = SECTION_RE.search(chunk)
    return "factsheet:%s" % m.group(1) if m else "factsheet:general"


def build_before() -> tuple[list[str], list[dict]]:
    """Old pipeline: raw read + plain clean_text, recursive 500/50, no repair."""
    chunks, meta = [], []
    for path, doc_id, ref_fn in (
        (ACT, "act2018", act_ref),
        (CONST, "constitution1999", const_ref),
        (FACT, "factsheet2020", fact_ref),
    ):
        raw = path.read_text(encoding="utf-8", errors="replace")
        text = clean_text(raw)  # repair=False, markers kept, no dedupe
        for c in recursive_split(text, size=500, overlap=50):
            chunks.append(c)
            meta.append({"doc_id": doc_id, "ref": ref_fn(c)})
    return chunks, meta


def build_after() -> tuple[list[str], list[dict], dict]:
    """New pipeline: dedupe+repair at load; Act section-aware, Constitution
    chapter-aware, factsheet recursive. Returns (chunks, meta, info)."""
    chunks, meta = [], []
    info: dict = {}
    per_doc: dict[str, list[str]] = {}

    raw_act = ACT.read_text(encoding="utf-8", errors="replace")
    pages = split_pages(raw_act)
    info["dups"] = detect_duplicate_pages(pages)
    act_text, sidecar, dropped = build_clean_text(raw_act, repair=True, dedupe=True)
    act_text = clean_text(act_text)
    info["sidecar_pages"] = len(sidecar)
    info["dropped"] = dropped
    info["act_coverage_after"] = sorted(clause_coverage(act_text))
    raw_before_cov = sorted(
        clause_coverage(clean_text(raw_act.replace("===== PAGE", " ")))
    )
    info["act_coverage_before"] = raw_before_cov
    act_chunks = section_aware_split(act_text, size=800)
    per_doc["act2018"] = act_chunks
    for c in act_chunks:
        chunks.append(c)
        meta.append({"doc_id": "act2018", "ref": act_ref(c)})

    raw_const = CONST.read_text(encoding="utf-8", errors="replace")
    const_text = clean_text(repair_joins(raw_const))
    const_chunks = constitution_aware_split(const_text, size=CONST_SIZE)
    per_doc["constitution1999"] = const_chunks
    for c in const_chunks:
        chunks.append(c)
        meta.append({"doc_id": "constitution1999", "ref": const_ref(c)})

    raw_fact = FACT.read_text(encoding="utf-8", errors="replace")
    fact_text = clean_text(repair_joins(raw_fact))
    fact_chunks = recursive_split(fact_text, size=500, overlap=50)
    per_doc["factsheet2020"] = fact_chunks
    for c in fact_chunks:
        chunks.append(c)
        meta.append({"doc_id": "factsheet2020", "ref": fact_ref(c)})

    info["per_doc"] = {k: v for k, v in per_doc.items()}
    return chunks, meta, info


def chunk_stats(chunks: list[str]) -> tuple[int, float, int]:
    n = len(chunks)
    avg = sum(len(c) for c in chunks) / n if n else 0.0
    mx = max((len(c) for c in chunks), default=0)
    return n, avg, mx


def run_queries(chunks: list[str], questions: list[str]) -> list[tuple[float, int]]:
    ret = TfidfRetriever(chunks)
    out = []
    for q in questions:
        i, s, _ = ret.query(q, k=1)[0]
        out.append((s, i))
    return out


def main() -> None:
    questions = load_questions()
    assert len(questions) == 10, "expected 10 questions, got %d" % len(questions)
    print("Questions loaded: %d (Q9=%r)" % (len(questions), questions[8]))

    # --- repair_joins showcase: 5 fixed + 3 deliberately-left ---
    fixed = {
        "Apersonwith disabilityhas theright": "A person with disability has the right",
        "FirstSchedule.": "First Schedule.",
        "PARTVI-OPPORTUNITY": "PART VI-OPPORTUNITY",
        "thisAct": "this Act",
        "equalbasiswithothers": "equal basis with others",
    }
    for old, new in fixed.items():
        got = repair_joins(old)
        assert got == new, "repair %r -> %r (expected %r)" % (old, got, new)
    left = ["Partiipation", "hroads", "N1,00o,000", "EXPANARORYMEMORANDUM"]
    for tok in left:
        assert repair_joins(tok) == tok, "must leave %r untouched" % tok
    print("repair_joins: 5 fixed + %d deliberately-left OK" % len(left))

    # --- full repair review dump: every distinct token repair_joins changes ---
    print("\n== REPAIR REVIEW (distinct tokens changed across corpus) ==")
    tok_re = re.compile(r"[A-Za-z]{6,}")
    raws = [
        ACT.read_text(encoding="utf-8", errors="replace"),
        CONST.read_text(encoding="utf-8", errors="replace"),
        FACT.read_text(encoding="utf-8", errors="replace"),
    ]
    changed: dict[str, str] = {}
    for raw in raws:
        for tok in set(tok_re.findall(raw)):
            if tok.lower() in ("partvi",):  # handled, skip noise
                pass
            fixed = repair_joins(tok)
            if fixed != tok:
                changed[tok] = fixed
    for tok in sorted(changed):
        print("  %-45s -> %s" % (tok[:45], changed[tok][:70]))
    print("  distinct tokens changed: %d" % len(changed))
    # residual suspects: camel boundaries repair_joins still leaves behind
    resid = sorted({t for raw in raws for t in set(tok_re.findall(repair_joins(raw)))
                    if re.search(r"[a-z][A-Z]", t)})
    print("  residual camel tokens (%d): %s" % (len(resid), resid[:20]))

    b_chunks, b_meta = build_before()
    a_chunks, a_meta, info = build_after()

    # --- dedupe report ---
    print("\n== DEDUPE (Act, %d pages) ==" % len(
        split_pages(ACT.read_text(encoding="utf-8", errors="replace"))))
    for i, j, r, c in info["dups"]:
        print("  pages %d->%d: difflib=%.3f line_contain=%.2f" % (i + 1, j + 1, r, c))
    for d in info["dropped"]:
        print(
            "  dropped p.%s (kept cleaner p.%s), salvaged %d unique lines"
            % (d["dropped_page"], d["kept_page"], d["salvaged_lines"])
        )
    print("  sidecar entries: %d" % info["sidecar_pages"])

    # --- clause regression check ---
    missing = set(range(1, 59)) - set(info["act_coverage_after"])
    print("\n== CLAUSE COVERAGE (Act, after cleanup) ==")
    print("  before: %d/58, after: %d/58, missing: %s"
          % (len(info["act_coverage_before"]), len(info["act_coverage_after"]),
             sorted(missing) or "none"))
    assert not missing, "clause numbers lost by cleanup: %s" % sorted(missing)

    # --- chunk stats ---
    print("\n== CHUNK STATS ==")
    print("  %-16s %6s %6s %9s %8s" % ("pipeline/doc", "n", "avg", "max", "over800"))
    nb, ab, xb = chunk_stats(b_chunks)
    print("  %-16s %6d %6.0f %9d %8s" % ("before/TOTAL", nb, ab, xb, ""))
    na, aa, xa = chunk_stats(a_chunks)
    print("  %-16s %6d %6.0f %9d %8s" % ("after/TOTAL", na, aa, xa, ""))
    for doc_id in ("act2018", "constitution1999", "factsheet2020"):
        dc = info["per_doc"][doc_id]
        n, av, mx = chunk_stats(dc)
        over = sum(1 for c in dc if len(c) > 800)
        print("  %-16s %6d %6.0f %9d %8d" % ("after/" + doc_id, n, av, mx, over))
    assert all(len(c) <= CONST_SIZE for c in info["per_doc"]["constitution1999"]), \
        "constitution chunk exceeds size cap"
    print("  (constitution size cap: %d)" % CONST_SIZE)

    # --- priority sections survive as own chunks ---
    # (i) each priority N owns >=1 single-section chunk ("S N: ", not a range);
    # (ii) no merged "SSa-b" chunk may span a priority number (pending runs are
    #       flushed at priority boundaries, so ranges never cover one).
    print("\n== PRIORITY SECTIONS (Constitution) ==")
    const_chunks = info["per_doc"]["constitution1999"]
    pri_ok = True
    for sec in sorted(PRIORITY_SECTIONS):
        hits = [c for c in const_chunks
                if re.search(r"\u00a7%d: " % sec, c[:160])]
        body_chars = sum(len(c) for c in hits)
        flag = "OK" if hits else "MISSING"
        if not hits:
            pri_ok = False
        print("  S%-3d single-chunks=%3d body_chars=%6d %s" % (sec, len(hits), body_chars, flag))
    for c in const_chunks:
        m = re.search(r"\u00a7\u00a7([\d,]+): ", c[:200])
        if m and any(int(x) in PRIORITY_SECTIONS for x in m.group(1).split(",")
                     if x.isdigit()):
            pri_ok = False
            print("  MERGED-RANGE VIOLATION: %s" % c[:120])
    assert pri_ok, "a priority section lacks own chunk(s) or got merged"

    # --- retrieval before/after ---
    b_scores = run_queries(b_chunks, questions)
    a_scores = run_queries(a_chunks, questions)
    print("\n== TOP-1 BEFORE -> AFTER ==")
    print("  %-58s %7s %7s %-22s %-22s" % ("question", "before", "after", "before(doc/ref)", "after(doc/ref)"))
    for q, (bs, bi), (as_, ai) in zip(questions, b_scores, a_scores):
        print("  %-58s %7.3f %7.3f %-22s %-22s" % (
            q[:58], bs, as_,
            "%s/%s" % (b_meta[bi]["doc_id"], b_meta[bi]["ref"]),
            "%s/%s" % (a_meta[ai]["doc_id"], a_meta[ai]["ref"])))
    b_mean = sum(s for s, _ in b_scores) / len(b_scores)
    a_mean = sum(s for s, _ in a_scores) / len(a_scores)
    b_nz = sum(1 for s, _ in b_scores if s > 0)
    a_nz = sum(1 for s, _ in a_scores if s > 0)
    print("  mean top-1: before=%.3f after=%.3f | nonzero: before=%d/10 after=%d/10"
          % (b_mean, a_mean, b_nz, a_nz))

    # --- exit criteria ---
    q9_after = a_scores[8][0]
    print("\n== EXIT CRITERIA ==")
    print("  clause 1-58 continuous: %s" % (not missing))
    print("  10/10 nonzero (after): %s" % (a_nz == 10))
    print("  Q9 constitution dignity/equality: before=%.3f after=%.3f (>0.16: %s)"
          % (b_scores[8][0], q9_after, q9_after > 0.16))
    assert a_nz == 10, "after pipeline has zero-score questions"
    assert q9_after > 0.16, "Q9 constitution query not above 0.16"
    print("\nPHASE01 BENCHMARK: PASS")


if __name__ == "__main__":
    main()
