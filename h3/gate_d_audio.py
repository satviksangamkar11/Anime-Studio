"""Gate D: audio mix, VO fit, BGM provenance and presence, post-AAC loudness, and .ass captions.

Pure builders and checks over supplied numbers. This module never runs ffmpeg, never calls ElevenLabs or any
model, and never downloads anything. VO .wav files, the BGM file and the narration text are owner inputs.

Reports match the other validators: {"ok", "errors": [{"code", "where", "message"}], "warnings": [...], "stats": {...}}.

Name note: the spec calls the presence floor `test_music_presence`. It is `check_music_presence` here, because pytest
would collect a `test_*` function imported into a test module.
"""
from __future__ import annotations

import json
import math
import re
import statistics
import wave
from pathlib import Path

from h3.voice_engine import H3_SPEECH_LANGS, VOICE_ENGINES, engine_for
from h3.shot_table_spec import (CAPTION, FPS, HOOK_NARRATION, LOUDNESS, STRONG_HOOKS, TAIL_SILENCE_MAX_SEC,
                                VO_FIT_MARGIN_SEC)

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
MASTER_LABEL = "master"
MIX_FORMAT = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
MIX_RATE = 48000
FADE_SEC = 0.005                                  # 5 ms anti-pop fade on every trimmed H3 SFX clip
SFX_DUCK = "threshold=0.03:ratio=4:attack=10:release=350"
BGM_DUCK = "threshold=0.03:ratio=6:attack=15:release=500"
AAC_BITRATE = "192k"
OPENING_HOOK_SEC = 2.0
# ponytail: BGM presence numbers come from the owner's master prompt. The p95 floor (-50 dB) is our pick:
# "non-silent" needs a number, so adjust it here if the owner gives one.
BGM_PRESENCE = {"median_under_voice_db": (15.0, 21.5), "p95_floor_db": -50.0, "speech_gate_db": -40.0}
BGM_REQUIRED = ("track_id", "path", "license_type", "bpm", "lufs")
CAPTION_FONT_FAMILY = "Noto Sans Devanagari"     # family name of NotoSansDevanagari-Bold.ttf
LATIN_FONT_FILE = "NotoSans-Bold.ttf"            # OFL, for English (lang "en") captions
LATIN_FONT_FAMILY = "Noto Sans"
# Per-language caption font. hi and mr are Devanagari (CAPTION["font"]); en is Latin. Limits and margins are shared.
CAPTION_FONTS = {
    "hi": {"file": CAPTION["font"], "family": CAPTION_FONT_FAMILY},
    "mr": {"file": CAPTION["font"], "family": CAPTION_FONT_FAMILY},
    "en": {"file": LATIN_FONT_FILE, "family": LATIN_FONT_FAMILY},
}
CAPTION_FONT_SIZE = 84
CAPTION_LINE_PX = 110                             # line height for the placement estimate
CAPTION_CHAR_PX = 46                              # average glyph advance for the placement estimate
CAPTION_MOVE_STEP_PX = 40                         # how far a card is raised when it covers a face

_RANGE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*s?\s*$")
_EBUR_I = re.compile(r"\bI:\s*(-?\d+(?:\.\d+)?)\s*LUFS")
_EBUR_TP = re.compile(r"True peak:\s*Peak:\s*(-?\d+(?:\.\d+)?)\s*dB")
_LN_I = re.compile(r"Input Integrated:\s*(-?\d+(?:\.\d+)?)\s*LUFS")
_LN_TP = re.compile(r"Input True Peak:\s*(-?\d+(?:\.\d+)?)\s*dB")
_LN_JSON_I = re.compile(r'"input_i"\s*:\s*"(-?\d+(?:\.\d+)?)"')
_LN_JSON_TP = re.compile(r'"input_tp"\s*:\s*"(-?\d+(?:\.\d+)?)"')


def _report(errors, warnings=(), stats=None):
    return {"ok": not errors, "errors": list(errors), "warnings": list(warnings), "stats": dict(stats or {})}


def _err(code, where, message):
    return {"code": code, "where": where, "message": message}


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _overlap(s, e, lo, hi):
    return max(0.0, min(e, hi) - max(s, lo))


def parse_time_range(value):
    """[s, e] list, or a "1.2-1.6s" / "1.2–1.6s" string -> (s, e). ValueError when malformed or not e > s."""
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(_is_num(v) for v in value):
        s, e = float(value[0]), float(value[1])
    elif isinstance(value, str) and _RANGE_RE.match(value):
        m = _RANGE_RE.match(value)
        s, e = float(m.group(1)), float(m.group(2))
    else:
        raise ValueError(f"bad time_range {value!r}")
    if e <= s:
        raise ValueError(f"time_range must have end > start: {value!r}")
    return s, e


def _speech_items(trk, t0=0.0):
    """Narration and dialogue of one shot as (start, end, word_count) on the reel clock (t0 = shot start)."""
    items = []
    narr = trk.get("narration")
    if narr and not isinstance(narr, dict):
        raise ValueError(f"narration must be an object with text and time_range, got {type(narr).__name__}")
    if narr and str(narr.get("text", "")).strip():
        s, e = parse_time_range(narr["time_range"])
        items.append((s + t0, e + t0, len(narr["text"].split())))
    for d in trk.get("dialogue") or []:
        if d.get("time_range") and str(d.get("text", "")).strip():
            s, e = parse_time_range(d["time_range"])
            items.append((s + t0, e + t0, len(d["text"].split())))
    return items


# ---------------------------------------------------------------- opening hook, narration density, closing shot

def check_opening_hook(opening_shot):
    """The 0-2 s hook must sit in the voice track AND in the SFX track of the opening shot (shot-relative seconds)."""
    where = f"shot {opening_shot.get('id')}"
    trk = opening_shot.get("audio_and_dialogue_track") or {}
    errors = []
    if not any(_overlap(s, e, 0.0, OPENING_HOOK_SEC) > 0 for s, e, _ in _speech_items(trk)):
        errors.append(_err("OPENING_HOOK_NO_VOICE", where, f"no narration or dialogue inside 0-{OPENING_HOOK_SEC:g}s"))
    sfx_hit = any(_overlap(*parse_time_range(c["time_range"]), 0.0, OPENING_HOOK_SEC) > 0
                  for c in trk.get("sfx_cues") or [])
    if not sfx_hit:
        errors.append(_err("OPENING_HOOK_NO_SFX", where, f"no sfx_cues inside 0-{OPENING_HOOK_SEC:g}s"))
    return _report(errors)


