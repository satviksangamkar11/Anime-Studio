"""Shot normaliser for the Anime-Studio Universal Pipeline (WP4 part 1).

build_episodes(data, fps=24) -> (episodes, problems). It never raises: malformed input becomes a P0 FAIL entry
and the offending shot is skipped, the other shots still build. Input is not mutated.

Shape detection: h3 = has "timing_and_lattice" and "shot_id"; v2.2 = has "beats"; any other shot with "id" = legacy.

Source key per ShotView field:
  id              v2.2/legacy: "id"                       h3: "shot_id"
  episode         v2.2/legacy: "episode"                  h3: episodes[].episode_id (story dict)
  frames          v2.2/legacy: "edit_frames" if present, else director/h3_director.frames_for_shot(shot)
                  h3: timing_and_lattice.editorial_frames
  look            v2.2/legacy: "look"                     h3: metadata.look
  cast_ids        v2.2: cast[].id                         h3: continuity_and_seam_lock.subjects_present, then
                  dialogue_and_lip_lock.utterances[].character_id (de-duplicated, order kept)
  beats           v2.2: beats[] {t, hold, primary, bhava, acting, reveal}; t is shot-relative seconds
                  h3: virtual beats (see below); legacy: none
  impacts         look.impact_frames {at_s (shot-relative), type, frames}
  text.prompt     v2.2: style, world, action, camera, sound, beats[].acting
                  h3: motion_7_stage stage texts, camera.compiled_clause, anime_timing_cadence.cadence_clause,
                      dialogue mouth_state_rule, utterance voiceover_action_cue, sound_plan.overall_soundscape
                  (h3 keeps no compiled IMD body, so the parts that the director compiles into it are used)
  text.light_world  v2.2: light, world                    h3: continuity location_id, metadata.location, metadata.light
  first_dialogue  v2.2: earliest dialogue[].line_hi (line_en if no line_hi)
                  h3: text of the earliest utterance kept in the editorial window
  dialogue_starts v2.2: dialogue[].t[0]                   h3: utterance start_sec minus trim_in (clip time)
  camera_moves    v2.2: camera.move (or compositing.post with push/zoom) unless static -> [shot start]
                  h3: camera.motion_type unless "Static Shot" -> [shot start]        legacy: camera text, same rule
  caption_changes v2.2: look.hook.caption non-empty -> [shot start]; h3 and legacy: []
  purpose         v2.2: purpose                           h3: metadata.purpose; legacy: ""
  sound_text      v2.2/legacy: sound                      h3: sound_plan.overall_soundscape

h3 virtual beats (A15): one beat per motion_7_stage stage, spanning its stage_frame_spans window
(end inclusive in the spans, so end = b + 1). Frames are shifted by trim_in_frame and clipped to the editorial
window; beats that fall outside it are dropped. primary = stage "6_impact_result". hold = True when the stage
starts inside anime_timing_cadence.hold_window_frames (only the hold window; burst and settle are motion).
reveal = False. virtual = True. bhava = None.

Episode time of a shot = start_frame / fps + shot-relative seconds. Impact at_frame = start_frame +
round(at_s * fps); at_s = at_frame / fps.
"""
import math
import re
import sys
from pathlib import Path

FPS = 24
STAGES = ("1_starting_state", "2_anticipation", "3_initiation", "4_drive",
          "5_contact_approach", "6_impact_result", "7_settled_end_state")   # mirrors h3/schema_and_linter.py
IMPACT_STAGE = "6_impact_result"
STATIC_WORD = "static"

_DIRECTOR = Path(__file__).resolve().parents[1] / "director"
if str(_DIRECTOR) not in sys.path:
    sys.path.append(str(_DIRECTOR))
try:
    import h3_director as _h3d
    _H3D_ERROR = None
except Exception as exc:  # reported once as a P0 by build_episodes; never raised
    _h3d = None
    _H3D_ERROR = f"{type(exc).__name__}: {exc}"


def _p0(message, shot=None, episode=None):
    return {"rule": "P0", "level": "FAIL", "shot": shot, "episode": episode, "message": message}


def _is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _valid_key(key):
    return _is_int(key) or (isinstance(key, str) and key != "")


def _str(x):
    return x if isinstance(x, str) else ""


