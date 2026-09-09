"""NGO lookup: CSV filter + fuzzy match + helpline banner (pandas only).

Contact verification 2026-09-08 (verifier subagent checked every contact
against the official site in the row's website column).
PRUNED from data/ngo.csv -- do NOT re-add without fresh verification:
  - The Leprosy Mission Nigeria: phone + email unverified on official pages.
  - Sightsavers Nigeria: no published Nigeria phone on official pages.
Medium confidence (kept; RECHECK before production reliance): NAB + NNAD --
their contact pages 404'd on fetch day, values kept from agreeing
official-domain snippets (scripts/test_phase03.py prints the RECHECK note).
"""
import difflib
import re

import pandas as pd

# --- Helpline banner contract ------------------------------------------------
# EVERY lookup path returns these two rows FIRST, before any CSV rows, via
# with_helplines(). Spec: DRAC Toll-Free 08000-3000-100 + DRAC WhatsApp
# 08000-3000-10 (repo non-negotiable: helplines always on top).
HELPLINES = [
    {"name": "DRAC Toll-Free (National Helpline)", "phone": "08000-3000-100"},
    {"name": "DRAC WhatsApp (National Helpline)", "phone": "08000-3000-10"},
]
DRAC_TOLLFREE = "08000-3000-100"
DRAC_WHATSAPP = "08000-3000-10"

SCHEMA = ["name", "disability_focus", "location", "phone", "email", "website", "description"]

# --- Verified-only guard -----------------------------------------------------
# Any CSV phone matching these fails load LOUDLY so guessed placeholders can
# never reach users again (old CSV had "0803 000 0000"-style guesses + blanks).
PLACEHOLDER_PATTERNS = [
    r"0803\s*000\s*0000",  # known guessed-phone placeholder style
    r"0000-000",  # zeroed-out number fragments
]
PLACEHOLDER_RES = [re.compile(p) for p in PLACEHOLDER_PATTERNS]

# --- Fuzzy safety ------------------------------------------------------------
# Playbook floor is 0.5 (deaf/death, blind/blend misroutes); raised to 0.6
# after a 2026-09-08 probe showed gibberish "martian" scoring 0.588 against
# the alias token "amputation" (Irede). Genuine misspellings in the matrix
# ("binness" 0.75, "visually" 0.86, "depresion" 0.95) still clear 0.6.
FUZZY_CUTOFF = 0.6

# Generic domain words: excluded from FUZZY token pools on both sides so a
# gibberish-plus-generic query ("xyzq martian disability") cannot score 1.0
# off the shared word "disability" (substring path is unaffected -- e.g.
# "hearing impairment", "mental health" still match directly).
_STOP = {"disability", "disabilities", "disabled", "impairment", "impairments",
        "disorder", "disorders", "handicap", "challenged"}

# Alias tokens per org so misspellings ("binness", "depresion") can match at
# TOKEN level -- they never resemble a full focus string closely enough for
# difflib.get_close_matches on whole values. Keys match name fragments.
_ALIASES = {
    "association of the blind": ["blind", "blindness", "sight", "vision", "eye", "eyes", "visually"],
    "association of the deaf": ["deaf", "deafness", "sign", "hearing-impaired"],
    "irede": ["amputee", "amputation", "prosthetic", "prosthesis", "mobility"],
    "down syndrome": ["down", "trisomy", "learning", "developmental"],
    "spinal cord": ["spinal", "paraplegia", "quadriplegia", "cord", "wheelchair"],
    "mentally aware": ["depression", "anxiety", "trauma", "suicide", "counselling",
                       "counseling", "therapy", "stress"],
    "taf africa": ["albino", "albinism", "skin"],
}


def helpline_frame() -> pd.DataFrame:
    """The 2-row banner frame (SCHEMA columns) prepended to every response."""
    rows = [{
        "name": h["name"],
        "disability_focus": "national helpline",
        "location": "Nigeria (national)",
        "phone": h["phone"],
        "email": "",
        "website": "",
        "description": "National disability helpline -- always listed first.",
    } for h in HELPLINES]
    return pd.DataFrame(rows, columns=SCHEMA)


def with_helplines(results: pd.DataFrame) -> pd.DataFrame:
    """Prepend the DRAC helpline banner to CSV result rows.

    THE function every lookup/response shape must go through, so the banner
    contract (toll-free + WhatsApp FIRST) cannot be bypassed by a new path.
    """
    base = results if isinstance(results, pd.DataFrame) else pd.DataFrame(results)
    for c in SCHEMA:  # tolerate thin frames (e.g. fallback rows)
        if c not in base.columns:
            base[c] = ""
    out = pd.concat([helpline_frame(), base[SCHEMA]], ignore_index=True)
    out = pd.DataFrame(out.drop_duplicates(subset=["name", "phone"], keep="first"),
                       columns=SCHEMA).reset_index(drop=True)
    return out


