"""WP8 post: grade, impacts, captions, encode and final gates for one episode build dir.

CLI:
  python director/post.py EPISODE_BUILD_DIR --story stories/<slug>/story.json [--episode-json PATH]
      [--styles-dir DIR] [--fonts-dir DIR] [--upscale-cmd "CMD {in} {out}"] [--out FILE]
      [--no-captions] [--no-sidecars] [--platform reels|shorts|youtube] [--language en|hi|mr] [--voice elevenlabs|h3] [--vo-dir DIR] [--dry-run]

EPISODE_BUILD_DIR layout:
  episode.json          h3 episode {"episode_id", "shots": [h3 shots]}; --episode-json overrides the path
  <shot_id>/clip.mp4    one clip per shot
  loudness.json         optional, from h3.assemble_reel.write_loudness_json
Output: <build>/<episode_id>_final.mp4 (or --out). Work files go to <build>/post/.
colour_report.json is written to the build dir on every real run, also when refusing.
Shot fields read: shot_id, timing_and_lattice (fps, trim_in_frame, trim_out_frame, editorial_frames,
trim_in_sec, trim_out_sec, editorial_duration_sec), metadata.look (act, hook, impact_frames),
optional metadata.captions ([{t0, t1, text, latin?, emphasis?, words?}] in shot-editorial seconds; words = aligned
words for karaoke), and metadata.look.hook.emphasis (list of hook words drawn larger in the emphasis colour).
Caption language (owner rule 2026-11-07): one reel per output language. English gets English captions, Hindi Hindi,
Marathi Marathi, and the text is the SPOKEN script of that language (the voice: H3 for English, ElevenLabs for Hindi and
Marathi). When the shots carry audio_and_dialogue_track, the cues come from h3.gate_d_audio.caption_cues (captions_by_lang
wins, else the narration and dialogue text of the language, on the shot's time_range). Only without a spoken script does
post fall back to the hook caption and metadata.captions, with a WARN. A caption in the wrong script is a FAIL:
Devanagari in an English reel, or no Devanagari in a Hindi or Marathi reel. --language overrides story.json language and
names the output <episode>_final_<lang>.mp4.
Voice (owner brief 2026-11-07): --voice elevenlabs (default; story.json voice_engine[lang] is used when --voice is not given)
or h3. H3 speech is English only (VE-01): --voice h3 for hi or mr is a FAIL. With elevenlabs, every shot that has narration or
dialogue in the language needs <vo-dir>/<lang>/<shot_id>.wav (default <build>/audio/vo); a missing file is a FAIL naming it,
never a fallback to the H3 audio. The voice is the only speech of the reel: the H3 clips' own audio stays as the SFX bed,
ducked under the voice, and the mix goes through the same loudnorm chain as Gate D (build_voice_branch). The audio is built
in the same graph as the picture, before the captions are burned. With --voice h3 (English only) the H3 audio is kept.
Grading: an act with neither a LUT file nor grade numbers exports ungraded; this is a prominent POST-UNGRADED warning and
colour_report.json carries graded: false (and graded_by_act).
Captions: --platform picks core.safe_zone_templates (default: core.safe_zone_frac); the fonts dir is used to measure and
wrap the text (at most 2 lines) and to check every glyph; a real run first checks that ffmpeg has libass and HarfBuzz and,
after the final file is written, writes <final>.<lang>.srt and .vtt next to it (--no-sidecars turns that off).

run_post() never raises: bad input becomes a POST FAIL entry. A dry run starts no subprocess and writes no file.
"""
import argparse
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
for _p in (_REPO, _HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from PIL import Image  # noqa: E402

from clip_tools import gates, last_frame, probe  # noqa: E402
from core.caption_cues import KIND_HOOK, KIND_SPOKEN, build_cue_list, hook_of, script_problems, spoken_cues  # noqa: E402
from core.caption_export import ffmpeg_preflight, write_sidecars  # noqa: E402
from core.captions import build_ass  # noqa: E402
from core.flash_check import REPORT_HEADER, check_flash  # noqa: E402
from core.frame_metrics import extract_frames, mean_lab  # noqa: E402
from core.lut import (act_reference_lab, apply_cube, combine, grade_fn, identity_fn,  # noqa: E402
                      parse_cube, shot_match_fn, shot_match_offset, write_cube)
from core.style_pack import delta_e_2000, load_core, load_pack, validate_pack  # noqa: E402
from h3.assemble_reel import _audio_chain, colour_seams, load_loudness_plan  # noqa: E402
from h3.gate_d_audio import build_vo_stem_filter, build_voice_branch, shot_has_speech, vo_fit_check  # noqa: E402

SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
HEX = re.compile(r"^#?[0-9A-Fa-f]{6}$")
TIMING_KEYS = ("fps", "trim_in_frame", "trim_out_frame", "editorial_frames",
               "trim_in_sec", "trim_out_sec", "editorial_duration_sec")
IMPACT_TYPES = ("white_out", "black_out", "inverted", "chroma_split", "alpha_sil")
DRY_WIDTH, DRY_HEIGHT = 1080, 1920   # dry run cannot probe clips; these stand in for the render size
LUT_SIZE = 33
TAIL = 800


def _entry(rule, level, message, shot=None):
    return {"rule": rule, "level": level, "shot": shot, "episode": None, "message": message}


def _tail(text, n=TAIL):
    text = (text or "").strip()
    return text[-n:] if len(text) > n else text


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _read_json(path, label):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"{label} unreadable: {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object")
    return data