def _text(x):
    """Flatten a str / list / dict of text into one string. Numbers and other values are skipped."""
    if isinstance(x, str):
        return x.strip()
    if isinstance(x, list):
        return " ".join(t for t in (_text(i) for i in x) if t)
    if isinstance(x, dict):
        return " ".join(t for t in (_text(v) for v in x.values()) if t)
    return ""


def _two_numbers(x):
    return isinstance(x, list) and len(x) == 2 and all(_is_num(v) for v in x)


def _two_ints(x):
    return isinstance(x, list) and len(x) == 2 and all(_is_int(v) for v in x)


def shot_shape(shot):
    """"h3", "v22" or "legacy". Non-dict input is reported as "legacy" (build_episodes rejects it)."""
    if not isinstance(shot, dict):
        return "legacy"
    if "timing_and_lattice" in shot and "shot_id" in shot:
        return "h3"
    if "beats" in shot:
        return "v22"
    return "legacy"


def shot_id(shot):
    """The shot id string, or None when missing or not a non-empty string."""
    if not isinstance(shot, dict):
        return None
    value = shot.get("shot_id" if shot_shape(shot) == "h3" else "id")
    return value if isinstance(value, str) and value else None


def shot_look(shot):
    """The look dict (metadata.look for h3, look otherwise), or None."""
    if not isinstance(shot, dict):
        return None
    if shot_shape(shot) == "h3":
        meta = shot.get("metadata")
        look = meta.get("look") if isinstance(meta, dict) else None
    else:
        look = shot.get("look")
    return look if isinstance(look, dict) else None


def _director_frames(shot):
    if _h3d is None:
        raise RuntimeError(f"director/h3_director.py not importable ({_H3D_ERROR})")
    return _h3d.frames_for_shot(shot)


def shot_editorial_frames(shot, fps=FPS):
    """Editorial length in frames. Raises ValueError (or RuntimeError when the director is missing).

    fps is accepted for symmetry with build_episodes; lengths are frame counts and the director counts at 24 fps.
    """
    if shot_shape(shot) == "h3":
        t = shot.get("timing_and_lattice")
        ed = t.get("editorial_frames") if isinstance(t, dict) else None
        if not _is_int(ed) or ed < 1:
            raise ValueError("timing_and_lattice.editorial_frames must be an integer >= 1")
        return ed
    ed_sec = shot.get("editorial_duration_sec")
    if "lattice_n" in shot and _is_num(ed_sec) and ed_sec > 0:
        # V4 writer row (audit gap 4, 2026-11-08): the cut length is the editorial length. pixel_frames / the legacy
        # `seconds` include handle frames the viewer never sees, so they must not feed the reel clock or the retention windows.
        frames = round(ed_sec * fps)
        pf = shot.get("pixel_frames")
        if frames < 1 or (_is_int(pf) and frames > pf):
            raise ValueError(f"editorial_duration_sec {ed_sec!r} must be > 0 and within the {pf} rendered frames")
        return frames
    if "edit_frames" in shot:
        edit = shot["edit_frames"]
        if not _is_int(edit) or edit < 1:
            raise ValueError(f"edit_frames {edit!r} must be an integer >= 1")
        if "seconds" in shot or "render_frames" in shot:
            _director_frames(shot)   # checks edit_frames against the render length
        return edit
    if "seconds" not in shot and "render_frames" not in shot:
        raise ValueError("shot needs seconds or render_frames (or edit_frames)")
    return _director_frames(shot)


def _beat(start_rel, end_rel, hold=False, primary=False, bhava=None, acting="", reveal=False, virtual=False):
    return {"start_rel": start_rel, "end_rel": end_rel, "hold": hold, "primary": primary,
            "bhava": bhava, "acting": acting, "reveal": reveal, "virtual": virtual}


def _soft_look(raw, soft):
    if raw is None:
        return None
    if not isinstance(raw, dict):
        soft.append("look is not a dict; ignored")
        return None
    return raw


def _impacts(look, soft):
    raw = look.get("impact_frames") if look else None
    out = []
    if raw is None:
        return out
    if not isinstance(raw, list):
        soft.append("look.impact_frames is not a list; ignored")
        return out
    for i, imp in enumerate(raw):
        ok = (isinstance(imp, dict) and _is_num(imp.get("at_s")) and imp["at_s"] >= 0
              and isinstance(imp.get("type"), str) and imp["type"] != ""
              and _is_int(imp.get("frames")) and imp["frames"] >= 0)
        if not ok:
            soft.append(f"look.impact_frames[{i}] malformed; skipped")
            continue
        out.append((float(imp["at_s"]), imp["type"], imp["frames"]))
    return out


