"""Nemotron Super (NVIDIA 14-key scheduler) checks the loop checklist FIRST. usage (cwd = D:/aai work/anime_studio_merge): python research/_run_checklist_check_super.py"""
import re, sys, time
from pathlib import Path
sys.path.insert(0, "D:/aai work/animation_research_tool")
from nvidia_scheduler import NvidiaScheduler, load_env_keys

M = Path("D:/aai work/anime_studio_merge")
checklist = (M / "research/LOOP_CHECKLIST_STEPS_1_4_2026-11-10.md").read_text(encoding="utf-8")
plan = (M / "research/PLAN_REVIEW_TRIAGE_2026-11-10.md").read_text(encoding="utf-8")
loop_facts = """FACTS about the loop system (from its README): job = spec + files + tests; round 0 coder writes module+tests; pytest; fix rounds with real pytest output; test files frozen after round 0; reviewers read files; exit codes 0 passed, 1 review-open/test-review-open/invalid-spec, 3 needs_review/escalate, 4 claim conflict, 5 passed-no-review, 6 reviewer CLI down; parallel jobs via pieces/p1_claims.py with file claims and a shared key ledger; coder_model is refused unless Ultra today; coder replies are whole FILE: blocks; Nemotron Super spends tokens thinking unless thinking is off and needs inputs of about 10 KB."""
prompt = f"""You are the first checker of a work checklist. Find: missing steps, wrong order, contradictions with the facts, risks that would make the loops fail or waste calls, jobs whose scope is too big for one whole-file coder reply, file overlaps between parallel jobs, vague acceptance criteria. For every finding give the exact fix to the checklist (replacement text). Also say if any job should be split, merged, or reordered, and list the 5 most likely ways this run fails. Compact lists, no preamble. Only use the facts given.

{loop_facts}

CHECKLIST:
{checklist}

TRIAGED PLAN (context):
{plan[:5000]}"""
sch = NvidiaScheduler(load_env_keys(Path("D:/aai work/animation_research_tool/.env")), model="nvidia/nemotron-3.5-super-vl-120b-a12b", read_timeout=900, max_calls=20, global_limit=14)
txt = ""
for _ in range(3):
    res = sch.call(prompt, max_tokens=16000)
    txt = re.sub(r"<think>.*?</think>", "", res.get("text") or "", flags=re.S).strip()
    if res.get("status") == "OK" and txt:
        break
    time.sleep(30)
(M / "research/LOOP_CHECKLIST_CHECK_SUPER_2026-11-10.md").write_text("# Nemotron Super check of the loop checklist\n\n" + (txt or "FAILED: empty") + "\n", encoding="utf-8")
with open("D:/aai work/anime_studio/PROJECT_LOG.md", "a", encoding="utf-8") as fh:
    fh.write(f"{time.strftime('%m-%d %H:%M')} | nemotron-super-nv | REVIEW-DONE | loop checklist check (checklist-first, owner order) | {len(txt)} chars NVIDIA\n")
print("done", len(txt))