def check_narration_density(shots, *, narration_driven=True):
    """Reel-level check over shots in order (each: editorial_duration_sec, audio_and_dialogue_track).

    Coverage and word count use the first HOOK_NARRATION window. Every dead-air gap between two speech
    intervals above max_dead_air_sec is flagged, anywhere in the reel (a shot junction is not required)."""
    if not narration_driven:
        return _report([], warnings=["narration density skipped: reel is not narration-driven"])
    win = HOOK_NARRATION["window_sec"]
    items, t0 = [], 0.0
    for shot in shots:
        items += _speech_items(shot.get("audio_and_dialogue_track") or {}, t0)
        t0 += _editorial_len(shot)
    words = sum(n * _overlap(s, e, 0.0, win) / (e - s) for s, e, n in items)
    merged = []
    for s, e in sorted((s, e) for s, e, _ in items):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    coverage = sum(_overlap(s, e, 0.0, win) for s, e in merged) / win
    errors = []
    if coverage < HOOK_NARRATION["min_coverage"] - 1e-9:
        errors.append(_err("NARRATION_COVERAGE_LOW", "reel", f"speech covers {coverage:.0%} of the first {win:g}s, "
                                                             f"need {HOOK_NARRATION['min_coverage']:.0%}"))
    if words < HOOK_NARRATION["min_words"] - 1e-6:
        errors.append(_err("NARRATION_WORDS_LOW", "reel", f"{words:.1f} words in the first {win:g}s, "
                                                          f"need {HOOK_NARRATION['min_words']}"))
    pauses = []
    for (_, a_end), (b_start, _) in zip(merged, merged[1:]):
        if b_start - a_end > HOOK_NARRATION["max_dead_air_sec"] + 1e-9:
            pauses.append((a_end, b_start))
            errors.append(_err("DEAD_AIR_PAUSE", f"{a_end:.2f}-{b_start:.2f}s",
                               f"dead air {b_start - a_end:.2f}s > {HOOK_NARRATION['max_dead_air_sec']}s"))
    stats = {"coverage_window": round(coverage, 3), "words_window": round(words, 1), "dead_air_pauses": len(pauses)}
    return _report(errors, stats=stats)


def check_closing_shot(closing_shot, *, story_gate_checks=None, vo_wav_path=None, payoff_end_sec=None):
    """Closing contract: strong hook, emotional-anchor payoff (Story Gate 4), and an optional question/CTA VO.

    With a VO: it starts after payoff_end_sec, the mouth is locked closed over its seconds, it fits the shot
    (VO_OVERFLOW_ERROR), and residual silence after it is <= TAIL_SILENCE_MAX_SEC. Times are shot-relative."""
    where = f"shot {closing_shot.get('id')}"
    errors = []
    if not closing_shot.get("is_closing_hook"):
        errors.append(_err("CLOSING_NOT_FLAGGED", where, "is_closing_hook must be true on the closing shot"))
    if closing_shot.get("hook_type") not in STRONG_HOOKS:
        errors.append(_err("CLOSING_WEAK_HOOK", where, f"hook_type must be one of {STRONG_HOOKS}"))
    gate = (story_gate_checks or {}).get("ending_reuses_emotional_anchor") or {}
    if gate.get("pass") is not True:
        errors.append(_err("CLOSING_NO_ANCHOR_PAYOFF", where, "ending_reuses_emotional_anchor must pass before the VO"))
    if vo_wav_path is None:
        return _report(errors)
    trk = closing_shot.get("audio_and_dialogue_track") or {}
    narr = trk.get("narration") or {}
    if not str(narr.get("text", "")).strip():
        errors.append(_err("CLOSING_VO_NO_TEXT", where, "a closing VO was given but narration text is empty"))
        return _report(errors)
    s, e = parse_time_range(narr["time_range"])
    warnings = []
    if payoff_end_sec is None:
        warnings.append("payoff end not known, VO-after-payoff not verified")
    elif s < payoff_end_sec:
        errors.append(_err("CLOSING_VO_BEFORE_PAYOFF", where, f"VO starts at {s:.2f}s, before the payoff ends at "
                                                             f"{payoff_end_sec}s"))
    pn = trk.get("performance_notes") or {}
    mouth = pn.get("mouth_state") or {}
    open_secs = [sec for sec in range(int(math.floor(s)), int(math.ceil(e)))
                 if mouth.get(str(sec)) != "closed"]
    if pn.get("narrator_mouth_closed") is not True or open_secs:
        errors.append(_err("CLOSING_MOUTH_OPEN", where, f"mouth must be closed while the VO plays "
                                                        f"(seconds not closed: {open_secs})"))
    editorial = _editorial_len(closing_shot)
    fit = vo_fit_check([{"shot_id": where, "wav_path": vo_wav_path, "editorial_duration_sec": editorial}])
    errors += fit["errors"]
    stats = {"vo": fit["stats"].get(where)}
    if fit["ok"]:
        residual = editorial - fit["stats"][where]["vo_sec"]
        stats["vo"]["residual_sec"] = round(residual, 3)
        if residual > TAIL_SILENCE_MAX_SEC + 1e-9:
            errors.append(_err("CLOSING_TAIL_SILENCE", where, f"tail silence {residual:.2f}s > {TAIL_SILENCE_MAX_SEC}s"))
    return _report(errors, warnings=warnings, stats=stats)


# ---------------------------------------------------------------- VO fit and BGM provenance

def wav_duration_sec(path):
    """Duration of a PCM .wav file from its header (stdlib wave only)."""
    with wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        if rate <= 0:
            raise wave.Error(f"wav has no sample rate: {path}")
        return w.getnframes() / rate


