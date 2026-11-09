"""Round-1 architecture review. usage: python research/_run_arch_reviews.py dots|supervl. Free OpenRouter models, sequential batches, never prints the key."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, "flow/scripts")
import dots_review as d
which = sys.argv[1]
d.MODEL = {"dots": d.MODEL, "supervl": "nvidia/nemotron-3.5-super-vl:free"}[which]
prompt = Path("research/_review_prompt_colour.txt").read_text(encoding="utf-8")
out = Path(f"research/COLOUR_PROMPT_REVIEW_{which.upper()}_2026-11-07.md"); out.write_text("", encoding="utf-8")
for name, files in json.load(open("research/_review_batches_colour.json")).items():
    t = time.strftime("%m-%d %H:%M")
    try:
        res = d.review(prompt, [Path(f) for f in files], max_tokens=24000)
        text = res["text"] + ("" if not res["paid"] else "\n[WARNING: paid]")
    except Exception as e:
        text = f"FAILED: {type(e).__name__}: {e}"
    with out.open("a", encoding="utf-8") as fh:
        fh.write(f"\n\n# BATCH {name} ({which}) {t}\n\n{text}\n")
    with open("PROJECT_LOG.md", "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%m-%d %H:%M')} | {which} | REVIEW-DONE | batch {name} | {len(text)} chars{' FAILED' if text.startswith('FAILED') else ''}\n")
print(which, "all batches done")
