"""Nemotron Super (NVIDIA scheduler, nvidia/nemotron-3.5-super-vl-120b-a12b) on the render review package. usage (cwd = merge worktree): python research/_run_render_nv.py [tag]"""
import sys, time
from pathlib import Path
sys.path.insert(0, "D:/aai work/anime_studio")
from h3 import e2e_sample
tag = sys.argv[1] if len(sys.argv) > 1 else "R2"
sch = e2e_sample.live_scheduler(); sch.model = "nvidia/nemotron-3.5-super-vl-120b-a12b"
prompt = Path("research/_review_prompt_render.txt").read_text(encoding="utf-8") + "\n\nPACKAGE:\n" + Path("research/_render_review_pkg.txt").read_text(encoding="utf-8")
try:
    text = e2e_sample._ask(sch)(prompt)
except Exception as e:
    text = f"FAILED: {type(e).__name__}: {e}"
Path(f"research/RENDER_{tag}_NEMOTRON_NV_2026-11-09.md").write_text(f"# RENDER {tag} (Nemotron Super, NVIDIA)\n\n{text}\n", encoding="utf-8")
with open("D:/aai work/anime_studio/PROJECT_LOG.md", "a", encoding="utf-8") as fh:
    fh.write(f"{time.strftime('%m-%d %H:%M')} | nemotron-super-nv | REVIEW-DONE | render pre-flight {tag} (NVIDIA scheduler) | {len(text)} chars{' FAILED' if text.startswith('FAILED') else ''}\n")
print("nv done")
