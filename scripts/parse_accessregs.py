"""Parse the Accessibility Regulations 2023 gazette into a regulation manifest.

Run: C:\\conda-envs\\drlca-rag\\python.exe -I scripts\\parse_accessregs.py
     ... --out=<path>   manifest out (default data/processed/accessregs2023_regs.json)
     ... --report       print every regulation's header, flags and length

METHOD. The source (S.I. No. 51 of 2023, data/raw/SOURCES.md row 4) is born-digital, so
this reads pymupdf's text layer directly; nothing is OCRed. Each page carries a body
column and a marginal-note column (the regulation titles, set in 8 pt) whose side
alternates: right on odd pages (x0 >= 455), left on even pages (x1 <= 172). Lines are
split into the two columns by x alone, and the script ASSERTS that every 8 pt line falls
in the note band and every other line in the body band, so a layout it was not measured
on fails loudly instead of leaking notes into bodies. A regulation starts at a body line
whose first span is bold and reads "N." with N exactly one more than the last; its
header is "N. <marginal note>", the note being the 8 pt group (wrapped lines closer than
11.5 pt) whose top sits nearest that line within 3 pt above to 15 pt below it (measured
offsets run 0 to ~11 pt), one note per regulation; a regulation with no note, or a note
with no regulation, is flagged/listed, never guessed. The number comes from the BODY and is cross-checked by position against
the Arrangement (pp. 3-7), which prints "132. Braille" for the body's 133: such a
mismatch is a flag, never a fix. CHAPTER/PART headings are removed from bodies and kept
as `chapter`/`part` fields; the "B 13xx" page numbers are dropped. The unnumbered
enacting formula on p. 9 (title block, "[22nd day of May, 2023]" with its marginal note
"Commencement.", and the "In exercise of the powers ..." paragraph) becomes `preamble`.
Text is VERBATIM: lines are joined with one space exactly as parse_act_v2.py joins OCR
rows, so a line-end hyphen stays ("barrier- free", "Commence- ment."), "N 500,000" stays,
and nothing is renumbered or normalised. The First Schedule (p. 69 on, figures) is out
of scope. Deterministic: same PDF in, byte-identical JSON out.

DEV ENV ONLY (pymupdf). src/rag.py reads the JSON this writes with stdlib json; the JSON
is the seam, exactly as for parse_act_v2.py -> act2018_v2_clauses.json.
"""

import difflib
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "data" / "raw" / "accessibility_regulations_2023_gazette_FGP.pdf"
OUT = ROOT / "data" / "processed" / "accessregs2023_regs.json"
PDF_SHA256 = "04bb8bec217b6ca01fa3ac3e5b5893ed619b2970ea7cb4b81f4ba2c047f28b05"

ARRANGEMENT_PAGES = range(3, 8)      # 1-based, inclusive 3..7
BODY_PAGES = range(9, 69)            # 1-based, inclusive 9..68
N_REGS = 172
TITLE_MATCH = 0.72                   # same threshold as parse_act_v2.py
NOTE_SIZE_MAX = 8.5                  # marginal notes are 8.0 pt; body 10.4-11.0
ODD_NOTE_X0 = 455.0                  # odd pages: note column starts right of this
EVEN_NOTE_X1 = 172.0                 # even pages: note column ends left of this
NOTE_ABOVE = 3.0                     # pt: a note may start this far ABOVE its line
NOTE_BELOW = 15.0                    # ...and this far below it (measured up to ~11)
NOTE_GAP = 11.5                      # pt: wrapped note lines ~9.6 apart, notes >= 13

FURNITURE_RE = re.compile(r"^B \d{4}$")
START_RE = re.compile(r"^(\d{1,3})\.(?!\d)")
HEAD_RE = re.compile(r"^(CHAPTER|PART)\s+[A-Z]")
ARR_NUM_RE = re.compile(r"^(\d{1,3})\.$")


