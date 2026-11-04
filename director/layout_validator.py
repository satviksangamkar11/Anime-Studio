"""Cross-shot layout rules for rich shots (SPEC_v2.2.md): check_layout(shots) -> list of problem strings ([] when clean).
Rules: cut_in and cut_out present; end_state of shot N and start_state of shot N+1 non-empty; a cast member's facing
flipping left<->right between consecutive shots of one scene needs a cut_in saying 'reverse' or 'crossing the line'
(180-degree rule); two cast members on opposite screen sides must have opposite facing (eyeline)."""

REVERSE_WORDS = ("reverse", "crossing the line")


def _eyeline(s):
    sid = s.get("id", "?")
    cast = [c for c in s.get("cast") or [] if c.get("screen") in ("left", "right") and c.get("facing") in ("left", "right")]
    out = []
    for x in cast:
        for y in cast:
            if x["screen"] == "left" and y["screen"] == "right" and x["facing"] == y["facing"]:
                out.append(f"{sid}: eyeline, {x['id']} (left) and {y['id']} (right) face the same way ({x['facing']})")
    return out


def check_layout(shots):
    out = []
    for s in shots:
        sid = s.get("id", "?")
        for k in ("cut_in", "cut_out"):
            if not s.get(k):
                out.append(f"{sid}: missing {k}")
        out += _eyeline(s)
    for a, b in zip(shots, shots[1:]):
        ida, idb = a.get("id", "?"), b.get("id", "?")
        if not a.get("end_state"):
            out.append(f"{ida}: missing end_state (hand-off to {idb})")
        if not b.get("start_state"):
            out.append(f"{idb}: missing start_state (hand-off from {ida})")
        if a.get("scene") != b.get("scene"):
            continue
        cut = str(b.get("cut_in") or "").lower()
        before = {c.get("id"): c.get("facing") for c in a.get("cast") or []}
        for c in b.get("cast") or []:
            old, new = before.get(c.get("id")), c.get("facing")
            if {old, new} == {"left", "right"} and not any(w in cut for w in REVERSE_WORDS):
                out.append(f"{idb}: {c['id']} facing flips {old} -> {new} from {ida} without a reverse or "
                           f"crossing-the-line cut_in (180-degree warning)")
    return out
