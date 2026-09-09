"""Load + clean legal TXT documents (stdlib + pandas only).

Load-time pipeline (raw files are NEVER overwritten):
  raw text -> split_pages -> dedupe_pages (drop near-duplicate scan pages,
      salvage unique lines) -> strip page markers -> repair_joins
      (conservative joined-word repair) -> clean_text (header/footer strip).

Numbering schemes are never conflated: use ``doc_id`` metadata downstream
(factsheet §N vs Act clause N vs Constitution §N are different things).
"""
import difflib
import re
from pathlib import Path

HEADER_FOOTER_PATTERNS = [
    r"lawnigeria\.com.*",
    r"Page \d+ of \d+",
    r"^\s*\d+\s*$",  # lone page numbers
]

# ---------------------------------------------------------------------------
# Joined-word repair
# ---------------------------------------------------------------------------
# Conservative allowlist of common English function words + domain words seen
# in the corpus. repair_joins() only ever splits a token when it segments
# FULLY into allowlist pieces -- safer to under-fix than corrupt legal terms.
# Words deliberately EXCLUDED to avoid false splits (each would corrupt a real
# word): can (cannot), out (without), get (together), ever (however),
# more (moreover), cause (because), one/every (everyone), part (apart),
# ten (often), allow (allowance), wise (otherwise), fore (before),
# other (another), able (usable/table), self (itself), trans/port (transport).
ALLOW_WORDS = frozenset(
    """
    a an the of to in on for with and or by from as is are be shall
    has have had that this these those not no any all such than who
    which what when where how he she it they his her their its him them
    may do does did done will would should must into onto within without
    after before between during against about
    act acts law laws legal aid free prohibition opportunity employment
    politics political vote service services goods facilities certificate
    temporary pension reform benefit benefits secretary executive employee
    employees president means outside territory capital abuja
    rights right human life dignity equality liberty privacy
    discrimination disability disabilities impairment mental sensory
    intellectual psychosocial person persons people child children women youth
    commission council board national federal republic nigeria public state
    states government agency agencies responsible line
    building buildings structure structures physical environment premises
    code plan plans accessibility accessible inaccessibility usable use used
    schedule first last period transitory officer charge relevant authority
    immediate notice receives redress seek sought court courts barrier
    existence event subject section sections arrangement fund funds
    establishment awareness programme programmes order purpose reasonable
    accommodation effect effective denial delay investigation enforce
    make makes made provide provides provided provision approve approves
    approval comply complying fails fail commit commits offence conviction
    liable ensure conform conforms scrutinise scrutinised bound duty power
    powers function functions manage appointment tenure cessation allowances
    member members staff general include includes including those
    equal basis access ramps lifts crossing crossings road roads sidewalk
    sidewalks pedestrian airport airports seaport seaports railway railways
    vehicle vehicles automobile communication information technology
    sign language braille interpreter interpreters special particular new
    established vest vested social economic civil cultural order justice
    fair hearing trial bail prison imprisonment term fine fines penalty
    penalties punishable guilty court day days year years month week time
    two three four five six seven eight nine hundred thousand million
    each others another same own such very too also only
    equal basis special needs needs need necessary necessarily shall will
    take takes took given give gives gave grant grants enjoy enjoys entitled
    protect protects protection promote assault harm injury property
    marry marriage family housing residence health care medical doctor
    hospital school schools university universities admission curriculum
    teacher teachers learn learning study scholarship transport travel
    road queues emergency emergencies disaster risk work job jobs employ
    employer unemployment retire retirement aged aging
    vote voter voters election elective appoint appointed
    hold holds office offices tenure serve public participate
    sign language deaf blind dumb lame cripple albino dwarf leprosy
    welfare wellbeing community communities society inclusive inclusion
    integrate integration full participate dignity respect decent
    cruel inhuman degrading torture slavery servitude forced compulsory
    privacy home correspondence honour reputation movement reside assembly
    associate thought conscience religion expression press thought opinion
    receive impart ideas assembly association belong peaceful personal
    fair trial defence counsel interpreter offence define penalty retro
    compensation unlawful arrest detention habeas corpus minor infraction
    build built erect alter demolish design construct maintain retain
    stairs stair lift ramp rails braille signage auditory visual tactile
    parking walkway driveway entrance exit door doorway corridor width
    toilet restroom seat priority customer client passenger pedestrian
    driver conductor owner operator route terminal garage motor park
    seaport harbour rail train station airport airline flight
    crew broadcast media television radio newspaper website internet
    computer software hardware device assistive aid aids appliance
    education educate educated learn teacher teach school pupil student
    curriculum syllabus braille textbook library scholarship bursary quota
    admission transcript degree diploma certificate skill
    vocation training apprentice artisan craft graduate employ unemployment
    payslip salary wage pension gratuity promotion dismiss sack retire
    health care hospital clinic doctor nurse drug medicine
    treatment therapy rehab surgery operation ward bed ambulance blood
    insurance nhis nutrition food water shelter housing estate landlord
    tenant lease mortgage homelessness relief poverty poor rich
    disaster emergency flood fire accident rescue evacuate priority queue
    first consideration risk vulnerable group social welfare palliative
    grant loan fund budget allocate allocation spend spent money
    naira kobo million billion bank account transfer deposit
    vote election ballot polling campaign party rally protest strike
    union association club society ngo civil society stakeholder consult
    data census survey count statistics research study find finding
    awareness enlightenment campaign rally seminar workshop poster jingle
    sign language interpreter dog cane wheelchair crutch prosthesis
    hearing aid glasses lens stigma discriminate bias prejudice stereotype
    exclude marginalise abandon neglect abuse exploit traffic
    beg begging alms charity pity sympathy empower support care
    maintain sustain relieve burden depend dependant guardian trustee parent
    mother father sibling spouse husband wife daughter cousin relative
    kin next of kin will inheritance inherit heir property land landed
    house shop store market farm crop animal cattle goat fowl
    trade commerce business company enterprise factory industry goods
    sell buyer seller price cost fee charge free gratis exempt waive tax
    duty tariff toll levy revenue customs excise income
    court judge justice magistrate lawyer attorney counsel solicitor
    advocate witness oath affidavit sue suit file appeal supreme
    federal high sharia customary tribunal panel commission inquiry probe
    police arrest detain cell custody bail bond surety prison custody
    sentence jail term convict acquit discharge fine penalty forfeit
    compensate damages claim petition complaint allege accuse charge count
    trial hear judgment decree order injunction writ summons serve notice
    act section subsection paragraph clause item schedule chapter
    article item line page volume copy gazette assent pass bill motion
    read commencement commence start begin end expire repeal amend alter
    review revise update print publish printer government federal
    state local area council ward constituency senate reps assembly house
    president vice governor deputy minister commissioner chairman councillor
    king emir obi obas chief traditional ruler district village town city
    lagos abuja kano ibadan benin enugu jos ilorin abuja fct rivers delta
    whereas anybody anywhere assign withhold withholds copyright island
    inland invested inaccessible anthem federation proceedings interpretation
    permanent issues issue payable unlawful june inclusiveness later
    """.split()
)

