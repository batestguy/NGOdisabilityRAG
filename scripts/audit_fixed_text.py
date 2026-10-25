"""H6-S.2 -- fixed-text traceability audit. Zero LLM, zero network, zero quota.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts\\audit_fixed_text.py   (from D:\\NGORAG)

WHY (docs/phases/19_zero_cost_self_review.md)
---------------------------------------------
No lawyer has read DRLCA (zero-cost rule, 2026-10-25). Hand-written text that
states law -- today rag.DOC_STATUS_NOTES, shown before the first Regulations
excerpt -- is therefore held to a mechanical standard instead: every fact in it
must be found, word for word, in the corpus chunk it cites.

WHAT IT CHECKS, PER NOTE
------------------------
1. Every claim's `say` span is present in the note (the ledger matches the text
   users actually see).
2. Every claim's `evidence` phrase is present in the cited chunk's text.
   Matching ignores case, whitespace and punctuation ONLY -- the gazette OCR runs
   words together ("seekredress incourt") and that must not hide a match. The
   corpus text itself is never altered.
3. Every citation tag in the note is a real chunk tag, and every claim's tag
   appears in the note (the user can see where it came from).
4. Every number printed in the note appears in some claim's evidence or tag.
   An unledgered number is a FAIL: nobody traced it.
5. Every sentence of the note is covered by at least one claim.

Claim kinds:
  verbatim     the source says it in these words
  paraphrase   same meaning, different words; the evidence phrases carry
               every fact (numbers, actors, conditions), and `why` says what
               changed
  interpretive a legal characterisation NOT stated in the source (e.g.
               "subsidiary legislation with legal force"). Not a FAIL -- it is
               owner-signed text -- but listed as UNTRACEABLE for the owner and
               the funded legal review (F1). Never silently passed.

Exit 1 on any FAIL. Interpretive claims are reported, not failed.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import rag  # noqa: E402
from retrieve import cite_tag  # noqa: E402

# The claim ledger for each fixed note. Edit the note -> edit the ledger.
LEDGER = {
    "accessregs2023": [
        {"say": "Persons with Disabilities (Accessibility) Regulations, 2023 "
                "(S.I. No. 51 of 2023)",
         "tag": "[Regs general]", "kind": "verbatim",
         "evidence": ["PERSONS WITH DISABILITIES (ACCESSIBILITY) REGULATIONS, 2023",
                      "S. I. No. 51 of 2023"]},
        {"say": "are subsidiary legislation with legal force",
         "tag": "[Regs general]", "kind": "interpretive",
         "evidence": [],
         "why": "A legal characterisation of an S.I.; no source sentence says it."},
        {"say": "made by the Governing Council of the National Commission for "
                "Persons with Disabilities under section 56 of the Disability Act 2018",
         "tag": "[Regs general]", "kind": "verbatim",
         "evidence": ["In exercise of the powers conferred on it by section 56",
                      "the Governing Council of the National Commission for "
                      "Persons with Disabilities",
                      "makes the following Regulations",
                      "(Prohibition) Act, 2018"]},
        {"say": "[Act cl. 56]",
         "tag": "[Act cl. 56]", "kind": "verbatim",
         "evidence": ["The Council may make regulations"]},
        {"say": "The gazette marks 22 May 2023 as their commencement date",
         "tag": "[Regs general]", "kind": "paraphrase",
         "evidence": ["[22nd day of May, 2023]", "Commence- ment"],
         "why": "The gazette prints the date with the marginal note "
                "'Commencement.'; the note says so in words. The gazette "
                "PUBLICATION date (7 July 2023) is an open F1 question."},
        {"say": "A person who breaks them is liable to an administrative penalty "
                "of not less than N 500,000",
         "tag": "[Regs reg. 168]", "kind": "paraphrase",
         "evidence": ["any person who contravenes the provisions of these Regulations "
                      "is liable to an administrative penalty of not less than N 500,000"],
         "why": "'contravenes the provisions of these Regulations' -> 'breaks them'."},
        {"say": "a company, government institution or body corporate to not less "
                "than N 2,000,000",
         "tag": "[Regs reg. 168]", "kind": "verbatim",
         "evidence": ["Any company, government institution or body corporate",
                      "administrative penalty of not less than N 2,000,000"]},
        {"say": "regardless of any penalty under the Act or other law [Regs reg. 168]",
         "tag": "[Regs reg. 168]", "kind": "paraphrase",
         "evidence": ["Notwithstanding the penalties provided under the Act or any other law"],
         "why": "'Notwithstanding' -> 'regardless of' (owner-signed, 2026-10-23)."},
        {"say": "The Commission, with the relevant authority, may seal off a place "
                "in default after a 90-day notice [Regs reg. 169]",
         "tag": "[Regs reg. 169]", "kind": "paraphrase",
         "evidence": ["the Commission, in collaboration with a relevant authority, "
                      "may seal off a built environment found to be in default",
                      "a 90 day notice to regularize the default"],
         "why": "'built environment' -> 'place'; the 90-day notice goes to the "
                "owner, manager, occupier or developer (not named in the note)."},
        {"say": "Under the Act you can notify the authority in charge of an "
                "inaccessible place without giving up your right to go to court "
                "[Act cl. 8]",
         "tag": "[Act cl. 8]", "kind": "paraphrase",
         "evidence": ["without prejudice to his right to seek redress in court",
                      "notify the relevant authority in charge of the environment",
                      "state of inaccessibility"],
         "why": "'without prejudice to his right to seek redress in court' -> "
                "'without giving up your right to go to court'. cl. 8(1) is "
                "'Subject to section 7' -- not mentioned in the note."},
    ],
}

TAG_RE = re.compile(r"\[(?:Act cl\.|Constitution s\.|Factsheet Section|Regs reg\.|Regs) ?[^\]]*\]")
NUM_RE = re.compile(r"\d[\d,]*")


def norm(s: str) -> str:
    """Lowercase, letters and digits only: OCR spacing must not hide a match."""
    return re.sub(r"[^0-9a-z]", "", s.lower())


def main() -> int:
    docs = rag.build_corpus()
    text_by_tag = {}
    for doc_id, chunks in docs.items():
        for c in chunks:
            text_by_tag.setdefault(cite_tag(doc_id, c.ref), []).append(c.text)

    fails, untraceable = [], []
    print("H6-S.2 fixed-text traceability (corpus %s)" % rag.CORPUS_VERSION)
    for doc_id, note in rag.DOC_STATUS_NOTES.items():
        claims = LEDGER.get(doc_id)
        print("\n== %s: %d claims ==" % (doc_id, len(claims or [])))
        if not claims:
            fails.append("%s: note has no ledger" % doc_id)
            continue
        for i, cl in enumerate(claims, 1):
            problems = []
            if cl["say"] not in note:
                problems.append("say-span not in note")
            if cl["tag"] not in note:
                problems.append("tag %s not shown in note" % cl["tag"])
            src = norm(" ".join(text_by_tag.get(cl["tag"], [])))
            if not src:
                problems.append("tag %s has no chunk" % cl["tag"])
            for ev in cl["evidence"]:
                if norm(ev) not in src:
                    problems.append("evidence not in %s: %r" % (cl["tag"], ev))
            if cl["kind"] in ("paraphrase", "interpretive") and not cl.get("why"):
                problems.append("%s claim without `why`" % cl["kind"])
            if cl["kind"] == "interpretive":
                untraceable.append("%s #%d %r -- %s" % (doc_id, i, cl["say"], cl["why"]))
            status = "FAIL" if problems else (
                "UNTRACEABLE" if cl["kind"] == "interpretive" else "ok")
            print("  %-11s #%d %-12s %s %s" % (status, i, cl["kind"], cl["tag"],
                                                cl["say"][:70]))
            for pr in problems:
                print("              -> " + pr)
                fails.append("%s #%d: %s" % (doc_id, i, pr))

        for tag in TAG_RE.findall(note):
            if tag not in text_by_tag:
                fails.append("%s: note tag %s matches no chunk" % (doc_id, tag))
        ledgered = norm(" ".join(e for cl in claims for e in cl["evidence"])
                        + " ".join(cl["tag"] for cl in claims))
        for num in NUM_RE.findall(note):
            if norm(num) not in ledgered:
                fails.append("%s: number %s is not in any claim's evidence" % (doc_id, num))
        covered = note.replace("About this source:", " ")  # a label, not a claim
        for cl in claims:
            covered = covered.replace(cl["say"], " ")
        covered = TAG_RE.sub(" ", covered)  # tags are checked in step 3
        leftover = [s.strip() for s in re.split(r"(?<=\.)\s+", covered)
                    if len(norm(s)) > 12 and norm(s) not in ("aboutthissource",)]
        for s in leftover:
            fails.append("%s: text not covered by any claim: %r" % (doc_id, s[:80]))

    print("\nUNTRACEABLE (interpretive, owner-signed; for the owner and funded review F1):")
    for u in untraceable or ["none"]:
        print("  - " + u)
    if fails:
        print("\nFAILS:")
        for f in fails:
            print("  - " + f)
        print("\nAUDIT_FIXED_TEXT: FAIL (%d)" % len(fails))
        return 1
    print("\nAUDIT_FIXED_TEXT: PASS (every fact traced verbatim or as a declared "
          "paraphrase; %d interpretive claim(s) listed)" % len(untraceable))
    return 0


if __name__ == "__main__":
    sys.exit(main())
