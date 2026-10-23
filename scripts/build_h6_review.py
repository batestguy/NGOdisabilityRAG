"""H6 step 1 -- build the legal-expert review pack (docs/phases/16_post_launch_roadmap.md, H6).

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\build_h6_review.py

Writes, deterministically and with ZERO network calls:
  docs/review/h6_review_sheet.csv   UTF-8 with BOM (Excel), one row per Q&A pair
  docs/review/h6_review_sheet.md    the same rows as a printable document

SOURCES. AI answers come ONLY from three versioned transcripts already on disk
(G2 single-turn, G4 multi-turn, G6 generator-refusal probes). No transcript stores
excerpt TEXT, so the offline excerpts are recomputed here with the shipping
display path, app.offline_legal_hits() on the default corpus at its own budget --
exactly what a user sees with the AI expander OFF. Since H8a.5 (2026-10-23) that is
corpus v3 (+ Accessibility Regulations 2023), k=4/doc, top_n=16, and each row shows
the fixed status note (rag.DOC_STATUS_NOTES) once, just before its first Regs excerpt,
as the app does (F10: the lawyer reviews the system that would ship). The v2 pack the
reviewer was first sent is kept verbatim as docs/review/h6_review_sheet_v2_2026-10-21.*. G2 and G4 recorded the excerpt TAG list
at the time; each row's non-Regs tags (the AI never saw a Regs excerpt) are compared against it and a difference is reported in the
.md (the corpus has had human-verified corrections since, e.g. Act cl. 1).
A few offline-only rows (`authored-h6`) fill the Constitution / cross-document
gap; their ai_answer is a fixed placeholder, never generated.

HELD-OUT SETS ARE NEVER OPENED: offtopic_h4.json, pidgin_h5a.json,
questions_test2.json, test2_pass1_questions.txt, and questions.json (whose `test`
entries are held out) are not read by this script at all. The SOURCES dict below
is the complete list of files read for rows, and it is asserted against FORBIDDEN.

Excerpt text and citation tags are copied verbatim -- OCR quirks and section
numbers are never cleaned up (spec invariant). Exits nonzero on any failed check.
"""

import csv
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))  # app.py lives at the repo root

OUT_DIR = ROOT / "docs" / "review"
OUT_CSV = OUT_DIR / "h6_review_sheet.csv"
OUT_MD = OUT_DIR / "h6_review_sheet.md"

SOURCES = {
    "G2": "scripts/test_phase02_results_cite-strict-v3_2026-09-24.json",
    "G4": "scripts/transcript_chat_chat-cite-strict-v2_2026-10-15.json",
    "G6": "scripts/probe_gen_refusal_cite-strict-v3_2026-10-15.json",
}
FORBIDDEN = (
    "data/eval/offtopic_h4.json",
    "data/eval/pidgin_h5a.json",
    "data/eval/questions_test2.json",
    "data/eval/test2_pass1_questions.txt",
    "data/eval/questions.json",
)

NO_AI = "(no AI answer recorded)"
OFFLINE_ONLY = "(offline only \u2014 AI answer not generated, to save quota)"
NO_EXCERPTS = ("(no excerpts shown \u2014 nothing cleared the match floor, so the app shows "
               "its standard refusal message and the helplines)")
CSV_SEP = " || "

CATEGORIES = {
    "act": "Disability Act 2018",
    "constitution": "1999 Constitution",
    "factsheet": "2020 Factsheet",
    "cross-document": "More than one document",
    "lay-pidgin": "Everyday wording (plain English or Pidgin)",
    "off-corpus": "Outside the four documents",
}

# Row-level warnings for AI answers recorded before a corpus correction. Each is
# self-checking: the quoted fragment must be in the recorded answer and absent
# from today's excerpts, or the build fails (so a stale note cannot linger).
STALE_ANSWER_NOTES = {
    ("G2", "Q1"): ("o uuu Aun",
                   "This AI answer was recorded before the Act cl. 1 text was corrected, so it "
                   "quotes scanning errors (garbled words). Please ignore the garbled words and "
                   "judge the rest of the answer."),
}

