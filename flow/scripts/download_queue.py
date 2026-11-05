"""The separate DOWNLOAD step of the Flow image system, ANIME copy (Kaliya Mardan). Copied from granthstudio; only the root, project URL and filing sub-folder differ.

  python flow/scripts/download_queue.py add --adhyay 1 --shot SH_S2_09 --version v02 --edit-id <id> --jobs flow/A_KM_flow_jobs_v2.json [--note ...]
  python flow/scripts/download_queue.py status --adhyay 1            # PENDING items with their Flow edit URL, then FILED ones
  python flow/scripts/download_queue.py collect --adhyay 1           # file every PENDING item whose saved download is in Downloads

Queue: <root>/adhyay_NN/download_queue.jsonl (append-only; the newest line per shot+version wins). Default root: D:/aai work/flow_outputs/anime_kaliya.
An item is FILED when flow_log.jsonl has a line for the same image_id + version (written by file_flow_download.py, which also checks the 2K file).
Whoever downloads (owner, Haiku, or a download tool) opens the edit URL, takes '2K Upscaled', and files with file_flow_download.py."""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

OUT_ROOT = Path("D:/aai work/flow_outputs/anime_kaliya")
PROJECT = "https://flow.google.com/project/6a7ab793-d05f-476d-91a2-aaeb00c234a0"
DOWNLOADS = Path("C:/Users/Satvik/Downloads")
FILER = Path(__file__).resolve().parent / "file_flow_download.py"


def chapter(root: Path, adhyay: int) -> Path:
    return root / f"adhyay_{adhyay:02d}"


def _lines(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.is_file() else []


def add(root: Path, adhyay: int, shot: str, version: str, edit_id: str, jobs: Path | None = None, note: str = "", model: str = "") -> dict:
    if not re.fullmatch(r"v\d{2}b?", version):
        raise ValueError("version must look like v02 or v02b")
    if not re.fullmatch(r"[0-9a-f-]{36}", edit_id):
        raise ValueError("edit id must be the 36-character id from the tile URL .../edit/<id>")
    job = None
    if jobs:
        job = next((j for j in json.loads(Path(jobs).read_text(encoding="utf-8")) if j["shot_id"] == shot), None)
        if job is None:
            raise ValueError(f"{shot} is not in {jobs}")
    item = {"time": datetime.datetime.now().astimezone().isoformat(), "shot_id": shot, "version": version, "flow_title": f"{shot}__{version}",
            "edit_id": edit_id, "url": f"{PROJECT}/edit/{edit_id}", "chips": job["chips"] if job else None,
            "prompt_sha256": job["prompt_sha256"] if job else None, "jobs_file": str(jobs) if jobs else None, "model_shown": model, "note": note}
    d = chapter(root, adhyay)
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "download_queue.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return item


def status(root: Path, adhyay: int) -> dict:
    d = chapter(root, adhyay)
    queue = {}
    for it in _lines(d / "download_queue.jsonl"):
        queue[(it["shot_id"], it["version"])] = it
    filed = {(r.get("image_id"), r.get("version")) for r in _lines(d / "flow_log.jsonl")}
    pending = [it for k, it in queue.items() if k not in filed]
    done = [it for k, it in queue.items() if k in filed]
    return {"pending": pending, "filed": done}


def find_download(downloads: Path, title: str) -> Path | None:
    """The newest saved 2K file whose name starts with the EXACT tile title: '<title>_<hash>_2K.jpg' (Flow's name). Never guesses by time."""
    hits = [p for p in downloads.glob(f"{title}_*2K*.jpg") if re.fullmatch(rf"{re.escape(title)}_[0-9a-zA-Z]+_2K(?: \(\d+\))?\.jpg", p.name)]
    return max(hits, key=lambda p: p.stat().st_mtime) if hits else None


def collect(root: Path, adhyay: int, downloads: Path, run=None) -> list[str]:
    """File every PENDING item whose download is in Downloads (exact-title match) with file_flow_download.py; the filer checks 2K size and duplicates."""
    import os
    import subprocess
    run = run or (lambda cmd, env: subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env))
    out = []
    for it in status(root, adhyay)["pending"]:
        f = find_download(downloads, it["flow_title"])
        if f is None:
            out.append(f"WAITING {it['flow_title']}: no '{it['flow_title']}_*_2K.jpg' in {downloads} yet")
            continue
        env = dict(os.environ, FLOW_OUT_ROOT=str(root), FLOW_ADHYAY=str(adhyay), FLOW_OPERATOR="download pass", FLOW_MAX_AGE_S="604800", PYTHONIOENCODING="utf-8")
        refs = "|".join(it.get("chips") or [])
        cmd = [sys.executable, str(FILER), str(f), it["shot_id"], it["version"], f"edit/{it['edit_id']}", refs, "download pass", "final",
               it.get("jobs_file") or "", it.get("model_shown") or ""]
        p = run(cmd, env)
        out.append(f"FILED {it['flow_title']} <- {f.name}" if p.returncode == 0 else f"REFUSED {it['flow_title']}: {(p.stderr or p.stdout).strip().splitlines()[-1] if (p.stderr or p.stdout).strip() else 'filer failed'}")
    return out


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("add")
    a1.add_argument("--adhyay", type=int, required=True)
    a1.add_argument("--shot", required=True)
    a1.add_argument("--version", required=True)
    a1.add_argument("--edit-id", required=True)
    a1.add_argument("--jobs", type=Path)
    a1.add_argument("--note", default="")
    a1.add_argument("--model", default="", help="the model chip shown on screen when the image was made")
    a2 = sub.add_parser("status")
    a2.add_argument("--adhyay", type=int, required=True)
    a3 = sub.add_parser("collect")
    a3.add_argument("--adhyay", type=int, required=True)
    a3.add_argument("--downloads", type=Path, default=DOWNLOADS)
    for p in (a1, a2, a3):
        p.add_argument("--root", type=Path, default=OUT_ROOT)
    a = ap.parse_args(argv)
    if a.cmd == "add":
        try:
            it = add(a.root, a.adhyay, a.shot, a.version, a.edit_id, a.jobs, a.note, a.model)
        except ValueError as e:
            print("REFUSED:", e)
            return 2
        print("queued", it["flow_title"], it["url"])
        return 0
    if a.cmd == "collect":
        rep = collect(a.root, a.adhyay, a.downloads)
        for line in rep:
            print(line)
        s = status(a.root, a.adhyay)
        print(f"{len(s['pending'])} still pending, {len(s['filed'])} filed")
        return 0 if not s["pending"] else 1
    s = status(a.root, a.adhyay)
    for it in s["pending"]:
        print("PENDING", it["flow_title"], it["url"])
    for it in s["filed"]:
        print("FILED  ", it["flow_title"])
    print(f"{len(s['pending'])} pending, {len(s['filed'])} filed")
    return 0 if not s["pending"] else 1


if __name__ == "__main__":
    sys.exit(main())
