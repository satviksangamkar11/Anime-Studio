"""Pack rules P0-P13 (WP4 part 2). Standard library plus core.style_pack only. Never raises.

Input: episodes in the INTERFACES.md Timeline contract, the style-pack dict, the core.json dict,
and optionally the story.json dict. Every problem is one entry
{"rule", "level", "shot", "episode", "message"}. Look values come from the pack, never from code.
"""
import math
import re
from pathlib import Path

from core.style_pack import validate_pack

RULE_IDS = tuple(f"P{i}" for i in range(14))
HOOK_TYPES = ("H-01", "H-02", "H-03", "H-04", "H-05", "H-06")
FONT_ROLES = ("display", "sacred", "subtitle_latin", "subtitle_devanagari")
FONT_EXTS = (".ttf", ".otf", ".ttc", ".woff", ".woff2")
_REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------- small helpers ----------
def _entry(rule, level, message, shot=None, episode=None):
    return {"rule": rule, "level": level, "shot": shot, "episode": episode, "message": message}


def _shot_entry(rule, level, message, ep, sh):
    return _entry(rule, level, message, shot=sh.get("id"), episode=ep.get("key"))


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _as_dict(v):
    return v if isinstance(v, dict) else {}


def _as_list(v):
    return v if isinstance(v, list) else []


def _norm(v):
    return v.strip().lower() if isinstance(v, str) else None


def _palettes(pack):
    return _as_dict(pack.get("palettes"))


def _pal(pack, pid):
    return _as_dict(_palettes(pack).get(pid)) if isinstance(pid, str) else {}


def _look(sh):
    lk = sh.get("look")
    return lk if isinstance(lk, dict) else None


def _text(sh, key):
    v = _as_dict(sh.get("text")).get(key)
    return v if isinstance(v, str) else None


def _fps(ep, core):
    for v in (ep.get("fps"), core.get("fps")):
        if _is_num(v) and v > 0:
            return float(v)
    return None


def _each_shot(ctx):
    for ep in ctx.episodes:
        for sh in ep["shots"]:
            yield ep, sh


class _Ctx:
    def __init__(self, episodes, pack, core, story, story_path_exists, font_dir, pack_junk):
        self.episodes = episodes
        self.pack = pack
        self.core = core
        self.story = story
        self.story_path_exists = story_path_exists
        self.font_dir = font_dir
        self.pack_junk = pack_junk
        if story_path_exists is None:
            self.story_exists = story is not None
        else:
            self.story_exists = bool(story_path_exists)


# ---------- P0: input shapes ----------
def _shot_problems(sh):
    if not isinstance(sh, dict):
        return ["shot must be an object"]
    probs = []
    if not isinstance(sh.get("id"), str):
        probs.append("id must be a string")
    for key in ("frames", "start_frame"):
        if not _is_num(sh.get(key)):
            probs.append(f"{key} must be a number, got {sh.get(key)!r}")
    imps = sh.get("impacts", [])
    if not isinstance(imps, list):
        probs.append("impacts must be a list")
    else:
        for i, im in enumerate(imps):
            if not (isinstance(im, dict) and _is_num(im.get("at_frame")) and _is_num(im.get("at_s"))
                    and _is_num(im.get("frames")) and isinstance(im.get("type"), str)):
                probs.append(f"impacts[{i}] needs numeric at_frame, at_s and frames and a string type")
    bts = sh.get("beats", [])
    if not isinstance(bts, list):
        probs.append("beats must be a list")
    else:
        for i, b in enumerate(bts):
            if not (isinstance(b, dict) and _is_num(b.get("start_s")) and _is_num(b.get("end_s"))):
                probs.append(f"beats[{i}] needs numeric start_s and end_s")
    return probs


