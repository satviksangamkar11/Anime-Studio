"""Official 4-rung post-render fallback policy (master prompt 3.4, contract section "Module API").

Failure number n of a shot (n = prior recorded failures + 1) maps to:
  n = 1  rung 1: regenerate in H3, prompt prefixed with the exact Reference Anchors block of the shot row.
  n = 2  rung 2: shorten to <= 6.0 s, move the dropped seconds into new adjacent lattice rows, re-run the
         Step 5.5 self-check (caller supplies it), then re-render. Optional FL2VA <-> Ref2VA switch.
  n = 3  rung 3: switch the row to Seedance 2.0 at 1080p (hybrid per-shot mixed mode); the switch is logged.
  n >= 4 rung 4: human gate (the Seedance attempt has also failed). No clip is emitted; the 4 choices are listed.
Pure decisions. The only I/O is the attempt-history JSON, written atomically. Never renders."""
from __future__ import annotations

import copy
import math
import re

from h3.asset_manifest import H3_MODEL_ID, SEEDANCE_MODEL_ID, SEEDANCE_RES, atomic_write_json, read_json_or_default
from h3.shot_table_spec import FALLBACK_RUNGS, HUMAN_CHOICES, LIGHTING_KEYS, REFERENCE_ANCHOR_KEYS, snap_seconds, lattice

SHORT_MAX_SEC = 6.0
HISTORY_SCHEMA = 1
_SEC_RANGE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*s?\s*$")


def _text(value) -> str:
    if isinstance(value, (list, tuple)):
        return "; ".join(str(v) for v in value) if value else "none"
    return str(value)


def _need(d: dict, keys, where: str) -> None:
    missing = [k for k in keys if not isinstance(d, dict) or k not in d]
    if missing:
        raise ValueError(f"{where} is missing {missing}")


def reference_anchor_prefix(row: dict) -> str:
    """The Reference Anchors block that rung 1 puts in front of the H3 prompt. Same anchors give the same text."""
    anchors = row.get("reference_anchors")
    _need(anchors, REFERENCE_ANCHOR_KEYS, f"{row.get('id')}.reference_anchors")
    _need(anchors["lighting_baseline"], LIGHTING_KEYS, f"{row.get('id')}.reference_anchors.lighting_baseline")
    lines = ["REFERENCE ANCHORS (hold exactly; they override any drift):",
             f"Fixed landmarks: {_text(anchors['fixed_landmarks'])}"]
    positions = []
    for c in anchors["character_positions"]:
        _need(c, ("id", "screen", "depth"), "character_positions entry")
        positions.append(f"{c['id']} at {_text(c['screen'])}, depth {_text(c['depth'])}")
    lines.append(f"Character positions: {_text(positions)}")
    exited = []
    for e in anchors["exited_character_status"]:
        _need(e, ("id", "left_after_shot", "off_stage_shots", "released"), "exited_character_status entry")
        state = "released" if e["released"] else "still off-stage, keep out of frame"
        exited.append(f"{e['id']} left after {e['left_after_shot']} ({e['off_stage_shots']} off-stage shots, {state})")
    lines.append(f"Exited characters: {_text(exited)}")
    light = anchors["lighting_baseline"]
    lines.append(f"Lighting: key {_text(light['key'])}; fill {_text(light['fill'])}; rim {_text(light['rim'])}; "
                 f"shot modifiers {_text(light['shot_modifiers'])}")
    return "\n".join(lines)


def _sec_range(text) -> tuple[float, float]:
    m = _SEC_RANGE.match(str(text))
    if not m or float(m.group(2)) < float(m.group(1)):
        raise ValueError(f"sfx time_range {text!r} is not 'a-b s'")
    return float(m.group(1)), float(m.group(2))


def _fmt(x: float) -> str:
    return f"{round(x, 3):g}"