def _shot_facts(shot):
    """Checked fields of one h3 shot. ValueError names what is missing or wrong."""
    if not isinstance(shot, dict):
        raise ValueError("shot entry is not an object")
    sid = shot.get("shot_id")
    if not isinstance(sid, str) or not SAFE_ID.match(sid):
        raise ValueError(f"shot_id missing or not a plain name: {sid!r}")
    t = shot.get("timing_and_lattice") if isinstance(shot.get("timing_and_lattice"), dict) else {}
    meta = shot.get("metadata") if isinstance(shot.get("metadata"), dict) else {}
    look = meta.get("look") if isinstance(meta.get("look"), dict) else None
    missing = [f"timing_and_lattice.{k}" for k in TIMING_KEYS if k not in t]
    if look is None:
        missing.append("metadata.look")
    elif not isinstance(look.get("act"), str):
        missing.append("metadata.look.act")
    if missing:
        raise ValueError(f"shot {sid} is missing {', '.join(missing)}")
    bad = [k for k in ("fps", "trim_in_frame", "trim_out_frame", "editorial_frames") if not _is_int(t[k])]
    bad += [k for k in ("trim_in_sec", "trim_out_sec", "editorial_duration_sec") if not _num(t[k])]
    if bad:
        raise ValueError(f"shot {sid}: not numbers: {', '.join(bad)}")
    ti, to, ed = t["trim_in_frame"], t["trim_out_frame"], t["editorial_frames"]
    if ti < 0 or to <= ti or ed < 1 or to - ti != ed:
        raise ValueError(f"shot {sid}: need 0 <= trim_in < trim_out and trim_out - trim_in == editorial_frames")
    raw_imp = look.get("impact_frames") or []
    if not isinstance(raw_imp, list):
        raise ValueError(f"shot {sid}: metadata.look.impact_frames must be a list")
    impacts = []
    for n, imp in enumerate(raw_imp):
        if (not isinstance(imp, dict) or not _num(imp.get("at_s")) or imp["at_s"] < 0
                or not isinstance(imp.get("type"), str) or not _is_int(imp.get("frames")) or imp["frames"] < 1):
            raise ValueError(f"shot {sid}: impact_frames[{n}] needs at_s >= 0, a type and frames >= 1")
        impacts.append({"at_s": float(imp["at_s"]), "type": imp["type"], "frames": imp["frames"]})
    hook = look.get("hook")
    caption = hook.get("caption") if isinstance(hook, dict) else None
    emph = hook.get("emphasis") if isinstance(hook, dict) and isinstance(hook.get("emphasis"), list) else []
    caps = meta.get("captions") or []
    if not isinstance(caps, list):
        raise ValueError(f"shot {sid}: metadata.captions must be a list")
    return {"sid": sid, "ti": ti, "to": to, "ed": ed, "t": t, "act": look["act"], "impacts": impacts,
            "hook_caption": caption if isinstance(caption, str) else None, "hook_emphasis": emph, "captions": caps,
            "raw": shot}


