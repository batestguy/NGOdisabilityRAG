"""Local OCR of the scanned Disability Act with RapidOCR (ONNX, CPU).

Run with the isolated env:  C:\\conda-envs\\drlca-rag\\python.exe scripts/ocr_local.py
Resumable: pages already in the JSON checkpoint are skipped.
Outputs:
  data/processed/disability_act_2018_rapidocr.json  (per-line text + confidence)
  data/processed/disability_act_2018_full.txt       (assembled, cleaned)
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

PDF = ROOT / "data" / "raw" / "disability_act_2018_full.pdf"
JSON_OUT = ROOT / "data" / "processed" / "disability_act_2018_rapidocr.json"
TXT_OUT = ROOT / "data" / "processed" / "disability_act_2018_full.txt"

CONF_THRESHOLD = 0.6  # lines below this are candidates for Gemini spot-correction


def main():
    import numpy as np
    import pymupdf
    from rapidocr_onnxruntime import RapidOCR

    from load import clean_text

    engine = RapidOCR()
    doc = pymupdf.open(PDF)
    ckpt = json.loads(JSON_OUT.read_text(encoding="utf-8")) if JSON_OUT.exists() else {}
    print(f"pages: {len(doc)}, cached: {len(ckpt)}", flush=True)
    t0 = time.time()
    for i in range(1, len(doc) + 1):
        if str(i) in ckpt:
            continue
        pix = doc.load_page(i - 1).get_pixmap(dpi=200)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        img = img[:, :, :3]  # drop alpha
        result, _ = engine(img)
        lines = [
            {"text": txt, "conf": float(conf), "box": [list(map(float, p)) for p in box]}
            for box, txt, conf in (result or [])
        ]
        lines.sort(key=lambda l: (l["box"][0][1] + l["box"][2][1]) / 2)  # top-to-bottom
        ckpt[str(i)] = lines
        JSON_OUT.write_text(json.dumps(ckpt), encoding="utf-8")
        avg = sum(l["conf"] for l in lines) / len(lines) if lines else 0.0
        low = sum(1 for l in lines if l["conf"] < CONF_THRESHOLD)
        print(f"page {i}/{len(doc)}: {len(lines)} lines, avg_conf={avg:.3f}, low_conf={low}", flush=True)
    print(f"OCR time: {time.time() - t0:.0f}s", flush=True)

    parts = []
    for i in range(1, len(doc) + 1):
        body = "\n".join(l["text"] for l in ckpt[str(i)])
        parts.append(f"===== PAGE {i} =====\n{body}")
    TXT_OUT.write_text(clean_text("\n".join(parts)), encoding="utf-8")
    print(f"saved {TXT_OUT} ({TXT_OUT.stat().st_size} bytes)", flush=True)


main()