def split_shot_row(row: dict) -> tuple[list[dict], list[str], float]:
    """Shorten the row to the longest lattice length <= 6.0 s and move the dropped seconds into new adjacent
    rows on the lattice. Returns (rows, warnings, total_drift_sec). The first row keeps the original id;
    new rows get `<id>_s2`, `<id>_s3`, ... Narration, dialogue and sfx cues are moved by start time."""
    sid = row.get("id")
    total = row.get("editorial_duration_sec")
    if isinstance(total, bool) or not isinstance(total, (int, float)) or not total > 0:
        raise ValueError(f"{sid}: editorial_duration_sec must be a positive number")
    if total <= SHORT_MAX_SEC:
        return [copy.deepcopy(row)], [], 0.0
    keep_n = max(n for n in range(6, 21) if lattice(n)["seconds"] <= SHORT_MAX_SEC)
    keep = lattice(keep_n)
    remainder = total - keep["seconds"]
    pieces = math.ceil(remainder / SHORT_MAX_SEC)
    per = remainder / pieces
    windows = [(0.0, keep["seconds"], keep)]
    for _ in range(pieces):
        lat = snap_seconds(per)
        start = windows[-1][1]
        windows.append((start, start + lat["seconds"], lat))
    ids = [sid] + [f"{sid}_s{i}" for i in range(2, len(windows) + 1)]
    drift = round(windows[-1][1] - total, 3)
    warnings = [f"{sid}: split rows inherit route {row.get('route')}; each piece needs its own boundary frames",
                f"{sid}: pieces inherit hook_type {row.get('hook_type')}; re-check hook density"]
    rows = []
    last = len(windows) - 1
    orig_handoff = row.get("continuity_handoff", {})
    for i, (w0, w1, lat) in enumerate(windows):
        new = copy.deepcopy(row)
        new["id"] = ids[i]
        new["lattice_n"], new["pixel_frames"] = lat["n"], lat["pixel_frames"]
        new["latent_slots"], new["editorial_duration_sec"] = lat["latent_slots"], lat["seconds"]
        new["continuity_handoff"] = {
            "incoming": orig_handoff.get("incoming") if i == 0 else f"continues from {ids[i - 1]}",
            "outgoing": orig_handoff.get("outgoing") if i == last else f"continues into {ids[i + 1]}",
            "loop_seam": orig_handoff.get("loop_seam") if i == last else None}
        if i > 0:
            new["is_opening_0_2s_hook"] = False
        if i < last:
            new["is_closing_hook"] = False
        new["per_second_directives"] = []
        for d in row.get("per_second_directives", []):
            t0, t1 = float(d["t0"]), float(d["t1"])
            if max(t0, w0) < min(t1, w1):
                nd = copy.deepcopy(d)
                nd["t0"], nd["t1"] = round(max(t0, w0) - w0, 3), round(min(t1, w1) - w0, 3)
                new["per_second_directives"].append(nd)
        new_audio = {"narration": None, "dialogue": [], "sfx_cues": [],
                     "performance_notes": copy.deepcopy(row.get("audio_and_dialogue_track", {}).get("performance_notes"))}
        src = row.get("audio_and_dialogue_track", {})
        narr = src.get("narration")
        if narr and _in(float(narr["time_range"][0]), w0, w1, i == last):
            new_audio["narration"] = _rebase_span(narr, float(narr["time_range"][0]), float(narr["time_range"][1]),
                                                  w0, w1, ids[i], "narration", warnings)
        for dlg in src.get("dialogue", []):
            s0, s1 = float(dlg["time_range"][0]), float(dlg["time_range"][1])
            if _in(s0, w0, w1, i == last):
                new_audio["dialogue"].append(_rebase_span(dlg, s0, s1, w0, w1, ids[i], "dialogue", warnings))
        for cue in src.get("sfx_cues", []):
            a, b = _sec_range(cue["time_range"])
            if _in(a, w0, w1, i == last):
                nc = copy.deepcopy(cue)
                nc["time_range"] = f"{_fmt(a - w0)}-{_fmt(b - w0)}s"
                if b > w1:
                    warnings.append(f"{ids[i]}: sfx {cue.get('sfx_key')} crosses the split boundary at {_fmt(w1)}s")
                new_audio["sfx_cues"].append(nc)
        new_audio["performance_notes"] = _rebase_mouth(new_audio["performance_notes"], w0, w1)
        new["audio_and_dialogue_track"] = new_audio
        rows.append(new)
    return rows, warnings, drift


def _in(start: float, w0: float, w1: float, is_last: bool) -> bool:
    return w0 <= start < w1 or (is_last and start >= w0)


def _rebase_span(item: dict, s0: float, s1: float, w0: float, w1: float, sid: str, kind: str,
                 warnings: list) -> dict:
    new = copy.deepcopy(item)
    new["time_range"] = [round(s0 - w0, 3), round(s1 - w0, 3)]
    if s1 > w1:
        warnings.append(f"{sid}: {kind} crosses the split boundary at {_fmt(w1)}s; re-time before render")
    return new


def _rebase_mouth(notes, w0: float, w1: float):
    """Keep only mouth_state seconds inside [w0, w1), rebased to this piece's start (whole seconds)."""
    if not isinstance(notes, dict) or not isinstance(notes.get("mouth_state"), dict):
        return notes
    new = copy.deepcopy(notes)
    kept = {}
    for k, v in notes["mouth_state"].items():
        sec = float(k)
        if w0 <= sec < w1:
            kept[str(int(sec - w0))] = v
    new["mouth_state"] = kept
    return new


def split_rows_for(row: dict) -> dict:
    """Public helper: rows plus warnings and drift, as used by rung 2."""
    rows, warnings, drift = split_shot_row(row)
    return {"rows": rows, "warnings": warnings, "total_drift_sec": drift}


