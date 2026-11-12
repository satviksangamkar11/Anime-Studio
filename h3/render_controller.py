"""Pre-render controller for the h3 sing8 route. Story-agnostic. Pre-render only: no network, no GPU. ffmpeg runs only for the G3 colour-seam check, and only when every clip.mp4 already exists.

Run from D:/aai work/anime_studio:
  python -m h3.render_controller --story-file STORY.json --scope shots --ids A,B
  python -m h3.render_controller --story-file STORY.json --scope shots A,B --allow-partial
  python -m h3.render_controller --story-file STORY.json --scope reel --episode EP_01 --dry-run
  python -m h3.render_controller --story-file STORY.json --scope all --second-pass
  python -m h3.render_controller --story-file STORY.json --scope all --mode execute --execute-render   (exit 3: no backend)

Exit codes: 0 clean; 1 lint, scope or story error (nothing executable written, unless --allow-partial writes the
ready shots); 2 refused usage (execute without BOTH flags); 3 execute gates passed, no backend started.
Outputs per episode: <out>/<episode_id>/<shot_id>/{prompt.txt, workflow.json}, <episode>/filter.txt and
assemble.cmd (only when every selected shot is ready), <episode>/readiness.json. Default out: <story folder>/build.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from h3.assemble_reel import (attach_colour_seams, build_ffmpeg_assembly_plan, load_loudness_plan,
                              write_assembly_script)
from h3.asset_manifest import H3_MODEL_ID, blocking_problems, hash_bible, hash_frame_file, hash_shot_row, load_manifest
from h3.compile_h3_sing8 import compile_comfyui_workflow, compile_episode, compile_fl2va_prompt
from h3.fallback_policy import attempts_for, load_history
from h3.gate_d_audio import plan_language_outputs
from director.timeline_lock_io import load_lock, lock_rows, verify_lock
from h3.pipeline_contract import PRE_RENDER, READY, assembly_allowed, build_plan, pre_render_ready
from h3.router import ref2va_limit_problems, route_shot
from h3.schema_and_linter import (ID_PATTERN, lint_profile, lint_story, picture_path_problem,
                                  read_png_dimensions_on_disk, resolve_keyframes)
from h3.shot_table_spec import FALLBACK_RUNGS, HUMAN_CHOICES
from h3.step9_qc import final_qc

SCOPES = ("shots", "reel", "all")
UNVERIFIED_NOTE = ("NOTE: Route C ComfyUI node classes are UNVERIFIED (written from an unverified spec); "
                   "every workflow.json carries _unverified_node_classes: true.")
NO_BACKEND_MSG = "no GPU backend configured (ComfyUI endpoint or Colab/Wan2GP runner not wired); nothing was started"
EXEC_REFUSED = "REFUSED: execute needs BOTH --mode execute AND --execute-render; nothing was started."
SHOT_FILES = ("prompt.txt", "workflow.json")
EPISODE_FILES = ("filter.txt", "assemble.cmd")


class ScopeError(ValueError):
    """Bad --scope, unknown shot id or unknown episode."""


def _backend_none(request):
    print(NO_BACKEND_MSG)
    return 3


BACKENDS = {"none": _backend_none}


def register_backend(name, fn):
    """Hook for a later render backend. fn(request) returns an int exit code (None means 0).
    request = {"episodes": [{"episode_id", "out_dir", "shots": [{"shot_id", "prompt", "workflow", "frames"}], "assembly"}]}."""
    BACKENDS[name] = fn


def run_backend(name, request):
    fn = BACKENDS.get(name)
    if fn is None:
        print(f"REFUSED: unknown backend {name!r}; registered: {sorted(BACKENDS)}")
        return 2
    rc = fn(request)
    return 0 if rc is None else int(rc)


# ---------- story and profile loading ----------

def _validate_id(value, kind):
    """Raise ValueError if value does not match ID_PATTERN."""
    if not isinstance(value, str) or not ID_PATTERN.match(value):
        raise ValueError(f"{kind} id {value!r} is unsafe; must match ^[A-Za-z0-9][A-Za-z0-9_-]{{0,63}}$")


def load_story(path):
    """Read a story JSON (SPEC). A relative episode asset_root resolves against the story file's folder."""
    path = os.path.abspath(path)
    with open(path, encoding="utf-8") as f:
        story = json.load(f)
    if not isinstance(story, dict) or not isinstance(story.get("registry"), dict) or not isinstance(story.get("episodes"), list):
        raise ValueError("story must be an object with a 'registry' object and an 'episodes' list")
    base = os.path.dirname(path)
    seen_eps, seen_shots = set(), {}
    for ep in story["episodes"]:
        if not (isinstance(ep, dict) and isinstance(ep.get("episode_id"), str)
                and isinstance(ep.get("asset_root"), str) and isinstance(ep.get("shots"), list)):
            raise ValueError("every episode needs a string episode_id and asset_root and a shots list")
        _validate_id(ep["episode_id"], "episode")  # before any path is built
        if ep["episode_id"] in seen_eps:
            raise ValueError(f"duplicate episode id {ep['episode_id']!r}")
        seen_eps.add(ep["episode_id"])
        if not all(isinstance(s, dict) and isinstance(s.get("shot_id"), str) for s in ep["shots"]):
            raise ValueError(f"episode {ep['episode_id']}: every shot needs a string shot_id")
        for s in ep["shots"]:
            _validate_id(s["shot_id"], "shot")
            if s["shot_id"] in seen_shots:
                raise ValueError(f"duplicate shot id {s['shot_id']!r} in episodes {seen_shots[s['shot_id']]} "
                                 f"and {ep['episode_id']}")
            seen_shots[s["shot_id"]] = ep["episode_id"]
        if not os.path.isabs(ep["asset_root"]):
            ep["asset_root"] = os.path.normpath(os.path.join(base, ep["asset_root"]))
    return story


