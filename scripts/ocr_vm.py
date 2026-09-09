"""Run on a Colab VM via `colab exec -s <session> -f ocr_vm.py`.

Reads the Gemini API key from /content/.gkey (uploaded separately via
`colab upload`), downloads the scanned Disability Act PDF, OCRs all pages
with gemini-2.5-flash, checkpointing each page to /content so reruns resume.
Outputs: /content/ocr_checkpoint.json + /content/disability_act_2018_full.txt
"""
import json
import os
import re
import time
import urllib.request

CKPT = "/content/ocr_checkpoint.json"
FAILED = "/content/ocr_failed.json"
PROGRESS = "/content/PROGRESS.md"
OUT = "/content/disability_act_2018_full.txt"
PDF = "/content/disability_act_2018_full.pdf"
PDF_URL = (
    "https://qualitativemagazine.com/wp-content/uploads/2022/10/"
    "1244-Discrimination-Against-Persons-with-Disabilities-Prohibition-ACT-2018.pdf"
)
PROMPT = (
    "Transcribe this scanned legal document page exactly, preserving section numbers, "
    "headings, and paragraph structure. Return only the transcribed text, no commentary. "
    "If a region is illegible, write [illegible]."
)


def save_progress(ckpt, failed, total):
    json.dump(ckpt, open(CKPT, "w", encoding="utf-8"))
    json.dump(sorted(failed), open(FAILED, "w", encoding="utf-8"))
    done = sorted(int(k) for k in ckpt)
    lines = [
        "# DRLCA OCR progress",
        f"Updated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"Pages done: {len(ckpt)} / {total} ({', '.join(map(str, done)) or 'none'})",
        f"Pages failed (will retry): {sorted(failed) or 'none'}",
        f"Chars so far: {sum(len(v) for v in ckpt.values())}",
    ]
    open(PROGRESS, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    push_to_github()


def push_to_github():
    """Push checkpoint + progress to the colab-progress branch. Skips silently
    unless /content/.gh (PAT) and /content/.ghrepo (user/repo) were uploaded."""
    if not (os.path.exists("/content/.gh") and os.path.exists("/content/.ghrepo")):
        return
    import subprocess

    tok = open("/content/.gh", encoding="utf-8").read().strip()
    slug = open("/content/.ghrepo", encoding="utf-8").read().strip()
    work = "/content/gh_push"
    os.makedirs(work, exist_ok=True)
    for f in (CKPT, FAILED, PROGRESS):
        if os.path.exists(f):
            open(os.path.join(work, os.path.basename(f)), "w", encoding="utf-8").write(
                open(f, encoding="utf-8").read()
            )
    url = f"https://{tok}@github.com/{slug}.git"
    cmds = [
        "git init -q 2>/dev/null; git checkout -q -B colab-progress",
        f"git remote remove origin 2>/dev/null; git remote add origin {url}",
        "git add ocr_checkpoint.json ocr_failed.json PROGRESS.md",
        "git -c user.email=colab@drlca -c user.name=drlca-colab commit -qm progress || true",
        "git push -q -u origin colab-progress",
    ]
    subprocess.run("cd /content/gh_push && " + " && ".join(cmds), shell=True, timeout=120)
    print("pushed checkpoint to GitHub colab-progress", flush=True)


def main():
    with open("/content/.gkey", encoding="utf-8") as f:
        api_key = f.read().strip()
    from google import genai

    client = genai.Client(api_key=api_key)

    if not os.path.exists(PDF):
        req = urllib.request.Request(PDF_URL, headers={"User-Agent": "Mozilla/5.0 DRLCA-Colab"})
        with urllib.request.urlopen(req, timeout=180) as r, open(PDF, "wb") as f:
            f.write(r.read())
        print(f"downloaded {os.path.getsize(PDF)} bytes", flush=True)

    import pymupdf  # noqa: E402

    doc = pymupdf.open(PDF)
    ckpt = json.load(open(CKPT, encoding="utf-8")) if os.path.exists(CKPT) else {}
    failed = set(json.load(open(FAILED, encoding="utf-8"))) if os.path.exists(FAILED) else set()
    print(f"pages: {len(doc)}, cached: {len(ckpt)}, failed-to-retry: {sorted(failed)}", flush=True)
    for i in range(1, len(doc) + 1):
        if str(i) in ckpt:
            continue
        img = doc.load_page(i - 1).get_pixmap(dpi=200).tobytes("png")
        ok = False
        for attempt in range(5):
            try:
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[PROMPT, {"inline_data": {"mime_type": "image/png", "data": img}}],
                )
                text = resp.text.strip()
                if len(text) < 50:  # empty/garbage response counts as failure
                    raise ValueError(f"suspiciously short transcription ({len(text)} chars)")
                ckpt[str(i)] = text
                failed.discard(i)
                print(f"page {i}/{len(doc)}: {len(text)} chars", flush=True)
                ok = True
                break
            except Exception as e:  # noqa: BLE001 - transient quota errors, retry
                print(f"page {i} retry {attempt}: {repr(e)[:130]}", flush=True)
                time.sleep(30)
        if not ok:
            failed.add(i)
            print(f"page {i}: MARKED FAILED, will retry on next run", flush=True)
        save_progress(ckpt, failed, len(doc))
        time.sleep(5)

    missing = [i for i in range(1, len(doc) + 1) if str(i) not in ckpt]
    if missing:
        raise SystemExit(f"INCOMPLETE, missing pages: {missing} — rerun to resume")
    full = "\n".join(f"===== PAGE {i} =====\n{ckpt[str(i)]}" for i in range(1, len(doc) + 1))
    full = re.sub(r"[^\S\n]+", " ", full).strip()
    open(OUT, "w", encoding="utf-8").write(full)
    print(f"DONE: {len(full)} chars -> {OUT}", flush=True)
    print("Sections found:", len(re.findall(r"Section \d+", full, re.I)), flush=True)


main()