def _rung_for(failure_count: int) -> int:
    return failure_count if failure_count < FALLBACK_RUNGS else FALLBACK_RUNGS


def _row(failure: dict) -> dict:
    row = failure.get("shot_row")
    if not isinstance(row, dict):
        raise ValueError("failure['shot_row'] is required for rungs 1 and 2 (prefix and split)")
    return row


def next_action(shot_id: str, attempts: list, failure: dict) -> dict:
    """Decide the next step for a shot that just failed QC or drifted.
    attempts: prior failure records of this shot (from load_history). failure: {"kind", "shot_row" (for rungs 1-2),
    optional "boundary_framing_drift": bool}. Returns the action dict; rung 4 never carries a clip."""
    if not isinstance(shot_id, str) or not shot_id:
        raise ValueError("shot_id must be a non-empty string")
    if not isinstance(attempts, list) or any(not isinstance(a, dict) for a in attempts):
        raise ValueError("attempts must be a list of attempt records")
    if not isinstance(failure, dict) or not str(failure.get("kind", "")).strip():
        raise ValueError("failure must be a dict with a non-empty 'kind'")
    n = len(attempts) + 1
    rung = _rung_for(n)
    base = {"shot_id": shot_id, "failure_count": n, "rung": rung}
    if rung == 1:
        row = _row(failure)
        return {**base, "action": "regenerate_h3_with_anchor_prefix", "model": H3_MODEL_ID, "route": row.get("route"),
                "prompt_prefix": reference_anchor_prefix(row)}
    if rung == 2:
        row = _row(failure)
        split = split_rows_for(row)
        action = {**base, "action": "shorten_split_recheck_rerender", "model": H3_MODEL_ID,
                  "route": row.get("route"), "split_rows": split["rows"], "warnings": split["warnings"],
                  "total_drift_sec": split["total_drift_sec"], "self_check_required": True, "self_check_ok": None}
        if failure.get("boundary_framing_drift") and row.get("route") in ("FL2VA", "Ref2VA"):
            action["optional_route_switch"] = "Ref2VA" if row["route"] == "FL2VA" else "FL2VA"
        return action
    if rung == 3:
        return {**base, "action": "switch_to_seedance", "model": SEEDANCE_MODEL_ID,
                "resolution": list(SEEDANCE_RES), "mode": "hybrid_per_shot_mixed", "manifest_log_required": True}
    return {**base, "action": "human_gate", "blocking": True, "clip_emitted": False,
            "human_choices": list(HUMAN_CHOICES)}


def verify_split(action: dict, self_check) -> dict:
    """Re-run the Step 5.5 self-check on rung-2 split rows. self_check(rows) -> {"ok": bool, ...}.
    Sets action["self_check_ok"]; the rows may be re-rendered only when it is True."""
    if action.get("action") != "shorten_split_recheck_rerender":
        raise ValueError("verify_split needs a rung 2 action")
    report = self_check(action["split_rows"])
    action["self_check_ok"] = bool(report["ok"])
    action["self_check_report"] = report
    return action


def may_rerender(action: dict) -> bool:
    """Rung 4 never re-renders. Rung 2 only after its self-check passed. Rungs 1 and 3 may render."""
    if action.get("rung") == FALLBACK_RUNGS:
        return False
    if action.get("rung") == 2:
        return action.get("self_check_ok") is True
    return True


def validate_human_choice(choice: str) -> str:
    if choice not in HUMAN_CHOICES:
        raise ValueError(f"human choice must be one of {HUMAN_CHOICES}, got {choice!r}")
    return choice


def load_history(path: str) -> dict:
    doc = read_json_or_default(path, lambda: {"schema": HISTORY_SCHEMA, "shots": {}})
    if not isinstance(doc, dict) or doc.get("schema") != HISTORY_SCHEMA or not isinstance(doc.get("shots"), dict):
        raise ValueError(f"{path}: not a v{HISTORY_SCHEMA} fallback history")
    return doc


def attempts_for(history: dict, shot_id: str) -> list:
    return list(history["shots"].get(shot_id, []))


def record_attempt(path: str, shot_id: str, failure: dict, action: dict) -> dict:
    """Append one failure and its action to the per-shot history (atomic). The shot row is not stored."""
    doc = load_history(path)
    recs = doc["shots"].setdefault(shot_id, [])
    rec = {"n": len(recs) + 1, "kind": str(failure["kind"]), "rung": action["rung"], "action": action["action"],
           "model": action.get("model")}
    recs.append(rec)
    atomic_write_json(path, doc)
    return rec


def reset_attempts(path: str, shot_id: str) -> None:
    """Call after a clip passes QC, so the next failure starts again at rung 1."""
    doc = load_history(path)
    doc["shots"].pop(shot_id, None)
    atomic_write_json(path, doc)
