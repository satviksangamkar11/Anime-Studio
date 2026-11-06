"""Anime Studio control UI: the local API on 127.0.0.1 (ui/PLAN.md sections 2, 4, 6, 11).

  C:\\Python314\\python.exe ui\\server.py                 spend OFF (default)
  C:\\Python314\\python.exe ui\\server.py --allow-spend   owner only: $ runs become possible; each still needs a preview token and the typed confirm

Stdlib only. Only the COMMANDS table can run anything; no shell; every argv is a list built from validated values.
Test hooks: --root-override studio=PATH | flow=PATH | downloads=PATH | python=PATH | colab=PATH (test_ui.py points them at fake tools)."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import traceback
from collections import Counter, namedtuple
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlsplit

STUDIO = Path(__file__).resolve().parents[1]
PORT = 8765
PYTHON = r"C:\Python314\python.exe"
COLAB = [r"C:\Users\Satvik\.local\bin\colab.exe"]
FLOW_ROOT = Path("D:/aai work/flow_outputs/anime_kaliya")
DOWNLOADS = Path("C:/Users/Satvik/Downloads")
CAP_UNITS = 15.0                              # Q3: one execute may start at most this many units
RATES = {"G4": 10.05, "A100": 6.73}           # Colab units per hour (HANDOFF 2026-11-05 23:45)
TOKEN_TTL = 60
MAX_TEXT = 200 * 1024
MAX_BODY = 512 * 1024
MAX_FILE = 60 * 1024 * 1024
FILE_EXTS = (".png", ".jpg", ".jpeg", ".mp4", ".json", ".md", ".txt", ".jsonl", ".log")
FORBIDDEN_PARTS = {"granthstudio", "animation_research_tool", "secrets"}
BANNED_TOKENS = {"--logtostderr", "--allow-paid", "--push", "--fetch", "--stage-via"}
BANNED_PAIRS = {("--via", "claude"), ("--via", "openrouter")}
H3_MISSING = "h3 engine not built yet"
STAGE_KEYS = ("1", "2", "3e1", "3e2", "3e3", "3e4", "3e5", "5")
STORY_PACK = "stories/kaliya_mardan/pack_dots_full_v22"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
JSON_CT = "application/json; charset=utf-8"
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".mp4": "video/mp4", ".json": JSON_CT,
        ".md": "text/plain; charset=utf-8", ".txt": "text/plain; charset=utf-8", ".jsonl": "text/plain; charset=utf-8",
        ".log": "text/plain; charset=utf-8", ".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8"}
REVIEW_VERDICT = {0: "PASS", 1: "BLOCK", 3: "UNSURE", 2: "REFUSED"}


class ApiError(Exception):
    def __init__(self, code: int, msg: str):
        super().__init__(msg)
        self.code, self.msg = code, msg


def bad(msg: str) -> ApiError:
    return ApiError(400, msg)


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass
class Config:
    studio: Path = STUDIO
    flow: Path = FLOW_ROOT
    downloads: Path = DOWNLOADS
    python: str = PYTHON
    colab: list = field(default_factory=lambda: list(COLAB))
    spend: bool = False
    clock: Callable[[], float] = time.time

    @property
    def runs(self) -> Path:
        return self.studio / "ui" / "runs"


@dataclass
class Raw:
    ctype: str
    data: bytes


# ---------------------------------------------------------------- redaction (plan section 6)
SECRET_RX = [re.compile(p) for p in (r"ya29\.\S+", r"Bearer\s+\S+", r"nvapi-\S+", r"hf_[A-Za-z0-9]{20,}",
                                     r"sk-[A-Za-z0-9_-]{16,}", r"AIza[0-9A-Za-z_-]{30,}", r"token=\S+")]


def redact(text: str) -> str:
    for rx in SECRET_RX:
        text = rx.sub("[REDACTED]", text)
    return text


def has_secret(text: str) -> bool:
    return any(rx.search(text) for rx in SECRET_RX)


def redact_obj(o):
    if isinstance(o, str):
        return redact(o)
    if isinstance(o, list):
        return [redact_obj(x) for x in o]
    if isinstance(o, dict):
        return {k: redact_obj(v) for k, v in o.items()}
    return o


# ---------------------------------------------------------------- files and paths
def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def load_list(path) -> list:
    data = load_json(path, [])
    return data if isinstance(data, list) else []


def shot_list(path) -> list:
    return [s for s in load_list(path) if isinstance(s, dict)]


def jsonl(path: Path) -> list:
    out = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    obj = json.loads(line)
                except ValueError:
                    obj = {"raw": line[:200], "bad_line": True}
                if isinstance(obj, dict):
                    out.append(obj)
    return out


def num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def tail_text(path: Path, max_bytes: int = 2 * 1024 * 1024) -> str:
    if not path.is_file():
        return ""
    with open(path, "rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - max_bytes))
        return f.read().decode("utf-8", errors="replace")


def safe_path(cfg, raw, roots=("studio", "flow"), exts=None, must_exist=True, want="any") -> str:
    """Resolve raw (absolute, or relative to the studio root). Refuses '..', paths outside the roots (symlinks included),
    granthstudio, animation_research_tool, secrets folders, .env files and kaggle.json. Returns the real path as a string."""
    if not isinstance(raw, str) or not raw or len(raw) > 500 or "\x00" in raw:
        raise bad("path is missing or too long")
    if ".." in re.split(r"[\\/]", raw):
        raise bad("'..' is not allowed in a path")
    p = Path(raw)
    if not p.is_absolute():
        p = cfg.studio / p
    real = Path(os.path.realpath(p))
    bases = {"studio": cfg.studio, "flow": cfg.flow}
    base = None
    for name in roots:
        b = Path(os.path.realpath(bases[name]))
        if real == b or real.is_relative_to(b):
            base = b
            break
    if base is None:
        raise bad("path is outside the allowed folders")
    for part in real.relative_to(base).parts:
        low = part.lower()
        if low in FORBIDDEN_PARTS or low.startswith(".env") or low == "kaggle.json":
            raise bad("path is not allowed")
    if exts and real.suffix.lower() not in exts:
        raise bad(f"file type must be one of {', '.join(exts)}")
    if must_exist and want == "file" and not real.is_file():
        raise bad("file does not exist")
    if must_exist and want == "dir" and not real.is_dir():
        raise bad("folder does not exist")
    if must_exist and want == "any" and not real.exists():
        raise bad("path does not exist")
    return str(real)


# ---------------------------------------------------------------- argument validators
Arg = namedtuple("Arg", "check required default")


def A(check, required=False, default=None):
    return Arg(check, required, default)


def _rx(pattern: str, what: str):
    rx = re.compile(pattern)

    def check(cfg, v):
        if not isinstance(v, str) or not rx.fullmatch(v):
            raise bad(f"{what} is not valid")
        return v
    return check


def _enum(what: str, *vals):
    def check(cfg, v):
        if not isinstance(v, str) or v not in vals:
            raise bad(f"{what} must be one of: {', '.join(vals)}")
        return v
    return check


def _int(lo: int, hi: int, what: str):
    def check(cfg, v):
        if isinstance(v, bool) or not (isinstance(v, int) or (isinstance(v, str) and v.isdigit())):
            raise bad(f"{what} must be a whole number")
        n = int(v)
        if not lo <= n <= hi:
            raise bad(f"{what} must be {lo} to {hi}")
        return n
    return check


def _path(roots, exts=None, must_exist=True, want="any"):
    def check(cfg, v):
        return safe_path(cfg, v, roots, exts, must_exist, want)
    return check


def _ids(cfg, v):
    if isinstance(v, str):
        v = [x.strip() for x in v.split(",") if x.strip()]
    if not isinstance(v, list) or not 1 <= len(v) <= 200:
        raise bad("ids must be a list of 1 to 200 shot ids")
    return [SHOT(cfg, x) for x in v]


def _cands(cfg, v):
    if not isinstance(v, list) or not 1 <= len(v) <= 2:
        raise bad("give one or two candidate pictures")
    return [safe_path(cfg, x, ("flow",), (".png", ".jpg", ".jpeg"), True, "file") for x in v]


def _note(cfg, v):
    if not isinstance(v, str) or len(v) > 200:
        raise bad("note must be text of at most 200 characters")
    if not all(ch.isprintable() for ch in v):
        raise bad("note has control characters")
    if v.startswith("-") or "--" in v:
        raise bad("note cannot contain command flags")
    return v


def _bool(cfg, v):
    if not isinstance(v, bool):
        raise bad("must be true or false")
    return v


SLUG = _rx(r"[a-z0-9_]{1,40}", "slug")
NAME = _rx(r"[a-z0-9_-]{1,40}", "name")
SHOT = _rx(r"[A-Z0-9][A-Z0-9_-]{0,39}", "shot id")
VERSION = _rx(r"v\d{2}b?", "version")
EDIT = _rx(r"[0-9a-f-]{36}", "edit id")
SESSION = _rx(r"[A-Za-z0-9_-]{1,40}", "session name")
PACK_REL = _rx(r"stories/[a-z0-9_]{1,40}/[a-z0-9_-]{1,40}", "pack")
SIZE = _enum("size", "768x1344", "864x1536")
GPU = _enum("gpu", *RATES)
SCOPE = _enum("scope", "shots", "reel", "all")
WRITER_MODEL = _enum("model", "nvidia/nemotron-3-ultra-550b-a55b")
VISION_MODEL = _enum("model", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", "nvidia/nemotron-3.5-super-vl-120b-a12b")
ADHYAY = _int(1, 12, "adhyay")
REEL = _int(1, 99, "reel")
IDS = _ids
CANDS = _cands
NOTE = _note
BOOL = _bool
CLIP = _path(("studio", "flow"), (".mp4",), True, "file")
CLIP_NEW = _path(("studio", "flow"), None, False)
JSON_FILE = _path(("studio",), (".json",), True, "file")
DIR_KF = _path(("studio", "flow"), None, True, "dir")
GEN_ADHYAY = _int(1, 99, "adhyay")
JOBS_NAME = _rx(r"[A-Za-z0-9_-]{1,60}_flow_jobs[A-Za-z0-9_-]{0,40}\.json", "jobs file name")


def _gen_root(cfg) -> Path:
    return Path(os.path.realpath(cfg.studio / "flow" / "generated"))


def gen_json(cfg, raw, what) -> str:
    """A .json file directly inside flow/generated/<slug>/ (where pack_to_spec and build_jobs write). Returns the real path."""
    real = Path(safe_path(cfg, raw, ("studio",), (".json",), True, "file"))
    root = _gen_root(cfg)
    if not real.is_relative_to(root) or len(real.relative_to(root).parts) != 2 or not re.fullmatch(r"[a-z0-9_]{1,40}", real.parent.name):
        raise bad(f"{what} must be a .json file in flow/generated/<slug>/")
    return str(real)


def _gen_json(what):
    return lambda cfg, v: gen_json(cfg, v, what)


def normalize(cfg, spec, raw) -> dict:
    if not isinstance(raw, dict):
        raise bad("args must be an object")
    unknown = sorted(set(raw) - set(spec.args))
    if unknown:
        raise bad(f"unknown argument(s): {', '.join(unknown)}")
    out = {}
    for name, arg in spec.args.items():
        if raw.get(name) is not None:
            out[name] = arg.check(cfg, raw[name])
        elif arg.required:
            raise bad(f"{name} is required")
        else:
            out[name] = arg.default(cfg) if callable(arg.default) else arg.default
    return out


def check_argv(argv: list) -> None:
    for i, tok in enumerate(argv):
        if tok in BANNED_TOKENS:
            raise bad(f"{tok} is never passed by the UI")
        if i and (argv[i - 1], tok) in BANNED_PAIRS:
            raise bad("claude and openrouter are not used by the UI")


def digest(argv: list) -> str:
    return hashlib.sha256(json.dumps(argv, ensure_ascii=False).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- command table (the whitelist)
def _py(cfg, *parts):
    return [cfg.python, str(cfg.studio.joinpath(*parts))]


def _adh(cfg, a) -> Path:
    return cfg.flow / f"adhyay_{a['adhyay']:02d}"


def _dq(cfg, verb, a, *more):
    return _py(cfg, "flow", "scripts", "download_queue.py") + [verb, "--root", str(cfg.flow), "--adhyay", str(a["adhyay"]), *more]


def _batch(cfg, name) -> Path:
    return cfg.studio / "director" / "colab_batches" / name


def _default_keyframes(cfg):
    return str(cfg.flow / "adhyay_01" / "keyframes_h3")


def scope_ids(shots_file, scope, ids=None, reel=None):
    """Shot ids a scope selects from a shot file: shots -> the given ids, reel N -> episode N, all -> None (no --ids)."""
    if scope == "all":
        return None
    shots = shot_list(shots_file)
    if scope == "shots":
        if not ids:
            raise bad("scope shots needs at least one shot id")
        known = {s.get("id") for s in shots}
        missing = [i for i in ids if i not in known]
        if missing:
            raise bad(f"not in the shot file: {', '.join(missing)}")
        return list(ids)
    if scope == "reel":
        if reel is None:
            raise bad("scope reel needs a reel number")
        picked = [s["id"] for s in shots if s.get("episode") == reel]
        if not picked:
            raise bad(f"no shots in reel {reel}")
        return picked
    raise bad("scope must be shots, reel or all")


def b_write_pack(cfg, a):
    src = cfg.studio / "stories" / a["slug"] / "SOURCE.md"
    if not src.is_file():
        raise bad("save the story first: SOURCE.md is missing")
    return _py(cfg, "director", "write_pack.py") + [str(src), str(src.parent / a["pack"]), "--staged", "--via", "nvidia", "--model", a["model"]]


def b_check_pack(cfg, a):
    d = cfg.studio.joinpath(*a["pack"].split("/"))
    if not d.is_dir():
        raise bad("pack folder does not exist")
    return _py(cfg, "director", "check_pack.py") + [str(d)]


def b_bridge(dry):
    def build(cfg, a):
        adh = _adh(cfg, a)
        argv = _py(cfg, "flow", "scripts", "bridge_flow_to_h3.py") + ["--final-dir", str(adh / "final"), "--out-dir", str(adh / "keyframes_h3"),
                                                                       "--size", a["size"], "--json"]
        return argv + (["--dry-run"] if dry else [])
    return build


def b_neighbour(cfg, a):
    out = _adh(cfg, a) / "shots" / f"{a['shot']}__neighbours.jpg"
    return _py(cfg, "flow", "scripts", "neighbour_sheet.py") + ["--jobs", a["jobs"], "--shot", a["shot"], "--candidate", *a["candidates"], "--out", str(out)]


def b_review(cfg, a):
    return _py(cfg, "flow", "scripts", "review_shot.py") + ["--jobs", a["jobs"], "--shot", a["shot"], "--candidate", *a["candidates"]]


def b_queue_add(cfg, a):
    return _dq(cfg, "add", a, "--shot", a["shot"], "--version", a["version"], "--edit-id", a["edit"], "--jobs", a["jobs"],
               "--model", "Nano Banana 2.1 x2", "--decided-by", "owner", "--note", a["note"])


def b_queue_accept(cfg, a):
    return _dq(cfg, "accept", a, "--shot", a["shot"], "--version", a["version"], "--by", "owner", "--note", a["note"])


def b_tidy(apply):
    def build(cfg, a):
        return _py(cfg, "flow", "scripts", "tidy_final.py") + ["--root", str(cfg.flow), "--adhyay", str(a["adhyay"])] + (["--apply"] if apply else [])
    return build


def b_clip_qa(cfg, a):
    return _py(cfg, "director", "clip_tools.py") + ["qa", a["clip"], a["out_dir"]]


def b_visual(cfg, a):
    argv = _py(cfg, "director", "visual_qa.py") + [a["clip"], a["direction"], a["out_dir"], "--via", "nvidia", "--model", a["model"]]
    return argv + (["--bible", a["bible"]] if a.get("bible") else [])


def b_prepare(cfg, a):
    if _batch(cfg, a["batch"]).exists():
        raise ApiError(409, f"batch {a['batch']} already exists: pick a new name")
    ids = scope_ids(a["shots"], a["scope"], a.get("ids"), a.get("reel"))
    argv = _py(cfg, "director", "run_kaggle.py") + [a["shots"], a["keyframes"], a["batch"]]
    if ids:
        argv += ["--ids", ",".join(ids)]
    return argv + ["--style", "kaliya_mardan", "--target", "colab", "--profile", "5"]


def b_colab_run(go):
    def build(cfg, a):
        d = _batch(cfg, a["batch"])
        if not (d / "run.py").is_file():
            raise bad("batch has no run.py: build the batch first")
        argv = _py(cfg, "director", "t0_pack", "run_t0_parallel.py") + ["--batch", str(d), "--results", str(d / "results"),
                                                                        "--gpu", a["gpu"], "--name", a["session"]]
        return argv + (["--go"] if go else [])
    return build


def b_h3(cfg, a):
    if a["scope"] == "shots" and not a.get("ids"):
        raise bad("scope shots needs ids")
    if a["scope"] == "reel" and not a.get("reel"):
        raise bad("scope reel needs a reel number")
    tail = {"shots": a.get("ids") or [], "reel": [str(a.get("reel"))], "all": []}[a["scope"]]
    return [cfg.python, "-m", "h3.render_controller", "--story-file", a["story"], "--scope", a["scope"], *tail, "--mode", "prepare-only"]


def b_build_spec(cfg, a):
    """pack_to_spec.py: stories/<slug>/<pack> -> flow/generated/<slug>/<slug>_image_spec.json and _flow_series.json. Writes files only."""
    pack = safe_path(cfg, a["pack"], ("studio",), None, True, "dir")
    out_dir = cfg.studio / "flow" / "generated" / Path(pack).parent.name   # PACK_REL already limits the slug to [a-z0-9_]
    argv = _py(cfg, "flow", "scripts", "pack_to_spec.py") + ["--pack", pack, "--adhyay", str(a["adhyay"]), "--out-dir", str(out_dir)]
    return argv + (["--overwrite"] if a["overwrite"] else [])


def b_build_jobs(cfg, a):
    """build_jobs.py: spec + series (same flow/generated/<slug>/ folder) -> one jobs file in that folder. Writes files only."""
    spec, series = a["spec"], a["series"]
    if Path(spec).parent != Path(series).parent:
        raise bad("spec and series must be in the same flow/generated/<slug>/ folder")
    return _py(cfg, "flow", "scripts", "build_jobs.py") + ["--adhyay", str(a["adhyay"]), "--spec", spec, "--series", series,
                                                           "--out", str(Path(spec).parent / a["out"])]


@dataclass(frozen=True)
class Cmd:
    id: str
    risk: str                 # R read-only, W writes local files, N free NVIDIA call, $ spends Colab units, R-ops stops a session
    spend: bool
    args: dict
    build: Callable
    needs_h3: bool = False
    post: str = ""            # "colab_verify": after the job, check the Colab session list


BATCH_ARGS = {"batch": A(NAME, True), "gpu": A(GPU, False, "G4"), "session": A(SESSION, False, "t0-kaliya")}
ADH = A(ADHYAY, False, 1)
SHOT_ARGS = {"adhyay": ADH, "shot": A(SHOT, True), "version": A(VERSION, True)}
COMMANDS = {c.id: c for c in (
    Cmd("write_pack", "N, W", False, {"slug": A(SLUG, True), "pack": A(NAME, True), "model": A(WRITER_MODEL, True)}, b_write_pack),
    Cmd("check_pack", "R", False, {"pack": A(PACK_REL, True)}, b_check_pack),
    Cmd("bridge_dry", "R", False, {"size": A(SIZE, True), "adhyay": ADH}, b_bridge(True)),
    Cmd("bridge_write", "W", False, {"size": A(SIZE, True), "adhyay": ADH}, b_bridge(False)),
    Cmd("neighbour_sheet", "W", False, {"jobs": A(JSON_FILE, True), "shot": A(SHOT, True), "candidates": A(CANDS, True), "adhyay": ADH}, b_neighbour),
    Cmd("review_shot", "N, W", False, {"jobs": A(JSON_FILE, True), "shot": A(SHOT, True), "candidates": A(CANDS, True), "adhyay": ADH}, b_review),
    Cmd("queue_add", "W", False, {**SHOT_ARGS, "edit": A(EDIT, True), "jobs": A(JSON_FILE, True), "note": A(NOTE, False, "")}, b_queue_add),
    Cmd("queue_status", "R", False, {"adhyay": ADH}, lambda c, a: _dq(c, "status", a, "--json")),
    Cmd("queue_collect", "W", False, {"adhyay": ADH}, lambda c, a: _dq(c, "collect", a, "--downloads", str(c.downloads))),
    Cmd("queue_accept", "W", False, {**SHOT_ARGS, "note": A(NOTE, False, "")}, b_queue_accept),
    Cmd("tidy_plan", "R", False, {"adhyay": ADH}, b_tidy(False)),
    Cmd("tidy_apply", "W", False, {"adhyay": ADH}, b_tidy(True)),
    Cmd("clip_qa", "W", False, {"clip": A(CLIP, True), "out_dir": A(CLIP_NEW, True)}, b_clip_qa),
    Cmd("visual_qa", "N, W", False, {"clip": A(CLIP, True), "direction": A(JSON_FILE, True), "out_dir": A(CLIP_NEW, True),
                                    "model": A(VISION_MODEL, True), "bible": A(JSON_FILE)}, b_visual),
    Cmd("run_kaggle_prepare", "W", False, {"shots": A(JSON_FILE, True), "scope": A(SCOPE, True), "ids": A(IDS), "reel": A(REEL),
                                           "keyframes": A(DIR_KF, False, _default_keyframes), "batch": A(NAME, True)}, b_prepare),
    Cmd("colab_sessions", "R", False, {}, lambda c, a: [*c.colab, "sessions"]),
    Cmd("colab_usage", "R", False, {}, lambda c, a: [*c.colab, "usage"]),
    Cmd("colab_stop", "R-ops", False, {"session": A(SESSION, True)}, lambda c, a: [*c.colab, "stop", "-s", a["session"]], post="colab_verify"),
    Cmd("colab_run_dry", "R", False, BATCH_ARGS, b_colab_run(False)),
    Cmd("colab_run", "$", True, BATCH_ARGS, b_colab_run(True)),
    Cmd("h3_prepare", "W", False, {"story": A(JSON_FILE, True), "scope": A(SCOPE, True), "ids": A(IDS), "reel": A(REEL)}, b_h3, needs_h3=True),
    Cmd("build_spec", "W", False, {"pack": A(PACK_REL, True), "adhyay": A(GEN_ADHYAY, True), "overwrite": A(BOOL, False, False)}, b_build_spec),
    Cmd("build_jobs_cmd", "W", False, {"spec": A(_gen_json("spec"), True), "series": A(_gen_json("series"), True),
                                       "adhyay": A(GEN_ADHYAY, True), "out": A(JOBS_NAME, True)}, b_build_jobs),
)}


def command_spec(name) -> Cmd:
    if not isinstance(name, str) or name not in COMMANDS:
        raise bad("unknown command")
    return COMMANDS[name]


def estimate_units(gpu: str, clips: int) -> float:
    """Plan section 3: rate x (7 min download + clips x 2.2 min + 5 min setup) / 60."""
    return round(RATES[gpu] * (7 + clips * 2.2 + 5) / 60, 1)


def batch_clips(cfg, name) -> int:
    man = load_json(_batch(cfg, name) / "render_manifest.json")
    if not isinstance(man, dict) or not isinstance(man.get("shots"), list):
        raise bad("batch has no render_manifest.json: rebuild it with run_kaggle.py --target colab")
    return len(man["shots"])


def spend_warning(session) -> str:
    s = session or "(unknown)"
    return f"Colab may still be running session {s}. Check Colab sessions now; if it is listed, run colab stop -s {s}."


def h3_built(cfg) -> bool:
    return (cfg.studio / "h3" / "render_controller.py").is_file()


# ---------------------------------------------------------------- parsers for the Colab CLI and the bridge (text formats, G14)
def parse_usage(text):
    m = re.search(r"(?i)(?:balance|remaining|units? left)[^0-9\-]{0,30}(-?\d+(?:\.\d+)?)", text or "")
    return float(m.group(1)) if m else None


def parse_sessions(text) -> list:
    t = text or ""
    if re.search(r"(?i)\bno (?:active )?sessions?\b", t):
        return []
    rows = []
    for line in t.splitlines():
        toks = line.split()
        if not toks or toks[0].upper() in ("NAME", "SESSION", "SESSIONS", "ID") or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", toks[0]):
            continue
        gpu = next((x for x in toks[1:] if re.fullmatch(r"G\d+|A100|T4|L4|H100|V100", x)), None)
        rows.append({"name": toks[0], "gpu": gpu, "status": " ".join(x for x in toks[1:] if x != gpu)})
    return rows


BRIDGE_LINE = re.compile(r"^(OK|SKIP|DRY-RUN|REFUSED)\s+(\S+)\s*(.*)$")


def parse_bridge_text(text) -> list:
    recs = []
    for line in text.splitlines():
        m = BRIDGE_LINE.match(line.strip())
        if m:
            recs.append({"status": "DRY" if m.group(1) == "DRY-RUN" else m.group(1), "label": m.group(2).rstrip(":"), "detail": m.group(3)})
    return recs


def parse_bridge_json(text):
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, list) else None


# ---------------------------------------------------------------- readers (read-only)
def run_tool_json(cfg, argv, timeout=120):
    try:
        r = subprocess.run(argv, cwd=str(cfg.studio), capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, shell=False, env=ENV, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as e:
        return {"error": f"could not run the check: {type(e).__name__}"}
    if r.returncode != 0:
        return {"error": redact((r.stderr or r.stdout).strip()[-300:])}
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {"error": "check printed no JSON"}


def read_pack(cfg, rel, check=False) -> dict:
    d = Path(safe_path(cfg, str(cfg.studio.joinpath(*rel.split("/"))), ("studio",), None, True, "dir"))
    stages = {k: (d / f"stage_{k}_raw.json").is_file() for k in STAGE_KEYS}
    for f in sorted(d.glob("stage_*_raw.json")):
        stages.setdefault(f.name[len("stage_"):-len("_raw.json")], True)
    pack_md = d / "PACK.md"
    text = pack_md.read_text(encoding="utf-8", errors="replace") if pack_md.is_file() else ""
    gate1 = re.split(r"(?m)^## Gate 2", text)[0][:60000]
    shots = shot_list(d / "shots.json")
    bible = load_json(d / "bible.json", {})
    bible = bible if isinstance(bible, dict) else {}
    chk = run_tool_json(cfg, _py(cfg, "director", "check_pack.py") + [str(d)]) if check else None
    issues = [str(i) for i in chk.get("issues", [])] if isinstance(chk, dict) and isinstance(chk.get("issues"), list) else []
    rows, eps = [], {}
    for s in shots:
        sid = str(s.get("id", ""))
        n_iss = sum(1 for i in issues if i.startswith(sid + ":"))
        rows.append({"id": sid, "episode": s.get("episode"), "mode": s.get("mode"), "seconds": s.get("seconds"),
                     "purpose": str(s.get("purpose") or "")[:200], "cut_in": s.get("cut_in"), "cut_out": s.get("cut_out"), "issues": n_iss})
        e = eps.setdefault(s.get("episode"), {"n": s.get("episode"), "shots": 0, "seconds": 0.0, "issues": 0})
        e["shots"] += 1
        e["seconds"] += num(s.get("seconds"))
        e["issues"] += n_iss
    episodes = []
    for e in sorted(eps.values(), key=lambda x: (x["n"] is None, x["n"] or 0)):
        e["seconds"] = round(e["seconds"], 1)
        if chk is None:
            e["check"] = "not checked"
        elif "error" in chk:
            e["check"] = "error"
        else:
            e["check"] = "PASS" if e["issues"] == 0 else f"ISSUES ({e['issues']})"
        episodes.append(e)

    def named(key):
        items = bible.get(key) if isinstance(bible.get(key), list) else []
        return [{"id": x.get("id"), "name": x.get("name")} for x in items if isinstance(x, dict)]
    def plain(key):
        return [x["name"] or x["id"] or "" for x in named(key)]
    modes = {}
    for r in rows:
        modes[str(r["mode"])] = modes.get(str(r["mode"]), 0) + 1
    return {"pack": rel, "stages": stages, "gate1": gate1, "episodes": episodes, "characters": named("characters"),
            "places": named("environments"), "props": named("props"), "character_names": plain("characters"),
            "place_names": plain("environments"), "prop_names": plain("props"), "modes": modes, "shots": rows, "check": chk}


def queue_state(cfg, adhyay) -> dict:
    dq = _dq_module()
    s = dq.status(cfg.flow, adhyay)
    return {"pending": s["pending"], "filed": s["filed"], "accepted": list(s["accepted"].values())}


_DQ = None


def _dq_module():
    """download_queue.py's own status() is the one reader of the queue, so the UI and the script never disagree."""
    global _DQ
    if _DQ is None:
        scripts = str(STUDIO / "flow" / "scripts")
        if scripts not in sys.path:
            sys.path.append(scripts)
        import download_queue
        _DQ = download_queue
    return _DQ


