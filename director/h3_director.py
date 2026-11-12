"""Anime studio director, Gate 4 -> Wan2GP: turns a shot list into one Wan2GP settings file per shot (MiniMax H3 + Pika H3 Flex 6 steps),
run headless on Kaggle with `python wgp.py --process <settings.json>` (proven 2026-11-04: S4 shot 3, Kaggle T4, 18m51s incl. downloads).

Shot list: JSON list of shots, each
  id            "SHOT-09" (SHOT-NN, SHOT-NNN or SHOT-NNA)
  mode          "fl2va" (start/end frame) or "ref2va" (reference images; start/end frames still allowed)
  seconds       wanted length; rounded to the NEAREST H3 grid count (107 + 17k frames at 24 fps, max 362)
  render_frames optional integer 107 + 17k (max 362); overrides seconds
  edit_frames   optional integer 1..render_frames (the part kept for the edit)
  aspect        "9:16" (default) or "16:9"
  resolution    optional, one of RES_OPTIONS for the aspect (9:16: 480x832 default, 544x960, 704x1280, 768x1344)
  start, end    optional image paths (PNG, relative, [A-Za-z0-9_./-]); end is a target, not a lock
  refs          ref2va only: identity sheets, in order; subjects write them as <Picture 1>, <Picture 2>, ... and the director
                renumbers them after the start and end frames (start + end + first ref = <Picture 3>)
  subjects      ref2va only: ["<Subject 1> is Bala Krishna in <Picture 1>", ...]
  sampler       optional, only pika_renoise (the Pika LoRA's sampler; the default); pika6 route only
  route         optional: "pika6" (default, the Pika presets above), "sing4" or "sing8" (Singularity v2 + Pika-Labs Turbo LoRA,
                4 or 8 steps; Ref2VA only, no sampler field; the route sets the model, LoRA, sampler, steps and CFG)
  style, world  one line each (describe the look; never name a film or show)
  action        what happens, with time codes ("0-1.5s ...; 1.5-4s ...")
  camera        one camera move
  sound         soundscape line ("" = quiet ambience); H3 audio is replaced in the edit unless kept on purpose
  seed          optional (default 42)
A RICH shot (SPEC_v2.2.md, has "beats") is compiled into the same prompt from its beats, camera and light; its keyframes
come from keyframes.start/end; main() also writes <id>.direction.json with the full rich spec.
Usage: python h3_director.py shots.json out_dir"""
import json
import math
import re
import sys
from pathlib import Path

import style_bible

