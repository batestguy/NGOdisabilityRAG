"""Parse the Act's 58 clauses out of the gazette OCR. Layer 2 of three.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\parse_act_v2.py
     ... --json=<ckpt>     OCR checkpoint in  (default below)
     ... --out=<path>      clause manifest out (default below)
     ... --body-from=5     first body page, 1-based (default: located, not assumed)
     ... --report          print every clause's anchor decision

STDLIB ONLY -- no pymupdf, no rapidocr, no numpy. That is the whole point of
this layer. `src/rag.py::_act_chunks_v2()` will read the JSON this emits, so if
this file ever needs an OCR dependency the slim Render runtime is gone. The
JSON artifact is the seam.

  OCR      scripts/ocr_gazette.py   pymupdf + rapidocr   dev-only
  parse    THIS FILE                stdlib               dev-only
  runtime  src/rag.py               reads the JSON       ships

WHAT ANCHORS A CLAUSE
---------------------
Two anchors, both required: the NUMERAL in the body column and the TITLE in the
marginal-note column. One anchor is a guess. Titles are never authored and never
inferred from body text -- they come from data/processed/gazette_arrangement.json,
the 58-entry manifest the D2 gate verified. This file may REJECT a title match;
it may not invent one.

Degraded acceptances are flagged, never silent:
  TITLE_WEAK       numeral found, title match below threshold
  NUMERAL_MISSING  title found, numeral unreadable (cl.40's exact case in v1)
  NOTE_UNMATCHED   a marginal note that matches no manifest title (expected:
                   cross-references like "First Schedule.")
Neither anchor -> the clause is reported missing and the run exits nonzero. No
guessing, no interpolation between neighbours.
"""

import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from ocrlib import rows, x_left, x_right, y_top, y_bottom  # noqa: E402

CKPT_IN = ROOT / "data" / "processed" / "gazette_rapidocr.json"
MANIFEST = ROOT / "data" / "processed" / "gazette_arrangement.json"
OUT = ROOT / "data" / "processed" / "act2018_v2_clauses.json"

ACT_CLAUSES = range(1, 59)
TITLE_MATCH = 0.72          # SequenceMatcher on normalised titles
MAX_NOTE_LINES = 6          # longest observed wrapped note is 5 lines (cl.5)

# "5. Road side-walks", "6.From the date", "7.-(1l) Before", "9.<?>(1) A person".
# The gazette's em-dash OCRs variously as '-', '—' or the replacement char,
# so the separator class is permissive -- but the numeral must OPEN the row.
NUM_RE = re.compile(r"^\s*(\d{1,2})\s*[.,\-–—�]")

# Running heads, printed page numbers, part headings. Not body, not notes.
#
# (?-i:...) on the PART alternative is LOAD-BEARING, not tidiness. The gazette
# prints its part headings with the space eaten by OCR ('PARTVI-OPPORTUNITY'),
# so the pattern cannot require a word boundary after PART -- and under the
# global IGNORECASE that made 'Participation' match PART + [IVX], which silently
# deleted clause 30's marginal note ('Participation' / 'in politics.') from the
# note column. Clause 30 was then left matching on 'in politics.' alone, scored
# 0.61, and came out TITLE_WEAK. Part headings are set in caps; the clause title
# is not, so case is exactly the discriminator.
FURNITURE_RE = re.compile(
    r"^\s*(A\s?\d{2,3}|\d{4}\s*No\.?\s*\d+|(?-i:PART\s*[IVX])"
    r"|Discrimination\s*against|Discriminationagainst|\(Prohibition\)"
    r"|ARRANGEMENT\b|SCHEDULE)", re.IGNORECASE)

# The Schedules and Forms follow clause 58 with no further clause anchor, so
# without this bound '58. Citation.' -- a one-sentence clause -- absorbs 5,480
# characters of First/Second Schedule text and every retrieval for it is wrong.
SCHEDULE_RE = re.compile(r"^\s*(FIRST|SECOND|THIRD|FOURTH)\s+SCHEDULE", re.I)


