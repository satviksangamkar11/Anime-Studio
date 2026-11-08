"""Tier 2 of the H3 field plan (research/DECISION_H3_FIELDS_2026-11-07.md): a model writes the AUTHORED fields of each shot
(emotional objective, shot scale, screen direction, camera axis, horizon, cut-in and cut-out biomechanical tags and
pose vectors, cadence windows and clause). The timing, seams, handles, location, props and story beat come from
v4_to_h3.derive_fields (tier 1); the model never writes them.

Per shot, exactly the e2e_sample pattern: a fixed blueprint in the prompt, one call, the shot is converted and linted
(converter messages + lint_story codes for this shot only), and the exact messages go back for up to MAX_REPAIRS
repair rounds (so at most 1 + MAX_REPAIRS calls). Shots are done in order because CN-07/CN-08 tie each cut-in to the
previous cut-out. A finished shot is cached in <pack>/h3_authored/<shot_id>.json with the hash of its inputs.

Tests never call a model: they inject a fake caller (a function str -> str). scheduler_caller() is the only live path;
it imports the NVIDIA 14-key scheduler lazily and is refused by the CLI unless ANIME_STUDIO_ALLOW_FREE_MODEL=1.

  python h3/h3_author.py <pack_dir> --dry-run    derived fields, missing fields, prompt size; no model call
  python h3/h3_author.py <pack_dir> --live       authors the missing fields (needs ANIME_STUDIO_ALLOW_FREE_MODEL=1)
Exit codes: 0 clean, 1 problems (derivation, failed or blocked shots), 2 refused or unreadable pack.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from h3 import v4_to_h3 as conv
from h3.schema_and_linter import lint_story

MAX_REPAIRS = 4
LIVE_FLAG_ENV = "ANIME_STUDIO_ALLOW_FREE_MODEL"
FIELD_SPEC = {
    "emotional_objective": "one short phrase: the feeling the shot must give the viewer",
    "shot_scale": "one short word: extreme wide, wide, medium wide, medium, medium close-up, close-up or extreme close-up",
    "screen_direction_vector": "snake_case direction of travel in frame, e.g. left_to_right or right_to_left, or static",
    "camera_axis_side": "left or right",
    "horizon_line_y_ratio": "number from 0.0 (top of frame) to 1.0 (bottom), e.g. 0.4",
    "cut_in_biomechanical_state_tag": "snake_case tag of the body state on the first frame, e.g. idle_at_tower_base",
    "cut_out_biomechanical_state_tag": "snake_case tag of the body state on the last frame",
    "cut_in_pose_vector": '{"torso_pitch_deg": number, "knee_flex_deg": number, "com_y_ratio": number from 0 to 1}',
    "cut_out_pose_vector": '{"torso_pitch_deg": number, "knee_flex_deg": number, "com_y_ratio": number from 0 to 1}',
    "hold_window_frames": "[start, end] integers: the still part of the shot",
    "burst_window_frames": "[start, end] integers: the fast part of the shot",
    "impact_or_settle_frames": "[start, end] integers: the landing or settle part of the shot",
    "cadence_clause": "one plain sentence naming the hold, the burst and the settle",
}


class ModelError(RuntimeError):
    """The caller could not produce a reply (reported as a problem, never a silent default)."""


def strip_think(text):
    """The answer only: <think>...</think> blocks are dropped; an unclosed <think> has no answer after it."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    return text.split("<think>", 1)[0].strip()


def parse_author_answer(text):
    """One JSON object of author fields. Tolerates code fences, think blocks, prose around the object, and a one-item
    {"shots": [...]} wrapper. Raises ValueError when no object is found."""
    t = strip_think(text)
    fence = re.search(r"```[A-Za-z]*\s*\n?(.*?)```", t, re.S)
    if fence:
        t = fence.group(1).strip()
    try:
        obj = json.loads(t)
    except json.JSONDecodeError:
        i, j = t.find("{"), t.rfind("}")
        if not 0 <= i < j:
            raise ValueError("no JSON object in the reply")
        obj = json.loads(t[i:j + 1])
    if isinstance(obj, dict) and isinstance(obj.get("shots"), list) and len(obj["shots"]) == 1:
        obj = obj["shots"][0]
    if not isinstance(obj, dict):
        raise ValueError("the reply is not a JSON object")
    return obj


