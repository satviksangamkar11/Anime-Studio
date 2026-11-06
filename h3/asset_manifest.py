"""Cryptographic asset versioning, clip manifest and resolution ladder (master prompt 4.6 and 3.3).

Every rendered clip is bound to (bible_sha256, shot_row_sha256, start_frame_sha256, end_frame_sha256, model_id).
Any upstream edit changes a hash, so the clip is stale and blocks assembly. Pure functions plus atomic JSON I/O.
Never renders, never runs ffmpeg, never calls a model."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile

H3_MODEL_ID = "h3-singularity-v2"
SEEDANCE_MODEL_ID = "seedance-2.0"
PLACEHOLDER_STATUS = "placeholder: missing clip"
HUMAN_GATE_STATUS = "human_gate"
BASE_RES = (864, 1536)            # pass 1 draft/approval, true 9:16
SECOND_PASS_RES = (1440, 2560)    # 2K pass, approved H3 clips only
SEEDANCE_RES = (1080, 1920)       # 1080p for every Seedance 2.0 fallback clip (both passes)
CLIP_FIELDS = ("bible_sha256", "shot_row_sha256", "start_frame_sha256", "end_frame_sha256", "model_id")
MANIFEST_SCHEMA = 1
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(obj) -> str:
    """Canonical JSON used for every hash: sorted keys, no whitespace, no NaN."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_bible(bible: dict) -> str:
    if not isinstance(bible, dict):
        raise ValueError("bible must be a dict")
    return sha256_text(canonical_json(bible))


def hash_shot_row(row: dict) -> str:
    if not isinstance(row, dict):
        raise ValueError("shot row must be a dict")
    return sha256_text(canonical_json(row))


def hash_frame_file(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _check_hash(value, name: str, nullable: bool) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, str) or not _HEX64.match(value):
        raise ValueError(f"{name} must be a 64-char lowercase sha256 hex string, got {value!r}")


def clip_key(bible_sha256, shot_row_sha256, start_frame_sha256, end_frame_sha256, model_id) -> str:
    """Asset version of one clip. Frames are None for a T2VA shot (no boundary image)."""
    _check_hash(bible_sha256, "bible_sha256", nullable=False)
    _check_hash(shot_row_sha256, "shot_row_sha256", nullable=False)
    _check_hash(start_frame_sha256, "start_frame_sha256", nullable=True)
    _check_hash(end_frame_sha256, "end_frame_sha256", nullable=True)
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("model_id must be a non-empty string")
    return sha256_text(canonical_json({"bible_sha256": bible_sha256, "shot_row_sha256": shot_row_sha256,
                                       "start_frame_sha256": start_frame_sha256,
                                       "end_frame_sha256": end_frame_sha256, "model_id": model_id}))


def make_clip_entry(shot_id: str, *, bible_sha256, shot_row_sha256, start_frame_sha256, end_frame_sha256,
                    model_id, path: str | None = None, correction: dict | None = None) -> dict:
    key = clip_key(bible_sha256, shot_row_sha256, start_frame_sha256, end_frame_sha256, model_id)
    return {"shot_id": shot_id, "status": "ok", "bible_sha256": bible_sha256, "shot_row_sha256": shot_row_sha256,
            "start_frame_sha256": start_frame_sha256, "end_frame_sha256": end_frame_sha256, "model_id": model_id,
            "clip_key": key, "path": path, "resolved": False, "correction": correction}


def make_placeholder_entry(shot_id: str) -> dict:
    """An explicit `placeholder: missing clip`. It blocks assembly until a human marks it resolved."""
    return {"shot_id": shot_id, "status": PLACEHOLDER_STATUS, "bible_sha256": None, "shot_row_sha256": None,
            "start_frame_sha256": None, "end_frame_sha256": None, "model_id": None, "clip_key": None,
            "path": None, "resolved": False, "correction": None}


def is_stale(entry: dict, current: dict) -> bool:
    """True when the clip was rendered from different upstream content than `current` (the five hashes)."""
    if not isinstance(entry, dict) or not isinstance(current, dict):
        raise ValueError("entry and current must be dicts")
    for f in CLIP_FIELDS:
        if f not in entry or f not in current or entry[f] != current[f]:
            return True
    return entry.get("clip_key") != clip_key(*(current[f] for f in CLIP_FIELDS))


