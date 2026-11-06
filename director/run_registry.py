"""Run registry for the stories (stdlib only): what was run for each story, with which model and path, step by step.

Per story folder stories/<slug>/ it keeps:
  story.json      meta: slug, title, language, source {type, url, fetched_at, saved_at, chars, truncated_note, note},
                  created_at, owner_request_text (short), tags
  RUNS.jsonl      append-only, ONE JSON LINE PER EVENT, never rewritten. A step writes a "started" line when it begins and
                  an "ok" / "failed" / "stopped" line when it ends; the reader keeps the last line of each step.
  RUN_REPORT.md   the readable copy, rendered from the two files above (report(studio, slug) or write_report(story_dir)).

Writers use Recorder (writer steps) and the record_* functions (story save, transcript, gate decision, stop). Those never
raise: an error is printed to stderr and the real work goes on. Run ids look like 20261106-2210-writer-super-vl (a second
run in the same minute gets -2). Pack folders of NEW runs: pack_<writer>_<YYYYMMDD>_v<n>, n the smallest free number;
an existing folder is never reused. Reading (summary, report_text) never writes a file."""
from __future__ import annotations

import contextlib
import datetime as dt
import functools
import hashlib
import json
import os
import re
import secrets
import sys
import time
from pathlib import Path

try:                      # Windows: byte-range lock; elsewhere: flock (both released when the process ends)
    import msvcrt
except ImportError:
    msvcrt = None
try:
    import fcntl
except ImportError:
    fcntl = None

STORY_FILE, RUNS_FILE, REPORT_FILE = "story.json", "RUNS.jsonl", "RUN_REPORT.md"
SCHEMA_VERSION = 1                                   # story.json schema; fields added after v1 are optional when read
OUTPUT_LANGUAGES = ("en", "hi", "mr")
LOCK_TIMEOUT = 10.0                                  # seconds a writer waits for RUNS.jsonl.lock before TimeoutError
KINDS = ("story_saved", "transcript_fetched", "analysis_stage", "analysis_done", "pack_check", "spec_built", "jobs_built",
         "image_review", "render_prepare", "gate_decision", "stopped", "failed")
STATUSES = ("started", "ok", "failed", "stopped")
SOURCE_TYPES = ("paste", "youtube", "file")
GATES, DECISIONS = ("A", "B", "C", "D"), ("approve", "reject")
SUGGESTED_WRITER = "super-vl"            # the writer whose name next_pack suggests (the UI default)
SLUG = re.compile(r"[a-z0-9_]{1,40}")
PACK = re.compile(r"[a-z0-9_-]{1,40}")
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,159}")
STAGE = re.compile(r"[0-9]{1,2}(?:e[0-9]{1,2})?|single")
EVENT_FIELDS = {"started_at", "ended_at", "model", "via", "effort", "pack", "files", "chars", "note", "url", "gate", "decision",
                "source_sha256", "output_languages", "voice_engine"}
VOICE_ENGINES = ("elevenlabs", "h3")                 # voice_engine values per language (owner option A, 2026-11-07)
SECRET_RX = [re.compile(p) for p in (r"ya29\.\S+", r"Bearer\s+\S+", r"nvapi-\S+", r"hf_[A-Za-z0-9]{20,}",
                                     r"sk-[A-Za-z0-9_-]{16,}", r"AIza[0-9A-Za-z_-]{30,}", r"token=\S+")]
TRANSCRIPT_MARK = "## TRANSCRIPT (verbatim)"


def redact(text: str) -> str:
    for rx in SECRET_RX:
        text = rx.sub("[REDACTED]", text)
    return text


def now_iso(when=None) -> str:
    return (when or dt.datetime.now().astimezone()).isoformat(timespec="seconds")


def parse_time(value):
    try:
        return dt.datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _tag(text) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:40] or "x"


def short_model(model) -> str:
    return str(model or "unknown").split("/")[-1].split(":")[0]


