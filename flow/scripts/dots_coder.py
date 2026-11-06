"""Dots as CODER (owner order 2026-11-06): the free Dots model writes files, the tests are the gate, a reviewer checks afterwards.

  python dots_coder.py --task task.md --context FILE [FILE ...] --allow REL [REL ...] --test "C:/Python314/python.exe -m pytest -q -p no:cacheprovider ui/test_x.py" [--rounds 4] [--root D:/aai work/anime_studio]

The model answers with files in blocks after a line `FINAL:`:
  ```file ui/pipeline.py
  ...content...
  ```
Only paths listed in --allow are written (relative, no .., inside --root); anything else is refused and reported. After writing, --test runs (list argv, no shell); a failing run is sent back with the current files for the next round (up to --rounds). No network except the OpenRouter call of dots_review.post; the key is never printed.
Exit 0 = tests pass, 1 = tests still failing after the last round, 2 = refused usage / no usable answer."""
from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dots_review as dr  # noqa: E402

BLOCK = re.compile(r"^```file[ \t]+(\S+)[ \t]*\n(.*?)\n```[ \t]*$", re.M | re.S)
MAX_CTX_CHARS = 150_000


def parse_files(text: str) -> dict[str, str]:
    """The file blocks of the LAST `FINAL:` section (or of the whole text when the marker is missing)."""
    tail = text.rsplit("FINAL:", 1)[-1]
    return {m.group(1): m.group(2) + "\n" for m in BLOCK.finditer(tail)}


def safe_target(root: Path, rel: str, allow: set[str]) -> Path | None:
    p = Path(rel)
    if rel not in allow or p.is_absolute() or ".." in p.parts:
        return None
    target = (root / p).resolve()
    return target if target.is_relative_to(root.resolve()) else None


def build_prompt(task: str, ctx: list[Path], allow: list[str], root: Path, failure: str | None, focus: str | None = None) -> str:
    parts = [task.strip(),
             "OUTPUT FORMAT (strict): think briefly (under 800 words). Then write a line that says exactly FINAL: and after it ONLY the complete " + ("file " + focus if focus else "files") + ", each as a fenced block whose opening line is ```file <relative path> and closing line is ```. Allowed paths: " + ", ".join([focus] if focus else allow) +
             ". Give each file COMPLETE (never a diff, never '...'). Plain Python 3.14 / vanilla JS / CSS, no dependencies beyond what the task allows. No text after the last block."]
    used = 0
    for f in ctx:
        text = f.read_text(encoding="utf-8", errors="replace")
        used += len(text)
        if used > MAX_CTX_CHARS:
            text = text[:2000] + "\n[truncated: context budget]"
        parts.append(f"=== CONTEXT FILE {f.relative_to(root) if f.is_relative_to(root) else f.name} ===\n{text}")
    for rel in allow:
        cur = root / rel
        if cur.is_file() and (failure or focus):
            parts.append(f"=== YOUR CURRENT VERSION OF {rel} ===\n{cur.read_text(encoding='utf-8', errors='replace')}")
    if failure:
        parts.append("=== THE TEST RUN FAILED ===\n" + failure + "\nFix the files so the tests pass; return ALL allowed files again, complete.")
    return "\n\n".join(parts)


def nemotron_ask(prompt: str, _sched=[]) -> str:
    """Nemotron Ultra through the EXISTING 14-key scheduler (free NVIDIA; 10 calls per key per 60 s). Used with --via nemotron."""
    import re
    if not _sched:
        sys.path.insert(0, "D:/aai work/animation_research_tool")
        import nvidia_scheduler as ns
        _sched.append(ns.NvidiaScheduler(ns.load_env_keys(Path("D:/aai work/animation_research_tool/.env")), model="nvidia/nemotron-3-ultra-550b-a55b", read_timeout=900))
    import time
    last = "?"
    for attempt in range(1, 4):   # the scheduler already retries 429s; a hard ERROR (timeout, gateway cut) gets two more tries here
        res = _sched[0].call([{"type": "text", "text": prompt}], max_tokens=30000)
        if res.get("status") == "OK":
            return re.sub(r"<think>.*?</think>", "", res.get("text") or "", flags=re.S)
        last = str(res.get("status"))
        print(f"nemotron: attempt {attempt}: {last}", file=sys.stderr, flush=True)
        time.sleep(20 * attempt)
    raise RuntimeError("nemotron call failed: " + last)


