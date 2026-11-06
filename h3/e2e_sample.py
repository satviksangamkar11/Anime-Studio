"""Free-model end-to-end sample for the h3 pre-render path. Owner rule: NO Claude call.

The only live model is NVIDIA Nemotron Ultra (nvidia/nemotron-3-ultra-550b-a55b), reached through the existing 14-key
scheduler (D:/aai work/animation_research_tool/nvidia_scheduler.py), imported the same way as
flow/scripts/review_shot.py. API keys are never printed.

Flow: made-up premise -> model writes a 3-shot episode JSON -> synthetic PNGs for the picture paths -> lint_story ->
up to 4 repair rounds that send the exact lint messages back -> render_controller prepare-only -> readiness table ->
'E2E: rounds=N ready=R/3'. The timing and seam blueprint is fixed in the prompt (lattice_n 6, pixel_frames 107,
3 shots, DYNAMIC and CHAINED seams); the model writes the content.

  python -m h3.e2e_sample --offline                         built-in valid story, no model call (tests use this)
  python -m h3.e2e_sample --premise "..." [--out-dir DIR]   live: at most 5 scheduler calls (1 + 4 repairs)
"""
import argparse
import copy
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from h3 import render_controller
from h3.schema_and_linter import (BLOCKS, SHOT_KEYS, STAGES, lint_story, load_default_profile,
                                  write_minimal_valid_png)

LIVE_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
MAX_REPAIRS = 4
MAX_TOKENS = 16000
PROFILE = "sing8_864x1536"
BASE = [864, 1536]
EPISODE_ID = "E2E_EP01"
DEFAULT_PREMISE = "A lantern keeper climbs a tall stone tower to relight the lamp that guides the boats home."
ROOT = Path(__file__).resolve().parents[2]              # D:/aai work
SCHED_DIR = ROOT / "animation_research_tool"
ENV_FILE = SCHED_DIR / ".env"
STYLE_LOCK = {"mandatory_prefix": "Hand-drawn anime cel animation, flat colour, clean ink lines, one continuous take",
              "banned_style_tokens": ["photorealistic", "3d render"]}
CHARACTERS = {"char_keeper": {"short_disambiguator": "the lean lantern keeper in a grey wool coat"}}
CADENCE_WINDOWS = {"hold_window_frames": [0, 57], "burst_window_frames": [58, 89], "impact_or_settle_frames": [90, 107]}
STAGE_SPANS = {"1_starting_state": [0, 13], "2_anticipation": [14, 27], "3_initiation": [28, 41],
               "4_drive": [42, 57], "5_contact_approach": [58, 73], "6_impact_result": [74, 89],
               "7_settled_end_state": [90, 107]}


class ModelError(RuntimeError):
    """The scheduler did not return a usable reply (not a validity problem; those become repair rounds)."""


def _sec(frames):
    return round(frames / 24, 2)


def _timing(ti, to, head, tail, running):
    ed = to - ti
    return {"lattice_n": 6, "pixel_frames": 107, "latent_slots": 32, "generation_duration_sec": _sec(107),
            "exact_generation_duration_sec": _sec(107), "prompt_alignment_sec_str": f"{107 / 24:.2f}", "fps": 24,
            "trim_in_frame": ti, "trim_out_frame": to, "head_handle_frames": head, "tail_handle_frames": tail,
            "trim_in_sec": _sec(ti), "trim_out_sec": _sec(to), "head_handle_sec": _sec(head),
            "tail_handle_sec": _sec(tail), "editorial_frames": ed, "editorial_duration_sec": _sec(ed),
            "master_reel_frame_window": [running, running + ed], "master_reel_window_sec": [_sec(running), _sec(running + ed)]}


def _pose(torso, knee, com):
    return {"torso_pitch_deg": torso, "knee_flex_deg": knee, "com_y_ratio": com}


