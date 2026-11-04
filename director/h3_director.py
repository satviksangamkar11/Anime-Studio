"""Anime studio director, Gate 4 -> Wan2GP: turns a shot list into one Wan2GP settings file per shot (MiniMax H3 + Pika H3 Flex 6 steps),
run headless on Kaggle with `python wgp.py --process <settings.json>` (proven 2026-11-04: S4 shot 3, Kaggle T4, 18m51s incl. downloads).

Shot list: JSON list of shots, each
  id            "SHOT-09"
  mode          "fl2va" (start/end frame) or "ref2va" (reference images; start/end frames still allowed)
  seconds       wanted length; rounded UP to H3's grid (107 + 17k frames at 24 fps, max 362)
  aspect        "9:16" (default) or "16:9"
  start, end    optional image paths (Flow keyframes after watermark removal); end is a target, not a lock
  refs          ref2va only: identity sheets, in order (<Picture 1>, <Picture 2>, ...)
  subjects      ref2va only: ["<Subject 1> is Bala Krishna in <Picture 1>", ...]
  style, world  one line each (describe the look; never name a film or show)
  action        what happens, with time codes ("0-1.5s ...; 1.5-4s ...")
  camera        one camera move
  sound         soundscape line ("" = quiet ambience); H3 audio is replaced in the edit unless kept on purpose
  seed          optional (default 42)
Usage: python h3_director.py shots.json out_dir"""
import json
import math
import sys
from pathlib import Path

FPS, FRAMES_MIN, FRAMES_STEP, FRAMES_MAX = 24, 107, 17, 362
RES = {"9:16": "480x832", "16:9": "832x480"}
PRESET = {   # Wan2GP's own "Pika H3 Flex ... Pruned 6 Steps" presets (shared/deepy/settings), commit bd1ff59
    "fl2va": ("minimax_h3_fl2va_pruned", "pika_h3_flex_fl2va_6step_v1_bf16.safetensors", ""),
    "ref2va": ("minimax_h3_ref2va_pruned", "pika_h3_flex_ref2va_6step_v1_bf16.safetensors", "I"),
}
LORA_URL = "https://huggingface.co/DeepBeepMeep/MiniMax-H3/resolve/main/loras/"
KEEP = "Keep every face, outfit, prop and background exactly as in the pictures; no new people; no style change; no on-screen text."


def frames_for(seconds):
    """Smallest legal H3 frame count covering `seconds` (107, 124, 141, ... 362)."""
    k = max(0, math.ceil((seconds * FPS - FRAMES_MIN) / FRAMES_STEP))
    frames = FRAMES_MIN + k * FRAMES_STEP
    if frames > FRAMES_MAX:
        raise ValueError(f"{seconds}s is longer than one H3 window ({FRAMES_MAX / FPS:.1f}s): split the shot")
    return frames


def prompt_for(shot):
    seconds = frames_for(shot["seconds"]) / FPS
    body = (f"[Shot 1] A {seconds:.1f}-second single take. {shot['style']} {shot['world']} {shot['action']} "
            f"Camera: {shot['camera']}. {KEEP}")
    sound = shot.get("sound") or "Quiet natural ambience only, no speech."
    if shot["mode"] == "fl2va":
        return f"integrated_multimodal_description: {body}\noverall_soundscape: {sound}\nnon_diegetic_music: N/A"
    subjects = "\n".join(shot["subjects"])
    return (f"subject_definitions:\n{subjects}\nsummary:\n[reference generation] {shot['action'].split(';')[0]}\n"
            f"detailed_description:\n{body}\noverall_soundscape: {sound}\nnon_diegetic_music: N/A")


def settings_for(shot):
    if shot["mode"] not in PRESET:
        raise ValueError(f"{shot['id']}: mode must be fl2va or ref2va")
    if shot["mode"] == "ref2va" and not (shot.get("refs") and shot.get("subjects")):
        raise ValueError(f"{shot['id']}: ref2va needs refs and subjects")
    if shot["mode"] == "fl2va" and not shot.get("start"):
        raise ValueError(f"{shot['id']}: fl2va needs a start keyframe")
    model, lora, video_prompt_type = PRESET[shot["mode"]]
    image_prompt_type = ("S" if shot.get("start") else "") + ("E" if shot.get("end") else "")
    s = {"model_type": model, "settings_version": 2.73, "activated_loras": [LORA_URL + lora], "loras_multipliers": "1.0",
         "sample_solver": "pika_renoise", "num_inference_steps": 6, "guidance_phases": 1, "guidance_scale": 1, "flow_shift": 12,
         "custom_sigmas": "", "skip_steps_cache_type": "", "custom_settings": {"audio_refinement": "none"},
         "prompt": prompt_for(shot), "image_mode": 0, "video_length": frames_for(shot["seconds"]), "sliding_window_size": FRAMES_MAX,
         "resolution": RES[shot.get("aspect", "9:16")], "image_prompt_type": image_prompt_type, "video_prompt_type": video_prompt_type,
         "audio_prompt_type": "", "seed": shot.get("seed", 42)}
    if shot.get("start"): s["image_start"] = shot["start"]
    if shot.get("end"): s["image_end"] = shot["end"]
    if shot["mode"] == "ref2va":   # the handler's own Ref2VA defaults (update_default_settings), set explicitly for headless runs
        s.update({"image_refs": list(shot["refs"]), "image_refs_relative_size": 100, "remove_background_images_ref": 0})
    return s


def main(shots_path, out_dir):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    for shot in json.loads(Path(shots_path).read_text(encoding="utf-8")):
        (out / f"settings_{shot['id']}.json").write_text(json.dumps(settings_for(shot), indent=1, ensure_ascii=False), encoding="utf-8")
        print(shot["id"], frames_for(shot["seconds"]), "frames")


if __name__ == "__main__":
    main(*sys.argv[1:3])