_CAMEL_BOUND = re.compile(r"(?<=[a-z])(?=[A-Z])")
_TOKEN_RE = re.compile(r"[A-Za-z]{6,}")  # short tokens are never joins
_PART_ROMAN_RE = re.compile(r"^PART([IVX]+)$")


def _segment(word: str) -> list[str] | None:
    """Segment a lowercase alpha word fully into ALLOW_WORDS; else None."""
    n = len(word)
    if word in ALLOW_WORDS:
        return [word]
    reachable = [False] * (n + 1)
    back = [-1] * (n + 1)
    reachable[0] = True
    for i in range(1, n + 1):
        for j in range(max(0, i - 20), i):  # allow-words are short
            piece = word[j:i]
            if not reachable[j]:
                continue
            if len(piece) < 2:  # no single-letter pieces: 'fundamental'
                continue  # would split fund|a|mental; 'a' handled by head rule
            if piece in ALLOW_WORDS:
                reachable[i] = True
                back[i] = j
                break
    if not reachable[n]:
        return None
    parts, i = [], n
    while i > 0:
        j = back[i]
        parts.append(word[j:i])
        i = j
    return parts[::-1]


def _restore_case(piece: str, segs: list[str]) -> str:
    """Re-join segments, preserving the piece's original capitalisation."""
    if len(segs) == 1:
        return piece  # unchanged
    if piece.isupper():
        return " ".join(s.upper() for s in segs)
    if piece[0].isupper():
        return " ".join([segs[0].capitalize()] + segs[1:])
    return " ".join(segs)


def _fix_token(match: re.Match) -> str:
    tok = match.group(0)
    if tok.lower() in ALLOW_WORDS:
        return tok
    m = _PART_ROMAN_RE.match(tok)
    if m:  # PARTVI -> PART VI (never a legal-word risk)
        return "PART " + m.group(1)

    def _try(rest: str) -> str | None:
        """Segment camel pieces; None if any piece fails (under-fix)."""
        pieces = _CAMEL_BOUND.split(rest)
        out_parts = []
        for p in pieces:
            segs = _segment(p.lower())
            if segs is None:
                return None
            out_parts.append(_restore_case(p, segs))
        return " ".join(out_parts)

    # Try the token as-is first, so words that merely START with 'A'
    # (ArrangementofSections -> Arrangement of Sections) parse correctly.
    fixed = _try(tok)
    if fixed is not None and len(fixed.split()) > 1:
        return fixed
    # Leading article "A..." (Apersonwith, Agovernment): split the "A"
    # only if the remainder segments fully on its own.
    if len(tok) > 6 and tok[0] == "A" and tok[1].islower():
        fixed = _try(tok[1:])
        if fixed is not None:
            return "A " + fixed
    return tok  # under-fix: leave the whole token untouched


