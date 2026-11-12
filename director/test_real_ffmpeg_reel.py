"""Real-ffmpeg proof of the final-reel path (no synthetic stand-ins for media).

A tiny reel-2-style fixture is built with ffmpeg itself: three H3-size clips (768x1344, 24 fps, moving testsrc2 picture, an
audible SFX bed), per-line voice WAVs for en/hi/mr, a real timeline lock from write_timeline_lock.main, the voice tracks from
build_vo_tracks.main, blocking sheets and pack rows from test_e2e_blocking_lock, and an Ableton-style 48 kHz full mix.
Then build_final_reel.main() runs for real: once without --mix, twice more without --mix (r1 then r2, r1 must survive),
and once with --mix (intake). Exports are checked with ffprobe and ffmpeg ebur128; a burned caption must change its band.

Skipped with a reason when ffmpeg/ffprobe is missing. Runs in about two minutes on the dev PC.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in (str(HERE), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import build_final_reel as bfr  # noqa: E402
import build_vo_tracks as bvt  # noqa: E402
import clip_qa  # noqa: E402
import test_e2e_blocking_lock as e2e  # noqa: E402
import timeline_lock_io as tli  # noqa: E402
import write_timeline_lock as wtl  # noqa: E402
from core.style_pack import load_core  # noqa: E402
from h3 import gate_d_audio as gd  # noqa: E402
from h3 import v4_to_h3 as v4  # noqa: E402

HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
pytestmark = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg/ffprobe not on PATH: the real-media reel proof cannot run")

REEL = "proof_reel2"
LANGS = ("en", "hi", "mr")
IDS = ("SHOT-001", "SHOT-002", "SHOT-003")
CLIP_W, CLIP_H = 768, 1344                       # the H3 clip size of rule 51 (sing8_768x1344)
FPS = 24
MIX_RATE = 48000
TEXT = {
    "SHOT-001": {"en": "Rain falls on the old step.", "hi": "पुरानी सीढ़ी पर बारिश हो रही है।", "mr": "जुन्या पायरीवर पाऊस पडतो आहे."},
    "SHOT-002": {"en": "The lamp is still lit.", "hi": "दीया अभी भी जल रहा है।", "mr": "दिवा अजून पेटलेला आहे."},
    "SHOT-003": {"en": "Morning comes to the hall.", "hi": "सुबह हॉल में आ गई है।", "mr": "सकाळ हॉलमध्ये आली आहे."},
}
for _sid in TEXT:                                # Gate D wants >= 38 words in the first 15 s: repeat each short line
    for _lg in TEXT[_sid]:
        TEXT[_sid][_lg] = " ".join([TEXT[_sid][_lg]] * 4)
LINE_SEC = {"SHOT-001": 6.0, "SHOT-002": 4.0, "SHOT-003": 7.0}   # spoken seconds per shot (en); the lock grows the cut from these
LANG_SCALE = {"en": 1.0, "hi": 1.15, "mr": 1.1}                  # hi and mr lines run longer than the English line
VOICE_RMS = 0.10                                 # about -20 dBFS speech
BUS_OVER_VOICE_DB = 18.0                         # rule 48: voice over bus must sit in 15..21.5 dB (18 dB here)


def _ff(*args):
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]


def _probe(path, entries):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", entries, "-of", "json", str(path)],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def _write_pcm16(path, arr, rate):
    """arr: float64 (samples, channels) in -1..1, written as 16-bit PCM WAV."""
    pcm = np.clip(np.round(arr * 32768.0), -32768, 32767).astype("<i2")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(arr.shape[1])
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def _speech(seconds, rate, rng):
    """Speech-like burst: band-limited noise under a 4 Hz syllable envelope, RMS VOICE_RMS."""
    n = int(round(seconds * rate))
    t = np.arange(n) / rate
    env = (0.5 + 0.5 * np.sin(2 * np.pi * 4.0 * t)) ** 2 * (0.3 + 0.7 * (t < seconds - 0.05))
    x = rng.standard_normal(n) * env
    x = x - x.mean()
    return x * (VOICE_RMS / max(float(np.sqrt(np.mean(x * x))), 1e-9))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _build_fixture(root):
    """Pack, blocking sheets, raw voice WAVs, manifest, the real lock (write_timeline_lock.main), clips, clip QA, voice tracks."""
    rng = np.random.default_rng(20261111)
    blk = root / "blocking"
    blk.mkdir(parents=True)
    for sid, sheet in e2e._sheets().items():
        # M-16 check: the longest voice (hi, LANG_SCALE 1.15) must fit writer_seconds
        sheet["writer_seconds"] = round(0.6 + LINE_SEC[sid] * max(LANG_SCALE.values()), 2)   # SHOT-001: 7.5
        (blk / f"{sid}.json").write_text(json.dumps(sheet), encoding="utf-8")
    pack = root / "pack"
    pack.mkdir()
    rows = e2e._pack_rows()
    for r in rows:
        for lang in LANGS:
            n = r["audio_and_dialogue_track"]["narration_by_lang"][lang]
            n["text"] = TEXT[r["id"]][lang]
            if r["id"] == "SHOT-003":                 # closing VO: mouth closed in every second (Gate D closing contract)
                pn = r["audio_and_dialogue_track"].setdefault("performance_notes", {})
                pn.update(text="narrator off screen", narrator_mouth_closed=True, mouth_state={str(i): "closed" for i in range(12)})
            n["time_range"] = [0.3, round(0.6 + LINE_SEC[r["id"]] * max(LANG_SCALE.values()), 3)]   # TIME-01: one range for all languages
    (pack / "shots.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    (pack / "bible.json").write_text(json.dumps(e2e.BIBLE, ensure_ascii=False), encoding="utf-8")
    raw = root / "raw"
    for lang in LANGS:
        for sid in IDS:
            seconds = LINE_SEC[sid] * LANG_SCALE[lang]
            _write_pcm16(raw / lang / f"{sid}-N.{lang}.wav", _speech(seconds, 44100, rng)[:, None], 44100)
    manifest = [{"id": f"{sid}-N.{lang}", "text": TEXT[sid][lang],
                 "text_sha256": hashlib.sha256(TEXT[sid][lang].encode("utf-8")).hexdigest()}
                for sid in IDS for lang in LANGS]
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    # D-VOICE manifests that build_final_reel reads (one per language, hashes of text and wav)
    import voice_manifest as vm
    vm_dir = root / "voice_manifest"
    vm_dir.mkdir()
    for lang in LANGS:
        vm.write_manifest(vm_dir, lang, [{"id": f"{sid}-N.{lang}", "text": TEXT[sid][lang],
                                          "wav": raw / lang / f"{sid}-N.{lang}.wav", "seconds": LINE_SEC[sid] * LANG_SCALE[lang],
                                          "speaker": "narrator"} for sid in IDS])
    lock_dir = root / "lock"
    rc = wtl.main(["--pack", str(pack), "--wav-root", str(raw), "--manifest", str(manifest_path), "--out-dir", str(lock_dir),
                   "--blocking-dir", str(blk)])
    assert rc == 0
    lock_path = lock_dir / "timeline_lock_v1.json"
    lock = tli.load_lock(str(lock_path))
    lock_rows = tli.lock_rows(lock)
    # H3 story from the same lock and pack (the story's trims must be the lock's trims)
    shots = json.loads((pack / "shots.json").read_text(encoding="utf-8"))
    conv = v4.convert_pack({"shots": shots, "bible": json.loads((pack / "bible.json").read_text(encoding="utf-8")),
                            "stage": json.loads(json.dumps(e2e.STAGE)), "asset_root": str(root)},
                           languages=list(LANGS), lock=lock, blocking_dir=str(blk))
    assert not [p for p in conv["problems"] if "lock" in p], conv["problems"]
    story_path = root / "story.json"
    conv["story"]["story_gate_checks"] = {"ending_reuses_emotional_anchor": {"pass": True}}   # Story Gate 4, as the V4 writer gives it
    story_path.write_text(json.dumps(conv["story"], ensure_ascii=False), encoding="utf-8")
    # clips: real H3-size pictures with motion and an audible SFX bed, one folder per shot with clip_qa.json
    clips = {}
    pixel = {s["id"]: int(s["pixel_frames"]) for s in lock["shots"]}
    for r in lock_rows:
        sid, pf = r["id"], pixel[r["id"]]
        folder = root / "clips" / sid
        folder.mkdir(parents=True)
        clip = folder / f"{sid}.mp4"
        dur = pf / FPS
        _ff("-f", "lavfi", "-i", f"testsrc2=size={CLIP_W}x{CLIP_H}:rate={FPS}:duration={dur}",
            "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={dur}",
            "-filter:a", "volume=0.07", "-map", "0:v", "-map", "1:a", "-frames:v", str(pf),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", str(clip))
        clips[sid] = str(clip)
        sheet = json.loads((blk / f"{sid}.json").read_text(encoding="utf-8"))
        sfx_keep, bed_db = clip_qa.audio_analysis(str(clip), sheet)
        doc = {"clip_sha256": _sha(clip), "window": [r["trim_in_frame"], r["trim_out_frame"]],
               "results": {"synthetic_motion_fixture": True}, "verdict": {"pass": True, "reasons": []},
               "sfx_keep": sfx_keep, "bed_db": bed_db, "owner_accept": None}
        (folder / "clip_qa.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    clips_json = root / "clips.json"
    clips_json.write_text(json.dumps(clips), encoding="utf-8")
    # voice tracks (build_vo_tracks.main writes the per-language WAVs and vo_tracks_report.json)
    vo = root / "vo"
    assert bvt.main(["--pack", str(pack), "--raw", str(raw), "--out", str(vo), "--lock", str(lock_path)]) == 0
    return SimpleNamespace(root=root, pack=pack, lock_path=lock_path, lock_rows=lock_rows, story=story_path, clips=clips_json,
                           vo=vo, manifest=manifest_path, raw=raw, rng=rng)


def _voice_over_bus_mix(fx, out_wav):
    """Ableton-style full mix (48 kHz stereo): the voice-only render placed on the lock clock plus a music/SFX bus at -18 dB.
    Returns the voice-only render path too (same session, same length)."""
    rows = fx.lock_rows
    total_sec = sum(float(r["editorial_duration_sec"]) for r in rows)
    need = int(round(total_sec * FPS)) * (MIX_RATE // FPS)
    rng = np.random.default_rng(7)
    out_paths = {}
    for lang in LANGS:
        voice = np.zeros((need + MIX_RATE, 2))
        t = 0.0
        for r in rows:
            off = int(round(t * MIX_RATE))
            clip_raw = fx.raw / lang / f"{r['id']}-N.{lang}.wav"
            with wave.open(str(clip_raw), "rb") as w:
                rate = w.getframerate()
                line = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64) / 32768.0
            line = np.interp(np.arange(0, len(line), rate / MIX_RATE), np.arange(len(line)), line)
            start = off + int(round(0.5 * MIX_RATE))           # the line starts at 0.5 s in the shot (pack time_range)
            voice[start:start + len(line), :] += line[:, None]
            t += float(r["editorial_duration_sec"])
        bus = rng.standard_normal((need + MIX_RATE, 2))
        bus *= (VOICE_RMS / 10 ** (BUS_OVER_VOICE_DB / 20)) / float(np.sqrt(np.mean(bus * bus)))
        vpath = fx.root / f"mix_voice_{lang}.wav"
        mpath = fx.root / f"mix_{lang}.wav"
        _write_pcm16(vpath, voice, MIX_RATE)
        _write_pcm16(mpath, voice + bus, MIX_RATE)
        out_paths[lang] = (str(mpath), str(vpath))
    return out_paths


def _ebur128(path):
    """Integrated loudness and true peak from ffmpeg's ebur128 summary (independent of build_final_reel)."""
    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-filter_complex", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    text = r.stderr
    summary = text[text.rfind("Summary:"):]
    integrated = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summary).group(1))
    tp = re.search(r"True peak:\s+(?:.*\n)?\s*Peak:\s+(-?[\d.]+) dBFS", summary)
    if tp is None:
        tp = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary[summary.find("True peak"):])
    return integrated, float(tp.group(1))


