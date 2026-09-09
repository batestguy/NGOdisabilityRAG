# Archive — dead ends kept for reference, NOT for execution

- `ocr_vm.py` — Colab-VM Gemini OCR. Abandoned: ~2 pages/hour vs 27 pages/11 min local.
  Lessons kept as traps in `docs/phases/` and `HANDOFF.md` (quota-bound waits, checkpointing).
- `ocr_act_gemini.py` — earlier local Gemini OCR attempt. Same reason.
- `find_act_download.py` — one-off scraper that found the free Act PDF. Job done, URL now in `data/raw/SOURCES.md`.
- `02_ocr_act_colab.ipynb` — Colab OCR notebook. Superseded by `scripts/ocr_local.py` + `drlca-rag` env.
- `requirements-legacy.txt` — pre-env generic requirements. Superseded by `requirements-rag.txt`.

Live OCR path: `scripts/ocr_local.py` (RapidOCR, resumable via `data/processed/disability_act_2018_rapidocr.json`).