def vo_fit_check(items):
    """items: [{"shot_id", "wav_path", "editorial_duration_sec"}]. VO_OVERFLOW_ERROR when the VO is longer than
    editorial - VO_FIT_MARGIN_SEC. VO_UNREADABLE when the file is not a readable wav."""
    errors, stats = [], {}
    for it in items:
        sid, ed = it["shot_id"], float(it["editorial_duration_sec"])
        try:
            vo = wav_duration_sec(it["wav_path"])
        except (wave.Error, EOFError, OSError) as exc:
            errors.append(_err("VO_UNREADABLE", sid, f"cannot read VO wav: {exc}"))
            continue
        stats[sid] = {"vo_sec": round(vo, 3), "editorial_sec": round(ed, 3)}
        if vo > ed - VO_FIT_MARGIN_SEC + 1e-6:
            errors.append(_err("VO_OVERFLOW_ERROR", sid, f"VO {vo:.2f}s exceeds editorial {ed:.2f}s minus "
                                                        f"{VO_FIT_MARGIN_SEC:.2f}s; re-time or rewrite shorter"))
    return _report(errors, stats=stats)


def validate_bgm_manifest(doc):
    """audio/bgm_manifest.json: {"tracks": [{track_id, path, license_type, bpm, lufs}, ...]}."""
    if not isinstance(doc, dict) or not isinstance(doc.get("tracks"), list):
        return _report([_err("BGM_MANIFEST_SHAPE", "bgm_manifest", 'expected {"tracks": [...]}')])
    tracks, errors, ids = doc["tracks"], [], set()
    # Q-R4-13: an empty track list means "no BGM" (owner: BGM off); it is valid, matching _bgm_track
    for i, t in enumerate(tracks):
        where = f"tracks[{i}]"
        if not isinstance(t, dict):
            errors.append(_err("BGM_FIELD_MISSING", where, "track must be an object"))
            continue
        missing = [k for k in BGM_REQUIRED if t.get(k) in (None, "")]
        if missing:
            errors.append(_err("BGM_FIELD_MISSING", where, f"missing {', '.join(missing)}"))
        if "track_id" not in missing:
            tid = str(t["track_id"])
            if tid in ids:
                errors.append(_err("BGM_DUPLICATE_ID", where, f"track_id {tid!r} repeated"))
            ids.add(tid)
        if "bpm" not in missing and not (_is_num(t["bpm"]) and t["bpm"] > 0):
            errors.append(_err("BGM_FIELD_INVALID", where, "bpm must be a positive number"))
        if "lufs" not in missing and not _is_num(t["lufs"]):
            errors.append(_err("BGM_FIELD_INVALID", where, "lufs must be a finite number"))
    return _report(errors, stats={"tracks": len(tracks)})


def read_bgm_manifest(path):
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _report([_err("BGM_MANIFEST_UNREADABLE", str(path), str(exc))])
    return validate_bgm_manifest(doc)


def _is_db(x):
    """True for a finite real number (not bool, not str)."""
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def check_music_presence(voice_db, bgm_db, *, speech_gate_db=BGM_PRESENCE["speech_gate_db"],
                         median_band=BGM_PRESENCE["median_under_voice_db"],
                         p95_floor_db=BGM_PRESENCE["p95_floor_db"]):
    """BGM never vanishes under speech. voice_db and bgm_db are equal-length per-window levels in dB.

    Speech windows are voice_db >= speech_gate_db. Their median (voice - bgm) must sit in median_band. The p95
    floor (the level exceeded in 95 % of windows, i.e. the 5th percentile) of bgm_db must exceed p95_floor_db."""
    if len(voice_db) != len(bgm_db) or not voice_db:
        return _report([_err("BGM_PRESENCE_BAD_INPUT", "levels", "voice and bgm arrays must be equal and non-empty")])
    diffs = [v - b for v, b in zip(voice_db, bgm_db)
             if _is_db(v) and _is_db(b) and v >= speech_gate_db]
    if not diffs:
        return _report([_err("BGM_PRESENCE_NO_SPEECH", "levels", "no speech windows: presence cannot be verified")])
    median = statistics.median(diffs)
    lo, hi = median_band
    errors = []
    if not lo <= median <= hi:
        errors.append(_err("BGM_MEDIAN_OUT_OF_BAND", "levels",
                           f"median BGM is {median:.1f} dB under voice, need {lo}-{hi} dB"))
    srt = sorted(b for b in bgm_db if _is_db(b))
    if not srt:
        errors.append(_err("BGM_SILENT_FLOOR", "levels", "no finite BGM level: floor cannot be verified"))
        return _report(errors, stats={"median_under_voice_db": round(median, 2), "p95_floor_db": None,
                                      "speech_windows": len(diffs)})
    floor = srt[int(0.05 * (len(srt) - 1))]
    if not floor > p95_floor_db:
        errors.append(_err("BGM_SILENT_FLOOR", "levels", f"BGM p95 floor {floor:.1f} dB is not above {p95_floor_db} dB"))
    return _report(errors, stats={"median_under_voice_db": round(median, 2), "p95_floor_db": floor,
                                  "speech_windows": len(diffs)})


# ---------------------------------------------------------------- ffmpeg filtergraph, mux and loudness

