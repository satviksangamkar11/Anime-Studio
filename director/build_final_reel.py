"""Final reel builder (backend): rendered clips + per-shot voice tracks -> one finished reel per language, WITHOUT music.

  1. cuts: h3.assemble_reel.build_ffmpeg_assembly_plan trims every clip to its editorial window (head/tail handles removed) and concatenates
     video and the clips' own H3 sound effects; ffmpeg runs it -> <out>/<reel>_video.mp4
  2. gate: h3.gate_d_audio.plan_language_outputs checks every language (VO fit, captions, hook, closing). Findings whose code the owner
     waived in <pack>/waivers.json are WRITTEN INTO THE REPORT (never hidden) and do not stop the build. Any other error stops it.
  3. mix + captions: the same Gate D functions the planner uses (SFX stem ducked under the voice stem, loudnorm to core delivery loudness,
     burned .ass captions in the language's script) -> <out>/export/<reel>_<lang>.mp4, then the AAC loudness is measured and checked.
No music is mixed (bgm_manifest None); the score is a later step. Never calls a model or ElevenLabs.

  python build_final_reel.py --pack <pack dir> --story <h3_story.json> --clips <clips.json {SHOT-001: path}>
      --vo <vo root with <lang>/<SHOT>.wav> --lock <timeline_lock_vN.json> --out <dir> --reel <name> [--langs en,hi,mr]

--reel is required (no default). The lock is the only timing source. Each clip's folder must hold a passing clip_qa.json (X-14).
Findings are waived only by <pack>/waivers.json {reel, codes, signed_by: "owner", date}. No waivers file = nothing is waived.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from core import caption_text as ct  # noqa: E402
from core.captions import ass_time  # noqa: E402
from core.style_pack import load_core  # noqa: E402
from h3 import assemble_reel as ar  # noqa: E402
from h3 import gate_d_audio as gd  # noqa: E402
from h3 import silence_rule as sr  # noqa: E402
import text_card_qa as tcq  # noqa: E402
import caption_fields as cf  # noqa: E402
import voice_manifest as vm  # noqa: E402
import clip_qa  # noqa: E402
import timeline_lock_io as tli  # noqa: E402
import wav_contract as wc  # noqa: E402
import waivers as wv  # noqa: E402

REEL_CLOSED = {"kalika_reel1"}          # rule 53: reel 1 is closed; this module never rebuilds it
REEL_NAME = re.compile(r"[a-z0-9_]+")
LANG_NAME = {"en": "english", "hi": "hindi", "mr": "marathi"}     # waivers.py names the languages this way


def probe_frames(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return int(r.stdout.strip())


def assemble_video(h3_shots, clips, out_video, work):
    """Run the editorial cut plan. Returns the plan (frames, duration, seams)."""
    plan = ar.build_ffmpeg_assembly_plan(h3_shots, str(out_video))
    paths = [str(clips[s["shot_id"]]) for s in h3_shots]
    for s, p in zip(h3_shots, paths):
        need = s["timing_and_lattice"]["trim_out_frame"]
        got = probe_frames(p)
        if got < need:
            raise ValueError(f"{s['shot_id']}: clip has {got} frames, the cut needs {need}")
    work.mkdir(parents=True, exist_ok=True)
    (work / "filter.txt").write_text(plan["filter_complex"], encoding="utf-8", newline="\n")
    d = load_core()["delivery"]
    argv = ["ffmpeg", "-y", "-v", "error"]
    for p in paths:
        argv += ["-i", p]
    argv += ["-filter_complex_script", str(work / "filter.txt"), "-map", "[vout]", "-map", "[aout]", "-r", str(plan["fps"]),
             "-c:v", d["codec"], "-crf", str(d["crf"]), "-pix_fmt", d["pix_fmt"], "-colorspace", d["colorspace"], "-color_primaries",
             d["color_primaries"], "-color_trc", d["color_trc"], "-color_range", d["color_range"],
             "-c:a", d["audio"]["codec"], "-b:a", d["audio"]["bitrate"], "-movflags", "+faststart", str(out_video)]
    subprocess.run(argv, check=True)
    return plan


def has_lines(row, lang):
    """True when shots.json gives this shot a spoken line (narration or dialogue) in the language."""
    a = row.get("audio_and_dialogue_track") or {}
    narration = ((a.get("narration_by_lang") or {}).get(lang) or {}).get("text")
    return bool(narration) or bool((a.get("dialogue_by_lang") or {}).get(lang))


def clean_argv(argv, pre_vf=None):
    """G15: the same mux argv without the caption burn: the video goes through the delivery crop (pre_vf, else null) and the
    same libx264 settings, the audio graph is untouched, so the audio is the same as the burned export's."""
    if "-filter_complex" not in argv:                   # a stubbed or draft argv has no graph to strip
        return list(argv)
    i = argv.index("-filter_complex")
    out = list(argv)
    out[i + 1] = f"{argv[i + 1].rsplit(';[0:v]', 1)[0]};[0:v]{pre_vf or 'null'}[vsub]"
    return out


def burned_from_clean_argv(clean, burned, ass, fonts_dir):
    """Optional burned export, cut from the finished clean export: audio stream copied (same bytes), video gets the ass burn."""
    return ["ffmpeg", "-y", "-i", str(clean), "-vf", gd.build_subtitles_filter(ass, fonts_dir), "-c:v", "libx264", "-crf", "14",
            "-preset", "slow", "-pix_fmt", "yuv420p", "-r", str(gd.FPS), "-c:a", "copy", "-movflags", "+faststart", str(burned)]


def audio_sha256(path):
    """sha256 of the audio stream alone (copied out as ADTS), so two files with different video can be compared."""
    done = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-c:a", "copy", "-f", "adts", "-"], capture_output=True)
    if done.returncode != 0 or not done.stdout:
        raise SystemExit(f"audio sha: cannot read the audio of {path}")
    return hashlib.sha256(done.stdout).hexdigest()