def build_author_prompt(row, derived, blueprint):
    """Self-contained prompt: the fixed blueprint, the V4 row without narration or dialogue, what is already known, and
    only the fields this shot still needs, each with its format."""
    req = conv.requested_fields(row, derived, blueprint)
    body = {k: v for k, v in row.items() if k not in ("h3_fields", "audio_and_dialogue_track")}
    known = {k: derived[k] for k in conv.DERIVED_FIELDS if k in derived}
    return "\n\n".join([
        "You write the continuity fields of ONE shot of an animated episode for an H3 video linter. "
        "Reply with ONLY one JSON object whose keys are exactly the fields under FIELDS TO WRITE. "
        "No prose, no markdown fences, no comments.",
        "FIXED BLUEPRINT (timing, seam types, handles, frame spans and any fixed cut-in values are decided already; "
        "copy them, do not write or change them):\n" + json.dumps(blueprint, indent=1),
        "SHOT (V4 row; narration and dialogue are not shown):\n" + json.dumps(body, ensure_ascii=False, indent=1),
        "ALREADY KNOWN (do not write these): " + json.dumps(known, ensure_ascii=False),
        "FIELDS TO WRITE:\n" + ("\n".join(f"- {k}: {FIELD_SPEC[k]}" for k in req) if req else "(none)"),
        "RULES:\n"
        "- hold_window_frames, burst_window_frames and impact_or_settle_frames are three windows in this order that "
        "start at 0 and end at pixel_frames (inclusive), each starting one frame after the previous one ends.\n"
        "- The cut-in tag and pose of the blueprint (if given) are fixed by the previous shot; they are not in FIELDS TO WRITE.\n"
        "- Tags are snake_case words. Poses are plain numbers. com_y_ratio is between 0 and 1.\n"
        "- No narration, no dialogue, no mouth or voice words, no sound words (sound is written elsewhere).",
    ])


def build_repair_prompt(base, messages, prior):
    return (base + "\n\nYOUR PREVIOUS REPLY FAILED THE CHECK. Fix only what these messages name, keep the BLUEPRINT "
            "values, and reply with the complete JSON object of FIELDS TO WRITE and nothing else.\n\nMESSAGES:\n"
            + "\n".join("- " + m for m in messages) + "\n\nYOUR PREVIOUS REPLY:\n" + (prior or "")[:4000])


def _placeholder_png(width, height):
    """A valid grey PNG of the given size (stdlib only). Authoring runs BEFORE Gate B makes the real boundary frames, but the linter
    needs two pictures of the right size to judge the authored fields (KF-06, route, PR-00 prompt compile)."""
    import struct
    import zlib

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = (b"\x00" + b"\x80" * width) * height
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def _lint_candidate(row, derived, blueprint, fields, bible, root, prev_row, sid):
    """Messages for one candidate: converter problems and lint codes for this shot only. The shot is converted inside a
    two-shot mini pack (the previous shot when there is one, so the cross-shot rules are checked too). A boundary frame that
    is not on disk yet (images come after authoring) is a placeholder of the profile size, real frames win when present."""
    import shutil
    import tempfile
    cur = dict(row, h3_fields=conv.merge_h3(row, derived, fields, blueprint))
    shots = ([prev_row] if prev_row is not None else []) + [cur]
    w, h = conv.load_default_profile("sing8_864x1536")["base_resolution"]
    with tempfile.TemporaryDirectory() as tmp:
        kd = os.path.join(tmp, "keyframes")
        os.makedirs(kd)
        for r in shots:
            for letter in "AB":
                name = f"{r.get('id')}-{letter}.png"
                real = os.path.join(root, "keyframes", name) if root else None
                if real and os.path.isfile(real):
                    shutil.copy(real, os.path.join(kd, name))
                else:
                    with open(os.path.join(kd, name), "wb") as f:
                        f.write(_placeholder_png(w, h))
        res = conv.convert_pack({"shots": shots, "bible": bible, "stage": {}, "asset_root": tmp}, languages=["en"])
        msgs = [p for p in res["problems"] if p.startswith(sid + ":")]
        if res["story"] is None:
            return msgs or [f"{sid}: the mini pack could not be converted"]
        errors = lint_story(res["story"])["errors"]
    return msgs + [e for e in errors if e.startswith(sid + ":")]


def check_answer(row, derived, blueprint, text, bible, root, prev_row=None):
    """(fields, messages). messages == [] means the candidate is accepted."""
    sid = derived.get("shot_id") or row.get("id")
    try:
        obj = parse_author_answer(text)
    except ValueError as exc:
        return None, [f"PARSE the reply is not one JSON object ({exc}); reply with the JSON object only"]
    req = conv.requested_fields(row, derived, blueprint)
    unknown = sorted(set(obj) - set(conv.AUTHOR_FIELDS))
    if unknown:
        return None, [f"AUTH-KEY {k!r} is not a field you write; remove it" for k in unknown]
    missing = [f for f in req if f not in obj]
    if missing:
        return None, [f"AUTH-MISSING the reply has no {', '.join(missing)}; write every field under FIELDS TO WRITE"]
    fields = {k: obj[k] for k in req}
    return fields, _lint_candidate(row, derived, blueprint, fields, bible, root, prev_row, sid)


