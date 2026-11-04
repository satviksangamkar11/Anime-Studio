"""Visual QA of one generated clip: the QA sheet (first / middle / last frame, clip_tools.qa) scored on the 9-criterion rubric of
SPEC_v2.2.md by a vision model, or by a person. Each criterion 0-2; accept = no 0 and total >= 14 of 18.
Writes <clip>_visual_qa.json (and <clip>_visual_qa_raw.json for the model paths).
  --via nvidia      NVIDIA build API (write_pack.call_nvidia, same key files); --model required
  --via openrouter  free vision models only (price 0 and image input); --model required; no paid calls
  --via manual      writes <clip>_visual_qa_prompt.txt (prompt + sheet path) and a blank score file for a person
The Claude CLI takes no images here, so it is refused.
Usage: python visual_qa.py clip.mp4 direction.json out_dir --via manual|nvidia|openrouter [--model M] [--bible bible.json]"""
import argparse
import base64
import json
import sys
import urllib.request
from pathlib import Path

import clip_tools
import write_pack

RUBRIC = {
    "indian_identity": "costume, ornaments and setting read as Braj",
    "character_consistency": "the characters match the sheet",
    "proportions": "heads and bodies match the bible's proportions",
    "line_art_intact": "clean line art, no melting or smearing",
    "acting_reads": "the beat's bhava is visible in face and body",
    "motion_has_weight": "anticipation and follow-through are visible",
    "staging_readable": "silhouette and screen direction read clearly",
    "light_motivated": "no glow hiding the performance",
    "continuity": "start and end states match the shot direction",
}
ACCEPT_TOTAL = 14
OPENROUTER_MODELS = "https://openrouter.ai/api/v1/models"


def build_review_prompt(shot_direction, bible_text, criteria=RUBRIC):
    direction = shot_direction if isinstance(shot_direction, str) else json.dumps(shot_direction, indent=1, ensure_ascii=False)
    lines = [f"- {name}: {what} (0, 1 or 2)" for name, what in criteria.items()]
    keys = ", ".join(f'"{name}": {{"score": 0-2, "reason": "one line"}}' for name in criteria)
    return ("You are the visual QA reviewer for one generated anime shot. The image is a frame sheet: left = first frame, "
            "middle = middle frame, right = last frame.\nJudge the frames against the shot direction and the style bible. Score each "
            "criterion 0 (fails), 1 (partly) or 2 (good), with one line of reason.\n\n"
            "## SHOT DIRECTION\n\n" + direction + "\n\n## STYLE BIBLE (locked identity)\n\n" + (bible_text.strip() or "(none given)")
            + "\n\n## CRITERIA\n\n" + "\n".join(lines)
            + "\n\nReturn only one JSON object with all criteria, no other text: {" + keys + "}\n")


def parse_scores(text, criteria=RUBRIC):
    """{criterion: {"score": 0|1|2, "reason": str}} from the reviewer's answer (fenced or bare JSON)."""
    start, end = text.find("{"), text.rfind("}")
    found = json.loads(text[start:end + 1]) if 0 <= start < end else None
    if not isinstance(found, dict):
        raise ValueError("no JSON object in the reviewer's answer")
    scores = {}
    for name in criteria:
        entry = found.get(name)
        if not isinstance(entry, dict):
            raise ValueError(f"no score for {name}")
        score = int(entry["score"]) if isinstance(entry.get("score"), str) and entry["score"].isdigit() else entry.get("score")
        if type(score) is not int or score not in (0, 1, 2):
            raise ValueError(f"{name}: score must be 0, 1 or 2, got {entry.get('score')!r}")
        scores[name] = {"score": score, "reason": str(entry.get("reason", "")).strip()}
    return scores


def judge(scores, criteria=RUBRIC):
    total = sum(scores[name]["score"] for name in criteria)
    zeros = [name for name in criteria if scores[name]["score"] == 0]
    return {"total": total, "max": 2 * len(criteria), "zeros": zeros, "accept": not zeros and total >= ACCEPT_TOTAL}


def check_openrouter_vision(model, catalog=None):
    """Refuses a model that takes no image input or is not free (write_pack.openrouter_is_free)."""
    catalog = catalog or json.load(urllib.request.urlopen(OPENROUTER_MODELS, timeout=60))["data"]
    entry = next((m for m in catalog if m["id"] == model), None)
    if entry is None:
        raise ValueError(f"{model} is not in OpenRouter's catalog")
    if "image" not in (entry.get("architecture") or {}).get("input_modalities", []):
        raise ValueError(f"{model} takes no image input")
    if not write_pack.openrouter_is_free(model, catalog):
        raise ValueError(f"{model} is a paid OpenRouter model: refused (no paid calls)")


def call_vision(prompt, sheet, via, model):
    image = "data:image/png;base64," + base64.b64encode(Path(sheet).read_bytes()).decode("ascii")
    content = [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": image}}]
    if via == "nvidia":
        return write_pack.call_nvidia(prompt, model, content)
    check_openrouter_vision(model)
    return write_pack.call_openrouter(prompt, model, content=content)


def review(clip, direction_json, out_dir, via, model=None, bible=None):
    """Scores one clip and writes <clip>_visual_qa.json; returns the record. bible: optional bible.json path."""
    if via == "claude":
        raise ValueError("the Claude CLI takes no images here yet: use --via nvidia, openrouter or manual")
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    stem = Path(clip).stem
    sheet = clip_tools.qa(clip, out)["sheet"]
    direction = json.loads(Path(direction_json).read_text(encoding="utf-8"))
    prompt = build_review_prompt(direction, Path(bible).read_text(encoding="utf-8") if bible else "")
    target = out / f"{stem}_visual_qa.json"
    if via == "manual":
        (out / f"{stem}_visual_qa_prompt.txt").write_text(f"Sheet image: {sheet}\n\n{prompt}", encoding="utf-8")
        record = {"clip": str(clip), "via": "manual", "model": None, "sheet": sheet, "status": "awaiting manual scores",
                  "scores": {name: {"score": None, "reason": ""} for name in RUBRIC}}
        target.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
        return record
    if not model:
        raise ValueError("--model is required with --via nvidia or openrouter")
    raw = call_vision(prompt, sheet, via, model)
    (out / f"{stem}_visual_qa_raw.json").write_text(raw, encoding="utf-8")
    answer = json.loads(raw)
    if answer.get("is_error"):
        raise ValueError(f"the vision call failed or was cut off ({answer.get('finish_reason')}): {str(answer.get('result'))[:500]}")
    scores = parse_scores(answer["result"])
    record = {"clip": str(clip), "via": via, "model": model, "sheet": sheet, "scores": scores, **judge(scores)}
    target.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
    return record


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("clip"); ap.add_argument("direction"); ap.add_argument("out_dir")
    ap.add_argument("--via", required=True, choices=("claude", "nvidia", "openrouter", "manual"))
    ap.add_argument("--model"); ap.add_argument("--bible", help="bible.json from the writer (optional)")
    a = ap.parse_args(argv)
    print(json.dumps(review(a.clip, a.direction, a.out_dir, a.via, a.model, a.bible), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
