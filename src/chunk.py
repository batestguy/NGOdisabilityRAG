"""Chunking: recursive-char baseline + section-aware variant (no deps)."""
import re


def recursive_split(text: str, size: int = 500, overlap: int = 50) -> list[str]:
    """Greedy splitter: paragraphs -> sentences -> hard cut. Char-based."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 2 <= size:
            cur = (cur + "\n\n" + p).strip()
        else:
            if cur:
                chunks.append(cur)
            while len(p) > size:  # hard-cut oversized paragraph
                chunks.append(p[:size])
                p = p[size - overlap:]
            cur = p
    if cur:
        chunks.append(cur)
    return chunks


SECTION_RE = re.compile(r"(Section \d+.*)", re.IGNORECASE)


def section_aware_split(text: str, size: int = 800) -> list[str]:
    """Split on 'Section N' headings first, then fall back to recursive."""
    parts = SECTION_RE.split(text)
    # re-join heading with its body; keep any preamble before the 1st heading
    # (dropping parts[0] would silently lose leading text)
    units = []
    if parts[0].strip():
        units.append(parts[0].strip())
    for i in range(1, len(parts), 2):
        units.append((parts[i] + "\n" + parts[i + 1]).strip() if i + 1 < len(parts) else parts[i])
    if not units:
        return recursive_split(text, size=size)
    chunks = []
    for u in units:
        chunks.extend(recursive_split(u, size=size) if len(u) > size else [u])
    return chunks


CHAPTER_RE = re.compile(r"(?im)^\s*Chapter\s+([IVX]+)\s*$")
# Body sections look like "33. (1) ..." or "47. There shall ..."; the lookahead
# keeps the match to genuine headings (paren subsection or capitalised start).
CONST_SEC_RE = re.compile(r"(?m)^\s*(\d{1,3})\.\s*(?=\(|[A-Z0-9\"'])")

# Priority Constitution sections: directive principles (14, 17) + Chapter IV
# fundamental rights (33-46). These must each survive as their own chunk(s)
# and are NEVER merged with neighbouring sections.
PRIORITY_SECTIONS = frozenset({14, 17} | set(range(33, 47)))


def _chapter_title(block: str, limit: int = 80) -> str:
    """First non-empty line of a chapter block (e.g. 'Fundamental Rights')."""
    for line in block.splitlines():
        if line.strip():
            return line.strip()[:limit]
    return ""


def constitution_aware_split(
    text: str,
    size: int = 800,
    priority_sections: frozenset = PRIORITY_SECTIONS,
) -> list[str]:
    """Split Constitution text on CHAPTER then Section N headings.

    Each chunk is prepended with ``"Constitution, {heading}: "`` where heading
    is the chapter (plus title) and, for single-section chunks, the section
    number (``§N``) or section range (``§§a-b``) for merged chunks. Small
    non-priority units are greedily merged up to ``size`` chars (prefix
    included); priority sections (14, 17, 33-46) are NEVER merged -- each
    becomes its own chunk (sub-split with the same §N prefix if oversized).
    Text before the first chapter heading is kept under a 'Preamble' heading.
    """
    ms = list(CHAPTER_RE.finditer(text))
    if not ms:
        return recursive_split(text, size=size)

    chapters: list[tuple[str, str]] = []  # (heading, block)
    if ms[0].start() > 0:
        pre = text[: ms[0].start()].strip()
        if pre:
            chapters.append(("Preamble", pre))
    for k, m in enumerate(ms):
        end = ms[k + 1].start() if k + 1 < len(ms) else len(text)
        block = text[m.end() : end].strip()
        if not block:
            continue
        title = _chapter_title(block)
        label = "Chapter %s" % m.group(1)
        chapters.append((label if not title else "%s - %s" % (label, title), block))

    chunks: list[str] = []
    for heading, block in chapters:
        # Split block into (section_num|None, unit_text) units.
        parts = CONST_SEC_RE.split(block)
        units: list[tuple[int | None, str]] = []
        if parts[0].strip():
            units.append((None, parts[0].strip()))
        for i in range(1, len(parts), 2):
            num = int(parts[i])
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            units.append((num, ("%d. %s" % (num, body)).strip()))

        # Flush helper: emit accumulated non-priority units as merged chunks.
        pending: list[tuple[int | None, str]] = []

        def _prefix(sec_nums: list[int]) -> str:
            # Member list (never a span): a merged "§§13,16" chunk contains
            # exactly §§13 and 16, so the label can never imply a priority
            # section it does not contain.
            if not sec_nums:
                return "Constitution, %s: " % heading
            if len(sec_nums) == 1:
                return "Constitution, %s \u00a7%d: " % (heading, sec_nums[0])
            return "Constitution, %s \u00a7\u00a7%s: " % (
                heading,
                ",".join(str(s) for s in sec_nums),
            )

        def _emit(text_body: str, sec_nums: list[int]) -> None:
            prefix = _prefix(sec_nums)
            budget = size - len(prefix)
            if len(prefix) + len(text_body) <= size:
                chunks.append(prefix + text_body)
            else:
                for piece in recursive_split(text_body, size=max(budget, 100)):
                    chunks.append(prefix + piece)

        def _flush() -> None:
            if not pending:
                return
            # Greedily pack pending units; never break a unit across chunks
            # unless the single unit itself exceeds the budget.
            cur: list[tuple[int | None, str]] = []
            cur_len = 0
            for sec, unit in pending:
                prefix = _prefix(
                    [s for s, _ in cur if s is not None]
                    + ([sec] if sec is not None else [])
                )
                need = len(unit) + (2 if cur else 0)
                if cur and len(prefix) + cur_len + need > size:
                    _emit(
                        "\n".join(u for _, u in cur),
                        [s for s, _ in cur if s is not None],
                    )
                    cur, cur_len = [], 0
                if not cur:
                    if len(_prefix([sec] if sec is not None else [])) + len(unit) > size:
                        _emit(unit, [sec] if sec is not None else [])
                        continue
                    cur, cur_len = [(sec, unit)], len(unit)
                else:
                    cur.append((sec, unit))
                    cur_len += need
            if cur:
                _emit("\n".join(u for _, u in cur), [s for s, _ in cur if s is not None])
            pending.clear()

        for sec, unit in units:
            if sec is not None and sec in priority_sections:
                _flush()
                _emit(unit, [sec])  # own chunk(s), never merged
            else:
                pending.append((sec, unit))
        _flush()
    return chunks