def load_profile_file(path):
    """A bare execution_profile, or a story / registry / {execution_profile} wrapper holding one."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and isinstance(data.get("registry"), dict):
        data = data["registry"].get("execution_profile")
    elif isinstance(data, dict) and isinstance(data.get("execution_profile"), dict):
        data = data["execution_profile"]
    if not isinstance(data, dict):
        raise ValueError(f"profile file {path} must hold an execution_profile object")
    return data


# ---------- scope ----------

def parse_scope(tokens, ids_opt=(), episode_opt=None):
    """--scope tokens: ['shots', 'A,B'] | ['reel', 'EP_01'] | ['all']; --ids (comma lists) and --episode also accepted."""
    kind, rest = tokens[0], list(tokens[1:])
    if kind not in SCOPES:
        raise ScopeError(f"unknown scope {kind!r}; use shots, reel or all")
    if kind == "shots":
        if episode_opt:
            raise ScopeError("--episode does not apply to --scope shots")
        ids = [x.strip() for part in rest + list(ids_opt) for x in part.split(",") if x.strip()]
        return kind, ids, None
    if kind == "reel":
        if len(rest) > 1 or ids_opt or (rest and episode_opt):
            raise ScopeError("--scope reel takes one episode id: 'reel EP_01' or --episode EP_01")
        return kind, [], episode_opt or (rest[0] if rest else None)
    if rest or ids_opt or episode_opt:
        raise ScopeError("--scope all takes no arguments")
    return kind, [], None


def select_scope(story, scope, ids=None, episode_id=None):
    """-> [{"episode": ep, "shots": [shot, ...]}] in story order. Unknown shot ids or episode raise ScopeError."""
    eps = story["episodes"]
    if scope == "all":
        if not eps:
            raise ScopeError("story has no episodes")
        return [{"episode": ep, "shots": list(ep["shots"])} for ep in eps]
    if scope == "reel":
        if not episode_id:
            raise ScopeError("--scope reel needs an episode id")
        ep = next((e for e in eps if e["episode_id"] == episode_id), None)
        if ep is None:
            raise ScopeError(f"unknown episode {episode_id!r}; story has {[e['episode_id'] for e in eps]}")
        return [{"episode": ep, "shots": list(ep["shots"])}]
    if scope == "shots":
        wanted = list(dict.fromkeys(ids or []))
        if not wanted:
            raise ScopeError("--scope shots needs shot ids (--ids A,B or 'shots A,B')")
        known = {s["shot_id"] for ep in eps for s in ep["shots"]}
        unknown = [x for x in wanted if x not in known]
        if unknown:
            raise ScopeError(f"unknown shot id(s): {', '.join(unknown)}")
        groups = []
        for ep in eps:
            picked = [s for s in ep["shots"] if s["shot_id"] in wanted]
            if picked:
                groups.append({"episode": ep, "shots": picked})
        return groups
    raise ScopeError(f"unknown scope {scope!r}")


# ---------- lint and per-shot facts ----------

def _attribute(messages, shot_ids):
    """Split 'SHOT: CODE ...' messages by shot; anything else is episode-level."""
    ids, own, rest = set(shot_ids), {}, []
    for m in messages:
        head = m.split(": ", 1)[0]
        if head in ids:
            own.setdefault(head, []).append(m)
        else:
            rest.append(m)
    return own, rest


def _lint_episode(story, ep, second_pass):
    """-> (own_errors, own_warnings, episode_errors, episode_warnings); own_* map shot_id -> messages."""
    reg = story["registry"]
    prof = reg.get("execution_profile")
    if not isinstance(prof, dict):
        return {}, {}, ["PO-03 registry.execution_profile is missing"], []
    try:
        pl = lint_profile(prof)
        if pl["errors"]:
            return {}, {}, list(pl["errors"]), list(pl["warnings"])
        if second_pass and "upscale_resolution" not in prof:
            return {}, {}, ["CLI-02 --second-pass needs execution_profile.upscale_resolution"], []
        res = lint_story({"registry": reg, "episodes": [ep]})
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        return {}, {}, [f"LINT-EXC the linter could not read episode {ep['episode_id']}: {e!r}"], []
    ids = [s["shot_id"] for s in ep["shots"]]
    own_e, rest_e = _attribute(res["errors"], ids)
    own_w, rest_w = _attribute(res["warnings"], ids)
    return own_e, own_w, rest_e, rest_w


def _picture_rows(root, shot, prev, base):
    """picture_1/2 status: OK, REUSED (picture_1 taken from the upstream shot), or MISSING (absent or wrong size)."""
    try:
        kf = resolve_keyframes(shot, prev, root)
    except (KeyError, TypeError, AttributeError):
        kf = None
    out = {}
    for label in ("picture_1", "picture_2"):
        rel = kf.get(label) if kf else None
        status = "MISSING"
        # never open a path that KF-07 refuses (absolute, drive letter or '..')
        if rel is not None and base and picture_path_problem(rel) is None:
            try:
                ok = read_png_dimensions_on_disk(os.path.join(root, rel)) == list(base)
            except (OSError, ValueError, TypeError):
                ok = False
            if ok:
                status = "REUSED" if (label == "picture_1" and kf.get("reused")) else "OK"
        out[label] = {"path": rel, "status": status}
    return out


def _safe_join(base, *parts):
    """Join and resolve, then ensure the result is inside base (both resolved). Raise ValueError if not."""
    target = (Path(base) / Path(*parts)).resolve()
    base_resolved = Path(base).resolve()
    if not target.is_relative_to(base_resolved):
        raise ValueError(f"path traversal attempt: {target} not under {base_resolved}")
    return target


# ---------- writing ----------

def _write_shot(reg, ep, shot, prev, ep_dir, second_pass):
    """Same files compile_episode writes, for one shot. Used only by --allow-partial."""
    kf = resolve_keyframes(shot, prev, ep["asset_root"])
    text = compile_fl2va_prompt(shot, reg)["compiled_prompt"]
    wf = compile_comfyui_workflow(shot, reg, text, second_pass, kf)
    d = _safe_join(ep_dir, shot["shot_id"])
    d.mkdir(parents=True, exist_ok=True)
    p_prompt = _safe_join(d, "prompt.txt")
    p_wf = _safe_join(d, "workflow.json")
    with open(p_prompt, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    with open(p_wf, "w", encoding="utf-8", newline="\n") as f:
        json.dump(wf, f, ensure_ascii=False, indent=2)
    return [str(p_prompt), str(p_wf)]


def _write_assembly(ep, shots_sel, ep_dir):
    loud = load_loudness_plan(os.path.join(ep_dir, "loudness.json"))
    plan = build_ffmpeg_assembly_plan(shots_sel, f"{ep['episode_id']}.mp4", loudness=loud)
    clips = [f"{s['shot_id']}/clip.mp4" for s in shots_sel]
    attach_colour_seams(plan, [os.path.join(ep_dir, c) for c in clips], shots_sel)
    paths = write_assembly_script(plan, clips, ep_dir)
    out = {"filter": paths["filter"], "cmd": paths["cmd"], "total_frames": plan["total_frames"],
           "total_duration_sec": plan["total_duration_sec"], "seams": len(plan["seam_transitions"])}
    if "colour_seams_note" not in plan:
        out["colour_seams"] = len(plan["colour_seams"])
    return out


def _remove_if_exists(paths):
    gone = []
    for p in paths:
        if os.path.isfile(p):
            os.remove(p)
            gone.append(p)
    return gone


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0


# ---------- prepare ----------

def prepare(story, groups, out_root, *, second_pass=False, allow_partial=False, write=True,
            mode="prepare-only", profile_source="story", story_file=None):
    """Lint every selected episode in full, then write outputs when write is True. Returns the report; prints nothing.

    A run is BLOCKED when the linter reports any error in a linted episode: exit 1, nothing executable written
    (stale executables of selected shots are removed). --allow-partial writes only shots with no errors of their own,
    never the assembly. A shot is ready when it has no errors of its own and the episode has no episode-level errors.
    """
    reg = story["registry"]
    prof = reg.get("execution_profile")
    fps = prof.get("fps") if isinstance(prof, dict) else None
    base = prof.get("base_resolution") if isinstance(prof, dict) else None
    episodes = []
    for g in groups:
        ep, shots = g["episode"], g["episode"]["shots"]
        ep_id = ep["episode_id"]
        sel = [s["shot_id"] for s in g["shots"]]
        pos = {s["shot_id"]: k for k, s in enumerate(shots)}
        own_e, own_w, rest_e, rest_w = _lint_episode(story, ep, second_pass)
        blocked = bool(rest_e) or any(own_e.values())
        ready = {sid: not own_e.get(sid) and not rest_e for sid in sel}
        ep_dir = _safe_join(out_root, ep_id)
        rows = []
        for sid in sel:
            shot = shots[pos[sid]]
            prev = shots[pos[sid] - 1] if pos[sid] else None
            t = shot.get("timing_and_lattice") if isinstance(shot.get("timing_and_lattice"), dict) else {}
            pf = t.get("pixel_frames")
            secs = max(0.0, round(pf / fps, 2)) if isinstance(pf, int) and not isinstance(pf, bool) and isinstance(fps, int) and fps else None
            pics = _picture_rows(ep["asset_root"], shot, prev, base)
            rows.append({"shot_id": sid, "sequence_order": shot.get("sequence_order"), "frames": pf, "seconds": secs,
                         "editorial_frames": t.get("editorial_frames"), "picture_1": pics["picture_1"],
                         "picture_2": pics["picture_2"], "errors": own_e.get(sid, []),
                         "warnings": own_w.get(sid, []), "ready": ready[sid]})
        written, written_ids, assembly, removed = [], set(), None, []
        if write:
            ep_dir.mkdir(parents=True, exist_ok=True)
            if not blocked:
                try:
                    for sid in sel:  # assert every shot folder stays inside ep_dir before compile_episode writes into it
                        _safe_join(ep_dir, sid)
                    load_loudness_plan(os.path.join(str(ep_dir), "loudness.json"))   # a corrupt file raises ValueError before any shot file is written
                    written = compile_episode(story, ep_id, str(ep_dir), shot_ids=sel, second_pass=second_pass)
                    written_ids = set(sel)
                    assembly = _write_assembly(ep, g["shots"], str(ep_dir))
                except ValueError as e:  # compile re-lints the episode; this should not fire after a clean lint
                    blocked, written, written_ids = True, [], set()
                    rest_e = rest_e + ["COMPILE " + str(e).replace("\n", " | ")]
                    for r in rows:
                        r["ready"] = False
            elif allow_partial:
                for sid in sel:
                    if ready[sid]:
                        k = pos[sid]
                        written += _write_shot(reg, ep, shots[k], shots[k - 1] if k else None, str(ep_dir), second_pass)
                        written_ids.add(sid)
            for sid in sel:
                if sid not in written_ids:
                    shot_dir = _safe_join(ep_dir, sid)
                    removed += _remove_if_exists([str(_safe_join(shot_dir, f)) for f in SHOT_FILES])
            if assembly is None:
                removed += _remove_if_exists([str(_safe_join(ep_dir, f)) for f in EPISODE_FILES])
        ep_out = {"episode_id": ep_id, "ep_dir": str(ep_dir), "selected": sel, "rows": rows, "blocked": blocked,
                  "exit_code": 1 if blocked else 0, "episode_errors": rest_e, "episode_warnings": rest_w,
                  "other_shot_errors": {k: v for k, v in own_e.items() if k not in sel},
                  "error_count": sum(len(v) for v in own_e.values()) + len(rest_e),
                  "warning_count": sum(len(v) for v in own_w.values()) + len(rest_w),
                  "written": written, "assembly": assembly, "removed": removed,
                  "readiness": str(_safe_join(ep_dir, "readiness.json")) if write else None,
                  "story_file": story_file, "mode": mode, "profile_source": profile_source,
                  "second_pass": second_pass, "allow_partial": allow_partial,
                  "unverified_node_classes": True}
        ep_out["totals"] = _totals(rows, ep_out["error_count"], ep_out["warning_count"])
        if write:
            with open(ep_out["readiness"], "w", encoding="utf-8") as f:
                json.dump(ep_out, f, indent=2, ensure_ascii=False)
        episodes.append(ep_out)
    rows = [r for e in episodes for r in e["rows"]]
    totals = _totals(rows, sum(e["error_count"] for e in episodes), sum(e["warning_count"] for e in episodes))
    return {"episodes": episodes, "totals": totals, "exit_code": 1 if any(e["blocked"] for e in episodes) else 0,
            "mode": mode}


def _totals(rows, errors, warnings):
    return {"shots": len(rows), "ready": sum(1 for r in rows if r["ready"]),
            "frames": sum(_num(r["frames"]) for r in rows),
            "seconds": round(sum(_num(r["seconds"]) for r in rows), 2),
            "editorial_frames": sum(_num(r["editorial_frames"]) for r in rows),
            "errors": errors, "warnings": warnings}


# ---------- report ----------

def _cell(v):
    return "-" if v is None else str(v)


def readiness_table(ep):
    """Fixed-width table for one episode: shot, frames, seconds, picture_1/2, errors, warnings, ready."""
    w = max([len("shot")] + [len(r["shot_id"]) for r in ep["rows"]]) + 2
    lines = [f"episode {ep['episode_id']}",
             f"{'shot':<{w}}{'frames':>7}{'seconds':>9}  {'picture_1':<10}{'picture_2':<10}{'errors':>7}{'warnings':>9}  ready"]
    for r in ep["rows"]:
        lines.append(f"{r['shot_id']:<{w}}{_cell(r['frames']):>7}{_cell(r['seconds']):>9}  "
                     f"{r['picture_1']['status']:<10}{r['picture_2']['status']:<10}"
                     f"{len(r['errors']):>7}{len(r['warnings']):>9}  {'YES' if r['ready'] else 'NO'}")
    return "\n".join(lines)


def print_report(res, *, allow_partial=False):
    print(UNVERIFIED_NOTE)
    for ep in res["episodes"]:
        print(readiness_table(ep))
        for r in ep["rows"]:
            for m in r["errors"]:
                print(f"  ! {m}")
            for m in r["warnings"]:
                print(f"  ~ {m}")
        for m in ep["episode_errors"]:
            print(f"  ! (episode) {m}")
        for m in ep["episode_warnings"]:
            print(f"  ~ (episode) {m}")
        for sid, msgs in ep["other_shot_errors"].items():
            for m in msgs:
                print(f"  ! (outside scope, blocks this run) {m}")
        for p in ep["removed"]:
            print(f"  removed stale executable from an earlier run: {p}")
        if ep["readiness"]:
            print(f"  readiness: {ep['readiness']}")
    t = res["totals"]
    print(f"TOTAL shots={t['shots']} ready={t['ready']}/{t['shots']} frames={t['frames']} seconds={t['seconds']} "
          f"editorial_frames={t['editorial_frames']} errors={t['errors']} warnings={t['warnings']}")
    written_shots = sum(1 for e in res["episodes"] for p in e["written"] if p.endswith("prompt.txt"))
    if res["mode"] == "dry-run":
        status = "exit 1 would be returned" if res["exit_code"] else "exit 0 would be returned"
        print(f"DRY RUN ({status}): nothing was written.")
    elif res["exit_code"]:
        if allow_partial:
            print(f"RUN BLOCKED (exit 1): --allow-partial wrote {written_shots} ready shot(s); no assembly written.")
        else:
            print("RUN BLOCKED (exit 1): nothing executable was written.")
    else:
        names = ", ".join(e["episode_id"] for e in res["episodes"])
        print(f"RUN CLEAN (exit 0): wrote {written_shots} shot(s) and the assembly for {names}.")


# ---------- full pipeline plan (dry run: never renders, never writes) ----------

MANIFEST_FILE = "asset_manifest.json"
HISTORY_FILE = "fallback_history.json"


def _lint_result(res):
    problems = []
    for ep in res["episodes"]:
        problems += [f"(episode {ep['episode_id']}) {m}" for m in ep["episode_errors"]]
        for r in ep["rows"]:
            problems += [f"{r['shot_id']}: {m}" for m in r["errors"]]
        for sid, msgs in ep["other_shot_errors"].items():
            problems += [f"{sid}: {m}" for m in msgs]
    return {"ok": not problems, "reasons": problems, "details": {"episodes": [e["episode_id"] for e in res["episodes"]]}}


def _route_result(groups):
    problems, routes = [], {}
    for g in groups:
        for shot in g["shots"]:
            sid = shot["shot_id"]
            routes[sid] = route_shot(shot)
            problems += [f"{sid}: {code} {msg}" for code, msg in ref2va_limit_problems(shot)]
    return {"ok": not problems, "reasons": problems, "details": {"routes": routes}}


def _prompt_result(story, groups):
    problems, compiled = [], 0
    for g in groups:
        for shot in g["shots"]:
            try:
                compile_fl2va_prompt(shot, story["registry"])  # the text is written only at render time
                compiled += 1
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                problems.append(f"{shot.get('shot_id', '?')}: prompt not compiled: {e}")
    return {"ok": not problems, "reasons": problems, "details": {"compiled": compiled}}


def _frame_hash(root, rel):
    """sha256 of a boundary frame on disk; None when the shot has no such frame (T2VA) or the file is missing."""
    if not rel or picture_path_problem(rel) is not None:
        return None
    path = os.path.join(root, rel)
    return hash_frame_file(path) if os.path.isfile(path) else None


def _current_hashes(story, groups):
    """shot_id -> the five hashes each shot has now (what its clip must have been rendered from).
    The bible hash is the whole registry: any upstream edit makes every clip stale (judgment call, see SPEC.md)."""
    bible = hash_bible(story["registry"])
    current = {}
    for g in groups:
        shots, root = g["episode"]["shots"], g["episode"]["asset_root"]
        pos = {s["shot_id"]: k for k, s in enumerate(shots)}
        for shot in g["shots"]:
            k = pos[shot["shot_id"]]
            kf = resolve_keyframes(shot, shots[k - 1] if k else None, root)
            current[shot["shot_id"]] = {
                "bible_sha256": bible, "shot_row_sha256": hash_shot_row(shot),
                "start_frame_sha256": _frame_hash(root, kf.get("picture_1")),
                "end_frame_sha256": _frame_hash(root, kf.get("picture_2")), "model_id": H3_MODEL_ID}
    return current


def _manifest_result(manifest, story, groups):
    problems = blocking_problems(manifest, _current_hashes(story, groups))
    return {"ok": not problems, "reasons": problems, "details": {"clips": len(manifest.get("clips", {}))}}


def _fallback_result(history, groups):
    problems, next_rung = [], {}
    for g in groups:
        for shot in g["shots"]:
            sid = shot["shot_id"]
            n = len(attempts_for(history, sid)) + 1  # number of the next failure of this shot
            next_rung[sid] = min(n, FALLBACK_RUNGS)
            if n >= FALLBACK_RUNGS:
                problems.append(f"{sid}: human gate, choose one of {list(HUMAN_CHOICES)}")
    return {"ok": not problems, "reasons": problems, "details": {"next_rung": next_rung}}


MAX_RENDERS_PER_SHOT = 3  # M-24: after 3 renders of one shot, stop and escalate; a 4th needs an owner flag
DRIFT_ORDER = ("simplify", "remove_camera_move", "move_b_closer", "split_or_chain", "new_seed", "route_change")


def render_allowed(history, shot_id, owner_flag=False):
    """(ok, reason). Refuses the next render of a shot once MAX_RENDERS_PER_SHOT renders are recorded, unless owner_flag."""
    done = len(attempts_for(history, shot_id))
    if done < MAX_RENDERS_PER_SHOT or owner_flag:
        return True, f"{shot_id}: {done} renders recorded"
    return False, (f"{shot_id}: {done} renders already recorded (limit {MAX_RENDERS_PER_SHOT}): "
                   "stop and escalate to the owner; a 4th render needs the owner flag")


def record_drift_step(log, step):
    """Returns log + [step]. Each drift pass changes one variable, in DRIFT_ORDER, never repeated or skipped backwards."""
    if step not in DRIFT_ORDER:
        raise ValueError(f"unknown drift step {step!r}; must be one of {list(DRIFT_ORDER)}")
    if log and DRIFT_ORDER.index(step) <= DRIFT_ORDER.index(log[-1]):
        raise ValueError(f"drift step {step!r} out of order after {log[-1]!r}; order is {list(DRIFT_ORDER)}")
    return list(log) + [step]


def _render_result(render_results, groups):
    if render_results is None:
        return None  # dry run: nothing was rendered, the step stays pending
    problems = []
    for g in groups:
        for shot in g["shots"]:
            got = render_results.get(shot["shot_id"], "missing")
            if got != "ok":
                problems.append(f"{shot['shot_id']}: no successful render ({got})")
    return {"ok": not problems, "reasons": problems, "details": {"rendered": len(render_results)}}


def _qc_result(groups, measurers):
    problems = []
    for g in groups:
        try:
            rep = final_qc(g["episode"]["shots"], measurers=measurers)
        except (KeyError, TypeError, ValueError, AttributeError) as e:  # rows not in the V4 layout: QC cannot run, so it blocks
            problems.append(f"{g['episode']['episode_id']}: Step 9 QC not run: {type(e).__name__}: {e}")
            continue
        problems += [f"{g['episode']['episode_id']}: {c['id']} failed: {c['detail']}" for c in rep["checks"] if not c["ok"]]
    return {"ok": not problems, "reasons": problems, "details": {"episodes": len(groups)}}


def _timeline_result(lock_path, groups):
    """The timeline lock must load, match its recorded inputs and params, and cover exactly the selected shots."""
    if not lock_path:
        return {"ok": False, "reasons": ["no timeline lock"], "details": {}}
    try:
        lock = load_lock(lock_path)
        verify_lock(lock_path, lock["inputs"], lock["params"])
    except (OSError, ValueError, KeyError) as e:  # StaleLockError is a ValueError
        return {"ok": False, "reasons": [f"timeline lock not usable: {e}"], "details": {}}
    lock_ids = {row["id"] for row in lock["shots"]}
    selected = {shot["shot_id"] for g in groups for shot in g["shots"]}
    problems = []
    if lock_ids != selected:
        problems.append(f"timeline lock shots {sorted(lock_ids)} differ from selected shots {sorted(selected)}")
    return {"ok": not problems, "reasons": problems, "details": {"lock_sha256": lock["lock_sha256"]}}


def _approval_sheet():
    """director/approval_sheet.py imports its neighbours by bare name, so its folder goes on sys.path first."""
    director = str(Path(__file__).resolve().parents[1] / "director")
    if director not in sys.path:
        sys.path.insert(0, director)
    import approval_sheet
    return approval_sheet


def _keyframe_result(gate_b_path, keyframe_gate_dir, groups):
    """Gate B: every selected shot has an approval whose keyframe gate still matches (director/approval_sheet.py)."""
    if not gate_b_path or not keyframe_gate_dir:
        return {"ok": False, "reasons": ["no Gate B record or keyframe gate folder"], "details": {}}
    try:
        gate_b_ok = _approval_sheet().gate_b_ok
    except (ImportError, AttributeError):
        return {"ok": False, "reasons": ["Gate B check not built: approval_sheet.gate_b_ok is missing (card X-11)"],
                "details": {}}
    shot_ids = sorted({shot["shot_id"] for g in groups for shot in g["shots"]})
    problems = list(gate_b_ok(Path(gate_b_path), Path(keyframe_gate_dir), shot_ids))
    return {"ok": not problems, "reasons": problems, "details": {"shots": len(shot_ids)}}


def _gate_d_result(story, groups, out_root, languages, lock_path=None):
    reg, problems, ok_by_episode = story["registry"], [], {}
    lock_seconds = None
    if lock_path:  # the lock's clock is the one build_final_reel uses; the story's values are never used with a lock
        try:
            lock_seconds = {row["id"]: row["editorial_duration_sec"] for row in lock_rows(load_lock(lock_path))}
        except (OSError, KeyError, TypeError, ValueError) as e:
            return {"ok": False, "reasons": [f"timeline lock seconds not readable: {e}"], "details": {}}
    for g in groups:
        ep = g["episode"]
        ep_id = ep["episode_id"]
        ep_dir = os.path.join(out_root, ep_id)
        shots = ep["shots"]
        if lock_seconds is not None:
            try:
                missing = [s["shot_id"] for s in shots if s["shot_id"] not in lock_seconds]
                if missing:
                    problems.append(f"{ep_id}: shots missing from the timeline lock: {missing}")
                    continue
                shots = [dict(s, editorial_duration_sec=lock_seconds[s["shot_id"]]) for s in shots]
            except (KeyError, TypeError) as e:  # a shot row without shot_id
                problems.append(f"{ep_id}: shot rows not readable for the timeline lock: {type(e).__name__}: {e}")
                continue
        video = {"shared_foley": os.path.join(ep_dir, "render", f"{ep_id}_shared_foley.mp4"),
                 "en_h3": os.path.join(ep_dir, "render", f"{ep_id}_en_h3.mp4")}
        # Story Gate 4 checks: story-level, then registry, then episode. Absent = closing gate fails closed (below).
        gate = story.get("story_gate_checks") or reg.get("story_gate_checks") or ep.get("story_gate_checks")
        if not gate:
            problems.append(f"{ep_id}: story_gate_checks missing: add it to the story registry as "
                            "registry['story_gate_checks'] (v4_to_h3 copies it from stage_1); closing VO stays blocked")
        try:
            res = plan_language_outputs(ep_id, languages, os.path.join(ep_dir, "audio", "vo"), None,
                                        shots=shots, video_path=video, video_has_audio=True,
                                        captions_dir=os.path.join(ep_dir, "captions"),
                                        export_dir=os.path.join(ep_dir, "export"),
                                        story_gate_checks=gate, payoff_end_sec=ep.get("payoff_end_sec"),
                                        voice_engines=reg.get("voice_engine"))
        except (KeyError, TypeError, ValueError, AttributeError) as e:  # e.g. a shot row without editorial_duration_sec
            problems.append(f"{ep_id}: Gate D not planned: {type(e).__name__}: {e}")
            continue
        # one verdict per language: rep["ok"] is False whenever rep["errors"] is non-empty (gate_d_audio._report)
        ok_by_episode[ep_id] = {lang: bool(rep["ok"]) for lang, rep in res["reports"].items()}
        for lang, rep in res["reports"].items():
            problems += [f"{ep_id} {lang}: {e['code']} {e['where']}: {e['message']}" for e in rep["errors"]]
    return {"ok": not problems, "reasons": problems,
            "details": {"languages": list(languages), "ok_by_episode": ok_by_episode}}


def plan_pipeline(story, groups, out_root, *, languages=None, render_results=None, qc_measurers=None,
                  lock_path=None, gate_b_path=None, keyframe_gate_dir=None):
    """Ordered H3 pipeline plan for the selected groups (steps and reasons: h3/pipeline_contract.py). Dry run only:
    never renders, never calls a backend, writes nothing. render_results: None (default, nothing rendered yet) or
    {shot_id: "ok" | "failed"}. qc_measurers: Step 9 measurers (missing ones make QC fail closed). languages: default
    the story's output_languages, else ["hi"] (the writer default). BGM is not passed (default none). Loudness stays pending: it needs
    the exported mp4. lock_path: timeline lock (required for assembly; Gate D uses its seconds). gate_b_path and
    keyframe_gate_dir: the Gate B record and the keyframe gate folder."""
    langs = list(languages or story.get("output_languages") or story["registry"].get("output_languages") or ["hi"])   # hi = the writer's default
    lint = prepare(story, groups, out_root, write=False, mode="dry-run")
    manifest = load_manifest(os.path.join(out_root, MANIFEST_FILE))
    history = load_history(os.path.join(out_root, HISTORY_FILE))
    results = {"timeline": _timeline_result(lock_path, groups),
               "keyframes": _keyframe_result(gate_b_path, keyframe_gate_dir, groups),
               "lint": _lint_result(lint), "route": _route_result(groups),
               "prompt": _prompt_result(story, groups), "manifest": _manifest_result(manifest, story, groups),
               "fallback": _fallback_result(history, groups), "render": _render_result(render_results, groups)}
    if render_results is not None:
        results["step9_qc"] = _qc_result(groups, qc_measurers or {})
    results["gate_d"] = _gate_d_result(story, groups, out_root, langs, lock_path)
    results = {k: v for k, v in results.items() if v is not None}
    steps = build_plan(results)
    return {"mode": "dry-run", "languages": langs, "steps": steps, "assembly_allowed": assembly_allowed(steps)}


# ---------- CLI ----------

def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_render_ready(out_root, lock_path, gate_b_path, story_file):
    """Written only after every pre-render gate passed: the runner's --go refuses without a matching record."""
    record = {"lock_input_sha256": load_lock(lock_path)["input_sha256"], "gate_b_sha256": _sha256(gate_b_path),
              "story_sha256": _sha256(story_file), "ok": True}
    Path(out_root).mkdir(parents=True, exist_ok=True)
    Path(out_root, "render_ready.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")


