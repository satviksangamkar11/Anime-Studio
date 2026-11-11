"""Nemotron Super (NVIDIA 14-key scheduler) reviews PLAN_STEPS_1_4 against the code and the branch diffs, slice by slice.
usage (cwd = D:/aai work/anime_studio_merge): python research/_run_plan_review_super.py
Writes research/PLAN_REVIEW_SUPER_SLICES_2026-11-10.md and PLAN_REVIEW_SUPER_2026-11-10.md. Never prints a key."""
import re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, "D:/aai work/animation_research_tool")
from nvidia_scheduler import NvidiaScheduler, load_env_keys

MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
M = Path("D:/aai work/anime_studio_merge"); A = Path("D:/aai work/anime_studio")
SLICE = 9000
plan = (M / "research/PLAN_STEPS_1_4_2026-11-10.md").read_text(encoding="utf-8")
head = plan.split("## Step 1")[0]
steps = {n: "## Step " + s for n, s in zip("1234", re.split(r"## Step \d", plan)[1:])}

def git(*a):
    return subprocess.run(["git", "-C", str(A), *a], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout

B1, B2 = "origin/merge-v4-universal-2026-11-07", "origin/v4-architecture-2026-11-07"

def slices(text, label, step):
    out, cur = [], ""
    for line in text.splitlines(keepends=True):
        if len(cur) + len(line) > SLICE and cur:
            out.append(cur); cur = ""
        cur += line[:SLICE]
    if cur: out.append(cur)
    return [(f"{label} part {i+1}/{len(out)}", step, s) for i, s in enumerate(out)]

items = []
items += slices(git("diff", "--name-status", B1, B2, "--", "director", "h3", "core", "tools", "flow") + "\n(A = only in v4 branch, D = only in merge branch, M = both, differs)", "branch file list", "1")
for f in ["h3/v4_to_h3.py", "h3/render_controller.py", "h3/h3_author.py", "h3/schema_and_linter.py"]:
    items += slices(git("diff", B1, B2, "--", f), f"diff merge->v4 {f}", "1")
for f in ["director/editorial_by_lang.py", "director/build_vo_tracks.py", "director/voice_cast.py", "director/build_final_reel.py"]:
    items += slices((M / f).read_text(encoding="utf-8"), f"merge-tree {f}", "1")
items += slices((M / "h3/compile_h3_sing8.py").read_text(encoding="utf-8"), "h3/compile_h3_sing8.py", "2")
items += slices((A / "director/build_h3_batch.py").read_text(encoding="utf-8"), "director/build_h3_batch.py", "2")
items += slices((A / "director/run_colab_batch.py").read_text(encoding="utf-8"), "director/run_colab_batch.py", "4")
print("slices:", len(items), flush=True)

Q = """You are a strict senior reviewer. Below: the PLAN header, the PLAN step this code belongs to, and one SLICE of code or of a git diff (a diff slice shows how the two code branches differ; '-' lines are the merge branch, '+' lines the v4 branch).
Output compact lists, no preamble:
DEFECTS: bugs, edge cases or missing handling in this slice that would break the plan or that the plan overlooks (cite function/line text).
CHANGES: the exact change needed for the plan, as a small unified diff or precise function-level instructions (names, parameters, order of operations). Not advice like 'add validation'.
TESTS: the smallest tests that prove it (name + what it asserts).
PLAN-WRONG: anything in the plan text that this code contradicts.
NEED: paths of other files you need to see to be sure (one per line, 'NEED: path'), only if truly required.
Only use facts in the slice and plan. Say 'none' for an empty list."""

sch = NvidiaScheduler(load_env_keys(Path("D:/aai work/animation_research_tool/.env")), model=MODEL, read_timeout=900, max_calls=300, global_limit=14)

def run(i):
    label, step, s = items[i]
    prompt = Q + "\n\nPLAN HEADER:\n" + head + "\n\nPLAN STEP:\n" + steps[step] + "\n\nSLICE: " + label + "\n-----\n" + s
    for attempt in range(3):
        res = sch.call(prompt, max_tokens=16000)
        txt = re.sub(r"<think>.*?</think>", "", res.get("text") or "", flags=re.S).strip()
        if res.get("status") == "OK" and txt:
            return i, label, txt
        time.sleep(30)
    return i, label, f"FAILED after 3 tries: {res.get('status')} {res.get('http_status')}"

with ThreadPoolExecutor(max_workers=3) as ex:
    results = sorted(ex.map(run, range(len(items))))
body = "\n\n".join(f"## {l}\n{t}" for _, l, t in results)
(M / "research/PLAN_REVIEW_SUPER_SLICES_2026-11-10.md").write_text("# Nemotron Super plan review, per slice\n\n" + body + "\n", encoding="utf-8")
need = sorted({m.strip() for m in re.findall(r"^NEED:\s*(.+)$", body, flags=re.M) if m.strip().lower() != "none"})
print("slices done; failed:", sum(t.startswith("FAILED") for _, _, t in results), "need:", len(need), flush=True)

SYN = """Merge these per-slice reviews of a pipeline plan into ONE report with sections:
1. MUST-FIX DEFECTS in the plan or code (deduplicated, ranked, each with the exact change).
2. CHANGES PER STEP (1a-1f, 2a-2d, 3, 4): file, function, what to change, in build order.
3. TESTS to add (name + assertion).
4. PLAN CORRECTIONS (what the plan says that the code contradicts).
5. OPEN QUESTIONS for the owner.
Concrete, cite file/function, under 2500 words."""
res = sch.call(SYN + "\n\n" + body[:60000], max_tokens=16000)
syn = re.sub(r"<think>.*?</think>", "", res.get("text") or f"FAILED {res.get('status')}", flags=re.S).strip()
(M / "research/PLAN_REVIEW_SUPER_2026-11-10.md").write_text("# Nemotron Super merged plan review\n\n" + syn + "\n\n## NEED requests\n" + "\n".join(need) + "\n", encoding="utf-8")
with open(A / "PROJECT_LOG.md", "a", encoding="utf-8") as fh:
    fh.write(f"{time.strftime('%m-%d %H:%M')} | nemotron-super-nv | REVIEW-DONE | plan steps 1-4 review ({len(items)} slices, {len(need)} NEED requests) | {len(syn)} chars NVIDIA\n")
print("synthesis done", len(syn), flush=True)