SPLIT_ID = re.compile(r"__v\d{2}|_cand[A-Z]")


def read_images(cfg, adhyay) -> dict:
    root = cfg.flow / f"adhyay_{adhyay:02d}"
    series = load_json(cfg.studio / "flow" / "flow_series_kaliya.json", {})
    series = series if isinstance(series, dict) else {}

    def items(section):
        sec = series.get(section) if isinstance(series.get(section), dict) else {}
        return [{"id": k, "name": v.get("name"), "chip": v.get("chip"), "sheet": v.get("sheet"),
                 "accepted": v.get("accepted"), "sheet_adhyay": v.get("sheet_adhyay")} for k, v in sec.items() if isinstance(v, dict)]
    style = series.get("style") if isinstance(series.get("style"), dict) else {}
    chip = style.get("chip_sheet") if isinstance(style.get("chip_sheet"), dict) else {}
    sheets = [{"id": "STYLE", "sheet": chip.get("sheet"), "accepted": chip.get("accepted")}] if chip else []
    sheets += [{"id": x["id"], "sheet": x["sheet"], "accepted": x["accepted"]} for sec in ("characters", "places", "props") for x in items(sec) if x["sheet"]]

    progress = jsonl(root / "shots_progress.jsonl")
    last_attempts = {p.get("shot_id"): p.get("attempts") for p in progress if p.get("shot_id")}
    jobs = []
    # the old hand-made jobs files (flow/A_KM_flow_jobs_*.json) and the builder's output (flow/generated/<slug>/*_flow_jobs*.json);
    # 'file' is relative to flow/, so the page can use 'flow/' + file
    job_files = sorted((cfg.studio / "flow").glob("A_KM_flow_jobs_*.json")) + \
        sorted((cfg.studio / "flow" / "generated").glob("*/*_flow_jobs*.json"))
    for f in job_files:
        name = f.relative_to(cfg.studio / "flow").as_posix()
        for j in load_list(f):
            if isinstance(j, dict):
                jobs.append({"file": name, "shot_id": j.get("shot_id"), "scene": j.get("scene"), "chips": j.get("chips") or [],
                             "prompt_sha256": (j.get("prompt_sha256") or "")[:12], "attempts": last_attempts.get(j.get("shot_id")),
                             "attempt_cap": j.get("attempt_cap"), "status": j.get("status")})
    shots = {}

    def shot_entry(sid):
        return shots.setdefault(sid, {"id": sid, "candidates": [], "reviews": []})
    if (root / "shots").is_dir():
        for p in sorted((root / "shots").glob("*.png")):
            if not p.name.startswith("_"):
                shot_entry(SPLIT_ID.split(p.stem)[0])["candidates"].append({"name": p.name, "path": str(p)})
        for p in sorted((root / "shots").glob("*__review.json")):
            data = load_json(p, {})
            if not isinstance(data, dict):
                continue
            sid = data.get("shot_id") or SPLIT_ID.split(p.name[:-len("__review.json")])[0]
            for r in data.get("results") or []:
                if isinstance(r, dict):
                    shot_entry(sid)["reviews"].append({"file": p.name, "candidate": Path(str(r.get("candidate") or "")).name,
                                                       "label": r.get("label"), "verdict": r.get("verdict"), "fix": r.get("fix")})
    q = queue_state(cfg, adhyay)
    finals = [{"name": p.name, "path": str(p), "bytes": p.stat().st_size} for p in sorted((root / "final").glob("*__final.png"))] \
        if (root / "final").is_dir() else []
    keyframes = [{"name": p.name, "path": str(p), "bytes": p.stat().st_size} for p in sorted((root / "keyframes_h3").glob("*.png"))] \
        if (root / "keyframes_h3").is_dir() else []
    return {"adhyay": adhyay, "exists": root.is_dir(), "series": {s: items(s) for s in ("characters", "places", "props")},
            "sheets": sheets, "jobs": jobs, "shots": [shots[k] for k in sorted(shots)],
            "progress": {"lines": progress, "total": len(progress), "legacy": sum(1 for p in progress if "decided_by" not in p)},
            "queue": {"pending": q["pending"], "counts": {"pending": len(q["pending"]), "filed": len(q["filed"]), "accepted": len(q["accepted"])}},
            "filed": q["filed"], "accepted": q["accepted"], "finals": finals, "keyframes": keyframes}


