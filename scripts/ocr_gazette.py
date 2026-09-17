"""OCR the Act gazette's ARRANGEMENT OF SECTIONS and answer the D2 go/no-go gate.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\ocr_gazette.py
     ... --pages=2-4      front matter pages to OCR (1-based, inclusive)
     ... --dpi=200        ~33 s/page on this CPU
     ... --json=<path>    checkpoint location (resumable; default below)
     ... --ocr-only       OCR the pages into the checkpoint and STOP: no
                          Arrangement parse, no gate, no manifest write

`--ocr-only` exists because the gate below is a FRONT-MATTER gate. Pointed at
body pages it parses statutory text as Arrangement entries and writes the
result over gazette_arrangement.json -- the verified 58-entry manifest D2's
parser is anchored on. Use it for the 27-page body pass.

DEV-ONLY. With scripts/ocrlib.py this is one of only two files that touch
pymupdf/rapidocr. Neither is importable from app.py's path at runtime and
neither belongs in requirements.txt -- the Render runtime ships the corpus
prebuilt as TXT and never re-OCRs at boot.

THE GATE
--------
D2's manifest-anchored parse rests entirely on the gazette's Arrangement of
Sections yielding a clean 1..58. Finding 1c established that this CANNOT be
checked against v1: v1's Arrangement truncates at L77 ("51.Power to acquire
land.") because the page carrying 52-58 never made it into the v1 assembly, and
the gazette's front matter has never been OCRed at all. So it gets OCRed here
and the question is answered from pixels, not from assumption.

  YES -- 1..58, no holes, no duplicates  -> D2's parser is unblocked.
  NO                                     -> fall back to MARGINAL NOTES for
     titles, stamp "title_source": "marginal_note" on every clause sourced that
     way, and report every discrepancy.

NEVER AUTHOR A TITLE. A plausible invented clause heading in front of a
generation model is precisely how a gap becomes a hallucinated provision that
passes verify_citations() mechanically.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from load import detect_duplicate_pages  # noqa: E402
from ocrlib import DEFAULT_DPI, ocr_pdf, page_lines, rows as _rows  # noqa: E402

PDF = ROOT / "data" / "raw" / "disability_act_2018_gazette_FGP.pdf"
JSON_OUT = ROOT / "data" / "processed" / "gazette_frontmatter_rapidocr.json"

ACT_CLAUSES = range(1, 59)          # the Act has 58 clauses
FRONT_MATTER = (2, 4)               # 1-based, inclusive: A97-A99

# An Arrangement entry: "12. Accessibility to roads, walk-ways and facilities."
# OCR routinely reads the separator dot as a comma and drops the trailing stop,
# so both are tolerated. The number must start the ROW -- a bare number inside a
# title ("Part 2") cannot match.
ENTRY_RE = re.compile(r"^\s*(\d{1,2})\s*[.,:]\s*(.*?)\s*$")

# Rows that are page furniture, not entries.
NOISE_RE = re.compile(
    r"^\s*(A\s*\d+|\d{4}\s*No\.?\s*\d+|PART\s*[IVX]|ARRANGEMENT\b|SCHEDULES?\b"
    r"|Section:|IN\s*QUEUES|AND\s*OTHER\s*STAFF|FOR\s*PERSONS\s*WITH"
    r"|IN\s*POLITICS"
    r"|DISCRIMINATION\s*AGAINST|Discrimination\s*against|\(PROHIBITION\)"
    r"|\(Prohibition\))", re.IGNORECASE)


def _squash(text: str) -> str:
    """Collapse whitespace. OCR's missing inter-word spaces
    ('EstablishmentofNational') are NOT repaired -- that would be authoring."""
    return re.sub(r"\s+", " ", text).strip()


def parse_arrangement(ckpt: dict, first: int, last: int) -> tuple[dict, list]:
    """Return ({clause: title}, [unparsed rows]) from the OCRed front matter."""
    entries: dict[int, str] = {}
    dupes: list[tuple[int, str, str]] = []
    suspect: list[str] = []
    rejected: list[str] = []
    last_num: int | None = None

    for page in range(first, last + 1):
        for row in _rows(page_lines(ckpt, page)):
            text = _squash(" ".join(l["text"] for l in row))
            if not text:
                continue
            if NOISE_RE.match(text):
                last_num = None          # a part heading ends any wrapped title
                continue
            m = ENTRY_RE.match(text)
            if not m:
                # A continuation of the previous entry's wrapped title
                # ("...in soliciting for alms and" / "penalty.").
                if last_num is not None and not re.match(r"^\s*\d", text):
                    entries[last_num] = _squash(entries[last_num] + " " + text)
                else:
                    rejected.append("p%d: %r" % (page, text))
                continue
            num, title = int(m.group(1)), _squash(m.group(2))
            # "26.S Service at queues." -- OCR duplicated the title's first
            # letter into the number's box. Reported, never silently patched.
            if re.match(r"^(\w)\s+\1", title, re.IGNORECASE):
                suspect.append("%d: %r (leading char doubled by OCR)"
                               % (num, title))
            if len(title) <= 2:
                suspect.append("%d: %r (title suspiciously short)" % (num, title))
            if num in entries and entries[num] != title:
                dupes.append((num, entries[num], title))
                last_num = None
                continue
            entries[num] = title
            last_num = num
    return {"entries": entries, "dupes": dupes, "suspect": suspect}, rejected


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    def opt(name, default):
        return next((a.split("=", 1)[1] for a in argv
                     if a.startswith("--%s=" % name)), default)

    dpi = int(opt("dpi", DEFAULT_DPI))
    json_out = Path(opt("json", JSON_OUT))
    first, last = FRONT_MATTER
    if "-" in str(opt("pages", "")):
        first, last = (int(x) for x in opt("pages", "").split("-", 1))

    assert PDF.exists(), "gazette not filed at %s (see data/raw/SOURCES.md)" % PDF
    print("== GAZETTE FRONT-MATTER OCR ==")
    print("  pdf   : %s" % PDF.name)
    print("  pages : %d-%d (1-based), dpi %d" % (first, last, dpi))

    ckpt = ocr_pdf(PDF, json_out, dpi=dpi, pages=range(first, last + 1))

    if "--ocr-only" in argv:
        print("\n--ocr-only: %d pages in checkpoint, gate skipped." % len(ckpt))
        return 0

    # ---- duplicate-page check ------------------------------------------
    # dedupe_pages() must NEVER run on v2. Its salvage branch
    # (src/load.py:347-363) appends unmatched lines of the DROPPED twin onto the
    # KEPT twin. On v1's genuinely duplicated scan that recovered cropped text;
    # on a clean source it is a corruption mechanism, silently interleaving
    # unrelated lines. So we DETECT and assert none, never dedupe.
    pages = [(str(p), "\n".join(l["text"] for l in page_lines(ckpt, p)))
             for p in range(first, last + 1)]
    dup = detect_duplicate_pages(pages)
    print("\n== DUPLICATE-PAGE CHECK ==")
    print("  consecutive near-duplicates: %s" % (dup or "none"))
    print("  scope: the %d front-matter pages OCRed here. The full 27-page"
          % len(pages))
    print("         check runs with D2's body OCR -- not this session.")
    assert dup == [], (
        "gazette front matter has near-duplicate pages %s. Do NOT reach for "
        "dedupe_pages(): its salvage branch corrupts a clean source." % dup)

    # ---- the gate -------------------------------------------------------
    parsed, rejected = parse_arrangement(ckpt, first, last)
    entries, dupes, suspect = (parsed["entries"], parsed["dupes"],
                               parsed["suspect"])
    found = sorted(entries)
    missing = [n for n in ACT_CLAUSES if n not in entries]
    extra = [n for n in found if n not in ACT_CLAUSES]

    print("\n== ARRANGEMENT OF SECTIONS ==")
    for n in found:
        print("  %2d. %s" % (n, entries[n]))

    print("\n== D2 GO/NO-GO GATE ==")
    print("  parsed entries    : %d" % len(entries))
    print("  expected          : 1..58")
    print("  holes             : %s" % (missing or "none"))
    print("  out of range      : %s" % (extra or "none"))
    print("  duplicate numbers : %s" % ([d[0] for d in dupes] or "none"))
    for n, a, b in dupes:
        print("      %d: %r vs %r" % (n, a, b))
    print("  titles to review  : %s" % (len(suspect) or "none"))
    for s in suspect:
        print("      %s" % s)
    if rejected:
        print("  unparsed lines    : %d (page furniture / wrapped titles)"
              % len(rejected))
        for r in rejected:
            print("      %s" % r)

    clean = not missing and not extra and not dupes
    print("\n  GATE: %s" % (
        "GO -- Arrangement yields a clean 1..58. D2's manifest-anchored parser "
        "is unblocked; titles come from the Arrangement."
        if clean else
        "NO-GO -- the Arrangement is NOT clean. D2 falls back to MARGINAL "
        "NOTES for titles, stamping \"title_source\": \"marginal_note\" per "
        "clause. Never author a title for the gap."))

    out = json_out.with_name("gazette_arrangement.json")
    # A clean manifest is never silently replaced by a dirty one. The gate is a
    # FRONT-MATTER gate; run over body pages it produces a plausible-looking but
    # wrong entry set, and the manifest is what every v2 clause title is anchored
    # to. Downgrade requires deleting the file by hand, deliberately.
    if out.exists() and not clean:
        prior = json.loads(out.read_text(encoding="utf-8"))
        if prior.get("clean"):
            raise SystemExit(
                "refusing to overwrite a CLEAN manifest (%d entries) with a "
                "dirty parse (%d entries, holes=%s). If you meant to OCR body "
                "pages, pass --ocr-only. If you really mean to re-derive the "
                "manifest, delete %s first."
                % (len(prior.get("entries", {})), len(entries), missing, out))
    out.write_text(json.dumps(
        {"source": PDF.name, "pages": [first, last], "dpi": dpi,
         "clean": clean, "entries": {str(k): v for k, v in entries.items()},
         "missing": missing, "extra": extra,
         "duplicates": [{"n": n, "a": a, "b": b} for n, a, b in dupes],
         "title_source": "arrangement" if clean else "marginal_note"},
        indent=1), encoding="utf-8")
    print("  wrote %s" % out)
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
