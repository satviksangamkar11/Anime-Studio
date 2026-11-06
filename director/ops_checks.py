"""Checks before a render or a big download (stdlib only): free disk space, UI server freshness, Colab spend ledger.

  python director/ops_checks.py [--disk PATH] [--health URL] [--spend] [--ledger PATH]

Exit 0 = fine; 1 = a blocker (disk under 2 GB or on C:, UI server stale or unreachable); 2 = nothing to check.
Disk: under 2 GB free blocks, under 5 GB warns; C: (the system drive, nearly full) never takes a big file.
Colab spend: at most 15 units per run (ui/server.py CAP_UNITS); a day and a week total come from the append-only ledger.
DAY_CAP_UNITS / WEEK_CAP_UNITS are not set by the owner yet (None = the totals are reported, not capped).
The ledger (ui/runs/colab_spend.jsonl, git-ignored) gets one line per Colab start through record_spend()."""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import math
import os
import shutil
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "ui" / "runs" / "colab_spend.jsonl"
FINGERPRINT_FILES = ("ui/server.py", "ui/static/pipeline.js")
BLOCK_FREE_GB, WARN_FREE_GB = 2.0, 5.0
RUN_CAP_UNITS = 15.0
DAY_CAP_UNITS = None          # owner to set; None = report only
WEEK_CAP_UNITS = None         # owner to set; None = report only
LOCK_STALE_SECONDS = 60
GB = 1024 ** 3


def disk_free(path, usage=shutil.disk_usage) -> dict:
    """Free space on the drive of `path` (the nearest existing folder is asked). status: ok | warn | block."""
    p = Path(os.path.abspath(path))
    probe = p
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    free_gb = round(usage(str(probe)).free / GB, 2)
    drive = os.path.splitdrive(str(p))[0].upper()
    if drive == "C:":
        status, reason = "block", "C: is the system drive (nearly full): big files go on D:"
    elif free_gb < BLOCK_FREE_GB:
        status, reason = "block", f"under {BLOCK_FREE_GB:g} GB free"
    elif free_gb < WARN_FREE_GB:
        status, reason = "warn", f"under {WARN_FREE_GB:g} GB free"
    else:
        status, reason = "ok", ""
    return {"path": str(p), "drive": drive, "free_gb": free_gb, "status": status, "reason": reason}


def code_fingerprint(root: Path = ROOT) -> str:
    h = hashlib.sha256()
    for rel in FINGERPRINT_FILES:
        f = root / rel
        h.update(rel.encode() + b"\0" + (f.read_bytes() if f.is_file() else b"<missing>"))
    return h.hexdigest()[:16]


def _get_json(url: str, timeout: float):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def ui_server_health(url: str, timeout: float = 3.0, fetch=_get_json, local: str | None = None) -> dict:
    """GET /api/pipeline and /api/registry. Status: ok (the server reports the same code fingerprint as the disk),
    'stale or unreachable' (a request failed, or the fingerprints differ: restart the server), or unverified (reachable, but
    the server reports no code_fingerprint, so its code cannot be checked: restart it after code changes)."""
    local = local or code_fingerprint()
    out = {"url": url, "status": "", "local_fingerprint": local, "server_fingerprint": None, "reasons": []}
    base = url.rstrip("/")
    bodies = {}
    for ep in ("/api/pipeline", "/api/registry"):
        try:
            bodies[ep] = fetch(base + ep, timeout)
        except Exception as exc:  # noqa: BLE001 - any failure means we cannot vouch for the server
            out["reasons"].append(f"{ep} unreachable ({type(exc).__name__})")
    if out["reasons"]:
        out["status"] = "stale or unreachable"
        return out
    server_fp = bodies["/api/pipeline"].get("code_fingerprint") if isinstance(bodies["/api/pipeline"], dict) else None
    out["server_fingerprint"] = server_fp
    if server_fp is None:
        out["status"] = "unverified"
        out["reasons"].append("server reports no code_fingerprint: cannot tell if it runs the code on disk; restart it after code changes")
    elif server_fp != local:
        out["status"] = "stale or unreachable"
        out["reasons"].append(f"running code {server_fp} differs from disk {local}: restart the server")
    else:
        out["status"] = "ok"
    return out


def _entries(ledger_path) -> tuple[list[dict], int]:
    recs, bad = [], 0
    p = Path(ledger_path)
    if not p.is_file():
        return recs, bad
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            rec["_t"] = dt.datetime.fromisoformat(rec["time"]).astimezone()
            rec["_u"] = float(rec["units"])
            recs.append(rec)
        except (ValueError, KeyError, TypeError):
            bad += 1
    return recs, bad


def colab_spend_total(ledger_path=DEFAULT_LEDGER, now: dt.datetime | None = None) -> dict:
    now = (now or dt.datetime.now().astimezone()).astimezone()
    recs, bad = _entries(ledger_path)
    total = today = week = 0.0
    for r in recs:
        total += r["_u"]
        if r["_t"].date() == now.date():
            today += r["_u"]
        if r["_t"].isocalendar()[:2] == now.isocalendar()[:2]:
            week += r["_u"]
    return {"total": round(total, 3), "today": round(today, 3), "this_week": round(week, 3), "runs": len(recs), "bad_lines": bad}


