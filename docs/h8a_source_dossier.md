# H8a.0 — source dossier (2026-10-22)

Step H8a.0 of `docs/phases/17_h8_corpus_expansion.md`. **Docs only: nothing is parsed, indexed or committed to
`data/raw/` until the owner signs one candidate below.** One document per round.

## Recommendation

**Candidate A, the Persons with Disabilities (Accessibility) Regulations, 2023.** It is the only candidate with an
official full text that is freely available. It is federal, it is made under the Act already in the corpus, and its text
layer is born-digital (no OCR). It also answers questions users actually ask: ramps, parking, toilets, buses, and an
administrative penalty for non-compliance. The CRPD (B) has a real licence question. No official text of the Lagos law
(C) was found.

---

## A. Persons with Disabilities (Accessibility) Regulations, 2023 — RECOMMENDED

| Field | Finding (verified 2026-10-22 unless marked) |
|---|---|
| Instrument | **S.I. No. 51 of 2023.** Federal Republic of Nigeria Official Gazette **No. 122, Vol. 110, Lagos, 7 July 2023**, Government Notice No. 95, pages **B1343–1513**. Printed by the Federal Government Printer (FGP 110/52023/150). |
| Made by | Governing Council of the National Commission for Persons with Disabilities. "DONE at Abuja this 22nd day of May, 2023", signed by Amina Rahma Audu, Acting Chairman, Governing Council. |
| Legal basis | "In exercise of the powers conferred on it by **section 56** of the Discrimination Against Persons with Disabilities (Prohibition) Act, 2018". Cross-checked: the corpus's `act2018_v2_clauses.json` has clause 56, "Regulations. The Council may make regulations for the purpose of carrying out or giving full effect to the provisions of this Act." So `[Act cl. 56]` is the in-corpus evidence for the Regulations' authority. |
| Source URL | https://ncpwd.gov.ng/pdfs/44document.pdf (the NCPWD's own site). This is the same site and folder that supplied the Act gazette already in the corpus (`6document.pdf`, Phase D). |
| File | 10,561,889 bytes, PDF 1.7, 173 pages, sha256 `04bb8bec217b6ca01fa3ac3e5b5893ed619b2970ea7cb4b81f4ba2c047f28b05`. Downloaded 2026-10-22 to `D:\NGORAG\runs\h8a0\dl_regs\regs2023.pdf` (gitignored; not yet in `data/raw/`). PDF metadata: created 2024-11-21 in Microsoft Word, so this is a re-typeset copy of the gazette, not a scan of it. |
| Text layer | **Born-digital.** About 162K characters in total. The Arrangement (pp. 3–8) and **the operative regulations 1–172 with their interpretation (pp. 9–68) are text.** The First Schedule ("Figures, symbols and tables", pp. 69–172) is mostly images, and the Second Schedule (symbols and abbreviations) is on p. 173. The figures are not citable text and would be excluded, like the Constitution's Arrangement in D4. |
| Citation unit | **Regulation N** (sub-regulations `(1)`), grouped into Chapters and Parts; **172 regulations** (Arrangement count = max number = 172). Marginal notes sit beside the text (e.g. "Administrative penalty."), as in the Act. The parser can reuse the Phase D manifest-anchored approach, with the Arrangement as the manifest. Proposed tag: `[Regs reg. N]`, `doc_id` `accessregs2023`. This must be checked against `CITE_TAG_RE`/`verify_citations` so it cannot collide with `[Act cl. N]` (F3, F5). |
| Content sample | Reg. 168: "Notwithstanding the penalties provided under the Act or any other law, any person who contravenes the provisions of these Regulations is liable to an administrative penalty of not less than N 500,000." Other parts cover exterior routes, ramps, kerbs, crossings, transport infrastructure, parking, entertainment and recreation, buildings, signage, and the National Disability Compliance Certificate (reg. 165 ff.). |
| Status | A federal subsidiary instrument (S.I.), made 22 May 2023 and gazetted 7 July 2023. **Not verified:** the commencement date (no commencement regulation was located in this pass) and any later amendment. Search found none. Ask the reviewer (H6) or check the NCPWD site before ingest. |
| Size risk | About 130K characters of operative text, roughly 3× the Act. It enters as its own document with its own k=4, so it cannot crowd the Act out of its own slots. It **can** win the shared `top_n` cut if the budget stays at 12 (F1). That is exactly what the H8a.3 gate measures. |
| Licence / reuse | **NOT ESTABLISHED. This needs the owner's signature.** The gazette states no copyright or terms. Nigerian statutes and subsidiary legislation are official public law texts, and this copy is published by the regulator itself for public use. **The project has never recorded a reuse position for the Act gazette either** (same source, already in the corpus and live). The owner's signature here should cover both, ideally after asking the H6 legal reviewer one line: "may a free, non-commercial legal-information tool quote Nigerian Acts and S.I.s verbatim with citation?" |

