"""One-off: run the caption review with Dots and Nemotron 3.5 Super VL (both OpenRouter :free). usage: python _run_caption_reviews.py"""
import sys
from pathlib import Path
sys.path.insert(0, "flow/scripts")
import dots_review as d
prompt = Path("research/_caption_review_prompt.txt").read_text(encoding="utf-8")
files = [Path(p) for p in ("research/CAPTION_FONTS_RESEARCH_2026-11-07.md", "h3/gate_d_audio.py", "assets/fonts/README.md", "director/simple_language.py", "director/asr_transcribe.py", "research/OWNER_MASTER_PROMPT_V4_2026-11-07.txt")]
which = sys.argv[1]
d.MODEL = {"dots": d.MODEL, "supervl": "nvidia/nemotron-3.5-super-vl:free"}[which]
res = d.review(prompt, files, max_tokens=24000)
Path(f"research/CAPTION_REVIEW_{which.upper()}_2026-11-07.md").write_text(res["text"], encoding="utf-8")
print(which, "done", len(res["text"]), "paid" if res["paid"] else "free", "truncated" if res.get("truncated") else "")