def writer_tag(writer=None, via=None, model=None) -> str:
    """'super-vl' for a writer shortcut; otherwise the path and the model's short name, e.g. 'nvidia-nemotron-3-ultra-550b-a55b'."""
    return writer or f"{via or 'unknown'}-{short_model(model)}"


def run_id(tag, when=None, taken=()) -> str:
    base = f"{(when or dt.datetime.now().astimezone()).strftime('%Y%m%d-%H%M')}-{_tag(tag)}"
    rid, n = base, 1
    while rid in taken:
        n += 1
        rid = f"{base}-{n}"
    return rid


def pack_name(writer, day=None, taken=()) -> str:
    """pack_<writer>_<YYYYMMDD>_v<n>: the smallest n whose name is not in `taken` (an existing folder is never reused)."""
    base = f"pack_{_tag(writer)[:16].strip('-')}_{(day or dt.date.today()):%Y%m%d}"
    n = 1
    while f"{base}_v{n}" in taken:
        n += 1
    return f"{base}_v{n}"


def story_folder(story_file):
    """stories/<slug>/ for a file directly inside it (SOURCE.md). None for anything else: nothing is recorded outside stories/."""
    folder = Path(story_file).parent
    return folder if folder.parent.name == "stories" and SLUG.fullmatch(folder.name) else None


def is_pack_folder(path: Path) -> bool:
    if not (path.is_dir() and PACK.fullmatch(path.name)):
        return False
    return any((path / n).is_file() for n in ("shots.json", "PACK.md", "raw_response.json")) or any(path.glob("stage_*_raw*.json"))


def pack_folders(story_dir) -> list:
    story_dir = Path(story_dir)
    return [p.name for p in sorted(story_dir.iterdir()) if is_pack_folder(p)] if story_dir.is_dir() else []


def is_finished(pack_dir: Path) -> bool:
    return (pack_dir / "PACK.md").is_file() and (pack_dir / "shots.json").is_file()


def latest_pack(story_dir):
    """The finished pack (PACK.md and shots.json) with the newest shots.json, or None."""
    story_dir = Path(story_dir)
    finished = [n for n in pack_folders(story_dir) if is_finished(story_dir / n)]
    return max(finished, key=lambda n: (story_dir / n / "shots.json").stat().st_mtime) if finished else None


def pack_summary(pack_dir) -> dict | None:
    shots = read_json(Path(pack_dir) / "shots.json")
    if not isinstance(shots, list):
        return None
    shots = [s for s in shots if isinstance(s, dict)]
    secs = sum(float(s["seconds"]) for s in shots if isinstance(s.get("seconds"), (int, float)) and not isinstance(s.get("seconds"), bool))
    reels = {s.get("episode") for s in shots if s.get("episode") is not None}
    return {"reels": len(reels), "shots": len(shots), "seconds": round(secs, 1)}


def envelope_info(raw_text: str) -> dict:
    """model, via, failed, finish and chars from one saved answer: the write_pack envelope, or the Claude CLI JSON."""
    try:
        data = json.loads(raw_text)
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    usage = data.get("modelUsage") if isinstance(data.get("modelUsage"), dict) else {}
    result = data.get("result")
    return {"model": data.get("model") or (next(iter(usage)) if usage else None),
            "via": data.get("via") or data.get("backend") or ("claude" if usage else None),
            "failed": bool(data.get("is_error")), "finish": data.get("finish_reason") or data.get("subtype"),
            "chars": len(result) if isinstance(result, str) else None}


def envelope_file(path) -> dict:
    try:
        return envelope_info(Path(path).read_text(encoding="utf-8"))
    except OSError:
        return {}


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")   # per process: two writers never share one temp file
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def file_sha256(path) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def source_file_hash(story_dir) -> str | None:
    """sha256 of stories/<slug>/SOURCE.md as it is on disk now (None when the file is missing)."""
    return file_sha256(Path(story_dir) / "SOURCE.md") if story_dir is not None else None