def author_shot(row, derived, caller, max_repairs=MAX_REPAIRS, *, bible=None, pack_root=None, prev_row=None,
                blueprint=None):
    """{"fields", "rounds", "problems"}. fields is None when problems is not empty (after 1 + max_repairs calls).
    caller: function prompt -> reply text. prev_row: the previous shot of the reel with its finished h3_fields."""
    bible = bible if isinstance(bible, dict) else {}
    bp = blueprint if blueprint is not None else conv.build_blueprint(derived, None)
    if not conv.requested_fields(row, derived, bp):
        return {"fields": {}, "rounds": 0, "problems": []}
    base = build_author_prompt(row, derived, bp)
    prompt, rounds, messages = base, 0, []
    for _ in range(max_repairs + 1):
        try:
            reply = caller(prompt)
        except Exception as exc:  # the caller failed: a precise problem, not a silent default
            return {"fields": None, "rounds": rounds, "problems": [f"MODEL call failed: {exc!r}"]}
        rounds += 1
        try:
            fields, messages = check_answer(row, derived, bp, reply, bible, pack_root, prev_row)
        except Exception as exc:  # the converter or linter failed on this reply: a per-shot problem, never a traceback
            return {"fields": None, "rounds": rounds, "problems": [f"MODEL check failed: {exc!r}"]}
        if not messages:
            return {"fields": fields, "rounds": rounds, "problems": []}
        prompt = build_repair_prompt(base, messages, reply)
    return {"fields": None, "rounds": rounds, "problems": messages}


def save_result(root, row, derived, blueprint, bible, result):
    """Atomic write of a successful result to <root>/h3_authored/<shot_id>.json, keyed by the input hash."""
    sid = derived["shot_id"]
    folder = os.path.join(root, conv.AUTHORED_DIR)
    os.makedirs(folder, exist_ok=True)
    data = {"shot_id": sid, "status": "ok", "rounds": result["rounds"], "fields": result["fields"],
            "hash": conv.authored_key(row, derived, blueprint, bible, root)}
    path = os.path.join(folder, sid + ".json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def author_pack(pack_dir, caller=None, *, dry_run=False):
    """Walks the pack in order (the cut-in of each shot follows the cut-out of the one before). Returns
    {"shots": [per-shot dicts], "problems": [...]}. Per-shot status: skipped (no id or bad timing), fresh (cache hit),
    authored (model, saved), dry-run (not called), failed (repairs used up), blocked (previous shot failed),
    nothing to author. Caller may be None only when dry_run is True."""
    shots, bible, _stage, root, problems = conv._source(str(pack_dir))
    if not isinstance(shots, list) or not isinstance(bible, dict):
        raise ValueError("shots.json and bible.json are required")
    if not dry_run and caller is None:
        raise ValueError("a live run needs a caller")
    items, group_problems = conv.group_rows(shots)
    report = {"shots": [], "problems": list(problems) + group_problems}
    keyframes_dir = os.path.join(root, "keyframes")
    last = {}
    for it in items:
        row, ep = it["row"], it["ep"]
        sid = row.get("id")
        entry = {"shot_id": sid, "status": "", "missing": [], "prompt_chars": 0, "rounds": 0, "problems": [], "derived": {}}
        report["shots"].append(entry)
        if not isinstance(sid, str) or not sid:
            entry.update(status="skipped", problems=[f"row {it['idx']}: no shot id"])
            continue
        _t1, _pf, _ed, err = conv._timing_inputs(row, sid)
        if err:
            entry.update(status="skipped", problems=[err])
            continue
        derived, dnotes = conv.derive_fields(row, it["prev"], it["next"], bible, it["first"], it["last"], keyframes_dir)
        entry["derived"] = derived
        entry["problems"] += [n[len("PROBLEM: "):] for n in dnotes if n.startswith("PROBLEM: ")]
        prev = last.get(ep)
        if prev is not None and prev.get("failed"):
            entry.update(status="blocked", problems=entry["problems"] + [f"previous shot {prev['shot_id']} is not authored"])
            last[ep] = {"failed": True, "shot_id": sid}
            continue
        cut = conv.cut_out_of(prev["h3"]) if prev else None
        bp = conv.build_blueprint(derived, cut)
        req = conv.requested_fields(row, derived, bp)
        entry["missing"] = req
        fields = {}
        if req:
            found, _status = conv.load_fresh_authored(root, row, derived, bp, bible)
            if found is not None:
                fields, entry["status"] = found, "fresh"
            else:
                entry["prompt_chars"] = len(build_author_prompt(row, derived, bp))
                if dry_run:
                    entry["status"] = "dry-run"
                else:
                    prev_row = dict(prev["row"], h3_fields=prev["h3"]) if prev else None
                    try:
                        res = author_shot(row, derived, caller, bible=bible, pack_root=root, prev_row=prev_row, blueprint=bp)
                    except Exception as exc:  # belt and braces: the shot fails, the pack walk goes on by the same rule
                        res = {"fields": None, "rounds": 0, "problems": [f"MODEL check failed: {exc!r}"]}
                    entry["rounds"] = res["rounds"]
                    if res["problems"]:
                        entry.update(status="failed", problems=entry["problems"] + res["problems"])
                        last[ep] = {"failed": True, "shot_id": sid}
                        continue
                    fields = res["fields"]
                    save_result(root, row, derived, bp, bible, res)
                    entry["status"] = "authored"
        else:
            entry["status"] = "nothing to author"
        last[ep] = {"failed": False, "shot_id": sid, "h3": conv.merge_h3(row, derived, fields, bp), "row": row}
    return report


def scheduler_caller(model=None):
    """The live caller: NVIDIA Nemotron through the existing 14-key scheduler (h3/e2e_sample.py). Imported lazily, so
    dry runs and tests never import it. Needs the owner's free-model go and ANIME_STUDIO_ALLOW_FREE_MODEL=1."""
    from h3 import e2e_sample  # lazy: pulls in render_controller and the scheduler
    sch = e2e_sample.live_scheduler()
    if model:
        sch.model = model   # e.g. nvidia/nemotron-3.5-super-vl-120b-a12b (owner: use the Super model)
    return e2e_sample._ask(sch)


def claude_caller(model="opus", effort="low"):
    """Live caller on the owner's Claude subscription (director/write_pack.call_claude: no tools, no MCP, empty folder).
    Owner 2026-11-08 night: 'use Opus low' for the H3 author step (lifts rule 11 for this step only). Imported lazily."""
    d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "director")
    if d not in sys.path:
        sys.path.insert(0, d)  # write_pack imports its sibling modules by bare name
    import write_pack as wp

    def ask(prompt):
        env = json.loads(wp.call_claude(prompt, model, effort))
        text = (env.get("result") or "").strip()
        if env.get("is_error") or not text:
            raise ValueError(f"claude returned no usable answer: {str(env)[:200]}")
        return text
    return ask