def _clean_episodes(episodes, entries):
    """Return episodes whose shots passed P0; each bad shot is reported and left out of the rules."""
    if not isinstance(episodes, list):
        entries.append(_entry("P0", "FAIL", f"episodes must be a list, got {type(episodes).__name__}"))
        return []
    good = []
    for i, ep in enumerate(episodes):
        if not isinstance(ep, dict):
            entries.append(_entry("P0", "FAIL", f"episode {i} must be an object"))
            continue
        key = ep.get("key")
        shots = ep.get("shots")
        if not isinstance(shots, list):
            entries.append(_entry("P0", "FAIL", "shots must be a list", episode=key))
            continue
        kept = []
        for j, sh in enumerate(shots):
            probs = _shot_problems(sh)
            sid = sh.get("id") if isinstance(sh, dict) else None
            for p in probs:
                entries.append(_entry("P0", "FAIL", f"shot {j}: {p}",
                                      shot=sid if isinstance(sid, str) else None, episode=key))
            if not probs:
                kept.append(sh)
        good.append({"key": key, "fps": ep.get("fps"), "shots": kept})
    return good


# ---------- P1: story and style pack ----------
def rule_p1(ctx):
    out = []
    if not ctx.story_exists:
        if ctx.story_path_exists is False:
            out.append(_entry("P1", "WARN", "stories/<slug>/story.json not found; story and pack checks skipped"))
        return out
    if ctx.story is None:
        out.append(_entry("P1", "FAIL", "stories/<slug>/story.json exists but could not be read"))
        return out
    if ctx.pack_junk:
        return out
    if ctx.pack is None:
        out.append(_entry("P1", "FAIL", "story.json exists but no style pack was loaded"))
        return out
    errors = validate_pack(ctx.pack)
    if errors:
        shown = "; ".join(errors[:5])
        if len(errors) > 5:
            shown += f"; +{len(errors) - 5} more"
        out.append(_entry("P1", "FAIL", f"style pack fails schema: {shown}"))
    if "style_pack" in ctx.story and "pack_id" in ctx.pack:
        sp, pid = ctx.story.get("style_pack"), ctx.pack.get("pack_id")
        if sp != pid:
            out.append(_entry("P1", "FAIL", f"story style_pack {sp!r} does not match pack_id {pid!r}"))
    return out


# ---------- P2: look block present and palette known ----------
def rule_p2(ctx):
    out = []
    pals = _palettes(ctx.pack) if ctx.pack is not None else None
    for ep, sh in _each_shot(ctx):
        lk = sh.get("look")
        if lk is None:
            # DECISION: look is optional until story.json exists (spec 3.4), then required.
            if ctx.story_exists:
                out.append(_shot_entry("P2", "FAIL", "look block missing (required once story.json exists)", ep, sh))
            continue
        if not isinstance(lk, dict):
            out.append(_shot_entry("P2", "FAIL", "look must be an object", ep, sh))
            continue
        if pals is None:
            continue
        pid = lk.get("palette_id")
        if not (isinstance(pid, str) and pid in pals):
            out.append(_shot_entry("P2", "FAIL", f"look.palette_id {pid!r} is not a palette in the pack", ep, sh))
    return out


# ---------- P3: act is a pack act ----------
def rule_p3(ctx):
    out = []
    if ctx.pack is None:
        return out
    acts = _as_dict(ctx.pack.get("acts"))
    for ep, sh in _each_shot(ctx):
        lk = _look(sh)
        if lk is None:
            continue
        act = lk.get("act")
        if not (isinstance(act, str) and act in acts):
            out.append(_shot_entry("P3", "FAIL", f"look.act {act!r} is not one of the pack acts", ep, sh))
    return out


# ---------- P4: cast ids listed in some palette ----------
def rule_p4(ctx):
    out = []
    if ctx.pack is None:
        return out
    known = set()
    for pal in _palettes(ctx.pack).values():
        for c in _as_list(_as_dict(pal).get("characters")):
            if isinstance(c, str):
                known.add(c)
    for ep, sh in _each_shot(ctx):
        for cid in _as_list(sh.get("cast_ids")):
            if not (isinstance(cid, str) and cid in known):
                out.append(_shot_entry("P4", "WARN", f"cast id {cid!r} is not listed in any palette's characters", ep, sh))
    return out