FPS, FRAMES_MIN, FRAMES_STEP, FRAMES_MAX = 24, 107, 17, 362
LEGAL = range(FRAMES_MIN, FRAMES_MAX + 1, FRAMES_STEP)
RES = {"9:16": "480x832", "16:9": "832x480"}   # default per aspect (the size proven on the Kaggle T4)
# optional per-shot "resolution": bigger sizes keep a small face recognisable; landscape is the same list flipped
RES_OPTIONS = {"9:16": ("480x832", "544x960", "704x1280", "768x1344")}   # H3 sizes are multiples of 32 (vae_block_size)
RES_OPTIONS["16:9"] = tuple("x".join(r.split("x")[::-1]) for r in RES_OPTIONS["9:16"])
PRESET = {   # Wan2GP's own "Pika H3 Flex ... Pruned 6 Steps" presets (shared/deepy/settings), commit bd1ff59
    "fl2va": ("minimax_h3_fl2va_pruned", "pika_h3_flex_fl2va_6step_v1_bf16.safetensors", ""),
    "ref2va": ("minimax_h3_ref2va_pruned", "pika_h3_flex_ref2va_6step_v1_bf16.safetensors", "I"),
}
PIKA_MODELS = (PRESET["fl2va"][0], PRESET["ref2va"][0])
LORA_URL = "https://huggingface.co/DeepBeepMeep/MiniMax-H3/resolve/main/loras/"
# T0 arms B and C (DECISION_best_workflow_2026-11-05.md, RETHINK): Singularity v2 pruned (Wan2GP defaults/minimax_h3_singularity_v2_pruned.json,
# architecture minimax_h3_ref2va_pruned) with a Pika-Labs Turbo LoRA: ComfyUI-format standard LoRA, euler, simple schedule, CFG 1, shift 12
ROUTES = ("pika6", "sing4", "sing8")
SING_MODEL = "minimax_h3_singularity_v2_pruned"
TURBO_URL = "https://huggingface.co/Pika-Labs/Pika-H3-Flex-Turbo-LoRA/resolve/main/"
TURBO = {"sing4": ("pika_h3_flex_turbo_4step_ref2va.safetensors", 4), "sing8": ("pika_h3_flex_turbo_8step_hd_ref2va.safetensors", 8)}
KEEP = "Keep every face, outfit, prop and background exactly as in the pictures; no new people; no style change; no on-screen text."
DEFAULT_STYLE = "Modern Japanese anime cel look with 2.5D layered depth and painted backgrounds."
# handler prompt_enhancer.py: FL2VA_DEEPY_PROMPT_INFOS line 30 ("For supplied frame anchors, prepend: `For the target video, at
# 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.`") and FL2VA_PROMPT_INFOS lines 49-53
# (start frame at 0.00; end frame at the exact end time; start+end: Picture 1 at 0.00, Picture 2 at the end)
ALIGN = "For the target video, at {t:.2f} seconds into the target video, <Picture {n}> (from [Shot 1]) is fully referenced."
# end image only: handler prompt_enhancer.py FL2VA_PROMPT_INFOS line 52 ("<Picture 1> (if only an End Image is provided) belongs to
# the actual final shot and aligns with the exact end time")
ALIGN_FINAL = "For the target video, at {t:.2f} seconds into the target video, <Picture 1> (from the actual final shot) is fully referenced."
# handler prompt_enhancer.py: REF2VA_PROMPT_INFOS lines 139-150 (six-section template), line 162 (keyframes get their own
# <Picture N> entry), _REF2VA_SHARED_RULES line 290 (retention_analysis wording and the four visual modes)
RETAIN = ("face, eyes, age proportions, hair, costume, ornaments, line weight and cel shading. "
          "May change: pose, expression, camera framing.")
SHOT_ID = re.compile(r"SHOT-\d{2,3}[A-Z]?")
T0_ID = re.compile(r"SHOT-T0-(FL|REF|[ABCD])-S\d+")   # T0 variants of one shot (t0_variants.py): FL/REF, or arms A-D
SUBJECT = re.compile(r"<Subject (\d+)> is .+? in <Picture (\d+)>\.?")   # group 1: the subject number, group 2: its picture
PATH = re.compile(r"[A-Za-z0-9_./-]+")
IMAGE_EXTS = (".png", ".jpg", ".jpeg")   # image fields only; no video or audio fields exist yet


def check_shot_id(sid):
    if not isinstance(sid, str) or not (SHOT_ID.fullmatch(sid) or T0_ID.fullmatch(sid)):
        raise ValueError(f"shot id {sid!r} must match SHOT-NN, SHOT-NNN, SHOT-NNA or SHOT-T0-(FL|REF|A|B|C|D)-S<seed>")
    return sid


def check_unique_ids(shots):
    """Every id has valid syntax, and no two shots share one: settings are keyed by id, so a clash would overwrite."""
    ids = [s.get("id") for s in shots]
    for i in ids:
        check_shot_id(i)
    dup = sorted({str(i) for i in ids if ids.count(i) > 1})
    if dup:
        raise ValueError(f"duplicate shot ids {dup}: every shot in a batch needs its own id")


def subject_problems(refs, subjects):
    """Each subject reads '<Subject k> is ... in <Picture N>' and names one or more <Picture N> (e.g. a face crop and a full-body
    crop of the same character), each N among the refs (1..len(refs));
    the subject indices run 1..n in order, each once."""
    out, indices = [], []
    for s in subjects:
        m = SUBJECT.fullmatch(s) if isinstance(s, str) else None
        if not m:
            out.append(f"subject {s!r} must read '<Subject k> is ... in <Picture N>'")
            continue
        indices.append(int(m.group(1)))
        pictures = re.findall(r"<Picture (\d+)>", s)
        if len(pictures) != len(set(pictures)):
            out.append(f"subject {s!r} names a <Picture N> twice")
        for n in pictures:
            if not 1 <= int(n) <= len(refs):
                out.append(f"subject {s!r} names <Picture {n}>, but there are {len(refs)} refs (<Picture 1> to <Picture {len(refs)}>)")
    if indices != list(range(1, len(indices) + 1)):
        out.append(f"subject indices {indices} must run 1..{len(indices)} in order, each once")
    return out


