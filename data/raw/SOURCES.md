# Legal sources — download instructions (free, public sources per spec)

## Required documents
| # | Document | Source | URL / access |
|---|----------|--------|--------------|
| 1 | Discrimination Against Persons with Disabilities (Prohibition) Act, 2018 (full text, FREE) | JONAPWD | https://jonapwdng.org/discrimination-against-persons-with-disabilities-prohibition-act-2018/ — full provisions, free |
| 1 alt | Same Act, downloadable copy (FREE) | Qualitative Magazine | https://qualitativemagazine.com/a-copy-of-discrimination-against-persons-with-disabilities-prohibition-act-2018/ — free download link at bottom of article |
| 1 summary | Same Act, factsheet/summary (FREE PDF) | PLAC | https://placng.org/i/wp-content/uploads/2020/07/The-Discrimination-Against-Persons-with-Disabilities-Prohibition-Act.pdf |
| 2 | Constitution of the FRN 1999 incl. 1st–5th Alterations (FREE PDF) | PLAC | https://placng.org/i/wp-content/uploads/2023/05/Constitution-of-the-Federal-Republic-of-Nigeria-2023.pdf — most up-to-date single copy |
| 2 alt | Constitution 1999 Cap. C23 (FREE PDF) | NHRC | https://nigeriarights.gov.ng/files/publications/1999%20CONSTITUTION%20OF%20THE%20FRN.pdf |
| 3 | Disability Act Easy-to-Read Version | JONAPWD | https://jonapwdng.org/easy-to-read-version-of-the-disability-act-2018/ (also announced on JONAPWD LinkedIn, Apr 2023) |
| 1 **authoritative** | Same Act as published — **Official Gazette No. 10, Vol. 106, Lagos, 21 January 2019, Act No. 2, pages A97–A122** | Federal Government Printer, Lagos (FGP 007/12019/700) | `data/raw/disability_act_2018_gazette_FGP.pdf` — 27 scanned pages, **no text layer**, filed Phase 10 D0 (2026-09-17) |

> **The gazette copy is the authoritative source for corpus v2** (Phase D). Rows 1 / 1 alt
> above are the free web transcriptions v1 was built from; where they and the gazette
> disagree, the gazette wins. It is a scan, so it must be OCRed — see
> `docs/phases/12_corpus_v2.md`. Nothing in `data/raw/` is read at boot; the corpus ships
> prebuilt as TXT.

> NOTE: lawnigeria.com sells its PDF copy for ₦2,000 — do NOT pay; the JONAPWD / Qualitative Magazine / PLAC copies above are free and sufficient for this project.

## How to add them here
1. Save each as PDF into `data/raw/`.
2. Extract to TXT (Colab: `%pip install -q pypdf`, then `python scripts/extract_pdf.py data/raw/<file>.pdf > data/processed/<name>.txt`).
3. Run `src/load.py:load_txt` to clean headers/footers.
4. Record source URL + access date in `LEARNING_JOURNAL.md`.

## Status
- [ ] Doc 1 downloaded + cleaned
- [ ] Doc 2 downloaded + cleaned
- [ ] Doc 3 downloaded + cleaned

Until then, `notebooks/01_foundation.ipynb` runs on a clearly-labelled
SAMPLE excerpt (`data/processed/_SAMPLE_DO_NOT_CITE.txt`) so the pipeline
is testable without fabricating citable law text.
