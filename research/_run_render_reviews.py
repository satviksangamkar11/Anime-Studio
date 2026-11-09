"""Render pre-flight review (owner 2026-11-09: all reviewers before --go). usage (cwd = merge worktree): python research/_run_render_reviews.py xing|supervl [tag]. Free OpenRouter models."""
import sys, time
from pathlib import Path
sys.path.insert(0, "flow/scripts")
import dots_review as d
which = sys.argv[1]; tag = sys.argv[2] if len(sys.argv) > 2 else "R1"
d.MODEL = {"supervl": "nvidia/nemotron-3.5-super-vl:free", "xing": "xingchen-agi/xing4.0-29b-a4b:free"}[which]
prompt = Path("research/_review_prompt_render.txt").read_text(encoding="utf-8")
out = Path(f"research/RENDER_{tag}_{which.upper()}_2026-11-09.md")
t = time.strftime("%m-%d %H:%M")
try:
    res = d.review(prompt, [Path("research/_render_review_pkg.txt")], max_tokens=32000)
    text = res["text"] + ("" if not res["paid"] else "\n[WARNING: paid]")
except Exception as e:
    text = f"FAILED: {type(e).__name__}: {e}"
out.write_text(f"# RENDER {tag} ({which}) {t}\n\n{text}\n", encoding="utf-8")
with open("D:/aai work/anime_studio/PROJECT_LOG.md", "a", encoding="utf-8") as fh:
    fh.write(f"{time.strftime('%m-%d %H:%M')} | {which} | REVIEW-DONE | render pre-flight {tag} (OpenRouter free) | {len(text)} chars{' FAILED' if text.startswith('FAILED') else ''}\n")
print(which, "done")
