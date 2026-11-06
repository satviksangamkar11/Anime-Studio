"""Compile shots to the sing8 FL2VA/REF2VA prompt and the Route C ComfyUI payload. Story-agnostic.

Node class names come from an unverified spec: every payload carries "_unverified_node_classes": true.
"""
import json
import os

from h3.schema_and_linter import (STAGES, compiled_soundscape, lint_story, lint_workflow, resolve_keyframes,
                                  sanitize_single_line as san)

TEXT_ENCODER = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"
AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"


def compile_fl2va_prompt(shot, registry):
    prof, style = registry["execution_profile"], registry["style_lock"]
    fps = prof["fps"]
    pf = shot["timing_and_lattice"]["pixel_frames"]
    stage = {k: san(shot["motion_7_stage"][k]) for k in STAGES}
    cadence = san(shot["anime_timing_cadence"]["cadence_clause"])
    cam = san(shot["camera"]["compiled_clause"])
    dlg = shot["dialogue_and_lip_lock"]
    parts = [san(dlg["mouth_state_rule"])]
    for u in dlg["utterances"]:
        name = san(registry["characters"][u["character_id"]]["short_disambiguator"])
        cue, spk = san(u["voiceover_action_cue"]), san(u["speaker_id"])
        lang, text = san(u["language"]), san(u["text"])
        if u["is_offscreen_voiceover"]:
            parts.append(f"{cue}, {name} ({spk}) says in an off-screen voiceover: "
                         f"<d>[{lang}] {text}</d> {san(u['lip_lock_clause'])}")
        else:
            parts.append(f"{cue}, {name} ({spk}) says: <d>[{lang}] {text}</d>")
    body = san(" ".join([
        f"[Shot 1] {san(style['mandatory_prefix'])}, preserving the exact character design, "
        "color palette, lighting, and environment in Picture 1 and Picture 2.",
        stage["1_starting_state"], stage["2_anticipation"], stage["3_initiation"],
        stage["4_drive"], stage["5_contact_approach"], cadence, cam, *parts,
        stage["6_impact_result"], stage["7_settled_end_state"]]))
    snd = compiled_soundscape(shot, registry)  # shared with the linter (SD-03)
    music = san(shot["sound_plan"]["non_diegetic_music"])
    header = (f"How the reference pictures align with the target video — Picture 1 (from Shot 1) "
              f"aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns "
              f"with the {pf / fps:.2f}-second mark of the target video.")
    prompt = (f"{header}\n\nintegrated_multimodal_description: {body}\n"
              f"overall_soundscape: {snd}\nnon_diegetic_music: {music}")
    return {"shot_id": shot["shot_id"], "compiled_prompt": prompt,
            "char_counts": {"imd_body": len(body), "total": len(prompt)}}


def compile_comfyui_workflow(shot, registry, compiled_prompt, enable_2k_second_pass=False, keyframes=None):
    prof = registry["execution_profile"]
    k, t = shot["fl2va_keyframes"], shot["timing_and_lattice"]
    mode, ns = k["mode"], prof["checkpoint_architecture_namespace"]
    kf = keyframes or {"picture_1": k["picture_1_path"], "picture_2": k["picture_2_path"]}
    w, h = prof["base_resolution"]
    ms = prof["model_sampling_av"]

    def node(title, cls, **inputs):
        return {"_title": title, "class_type": cls, "inputs": inputs}

    nodes = {
        "1": node("1_CheckpointLoader", "MiniMaxH3CheckpointLoader", ckpt_name=prof["checkpoint_name"]),
        "2": node("2_LoraLoader", "LoraLoaderModelOnly", model=["1", 0],
                  lora_name=prof["mode_to_lora_map"][f"{mode}_{ns}"], strength_model=prof["runtime_lora_strength"]),
        "3": node("3_ModelSamplingAV", "ModelSamplingAV", model=["2", 0],
                  video_shift=ms["mode_to_video_shift_map"][mode], audio_shift=ms["audio_shift"]),
        "4": node("4_TextEncoder", "MiniMaxH3TextEncode", text_encoder=TEXT_ENCODER, prompt=compiled_prompt),
        "5": node("5_FL2VAConditioning", "MiniMaxH3ImageToVideo", positive=["4", 0],
                  first_frame=kf["picture_1"], last_frame=kf["picture_2"], width=w, height=h,
                  length=t["pixel_frames"], expected_latent_slots=t["latent_slots"],
                  ref_image_size=prof["ref_image_size_policy"]),
        "6": node("6_BasicGuider", "BasicGuider", model=["3", 0], conditioning=["5", 0],
                  cfg=prof["cfg"], has_negative_branch=False),
        "7": node("7_KSampler", "KSampler", guider=["6", 0], latent_image=["5", 1],
                  steps=prof["steps_nfe"], sampler_name=prof["sampler_name"], scheduler=prof["scheduler"]),
        "8": node("8_VideoVAEDecode", "VideoVAEDecode", samples=["7", 0], vae_name=VIDEO_VAE, precision="fp16"),
        "9": node("9_AudioVAEDecode", "AudioVAEDecode", samples=["7", 0], vae_name=AUDIO_VAE, precision="fp32"),
    }
    if enable_2k_second_pass:  # second-pass class names and wiring are unverified
        if "upscale_resolution" not in prof:
            raise ValueError("second pass needs execution_profile.upscale_resolution")
        nodes["10"] = node("10_SeparateAVLatent", "SeparateAVLatent", samples=["7", 0])
        nodes["11"] = node("11_LatentUpscaler3D", "LatentUpscaler3D", samples=["10", 0],
                           target_resolution=prof["upscale_resolution"])
        nodes["12"] = node("12_DirectorRefit2K", "DirectorRefit2K", samples=["11", 0])
        nodes["13"] = node("13_ConcatAVLatent", "ConcatAVLatent", video=["12", 0], audio=["10", 1])
    return {"shot_id": shot["shot_id"], "_unverified_node_classes": True, "nodes": nodes}


def compile_episode(story, episode_id, out_dir, shot_ids=None, second_pass=False):
    """Lint the episode first (raises ValueError on any error), then write <out>/<shot_id>/prompt.txt and workflow.json."""
    ep = next(e for e in story["episodes"] if e["episode_id"] == episode_id)
    reg = story["registry"]
    res = lint_story({"registry": reg, "episodes": [ep]})
    if res["errors"]:
        raise ValueError("\n".join(res["errors"]))
    written, shots = [], ep["shots"]
    for i, shot in enumerate(shots):
        sid = shot["shot_id"]
        if shot_ids is not None and sid not in shot_ids:
            continue
        prev = shots[i - 1] if i else None
        kf = resolve_keyframes(shot, prev, ep["asset_root"])
        text = compile_fl2va_prompt(shot, reg)["compiled_prompt"]
        wf = compile_comfyui_workflow(shot, reg, text, second_pass, kf)
        lint = lint_workflow(wf, shot, reg["execution_profile"])
        if lint["errors"]:
            raise ValueError("\n".join(lint["errors"]))
        d = os.path.join(out_dir, sid)
        os.makedirs(d, exist_ok=True)
        p_prompt, p_wf = os.path.join(d, "prompt.txt"), os.path.join(d, "workflow.json")
        with open(p_prompt, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        with open(p_wf, "w", encoding="utf-8", newline="\n") as f:
            json.dump(wf, f, ensure_ascii=False, indent=2)
        written += [p_prompt, p_wf]
    return written