def mux_argv(rows, lang, vo_dir, video, export, ass, fonts_dir, pre_vf=None, sfx_policy=None):
    """The planner's own mix and mux, built directly so a waived finding does not block it (same functions, same order).
    Rows come from lock_rows (offset_sec is the lock's own clock). A shot with lines and no voice file stops the build.
    pre_vf is the delivery crop/scale (delivery_vf) that runs before the ass burn."""
    inputs, vo_refs, t = [str(video)], [], 0.0
    for r in rows:
        ed = float(r["editorial_duration_sec"])
        t += ed
        p = Path(vo_dir) / lang / f"{r['id']}.wav"
        if p.is_file():
            inputs.append(str(p))
            vo_refs.append((len(inputs) - 1, ed))
        elif has_lines(r, lang):
            raise SystemExit(f"{r['id']}: {lang} voice file missing ({p}) for a shot that has lines")
        else:
            vo_refs.append((None, ed))
    sfx = [{"input_index": f"h3s{k}", "trim_in_sec": float(r["offset_sec"]),
            "trim_out_sec": float(r["offset_sec"]) + float(r["editorial_duration_sec"])} for k, r in enumerate(rows)]
    mix = ";".join([gd.build_sfx_split_filter(0, len(rows)), gd.build_vo_stem_filter(vo_refs), gd.build_mix_filter(sfx, "vo_full", None, t, **({"sfx_policy": sfx_policy} if sfx_policy is not None else {}))])
    return gd.build_final_mux_argv(video, inputs[1:], mix, export, burn_captions=True, ass_path=ass, fonts_dir=fonts_dir,
                                   pre_vf=pre_vf), t


# Caption spec v2 (research/CAPTION_SPEC_v2_REELS_SHORTS_2026-11-09.md). The family is the font file's own name (name ID 1):
# plain "Mukta" made libass draw a system font. Burned with the ass filter + shaping=complex (conjuncts join).
CAPTION_FONT = "Mukta ExtraBold"
CAPTION_FONT_FILE = "Mukta-ExtraBold.ttf"
PLAY_W, PLAY_H = 1080, 1920
CAPTION_SIZE = {"en": 112, "hi": 104, "mr": 104}
CAPTION_MAX_W = 840                         # max text width in px (safe zone x 90-930 with the outline)
CAPTION_POS = (510, 1290)                   # \an5 centre; x 510 is 30 px left of centre to clear the right button rail
CARD_WORDS = {"en": 4, "hi": 3, "mr": 3}
CARD_CHARS = {"en": None, "hi": 18, "mr": 18}
GREEN_BGR, WHITE_BGR = "&H004EFF3C&", "&H00FFFFFF&"   # ASS colours are BGR: active word green #3CFF4E, the rest white
CAPTION_PACK = {"typography": {"subtitle_latin": CAPTION_FONT, "subtitle_devanagari": CAPTION_FONT, "min_px_at_1080w": 60}}
# Delivery frame (rule 51): the 768x1344 picture is scaled to 1098x1920 (lanczos) and centre-cropped to 1080x1920 BEFORE the ass burn,
# so libass draws the captions on the frame the viewer sees. 768*1920/1344 = 1097.14, rounded to the even 1098; (1098-1080)/2 = 9.
DELIVERY_VF = "scale=1098:1920:flags=lanczos,crop=1080:1920:9:0"
DELIVERY_SOURCE_SIZE = {(768, 1344): DELIVERY_VF, (1080, 1920): None}


def caption_fits(font_file, lang):
    """Card test for split_cards: the card wraps into at most 2 lines at CAPTION_MAX_W with the real font."""
    size = CAPTION_SIZE[lang]

    def fits(card):
        return len(ct.wrap_lines(card, str(font_file), size, CAPTION_MAX_W, 2)[0]) <= 2
    return fits