def safe_path(p):
    """A relative image path: [A-Za-z0-9_./-] only, no '..', no drive, no leading '/', ending .png/.jpg/.jpeg."""
    if not isinstance(p, str) or not PATH.fullmatch(p) or ".." in p or p.startswith("/") or not p.endswith(IMAGE_EXTS):
        raise ValueError(f"unsafe or unknown image path {p!r}: relative, [A-Za-z0-9_./-] only, ending in {' '.join(IMAGE_EXTS)}")
    return p


def frames_for(seconds):
    """Nearest legal H3 frame count to `seconds` (107, 124, 141, ... 362). Up to one step (17 frames) past 362 still gives 362."""
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError(f"seconds must be a finite positive number, got {seconds!r}")
    raw = seconds * FPS
    if raw > FRAMES_MAX + FRAMES_STEP / 2:
        raise ValueError(f"{seconds}s is longer than one H3 window ({FRAMES_MAX / FPS:.1f}s): split the shot")
    n = round(raw)
    return min(LEGAL, key=lambda f: (abs(f - n), f))


def frames_for_shot(shot):
    """render_frames (an exact legal count) overrides seconds; edit_frames must be 1..the render length."""
    if "render_frames" in shot:
        r = shot["render_frames"]
        if isinstance(r, bool) or not isinstance(r, int) or r not in LEGAL:
            raise ValueError(f"render_frames {r!r} must be 107 + 17k and at most {FRAMES_MAX}")
        frames = r
    else:
        frames = frames_for(shot["seconds"])
    if "edit_frames" in shot:
        e = shot["edit_frames"]
        if isinstance(e, bool) or not isinstance(e, int) or not 1 <= e <= frames:
            raise ValueError(f"edit_frames {e!r} must be an integer from 1 to {frames}")
    return frames


def is_rich(shot):
    return "beats" in shot


def start_of(shot):
    return shot.get("start") or (shot.get("keyframes") or {}).get("start")


def end_of(shot):
    return shot.get("end") or (shot.get("keyframes") or {}).get("end")


def action_of(shot):
    return shot["beats"][0]["acting"] if is_rich(shot) else shot["action"]


def beat_line(b):
    line = f"{b['t'][0]:g}-{b['t'][1]:g}s: {b['acting']}"
    return f"{line}; {b['secondary']}" if b.get("secondary") else line


def body_for(shot, seconds):
    """seconds is frames / FPS, shown to 2 decimals so the text matches video_length (107 frames -> 4.46)."""
    if not is_rich(shot):
        return f"[Shot 1] A {seconds:.2f}-second single take. {shot['style']} {shot['world']} {shot['action']} Camera: {shot['camera']}. {KEEP}"
    cam, light = shot["camera"], shot["light"]
    beats = " ".join(beat_line(b) for b in shot["beats"])
    return (f"[Shot 1] A {seconds:.2f}-second single take. {shot.get('style') or DEFAULT_STYLE} {beats} "
            f"Camera: {cam['move']}, {cam['lens_mm']}mm lens, {cam['start_framing']}->{cam['end_framing']} framing. "
            f"Light: {light['key']}; {light['rim']}; {light['mood']}. {KEEP}")


def identity_text(shot, bible):
    """Style-bible text for the shot's cast, set and props, then the project's palette, line and shading rules (never film names)."""
    if bible is None:
        return ""
    ids = [c["id"] for c in shot.get("cast") or []] + ([shot["set"]] if shot.get("set") else []) + [p["id"] for p in shot.get("props") or []]
    out = []
    for entity in ids:
        try:
            out.append(style_bible.prompt_block(bible, entity))
        except KeyError:
            raise ValueError(f"{shot['id']}: {entity} is not in the style bible") from None
    rules = [(bible.get(key) or {}).get("rule") for key in ("palette", "line", "shading")]
    if any(rules):
        out.append("Style: " + " ".join(r for r in rules if r))
    return " ".join(out)