def repair_joins(text: str) -> str:
    """Repair justified-text word joins (e.g. 'Apersonwith' -> 'A person with').

    Conservative: a token is only split when it segments FULLY into
    allowlist words (or the PART+roman rule fires). Misspellings
    ('Partiipation', 'EXPANARORYMEMORANDUM'), stray-letter artefacts
    ('hroads') and digit mixes ('N1,00o,000') are left alone -- never guess.
    """
    return _TOKEN_RE.sub(_fix_token, text)


# ---------------------------------------------------------------------------
# Scan-page dedupe (Act TXT has ===== PAGE N ===== markers; pages 5/6 overlap)
# ---------------------------------------------------------------------------
PAGE_MARK_RE = re.compile(r"===== PAGE (\d+) =====")


def split_pages(raw: str) -> list[tuple[str, str]]:
    """Split raw text on page markers. No markers -> [('0', raw)]."""
    marks = list(PAGE_MARK_RE.finditer(raw))
    if not marks:
        return [("0", raw)]
    pages = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(raw)
        pages.append((m.group(1), raw[m.end():end]))
    return pages


def pages_similarity(a: str, b: str) -> float:
    """difflib ratio on whitespace-normalised page bodies."""
    na = re.sub(r"\s+", " ", a).strip()
    nb = re.sub(r"\s+", " ", b).strip()
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _line_containment(a: str, b: str) -> float:
    """Max over both directions: |shared lines| / |lines of smaller page|."""
    norm = lambda t: {re.sub(r"\s+", " ", l).strip() for l in t.splitlines()}
    norm = [ln for ln in norm(a) if ln]
    sa = set(norm)
    sb = {l for l in (re.sub(r"\s+", " ", l).strip() for l in b.splitlines()) if l}
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    return inter / min(len(sa), len(sb))


def detect_duplicate_pages(
    pages: list[tuple[str, str]],
    ratio_thresh: float = 0.75,
) -> list[tuple[int, int, float, float]]:
    """Find near-duplicate CONSECUTIVE pages. Returns (i, j, ratio, containment).

    NOTE: the playbook's literal difflib threshold (>0.85) MISSES the known
    p5/6 overlap (ws-normalised ratio 0.819 -- OCR spacing noise depresses
    char-level similarity). 0.75 still has a wide margin here: the next most
    similar consecutive pair scores 0.084. Line-containment is reported as
    corroborating evidence (p5/6: 0.44 vs <0.30 everywhere else).
    """
    dups = []
    for i in range(len(pages) - 1):
        r = pages_similarity(pages[i][1], pages[i + 1][1])
        c = _line_containment(pages[i][1], pages[i + 1][1])
        if r > ratio_thresh:
            dups.append((i, i + 1, r, c))
    return dups


def _repair_edit_count(body: str) -> int:
    """How many tokens repair_joins() changes -- fewer edits = cleaner copy."""
    count = 0

    def _count(m: re.Match) -> str:
        nonlocal count
        fixed = _fix_token(m)
        if fixed != m.group(0):
            count += 1
        return fixed

    _TOKEN_RE.sub(_count, body)
    return count