def _summary_line(shot):
    d = shot.get("derived") or {}
    keys = ("incoming_seam_type", "outgoing_seam_type", "trim_in_frame", "trim_out_frame", "head_handle_frames",
            "tail_handle_frames", "location_id", "props_present", "story_beat")
    return json.dumps({k: d[k] for k in keys if k in d}, ensure_ascii=False)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python h3/h3_author.py",
                                 description="Derive and author the H3-only fields of a V4 pack (free models only, owner go).")
    ap.add_argument("pack_dir")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="print derived fields, missing fields and prompt size; no model call")
    mode.add_argument("--live", action="store_true", help=f"call the free model (needs {LIVE_FLAG_ENV}=1)")
    ap.add_argument("--model", default=None, help="with --live (free model): scheduler model id, default the e2e model")
    ap.add_argument("--opus", action="store_true", help="with --live: author with Claude Opus at low effort (owner go) instead of the free model")
    args = ap.parse_args(argv)
    if args.live and args.opus:
        pass  # the explicit --opus flag is the owner's go for the Claude call; the free-model env flag is not needed
    elif args.live and os.environ.get(LIVE_FLAG_ENV) != "1":
        print(f"refused: --live needs {LIVE_FLAG_ENV}=1 (the owner's free-model go); nothing was called", file=sys.stderr)
        return 2
    if not os.path.isfile(os.path.join(args.pack_dir, "shots.json")):
        print(f"no shots.json in {args.pack_dir}", file=sys.stderr)
        return 2
    try:
        caller = (claude_caller() if args.opus else scheduler_caller(args.model)) if args.live else None
        report = author_pack(args.pack_dir, caller, dry_run=args.dry_run)
    except (OSError, ValueError, KeyError, ImportError) as exc:
        print(f"pack could not be read or the scheduler is unavailable: {exc!r}", file=sys.stderr)
        return 2
    for p in report["problems"]:
        print("PROBLEM", p)
    counts = {}
    for s in report["shots"]:
        counts[s["status"]] = counts.get(s["status"], 0) + 1
        if args.dry_run:
            print(f"{s['shot_id']}: {s['status']}; derived {_summary_line(s)}")
            print(f"    missing ({len(s['missing'])}): {', '.join(s['missing']) or 'none'}; prompt chars {s['prompt_chars']}")
        else:
            print(f"{s['shot_id']}: {s['status']} rounds={s['rounds']}")
        for p in s["problems"]:
            print("PROBLEM", p)
    bad = bool(report["problems"]) or any(s["problems"] or s["status"] in ("failed", "blocked", "skipped")
                                          for s in report["shots"])
    verdict = ("problems" if bad else "no derivation problems") if args.dry_run else ("problems" if bad else "clean")
    print("H3A: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) + " -> " + verdict)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