def _lock(f) -> None:
    """One exclusive, non-blocking lock on the open lock file f. Raises OSError while another process or thread holds it."""
    if msvcrt:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(f) -> None:
    if msvcrt:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def _locked(path: Path, timeout: float = LOCK_TIMEOUT):
    """Exclusive lock for appends to `path`, held on the separate file <path>.lock (readers of `path` are never blocked by it).
    ponytail: one lock per story folder; per-run locks only if many writers ever share one story."""
    lock_path = path.with_name(path.name + ".lock")
    with open(lock_path, "a+b") as f:
        deadline = time.monotonic() + timeout
        while True:
            try:
                _lock(f)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"{lock_path.name} still held after {timeout:.0f} s") from None
                time.sleep(0.01)
        try:
            yield
        finally:
            _unlock(f)


# ---------------------------------------------------------------- story meta
def transcript_chars(text: str) -> int:
    body = text.split(TRANSCRIPT_MARK, 1)[1] if TRANSCRIPT_MARK in text else text
    return len(body.strip())


def detect_source(text: str, saved_at=None) -> dict:
    """The source of a SOURCE.md text: a YouTube link in its 'Fetched from' line, else a paste."""
    found = re.search(r"Fetched from (https?://\S+)", text)
    source = {"type": "youtube", "url": found.group(1).rstrip(".,)")} if found else {"type": "paste"}
    source["chars"] = transcript_chars(text)
    source["saved_at"] = saved_at or now_iso()
    source["truncated_note"] = "pasted text ends mid-sentence (per the SOURCE header)" if "ends mid-sentence" in text[:4000] else None
    return source


def title_from_source(text: str, default: str) -> str:
    for line in text.splitlines():
        if line.startswith("# SOURCE:"):
            return line[len("# SOURCE:"):].strip()[:160] or default
    return default


def detect_language(text: str) -> str:
    if len(re.findall("[ऀ-ॿ]", text)) < 20:
        return "en"
    return "mr" if "ळ" in text else "hi"        # the letter (u0933) is Marathi; a Hindi text never uses it


def default_story(story_dir) -> dict:
    story_dir = Path(story_dir)
    return {"slug": story_dir.name, "title": story_dir.name, "language": None, "source": {}, "created_at": None,
            "owner_request_text": "", "tags": [], "schema_version": SCHEMA_VERSION, "source_sha256": None,
            "output_language": None, "rating": None}


def read_story(story_dir) -> dict | None:
    data = read_json(Path(story_dir) / STORY_FILE)
    return data if isinstance(data, dict) else None


def update_story(story_dir, *, title=None, language=None, source=None, owner_request_text=None, tags=None, created_at=None,
                 source_sha256=None, output_language=None, rating=None) -> dict:
    """Creates story.json when it is missing; otherwise changes only the fields given (None = keep).
    output_language is en, hi or mr (ValueError otherwise). rating is free text; '' clears it (the owner sets it, never the code)."""
    story_dir = Path(story_dir)
    if output_language is not None and output_language not in OUTPUT_LANGUAGES:
        raise ValueError(f"output_language must be one of {', '.join(OUTPUT_LANGUAGES)}")
    meta = read_story(story_dir)
    if meta is None:
        meta = dict(default_story(story_dir), created_at=created_at or now_iso())
    if title:
        meta["title"] = title[:160]
    if language:
        meta["language"] = language
    if source:
        meta["source"] = {**(meta.get("source") or {}), **{k: v for k, v in source.items() if v is not None}}
    if owner_request_text is not None:
        meta["owner_request_text"] = owner_request_text[:200]
    if tags:
        meta["tags"] = sorted(set(meta.get("tags") or []) | set(tags))
    if source_sha256 is not None:
        meta["source_sha256"] = source_sha256
    if output_language is not None:
        meta["output_language"] = output_language
    if rating is not None:
        meta["rating"] = rating.strip()[:300] or None
    meta["schema_version"] = SCHEMA_VERSION
    _write_atomic(story_dir / STORY_FILE, json.dumps(meta, ensure_ascii=False, indent=1) + "\n")
    return meta