def _split_cmd(cmd):
    if os.name == "nt":   # POSIX shlex would eat the backslashes of Windows paths
        parts = shlex.split(cmd, posix=False)
        parts = [p[1:-1] if len(p) >= 2 and p[0] == p[-1] == '"' else p for p in parts]
    else:
        parts = shlex.split(cmd)
    if not parts:
        raise ValueError("upscale command is empty")
    return parts


def _flash_colours(pack):
    fc = pack.get("flash_colours") if isinstance(pack.get("flash_colours"), dict) else {}
    out = {}
    for key, default in (("white", "#FFFFFF"), ("black", "#000000")):
        v = fc.get(key, default)
        if not isinstance(v, str) or not HEX.match(v):
            raise ValueError(f"flash_colours.{key} must be a #RRGGBB colour")
        out[key] = "0x" + v.lstrip("#").upper()
    return out


def _impact_filter(kind, a, b, flash, chroma_px):
    en = f"enable='between(n,{a},{b})'"
    if kind in ("white_out", "black_out"):
        return f"drawbox=x=0:y=0:w=iw:h=ih:color={flash[kind.split('_')[0]]}:t=fill:{en}"
    if kind == "inverted":
        return f"negate:{en}"
    if kind == "chroma_split":
        return f"rgbashift=rh={-chroma_px}:bh={chroma_px}:{en}"
    return None


def _act_fn(pack, act, styles):
    """(fn, note): the act's .cube when it exists, else grade_fn(act.grade), else identity (note set)."""
    acts = pack.get("acts") if isinstance(pack.get("acts"), dict) else {}
    a = acts.get(act)
    if not isinstance(a, dict):
        return identity_fn, f"act {act!r} is not in the pack: identity grade"
    rel = a.get("lut")
    if isinstance(rel, str) and rel and (styles / rel).is_file():
        cube = parse_cube(styles / rel)
        table, size = cube["table"], cube["size"]
        return (lambda r, g, b: apply_cube(table, size, (r, g, b))), None
    if isinstance(a.get("grade"), dict):
        return grade_fn(a["grade"]), None
    return identity_fn, f"act {act!r} has no LUT file or grade: identity grade"


def _frame_lab(path):
    with Image.open(path) as im:
        return mean_lab(im.convert("RGB"))


def _clip_mean_lab(clip, ti, ed, work):
    """Mean Lab over about 8 sampled editorial frames of one clip (trim_in .. trim_out)."""
    shutil.rmtree(work, ignore_errors=True)
    step = max(1, ed // 8)
    frames = extract_frames(clip, work, scale=0.25, every=step, start=ti, count=math.ceil(ed / step))
    labs = [_frame_lab(p) for idx, p in frames if idx < ti + ed]
    if not labs:
        raise RuntimeError(f"no editorial frames could be read from {Path(clip).name}")
    return tuple(sum(lab[i] for lab in labs) / len(labs) for i in range(3))


def _rel(path, base):
    return Path(os.path.relpath(str(path), str(base))).as_posix()


def _version_line():
    r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout.splitlines() or [None])[0]


def _with_post_shot(entries):
    """Caption entries already carry rule, level, shot and episode; make sure the keys exist for the report."""
    return [dict({"shot": None, "episode": None}, **e) for e in entries]


def _extra_captions(facts, fps, entries):
    """metadata.captions of every shot (shot-editorial seconds) on the episode clock: the explicit caption list used when the
    shots carry no spoken script. Malformed rows are skipped with a WARN."""
    cues = []
    for f in facts:
        offset = f["start"] / fps
        for n, c in enumerate(f["captions"]):
            if not (isinstance(c, dict) and _num(c.get("t0")) and _num(c.get("t1")) and isinstance(c.get("text"), str)):
                entries.append(_entry("POST", "WARN", f"shot {f['sid']}: metadata.captions[{n}] is not {{t0, t1, text}}; skipped"))
                continue
            words = c.get("words") if isinstance(c.get("words"), list) else None
            if words:   # aligned words are in shot-editorial seconds like the cue: shift them to episode time
                words = [dict(w, t0=w["t0"] + offset, t1=w["t1"] + offset)
                         if isinstance(w, dict) and _num(w.get("t0")) and _num(w.get("t1")) else w for w in words]
            cues.append({"t0": c["t0"] + offset, "t1": c["t1"] + offset, "text": c["text"], "kind": KIND_SPOKEN,
                         "latin": c.get("latin"), "emphasis": c.get("emphasis"), "words": words})
    return cues