def dedupe_pages(
    pages: list[tuple[str, str]],
    ratio_thresh: float = 0.75,
    salvage_thresh: float = 0.6,
) -> tuple[list[tuple[str, str]], list[dict], dict[str, str]]:
    """Drop near-duplicate scan pages, keep the cleaner copy.

    Cleaner copy = fewer repair_joins edits (tie-break: longer body).
    Lines from the dropped page with max difflib similarity < salvage_thresh
    against every kept line are appended (preserves unique fragments, e.g.
    clause-7 subsections cropped differently across the two scans).
    Returns (kept_pages, dropped_info, sidecar page->char-offset placeholder).
    Offsets are finalised by build_clean_text(); sidecar maps kept page num
    to its offset there (dropped pages map to the kept twin's offset).
    """
    drop_idx: dict[int, int] = {}  # dropped index -> kept index
    for i, j, r, c in detect_duplicate_pages(pages, ratio_thresh):
        if i in drop_idx or j in drop_idx:
            continue  # already handled (chains shouldn't happen; be safe)
        ei, ej = _repair_edit_count(pages[i][1]), _repair_edit_count(pages[j][1])
        # Fewer edits wins; tie-break: longer normalised body.
        if (ei, -len(re.sub(r"\s+", "", pages[i][1]))) <= (
            ej,
            -len(re.sub(r"\s+", "", pages[j][1])),
        ):
            keep, drop = i, j
        else:
            keep, drop = j, i
        drop_idx[drop] = keep

    kept: list[tuple[str, str]] = []
    dropped_info: list[dict] = []
    twin_of: dict[str, str] = {}
    for idx, (num, body) in enumerate(pages):
        if idx in drop_idx:
            keep = drop_idx[idx]
            knum = pages[keep][0]
            twin_of[num] = knum
            # Salvage genuinely unique lines from the dropped page.
            kept_lines = [l for l in pages[keep][1].splitlines()]
            salvaged = []
            for line in body.splitlines():
                s = line.strip()
                if not s:
                    continue
                best = max(
                    (
                        difflib.SequenceMatcher(None, s, k.strip()).ratio()
                        for k in kept_lines
                        if k.strip()
                    ),
                    default=0.0,
                )
                if best < salvage_thresh:
                    salvaged.append(line)
            dropped_info.append(
                {
                    "dropped_page": num,
                    "kept_page": knum,
                    "salvaged_lines": len(salvaged),
                    "salvaged": salvaged,
                }
            )
            continue
        kept.append((num, body))
    # Append salvaged lines to their kept twin.
    salv_by_page: dict[str, list[str]] = {}
    for d in dropped_info:
        salv_by_page.setdefault(d["kept_page"], []).extend(d["salvaged"])
    final_kept = []
    for num, body in kept:
        if num in salv_by_page and salv_by_page[num]:
            body = body + "\n" + "\n".join(salv_by_page[num])
        final_kept.append((num, body))
    # Sidecar offsets need the joined text; computed by build_clean_text().
    return final_kept, dropped_info, twin_of


def strip_page_markers(raw: str) -> str:
    """Remove ===== PAGE N ===== markers (provenance lives in sidecar map)."""
    return PAGE_MARK_RE.sub("\n", raw)


def build_clean_text(
    raw: str, *, repair: bool = True, dedupe: bool = True
) -> tuple[str, dict[str, int], list[dict]]:
    """Full load-time pipeline. Returns (clean_text, sidecar, dropped_info).

    sidecar: {page_num: char offset in clean_text} (dropped pages point at
    their kept twin's offset). Files without markers get {'0': 0}.
    """
    pages = split_pages(raw)
    twin_of: dict[str, str] = {}
    dropped_info: list[dict] = []
    if dedupe and len(pages) > 1:
        pages, dropped_info, twin_of = dedupe_pages(pages)
    chunks: list[str] = []
    sidecar: dict[str, int] = {}
    offset = 0
    for num, body in pages:
        if repair:
            body = repair_joins(body)
        chunks.append(body)
        sidecar[num] = offset
        offset += len(body)
    for dropped, kept in twin_of.items():
        sidecar[dropped] = sidecar[kept]
    return "".join(chunks), sidecar, dropped_info


CLAUSE_RE = re.compile(r"(?<!\d)(\d{1,2})(?!\d)\s*[\.\)]")


def clause_coverage(text: str, lo: int = 1, hi: int = 58) -> set[int]:
    """Clause numbers present (arrangement-of-sections TOC + body markers).

    Tolerant pattern: matches 'N.'/'N)' anywhere (TOC lists sections
    mid-line, e.g. '18.Inclusiveness ofeducation.19.Subsidised...').
    Used as a REGRESSION check: cleanup must not lose clause numbers.
    Act-only -- do not apply to Constitution/factsheet numbering.
    """
    return {int(m.group(1)) for m in CLAUSE_RE.finditer(text) if lo <= int(m.group(1)) <= hi}


def clean_text(text: str, *, repair: bool = False) -> str:
    """Strip page artefacts, normalize whitespace, keep section markers."""
    if repair:
        text = repair_joins(text)
    for pat in HEADER_FOOTER_PATTERNS:
        text = re.sub(pat, "", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_txt(path: str | Path, *, repair: bool = True, dedupe: bool = True) -> str:
    """Load a TXT through the full load-time pipeline (raw file untouched).

    Returns clean chunkable text. For the (text, sidecar, dropped_info)
    triple, use build_clean_text() directly.
    """
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    text, _, _ = build_clean_text(raw, repair=repair, dedupe=dedupe)
    return clean_text(text)


def save_processed(text: str, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
