"""Reusable RapidOCR helpers, extracted from scripts/ocr_local.py at Phase 10 D2.

DEV-ONLY. This module (and its callers) are the only places pymupdf/rapidocr are
imported. They are in requirements-rag.txt, never in requirements.txt -- the
Render runtime ships the corpus prebuilt as TXT and must never re-OCR at boot.
Imports are therefore function-local, so this module can be imported and its
pure helpers used without dragging ONNX in.

WHY THIS EXISTS -- READ BEFORE REACHING FOR ocr_local
-----------------------------------------------------
`scripts/ocr_local.py` cannot be imported. It has a bare `main()` at module
scope with no `__main__` guard, and `main()` unconditionally writes
`data/processed/disability_act_2018_full.txt` -- the v1 corpus every published
baseline in this repo is measured against. `import ocr_local` destroys it,
silently. That hazard is fixed in place at D2 (guard + --force), but the durable
answer is that shared OCR code lives HERE and ocr_local imports it, not the
reverse.

GEOMETRY IS KEPT ON PURPOSE
---------------------------
v1's assembler joined `l["text"]` and threw the boxes away (ocr_local.py:57).
The boxes are exactly what the marginal-note problem needs: the gazette prints
clause titles in a narrow left-hand column that OCR splices into the body, which
is why 25/62 v1 Act chunks ended up uncitable. `page_lines()` returns the box
with every line, and `column_split()` uses it. Nothing here discards geometry.
"""

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_DPI = 200          # ~33 s/page on this CPU
CONF_THRESHOLD = 0.6       # lines below this are low-confidence candidates


def ocr_pdf(
    pdf: Path,
    json_out: Path | None = None,
    *,
    dpi: int = DEFAULT_DPI,
    pages: range | list[int] | None = None,
    verbose: bool = True,
) -> dict[str, list[dict]]:
    """OCR `pages` of `pdf` (1-based). Resumable via the json_out checkpoint.

    Returns {page_number_str: [{"text", "conf", "box"}, ...]}, each page's lines
    sorted top-to-bottom by box centre. Identical per-line shape to v1's
    checkpoint, so v1 JSON files remain readable by this code.
    """
    import numpy as np
    import pymupdf
    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()
    doc = pymupdf.open(pdf)
    ckpt: dict[str, list[dict]] = {}
    if json_out is not None and json_out.exists():
        ckpt = json.loads(json_out.read_text(encoding="utf-8"))
    todo = list(pages) if pages is not None else list(range(1, len(doc) + 1))
    if verbose:
        print("pages: %d, requested: %d, cached: %d"
              % (len(doc), len(todo), len(ckpt)), flush=True)

    t0 = time.time()
    for i in todo:
        if str(i) in ckpt:
            continue
        pix = doc.load_page(i - 1).get_pixmap(dpi=dpi)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n)
        img = img[:, :, :3]  # drop alpha
        result, _ = engine(img)
        lines = [
            {"text": txt, "conf": float(conf),
             "box": [list(map(float, p)) for p in box]}
            for box, txt, conf in (result or [])
        ]
        lines.sort(key=lambda l: (l["box"][0][1] + l["box"][2][1]) / 2)
        ckpt[str(i)] = lines
        if json_out is not None:
            json_out.write_text(json.dumps(ckpt), encoding="utf-8")
        if verbose:
            avg = sum(l["conf"] for l in lines) / len(lines) if lines else 0.0
            low = sum(1 for l in lines if l["conf"] < CONF_THRESHOLD)
            print("page %d: %d lines, avg_conf=%.3f, low_conf=%d"
                  % (i, len(lines), avg, low), flush=True)
    if verbose:
        print("OCR time: %.0fs" % (time.time() - t0), flush=True)
    return ckpt


def page_lines(ckpt: dict[str, list[dict]], page: int) -> list[dict]:
    """Lines of one page, geometry intact. Empty list if not OCRed."""
    return ckpt.get(str(page), [])


def x_left(line: dict) -> float:
    """Left edge of a line's box. The marginal-note column is identified by
    this, not by text content."""
    return min(p[0] for p in line["box"])


def x_right(line: dict) -> float:
    return max(p[0] for p in line["box"])


def column_split(lines: list[dict], boundary: float) -> tuple[list[dict], list[dict]]:
    """Split one page's lines into (left_of_boundary, right_of_boundary).

    On the gazette, the left column is the marginal notes (clause titles) and
    the right is the operative body. `boundary` is a page-x coordinate; callers
    derive it from the observed distribution rather than hardcoding, because dpi
    scales every coordinate linearly.
    """
    left = [l for l in lines if x_right(l) <= boundary]
    right = [l for l in lines if x_right(l) > boundary]
    return left, right


def assemble_v1(ckpt: dict[str, list[dict]], n_pages: int) -> str:
    """v1's assembler, byte-for-byte: page markers, text only, geometry dropped.

    Preserved verbatim so scripts/ocr_local.py keeps producing the exact file
    every published baseline was measured on. New work should NOT use this --
    it is the lossy path this module exists to move past.
    """
    from load import clean_text

    parts = []
    for i in range(1, n_pages + 1):
        body = "\n".join(l["text"] for l in ckpt[str(i)])
        parts.append("===== PAGE %d =====\n%s" % (i, body))
    return clean_text("\n".join(parts))