def build_mix_filter(sfx_clips, vo_input, bgm_input, total_reel_duration_sec):
    """Exact 3-stem filtergraph text ending in [master]. Input numbers are ffmpeg input indexes.

    sfx_clips: [{"input_index", "trim_in_sec", "trim_out_sec"}] in reel order (concatenated into [h3_sfx_full]).
    vo_input=None (English H3 voice): the H3 clip's own audio carries the speech AND the SFX, so the mix is the
    SFX stem alone with the optional BGM ducked under it (no VO stem, no SFX ducking against a VO).
    Never runs ffmpeg. Raises ValueError when the SFX stem is longer than the reel (atrim would cut its tail)."""
    total = float(total_reel_duration_sec)
    if not sfx_clips or total <= 0:
        raise ValueError("need at least one SFX clip and a positive total_reel_duration_sec")
    chains, labels, sfx_sum = [], [], 0.0
    for n, c in enumerate(sfx_clips):
        dur = c["trim_out_sec"] - c["trim_in_sec"]
        if dur <= 0:
            raise ValueError(f"SFX clip {n} has no duration")
        sfx_sum += dur
        labels.append(f"sfx{n}")
        chains.append(f"{_src(c['input_index'])}atrim=start={c['trim_in_sec']:.3f}:end={c['trim_out_sec']:.3f},"
                      f"asetpts=PTS-STARTPTS,{MIX_FORMAT},afade=t=in:st=0:d={FADE_SEC:.3f},"
                      f"afade=t=out:st={dur - FADE_SEC:.3f}:d={FADE_SEC:.3f}[{labels[-1]}]")
    if sfx_sum > total + 1e-3:
        raise ValueError(f"SFX stem {sfx_sum:.3f}s is longer than the reel {total:.3f}s; atrim would cut it")
    chains.append("".join(f"[{l}]" for l in labels) + f"concat=n={len(labels)}:v=0:a=1[h3_sfx_full]")
    lt = LOUDNESS
    loud = f"loudnorm=I={lt['target_lufs']:g}:TP={lt['loudnorm_tp']:g}:LRA={lt['lra']:g}[{MASTER_LABEL}]"
    if vo_input is None:  # UNVERIFIED in a real render: one stem from the H3 clip's audio (speech + SFX)
        if bgm_input is None:
            chains.append(f"[h3_sfx_full]atrim=0:{total:.3f},{loud}")
        else:
            chains.append("[h3_sfx_full]asplit=2[sfx_out][sc_bgm]")
            chains.append(f"{_src(bgm_input)}{MIX_FORMAT}[bgm]")
            chains.append(f"[bgm][sc_bgm]sidechaincompress={BGM_DUCK}[bgm_ducked]")
            chains.append(f"[sfx_out][bgm_ducked]amix=inputs=2:duration=longest:normalize=0,atrim=0:{total:.3f},{loud}")
        return ";".join(chains)
    chains.append(f"{_src(vo_input)}{MIX_FORMAT},apad=whole_dur={total:.3f}[elevenlabs_vo]")
    with_bgm = bgm_input is not None                  # owner default: no BGM; with it, ONE continuous track
    chains.append("[elevenlabs_vo]asplit=3[vo_out][sc_sfx][sc_bgm]" if with_bgm else "[elevenlabs_vo]asplit=2[vo_out][sc_sfx]")
    chains.append(f"[h3_sfx_full][sc_sfx]sidechaincompress={SFX_DUCK}[sfx_ducked]")
    if with_bgm:
        chains.append(f"{_src(bgm_input)}{MIX_FORMAT}[bgm]")
        chains.append(f"[bgm][sc_bgm]sidechaincompress={BGM_DUCK}[bgm_ducked]")
    lt = LOUDNESS
    stems = "[sfx_ducked][vo_out][bgm_ducked]" if with_bgm else "[sfx_ducked][vo_out]"
    chains.append(f"{stems}amix=inputs={3 if with_bgm else 2}:duration=longest:normalize=0,atrim=0:{total:.3f},"
                  f"loudnorm=I={lt['target_lufs']:g}:TP={lt['loudnorm_tp']:g}:LRA={lt['lra']:g}[{MASTER_LABEL}]")
    return ";".join(chains)


def build_final_mux_argv(video_path, audio_paths, mix_filter, out_mp4, *, burn_captions=True, ass_path=None,
                         fonts_dir=None):
    """argv for the final mp4 (no execution). Input 0 is the video; audio_paths are inputs 1..N, the numbering
    build_mix_filter expects.

    burn_captions=True burns the .ass captions in with the bundled font and re-encodes the video (libx264, crf 14,
    preset slow, yuv420p, 24 fps). burn_captions=False copies the video (draft and tests only). The audio is always
    AAC. No -shortest, so the audio tail is never cut. Run ffmpeg from the repo root so relative caption and font
    paths resolve."""
    if f"[{MASTER_LABEL}]" not in mix_filter:
        raise ValueError(f"mix filter must end in [{MASTER_LABEL}]")
    argv = ["ffmpeg", "-y", "-i", str(video_path)]
    for p in audio_paths:
        argv += ["-i", str(p)]
    if burn_captions:
        if not ass_path:
            raise ValueError("burn_captions=True needs ass_path, the .ass file to burn in")
        graph = f"{mix_filter};[0:v]{build_subtitles_filter(ass_path, fonts_dir)}[vsub]"
        video_map = "[vsub]"
        video_args = ["-c:v", "libx264", "-crf", "14", "-preset", "slow", "-pix_fmt", "yuv420p", "-r", str(FPS)]
    else:
        graph, video_map, video_args = mix_filter, "0:v:0", ["-c:v", "copy"]
    argv += ["-filter_complex", graph, "-map", video_map, "-map", f"[{MASTER_LABEL}]", *video_args,
             "-c:a", "aac", "-b:a", AAC_BITRATE, "-ar", str(MIX_RATE), "-ac", "2",
             "-movflags", "+faststart", str(out_mp4)]
    return argv


def build_loudness_verify_argv(mp4_path):
    """argv that measures the AAC-encoded mp4 with ebur128 (integrated loudness and true peak). Not executed here."""
    return ["ffmpeg", "-hide_banner", "-nostats", "-i", str(mp4_path), "-af", "ebur128=peak=true", "-f", "null", "-"]


def parse_loudness_text(text):
    """Integrated LUFS and true peak (dBTP) from ffmpeg ebur128 or loudnorm output. None for a value not found.
    The last match wins, so the summary block beats any per-frame lines."""
    def last(patterns):
        for p in patterns:
            found = p.findall(text)
            if found:
                return float(found[-1])
        return None
    return {"integrated_lufs": last([_EBUR_I, _LN_I, _LN_JSON_I]), "true_peak_dbtp": last([_EBUR_TP, _LN_TP, _LN_JSON_TP])}


def check_post_aac_loudness(ffmpeg_text):
    """Gate D final audio: integrated -14 +-0.5 LUFS and true peak <= -1.5 dBTP, measured on the AAC mp4."""
    m = parse_loudness_text(ffmpeg_text)
    errors = []
    if m["integrated_lufs"] is None or m["true_peak_dbtp"] is None:
        errors.append(_err("LOUDNESS_UNREADABLE", "ffmpeg output", f"missing measurement: {m}"))
    else:
        if abs(m["integrated_lufs"] - LOUDNESS["target_lufs"]) > LOUDNESS["tolerance"] + 1e-9:
            errors.append(_err("LOUDNESS_OUT_OF_TARGET", "aac_mp4",
                               f"integrated {m['integrated_lufs']} LUFS, need {LOUDNESS['target_lufs']} "
                               f"+-{LOUDNESS['tolerance']}"))
        if m["true_peak_dbtp"] > LOUDNESS["tp_ceiling_dbtp"] + 1e-9:
            errors.append(_err("TRUE_PEAK_OVER", "aac_mp4",
                               f"true peak {m['true_peak_dbtp']} dBTP, must be <= {LOUDNESS['tp_ceiling_dbtp']}"))
    return _report(errors, stats=m)


