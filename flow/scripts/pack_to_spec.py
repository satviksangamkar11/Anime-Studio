"""
Story pack -> Flow image spec + series (story-agnostic).

Reads a pack written by director/write_pack.py (stories/<slug>/<pack>/shots.json + bible.json) and writes the two
files that flow/scripts/build_jobs.py consumes:
  <slug>_image_spec.json    one spec shot per keyframe: <SHOT>A = start frame, <SHOT>B = end frame (both 'generate')
  <slug>_flow_series.json   characters, places, props (chip, sheet, accepted, sentence), style, model, tail, forbidden

Rules (everything comes from the pack; nothing is invented):
1. Keyframes: a shot's keyframes.start gives <id>A and keyframes.end gives <id>B. END frames are NOT Flow edits: an edit
   needs the Flow edit id of the start tile, which exists only after that tile is accepted, and build_jobs refuses an
   edit without one. So both are generate jobs; B is written from end_state (warned in the spec).
2. Action: camera framing and height + start_state (A) or end_state (B), cast screen/facing, props with 'where'.
   Light: light.key, light.mood, light.rim (rim omitted when 'none'). Reference sentence from the aspect.
3. Chips: characters = cast ids; place chip from the set id; prop chips from the shot's props; ONE style chip.
   Derived chip names must be checked against the exact Flow asset names when they are uploaded.
4. Nothing is accepted by the converter: every sheet is accepted: false until the owner accepts it.
5. Refused (PackError, CLI exit 2): unsafe ids, a cast or set id missing from the bible, bad aspect, empty state or
   light, unsafe slug or adhyay. A prop id missing from the bible is only a warning (chip and text from the id).
Studio rules, not story facts: model block, tail, style chip name, default forbidden words (build_jobs), sheet names
and the outputs root default. They are copied here and listed in the warnings when they matter.

CLI: python flow/scripts/pack_to_spec.py --pack stories/<slug>/<pack> --adhyay N --out-dir flow/generated/<slug>
     [--outputs-root PATH] [--flow-project ID] [--overwrite]
"""

import argparse
import json
import re
import sys
from pathlib import Path

from build_jobs import DEFAULT_FORBIDDEN_WORDS

SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")  # fullmatch of ^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$
FLOW_DIR = Path(__file__).resolve().parent.parent  # the studio flow/ folder

OUTPUTS_ROOT_TEMPLATE = "D:/aai work/flow_outputs/anime_{slug}"   # audit B 11-08: same folder as ui flow_root(story)
STYLE_CHIP = "STYLE_CHIP_SHEET__v01"
TAIL = ("Full-frame picture, edge to edge, no border, no inset. "
        "No text, no letters, no modern objects, no halo.")
MODEL = {
    "name": "Nano Banana 2.1",
    "fallback": None,
    "count": "x2",
    "aspect": "per job: 16:9 for sheets and plates, 9:16 for keyframes (set the chip per job; see RUN_NOTES.md)",
    "download": "2K Upscaled",
    "_note": "Nano Banana 2.1 only, no fallback, always x2 (studio rule, IMAGE_SYSTEM_FULL.md section 1).",
}
LAYER_PREFIX = {"FG": "foreground", "MID": "middle", "BG": "background"}


class PackError(ValueError):
    """A pack that must not be converted. The CLI prints it and exits 2."""


def _check_id(value, what):
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise PackError(f"unsafe {what} id {value!r}: must match ^[A-Za-z0-9][A-Za-z0-9_-]{{0,63}}$")
    return value


def _sentence(text):
    return text.strip().rstrip(".") + "."


def _words(text):
    return str(text).replace("_", " ").replace("-", " ").strip()


def _name(entity_id, data):
    """Display name: the bible's name when it has one, else the id without its prefix (CHAR-MIRA -> Mira)."""
    if data.get("name"):
        return str(data["name"])
    base = entity_id.split("-", 1)[1] if "-" in entity_id else entity_id
    return " ".join(part.capitalize() for part in base.split("-") if part)


def _frame_sentence(sid, aspect):
    try:
        w, h = (int(x) for x in str(aspect).split(":"))
    except ValueError:
        raise PackError(f"shot {sid}: aspect {aspect!r} must look like 9:16") from None
    if w <= 0 or h <= 0:
        raise PackError(f"shot {sid}: aspect {aspect!r} must be positive")
    if h > w:
        return f"Portrait {aspect} frame, vertical picture."
    if w > h:
        return f"Landscape {aspect} frame, horizontal picture."
    return f"Square {aspect} frame, square picture."