# ---------- P5: vfx colours, special laws, neon count ----------
def rule_p5(ctx):
    out = []
    if ctx.pack is None:
        return out
    max_neon = _as_dict(ctx.pack.get("frame_law")).get("max_neon_hues_per_shot")
    for ep, sh in _each_shot(ctx):
        lk = _look(sh)
        if lk is None:
            continue
        pal = _pal(ctx.pack, lk.get("palette_id"))
        if not pal:
            continue
        colours = _as_dict(pal.get("colors"))
        laws = [law for law in _as_list(pal.get("special_laws")) if isinstance(law, dict)]
        vfx = []
        for v in _as_list(lk.get("vfx")):
            if not isinstance(v, dict):
                out.append(_shot_entry("P5", "FAIL", "vfx entries must be objects", ep, sh))
                continue
            col = v.get("color")
            if not (isinstance(col, str) and col in colours):
                out.append(_shot_entry("P5", "FAIL", f"vfx colour {col!r} is not a colour name in palette "
                                       f"{lk.get('palette_id')!r}", ep, sh))
                continue
            vfx.append((col, _norm(v.get("role"))))
        for law in laws:
            if "color" in law and "only_roles" in law:
                allowed = {_norm(r) for r in _as_list(law["only_roles"]) if isinstance(r, str)}
                for col, role in vfx:
                    if col == law["color"] and role not in allowed:
                        out.append(_shot_entry("P5", "FAIL", f"colour {col!r} is under law {law.get('id')!r}; "
                                               f"role {role!r} is not in {sorted(allowed)}", ep, sh))
            if ("role" in law and "max_vfx" in law and isinstance(law["role"], str)
                    and _is_int(law["max_vfx"])):
                want = _norm(law["role"])
                count = sum(1 for _, r in vfx if r == want)
                if count > law["max_vfx"]:
                    out.append(_shot_entry("P5", "FAIL", f"{count} vfx with role {law['role']!r} exceed law "
                                           f"{law.get('id')!r} max {law['max_vfx']}", ep, sh))
        neon = []
        for col, _ in vfx:
            if _as_dict(colours.get(col)).get("neon") is True and col not in neon:
                neon.append(col)
        if _is_int(max_neon) and len(neon) > max_neon:
            out.append(_shot_entry("P5", "FAIL", f"{len(neon)} distinct neon colours ({', '.join(neon)}) exceed "
                                   f"frame_law.max_neon_hues_per_shot {max_neon}", ep, sh))
    return out