def _ids(seq, soft, label):
    out = []
    if seq is None:
        return out
    if not isinstance(seq, list):
        soft.append(f"{label} is not a list; ignored")
        return out
    for item in seq:
        ident = item.get("id") if isinstance(item, dict) else item
        if isinstance(ident, str) and ident and ident not in out:
            out.append(ident)
        else:
            soft.append(f"{label} entry without an id ignored")
    return out


def _caption_changes(look):
    hook = look.get("hook") if look else None
    caption = hook.get("caption") if isinstance(hook, dict) else None
    return [0.0] if isinstance(caption, str) and caption.strip() else []


def _range_start(value):
    """Start second of a time range given as [a, b] or as the text '1.2-1.6s'; None when it has none."""
    if _two_numbers(value):
        return float(value[0])
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*-", value) if isinstance(value, str) else None
    return float(m.group(1)) if m else None


def _v4_parts(shot, length_s):
    """Beats, cast ids, dialogue (start, text), camera move times and caption change times of a V4 writer row (per_second_directives)."""
    beats, camera_rel = [], []
    for d in shot.get("per_second_directives") or []:
        if not isinstance(d, dict) or not _is_num(d.get("t0")) or not _is_num(d.get("t1")) or d["t0"] >= length_s:
            continue
        acting = _str(d.get("action_pose_expression"))
        beats.append(_beat(float(d["t0"]), min(float(d["t1"]), length_s), hold="hold" in acting.lower(), acting=acting))
        cam = _str(d.get("camera")).strip().lower()
        if cam and STATIC_WORD not in cam and "hold" not in cam:
            camera_rel.append(float(d["t0"]))
    anchors = shot.get("reference_anchors") if isinstance(shot.get("reference_anchors"), dict) else {}
    cast = [p["id"] for p in anchors.get("character_positions") or [] if isinstance(p, dict) and isinstance(p.get("id"), str)]
    track = shot.get("audio_and_dialogue_track") if isinstance(shot.get("audio_and_dialogue_track"), dict) else {}
    dialogue = []
    for line in track.get("dialogue") or []:
        start = _range_start(line.get("time_range")) if isinstance(line, dict) else None
        if start is not None and 0 <= start < length_s:
            dialogue.append((start, _str(line.get("text"))))
    caption_rel = []
    by_lang = track.get("captions_by_lang")
    for cards in by_lang.values() if isinstance(by_lang, dict) else []:
        for card in cards if isinstance(cards, list) else []:
            start = _range_start(card.get("time_range")) if isinstance(card, dict) else None
            if start is not None and 0 <= start < length_s:
                caption_rel.append(start)
    return {"beats": beats, "cast_ids": cast, "dialogue": dialogue, "camera_rel": camera_rel, "caption_rel": caption_rel}