# Seam blueprint: S1 opens on a chained hold and cuts DYNAMIC; S2 enters DYNAMIC and ends CHAINED; S3 chains in and out.
# Cut continuity: S1 out tag/pose == S2 in tag/pose (within 5 deg, 5 deg, 0.03); S2 out == S3 in.
BLUEPRINT = [
    {"timing": _timing(0, 77, 0, 30, 0), "in": ("CHAINED_POSE_HOLD", "idle_at_tower_base", _pose(2.0, 10.0, 0.50)),
     "out": ("DYNAMIC_MATCH_ON_ACTION", "lunging_at_landing", _pose(12.0, 22.0, 0.55)),
     "pics": ("e2e_s1_start.png", "e2e_s1_end.png")},
    {"timing": _timing(11, 107, 11, 0, 77), "in": ("DYNAMIC_MATCH_ON_ACTION", "lunging_at_landing", _pose(12.5, 21.0, 0.56)),
     "out": ("CHAINED_POSE_HOLD", "pulling_up_on_stair", _pose(8.0, 15.0, 0.50)),
     "pics": ("e2e_s2_start.png", "e2e_s2_end.png")},
    {"timing": _timing(0, 107, 0, 0, 173), "in": ("CHAINED_POSE_HOLD", "pulling_up_on_stair", _pose(8.5, 15.5, 0.505)),
     "out": ("CHAINED_POSE_HOLD", "upright_at_lamp", _pose(3.0, 11.0, 0.52)),
     "pics": ("e2e_s2_end.png", "e2e_s3_end.png")},
]
TARGET_EDITORIAL = sum(b["timing"]["editorial_frames"] for b in BLUEPRINT)

SHOT_TEXT = [
    {"beat": "The keeper begins the climb at the foot of the tower.", "emotion": "Quiet resolve before a long task.",
     "scale": "medium", "in_note": "Opens the episode on a held pose at the tower base.",
     "out_note": "Action cut on the lunge at the landing.",
     "stages": [
         "The lantern keeper stands at the foot of the grey stone tower, a brass lantern hanging from one hand and his wool coat moving in the wind.",
         "He lifts his eyes to the spiral stair, a slow breath raises his shoulders, and his grip tightens on the lantern handle.",
         "He sets one boot on the first worn step and shifts his weight forward, the lantern swinging gently beside his knee.",
         "He climbs with long steady strides, one hand on the cold wall, the coat sweeping as the stair turns out of sight.",
         "A boot finds a loose stone, a small puff of dust lifts into the lamplight, and he catches the rail without slowing.",
         "He plants both feet on the landing in a low lunge, the lantern flares and rocks, and the light scatters across the wall.",
         "He rises into an upright pose on the landing, breathing calm, eyes fixed on the dark lamp room above."],
     "cadence": "Hold the stance quietly, then a quick burst of footsteps and swinging light, then settle on the landing.",
     "camera": {"motion_type": "Tracking Shot", "amplitude": "with small amplitude", "speed": "at slow speed",
                "compiled_clause": "The camera tracks the keeper with small amplitude at slow speed."},
     "sound": ("Wind over stone, the iron creak of a door, distant gulls.", "N/A")},
    {"beat": "The keeper climbs past a narrow window and hauls himself up the steep stair.",
     "emotion": "Strain turning into steady determination.", "scale": "medium",
     "in_note": "Dynamic match on the lunge from the first shot.",
     "out_note": "Chained pose hold into the upright stance at the landing.",
     "stages": [
         "The keeper rounds the landing, the lantern light sliding across a narrow window slit as the wind pushes against the glass.",
         "He reaches up for the next step, his knee bending hard, and a loose shutter bangs somewhere above him.",
         "He lunges forward onto the next tread, the lantern dipping low and the coat snapping behind him.",
         "He drives upward in quick steps, leaning into the steep stair with one hand braced on the wall.",
         "His hand slides along the rail, the stone under his boot cracks faintly, and he steadies himself mid-step.",
         "He hauls himself up onto the stair, shoulders rising as he pulls the lantern close to his chest.",
         "He stands tall on the stair, catching his breath, the light steady and his eyes lifted toward the top of the tower."],
     "cadence": "Hold the climb steady, then a short burst of hand and boot contact, then settle as he stands upright.",
     "camera": {"motion_type": "Push In", "amplitude": "with small amplitude", "speed": "at slow speed",
                "compiled_clause": "The camera pushes in with small amplitude at slow speed."},
     "sound": ("Gusts through a window slit, a shutter knocking, the scrape of boots on stone.",
               "N/A")},
    {"beat": "The keeper reaches the lamp room and relights the lamp.", "emotion": "Relief and purpose.",
     "scale": "wide", "in_note": "Chained from the stair pose held at the top of the climb.",
     "out_note": "Settled upright pose beside the lit lamp.",
     "stages": [
         "The keeper stands before the iron door of the lamp room, the lantern steady, his breath still short from the climb.",
         "He lifts the latch with his free hand, a slow breath lifting his shoulders as the cold air spills in.",
         "He steps through the doorway and turns toward the dark lamp, the lantern held out ready to pass its flame.",
         "He reaches to the brass valve and turns it, the wick hisses, and his arm moves in a smooth arc.",
         "The wick catches with a soft pop, a warm glow touches his face, and he leans closer to the flame.",
         "The lamp flares to full light, the beam sweeps outward over the water, and he steps back with a sharp breath.",
         "He stands upright beside the lit lamp, calm and still, the beam steady across the dark sea."],
     "cadence": "Hold the still doorway, then a quick burst as the wick catches, then settle in the steady beam.",
     "camera": {"motion_type": "Static Shot", "amplitude": "medium_omitted", "speed": "normal_omitted",
                "compiled_clause": "The camera holds a static shot."},
     "sound": ("A soft hiss of flame, wind at the lamp glass, distant water.", "N/A")},
]
PIC_SIZE = tuple(BASE)


