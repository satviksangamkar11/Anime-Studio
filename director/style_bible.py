"""Style bible loader and locked prompt text (Flow and H3).

Data lives in style/<project>.json. Outputs are plain text; no film or studio names.
"""
import json
from pathlib import Path

STYLE_DIR = Path(__file__).resolve().parent / "style"
MAX_BLOCK = 600


def load(project):
    path = STYLE_DIR / f"{project}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _entities(bible):
    for key in ("characters", "environments", "props"):
        for item in bible.get(key, []):
            yield key, item


def ids(bible):
    return {item["id"] for _, item in _entities(bible)}


def _find(bible, entity_id):
    for _, item in _entities(bible):
        if item["id"] == entity_id:
            return item
    raise KeyError(entity_id)


def _costume_text(char, n=2):
    parts = []
    for piece in char.get("costume", [])[:n]:
        hexes = piece.get("colour_hex", "")
        parts.append(f"{piece['piece']} {hexes}".strip())
    return "; ".join(parts)


def _char_block(char):
    markers = "; ".join(char.get("silhouette_markers", [])[:3])
    heads = char.get("proportions_heads")
    heads_text = f"{heads} heads" if heads is not None else "hood fan of 7-9 visible hoods"
    hair = char.get("hair", {}).get("base_colour", "")
    text = (
        f"{char['name']}. {heads_text}. Silhouette: {markers}. "
        f"Skin: {char['skin']['treatment'].split(';')[0]}. "
        f"Costume: {_costume_text(char)}. Hair: {hair}. "
        f"Locked, never: {'; '.join(char.get('forbidden_drift', [])[:2])}."
    )
    return text


def _env_block(env):
    comp = env["composition"]
    return (
        f"{env['name']}. {env['geography']}. Light: {env['day_key']}. "
        f"Layers: fg {comp['fg']}; mid {comp['mid']}; bg {comp['bg']}."
    )


def _prop_block(prop):
    return (
        f"{prop['name']}: {prop['description']}. Colour {prop['colour_hex']}. "
        f"Never: {prop.get('forbidden_drift', '')}."
    )


def prompt_block(bible, entity_id):
    item = _find(bible, entity_id)
    if entity_id.startswith("CHAR-"):
        text = _char_block(item)
    elif entity_id.startswith("ENV-"):
        text = _env_block(item)
    else:
        text = _prop_block(item)
    if len(text) > MAX_BLOCK:
        text = text[: MAX_BLOCK - 3] + "..."
    return text


def flow_sheet_prompt(bible, char_id):
    char = _find(bible, char_id)
    if not char_id.startswith("CHAR-"):
        raise ValueError(f"{char_id} is not a character")
    palette = [p["colour_hex"] for p in char.get("costume", []) if p.get("colour_hex")]
    heads = char.get("proportions_heads")
    heads_text = f"{heads} heads tall" if heads is not None else "scale: a hood fan of 7-9 visible hoods"
    costume_lines = "; ".join(
        f"{p['piece']} ({p.get('colour_hex', '')})" for p in char.get("costume", [])
    )
    return (
        "Character reference sheet on a neutral grey background (#808080). One image, three panels "
        "in a row: Panel 1 face close-up three-quarter view; Panel 2 full body front view; "
        "Panel 3 full body back view. Same character, same costume and colours in all three panels.\n"
        f"Character: {char['name']}. Proportions: {heads_text}. "
        f"Silhouette: {'; '.join(char.get('silhouette_markers', []))}. "
        f"Skin: {char['skin']['treatment']}. "
        f"Eyes: {char['eyes']['shape']}; iris {char['eyes']['iris']}. "
        f"Hair: {char.get('hair', {}).get('style', '')}. "
        f"Costume callouts: {costume_lines}. "
        f"Locked colours: {', '.join(palette) or 'see bible'}. "
        "Style: 2D cel-shaded Indian classical anime character, variable ink line, hard shadow planes, "
        "no airbrush gradients on the figure, no glow, no rim light on this sheet. "
        f"Avoid: {'; '.join(char.get('forbidden_drift', []))}. "
        "Original design."
    )
