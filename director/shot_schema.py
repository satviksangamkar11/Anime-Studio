"""Rich shot contract (SPEC_v2.2.md), one shot per dict.
  validate_shot(shot, bible_ids=None) -> list of problem strings ([] when clean)
  validate_shots(shots, bible_ids=None) -> the same plus unique ids and episode numbers
Warnings start with 'WARN:'. Beats cover 0..seconds with a 0.05 s tolerance.
bible_ids: set of known CHAR/PROP/ENV ids; when given, unknown cast, prop and set ids are reported."""
from h3_director import frames_for

TOL = 0.05
REQUIRED = ("id", "scene", "mode", "seconds", "aspect", "purpose", "cast", "props", "set", "beats",
            "camera", "layers", "light", "compositing", "keyframes", "sound")


def validate_shot(shot, bible_ids=None):
    sid = shot.get("id", "?")
    out = []
    for k in REQUIRED:
        if shot.get(k) in (None, ""):
            out.append(f"{sid}: missing {k}")
    secs = shot.get("seconds")
    secs_ok = isinstance(secs, (int, float)) and not isinstance(secs, bool) and secs > 0
    if secs is not None and not secs_ok:
        out.append(f"{sid}: seconds must be a positive number")
    elif secs_ok:
        try:
            frames_for(secs)
        except ValueError as e:
            out.append(f"{sid}: {e}")
    mode = shot.get("mode")
    if mode not in (None, "fl2va", "ref2va"):
        out.append(f"{sid}: mode {mode!r} must be fl2va or ref2va")
    if mode == "ref2va" and not (shot.get("refs") and shot.get("subjects")):
        out.append(f"{sid}: ref2va needs refs and subjects")
    if mode == "fl2va" and not (shot.get("keyframes") or {}).get("start"):
        out.append(f"{sid}: fl2va needs keyframes.start")

    beats = shot.get("beats") or []
    prev = 0.0
    for i, b in enumerate(beats, 1):
        t = b.get("t")
        ok = isinstance(t, list) and len(t) == 2 and all(isinstance(x, (int, float)) for x in t) and t[0] < t[1]
        if not ok:
            out.append(f"{sid}: beat {i} needs t [start, end] with start < end")
            continue
        if abs(t[0] - prev) > TOL:
            out.append(f"{sid}: beat {i} starts at {t[0]} after {prev} ({'gap' if t[0] > prev else 'overlap'})")
        prev = t[1]
        if not b.get("acting"):
            out.append(f"{sid}: beat {i} has no acting")
        if b.get("hold") and not (b.get("bhava") or b.get("purpose")):
            out.append(f"{sid}: hold beat {i} has no emotional purpose")
    if secs_ok and not beats:
        out.append(f"{sid}: no beats")
    elif beats and secs_ok and abs(prev - secs) > TOL:
        out.append(f"{sid}: beats end at {prev}, shot is {secs} s")

    primary = sum(1 for b in beats if b.get("primary") is True)
    if primary > 1:
        out.append(f"{sid}: {primary} beats marked primary, at most one")
    elif beats and primary == 0:
        out.append(f"{sid}: WARN: no beat marked primary")

    if bible_ids is not None:
        ids = [c.get("id") for c in shot.get("cast") or []] + [p.get("id") for p in shot.get("props") or []]
        ids.append(shot.get("set"))
        for x in ids:
            if x and x not in bible_ids:
                out.append(f"{sid}: unknown id {x} (not in style bible)")
    return out


def validate_shots(shots, bible_ids=None):
    out = []
    ids = [s.get("id") for s in shots]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        out.append(f"{dup}: duplicate id")
    for s in shots:
        if s.get("episode") in (None, ""):
            out.append(f"{s.get('id', '?')}: missing episode")
        out += validate_shot(s, bible_ids)
    return out