def _parse_rich_or_legacy(shot, fps):
    """v2.2 and legacy shots. Returns shot-relative parts. Raises ValueError for malformed input (P0)."""
    soft = []
    frames = shot_editorial_frames(shot, fps)
    length_s = frames / fps
    look = _soft_look(shot.get("look"), soft)

    beats = []
    beats_raw = []
    if "beats" in shot:
        beats_raw = shot["beats"]
        if not isinstance(beats_raw, list):
            raise ValueError("beats must be a list")
        for i, b in enumerate(beats_raw):
            if not isinstance(b, dict):
                raise ValueError(f"beats[{i}] is not a dict")
            t = b.get("t")
            if not _two_numbers(t) or t[0] < 0 or t[1] < t[0]:
                raise ValueError(f"beats[{i}].t must be [start, end] numbers with 0 <= start <= end")
            start, end = float(t[0]), float(t[1])
            if start >= length_s:
                continue                       # beyond the editorial end: dropped
            beats.append(_beat(start, min(end, length_s), hold=b.get("hold") is True,
                               primary=b.get("primary") is True, bhava=b.get("bhava") if isinstance(b.get("bhava"), str) else None,
                               acting=_str(b.get("acting")), reveal=b.get("reveal") is True))

    v4 = _v4_parts(shot, length_s) if isinstance(shot.get("per_second_directives"), list) else None
    if v4:   # the writer's V4 row (11-08 audit A): beats, cast, dialogue starts, camera moves and caption changes come from its columns
        beats = v4["beats"]
        beats_raw = [{"acting": b["acting"]} for b in beats]

    dialogue = []
    raw_dialogue = shot.get("dialogue")
    if v4:
        raw_dialogue = []
        dialogue = list(v4["dialogue"])
    if raw_dialogue is not None and not isinstance(raw_dialogue, list):
        soft.append("dialogue is not a list; ignored")
        raw_dialogue = []
    for i, d in enumerate(raw_dialogue or []):
        if not isinstance(d, dict) or not _two_numbers(d.get("t")):
            soft.append(f"dialogue[{i}] has no valid t; ignored")
            continue
        start = float(d["t"][0])
        if 0 <= start < length_s:
            dialogue.append((start, _str(d.get("line_hi")) or _str(d.get("line_en"))))

    camera = shot.get("camera")
    move = camera.get("move") if isinstance(camera, dict) else camera
    move = _str(move).strip()
    compositing = shot.get("compositing")
    post = _str(compositing.get("post")).lower() if isinstance(compositing, dict) else ""
    moved = (move != "" and STATIC_WORD not in move.lower()) or any(w in post for w in ("push", "zoom"))
    camera_rel = v4["camera_rel"] if v4 else ([0.0] if moved else [])

    prompt_parts = [_text(shot.get(k)) for k in ("style", "world", "action")]
    prompt_parts.append(_text(camera))
    prompt_parts.append(_text(shot.get("sound")))
    prompt_parts += [_text(b.get("acting")) for b in beats_raw]
    light_world = " ".join(p for p in (_text(shot.get("light")), _text(shot.get("world"))) if p)

    dialogue.sort(key=lambda d: d[0])
    return {
        "frames": frames,
        "look": look,
        "beats": beats,
        "impacts": _impacts(look, soft),
        "cast_ids": v4["cast_ids"] if v4 else _ids(shot.get("cast"), soft, "cast"),
        "text": {"prompt": "\n".join(p for p in prompt_parts if p), "light_world": light_world},
        "first_dialogue": dialogue[0][1] if dialogue else None,
        "dialogue_rel": [d[0] for d in dialogue],
        "camera_rel": camera_rel,
        "caption_rel": sorted(set(_caption_changes(look) + (v4["caption_rel"] if v4 else []))),
        "purpose": _str(shot.get("purpose")),
        "sound_text": _str(shot.get("sound")),
        "soft": soft,
    }