def split_cards(text, lang="en", fits=None):
    """Balanced cards inside the spec limits: en at most 4 words, hi/mr at most 3 words and 18 characters, and `fits` (2 lines
    at 840 px) when given. Sentence ends are cut first. A punctuation-only token (a stray " .") joins the word before it."""
    text = re.sub(r"\s+([.,;:!?।])", r"\1", " ".join(text.split()))
    toks = []
    for t in text.split(" "):
        if toks and not re.search(r"\w", t):
            toks[-1] += t
        else:
            toks.append(t)
    sents = [s for s in re.split(r"(?<=[.?!।])\s+", " ".join(toks).strip()) if s]
    limit, max_chars = CARD_WORDS[lang], CARD_CHARS[lang]

    def ok(ws):
        s = " ".join(ws)
        return (max_chars is None or len(s) <= max_chars) and (fits is None or fits(s))
    cards = []
    for s in sents:
        words = s.split()
        for n in range(-(-len(words) // limit), len(words) + 1):      # fewest balanced cards that pass the limits
            size = -(-len(words) // n)
            chunks = [words[i:i + size] for i in range(0, len(words), size)]
            if all(ok(c) for c in chunks):
                break
        cards += chunks
    return cards


def word_cues(text, t0, t1, lang="en", fits=None):
    """Cue dicts for one spoken line: spec-v2 cards, time shared by letters, each word aligned inside its card (letters-proportional)."""
    cards = split_cards(text, lang, fits)
    weights = [sum(len(w) for w in c) + len(c) for c in cards]
    total, cues, cur = float(sum(weights)), [], t0
    for c, wt in zip(cards, weights):
        end = cur + (t1 - t0) * wt / total
        lw = [len(w) + 0.5 for w in c]
        s, words = cur, []
        for w, x in zip(c, lw):
            e = s + (end - cur) * x / sum(lw)
            words.append({"text": w, "t0": round(s, 3), "t1": round(e, 3), "conf": 1.0})
            s = e
        cues.append({"t0": round(cur, 3), "t1": round(end, 3), "text": " ".join(c), "words": words, "kind": "spoken"})
        cur = end
    return cues


def probe_size(path):
    """(width, height) of the first video stream, from ffprobe."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0:s=x", str(path)], capture_output=True, text=True, check=True)
    w, h = r.stdout.strip().split("x")
    return int(w), int(h)


def delivery_vf(size):
    """The video filter that puts a picture on the 1080x1920 delivery frame before the captions. 768x1344 gets DELIVERY_VF,
    1080x1920 needs none, any other size stops the build (rule 51 names only these two)."""
    if tuple(size) not in DELIVERY_SOURCE_SIZE:
        raise SystemExit(f"video is {size[0]}x{size[1]}; rule 51 allows only 768x1344 (cropped) or 1080x1920")
    return DELIVERY_SOURCE_SIZE[tuple(size)]


def load_manifest_rows(template, lang):
    """Rows of the voice manifest of one language (voice_manifest.py: schema, language, text and wav hashes, row set).
    '{lang}' in the path is filled in; a path without it is used for every language. Any refusal stops the build."""
    try:
        return vm.load_voice_manifest(Path(str(template).replace("{lang}", lang)), lang=lang)
    except vm.VoiceManifestError as exc:
        raise SystemExit(f"voice manifest: {exc}") from exc


def manifest_by_id(manifest):
    """Voice manifest rows {id: "<line>.<lang>", text, text_sha256} (voice_cast.py jobs) keyed by id. Duplicate ids stop the build."""
    by_id = {}
    for m in manifest:
        if m["id"] in by_id:
            raise SystemExit(f"voice manifest: duplicate id {m['id']}")
        by_id[m["id"]] = m
    return by_id


def line_captions(rows, report, lang, manifest):
    """[(caption_text, start, end)] on the reel clock, one per spoken line of `lang`, in report order (the voice report times).
    spoken_text is the voice manifest text of "<line>.<lang>" (its sha256 must equal text_sha256). Caption text comes from the
    shots.json line keys caption_text and caption_diff_approved, resolved by caption_fields (a caption difference needs the
    owner's approval and the same word count)."""
    offsets, t = {}, 0.0
    for r in rows:
        offsets[r["id"]] = t
        t += float(r["editorial_duration_sec"])
    src = {}
    for r in rows:
        a = r["audio_and_dialogue_track"]
        n = (a.get("narration_by_lang") or {}).get(lang) or {}
        if n.get("text"):
            src[f"{r['id']}-N"] = n
        for k, d in enumerate((a.get("dialogue_by_lang") or {}).get(lang) or [], 1):
            src[f"{r['id']}-D{k}"] = d
    by_id = manifest_by_id(manifest)
    needed = [ln["id"] for sh in report if sh["lang"] == lang for ln in sh["lines"]]
    lines = []
    for line_id in dict.fromkeys(needed):
        if line_id not in src:
            raise SystemExit(f"{line_id}: report line has no {lang} line in shots.json")
        key = f"{line_id}.{lang}"
        if key not in by_id:
            raise SystemExit(f"{key}: no row in the voice manifest")
        m = by_id[key]
        spoken = m.get("text")
        if hashlib.sha256(str(spoken).encode("utf-8")).hexdigest() != m.get("text_sha256"):
            raise SystemExit(f"{key}: manifest text_sha256 does not match its text")
        lines.append({"id": line_id, "lang": lang, "spoken_text": spoken, "caption_text": src[line_id].get("caption_text"),
                      "caption_diff_approved": src[line_id].get("caption_diff_approved", False)})
    try:
        captions = {c["id"]: c["text"] for c in cf.caption_lines(lines)}
    except cf.CaptionError as exc:
        raise SystemExit(f"{lang} captions: {exc}") from exc
    return [(captions[ln["id"]], offsets[sh["shot"]] + ln["start"], offsets[sh["shot"]] + ln["end"])
            for sh in report if sh["lang"] == lang for ln in sh["lines"]]


def spoken_cues_real(rows, report, lang, manifest, font_file=None):
    """Caption cues from the REAL packed voice timings (see line_captions): spec-v2 word cards per spoken line."""
    fits = caption_fits(font_file, lang) if font_file else None
    cues = []
    for text, t0, t1 in line_captions(rows, report, lang, manifest):
        cues += word_cues(text, t0, t1, lang, fits)
    return sorted(cues, key=lambda c: c["t0"])


SRT_LINE_CHARS, SRT_MAX_LINES, SRT_MIN_SEC = 42, 2, 1.0       # B-07: YouTube line mode (Netflix 42 x 2; code points)


def _srt_wrap(words):
    """Greedy wrap into lines of at most SRT_LINE_CHARS code points; returns a list of cue texts of at most SRT_MAX_LINES lines."""
    cues, lines, cur = [], [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > SRT_LINE_CHARS:
            lines.append(cur)
            cur = ""
            if len(lines) == SRT_MAX_LINES:
                cues.append("\n".join(lines))
                lines = []
        cur = f"{cur} {w}" if cur else w
    if cur:
        lines.append(cur)
    if lines:
        cues.append("\n".join(lines))
    return cues


def srt_line_cues(lines):
    """YouTube SRT cues, one block per spoken line: [(text, start, end)] -> [{"t0", "t1", "text"}]. A line is split at sentence
    ends, each piece wrapped to at most 42 characters x 2 lines (more cues when it does not fit); the line's own time span is shared
    by letters, so the first cue starts and the last ends exactly at the voice report times. A cue shorter than 1.0 s is stretched
    to 1.0 s when the next cue starts later (never past it)."""
    cues = []
    for text, t0, t1 in lines:
        pieces = []
        for sent in re.split(r"(?<=[.?!।])\s+", " ".join(text.split())):
            pieces += _srt_wrap(sent.split()) if sent else []
        weights = [max(1, len(p.replace("\n", " "))) for p in pieces]
        cur = t0
        for i, (p, wt) in enumerate(zip(pieces, weights)):
            end = t1 if i == len(pieces) - 1 else cur + (t1 - t0) * wt / sum(weights)
            cues.append({"t0": round(cur, 3), "t1": round(end, 3), "text": p})
            cur = end
    for a, nxt in zip(cues, cues[1:] + [None]):
        want = a["t0"] + SRT_MIN_SEC
        if a["t1"] < want:
            a["t1"] = round(want if nxt is None else max(a["t1"], min(want, nxt["t0"])), 3)
    return cues


def write_srt(cues, path):
    """UTF-8 without BOM, LF, HH:MM:SS,mmm (core.caption_export.to_srt). Returns the sha256 of the file."""
    from core import caption_export as cx
    srt, entries = cx.to_srt(cues)
    fails = [e["message"] for e in entries if e["level"] == "FAIL"]
    if fails or not srt:
        raise SystemExit(f"SRT {path}: " + ("; ".join(fails) or "no cues"))
    Path(path).write_text(srt, encoding="utf-8", newline="\n")
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def caption_ass(cues, lang, fonts_dir):
    """Spec v2 ASS text, PlayRes 1080x1920. One event per spoken word: the card shows in white and the word being spoken is green
    #3CFF4E with a 108% pop on that word only. Lines are a balanced wrap at 840 px with the real font. Each card's words must
    be aligned (cue["words"], from word_cues)."""
    font = Path(fonts_dir) / CAPTION_FONT_FILE
    size = CAPTION_SIZE[lang]
    x, y = CAPTION_POS
    asc, desc = ct._font(str(font), size).getmetrics()
    line_h = asc + desc                                    # one line of the real font, px
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {PLAY_W}", f"PlayResY: {PLAY_H}", "WrapStyle: 2",
        "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
        "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        # outline 9 px black, shadow 4 px at 60% opacity (alpha 0x66), no box (BorderStyle 1)
        f"Style: Cap,{CAPTION_FONT},{size},{WHITE_BGR},&H000000FF&,&H00000000&,&H66000000&,0,0,0,0,100,100,0,0,1,9,4,5,0,0,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for cue in cues:
        ws = cue["words"]
        texts = [w["text"] for w in ws]
        wrapped, _ = ct.wrap_lines(" ".join(texts), str(font), size, CAPTION_MAX_W, 2)
        counts = [len(ln.split(" ")) for ln in wrapped]
        if sum(counts) != len(texts):
            raise ValueError(f"card {' '.join(texts)!r} cannot be wrapped without breaking a word")
        # a 2-line card moves its centre up by half a line, so its bottom line stays at y (inside the safe zone)
        cy = y - round((len(counts) - 1) * line_h / 2)
        for i, w in enumerate(ws):
            end = ws[i + 1]["t0"] if i + 1 < len(ws) else cue["t1"]
            body, k = [], 0
            for n in counts:
                seg = []
                for j in range(k, k + n):
                    word = texts[j]
                    seg.append("{\\1c%s\\fscx108\\fscy108}%s{\\1c%s\\fscx100\\fscy100}" % (GREEN_BGR, word, WHITE_BGR)
                               if j == i else word)
                body.append(" ".join(seg))
                k += n
            lines.append(f"Dialogue: 0,{ass_time(w['t0'])},{ass_time(end)},Cap,,0,0,0,,{{\\an5\\pos({x},{cy})}}" + "\\N".join(body))
    return "\n".join(lines) + "\n"


def measure(export):
    text = subprocess.run(gd.build_loudness_verify_argv(str(export)), capture_output=True, text=True).stderr
    return gd.check_post_aac_loudness(text)


def correct_loudness(export, loud, tries=2):
    """One-pass loudnorm is only approximate. Measure the real AAC file, apply the exact gain and a true-peak limiter to the AUDIO only
    (video stream copied), re-measure, repeat up to `tries` times. Returns the last measurement."""
    audio = load_core()["delivery"]["audio"]
    for k in range(tries):
        if loud["ok"]:
            break
        # AAC re-encoding overshoots the sample-peak limiter (reel 1 v4 hi: -0.6 dBTP after 2 tries): 0.5 dB more margin per try
        limit = round(10 ** ((audio["loudnorm_tp_db"] - 0.5 * (k + 1)) / 20), 4)
        gain = audio["lufs"] - loud["stats"]["integrated_lufs"]
        tmp = Path(str(export) + ".fix.mp4")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(export), "-c:v", "copy", "-af", f"volume={gain:.2f}dB,alimiter=limit={limit}:level=disabled",
                        "-c:a", audio["codec"], "-b:a", audio["bitrate"], "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(tmp)], check=True)
        tmp.replace(export)
        loud = measure(export)
    return loud


# X-17 mix intake (rules 48, 50): a full DAW mix of the reel plus its voice-only render, checked before it is used.
MIX_RATE = 48000
MIX_MIN_MEDIAN_DB, MIX_MAX_MEDIAN_DB, MIX_MIN_DB = 15.0, 21.5, 12.0     # voice over bus, rule 48 / 50
MIN_FREE_GB_EXPORT = 2.0                                               # local disk check before export (rule 50)


def lang_path(text):
    lang, sep, path = text.partition("=")
    if not sep or not lang or not path:
        raise argparse.ArgumentTypeError(f"expected LANG=WAV, got {text!r}")
    return lang, path


def read_wav(path):
    """(rate, float64 array (samples, channels) in -1..1) of a 16-bit PCM WAV."""
    with wave.open(str(path), "rb") as w:
        rate, ch, width, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    if width != 2:
        raise SystemExit(f"{path}: 16-bit PCM WAV needed, got {8 * width}-bit")
    return rate, np.frombuffer(raw, dtype="<i2").reshape(-1, ch).astype(np.float64) / 32768.0


def write_wav_pcm16(path, arr, rate):
    pcm = np.clip(np.round(arr * 32768.0), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(arr.shape[1])
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def _rms_db_ratio(num, den):
    rms = lambda x: max(float(np.sqrt(np.mean(np.square(x)))), 1e-9)
    return 20.0 * math.log10(rms(num) / rms(den))


def intake(mix, voice, total_frames, report_rows, work_dir=None, voice_rest=(), silence_ok=(), waived=frozenset()):
    """Check a DAW mix of the whole reel against its voice-only render (rules 48, 50(3)). Length: the mix must hold the lock's
    total (total_frames x 2000 samples at 48 kHz / 24 fps); longer is trimmed to exactly that. Bus = mix - voice. Voice over bus
    per speech window: median in [15, 21.5] dB and minimum >= 12 dB. report_rows: [{offset_sec, lines: [{start, end}]}] (the
    lock's clock: offset_sec + the line's start/end inside the shot). Returns {trimmed_path, median_db, min_db, samples}."""
    wc.require_wav(mix)
    wc.require_wav(voice)
    rate_m, m = read_wav(mix)
    rate_v, v = read_wav(voice)
    if rate_m != MIX_RATE or rate_v != MIX_RATE:
        raise SystemExit(f"mix and voice must be {MIX_RATE} Hz, got {rate_m} and {rate_v}")
    if m.shape[1] != v.shape[1]:
        raise SystemExit(f"mix has {m.shape[1]} channels, voice has {v.shape[1]}")
    need = int(total_frames) * (MIX_RATE // gd.FPS)
    for name, arr in (("mix", m), ("voice", v)):
        if arr.shape[0] < need - 1:
            raise SystemExit(f"{name} {need - arr.shape[0]} samples short: the lock needs {need} ({total_frames} frames)")
    fit = lambda arr: arr[:need] if arr.shape[0] >= need else np.vstack([arr, np.zeros((need - arr.shape[0], arr.shape[1]))])
    m, v = fit(m), fit(v)
    mono_m, mono_v = m.mean(axis=1), v.mean(axis=1)
    bus = mono_m - mono_v
    diffs = []
    for row in report_rows:
        for ln in row["lines"]:
            t0 = int(round((row["offset_sec"] + ln["start"]) * MIX_RATE))
            t1 = min(int(round((row["offset_sec"] + ln["end"]) * MIX_RATE)), need)
            if t1 > t0:
                diffs.append(_rms_db_ratio(mono_v[t0:t1], bus[t0:t1]))
    if not diffs:
        raise SystemExit("no speech windows in the voice report: voice over bus cannot be measured")
    med, low = float(np.median(diffs)), float(min(diffs))
    if not (MIX_MIN_MEDIAN_DB <= med <= MIX_MAX_MEDIAN_DB) or low < MIX_MIN_DB:
        raise SystemExit(f"voice over bus: median {med:.2f} dB (need {MIX_MIN_MEDIAN_DB:g}-{MIX_MAX_MEDIAN_DB:g}), "
                         f"min {low:.2f} dB (need >= {MIX_MIN_DB:g})")
    work = Path(work_dir) if work_dir else Path(mix).parent
    work.mkdir(parents=True, exist_ok=True)
    trimmed = work / f"{Path(mix).stem}_trim{need}.wav"
    write_wav_pcm16(trimmed, m, MIX_RATE)
    rule = sr.check_wav(trimmed, voice_rest, silence_ok)           # NO_SILENCE v2 on the mix, before muxing
    bad = [e for e in rule["errors"] if e["code"] not in waived or e["code"] in sr.CRITICAL]
    if bad:
        raise SystemExit("mix fails NO_SILENCE v2: " + "; ".join(sr.fail_text(e) for e in bad))
    return {"trimmed_path": str(trimmed), "median_db": round(med, 2), "min_db": round(low, 2), "samples": need}


def mix_filter_text(need):
    return f"[1:a]atrim=end_sample={need},asetpts=PTS-STARTPTS[{gd.MASTER_LABEL}]"


def next_export(export_dir, reel, lang):
    """<reel>_<lang>_rN.mp4 with N = 1 + the highest existing N. Existing exports are never overwritten (rule 50(2))."""
    pat = re.compile(re.escape(f"{reel}_{lang}") + r"_r(\d+)\.mp4")
    top, d = 0, Path(export_dir)
    if d.is_dir():
        for p in d.iterdir():
            m = pat.fullmatch(p.name)
            if m:
                top = max(top, int(m.group(1)))
    return d / f"{reel}_{lang}_r{top + 1}.mp4"


def check_free_disk(path, min_gb=MIN_FREE_GB_EXPORT, disk_usage=shutil.disk_usage):
    free = disk_usage(str(path)).free
    if free < min_gb * 2**30:
        raise SystemExit(f"{path}: {free / 2**30:.2f} GB free, the export needs {min_gb:g} GB")


def voice_db_of(wav_path, line_windows):
    """RMS (dB) of one shot's voice file over its spoken line windows [(start, end) s, shot-relative]. None when there is no file."""
    if not Path(wav_path).is_file():
        return None
    rate, arr = read_wav(wav_path)
    mono = arr.mean(axis=1)
    segs = [mono[int(round(a * rate)):int(round(b * rate))] for a, b in line_windows]
    segs = [s for s in segs if s.size]
    if not segs:
        return None
    x = np.concatenate(segs)
    return 20.0 * math.log10(max(float(np.sqrt(np.mean(np.square(x)))), 1e-9))


def sfx_policy_for(rows, clips, vo_dir, lang, vo_report):
    """X-18 (rule 50(6)): one entry per row for mux_argv (None = no voice in this shot, so no ducking) and the levels for
    gd.check_sfx_beds. Keep windows and the bed level come from each clip's clip_qa.json (a missing file raises)."""
    policy, levels = [], []
    for r in rows:
        qa = json.loads((Path(clips[r["id"]]).parent / "clip_qa.json").read_text(encoding="utf-8"))
        wins = [(ln["start"], ln["end"]) for row in vo_report if row["shot"] == r["id"] and row["lang"] == lang for ln in row["lines"]]
        voice_db = voice_db_of(Path(vo_dir) / lang / f"{r['id']}.wav", wins)
        if voice_db is None:
            policy.append(None)
            continue
        bed = float(qa["bed_db"])
        policy.append({"keep": [tuple(w) for w in qa["sfx_keep"]], "bed_gain_db": gd.bed_gain_db(voice_db, bed)})
        levels.append({"shot": r["id"], "voice_db": voice_db, "bed_db": bed})
    return policy, levels


def reel_name(text):
    if not REEL_NAME.fullmatch(text):
        raise argparse.ArgumentTypeError(f"--reel must match [a-z0-9_]+, got {text!r}")
    return text


def build_arg_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--story", required=True)
    ap.add_argument("--clips", required=True)
    ap.add_argument("--vo", required=True)
    ap.add_argument("--lock", required=True, help="timeline lock (timeline_lock_vN.json) the reel is cut from")
    ap.add_argument("--out", required=True)
    ap.add_argument("--reel", required=True, type=reel_name)
    ap.add_argument("--langs", default="en,hi,mr")
    ap.add_argument("--fonts", default=str(HERE.parent / "styles" / "fonts"))
    ap.add_argument("--manifest", help="voice manifest (voice_manifest/1, D-VOICE); '{lang}' in the path is filled per language; required unless --title-cards")
    ap.add_argument("--title-cards", action="store_true", help="burn the writer's title cards instead of the spoken words (old behaviour)")
    ap.add_argument("--story-id", help="story id that scoped waivers name (default: the story json's story_id, else the pack folder name)")
    ap.add_argument("--render-version", help="render version that version-scoped waivers name (default: none; only unversioned waivers match)")
    ap.add_argument("--ocr", help="JSON of OCR read from card frames: [{\"lang\", \"expected_text\", \"title\", \"items\": "
                    "[{\"text\", \"box\": [x0, y0, x1, y1]}]}]; when given, text-card QA runs and a problem blocks the language")
    ap.add_argument("--burned-captions", action="store_true",
                    help="G15: also write a burned-caption export (<export stem>_burned.mp4). Default: only the clean export (no burned "
                    "captions) for every language, for Instagram and YouTube; the SRT is written either way")
    ap.add_argument("--mix", action="append", type=lang_path, default=[], metavar="LANG=WAV",
                    help="the DAW mix of the whole reel for LANG (X-17): trimmed to the lock length, used as the language's audio")
    ap.add_argument("--mix-voice", action="append", type=lang_path, default=[], metavar="LANG=WAV",
                    help="the voice-only render of the same session for LANG (needed with --mix: voice over bus check)")
    return ap


def reel_number(reel):
    """waivers.py keys a waiver file by an int reel: the number at the end of the reel name (kalika_reel2 -> 2)."""
    m = re.search(r"([0-9]+)$", reel)
    if not m:
        raise SystemExit(f"reel {reel!r} has no number at its end, so waivers.json cannot name it")
    return int(m.group(1))


def load_waivers(pack, reel):
    """(records, problems) from <pack>/waivers.json via waivers.read_waivers. Missing file = no records. A malformed file, or a
    legacy object for another reel, stops the build. Refused entries come back as problems (they waive nothing)."""
    path = Path(pack) / "waivers.json"
    try:
        records, problems = wv.read_waivers(str(path))
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise SystemExit(f"waivers {path}: {exc}") from exc
    want = reel_number(reel)
    for rec in records:
        if rec["legacy"] and rec["reel_no"] != want:
            raise SystemExit(f"waivers {path}: waivers are for reel {rec['reel_no']!r}, not reel {want}")
    return records, problems


def split_findings(errors, waived_codes):
    """(waived, blocking) for one language's gate errors. Only codes in waived_codes are waived."""
    waived = [e for e in errors if e["code"] in waived_codes]
    blocking = [e for e in errors if e["code"] not in waived_codes]
    return waived, blocking


def clip_qa_problems(clip):
    """Problems with one clip: <shot folder>/clip_qa.json must exist, then clip_qa.clip_ok decides (clip sha256, a present
    verdict that passes or is accepted by the owner)."""
    clip = Path(clip)
    if not clip.is_file():
        return [f"{clip}: clip file missing"]
    qa_path = clip.parent / "clip_qa.json"
    if not qa_path.is_file():
        return [f"{clip}: no clip_qa.json next to the clip"]
    try:
        return [f"{clip}: {p}" for p in clip_qa.clip_ok(str(qa_path), str(clip))]
    except (ValueError, AttributeError):
        return [f"{qa_path}: not a valid clip_qa.json"]


def lock_rows_for_pack(lock_path, pack):
    """Verified lock rows merged with the pack's shots.json (dialogue, line text) by shot id.
    A stale or invalid lock stops the build."""
    try:
        lock = tli.load_lock(lock_path)
        tli.verify_lock(lock_path, lock["inputs"], lock["params"])
        rows = tli.lock_rows(lock)
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit(f"lock {lock_path}: {exc}") from exc
    pack_rows = {r["id"]: r for r in json.loads((Path(pack) / "shots.json").read_text(encoding="utf-8"))}
    if [r["id"] for r in rows] != list(pack_rows):
        raise SystemExit("lock shots and pack shots.json differ in id or order")
    extra = {sh["id"]: {k: sh[k] for k in ("voice_rest", "silence_ok") if sh.get(k) is not None} for sh in lock["shots"]}
    return [{**pack_rows[r["id"]], **extra[r["id"]], **r} for r in rows]    # M-34: lock_rows drops these two keys


def check_story_trims(h3_shots, rows):
    """The H3 story's trims must be the lock's trims: a shot cut from other timing is refused."""
    if [s["shot_id"] for s in h3_shots] != [r["id"] for r in rows]:
        raise SystemExit("lock shots and H3 story shots differ in id or order")
    for s, r in zip(h3_shots, rows):
        t = s["timing_and_lattice"]
        if (t.get("trim_in_frame"), t.get("trim_out_frame")) != (r["trim_in_frame"], r["trim_out_frame"]):
            raise SystemExit(f"{r['id']}: H3 story trims {t.get('trim_in_frame')}..{t.get('trim_out_frame')} "
                             f"differ from the lock {r['trim_in_frame']}..{r['trim_out_frame']}")


def master_wav_argv(video, wav):
    """ffmpeg argv: the audio of the reel master as 16-bit 48 kHz stereo WAV (gate_d.check_no_silence reads PCM16)."""
    return ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vn", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", str(wav)]


def lra_warnings(lra):
    """LRA above the core delivery limit is a warning only (M-09)."""
    if lra is not None and lra > gd.LOUDNESS["lra"] + 1e-9:
        return [f"LRA {lra} LU above {gd.LOUDNESS['lra']} LU (warn only)"]
    return []


def audio_gate_from_wav(wav):
    """(errors, warnings) of the PRE-MIX clip audio. Errors is always empty: the model's own sound is muted or ducked later (rule
    50(6)), so a quiet clip is not a defect. Every silence finding becomes a CLIP_AUDIO_QUIET warning string."""
    rep = sr.check_wav(wav)
    return [], [f"CLIP_AUDIO_QUIET: {sr.fail_text(f)}" for f in rep["errors"] + rep["warnings"]]


def export_silence_check(export, work_dir, voice_rest=(), silence_ok=(), waived=frozenset()):
    """NO_SILENCE v2 on the REAL per-language master: decode the finished export and run the rule. Returns (blocking, report):
    blocking = findings whose code is not in `waived` (only DEAD_AIR can ever be waived); report is the rule's own dict plus
    "waived". A decode failure blocks."""
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    wav = work / (Path(export).stem + "_master.wav")
    done = subprocess.run(master_wav_argv(export, wav), capture_output=True, text=True)
    if done.returncode != 0 or not wav.is_file():
        err = {"code": "MASTER_DECODE", "where": str(export), "message": f"decode failed: {done.stderr.strip()[:200]}"}
        return [err], {"ok": False, "errors": [err], "warnings": [], "stats": {}, "waived": []}
    rep = sr.check_wav(wav, voice_rest, silence_ok)
    blocking = [e for e in rep["errors"] if e["code"] not in waived or e["code"] in sr.CRITICAL]
    rep["waived"] = [e for e in rep["errors"] if e not in blocking]
    return blocking, rep


def rest_windows(rows):
    """(voice_rest, silence_ok) on the REEL clock from the lock rows: shot-relative [a, b] lists in row["voice_rest"] and
    row["silence_ok"] (blocking sheet, B-10) moved by the row's offset_sec. Rows without the fields give nothing."""
    out = ([], [])
    for r in rows:
        for k, key in enumerate(("voice_rest", "silence_ok")):
            val = r.get(key) or []
            if val and not isinstance(val[0], (list, tuple)):    # the sheet's one [t0, t1] pair, or a list of pairs
                val = [val]
            out[k].extend(sr.reel_windows([tuple(w) for w in val], float(r["offset_sec"])))
    return out


def master_audio_check(video, work_dir):
    """Decodes the reel master's audio to WAV, then runs NO_SILENCE (errors) and the LRA warning (warnings)."""
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    wav = work / "master_audio.wav"
    done = subprocess.run(master_wav_argv(video, wav), capture_output=True, text=True)
    if done.returncode != 0 or not wav.is_file():
        return [f"master audio decode failed: {done.stderr.strip()[:200]}"], []
    errors, warnings = audio_gate_from_wav(wav)
    loud = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav), "-af", "ebur128=peak=true", "-f", "null", "-"],
                          capture_output=True, text=True)
    return errors, warnings + lra_warnings(gd.parse_lra(loud.stderr))


def main(argv=None):
    a = build_arg_parser().parse_args(argv)
    if a.reel in REEL_CLOSED:
        raise SystemExit(f"{a.reel} is closed (rule 53): build_final_reel does not rebuild it")
    pack = Path(a.pack)
    rows = lock_rows_for_pack(a.lock, pack)
    story = json.loads(Path(a.story).read_text(encoding="utf-8"))
    h3_shots = story["episodes"][0]["shots"]
    check_story_trims(h3_shots, rows)
    clips = json.loads(Path(a.clips).read_text(encoding="utf-8"))
    problems = [p for clip in clips.values() for p in clip_qa_problems(clip)]
    if problems:
        raise SystemExit("clip QA blocks the build:\n  " + "\n  ".join(problems))
    waiver_records, waiver_problems = load_waivers(pack, a.reel)
    story_id = a.story_id or story.get("story_id") or pack.name
    if not a.title_cards and not (Path(a.vo) / "vo_tracks_report.json").is_file():
        raise SystemExit(f"missing {Path(a.vo) / 'vo_tracks_report.json'} (build_vo_tracks --out <vo>); "
                         "or pass --title-cards")
    if not a.title_cards and not a.manifest:
        raise SystemExit("--manifest is required (the voice manifest the spoken captions come from); or pass --title-cards")
    out = Path(a.out)
    (out / "export").mkdir(parents=True, exist_ok=True)
    (out / "captions").mkdir(parents=True, exist_ok=True)
    video = out / f"{a.reel}_video.mp4"
    plan = assemble_video(h3_shots, clips, video, out / "assembly")
    audio_errors, audio_warnings = master_audio_check(video, out / "audio_check")
    if audio_errors:
        raise SystemExit("master audio blocks the build:\n  " + "\n  ".join(audio_errors))
    pre_vf = delivery_vf(probe_size(video))
    langs = a.langs.split(",")
    mix, mix_voice = dict(a.mix), dict(a.mix_voice)
    if set(mix) != set(mix_voice) or not set(mix) <= set(langs):
        raise SystemExit("--mix and --mix-voice must name the same languages, each one listed in --langs")
    res = gd.plan_language_outputs(a.reel, langs, a.vo, None, shots=rows, video_path=str(video), video_has_audio=True, burn_captions=True,
                                   captions_dir=str(out / "captions"), export_dir=str(out / "export"), fonts_dir=a.fonts,
                                   voice_engines={lg: "elevenlabs" for lg in langs},
                                   story_gate_checks=story.get("story_gate_checks"))   # absent = closing gate blocks (fail closed)
    report = {"reel": a.reel, "video": str(video), "frames": plan["total_frames"], "seconds": plan["total_duration_sec"],
              "story_id": story_id, "render_version": a.render_version,
              "waiver_problems": [{"waiver_id": wid, "reason": why} for wid, why in waiver_problems], "languages": {}}
    report["master_audio"] = {"errors": audio_errors, "warnings": audio_warnings}
    stop = False
    ocr_cards = json.loads(Path(a.ocr).read_text(encoding="utf-8")) if a.ocr else None
    for lg in langs:
        rep, lp = res["reports"][lg], res["languages"][lg]
        codes = [e["code"] for e in rep["errors"]]
        waived_map, blocking_codes = wv.split_waived(codes, waiver_records, story_id, a.reel, LANG_NAME.get(lg, lg), a.render_version)
        waived = [{**e, "waiver_ids": waived_map[e["code"]]} for e in rep["errors"] if e["code"] in waived_map]
        blocking = [e for e in rep["errors"] if e["code"] in blocking_codes]
        entry = {"waived_findings": waived, "blocking_errors": blocking, "warnings": rep["warnings"]}
        report["languages"][lg] = entry
        if blocking:
            stop = True
            continue
        ass = out / "captions" / f"{a.reel}_{lg}.ass"
        report_path = Path(a.vo) / "vo_tracks_report.json"      # one report for all languages (build_vo_tracks --out <vo>)
        if a.title_cards:
            cues = lp["captions"]                       # the writer's title cards (old behaviour, only on request)
            srt_cues = cues
        else:
            vo_json, mrows = json.loads(report_path.read_text(encoding="utf-8")), load_manifest_rows(a.manifest, lg)
            cues = spoken_cues_real(rows, vo_json, lg, mrows, Path(a.fonts) / CAPTION_FONT_FILE)   # captions = the spoken words, hash-checked (D-VOICE)
            srt_cues = srt_line_cues(line_captions(rows, vo_json, lg, mrows))     # YouTube SRT: one block per spoken line (B-07)
        for msg in gd.script_problems(cues, lg) if hasattr(gd, "script_problems") else []:
            raise SystemExit(f"{lg}: {msg}")
        ass_text, entries = gd.build_captions(cues, lang=lg, pack=CAPTION_PACK, fonts_dir=a.fonts)
        fails = [e["message"] for e in entries if e["level"] == "FAIL"]
        if fails:
            raise SystemExit(f"{lg} captions: " + "; ".join(fails))
        ass.write_text(ass_text if cues is lp["captions"] else caption_ass(cues, lg, a.fonts), encoding="utf-8", newline="\n")
        entry["caption_warnings"] = sorted({e["message"] for e in entries if e["level"] == "WARN"})[:6]
        entry["captions"] = {"cues": len(cues), "mode": "title cards" if cues is lp["captions"] else "spoken words"}
        if ocr_cards is not None:                      # G22: text-card QA, only when the OCR of the card frames is given
            card_problems = tcq.check_cards(ocr_cards, lg)
            entry["text_card_qa"] = {"ok": not card_problems, "problems": card_problems}
            if card_problems:
                entry["blocking_errors"].append({"code": "TEXT_CARD_QA", "where": lg, "message": "; ".join(card_problems)[:300]})
                stop = True
                continue
        export = next_export(out / "export", a.reel, lg)
        waived_map, _ = wv.split_waived(["DEAD_AIR"], waiver_records, story_id, a.reel, LANG_NAME.get(lg, lg), a.render_version)
        silence_waived, rest = frozenset(waived_map), rest_windows(rows)
        if lg in mix:
            offs = {r["id"]: float(r["offset_sec"]) for r in rows}
            vo_report = json.loads(report_path.read_text(encoding="utf-8"))
            windows = [{"offset_sec": offs[r["shot"]], "lines": r["lines"]} for r in vo_report if r["lang"] == lg and r["shot"] in offs]
            total_frames = round(sum(float(r["editorial_duration_sec"]) for r in rows) * gd.FPS)
            info = intake(mix[lg], mix_voice[lg], total_frames, windows, work_dir=out / "mix", voice_rest=rest[0],
                          silence_ok=rest[1], waived=silence_waived)
            entry["mix"] = info
            total = info["samples"] / MIX_RATE
            argv_ = gd.build_final_mux_argv(video, [info["trimmed_path"]], mix_filter_text(info["samples"]), export, burn_captions=True,
                                            ass_path=ass, fonts_dir=a.fonts, pre_vf=pre_vf)
        else:
            vo_rep = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else []
            policy, levels = sfx_policy_for(rows, clips, a.vo, lg, vo_rep)
            bed_errors = gd.check_sfx_beds(levels)
            if bed_errors:
                raise SystemExit(f"{lg} SFX beds: " + "; ".join(e["message"] for e in bed_errors))
            argv_, total = mux_argv(rows, lg, a.vo, video, export, ass, a.fonts, pre_vf=pre_vf, sfx_policy=policy)
        argv_ = clean_argv(argv_, pre_vf)                # G15: the default export carries no burned captions
        check_free_disk(out / "export")
        subprocess.run(argv_, check=True, cwd=str(HERE.parent))
        loud = correct_loudness(export, measure(export))
        entry.update(export=str(export), seconds=round(total, 2), loudness=loud["stats"], loudness_ok=loud["ok"], loudness_errors=loud["errors"])
        # NO_SILENCE v2 on what the viewer hears: the finished export, decoded (E5)
        bad, silence = export_silence_check(export, out / "audio_check", rest[0], rest[1], silence_waived)
        entry["silence"] = silence
        if bad:
            rejected = export.with_name(export.stem + "_REJECTED" + export.suffix)
            export.replace(rejected)
            entry["export"] = str(rejected)
            entry["blocking_errors"] += bad
            stop = True
            continue
        if a.burned_captions:                           # explicit flag only: burned copy, same audio stream
            burned = export.with_name(export.stem + "_burned" + export.suffix)
            subprocess.run(burned_from_clean_argv(export, burned, ass, a.fonts), check=True, cwd=str(HERE.parent))
            entry["burned_export"] = str(burned)
            entry["audio_sha256"], burned_sha = audio_sha256(export), audio_sha256(burned)
            if burned_sha != entry["audio_sha256"]:
                entry["blocking_errors"].append({"code": "AUDIO_SHA_MISMATCH", "where": lg,
                                                 "message": "burned export audio differs from the clean export"})
                stop = True
                continue
        if srt_cues:                                    # next to the export, same name and version, written only after success
            srt = export.with_suffix(".srt")
            entry["srt_path"], entry["srt_sha256"] = str(srt), write_srt(srt_cues, srt)
    (out / f"{a.reel}_build_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    for lg, e in report["languages"].items():
        print(lg, "BLOCKED" if e["blocking_errors"] else "built", "| waived:", sorted({w["code"] for w in e["waived_findings"]}),
              "| loudness ok:", e.get("loudness_ok"), "|", e.get("export", ""))
        for b in e["blocking_errors"]:
            print("  BLOCK", b["code"], b["where"], str(b["message"])[:160])
    return 1 if stop else 0


if __name__ == "__main__":
    sys.exit(main())