# (source, item id, category). Order here is the order in the pack.
# Left out on purpose: G4 CD3.t1 (same question as G2 Q2), CD10.t1 (parking,
# covered by G6 P07), CD10.t3 (off-corpus -- the pack has exactly two, G2 R1/R2),
# G6 P10 (transport, covered by G2 Q6).
ROWS = [
    ("G2", "Q1", "act"),
    ("G2", "Q2", "act"),
    ("G2", "Q3", "act"),
    ("G2", "Q5", "act"),
    ("G2", "Q6", "act"),
    ("G2", "Q4", "factsheet"),
    ("G2", "Q7", "factsheet"),
    ("G2", "Q8", "factsheet"),
    ("G2", "Q9", "constitution"),
    ("authored-h6", "A1", "constitution"),
    ("authored-h6", "A2", "constitution"),
    ("G2", "Q10", "cross-document"),
    ("authored-h6", "A3", "cross-document"),
    ("G4", "CD1.t1", "act"),
    ("G4", "CD1.t2", "lay-pidgin"),
    ("G4", "CD1.t3", "act"),
    ("G4", "CD3.t2", "factsheet"),
    ("G4", "CD3.t3", "act"),
    ("G4", "CD10.t2", "act"),
    ("G6", "P01", "lay-pidgin"),
    ("G6", "P04", "lay-pidgin"),
    ("G6", "P05", "lay-pidgin"),
    ("G6", "P07", "lay-pidgin"),
    ("G6", "P08", "lay-pidgin"),
    ("G6", "P11", "lay-pidgin"),
    ("G6", "P13", "lay-pidgin"),
    ("G6", "P14", "lay-pidgin"),
    ("G6", "P17", "lay-pidgin"),
    ("G2", "R1-same-vocab", "off-corpus"),
    ("G2", "R2-generic", "off-corpus"),
]

# Written fresh for H6 (2026-10-21) to fill the Constitution / cross-document gap.
AUTHORED = {
    "A1": "What does the Constitution say about the right to personal liberty?",
    "A2": "Does the Constitution protect me from discrimination because of my "
          "circumstances of birth?",
    "A3": "Do both the Constitution and the Disability Act protect persons with "
          "disabilities from discrimination?",
}

CONTROL_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")
# Markdown would turn an excerpt line "58. Citation." followed by "58. This Act..."
# into an ordered list numbered 58, 59 -- a rendered RENUMBERING. So line-initial
# list/heading markers in excerpt text are backslash-escaped in the .md only; they
# render verbatim. The CSV keeps the raw text.
MD_LINE_START_RE = re.compile(r"^(\d+)\.(?=\s|$)|^([-*+#])")


def md_excerpt_line(line: str) -> str:
    return MD_LINE_START_RE.sub(
        lambda m: m.group(1) + "\\." if m.group(1) else "\\" + m.group(2), line)


def load_sources() -> dict:
    for rel in SOURCES.values():
        assert rel not in FORBIDDEN, rel
    g2 = json.loads((ROOT / SOURCES["G2"]).read_text(encoding="utf-8"))
    g4 = json.loads((ROOT / SOURCES["G4"]).read_text(encoding="utf-8"))
    g6 = json.loads((ROOT / SOURCES["G6"]).read_text(encoding="utf-8"))
    return {"G2": {r["id"]: r for r in g2},
            "G4": {t["id"]: t for t in g4["turns"]},
            "G4_turns": g4["turns"],
            "G6": {r["id"]: r for r in g6["rows"]}}


def answer_of(src: str, rec: dict):
    """(answer text or None, llm_error) exactly as the transcript recorded it."""
    ans = rec.get("answer_full") if src == "G2" else rec.get("answer")
    return ans, rec.get("llm_error")


REGS = "accessregs2023"
NOTE_LEAD = "About this source:"


def note_md(note: str) -> str:
    """The status note as the app displays it: lead bolded, text verbatim."""
    return ("**%s**%s" % (NOTE_LEAD, note[len(NOTE_LEAD):])
            if note.startswith(NOTE_LEAD) else note)


