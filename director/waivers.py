"""Per-reel waivers: codes the owner has signed off as acceptable for one reel.

File format (JSON): {"reel": int, "codes": [str], "owner": str, "date": "YYYY-MM-DD", "reason": str}.
A missing file means no waivers, so every finding blocks.

Scoped format (2026-11-11): {"waivers": [record, ...]} or a bare list of records. See read_waivers().
Legacy objects still load as scope "reel" for their reel number, every language, any render version.
"""

import datetime
import json
import os
import re
import unicodedata

_KEYS = {"reel", "codes", "owner", "date", "reason"}
_CODE_RE = re.compile(r"^[A-Z_]+$")
_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_REEL_NO_RE = re.compile(r"([0-9]+)$")
_SCOPES = frozenset({"story", "reel", "language_render"})
_LANGUAGES = frozenset({"hindi", "english", "marathi"})

# File, audio and lock integrity codes. A waiver naming one of them is refused, never approved.
# Sources: h3/gate_d_audio.py (VO and BGM gates), director/build_final_reel.py (lock and file checks).
CRITICAL_CODES = frozenset({
    "CORRUPT_RENDER", "MISSING_AUDIO", "BROKEN_FILE", "INVALID_DELIVERABLE", "ZERO_BYTES", "STALE_LOCK",
    "VO_MISSING", "VO_UNREADABLE", "NO_VO_FILES", "LOUDNESS_UNREADABLE", "BGM_MANIFEST_UNREADABLE",
})


def load_waivers(path, reel):
    """Return the frozenset of waived codes for `reel`; raise ValueError if the file is invalid."""
    if not os.path.isfile(path):
        if os.path.exists(path):
            raise ValueError("waivers path is not a file: " + str(path))
        return frozenset()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: waivers file must be a JSON object")
    unknown = set(data) - _KEYS
    if unknown:
        raise ValueError(f"{path}: unknown key(s) {sorted(unknown)}")
    missing = _KEYS - set(data)
    if missing:
        raise ValueError(f"{path}: missing key(s) {sorted(missing)}")
    if isinstance(data["reel"], bool) or not isinstance(data["reel"], int):
        raise ValueError(f"{path}: reel must be an int, got {data['reel']!r}")
    if data["reel"] != reel:
        raise ValueError(f"{path}: waivers are for reel {data['reel']!r}, not reel {reel!r}")
    if not isinstance(data["owner"], str) or not data["owner"].strip():
        raise ValueError(f"{path}: owner must not be empty")
    if not isinstance(data["reason"], str) or not data["reason"].strip():
        raise ValueError(f"{path}: reason must not be empty")
    if not isinstance(data["date"], str) or not _DATE_RE.fullmatch(data["date"]):
        raise ValueError(f"{path}: date must be YYYY-MM-DD, got {data['date']!r}")
    try:
        datetime.date.fromisoformat(data["date"])
    except ValueError as exc:
        raise ValueError(f"{path}: invalid date {data['date']!r}") from exc
    if not isinstance(data["codes"], list):
        raise ValueError(f"{path}: codes must be a list")
    for code in data["codes"]:
        if not isinstance(code, str) or not _CODE_RE.fullmatch(code):
            raise ValueError(f"{path}: bad waiver code {code!r}")
    bad = sorted(set(data["codes"]) & CRITICAL_CODES)
    if bad:
        raise ValueError(f"{path}: critical code(s) can never be waived: {bad}")
    return frozenset(data["codes"])


def _reel_no(reel_id):
    """Number at the end of a reel id: REEL-004 -> 4, kalika_reel2 -> 2. None when there is none."""
    match = _REEL_NO_RE.search(str(reel_id or ""))
    return int(match.group(1)) if match else None


def _person_key(name):
    """Comparison key for a person's name: NFKC, then strip, then casefold. 'Satvik', ' satvik ' and full-width
    'ｓａｔｖｉｋ' all give 'satvik'. Used only for the self-approval check; the stored names are not changed."""
    return unicodedata.normalize("NFKC", name).strip().casefold()


def _text(entry, key):
    value = entry.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _parse_iso(value):
    if not isinstance(value, str):
        raise ValueError("not a string")
    return datetime.datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)


def _legacy_record(path, data):
    codes = load_waivers(path, data.get("reel"))
    return {"waiver_id": None, "legacy": True, "scope": "reel", "story_id": None, "reel_id": None,
            "reel_no": data["reel"], "language": None, "codes": codes, "render_version": None,
            "owner": data["owner"], "approved_by": None}