def alignment_lines(shot, frames):
    """FL2VA: Picture 1 is the start frame at 0.00 s; the end frame is the next picture, at the exact end time."""
    if start_of(shot):
        lines = [ALIGN.format(t=0, n=1)] + ([ALIGN.format(t=frames / FPS, n=2)] if end_of(shot) else [])
    elif end_of(shot):
        lines = [ALIGN_FINAL.format(t=frames / FPS)]
    else:
        lines = []
    return "".join(line + "\n" for line in lines)


def keyframes_of(shot, frames):
    """Ref2VA: (label, line) for the start and end frames, numbered before the references."""
    out, n = [], 0
    if start_of(shot):
        n += 1
        out.append((f"<Picture {n}>", f"<Picture {n}> is the start frame of [Shot 1] at 0.00 seconds."))
    if end_of(shot):
        n += 1
        out.append((f"<Picture {n}>", f"<Picture {n}> is the end frame of [Shot 1] at {frames / FPS:.2f} seconds."))
    return out


def _global_pictures(text, offset):
    """Subjects name their refs from <Picture 1>; the start and end frames come first in H3's numbering."""
    return re.sub(r"<Picture (\d+)>", lambda m: f"<Picture {int(m.group(1)) + offset}>", text)


def prompt_for(shot, frames, bible=None):
    identity = identity_text(shot, bible)
    body = body_for(shot, frames / FPS) + (f" {identity}" if identity else "")
    sound = shot.get("sound") or "Quiet natural ambience only, no speech."
    if shot["mode"] == "fl2va":
        return f"{alignment_lines(shot, frames)}integrated_multimodal_description: {body}\noverall_soundscape: {sound}\nnon_diegetic_music: N/A"
    keys = keyframes_of(shot, frames)
    offset = len(keys)
    subjects = "\n".join([_global_pictures(s, offset) for s in shot["subjects"]] + [line for _, line in keys])
    labels = dict.fromkeys(re.findall(r"<Subject \d+>", subjects))
    retention = [f"{label} (keyframe): fully_preserved - the frame as given." for label, _ in keys]
    retention += [f"{label} (appears in [Shot 1]): fully_preserved - {RETAIN}" for label in labels]
    task = "[keyframe completion + reference generation]" if keys else "[reference generation]"   # handler prompt_enhancer.py ~288
    return (f"subject_definitions:\n{subjects}\nsummary:\n{task} {action_of(shot).split(';')[0]}\n"
            f"retention_analysis:\n" + "\n".join(retention) + "\n"
            f"detailed_description:\n{body}\noverall_soundscape: {sound}\nnon_diegetic_music: N/A")


def compile_direction(shot):
    """The full rich spec, kept unchanged next to the settings as <id>.direction.json."""
    return shot


def check_turbo(s, turbo):
    """Singularity v2 with a Pika-Labs Turbo LoRA (sing4, sing8): the Turbo LoRA is the only adapter (never with the official Pika
    adapter), with euler, the file's own step count, multiplier 1.0, CFG 1, one phase, flow shift 12, empty custom sigmas, no skipping."""
    if s["model_type"] != SING_MODEL:
        raise ValueError("the Pika Turbo LoRA runs on Singularity v2 only (routes sing4 and sing8)")
    if not turbo:
        raise ValueError("Singularity v2 runs only with its Pika Turbo LoRA (routes sing4 and sing8)")
    if len(s["activated_loras"]) != 1:
        raise ValueError("the Pika Turbo LoRA must be the only adapter: never with the official Pika adapter or another LoRA")
    steps = {TURBO_URL + lora: n for lora, n in TURBO.values()}[turbo[0]]
    want = ("euler", steps, "1.0", 1, 1, 12, "", "")
    got = (s["sample_solver"], s["num_inference_steps"], s["loras_multipliers"], s["guidance_scale"], s["guidance_phases"],
           s["flow_shift"], s["custom_sigmas"], s["skip_steps_cache_type"])
    if got != want:
        raise ValueError(f"Pika Turbo {steps}-step LoRA requires euler, {steps} steps, multiplier 1.0, CFG 1, one phase, flow shift 12, "
                         "empty custom sigmas and no skipping")