def _light_sentence(sid, light):
    light = light or {}
    parts = [str(light[k]).strip().rstrip(".") for k in ("key", "mood") if light.get(k)]
    rim = str(light.get("rim") or "").strip().rstrip(".")
    if rim and rim.lower() != "none":
        parts.append(f"rim {rim}")
    if not parts:
        raise PackError(f"shot {sid}: light is empty")
    return _sentence("Light: " + "; ".join(parts))


def _action(sid, shot, kind, chars_b, props_b):
    camera = shot.get("camera") or {}
    state = str(shot.get(f"{kind}_state") or "").strip().rstrip(".")
    if not state:
        raise PackError(f"shot {sid}: {kind}_state is empty")
    framing = str(camera.get(f"{kind}_framing") or "").strip()
    head = f"{framing[:1].upper()}{framing[1:]} shot" if framing else "Shot"
    if camera.get("height"):
        head += f", camera {camera['height']}"
    out = [f"{head}: {state}."]
    cast_bits = []
    for c in shot.get("cast") or []:
        bits = [f"on screen {c['screen']}"] if c.get("screen") else []
        if c.get("facing"):
            bits.append(f"facing {c['facing']}")
        cast_bits.append(f"{_name(c['id'], chars_b[c['id']] or {})} {', '.join(bits)}".rstrip())
    prop_bits = []
    for p in shot.get("props") or []:
        name = _name(p["id"], props_b.get(p["id"]) or {})
        prop_bits.append(f"{name} ({p['where']})" if p.get("where") else name)
    if cast_bits:
        out.append(_sentence("; ".join(cast_bits)))
    if prop_bits:
        out.append(_sentence("Props: " + "; ".join(prop_bits)))
    return " ".join(out)


def _character_sentence(cid, data, name):
    # No trailing period: build_jobs joins sentences with '; ' and adds the period itself.
    bits = []
    if data.get("age"):
        bits.append(f"age {_words(data['age'])}")
    heads = data.get("heads")
    if isinstance(heads, (int, float)) and not isinstance(heads, bool):
        bits.append(f"about {heads} heads tall")
    attrs = [_words(a) for a in data.get("attributes") or []]
    if attrs:
        bits.append("attributes: " + ", ".join(attrs))
    bits.append("exactly as in the attached character sheet")
    return f"{name} (attached {cid}): " + "; ".join(bits)


def _layer_phrase(layer):
    prefix, _, rest = str(layer).partition("_")
    if prefix in LAYER_PREFIX:
        return f"{LAYER_PREFIX[prefix]} {_words(rest)}"
    return _words(layer)


def _place_text(name, data):
    # build_jobs writes this after "Setting: " and adds the period.
    text = f"the {name.lower()} set"
    layers = [_layer_phrase(x) for x in data.get("layers") or []]
    if layers:
        text += ": " + "; ".join(layers)
    if data.get("light"):
        text += f"; light {_words(data['light'])}"
    return text


def _prop_sentence(name, data):
    details = [f"{_words(k)} {_words(v)}" for k, v in data.items()
               if k != "palette_ref" and isinstance(v, (str, int, float)) and not isinstance(v, bool)]
    return name + (f" ({', '.join(details)})" if details else "")


def _by_id(section):
    """The writer saves a bible section either as {id: entry} (Nemotron) or as [{id, ...}] (Opus); accept both."""
    if isinstance(section, list):
        return {e["id"]: e for e in section if isinstance(e, dict) and isinstance(e.get("id"), str)}
    return section or {}


def _style_text(bible):
    line = bible.get("line") or {}
    shading = bible.get("shading") or {}
    rim = bible.get("rim_light") or {}
    bits = ["2.5D cel-shaded anime rendering: ink lines" + (", tapered" if line.get("taper") else "")]
    if shading.get("method"):
        bits.append(f"{_words(shading['method'])} shading")
    if rim.get("requires_visible_source"):
        bits.append("rim light only where a visible light source exists")
    if rim.get("no_default_halo"):
        bits.append("no halo")
    return ", ".join(bits) + "."


