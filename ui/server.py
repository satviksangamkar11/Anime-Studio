"""Anime Studio control UI: the local API on 127.0.0.1 (ui/PLAN.md sections 2, 4, 6, 11).

  C:\\Python314\\python.exe ui\\server.py                 spend OFF (default)
  C:\\Python314\\python.exe ui\\server.py --allow-spend   owner only: $ runs become possible; each still needs a preview token and the typed confirm
  C:\\Python314\\python.exe ui\\server.py --allow-claude  owner only: the Claude writer becomes possible; each run still needs the typed word CLAUDE

Stdlib only. Only the COMMANDS table can run anything; no shell; every argv is a list built from validated values.
Test hooks: --root-override studio=PATH | flow=PATH | downloads=PATH | python=PATH | colab=PATH (test_ui.py points them at fake tools)."""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import shutil
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
TEXT_EXTS = (".json", ".md", ".txt", ".jsonl", ".log")
FORBIDDEN_PARTS = {"granthstudio", "animation_research_tool", "secrets"}
BANNED_TOKENS = {"--logtostderr", "--allow-paid", "--push", "--fetch", "--stage-via"}
BANNED_PAIRS = {("--via", "claude"), ("--via", "openrouter"), ("--writer", "opus")}   # --writer opus: only write_pack_claude may carry it
H3_MISSING = "h3 engine not built yet"
LEGACY_STORY = "kaliya_mardan"                # the one legacy project: its own roots and style; other stories use story_links
LANGS = ("en", "hi", "mr")
YT_URL = re.compile(r"^https?://(www\.)?(youtube\.com|youtu\.be)/[^\s]{1,300}$", re.I)
DISK_PATHS = ("C:/", "D:/")
LEDGER_NAME = "colab_spend.jsonl"
STARTED = dt.datetime.now().astimezone().isoformat(timespec="seconds")
SERVER_MTIME0 = os.path.getmtime(os.path.abspath(__file__))
PIPELINE_MOD = None
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
    allow_claude: bool = False                # owner only (--allow-claude): the Claude writer may be chosen; each run still needs the typed word
    clock: Callable[[], float] = time.time
    total_cap: float | None = None            # owner sets a cumulative Colab cap; None = report only
    disk_paths: tuple = DISK_PATHS

    @property
    def runs(self) -> Path:
        return self.studio / "ui" / "runs"

    @property
    def ledger(self) -> Path:
        return self.runs / LEDGER_NAME


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


def _registry():
    """director/run_registry.py (stdlib): the run log of each story. None when it cannot be imported (the UI still runs)."""
    d = str(STUDIO / "director")
    if d not in sys.path:
        sys.path.insert(0, d)
    try:
        import run_registry
    except ImportError:
        return None
    return run_registry


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
WRITER_MODEL = _enum("model", "nvidia/nemotron-3-ultra-550b-a55b", "nvidia/nemotron-3.5-super-vl-120b-a12b")   # legacy single-call NVIDIA path (argv kept as before)
WRITER_NAME = _enum("writer", "super-vl", "ultra")                          # write_pack --writer shortcut; both are free OpenRouter models
WRITER_ROUTE = {"super-vl": ("openrouter", "nvidia/nemotron-3.5-super-vl:free"),   # mirrors director/write_pack.py WRITERS (test_registry checks)
                "ultra": ("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free")}
DEFAULT_WRITER = "super-vl"
CLAUDE_CONFIRM = "CLAUDE"                     # the typed word for the one Claude command (write_pack_claude)
CLAUDE_OFF = "claude is off: the server was not started with --allow-claude"
DEFAULT_WRITER_CHOICE = "or-super-vl"
WRITER_CHOICES = (   # GET /api/writers, in display order; the page names each choice with the i18n keys writer.<id>.name / .desc
    {"id": "nv-ultra", "group": "nvidia", "command": "write_pack", "args": {"model": "nvidia/nemotron-3-ultra-550b-a55b"},
     "cost": "free", "speed": "slow", "quality": "high", "tested": True, "needs": "nvidia"},
    {"id": "nv-super-vl", "group": "nvidia", "command": "write_pack", "args": {"model": "nvidia/nemotron-3.5-super-vl-120b-a12b"},
     "cost": "free", "speed": "medium", "quality": "good", "tested": False, "needs": "nvidia"},
    {"id": "or-super-vl", "group": "openrouter", "command": "write_pack", "args": {"writer": "super-vl"},
     "cost": "free", "speed": "medium", "quality": "good", "tested": True, "needs": "openrouter"},
    {"id": "or-ultra", "group": "openrouter", "command": "write_pack", "args": {"writer": "ultra"},
     "cost": "free", "speed": "slow", "quality": "high", "tested": False, "needs": "openrouter"},
    {"id": "claude-opus", "group": "claude", "command": "write_pack_claude", "args": {},
     "cost": "subscription", "speed": "medium", "quality": "highest", "tested": True, "needs": "claude"},
)
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


def _yt_url(cfg, v):
    if not isinstance(v, str) or not YT_URL.fullmatch(v):
        raise bad("the link must be a YouTube address")
    return v


PACK_PATH = _rx(r"stories/[a-z0-9_]{1,40}/[a-z0-9_-]{1,40}", "pack path")


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


def check_argv(argv: list, allow: frozenset = frozenset()) -> None:
    for i, tok in enumerate(argv):
        if tok in BANNED_TOKENS:
            raise bad(f"{tok} is never passed by the UI")
        pair = (argv[i - 1], tok) if i else None
        if pair in BANNED_PAIRS and pair not in allow:
            if pair == ("--writer", "opus"):
                raise bad("claude runs only through the Claude choice (write_pack_claude)")
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
        known = {str(s.get("id")) for s in shots if s.get("id") is not None}   # text form: an unhashable id must not raise
        missing = [i for i in ids if str(i) not in known]
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


def write_pack_route(a, writer=None) -> str:
    """The path and model a write_pack preview will run, as text for the owner."""
    if writer == "opus":
        return "writer opus: claude opus, effort medium (Claude subscription; may cost money)"
    if a.get("model"):
        return f"legacy NVIDIA path: nvidia {a['model']}"
    name = a.get("writer") or DEFAULT_WRITER
    via, model = WRITER_ROUTE[name]
    return f"writer {name}: {via} {model} (free model, streamed)"


