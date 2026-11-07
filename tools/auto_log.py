"""PostToolUse hook: append one line to PROJECT_LOG.md after every file edit and every test/commit/push/download command.

Reads the hook JSON from stdin. Append-only, never raises, never logs file contents, redacts anything that looks like a key.
Line format (blot.md): `MM-DD HH:MM | auto | EDIT|CMD | <what> | hook`.
Set AUTO_LOG_FILE to write somewhere else (tests).
"""
import json
import os
import re
import sys
import time
from pathlib import Path

LOG = Path(os.environ.get("AUTO_LOG_FILE") or Path(__file__).resolve().parent.parent / "PROJECT_LOG.md")
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
LOGGED_CMD = re.compile(r"\bgit\s+(commit|push|merge|tag)\b|\bpytest\b|\b(curl|wget)\b|\bpip3?\s+install\b")
SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{8,}|nvapi-\S+|hf_[A-Za-z0-9]{8,}|ghp_\S+|AIza\S+|Bearer\s+\S+|"
                    r"(?i:key|token|secret|password)\s*[=:]\s*\S+)")
SKIP_PATH = ("/scratchpad/", "/Temp/claude/", "PROJECT_LOG.md", "/__pycache__/")


def line_for(payload):
    tool, inp = payload.get("tool_name"), payload.get("tool_input") or {}
    if tool in EDIT_TOOLS:
        path = str(inp.get("file_path") or inp.get("notebook_path") or "").replace("\\", "/")
        if not path or any(s in path for s in SKIP_PATH):
            return None
        return ("EDIT", path.replace("D:/aai work/", ""))
    if tool == "Bash":
        cmd = str(inp.get("command") or "")
        if not LOGGED_CMD.search(cmd):
            return None
        first = SECRET.sub("<redacted>", cmd.strip().splitlines()[0])[:110]
        return ("CMD", first)
    return None


def main():
    try:
        got = line_for(json.load(sys.stdin))
        if not got:
            return
        text = f"{got[0]} | {got[1]} | hook"
        last = LOG.read_text(encoding="utf-8").rstrip("\n").rsplit("\n", 1)[-1] if LOG.exists() else ""
        if last.endswith(f"| auto | {text}"):   # same step twice in a row: one line is enough
            return
        with LOG.open("a", encoding="utf-8", newline="\n") as f:
            f.write(f"{time.strftime('%m-%d %H:%M')} | auto | {text}\n")
    except Exception:   # a logging hook must never break the tool call
        pass


if __name__ == "__main__":
    main()