def _assert_verified_phones(df: pd.DataFrame) -> None:
    """Fail loudly on placeholder/empty phones so they never reach users."""
    bad = []
    for idx, row in df.iterrows():
        phone = str(row.get("phone", "")).strip()
        if not phone or any(rx.search(phone) for rx in PLACEHOLDER_RES):
            bad.append("row %s (%s): phone=%r" % (idx, row.get("name", "?"), row.get("phone", "")))
    if bad:
        raise ValueError(
            "Unverified/placeholder NGO phone(s) -- replace with published "
            "contacts or prune the row:\n  " + "\n  ".join(bad))


def load_ngo(csv_path: str) -> pd.DataFrame:
    """Load + schema-check the verified CSV; reject placeholder phones."""
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    missing = [c for c in SCHEMA if c not in df.columns]
    if missing:
        raise ValueError(f"NGO CSV missing columns: {missing}")
    _assert_verified_phones(df)
    return df


def _tokens(s: str) -> list:
    return re.findall(r"[a-z0-9]+", s.lower())


def _aliases_for(name: str) -> list:
    name_l = name.lower()
    toks: list = []
    for key, aliases in _ALIASES.items():
        if key in name_l:
            toks.extend(aliases)
    return toks


def _disability_ranked(df: pd.DataFrame, query: str) -> list:
    """Rank CSV rows for a disability query.

    Full-query substring first (primary-focus segment outranks secondary, so
    "visual" -> NAB, not TAF whose focus lists it second); token-level
    difflib fuzzy fallback (cutoff FUZZY_CUTOFF) ONLY when no substring hit,
    so the fuzzy flag honestly means "fuzzy (not substring) decided".
    Generic _STOP words are ignored on both sides of fuzzy scoring.
    Returns [{pos, idx, score, method, single}] sorted best-first.
    """
    q = query.strip().lower()
    if not q:
        return []
    subs, fuzz = [], []
    for pos, (idx, row) in enumerate(df.iterrows()):
        focus = str(row.get("disability_focus", ""))
        focus_l = focus.lower()
        segments = [s.strip() for s in re.split(r"[;/]", focus_l)]
        single = len([s for s in segments if s]) <= 1
        if q and q in focus_l:
            # Primary (single-category, or match inside the first-listed
            # focus) outranks secondary mentions: "visual" -> NAB over TAF.
            primary = single or (segments and q in segments[0])
            subs.append({"pos": pos, "idx": idx, "score": 1.0 if primary else 0.9,
                         "method": "substring-primary" if primary else "substring-secondary",
                         "single": single})
            continue
        qtoks = [t for t in _tokens(q) if t not in _STOP]
        candidates = [t for t in _tokens(focus) + _aliases_for(str(row.get("name", "")))
                      if t not in _STOP]
        best = 0.0
        for qt in qtoks:
            for ct in candidates:
                r = difflib.SequenceMatcher(None, qt, ct).ratio()
                if r > best:
                    best = r
        if best >= FUZZY_CUTOFF:
            fuzz.append({"pos": pos, "idx": idx, "score": best,
                         "method": "fuzzy", "single": single})
    ranked = subs if subs else fuzz
    # Best score first; ties -> specialist (single-focus) rows, then CSV order.
    ranked.sort(key=lambda r: (-round(r["score"], 3), 0 if r["single"] else 1, r["pos"]))
    return ranked


def _location_match(loc_text: str, query: str):
    """How a row location matches: 'substring' / 'fuzzy' / None."""
    q = query.strip().lower()
    loc = (loc_text or "").lower()
    if not q:
        return None
    if q in loc:
        return "substring"
    if difflib.SequenceMatcher(None, q, loc).ratio() >= FUZZY_CUTOFF:
        return "fuzzy"
    for qt in _tokens(q):
        for ct in _tokens(loc):
            if difflib.SequenceMatcher(None, qt, ct).ratio() >= FUZZY_CUTOFF:
                return "fuzzy"
    return None


