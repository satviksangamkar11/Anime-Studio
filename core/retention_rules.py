"""Retention rules R1-R10 (WP4 part 3). Standard library only. Never raises.

Input: Episode dicts from core/timeline.py (see INTERFACES.md, "Timeline contract for WP4").
All times are episode seconds. Every threshold comes from core["retention"].
"""
import re

RULE_IDS = tuple(f"R{n}" for n in range(1, 11))
REQUIRED_RETENTION_KEYS = (
    "first_motion_s", "first_face_change_s", "hook_caption_max_words", "no_hold_before_s",
    "static_warn_s", "static_fail_s", "rehook_window_frac",
)
_FACE_WORDS = re.compile(r"\b(eyes?|brows?|mouth|lips)\b")
_PUSH_ZOOM_AT_ZERO = re.compile(r"\b(push|zoom)\b[^.;\n]*?\bstart\w*\b[^.;\n]{0,20}?(?<![\d.])0(?:\.0+)?(?![\d.])")
_BLACK_WORDS = ("fade", "title card", "black")


def _entry(rule, level, shot, episode, message):
    return {"rule": rule, "level": level, "shot": shot, "episode": episode, "message": message}


def _num(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate(episodes, core, story):
    """Return P0 entries for structural problems; [] when the input can be checked."""
    if not isinstance(episodes, list):
        return [_entry("P0", "FAIL", None, None, "episodes must be a list")]
    ret = core.get("retention") if isinstance(core, dict) else None
    if not isinstance(ret, dict) or any(not _num(ret.get(k)) and not isinstance(ret.get(k), list)
                                        for k in REQUIRED_RETENTION_KEYS):
        return [_entry("P0", "FAIL", None, None, "core['retention'] is missing or incomplete")]
    if story is not None and not isinstance(story, dict):
        return [_entry("P0", "FAIL", None, None, "story must be a dict or None")]
    if isinstance(story, dict) and story.get("episode_target_s") is not None:
        target = story["episode_target_s"]
        if not (isinstance(target, (list, tuple)) and len(target) == 2 and all(_num(v) for v in target)):
            return [_entry("P0", "FAIL", None, None, "story episode_target_s must be [lo, hi] numbers")]
    out = []
    for ep in episodes:
        if not isinstance(ep, dict):
            out.append(_entry("P0", "FAIL", None, None, "episode is not an object"))
            continue
        key = ep.get("key")
        if not _num(ep.get("fps")) or ep["fps"] <= 0 or not _num(ep.get("total_frames")):
            out.append(_entry("P0", "FAIL", None, key, "episode needs numeric fps and total_frames"))
            continue
        shots = ep.get("shots")
        if not isinstance(shots, list) or not shots:
            out.append(_entry("P0", "FAIL", None, key, "episode has no shots list"))
            continue
        for shot in shots:
            sid = shot.get("id") if isinstance(shot, dict) else None
            if not isinstance(shot, dict) or not _num(shot.get("start_frame")) or not _num(shot.get("frames")):
                out.append(_entry("P0", "FAIL", sid, key, "shot needs numeric start_frame and frames"))
                continue
            beats = shot.get("beats", [])
            if not isinstance(beats, list) or any(
                    not isinstance(b, dict) or not _num(b.get("start_s")) or not _num(b.get("end_s"))
                    for b in beats):
                out.append(_entry("P0", "FAIL", sid, key, "beats must be a list of {start_s, end_s} objects"))
            look = shot.get("look")
            if look is not None and not isinstance(look, dict):
                out.append(_entry("P0", "FAIL", sid, key, "look must be an object"))
            elif isinstance(look, dict) and look.get("hook") is not None and not isinstance(look["hook"], dict):
                out.append(_entry("P0", "FAIL", sid, key, "look.hook must be an object"))
    return out


def _start_s(ep, shot):
    return shot["start_frame"] / ep["fps"]


def _end_s(ep, shot):
    return (shot["start_frame"] + shot["frames"]) / ep["fps"]


def _ep_len_s(ep):
    return ep["total_frames"] / ep["fps"]


def _look(shot):
    look = shot.get("look")
    return look if isinstance(look, dict) else {}


def _beats_sorted(shot):
    return sorted(shot.get("beats") or [], key=lambda b: b["start_s"])


def _all_beats(ep):
    return [b for shot in ep["shots"] for b in _beats_sorted(shot)]


def _norm(text):
    return " ".join(str(text).split()).lower()


def _push_zoom_at_zero(shot):
    raw = shot.get("raw")
    comp = raw.get("compositing") if isinstance(raw, dict) else None
    post = comp.get("post") if isinstance(comp, dict) else None
    return isinstance(post, str) and _PUSH_ZOOM_AT_ZERO.search(post.lower()) is not None


def rule_r1(ep, ret, story, is_final):
    """First shot has a hook and a focal in its cast; WARN if its first beat says fade/title card/black."""
    shot = ep["shots"][0]
    sid, key = shot.get("id"), ep["key"]
    if shot.get("look") is None:
        level = "FAIL" if story is not None else "WARN"
        return [_entry("R1", level, sid, key, "first shot has no look block (hook and focal needed)")]
    out = []
    look = _look(shot)
    if not isinstance(look.get("hook"), dict):
        out.append(_entry("R1", "FAIL", sid, key, "first shot has no look.hook"))
    if look.get("focal") not in shot.get("cast_ids", []):
        out.append(_entry("R1", "FAIL", sid, key, f"focal {look.get('focal')!r} is not in cast_ids"))
    beats = _beats_sorted(shot)
    if beats and any(w in str(beats[0].get("acting") or "").lower() for w in _BLACK_WORDS):
        out.append(_entry("R1", "WARN", sid, key, "first beat text says fade, title card or black"))
    return out


def rule_r2(ep, ret, story, is_final):
    """Motion starts by first_motion_s: a beat covering 0 .. first_motion_s must NOT be hold: true, unless the first shot's post declares push/zoom at 0.
    (11-08: the check was inverted against COLOUR_AUDIT.md R2 / brief B4c, which failed every motion-first row.)"""
    shot = ep["shots"][0]
    sid, key = shot.get("id"), ep["key"]
    limit = ret["first_motion_s"]
    beats = _beats_sorted(shot)
    if not beats:
        return [_entry("R2", "WARN", sid, key, "no beats in first shot")]
    covering = [b for b in beats if b["start_s"] < limit and b["end_s"] > 0.0]
    if not covering:
        return [_entry("R2", "WARN", sid, key, "no beat covers the first_motion_s window")]
    if _push_zoom_at_zero(shot):
        return []
    bad = [b for b in covering if b.get("hold") is True]
    if bad:
        return [_entry("R2", "FAIL", sid, key,
                       f"a hold beat covers {bad[0]['start_s']:.2f} s: motion must start within first_motion_s {limit} s")]
    return []


def rule_r3(ep, ret, story, is_final):
    """Some beat starting by first_face_change_s has a bhava or names eyes, brows or mouth. WARN otherwise."""
    limit = ret["first_face_change_s"]
    beats = _all_beats(ep)
    sid, key = ep["shots"][0].get("id"), ep["key"]
    if not beats:
        return [_entry("R3", "WARN", sid, key, "no beats in episode")]
    for b in beats:
        if b["start_s"] <= limit and (b.get("bhava") or _FACE_WORDS.search(str(b.get("acting") or "").lower())):
            return []
    return [_entry("R3", "WARN", sid, key, f"no face change (bhava or eyes/brows/mouth) by {limit} s")]


def rule_r4(ep, ret, story, is_final):
    """Hook caption must be present, at most hook_caption_max_words words, and differ from the first dialogue."""
    shot = ep["shots"][0]
    sid, key = shot.get("id"), ep["key"]
    hook = _look(shot).get("hook")
    if not isinstance(hook, dict):
        return []  # R1 reports the missing hook
    caption = hook.get("caption")
    if not isinstance(caption, str) or not caption.strip():
        return [_entry("R4", "FAIL", sid, key, "hook caption is missing")]
    out = []
    words = len(caption.split())
    if words > ret["hook_caption_max_words"]:
        out.append(_entry("R4", "FAIL", sid, key,
                          f"hook caption has {words} words, max {ret['hook_caption_max_words']}"))
    first = shot.get("first_dialogue")
    if isinstance(first, str) and _norm(caption) == _norm(first):
        out.append(_entry("R4", "FAIL", sid, key, "hook caption repeats the first dialogue line"))
    return out


def rule_r5(ep, ret, story, is_final):
    """No hold: true beat may start before no_hold_before_s (COLOUR_AUDIT.md R5: stillness pays off only after the viewer decided to stay)."""
    beats = _all_beats(ep)
    sid, key = ep["shots"][0].get("id"), ep["key"]
    if not beats:
        return [_entry("R5", "WARN", sid, key, "no beats in episode")]
    limit = ret["no_hold_before_s"]
    early = [b for b in beats if b.get("hold") is True and b["start_s"] < limit]
    if not early:
        return []
    return [_entry("R5", "FAIL", sid, key, f"a hold beat starts at {early[0]['start_s']:.2f} s, before {limit} s")]


def _change_events(ep):
    """(time, shot id) for every change event in the episode, sorted and deduped within one frame."""
    events = []
    for shot in ep["shots"]:
        sid = shot.get("id")
        events.append((_start_s(ep, shot), sid))
        prev = None
        for b in _beats_sorted(shot):
            changed = prev is not None and (b.get("bhava") or None) != (prev.get("bhava") or None)
            if b.get("primary") is True or changed:
                events.append((b["start_s"], sid))
            prev = b
        for t in shot.get("camera_moves") or []:
            events.append((t, sid))
        for t in shot.get("dialogue_starts") or []:
            events.append((t, sid))
        for imp in shot.get("impacts") or []:
            events.append((imp["at_s"], sid))
        for t in shot.get("caption_changes") or []:
            events.append((t, sid))
    end = _ep_len_s(ep)
    tol = 1.0 / ep["fps"]
    events = sorted((t, sid) for t, sid in events if 0.0 <= t <= end)
    kept = []
    for t, sid in events:
        if kept and t - kept[-1][0] < tol:
            continue
        kept.append((t, sid))
    return kept


def _shot_at(ep, t):
    for shot in ep["shots"]:
        if _start_s(ep, shot) <= t < _end_s(ep, shot):
            return shot
    return None


def rule_r6(ep, ret, story, is_final):
    """No gap between change events longer than static_warn_s (WARN) or static_fail_s (FAIL)."""
    key = ep["key"]
    events = _change_events(ep)
    end = _ep_len_s(ep)
    if not events or events[0][0] > 0.0:
        events.insert(0, (0.0, ep["shots"][0].get("id")))
    points = events + [(end, None)]
    out = []
    for (a, sid), (b, _) in zip(points, points[1:]):
        gap = round(b - a, 6)
        if gap <= ret["static_warn_s"]:
            continue
        level = "FAIL" if gap > ret["static_fail_s"] else "WARN"
        mid = (a + b) / 2.0
        shot = _shot_at(ep, mid)
        if shot is not None:
            sid = shot.get("id")
            purpose = _look(shot).get("hold_purpose")
            beat = next((x for x in _beats_sorted(shot)
                         if x["start_s"] <= mid < x["end_s"]), None)
            if (isinstance(purpose, str) and purpose.strip()) or (
                    beat is not None and beat.get("hold") is True and beat.get("bhava")):
                level = "WARN"
        out.append(_entry("R6", level, sid, key,
                          f"static gap {a:.2f}-{b:.2f} s ({gap:.2f} s) with no cut, beat change, "
                          f"camera move, dialogue, impact or caption change"))
    return out


def rule_r7(ep, ret, story, is_final):
    """An act change or a reveal beat should land inside rehook_window_frac of the episode."""
    shots = ep["shots"]
    key, sid0 = ep["key"], shots[0].get("id")
    reveals = [(b["start_s"], shot.get("id")) for shot in shots for b in shot.get("beats") or []
               if b.get("reveal") is True]
    acts = [_look(s).get("act") for s in shots]
    distinct = {a for a in acts if a is not None}
    if len(distinct) < 2 and not reveals:
        return []
    lo_frac, hi_frac = ret["rehook_window_frac"]
    length = _ep_len_s(ep)
    events = [(_start_s(ep, shots[i]), shots[i].get("id")) for i in range(1, len(shots))
              if acts[i - 1] is not None and acts[i] is not None and acts[i - 1] != acts[i]]
    events += reveals
    lo, hi = lo_frac * length, hi_frac * length
    if any(lo <= t <= hi for t, _ in events):
        return []
    return [_entry("R7", "WARN", sid0, key,
                   f"no act change or reveal beat between {lo:.2f} and {hi:.2f} s (episode {length:.2f} s)")]


def rule_r8(ep, ret, story, is_final):
    """Non-final episodes: last shot purpose names a cliffhanger, and its look has a closing question caption."""
    if is_final:
        return []
    last = ep["shots"][-1]
    sid, key = last.get("id"), ep["key"]
    out = []
    purpose = str(last.get("purpose") or "").lower()
    if "cliffhanger" not in purpose and "cliff-hanger" not in purpose:
        out.append(_entry("R8", "WARN", sid, key, "last shot purpose does not mention a cliffhanger"))
    look = _look(last)
    captions = [look.get("end_caption"), look.get("closing_caption")]
    if not any(isinstance(c, str) and c.strip().endswith("?") for c in captions):
        out.append(_entry("R8", "WARN", sid, key,
                          "no closing-question caption (look.end_caption or look.closing_caption)"))
    return out


def rule_r9(ep, ret, story, is_final):
    """First shot has non-empty sound (no silent lead-in)."""
    shot = ep["shots"][0]
    text = shot.get("sound_text")
    if isinstance(text, str) and text.strip():
        return []
    return [_entry("R9", "FAIL", shot.get("id"), ep["key"], "first shot has no sound (silent lead-in)")]


def rule_r10(ep, ret, story, is_final):
    """Episode length within story episode_target_s, widened by one clip (longest shot)."""
    if not isinstance(story, dict) or story.get("episode_target_s") is None:
        return []
    lo, hi = story["episode_target_s"]
    length = _ep_len_s(ep)
    clip = max(s["frames"] for s in ep["shots"]) / ep["fps"]
    if lo - clip <= length <= hi + clip:
        return []
    return [_entry("R10", "WARN", None, ep["key"],
                   f"episode length {length:.2f} s outside target {lo}-{hi} s (+/- one clip {clip:.2f} s)")]


_RULES = (rule_r1, rule_r2, rule_r3, rule_r4, rule_r5, rule_r6, rule_r7, rule_r8, rule_r9, rule_r10)


def check_retention_rules(episodes, core, story=None):
    """Run R1-R10 on each episode. Returns report entries; malformed input gives P0 FAIL entries."""
    try:
        problems = _validate(episodes, core, story)
        if problems:
            return problems
        ret = core["retention"]
        out = []
        for index, ep in enumerate(episodes):
            is_final = index == len(episodes) - 1
            for rule in _RULES:
                out.extend(rule(ep, ret, story, is_final))
        return out
    except Exception as exc:  # safety net: rule code must never raise
        return [_entry("P0", "FAIL", None, None, f"retention rules failed: {type(exc).__name__}")]
