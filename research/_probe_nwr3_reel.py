"""NWR3 review probe: build the real reel notes from the test fixture and inspect them. Read-only, writes nothing
except a scratch MIDI file in the system temp folder given on the command line."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path("D:/aai work/anime_studio_merge")
sys.path.insert(0, str(ROOT))
from score import note_writer as nw  # noqa: E402

spec = importlib.util.spec_from_file_location("tnw", ROOT / "score" / "tests" / "test_note_writer.py")
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)

bible = json.loads(T.BIBLE.read_text(encoding="utf-8"))
cue = json.loads(T.CUE.read_text(encoding="utf-8"))
rep = nw.write_notes(T.REEL_PLAN, cue, bible)
print("ok", rep["ok"], "errors", rep["errors"])
print("warnings", sorted({(w["code"]) for w in rep["warnings"]}))
print("per_role", rep["stats"]["per_role"])
voice = [tuple(w) for w in cue["voice"]["union"]]
GATED = nw.busy_roles(bible) | nw.GATED_EXTRA
print("gated roles", sorted(GATED))


def overl(n, a, b):
    return n["t_s"] < b - 1e-6 and n["t_s"] + n["dur_s"] > a + 1e-6


print("\n== voice windows: notes sounding under speech ==")
viol_gated, viol_ungated = [], []
soft_vel = {}
for role, rows in rep["tracks"].items():
    for n in rows:
        for a, b in voice:
            if not overl(n, a, b):
                continue
            exempt = role in nw.LOW_OK and n["pitch"] <= nw.LOW_MAX
            if role in GATED and not exempt:
                viol_gated.append((role, n, (a, b)))
            elif role not in GATED and role not in ("drone", "pad", "bass") and n["pitch"] > nw.LOW_MAX:
                viol_ungated.append((role, n, (a, b)))
            if role in nw.SOFT_ROLES:
                soft_vel[role] = max(soft_vel.get(role, 0), n["vel"])
print("gated violations:", len(viol_gated), viol_gated[:5])
print("ungated non-drone/pad/bass roles above 50 under speech:")
for r, n, w in viol_ungated:
    print("  ", r, n, "window", w)
print("max velocity of drums/folk_perc under speech:", soft_vel)

print("\n== drop-outs: notes sounding inside a drop-out ==")
for ev in T.REEL_PLAN["events"]:
    d = ev.get("preceded_by_dropout_s", 0)
    if not d:
        continue
    a, b = ev["at_s"] - d, ev["at_s"]
    hits = [(r, n) for r, rows in rep["tracks"].items() for n in rows if overl(n, a, b)]
    print(f"drop {a:.3f}-{b:.3f} ({ev['type']} {ev.get('theme', '')}): {len(hits)} notes", hits[:3])

print("\n== bass root and mid harmonic pairs ==")
roots = [n["t_s"] for n in rep["tracks"].get("bass", []) if n["pitch"] == 38]
mids = {n["t_s"] for n in rep["tracks"].get("bass", []) if n["pitch"] == 57}
print("roots", len(roots), "mids", len(mids), "roots without mid", [t for t in roots if t not in mids][:5])

print("\n== theme entries: every planned note present (pitch at its time) ==")
sections = T.REEL_PLAN["sections"]
for ev in T.REEL_PLAN["events"]:
    if ev["type"] != "theme_entry":
        continue
    sec = next(s for s in sections if s["start_s"] <= ev["at_s"] < s["end_s"])
    step = 60.0 / sec["bpm"] * nw.FEEL_STEP[ev["feel"]]
    pitches = nw._theme_pitches(bible["themes"][ev["theme"]]["degrees"])
    got = []
    for k, p in enumerate(pitches):
        t = round(ev["at_s"] + k * step, 6)
        found = [n for n in rep["tracks"].get(ev["role"], []) if abs(n["t_s"] - t) < 1e-5 and n["pitch"] == p]
        got.append((t, p, bool(found)))
    missing = [g for g in got if not g[2]]
    print(f"{ev['theme']:9s} at {ev['at_s']:6.2f} role={ev['role']:6s} feel={ev['feel']:6s} missing={missing}")

print("\n== drum onsets per section ==")
for sec in sections:
    s, e = sec["start_s"], sec["end_s"]
    cnt = {}
    for role in ("drums", "folk_perc"):
        for n in rep["tracks"].get(role, []):
            if s <= n["t_s"] < e:
                cnt.setdefault((role, n["pitch"]), []).append(n["t_s"])
    desc = {k: (len(v), [round(x, 3) for x in v[:4]]) for k, v in sorted(cnt.items())}
    print(f"{sec['start_s']:5.1f}-{sec['end_s']:5.1f} {sec['genre']:17s} bpm={sec['bpm']}", desc)

print("\n== 34.0 downbeat, all roles 33.8-34.6 ==")
for r, rows in rep["tracks"].items():
    for n in rows:
        if 33.8 <= n["t_s"] < 34.6:
            print("  ", r, n)

print("\n== 48.0 Shiva entry, all roles 47.5-50.8 ==")
for r, rows in sorted(rep["tracks"].items()):
    for n in rows:
        if 47.5 <= n["t_s"] < 50.8:
            print("  ", r, n)

print("\n== 60.0 hit, all roles 59.5-60.5 ==")
for r, rows in rep["tracks"].items():
    for n in rows:
        if 59.5 <= n["t_s"] < 60.5:
            print("  ", r, n)

print("\n== end: all notes starting 68.0 or later ==")
for r, rows in rep["tracks"].items():
    for n in rows:
        if n["t_s"] >= 68.0 or n["t_s"] + n["dur_s"] > 69.8:
            if n["t_s"] >= 68.0:
                print("  ", r, n, "end", round(n["t_s"] + n["dur_s"], 6))
print("max note end", max(n["t_s"] + n["dur_s"] for rows in rep["tracks"].values() for n in rows))

print("\n== determinism ==")
a = json.dumps(nw.write_notes(T.REEL_PLAN, cue, bible), sort_keys=True)
b = json.dumps(nw.write_notes(T.REEL_PLAN, cue, bible), sort_keys=True)
print("identical:", a == b)

print("\n== MIDI round trip ==")
out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("nwr3_reel.mid")
mr = nw.write_midi(rep["tracks"], out, markers=rep["markers"])
print("write ok", mr["ok"], "notes", mr["notes"], "errors", mr["errors"])
fmt, ntrk, div, tracks = T._parse_midi(out.read_bytes())
print("format", fmt, "tracks", ntrk, "ppq", div)
names = [t["name"] for t in tracks]
print("track names", names)
parsed_notes = sum(len(t["notes"]) for t in tracks)
written = sum(len(v) for v in rep["tracks"].values())
print("parsed notes", parsed_notes, "written", written)
markers = [m for t in tracks for m in t["markers"]]
print("markers", [m[1] for m in markers])
bad = []
for t, role in zip(tracks[1:], rep["tracks"].keys()):
    exp = sorted((round(n["t_s"] * 480), max(round(n["t_s"] * 480) + 1, round((n["t_s"] + n["dur_s"]) * 480)), n["pitch"])
                 for n in rep["tracks"][role])
    got = sorted(t["notes"])
    if exp != got:
        bad.append((role, len(exp), len(got)))
print("tracks with pitch/tick mismatch:", bad)
print("tempo", tracks[0]["tempo"])