def _parse_h3(shot, fps):
    """h3 shots. Returns shot-relative parts (editorial time). Raises ValueError for malformed input (P0)."""
    soft = []
    timing = shot["timing_and_lattice"]
    if not isinstance(timing, dict):
        raise ValueError("timing_and_lattice must be a dict")
    trim_in = timing.get("trim_in_frame")
    if not _is_int(trim_in) or trim_in < 0:
        raise ValueError("timing_and_lattice.trim_in_frame must be an integer >= 0")
    frames = shot_editorial_frames(shot, fps)

    meta = shot.get("metadata")
    if meta is not None and not isinstance(meta, dict):
        soft.append("metadata is not a dict; ignored")
        meta = {}
    meta = meta or {}
    look = _soft_look(meta.get("look"), soft)

    motion = shot.get("motion_7_stage")
    motion = motion if isinstance(motion, dict) else {}
    spans = motion.get("stage_frame_spans")
    cadence = shot.get("anime_timing_cadence")
    cadence = cadence if isinstance(cadence, dict) else {}
    hold_win = cadence.get("hold_window_frames")
    hold_ok = _two_ints(hold_win)
    if hold_win is not None and not hold_ok:
        soft.append("anime_timing_cadence.hold_window_frames malformed; no hold beats")
    if not isinstance(spans, dict):
        soft.append("motion_7_stage.stage_frame_spans missing; no beats")
        spans = {}

    beats = []
    for stage in STAGES:
        span = spans.get(stage)
        if not _two_ints(span) or span[0] < 0 or span[1] < span[0]:
            if stage in spans:
                soft.append(f"stage {stage} span malformed; skipped")
            continue
        a, b = span
        start = max(0, a - trim_in)            # clip-frame to editorial-frame
        end = min(frames, b + 1 - trim_in)     # span end is inclusive in the clip
        if end <= start:
            continue                           # outside the editorial window
        text = motion.get(stage)
        beats.append(_beat(start / fps, end / fps,
                           hold=hold_ok and hold_win[0] <= a <= hold_win[1],
                           primary=stage == IMPACT_STAGE,
                           acting=_str(text), virtual=True))

    cont = shot.get("continuity_and_seam_lock")
    cont = cont if isinstance(cont, dict) else {}
    dlg = shot.get("dialogue_and_lip_lock")
    dlg = dlg if isinstance(dlg, dict) else {}
    utterances = dlg.get("utterances")
    if utterances is None:
        utterances = []
    if not isinstance(utterances, list):
        soft.append("dialogue_and_lip_lock.utterances is not a list; ignored")
        utterances = []

    dialogue = []
    for i, u in enumerate(utterances):
        if not isinstance(u, dict) or not _is_num(u.get("start_sec")):
            soft.append(f"utterance[{i}] has no start_sec; ignored")
            continue
        rel = float(u["start_sec"]) - trim_in / fps
        if 0 <= rel < frames / fps:
            dialogue.append((rel, _str(u.get("text"))))
    dialogue.sort(key=lambda d: d[0])

    cast_ids = _ids(cont.get("subjects_present"), soft, "subjects_present")
    for u in utterances:
        ident = u.get("character_id") if isinstance(u, dict) else None
        if isinstance(ident, str) and ident and ident not in cast_ids:
            cast_ids.append(ident)

    camera = shot.get("camera")
    camera = camera if isinstance(camera, dict) else {}
    motion_type = _str(camera.get("motion_type")).strip()
    moved = motion_type != "" and STATIC_WORD not in motion_type.lower()

    stage_texts = [motion[s] for s in STAGES if isinstance(motion.get(s), str)]
    cadence_clause = cadence.get("cadence_clause")
    prompt_parts = stage_texts + [
        _text(camera.get("compiled_clause")), _text(cadence_clause), _text(dlg.get("mouth_state_rule"))]
    prompt_parts += [_text(u.get("voiceover_action_cue")) for u in utterances if isinstance(u, dict)]
    sound_plan = shot.get("sound_plan")
    sound_text = _str(sound_plan.get("overall_soundscape")) if isinstance(sound_plan, dict) else ""
    prompt_parts.append(sound_text)
    light_world = " ".join(p for p in (
        _text(cont.get("location_id")), _text(meta.get("location")), _text(meta.get("light"))) if p)

    return {
        "frames": frames,
        "look": look,
        "beats": beats,
        "impacts": _impacts(look, soft),
        "cast_ids": cast_ids,
        "text": {"prompt": "\n".join(p for p in prompt_parts if p), "light_world": light_world},
        "first_dialogue": dialogue[0][1] if dialogue else None,
        "dialogue_rel": [d[0] for d in dialogue],
        "camera_rel": [0.0] if moved else [],
        "caption_rel": [],
        "purpose": _str(meta.get("purpose")),
        "sound_text": sound_text,
        "soft": soft,
    }


def _try_parse(shot, fps, key, problems):
    sid = shot_id(shot)
    if sid is None:
        problems.append(_p0("shot has no id (shot_id for h3, id otherwise)", episode=key))
        return None
    try:
        parts = _parse_h3(shot, fps) if shot_shape(shot) == "h3" else _parse_rich_or_legacy(shot, fps)
    except Exception as exc:  # malformed input is reported, never raised
        problems.append(_p0(f"{type(exc).__name__}: {exc}", shot=sid, episode=key))
        return None
    parts.update({"id": sid, "shape": shot_shape(shot), "raw": shot, "key": key})
    return parts