# ---------------------------------------------------------------- .ass captions

def _font_spec(lang):
    if lang not in CAPTION_FONTS:
        raise ValueError(f"unknown caption language {lang!r}; expected one of {tuple(CAPTION_FONTS)}")
    return CAPTION_FONTS[lang]


def ensure_font(fonts_dir=None, lang="hi"):
    """Path of the bundled caption font for lang (hi/mr: Devanagari, en: Latin). Fails clearly when missing;
    never downloads."""
    spec = _font_spec(lang)
    p = Path(fonts_dir or FONTS_DIR) / spec["file"]
    if not p.is_file():
        raise FileNotFoundError(f"caption font missing for lang {lang!r}: {p}. Place {spec['file']} (SIL OFL 1.1) in "
                                f"assets/fonts/; see assets/fonts/README.md. This code never downloads it.")
    return p


def split_cards(text, max_words=CAPTION["max_words"]):
    """Balanced split into cards of at most max_words words: 13 words -> 5, 5, 3; 7 words -> 4, 3."""
    words = text.split()
    if not words:
        return []
    n = math.ceil(len(words) / max_words)
    size = math.ceil(len(words) / n)
    return [words[i:i + size] for i in range(0, len(words), size)]


def build_cards(cues):
    """cues: [{"text", "start", "end"}] -> cards [{"start", "end", "words": [(word, centiseconds)]}].
    Card time is shared by word count; each word gets an equal slice of its card (karaoke \\k)."""
    cards = []
    for cue in cues:
        s, e = float(cue["start"]), float(cue["end"])
        if e <= s:
            raise ValueError(f"cue end must be after start: {cue!r}")
        chunks = split_cards(cue["text"])
        total = sum(len(c) for c in chunks)
        done = 0
        for chunk in chunks:
            c_start = s + (e - s) * done / total
            done += len(chunk)
            c_end = s + (e - s) * done / total
            per_word = (c_end - c_start) / len(chunk)
            cards.append({"start": c_start, "end": c_end,
                          "words": [(w, max(1, round(per_word * 100))) for w in chunk]})
    return cards


def _estimate_lines(words):
    usable = CAPTION["play_res"][0] - CAPTION["margin_l"] - CAPTION["margin_r"]
    width = sum(len(w) + 1 for w in words) * CAPTION_CHAR_PX
    return max(1, math.ceil(width / usable))


def _caption_top(lines, margin_v):
    return (CAPTION["play_res"][1] - margin_v) - lines * CAPTION_LINE_PX


def _overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def place_card(words, face_boxes=()):
    """(margin_v, flagged). Raises the caption in CAPTION_MOVE_STEP_PX steps until it clears every face box and
    stays at or below top_blocked_y. flagged=True when no clear spot exists (default position kept)."""
    width, height = CAPTION["play_res"]
    lines = _estimate_lines(words)
    mv = CAPTION["margin_v"]
    while True:
        box = (CAPTION["margin_l"], _caption_top(lines, mv), width - CAPTION["margin_r"], height - mv)
        if not any(_overlaps(box, f) for f in face_boxes):
            return mv, False
        mv += CAPTION_MOVE_STEP_PX
        if _caption_top(lines, mv) < CAPTION["top_blocked_y"]:
            return CAPTION["margin_v"], True


