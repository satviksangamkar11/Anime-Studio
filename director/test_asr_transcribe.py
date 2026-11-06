"""Offline tests for asr_transcribe. yt-dlp, ffmpeg, the Whisper model and Groq are all faked: no download, no model call."""
import io
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
import wave
from collections import namedtuple
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asr_transcribe as asr  # noqa: E402

SEG = namedtuple("SEG", "start end text")
KEY = "gsk_TESTKEY_not_real_123"
URL = "https://youtu.be/QIJ4qxo_Oz4"
ORIG_PICK_DEVICE = asr.pick_device
SENT = ["नमस्ते दोस्तों आज हम एक नई कहानी शुरू करते हैं।", "यह कथा बहुत पुरानी और सुंदर है।",
        "इसे ध्यान से सुनिए और समझिए।", "हर पात्र का एक गहरा अर्थ है।",
        "आइए इस यात्रा को साथ मिलकर देखें।", "अब कहानी का पहला भाग शुरू होता है।"]


def fmt(s: float) -> str:
    return f"00:{int(s // 60):02d}:{s % 60:06.3f}"


def make_vtt(lines, step=5.0) -> str:
    out = ["WEBVTT", "Kind: captions", ""]
    for i, t in enumerate(lines):
        out += [f"{fmt(i * step)} --> {fmt((i + 1) * step)}", t, ""]
    return "\n".join(out)


def write_wav(path, secs: float) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(secs * 16000))


class FakeModel:
    def __init__(self, detections=(), chunks=()):
        self.detections = list(detections)  # one {lang: prob} per detection window
        self.chunks = list(chunks)          # one segment list per transcribe call
        self.transcribe_kwargs = []
        self.detect_calls = 0

    def detect_language(self, audio=None, **kw):
        self.detect_calls += 1
        allp = sorted(self.detections.pop(0).items(), key=lambda x: -x[1])
        return allp[0][0], allp[0][1], allp

    def transcribe(self, audio, **kw):
        self.transcribe_kwargs.append(kw)
        return iter(self.chunks.pop(0)), None