def _scoped_record(entry, label):
    """Return (record, problems). record is None when the entry is unusable; problems are (waiver_id, reason)."""
    if not isinstance(entry, dict):
        return None, [(label, "record must be a JSON object")]
    wid = _text(entry, "waiver_id")
    if wid is None:
        return None, [(label, "waiver_id must be a non-empty string")]
    scope = entry.get("scope")
    if scope not in _SCOPES:
        return None, [(wid, f"scope must be one of {sorted(_SCOPES)}, got {scope!r}")]
    story_id = _text(entry, "story_id")
    reel_id = _text(entry, "reel_id")
    if story_id is None:
        return None, [(wid, "story_id must be a non-empty string")]
    if scope != "story" and _reel_no(reel_id) is None:
        return None, [(wid, f"reel_id must end in a number for scope {scope}, got {reel_id!r}")]
    language = entry.get("language")
    if scope == "language_render" and language not in _LANGUAGES:
        return None, [(wid, f"language must be one of {sorted(_LANGUAGES)}, got {language!r}")]
    rv = entry.get("render_version")
    if rv is not None and _text(entry, "render_version") is None:
        return None, [(wid, f"render_version must be a non-empty string, got {rv!r}")]
    if entry.get("status") != "approved":
        return None, [(wid, f"status is {entry.get('status')!r}, not approved")]
    owner = _text(entry, "owner")
    if owner is None:
        return None, [(wid, "owner must be a non-empty string")]
    approved_by = _text(entry, "approved_by")
    if approved_by is None:
        return None, [(wid, "approved_by is missing or empty")]
    if _person_key(approved_by) == _person_key(owner):
        return None, [(wid, "approved_by equals owner: self-approval refused")]
    try:
        _parse_iso(entry.get("approved_at"))
    except ValueError:
        return None, [(wid, f"approved_at is not ISO-8601: {entry.get('approved_at')!r}")]
    codes = entry.get("codes")
    if not isinstance(codes, list) or not codes:
        return None, [(wid, "codes must be a non-empty list")]
    if any(not isinstance(c, str) or not _CODE_RE.fullmatch(c) for c in codes):
        return None, [(wid, f"bad waiver code in {codes!r}")]
    problems = [(wid, f"critical code {c} can never be waived") for c in codes if c in CRITICAL_CODES]
    kept = frozenset(c for c in codes if c not in CRITICAL_CODES)
    if not kept:
        return None, problems
    record = {"waiver_id": wid, "legacy": False, "scope": scope, "story_id": story_id, "reel_id": reel_id,
              "reel_no": _reel_no(reel_id), "language": language if scope == "language_render" else None,
              "codes": kept, "render_version": _text(entry, "render_version"), "owner": owner,
              "approved_by": approved_by}
    return record, problems


def read_waivers(path):
    """Return (records, problems) for a waivers file. records are the approved, usable waivers. problems are
    (waiver_id, reason) pairs for every refused entry. A missing file gives ([], []). A duplicate waiver_id raises."""
    if not os.path.isfile(path):
        if os.path.exists(path):
            raise ValueError("waivers path is not a file: " + str(path))
        return [], []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "waivers" not in data and "scope" not in data:
        return [_legacy_record(path, data)], []
    if isinstance(data, dict):
        if set(data) != {"waivers"}:
            raise ValueError(f"{path}: expected only the key 'waivers', got {sorted(data)}")
        data = data["waivers"]
    if not isinstance(data, list):
        raise ValueError(f"{path}: waivers must be a JSON list")
    ids = [e.get("waiver_id") for e in data if isinstance(e, dict) and e.get("waiver_id")]
    dups = sorted({str(i) for i in ids if ids.count(i) > 1})
    if dups:
        raise ValueError(f"{path}: duplicate waiver_id {dups}")
    records, problems = [], []
    for index, entry in enumerate(data):
        record, found = _scoped_record(entry, f"{path}[{index}]")
        problems.extend(found)
        if record is not None:
            records.append(record)
    return records, problems


def _matches_where(rec, story_id, reel_id, language):
    if rec["legacy"]:
        return _reel_no(reel_id) == rec["reel_no"]
    if rec["story_id"] != story_id:
        return False
    if rec["scope"] == "story":
        return True
    if rec["reel_id"] != reel_id:
        return False
    return rec["scope"] == "reel" or rec["language"] == language


def _matches_version(rec, render_version):
    if rec["legacy"]:
        return True
    if rec["render_version"] is not None:
        return rec["render_version"] == render_version
    return rec["scope"] == "story"


def applicable_waivers(records, story_id, reel_id, language, render_version, finding_code):
    """Approved records (from read_waivers) that waive finding_code for this story, reel, language and version."""
    return [rec for rec in records
            if finding_code in rec["codes"]
            and _matches_where(rec, story_id, reel_id, language)
            and _matches_version(rec, render_version)]


def split_waived(codes, records, story_id, reel_id, language, render_version):
    """(waived, blocking): waived maps each covered code to its waiver ids; blocking lists the uncovered codes."""
    waived, blocking = {}, []
    for code in codes:
        hits = applicable_waivers(records, story_id, reel_id, language, render_version, code)
        if hits:
            waived[code] = [rec["waiver_id"] or "legacy" for rec in hits]
        else:
            blocking.append(code)
    return waived, blocking