def blocking_problems(manifest: dict, current: dict) -> list[str]:
    """Reasons assembly must stop. `current` maps shot_id -> the five hashes of that shot as it is now."""
    problems = []
    clips = manifest.get("clips", {})
    switches = manifest.get("model_switches", [])
    for shot_id in sorted(current):
        if shot_id not in clips:
            problems.append(f"{shot_id}: missing clip (no manifest entry)")
    for shot_id in sorted(clips):
        entry = clips[shot_id]
        status = entry.get("status")
        if status == PLACEHOLDER_STATUS:
            if not entry.get("resolved"):
                problems.append(f"{shot_id}: {PLACEHOLDER_STATUS} unresolved")
            continue
        if status == HUMAN_GATE_STATUS:
            problems.append(f"{shot_id}: waiting for a human choice (rung 4), no clip")
            continue
        if shot_id not in current:
            problems.append(f"{shot_id}: clip has no current shot row (orphan)")
            continue
        if is_stale(entry, current[shot_id]):
            problems.append(f"{shot_id}: stale clip hash (upstream edited, re-render)")
            continue
        if status != "ok":
            problems.append(f"{shot_id}: unknown status {status!r}")
        model = entry.get("model_id")
        if model != H3_MODEL_ID and not any(s.get("shot_id") == shot_id and s.get("to_model") == model
                                            for s in switches):
            problems.append(f"{shot_id}: model {model} not logged in model_switches (silent mix)")
    return problems


def record_model_switch(manifest: dict, shot_id: str, from_model: str, to_model: str, rung: int,
                        reason: str) -> dict:
    """Log a per-shot model switch (rung 3). Must be called before the switched clip is accepted."""
    if from_model == to_model:
        raise ValueError("model switch needs two different models")
    manifest.setdefault("model_switches", []).append({"shot_id": shot_id, "from_model": from_model,
                                                      "to_model": to_model, "rung": rung, "reason": reason})
    return manifest


def render_plan(clips: list, approved_ids=()) -> list[dict]:
    """Resolution ladder. clips: [{"shot_id", "model_id"}] in reel order.
    Pass 1 for every clip: H3 at 864x1536, Seedance fallback at 1080x1920.
    Pass 2 only for approved clips: H3 at 1440x2560, Seedance at 1080x1920 (1080p instead of 2K)."""
    ids = []
    for c in clips:
        if c["shot_id"] in ids:
            raise ValueError(f"duplicate shot id {c['shot_id']!r}")
        if c.get("model_id") not in (H3_MODEL_ID, SEEDANCE_MODEL_ID):
            raise ValueError(f"unknown model {c.get('model_id')!r} for {c['shot_id']!r}")
        ids.append(c["shot_id"])
    approved = set(approved_ids)
    unknown = approved - set(ids)
    if unknown:
        raise ValueError(f"approved ids not in the clip list: {sorted(unknown)}")
    jobs = []
    for c in clips:
        w, h = SEEDANCE_RES if c["model_id"] == SEEDANCE_MODEL_ID else BASE_RES
        jobs.append({"shot_id": c["shot_id"], "pass": 1, "model_id": c["model_id"], "width": w, "height": h})
    for c in clips:
        if c["shot_id"] in approved:
            w, h = SEEDANCE_RES if c["model_id"] == SEEDANCE_MODEL_ID else SECOND_PASS_RES
            jobs.append({"shot_id": c["shot_id"], "pass": 2, "model_id": c["model_id"], "width": w, "height": h})
    return jobs


def atomic_write_json(path: str, doc) -> None:
    """Write to a temp file in the same folder, then os.replace. A failed write leaves the old file intact."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(doc, f, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def read_json_or_default(path: str, default_factory):
    if not os.path.exists(path):
        return default_factory()
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def empty_manifest() -> dict:
    return {"schema": MANIFEST_SCHEMA, "clips": {}, "model_switches": []}


def load_manifest(path: str) -> dict:
    doc = read_json_or_default(path, empty_manifest)
    if not isinstance(doc, dict) or doc.get("schema") != MANIFEST_SCHEMA or not isinstance(doc.get("clips"), dict):
        raise ValueError(f"{path}: not a v{MANIFEST_SCHEMA} asset manifest")
    doc.setdefault("model_switches", [])
    return doc


def save_manifest(path: str, manifest: dict) -> None:
    atomic_write_json(path, manifest)
