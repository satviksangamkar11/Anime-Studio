"""Tests for the scoped waiver rules in director/waivers.py (story, reel, language_render, versions, approval)."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

import waivers as wv

STORY = "STORY-001"
CODE = "DEAD_AIR_PAUSE"


def _rec(**over):
    data = {
        "waiver_id": "W-0001",
        "scope": "story",
        "story_id": STORY,
        "codes": [CODE],
        "owner": "production_owner",
        "issue": "pause too long",
        "reason": "accepted for pilot",
        "approved_by": "qc_approver",
        "approved_at": "2026-11-11T10:00:00+05:30",
        "status": "approved",
    }
    data.update(over)
    return data


def _load(tmp_path, entries):
    p = tmp_path / "waivers.json"
    p.write_text(json.dumps({"waivers": entries}), encoding="utf-8")
    return wv.read_waivers(str(p))


def _hits(records, reel="REEL-004", lang="hindi", version="v03", code=CODE, story=STORY):
    return wv.applicable_waivers(records, story, reel, lang, version, code)


# rule 1: scope
def test_story_scope_applies_every_reel_and_language(tmp_path):
    recs, probs = _load(tmp_path, [_rec()])
    assert probs == []
    for reel in ("REEL-001", "REEL-004"):
        for lang in ("hindi", "english", "marathi"):
            assert len(_hits(recs, reel, lang, "v07")) == 1


def test_story_scope_other_story_not_applied(tmp_path):
    recs, _ = _load(tmp_path, [_rec()])
    assert _hits(recs, story="STORY-002") == []


def test_reel_scope_all_languages_of_that_reel_only(tmp_path):
    recs, probs = _load(tmp_path, [_rec(scope="reel", reel_id="REEL-004", render_version="v03")])
    assert probs == []
    for lang in ("hindi", "english", "marathi"):
        assert len(_hits(recs, "REEL-004", lang, "v03")) == 1
    assert _hits(recs, "REEL-005", "hindi", "v03") == []


def test_language_render_applies_only_to_that_language(tmp_path):
    recs, probs = _load(tmp_path, [_rec(scope="language_render", reel_id="REEL-004", language="hindi",
                                        render_version="v03")])
    assert probs == []
    assert len(_hits(recs, "REEL-004", "hindi", "v03")) == 1
    assert _hits(recs, "REEL-004", "english", "v03") == []   # wrong language
    assert _hits(recs, "REEL-004", "marathi", "v03") == []
    assert _hits(recs, "REEL-005", "hindi", "v03") == []     # wrong reel


def test_language_render_unknown_language_refused(tmp_path):
    recs, probs = _load(tmp_path, [_rec(scope="language_render", reel_id="REEL-004", language="tamil",
                                        render_version="v03")])
    assert recs == [] and len(probs) == 1 and "language" in probs[0][1]


def test_unknown_scope_refused(tmp_path):
    recs, probs = _load(tmp_path, [_rec(scope="global")])
    assert recs == [] and "scope" in probs[0][1]


# rule 2: version
def test_versioned_story_waiver_only_exact_version(tmp_path):
    recs, _ = _load(tmp_path, [_rec(render_version="v03")])
    assert len(_hits(recs, version="v03")) == 1
    assert _hits(recs, version="v04") == []                  # regenerated render is not approved


def test_versioned_reel_waiver_not_approving_new_version(tmp_path):
    recs, _ = _load(tmp_path, [_rec(scope="reel", reel_id="REEL-004", render_version="v03")])
    assert _hits(recs, "REEL-004", "hindi", "v04") == []


def test_reel_waiver_without_version_applies_to_nothing(tmp_path):
    recs, probs = _load(tmp_path, [_rec(scope="reel", reel_id="REEL-004")])
    assert probs == []
    assert _hits(recs, "REEL-004", "hindi", "v03") == []


def test_non_string_render_version_refused(tmp_path):
    recs, probs = _load(tmp_path, [_rec(render_version=3)])
    assert recs == [] and "render_version" in probs[0][1]


# rule 3: approval
def test_self_approved_refused(tmp_path):
    recs, probs = _load(tmp_path, [_rec(approved_by="production_owner")])
    assert recs == [] and "self-approval" in probs[0][1]


def test_self_approval_case_insensitive_refused(tmp_path):
    recs, probs = _load(tmp_path, [_rec(owner="satvik", approved_by="Satvik")])
    assert recs == [] and "self-approval" in probs[0][1]
    recs, probs = _load(tmp_path, [_rec(owner="production_owner", approved_by="PRODUCTION_OWNER")])
    assert recs == [] and "self-approval" in probs[0][1]


def test_self_approval_ignores_surrounding_spaces_refused(tmp_path):
    recs, probs = _load(tmp_path, [_rec(owner="satvik", approved_by="  satvik \t")])
    assert recs == [] and "self-approval" in probs[0][1]


def test_self_approval_unicode_nfkc_refused(tmp_path):
    # full-width latin letters are compatibility forms: NFKC maps them to plain 'satvik'
    recs, probs = _load(tmp_path, [_rec(owner="satvik", approved_by="ｓａｔｖｉｋ")])
    assert recs == [] and "self-approval" in probs[0][1]


def test_self_approval_casefold_not_lower(tmp_path):
    # casefold('STRASSE') == casefold('Straße') == 'strasse'; lower() would miss the German sharp s
    recs, probs = _load(tmp_path, [_rec(owner="Straße", approved_by="STRASSE")])
    assert recs == [] and "self-approval" in probs[0][1]


def test_different_person_with_similar_name_accepted(tmp_path):
    recs, probs = _load(tmp_path, [_rec(owner="satvik", approved_by="satvik2")])
    assert probs == [] and len(recs) == 1 and recs[0]["approved_by"] == "satvik2"


def test_stored_approver_name_is_not_rewritten(tmp_path):
    recs, probs = _load(tmp_path, [_rec(owner="production_owner", approved_by="  QC Approver ")])
    assert probs == [] and recs[0]["approved_by"] == "QC Approver"


def test_missing_approved_by_refused(tmp_path):
    entry = _rec()
    del entry["approved_by"]
    recs, probs = _load(tmp_path, [entry])
    assert recs == [] and "approved_by" in probs[0][1]


def test_blank_approved_by_refused(tmp_path):
    recs, probs = _load(tmp_path, [_rec(approved_by="   ")])
    assert recs == [] and "approved_by" in probs[0][1]


def test_bad_approved_at_refused(tmp_path):
    recs, probs = _load(tmp_path, [_rec(approved_at="11/11/2026")])
    assert recs == [] and "ISO-8601" in probs[0][1]


def test_revoked_waiver_not_applied(tmp_path):
    recs, probs = _load(tmp_path, [_rec(status="revoked")])
    assert recs == [] and "revoked" in probs[0][1]
    assert _hits(recs) == []


def test_pending_waiver_not_applied(tmp_path):
    recs, probs = _load(tmp_path, [_rec(status="pending")])
    assert recs == [] and "pending" in probs[0][1]


# rule 4: critical codes
@pytest.mark.parametrize("code", sorted(wv.CRITICAL_CODES))
def test_critical_code_never_waived(tmp_path, code):
    recs, probs = _load(tmp_path, [_rec(codes=[code])])
    assert recs == [] and code in probs[0][1]
    assert wv.applicable_waivers(recs, STORY, "REEL-004", "hindi", "v03", code) == []


def test_mixed_record_keeps_non_critical_code(tmp_path):
    recs, probs = _load(tmp_path, [_rec(codes=[CODE, "MISSING_AUDIO"])])
    assert recs[0]["codes"] == frozenset({CODE})
    assert len(probs) == 1 and "MISSING_AUDIO" in probs[0][1]


def test_legacy_critical_code_refused(tmp_path):
    p = tmp_path / "old.json"
    p.write_text(json.dumps({"reel": 2, "codes": ["MISSING_AUDIO"], "owner": "A", "date": "2026-11-11",
                             "reason": "x"}), encoding="utf-8")
    with pytest.raises(ValueError, match="critical"):
        wv.load_waivers(str(p), 2)


# rule 5: duplicate ids
def test_duplicate_waiver_id_raises(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        _load(tmp_path, [_rec(), _rec(story_id="STORY-002")])


# rule 6: split and missing file
def test_split_waived_lists_waived_and_blocking(tmp_path):
    recs, _ = _load(tmp_path, [_rec(scope="reel", reel_id="REEL-004", render_version="v03")])
    waived, blocking = wv.split_waived([CODE, "VO_MISSING", "CLOSING_MOUTH_OPEN"], recs, STORY, "REEL-004",
                                       "hindi", "v03")
    assert waived == {CODE: ["W-0001"]}
    assert blocking == ["VO_MISSING", "CLOSING_MOUTH_OPEN"]


def test_missing_file_gives_nothing(tmp_path):
    assert wv.read_waivers(str(tmp_path / "none.json")) == ([], [])


# backward compatibility: old single-object format
def test_legacy_format_still_works(tmp_path):
    p = tmp_path / "old.json"
    p.write_text(json.dumps({"reel": 2, "codes": [CODE], "owner": "Satvik", "date": "2026-11-11",
                             "reason": "old"}), encoding="utf-8")
    recs, probs = wv.read_waivers(str(p))
    assert probs == []
    assert len(_hits(recs, "kalika_reel2", "english", "v09", story="STORY-009")) == 1
    assert _hits(recs, "kalika_reel3", "hindi", "v09") == []
    assert wv.load_waivers(str(p), 2) == frozenset({CODE})