def _partial(i):
    """The fixed part of shot i+1: ids, timing, seams, tags, poses, picture paths, spans. The model completes the rest."""
    bp = BLUEPRINT[i]
    return {"shot_id": f"E2E-{i + 1:02d}", "episode_id": EPISODE_ID, "sequence_order": i + 1,
            "timing_and_lattice": copy.deepcopy(bp["timing"]),
            "continuity_and_seam_lock": {
                "incoming_seam_type": bp["in"][0], "cut_in_biomechanical_state_tag": bp["in"][1],
                "cut_in_pose_vector": dict(bp["in"][2]), "outgoing_seam_type": bp["out"][0],
                "cut_out_biomechanical_state_tag": bp["out"][1], "cut_out_pose_vector": dict(bp["out"][2])},
            "fl2va_keyframes": {"mode": "REF2VA", "picture_1_path": bp["pics"][0], "picture_2_path": bp["pics"][1],
                                "dimensions_verified": list(BASE)},
            "motion_7_stage": {"stage_frame_spans": copy.deepcopy(STAGE_SPANS)},
            "anime_timing_cadence": copy.deepcopy(CADENCE_WINDOWS)}


def build_shots():
    """Deterministic valid episode (offline path). Same content the live model is asked to write."""
    shots = []
    for i in range(3):
        s, t = _partial(i), SHOT_TEXT[i]
        s["story_beat"], s["emotional_objective"], s["mute_animatic_verification"] = t["beat"], t["emotion"], False
        s["continuity_and_seam_lock"].update({
            "location_id": "loc_tower_stair", "shot_scale": t["scale"], "subjects_present": ["char_keeper"],
            "props_present": ["brass lantern"], "screen_direction_vector": "left_to_right", "camera_axis_side": "left",
            "horizon_line_y_ratio": 0.4, "incoming_seam_note": t["in_note"], "outgoing_seam_note": t["out_note"]})
        s["motion_7_stage"].update(dict(zip(STAGES, t["stages"])))
        s["anime_timing_cadence"]["cadence_clause"] = t["cadence"]
        s["camera"] = dict(t["camera"])
        s["dialogue_and_lip_lock"] = {"has_dialogue": False, "utterances": [],
                                      "mouth_state_rule": "Mouths stay closed for the whole shot."}
        s["sound_plan"] = {"overall_soundscape": t["sound"][0], "non_diegetic_music": t["sound"][1]}
        shots.append(s)
    return shots


def build_story(shots, asset_root):
    return {"registry": {"execution_profile": load_default_profile(PROFILE), "style_lock": copy.deepcopy(STYLE_LOCK),
                         "characters": copy.deepcopy(CHARACTERS)},
            "episodes": [{"episode_id": EPISODE_ID, "asset_root": asset_root, "shots": shots,
                          "episode_plan": {"target_editorial_frames": TARGET_EDITORIAL}}]}


# ---------- prompt ----------