def convert(shots, bible, adhyay, slug, outputs_root=None, flow_project=None):
    """Return (spec_dict, series_dict) for build_jobs. Raises PackError for a pack that must not be converted."""
    _check_id(slug, "slug")
    if isinstance(adhyay, bool) or not isinstance(adhyay, int) or adhyay < 1:
        raise PackError(f"adhyay must be a whole number of 1 or more, got {adhyay!r}")
    if not isinstance(shots, list) or not shots:
        raise PackError("shots must be a non-empty list")
    if not isinstance(bible, dict):
        raise PackError("bible must be an object")
    chars_b = _by_id(bible.get("characters"))
    envs_b = _by_id(bible.get("environments"))
    props_b = _by_id(bible.get("props"))
    extra_forbidden = bible.get("forbidden_words") or []
    if not isinstance(extra_forbidden, list) or not all(isinstance(w, str) for w in extra_forbidden):
        raise PackError("bible forbidden_words must be a list of strings")

    warnings, problems = [], []
    spec_shots, slot_order = [], {}
    used_chars, used_envs, used_props = {}, {}, {}  # ordered sets of referenced ids
    seen = set()
    checked = []  # (shot, sid, scene, cast, set_id, props, keyframes, wanted), validated before any build
    for shot in shots:
        if not isinstance(shot, dict):
            raise PackError("every shot must be an object")
        sid = _check_id(shot.get("id"), "shot")
        if sid in seen:
            raise PackError(f"duplicate shot id {sid}")
        seen.add(sid)
        scene = str(shot.get("scene") or sid)

        cast = shot.get("cast") or []
        for c in cast:
            cid = _check_id(c.get("id") if isinstance(c, dict) else None, "cast")
            if cid not in chars_b:
                problems.append(f"{sid}: cast id {cid} is not in the bible")
            used_chars[cid] = None
        set_id = _check_id(shot.get("set"), "set")
        if set_id not in envs_b:
            problems.append(f"{sid}: set id {set_id} is not in the bible")
        used_envs[set_id] = None
        props = shot.get("props") or []
        for p in props:
            used_props[_check_id(p.get("id") if isinstance(p, dict) else None, "prop")] = None

        keyframes = shot.get("keyframes") or {}
        wanted = [(kind, sfx) for kind, sfx in (("start", "A"), ("end", "B")) if keyframes.get(kind)]
        if not wanted:
            warnings.append(f"{sid}: no start or end keyframe, so no spec shot")
        checked.append((shot, sid, scene, cast, set_id, props, keyframes, wanted))
    if problems:
        raise PackError("pack and bible disagree: " + "; ".join(problems))

    for shot, sid, scene, cast, set_id, props, keyframes, wanted in checked:
        for kind, sfx in wanted:
            spec_id = _check_id(sid + sfx, "shot")
            spec_shots.append({
                "shot_id": spec_id,
                "scene": scene,
                "method": "generate",
                "characters": [c["id"] for c in cast],
                "place": set_id,
                "props": [p["id"] for p in props],
                "action": _action(sid, shot, kind, chars_b, props_b),
                "light": _light_sentence(sid, shot.get("light")),
                "reference_sentence": _frame_sentence(sid, shot.get("aspect")),
                "base_edit_id": None,
                "edit_instruction": None,
                "keyframe": kind,
                "keyframe_file": str(keyframes[kind]),
                "source_shot": sid,
            })
            slot_order.setdefault(scene, []).append(spec_id)

    no_name, thin, missing_props = [], [], []
    characters, places, props_out = {}, {}, {}
    for cid in used_chars:
        data = chars_b[cid] or {}
        name = _name(cid, data)
        if not data.get("name"):
            no_name.append(cid)
        if not any(data.get(k) for k in ("age", "heads", "attributes")):
            thin.append(cid)
        characters[cid] = {"name": name, "sheet_adhyay": adhyay, "sheet": f"{cid}__identity_master.png",
                           "accepted": False, "sentence": _character_sentence(cid, data, name)}
    for eid in used_envs:
        data = envs_b[eid] or {}
        name = _name(eid, data)
        if not data.get("name"):
            no_name.append(eid)
        places[eid] = {"chip": f"{eid.replace('-', '_')}__v01", "sheet_adhyay": adhyay, "sheet": f"{eid}.png",
                       "accepted": False, "text": _place_text(name, data)}
    for pid in used_props:
        data = props_b.get(pid)
        if data is None:
            missing_props.append(pid)
            data = {}
        name = _name(pid, data)
        if not data.get("name"):
            no_name.append(pid)
        props_out[pid] = {"name": name, "chip": pid, "sheet_adhyay": adhyay, "sheet": f"{pid}.png",
                          "accepted": False, "sentence": _prop_sentence(name, data)}

    if no_name:
        warnings.append("names taken from ids (bible has no name field): " + ", ".join(no_name))
    if thin:
        warnings.append("characters with no age, heads or attributes in the bible (sentence is name only): "
                        + ", ".join(thin))
    if missing_props:
        warnings.append("props missing from the bible (chip and text from the id only): " + ", ".join(missing_props))
    warnings.append(f"not accepted yet: {len(characters)} characters, {len(places)} places, {len(props_out)} props "
                    f"have accepted=false, so no reference sheet is attached and no prop chip is used until the owner "
                    f"accepts the sheet and sets accepted=true in {slug}_flow_series.json")
    warnings.append("chip names are derived from ids (character id; place id with _ and __v01; prop id; "
                    f"style {STYLE_CHIP}): check each against the exact Flow asset name when uploaded")
    warnings.append("character sentences, place texts, prop sentences and the style text are built from bible fields "
                    "only (age, heads, attributes, layers, light, line, shading): the owner's approved wording is not "
                    "in the pack, so review them before any Flow run")
    if any(s["keyframe"] == "end" for s in spec_shots):
        warnings.append("END frames (B) are new generations from end_state text: not edits of their A tile, and the A "
                        "tile is not attached as a chip (build_jobs has no such chip; IMAGE_SYSTEM_FULL.md section 3)")
    if outputs_root is None:
        outputs_root = OUTPUTS_ROOT_TEMPLATE.format(slug=slug)
        warnings.append(f"outputs_root defaulted to {outputs_root} (pass --outputs-root to change it)")
    if flow_project is None:
        warnings.append("flow_project is not set: fill in the Flow project id before any Flow run")

    spec = {
        "_note": (f"Generated from the {slug} pack by flow/scripts/pack_to_spec.py ({len(shots)} shots, "
                  f"{len(spec_shots)} keyframes). Each spec shot is one keyframe: A = start, B = end. Regenerate, "
                  "do not hand-edit."),
        "adhyay": adhyay,
        "slug": slug,
        "slot_order": slot_order,
        "shots": spec_shots,
        "warnings": warnings,
    }
    series = {
        "_note": (f"Generated from the {slug} pack by flow/scripts/pack_to_spec.py. The owner sets accepted=true "
                  "and the exact Flow chip name after each sheet is approved and uploaded."),
        "version": 1,
        "slug": slug,
        "flow_project": flow_project,
        "outputs_root": outputs_root,
        "model": dict(MODEL),
        "style": {
            "chip": STYLE_CHIP,
            "chip_sheet": {"sheet_adhyay": adhyay, "sheet": "STYLE_CHIP_SHEET.png", "accepted": False},
            "text": _style_text(bible),
        },
        "tail": TAIL,
        "forbidden_words": list(DEFAULT_FORBIDDEN_WORDS) + [w for w in extra_forbidden
                                                             if w not in DEFAULT_FORBIDDEN_WORDS],
        "characters": characters,
        "places": places,
        "props": props_out,
    }
    return spec, series