def _caption_cue_list(facts, fps, language, entries):
    """The cue list that is burned and written to SRT and WebVTT, built by the shared caption engine
    (core/caption_cues.py): the spoken script of the language, plus the hook caption on frame 1 under the hook policy.
    Returns (cues, spoken_from_track)."""
    shots = [f["raw"] for f in facts]
    offsets = [f["start"] / fps for f in facts]
    first = facts[0]
    from_track = any(isinstance(s.get("audio_and_dialogue_track"), dict) for s in shots)
    spoken = spoken_cues(shots, offsets, language) if from_track else []
    if not spoken:
        spoken = _extra_captions(facts, fps, entries)
    hook_text, hook_dur = hook_of(first["raw"], language)
    cues, hook_entries = build_cue_list(spoken, hook_text, hook_end=round(first["ed"] / fps, 3), hook_duration=hook_dur)
    entries.extend(_with_post_shot(hook_entries))
    for c in cues:
        if c["kind"] == KIND_HOOK:
            c["emphasis"] = first["hook_emphasis"]
    return cues, bool(from_track and any(c["kind"] == KIND_SPOKEN for c in cues))


def _write_colour_report(build, report):
    doc = {"episode": report["episode"], "fail": report["fail"], "written": report["written"],
           "output": report["output"], "steps": report["steps"], "entries": report["entries"],
           "graded": report.get("graded"), "graded_by_act": report.get("graded_by_act"), "voice": report.get("voice"),
           "flash_note": REPORT_HEADER, "ffmpeg": report["ffmpeg"]}
    try:
        build.mkdir(parents=True, exist_ok=True)
        (build / "colour_report.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n",
                                                  encoding="utf-8")
    except OSError as exc:
        report["entries"].append(_entry("POST", "FAIL", f"could not write colour_report.json: {exc}"))
        report["fail"] = True


def run_post(build_dir, story_path, *, episode_json=None, styles_dir=None, fonts_dir=None, upscale_cmd=None,
             out=None, captions=True, dry_run=False, platform=None, sidecars=True, language=None, voice=None,
             vo_dir=None):
    """Grade, insert impacts, caption, encode and gate one episode. Returns the report dict."""
    report = {"episode": None, "fail": False, "written": False, "output": None, "steps": [], "entries": [],
              "flash_note": REPORT_HEADER, "ffmpeg": None, "graph": "", "commands": [], "dry_run": bool(dry_run)}
    build = Path(build_dir)
    try:
        _run(build, report, story_path, episode_json, styles_dir, fonts_dir, upscale_cmd, out, captions, dry_run,
             platform, sidecars, language, voice, vo_dir)
    except Exception as exc:  # the CLI never prints a traceback
        report["entries"].append(_entry("POST", "FAIL", f"unexpected error: {type(exc).__name__}: {exc}"))
    report["fail"] = report["fail"] or any(e["level"] == "FAIL" for e in report["entries"])
    if not dry_run:
        _write_colour_report(build, report)
    return report