def check_combo(s):
    """The handler's Pika rule (minimax_h3_handler.py lines 1007-1014): the pika_renoise sampler and the Pika adapter come together,
    on an FL2VA or Ref2VA model with that family's own adapter, 6 steps, flow shift 12, one phase, empty custom sigmas, no skipping.
    Singularity v2 (routes sing4, sing8) runs only with its Pika Turbo LoRA: check_turbo."""
    known = {LORA_URL + lora for _, lora, _ in PRESET.values()} | {TURBO_URL + lora for lora, _ in TURBO.values()}
    if any(lora not in known for lora in s["activated_loras"]):
        raise ValueError("activated_loras must hold only the adapters this director builds (the Pika preset per mode, or a Turbo LoRA)")
    turbo = [lora for lora in s["activated_loras"] if lora.startswith(TURBO_URL)]
    if turbo or s["model_type"] == SING_MODEL:
        return check_turbo(s, turbo)
    pika_loras = [lora for lora in s["activated_loras"] if "pika_h3_flex" in lora]
    pika_sampler = s["sample_solver"] == "pika_renoise"
    if not pika_sampler and not pika_loras:
        return
    if not (pika_sampler and pika_loras):
        raise ValueError("Pika H3 Flex: the pika_renoise sampler and the Pika adapter must be used together")
    if s["model_type"] not in PIKA_MODELS:
        raise ValueError("Pika H3 Flex requires a standard FL2VA or Ref2VA model")
    family = "fl2va" if s["model_type"] == PRESET["fl2va"][0] else "ref2va"
    if len(pika_loras) != 1 or f"pika_h3_flex_{family}_6step" not in pika_loras[0]:
        raise ValueError(f"Pika H3 Flex on {family} needs its own {family} adapter and no other Pika adapter")
    if (s["num_inference_steps"], s["flow_shift"], s["guidance_phases"], s["custom_sigmas"]) != (6, 12, 1, ""):
        raise ValueError("Pika H3 Flex requires 6 steps, flow shift 12, one phase and empty custom sigmas")
    if s["skip_steps_cache_type"] != "":
        raise ValueError("Pika H3 Flex requires Steps Skipping off")


def route_preset(shot, route):
    """(model_type, activated_loras, sample_solver, steps, video_prompt_type) of one shot. pika6 is the proven Pika preset of its mode;
    sing4 and sing8 are Singularity v2 Ref2VA with their Pika-Labs Turbo LoRA (euler, that file's own step count)."""
    if route == "pika6":
        model, lora, video_prompt_type = PRESET[shot["mode"]]
        return model, [LORA_URL + lora], shot.get("sampler", "pika_renoise"), 6, video_prompt_type
    lora, steps = TURBO[route]
    return SING_MODEL, [TURBO_URL + lora], "euler", steps, PRESET["ref2va"][2]


def resolution_of(shot):
    aspect = shot.get("aspect", "9:16")
    if aspect not in RES:
        raise ValueError(f"{shot.get('id')}: aspect must be 9:16 or 16:9")
    res = shot.get("resolution", RES[aspect])
    if res not in RES_OPTIONS[aspect]:
        raise ValueError(f"{shot.get('id')}: resolution {res} is not one of {', '.join(RES_OPTIONS[aspect])} for {aspect}")
    return res


