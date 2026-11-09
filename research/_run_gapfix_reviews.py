"""Gap-fix review (owner rule 8: one pass + one check). usage (cwd = merge worktree): python research/_run_gapfix_reviews.py xing|supervl [tag]. Free OpenRouter models."""
import sys, time
from pathlib import Path
sys.path.insert(0, "flow/scripts")
import dots_review as d
which = sys.argv[1]; tag = sys.argv[2] if len(sys.argv) > 2 else "R1"
d.MODEL = {"supervl": "nvidia/nemotron-3.5-super-vl:free", "xing": "xingchen-agi/xing4.0-29b-a4b:free"}[which]
prompt = Path("research/_review_prompt_gapfix.txt").read_text(encoding="utf-8")
out = Path(f"research/GAPFIX_{tag}_{which.upper()}_2026-11-08.md")
LOG = "D:/aai work/anime_studio/PROJECT_LOG.md"
t = time.strftime("%m-%d %H:%M")
try:
    res = d.review(prompt, [Path("research/_gapfix_diff.patch")], max_tokens=32000)
    text = res["text"] + ("" if not res["paid"] else "\n[WARNING: paid]")
except Exception as e:
    text = f"FAILED: {type(e).__name__}: {e}"
out.write_text(f"# GAPFIX {tag} ({which}) {t}\n\n{text}\n", encoding="utf-8")
with open(LOG, "a", encoding="utf-8") as fh:
    fh.write(f"{time.strftime('%m-%d %H:%M')} | {which} | REVIEW-DONE | gapfix {tag} (OpenRouter free) | {len(text)} chars{' FAILED' if text.startswith('FAILED') else ''}\n")
print(which, "done")
