"""Deterministic two-shot dry run: one FL2VA (start+end) and one Ref2VA (start+end+identity ref), no network."""
import ast
import base64
import json

from PIL import Image

import dry_run
import run_kaggle

SHARED = {"episode": 1, "aspect": "9:16", "style": "Flat 2D cel anime.", "world": "River at dawn.", "camera": "slow crane down",
          "sound": "river hush", "seconds": 5.2}
FL = dict(SHARED, id="SHOT-01", mode="fl2va", start="keyframes/A-START.png", end="keyframes/A-END.png",
          action="0-2s he steps forward; 2-5s he looks up.")
REF = dict(SHARED, id="SHOT-02", mode="ref2va", start="keyframes/B-START.png", end="keyframes/B-END.png", refs=["refs/krishna.png"],
           subjects=["<Subject 1> is Bala Krishna in <Picture 1>."], action="0-2s he turns; 2-5s he smiles.")
PIKA = {"sample_solver": "pika_renoise", "num_inference_steps": 6, "guidance_phases": 1, "guidance_scale": 1, "flow_shift": 12,
        "custom_sigmas": "", "loras_multipliers": "1.0", "skip_steps_cache_type": "", "settings_version": 2.73,
        "custom_settings": {"audio_refinement": "none"}, "image_mode": 0, "sliding_window_size": 362, "resolution": "480x832",
        "audio_prompt_type": "", "seed": 42}
LORA = "https://huggingface.co/DeepBeepMeep/MiniMax-H3/resolve/main/loras/"


def make_root(root):
    for name, colour in (("keyframes/A-START.png", "red"), ("keyframes/A-END.png", "green"), ("keyframes/B-START.png", "blue"),
                         ("keyframes/B-END.png", "white"), ("refs/krishna.png", "yellow")):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (48, 64), colour).save(root / name)


def embedded_blobs(script):
    """Every base64.b64decode("...") literal in the generated script, decoded as JSON, found by AST (not by string splitting)."""
    decoded = []
    for node in ast.walk(ast.parse(script)):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "b64decode" and node.args and isinstance(node.args[0], ast.Constant):
            text = node.args[0].value
            if text.startswith("__"):
                continue
            decoded.append(json.loads(base64.b64decode(text)))
    return decoded


def test_two_shots_build_into_one_deterministic_kaggle_script(tmp_path):
    make_root(tmp_path)
    script, meta = run_kaggle.build([FL, REF], tmp_path, "dry")
    assert script == run_kaggle.build([FL, REF], tmp_path, "dry")[0]   # same inputs, same script
    ast.parse(script)
    blobs = embedded_blobs(script)
    images = next(b for b in blobs if "SHOT-01" not in b)
    settings = next(b for b in blobs if "SHOT-01" in b)
    assert set(settings) == {"SHOT-01", "SHOT-02"} and meta["id"].endswith("/anime-dry")

    fl, ref = settings["SHOT-01"], settings["SHOT-02"]
    assert fl["video_length"] == 124 and ref["video_length"] == 124
    for path in (fl["image_start"], fl["image_end"], ref["image_start"], ref["image_end"], ref["image_refs"][0]):
        assert path.startswith("/kaggle/working/Wan2GP/inputs/") and path.endswith(".png"), path
        name = path.rsplit("/", 1)[1]
        assert base64.b64decode(images[name])[:4] == b"\x89PNG"
    assert fl["image_prompt_type"] == "SE" and ref["video_prompt_type"] == "I"

    assert ("For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced."
            in fl["prompt"])
    assert "subject_definitions:\n<Subject 1> is Bala Krishna in <Picture 3>." in ref["prompt"]
    assert "retention_analysis:\n" in ref["prompt"] and "fully_preserved" in ref["prompt"]


def test_pika_settings_are_the_proven_six_step_ones(tmp_path):
    make_root(tmp_path)
    script, _ = run_kaggle.build([FL, REF], tmp_path, "dry")
    settings = next(b for b in embedded_blobs(script) if "SHOT-01" in b)
    for sid, lora in (("SHOT-01", "pika_h3_flex_fl2va_6step_v1_bf16.safetensors"),
                      ("SHOT-02", "pika_h3_flex_ref2va_6step_v1_bf16.safetensors")):
        s = settings[sid]
        assert {k: s[k] for k in PIKA} == PIKA
        assert s["activated_loras"] == [LORA + lora]
    assert settings["SHOT-01"]["model_type"] == "minimax_h3_fl2va_pruned"
    assert settings["SHOT-02"]["model_type"] == "minimax_h3_ref2va_pruned"


def test_dry_run_writes_one_settings_file_per_shot(tmp_path):
    make_root(tmp_path / "root")
    shots = tmp_path / "shots.json"
    shots.write_text(json.dumps([FL, REF]), encoding="utf-8")
    dry_run.main(str(shots), str(tmp_path / "root"), str(tmp_path / "out"))
    for sid, length in (("SHOT-01", 124), ("SHOT-02", 124)):
        data = json.loads((tmp_path / "out" / f"settings_{sid}.json").read_text(encoding="utf-8"))
        assert data["video_length"] == length and data["image_start"].startswith("/kaggle/working/Wan2GP/inputs/")
