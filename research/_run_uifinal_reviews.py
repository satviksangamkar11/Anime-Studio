"""Final UI+backend review. usage (cwd = merge worktree): python research/_run_uifinal_reviews.py dots|supervl [round-tag]. Free OpenRouter models, sequential batches, never prints the key."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, "flow/scripts")
import dots_review as d
which = sys.argv[1]; tag = sys.argv[2] if len(sys.argv) > 2 else "R1"
d.MODEL = {"dots": d.MODEL, "supervl": "nvidia/nemotron-3.5-super-vl:free"}[which]
prompt = Path("research/_review_prompt_uifinal.txt").read_text(encoding="utf-8")
out = Path(f"research/UIFINAL_{tag}_{which.upper()}_2026-11-07.md"); out.write_text("", encoding="utf-8")
LOG = "D:/aai work/anime_studio/PROJECT_LOG.md"
for name, files in json.load(open("research/_review_batches_uifinal.json")).items():
    t = time.strftime("%m-%d %H:%M")
    try:
        res = d.review(prompt, [Path(f) for f in files], max_tokens=32000)
        text = res["text"] + ("" if not res["paid"] else "\n[WARNING: paid]")
    except Exception as e:
        text = f"FAILED: {type(e).__name__}: {e}"
    with out.open("a", encoding="utf-8") as fh:
        fh.write(f"\n\n# BATCH {name} ({which}) {t}\n\n{text}\n")
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%m-%d %H:%M')} | {which} | REVIEW-DONE | uifinal {tag} batch {name} | {len(text)} chars{' FAILED' if text.startswith('FAILED') else ''}\n")
print(which, "all batches done")