def build_parser():
    ap = argparse.ArgumentParser(prog="python -m h3.render_controller",
                                 description="Pre-render gate for the h3 sing8 route. Writes nothing executable unless clean.")
    ap.add_argument("--story-file", required=True, help="story JSON per SPEC.md")
    ap.add_argument("--scope", nargs="+", required=True, metavar="SCOPE",
                    help="shots [IDS] | reel EPISODE_ID | all")
    ap.add_argument("--ids", action="append", default=[], help="comma-separated shot ids for --scope shots")
    ap.add_argument("--episode", help="episode id for --scope reel")
    ap.add_argument("--profile", help="profile JSON (bare execution_profile, or a story wrapper); default: the story's registry")
    ap.add_argument("--second-pass", action="store_true", help="add the unverified 2K second-pass nodes")
    ap.add_argument("--out-dir", help="output root; episode files go to <out-dir>/<episode_id>/ (default: <story folder>/build)")
    ap.add_argument("--mode", choices=("prepare-only", "execute"), default="prepare-only")
    ap.add_argument("--execute-render", action="store_true", help="with --mode execute, call the render backend")
    ap.add_argument("--dry-run", action="store_true", help="prepare-only that writes nothing")
    ap.add_argument("--allow-partial", action="store_true", help="also write the shots that pass when others fail")
    ap.add_argument("--backend", default="none", help="render backend name (default: none)")
    ap.add_argument("--lock", help="timeline lock JSON (required for --mode execute)")
    ap.add_argument("--gate-b", help="Gate B approval record JSON (director/approval_sheet.py)")
    ap.add_argument("--keyframe-gates", help="folder of per-shot keyframe gate JSON files")
    return ap


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = build_parser().parse_args(argv)
    if args.mode == "execute" or args.execute_render:
        if not (args.mode == "execute" and args.execute_render):
            print(EXEC_REFUSED)
            return 2
        if args.dry_run:
            print("REFUSED: --dry-run writes nothing and cannot be combined with execute.")
            return 2
        if not args.lock:
            print("REFUSED: execute needs --lock (the timeline lock); nothing was started.")
            return 2
    try:
        story = load_story(args.story_file)
        source = "story registry"
        if args.profile:
            story["registry"]["execution_profile"] = load_profile_file(args.profile)
            source = args.profile
        kind, ids, episode = parse_scope(args.scope, args.ids, args.episode)
        groups = select_scope(story, kind, ids, episode)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        print(f"ERROR: {e}")
        return 1
    story_file = os.path.abspath(args.story_file)
    out_root = os.path.abspath(args.out_dir) if args.out_dir else os.path.join(os.path.dirname(story_file), "build")
    if args.mode == "execute":
        gates = plan_pipeline(story, groups, out_root, lock_path=args.lock, gate_b_path=args.gate_b,
                              keyframe_gate_dir=args.keyframe_gates)
        if not pre_render_ready(gates["steps"]):
            for s in gates["steps"]:
                if s["status"] != READY and s["id"] in PRE_RENDER:
                    print(f"BLOCKED {s['id']}: {'; '.join(s['reasons']) or s['status']}")
            print("execute not started: the pre-render gates are not all ready (exit 1).")
            return 1
    mode = "dry-run" if args.dry_run else args.mode
    try:
        res = prepare(story, groups, out_root, second_pass=args.second_pass, allow_partial=args.allow_partial,
                      write=not args.dry_run, mode=mode, profile_source=source, story_file=story_file)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:  # e.g. a refused path: report it, exit 1, no traceback
        print(f"ERROR: {e}")
        return 1
    print_report(res, allow_partial=args.allow_partial)
    if args.mode != "execute":
        return res["exit_code"]
    if res["exit_code"] != 0:
        print("execute not started: the prepare-only gates failed (exit 1).")
        return 1
    _write_render_ready(out_root, args.lock, args.gate_b, story_file)
    request = {"episodes": [{
        "episode_id": e["episode_id"], "out_dir": e["ep_dir"], "assembly": e["assembly"],
        "shots": [{"shot_id": r["shot_id"], "prompt": os.path.join(e["ep_dir"], r["shot_id"], "prompt.txt"),
                   "workflow": os.path.join(e["ep_dir"], r["shot_id"], "workflow.json"), "frames": r["frames"]}
                  for r in e["rows"]]} for e in res["episodes"]]}
    return run_backend(args.backend, request)


if __name__ == "__main__":
    sys.exit(main())
