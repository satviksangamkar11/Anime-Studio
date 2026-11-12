"""Continuity sheet (I-05): code-made per-scene summary from blocking sheets, no generation.

Per shot: screen direction of each cast member (start facing), eyeline pairs (two members facing each other,
the left one facing right), prop states (A only / B only / A+B / none) and the end state of each cast member.
A direction flip on a match cut (the next shot starts facing the other way) is listed as a FLIP.
Output: an SVG text sheet (stdlib only).
"""
import html
from pathlib import Path


def _members(sheet):
    return [m for m in sheet.get("cast", []) if isinstance(m, dict) and m.get("id")]


def _start(m):
    v = m.get("start")
    return v if isinstance(v, dict) else {}


def _end(m):
    v = m.get("end")
    return v if isinstance(v, dict) else {}


def direction(sheet):
    return {m["id"]: _start(m).get("facing") for m in _members(sheet)}


def eyeline_pairs(sheet):
    ms = _members(sheet)
    pairs = []
    for a in ms:
        for b in ms:
            if a is b:
                continue
            if (_start(a).get("facing") == "right" and _start(b).get("facing") == "left"
                    and _start(a).get("x", 0) < _start(b).get("x", 0)):
                pairs.append([a["id"], b["id"]])
    return pairs


def _prop_state(visible):
    seen = set(visible) if isinstance(visible, list) else set()
    if seen >= {"A", "B"}:
        return "A+B"
    if seen == {"A"}:
        return "A only"
    if seen == {"B"}:
        return "B only"
    return "none"


def prop_states(sheet):
    return {p["id"]: _prop_state(p.get("visible")) for p in sheet.get("props", []) if isinstance(p, dict) and p.get("id")}


def end_state(sheet):
    out = {}
    for m in _members(sheet):
        e = _end(m)
        out[m["id"]] = {"x": e.get("x"), "y": e.get("y"), "pose": e.get("pose"), "facing": e.get("facing")}
    return out


def direction_flips(sheets):
    flips = []
    for prev, nxt in zip(sheets, sheets[1:]):
        if prev.get("cut_to_next") != "match":
            continue
        starts = {m["id"]: _start(m).get("facing") for m in _members(nxt)}
        for m in _members(prev):
            if m["id"] in starts and _end(m).get("facing") != starts[m["id"]]:
                flips.append((prev.get("shot_id"), nxt.get("shot_id"), m["id"]))
    return flips


def continuity_rows(sheets):
    return [{"shot_id": s.get("shot_id"), "direction": direction(s), "eyeline_pairs": eyeline_pairs(s),
             "prop_states": prop_states(s), "end_state": end_state(s)} for s in sheets]


def _lines(sheets):
    lines = []
    for row in continuity_rows(sheets):
        lines.append(row["shot_id"] or "UNKNOWN")
        lines.append("  direction: " + (", ".join("%s %s" % (k, v) for k, v in row["direction"].items()) or "none"))
        lines.append("  eyeline: " + (", ".join("%s facing %s" % (a, b) for a, b in row["eyeline_pairs"]) or "none"))
        lines.append("  props: " + (", ".join("%s %s" % (k, v) for k, v in row["prop_states"].items()) or "none"))
        lines.append("  end: " + (", ".join("%s %s facing %s" % (k, v["pose"], v["facing"])
                                            for k, v in row["end_state"].items()) or "none"))
    for a, b, mid in direction_flips(sheets):
        lines.append("FLIP %s to %s: %s changes screen direction on a match cut" % (a, b, mid))
    return lines


def write_continuity_svg(sheets, out):
    lines = _lines(sheets)
    height = 40 + 26 * len(lines)
    body = ['<text x="20" y="%d" font-size="18" font-family="sans-serif">%s</text>'
            % (30 + 26 * i, html.escape(line)) for i, line in enumerate(lines)]
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="%d">\n<rect width="100%%" height="100%%" '
           'fill="#ffffff"/>\n%s\n</svg>\n' % (height, "\n".join(body)))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    return out