@pytest.fixture
def dwork():
    """Test scratch folder on D: (the owner's rule: no big files on C:)."""
    d = Path("D:/aai work/asr_tmp") / f"pytest-{uuid.uuid4().hex[:8]}"
    d.mkdir(parents=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def roots(dwork, monkeypatch):
    tmp, studio = dwork / "asr_tmp", dwork / "studio"
    monkeypatch.setattr(asr, "ASR_TMP", tmp)
    monkeypatch.setattr(asr, "STUDIO", studio)
    monkeypatch.setattr(asr, "_cache_env", lambda: None)
    monkeypatch.setattr(asr, "pick_device", lambda: ("cpu", "int8"))
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    return tmp, studio


@pytest.fixture
def fake_run(monkeypatch):
    seconds = {"src": 90.0}
    calls = []

    def run(cmd):
        calls.append(cmd)
        if cmd[0] == "yt-dlp":
            Path(cmd[cmd.index("-o") + 1].replace("%(ext)s", "webm")).write_bytes(b"audio")
        elif cmd[0] == "ffmpeg":
            secs = seconds["src"]
            if "-t" in cmd:
                secs = min(secs, float(cmd[cmd.index("-t") + 1]))
            write_wav(cmd[-1], secs)
        else:
            raise AssertionError(f"unexpected command {cmd[0]}")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(asr, "_run", run)
    return calls, seconds


def use_model(monkeypatch, model):
    monkeypatch.setattr(asr, "_load_whisper", lambda name, dev, ct: model)


# ---------------------------------------------------------------- captions

def test_vtt_rolling_captions_become_running_text():
    vtt = ("WEBVTT\n\n00:00:00.000 --> 00:00:02.000 align:start\nनमस्ते दोस्तों\n\n"
           "00:00:02.000 --> 00:00:04.000\nनमस्ते दोस्तों <c>आज</c> हम\n\n"
           "00:00:04.000 --> 00:00:06.000\nआज हम कहानी शुरू करते हैं\n")
    segs = asr.roll_segments(asr.vtt_cues(vtt))
    assert " ".join(s["text"] for s in segs) == "नमस्ते दोस्तों आज हम कहानी शुरू करते हैं"
    assert segs[0]["start"] == 0.0 and segs[-1]["end"] == 6.0


def test_caption_quality_accepts_a_good_track():
    q = asr.caption_quality(" ".join(SENT), SENT, 60, "hi")
    assert q["ok"] and q["reasons"] == []


@pytest.mark.parametrize("text, cues, dur, lang, reason", [
    (" ".join(SENT), ["हाँ जी"] * 10, 60, "hi", "one caption line"),
    ("हाँ", ["हाँ"], 300, "hi", "words/min"),
    ("♪ ♫ ♪ ♫ नमस्ते", SENT[:6], 60, "hi", "symbols"),
    ("hello everyone this is a story about gods and kings in the old days", SENT, 60, "hi", "wrong script"),
])
def test_caption_quality_rejects_bad_tracks(text, cues, dur, lang, reason):
    q = asr.caption_quality(text, cues, dur, lang)
    assert not q["ok"] and any(reason in r for r in q["reasons"])


def test_manual_captions_win_over_auto(roots, monkeypatch):
    tmp, _ = roots
    meta = {"duration": 60, "subtitles": {"hi": [{"ext": "vtt"}]}, "automatic_captions": {"hi-orig": [{}]}, "language": "hi"}
    seen = []

    def fetch(url, lang, kind, job):
        seen.append((kind, lang))
        return make_vtt(SENT)

    monkeypatch.setattr(asr, "_caption_text", fetch)
    res = asr.check_captions(URL, ("hi",), meta=meta, work_dir=tmp)
    assert res["engine"] == "captions" and res["params"]["track"] == "manual"
    assert seen == [("manual", "hi")]
    assert res["text"].startswith("नमस्ते दोस्तों") and res["seconds_audio"] == 60
    assert not list(tmp.glob("job-*"))


def test_bad_auto_captions_return_none(roots, monkeypatch):
    tmp, _ = roots
    meta = {"duration": 60, "subtitles": {}, "automatic_captions": {"hi-orig": [{}]}, "language": "hi"}
    monkeypatch.setattr(asr, "_caption_text", lambda url, lang, kind, job: make_vtt(["हाँ जी"] * 10))
    assert asr.check_captions(URL, ("hi",), meta=meta, work_dir=tmp) is None


def test_machine_translation_track_is_never_used(roots, monkeypatch):
    tmp, _ = roots
    meta = {"duration": 60, "subtitles": {}, "automatic_captions": {"hi": [{}]}, "language": "en"}
    monkeypatch.setattr(asr, "_caption_text", lambda *a: pytest.fail("translation track fetched"))
    assert asr.check_captions(URL, ("hi",), meta=meta, work_dir=tmp) is None


def test_check_captions_refuses_non_youtube():
    with pytest.raises(ValueError, match="REFUSED"):
        asr.check_captions("https://evil.example/v.mp4", meta={})


def test_get_transcript_uses_captions_then_falls_back_to_speech(roots, monkeypatch):
    tmp, _ = roots
    monkeypatch.setattr(asr, "check_captions", lambda *a, **k: {"text": "cap", "engine": "captions"})
    monkeypatch.setattr(asr, "transcribe_url", lambda *a, **k: pytest.fail("ASR run although captions exist"))
    assert asr.get_transcript(URL, "hi")["engine"] == "captions"

    monkeypatch.setattr(asr, "check_captions", lambda *a, **k: None)
    monkeypatch.setattr(asr, "transcribe_url", lambda *a, **k: {"engine": "local"})
    assert asr.get_transcript(URL, "hi")["engine"] == "local"

    monkeypatch.setattr(asr, "check_captions", lambda *a, **k: pytest.fail("captions checked on a bounded run"))
    monkeypatch.setattr(asr, "transcribe_url", lambda *a, **k: {"engine": "local"})
    assert asr.get_transcript(URL, "hi", max_seconds=90)["engine"] == "local"


# ---------------------------------------------------------------- language

def test_window_starts_are_start_middle_end():
    assert asr.window_starts(90) == [(0, 30), (30, 60), (60, 90)]
    assert asr.window_starts(20) == [(0, 20)]


def test_unanimous_confident_language_is_accepted():
    d = asr.decide_language([{"hi": 0.97, "mr": 0.02, "en": 0.01}] * 3)
    assert d["language"] == "hi" and d["needs_choice"] is False


def test_low_confidence_hindi_asks_the_owner_between_hi_and_mr():
    d = asr.decide_language([{"hi": 0.55, "mr": 0.4, "en": 0.05}] * 3)
    assert d["needs_choice"] is True and d["language"] is None and d["candidates"] == ["hi", "mr"]


def test_disagreeing_windows_never_guess():
    d = asr.decide_language([{"hi": 0.9, "mr": 0.08, "en": 0.02}, {"mr": 0.8, "hi": 0.15, "en": 0.05},
                             {"hi": 0.9, "mr": 0.08, "en": 0.02}])
    assert d["needs_choice"] is True and d["candidates"] == ["hi", "mr"]


def test_languages_outside_en_hi_mr_are_ignored():
    d = asr.decide_language([{"ur": 0.9, "hi": 0.06, "en": 0.04}] * 3)
    assert d["needs_choice"] is True  # best allowed language is hi at 0.06: too weak to accept
    assert asr.decide_language([{"en": 0.99}] * 3)["language"] == "en"


def test_marathi_text_decided_as_hindi_is_flagged_not_accepted(roots, fake_run, monkeypatch):
    tmp, _ = roots
    marathi = "हा व्हिडिओ आहे आणि त्यांनी केले आहे आहेत"
    model = FakeModel(detections=[{"hi": 0.99, "mr": 0.005, "en": 0.005}] * 3, chunks=[[SEG(0, 3, marathi)]])
    use_model(monkeypatch, model)
    res = asr.transcribe_url(URL, "auto", "local", 90, work_dir=tmp)
    assert res["language"] == "hi" and res["needs_choice"] is True and res["candidates"] == ["hi", "mr"]
    assert any("Marathi" in n for n in res["notes"])


def test_forced_language_skips_detection_and_hindi_text_is_not_flagged(roots, fake_run, monkeypatch):
    tmp, _ = roots
    model = FakeModel(chunks=[[SEG(0, 2, "यह एक बहुत अच्छी बात है और हम सब जानते हैं")]])
    use_model(monkeypatch, model)
    res = asr.transcribe_url(URL, "hi", "local", 90, work_dir=tmp)
    assert model.detect_calls == 0 and res["language_confidence"] is None
    assert res["needs_choice"] is False and res["language"] == "hi"
    assert model.transcribe_kwargs[0]["initial_prompt"] == asr.PROMPT["hi"]


def test_script_check_flags_wrong_script():
    assert asr.script_check("नमस्ते दुनिया", "hi")["ok"]
    bad = asr.script_check("hello everyone", "hi")
    assert not bad["ok"] and "Devanagari" in bad["note"]
    assert asr.script_check("hello everyone", "en")["ok"]
    assert not asr.script_check("मराठी शब्द", "en")["ok"]


# ---------------------------------------------------------------- chunks, flow, output

def test_plan_chunks():
    assert asr.plan_chunks(1300, 600) == [(0, 600), (600, 1200), (1200, 1300)]
    assert asr.plan_chunks(600, 600) == [(0, 600)]
    assert asr.plan_chunks(0) == []


def test_auto_flow_transcribes_once_with_safe_params_and_cleans_temp(roots, fake_run, monkeypatch):
    tmp, _ = roots
    calls, _ = fake_run
    model = FakeModel(detections=[{"hi": 0.97, "mr": 0.02, "en": 0.01}] * 3, chunks=[[SEG(0.0, 2.0, " नमस्ते दोस्तों ")]])
    use_model(monkeypatch, model)
    res = asr.transcribe_url(URL, "auto", "local", 90, work_dir=tmp)
    assert calls[0][0] == "yt-dlp" and "--no-cache-dir" in calls[0] and calls[1][0] == "ffmpeg"
    assert res["language"] == "hi" and res["needs_choice"] is False
    assert res["segments"] == [{"start": 0.0, "end": 2.0, "text": "नमस्ते दोस्तों"}]
    kw = model.transcribe_kwargs[0]
    assert kw["language"] == "hi" and kw["vad_filter"] is True and kw["condition_on_previous_text"] is False
    assert kw["beam_size"] == 5 and kw["initial_prompt"] == asr.PROMPT["hi"]
    assert res["seconds_audio"] == 90.0 and res["params"]["max_seconds"] == 90
    assert not list(tmp.glob("job-*"))  # temp audio deleted


def test_auto_flow_disagreement_returns_needs_choice_without_transcribing(roots, fake_run, monkeypatch):
    tmp, _ = roots
    model = FakeModel(detections=[{"hi": 0.9, "mr": 0.08, "en": 0.02}, {"mr": 0.8, "hi": 0.15, "en": 0.05},
                                  {"hi": 0.9, "mr": 0.08, "en": 0.02}])
    use_model(monkeypatch, model)
    res = asr.transcribe_url(URL, "auto", "local", 90, work_dir=tmp)
    assert res["needs_choice"] is True and res["candidates"] == ["hi", "mr"] and res["segments"] == []
    assert model.transcribe_kwargs == []


def test_long_audio_is_chunked_and_offsets_applied(roots, fake_run, monkeypatch):
    tmp, _ = roots
    _, seconds = fake_run
    seconds["src"] = 25.0
    monkeypatch.setattr(asr, "CHUNK_S", 10)
    model = FakeModel(chunks=[[SEG(0, 1, "एक")], [SEG(0, 1, "दो")], [SEG(0.5, 2, "तीन")]])
    use_model(monkeypatch, model)
    res = asr.transcribe_url(URL, "hi", "local", None, work_dir=tmp)
    assert [s["start"] for s in res["segments"]] == [0.0, 10.0, 20.5]
    assert len(model.transcribe_kwargs) == 3


def test_cuda_load_failure_falls_back_to_cpu_and_says_so(roots, fake_run, monkeypatch):
    tmp, _ = roots
    model = FakeModel(chunks=[[SEG(0, 1, "नमस्ते")]])

    def loader(name, dev, ct):
        if dev == "cuda":
            raise RuntimeError("cublas64_12.dll not found")
        return model

    monkeypatch.setattr(asr, "pick_device", lambda: ("cuda", "int8_float16"))
    monkeypatch.setattr(asr, "_load_whisper", loader)
    res = asr.transcribe_url(URL, "hi", "local", 90, work_dir=tmp)
    assert res["params"]["device"] == "cpu" and res["params"]["compute_type"] == "int8"
    assert any("fell back to cpu int8" in n for n in res["notes"])


def test_device_choice_follows_cuda_count(monkeypatch):
    monkeypatch.setattr(asr, "_cuda_dlls", lambda: None)
    fake = type(sys)("ctranslate2")
    monkeypatch.setitem(sys.modules, "ctranslate2", fake)
    fake.get_cuda_device_count = lambda: 1
    assert ORIG_PICK_DEVICE() == ("cuda", "int8_float16")
    fake.get_cuda_device_count = lambda: 0
    assert ORIG_PICK_DEVICE() == ("cpu", "int8")


# ---------------------------------------------------------------- paths and engines

def test_output_and_work_dirs_only_under_allowed_roots(roots, dwork, monkeypatch):
    tmp, studio = roots
    res = {"segments": [{"start": 0, "end": 1, "text": "नमस्ते"}], "text": "नमस्ते"}
    seg, txt = asr.save_outputs(res, studio / "stories" / "x")
    assert json.loads(seg.read_text(encoding="utf-8"))["segments"][0]["text"] == "नमस्ते"
    assert txt.read_text(encoding="utf-8").strip() == "नमस्ते"
    with pytest.raises(ValueError, match="REFUSED"):
        asr.save_outputs(res, dwork / "elsewhere")
    with pytest.raises(ValueError, match="REFUSED"):
        asr.save_outputs(res, studio / ".." / "elsewhere")
    monkeypatch.setattr(asr, "_run", lambda cmd: pytest.fail("subprocess started for a refused folder"))
    with pytest.raises(ValueError, match="REFUSED"):
        asr.transcribe_url(URL, "hi", work_dir=dwork / "C_like")


def test_refuses_bad_arguments_before_any_download(roots, monkeypatch):
    monkeypatch.setattr(asr, "_run", lambda cmd: pytest.fail("subprocess started"))
    with pytest.raises(ValueError, match="REFUSED"):
        asr.transcribe_url("https://evil.example/x.mp4", "hi")
    with pytest.raises(ValueError, match="lang"):
        asr.transcribe_url(URL, "fr")
    with pytest.raises(ValueError, match="engine"):
        asr.transcribe_url(URL, "hi", "bogus")
    with pytest.raises(ValueError, match="needs --lang"):
        asr.transcribe_url(URL, "auto", "groq")
    with pytest.raises(ValueError, match="max_seconds"):
        asr.transcribe_url(URL, "hi", max_seconds=0)


def test_groq_engine_without_key_refuses_clearly(roots, monkeypatch):
    monkeypatch.setattr(asr, "GROQ_KEY_FILE", roots[0] / "no_such_key.txt")
    monkeypatch.setattr(asr, "_run", lambda cmd: pytest.fail("subprocess started without a key"))
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        asr.transcribe_url(URL, "hi", "groq")


def test_groq_chunks_are_offset_and_under_upload_limit(roots, fake_run, monkeypatch):
    tmp, _ = roots
    calls, seconds = fake_run
    seconds["src"] = 25.0
    monkeypatch.setenv("GROQ_API_KEY", KEY)
    monkeypatch.setattr(asr, "CHUNK_S", 10)
    sent = []

    def fake_post(wav, lang, key, api_model):
        sent.append((lang, api_model, wav.stat().st_size))
        return {"segments": [{"start": 1.0, "end": 2.0, "text": "नमस्ते"}]}

    monkeypatch.setattr(asr, "_post_groq", fake_post)
    res = asr.transcribe_url(URL, "hi", "groq", None, "large-v3-turbo", work_dir=tmp)
    assert [s["start"] for s in res["segments"]] == [1.0, 11.0, 21.0]
    assert len(sent) == 3 and all(lang == "hi" and m == "whisper-large-v3-turbo" for lang, m, _ in sent)
    assert max(size for *_, size in sent) <= asr.GROQ_MAX_BYTES
    assert KEY not in json.dumps(res)


def test_groq_http_error_text_is_scrubbed(dwork, monkeypatch):
    wav = dwork / "p.wav"
    write_wav(wav, 1)

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(f"invalid key {KEY}".encode()))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError) as err:
        asr._post_groq(wav, "hi", KEY, "whisper-large-v3-turbo")
    assert KEY not in str(err.value) and "401" in str(err.value)


