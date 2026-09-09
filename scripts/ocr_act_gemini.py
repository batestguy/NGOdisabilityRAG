"""OCR the scanned Act PDF via Gemini free tier, with per-page checkpointing.

Usage: python scripts/ocr_act_gemini.py [start_page] [end_page]  (1-based, inclusive)
Resumes: pages already in data/processed/ocr_checkpoint.json are skipped.
Finalize: python scripts/ocr_act_gemini.py --finalize
"""
import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

import pymupdf
import google.generativeai as genai

SRC = "D:/NGORAG/data/raw/disability_act_2018_full.pdf"
CKPT = "D:/NGORAG/data/processed/ocr_checkpoint.json"
OUT = "D:/NGORAG/data/processed/disability_act_2018_full.txt"

PROMPT = (
    "Transcribe this scanned legal document page exactly, preserving "
    "section numbers, headings, and paragraph structure. Return only the "
    "transcribed text, no commentary. If a region is illegible, write [illegible]."
)


def load_ckpt():
    if os.path.exists(CKPT):
        return json.load(open(CKPT, encoding="utf-8"))
    return {}


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--finalize":
        ckpt = load_ckpt()
        doc_pages = pymupdf.open(SRC).page_count
        missing = [i for i in range(1, doc_pages + 1) if str(i) not in ckpt]
        assert not missing, f"missing pages: {missing}"
        sys.path.insert(0, "D:/NGORAG/src")
        from load import clean_text, save_processed

        full = clean_text(
            "\n".join(f"===== PAGE {i} =====\n{ckpt[str(i)]}" for i in range(1, doc_pages + 1))
        )
        save_processed(full, OUT)
        print(f"finalized {doc_pages} pages, {len(full)} chars -> {OUT}")
        return

    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else pymupdf.open(SRC).page_count

    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    model = genai.GenerativeModel("models/gemini-2.5-flash")
    doc = pymupdf.open(SRC)
    ckpt = load_ckpt()
    for i in range(lo, hi + 1):
        if str(i) in ckpt:
            print(f"page {i}: cached, skip", flush=True)
            continue
        pix = doc.load_page(i - 1).get_pixmap(dpi=200)
        img = pix.tobytes("png")
        for attempt in range(4):
            try:
                resp = model.generate_content([PROMPT, {"mime_type": "image/png", "data": img}])
                ckpt[str(i)] = resp.text.strip()
                json.dump(ckpt, open(CKPT, "w", encoding="utf-8"))
                print(f"page {i}: {len(resp.text)} chars (saved)", flush=True)
                break
            except Exception as e:  # noqa: BLE001
                msg = repr(e)
                print(f"page {i} attempt {attempt}: {msg[:130]}", flush=True)
                if "NotFound" in msg or "PermissionDenied" in msg:
                    raise
                time.sleep(20)
        else:
            print(f"page {i}: GIVING UP, continue to next", flush=True)
        time.sleep(5)


main()