def _run(build, report, story_path, episode_json, styles_dir, fonts_dir, upscale_cmd, out, captions, dry_run,
         platform=None, sidecars=True, language_override=None, voice_arg=None, vo_dir=None):
    entries, steps = report["entries"], report["steps"]

    def fail(msg, shot=None):
        entries.append(_entry("POST", "FAIL", msg, shot))

    def warn(msg, shot=None):
        entries.append(_entry("POST", "WARN", msg, shot))

    styles = Path(styles_dir) if styles_dir else _REPO / "styles"
    fonts = Path(fonts_dir) if fonts_dir else styles / "fonts"
    post = build / "post"
    core = load_core()
    delivery = core["delivery"]

    try:
        story = _read_json(story_path, "story.json")
        pack_id = story.get("style_pack")
        if not isinstance(pack_id, str):
            raise ValueError("story.json needs a string style_pack")
        language = story.get("language") if isinstance(story.get("language"), str) else "hi"
        if language_override is not None:
            if language_override not in ("en", "hi", "mr"):
                raise ValueError(f"--language must be en, hi or mr, got {language_override!r}")
            language = language_override
        pack = load_pack(pack_id, styles_dir=styles_dir)
    except ValueError as exc:
        fail(str(exc))
        return
    pack_errors = validate_pack(pack)
    if pack_errors:
        for msg in pack_errors:
            fail(f"style pack invalid: {msg}")
        return
    try:
        flash = _flash_colours(pack)
    except ValueError as exc:
        fail(str(exc))
        return

    ep_path = Path(episode_json) if episode_json else build / "episode.json"
    try:
        ep = _read_json(ep_path, ep_path.name)
    except ValueError as exc:
        fail(str(exc))
        return
    episode_id = ep.get("episode_id")
    report["episode"] = episode_id
    if not isinstance(episode_id, str) or not SAFE_ID.match(episode_id):
        fail("episode.json needs a plain episode_id string")
        return
    shots = ep.get("shots")
    if not isinstance(shots, list) or not shots:
        fail("episode.json needs a non-empty shots list")
        return

    facts, bad = [], False
    for idx, shot in enumerate(shots):
        try:
            facts.append(_shot_facts(shot))
        except ValueError as exc:
            fail(f"shot {idx}: {exc}")
            bad = True
    if len({f["sid"] for f in facts}) != len(facts):
        fail("duplicate shot_id in episode.json")
        bad = True
    if bad:
        return

    fps = core["fps"]
    for f in facts:
        if f["t"]["fps"] != fps:
            fail(f"timing fps {f['t']['fps']} differs from core fps {fps}", f["sid"])
            return
        clip = build / f["sid"] / "clip.mp4"
        if not clip.is_file():
            fail(f"clip missing: {clip}", f["sid"])
            bad = True
    if bad:
        return
    try:
        loud = load_loudness_plan(str(build / "loudness.json")) or {}
    except ValueError as exc:
        fail(str(exc))
        return

    cum = 0
    for f in facts:
        f["start"] = cum
        cum += f["ed"]
        acts = pack.get("acts") if isinstance(pack.get("acts"), dict) else {}
        a = acts.get(f["act"])
        if not isinstance(a, dict):
            warn(f"act {f['act']!r} is not in the pack: no grain", f["sid"])
        f["grain"] = isinstance(a, dict) and a.get("grain") is True
    total = cum
    steps.append(f"{len(facts)} shots, {total} editorial frames at {fps} fps")

    suffix = f"_{language_override}" if language_override else ""
    report["output"] = os.path.abspath(str(out) if out else build / f"{episode_id}_final{suffix}.mp4")
    final = Path(report["output"])
    tmp_name = f"{final.stem}.tmp.mp4"

    if dry_run:
        width, height = DRY_WIDTH, DRY_HEIGHT
        steps.append(f"dry run: size {width}x{height} assumed; nothing is run or written")
    else:
        try:
            info = probe(build / facts[0]["sid"] / "clip.mp4")
            width, height = info["width"], info["height"]
        except (subprocess.CalledProcessError, OSError, KeyError, ValueError, IndexError) as exc:
            fail(f"could not probe the first clip: {exc}", facts[0]["sid"])
            return
    chroma_px = max(1, round(8 * width / 1080))
    work = {f["sid"]: build / f["sid"] / "clip.mp4" for f in facts}

    # 1. optional upscale (never through a shell)
    if upscale_cmd:
        try:
            argv_t = _split_cmd(upscale_cmd)
        except ValueError as exc:
            fail(str(exc))
            return
        for f in facts:
            dst = post / "up" / f"{f['sid']}.mp4"
            argv = [a.replace("{in}", str(work[f["sid"]])).replace("{out}", str(dst)) for a in argv_t]
            report["commands"].append(argv)
            if dry_run:
                work[f["sid"]] = dst
                continue
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace")
            except OSError as exc:
                fail(f"upscale could not start for {f['sid']}: {exc}", f["sid"])
                return
            if r.returncode != 0 or not dst.is_file():
                fail(f"upscale failed for {f['sid']}: {_tail(r.stderr)}", f["sid"])
                return
            work[f["sid"]] = dst
        steps.append("upscale: " + ("planned" if dry_run else "done"))

    if not dry_run:
        post.mkdir(parents=True, exist_ok=True)

    # 2. G2 per clip (as it sits in the episode)
    if not dry_run:
        for f in facts:
            rep = gates(work[f["sid"]], dict(f["raw"], id=f["sid"]), story, out_dir=post / "gates",
                        styles_dir=styles_dir)
            entries.extend(rep["entries"])
        steps.append("G2 per clip")

    # 3. shot match and per-shot combined LUT
    clamp = core["gates"]["shot_match_clamp_de"]
    graded = {}
    for f in facts:
        sid = f["sid"]
        ref = act_reference_lab(pack, f["act"])
        offset = (0.0, 0.0, 0.0)
        if not dry_run:
            try:
                mean = _clip_mean_lab(work[sid], f["ti"], f["ed"], post / "frames" / sid)
            except (RuntimeError, ValueError, OSError) as exc:
                fail(f"shot match could not measure the clip: {exc}", sid)
                return
            offset = shot_match_offset(mean, ref, clamp)
        act_fn, note = _act_fn(pack, f["act"], styles)
        graded[f["act"]] = note is None
        if note:
            warn(note, sid)
        f["lut"] = f"luts/{sid}.cube"
        if not dry_run:
            write_cube(post / f["lut"], combine(shot_match_fn(offset), act_fn), size=LUT_SIZE,
                       title="shot match + act (generated)")
    steps.append("shot match and act LUTs" + (" planned" if dry_run else " written"))
    report["graded_by_act"] = dict(graded)
    report["graded"] = all(graded.values())
    if not report["graded"]:
        ungraded = sorted(a for a, ok in graded.items() if not ok)
        entries.append(_entry("POST-UNGRADED", "WARN", "UNGRADED EXPORT: no LUT file and no grade numbers for act(s) "
                              + ", ".join(ungraded) + "; this reel is NOT graded (colour_report.json: graded false)"))

    # 3b. the voice of this language (before the graph, so the audio is final before the captions are burned)
    voice = voice_arg or (story.get("voice_engine") or {}).get(language) if isinstance(story.get("voice_engine"), dict) \
        else voice_arg
    voice = voice or "elevenlabs"
    report["voice"] = {"engine": voice, "language": language, "vo_files": []}
    vo_refs, vo_inputs = None, []
    if voice not in ("elevenlabs", "h3"):
        fail(f"--voice must be elevenlabs or h3, got {voice!r}")
        return
    if voice == "h3" and language != "en":
        fail(f"VE-01 H3 speech is English only: a {language} reel must use the elevenlabs voice")
        return
    if voice == "elevenlabs":
        vdir = Path(vo_dir) if vo_dir else build / "audio" / "vo"
        speech = [shot_has_speech(f["raw"], language) for f in facts]
        if not any(speech):
            warn(f"no {language} narration or dialogue on any shot: the H3 audio is kept (no voice mix)")
        else:
            vo_refs, existing, missing = [], [], []
            for f, sp in zip(facts, speech):
                ed = f["ed"] / fps
                if not sp:
                    vo_refs.append((None, ed))
                    continue
                path = vdir / language / f"{f['sid']}.wav"
                if not path.is_file():
                    missing.append(str(path))
                    continue
                vo_inputs.append(path)
                vo_refs.append((len(facts) + len(vo_inputs) - 1, ed))
                existing.append({"shot_id": f["sid"], "wav_path": str(path), "editorial_duration_sec": ed})
            for m in missing:
                fail(f"VO_MISSING: no {language} voice file at {m}; the export is refused, never a fallback to the H3 audio")
            if missing:
                return
            for e in vo_fit_check(existing)["errors"]:
                fail(f"{e['code']}: {e['message']}", e["where"])
            report["voice"]["vo_files"] = [str(x) for x in vo_inputs]
            steps.append(f"voice: {language} {voice}, {len(vo_inputs)} file(s), mixed before the captions")

    # 4. video and audio graph (16-bit until the one conversion)
    parts, inputs = [], []
    for i, f in enumerate(facts):
        # The explicit scale does the RGB conversion, so ffmpeg inserts no auto_scale (A13). Input matrix and range
        # are the delivery values (bt709, tv); untagged clips are assumed to match (OPEN_QUESTION).
        v = (f"[{i}:v]trim=start_frame={f['ti']}:end_frame={f['to']},setpts=PTS-STARTPTS,"
             f"scale=in_color_matrix={delivery['colorspace']}:in_range={delivery['color_range']},"
             f"format=gbrp16le,lut3d=file={f['lut']}")
        if f["grain"]:
            v += ",noise=alls=2:allf=t"
        parts.append(f"{v}[v{i}]")
        parts.append(_audio_chain(i, f["t"], loud.get(f["sid"])))
    n = len(facts)
    audio_label = "asfx" if vo_refs else "aout"
    parts.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vcat][{audio_label}]")
    if vo_refs:
        total = sum(ed for _, ed in vo_refs)
        a_cfg = delivery["audio"]
        parts.append(build_vo_stem_filter(vo_refs))
        parts.extend(build_voice_branch("asfx", "vo_full", None, total, "aout", a_cfg["lufs"], a_cfg["loudnorm_tp_db"], a_cfg["lra"]))
    try:
        for f in facts:
            inputs += ["-i", _rel(work[f["sid"]], post)]
        for wav in vo_inputs:
            inputs += ["-i", _rel(wav, post) if not os.path.isabs(str(wav)) else str(wav)]
    except ValueError as exc:
        fail(f"clip path cannot be made relative to post/: {exc}")
        return

    # 5. impacts: replace frames on the episode timeline, 16-bit
    cur, k = "vcat", 0
    for f in facts:
        for imp in f["impacts"]:
            kind = imp["type"]
            if kind not in IMPACT_TYPES:
                warn(f"unknown impact type {kind!r} skipped", f["sid"])
                continue
            if kind == "alpha_sil":
                warn("POST alpha_sil needs a manual edit (not automated)", f["sid"])
                continue
            a = f["start"] + round(imp["at_s"] * fps)
            b = a + imp["frames"] - 1
            parts.append(f"[{cur}]{_impact_filter(kind, a, b, flash, chroma_px)}[vi{k}]")
            cur = f"vi{k}"
            k += 1
    steps.append(f"impacts: {k} filters")

    # 6. the ONE conversion to 8-bit (A13), then captions on 8-bit
    cs, rng, pix = delivery["colorspace"], delivery["color_range"], delivery["pix_fmt"]
    cues = []
    if captions:
        try:
            cues, from_track = _caption_cue_list(facts, fps, language, entries)
        except (ValueError, TypeError, KeyError) as exc:
            fail(f"captions of {language} could not be built: {exc}")
            cues, from_track = [], False
        if from_track:
            steps.append(f"captions: spoken {language} script, {len(cues)} cue(s)")
        elif cues:
            warn(f"no spoken {language} script on the shots: captions are the hook caption and metadata.captions")
        for msg in script_problems(cues, language):   # the one script validator (core/caption_cues.py)
            fail(msg)
    burn = bool(captions and cues)
    parts.append(f"[{cur}]scale=out_color_matrix={cs}:out_range={rng}:flags=accurate_rnd+full_chroma_int"
                 f":sws_dither=ed,format={pix}[{'vconv' if burn else 'vout'}]")
    cap_text = None
    if captions:
        if not cues:
            warn("no captions to burn in", None)
        else:
            has_font = fonts.is_dir() and any(p.suffix.lower() in (".ttf", ".otf", ".ttc")
                                              for p in fonts.iterdir())
            cap_text, cap_entries = build_ass(cues, pack, core, width, height, language,
                                              font_dir=fonts if has_font else None, template=platform)
            entries.extend(cap_entries)
            if not dry_run:   # one ffmpeg -buildconf query; a dry run starts no subprocess
                entries.extend(_with_post_shot(ffmpeg_preflight()))
            opt = ""
            if not has_font:
                warn(f"POST fonts missing in {fonts}: libass falls back", None)
            else:
                try:
                    opt = f":fontsdir={_rel(fonts, post)}"
                except ValueError as exc:
                    warn(f"fonts dir cannot be made relative to post/: {exc}", None)
            parts.append(f"[vconv]subtitles=captions.ass{opt}[vout]")
    steps.append("captions: " + ("planned" if burn else "none"))

    graph = ";\n".join(parts)
    report["graph"] = graph
    d = delivery
    argv = (["ffmpeg", "-y", "-v", "error"] + inputs
            + ["-filter_complex_script", "graph.txt", "-map", "[vout]", "-map", "[aout]",
               "-c:v", d["codec"], "-crf", str(d["crf"]), "-pix_fmt", d["pix_fmt"],
               "-colorspace", d["colorspace"], "-color_primaries", d["color_primaries"],
               "-color_trc", d["color_trc"], "-color_range", d["color_range"],
               # -color_trc / -color_primaries alone leave the stream tags "unknown" on ffmpeg 8; the VUI
               # parameters write the three bt709 tags (A17 delivery check).
               "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709:fullrange=off",
               "-c:a", d["audio"]["codec"], "-b:a", d["audio"]["bitrate"], "-movflags", "+faststart",
               tmp_name])
    report["commands"].append(argv)
    if dry_run:
        steps.append("dry run: graph and commands planned, nothing run or written")
        return

    # ---- real run from here ----
    (post / "graph.txt").write_text(graph + "\n", encoding="utf-8", newline="\n")
    if burn:
        (post / "captions.ass").write_text(cap_text, encoding="utf-8", newline="\n")
    try:
        report["ffmpeg"] = _version_line()
    except OSError as exc:
        warn(f"ffmpeg -version failed: {exc}")
    r = subprocess.run(argv, cwd=str(post), capture_output=True, text=True, encoding="utf-8", errors="replace")
    tmp = post / tmp_name
    if r.returncode != 0:
        tmp.unlink(missing_ok=True)
        fail(f"ffmpeg encode failed: {_tail(r.stderr)}")
        return
    steps.append("encoded " + tmp_name)

    # 7. final gates on the assembled episode (A18, A21)
    try:
        entries.extend(check_flash(tmp, core=core))
    except (RuntimeError, ValueError, OSError) as exc:
        fail(f"flash check could not run: {exc}")
    clips = [work[f["sid"]] for f in facts]
    entries.extend(colour_seams(clips, [f["raw"] for f in facts], core))
    steps.append("F1, F2, G3 run")
    try:
        seam = post / "seam"
        shutil.rmtree(seam, ignore_errors=True)
        first = extract_frames(tmp, seam / "first", scale=0.25, count=1)[0][1]
        last = last_frame(tmp, seam / "last.png")
        de = delta_e_2000(_frame_lab(first), _frame_lab(last))
        limit = core["gates"]["loop_seam_de2000_max"]
        if de > limit:
            entries.append(_entry("G5", "WARN", f"loop seam dE2000 {de:.2f} > {limit:g} (last vs first frame)"))
        steps.append(f"G5 loop seam dE2000 {de:.2f}")
    except (RuntimeError, ValueError, OSError, IndexError) as exc:
        fail(f"loop seam check could not run: {exc}")

    # 8. refuse or write
    if any(e["level"] == "FAIL" for e in entries):
        tmp.unlink(missing_ok=True)
        report["written"] = False
        steps.append("refused: a FAIL entry exists; no final file written")
    else:
        final.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp), str(final))
        report["written"] = True
        steps.append(f"written {final}")
        if captions and sidecars and cues:   # YouTube sidecars from the same cues (9.1)
            paths, sc_entries = write_sidecars({language: cues}, final.parent, final.stem)
            entries.extend(_with_post_shot(sc_entries))
            steps.append(f"sidecars: {len(paths)} file(s)")


def main(argv=None):
    p = argparse.ArgumentParser(description="Grade, impacts, captions, encode and final gates for one episode.")
    p.add_argument("build_dir")
    p.add_argument("--story", required=True)
    p.add_argument("--episode-json")
    p.add_argument("--styles-dir")
    p.add_argument("--fonts-dir")
    p.add_argument("--upscale-cmd")
    p.add_argument("--out")
    p.add_argument("--no-captions", action="store_true")
    p.add_argument("--no-sidecars", action="store_true")
    p.add_argument("--platform", choices=("reels", "shorts", "youtube"))
    p.add_argument("--language", choices=("en", "hi", "mr"))
    p.add_argument("--voice", choices=("elevenlabs", "h3"))
    p.add_argument("--vo-dir")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    report = run_post(args.build_dir, args.story, episode_json=args.episode_json, styles_dir=args.styles_dir,
                      fonts_dir=args.fonts_dir, upscale_cmd=args.upscale_cmd, out=args.out,
                      captions=not args.no_captions, dry_run=args.dry_run, platform=args.platform,
                      sidecars=not args.no_sidecars, language=args.language, voice=args.voice,
                      vo_dir=args.vo_dir)
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return 1 if report["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