def norm(s: str) -> str:
    """Same normalisation as parse_act_v2.norm(): compare letters and digits only."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def page_lines(page) -> list[dict]:
    """Non-blank text lines with geometry, size and first-span boldness."""
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            spans = [s for s in l["spans"] if s["text"].strip()]
            if not spans:
                continue
            text = "".join(s["text"] for s in l["spans"]).strip()
            out.append({
                "text": text,
                "x0": l["bbox"][0], "x1": l["bbox"][2], "y": l["bbox"][1],
                "size": max(s["size"] for s in spans),
                "bold": "Bold" in spans[0]["font"],
            })
    out.sort(key=lambda d: (round(d["y"], 1), d["x0"]))
    return out


def split_columns(pno: int, lines: list[dict]) -> tuple[list[dict], list[dict]]:
    """(body, notes) for one page, by x band. Asserts the bands are clean."""
    body, notes = [], []
    for l in lines:
        if FURNITURE_RE.match(l["text"]):
            continue
        in_note_band = (l["x0"] >= ODD_NOTE_X0) if pno % 2 else (l["x1"] <= EVEN_NOTE_X1)
        is_note_size = l["size"] <= NOTE_SIZE_MAX
        if in_note_band != is_note_size:
            raise SystemExit("p.%d: line %r (x %.1f-%.1f, %.1f pt) breaks the column model"
                             % (pno, l["text"], l["x0"], l["x1"], l["size"]))
        (notes if in_note_band else body).append(l)
    return body, notes


def group_notes(notes: list[dict]) -> list[dict]:
    """Group wrapped note lines: a gap wider than NOTE_GAP starts a new note."""
    groups: list[dict] = []
    for l in notes:
        if groups and l["y"] - groups[-1]["last_y"] <= NOTE_GAP:
            groups[-1]["lines"].append(l["text"])
            groups[-1]["last_y"] = l["y"]
        else:
            groups.append({"y": l["y"], "last_y": l["y"], "lines": [l["text"]]})
    return groups


def assign_notes(groups: list[dict], anchors_y: list[float]) -> dict[int, int]:
    """anchor index -> note group index, one-to-one.

    A note sits level with, or a little below, the line it annotates (measured offsets
    0 to ~11 pt). Each group goes to the nearest anchor inside [-NOTE_ABOVE, +NOTE_BELOW];
    ties and leftovers are reported by the caller, never guessed.
    """
    pairs = sorted(
        (abs(g["y"] - a), ai, gi)
        for gi, g in enumerate(groups) for ai, a in enumerate(anchors_y)
        if -NOTE_ABOVE <= g["y"] - a <= NOTE_BELOW)
    out: dict[int, int] = {}
    taken: set[int] = set()
    for _, ai, gi in pairs:
        if ai not in out and gi not in taken:
            out[ai] = gi
            taken.add(gi)
    return out


def parse_arrangement(doc) -> list[tuple[int, str]]:
    """Ordered (printed number, title) list. Ordered, not keyed: it prints 132 twice."""
    entries: list[list] = []
    for pno in ARRANGEMENT_PAGES:
        for l in page_lines(doc[pno - 1]):
            t = l["text"]
            m = ARR_NUM_RE.match(t)
            if m:
                entries.append([int(m.group(1)), []])
            elif FURNITURE_RE.match(t) or HEAD_RE.match(t) or t.isupper() or t.startswith("Regulation"):
                continue
            elif entries:
                entries[-1][1].append(t)
    return [(n, " ".join(parts)) for n, parts in entries]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    out_path = OUT
    report = "--report" in argv
    for a in argv:
        if a.startswith("--out="):
            out_path = Path(a.split("=", 1)[1])
    sys.stdout.reconfigure(encoding="utf-8")

    sha = hashlib.sha256(PDF.read_bytes()).hexdigest()
    assert sha == PDF_SHA256, "source PDF sha256 %s != pinned %s" % (sha, PDF_SHA256)
    doc = pymupdf.open(PDF)
    assert doc.page_count == 173, doc.page_count

    arrangement = parse_arrangement(doc)
    assert len(arrangement) == N_REGS, "Arrangement lists %d entries" % len(arrangement)

    regs: list[dict] = []
    preamble = {"header": None, "text": None, "pages": [9], "margin_notes": []}
    pre_lines: list[str] = []
    in_preamble = True
    chapter, part, pending_chapter = None, None, False
    unmatched_notes: list[dict] = []
    headings: list[dict] = []

    for pno in BODY_PAGES:
        body, notes = split_columns(pno, page_lines(doc[pno - 1]))
        # Regulation-start candidates on this page (needed to group notes).
        expect = (regs[-1]["n"] + 1) if regs else 1
        starts = []
        for l in body:
            m = START_RE.match(l["text"])
            if l["bold"] and m and int(m.group(1)) == expect + len(starts):
                starts.append(l)
        anchors = [l["y"] for l in starts]
        if pno == 9:
            date = [l for l in body if l["text"].startswith("[22nd day of May, 2023]")]
            assert len(date) == 1, "p.9 commencement date line not found"
            anchors.append(date[0]["y"])
        groups = group_notes(notes)
        assigned = assign_notes(groups, anchors)
        by_y = {anchors[ai]: " ".join(groups[gi]["lines"]) for ai, gi in assigned.items()}
        used = set(assigned.values())

        def note_for(y: float) -> str | None:
            return by_y.get(y)

        start_ids = {id(l) for l in starts}
        for l in body:
            t = l["text"]
            if HEAD_RE.match(t):
                if t.startswith("CHAPTER"):
                    chapter, part = t, None
                    pending_chapter = "—" not in t
                else:
                    part, pending_chapter = t, False
                headings.append({"page": pno, "text": t})
                in_preamble = False
                continue
            if pending_chapter and t.isupper():
                chapter = "%s—%s" % (chapter, t)      # "CHAPTER ONE" + its subtitle line
                headings.append({"page": pno, "text": t})
                pending_chapter = False
                continue
            pending_chapter = False
            if id(l) in start_ids:
                n = int(START_RE.match(t).group(1))
                arr_n, arr_title = arrangement[n - 1]
                note = note_for(l["y"])
                flags = []
                if arr_n != n:
                    flags.append("ARRANGEMENT_NUMBER_MISMATCH")
                if note is None:
                    flags.append("NOTE_MISSING")
                title = note if note is not None else arr_title
                r = round(ratio(title, arr_title), 4)
                if r < TITLE_MATCH:
                    flags.append("TITLE_MISMATCH")
                regs.append({"n": n, "title": title, "header": "%d. %s" % (n, title),
                             "arrangement_n": arr_n, "arrangement_title": arr_title,
                             "chapter": chapter, "part": part, "pages": [pno],
                             "flags": flags, "title_ratio": r, "_lines": [t]})
                in_preamble = False
                continue
            if in_preamble:
                pre_lines.append(t)
                if t.startswith("[22nd day of May, 2023]"):
                    note = note_for(l["y"])
                    assert note is not None, "p.9 commencement marginal note not found"
                    preamble["margin_notes"].append({"text": note, "beside": t})
                    pre_lines.append(note)     # restored beside the line it annotates
                continue
            assert regs, "body text before regulation 1 outside the preamble: %r" % t
            regs[-1]["_lines"].append(t)
            if pno not in regs[-1]["pages"]:
                regs[-1]["pages"].append(pno)
        for gi, g in enumerate(groups):
            if gi not in used:
                unmatched_notes.append({"page": pno, "text": " ".join(g["lines"])})

    for r in regs:
        r["text"] = " ".join(r.pop("_lines"))
        if not START_RE.sub("", r["text"]).strip(" .—-"):
            r["flags"].append("EMPTY")
    preamble["header"] = ("Persons with Disabilities (Accessibility) Regulations, 2023"
                          " — enacting formula")
    preamble["text"] = " ".join(pre_lines)

    nums = [r["n"] for r in regs]
    assert nums == list(range(1, N_REGS + 1)), "regulations found: %d, gaps/order wrong" % len(nums)
    for r in regs:
        assert "B 13" not in r["text"] and "B 14" not in r["text"], r["n"]

    blob = {
        "source": PDF.name,
        "source_sha256": sha,
        "title_source": "marginal_note",
        "arrangement_pages": [ARRANGEMENT_PAGES.start, ARRANGEMENT_PAGES.stop - 1],
        "body_pages": [BODY_PAGES.start, BODY_PAGES.stop - 1],
        "located": len(regs),
        "missing": N_REGS - len(regs),
        "headings": headings,
        "unmatched_notes": unmatched_notes,
        "preamble": preamble,
        "regs": regs,
    }
    out_path.write_text(json.dumps(blob, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    lens = [len(r["text"]) for r in regs]
    flagged = [(r["n"], r["flags"]) for r in regs if r["flags"]]
    if report:
        for r in regs:
            print("%3d %-60s %-34s %5d %.2f" % (r["n"], r["header"][:60], ",".join(r["flags"]) or "ok",
                                              len(r["text"]), r["title_ratio"]))
    print("regulations: %d located, %d missing" % (len(regs), N_REGS - len(regs)))
    print("flags: %s" % (flagged or "none"))
    print("unmatched marginal notes: %s" % (unmatched_notes or "none"))
    print("body length min/median/max: %d / %d / %d" % (min(lens), statistics.median(lens), max(lens)))
    print("preamble: %d chars, margin notes %s" % (len(preamble["text"]),
                                                  [m["text"] for m in preamble["margin_notes"]]))
    print("PARSE_ACCESSREGS: OK -> %s" % out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