def test_cli_prints_summary_and_writes_side_files_without_the_key(roots, monkeypatch, capsys):
    _, studio = roots
    monkeypatch.setenv("GROQ_API_KEY", KEY)
    text = "नमस्ते दोस्तों आज हम"
    fake = {"segments": [{"start": 0.0, "end": 2.0, "text": text}], "text": text, "language": "mr",
            "language_confidence": 0.95, "engine": "local", "model": "large-v3-turbo", "needs_choice": False,
            "candidates": None, "seconds_audio": 90.0, "seconds_wall": 5.0, "asr_seconds": 3.0, "x_realtime": 30.0,
            "notes": [], "params": {"device": "cpu"}}
    monkeypatch.setattr(asr, "transcribe_url", lambda *a, **k: fake)
    code = asr.main([URL, "--lang", "mr", "--out-dir", str(studio / "out")])
    out, err = capsys.readouterr()
    assert code == 0 and KEY not in out and KEY not in err
    summary = json.loads(out)
    assert summary["language"] == "mr" and summary["text_head"] == text and summary["segments"] == 1
    assert (studio / "out" / "asr_text.txt").read_text(encoding="utf-8").strip() == text


def test_cli_error_message_never_shows_the_key(roots, fake_run, monkeypatch, capsys):
    _, studio = roots
    monkeypatch.setenv("GROQ_API_KEY", KEY)
    _, seconds = fake_run
    seconds["src"] = 10.0

    def boom(wav, lang, key, api_model):
        raise RuntimeError(f"groq HTTP 401: bad key {key}")

    monkeypatch.setattr(asr, "_post_groq", boom)
    code = asr.main([URL, "--lang", "hi", "--engine", "groq", "--max-seconds", "10", "--out-dir", str(studio / "out")])
    out, err = capsys.readouterr()
    assert code == 1 and KEY not in out and KEY not in err and "401" in err


def test_to_source_text_joins_segments_into_running_text():
    res = {"segments": [{"text": "नमस्ते  दुनिया"}, {"text": " आज\nहम"}], "text": "ignored"}
    assert asr.to_source_text(res) == "नमस्ते दुनिया आज हम"
    assert asr.to_source_text({"segments": [], "text": " पूरा  पाठ "}) == "पूरा पाठ"
