"""Round-3 regressions (triage R3-H3, voice_manifest.py): a non-object shot row is skipped, not an AttributeError."""
from h3.voice_manifest import build_manifest, stale_entries


def test_build_manifest_skips_non_object_rows(tmp_path):
    shot = {"id": "s1", "audio_and_dialogue_track": {"narration_by_lang": {"en": {"text": "Hello there.", "language": "en",
                                                                                "time_range": [0.0, 1.0]}}}}
    m = build_manifest(str(tmp_path), [42, shot, "junk"], ["en"])
    assert [e["shot_id"] for e in m["entries"]] == ["s1"]


def test_stale_entries_skips_non_object_rows():
    assert stale_entries({"entries": []}, [42, "junk"]) == []