# ---------- P6: impact budget ----------
def rule_p6(ctx):
    out = []
    if ctx.pack is None or ctx.core is None:
        return out
    imp_cfg = _as_dict(ctx.core.get("impact"))
    vals = [imp_cfg.get(k) for k in ("window_s", "max_frames_per_window", "max_frames_per_entry", "min_gap_frames")]
    if not all(_is_num(v) for v in vals):
        return [_entry("P0", "FAIL", "core.impact needs numeric window_s, max_frames_per_window, "
                                     "max_frames_per_entry and min_gap_frames")]
    window_s, max_win, max_entry, min_gap = vals
    impc = _as_dict(ctx.pack.get("impact"))
    allowed = _as_list(impc.get("allowed_types"))
    type_max = _as_dict(impc.get("type_max_frames"))
    for ep in ctx.episodes:
        fps = _fps(ep, ctx.core)
        if fps is None:
            out.append(_entry("P0", "FAIL", "no usable fps for episode", episode=ep.get("key")))
            continue
        recs = []  # (at_frame, frames, type, shot id), episode-absolute, sorted below
        for sh in ep["shots"]:
            lk = _look(sh) or {}
            pal = _pal(ctx.pack, lk.get("palette_id"))
            laws = [law for law in _as_list(pal.get("special_laws")) if isinstance(law, dict)]
            beats = [b for b in _as_list(sh.get("beats")) if isinstance(b, dict)]
            tags = [t for t in _as_list(lk.get("tags")) if isinstance(t, str)]
            for im in _as_list(sh.get("impacts")):
                t, f, at = im["type"], im["frames"], im["at_frame"]
                where = f"impact {t!r} x{f} at frame {at:g}"
                recs.append((at, f, t, sh.get("id")))
                if t not in allowed:
                    out.append(_shot_entry("P6", "FAIL", f"{where}: type is not in pack allowed_types", ep, sh))
                limit = max_entry
                if t in type_max and _is_int(type_max[t]):
                    limit = min(limit, type_max[t])
                if f > limit:
                    out.append(_shot_entry("P6", "FAIL", f"{where}: exceeds the limit of {limit:g} frames", ep, sh))
                for law in laws:
                    if ("tag" in law and "only_impact_types" in law and isinstance(law["tag"], str)
                            and law["tag"] in tags and t not in _as_list(law["only_impact_types"])):
                        out.append(_shot_entry("P6", "FAIL", f"{where}: tag law {law.get('id')!r} allows only "
                                               f"{_as_list(law['only_impact_types'])} when tag {law['tag']!r} is set",
                                               ep, sh))
                    rv = law.get("reveal_impact")
                    if not isinstance(rv, dict):
                        continue
                    for b in beats:
                        if b.get("reveal") is not True or not (_is_num(b.get("start_s")) and _is_num(b.get("end_s"))):
                            continue
                        if b["start_s"] * fps <= at < b["end_s"] * fps:
                            if t != rv.get("type") or f != rv.get("frames"):
                                out.append(_shot_entry("P6", "FAIL", f"{where} falls in a reveal beat; time law "
                                                       f"{law.get('id')!r} requires {rv.get('type')!r} "
                                                       f"x{rv.get('frames')} frames", ep, sh))
                            break
        recs.sort(key=lambda r: r[0])
        win = window_s * fps
        over = []
        for r in recs:
            total = sum(x[1] for x in recs if r[0] <= x[0] < r[0] + win)
            if total > max_win:
                over.append((r, total))
        if over:
            r, total = over[0]
            out.append(_entry("P6", "FAIL", f"{total:g} impact frames in a {window_s:g} s window starting at "
                              f"{r[0] / fps:.2f} s (max {max_win:g}); {len(over)} window(s) over the limit",
                              shot=r[3], episode=ep.get("key")))
        # DECISION: spacing is end-to-start: next.at_frame - (prev.at_frame + prev.frames) >= min_gap_frames.
        for prev, nxt in zip(recs, recs[1:]):
            gap = nxt[0] - (prev[0] + prev[1])
            if gap < min_gap:
                out.append(_entry("P6", "FAIL", f"gap of {gap:g} frames between the end of the impact at frame "
                                  f"{prev[0] + prev[1]:g} and the next impact at frame {nxt[0]:g} (min {min_gap:g})",
                                  shot=nxt[3], episode=ep.get("key")))
    return out


# ---------- P7: hook on first shot only ----------
def rule_p7(ctx):
    out = []
    for ep in ctx.episodes:
        for idx, sh in enumerate(ep["shots"]):
            lk = _look(sh)
            if lk is None:
                continue
            hook = lk.get("hook")
            if idx != 0:
                if hook is not None:
                    out.append(_shot_entry("P7", "FAIL", "look.hook is only allowed on the first shot of an episode",
                                           ep, sh))
                continue
            if hook is None:
                out.append(_shot_entry("P7", "FAIL", "first shot of the episode has no look.hook", ep, sh))
                continue
            htype = hook.get("type") if isinstance(hook, dict) else None
            if not (isinstance(htype, str) and htype in HOOK_TYPES):
                out.append(_shot_entry("P7", "FAIL", f"look.hook.type {htype!r} is not one of H-01..H-06", ep, sh))
    return out


