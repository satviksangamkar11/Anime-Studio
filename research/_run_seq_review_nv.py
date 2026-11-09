"""Sequence/architecture review: Nemotron Super (NVIDIA 14-key scheduler) over ALL logs and rules, sliced ~11 KB.
usage (cwd = D:/aai work/anime_studio_merge): python research/_run_seq_review_nv.py
Writes research/SEQ_REVIEW_" + TAG + "_SLICES_2026-11-09.md and SEQ_REVIEW_NEMOTRON_2026-11-09.md. Never prints a key."""
import re, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, "D:/aai work/animation_research_tool")
from nvidia_scheduler import NvidiaScheduler, load_env_keys

MODEL = sys.argv[1] if len(sys.argv) > 1 else "nvidia/nemotron-3.5-super-vl-120b-a12b"
TAG = sys.argv[2] if len(sys.argv) > 2 else "NEMOTRON"
A = Path("D:/aai work/anime_studio"); M = Path("D:/aai work/anime_studio_merge")
SLICE = 11000

QUESTION = """You review the history of an anime-reel production pipeline (story -> writer -> keyframe images -> video clips on a rented GPU -> voices -> music -> sound mix -> captions -> final reel). The text below is a SLICE of its rules, lessons and project log. Owner's concern: steps were done in the wrong ORDER (example: video was rendered first, voices later, so voice length did not fit the picture and an extra 'editorial timeline' repair step was needed; the right order is audio first, then video built to the audio length).
For THIS slice only, output compact bullet lists (no preamble, no restating the text):
PROBLEMS: each = [id or rule/line cited] problem | root cause | cost if stated.
ORDER-PROBLEMS: any place where a step ran before something it depends on (what ran too early, what it should have waited for).
ARCH-CHANGES: concrete architectural change that would stop it recurring (a stage to add, move, merge, a gate, a contract/file handed between stages).
Say 'none in this slice' for an empty list. Only use facts in the slice; do not invent."""

def slices(text, label):
    out, cur = [], ""
    for para in re.split(r"(?<=\n)", text):
        if len(cur) + len(para) > SLICE and cur:
            out.append(cur); cur = ""
        cur += para[:SLICE]
    if cur: out.append(cur)
    return [(f"{label} part {i+1}/{len(out)}", s) for i, s in enumerate(out)]

parts = []
parts += slices((A / "blot.md").read_text(encoding="utf-8"), "blot.md rules")
parts += slices((M / "MISTAKES_AND_LESSONS.md").read_text(encoding="utf-8"), "MISTAKES_AND_LESSONS")
log = (A / "PROJECT_LOG.md").read_text(encoding="utf-8").splitlines()
keep = [l for l in log if re.search(r"\| (FAIL:?|DECISION|OWNER|FIX:) \|", l)]
parts += slices("\n".join(l[:420] for l in keep) + "\n", "PROJECT_LOG decisions/fails/owner lines")
for f in ["docs/PIPELINE_AUDIT_2026-11-07.md", "docs/AUDIT_2026-11-08_REEL1.md", "research/HANDOFF_REEL1_TO_MUSIC_2026-11-09.md",
          "CHECKLIST_ARCHITECTURE_2026-11-07.md", "STATUS.md", "research/AUDIO_PLAN_FROZEN_2026-11-06.md", "research/VOICE_SYSTEM_DESIGN_2026-11-09.md", "research/SCORING_SYSTEM_PLAN_2026-11-09.md"]:
    p = M / f
    if p.is_file(): parts += slices(p.read_text(encoding="utf-8"), f)
print("slices:", len(parts), flush=True)

import json, urllib.request
OR = MODEL.startswith("dots")
class _OR:
    def call(self, prompt, max_tokens=6000):
        key = Path("D:/aai work/loop_p0/secrets/openrouter_paid_key.txt").read_text().strip()
        body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0, "max_tokens": max_tokens}).encode()
        try:
            r = urllib.request.urlopen(urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}), timeout=600)
            d = json.loads(r.read()); c = d["choices"][0]["message"].get("content") or ""
            return {"status": "OK" if c.strip() else "EMPTY", "text": c, "cost": (d.get("usage") or {}).get("cost")}
        except Exception as e:
            return {"status": "ERR", "http_status": str(e)[:80]}
sch = _OR() if OR else NvidiaScheduler(load_env_keys(Path("D:/aai work/animation_research_tool/.env")), model=MODEL, read_timeout=600, max_calls=200, global_limit=14)

def run(i):
    label, s = parts[i]
    for attempt in range(3):
        res = sch.call(QUESTION + "\n\nSLICE: " + label + "\n-----\n" + s, max_tokens=int(sys.argv[3]) if len(sys.argv) > 3 else 6000)
        if res.get("status") == "OK" and (res.get("text") or "").strip():
            return i, label, re.sub(r"<think>.*?</think>", "", res["text"], flags=re.S).strip()
        time.sleep(30)
    return i, label, f"FAILED after 3 tries: {res.get('status')} {res.get('http_status')}"

with ThreadPoolExecutor(max_workers=2 if OR else 4) as ex:
    results = sorted(ex.map(run, range(len(parts))))
body = "\n\n".join(f"## {l}\n{t}" for _, l, t in results)
(M / ("research/SEQ_REVIEW_" + TAG + "_SLICES_2026-11-09.md")).write_text("# Nemotron Super slice reviews\n\n" + body + "\n", encoding="utf-8")
print("slices done; failed:", sum(t.startswith("FAILED") for _, _, t in results), flush=True)

SYN = """Below are per-slice findings of a review of an anime-reel pipeline's whole history. Merge them into ONE report with these sections:
1. PROBLEMS (deduplicated, grouped by stage: story/writer, keyframe images, video render, voices/audio, music, SFX/mix, captions, assembly/QC, tooling/process), each with root cause and cost, most expensive first.
2. ORDER PROBLEMS: every place a step ran before its dependency.
3. THE CORRECT SEQUENCE: a numbered stage order for a production pipeline (audio-first idea included if justified), what each stage hands to the next (the contract/file), and the gate that must pass before the next stage starts.
4. ARCHITECTURAL CHANGES: ranked list (what to build/change, which problem it removes).
Be concrete, cite rule/lesson ids from the slices, keep under 2500 words."""
res = sch.call(SYN + "\n\n" + body[:60000], max_tokens=int(sys.argv[3]) * 2 if len(sys.argv) > 3 else 12000)
syn = re.sub(r"<think>.*?</think>", "", res.get("text") or f"FAILED {res.get('status')}", flags=re.S).strip()
(M / ("research/SEQ_REVIEW_" + TAG + "_2026-11-09.md")).write_text("# Nemotron Super merged report\n\n" + syn + "\n", encoding="utf-8")
with open(A / "PROJECT_LOG.md", "a", encoding="utf-8") as fh:
    fh.write(f"{time.strftime('%m-%d %H:%M')} | nemotron-super-nv | REVIEW-DONE | sequence/architecture review of all logs+rules ({len(parts)} slices) | {len(syn)} chars NVIDIA\n")
print("synthesis done", len(syn))
