"""Post-fetch clip QA (M-28): after the clips are home, run clip_qa.qa_shot for every shot, report pass/fail.
The plan file says, per shot, where its clip (relative to the results folder), keyframe PNGs, clip review,
shot sheet and audio are:
  {"lock": "timeline_lock.json", "root": "<folder that gets results/<SHOT>/clip_qa.json>",
   "shots": {"SHOT-001": {"clip", "key_a", "key_b", "review", "sheet", "audio"}}}
Route (from routes.json) and chain_prev (from chain_step, via the shot sheet's chain_from) come from
run_colab_batch.qa_inputs. Nothing here renders or calls a model. A shot fails on a failed verdict, a QA error,
a missing clip or a missing plan entry."""
import json
from pathlib import Path

import clip_qa

SHOT_KEYS = ("clip", "key_a", "key_b", "review", "sheet", "audio")


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def key_gray(path):
    """A keyframe PNG as the grey float image clip_qa expects (same size and scale as the clip frames)."""
    return clip_qa.extract(path, 0, 1)[0]


def load_plan(path):
    plan = _read_json(path)
    for k in ("lock", "root"):
        if not plan.get(k):
            raise ValueError(f"qa plan: {k!r} missing")
    if not isinstance(plan.get("shots"), dict):
        raise ValueError("qa plan: 'shots' must be an object")
    for sid, entry in plan["shots"].items():
        for k in SHOT_KEYS:
            if not entry.get(k):
                raise ValueError(f"qa plan: {sid}: {k!r} missing")
    return plan


def run(plan, results, inputs, qa=clip_qa.qa_shot, load_key=key_gray, load_sheet=_read_json, shot_ids=None,
        load_rgb=None, identity_ask=None):
    """{shot: {"ok": bool, "reason": str}} for shot_ids (default: every plan shot).
    inputs(shot) -> {"route", "chain_prev"}."""
    out = {}
    for sid in (shot_ids if shot_ids is not None else list(plan["shots"])):
        e = plan["shots"].get(sid)
        if e is None:
            out[sid] = {"ok": False, "reason": f"{sid}: no entry in the qa plan"}
            continue
        try:
            clip = Path(results) / e["clip"]
        except (KeyError, TypeError) as exc:
            out[sid] = {"ok": False, "reason": f"{sid}: qa plan entry has no usable clip: {exc!r}"}
            continue
        if not clip.is_file():
            out[sid] = {"ok": False, "reason": f"{sid}: clip missing: {clip}"}
            continue
        try:
            inp = inputs(sid)
            key_a = load_key(e["key_a"])
            key_b = key_a if inp["route"] == "S" else load_key(e["key_b"])      # route S has no end frame to check
            extra = {}
            if e.get("identity") and inp["route"] == "S":      # G9: identity master for route S only
                ask, src = identity_ask or _pick_identity()
                extra = {"identity_master": (load_rgb or _rgb_png)(e["identity"]), "identity_ask": ask,
                         "identity_source": src}
            doc = qa(sid, str(clip), plan["lock"], key_a, key_b, e["review"], load_sheet(e["sheet"]), e["audio"],
                     plan["root"], route=inp["route"], chain_prev=inp["chain_prev"], **extra)
        except Exception as exc:    # M-31: any QA/plan error fails this shot; it must not crash the batch
            out[sid] = {"ok": False, "reason": f"{sid}: {exc}"}
            continue
        v = doc.get("verdict") or {}
        if v.get("pass") is True:
            out[sid] = {"ok": True, "reason": "pass"}
        else:
            codes = ", ".join(str(x.get("code")) for x in v.get("reasons", [])) or "no pass"
            out[sid] = {"ok": False, "reason": f"{sid}: clip QA failed: {codes}"}
    return out


def _pick_identity():
    import qa_plan
    return qa_plan.pick_identity_ask()


def _rgb_png(path):
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(path).convert("RGB").resize((192, 336)))


def exit_code(results):
    """0 only when at least one shot was checked and all passed."""
    return 0 if results and all(v["ok"] for v in results.values()) else 1


def run_from_files(plan_path, results, routes_path, pack, shot_ids):
    """The call site used by run_colab_batch: plan + routes.json files in, per-shot results out."""
    import run_colab_batch as rcb      # lazy: run_colab_batch imports this module
    plan = load_plan(plan_path)
    routes = _read_json(routes_path)

    def inputs(sid):
        return rcb.qa_inputs(sid, _read_json(plan["shots"][sid]["sheet"]), routes, pack)
    return run(plan, results, inputs, shot_ids=shot_ids)