SCHEMA_RULES = """\
- Shot top-level keys are exact. The only optional extra key is "metadata". No other extra keys anywhere.
- timing_and_lattice: pixel_frames = 17*lattice_n+5; latent_slots = 5*lattice_n+2; the *_sec fields are round(frames/24, 2).
  head_handle_frames == trim_in_frame; tail_handle_frames == pixel_frames - trim_out_frame; editorial_frames == trim_out_frame - trim_in_frame.
  master_reel_frame_window = [running, running + editorial_frames], running = sum of earlier shots' editorial_frames;
  master_reel_window_sec = the same two numbers divided by 24, rounded to 2 decimals.
  episode_plan.target_editorial_frames = sum of editorial_frames of the three shots.
- Seams: CHAINED_POSE_HOLD incoming needs trim_in_frame 0 and head_handle_frames 0. CHAINED_POSE_HOLD outgoing needs
  trim_out_frame == pixel_frames and tail_handle_frames 0. DYNAMIC_MATCH_ON_ACTION incoming needs head_handle_frames 8..35;
  DYNAMIC_MATCH_ON_ACTION outgoing needs tail_handle_frames 24..47.
- A CHAINED_POSE_HOLD incoming shot: picture_1_path must equal the previous shot's picture_2_path.
- Across each cut: cut_in_biomechanical_state_tag equals the previous cut_out tag; |torso_pitch_deg| <= 5.0,
  |knee_flex_deg| <= 5.0, |com_y_ratio| <= 0.03 between the previous cut_out_pose_vector and this cut_in_pose_vector.
- motion_7_stage: 7 stage strings plus stage_frame_spans (contiguous; first starts at 0; last ends at pixel_frames).
  A DYNAMIC outgoing shot must have trim_out_frame inside the 6_impact_result span.
- anime_timing_cadence: the three windows are contiguous from 0 to pixel_frames.
- camera.motion_type is one of: Zoom In, Zoom Out, Push In, Pull Out, Pan Left, Pan Right, Truck Left, Truck Right,
  Tilt Up, Tilt Down, Pedestal Up, Pedestal Down, Arc Shot, Tracking Shot, Static Shot, Shake Slightly, Shake Strongly,
  POV, Roll Clockwise, Roll Counterclockwise. compiled_clause (lower case words) must contain that motion's phrase:
  Push In -> "pushes in", Tracking Shot -> "tracks", Static Shot -> "holds a static shot".
  amplitude is "with small amplitude" or "with large amplitude" and that phrase must appear in compiled_clause,
  or "medium_omitted" (then the words amplitude and speed must not appear in compiled_clause).
  speed is "at slow speed" or "at fast speed" and that phrase must appear, or "normal_omitted".
- fl2va_keyframes.mode must be exactly "REF2VA". Picture paths are plain file names. dimensions_verified is [864, 1536].
- The compiled description is built from your stage strings: each stage is one or two plain sentences of about
  90 to 160 characters, no line breaks, no clock timestamps, and never the words photorealistic or 3d render.
- No dialogue in this test: has_dialogue false and utterances [] in every shot.
"""


def _key_lines():
    lines = ["Shot top-level keys: " + ", ".join(sorted(SHOT_KEYS))]
    for name in sorted(BLOCKS):
        req, opt = BLOCKS[name]
        line = f"{name}: " + ", ".join(sorted(req))
        if opt:
            line += " (optional: " + ", ".join(sorted(opt)) + ")"
        lines.append(line)
    return lines


def build_prompt(premise):
    return "\n\n".join([
        "You write one 3-shot animation episode as a single JSON object for the h3 linter. "
        f"PREMISE (made up for this test): {premise}",
        "OUTPUT: ONLY one JSON object {\"shots\": [shot 1, shot 2, shot 3]} with the three shots in blueprint order. "
        "No prose, no markdown fences, no comments.",
        "KEY NAMES (exact, from the linter):\n" + "\n".join(_key_lines()),
        "RULES:\n" + SCHEMA_RULES,
        "BLUEPRINT: partial shot objects. Copy every value exactly, then complete each shot:\n"
        + json.dumps([_partial(i) for i in range(3)], indent=1),
        "WRITE FOR EACH SHOT: story_beat, emotional_objective, mute_animatic_verification (false); "
        "continuity_and_seam_lock: location_id, shot_scale, subjects_present, props_present, screen_direction_vector, "
        "camera_axis_side, horizon_line_y_ratio, incoming_seam_note, outgoing_seam_note; "
        "motion_7_stage: the seven stage strings 1_starting_state to 7_settled_end_state, following the premise in order; "
        "anime_timing_cadence.cadence_clause: one plain sentence naming the hold, the burst and the settle; "
        "camera: motion_type, amplitude, speed, compiled_clause; "
        "dialogue_and_lip_lock: has_dialogue false, utterances [], mouth_state_rule; "
        "sound_plan: overall_soundscape = at least 40 characters of concrete sound effects (steps, wind, water, cloth, impacts); non_diegetic_music = exactly N/A.",
    ])