def _ts(sec):
    cs = int(round(sec * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def _ass_word(word):
    return re.sub(r"[{}\\]", "", word)


def _ass_header(lang="hi"):
    w, h = CAPTION["play_res"]
    spec = _font_spec(lang)
    return (
        "[Script Info]\n"
        f"; font file: assets/fonts/{spec['file']} (burn with fontsdir=assets/fonts)\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {w}\n"
        f"PlayResY: {h}\n"
        "ScaledBorderAndShadow: yes\n"
        "WrapStyle: 0\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding\n"
        # Primary = yellow (the sung word), Secondary = white (not yet sung), black outline for contrast.
        f"Style: Caption,{spec['family']},{CAPTION_FONT_SIZE},&H0000FFFF,&H00FFFFFF,&H00000000,&H80000000,"
        f"-1,0,0,0,100,100,0,0,1,6,0,{CAPTION['alignment']},{CAPTION['margin_l']},{CAPTION['margin_r']},"
        f"{CAPTION['margin_v']},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def build_ass(cues, face_boxes=(), lang="hi"):
    """(ass_text, warnings). cues: [{"text", "start", "end"}]; face_boxes: (x0, y0, x1, y1) in PlayRes pixels.
    lang picks the font family only (hi/mr/en). Pure text: the font file is not read here (write_captions checks
    it). Raises ValueError if any caption would sit above top_blocked_y."""
    header = _ass_header(lang)
    events, warnings = [], []
    for card in build_cards(cues):
        words = [w for w, _ in card["words"]]
        mv, flagged = place_card(words, face_boxes)
        if flagged:
            warnings.append(f"caption at {card['start']:.2f}s covers a face and has no clear spot; kept MarginV={mv}")
        top = _caption_top(_estimate_lines(words), mv)
        if top < CAPTION["top_blocked_y"]:
            raise ValueError(f"caption top y={top:.0f} is above y={CAPTION['top_blocked_y']}")
        text = " ".join(f"{{\\k{cs}}}{_ass_word(w)}" for w, cs in card["words"])
        events.append(f"Dialogue: 0,{_ts(card['start'])},{_ts(card['end'])},Caption,,"
                      f"{CAPTION['margin_l']},{CAPTION['margin_r']},{mv},,{text}")
    return header + "\n".join(events) + ("\n" if events else ""), warnings


def write_captions(out_path, cues, face_boxes=(), fonts_dir=None, lang="hi"):
    """ensure_font(lang), then build_ass(lang), then write the .ass file. Returns the warnings list."""
    ensure_font(fonts_dir, lang)
    text, warnings = build_ass(cues, face_boxes, lang)
    Path(out_path).write_text(text, encoding="utf-8", newline="\n")
    return warnings


_FF_SPECIAL = re.compile(r"[,;\[\]']")
_ABS_PATH = re.compile(r"^([A-Za-z]:|/|\\\\)")


def _ff_path(p):
    """A path as a filtergraph option value. A relative path (ffmpeg runs from the repo root) needs no escaping.
    An absolute Windows path gets forward slashes, the drive colon escaped as \\: and the value single-quoted, so
    the colon is not read as an option separator."""
    raw = str(p)
    s = raw.replace("\\", "/")
    if _FF_SPECIAL.search(s):
        raise ValueError(f"path has a filtergraph special character (, ; [ ] '): {raw!r}")
    if _ABS_PATH.match(raw):
        return "'" + s.replace(":", "\\:") + "'"
    if ":" in s:
        raise ValueError(f"relative path must not contain a colon: {raw!r}")
    return s


def build_subtitles_filter(ass_path, fonts_dir=None):
    """Text of the ffmpeg subtitles filter that burns the .ass file with the font in fonts_dir (default the relative
    assets/fonts). Not run here."""
    return f"subtitles=filename={_ff_path(ass_path)}:fontsdir={_ff_path(fonts_dir or 'assets/fonts')}"


# ---------------------------------------------------------------- one final reel per selected language

LANGUAGES = ("en", "hi", "mr")


def _src(ref):
    """ffmpeg audio source: an int is input [n:a]; a str is a label already made earlier in the graph."""
    return f"[{ref}:a]" if isinstance(ref, int) else f"[{ref}]"


def build_sfx_split_filter(source_ref, n):
    """Splits one audio source into labels h3s0..h3s{n-1}, one per trimmed SFX clip (each label is used once)."""
    return f"{_src(source_ref)}asplit={n}" + "".join(f"[h3s{k}]" for k in range(n))


def build_vo_stem_filter(vo_clips):
    """VO stem on the reel clock -> [vo_full]. vo_clips: [(input_ref or None, editorial_sec)] in shot order.
    None means the shot has no VO, so it gets silence of its editorial length. Each clip is padded then trimmed
    to its own shot, so the stem stays aligned with the shot starts."""
    chains, labels = [], []
    for k, (ref, ed) in enumerate(vo_clips):
        ed = float(ed)
        if ref is None:
            chains.append(f"anullsrc=channel_layout=stereo:sample_rate={MIX_RATE},atrim=0:{ed:.3f},"
                          f"asetpts=PTS-STARTPTS,{MIX_FORMAT}[vo{k}]")
        else:
            chains.append(f"{_src(ref)}{MIX_FORMAT},apad=whole_dur={ed:.3f},atrim=0:{ed:.3f},"
                          f"asetpts=PTS-STARTPTS[vo{k}]")
        labels.append(f"[vo{k}]")
    chains.append("".join(labels) + f"concat=n={len(labels)}:v=0:a=1[vo_full]")
    return ";".join(chains)


def _pick_languages(languages):
    langs = list(languages)
    if not langs or len(set(langs)) != len(langs) or any(lang not in LANGUAGES for lang in langs):
        raise ValueError(f"languages must be a non-empty, unique subset of {LANGUAGES}; got {languages!r}")
    return langs


def _lang_track(trk, lang):
    """(narration, dialogue) of one shot for one language. Shots with *_by_lang maps use them. Single-language shots
    keep the old fields and serve only their narration language (dialogue is taken as that language)."""
    if trk.get("narration_by_lang") is not None or trk.get("dialogue_by_lang") is not None:
        nbl, dbl = trk.get("narration_by_lang"), trk.get("dialogue_by_lang")
        nbl = nbl if isinstance(nbl, dict) else {}   # a non-object *_by_lang is reported as TIME-01 by same_timing_problems
        dbl = dbl if isinstance(dbl, dict) else {}
        return nbl.get(lang), dbl.get(lang) or []
    narr = trk.get("narration")
    if narr and narr.get("language") == lang:
        return narr, trk.get("dialogue") or []
    return None, []


def _lang_view_track(shot, lang):
    trk = shot.get("audio_and_dialogue_track") or {}
    narr, dia = _lang_track(trk, lang)
    return {"narration": narr, "dialogue": dia, "sfx_cues": trk.get("sfx_cues") or [],
            "performance_notes": trk.get("performance_notes") or {}}


def _caption_cues(shots, offsets, lang):
    """Caption cues on the reel clock. captions_by_lang[lang] wins when given ({"text", "time_range"}, or plain text
    on the narration time). Otherwise the narration and dialogue text of that language is captioned."""
    cues = []
    for shot, t0 in zip(shots, offsets):
        trk = shot.get("audio_and_dialogue_track") or {}
        narr, dia = _lang_track(trk, lang)
        cap = (trk.get("captions_by_lang") or {}).get(lang)
        items = []
        if isinstance(cap, dict):
            items.append((cap.get("text"), cap.get("time_range") or (narr or {}).get("time_range")))
        elif isinstance(cap, str) and narr:
            items.append((cap, narr.get("time_range")))
        else:
            items.append(((narr or {}).get("text"), (narr or {}).get("time_range")))
            items += [(d.get("text"), d.get("time_range")) for d in dia]
        for text, rng in items:
            if str(text or "").strip() and rng:
                s, e = parse_time_range(rng)
                cues.append({"text": text, "start": s + t0, "end": e + t0})
    return cues


def _bgm_track(bgm_manifest):
    """(errors, path of the one continuous BGM track). Accepts the parsed manifest or a path to the json file."""
    doc = bgm_manifest
    if doc is None:                                   # no background music (owner default)
        return [], None
    if isinstance(doc, (str, Path)):
        try:
            doc = json.loads(Path(doc).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return [_err("BGM_MANIFEST_UNREADABLE", str(bgm_manifest), str(exc))], None
    if isinstance(doc, dict) and doc.get("tracks") == []:   # explicit "no BGM"
        return [], None
    errors = list(validate_bgm_manifest(doc)["errors"])
    if errors:
        return errors, None
    tracks = doc["tracks"]
    if len(tracks) != 1:
        return [_err("BGM_TRACK_COUNT", "bgm_manifest", "exactly one continuous BGM track is mixed")], None
    return [], tracks[0]["path"]


def _plan_one_language(reel, lang, shots, offsets, vo_dir, bgm_path, bgm_errors, *, video_path, captions_dir,
                       export_dir, face_boxes, fonts_dir, story_gate_checks, payoff_end_sec, narration_driven,
                       measured_text, sfx_stem_path, burn_captions, voice_engine="elevenlabs"):
    views = [dict(s, audio_and_dialogue_track=_lang_view_track(s, lang)) for s in shots]
    errors, warnings, stats = list(bgm_errors), [], {}
    h3_voice = voice_engine == "h3"                   # English H3 speech: no VO files, the clip's own audio is the voice

    def take(name, rep):
        errors.extend(rep["errors"])
        warnings.extend(rep["warnings"])
        stats[name] = rep["stats"]

    # VO file set audio/vo/<lang>/<shot_id>.wav for every shot with speech in this language (ElevenLabs engine only).
    vo_clips, vo_files, existing = [], {}, []
    any_speech = False
    for s, v in zip(shots, views):
        sid, ed = _sid(s), _editorial_len(s)
        if h3_voice or not _speech_items(v["audio_and_dialogue_track"]):
            vo_clips.append((None, ed))
            continue
        any_speech = True
        path = Path(vo_dir) / lang / f"{sid}.wav"
        vo_clips.append((str(path), ed))
        if path.is_file():
            vo_files[sid] = str(path)
            if ed > 0:
                existing.append({"shot_id": sid, "wav_path": str(path), "editorial_duration_sec": ed})
        else:
            errors.append(_err("VO_MISSING", sid, f"no {lang} VO file at {path}"))
    if not h3_voice and any_speech and not vo_files:
        errors.append(_err("NO_VO_FILES", lang, f"no {lang} VO file for any shot under {Path(vo_dir) / lang}"))
    take("vo_fit", vo_fit_check(existing))

    cues = _caption_cues(shots, offsets, lang)
    if not cues:
        errors.append(_err("NO_CAPTIONS", lang, f"no {lang} caption text in any shot"))
    try:
        ensure_font(fonts_dir, lang)
    except FileNotFoundError as exc:
        errors.append(_err("FONT_MISSING", lang, str(exc)))
    if cues:
        try:
            warnings.extend(build_ass(cues, face_boxes, lang)[1])
        except ValueError as exc:
            errors.append(_err("ASS_GEOMETRY", lang, str(exc)))

    take("narration", check_narration_density(views, narration_driven=narration_driven))
    op = next((v for s, v in zip(shots, views) if s.get("is_opening_0_2s_hook")), None)
    if op is None:
        errors.append(_err("OPENING_SHOT_MISSING", lang, "no shot has is_opening_0_2s_hook"))
    else:
        take("opening", check_opening_hook(op))
    ci = next((i for i, s in enumerate(shots) if s.get("is_closing_hook")), None)
    if ci is None:
        errors.append(_err("CLOSING_SHOT_MISSING", lang, "no shot has is_closing_hook"))
    else:
        take("closing", check_closing_shot(views[ci], story_gate_checks=story_gate_checks,
                                           vo_wav_path=vo_files.get(_sid(shots[ci])), payoff_end_sec=payoff_end_sec))

    # Pre-render gate: the mix and mux are only built when nothing above failed for this language.
    export = f"{export_dir}/{reel}_{lang}.mp4"
    plan = {"vo_files": vo_files, "caption_path": f"{captions_dir}/{reel}_{lang}.ass", "captions": cues,
            "export_path": export, "loudness_argv": build_loudness_verify_argv(export),
            "mix_filter": None, "mux_argv": None}
    if not errors:
        inputs, vo_refs = [str(video_path)], []
        sfx_ref = 0                                   # the reel's own audio [0:a] unless a stem file is given
        if sfx_stem_path is not None:
            inputs.append(str(sfx_stem_path))
            sfx_ref = len(inputs) - 1
        for path, ed in vo_clips:
            if h3_voice:
                break
            if path is None:
                vo_refs.append((None, ed))
            else:
                inputs.append(path)
                vo_refs.append((len(inputs) - 1, ed))
        bgm_idx = None
        if bgm_path is not None:
            bgm_idx = len(inputs)
            inputs.append(bgm_path)
        total = offsets[-1] + _editorial_len(shots[-1])
        sfx = [{"input_index": f"h3s{k}", "trim_in_sec": t0, "trim_out_sec": t0 + _editorial_len(s)}
               for k, (s, t0) in enumerate(zip(shots, offsets))]
        if h3_voice:
            plan["mix_filter"] = ";".join([build_sfx_split_filter(sfx_ref, len(shots)),
                                           build_mix_filter(sfx, None, bgm_idx, total)])
        else:
            plan["mix_filter"] = ";".join([build_sfx_split_filter(sfx_ref, len(shots)), build_vo_stem_filter(vo_refs),
                                           build_mix_filter(sfx, "vo_full", bgm_idx, total)])
        plan["mux_argv"] = build_final_mux_argv(video_path, inputs[1:], plan["mix_filter"], export,
                                                burn_captions=burn_captions, ass_path=plan["caption_path"],
                                                fonts_dir=fonts_dir)

    # Post-render: loudness of the AAC mp4, checked per language when its measurement is supplied.
    if measured_text and lang in measured_text:
        take("loudness", check_post_aac_loudness(measured_text[lang]))
    else:
        warnings.append(f"loudness for {lang} not measured yet: run loudness_argv on {export} after render")
    return _report(errors, warnings, stats), plan


def _sid(shot):
    """The shot id: shot_id (the H3 schema key), else the older id key."""
    return shot.get("shot_id", shot.get("id")) if isinstance(shot, dict) else None


def _editorial_len(shot):
    """The editorial length in seconds, or 0.0 when it is not a positive number (same_timing_problems reports that as TIME-01)."""
    ed = shot.get("editorial_duration_sec") if isinstance(shot, dict) else None
    return float(ed) if isinstance(ed, (int, float)) and not isinstance(ed, bool) and ed > 0 else 0.0


def plan_language_outputs(reel, languages, vo_dir, bgm_manifest, *, shots, video_path, video_has_audio=None,
                          sfx_stem_path=None, burn_captions=True, captions_dir="captions", export_dir="export",
                          face_boxes=(), fonts_dir=None, story_gate_checks=None, payoff_end_sec=None,
                          narration_driven=True, measured_text=None, voice_engines=None):
    """One final reel per selected language (en, hi, mr; any subset, order = priority) from the same video and SFX.
    voice_engines: the story's voice_engine dict. None = every language uses ElevenLabs files (old behaviour).
    Render variants (owner 2026-11-07): one shared pure-Foley video serves hi, mr and every elevenlabs language; an
    "h3" English language uses its own second H3 render. video_path is one path (shared only) or a dict
    {"shared_foley": path, "en_h3": path}; a dict without "en_h3" fails for an h3 language.

    Returns {"ok": all languages ok, "reports": {lang: report}, "languages": {lang: plan}}. A plan holds the VO file
    set audio/vo/<lang>/<shot_id>.wav, the .ass caption path and cues, the export path export/<reel>_<lang>.mp4,
    the mix filtergraph, the mux argv and the loudness argv. A language with errors gets no mix or mux argv; the
    other languages are not affected. Never runs ffmpeg."""
    langs = _pick_languages(languages)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", str(reel)) or ".." in str(reel):
        raise ValueError(f"reel id {reel!r} may only hold letters, digits, _ . - (it becomes part of file paths)")
    if not shots:
        raise ValueError("shots must not be empty")
    if sfx_stem_path is None and video_has_audio is not True:
        raise ValueError(f"no H3 SFX source: video_has_audio={video_has_audio!r} and no sfx_stem_path given. Pass "
                         "video_has_audio=True when the reel's own audio carries the H3 SFX, or sfx_stem_path=<the "
                         "SFX stem file>.")
    bgm_errors, bgm_path = _bgm_track(bgm_manifest)
    offsets, t = [], 0.0
    for s in shots:
        offsets.append(t)
        t += _editorial_len(s)
    reports, plans = {}, {}
    try:
        timing_errs = same_timing_problems(shots)
    except (ValueError, AttributeError) as exc:        # a malformed time_range, or a non-object *_by_lang / track
        timing_errs = [_err("TIME-01", "shots", f"bad time_range or track: {type(exc).__name__}: {exc}")]
    for lang in langs:
        eng = engine_for(voice_engines, lang) if voice_engines is not None else "elevenlabs"
        if eng not in VOICE_ENGINES or (eng == "h3" and lang not in H3_SPEECH_LANGS):
            reports[lang] = _report([_err("PLAN-01", lang, f"voice engine {eng!r} is not allowed for {lang}: use "
                                                          f"elevenlabs, or h3 for English only")], [], {})
            plans[lang] = {"mix_filter": None, "mux_argv": None}
            continue
        try:
            reports[lang], plans[lang] = _plan_one_language(
                reel, lang, shots, offsets, vo_dir, bgm_path, list(bgm_errors) + timing_errs, video_path=_video_for(video_path, eng),
                captions_dir=captions_dir, export_dir=export_dir, face_boxes=face_boxes, fonts_dir=fonts_dir,
                story_gate_checks=story_gate_checks, payoff_end_sec=payoff_end_sec,
                narration_driven=narration_driven, measured_text=measured_text, sfx_stem_path=sfx_stem_path,
                burn_captions=burn_captions, voice_engine=eng)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:   # one bad language must not stop the others (AttributeError: a non-object track/gate/mouth block)
            reports[lang] = _report([_err("PLAN-01", lang, f"{type(exc).__name__}: {exc}")], [], {})
            plans[lang] = {"mix_filter": None, "mux_argv": None}
        if eng == "h3":
            reports[lang]["warnings"].append("en=h3 breaks the render-once rule: English uses its own H3 video (second render, adds H3 cost)")
    return {"ok": all(r["ok"] for r in reports.values()), "reports": reports, "languages": plans}


def same_timing_problems(shots):
    """TIME-01: one timing for every language. Each shot has one positive editorial length, and every language of a shot uses
    the same time ranges (narration, dialogue and caption cards in *_by_lang), so the cut points of the reels match.
    Returns error dicts (added to every language, which then gets no mix)."""
    errs = []
    for s in shots:
        sid = s.get("id", "?")
        ed = s.get("editorial_duration_sec")
        if not (isinstance(ed, (int, float)) and not isinstance(ed, bool) and ed > 0):
            errs.append(_err("TIME-01", sid, "editorial_duration_sec must be a positive number (one timing for every language)"))
            continue
        trk = s.get("audio_and_dialogue_track") or {}
        per_lang = {}
        for key in ("narration_by_lang", "dialogue_by_lang", "captions_by_lang"):
            by_lang = trk.get(key) or {}
            if not isinstance(by_lang, dict):
                errs.append(_err("TIME-01", sid, f"{key} must be an object keyed by language, got {type(by_lang).__name__}"))
                continue
            for lang, val in by_lang.items():
                if val is None:
                    items = []
                elif isinstance(val, dict):
                    items = [val]
                elif isinstance(val, list):
                    items = val
                else:
                    errs.append(_err("TIME-01", sid, f"{key}[{lang}] must be an object or a list of objects, "
                                                     f"got {type(val).__name__}"))
                    continue
                ranges = [parse_time_range(x["time_range"]) for x in items
                          if isinstance(x, dict) and x.get("time_range") not in (None, [])]
                if ranges:   # a language with no time_range is not timed in this shot: it is not compared (no false TIME-01)
                    per_lang.setdefault(lang, []).extend(ranges)
        keys = {lang: sorted((round(a, 3), round(b, 3)) for a, b in r) for lang, r in per_lang.items()}
        if len({tuple(v) for v in keys.values()}) > 1:
            errs.append(_err("TIME-01", sid, f"languages use different time ranges: {keys}"))
    return errs


def _video_for(video_path, engine):
    """The video a language is built from: one path for all, or the dict variant of its engine."""
    if not isinstance(video_path, dict):
        return video_path
    key = "en_h3" if engine == "h3" else "shared_foley"
    if key not in video_path:
        raise ValueError(f"video_path needs a {key!r} entry for voice engine {engine!r}")
    return video_path[key]
