"""Compile shots to the sing8 prompts and the Route C ComfyUI payload. Story-agnostic.

compile_fl2va_prompt is the one prompt entry point: FL2VA-routed shots get the 4-part FL2VA layout, Ref2VA-routed
shots get the official 6-section ref-en.txt layout. Pure-Foley: no speech ever reaches the prompt (refused at source),
Flow chips and storyboard tags are stripped before emission, and the mouth lock sits in the description.
Node class names come from an unverified spec: every payload carries "_unverified_node_classes": true.
"""
import json
import os

from h3.router import REF2VA, ref_inventory, route_shot, video_shift_for, workflow_mode
from h3.schema_and_linter import (MOUTH_LOCK_SENTENCE, STAGES, clean_text, compiled_soundscape, lint_story,
                                  lint_workflow, refuse_speech_in_source, resolve_keyframes, sanitize_single_line as san,
                                  strip_tags, stripped_tags_of, voice_context, voice_mode)

TEXT_ENCODER = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"
AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"
OFFSCREEN_LIP = "The on-screen character's lips remain completely closed."  # official base-en s4.4 (voiceover)


def _mouth_lock(dlg, silent=True):
    """The mouth-state rule, plus the positive lock sentence when nobody on screen speaks (English voice mode)."""
    return f"{clean_text(dlg['mouth_state_rule'])} {MOUTH_LOCK_SENTENCE}" if silent else clean_text(dlg["mouth_state_rule"])


def _speech_sentences(shot, registry):
    """English H3 speech in the official form (base-en s4.4): `{cue}, {character} ({Sx}), {voice description}, says:
    <d>[English] {text}</d>`; off-screen lines say `says in an off-screen voiceover` and state the lips stay closed.
    The voice description is the character's anchor sentence, verbatim in every shot (UNVERIFIED that it fixes the voice)."""
    out = []
    for u in (shot.get("dialogue_and_lip_lock") or {}).get("utterances") or []:
        ch = registry["characters"][u["character_id"]]
        desc = ch["voice_anchor"]["voice_description"]
        who = f"{clean_text(ch['short_disambiguator'])} ({u['speaker_id']}), {desc}"
        text = san(strip_tags(u["text"])[0])
        cue = clean_text(u.get("voiceover_action_cue") or "")
        if u.get("is_offscreen_voiceover"):
            line = f"{who}, says in an off-screen voiceover: <d>[English] {text}</d> {OFFSCREEN_LIP}"
        else:
            line = f"{who}, says: <d>[English] {text}</d>"
        out.append(f"{cue} {line}".strip())
    return " ".join(out)


def _fl2va(shot, registry):
    prof, style = registry["execution_profile"], registry["style_lock"]
    fps, pf = prof["fps"], shot["timing_and_lattice"]["pixel_frames"]
    stage = {k: clean_text(shot["motion_7_stage"][k]) for k in STAGES}
    cadence = clean_text(shot["anime_timing_cadence"]["cadence_clause"])
    cam = clean_text(shot["camera"]["compiled_clause"])
    ctx = voice_context(shot, registry)
    speech = _speech_sentences(shot, registry) if ctx else ""
    body = san(" ".join([
        f"[Shot 1] {clean_text(style['mandatory_prefix'])}, preserving the exact character design, "
        "color palette, lighting, and environment in Picture 1 and Picture 2.",
        stage["1_starting_state"], stage["2_anticipation"], stage["3_initiation"],
        stage["4_drive"], stage["5_contact_approach"], cadence, cam, speech,
        _mouth_lock(shot["dialogue_and_lip_lock"], ctx["silent"] if ctx else True),
        stage["6_impact_result"], stage["7_settled_end_state"]]))
    snd = compiled_soundscape(shot, registry)  # shared with the linter (SD-03)
    music = clean_text(shot["sound_plan"]["non_diegetic_music"])
    header = (f"How the reference pictures align with the target video — Picture 1 (from Shot 1) "
              f"aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns "
              f"with the {pf / fps:.2f}-second mark of the target video.")
    prompt = (f"{header}\n\nintegrated_multimodal_description: {body}\n"
              f"overall_soundscape: {snd}\nnon_diegetic_music: {music}")
    return prompt, body