def b_write_pack(cfg, a, writer=None):
    name = writer or a.get("writer") or DEFAULT_WRITER
    src = cfg.studio / "stories" / a["slug"] / "SOURCE.md"
    if not src.is_file():
        raise bad("save the story first: SOURCE.md is missing")
    dest = src.parent / a["pack"]
    if (dest / "PACK.md").exists():   # a finished pack is never overwritten: a new run needs a new name
        rr = _registry()
        taken = {p.name for p in src.parent.iterdir() if p.is_dir()}
        hint = rr.pack_name(name, taken=taken) if rr else "a new pack name"
        raise bad(f"{a['pack']} is already finished (PACK.md exists): use {hint}")
    if a.get("model") and a.get("writer"):
        raise bad("give a writer or a model, not both")
    if not a.get("out_lang"):
        raise bad("choose at least one output language (en, hi, mr): the writer has no default")
    lang = ["--out-lang", a["out_lang"]]
    if a.get("model"):
        return _py(cfg, "director", "write_pack.py") + [str(src), str(dest), "--staged", "--via", "nvidia", "--model", a["model"]] + lang
    return _py(cfg, "director", "write_pack.py") + [str(src), str(dest), "--staged", "--writer", name] + lang


def b_write_pack_claude(cfg, a):
    """write_pack --writer opus (Claude). Reached only through CLAUDE_COMMANDS: the server must run with --allow-claude."""
    return b_write_pack(cfg, {**a, "writer": None, "model": None}, writer="opus")


def out_lang_arg(cfg, v):
    """'en', 'hi,en' (priority order) or 'all' -> the comma list for --out-lang. Refuses repeats, empty and unknown codes."""
    if not isinstance(v, str):
        raise bad("out_lang must be text")
    if v.strip() == "all":
        return ",".join(LANGS)
    parts = [x.strip() for x in v.split(",")]
    if not parts or any(x not in LANGS for x in parts) or len(set(parts)) != len(parts):
        raise bad("out_lang must be en, hi, mr (one or more, no repeats) or all")
    return ",".join(parts)


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
    style = a.get("style") or (LEGACY_STORY if Path(a["shots"]).parent.parent.name == LEGACY_STORY else None)
    if not style:
        raise bad("style is required for this story (the legacy Kaliya style is only the default for its own folder)")
    return argv + ["--style", style, "--target", "colab", "--profile", str(a.get("profile") or 5)]


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
    story = load_json(a["story"], None)
    if not isinstance(story, dict) or not isinstance(story.get("episodes"), list) or not isinstance(story.get("registry"), dict):
        raise bad("the story file must be an H3 story (episodes + registry); shots.json is not accepted here")
    tail = {"shots": a.get("ids") or [], "reel": [f"EP_{int(a['reel']):02d}"] if a.get("reel") else [], "all": []}[a["scope"]]
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
    risk: str                 # R read-only, W writes local files, N free NVIDIA call, $ spends Colab units, R-ops stops a session, C Claude call
    spend: bool
    args: dict
    build: Callable
    needs_h3: bool = False
    post: str = ""            # "colab_verify": after the job, check the Colab session list
    confirm: str = ""         # typed word asked before a command that is not a spend (write_pack_claude: CLAUDE)
    needs: str = ""           # "claude": refused unless the server was started with --allow-claude
    allow: frozenset = frozenset()   # argv pairs this command may carry (the only place --writer opus is allowed)


def b_yt(cfg, a):
    """director/yt_transcript.py: link -> stories/<slug>/SOURCE.md. Writes one file; no spend, no model call."""
    argv = _py(cfg, "director", "yt_transcript.py") + [a["url"], str(cfg.studio / "stories" / a["story"]),
                                                      "--lang", a["lang"], "--asr", a["asr"]]
    return argv + (["--overwrite"] if a["overwrite"] else [])


def b_author(cfg, a):
    """h3/h3_author.py: dry run only (prompts, no model call). The live run is refused here and in dispatch."""
    pack = safe_path(cfg, a["pack"], ("studio",), None, True, "dir")
    return [cfg.python, str(cfg.studio / "h3" / "h3_author.py"), pack, "--dry-run"]


BATCH_ARGS = {"batch": A(NAME, True), "gpu": A(GPU, False, "G4"), "session": A(SESSION, False, "t0-kaliya")}
ADH = A(ADHYAY, False, 1)
SHOT_ARGS = {"adhyay": ADH, "shot": A(SHOT, True), "version": A(VERSION, True)}
COMMANDS = {c.id: c for c in (
    Cmd("write_pack", "N, W", False, {"slug": A(SLUG, True), "pack": A(NAME, True), "writer": A(WRITER_NAME), "model": A(WRITER_MODEL),
                                      "out_lang": A(out_lang_arg)}, b_write_pack),
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
                                           "keyframes": A(DIR_KF, False, _default_keyframes), "batch": A(NAME, True),
                                           "style": A(NAME), "profile": A(_int(1, 5, "profile"))}, b_prepare),
    Cmd("colab_sessions", "R", False, {}, lambda c, a: [*c.colab, "sessions"]),
    Cmd("colab_usage", "R", False, {}, lambda c, a: [*c.colab, "usage"]),
    Cmd("colab_stop", "R-ops", False, {"session": A(SESSION, True)}, lambda c, a: [*c.colab, "stop", "-s", a["session"]], post="colab_verify"),
    Cmd("colab_run_dry", "R", False, BATCH_ARGS, b_colab_run(False)),
    Cmd("yt_transcript", "W", False, {"url": A(_yt_url, True), "story": A(SLUG, True), "lang": A(_enum("lang", "auto", "en", "hi", "mr"), False, "auto"),
                                      "asr": A(_enum("asr", "auto", "off", "force"), False, "auto"), "overwrite": A(BOOL, False, False)}, b_yt),
    Cmd("h3_author", "R", False, {"pack": A(PACK_PATH, True)}, b_author),
    Cmd("colab_run", "$", True, BATCH_ARGS, b_colab_run(True), post="colab_verify"),
    Cmd("h3_prepare", "W", False, {"story": A(JSON_FILE, True), "scope": A(SCOPE, True), "ids": A(IDS), "reel": A(REEL)}, b_h3, needs_h3=True),
    Cmd("build_spec", "W", False, {"pack": A(PACK_REL, True), "adhyay": A(GEN_ADHYAY, True), "overwrite": A(BOOL, False, False)}, b_build_spec),
    Cmd("build_jobs_cmd", "W", False, {"spec": A(_gen_json("spec"), True), "series": A(_gen_json("series"), True),
                                       "adhyay": A(GEN_ADHYAY, True), "out": A(JOBS_NAME, True)}, b_build_jobs),
)}


