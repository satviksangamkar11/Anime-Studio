"""Final reel builder (backend): rendered clips + per-shot voice tracks -> one finished reel per language, WITHOUT music.

  1. cuts: h3.assemble_reel.build_ffmpeg_assembly_plan trims every clip to its editorial window (head/tail handles removed) and concatenates
     video and the clips' own H3 sound effects; ffmpeg runs it -> <out>/<reel>_video.mp4
  2. gate: h3.gate_d_audio.plan_language_outputs checks every language (VO fit, captions, hook, closing). Findings whose code is in WAIVED are
     the writer's script-level retention rules (narration density, dead air between scripted lines) and the closing-shot anchor/mouth rule;
     the owner ordered the finished reel, so they are WRITTEN INTO THE REPORT (never hidden) and do not stop the build. Any other error stops it.
  3. mix + captions: the same Gate D functions the planner uses (SFX stem ducked under the voice stem, loudnorm to core delivery loudness,
     burned .ass captions in the language's script) -> <out>/export/<reel>_<lang>.mp4, then the AAC loudness is measured and checked.
No music is mixed (bgm_manifest None); the score is a later step. Never calls a model or ElevenLabs.

  python build_final_reel.py --pack <pack dir> --story <h3_story.json> --clips <clips.json {SHOT-001: path}> --vo <vo root with <lang>/<SHOT>.wav> --out <dir> [--reel kalika_reel1] [--langs en,hi,mr]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from core.style_pack import load_core  # noqa: E402
from h3 import assemble_reel as ar  # noqa: E402
from h3 import gate_d_audio as gd  # noqa: E402

WAIVED = {"NARRATION_COVERAGE_LOW", "NARRATION_WORDS_LOW", "DEAD_AIR_PAUSE", "CLOSING_NO_ANCHOR_PAYOFF", "CLOSING_MOUTH_OPEN"}


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


def mux_argv(rows, lang, vo_dir, video, export, ass, fonts_dir):
    """The planner's own mix and mux, built directly so a waived finding does not block it (same functions, same order)."""
    inputs, vo_refs, offsets, t = [str(video)], [], [], 0.0
    for r in rows:
        ed = float(r["editorial_duration_sec"])
        offsets.append(t)
        t += ed
        p = Path(vo_dir) / lang / f"{r['id']}.wav"
        if p.is_file():
            inputs.append(str(p))
            vo_refs.append((len(inputs) - 1, ed))
        else:
            vo_refs.append((None, ed))
    sfx = [{"input_index": f"h3s{k}", "trim_in_sec": o, "trim_out_sec": o + float(r["editorial_duration_sec"])} for k, (r, o) in enumerate(zip(rows, offsets))]
    mix = ";".join([gd.build_sfx_split_filter(0, len(rows)), gd.build_vo_stem_filter(vo_refs), gd.build_mix_filter(sfx, "vo_full", None, t)])
    return gd.build_final_mux_argv(video, inputs[1:], mix, export, burn_captions=True, ass_path=ass, fonts_dir=fonts_dir), t


# owner 2026-11-09: Mukta ExtraBold, ~60 px at 1080 wide. The family must be the font's own name ("Mukta ExtraBold", name ID 1):
# with plain "Mukta" libass found no match and silently drew a system font.
CAPTION_PACK = {"typography": {"subtitle_latin": "Mukta ExtraBold", "subtitle_devanagari": "Mukta ExtraBold", "min_px_at_1080w": 60}}
YELLOW_BGR, WHITE_BGR = "&H0000D4FF", "&H00FFFFFF"     # ASS colours are BGR: active word yellow #FFD400, the rest white (owner research)