def main() -> int:
    import app  # import-safe by contract (no server)
    import rag
    from retrieve import PerDocRetriever, cite_tag, corpus_sha256

    docs = rag.build_corpus()
    ret = PerDocRetriever(docs)
    version, top_n = rag.CORPUS_VERSION, rag.default_top_n(ret)
    NOTE = rag.DOC_STATUS_NOTES[REGS]
    src = load_sources()
    fails = []

    def check(ok, label):
        print("[%s] %s" % ("PASS" if ok else "FAIL", label))
        if not ok:
            fails.append(label)

    rows = []
    for n, (source, item, cat) in enumerate(ROWS, 1):
        rec = src[source][item] if source != "authored-h6" else None
        if source == "G2":
            assert rec is not None
            question = rec["question"]
            rq = None
            recorded = [cite_tag(s["doc_id"], s["ref"]) for s in rec["scores"]
                        if s["score"] >= rec["min_score"]]
        elif source == "G4":
            assert rec is not None
            conv = item.split(".")[0]
            prior = [t["question"] for t in src["G4_turns"]
                     if t["id"].split(".")[0] == conv
                     and int(t["id"].split(".t")[1]) < int(item.split(".t")[1])]
            question = rec["question"] if not prior else "(Earlier: %s) Now: %s" % (
                " / ".join('"%s"' % q for q in prior), rec["question"])
            rq = rec["retrieval_query"]
            recorded = list(rec["shown_tags"])
        elif source == "G6":
            assert rec is not None
            question, rq, recorded = rec["text"], None, None
        else:
            question, rq, recorded = AUTHORED[item], None, None
        ask_text = rec["question"] if rec is not None and source in ("G2", "G4") else question
        view = app.offline_legal_hits(ask_text, ret, retrieval_query=rq)
        excerpts = [(e["tag"], e["text"], e["doc_id"], e["ref"]) for e in view["excerpts"]]
        for tag, _, d, r in excerpts:
            if tag != cite_tag(d, r):
                fails.append("%s tag %s not cite_tag(%s, %s)" % (item, tag, d, r))

        if source == "authored-h6":
            ai_answer, ai_tags = OFFLINE_ONLY, []
        else:
            assert rec is not None
            ans, err = answer_of(source, rec)
            if ans is None or err:
                ai_answer, ai_tags = NO_AI, []
            else:
                ai_answer = ans
                ai_tags = list(dict.fromkeys("[%s]" % t for t in rag.extract_citations(ans)))
                if rec.get("citations") is not None and \
                        rag.extract_citations(ans) != rec["citations"]:
                    fails.append("%s: extracted citations != recorded citations" % item)

        shown = [t for t, _, _, _ in excerpts]
        sheet_note = ""
        if (source, item) in STALE_ANSWER_NOTES:
            frag, sheet_note = STALE_ANSWER_NOTES[(source, item)]
            if frag not in ai_answer or any(frag in txt for _, txt, _, _ in excerpts):
                fails.append("%s: stale-answer note no longer applies (fragment %r)" % (item, frag))
        rows.append({
            "row_id": "H6-%02d" % n,
            "source": "authored-h6" if source == "authored-h6"
                      else "%s %s#%s" % (source, Path(SOURCES[source]).name, item),
            "category": cat,
            "question": question,
            "excerpts": excerpts,
            "ai_answer": ai_answer,
            "ai_tags": ai_tags,
            "sheet_note": sheet_note,
            "recorded": recorded,
            # The AI transcripts were recorded on v2 and never saw a Regs excerpt,
            # so the comparison is against today's NON-Regs tags.
            "recorded_match": None if recorded is None else recorded == [
                t for t, _, d, _ in excerpts if d != REGS],
            "_src": source, "_item": item,
        })

    # ---- CSV -----------------------------------------------------------------
    cols = ["row_id", "source", "category", "question", "offline_excerpts", "ai_answer",
            "ai_tags", "sheet_note", "correct", "partially", "wrong", "harmful",
            "reviewer_note", "what_it_should_have_said"]
    buf = io.StringIO(newline="")
    w = csv.writer(buf)  # default dialect: CRLF, minimal quoting -- Excel-friendly
    w.writerow(cols)
    def csv_join(excerpts):
        out, noted = [], False
        for t, txt, d, _ in excerpts:
            if d == REGS and not noted:
                out.append(NOTE)               # once, before the first Regs excerpt
                noted = True
            out.append("%s %s" % (t, txt))
        return CSV_SEP.join(out)

    for r in rows:
        exc = csv_join(r["excerpts"]) or NO_EXCERPTS
        w.writerow([r["row_id"], r["source"], r["category"], r["question"], exc,
                    r["ai_answer"], "; ".join(r["ai_tags"]), r["sheet_note"],
                    "", "", "", "", "", ""])
    csv_text = buf.getvalue()
    for r in rows:
        r["csv_excerpts"] = csv_join(r["excerpts"])

    # ---- MD ------------------------------------------------------------------
    md = []
    add = md.append
    differs = [r["row_id"] for r in rows if r["recorded_match"] is False]
    matches = [r["row_id"] for r in rows if r["recorded_match"] is True]
    no_record = [r["row_id"] for r in rows if r["recorded"] is None]
    no_ai = [r["row_id"] for r in rows if r["ai_answer"] in (NO_AI, OFFLINE_ONLY)]
    add("# DRLCA legal review sheet (H6)")
    add("")
    add("## A note for the reviewer")
    add("")
    add("Thank you for agreeing to read this. **DRLCA** is a free website that answers questions "
        "about the rights of persons with disabilities in Nigeria. It answers only from four "
        "documents: the **Discrimination Against Persons with Disabilities (Prohibition) Act 2018**, "
        "the **1999 Constitution**, a **2020 Factsheet** that summarises the Act, and (new in this "
        "version of the sheet) the **Persons with Disabilities (Accessibility) Regulations, 2023** "
        "(S.I. No. 51 of 2023). It also points people to the DRAC helplines and to disability "
        "organisations.")
    add("")
    add("*This sheet replaces the earlier three-document version you may have received "
        "(`h6_review_sheet_v2_2026-10-21`, kept unchanged). The questions and AI answers are the "
        "same; the excerpts now come from the four documents, and there are four new questions "
        "about the Regulations just below.*")
    add("")
    add("**What every user sees.** For each question the site shows short passages (\"excerpts\") "
        "taken word for word from the three documents. Each excerpt starts with a citation tag that "
        "says where it came from:")
    add("")
    add("* `[Act cl. N]` \u2014 clause N of the Disability Act 2018")
    add("* `[Constitution s. N]` \u2014 section N of the 1999 Constitution")
    add("* `[Factsheet Section N]` \u2014 Section N of the 2020 Factsheet")
    add("* `[Regs reg. N]` \u2014 regulation N of the Accessibility Regulations 2023 "
        "(`[Regs general]` is their unnumbered opening text: title, commencement date and "
        "enacting power)")
    add("")
    add("These four numbering schemes are different: Act clause 12, Constitution section 12 and "
        "regulation 12 are not the same provision. The excerpt text is copied exactly as it appears in our copy of "
        "each document, including any scanning errors (odd characters, broken words), because we "
        "never alter the source text without a human check. The site shows the first three excerpts "
        "and folds the rest under a \"more\" link.")
    add("")
    add("**A fixed note on the Regulations.** Whenever excerpts from the Regulations are shown, the "
        "site shows one fixed, hand-written note about their legal status (\"About this source: "
        "...\") once, just before the first Regulations excerpt, and reads it aloud there. It is "
        "the same text every time and is never generated by the AI. It appears in this sheet "
        "exactly where a user would see it.")
    add("")
    add("**The AI answer is optional.** A user can switch on an \"AI answer\" that writes a short "
        "plain-English answer from the excerpts, with a citation tag after each claim. It is "
        "**OFF by default**, so most users only ever see the excerpts. The AI answers in this sheet "
        "were recorded in September and October 2026 in our own tests. A refusal (\"I can't answer "
        "this from the Disability Act 2018, the 1999 Constitution, or the factsheet I have...\") is "
        "the intended behaviour when the documents do not answer the question. **The AI answers "
        "were recorded before the Regulations were added, and the AI does not yet use the "
        "Regulations excerpts** (the site says so next to the AI answer).")
    add("")
    add("**What we would like from you.** For each question below:")
    add("")
    add("1. Read the question, the excerpts, and the AI answer.")
    add("2. Mark **one** of the four boxes with an **X**:")
    add("   * **Correct** \u2014 the answer is legally right and complete enough to rely on.")
    add("   * **Partially** \u2014 right in part, but something important is missing or imprecise.")
    add("   * **Wrong** \u2014 the answer misstates the law.")
    add("   * **Harmful** \u2014 the answer could lead a person with disability to lose a right, give "
        "up a claim, or take an unsafe step. Use this instead of Wrong when that is the case.")
    add("3. Where there is no AI answer (marked *offline only*), judge whether the excerpts shown "
        "would point a reader to the right law. For a refusal, judge whether refusing was right.")
    add("4. Add a short note, and if the answer was not correct, write what it should have said.")
    add("")
    add("You can fill in this printed copy, or the spreadsheet version of the same rows "
        "(`h6_review_sheet.csv`). **Please ignore the internal ID line under each question** "
        "(for example `H6-01 \u00b7 G2 ...`); it only helps us match your answers back to our "
        "records.")
    add("")
    add("**About the excerpts in this sheet.** No test record stored the excerpt text itself, so "
        "the excerpts for **all %d questions were recomputed when this sheet was built**, using the "
        "same search the live site uses. For %d questions we had kept the list of citation tags "
        "shown at the time the AI answer was recorded: leaving aside the new Regulations excerpts, "
        "today's list is the same for %d of them "
        "(%s) and different for %d (%s). The other %d questions had no earlier list to compare "
        "(%s). Separately, the wording of a few Act clauses (for example clause 1) was corrected "
        "against the official text after some AI answers were recorded, so an AI answer may quote "
        "scanning errors that no longer appear in the excerpt above it. Please judge the law, not "
        "the scanning errors."
        % (len(rows), len(matches) + len(differs), len(matches), ", ".join(matches) or "none",
           len(differs), ", ".join(differs) or "none", len(no_record),
           ", ".join(no_record) or "none"))
    add("")
    n_words = len(NOTE.split())
    n_regs_rows = sum(any(d == REGS for _, _, d, _ in r["excerpts"]) for r in rows)
    n_regs_inline = sum(any(d == REGS for _, _, d, _ in r["excerpts"][:app.INLINE_EXCERPTS])
                        for r in rows)
    add("## Four questions about the Accessibility Regulations (new)")
    add("")
    add("Please answer these before the question-by-question part. Short answers are fine.")
    add("")
    add("**(i) The status note.** This is the exact text the site shows (and reads aloud) before "
        "the first Regulations excerpt:")
    add("")
    add("> " + note_md(NOTE))
    add("")
    add("Is it legally accurate? Is anything in it wrong, overstated or missing (for example who "
        "imposes the administrative penalty, and the relationship to penalties under the Act)?")
    add("")
    add("**Your answer:**")
    add("")
    add("&nbsp;")
    add("")
    add("**(ii) The commencement date.** The gazette prints \"[22nd day of May, 2023]\" beside the "
        "marginal note \"Commencement.\", but the gazette itself was published on 7 July 2023 "
        "(Official Gazette No. 122, Vol. 110). Is it right to tell users the Regulations commenced on "
        "22 May 2023? If you know of any later amendment to the Regulations, please say so.")
    add("")
    add("**Your answer:**")
    add("")
    add("&nbsp;")
    add("")
    add("**(iii) How often the note appears.** The note is about %d words. The search shows a "
        "Regulations excerpt for most questions, including many that are not about accessibility "
        "(in our own test questions, about 86%% of turns; in this sheet, %d of %d questions, %d of "
        "them among the first three excerpts). Is a note of this length acceptable on most answers, "
        "or would you prefer a short one-line lead (for example \"These are binding regulations "
        "made under the Act\") with the full text folded behind a \"more\" link?"
        % (n_words, n_regs_rows, len(rows), n_regs_inline))
    add("")
    add("**Your answer:**")
    add("")
    add("&nbsp;")
    add("")
    add("**(iv) Quoting the texts.** May a free, non-commercial legal-information tool quote "
        "Nigerian Acts and Statutory Instruments (here the Act 2018 gazette and S.I. No. 51 of "
        "2023) verbatim, with citation? The project owner has signed off on this, and we would "
        "welcome your view.")
    add("")
    add("**Your answer:**")
    add("")
    add("&nbsp;")
    add("")
    add("---")
    add("")
    for i, r in enumerate(rows, 1):
        add("## Question %d of %d \u2014 %s" % (i, len(rows), CATEGORIES[r["category"]]))
        add("")
        add("*Internal ID (please ignore): %s \u00b7 %s*" % (r["row_id"], r["source"]))
        add("")
        add("**Question:** %s" % r["question"])
        add("")
        add("### What every user sees (excerpts)")
        add("")
        if not r["excerpts"]:
            add(NO_EXCERPTS)
            add("")
        noted = False
        for j, (tag, txt, d, _) in enumerate(r["excerpts"], 1):
            if d == REGS and not noted:
                add("*Fixed note shown before the first Regulations excerpt:*")
                add("")
                add("> " + note_md(NOTE))
                add("")
                noted = True
            add("**%s** (excerpt %d of %d)" % (tag, j, len(r["excerpts"])))
            add("")
            for line in txt.split("\n"):
                add(("> " + md_excerpt_line(line)).rstrip())
            add("")
        if r["recorded_match"] is False:
            add("*Note: leaving aside the Regulations, the excerpts shown when the AI answer below "
                "was recorded were slightly different: %s.*" % ", ".join(r["recorded"]))
            add("")
        add("### AI answer (optional feature, off by default)")
        add("")
        if r["sheet_note"]:
            add("**Please note:** %s" % r["sheet_note"])
            add("")
        if r["ai_answer"] in (NO_AI, OFFLINE_ONLY):
            add("*%s*" % r["ai_answer"])
        else:
            add(r["ai_answer"])
        add("")
        add("**Citation tags the AI used:** %s" % ("; ".join(r["ai_tags"]) or "none"))
        add("")
        add("### Your verdict (mark one with an X)")
        add("")
        add("| Correct | Partially | Wrong | Harmful |")
        add("|:---:|:---:|:---:|:---:|")
        add("| \u00a0 | \u00a0 | \u00a0 | \u00a0 |")
        add("")
        add("**Note:**")
        add("")
        add("&nbsp;")
        add("")
        add("**What it should have said:**")
        add("")
        add("&nbsp;")
        add("")
        add("---")
        add("")
    add("*Technical note for the DRLCA team: generated by `scripts/build_h6_review.py` from %s; "
        "corpus %s chunk-stream sha256 `%s`; excerpts via `app.offline_legal_hits` "
        "(k=4/doc, top_n=%d); status note `rag.DOC_STATUS_NOTES[\"%s\"]` verbatim. Zero network "
        "calls. A line-initial `N.` in excerpt text is written "
        "`N\\.` here so Markdown does not renumber it; the CSV holds the raw text.*"
        % (", ".join("`%s`" % p for p in SOURCES.values()), version, corpus_sha256(docs),
           top_n, REGS))
    md_text = "\n".join(md) + "\n"

    # ---- checks --------------------------------------------------------------
    print("== build_h6_review: %d rows ==" % len(rows))
    check(20 <= len(rows) <= 30, "row count %d in 20..30" % len(rows))
    cats = [r["category"] for r in rows]
    check(cats.count("off-corpus") == 2, "exactly 2 off-corpus rows (%d)" % cats.count("off-corpus"))
    check(set(cats) == set(CATEGORIES), "every category present: %s"
          % {c: cats.count(c) for c in CATEGORIES})
    check(len({r["row_id"] for r in rows}) == len(rows), "row ids unique")
    check(len({(r["_src"], r["_item"]) for r in rows}) == len(rows), "no source item used twice")
    check(not set(SOURCES.values()) & set(FORBIDDEN), "no row sourced from a forbidden file")
    check(all(r["source"] == "authored-h6" or r["source"].split(" ")[1].split("#")[0]
              in {Path(p).name for p in SOURCES.values()} for r in rows),
          "every row's source is an allowed transcript or authored-h6")
    bad = []
    for r in rows:
        for tag, txt, d, ref in r["excerpts"]:
            if tag not in r["csv_excerpts"] or tag not in md_text or tag != cite_tag(d, ref):
                bad.append((r["row_id"], tag))
        if r["ai_tags"]:
            ans, _ = answer_of(r["_src"], src[r["_src"]][r["_item"]])
            bad += [(r["row_id"], t) for t in r["ai_tags"] if t not in ans]
    check(not bad, "every excerpt/AI tag verbatim in its source (rag output / transcript)%s"
          % ("" if not bad else ": %s" % bad[:5]))
    check(all(r["ai_answer"] == OFFLINE_ONLY for r in rows if r["_src"] == "authored-h6")
          and all(r["ai_answer"] != OFFLINE_ONLY for r in rows if r["_src"] != "authored-h6"),
          "offline-only placeholder used exactly on authored rows")
    unequal = []
    for r in rows:
        if r["_src"] != "authored-h6" and r["ai_answer"] != NO_AI:
            ans, _ = answer_of(r["_src"], src[r["_src"]][r["_item"]])
            if r["ai_answer"] != ans:
                unequal.append(r["row_id"])
    check(not unequal, "every AI answer byte-identical to its transcript%s"
          % ("" if not unequal else ": %s" % unequal))
    stale_fails = [f for f in fails if "stale-answer note" in f]
    check(not stale_fails and sum(bool(r["sheet_note"]) for r in rows) == len(STALE_ANSWER_NOTES),
          "every stale-answer note still applies and is attached (%d)" % len(STALE_ANSWER_NOTES))
    for name, text in (("csv", csv_text), ("md", md_text)):
        hits = CONTROL_RE.findall(text)
        check(not hits, "%s has no control characters%s" % (name, "" if not hits
                                                            else ": %r" % sorted(set(hits))))
    # H8a.5 (F10): the note is in the reviewer block verbatim, and in every row that
    # shows a Regs excerpt exactly once, immediately before the first one.
    nm = "> " + note_md(NOTE)
    misplaced = []
    for r in rows:
        regs = [j for j, (_, _, d, _) in enumerate(r["excerpts"]) if d == REGS]
        want = 1 if regs else 0
        if r["csv_excerpts"].count(NOTE) != want:
            misplaced.append(r["row_id"])
        elif regs and r["csv_excerpts"].split(CSV_SEP)[regs[0]] != NOTE:
            misplaced.append(r["row_id"])
    check(version == "v3" and top_n == 16, "pack built on %s at top_n=%d" % (version, top_n))
    check(not misplaced and md_text.count(nm) == n_regs_rows + 1 and n_regs_rows > 0,
          "status note verbatim: reviewer block + once per Regs row before its first Regs "
          "excerpt (%d rows)%s" % (n_regs_rows, "" if not misplaced else ": %s" % misplaced))
    check(all(q in md_text for q in ("**(i) The status note.**", "**(ii) The commencement date.**",
                                     "**(iii) How often the note appears.**",
                                     "**(iv) Quoting the texts.**")),
          "reviewer question block (i)-(iv) present")
    build_fails = [f for f in fails if ":" in f and ("cite_tag" in f or "citations" in f)]
    check(not build_fails, "build-time tag/citation consistency%s"
          % ("" if not build_fails else ": %s" % build_fails))

    print("\nby source: %s" % {s: sum(r["_src"] == s for r in rows)
                               for s in ("G2", "G4", "G6", "authored-h6")})
    print("no AI answer: %s" % (", ".join(no_ai) or "none"))
    print("excerpt tag list vs recorded: match %s | differs %s | none recorded %s"
          % (matches, differs, no_record))

    if fails:
        print("\nFAILURES:")
        for f in fails:
            print("  - %s" % f)
        print("nothing written")
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_CSV.write_bytes(b"\xef\xbb\xbf" + csv_text.encode("utf-8"))
    OUT_MD.write_bytes(md_text.encode("utf-8"))
    print("\nwrote %s (%d bytes)\nwrote %s (%d bytes)\nALL PASS"
          % (OUT_CSV.relative_to(ROOT), OUT_CSV.stat().st_size,
             OUT_MD.relative_to(ROOT), OUT_MD.stat().st_size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
