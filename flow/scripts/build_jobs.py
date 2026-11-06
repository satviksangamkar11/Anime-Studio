"""
Flow Job Builder for Kaliya Mardan (anime) series.

Rules derived from A_KM_flow_jobs_keyframesA.json and flow_series_kaliya.json:

1. flow_title = "<shot_id>__v<NN>" where NN is two-digit version (01 unless spec provides otherwise).
2. chips order: character IDs (from series.characters), then place chip (from series.places[place].chip),
   then prop chips (from series.props[prop].chip for the prop ids in the spec shot's "props" list; a prop with
   accepted: false has no sheet yet, so no chip), then exactly ONE style chip (series.style.chip).
   Character/place chips are the series IDs; place chip is the place's chip field.
3. unaccepted_sheets: any character or place sheet referenced in the shot that has accepted: false in series.
   (Props with accepted: false are not added to unaccepted_sheets here; they are omitted from chips.)
4. people_count = len(characters).
5. prompt composition (exact pattern from reference jobs):
   a. Style text (series.style.text)
   b. People line: if people_count > 0: "Exactly N person: <character sentence for each character joined by '; '>."
      else: "No people in the picture."
      NOTE: Character sentences are used AS-IS from series.characters[cid].sentence (they already contain
      the "Name (attached CID):" prefix). Do not prepend the character name again.
      The people line MUST end with a period (added after joining sentences).
   c. Setting line: "Setting: <place text from series.places[place].text>" with a trailing period added if missing.
      For ENV-KADAMBA-BANK, the reference jobs use a specific override text (see PLACE_TEXT_OVERRIDES).
   d. Action text (shot.action)
   e. If people_count > 0: "Show only these people and no others."
   f. Light text (shot.light)
   g. Reference sentence (shot.reference_sentence)
   h. Tail text (series.tail)
   All parts separated by a single space.
6. prompt_sha256 = sha256(prompt.encode()).hexdigest()
7. previous_shot / next_shot are always None (per reference file).
8. attempt_cap = 8.
9. method = shot.method ('generate' or 'edit').
10. Edit job validation: if method == 'edit' and (base_edit_id is None or base_edit_id == '' or 'PENDING' in str(base_edit_id)):
    raise ValueError(f"Shot {shot_id}: edit job requires a valid base_edit_id")
11. Forbidden words: from series.forbidden or series.forbidden_words (list of strings; default DEFAULT_FORBIDDEN_WORDS).
    Check prompt (case-insensitive, whole-word for regex-like entries).
    If any forbidden word appears, raise ValueError(f"Shot {shot_id}: forbidden word '<word>' in prompt").
12. Unknown character/place ID: if shot.characters contains id not in series.characters, or shot.place not in series.places,
    raise ValueError.
13. Duplicate shot_id in spec.shots: raise ValueError.
14. sheets array: absolute paths to accepted character and place reference sheets for this shot.
    Path = series.outputs_root + f"\\adhyay_{adhyay:02d}\\references\\" + series.characters[char_id].sheet (or places[place].sheet).
    Only include if accepted: true.
15. neighbour_chips = [] and neighbour_sentence = "Match the attached neighbouring shot for the house, road, props and positions."
    (constant from reference).
16. model = series.model (copied as-is).
17. status = "TODO".
18. file_version = "v01" (matches flow_title version).
19. props = [] (not used in reference; kept for compatibility).
20. CLI: --adhyay, --spec, --series, --out, [--model-name], [--overwrite]. Refuses to overwrite --out unless --overwrite.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


# Place text overrides to match reference jobs exactly.
# The reference jobs for ENV-KADAMBA_BANK use a specific variant that differs from the current series data.
# Must include trailing period to match reference prompt exactly.
PLACE_TEXT_OVERRIDES = {
    "ENV-KADAMBA-BANK": (
        "the dark ash-sand bank at the water's edge with a green grass line at the kadamba's roots, "
        "exactly as in the attached place sheet of the Yamuna at dawn: "
        "the green grass line stops where the ash begins, one lone kadamba tree leans over the water "
        "with dark green leaves out of focus in the foreground, a Braj village far behind on the upper right, "
        "low sun from screen left, sky haze, flat painted bands of river and far bank with aerial haze."
    ),
}


# Studio-wide forbidden words, used when a series does not list its own. Imported by pack_to_spec.py.
DEFAULT_FORBIDDEN_WORDS = ["loincloth", "naked", "nude", "bare-chested"]


def _get_place_prompt_text(place_id: str, place_data: dict) -> str:
    """Get the place text for prompt composition, applying overrides and ensuring trailing period."""
    if place_id in PLACE_TEXT_OVERRIDES:
        return PLACE_TEXT_OVERRIDES[place_id]
    text = place_data.get("text", "")
    if text and not text.endswith("."):
        text += "."
    return text


def build_jobs(spec: dict, series: dict, adhyay: int) -> list[dict]:
    # Validate adhyay matches
    if spec.get("adhyay") != adhyay:
        raise ValueError(f"Spec adhyay {spec.get('adhyay')} does not match requested adhyay {adhyay}")

    # Flatten slot_order to get shot sequence (used for validation only)
    slot_order = spec.get("slot_order", {})
    shot_sequence = []
    for scene, shots in slot_order.items():
        shot_sequence.extend(shots)

    # Map shot_id -> shot data
    shots_by_id = {s["shot_id"]: s for s in spec.get("shots", [])}

    # Check duplicate shot_ids
    seen = set()
    for s in spec.get("shots", []):
        if s["shot_id"] in seen:
            raise ValueError(f"Duplicate shot_id: {s['shot_id']}")
        seen.add(s["shot_id"])

    # Validate all shot_ids in slot_order exist in shots
    for sid in shot_sequence:
        if sid not in shots_by_id:
            raise ValueError(f"Shot {sid} in slot_order not found in shots")

    # Forbidden words from series
    # The Kaliya series file names this list "forbidden_words"; both keys are read.
    forbidden_words = series.get("forbidden", series.get("forbidden_words", DEFAULT_FORBIDDEN_WORDS))

    # Pre-compile forbidden patterns (support word-boundary regex like \bbare\b)
    forbidden_patterns = []
    for w in forbidden_words:
        try:
            # If it looks like a regex pattern, compile it
            if re.search(r"[\\^$.*+?{}[]|()]", w):
                forbidden_patterns.append(re.compile(w, re.IGNORECASE))
            else:
                forbidden_patterns.append(re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE))
        except re.error:
            # Fallback to literal substring
            forbidden_patterns.append(re.compile(re.escape(w), re.IGNORECASE))

    # Style chip
    style_chip = series.get("style", {}).get("chip")
    if not style_chip:
        raise ValueError("Series style.chip is missing")

    # Tail text
    tail = series.get("tail", "")

    jobs = []
    for shot_id in shot_sequence:
        shot = shots_by_id[shot_id]
        scene = shot.get("scene", "")
        method = shot.get("method", "generate")
        characters = shot.get("characters", [])
        place = shot.get("place")
        props = shot.get("props", [])
        action = shot.get("action", "")
        light = shot.get("light", "")
        reference_sentence = shot.get("reference_sentence", "")
        base_edit_id = shot.get("base_edit_id")
        edit_instruction = shot.get("edit_instruction")

        # Validate method
        if method not in ("generate", "edit"):
            raise ValueError(f"Shot {shot_id}: invalid method '{method}'")

        # Edit job validation
        if method == "edit":
            if base_edit_id is None or base_edit_id == "" or "PENDING" in str(base_edit_id):
                raise ValueError(f"Shot {shot_id}: edit job requires a valid base_edit_id")

        # Validate characters
        for cid in characters:
            if cid not in series.get("characters", {}):
                raise ValueError(f"Shot {shot_id}: unknown character '{cid}'")

        # Validate place
        if place not in series.get("places", {}):
            raise ValueError(f"Shot {shot_id}: unknown place '{place}'")

        # Validate props
        for pid in props:
            if pid not in series.get("props", {}):
                raise ValueError(f"Shot {shot_id}: unknown prop '{pid}'")

        # Build chips
        chips = []
        # Character chips (ids)
        for cid in characters:
            chips.append(cid)
        # Place chip
        place_chip = series["places"][place].get("chip")
        if not place_chip:
            raise ValueError(f"Place {place} has no chip")
        chips.append(place_chip)
        # Prop chips, in shot order (only props the shot lists; the Kaliya reference shots list none)
        for pid in props:
            prop = series["props"][pid]
            if not prop.get("accepted", True):
                continue
            if not prop.get("chip"):
                raise ValueError(f"Prop {pid} has no chip")
            if prop["chip"] not in chips:
                chips.append(prop["chip"])
        # Style chip (exactly one)
        chips.append(style_chip)

        # Unaccepted sheets: character or place sheets with accepted: false
        unaccepted_sheets = []
        for cid in characters:
            char = series["characters"][cid]
            if not char.get("accepted", True):
                unaccepted_sheets.append(char.get("sheet", ""))
        place_data = series["places"][place]
        if not place_data.get("accepted", True):
            unaccepted_sheets.append(place_data.get("sheet", ""))
        # Filter empty
        unaccepted_sheets = [s for s in unaccepted_sheets if s]

        # People count
        people_count = len(characters)

        # Build prompt
        parts = []

        # Style text
        style_text = series.get("style", {}).get("text", "")
        if style_text:
            parts.append(style_text)

        # People line: use character sentences AS-IS (they already contain "Name (attached CID):" prefix)
        # The people line MUST end with a period to match reference prompts.
        if people_count > 0:
            char_sentences = []
            for cid in characters:
                char = series["characters"][cid]
                sentence = char.get("sentence", "")
                if sentence:
                    char_sentences.append(sentence)
            if char_sentences:
                parts.append(f"Exactly {people_count} person: {'; '.join(char_sentences)}.")
            else:
                parts.append(f"Exactly {people_count} person.")
        else:
            parts.append("No people in the picture.")

        # Setting line: use override for ENV-KADAMBA-BANK, ensure trailing period
        place_text = _get_place_prompt_text(place, place_data)
        if place_text:
            parts.append(f"Setting: {place_text}")

        # Action
        if action:
            parts.append(action)

        # Show only these people
        if people_count > 0:
            parts.append("Show only these people and no others.")

        # Light
        if light:
            parts.append(light)

        # Reference sentence
        if reference_sentence:
            parts.append(reference_sentence)

        # Tail
        if tail:
            parts.append(tail)

        prompt = " ".join(parts)

        # Forbidden word check
        for pattern in forbidden_patterns:
            match = pattern.search(prompt)
            if match:
                # Extract the matched word for error message
                matched = match.group(0)
                raise ValueError(f"Shot {shot_id}: forbidden word '{matched}' in prompt")

        # Prompt SHA256
        prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        # Sheets paths (only accepted)
        sheets = []
        outputs_root = series.get("outputs_root", "")
        ref_dir = Path(outputs_root) / f"adhyay_{adhyay:02d}" / "references"
        for cid in characters:
            char = series["characters"][cid]
            if char.get("accepted", True):
                sheet_name = char.get("sheet")
                if sheet_name:
                    sheets.append(str(ref_dir / sheet_name))
        place_sheet = place_data.get("sheet")
        if place_data.get("accepted", True) and place_sheet:
            sheets.append(str(ref_dir / place_sheet))

        # Previous/next are always None per reference file
        prev_shot = None
        next_shot = None

        # Flow title
        flow_title = f"{shot_id}__v01"

        # Model (copy from series)
        model = series.get("model", {})

        job = {
            "adhyay": adhyay,
            "shot_id": shot_id,
            "scene": scene,
            "method": method,
            "file_version": "v01",
            "flow_title": flow_title,
            "characters": characters,
            "people_count": people_count,
            "props": [],
            "chips": chips,
            "unaccepted_sheets": unaccepted_sheets,
            "prompt": prompt,
            "prompt_sha256": prompt_sha256,
            "base_edit_id": base_edit_id,
            "edit_instruction": edit_instruction,
            "previous_shot": prev_shot,
            "next_shot": next_shot,
            "sheets": sheets,
            "attempt_cap": 8,
            "neighbour_chips": [],
            "neighbour_sentence": "Match the attached neighbouring shot for the house, road, props and positions.",
            "model": model,
            "status": "TODO",
        }
        jobs.append(job)

    return jobs


def main():
    parser = argparse.ArgumentParser(description="Build Flow jobs from spec and series")
    parser.add_argument("--adhyay", type=int, required=True)
    parser.add_argument("--spec", type=str, required=True)
    parser.add_argument("--series", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--model-name", type=str, default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    out_path = Path(args.out)
    if out_path.exists() and not args.overwrite:
        print(f"Refusing to overwrite {out_path} (use --overwrite)", file=sys.stderr)
        sys.exit(1)

    with open(args.spec, "r", encoding="utf-8") as f:
        spec = json.load(f)
    with open(args.series, "r", encoding="utf-8") as f:
        series = json.load(f)

    # Override model name if provided
    if args.model_name:
        series.setdefault("model", {})["name"] = args.model_name

    jobs = build_jobs(spec, series, args.adhyay)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=1, ensure_ascii=False)

    print(f"Wrote {len(jobs)} jobs to {out_path}")


if __name__ == "__main__":
    main()