## B. UN Convention on the Rights of Persons with Disabilities — NOT RECOMMENDED for the first round

| Field | Finding |
|---|---|
| Nigeria | **Signed 30 March 2007; ratified 24 September 2010.** Verified on the UN Treaty Collection (MTDSG IV-15) on 2026-10-22. No Nigerian declaration or reservation appeared in the part of the page read; the page was truncated, so this is not fully confirmed. |
| Domestic effect | Not directly enforceable unless enacted into law by the National Assembly (Constitution s. 12(1), already in the corpus). Every answer citing it would need that status note (H8a.4). How far the 2018 Act gives effect to the CRPD is a legal question for the H6 reviewer; the Act does not reproduce the treaty text. |
| Licence / reuse | **A real obstacle.** un.org's Terms of Use allow download and copying for "personal, non-commercial use" with "no right to resell or redistribute them or to compile or create derivative works therefrom". Chunking and redistributing the text in a public app is arguably redistribution or a derivative work. Treaty texts may be treated differently (the UN's separate Copyright page was not read). The OHCHR page returned HTTP 403 to the fetch tool. **Needs a legal answer before it can be considered.** |
| Usefulness | Medium. Users asking "what are my rights" would get treaty text that a Nigerian court will not enforce directly. That is a misleading-answer risk for this population. |

## C. Lagos State Special People's Law, 2011 — BLOCKED (no official text)

| Field | Finding |
|---|---|
| Text | **No free official full text found** (two searches on 2026-10-22). Law Nigeria reproduces the structure (41 sections) and sells a PDF for ₦2,000; `data/raw/SOURCES.md` already says not to pay that site, and it is not an official source. The Equal Rights Trust hosts a 2011 submission on the 2010 **Bill**, not the Law. |
| Dates | Sources disagree. LASODA's FAQ says enacted 24 June 2011; the press gives 21 June 2011 or 2012 for passage. |
| Leads | LASODA (officiallasoda.com / lasoda.lagosstate.gov.ng), the Lagos State House of Assembly, or the Lagos State gazette (Ministry of Justice). Contacting LASODA directly is the realistic path, and that is owner work. |
| Extra cost | State law: every answer needs "applies in Lagos only", and legal turns carry no location signal today. |

## D. Not pursued

- **NCPWD enforcement guidelines and compliance certificates:** administrative guidance, not law.
- **Other states' disability laws:** defer until one sub-national law has been done end to end.
- **African Disability Protocol:** Nigeria signed the instrument of ratification on 19 October 2023 (press report, not verified). It raises the same licence and domestic-effect questions as the CRPD.

---

## Owner sign-off

- [x] **Chosen document:** **A, Persons with Disabilities (Accessibility) Regulations, 2023 (S.I. No. 51 of 2023)**
- [x] **Reuse position:** "DRLCA may store and quote the chosen text verbatim with citation, non-commercially."
  **Signed: the owner (repo owner `batestguy`), 2026-10-22, in session:** *"go with the Accessibility Regulations, I sign off".*
- [ ] Also covers the Act gazette already in the corpus (`data/raw/disability_act_2018_gazette_FGP.pdf`): **not stated in
  the sign-off.** Ask the owner to confirm yes or no next session; until then the Act's reuse position stays unrecorded.
- [ ] Optional: put the one-line reuse question to the H6 legal reviewer.

**Filed after sign-off:** `data/raw/accessibility_regulations_2023_gazette_FGP.pdf`, sha256
`04bb8bec217b6ca01fa3ac3e5b5893ed619b2970ea7cb4b81f4ba2c047f28b05` (identical to the dossier download), with a row in
`data/raw/SOURCES.md`. Nothing in `data/raw/` is read at boot, and nothing has been parsed.

**After signing:** H8a.1 (author dev + blind `test3` questions from the official text, committed before any parsing). It can
start before the H6 review returns, because it changes nothing users see. **H8a.5's cut-over waits for H6.**

### Sources

- Gazette PDF (NCPWD): https://ncpwd.gov.ng/pdfs/44document.pdf
- RoLAC/IDEA on the 2023 Regulations rollout: https://www.idea.int/news/rolac-informs-relevant-stakeholders-implementation-2023-pwd-accessibility-regulations
- UN Treaty Collection, CRPD (IV-15): https://treaties.un.org/Pages/ViewDetails.aspx?src=TREATY&mtdsg_no=IV-15&chapter=4&clang=_en
- UN Terms of Use: https://www.un.org/en/about-us/terms-of-use
- Law Nigeria, Lagos Special People's Law (paid, not official): https://lawnigeria.com/2019/10/15/special-peoples-law-of-lagos-state/
- LASODA: https://officiallasoda.com/
