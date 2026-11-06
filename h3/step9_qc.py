"""Step 9 final review gate (master prompt 4.6, qc-checklist). Four checks over supplied measurements.

The media measurers (audio peaks, visual observations, closing-shot payoff, on-screen labels) are injected as
callables. This module never decodes media. A missing measurer, or one that raises, FAILS its check (fail closed)."""
from __future__ import annotations

import re

from h3.shot_table_spec import STRONG_HOOKS

SFX_TOLERANCE_SEC = 0.25      # default peak-to-cue tolerance; the owner gave no number, so this is a parameter
CHECK_IDS = ("sfx_alignment", "visual_continuity", "closing_payoff", "no_storyboard_labels")
_RANGE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*s?\s*$")
_LABEL_PATTERNS = [re.compile(p, re.IGNORECASE) for p in (
    r"\[\s*(char|scene|shot|dur|hook)\s*:",          # official double-binding tags
    r"@(CHAR|ENV|STYLE|PROP)-",                       # Flow chip tags
    r"\bSHEET-",
    r"\b(SHOT|SCENE|PANEL|BEAT)\s*#?\s*\d+\b",        # panel or shot numbers
    r"\b(CHAR|SCENE|HOOK|DUR)\s*:",                   # storyboard field labels
    r"\b\d+(?:\.\d+)?\s*s\s*[-–]\s*\d+(?:\.\d+)?\s*s\b",   # timing labels such as 0.0s-1.2s
)]


class _NotMeasured(ValueError):
    pass


def parse_time_range(text) -> tuple[float, float]:
    m = _RANGE.match(str(text))
    if not m or float(m.group(2)) < float(m.group(1)):
        raise ValueError(f"time_range {text!r} is not 'a-b s'")
    return float(m.group(1)), float(m.group(2))


def shot_offsets(shots: list) -> dict:
    """Reel start time of each shot, from the editorial durations in order."""
    offsets, cum = {}, 0.0
    for row in shots:
        sid = row["id"]
        if sid in offsets:
            raise ValueError(f"duplicate shot id {sid!r}")
        dur = row["editorial_duration_sec"]
        if isinstance(dur, bool) or not isinstance(dur, (int, float)) or not dur > 0:
            raise ValueError(f"{sid}: editorial_duration_sec must be a positive number")
        offsets[sid] = cum
        cum += float(dur)
    return offsets


def _norm(value) -> str:
    return " ".join(str(value).split()).casefold()


def check_sfx_alignment(shots: list, peaks, offsets: dict | None = None,
                        tolerance_sec: float = SFX_TOLERANCE_SEC) -> tuple[bool, str]:
    """Every Column 6 sfx cue needs an audio energy peak within [cue start - tol, cue end + tol] of reel time."""
    offsets = offsets or shot_offsets(shots)
    peak_times = sorted(float(p) for p in peaks)
    cues, unmatched = 0, []
    for row in shots:
        for cue in row.get("audio_and_dialogue_track", {}).get("sfx_cues", []) or []:
            a, b = parse_time_range(cue["time_range"])
            cues += 1
            lo = offsets[row["id"]] + a - tolerance_sec
            hi = offsets[row["id"]] + b + tolerance_sec
            if not any(lo <= p <= hi for p in peak_times):
                unmatched.append(f"{row['id']} {cue.get('sfx_key')} {a:g}-{b:g}s")
    if cues == 0:
        return False, "no sfx_cues in the reel (pure-Foley mode requires them)"
    if unmatched:
        return False, f"{len(unmatched)} of {cues} sfx cues have no audio peak within {tolerance_sec}s: " + "; ".join(unmatched)
    return True, f"{cues} sfx cues matched audio peaks within {tolerance_sec}s"