CLAUDE_COMMANDS = {c.id: c for c in (   # apart from COMMANDS on purpose: test_ui pins COMMANDS to its own case table; command_spec reads both
    Cmd("write_pack_claude", "C, W", False, {"slug": A(SLUG, True), "pack": A(NAME, True), "out_lang": A(out_lang_arg)},
        b_write_pack_claude, confirm=CLAUDE_CONFIRM, needs="claude", allow=frozenset({("--writer", "opus")})),
)}


def command_spec(name) -> Cmd:
    if isinstance(name, str) and name in CLAUDE_COMMANDS:
        return CLAUDE_COMMANDS[name]
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
        secs = s.get("editorial_duration_sec")
        if secs is None:          # 0 is a real value; only a missing field falls back to 'seconds'
            secs = s.get("seconds")
        rows.append({"id": sid, "episode": s.get("episode"), "mode": s.get("route") or s.get("mode"),
                     "seconds": max(0, secs) if isinstance(secs, (int, float)) and not isinstance(secs, bool)
                     else 0,   # negative shows as 0; bool, None and any non-number (e.g. a string) as 0
                     "purpose": str(s.get("purpose") or "")[:200], "cut_in": s.get("cut_in"), "cut_out": s.get("cut_out"), "issues": n_iss})
        ep_key = s.get("episode")
        if isinstance(ep_key, (list, dict)):
            ep_key = str(ep_key)         # unhashable episode: its text form (the dict key must be hashable)
        e = eps.setdefault(ep_key, {"n": ep_key, "shots": 0, "seconds": 0.0, "issues": 0})
        e["shots"] += 1
        e["seconds"] += max(0.0, num(secs))   # zero or negative seconds count as 0
        e["issues"] += n_iss
    episodes = []
    # numbers sort among numbers, everything else among strings: mixed types must not raise TypeError
    ep_key = lambda x: ((x["n"] is None, 0, x["n"]) if isinstance(x["n"], (int, float)) and not isinstance(x["n"], bool)
                        else (x["n"] is None, 1, str(x["n"])))
    for e in sorted(eps.values(), key=ep_key):
        e["seconds"] = round(e["seconds"], 1)
        if chk is None:
            e["check"] = "not checked"
        elif "error" in chk:
            e["check"] = "error"
        else:
            e["check"] = "PASS" if e["issues"] == 0 else f"ISSUES ({e['issues']})"
        episodes.append(e)

    def named(key):
        return [{"id": x.get("id"), "name": x.get("name")} for x in _pipeline().bible_items(bible, key)]
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


def _story_image_root(cfg, slug):
    """The images folder a story links to (story_links kind 'images'). None when it has none."""
    d = str(STUDIO / "director")
    if d not in sys.path:
        sys.path.append(d)
    import story_links
    for link in story_links.check(cfg.studio, slug):
        if link.get("kind") == "images" and link.get("exists") and link.get("resolved"):
            return Path(link["resolved"])
    return None


def read_images(cfg, adhyay, slug=LEGACY_STORY) -> dict:
    legacy = slug == LEGACY_STORY
    if legacy:
        root = cfg.flow / f"adhyay_{adhyay:02d}"
        series_file = cfg.studio / "flow" / "flow_series_kaliya.json"
    else:
        root = _story_image_root(cfg, slug) or (cfg.studio / "flow" / "__no_images_folder__")
        series_file = cfg.studio / "flow" / "generated" / slug / f"{slug}_flow_series.json"
    series = load_json(series_file, {})
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
    job_files = (sorted((cfg.studio / "flow").glob("A_KM_flow_jobs_*.json")) if legacy else []) + \
        sorted((cfg.studio / "flow" / "generated" / slug).glob("*_flow_jobs*.json"))
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
    q = queue_state(cfg, adhyay) if legacy else {"pending": [], "filed": [], "accepted": []}
    finals = [{"name": p.name, "path": str(p), "bytes": _size(p)} for p in sorted((root / "final").glob("*__final.png"))] \
        if (root / "final").is_dir() else []
    keyframes = [{"name": p.name, "path": str(p), "bytes": _size(p)} for p in sorted((root / "keyframes_h3").glob("*.png"))] \
        if (root / "keyframes_h3").is_dir() else []
    return {"adhyay": adhyay, "exists": root.is_dir(), "series": {s: items(s) for s in ("characters", "places", "props")},
            "sheets": sheets, "jobs": jobs, "shots": [shots[k] for k in sorted(shots)],
            "progress": {"lines": progress, "total": len(progress), "legacy": sum(1 for p in progress if "decided_by" not in p)},
            "queue": {"pending": q["pending"], "counts": {"pending": len(q["pending"]), "filed": len(q["filed"]), "accepted": len(q["accepted"])}},
            "filed": q["filed"], "accepted": q["accepted"], "finals": finals, "keyframes": keyframes}


def _size(p: Path):
    """File size in bytes, or None when the file vanished after the listing (a glob/stat race must not crash it)."""
    try:
        return p.stat().st_size
    except OSError:
        return None