def _ref2va(shot, registry):
    """Official 6 sections: subject_definitions, summary, retention_analysis, detailed_description,
    overall_soundscape, non_diegetic_music (hard-locked N/A)."""
    inv, cont = ref_inventory(shot), shot["continuity_and_seam_lock"]
    chars = registry["characters"]
    subj = []
    for i, cid in enumerate(cont["subjects_present"], 1):
        name = clean_text(chars[cid]["short_disambiguator"])
        pic = f", design locked to <Picture {i}>" if i <= len(inv["images"]) else ""
        subj.append(f"<Subject {i}> is {name} ({cid}){pic}.")
    if voice_mode(registry):  # official ref-en s2.4: an <Audio N> is the voice timbre of the speaker it is bound to
        sid_of = {cid: sid for sid, cid in (registry.get("voice_speaker_map") or {}).items()}
        for k, cid in enumerate(inv["audio"], 1):
            subj.append(f"<Audio {k}> is the voice timbre reference for {sid_of.get(cid, cid)} "
                        f"({clean_text(chars[cid]['short_disambiguator'])}): {chars[cid]['voice_anchor']['voice_description']}.")
    ctx = voice_context(shot, registry)
    speech = _speech_sentences(shot, registry) if ctx else ""
    pictures = ", ".join(f"<Picture {i}>" for i in range(1, len(inv["images"]) + 1)) or "the reference cards"
    videos = " ".join(f"<Video {i}> supplies the motion reference." for i in range(1, len(inv["videos"]) + 1))
    stage = {k: clean_text(shot["motion_7_stage"][k]) for k in STAGES}
    cadence = clean_text(shot["anime_timing_cadence"]["cadence_clause"])
    cam = clean_text(shot["camera"]["compiled_clause"])
    body = san(" ".join([stage["1_starting_state"], stage["2_anticipation"], stage["3_initiation"],
                         stage["4_drive"], stage["5_contact_approach"], cadence, cam, speech,
                         _mouth_lock(shot["dialogue_and_lip_lock"], ctx["silent"] if ctx else True),
                         stage["6_impact_result"], stage["7_settled_end_state"]]))
    sections = [
        ("subject_definitions", san(" ".join(subj)) or "No named subject is in frame."),
        ("summary", san(f"{clean_text(shot['story_beat'])} {clean_text(shot['emotional_objective'])}")),
        ("retention_analysis", san(f"Keep the {clean_text(cont['shot_scale'])} framing, the environment, palette and "
                                   f"lighting of {pictures} steady; screen direction {clean_text(cont['screen_direction_vector'])}, "
                                   f"camera axis {clean_text(cont['camera_axis_side'])}. {videos}")),
        ("detailed_description", body),
        ("overall_soundscape", compiled_soundscape(shot, registry)),
        ("non_diegetic_music", "N/A"),
    ]
    text = "\n".join(f"{name}: {value}" for name, value in sections)
    return text, body


def compile_fl2va_prompt(shot, registry):
    """The prompt of one shot (FL2VA layout, or the Ref2VA 6-section layout for Ref2VA-routed shots).
    Raises PromptRefused (SL-01..SL-04) when speech is present in the source."""
    refuse_speech_in_source(shot, voice=voice_mode(registry))
    if route_shot(shot) == REF2VA:
        prompt, body = _ref2va(shot, registry)
    else:
        prompt, body = _fl2va(shot, registry)
    return {"shot_id": shot["shot_id"], "compiled_prompt": prompt,
            "char_counts": {"imd_body": len(body), "total": len(prompt)},
            "stripped_tags": stripped_tags_of(shot)}


def compile_comfyui_workflow(shot, registry, compiled_prompt, enable_2k_second_pass=False, keyframes=None):
    prof = registry["execution_profile"]
    k, t = shot["fl2va_keyframes"], shot["timing_and_lattice"]
    route = route_shot(shot)
    if route not in ("FL2VA", REF2VA):
        raise ValueError(f"route {route} has no sing8 workflow (only FL2VA and Ref2VA)")
    ns = prof["checkpoint_architecture_namespace"]
    kf = keyframes or {"picture_1": k.get("picture_1_path"), "picture_2": k.get("picture_2_path")}
    w, h = prof["base_resolution"]
    ms = prof["model_sampling_av"]
    refs = ref_inventory(shot)["images"]

    def node(title, cls, **inputs):
        return {"_title": title, "class_type": cls, "inputs": inputs}

    nodes = {
        "1": node("1_CheckpointLoader", "MiniMaxH3CheckpointLoader", ckpt_name=prof["checkpoint_name"]),
        "2": node("2_LoraLoader", "LoraLoaderModelOnly", model=["1", 0],
                  lora_name=prof["mode_to_lora_map"][f"{workflow_mode(route)}_{ns}"],
                  strength_model=prof["runtime_lora_strength"]),
        "3": node("3_ModelSamplingAV", "ModelSamplingAV", model=["2", 0],
                  video_shift=video_shift_for(prof, route), audio_shift=ms["audio_shift"]),
        "4": node("4_TextEncoder", "MiniMaxH3TextEncode", text_encoder=TEXT_ENCODER, prompt=compiled_prompt),
        "5": node("5_FL2VAConditioning", "MiniMaxH3ImageToVideo", positive=["4", 0],
                  first_frame=kf["picture_1"], last_frame=kf["picture_2"], width=w, height=h,
                  length=t["pixel_frames"], expected_latent_slots=t["latent_slots"],
                  ref_image_size=prof["ref_image_size_policy"], reference_images=refs),
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
    ep = next((e for e in story["episodes"] if e.get("episode_id") == episode_id), None)
    if ep is None:
        raise ValueError(f"episode {episode_id!r} is not in the story")
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
        try:
            wf = compile_comfyui_workflow(shot, reg, text, second_pass, kf)
        except KeyError as exc:                  # a profile without the LoRA / shift entry for this route
            raise ValueError(f"{sid}: execution profile has no entry {exc} for this route") from exc
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