def load_pack(pack_dir):
    pack_dir = Path(pack_dir)
    shots_path, bible_path = pack_dir / "shots.json", pack_dir / "bible.json"
    if not (shots_path.is_file() and bible_path.is_file()):
        raise PackError(f"{pack_dir} needs shots.json and bible.json")
    shots = json.loads(shots_path.read_text(encoding="utf-8"))
    bible = json.loads(bible_path.read_text(encoding="utf-8"))
    return shots, bible


def main(argv=None, flow_dir=FLOW_DIR):
    parser = argparse.ArgumentParser(description="Convert a story pack to a Flow image spec and series")
    parser.add_argument("--pack", required=True, help="stories/<slug>/<pack>")
    parser.add_argument("--adhyay", type=int, required=True)
    parser.add_argument("--out-dir", required=True, help="a folder inside the studio flow/ folder")
    parser.add_argument("--outputs-root", default=None)
    parser.add_argument("--flow-project", default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        pack_dir = Path(args.pack)
        slug = pack_dir.resolve().parent.name  # stories/<slug>/<pack>
        _check_id(slug, "slug")
        out_dir = Path(args.out_dir).resolve()
        flow = Path(flow_dir).resolve()
        if out_dir == flow or flow not in out_dir.parents:
            raise PackError(f"out-dir {out_dir} must be a folder inside {flow}")
        shots, bible = load_pack(pack_dir)
        spec, series = convert(shots, bible, args.adhyay, slug,
                               outputs_root=args.outputs_root, flow_project=args.flow_project)
        spec_path = out_dir / f"{slug}_image_spec.json"
        series_path = out_dir / f"{slug}_flow_series.json"
        if not args.overwrite and (spec_path.exists() or series_path.exists()):
            raise PackError(f"refusing to overwrite files in {out_dir} (use --overwrite)")
        out_dir.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(json.dumps(spec, indent=1, ensure_ascii=False), encoding="utf-8")
        series_path.write_text(json.dumps(series, indent=1, ensure_ascii=False), encoding="utf-8")
    except (PackError, OSError, ValueError) as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    for w in spec["warnings"]:
        print(f"WARN: {w}", file=sys.stderr)
    print(f"Wrote {len(spec['shots'])} spec shots to {spec_path} and {series_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
