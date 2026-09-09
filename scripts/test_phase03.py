"""Phase 03 test matrix: verified CSV + helpline banner + fuzzy + fallback.

Run: C:\\conda-envs\\drlca-rag\\python.exe scripts/test_phase03.py
Stdlib + pandas only. Prints a results table + PASS/FAIL summary + the
RECHECK note; exits nonzero on ANY failure so CI/CI-style runs catch it.

Asserts per playbook 03_ngo_connector.md:
  - correct org top-1 per (disability x location) cell (7 disabilities,
    incl. misspellings that must take the fuzzy path),
  - DRAC Toll-Free 08000-3000-100 + DRAC WhatsApp 08000-3000-10 FIRST in
    EVERY response,
  - unknown disability/location -> helplines + JONAPWD umbrella row, never empty,
  - verified-only guard rejects placeholder phones at load time,
  - difflib cutoff stays >= 0.5, pruned rows stay out of the CSV.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import ngo  # noqa: E402
from ngo import (  # noqa: E402
    DRAC_TOLLFREE,
    DRAC_WHATSAPP,
    FUZZY_CUTOFF,
    _assert_verified_phones,
    find_ngo_with_meta,
    load_ngo,
)

CSV = ROOT / "data" / "ngo.csv"

# Medium-confidence rows (contact pages 404'd on fetch day 2026-09-08; values
# from agreeing official-domain snippets). Printed every run by design.
RECHECK_NOTE = (
    "RECHECK (medium confidence, 2026-09-08): Nigerian Association of the Blind "
    "(NAB) + Nigerian National Association of the Deaf (NNAD) contact pages 404'd "
    "on fetch day; phone/email values kept from agreeing official-domain snippets. "
    "Re-verify both against official sites before production reliance."
)

# id, disability query, location query, expected top-1 org (substring of name),
# expect_fuzzy (None = don't assert), expect_loc_unmatched (bool).
CELLS = [
    # --- clean substring path, HQs aligned ---
    ("D1", "visual impairment", "Lagos", "Association of the Blind", False, False),
    ("D2", "hearing impairment", "Abuja", "Association of the Deaf", False, False),
    ("D3", "limb loss", "Lagos", "Irede", False, False),
    ("D4", "Down syndrome", "Lagos", "Down Syndrome", False, False),
    ("D5", "mental health", "Lagos", "Mentally Aware", False, False),
    ("D6", "albinism", "Abuja", "TAF Africa", False, False),
    ("D7", "spinal injury", "Lagos", "Spinal Cord", True, False),
    # --- misspellings: MUST take the fuzzy fallback path ---
    ("F1", "visually impaired", "Lagos", "Association of the Blind", True, False),
    ("F2", "hearing impared", "Abuja", "Association of the Deaf", True, False),
    ("F3", "blindnss", "Lagos", "Association of the Blind", True, False),
    ("F4", "binness", "rural", "Association of the Blind", True, True),
    ("F5", "depresion", "Lagos", "Mentally Aware", True, False),
    # --- location behavior ---
    ("L1", "visual impairment", "Kano", "Association of the Blind", False, True),
    ("L2", "visual impairment", "Abuja", "TAF Africa", False, False),  # location-priority:
    # TAF is the Abuja-based org whose focus includes visual impairment.
    # --- unknown -> helplines + JONAPWD, never empty ---
    ("U1", "xyzq martian disability", "Lagos", "JONAPWD", None, False),
    ("U2", "xyzq", "Atlantis", "JONAPWD", None, False),
]


def check_banner(res: pd.DataFrame):
    """Helpline banner FIRST: returns (ok, detail)."""
    if len(res) < 2:
        return False, "fewer than 2 rows"
    r0, r1 = res.iloc[0], res.iloc[1]
    ok = (r0["phone"] == DRAC_TOLLFREE and "Toll-Free" in str(r0["name"])
          and r1["phone"] == DRAC_WHATSAPP and "WhatsApp" in str(r1["name"]))
    return ok, "row0=%s/%s row1=%s/%s" % (r0["name"], r0["phone"], r1["name"], r1["phone"])


def main() -> int:
    failures = []
    print("csv=%s" % CSV)
    print("RECHECK note: %s\n" % RECHECK_NOTE)

    # --- static guards (run before the matrix) ---
    try:
        df = load_ngo(str(CSV))
        print("load_ngo: OK (%d rows)" % len(df))
    except Exception as e:  # noqa: BLE001 -- test must report, not crash
        print("load_ngo: FAIL (%s)" % e)
        return 1
    statics = [
        ("10 verified rows", len(df) == 10, "got %d" % len(df)),
        ("cutoff>=0.5", FUZZY_CUTOFF >= 0.5, "FUZZY_CUTOFF=%s" % FUZZY_CUTOFF),
        ("Leprosy pruned", not df["name"].str.contains("Leprosy").any(), ""),
        ("Sightsavers pruned", not df["name"].str.contains("Sightsavers").any(), ""),
    ]
    # Guard must fire on each placeholder style; must NOT fire on real phones.
    for label, phone in [("0803-style", "0803 000 0000"), ("zeroed", "0000-000-111"), ("empty", "")]:
        trial = pd.DataFrame([{
            "name": "Probe", "disability_focus": "x", "location": "y", "phone": phone,
            "email": "", "website": "", "description": ""}], columns=list(ngo.SCHEMA))
        try:
            _assert_verified_phones(trial)
            statics.append(("guard rejects %s" % label, False, "no error raised"))
        except ValueError:
            statics.append(("guard rejects %s" % label, True, ""))
    for label, ok, detail in statics:
        print("[%s] static: %s %s" % ("PASS" if ok else "FAIL", label, detail))
        if not ok:
            failures.append("static:%s" % label)

    # --- matrix ---
    print("\n%-4s %-24s %-10s %-34s %-5s %-6s %-4s  %s"
          % ("cell", "disability", "location", "top-1 org", "fuzzy", "helpl", "res", "note"))
    for cid, dis, loc, expected, exp_fuzzy, exp_unmatched in CELLS:
        res, meta = find_ngo_with_meta(df, disability=dis, location=loc)
        banner_ok, banner_detail = check_banner(res)
        top1 = meta["top1"] or ""
        top_ok = expected.lower() in top1.lower() and len(res) >= 3
        fuzzy_ok = (exp_fuzzy is None) or (meta["fuzzy_fallback"] == exp_fuzzy)
        loc_ok = (not exp_unmatched) or ("matched nothing" in meta["location_note"])
        ok = banner_ok and top_ok and fuzzy_ok and loc_ok
        print("%-4s %-24s %-10s %-34s %-5s %-6s %-4s  %s" % (
            cid, dis[:24], loc[:10], top1[:34],
            "Y" if meta["fuzzy_fallback"] else "n",
            "Y" if banner_ok else "FAIL",
            "PASS" if ok else "FAIL",
            ("fuzzy: %s | loc: %s" % (meta["fuzzy_note"], meta["location_note"]))[:110]))
        if not ok:
            detail = "cell=%s dis=%r loc=%r top1=%r banner=%s(%s) fuzzy=%s loc_note=%s" % (
                cid, dis, loc, top1, banner_ok, banner_detail,
                meta["fuzzy_fallback"], meta["location_note"])
            failures.append(detail)

    # --- banner evidence: every response shape, incl. the records shape ---
    recs = ngo.find_ngo_records(df, disability="depresion", location="Kano")
    rec_ok = (recs[0]["phone"] == DRAC_TOLLFREE and recs[1]["phone"] == DRAC_WHATSAPP
              and "Mentally Aware" in recs[2]["name"])
    print("\nrecords-shape banner check (depresion/Kano): %s "
          "(row0=%s, row1=%s, row2=%s)" % (
              "PASS" if rec_ok else "FAIL",
              recs[0]["phone"], recs[1]["phone"], recs[2]["name"]))
    if not rec_ok:
        failures.append("records-shape banner order wrong")

    n_cells = len(CELLS)
    n_pass = n_cells - sum(1 for f in failures if f.startswith("cell="))
    print("\nmatrix: %d/%d cells PASS | statics: %d/%d PASS | RECHECK printed: yes"
          % (n_pass, n_cells,
             sum(1 for s in statics if s[1]), len(statics)))
    if failures:
        print("FAILURES:")
        for f in failures:
            print("  - %s" % f)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