# ---------- P8: last shot is an outro on the first shot's palette ----------
def rule_p8(ctx):
    out = []
    if ctx.pack is None:
        return out
    acts = _as_dict(ctx.pack.get("acts"))
    for ep in ctx.episodes:
        shots = ep["shots"]
        if not shots:
            continue
        first, last = _look(shots[0]), _look(shots[-1])
        if first is None or last is None:
            continue
        act = last.get("act")
        role = _as_dict(acts.get(act)).get("role") if isinstance(act, str) else None
        if role != "outro":
            out.append(_shot_entry("P8", "WARN", f"last shot act {act!r} has role {role!r}, expected outro",
                                   ep, shots[-1]))
        if last.get("palette_id") != first.get("palette_id"):
            out.append(_shot_entry("P8", "WARN", f"last shot palette {last.get('palette_id')!r} differs from "
                                   f"first shot palette {first.get('palette_id')!r}", ep, shots[-1]))
    return out


# ---------- P9: forbidden words in prompt text ----------
def rule_p9(ctx):
    out = []
    if ctx.pack is None:
        return out
    pats = []
    for w in _as_list(ctx.pack.get("prompt_forbidden_words")):
        if isinstance(w, str) and w.strip():
            body = r"\s+".join(re.escape(p) for p in w.split())
            pats.append((w.strip(), re.compile(r"(?<!\w)" + body + r"(?!\w)", re.IGNORECASE)))
    for ep, sh in _each_shot(ctx):
        prompt = _text(sh, "prompt")
        if prompt is None:
            continue
        for word, pat in pats:
            if pat.search(prompt):
                out.append(_shot_entry("P9", "FAIL", f"prompt contains forbidden word {word!r}", ep, sh))
    return out


# ---------- P10: fonts exist, Devanagari set for hi/mr ----------
def _font_path(font_dir):
    if not isinstance(font_dir, (str, Path)) or not str(font_dir).strip():
        return None
    p = Path(font_dir)
    return p if p.is_absolute() else _REPO_ROOT / p


def _font_files(path):
    try:
        return [f.name.lower() for f in path.iterdir() if f.is_file()]
    except OSError:
        return []


def _family_found(name, files):
    family = re.sub(r"\s+", "", name.lower())
    for fn in files:
        if fn.endswith(FONT_EXTS) and re.sub(r"[\s_\-]", "", fn).startswith(family):
            return True
    return False


def rule_p10(ctx):
    out = []
    if ctx.pack is None:
        return out
    typ = _as_dict(ctx.pack.get("typography"))
    fdir = ctx.font_dir if ctx.font_dir is not None else typ.get("font_dir")
    families = []
    for role in FONT_ROLES:
        name = typ.get(role)
        if name is None:
            continue
        if isinstance(name, str) and name.strip():
            families.append((role, name.strip()))
        else:
            out.append(_entry("P10", "FAIL", f"typography.{role} must be a font family name or null"))
    if families:
        path = _font_path(fdir)
        if path is None:
            out.append(_entry("P10", "FAIL", "typography.font_dir is not set"))
        elif not path.is_dir():
            out.append(_entry("P10", "FAIL", f"font directory {fdir} not found"))
        else:
            files = _font_files(path)
            for role, name in families:
                if not _family_found(name, files):
                    out.append(_entry("P10", "FAIL", f"font family {name!r} (typography.{role}) not found in {fdir}"))
    lang = ctx.story.get("language") if isinstance(ctx.story, dict) else None
    if lang in ("hi", "mr"):
        dv = typ.get("subtitle_devanagari")
        if not (isinstance(dv, str) and dv.strip()):
            out.append(_entry("P10", "FAIL", f"story language {lang!r} needs typography.subtitle_devanagari"))
    return out