@contextlib.contextmanager
def _lock(path: Path, sleep, tries: int, wait: float):
    """Exclusive lock file. A lock older than LOCK_STALE_SECONDS (a crashed writer) is removed."""
    for _ in range(tries):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > LOCK_STALE_SECONDS:
                    path.unlink()
                    continue
            except FileNotFoundError:
                continue
            sleep(wait)
    else:
        raise TimeoutError(f"ledger is locked by another writer: {path.name}")
    os.close(fd)
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()


def record_spend(ledger_path, *, units, session, story, reason, now: dt.datetime | None = None,
                 sleep=time.sleep, tries: int = 100, wait: float = 0.1) -> dict:
    """Append one line {time, units, session, story, reason}. One O_APPEND write under a lock file; nothing is ever rewritten."""
    u = float(units)
    if not (math.isfinite(u) and u > 0):
        raise ValueError("units must be a positive number")
    if not str(reason or "").strip():
        raise ValueError("reason is required")
    rec = {"time": (now or dt.datetime.now().astimezone()).isoformat(timespec="seconds"), "units": round(u, 3),
           "session": str(session or "")[:80], "story": str(story or "")[:120], "reason": str(reason)[:200]}
    ledger = Path(ledger_path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8")
    with _lock(ledger.with_name(ledger.name + ".lock"), sleep, tries, wait):
        fd = os.open(ledger, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line)
            os.fsync(fd)
        finally:
            os.close(fd)
    return rec


def check_spend(units, ledger_path=DEFAULT_LEDGER, now: dt.datetime | None = None, run_cap=RUN_CAP_UNITS,
                day_cap=DAY_CAP_UNITS, week_cap=WEEK_CAP_UNITS) -> dict:
    totals = colab_spend_total(ledger_path, now)
    blockers = []
    if not (isinstance(units, (int, float)) and math.isfinite(units) and units > 0):
        blockers.append("estimate must be a positive number of units")
    else:
        if units > run_cap:
            blockers.append(f"estimate {units:g} units is above the per-run cap {run_cap:g}")
        if day_cap is not None and totals["today"] + units > day_cap:
            blockers.append(f"today's total {totals['today']:g} + {units:g} is above the day cap {day_cap:g}")
        if week_cap is not None and totals["this_week"] + units > week_cap:
            blockers.append(f"this week's total {totals['this_week']:g} + {units:g} is above the week cap {week_cap:g}")
    return {"ok": not blockers, "blockers": blockers, "totals": totals}


def check_before_render(render_dir, *, estimate_units=None, session=None, ledger_path=DEFAULT_LEDGER,
                        now: dt.datetime | None = None, usage=shutil.disk_usage) -> dict:
    """Disk on the render folder's drive, the Colab spend cap (only when estimate_units is given: Colab runs) and the colab stop
    reminder. ok = no blockers. Warnings do not block."""
    disk = disk_free(render_dir, usage)
    blockers, warnings = [], []
    if disk["status"] == "block":
        blockers.append(f"disk {disk['path']}: {disk['reason']} ({disk['free_gb']} GB free)")
    elif disk["status"] == "warn":
        warnings.append(f"disk {disk['path']}: {disk['reason']} ({disk['free_gb']} GB free)")
    spend = None
    if estimate_units is not None:
        spend = check_spend(estimate_units, ledger_path, now)
        blockers += spend["blockers"]
    reminder = (f"After the Colab run: colab stop -s {session or '<session>'} (always; never use --logtostderr), "
                "then check colab sessions.")
    return {"ok": not blockers, "blockers": blockers, "warnings": warnings, "disk": disk, "spend": spend, "reminder": reminder}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--disk", metavar="PATH", help="free space on PATH's drive")
    ap.add_argument("--health", metavar="URL", help="UI server, e.g. http://127.0.0.1:8765")
    ap.add_argument("--spend", action="store_true", help="Colab units in the ledger")
    ap.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    a = ap.parse_args(argv)
    if not (a.disk or a.health or a.spend):
        ap.print_help()
        return 2
    rc = 0
    if a.disk:
        d = disk_free(a.disk)
        print(f"disk {d['drive'] or '-'} {d['free_gb']} GB free: {d['status'].upper()}" + (f" ({d['reason']})" if d["reason"] else ""))
        if d["status"] == "block":
            rc = 1
    if a.health:
        h = ui_server_health(a.health)
        print(f"ui server {h['url']}: {h['status']}")
        for r in h["reasons"]:
            print(f"  - {r}")
        if h["status"] == "stale or unreachable":
            rc = 1
    if a.spend:
        t = colab_spend_total(a.ledger)
        print(f"colab units: total {t['total']}, today {t['today']}, this week {t['this_week']} "
              f"({t['runs']} run(s), bad ledger lines {t['bad_lines']})")
        print(f"caps: per run {RUN_CAP_UNITS:g}; day {DAY_CAP_UNITS}; week {WEEK_CAP_UNITS} (None = not set)")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