def _clips_in(results: Path) -> list:
    out = []
    if results.is_dir():
        for shot_dir in sorted(p for p in results.iterdir() if p.is_dir()):
            for mp4 in sorted(shot_dir.glob("*.mp4")):
                qa = load_json(results / "qa" / f"{mp4.stem}_qa.json")
                out.append({"shot": shot_dir.name, "take": mp4.stem, "file": str(mp4), "bytes": mp4.stat().st_size,
                            "seconds": qa.get("seconds") if isinstance(qa, dict) else None, "qa": bool(qa)})
    return out[:500]


def read_video(cfg) -> dict:
    st = cfg.studio / "stories"
    shot_files = sorted(p.relative_to(cfg.studio).as_posix() for p in st.rglob("shots*.json"))[:300] if st.is_dir() else []
    t0 = cfg.studio / "director" / "t0_pack" / "t0_shots.json"
    if t0.is_file():
        shot_files.append("director/t0_pack/t0_shots.json")
    batches, clips = [], _clips_in(cfg.studio / "director" / "t0_pack" / "results")
    bdir = cfg.studio / "director" / "colab_batches"
    if bdir.is_dir():
        for b in sorted(p for p in bdir.iterdir() if p.is_dir() and re.fullmatch(r"[a-z0-9_-]{1,40}", p.name)):
            man = load_json(b / "render_manifest.json")
            man = man if isinstance(man, dict) else {}
            run_py = b / "run.py"
            batches.append({"name": b.name, "run_py_bytes": run_py.stat().st_size if run_py.is_file() else None,
                            "run_ipynb_bytes": (b / "run.ipynb").stat().st_size if (b / "run.ipynb").is_file() else None,
                            "settings": len(man["shots"]) if isinstance(man.get("shots"), list) else None,
                            "embed_mb": man.get("embed_mb_total"), "status": load_json(b / "results" / "status.json")})
            clips += _clips_in(b / "results")
    return {"shot_files": shot_files, "batches": batches, "clips": clips[:500]}


