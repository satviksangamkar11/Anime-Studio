"""G5/G6/G21: language_code, seed, explicit settings, pronunciation locators, output format. Fake client, no network."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import voice_cast as v  # noqa: E402

PLAN = {"lines": [{"id": "S1-N", "voice": "NARRATOR", "en": "Daksha spoke.", "hi": "दक्ष बोले।", "mr": "दक्ष बोलला."}]}
VM = {lg: {"NARRATOR": f"vid-{lg}"} for lg in v.LANGS}


def jobs(model="eleven_v4", models=None, **kw):
    return v.build_jobs(PLAN, ["S1-N"], VM, model, models, **kw)


def by_lang(js):
    return {j["lang"]: j for j in js}


def test_job_has_language_code_v4():
    for m in ("eleven_v4", "eleven_v3"):
        assert {lg: j["language_code"] for lg, j in by_lang(jobs(m)).items()} == {"en": "en", "hi": "hi", "mr": "mr"}


def test_no_language_code_for_multilingual_v2():
    j = by_lang(jobs("eleven_v4", {"hi": {"NARRATOR": "eleven_multilingual_v2"}}))
    assert j["hi"]["language_code"] is None and j["mr"]["language_code"] == "mr"
    assert "language_code" not in v.request_body(j["hi"])
    assert v.request_body(j["mr"])["language_code"] == "mr"


def test_seed_in_job_key():
    a = by_lang(jobs())["en"]
    assert a["seed"] == int(hashlib.sha256(b"S1-N").hexdigest()[:8], 16)
    assert 0 <= a["seed"] <= 4294967295 and v.request_body(a)["seed"] == a["seed"]
    assert v.job_key("en", "vid-en", "eleven_v4", "t", v.SETTINGS, "en", 1) != v.job_key("en", "vid-en", "eleven_v4", "t", v.SETTINGS, "en", 2)


def test_settings_explicit_defaults():
    j = by_lang(jobs())["en"]
    assert j["settings"] == {"stability": 0.5, "similarity_boost": 0.75, "style": 0, "use_speaker_boost": True}
    assert v.request_body(j)["voice_settings"] == j["settings"]
    s = by_lang(jobs(line_speed={"S1-N.en": 1.15}))["en"]["settings"]
    assert s["speed"] == 1.15 and s["stability"] == 0.5


def loc(n):
    return [{"pronunciation_dictionary_id": f"d{i}", "version_id": f"v{i}"} for i in range(n)]


def test_locators_max_3(tmp_path):
    (tmp_path / "pronunciation_en.json").write_text(json.dumps({"locators": loc(3)}), encoding="utf-8")
    assert len(v.pronunciation_dictionary_locators(tmp_path, "en")) == 3
    assert v.pronunciation_dictionary_locators(tmp_path, "hi") == []                  # no file = none
    (tmp_path / "pronunciation_hi.json").write_text(json.dumps({"locators": loc(4)}), encoding="utf-8")
    with pytest.raises(SystemExit):
        v.pronunciation_dictionary_locators(tmp_path, "hi")


def test_locator_ids_in_job_key():
    a = by_lang(jobs())["en"]
    b = by_lang(jobs(locators={"en": loc(1)}))["en"]
    c = by_lang(jobs(locators={"en": [{"pronunciation_dictionary_id": "other", "version_id": "v0"}]}))["en"]
    assert len({a["key"], b["key"], c["key"]}) == 3
    assert v.request_body(b)["pronunciation_dictionary_locators"] == loc(1)
    assert "pronunciation_dictionary_locators" not in v.request_body(a)
    assert b["text"] == a["text"]                                                     # spoken text/caption text unchanged


def test_output_format_from_config(tmp_path):
    d = by_lang(jobs())["en"]
    assert d["output_format"] == "mp3_44100_128"                                      # default unchanged
    w = by_lang(jobs(output_format="wav_44100"))["en"]
    assert w["output_format"] == "wav_44100" and w["key"] != d["key"]
    paths = []
    v.run([w], tmp_path, 10_000, "k" * 20, post=lambda m, p, k, b=None: (paths.append(p), (b"x", {}))[1],
          ledger=v.Ledger(tmp_path / "l.jsonl", 10_000), probe=lambda p: 2.0)
    assert paths[0].endswith("?output_format=wav_44100")


def test_default_path_still_mp3(tmp_path):
    paths = []
    v.run([by_lang(jobs())["en"]], tmp_path, 10_000, "k" * 20,
          post=lambda m, p, k, b=None: (paths.append(p), (b"x", {}))[1],
          ledger=v.Ledger(tmp_path / "l.jsonl", 10_000), probe=lambda p: 2.0)
    assert paths[0].endswith("?output_format=mp3_44100_128")
    assert list((tmp_path / "mp3" / "en").glob("*.mp3"))
