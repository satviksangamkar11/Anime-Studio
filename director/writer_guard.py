import json
import math
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from voice_cast import Ledger

LIMIT_ERRORS = {"rate_limit", "authentication_failed", "billing_error", "account_on_hold", "oauth_org_not_allowed"}

LEDGERS = Path("ledgers")


class WriterUnavailable(RuntimeError):
    pass


class WriterLimit(RuntimeError):
    pass


def cli_ready(which=shutil.which, run=subprocess.run):
    if which("claude") is None:
        raise WriterUnavailable("claude is not on PATH")
    try:
        result = run(["claude", "--version"], capture_output=True, text=True)
    except OSError:
        raise WriterUnavailable("claude is not runnable")
    if result.returncode != 0:
        raise WriterUnavailable("claude --version returned %d" % result.returncode)


def scan_stream(stdout):
    limit_error = None
    is_error = False
    cost_usd = None
    num_turns = None
    usage = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("type") == "system" and obj.get("subtype") == "api_retry":
            error = obj.get("error")
            if error in LIMIT_ERRORS and limit_error is None:
                limit_error = obj
        elif obj.get("type") == "result":
            is_error = obj.get("is_error", False)
            cost_usd = obj.get("total_cost_usd")
            num_turns = obj.get("num_turns")
            usage = obj.get("usage")
    return {
        "limit_error": limit_error,
        "is_error": is_error,
        "cost_usd": cost_usd,
        "num_turns": num_turns,
        "usage": usage,
    }


def _log_row(usage_path, row):
    usage_path.parent.mkdir(parents=True, exist_ok=True)
    with open(usage_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def guarded_call(stage, prompt, call_fn, ledger, est_cents, usage_path):
    cap_raw = os.environ.get("WRITER_CAP_CENTS", "").strip()
    if not cap_raw.isdigit() or int(cap_raw) <= 0:
        raise SystemExit("WRITER_CAP_CENTS must be a positive integer")
    if ledger.cap != int(cap_raw):
        raise SystemExit("ledger cap must equal WRITER_CAP_CENTS")
    if isinstance(est_cents, bool) or not isinstance(est_cents, int) or est_cents <= 0:
        raise SystemExit("est_cents must be a positive int")
    jid = "%s:%s" % (stage, uuid.uuid4().hex[:8])
    ledger.reserve(jid, est_cents)
    try:
        stdout = call_fn(prompt, max_budget_usd=est_cents / 100)
    except BaseException:
        ledger.settle(jid, est_cents, confirmed=False)
        row = {
            "t": time.time(),
            "stage": stage,
            "num_turns": None,
            "usage": None,
            "cost_usd": None,
            "is_error": True,
            "limit_error": None,
        }
        _log_row(usage_path, row)
        raise
    info = scan_stream(stdout)
    if info["num_turns"] is None and info["cost_usd"] is None and info["limit_error"] is None:
        ledger.settle(jid, est_cents, confirmed=False)
        row = {
            "t": time.time(),
            "stage": stage,
            "num_turns": None,
            "usage": None,
            "cost_usd": None,
            "is_error": True,
            "limit_error": info["limit_error"],
        }
        _log_row(usage_path, row)
        raise RuntimeError("writer stream had no result")
    if info["cost_usd"] is not None:
        if isinstance(info["cost_usd"], bool) or not isinstance(info["cost_usd"], (int, float)):
            ledger.settle(jid, est_cents, confirmed=False)
            row = {
                "t": time.time(),
                "stage": stage,
                "num_turns": info["num_turns"],
                "usage": info["usage"],
                "cost_usd": info["cost_usd"],
                "is_error": True,
                "limit_error": info["limit_error"],
            }
            _log_row(usage_path, row)
            raise RuntimeError("bad cost_usd")
        if not math.isfinite(info["cost_usd"]) or info["cost_usd"] < 0:
            ledger.settle(jid, est_cents, confirmed=False)
            row = {
                "t": time.time(),
                "stage": stage,
                "num_turns": info["num_turns"],
                "usage": info["usage"],
                "cost_usd": info["cost_usd"],
                "is_error": True,
                "limit_error": info["limit_error"],
            }
            _log_row(usage_path, row)
            raise RuntimeError("bad cost_usd")
    settled_cents = math.ceil(info["cost_usd"] * 100) if info["cost_usd"] is not None else est_cents
    ledger.settle(jid, settled_cents, confirmed=False)
    row = {
        "t": time.time(),
        "stage": stage,
        "num_turns": info["num_turns"],
        "usage": info["usage"],
        "cost_usd": info["cost_usd"],
        "is_error": info["is_error"],
        "limit_error": info["limit_error"],
    }
    _log_row(usage_path, row)
    if info["limit_error"] is not None:
        raise WriterLimit("writer limit error: %r" % info["limit_error"])
    if info["is_error"]:
        raise RuntimeError("writer returned an error result")
    return stdout


def validate_pack(rows, blocking_dir):
    problems = []
    seen_ids = set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            problems.append("row #%d is not an object" % i)
            continue
        rid = row.get("id")
        if not isinstance(rid, str):
            problems.append("row #%d missing id" % i)
            continue
        if rid in seen_ids:
            problems.append("%s: duplicate id" % rid)
            continue
        seen_ids.add(rid)
        directives = row.get("per_second_directives")
        if not isinstance(directives, list):
            problems.append("%s: per_second_directives must be a list" % rid)
            continue
        blocking_path = os.path.join(blocking_dir, rid + ".json")
        if not os.path.exists(blocking_path):
            problems.append("%s: missing blocking file" % rid)
            continue
        try:
            import blocking
            sheet = blocking.load_sheet(blocking_path)
            problems.extend(blocking.validate(sheet))
        except Exception as exc:
            problems.append("%s: blocking load error: %s" % (rid, exc))
        prev_t1 = None
        for directive in directives:
            if not isinstance(directive, dict):
                problems.append("%s: directive must be an object" % rid)
                continue
            t0 = directive.get("t0")
            t1 = directive.get("t1")
            if not isinstance(t0, (int, float)) or isinstance(t0, bool):
                problems.append("%s: directive t0 must be numeric" % rid)
                continue
            if not isinstance(t1, (int, float)) or isinstance(t1, bool):
                problems.append("%s: directive t1 must be numeric" % rid)
                continue
            if not (t0 < t1):
                problems.append("%s: directive t0 < t1 required" % rid)
            if prev_t1 is None:
                if abs(t0 - 0.0) > 0.05:
                    problems.append("%s: directives must start at 0" % rid)
            else:
                if abs(t0 - prev_t1) > 0.05:
                    problems.append("%s: directive gap %s -> %s" % (rid, prev_t1, t0))
            prev_t1 = t1
            refs = directive.get("source_refs")
            if not isinstance(refs, list) or not all(isinstance(r, str) for r in refs):
                problems.append("%s: directive source_refs must be [str]" % rid)
    return problems