def upgrade_story_fields(story_dir, write: bool = True) -> bool:
    """Adds the fields a v1 story.json lacks (schema_version, source_sha256 = the SOURCE.md hash now, output_language, rating).
    A value that is already there is never changed. Returns True when something was (or, with write=False, would be) added."""
    story_dir = Path(story_dir)
    meta = read_story(story_dir)
    if meta is None:
        return False
    fill = {"schema_version": SCHEMA_VERSION, "source_sha256": source_file_hash(story_dir), "output_language": None, "rating": None}
    missing = {k: v for k, v in fill.items() if k not in meta}
    if not missing:
        return False
    if write:
        meta.update(missing)
        _write_atomic(story_dir / STORY_FILE, json.dumps(meta, ensure_ascii=False, indent=1) + "\n")
    return True


# ---------------------------------------------------------------- events
def read_events(story_dir) -> list:
    path = Path(story_dir) / RUNS_FILE
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if isinstance(ev, dict):
                out.append(ev)
    return out


def _run_ids(story_dir) -> set:
    return {e.get("run_id") for e in read_events(story_dir)}


def _checked(ev: dict) -> dict:
    if ev["kind"] not in KINDS:
        raise ValueError(f"unknown kind {ev['kind']!r}")
    if ev["status"] not in STATUSES:
        raise ValueError(f"unknown status {ev['status']!r}")
    if not isinstance(ev["run_id"], str) or not RUN_ID.fullmatch(ev["run_id"]):
        raise ValueError("bad run_id")
    if ev.get("stage") is not None and not (isinstance(ev["stage"], str) and STAGE.fullmatch(ev["stage"])):
        raise ValueError(f"bad stage {ev.get('stage')!r}")
    if ev.get("pack") is not None and not (isinstance(ev["pack"], str) and PACK.fullmatch(ev["pack"])):
        raise ValueError("bad pack folder name")
    if ev.get("gate") is not None and ev["gate"] not in GATES:
        raise ValueError("bad gate")
    if ev.get("decision") is not None and ev["decision"] not in DECISIONS:
        raise ValueError("bad decision")
    if ev.get("chars") is not None and (isinstance(ev["chars"], bool) or not isinstance(ev["chars"], int) or ev["chars"] < 0):
        raise ValueError("chars must be a whole number")
    if ev.get("source_sha256") is not None and not (isinstance(ev["source_sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", ev["source_sha256"])):
        raise ValueError("source_sha256 must be a sha256 hex digest")
    langs = ev.get("output_languages")
    if langs is not None:  # optional: old events lack it; a list, a non-repeating subset of en/hi/mr, in priority order
        if not (isinstance(langs, list) and langs and len(set(langs)) == len(langs)
                and all(x in OUTPUT_LANGUAGES for x in langs)):
            raise ValueError(f"output_languages must be a non-empty, non-repeating list from {OUTPUT_LANGUAGES}")
    engines = ev.get("voice_engine")
    if engines is not None:  # optional dict lang -> engine
        if not (isinstance(engines, dict) and all(k in OUTPUT_LANGUAGES for k in engines)
                and all(v in VOICE_ENGINES for v in engines.values())
                and all(v != "h3" or k == "en" for k, v in engines.items())):   # h3 voice is English only
            raise ValueError(f"voice_engine must map {OUTPUT_LANGUAGES} to {VOICE_ENGINES}")
    files = ev.get("files")
    if files is not None:
        if not isinstance(files, list) or len(files) > 50:
            raise ValueError("files must be a list of at most 50 names")
        for f in files:
            if not isinstance(f, str) or not f or f.startswith(("/", "\\")) or ":" in f or ".." in re.split(r"[\\/]", f):
                raise ValueError(f"file must be a relative path inside the story folder: {f!r}")
    for key, limit in (("model", 200), ("via", 60), ("effort", 20), ("url", 300), ("note", 300)):
        if isinstance(ev.get(key), str):
            ev[key] = redact(ev[key])[:limit]
    return ev


def append_event(story_dir, run, kind, stage, status, *, at=None, event_id=None, **fields) -> dict:
    """Appends one line to RUNS.jsonl. Unknown fields and bad values raise ValueError (nothing is written)."""
    unknown = set(fields) - EVENT_FIELDS
    if unknown:
        raise ValueError(f"unknown event field(s): {', '.join(sorted(unknown))}")
    ev = {"event_id": event_id or secrets.token_hex(4), "run_id": run, "at": at or now_iso(), "kind": kind, "stage": stage,
          "status": status}
    ev.update({k: v for k, v in fields.items() if v not in (None, "", [])})
    ev = _checked(ev)
    story_dir = Path(story_dir)
    story_dir.mkdir(parents=True, exist_ok=True)
    line = json.dumps(ev, ensure_ascii=False) + "\n"
    with _locked(story_dir / RUNS_FILE), open(story_dir / RUNS_FILE, "a", encoding="utf-8", newline="\n") as f:
        f.write(line)
    return ev


def steps(events) -> list:
    """One row per step. A 'started' line opens a row and the next line of the same (run, kind, stage) closes it; a retry is
    a new row (a second 'started', or a finished line with nothing open, as the backfill writes them), so no attempt is lost."""
    rows, waiting = [], {}
    for ev in events:
        key = (ev.get("run_id"), ev.get("kind"), ev.get("stage"))
        if ev.get("status") == "started":
            rows.append(dict(ev))
            waiting[key] = len(rows) - 1
        elif key in waiting:
            rows[waiting.pop(key)].update({k: v for k, v in ev.items() if v not in (None, "", [])})
        else:
            rows.append(dict(ev))
    return rows


def run_status(rows) -> str:
    """A writer run is what its analysis_done step says; other runs are judged by all their steps."""
    done = [r for r in rows if r.get("kind") == "analysis_done"]
    statuses = {r.get("status") for r in (done or rows)}
    if "failed" in statuses:
        return "failed"
    if "stopped" in statuses:
        return "stopped"
    return "open" if "started" in statuses else "ok"


def runs(events, rows=None) -> list:
    """One dict per run in order of first appearance: status, steps, models, vias, packs, start, end, last note."""
    rows = steps(events) if rows is None else rows
    order, by_run = [], {}
    for row in rows:
        rid = row.get("run_id")
        if rid not in by_run:
            by_run[rid] = []
            order.append(rid)
        by_run[rid].append(row)
    out = []
    for rid in order:
        rs = by_run[rid]
        starts = [r.get("started_at") or r.get("at") for r in rs if r.get("started_at") or r.get("at")]
        ends = [r.get("ended_at") or r.get("at") for r in rs if r.get("ended_at") or r.get("at")]
        notes = [r["note"] for r in rs if r.get("note")]
        model_rows = [r for r in rs if r.get("kind") == "analysis_stage"] or rs   # the stages say which model; the run row may say "mixed"
        out.append({"run_id": rid, "status": run_status(rs), "steps": len(rs),
                    "models": sorted({r["model"] for r in model_rows if r.get("model")}),
                    "vias": sorted({r["via"] for r in model_rows if r.get("via")}),
                    "packs": sorted({r["pack"] for r in rs if r.get("pack")}),
                    "started_at": min(starts) if starts else None, "ended_at": max(ends) if ends else None,
                    "note": notes[-1] if notes else ""})
    return out


def pack_models(rows) -> dict:
    """pack folder -> model: the run-level row wins over the stage rows; the last run that wrote the pack wins."""
    out = {}
    for r in sorted(rows, key=lambda r: r.get("kind") == "analysis_done"):
        if r.get("pack") and r.get("kind") in ("analysis_stage", "analysis_done") and r.get("model"):
            out[r["pack"]] = r["model"]
    return out


def pack_route(rows, pack) -> tuple:
    """(model, via) of the last run-level row for the pack (or None, None)."""
    last = [r for r in rows if r.get("pack") == pack and r.get("kind") == "analysis_done"]
    if not last:
        return None, None
    return last[-1].get("model"), last[-1].get("via")


def pack_source_status(story_dir, pack) -> str:
    """'same' or 'changed': SOURCE.md against the hash the pack's last run event recorded. 'unknown' when no event of that pack
    has a hash (runs before schema 1, or backfilled ones); 'no SOURCE.md' when there is nothing to compare."""
    now = source_file_hash(story_dir)
    if now is None:
        return "no SOURCE.md"
    recorded = [e["source_sha256"] for e in read_events(story_dir) if e.get("pack") == pack and e.get("source_sha256")]
    if not recorded:
        return "unknown"
    return "same" if recorded[-1] == now else "changed"


# ---------------------------------------------------------------- writing (never raises)
def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        print(f"run registry: {getattr(fn, '__name__', 'write')} skipped ({type(exc).__name__}: {str(exc)[:200]})", file=sys.stderr)
        return None


def best_effort(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return _safe(fn, *args, **kwargs)
    return wrapper


class Step:
    """One step as a context manager: a 'started' line on entry, then ok / failed / stopped on exit.
    Inside the block set .chars, .files or .note; a KeyboardInterrupt or SystemExit is recorded as stopped."""

    def __init__(self, rec, kind, stage, meta, note=""):
        self.rec, self.kind, self.stage, self.meta = rec, kind, stage, meta
        self.chars, self.files, self.note = None, list(meta.get("files") or []), note
        self.started_at = None

    def _fields(self) -> dict:
        return {k: v for k, v in dict(self.meta, files=self.files).items() if v not in (None, "", [])}

    def __enter__(self):
        self.started_at = now_iso()
        self.rec._write(self.kind, self.stage, "started", started_at=self.started_at, **self._fields())
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            status, note = "ok", self.note
        elif issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            status, note = "stopped", "interrupted"
        else:
            status, note = "failed", f"{exc_type.__name__}: {exc}"
        self.rec._write(self.kind, self.stage, status, started_at=self.started_at, ended_at=now_iso(), chars=self.chars,
                        note=note, **self._fields())
        return False


class Recorder:
    """The steps of one writer run in stories/<slug>/RUNS.jsonl. story_dir None (a file outside stories/<slug>/) records nothing."""

    def __init__(self, story_dir, tag, pack=None, via=None, model=None, effort=None):
        self.dir = Path(story_dir) if story_dir is not None else None
        self.pack, self.via, self.model, self.effort = pack, via, model, effort
        self.run = _safe(self._new_run, tag) if self.dir is not None else None

    def _new_run(self, tag) -> str:
        return run_id(f"writer-{tag}", taken=_run_ids(self.dir))

    def _write(self, kind, stage, status, **fields):
        if self.dir is None or self.run is None:
            return None
        return _safe(append_event, self.dir, self.run, kind, stage, status, **fields)

    def step(self, kind, stage=None, *, via=None, model=None, effort=None, files=(), note="") -> Step:
        via = via or self.via
        effort = (effort or self.effort) if via == "claude" else None
        meta = {"pack": self.pack, "via": via, "model": model or self.model, "effort": effort, "files": list(files)}
        if kind == "analysis_done":          # the pack's run event carries the SOURCE.md hash it was made from (drift check)
            meta["source_sha256"] = source_file_hash(self.dir)
        return Step(self, kind, stage, meta, note)


@best_effort
def record_story_saved(story_dir, text: str, overwrite: bool = False) -> str:
    story_dir = Path(story_dir)
    update_story(story_dir, title=title_from_source(text, story_dir.name), language=detect_language(text),
                 source=detect_source(text), source_sha256=source_file_hash(story_dir) or hashlib.sha256(text.encode("utf-8")).hexdigest())
    run = run_id("story-save", taken=_run_ids(story_dir))
    append_event(story_dir, run, "story_saved", None, "ok", files=["SOURCE.md"], chars=transcript_chars(text),
                 note="overwrite" if overwrite else "")
    write_report(story_dir)
    return run


@best_effort
def record_transcript(story_dir, *, url: str, chars: int, lang: str = "hi", title=None, file: str = "SOURCE.md") -> str:
    story_dir = Path(story_dir)
    fetched = now_iso()
    update_story(story_dir, title=title, source_sha256=source_file_hash(story_dir),
                 source={"type": "youtube", "url": url, "fetched_at": fetched, "saved_at": fetched,
                         "chars": chars, "truncated_note": None, "note": f"YouTube captions, language {lang}"})
    run = run_id("transcript", taken=_run_ids(story_dir))
    append_event(story_dir, run, "transcript_fetched", None, "ok", url=url, chars=chars, files=[file], note=f"captions {lang}")
    write_report(story_dir)
    return run


@best_effort
def record_gate_decision(story_dir, gate: str, decision: str, note: str = "", who: str = "owner") -> str:
    story_dir = Path(story_dir)
    run = run_id(f"gate-{gate.lower()}", taken=_run_ids(story_dir))
    append_event(story_dir, run, "gate_decision", None, "ok", gate=gate, decision=decision,
                 note=f"by {who}" + (f": {note}" if note else ""))
    write_report(story_dir)
    return run


@best_effort
def close_open_steps(story_dir, status: str, note: str) -> int:
    """The process that wrote a step has ended: every step still 'started' gets `status` (stopped or failed) and the note."""
    story_dir = Path(story_dir)
    open_rows = [r for r in steps(read_events(story_dir)) if r.get("status") == "started"]
    for r in open_rows:
        append_event(story_dir, r["run_id"], r["kind"], r.get("stage"), status, started_at=r.get("started_at"), ended_at=now_iso(),
                     pack=r.get("pack"), via=r.get("via"), model=r.get("model"), effort=r.get("effort"), files=r.get("files"), note=note)
    for rid in dict.fromkeys(r["run_id"] for r in open_rows):
        append_event(story_dir, rid, "stopped" if status == "stopped" else "failed", None, status, note=note)
    if open_rows:
        write_report(story_dir)
    return len(open_rows)


# ---------------------------------------------------------------- summary and report
def summary(story_dir) -> dict:
    """One row for the story list (read only): title, source, latest pack, models, run count, status."""
    story_dir = Path(story_dir)
    story = read_story(story_dir) or default_story(story_dir)
    events = read_events(story_dir)
    rows = steps(events)
    rs = runs(events, rows)
    taken = {p.name for p in story_dir.iterdir() if p.is_dir()} if story_dir.is_dir() else set()
    last = rs[-1] if rs else None
    return {"slug": story.get("slug") or story_dir.name, "title": story.get("title") or story_dir.name,
            "language": story.get("language"), "source": story.get("source") or {}, "latest_pack": latest_pack(story_dir),
            "packs": pack_folders(story_dir), "pack_models": pack_models(rows), "run_count": len(rs),
            "last_model": next((r["model"] for r in reversed(rows) if r.get("model")), None),
            "status": last["status"] if last else "no runs", "last_run_at": last["ended_at"] if last else None,
            "last_run_id": last["run_id"] if last else None, "next_pack": pack_name(SUGGESTED_WRITER, taken=taken)}


def _cell(value) -> str:
    if value in (None, "", []):
        return "-"
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value)
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")[:300]


def _duration(row) -> str:
    start, end = parse_time(row.get("started_at")), parse_time(row.get("ended_at"))
    try:
        return f"{(end - start).total_seconds():.1f} s" if start and end else "-"
    except TypeError:
        return "-"


def render_markdown(story: dict, events: list, latest: dict | None) -> str:
    rows = steps(events)
    rs = runs(events, rows)
    source = story.get("source") or {}
    lines = [f"# Run report: {story.get('title') or story.get('slug')}", "",
             f"- Story: `{story.get('slug')}`, language {story.get('language') or '-'}, created {story.get('created_at') or '-'}",
             f"- Source: {source.get('type') or '-'}" + (f" {source['url']}" if source.get("url") else "")
             + f", saved {source.get('saved_at') or '-'}, transcript {source.get('chars', '-')} chars",
             f"- Truncated: {source.get('truncated_note') or 'no'}",
             f"- Owner request: {story.get('owner_request_text') or '-'}",
             f"- Events in RUNS.jsonl: {len(events)}" + (f", last at {events[-1].get('at')}" if events else ""), "", "## Latest pack", ""]
    if latest:
        lines.append(f"- {latest['pack']}: {latest.get('reels', '-')} reels, {latest.get('shots', '-')} shots, "
                     f"{latest.get('seconds', '-')} s of shots, model {latest.get('model') or 'unknown'} "
                     f"(via {latest.get('via') or 'unknown'})")
    else:
        lines.append("- No finished pack yet (PACK.md and shots.json are missing).")
    lines += ["", "## Runs", "", "| Run | Status | Started | Models | Vias | Steps | Note |", "|---|---|---|---|---|---|---|"]
    for r in rs:
        lines.append(f"| {_cell(r['run_id'])} | {_cell(r['status'])} | {_cell(r['started_at'])} | {_cell(r['models'])} | "
                     f"{_cell(r['vias'])} | {r['steps']} | {_cell(r['note'])} |")
    lines += ["", "## Steps", "", "| Run | Kind | Stage | Status | Model | Via | Effort | Started | Duration | Files | Chars | Note |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {_cell(r.get('run_id'))} | {_cell(r.get('kind'))} | {_cell(r.get('stage'))} | {_cell(r.get('status'))} | "
                     f"{_cell(r.get('model'))} | {_cell(r.get('via'))} | {_cell(r.get('effort'))} | {_cell(r.get('started_at'))} | "
                     f"{_duration(r)} | {_cell(r.get('files'))} | {_cell(r.get('chars'))} | {_cell(r.get('note'))} |")
    return "\n".join(lines) + "\n"


def report_text(story_dir) -> str:
    """The report as text, rendered from story.json and RUNS.jsonl (read only: nothing is written)."""
    story_dir = Path(story_dir)
    story = read_story(story_dir) or default_story(story_dir)
    events = read_events(story_dir)
    rows = steps(events)
    latest = None
    name = latest_pack(story_dir)
    if name:
        model, via = pack_route(rows, name)
        latest = {"pack": name, **(pack_summary(story_dir / name) or {}), "model": model or pack_models(rows).get(name), "via": via}
    return render_markdown(story, events, latest)


@best_effort
def write_report(story_dir) -> str:
    text = report_text(story_dir)
    _write_atomic(Path(story_dir) / REPORT_FILE, text)
    return text


def report(studio, slug: str) -> str:
    """Renders stories/<slug>/RUN_REPORT.md from its story.json and RUNS.jsonl, writes it and returns the text."""
    if not SLUG.fullmatch(slug):
        raise ValueError("slug must be lower-case letters, digits and _ (1-40)")
    story_dir = Path(studio) / "stories" / slug
    if not story_dir.is_dir():
        raise FileNotFoundError(f"no story folder {story_dir}")
    text = report_text(story_dir)
    _write_atomic(story_dir / REPORT_FILE, text)
    return text