def _clips_in(results: Path) -> list:
    out = []
    if results.is_dir():
        for shot_dir in sorted(p for p in results.iterdir() if p.is_dir()):
            for mp4 in sorted(shot_dir.glob("*.mp4")):
                qa = load_json(results / "qa" / f"{mp4.stem}_qa.json")
                out.append({"shot": shot_dir.name, "take": mp4.stem, "file": str(mp4), "bytes": _size(mp4),
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
            batches.append({"name": b.name, "run_py_bytes": _size(run_py) if run_py.is_file() else None,
                            "run_ipynb_bytes": _size(b / "run.ipynb") if (b / "run.ipynb").is_file() else None,
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
        self.verified = None      # spend jobs: True once the Colab session is verified gone (D8 lock until then)

    @classmethod
    def from_record(cls, rec: dict, log_path: Path) -> "Job":
        job = cls(str(rec.get("id")), str(rec.get("command", "")), rec.get("argv") or [], bool(rec.get("spend")),
                  rec.get("session"), rec.get("post", ""), log_path)
        job.state, job.rc = rec.get("state", "done"), rec.get("rc")
        job.started, job.ended = rec.get("started"), rec.get("ended")
        job.verified, job.warning = rec.get("verified"), rec.get("warning", "")
        if job.state == "running":           # the server restarted while the process ran: unknown until checked by hand
            job.state = "lost"
            job.warning = "the server restarted while this job ran: check Colab by hand"
        return job

    def summary(self) -> dict:
        return {"id": self.id, "command": self.command, "state": self.state, "rc": self.rc, "started": self.started,
                "ended": self.ended, "spend": self.spend, "warning": self.warning, "verified": self.verified}


class Api:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.lock = threading.RLock()
        self.tokens: dict = {}
        self.jobs: dict = {}
        self._load_jobs()

    def _load_jobs(self):
        """D8: the job table is rebuilt from runs/jobs/*.json, so a restart forgets nothing."""
        d = self.cfg.runs / "jobs"
        if not d.is_dir():
            return
        for f in sorted(d.glob("*.json")):
            rec = load_json(f)
            if isinstance(rec, dict) and rec.get("id"):
                job = Job.from_record(rec, d / (rec.get("log") or f.stem + ".log"))
                self.jobs[job.id] = job

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
        rec = {**job.summary(), "argv": [redact(x) for x in job.argv], "session": job.session, "log": job.log_path.name, "post": job.post}
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
        if self.cfg.total_cap is not None:   # D9: cumulative, from the append-only ledger
            total = _ops_checks().colab_spend_total(self.cfg.ledger)["total"]
            if total + est > self.cfg.total_cap:
                raise ApiError(403, f"ledger total {total:g} + {est:g} is above the total cap {self.cfg.total_cap:g}")
        return bal

    def _active(self) -> bool:
        """D8: a spend job blocks new spend until it is verified gone (not only while it runs)."""
        return any(j.state == "running" or (j.spend and j.verified is not True) for j in self.jobs.values())

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
        if job.command == "write_pack" and job.state in ("stopped", "failed"):
            self._close_run(job)

    def _close_run(self, job):
        """A write_pack job that was stopped or failed: its open steps get a closing line in the run log."""
        folder = self._hook("story_folder", Path(job.argv[2]))
        if folder is not None:
            status = "stopped" if job.state == "stopped" else "failed"
            self._hook("close_open_steps", folder, status, "stopped from the UI" if status == "stopped" else f"exit {job.rc}")

    def _hook(self, what, *args, **kwargs):
        """A run-registry call made by the UI: best effort. A failure is audited and returns None; it never breaks the request."""
        try:
            rr = _registry()
            if rr is None:
                raise ImportError("run_registry")
            return getattr(rr, what)(*args, **kwargs)
        except Exception as e:
            try:
                self._audit("registry_hook_failed", hook=what, error=type(e).__name__)
            except OSError:
                pass
            return None

    def _verify_stop(self, job):
        text = self._cli_text(["sessions"])
        job.verified = False
        if text is None:
            line, job.state = "could not read colab sessions: check by hand before you trust the stop\n", "stop_failed"
        elif job.session in {r["name"] for r in parse_sessions(text)}:
            line, job.state = f"STOP FAILED: session {job.session} is still listed; run colab stop -s {job.session} now\n", "stop_failed"
        else:
            line, job.verified = f"session {job.session} is no longer listed\n", True
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
                "spend_allowed": c.spend, "claude_allowed": c.allow_claude, "spend_cap_units": CAP_UNITS, "job": running[0] if running else None,
                "h3_built": h3_built(c), "time": now_iso(),
                "disk": [_ops_checks().disk_free(p) for p in c.disk_paths], "build": _ops_checks().code_fingerprint(c.studio)}

    def writers(self) -> dict:
        """GET /api/writers: the step 2 choices and whether each can run now. Counts and yes/no only: never key text or paths."""
        c = self.cfg
        nv = len(list((c.studio.parent / "secrets" / "nvidia").glob("nvidia_api_key*.txt")))
        orf = Path(os.environ.get("OPENROUTER_KEY_FILE") or c.studio.parent / "loop_p0" / "secrets" / "openrouter_paid_key.txt").is_file()
        cli = shutil.which("claude") is not None

        def reason(o):
            if o["needs"] == "nvidia":
                return "" if nv else "no_nvidia_key"
            if o["needs"] == "openrouter":
                return "" if orf else "no_openrouter_key"
            if not c.allow_claude:
                return "claude_off"
            return "" if cli else "claude_missing"
        opts = []
        for o in WRITER_CHOICES:
            why = reason(o)
            opts.append({**{k: v for k, v in o.items() if k != "needs"}, "available": not why, "reason": why})
        return {"default": DEFAULT_WRITER_CHOICE, "claude_allowed": c.allow_claude, "confirm_word": CLAUDE_CONFIRM,
                "checks": {"nvidia_key_files": nv, "openrouter_key_file": orf, "claude_cli": cli}, "options": opts}

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
                    s = self._hook("summary", d) or {}
                    latest = s.get("latest_pack")
                    out.append({"slug": d.name, "packs": packs, "has_source": (d / "SOURCE.md").is_file(), "latest_pack": latest,
                                "latest_model": (s.get("pack_models") or {}).get(latest) or s.get("last_model"),
                                "output_languages": _pipeline().output_languages(self.cfg.studio, d.name),
                                "state": self._story_state_safe(d.name)})
        return {"slugs": out}

    def registry_list(self) -> dict:
        """GET /api/registry: one run-log summary per story folder (read only)."""
        rr = _registry()
        if rr is None:
            raise ApiError(503, "run registry not installed")
        root, out = self.cfg.studio / "stories", []
        if root.is_dir():
            for d in sorted(root.iterdir()):
                if d.is_dir() and re.fullmatch(r"[a-z0-9_]{1,40}", d.name):
                    try:
                        out.append(rr.summary(d))
                    except Exception:
                        out.append({"slug": d.name, "error": "could not read the run log"})
        return redact_obj({"stories": out})

    def registry_get(self, slug) -> dict:
        """GET /api/registry/{slug}: the story, its runs, every step and RUN_REPORT text (read only; nothing is written)."""
        slug = SLUG(self.cfg, slug)
        rr = _registry()
        if rr is None:
            raise ApiError(503, "run registry not installed")
        d = self.cfg.studio / "stories" / slug
        if not d.is_dir():
            raise ApiError(404, "no such story")
        events = rr.read_events(d)
        rows = rr.steps(events)
        return redact_obj({"slug": slug, "story": rr.read_story(d), "summary": rr.summary(d), "runs": rr.runs(events, rows),
                           "steps": rows, "report": rr.report_text(d)})

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
        if target.exists():   # M2: the old text is kept before an overwrite
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            (d / f"SOURCE.md.bak-{stamp}").write_bytes(target.read_bytes())
        target.write_bytes(data)
        self._hook("record_story_saved", d, text, overwrite)
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
        project = self._project_update(changes)
        warning = ""
        if project.get("story_slug") and project.get("pack") and not (self.cfg.studio / "stories" / project["story_slug"] / project["pack"]).is_dir():
            warning = "the pack folder does not exist yet (fine for a new analysis)"
        return {"ok": True, "project": project, "scope": {"story": project.get("story_slug"), "pack": project.get("pack")}, "warning": warning}

    def pack(self, rel, check=False) -> dict:
        rel = PACK_REL(self.cfg, rel)
        if not self.cfg.studio.joinpath(*rel.split("/")).is_dir():
            raise ApiError(404, "no such pack")
        return read_pack(self.cfg, rel, check)

    # -- commands: preview, run, jobs
    def preview(self, body) -> dict:
        spec = command_spec(body.get("command"))
        args = normalize(self.cfg, spec, body.get("args") or {})
        if spec.needs == "claude" and not self.cfg.allow_claude:
            raise ApiError(403, CLAUDE_OFF)
        if spec.needs_h3 and not h3_built(self.cfg):
            raise ApiError(409, H3_MISSING)
        argv = spec.build(self.cfg, args)
        check_argv(argv, spec.allow)
        route = write_pack_route(args, "opus" if spec.id == "write_pack_claude" else None) \
            if spec.id in ("write_pack", "write_pack_claude") else None
        est = balance = None
        confirm = spec.confirm or None
        if spec.spend:
            est = estimate_units(args["gpu"], batch_clips(self.cfg, args["batch"]))
            balance = self._spend_gate(est) if self.cfg.spend else "not checked (spend is OFF)"
            confirm = f"EXECUTE {est:.1f}"
        token = secrets.token_urlsafe(18)
        rec = {"command": spec.id, "argv": argv, "digest": digest(argv), "spend": spec.spend, "est": est, "confirm": confirm,
               "needs": spec.needs, "post": spec.post, "session": args.get("session"), "created": self.cfg.clock(), "used": False,
               "gpu": args.get("gpu"), "batch": args.get("batch"), "story": args.get("story") or args.get("slug")}
        with self.lock:
            self.tokens[token] = rec
        self._audit("preview", command=spec.id, argv=argv, spend=spec.spend, estimate=est)
        return {"argv": argv, "risk": spec.risk, "estimate": est, "balance": balance, "token": token, "expires_s": TOKEN_TTL,
                "needs_confirm": bool(confirm), "confirm_text": confirm, "spend_allowed": self.cfg.spend, "route": route}

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
        if rec.get("needs") == "claude" and not self.cfg.allow_claude:
            raise ApiError(403, CLAUDE_OFF)
        if rec["confirm"] and body.get("confirm") != rec["confirm"]:
            raise bad(f"type exactly: {rec['confirm']}")
        with self.lock:
            if self._active():
                raise ApiError(409, "another job is running: wait for it or stop it")
        if rec["spend"]:
            if estimate_units(rec["gpu"], batch_clips(self.cfg, rec["batch"])) != rec["est"]:
                raise ApiError(403, "the batch changed since the preview: preview again")
            self._spend_gate(rec["est"])
        with self.lock:
            if rec["used"]:
                raise ApiError(403, "this preview was already used: preview again")
            if self._active():   # re-check: another run may have started while the spend gate was working (Dots review 2026-11-06)
                raise ApiError(409, "another job is running: wait for it or stop it")
            if rec["spend"] and not rec.get("recorded"):   # owner 2026-11-07: no spend without a ledger row, so the row is written first
                try:
                    _ops_checks().record_spend(self.cfg.ledger, units=rec["est"], session=rec["session"], story=rec.get("story") or "",
                                               reason=rec["command"])
                except Exception as exc:
                    raise ApiError(500, f"spend ledger write failed ({type(exc).__name__}: {exc}): the job was NOT started")
                rec["recorded"] = True   # a retry after a Popen failure must not record the same spend twice
            job = self._start(rec["command"], rec["argv"], rec["spend"], rec["session"], rec["post"])   # Popen failure raises here: preview stays usable
            rec["used"] = True   # the job exists, so the preview is single-use from now on
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
        if job.command == "yt_transcript":
            return redact_obj(yt_result(job.rc, text))
        if job.command == "review_shot":
            return {"verdict": REVIEW_VERDICT.get(job.rc, "NO RESULT"), "exit": job.rc}
        return redact_obj({"lines": text.splitlines()[-50:]})

    def job_stop(self, jid) -> dict:
        job = self._job(jid)
        with self.lock:
            live = job.state == "running" and job.proc is not None and job.proc.poll() is None
            if live:
                job.state = "stopped"
        if live:
            _kill_tree(job.proc)   # M3: the whole tree (colab CLI, ffmpeg, Whisper children too)
            job.warning = spend_warning(job.session) if job.spend else ""
        if job.spend and job.verified is not True and not live:
            self._verify_stop(job)   # a finished or lost $ job is checked before any new spend
        self._persist(job)
        self._audit("stop", command=job.command, job=job.id, state=job.state)
        return {"state": job.state, "warning": job.warning if live else "the job had already finished"}

    # -- U1 additions: version, ops, story state and settings, links, voices, validator, render, author
    def version(self) -> dict:
        now_mtime = os.path.getmtime(os.path.abspath(__file__))
        stale = now_mtime > SERVER_MTIME0 + 1
        return {"pid": os.getpid(), "started": STARTED, "server_mtime_at_start": SERVER_MTIME0, "server_mtime_now": now_mtime,
                "stale": stale, "build": _ops_checks().code_fingerprint(self.cfg.studio)}

    def ops(self, q=None) -> dict:
        ok = _ops_checks()
        disks = {name: ok.disk_free(path) for name, path in zip(("C", "D"), self.cfg.disk_paths)}
        ledger = ok.colab_spend_total(self.cfg.ledger)
        # B9: the Colab session list is read only when asked (?colab=1, the "Check Colab sessions" button), never on the 30 s poll
        listed = self._cli_text(["sessions"]) if (q or {}).get("colab") == "1" else None
        return {"disk": disks, "server": {**self.version(), "build": ok.code_fingerprint(self.cfg.studio)},
                "colab": {"ledger_total_units": ledger["total"], "ledger_today": ledger["today"], "cap_units": CAP_UNITS,
                          "total_cap_units": self.cfg.total_cap, "runs": jsonl(self.cfg.ledger)[-10:],
                          "sessions_checked": listed is not None,
                          "sessions_listed": [r["name"] for r in parse_sessions(listed)] if listed is not None else None}}

    def story_state(self, slug) -> dict:
        slug = SLUG(self.cfg, slug)
        return _story_state_module().summarize(self.cfg.studio, slug)

    def _story_state_safe(self, slug) -> dict:
        try:
            return _story_state_module().summarize(self.cfg.studio, slug)
        except Exception as e:   # one broken story shows a warning, never a crash of the list
            return {"error": f"{type(e).__name__}: {str(e)[:120]}"}

    def _story_dir(self, slug) -> Path:
        d = self.cfg.studio / "stories" / SLUG(self.cfg, slug)
        if not d.is_dir():
            raise ApiError(404, "no such story")
        return d

    def set_languages(self, slug, body) -> dict:
        d = self._story_dir(slug)
        raw = body.get("languages")
        if raw == "all":
            langs = list(LANGS)
        elif isinstance(raw, list) and raw and all(isinstance(x, str) for x in raw):
            langs = raw
        else:
            raise bad("languages: a list of en, hi, mr (at least one, no repeats) or 'all'")
        if len(set(langs)) != len(langs) or any(x not in LANGS for x in langs):
            raise bad("languages: en, hi, mr only, no repeats")
        pl = _pipeline()
        with self.lock:
            pl.update_story_json(self.cfg.studio, d.name, {"output_languages": langs, "output_language": langs[0]})
        return {"output_languages": langs}

    def set_voices(self, slug, body) -> dict:
        d = self._story_dir(slug)
        pl = _pipeline()
        ve = pl._h3("voice_engine")
        raw = body.get("voice_engine")
        if not isinstance(raw, dict):
            raise bad("voice_engine must be an object: {\"en\": \"elevenlabs\"|\"h3\", \"hi\": \"elevenlabs\", \"mr\": \"elevenlabs\"}")
        langs = pl.output_languages(self.cfg.studio, d.name) or list(LANGS)
        errs, _warns = ve.voice_engine_problems(raw, langs)
        if errs:
            raise bad("; ".join(f"{c} {m}" for c, m in errs))
        resolved = ve.resolve_engines(langs, raw)
        with self.lock:
            pl.update_story_json(self.cfg.studio, d.name, {"voice_engine": resolved})
        rr = _registry()
        if rr is not None:
            self._hook("append_event", d, rr.run_id("voices"), "story_saved", None, "ok", voice_engine=resolved)
        return {"voice_engine": resolved, "warnings": [f"{c} {m}" for c, m in _warns]}

    def set_bgm(self, slug, body) -> dict:
        d = self._story_dir(slug)
        pl = _pipeline()
        enabled = _bool(self.cfg, body.get("enabled", False))
        if not enabled:
            bgm = {"enabled": False, "manifest": None}
        else:
            raw = body.get("manifest")
            path = safe_path(self.cfg, raw, ("studio",), (".json",), True, "file") if isinstance(raw, str) else None
            if path is None:
                raise bad("background music needs a bgm manifest path (.json inside the studio)")
            rep = pl._h3("gate_d_audio").read_bgm_manifest(path)
            if not rep["ok"]:
                raise bad("; ".join(f"{e['code']} {e['message']}" for e in rep["errors"][:3]))
            bgm = {"enabled": True, "manifest": str(Path(path).relative_to(self.cfg.studio)).replace("\\", "/")}
        with self.lock:
            pl.update_story_json(self.cfg.studio, d.name, {"bgm": bgm})
        return {"bgm": bgm, "label": pl._bgm_label({"bgm": bgm})["label"]}

    def _pack_dir(self, pack_path) -> tuple:
        rel = PACK_PATH(self.cfg, pack_path)
        d = self.cfg.studio.joinpath(*rel.split("/"))
        if not d.is_dir():
            raise ApiError(404, "no such pack")
        return rel, d, rel.split("/")[1], d.name

    def pack_voices_get(self, pack_path) -> dict:
        rel, d, slug, _name = self._pack_dir(pack_path)
        pl = _pipeline()
        return {"pack": rel, "characters": pl.voice_names(d), "voices": pl.read_voice_map(d),
                "languages": pl.output_languages(self.cfg.studio, slug) or list(LANGS)}

    def pack_voices_set(self, pack_path, body) -> dict:
        rel, d, slug, _name = self._pack_dir(pack_path)
        pl = _pipeline()
        voices = body.get("voices")
        if not isinstance(voices, dict):
            raise bad("voices must be an object: {character_id or NARRATOR: {en, hi, mr}}")
        langs = pl.output_languages(self.cfg.studio, slug) or list(LANGS)
        problems = pl.write_voice_map(d, voices, langs)
        if problems:
            raise bad("; ".join(problems[:5]))
        return self.pack_voices_get(rel)

    def pack_validate_get(self, pack_path) -> dict:
        rel, d, slug, name = self._pack_dir(pack_path)
        doc = _pipeline().load_validation(self.cfg.runs, slug, name)
        if doc is None:
            raise ApiError(404, "no validator report for this pack yet: run the validator")
        return doc

    def pack_validate_run(self, pack_path, body) -> dict:
        rel, d, slug, name = self._pack_dir(pack_path)
        pl = _pipeline()
        legacy = body.get("legacy")
        rep = pl.run_validator(self.cfg.studio, slug, name, None if legacy is None else _bool(self.cfg, legacy))
        self._audit("validate", pack=rel, ok=rep["ok"], errors=len(rep["errors"]))
        return pl.save_validation(self.cfg.runs, rep)

    def render_status(self, story, pack) -> dict:
        slug, name = SLUG(self.cfg, story), NAME(self.cfg, pack)
        if not (self.cfg.studio / "stories" / slug / name).is_dir():
            raise ApiError(404, "no such pack")
        return _pipeline().render_status(self.cfg.studio, slug, name)

    def render_choice(self, body) -> dict:
        slug, name = SLUG(self.cfg, body.get("story")), NAME(self.cfg, body.get("pack"))
        shot = SHOT(self.cfg, body.get("shot"))
        note = _note(self.cfg, body.get("note", "")) if body.get("note") else ""
        if not (self.cfg.studio / "stories" / slug / name).is_dir():
            raise ApiError(404, "no such pack")
        try:
            rec = _pipeline().record_human_choice(self.cfg.studio, slug, name, shot, str(body.get("choice", "")), note)
        except ValueError as e:
            raise bad(str(e))
        return {"ok": True, "recorded": rec}

    def author_status(self, pack_path) -> dict:
        rel, d, _slug, _name = self._pack_dir(pack_path)
        try:
            rep = _h3_author_module().author_pack(str(d), dry_run=True)
        except ValueError as e:
            raise bad(str(e))
        shots = [{"shot_id": s.get("shot_id"), "status": s.get("status"), "missing": s.get("missing", []),
                  "prompt_chars": s.get("prompt_chars", 0), "problems": s.get("problems", []),
                  "cache": "fresh" if s.get("status") == "fresh" else ("stale or missing" if s.get("missing") else "not needed")}
                 for s in rep["shots"]]
        # the live run is not wired into the UI in v1: run_allowed stays False until the owner approves a live route
        missing = [{"shot_id": s["shot_id"], "fields": s["missing"]} for s in shots if s["missing"]]   # the panel reads derived, missing, cache
        derived = {"count": sum(1 for s in rep["shots"] if s.get("derived"))}
        cache = ("fresh" if shots and all(s["status"] == "fresh" for s in shots)
                 else ("stale or missing" if missing else "not needed"))
        return {"pack": rel, "dry_run": True, "shots": shots, "derived": derived, "missing": missing, "cache": cache,
                "problems": rep["problems"], "run_allowed": False,
                "run_note": "live author runs are not wired in the UI yet (owner go and ANIME_STUDIO_ALLOW_FREE_MODEL=1 needed)"}

    def link(self, slug, body) -> dict:
        d = self._story_dir(slug)
        args = {"url": body.get("url"), "story": d.name, "lang": body.get("lang", "auto"), "asr": body.get("asr", "auto"),
                "overwrite": body.get("overwrite", False)}
        return self.preview({"command": "yt_transcript", "args": args})

    def images(self, adhyay, story=LEGACY_STORY) -> dict:
        return read_images(self.cfg, ADHYAY(self.cfg, adhyay), SLUG(self.cfg, story))

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
        slug = SLUG(self.cfg, body.get("story"))
        NAME(self.cfg, body.get("pack"))
        jobs_path = gen_json(self.cfg, body.get("jobs"), "jobs")
        if Path(jobs_path).parent.name != slug:
            raise bad("the jobs file must be in flow/generated/<story>/ of the same story")
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

    def results_roots(self, slug, pack) -> list:
        """Result folders of one story and pack: story_links kind 'results' (pack-specific or story-wide). The legacy
        Kaliya project also keeps its T0 folder and its colab batches."""
        roots = [Path(l["resolved"]) for l in _story_links_module().check(self.cfg.studio, slug)
                 if l.get("kind") == "results" and l.get("exists") and l.get("resolved") and l.get("pack") in (None, pack)]
        if slug == LEGACY_STORY:
            roots.append(self.cfg.studio / "director" / "t0_pack" / "results")
            bdir = self.cfg.studio / "director" / "colab_batches"
            if bdir.is_dir():
                roots += [b / "results" for b in sorted(bdir.iterdir()) if b.is_dir()]
        return roots

    def export(self, reel, story, pack) -> dict:
        n = REEL(self.cfg, reel)
        slug = SLUG(self.cfg, story)
        name = NAME(self.cfg, pack)
        if not (self.cfg.studio / "stories" / slug / name).is_dir():
            raise ApiError(404, "no such pack")
        rel = f"stories/{slug}/{name}"
        ids = [s.get("id") for s in shot_list(self.cfg.studio.joinpath(*rel.split("/")) / "shots.json") if str(s.get("episode")) == str(n)]
        order = {str(sid): i for i, sid in enumerate(ids)}   # text form: unhashable shot ids must not raise
        clips = [c for root in self.results_roots(slug, name) for c in _clips_in(root) if str(c["shot"]) in order]
        clips.sort(key=lambda c: (order[str(c["shot"])], c["take"]))
        reel_dir = self.cfg.studio / "reels" / f"reel_{n:02d}"
        files = sorted(p.name for p in reel_dir.iterdir() if p.is_file()) if reel_dir.is_dir() else []
        return {"reel": n, "pack": rel, "shot_ids": ids, "clips_in_order": clips, "assembly": "not built",
                "assembly_note": "not built (gap G12): no assembly command in v1", "reel_files": files}

    def file_response(self, raw) -> Raw:
        real = Path(safe_path(self.cfg, raw, ("studio", "flow"), FILE_EXTS, True, "file"))
        if real.is_relative_to(Path(os.path.realpath(self.cfg.runs))):
            raise ApiError(403, "the ui/runs folder is not served: use the job log or result endpoints")
        if real.stat().st_size > MAX_FILE:
            raise ApiError(413, "file is over 60 MB")
        ctype = MIME.get(real.suffix.lower(), "application/octet-stream")
        if real.suffix.lower() in TEXT_EXTS:
            return Raw(ctype, redact(real.read_text(encoding="utf-8", errors="replace")).encode("utf-8"))
        return Raw(ctype, real.read_bytes())


def _story_state_module():
    d = str(STUDIO / "director")
    if d not in sys.path:
        sys.path.append(d)
    import story_state
    return story_state


def _h3_author_module():
    root = str(STUDIO)
    if root not in sys.path:
        sys.path.insert(0, root)
    from h3 import h3_author
    return h3_author


def _story_links_module():
    d = str(STUDIO / "director")
    if d not in sys.path:
        sys.path.append(d)
    import story_links
    return story_links


def _ops_checks():
    """director/ops_checks.py (disk, Colab ledger, lock); imported lazily."""
    d = str(STUDIO / "director")
    if d not in sys.path:
        sys.path.append(d)
    import ops_checks
    return ops_checks


def _kill_tree(proc) -> None:
    """Windows: taskkill /T takes the children too. Elsewhere: kill the process."""
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=30, shell=False)
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        proc.kill()
    except OSError:
        pass


def yt_result(rc, text) -> dict:
    """yt_transcript exit map: 0 ok, 3 needs_choice (candidates in the text), 2 refused (reason line)."""
    lines = text.splitlines()
    reason = next((x for x in lines if x.startswith(("REFUSED", "NEEDS_CHOICE"))), "")
    written = next((x for x in lines if x.startswith("written ")), "")
    chars = re.search(r"\((\d+) chars of transcript\)", written)
    engine = "whisper" if "SPEECH RECOGNITION" in text else ("captions" if "YouTube captions" in text else None)
    cands = []
    m = re.search(r"candidates are (\[.*?\])", reason)
    if m:
        try:
            cands = [str(c) for c in ast.literal_eval(m.group(1))]
        except (ValueError, SyntaxError):
            cands = []
    status = {0: "ok", 3: "needs_choice", 2: "refused"}.get(rc, "failed")
    file = written[len("written "):].split(" (")[0] if written else None
    return {"status": status, "candidates": cands, "engine": engine, "chars": int(chars.group(1)) if chars else None,
            "file": file, "reason": reason or (text.strip().splitlines()[-1] if text.strip() and status == "failed" else ""),
            "overwrite_offer": status == "refused" and "exists" in reason}


def fixed_file(cfg, parts, ctype) -> Raw:
    """A file at a fixed place under the studio folder. The caller passes literal parts, never request text. 404 when missing."""
    p = cfg.studio.joinpath(*parts)
    if not p.is_file():
        raise ApiError(404, "file is missing")
    return Raw(ctype, p.read_bytes())


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


def pipeline_get(api, what, q):
    """GET /api/pipeline and /api/pipeline/summary, optional ?story=&pack= (default: the project pointer)."""
    pl = _pipeline()
    story, pack = q.get("story") or None, q.get("pack") or None
    if story is not None:
        SLUG(api.cfg, story)
    if pack is not None:
        NAME(api.cfg, pack)
    if what == "summary":
        return pl.summary(api.cfg.studio, api.cfg.runs, story, pack)
    state = pl.pipeline_state(api.cfg.studio, api.cfg.runs, None, story, pack)
    state["code_fingerprint"] = _ops_checks().code_fingerprint(api.cfg.studio)   # ops health check compares it with disk
    return state


def pipeline_gate(api, body):
    """POST /api/pipeline/gate {story, pack, gate, decision, note, confirm?}: the only write is runs/approvals.jsonl.
    The story and pack must be the project pointer (409 otherwise). An out-of-date server approves nothing (B1)."""
    if api.version()["stale"]:
        raise ApiError(409, "the studio server is out of date: restart it before you approve or reject")
    pl = _pipeline()
    try:
        gate = pl.apply_gate(api.cfg.studio, api.cfg.runs, str(body.get("gate", "")), str(body.get("decision", "")),
                             str(body.get("note", "")), body.get("confirm"), who="owner",
                             story=body.get("story"), pack=body.get("pack"))
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
        m = re.fullmatch(r"/i18n/(en|mr)\.json", path)   # the UI string tables (ui/static/i18n); two fixed names only
        if m:
            return fixed_file(api.cfg, ("ui", "static", "i18n", m.group(1) + ".json"), JSON_CT)
        if path == "/fonts/NotoSansDevanagari-Variable.ttf":   # the bundled Devanagari font (offline)
            return fixed_file(api.cfg, ("styles", "fonts", "NotoSansDevanagari-Variable.ttf"), "font/ttf")
        if path in ("/api/pipeline", "/api/pipeline/summary"):
            return pipeline_get(api, path.rsplit("/", 1)[-1], q)
        if path == "/api/version":
            return api.version()
        if path == "/api/ops":
            return api.ops(q)
        if path == "/api/writers":
            return api.writers()
        m = re.fullmatch(r"/api/story/([a-z0-9_]{1,40})/state", path)
        if m:
            return api.story_state(m.group(1))
        if path == "/api/pack/voices":
            return api.pack_voices_get(q.get("pack", ""))
        if path == "/api/pack/validate":
            return api.pack_validate_get(q.get("pack", ""))
        if path == "/api/render/status":
            return api.render_status(q.get("story", ""), q.get("pack", ""))
        if path == "/api/author/status":
            return api.author_status(q.get("pack", ""))
        if path == "/api/status":
            return api.status()
        if path == "/api/h3":
            return api.h3()
        if path == "/api/story":
            return api.stories()
        m = re.fullmatch(r"/api/story/([a-z0-9_]{1,40})", path)
        if m:
            return api.story_get(m.group(1))
        if path == "/api/registry":
            return api.registry_list()
        m = re.fullmatch(r"/api/registry/([^/]{1,80})", path)
        if m:
            return api.registry_get(m.group(1))
        if path == "/api/pack":
            return api.pack(q.get("pack", ""), q.get("check") == "1")
        if path == "/api/jobs":
            return api.jobs_list()
        m = re.fullmatch(r"/api/jobs/([0-9A-Za-z_-]{1,64})/(log|result)", path)
        if m:
            return api.job_log(m.group(1), q) if m.group(2) == "log" else api.job_result(m.group(1))
        if path == "/api/images":
            return api.images(q.get("adhyay", "1"), q.get("story", LEGACY_STORY))
        if path == "/api/review":
            return api.review(q.get("shot", ""), q.get("cand", ""), q.get("adhyay", "1"))
        if path == "/api/video":
            return api.video()
        if path == "/api/colab":
            return api.colab()
        if path == "/api/export":
            return api.export(q.get("reel", ""), q.get("story", ""), q.get("pack", ""))
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
        m = re.fullmatch(r"/api/story/([a-z0-9_]{1,40})/(languages|voices|bgm|link)", path)
        if m:
            slug, what = m.group(1), m.group(2)
            return {"languages": api.set_languages, "voices": api.set_voices, "bgm": api.set_bgm, "link": api.link}[what](slug, body)
        if path == "/api/pack/voices":
            return api.pack_voices_set(q.get("pack", "") or (body or {}).get("pack", ""), body)
        if path == "/api/pack/validate":
            return api.pack_validate_run(q.get("pack", "") or (body or {}).get("pack", ""), body)
        if path == "/api/render/choice":
            return api.render_choice(body)
        if path == "/api/author/preview":
            return api.author_status(body.get("pack", ""))
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
    ap.add_argument("--allow-claude", action="store_true",
                    help="owner only: the Claude writer becomes possible; each run still needs a preview and the typed word CLAUDE")
    ap.add_argument("--root-override", action="append", default=[], metavar="NAME=PATH",
                    help="test hooks: studio, flow, downloads, python, colab")
    a = ap.parse_args(argv)
    cfg = Config(spend=a.allow_spend, allow_claude=a.allow_claude)
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
    try:
        srv = make_server(cfg, a.port)
    except OSError as e:
        print(f"Anime Studio UI could not start on 127.0.0.1:{a.port} ({e}). Another copy may be running: stop it, then start again.", file=sys.stderr)
        return 1
    print(f"Anime Studio UI: http://127.0.0.1:{srv.server_address[1]}  spend {'ON' if cfg.spend else 'OFF'}  claude {'ON' if cfg.allow_claude else 'OFF'}",
          flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