def split_cards(text, max_words=6):
    """Balanced cards of at most max_words words, cut at sentence ends first (a card never joins two sentences when it can avoid it)."""
    sents = [s for s in re.split(r"(?<=[.?!।])\s+", text.strip()) if s]
    cards = []
    for s in sents:
        words = s.split()
        n = -(-len(words) // max_words)
        size = -(-len(words) // n)
        cards += [words[i:i + size] for i in range(0, len(words), size)]
    return cards


def word_cues(text, t0, t1):
    """Cue dicts for one spoken line: cards of at most 6 words, time shared by letters, each word aligned inside its card (letters-proportional)."""
    cards = split_cards(text)
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


def spoken_cues_real(rows, report, lang):
    """Caption cues from the REAL packed voice timings (vo_tracks_report.json of the language) and the line text of shots.json."""
    offsets, t = {}, 0.0
    for r in rows:
        offsets[r["id"]] = t
        t += float(r["editorial_duration_sec"])
    text = {}
    for r in rows:
        a = r["audio_and_dialogue_track"]
        n = (a.get("narration_by_lang") or {}).get(lang) or {}
        if n.get("text"):
            text[f"{r['id']}-N"] = n["text"]
        for k, d in enumerate((a.get("dialogue_by_lang") or {}).get(lang) or [], 1):
            text[f"{r['id']}-D{k}"] = d["text"]
    cues = []
    for sh in report:
        if sh["lang"] != lang:
            continue
        for ln in sh["lines"]:
            cues += word_cues(text[ln["id"]], offsets[sh["shot"]] + ln["start"], offsets[sh["shot"]] + ln["end"])
    return sorted(cues, key=lambda c: c["t0"])


def _ass_t(s):
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"


def _secs(t):
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def style_colours(ass_text):
    """Owner look: ONLY the word being spoken is yellow, every other word of the card white. Each engine karaoke event
    ({\\kNN}word ...) becomes one event per word, timed by the engine's \\k durations; the last word holds to the card end."""
    out = []
    for line in ass_text.splitlines():
        if line.startswith("Style:"):
            p = line.split(",")
            p[3], p[4] = WHITE_BGR, WHITE_BGR
            out.append(",".join(p))
            continue
        m = re.match(r"(Dialogue: [^,]*,)([^,]*),([^,]*),((?:[^,]*,){6})\{([^}]*)\}(.*)$", line)
        toks = re.findall(r"\{\\k(\d+)\}([^{]*)", m.group(6)) if m else []
        if not toks:
            out.append(line)
            continue
        head = re.sub(r"\\[12]c&H[0-9A-Fa-f]+&", "", m.group(5))
        t0, t1 = _secs(m.group(2)), _secs(m.group(3))
        s = t0
        for i, (k, _) in enumerate(toks):
            e = t1 if i == len(toks) - 1 else min(t1, s + int(k) / 100)
            body = "".join("{\\1c%s&}%s" % (YELLOW_BGR if j == i else WHITE_BGR, w) for j, (_, w) in enumerate(toks))
            out.append(f"{m.group(1)}{_ass_t(s)},{_ass_t(e)},{m.group(4)}{{{head}}}{body}")
            s = e
    return "\n".join(out) + "\n"


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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--story", required=True)
    ap.add_argument("--clips", required=True)
    ap.add_argument("--vo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--reel", default="kalika_reel1")
    ap.add_argument("--langs", default="en,hi,mr")
    ap.add_argument("--fonts", default=str(HERE.parent / "styles" / "fonts"))
    ap.add_argument("--title-cards", action="store_true", help="burn the writer's title cards instead of the spoken words (old behaviour)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    (out / "export").mkdir(parents=True, exist_ok=True)
    (out / "captions").mkdir(parents=True, exist_ok=True)
    from editorial_by_lang import apply_rows, apply_shots, load
    ext = load(a.pack)                                  # <pack>/editorial_by_lang.json; missing = the v3 lengths
    rows = apply_rows(json.loads((Path(a.pack) / "shots.json").read_text(encoding="utf-8")), ext)
    story = json.loads(Path(a.story).read_text(encoding="utf-8"))
    h3_shots = apply_shots(story["episodes"][0]["shots"], ext)
    if [r["id"] for r in rows] != [s["shot_id"] for s in h3_shots]:
        raise SystemExit("pack rows and H3 story shots differ in id or order")
    clips = json.loads(Path(a.clips).read_text(encoding="utf-8"))
    video = out / f"{a.reel}_video.mp4"
    plan = assemble_video(h3_shots, clips, video, out / "assembly")
    langs = a.langs.split(",")
    res = gd.plan_language_outputs(a.reel, langs, a.vo, None, shots=rows, video_path=str(video), video_has_audio=True, burn_captions=True,
                                   captions_dir=str(out / "captions"), export_dir=str(out / "export"), fonts_dir=a.fonts,
                                   voice_engines={lg: "elevenlabs" for lg in langs})
    report = {"reel": a.reel, "video": str(video), "frames": plan["total_frames"], "seconds": plan["total_duration_sec"], "languages": {}}
    stop = False
    for lg in langs:
        rep, lp = res["reports"][lg], res["languages"][lg]
        waived = [e for e in rep["errors"] if e["code"] in WAIVED]
        blocking = [e for e in rep["errors"] if e["code"] not in WAIVED]
        entry = {"waived_findings": waived, "blocking_errors": blocking, "warnings": rep["warnings"]}
        report["languages"][lg] = entry
        if blocking:
            stop = True
            continue
        ass = out / "captions" / f"{a.reel}_{lg}.ass"
        report_path = Path(a.vo) / "vo_tracks_report.json"      # one report for all languages (build_vo_tracks --out <vo>)
        if not report_path.is_file():
            report_path = Path(a.vo).parent / f"vo_{lg}" / "vo_tracks_report.json"
        if a.title_cards or not report_path.is_file():
            cues = lp["captions"]                       # the writer's title cards (old behaviour, only on request)
        else:
            cues = spoken_cues_real(rows, json.loads(report_path.read_text(encoding="utf-8")), lg)   # owner 2026-11-09: captions = the spoken words
        for msg in gd.script_problems(cues, lg) if hasattr(gd, "script_problems") else []:
            raise SystemExit(f"{lg}: {msg}")
        ass_text, entries = gd.build_captions(cues, lang=lg, pack=CAPTION_PACK, fonts_dir=a.fonts)
        fails = [e["message"] for e in entries if e["level"] == "FAIL"]
        if fails:
            raise SystemExit(f"{lg} captions: " + "; ".join(fails))
        ass.write_text(style_colours(ass_text), encoding="utf-8", newline="\n")
        from core import caption_export as cx
        entry["caption_warnings"] = sorted({e["message"] for e in entries if e["level"] == "WARN"})[:6]
        entry["captions"] = {"cues": len(cues), "mode": "title cards" if cues is lp["captions"] else "spoken words"}
        cx.write_sidecars({lg: cues}, str(out / "captions"), a.reel)
        export = out / "export" / f"{a.reel}_{lg}.mp4"
        argv_, total = mux_argv(rows, lg, a.vo, video, export, ass, a.fonts)
        subprocess.run(argv_, check=True, cwd=str(HERE.parent))
        loud = correct_loudness(export, measure(export))
        entry.update(export=str(export), seconds=round(total, 2), loudness=loud["stats"], loudness_ok=loud["ok"], loudness_errors=loud["errors"])
    (out / f"{a.reel}_build_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    for lg, e in report["languages"].items():
        print(lg, "BLOCKED" if e["blocking_errors"] else "built", "| waived:", sorted({w["code"] for w in e["waived_findings"]}),
              "| loudness ok:", e.get("loudness_ok"), "|", e.get("export", ""))
        for b in e["blocking_errors"]:
            print("  BLOCK", b["code"], b["where"], str(b["message"])[:160])
    return 1 if stop else 0


if __name__ == "__main__":
    sys.exit(main())