# ---------------------------------------------------------------- jobs
class Job:
    def __init__(self, jid, command, argv, spend, session, post, log_path):
        self.id, self.command, self.argv = jid, command, list(argv)
        self.spend, self.session, self.post, self.log_path = spend, session, post, log_path
        self.state, self.rc, self.warning = "running", None, ""
        self.started, self.ended, self.proc = now_iso(), None, None

    def summary(self) -> dict:
        return {"id": self.id, "command": self.command, "state": self.state, "rc": self.rc, "started": self.started,
                "ended": self.ended, "spend": self.spend, "warning": self.warning}


class Api:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.lock = threading.RLock()
        self.tokens: dict = {}
        self.jobs: dict = {}

    # -- audit, jobs
    def _audit(self, event, **fields):
        line = redact(json.dumps({"time": now_iso(), "event": event, **fields}, ensure_ascii=False, default=str))
        with self.lock:
            self.cfg.runs.mkdir(parents=True, exist_ok=True)
            with open(self.cfg.runs / "audit.jsonl", "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def _persist(self, job):
        d = self.cfg.runs / "jobs"
        d.mkdir(parents=True, exist_ok=True)
        rec = {**job.summary(), "argv": [redact(x) for x in job.argv], "session": job.session, "log": job.log_path.name}
        (d / f"{job.id}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")

    def _cli_text(self, args, timeout=60):
        try:
            r = subprocess.run([*self.cfg.colab, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=timeout, shell=False, env=ENV, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            return None
        return r.stdout if r.returncode == 0 else None

    def _spend_gate(self, est):
        if est > CAP_UNITS:
            raise ApiError(403, f"estimate {est} units is above the cap of {CAP_UNITS:g}")
        text = self._cli_text(["usage"])
        bal = parse_usage(text) if text is not None else None
        if bal is None:
            raise ApiError(403, "balance unknown: spend refused (colab usage gave no readable balance)")
        if bal < 1.5 * est:
            raise ApiError(403, f"balance {bal:g} is below 1.5 x the estimate {est}: spend refused")
        return bal

    def _active(self) -> bool:
        return any(j.state == "running" for j in self.jobs.values())

    def _start(self, command, argv, spend, session, post) -> Job:
        jid = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
        jdir = self.cfg.runs / "jobs"
        jdir.mkdir(parents=True, exist_ok=True)
        log_path = jdir / f"{jid}.log"
        logf = open(log_path, "wb")
        try:
            proc = subprocess.Popen(argv, cwd=str(self.cfg.studio), stdin=subprocess.DEVNULL, stdout=logf,
                                    stderr=subprocess.STDOUT, env=ENV, shell=False)
        except OSError as e:
            logf.close()
            raise ApiError(500, f"could not start the command: {type(e).__name__}")
        job = Job(jid, command, argv, spend, session, post, log_path)
        job.proc = proc
        self.jobs[jid] = job
        self._persist(job)
        self._audit("run", command=command, job=jid, argv=argv, spend=spend)
        threading.Thread(target=self._wait, args=(job, logf), daemon=True).start()
        return job

    def _wait(self, job, logf):
        rc = job.proc.wait()
        logf.close()
        if job.post == "colab_verify":
            self._verify_stop(job)   # runs while the state is still "running", so no client sees "done" before the check
        with self.lock:
            job.rc, job.ended = rc, now_iso()
            if job.state == "running":
                job.state = "done" if rc == 0 else "failed"
            if job.spend and job.state != "done":
                job.warning = spend_warning(job.session)
        self._persist(job)
        self._audit("end", command=job.command, job=job.id, rc=rc, state=job.state)

    def _verify_stop(self, job):
        text = self._cli_text(["sessions"])
        if text is None:
            line, job.state = "could not read colab sessions: check by hand before you trust the stop\n", "stop_failed"
        elif job.session in {r["name"] for r in parse_sessions(text)}:
            line, job.state = f"STOP FAILED: session {job.session} is still listed; run colab stop -s {job.session} now\n", "stop_failed"
        else:
            line = f"session {job.session} is no longer listed\n"
        if job.state == "stop_failed":
            job.warning = spend_warning(job.session)
        with open(job.log_path, "a", encoding="utf-8") as f:
            f.write(line)

    def _job(self, jid) -> Job:
        with self.lock:
            job = self.jobs.get(jid)
        if job is None:
            raise ApiError(404, "unknown job")
        return job

    # -- status, h3, stories, pack
    def status(self) -> dict:
        c = self.cfg
        with self.lock:
            running = [j.summary() for j in self.jobs.values() if j.state == "running"]
        return {"studio_ok": c.studio.is_dir(), "flow_ok": c.flow.is_dir(), "python": c.python, "colab_cli": Path(c.colab[0]).is_file(),
                "nvidia_key_files": len(list((c.studio.parent / "secrets" / "nvidia").glob("nvidia_api_key*.txt"))),
                "spend_allowed": c.spend, "spend_cap_units": CAP_UNITS, "job": running[0] if running else None,
                "h3_built": h3_built(c), "time": now_iso()}

    def h3(self) -> dict:
        built = h3_built(self.cfg)
        return {"built": built, "message": "h3 engine built" if built else H3_MISSING, "command": "h3_prepare", "module": "h3.render_controller"}

    def stories(self) -> dict:
        root, out = self.cfg.studio / "stories", []
        if root.is_dir():
            for d in sorted(root.iterdir()):
                if d.is_dir() and re.fullmatch(r"[a-z0-9_]{1,40}", d.name):
                    packs = [p.name for p in sorted(d.iterdir()) if p.is_dir() and re.fullmatch(r"[a-z0-9_-]{1,40}", p.name)
                             and ((p / "shots.json").is_file() or (p / "PACK.md").is_file())]
                    out.append({"slug": d.name, "packs": packs, "has_source": (d / "SOURCE.md").is_file()})
        return {"slugs": out}

    def story_get(self, slug) -> dict:
        slug = SLUG(self.cfg, slug)
        p = self.cfg.studio / "stories" / slug / "SOURCE.md"
        if not p.exists():
            raise ApiError(404, "no SOURCE.md for this story")
        real = Path(safe_path(self.cfg, str(p), ("studio",), (".md",), True, "file"))
        data = real.read_bytes()
        return {"text": data.decode("utf-8", errors="replace"), "bytes": len(data)}

    def story_save(self, slug, body) -> dict:
        slug = SLUG(self.cfg, slug)
        text, overwrite = body.get("text"), body.get("overwrite") is True
        if not isinstance(text, str):
            raise bad("text must be a string")
        data = text.encode("utf-8")
        if len(data) > MAX_TEXT:
            raise ApiError(413, "story is over 200 KB")
        d = self.cfg.studio / "stories" / slug
        safe_path(self.cfg, str(d), ("studio",), None, False)
        target = d / "SOURCE.md"
        if target.exists() and not overwrite:
            raise ApiError(409, "SOURCE.md exists: tick overwrite to replace it")
        d.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        self._project_update({"story_slug": slug})
        return {"saved": f"stories/{slug}/SOURCE.md", "bytes": len(data)}

    def _project_update(self, changes: dict) -> dict:
        """runs/project.json: the pipeline's pointer to the current story, pack and folders (written only here; values validated by the caller)."""
        pl = _pipeline()
        with self.lock:
            project = pl.load_project(self.cfg.runs)
            project.update(changes)
            pl.save_project(self.cfg.runs, project)
        return project

    def pipeline_project(self, body) -> dict:
        """POST /api/pipeline/project {story_slug, pack?, images_dir?, results_dir?, takes?}"""
        changes = {}
        if "story_slug" in body:
            changes["story_slug"] = SLUG(self.cfg, body["story_slug"])
        if body.get("pack") not in (None, ""):
            if not isinstance(body["pack"], str) or not re.fullmatch(r"[a-z0-9_-]{1,40}", body["pack"]):
                raise bad("pack name: lower-case letters, digits, - and _ (1-40)")
            changes["pack"] = body["pack"]
        for key, roots in (("images_dir", ("flow",)), ("results_dir", ("studio", "flow"))):
            if body.get(key) not in (None, ""):
                changes[key] = safe_path(self.cfg, str(body[key]), roots, None, True, "dir")
        if "takes" in body:
            t = body["takes"]
            if not isinstance(t, int) or isinstance(t, bool) or not 1 <= t <= 10:
                raise bad("takes: whole number 1-10")
            changes["takes"] = t
        if not changes:
            raise bad("nothing to set")
        return {"ok": True, "project": self._project_update(changes)}

    def pack(self, rel, check=False) -> dict:
        rel = PACK_REL(self.cfg, rel)
        if not self.cfg.studio.joinpath(*rel.split("/")).is_dir():
            raise ApiError(404, "no such pack")
        return read_pack(self.cfg, rel, check)

    # -- commands: preview, run, jobs
    def preview(self, body) -> dict:
        spec = command_spec(body.get("command"))
        args = normalize(self.cfg, spec, body.get("args") or {})
        if spec.needs_h3 and not h3_built(self.cfg):
            raise ApiError(409, H3_MISSING)
        argv = spec.build(self.cfg, args)
        check_argv(argv)
        est = balance = confirm = None
        if spec.spend:
            est = estimate_units(args["gpu"], batch_clips(self.cfg, args["batch"]))
            balance = self._spend_gate(est) if self.cfg.spend else "not checked (spend is OFF)"
            confirm = f"EXECUTE {est:.1f}"
        token = secrets.token_urlsafe(18)
        rec = {"command": spec.id, "argv": argv, "digest": digest(argv), "spend": spec.spend, "est": est, "confirm": confirm,
               "post": spec.post, "session": args.get("session"), "created": self.cfg.clock(), "used": False}
        with self.lock:
            self.tokens[token] = rec
        self._audit("preview", command=spec.id, argv=argv, spend=spec.spend, estimate=est)
        return {"argv": argv, "risk": spec.risk, "estimate": est, "balance": balance, "token": token, "expires_s": TOKEN_TTL,
                "needs_confirm": spec.spend, "confirm_text": confirm, "spend_allowed": self.cfg.spend}

    def run(self, body) -> dict:
        tok = body.get("token")
        with self.lock:
            rec = self.tokens.get(tok) if isinstance(tok, str) else None
        if rec is None:
            raise ApiError(403, "unknown preview token")
        if rec["used"]:
            raise ApiError(403, "this preview was already used: preview again")
        if self.cfg.clock() - rec["created"] > TOKEN_TTL:
            raise ApiError(403, "preview expired after 60 s: preview again")
        if "command" in body or "args" in body:
            try:
                spec = command_spec(body.get("command", rec["command"]))
                argv = spec.build(self.cfg, normalize(self.cfg, spec, body.get("args") or {}))
            except ApiError:
                argv = None
            if argv is None or spec.id != rec["command"] or digest(argv) != rec["digest"]:
                raise ApiError(403, "arguments changed since the preview: preview again")
        if rec["spend"] and not self.cfg.spend:
            raise ApiError(403, "spend is OFF: the server was not started with --allow-spend")
        if rec["spend"] and body.get("confirm") != rec["confirm"]:
            raise bad(f"type exactly: {rec['confirm']}")
        with self.lock:
            if self._active():
                raise ApiError(409, "another job is running: wait for it or stop it")
        if rec["spend"]:
            self._spend_gate(rec["est"])
        with self.lock:
            if rec["used"]:
                raise ApiError(403, "this preview was already used: preview again")
            if self._active():   # re-check: another run may have started while the spend gate was working (Dots review 2026-11-06)
                raise ApiError(409, "another job is running: wait for it or stop it")
            rec["used"] = True
            job = self._start(rec["command"], rec["argv"], rec["spend"], rec["session"], rec["post"])
        return {"job_id": job.id}

    def jobs_list(self) -> list:
        with self.lock:
            return [j.summary() for j in reversed(list(self.jobs.values()))]

    def job_log(self, jid, q) -> Raw:
        job = self._job(jid)
        n = _int(1, 2000, "tail")(self.cfg, q.get("tail", "200"))
        text = redact("\n".join(tail_text(job.log_path).splitlines()[-n:]))
        return Raw("text/plain; charset=utf-8", text.encode("utf-8"))

    def job_result(self, jid) -> dict:
        job = self._job(jid)
        text = tail_text(job.log_path, 1_000_000)
        if job.command.startswith("bridge_"):
            recs = parse_bridge_json(text)
            if recs is None:
                recs = parse_bridge_text(text)
            return redact_obj({"records": recs, "counts": dict(Counter(r.get("status") for r in recs))})
        if job.command == "queue_collect":
            return redact_obj({"lines": [x for x in text.splitlines() if x.split(" ", 1)[0] in ("FILED", "REFUSED", "WAITING")]})
        if job.command == "review_shot":
            return {"verdict": REVIEW_VERDICT.get(job.rc, "NO RESULT"), "exit": job.rc}
        return redact_obj({"lines": text.splitlines()[-50:]})

    def job_stop(self, jid) -> dict:
        job = self._job(jid)
        with self.lock:
            live = job.state == "running" and job.proc.poll() is None
            if live:
                job.state = "stopped"
        if live:
            job.proc.kill()   # kills the local process only; a $ job may keep its Colab session
            job.warning = spend_warning(job.session) if job.spend else ""
        self._persist(job)
        self._audit("stop", command=job.command, job=job.id, state=job.state)
        return {"state": job.state, "warning": job.warning if live else "the job had already finished"}

    # -- images, review, packet, video, colab, export, files
    def images(self, adhyay) -> dict:
        return read_images(self.cfg, ADHYAY(self.cfg, adhyay))

    def review(self, shot, cand, adhyay) -> dict:
        shot, adh = SHOT(self.cfg, shot), ADHYAY(self.cfg, adhyay)
        if not isinstance(cand, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,160}\.(?:png|jpg|jpeg)", cand):
            raise bad("cand must be a picture file name")
        shots_dir = _adh(self.cfg, {"adhyay": adh}) / "shots"
        cand_path = Path(safe_path(self.cfg, str(shots_dir / cand), ("flow",), (".png", ".jpg", ".jpeg"), True, "file"))
        rev_path = shots_dir / (cand_path.stem + "__review.json")
        data = load_json(rev_path, {})
        raw_results = data.get("results") if isinstance(data, dict) else None
        results = [r for r in (raw_results or []) if isinstance(r, dict)]
        hit = next((r for r in results if Path(str(r.get("candidate") or "")).name == cand), results[0] if results else None)
        if hit is None:
            raise ApiError(404, "no review for this picture")
        return {"shot": shot, "file": rev_path.name, "verdict": hit.get("verdict"), "fix": hit.get("fix"),
                "regen_sentence": hit.get("regen_sentence"), "edit_instruction": hit.get("edit_instruction"),
                "answers": hit.get("answers") or {}}

    def packet(self, body) -> dict:
        jobs_path = safe_path(self.cfg, body.get("jobs"), ("studio",), (".json",), True, "file")
        shots = body.get("shots")
        if not isinstance(shots, list) or not 1 <= len(shots) <= 60:
            raise bad("shots must be a list of 1 to 60 shot ids")
        ids = [SHOT(self.cfg, s) for s in shots]
        entries = {str(j.get("shot_id")): j for j in load_list(jobs_path) if isinstance(j, dict)}
        lines = [f"# Flow agent packet ({now_iso()})", "", "Rules (owner, plan section 11.7):",
                 "- Flow generation and download agents run on Haiku, effort LOW.", "- One scene per agent; each agent uses its own browser tab id.",
                 "- Model chip: Nano Banana 2.1 x2.", "- No downloads in phase 1.", ""]
        for sid in ids:
            j = entries.get(sid)
            if j is None:
                raise bad(f"{sid} is not in the jobs file")
            lines += [f"## {sid}  ({j.get('flow_title', '')})", f"- chips: {', '.join(j.get('chips') or []) or 'none'}",
                      f"- prompt sha256: {j.get('prompt_sha256', '')}"]
            if j.get("edit_instruction"):
                lines.append(f"- edit instruction: {j['edit_instruction']}")
            lines += ["- prompt:", "", "```text", str(j.get("prompt", "")), "```", ""]
        md = "\n".join(lines)
        if has_secret(md):
            raise bad("packet not written: key-like text found in the job text")
        d = self.cfg.runs / "packets"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"packet-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}.md"
        path.write_text(md, encoding="utf-8")
        self._audit("packet", path=str(path), shots=ids)
        return {"path": str(path), "markdown": md}

    def video(self) -> dict:
        return read_video(self.cfg)

    def colab(self) -> dict:
        s_text, u_text = self._cli_text(["sessions"]), self._cli_text(["usage"])
        return {"sessions": parse_sessions(s_text) if s_text is not None else None,
                "balance": parse_usage(u_text) if u_text is not None else None,
                "read_ok": {"sessions": s_text is not None, "usage": u_text is not None},
                "rate_units_per_hour": RATES, "cap_units": CAP_UNITS}

    def export(self, reel, pack) -> dict:
        n, rel = REEL(self.cfg, reel), PACK_REL(self.cfg, pack)
        ids = [s.get("id") for s in shot_list(self.cfg.studio.joinpath(*rel.split("/")) / "shots.json") if s.get("episode") == n]
        order = {sid: i for i, sid in enumerate(ids)}
        clips = [c for c in read_video(self.cfg)["clips"] if c["shot"] in order]
        clips.sort(key=lambda c: (order[c["shot"]], c["take"]))
        reel_dir = self.cfg.studio / "reels" / f"reel_{n:02d}"
        files = sorted(p.name for p in reel_dir.iterdir() if p.is_file()) if reel_dir.is_dir() else []
        return {"reel": n, "pack": rel, "shot_ids": ids, "clips_in_order": clips, "assembly": "not built",
                "assembly_note": "not built (gap G12): no assembly command in v1", "reel_files": files}

    def file_response(self, raw) -> Raw:
        real = Path(safe_path(self.cfg, raw, ("studio", "flow"), FILE_EXTS, True, "file"))
        if real.stat().st_size > MAX_FILE:
            raise ApiError(413, "file is over 60 MB")
        return Raw(MIME.get(real.suffix.lower(), "application/octet-stream"), real.read_bytes())


def static_file(cfg, name) -> Raw:
    base = cfg.studio / "ui" / "static"
    if not (base / name).is_file():
        raise ApiError(404, "static file is missing")
    real = Path(safe_path(cfg, str(base / name), ("studio",), (".html", ".js", ".css"), True, "file"))
    return Raw(MIME[real.suffix.lower()], real.read_bytes())


def _pipeline():
    """The pipeline state module (ui/pipeline.py); loaded lazily so the server still runs while it is missing."""
    try:
        import pipeline
        return pipeline
    except ImportError:
        raise ApiError(503, "pipeline module not installed yet")


def pipeline_get(api, what):
    pl = _pipeline()
    if what == "summary":
        return pl.summary(api.cfg.studio, api.cfg.runs)
    return pl.pipeline_state(api.cfg.studio, api.cfg.runs)


def pipeline_gate(api, body):
    """POST /api/pipeline/gate {gate, decision, note, confirm?}: records the owner's decision (the only write is runs/approvals.jsonl)."""
    pl = _pipeline()
    try:
        gate = pl.apply_gate(api.cfg.studio, api.cfg.runs, str(body.get("gate", "")), str(body.get("decision", "")),
                             str(body.get("note", "")), body.get("confirm"), who="owner")
    except pl.GateError as e:
        raise ApiError(getattr(e, "code", 409), str(e))
    return {"ok": True, "gate": gate}


def dispatch(api: Api, method: str, path: str, q: dict, body: dict):
    if method == "GET":
        if path == "/":
            return static_file(api.cfg, "index.html")
        m = re.fullmatch(r"/(?:static/)?([A-Za-z0-9_.-]{1,80}\.(?:css|js))", path)   # index.html links style.css and app.js relative to "/"
        if m:
            return static_file(api.cfg, m.group(1))
        if path in ("/api/pipeline", "/api/pipeline/summary"):
            return pipeline_get(api, path.rsplit("/", 1)[-1])
        if path == "/api/status":
            return api.status()
        if path == "/api/h3":
            return api.h3()
        if path == "/api/story":
            return api.stories()
        m = re.fullmatch(r"/api/story/([a-z0-9_]{1,40})", path)
        if m:
            return api.story_get(m.group(1))
        if path == "/api/pack":
            return api.pack(q.get("pack", ""), q.get("check") == "1")
        if path == "/api/jobs":
            return api.jobs_list()
        m = re.fullmatch(r"/api/jobs/([0-9A-Za-z_-]{1,64})/(log|result)", path)
        if m:
            return api.job_log(m.group(1), q) if m.group(2) == "log" else api.job_result(m.group(1))
        if path == "/api/images":
            return api.images(q.get("adhyay", "1"))
        if path == "/api/review":
            return api.review(q.get("shot", ""), q.get("cand", ""), q.get("adhyay", "1"))
        if path == "/api/video":
            return api.video()
        if path == "/api/colab":
            return api.colab()
        if path == "/api/export":
            return api.export(q.get("reel", ""), q.get("pack", STORY_PACK))
        if path == "/api/file":
            return api.file_response(q.get("path", ""))
    elif method == "POST":
        m = re.fullmatch(r"/api/story/([a-z0-9_]{1,40})", path)
        if m:
            return api.story_save(m.group(1), body)
        if path == "/api/preview":
            return api.preview(body)
        if path == "/api/run":
            return api.run(body)
        m = re.fullmatch(r"/api/jobs/([0-9A-Za-z_-]{1,64})/stop", path)
        if m:
            return api.job_stop(m.group(1))
        if path == "/api/packet":
            return api.packet(body)
        if path == "/api/pipeline/gate":
            return pipeline_gate(api, body)
        if path == "/api/pipeline/project":
            return api.pipeline_project(body)
    raise ApiError(404, "unknown path")


class Handler(BaseHTTPRequestHandler):
    server_version = "AnimeStudioUI"
    protocol_version = "HTTP/1.0"

    def log_message(self, fmt, *args):   # keep the console quiet; the audit file has the record
        pass

    def do_GET(self):
        self._serve("GET")

    def do_POST(self):
        self._serve("POST")

    def _serve(self, method):
        try:
            self._guard(method == "POST")
            url = urlsplit(self.path)
            q = {k: v[-1] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
            body = self._body() if method == "POST" else {}
            result = dispatch(self.server.api, method, url.path, q, body)
            if isinstance(result, Raw):
                self._send(200, result.ctype, result.data)
            else:
                self._send(200, JSON_CT, json.dumps(result, ensure_ascii=False).encode("utf-8"))
        except ApiError as e:
            self._send(e.code, JSON_CT, json.dumps({"error": e.msg}, ensure_ascii=False).encode("utf-8"))
        except Exception:
            traceback.print_exc()
            self._send(500, JSON_CT, b'{"error": "internal error (see the server console)"}')

    def _guard(self, post):
        if self.headers.get("Host", "") not in self.server.allowed_hosts:
            raise ApiError(403, "host not allowed: use 127.0.0.1 or localhost")
        origin = self.headers.get("Origin")
        if origin is not None and origin not in self.server.allowed_origins:
            raise ApiError(403, "origin not allowed")
        if post and self.headers.get("X-UI") != "1":
            raise ApiError(403, "POST needs the X-UI: 1 header")

    def _body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise bad("bad Content-Length")
        if n > MAX_BODY:
            raise ApiError(413, "request body is too big")
        raw = self.rfile.read(n) if n > 0 else b""
        if not raw.strip():
            return {}
        try:
            obj = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise bad("body is not valid JSON")
        if not isinstance(obj, dict):
            raise bad("body must be a JSON object")
        return obj

    def _send(self, code, ctype, data: bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)


class UIServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False   # Windows: SO_REUSEADDR would let a second process take the port


def make_server(cfg: Config, port: int = PORT) -> UIServer:
    srv = UIServer(("127.0.0.1", port), Handler)
    srv.api = Api(cfg)
    actual = srv.server_address[1]
    srv.allowed_hosts = {f"127.0.0.1:{actual}", f"localhost:{actual}"}
    srv.allowed_origins = {f"http://{h}" for h in srv.allowed_hosts}
    return srv


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Anime Studio control UI (local API on 127.0.0.1).")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--allow-spend", action="store_true", help="enable $ runs; each still needs a preview token and the typed confirm")
    ap.add_argument("--root-override", action="append", default=[], metavar="NAME=PATH",
                    help="test hooks: studio, flow, downloads, python, colab")
    a = ap.parse_args(argv)
    cfg = Config(spend=a.allow_spend)
    for item in a.root_override:
        name, _, value = item.partition("=")
        if name == "colab":
            cfg.colab = [value]
        elif name in ("studio", "flow", "downloads"):
            setattr(cfg, name, Path(value))
        elif name == "python":
            cfg.python = value
        else:
            ap.error(f"unknown override {name}")
    srv = make_server(cfg, a.port)
    print(f"Anime Studio UI: http://127.0.0.1:{srv.server_address[1]}  spend {'ON' if cfg.spend else 'OFF'}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