def repair_prompt(premise, messages, prior):
    """A call is stateless, so the repair prompt repeats the full prompt, then the exact lint messages and the old reply."""
    return (build_prompt(premise)
            + "\n\nYOUR PREVIOUS ATTEMPT FAILED THE LINTER. Fix only what these messages name, keep every BLUEPRINT value, "
              "and reply with the complete corrected JSON object {\"shots\": [...]} and nothing else.\n\nLINT MESSAGES:\n"
            + "\n".join("- " + m for m in messages)
            + "\n\nYOUR PREVIOUS JSON:\n" + prior)


# ---------- reply handling ----------

def strip_think(text):
    """The answer only: <think>...</think> blocks are dropped; an unclosed <think> has no answer after it."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    return text.split("<think>", 1)[0].strip()


def parse_model_json(text):
    t = (text or "").strip()
    fence = re.search(r"```[A-Za-z]*\s*\n?(.*?)```", t, re.S)
    if fence:
        t = fence.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        i, j = t.find("{"), t.rfind("}")
        if 0 <= i < j:
            return json.loads(t[i:j + 1])
        raise


def check_reply(reply, asset_root):
    """-> (shots or None, messages). messages == [] means the story lints clean. Writes synthetic PNGs for the paths."""
    try:
        obj = parse_model_json(reply)
    except ValueError as e:
        return None, [f"PARSE reply is not valid JSON ({e}); reply with the JSON object only, no prose, no fences"]
    shots = obj.get("shots") if isinstance(obj, dict) else None
    if not isinstance(shots, list) or len(shots) != 3 or not all(isinstance(s, dict) for s in shots):
        return None, ["SHAPE reply must be one JSON object {\"shots\": [3 shot objects]}"]
    bad, paths = [], []
    for s in shots:
        kf = s.get("fl2va_keyframes")
        for key in ("picture_1_path", "picture_2_path"):
            p = kf.get(key) if isinstance(kf, dict) else None
            if not isinstance(p, str) or not p or os.path.basename(p) != p or p in (".", ".."):
                bad.append(f"PATH {key} of {s.get('shot_id')!r} must be a plain file name, got {p!r}")
            else:
                paths.append(p)
    if bad:
        return None, bad
    for p in sorted(set(paths)):
        target = os.path.join(asset_root, p)
        if not os.path.isfile(target):
            write_minimal_valid_png(target, PIC_SIZE[0], PIC_SIZE[1])
    try:
        lint = lint_story(build_story(shots, asset_root))
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        return shots, [f"LINT-EXC the linter could not read the story: {e!r}"]
    return shots, lint["errors"]


def _codes(messages):
    out = []
    for m in messages:
        parts = m.split(" ", 2)
        code = parts[1] if len(parts) > 1 and parts[0].endswith(":") else parts[0]
        if code not in out:
            out.append(code)
    return out


# ---------- scheduler ----------

def live_scheduler():
    """NvidiaScheduler over the existing 14-key pool, imported as flow/scripts/review_shot.py does."""
    sys.path.append(str(SCHED_DIR))
    flag = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        from nvidia_scheduler import NvidiaScheduler, load_env_keys
    finally:
        sys.dont_write_bytecode = flag
    keys = load_env_keys(ENV_FILE)   # ValueError if the 14 keys are missing; the message names no key
    return NvidiaScheduler(keys, model=LIVE_MODEL, read_timeout=600)


def _ask(scheduler):
    def ask(prompt):
        res = scheduler.call(prompt, max_tokens=MAX_TOKENS)
        if res.get("status") != "OK":
            code = f" HTTP {res['http_status']}" if res.get("http_status") else ""
            raise ModelError(f"scheduler {res.get('status')}{code}")
        return strip_think(res.get("text") or "")
    return ask


# ---------- run ----------

def run_e2e(premise=DEFAULT_PREMISE, out_dir=None, *, offline=False, scheduler=None, max_repairs=MAX_REPAIRS, log=print):
    """Returns {rounds, ready, total, exit_code, out_dir, story_path, codes}. rounds = model calls (0 when offline)."""
    out = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="h3_e2e_"))
    pics = out / "pics"
    pics.mkdir(parents=True, exist_ok=True)
    asset_root = str(pics)
    log(f"out: {out}")
    attempts, rounds, shots, messages = [], 0, None, []
    if offline:
        log("mode: offline (built-in story, no model call)")
        shots, messages = check_reply(json.dumps({"shots": build_shots()}), asset_root)
    else:
        log(f"mode: live, model {LIVE_MODEL}, at most {1 + max_repairs} calls")
        try:
            ask = _ask(scheduler if scheduler is not None else live_scheduler())
        except (ValueError, ImportError, OSError) as e:
            return _fail(out, 0, attempts, log, f"scheduler unavailable: {e}")
        prior = ""
        for rnd in range(1, max_repairs + 2):
            prompt = build_prompt(premise) if rnd == 1 else repair_prompt(premise, messages, prior)
            try:
                reply = ask(prompt)
            except ModelError as e:
                rounds += 1
                attempts.append({"round": rnd, "status": str(e)})
                return _fail(out, rounds, attempts, log, f"round {rnd} model call failed: {e}")
            rounds += 1
            (out / "replies").mkdir(exist_ok=True)
            (out / "replies" / f"round_{rnd}.txt").write_text(reply, encoding="utf-8")
            prior = reply
            shots, messages = check_reply(reply, asset_root)
            attempts.append({"round": rnd, "errors": messages})
            if not messages:
                log(f"round {rnd}: lints clean")
                break
            log(f"round {rnd}: {len(messages)} lint message(s): {', '.join(_codes(messages))}")
    if messages or shots is None:
        return _fail(out, rounds, attempts, log, f"lint codes {', '.join(_codes(messages)) or 'none'}", messages)
    story_path = out / "story.json"
    story_path.write_text(json.dumps(build_story(shots, asset_root), indent=2, ensure_ascii=False), encoding="utf-8")
    rc = render_controller.main(["--story-file", str(story_path), "--scope", "all",
                                 "--out-dir", str(out / "build"), "--mode", "prepare-only"])
    readiness = json.loads((out / "build" / EPISODE_ID / "readiness.json").read_text(encoding="utf-8"))
    ready, total = readiness["totals"]["ready"], readiness["totals"]["shots"]
    exit_code = 0 if rc == 0 and ready == total == 3 else 1
    log(f"E2E: rounds={rounds} ready={ready}/{total}" + ("" if exit_code == 0 else " FAILED"))
    (out / "attempts.json").write_text(json.dumps(attempts, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"rounds": rounds, "ready": ready, "total": total, "exit_code": exit_code, "out_dir": str(out),
            "story_path": str(story_path), "codes": [], "messages": []}


def _fail(out, rounds, attempts, log, why, messages=()):
    (out / "attempts.json").write_text(json.dumps(attempts, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"E2E: rounds={rounds} ready=0/3 FAILED: {why}")
    for m in messages:
        log(f"  ! {m}")
    return {"rounds": rounds, "ready": 0, "total": 3, "exit_code": 1, "out_dir": str(out), "story_path": None,
            "codes": _codes(messages), "messages": list(messages)}


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(prog="python -m h3.e2e_sample",
                                 description="Free-model (NVIDIA only) end-to-end sample of the h3 pre-render path.")
    ap.add_argument("--offline", action="store_true", help="built-in valid story; no model call")
    ap.add_argument("--premise", default=DEFAULT_PREMISE, help="made-up one-line premise for the live call")
    ap.add_argument("--out-dir", default=None, help="output folder (default: a new temp folder, printed)")
    args = ap.parse_args(argv)
    return run_e2e(args.premise, args.out_dir, offline=args.offline)["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