def check_visual_continuity(shots: list, observations: dict) -> tuple[bool, str]:
    """observations: {shot_id: {"landmarks": [str], "character_positions": {id: {"screen", "depth"}},
    "lighting": {"key", "fill", "rim"}}}. Compared against each row's reference_anchors."""
    problems = []
    for row in shots:
        sid = row["id"]
        anchors = row["reference_anchors"]
        obs = observations.get(sid)
        if obs is None:
            problems.append(f"{sid}: no visual observation")
            continue
        seen_landmarks = {_norm(x) for x in obs.get("landmarks", [])}
        for lm in anchors["fixed_landmarks"]:
            if _norm(lm) not in seen_landmarks:
                problems.append(f"{sid}: landmark {lm!r} not observed")
        positions = obs.get("character_positions", {})
        for cp in anchors["character_positions"]:
            seen = positions.get(cp["id"])
            if seen is None:
                problems.append(f"{sid}: {cp['id']} not observed")
            elif _norm(seen.get("screen")) != _norm(cp["screen"]) or _norm(seen.get("depth")) != _norm(cp["depth"]):
                problems.append(f"{sid}: {cp['id']} at {seen.get('screen')}/{seen.get('depth')}, "
                                f"anchor {cp['screen']}/{cp['depth']}")
        for ex in anchors["exited_character_status"]:
            if not ex["released"] and ex["id"] in positions:
                problems.append(f"{sid}: {ex['id']} is visible but not released from off-stage")
        light = obs.get("lighting", {})
        for key in ("key", "fill", "rim"):
            if _norm(light.get(key)) != _norm(anchors["lighting_baseline"][key]):
                problems.append(f"{sid}: lighting {key} {light.get(key)!r} vs anchor {anchors['lighting_baseline'][key]!r}")
    if problems:
        return False, f"{len(problems)} continuity mismatches: " + "; ".join(problems)
    return True, f"{len(shots)} shots match reference_anchors"


def check_closing_payoff(shots: list, payoff_observed) -> tuple[bool, str]:
    """The last shot must carry a strong hook, be the closing hook, and deliver the emotional-anchor payoff."""
    last = shots[-1]
    problems = []
    if last.get("hook_type") not in STRONG_HOOKS:
        problems.append(f"hook {last.get('hook_type')!r} not in STRONG_HOOKS")
    if last.get("is_closing_hook") is not True:
        problems.append("is_closing_hook is not true")
    if payoff_observed is not True:
        problems.append("emotional-anchor payoff not observed")
    if problems:
        return False, f"closing shot {last['id']}: " + "; ".join(problems)
    return True, f"closing shot {last['id']} delivers the payoff with hook {last['hook_type']}"


def check_no_storyboard_labels(shots: list, labels: dict) -> tuple[bool, str]:
    """labels: {shot_id: [text read from the frames]}. Any storyboard tag, chip or timing label fails."""
    problems = []
    for row in shots:
        sid = row["id"]
        if sid not in labels:
            problems.append(f"{sid}: no frame-label result")
            continue
        for text in labels[sid]:
            for pat in _LABEL_PATTERNS:
                if pat.search(str(text)):
                    problems.append(f"{sid}: on-screen label {str(text)[:60]!r}")
                    break
    if problems:
        return False, f"{len(problems)} storyboard labels or gaps: " + "; ".join(problems)
    return True, f"no storyboard tags or labels in {len(shots)} shots"


def _measure(measurers: dict, name: str, *args):
    fn = measurers.get(name)
    if fn is None:
        raise _NotMeasured(f"no {name} measurer supplied")
    return fn(*args)


def final_qc(shots: list, *, measurers: dict | None = None, sfx_tolerance_sec: float = SFX_TOLERANCE_SEC,
             offsets: dict | None = None) -> dict:
    """measurers maps names to callables: "audio_peaks"() -> [reel seconds], "visual_observations"() -> {shot_id: obs},
    "closing_payoff"(last_row) -> bool, "frame_labels"() -> {shot_id: [str]}. Returns {"ok", "checks": [{id, ok, detail}]}."""
    if not isinstance(shots, list) or not shots:
        raise ValueError("final_qc needs a non-empty shot list")
    measurers = measurers or {}
    offsets = offsets or shot_offsets(shots)
    checks = []

    def run(cid, fn):
        try:
            ok, detail = fn()
        except Exception as e:  # fail closed: a broken measurer or bad row is a failed check, never a crash or a pass
            ok, detail = False, f"could not evaluate: {type(e).__name__}: {e}"
        checks.append({"id": cid, "ok": bool(ok), "detail": detail})

    run("sfx_alignment", lambda: check_sfx_alignment(
        shots, _measure(measurers, "audio_peaks"), offsets, sfx_tolerance_sec))
    run("visual_continuity", lambda: check_visual_continuity(shots, _measure(measurers, "visual_observations")))
    run("closing_payoff", lambda: check_closing_payoff(shots, _measure(measurers, "closing_payoff", shots[-1])))
    run("no_storyboard_labels", lambda: check_no_storyboard_labels(shots, _measure(measurers, "frame_labels")))
    return {"ok": all(c["ok"] for c in checks), "checks": checks}