# ---------- P11: time_lock keywords in light/world text ----------
def rule_p11(ctx):
    out = []
    if ctx.pack is None:
        return out
    for ep, sh in _each_shot(ctx):
        lk = _look(sh)
        if lk is None:
            continue
        tl = _pal(ctx.pack, lk.get("palette_id")).get("time_lock")
        if not isinstance(tl, dict):
            continue
        kws = [k.strip().lower() for k in _as_list(tl.get("keywords")) if isinstance(k, str) and k.strip()]
        if not kws:
            continue
        light = (_text(sh, "light_world") or "").lower()
        if not any(k in light for k in kws):
            out.append(_shot_entry("P11", "WARN", f"light_world has none of the time_lock keywords {kws}", ep, sh))
    return out


# ---------- P12: accent_use limit per palette per episode ----------
def rule_p12(ctx):
    out = []
    if ctx.pack is None:
        return out
    for ep in ctx.episodes:
        counts = {}
        for sh in ep["shots"]:
            lk = _look(sh)
            if lk is None or lk.get("accent_use") is not True:
                continue
            pid = lk.get("palette_id")
            if isinstance(pid, str):
                counts[pid] = counts.get(pid, 0) + 1
        for pid, n in counts.items():
            lim = _pal(ctx.pack, pid).get("accent_max_per_episode")
            if _is_int(lim) and n > lim:
                out.append(_entry("P12", "FAIL", f"{n} shots use accent_use in palette {pid!r}; limit is {lim} "
                                  "per episode", episode=ep.get("key")))
    return out


# ---------- P13: look.phase is a colour_script phase ----------
def rule_p13(ctx):
    out = []
    if ctx.pack is None:
        return out
    cs = ctx.pack.get("colour_script")
    if not isinstance(cs, dict) or not isinstance(cs.get("phases"), list):
        return out
    ids = {ph["id"] for ph in cs["phases"] if isinstance(ph, dict) and isinstance(ph.get("id"), str)}
    for ep, sh in _each_shot(ctx):
        lk = _look(sh)
        if lk is None:
            continue
        ph = lk.get("phase")
        if ph is None:
            out.append(_shot_entry("P13", "FAIL", "look.phase missing (pack defines colour_script phases)", ep, sh))
        elif not (isinstance(ph, str) and ph in ids):
            out.append(_shot_entry("P13", "FAIL", f"look.phase {ph!r} is not a phase in colour_script.phases", ep, sh))
    return out


_RULES = (("P1", rule_p1), ("P2", rule_p2), ("P3", rule_p3), ("P4", rule_p4), ("P5", rule_p5),
          ("P6", rule_p6), ("P7", rule_p7), ("P8", rule_p8), ("P9", rule_p9), ("P10", rule_p10),
          ("P11", rule_p11), ("P12", rule_p12), ("P13", rule_p13))


def check_pack_rules(episodes, pack, core, story=None, story_path_exists=None, font_dir_override=None):
    entries = []
    try:
        pack_junk = pack is not None and not isinstance(pack, dict)
        if pack_junk:
            entries.append(_entry("P0", "FAIL", f"pack must be a JSON object or None, got {type(pack).__name__}"))
            pack = None
        if not isinstance(core, dict):
            entries.append(_entry("P0", "FAIL", f"core must be the dict from load_core(), got {type(core).__name__}"))
            core = None
        if story is not None and not isinstance(story, dict):
            entries.append(_entry("P0", "FAIL", f"story must be a JSON object or None, got {type(story).__name__}"))
            story = None
        font_dir = font_dir_override
        if font_dir is not None and not isinstance(font_dir, (str, Path)):
            entries.append(_entry("P0", "FAIL", "font_dir_override must be a path or None"))
            font_dir = None
        eps = _clean_episodes(episodes, entries)
        ctx = _Ctx(eps, pack, core, story, story_path_exists, font_dir, pack_junk)
    except Exception as exc:  # safety net: junk input must never raise
        entries.append(_entry("P0", "FAIL", f"pack rules could not be set up: {type(exc).__name__}: {exc}"))
        return entries
    for rid, fn in _RULES:
        try:
            entries.extend(fn(ctx))
        except Exception as exc:
            entries.append(_entry("P0", "FAIL", f"{rid} could not run: {type(exc).__name__}: {exc}"))
    return entries