def _frame_rgb(path, t, vf=None):
    args = ["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path)]
    if vf:
        args += ["-vf", vf]
    args += ["-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    r = subprocess.run(args, capture_output=True, check=True)
    w, h = 1080, 1920
    return np.frombuffer(r.stdout, dtype=np.uint8).reshape(h, w, 3).astype(np.int16)


def _first_long_cue(ass_path):
    """Midpoint (s) and text of the longest Dialogue event in an ass file."""
    best = None
    for line in Path(ass_path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        h, m, s = parts[1].split(":")
        t0 = int(h) * 3600 + int(m) * 60 + float(s)
        h, m, s = parts[2].split(":")
        t1 = int(h) * 3600 + int(m) * 60 + float(s)
        if best is None or t1 - t0 > best[1] - best[0]:
            best = (t0, t1, parts[9])
    return (best[0] + best[1]) / 2, best[2]


def _run_final(fx, out, mixes=None):
    args = ["--pack", str(fx.pack), "--story", str(fx.story), "--clips", str(fx.clips), "--vo", str(fx.vo),
            "--lock", str(fx.lock_path), "--out", str(out), "--reel", REEL, "--langs", ",".join(LANGS),
            "--fonts", str(ROOT / "styles" / "fonts"), "--manifest", str(fx.root / "voice_manifest" / "voice_manifest.{lang}.json"), "--story-id", "proof_story",
            "--render-version", "proof"]
    if mixes:
        for lang, (mpath, _vpath) in mixes.items():
            args += ["--mix", f"{lang}={mpath}"]
        for lang, (_mpath, vpath) in mixes.items():
            args += ["--mix-voice", f"{lang}={vpath}"]
    return bfr.main(args)


@pytest.fixture(scope="module")
def proof(tmp_path_factory):
    root = tmp_path_factory.mktemp("real_reel")
    fx = _build_fixture(root)
    out = root / "out"
    rc1 = _run_final(fx, out)
    export_r1 = {lg: out / "export" / f"{REEL}_{lg}_r1.mp4" for lg in LANGS}
    sha_r1 = {lg: _sha(p) for lg, p in export_r1.items() if p.exists()}
    rc2 = _run_final(fx, out)
    mixes = _voice_over_bus_mix(fx, root)
    out_mix = root / "out_mix"
    rc3 = _run_final(fx, out_mix, mixes)
    return SimpleNamespace(fx=fx, out=out, out_mix=out_mix, rc=(rc1, rc2, rc3), sha_r1=sha_r1, export_r1=export_r1,
                           mixes=mixes)


# ---------------------------------------------------------------- the proof

def test_fixture_is_real_media_at_h3_size(proof):
    for r in proof.fx.lock_rows:
        clip = Path(json.loads(proof.fx.clips.read_text(encoding="utf-8"))[r["id"]])
        info = _probe(clip, "stream=codec_type,width,height,nb_frames,r_frame_rate:format=duration")
        v = next(s for s in info["streams"] if s["codec_type"] == "video")
        assert (v["width"], v["height"]) == (CLIP_W, CLIP_H)
        assert v["r_frame_rate"] == f"{FPS}/1"
        assert any(s["codec_type"] == "audio" for s in info["streams"])


def test_no_mix_run_exits_clean_and_exports_three_languages(proof):
    assert proof.rc[0] == 0, "build_final_reel.main() must succeed without --mix"
    for lg in LANGS:
        assert proof.export_r1[lg].is_file(), proof.export_r1[lg]
    report = json.loads((proof.out / f"{REEL}_build_report.json").read_text(encoding="utf-8"))
    for lg in LANGS:
        assert not report["languages"][lg]["blocking_errors"], report["languages"][lg]["blocking_errors"]


def test_export_duration_size_and_audio(proof):
    total_frames = sum(int(r["editorial_duration_sec"] * FPS + 0.5) for r in proof.fx.lock_rows)
    for lg in LANGS:
        info = _probe(proof.export_r1[lg], "stream=codec_type,width,height,codec_name:format=duration")
        v = next(s for s in info["streams"] if s["codec_type"] == "video")
        assert (v["width"], v["height"]) == (1080, 1920)
        assert any(s["codec_type"] == "audio" for s in info["streams"]), lg
        assert abs(float(info["format"]["duration"]) - total_frames / FPS) <= 1 / FPS + 0.02, (lg, info["format"]["duration"])


def test_loudness_is_core_target_and_true_peak_is_below_minus_one(proof):
    target = load_core()["delivery"]["audio"]
    for lg in LANGS:
        integrated, tp = _ebur128(proof.export_r1[lg])
        assert abs(integrated - target["lufs"]) <= target["tolerance_lu"], (lg, integrated)
        assert tp <= target["true_peak_db"] + 1e-6, (lg, tp)


def test_default_export_is_clean_and_burned_copy_has_captions(proof):
    """G15: the default export has no caption band; the optional burned copy (from the clean export) does."""
    ass = proof.out / "captions" / f"{REEL}_en.ass"
    t, text = _first_long_cue(ass)
    vf = bfr.DELIVERY_VF
    clean = _frame_rgb(proof.export_r1["en"], t)
    without = _frame_rgb(proof.out / f"{REEL}_video.mp4", t, vf)
    band = (slice(1150, 1320), slice(90, 990))
    ctrl = (slice(300, 520), slice(90, 990))
    d_clean = float(np.abs(clean[band] - without[band]).mean())
    d_ctrl = float(np.abs(clean[ctrl] - without[ctrl]).mean())
    print("clean band", d_clean, "control", d_ctrl)
    assert d_clean < 2 * d_ctrl + 2.0, (text, d_clean, d_ctrl)           # codec noise only, no caption band
    burned = proof.out / "export" / "burned_check.mp4"
    subprocess.run(bfr.burned_from_clean_argv(proof.export_r1["en"], burned, ass, str(ROOT / "styles" / "fonts")),
                   check=True, cwd=str(ROOT))
    with_caps = _frame_rgb(burned, t)
    d_burn = float(np.abs(with_caps[band] - clean[band]).mean())
    print("burned band", d_burn)
    assert d_burn > 4.0 and d_burn > 3 * d_clean, (text, d_burn, d_clean)
    assert bfr.audio_sha256(burned) == bfr.audio_sha256(proof.export_r1["en"])
    burned.unlink()


def test_second_run_makes_r2_and_never_overwrites_r1(proof):
    assert proof.rc[1] == 0
    for lg in LANGS:
        r2 = proof.out / "export" / f"{REEL}_{lg}_r2.mp4"
        assert r2.is_file(), r2
        assert _sha(proof.export_r1[lg]) == proof.sha_r1[lg], "r1 was overwritten"


def test_mix_run_uses_intake_and_matches_the_lock_length(proof):
    assert proof.rc[2] == 0
    rep = json.loads((proof.out_mix / f"{REEL}_build_report.json").read_text(encoding="utf-8"))
    total_frames = round(sum(float(r["editorial_duration_sec"]) for r in proof.fx.lock_rows) * FPS)
    for lg in LANGS:
        mix = rep["languages"][lg]["mix"]
        assert mix["samples"] == total_frames * (MIX_RATE // FPS)
        assert BUS_OVER_VOICE_DB - 3 <= mix["median_db"] <= 21.5, mix
        export = Path(rep["languages"][lg]["export"])
        assert export.name == f"{REEL}_{lg}_r1.mp4"
        info = _probe(export, "format=duration")
        assert abs(float(info["format"]["duration"]) - total_frames / FPS) <= 1 / FPS + 0.02
        integrated, tp = _ebur128(export)
        target = load_core()["delivery"]["audio"]
        assert abs(integrated - target["lufs"]) <= target["tolerance_lu"], (lg, integrated)
        assert tp <= target["true_peak_db"] + 1e-6, (lg, tp)


def test_gate_d_plans_every_language_on_the_fixture(proof):
    rows = bfr.lock_rows_for_pack(str(proof.fx.lock_path), proof.fx.pack)
    res = gd.plan_language_outputs(REEL, list(LANGS), str(proof.fx.vo), None, shots=rows,
                                   video_path=str(proof.out / f"{REEL}_video.mp4"), video_has_audio=True, burn_captions=True,
                                   captions_dir=str(proof.out / "captions"),
                                   export_dir=str(proof.out / "export"), fonts_dir=str(ROOT / "styles" / "fonts"),
                                   voice_engines={lg: "elevenlabs" for lg in LANGS},
                                   story_gate_checks={"ending_reuses_emotional_anchor": {"pass": True}})
    for lg in LANGS:
        assert res["reports"][lg]["ok"], res["reports"][lg]["errors"]
        assert res["languages"][lg]["mux_argv"], lg
        # the render_controller verify step: Gate D's own loudness parser on the real export
        text = subprocess.run(gd.build_loudness_verify_argv(str(proof.export_r1[lg])), capture_output=True, text=True).stderr
        assert gd.check_post_aac_loudness(text)["ok"], lg