def norm(s: str) -> str:
    """Titles are compared with punctuation and spacing removed entirely.

    The manifest itself carries OCR join artifacts -- 'Functions ofthe
    Commission.', 'Accessibility toroads,side-walk' -- and the marginal notes
    carry different ones. Comparing raw strings scores a true match low for a
    reason that has nothing to do with whether it is the right clause.
    """
    return re.sub(r"[^a-z0-9]", "", s.lower())


def ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def note_lines(lines: list[dict]) -> list[dict]:
    """Identify this page's marginal-note column. Band first, then refine.

    DETECTED PER PAGE, NEVER HARDCODED -- the gazette alternates verso/recto and
    the note column flips with it (measured on this scan: p5 right x1160-1300,
    p6 LEFT x105-245, p7 right x1140-1290). A hardcoded side drops every note on
    half the document, and since the note is one of the two required anchors,
    that half silently degrades to numeral-only acceptance.

    TWO EARLIER VERSIONS FAILED HERE, both by trusting an extremum:

    1. Splitting on the widest horizontal GAP reintroduced the verso/recto
       asymmetry by accident -- on recto the body-to-note gap is ~418px and it
       fired, on verso it is ~154px and it did not. Verso notes stayed in the
       body, rows() welded them onto the body row, and the text became
       'Accessibility 5. Road side-walks...', which no numeral regex anchored at
       the start can match. Clauses 5-8, 13-15, 21-27 and 32-34 vanished.
    2. Taking the body extent as min/max over wide lines broke on single
       outliers. On p11 one OCR box merged a note into the body line
       ('31.-(1) There is established the National Co...', x271-1321 against a
       ~1156 body edge) and swallowed all 13 notes; on p13 the body edge landed
       at 1161 against notes starting at 1164, clipping 'Functions of' and
       'Commission.' -- i.e. clause 38's own title -- into the body.

    So: take NARROW lines in the outer quarter of the measure as candidates
    (using x_right on the left side and x_left on the right, so a short trailing
    body line like 'the visually impaired.' cannot qualify), then re-select every
    line that falls inside the candidates' actual x-range. The refine pass is
    what recovers notes sitting a few pixels inside a band edge.
    """
    if len(lines) < 4:
        return []
    x0 = min(x_left(l) for l in lines)
    x1 = max(x_right(l) for l in lines)
    span = x1 - x0
    if span <= 0:
        return []

    def narrow(l):
        return (x_right(l) - x_left(l)) < 0.30 * span

    left = [l for l in lines if narrow(l) and x_right(l) < x0 + 0.25 * span]
    right = [l for l in lines if narrow(l) and x_left(l) > x0 + 0.75 * span]
    cand = left if len(left) > len(right) else right
    if len(cand) < 2:
        return []                       # single-column page (cover, forms)
    cx0 = min(x_left(l) for l in cand)
    cx1 = max(x_right(l) for l in cand)
    return [l for l in lines if x_left(l) >= cx0 - 12 and x_right(l) <= cx1 + 12]


def page_layout(lines: list[dict]) -> dict:
    """One page -> {'body': [row dicts], 'notes': [note lines, y-ordered]}.

    Notes are returned as LINES, not pre-joined groups. Grouping them by a
    y-gap threshold looked right and was not: within a wrapped note the gap
    measures about -2px, but two DIFFERENT notes on p13 ('Allowances of
    members.' / 'Powers of the Council.') sit only 28px apart, so any threshold
    loose enough to join a wrapped note also welds neighbouring clause titles
    into one string. best_window() matches over consecutive lines instead, which
    needs no threshold at all.
    """
    notes = note_lines(lines)
    note_ids = {id(l) for l in notes}
    body_lines = [l for l in lines if id(l) not in note_ids]
    body = []
    for row in rows(body_lines):
        text = re.sub(r"\s+", " ", " ".join(l["text"] for l in row)).strip()
        if not text or FURNITURE_RE.match(text):
            continue
        body.append({"text": text, "y0": min(y_top(l) for l in row),
                     "conf": min(l["conf"] for l in row)})
    notes = [{"text": re.sub(r"\s+", " ", l["text"]).strip(),
              "y0": y_top(l), "y1": y_bottom(l)}
             for l in sorted(notes, key=y_top)]
    return {"body": body,
            "notes": [n for n in notes
                      if n["text"] and not FURNITURE_RE.match(n["text"])]}


