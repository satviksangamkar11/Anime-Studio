"""5-mode H3 router for the sing8 route (owner master prompt V4, section 3.1). Pure functions, no I/O.

Modes: T2VA (0 images), I2VA (start frame only), L2VA (end frame only), FL2VA (both boundary frames),
Ref2VA (reference cards and no rigid boundary lock).
"""
from h3.shot_table_spec import MODES, REF2VA_LIMITS

ROUTES = MODES
REF2VA = "Ref2VA"


def _has(value):
    return isinstance(value, str) and value != ""


def ref_inventory(shot):
    """Reference lists of a shot as {images, videos, audio}; each defaults to []."""
    k = shot.get("fl2va_keyframes")
    k = k if isinstance(k, dict) else {}
    return {"images": _ref_list(k, "reference_images"), "videos": _ref_list(k, "reference_videos"),
            "audio": _ref_list(k, "reference_audio")}


def _ref_list(k, key):
    """A non-list value (a string, a dict) is not a reference list: count it as none here; RF-03 reports it."""
    v = k.get(key)
    return list(v) if isinstance(v, list) else []


def route_shot(shot):
    """The H3 mode of a shot: any audio reference -> Ref2VA (the only mode with documented <Audio N>, ref-en s2.4);
    reference cards without both boundary frames -> Ref2VA; otherwise by the boundary frames."""
    k = shot.get("fl2va_keyframes") or {}
    start, end = _has(k.get("picture_1_path")), _has(k.get("picture_2_path"))
    if ref_inventory(shot)["audio"]:
        return REF2VA
    if ref_inventory(shot)["images"] and not (start and end):
        return REF2VA
    if start and end:
        return "FL2VA"
    if start:
        return "I2VA"
    if end:
        return "L2VA"
    return "T2VA"


def ref2va_limit_problems(shot, voice=False):
    """[(code, message)] for the Ref2VA reference limits: <= 9 image refs, <= 3 video refs.
    Audio: 0 in pure-Foley mode (AU-01). In English H3 voice mode audio refs are voice anchors, counted and timed by
    voice_engine.audio_ref_problems (VA-05/VA-06), so they are not counted here."""
    inv, out = ref_inventory(shot), []
    k = shot.get("fl2va_keyframes")
    k = k if isinstance(k, dict) else {}
    for key in ("reference_images", "reference_videos", "reference_audio"):
        if k.get(key) is not None and not isinstance(k.get(key), list):
            out.append(("RF-03", f"{key} must be a list, got {type(k.get(key)).__name__}"))
    if len(inv["images"]) > REF2VA_LIMITS["image_refs"]:
        out.append(("RF-01", f"{len(inv['images'])} image refs, Ref2VA allows at most {REF2VA_LIMITS['image_refs']}"))
    if len(inv["videos"]) > REF2VA_LIMITS["video_refs"]:
        out.append(("RF-02", f"{len(inv['videos'])} video refs, Ref2VA allows at most {REF2VA_LIMITS['video_refs']}"))
    if not voice and inv["audio"]:
        out.append(("AU-01", "Ref2VA takes 0 audio refs in pure-Foley mode (no <Audio N>): voice references re-arm H3 speech"))
    return out


def ref2va_limits_ok(shot, voice=False):
    return not ref2va_limit_problems(shot, voice)


def video_shift_for(profile, route):
    """ComfyUI ModelSamplingAV video_shift from the profile: 12.0 style for Ref2VA, keyframe value otherwise."""
    shifts = profile["model_sampling_av"]["video_shift"]
    return shifts["ref2va"] if route == REF2VA else shifts["keyframe"]


def workflow_mode(route):
    """Key part of mode_to_lora_map: the Ref2VA LoRA is registered under REF2VA."""
    return "REF2VA" if route == REF2VA else route