def run_tests(cmd: str, root: Path, timeout: int = 600) -> tuple[bool, str]:
    r = subprocess.run(shlex.split(cmd, posix=False), cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    out = (r.stdout + "\n" + r.stderr).strip().splitlines()
    return r.returncode == 0, "\n".join(out[-70:])


def code(task: str, ctx: list[Path], allow: list[str], test: str, root: Path, rounds: int = 4, caller=None, tester=run_tests, key: str | None = None, per_file: bool = False) -> dict:
    """Rounds of: ask the model for the files still missing (all of them at first, or after a failing test run), write the valid answers,
    and run the tests only when EVERY allowed file has been written. A cut-off answer therefore never counts as success."""
    allow_set = set(allow)
    ask = caller or (lambda p: dr.review(p, [], key=key, raw=True, max_tokens=32000)["text"])
    failure, log, have = None, [], set()
    for n in range(1, rounds + 1):
        targets = [a for a in allow if a not in have]
        calls = targets if per_file else [None]
        written, refused = [], []
        for focus in calls:
            try:
                res = ask(build_prompt(task, ctx, targets if not per_file else allow, root, failure, focus))
            except RuntimeError as e:   # a failed call costs this round only; the next round asks again
                log.append({"round": n, "written": [], "refused": [], "tests": "model call failed: " + str(e)[:120]})
                continue
            for rel, body in parse_files(res).items():
                t = safe_target(root, rel, allow_set)
                if t is None:
                    refused.append(rel)
                elif focus is None or rel == focus:
                    t.parent.mkdir(parents=True, exist_ok=True)
                    t.write_text(body, encoding="utf-8")
                    written.append(rel)
                    have.add(rel)
        missing = [a for a in allow if a not in have]
        if missing:
            log.append({"round": n, "written": written, "refused": refused, "tests": "incomplete answer, missing: " + ", ".join(missing)})
            failure = "Your last answer did not contain these complete files: " + ", ".join(missing) + ". Return them complete (a cut-off answer is not accepted)."
            continue
        ok, out = tester(test, root)
        log.append({"round": n, "written": written, "refused": refused, "tests": "pass" if ok else "fail"})
        if ok:
            return {"ok": True, "rounds": n, "log": log}
        failure, have = out, set()   # a failing run: every file may need to change, ask for all again
    return {"ok": False, "rounds": rounds, "log": log, "last_failure": failure}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", type=Path, required=True)
    ap.add_argument("--context", nargs="*", type=Path, default=[])
    ap.add_argument("--allow", nargs="+", required=True)
    ap.add_argument("--test", required=True)
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--via", choices=("dots", "nemotron"), default="dots", help="which free model codes (nemotron = the 14-key NVIDIA scheduler)")
    ap.add_argument("--per-file", action="store_true", help="one model call per allowed file (for big files that would not fit one answer)")
    ap.add_argument("--root", type=Path, default=Path("D:/aai work/anime_studio"))
    a = ap.parse_args(argv)
    if not a.task.is_file() or any(not c.is_file() for c in a.context):
        print("REFUSED: task or context file missing")
        return 2
    res = code(a.task.read_text(encoding="utf-8"), [c.resolve() for c in a.context], a.allow, a.test, a.root.resolve(), a.rounds, per_file=a.per_file, caller=nemotron_ask if a.via == "nemotron" else None)
    for entry in res["log"]:
        print(entry)
    if not res["ok"]:
        print("LAST FAILURE:\n" + (res.get("last_failure") or ""))
    return 0 if res["ok"] else (1 if any(e["written"] for e in res["log"]) else 2)


if __name__ == "__main__":
    sys.exit(main())