def _view(parts, index, start, fps):
    t0 = start / fps
    beats = [{"start_s": t0 + b["start_rel"], "end_s": t0 + b["end_rel"], "hold": b["hold"],
              "primary": b["primary"], "bhava": b["bhava"], "acting": b["acting"],
              "reveal": b["reveal"], "virtual": b["virtual"]} for b in parts["beats"]]
    impacts = []
    for at_rel, typ, frames in parts["impacts"]:
        at_frame = start + round(at_rel * fps)
        impacts.append({"at_frame": at_frame, "at_s": at_frame / fps, "type": typ, "frames": frames})
    problems = list(parts["soft"])
    if not beats:
        problems.append("no beats")
    return {
        "id": parts["id"], "shape": parts["shape"], "index": index, "start_frame": start,
        "frames": parts["frames"], "look": parts["look"], "cast_ids": parts["cast_ids"],
        "beats": beats, "impacts": impacts, "text": parts["text"],
        "first_dialogue": parts["first_dialogue"],
        "dialogue_starts": [t0 + r for r in parts["dialogue_rel"]],
        "camera_moves": [t0 + r for r in parts["camera_rel"]],
        "caption_changes": [t0 + r for r in parts["caption_rel"]],
        "purpose": parts["purpose"], "sound_text": parts["sound_text"],
        "problems": problems, "raw": parts["raw"],
    }


def _assemble(parts_list, key, fps):
    shots = []
    start = 0
    for parts in parts_list:
        shots.append(_view(parts, len(shots), start, fps))
        start += parts["frames"]
    return {"key": key, "fps": fps, "shots": shots, "total_frames": start}


def _build_flat(data, fps, problems):
    groups = {}
    for n, shot in enumerate(data):
        if not isinstance(shot, dict):
            problems.append(_p0(f"item {n} is not a shot dict"))
            continue
        if shot_shape(shot) == "h3":
            problems.append(_p0("h3 shot in a flat list is not accepted; wrap h3 shots in an h3 story dict",
                                shot=shot_id(shot)))
            continue
        key = shot.get("episode")
        if not _valid_key(key):
            problems.append(_p0(f"shot {n} has no valid episode (int or non-empty str)", shot=shot_id(shot)))
            continue
        parts = _try_parse(shot, fps, key, problems)
        if parts is not None:
            groups.setdefault(key, []).append(parts)
    return [_assemble(parts_list, key, fps) for key, parts_list in groups.items()]


def _build_h3_story(data, fps, problems):
    episodes_raw = data.get("episodes")
    if not isinstance(episodes_raw, list):
        problems.append(_p0("h3 story needs an 'episodes' list"))
        return []
    episodes = []
    seen = set()
    for n, ep in enumerate(episodes_raw):
        key = ep.get("episode_id") if isinstance(ep, dict) else None
        if not isinstance(key, str) or key == "":
            problems.append(_p0(f"episode {n} needs a non-empty episode_id"))
            continue
        if key in seen:
            problems.append(_p0(f"duplicate episode_id {key!r}; second copy skipped", episode=key))
            continue
        shots_raw = ep.get("shots")
        if not isinstance(shots_raw, list) or not shots_raw:
            problems.append(_p0(f"episode {key!r} has no shots", episode=key))
            continue
        seen.add(key)
        parts_list = []
        for m, shot in enumerate(shots_raw):
            if not isinstance(shot, dict):
                problems.append(_p0(f"episode {key!r} item {m} is not a shot dict", episode=key))
                continue
            if shot_shape(shot) != "h3":
                problems.append(_p0("shot in an h3 story is not an h3 shot (needs timing_and_lattice and shot_id)",
                                    shot=shot_id(shot), episode=key))
                continue
            parts = _try_parse(shot, fps, key, problems)
            if parts is not None:
                parts_list.append(parts)
        episodes.append(_assemble(parts_list, key, fps))
    return episodes


def build_episodes(data, fps=FPS):
    """Normalise shots into episodes. Returns (episodes, problems); problems are P0 FAIL entries. Never raises."""
    problems = []
    if not _is_num(fps) or fps <= 0:
        return [], [_p0(f"fps must be a positive number, got {fps!r}")]
    if _h3d is None:
        problems.append(_p0(f"director/h3_director.py not importable; shots that need frames_for_shot are skipped: {_H3D_ERROR}"))
    try:
        if isinstance(data, dict):
            episodes = _build_h3_story(data, fps, problems)
        elif isinstance(data, list):
            episodes = _build_flat(data, fps, problems)
        else:
            problems.append(_p0(f"input must be a list of shots or an h3 story dict, got {type(data).__name__}"))
            episodes = []
    except Exception as exc:  # last-resort guard: never raise
        problems.append(_p0(f"unexpected error while building timeline: {type(exc).__name__}: {exc}"))
        episodes = []
    return episodes, problems