def best_window(notes: list[dict], title: str, used: set[int],
                near_y: float | None = None) -> tuple[float, int, int]:
    """Best match for `title` over any run of <=MAX_NOTE_LINES consecutive notes.

    Wrapped notes are the reason this is a window and not a line: 'Accessibility'
    / 'to roads' / 'side-walks' / 'and special' / 'facilities.' are five OCR
    lines and none of them matches the Arrangement title on its own. Searching
    windows rather than pre-grouping means a wrong grouping cannot cost a match.

    Returns (ratio, start, end_exclusive); ratio 0.0 when nothing is available.
    """
    best = (0.0, -1, -1)
    for i in range(len(notes)):
        if i in used:
            continue
        if near_y is not None and abs(notes[i]["y0"] - near_y) > 300:
            continue
        joined = ""
        for j in range(i, min(i + MAX_NOTE_LINES, len(notes))):
            if j in used:
                break
            joined = (joined + " " + notes[j]["text"]).strip()
            r = ratio(joined, title)
            if r > best[0]:
                best = (r, i, j + 1)
    return best


def locate(pages: dict[int, dict], titles: dict[int, str]) -> tuple[dict, list]:
    """Anchor every clause with a MONOTONIC CURSOR over (page, row).

    The cursor is what kills the 'section 27 of the Interpretation Act'
    false-positive class STRUCTURALLY -- no heuristic, no stop-list. That string
    sits at 89.8% of the document, long past where the cursor for any low clause
    number is looking, so it is never a candidate for clause 27 in the first
    place.
    """
    flat = []                                   # [(page, idx, row)] in order
    for p in sorted(pages):
        for i, row in enumerate(pages[p]["body"]):
            flat.append((p, i, row))

    found: dict[int, dict] = {}
    used: dict[int, set[int]] = {p: set() for p in pages}
    cursor = 0
    for n in ACT_CLAUSES:
        title = titles[n]
        hit = None
        for j in range(cursor, len(flat)):
            p, i, row = flat[j]
            m = NUM_RE.match(row["text"])
            if not m or int(m.group(1)) != n:
                continue
            # Second anchor: marginal notes on this page, beside this row,
            # whose joined text matches THIS clause's manifest title.
            r, s, e = best_window(pages[p]["notes"], title, used[p], row["y0"])
            hit = {"n": n, "page": p, "row": i, "flags": [],
                   "title_ratio": round(r, 3), "conf": row["conf"]}
            if r >= TITLE_MATCH:
                used[p].update(range(s, e))
            else:
                hit["flags"].append("TITLE_WEAK")
            cursor = j + 1
            break
        if hit is None:
            # NUMERAL_MISSING: fall back to the title anchor alone. This is
            # cl.40's exact case in v1 -- body present, numeral eaten by OCR.
            for p in sorted(pages):
                r, s, e = best_window(pages[p]["notes"], title, used[p])
                if r < TITLE_MATCH or not pages[p]["body"]:
                    continue
                ny = pages[p]["notes"][s]["y0"]
                idx = min(range(len(pages[p]["body"])),
                          key=lambda i: abs(pages[p]["body"][i]["y0"] - ny))
                flat_i = next((j for j, (pp, ii, _) in enumerate(flat)
                               if pp == p and ii == idx), None)
                if flat_i is None or flat_i < cursor:
                    continue
                used[p].update(range(s, e))
                hit = {"n": n, "page": p, "row": idx,
                       "flags": ["NUMERAL_MISSING"], "title_ratio": round(r, 3),
                       "conf": pages[p]["body"][idx]["conf"]}
                cursor = flat_i + 1
                break
        if hit:
            found[n] = hit

    # Body text: from each anchor to the next anchor, in flat order.
    order = sorted(found, key=lambda n: (found[n]["page"], found[n]["row"]))
    starts = {n: next(j for j, (p, i, _) in enumerate(flat)
                      if p == found[n]["page"] and i == found[n]["row"])
              for n in order}
    sched = next((j for j, (_, _, r) in enumerate(flat)
                  if SCHEDULE_RE.match(r["text"])), len(flat))
    for idx, n in enumerate(order):
        end = starts[order[idx + 1]] if idx + 1 < len(order) else sched
        body = [flat[j][2]["text"] for j in range(starts[n], end)]
        found[n]["text"] = " ".join(body)
        found[n]["pages"] = sorted({flat[j][0] for j in range(starts[n], end)})

    unmatched = []
    for p in sorted(pages):
        for k, g in enumerate(pages[p]["notes"]):
            if k not in used[p]:
                unmatched.append("p%d: %r" % (p, g["text"]))
    sched_page = flat[sched][0] if sched < len(flat) else None
    return found, unmatched, sched_page


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    def opt(name, default):
        return next((a.split("=", 1)[1] for a in argv
                     if a.startswith("--%s=" % name)), default)

    ckpt_p = Path(opt("json", CKPT_IN))
    out_p = Path(opt("out", OUT))
    assert ckpt_p.exists(), "no OCR checkpoint at %s -- run ocr_gazette.py" % ckpt_p
    assert MANIFEST.exists(), "no Arrangement manifest at %s" % MANIFEST

    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert man.get("clean"), "manifest is not clean; D2's gate must pass first"
    titles = {int(k): v for k, v in man["entries"].items()}
    assert sorted(titles) == list(ACT_CLAUSES), "manifest is not 1..58"

    ckpt = json.loads(ckpt_p.read_text(encoding="utf-8"))
    body_from = int(opt("body-from", 0))
    pages = {int(p): page_layout(ls) for p, ls in ckpt.items() if ls}
    if body_from:
        pages = {p: v for p, v in pages.items() if p >= body_from}

    print("== PARSE ACT v2 ==")
    print("  checkpoint : %s (%d pages)" % (ckpt_p.name, len(ckpt)))
    print("  manifest   : %d titles, source=%s"
          % (len(titles), man["title_source"]))
    for p in sorted(pages):
        nl = note_lines(ckpt[str(p)])
        col = ("x%.0f-%.0f" % (min(x_left(l) for l in nl),
                               max(x_right(l) for l in nl))) if nl else "none"
        print("  page %2d: %2d body rows, %2d note lines, note column %s"
              % (p, len(pages[p]["body"]), len(pages[p]["notes"]), col))

    found, unmatched, sched_page = locate(pages, titles)
    missing = [n for n in ACT_CLAUSES if n not in found]
    weak = [n for n in found if "TITLE_WEAK" in found[n]["flags"]]
    nonum = [n for n in found if "NUMERAL_MISSING" in found[n]["flags"]]

    if "--report" in argv:
        print("\n== ANCHORS ==")
        for n in sorted(found):
            f = found[n]
            print("  cl.%-2d p%-2d title_r=%.2f conf=%.2f %-16s %s"
                  % (n, f["page"], f["title_ratio"], f["conf"],
                     ",".join(f["flags"]) or "ok", f["text"][:52]))

    print("\n== CLAUSE LOCATOR ==")
    print("  located          : %d / 58" % len(found))
    print("  missing          : %s" % (missing or "none"))
    print("  TITLE_WEAK       : %s" % (weak or "none"))
    print("  NUMERAL_MISSING  : %s" % (nonum or "none"))
    print("  schedules begin  : p%s (clause text stops there; the Schedules "
          "are NOT clause text and are left for D3)" % sched_page)
    print("  notes unmatched  : %d" % len(unmatched))
    for u in unmatched:
        print("      %s" % u)

    out_p.write_text(json.dumps(
        {"source": man["source"], "title_source": man["title_source"],
         "located": len(found), "missing": missing,
         "clauses": [{"n": n, "title": titles[n],
                      "header": "%d. %s" % (n, titles[n]),
                      "pages": found[n].get("pages", [found[n]["page"]]),
                      "flags": found[n]["flags"],
                      "title_ratio": found[n]["title_ratio"],
                      "text": found[n].get("text", "")}
                     for n in sorted(found)]},
        indent=1), encoding="utf-8")
    print("  wrote %s" % out_p)

    if missing:
        print("\n  INCOMPLETE -- %d clauses have neither anchor. No stub is "
              "emitted and no title is authored for them." % len(missing))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