def _jonapwd_row(df: pd.DataFrame) -> pd.DataFrame:
    """Umbrella-body fallback row (never empty): JONAPWD from CSV if present."""
    hit = df[df["name"].str.contains("JONAPWD", case=False, na=False)]
    if len(hit):
        return pd.DataFrame(hit.head(1), columns=SCHEMA)
    # Defensive: CSV should always carry JONAPWD; never return nothing.
    return pd.DataFrame([{
        "name": "Joint National Association of Persons with Disabilities (JONAPWD)",
        "disability_focus": "all disabilities",
        "location": "Abuja (national, state chapters)",
        "phone": "+234-(0)9063322622; 09115970958",
        "email": "info@jonapwd.org",
        "website": "https://www.jonapwd.org",
        "description": "Umbrella body of disability clusters across Nigeria; "
                       "policy advocacy and member referrals.",
    }], columns=SCHEMA)


def find_ngo_with_meta(df: pd.DataFrame, disability: str = "", location: str = "",
                       k: int = 5) -> tuple:
    """Full lookup: helplines FIRST + ranked CSV rows + meta dict.

    meta keys: fuzzy_fallback (bool), fuzzy_note, location_note,
    fallback_jonapwd (bool), top1 (first CSV org name or None).
    Empty-result rule: unknown disability (or unknown location with no
    disability filter) -> helplines + JONAPWD row, never an empty list.
    Unknown location WITH a matched disability keeps the disability ranking
    (location-insensitive) and says so in location_note.
    """
    meta = {"fuzzy_fallback": False, "fuzzy_note": "", "location_note": "",
            "fallback_jonapwd": False, "top1": None}
    dis = (disability or "").strip()
    loc = (location or "").strip()

    if dis:
        ranked = _disability_ranked(df, dis)
        if not ranked:
            meta["fallback_jonapwd"] = True
            meta["fuzzy_note"] = "no disability match for %r -> JONAPWD umbrella fallback" % dis
            meta["location_note"] = "fallback: location filter not applied"
            org = _jonapwd_row(df)
            meta["top1"] = org.iloc[0]["name"]
            out = with_helplines(org)
            out.attrs["ngo_meta"] = meta
            return out, meta
    else:
        ranked = [{"pos": pos, "idx": idx, "score": 1.0, "method": "unfiltered", "single": True}
                  for pos, idx in enumerate(df.index)]

    if loc:
        matched, methods = [], []
        for r in ranked:
            m = _location_match(str(df.loc[r["idx"], "location"]), loc)
            if m:
                matched.append(r)
                methods.append(m)
        if matched:
            meta["location_note"] = "location %r matched %d row(s) (%s)" % (
                loc, len(matched), ",".join(sorted(set(methods))))
            ranked = matched
        elif dis:
            meta["location_note"] = (
                "location %r matched nothing -- kept disability ranking "
                "(location-insensitive)") % loc
        else:
            meta["fallback_jonapwd"] = True
            meta["fuzzy_note"] = "no location match for %r (no disability filter) -> JONAPWD fallback" % loc
            meta["location_note"] = meta["fuzzy_note"]
            org = _jonapwd_row(df)
            meta["top1"] = org.iloc[0]["name"]
            out = with_helplines(org)
            out.attrs["ngo_meta"] = meta
            return out, meta
    else:
        meta["location_note"] = "no location filter"

    kept = ranked[: max(k, 1)]
    fuzzy_rows = [str(df.loc[r["idx"], "name"]) for r in kept if r["method"] == "fuzzy"]
    meta["fuzzy_fallback"] = bool(fuzzy_rows)
    meta["fuzzy_note"] = ("fuzzy fallback decided match for: %s" % "; ".join(fuzzy_rows)
                          if fuzzy_rows else "substring/unfiltered match (no fuzzy fallback)")
    orgs = df.loc[[r["idx"] for r in kept]]
    if len(orgs):
        meta["top1"] = orgs.iloc[0]["name"]
    out = with_helplines(orgs)
    out.attrs["ngo_meta"] = meta
    return out, meta


def find_ngo(df: pd.DataFrame, disability: str = "", location: str = "", k: int = 5) -> pd.DataFrame:
    """Substring prefilter + difflib fuzzy fallback; helplines always FIRST.

    Returns DataFrame (banner rows, then CSV rows). Fuzzy usage is logged on
    the frame: out.attrs["ngo_meta"]["fuzzy_fallback"] / ["fuzzy_note"].
    Use find_ngo_with_meta() when you need the (frame, meta) tuple directly.
    """
    out, _ = find_ngo_with_meta(df, disability=disability, location=location, k=k)
    return out


def find_ngo_records(df: pd.DataFrame, disability: str = "", location: str = "",
                     k: int = 5) -> list:
    """List-of-dicts response shape -- same banner contract via with_helplines."""
    out, _ = find_ngo_with_meta(df, disability=disability, location=location, k=k)
    return out.to_dict("records")