def settings_for(shot, bible=None, to_path=None, require_bible=False):
    """One Wan2GP settings dict. to_path maps a relative image path to the path the runner will use (default: unchanged).
    require_bible: refuse to build without a style bible (preflight and T0 builds)."""
    sid = check_shot_id(shot.get("id"))
    if require_bible and bible is None:
        raise ValueError(f"{sid}: a style bible is required for this build (pass the project's style file)")
    if is_rich(shot):   # a rich shot must pass the contract first (shot_schema imports this module, hence the local import)
        from shot_schema import validate_shot
        problems = [p for p in validate_shot(shot) if not p.split(": ", 1)[-1].startswith("WARN:")]
        if problems:
            raise ValueError("; ".join(problems))
    if shot["mode"] not in PRESET:
        raise ValueError(f"{sid}: mode must be fl2va or ref2va")
    route = shot.get("route", "pika6")
    if route not in ROUTES:
        raise ValueError(f"{sid}: route must be one of {', '.join(ROUTES)}")
    if route != "pika6":
        if shot["mode"] != "ref2va":
            raise ValueError(f"{sid}: route {route} is Singularity v2 on Ref2VA: use mode ref2va")
        if "sampler" in shot:
            raise ValueError(f"{sid}: route {route} sets its own sampler (euler): remove sampler")
    refs = shot.get("refs") or []
    if shot["mode"] == "ref2va" and not (refs and shot.get("subjects")):
        raise ValueError(f"{sid}: ref2va needs refs and subjects")
    if shot["mode"] == "ref2va" and subject_problems(refs, shot["subjects"]):
        raise ValueError(f"{sid}: " + "; ".join(subject_problems(refs, shot["subjects"])))
    if shot["mode"] == "fl2va" and refs:
        raise ValueError(f"{sid}: fl2va takes start and end frames only; use mode ref2va for references")
    if shot["mode"] == "fl2va" and not (start_of(shot) or end_of(shot)):
        raise ValueError(f"{sid}: fl2va needs a start or end keyframe")
    images = [p for p in (start_of(shot), end_of(shot), *refs) if p]
    for p in images:
        safe_path(p)
    frames = frames_for_shot(shot)
    model, loras, solver, steps, video_prompt_type = route_preset(shot, route)
    to = to_path or (lambda p: p)
    image_prompt_type = ("S" if start_of(shot) else "") + ("E" if end_of(shot) else "")
    declared = shot.get("image_prompt_type")   # M-02: a declared mode must match the images (S = start only, no end image)
    if declared not in (None, image_prompt_type):
        raise ValueError(f"{sid}: image_prompt_type {declared!r} does not match its images ({image_prompt_type!r})")
    s = {"model_type": model, "settings_version": 2.82, "activated_loras": loras, "loras_multipliers": "1.0",
         "sample_solver": solver, "num_inference_steps": steps, "guidance_phases": 1, "guidance_scale": 1,
         "flow_shift": 12, "custom_sigmas": "", "skip_steps_cache_type": "", "custom_settings": {"audio_refinement": "none"},
         "prompt": shot.get("prompt_override") or prompt_for(shot, frames, bible), "image_mode": 0, "video_length": frames, "sliding_window_size": FRAMES_MAX,
         "resolution": resolution_of(shot), "image_prompt_type": image_prompt_type, "video_prompt_type": video_prompt_type,
         "audio_prompt_type": "", "seed": shot.get("seed", 42)}
    if start_of(shot): s["image_start"] = to(start_of(shot))
    if end_of(shot): s["image_end"] = to(end_of(shot))
    if shot["mode"] == "ref2va":   # the handler's own Ref2VA defaults (update_default_settings), set explicitly for headless runs
        s.update({"image_refs": [to(r) for r in refs], "image_refs_relative_size": 100, "remove_background_images_ref": 0})
    check_combo(s)
    return s


def main(shots_path, out_dir, style):
    """Writes settings_<id>.json (and <id>.direction.json for rich shots). Duplicate ids and any bad shot stop the run before
    a file is written; the style project is mandatory (identity text, require_bible)."""
    shots = json.loads(Path(shots_path).read_text(encoding="utf-8"))
    check_unique_ids(shots)
    bible = style_bible.load(style)
    built = [(shot, settings_for(shot, bible, require_bible=True)) for shot in shots]
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    for shot, s in built:
        (out / f"settings_{shot['id']}.json").write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")
        if is_rich(shot):
            (out / f"{shot['id']}.direction.json").write_text(json.dumps(compile_direction(shot), indent=1, ensure_ascii=False), encoding="utf-8")
        print(shot["id"], s["video_length"], "frames")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: python h3_director.py shots.json out_dir style_project")
    main(*sys.argv[1:4])
