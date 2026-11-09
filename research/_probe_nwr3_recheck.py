"""NWR3 re-check probe (round 6): checks each NWR3 finding against the coder's fixes and looks for new defects.
Read-only: builds notes in memory, writes nothing."""
import copy
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
assert rep["ok"], rep["errors"]
tr = rep["tracks"]
voice = [tuple(w) for w in cue["voice"]["union"]]


def ov(n, a, b):
    return n["t_s"] < b - 1e-6 and n["t_s"] + n["dur_s"] > a + 1e-6


def rows(role, a, b):
    return [n for n in tr.get(role, []) if a - 1e-6 <= n["t_s"] < b]


print("== NWR3-1 piano/brass/horn under speech: max velocity ==")
for role in ("piano", "brass", "horn"):
    under = [n for n in tr.get(role, []) if any(ov(n, a, b) for a, b in voice)]
    print(role, "notes under speech", len(under), "max vel", max([n["vel"] for n in under], default=None))
print("bible piano busy:", bible["track_roles"]["piano"]["busy"], "| spec item 5 says busy true")

print("\n== NWR3-2 Shiva entry 48.0: drums and folk_perc onsets 48.0 to 50.7 ==")
print("drums/folk onsets", [(r, n["pitch"], n["t_s"], n["vel"]) for r in ("drums", "folk_perc")
                             for n in tr.get(r, []) if 48.0 <= n["t_s"] < 50.7])
shiva_end = max(n["t_s"] + n["dur_s"] for n in tr["brass"] if n["t_s"] >= 48.0 and n["pitch"] in (38, 39, 62, 63))
print("SHIVA brass last end", round(shiva_end, 6))
print("first drum kick after 48.0:", [n for n in tr["drums"] if n["pitch"] == 36 and n["t_s"] >= 48.0][:2])
print("first drum of any kind after 48.0:", min((n["t_s"] for r in ("drums", "folk_perc") for n in tr.get(r, [])
                                                 if n["t_s"] >= 48.0), default=None))

print("\n== NWR3-2 / question 2: loudest attacks in the reel (vel >= 95) ==")
loud = sorted({(n["t_s"], r, n["pitch"], n["vel"]) for r, rs in tr.items() for n in rs if n["vel"] >= 95})
for x in loud:
    print("  ", x)

print("\n== NWR3-5c curse (KAMADEVA 56.0, pad, transform 62 65 69 72 69 at half step) ==")
step = 60 / 176 * 2
want = [(round(56.0 + k * step, 4), p) for k, p in enumerate((62, 65, 69, 72, 69))]
print("expected onsets", want)
pad_rows = [n for n in tr["pad"] if n["t_s"] < 60.0 and n["t_s"] + n["dur_s"] > 55.5]
print("pad notes 55.5-60.0:", pad_rows)
for t, p in want:
    hit = [n for n in pad_rows if abs(n["t_s"] - t) < 1e-3 and n["pitch"] == p]
    print(f"  onset {t} pitch {p}: {'AUDIBLE ATTACK' if hit else 'NO ATTACK (merged into base pad)'}")

print("\n== NWR3-2 side effect: base pad 62/69 starting 48.0 (merge takes max velocity of the curse) ==")
print([n for n in tr["pad"] if n["t_s"] == 48.0])
print("pad velocity in section 48-64 without the curse (section vel 84):")
plan2 = copy.deepcopy(T.REEL_PLAN)
plan2["events"] = [e for e in plan2["events"] if not (e.get("theme") == "KAMADEVA" and e.get("at_s") == 56.0)]
rep2 = nw.write_notes(plan2, cue, bible)
print([n for n in rep2["tracks"]["pad"] if n["t_s"] == 48.0])

print("\n== NWR3-6 11.0 s cut: swell ends on the cut frame ==")
print([n for n in tr["pad"] if n["pitch"] == 64 and 9.0 < n["t_s"] < 12.0])

print("\n== NWR3-5a heartbeat 6-11 s kicks ==")
print([n["t_s"] for n in tr["drums"] if n["pitch"] == 36 and 6.0 <= n["t_s"] < 11.0])

print("\n== NWR3-5b chaos entry 43.2 (lead, transform 74 75 81 84 80) ==")
print([(n["t_s"], n["pitch"], n["vel"]) for n in tr["lead"] if 43.1 <= n["t_s"] < 44.3])

print("\n== NWR3-8 horn: SHIVA theme on horn at 2.0 s under voice ==")
p3 = copy.deepcopy(T.REEL_PLAN)
p3["events"].append({"at_s": 2.0, "type": "theme_entry", "theme": "SHIVA", "role": "horn", "feel": "normal"})
rep3 = nw.write_notes(p3, cue, bible)
print("horn notes 0.5-3.5 s:", [(n["t_s"], n["pitch"], n["vel"]) for n in rep3["tracks"].get("horn", [])
                                 if 0.5 <= n["t_s"] < 3.5])

print("\n== NWR3-9 MIDI channel per role ==")
print(nw.MIDI_CHANNEL)
print("channels used by roles with notes:", {r: nw.MIDI_CHANNEL[r] for r in tr})
print("channel 9 shared with non-drum role:", [r for r, c in nw.MIDI_CHANNEL.items() if c == 9 and r != "drums"])

print("\n== NWR3-7 tempo_map genre wording in the docstring ==")
src = (ROOT / "score" / "note_writer.py").read_text(encoding="utf-8").splitlines()
print([l for l in src if "tempo_map" in l])
print("note_writer reads bible tempo_map:", any("bible" in l and "tempo_map" in l and "[" in l for l in src))

print("\n== NWR3-10 test docstring ==")
tsrc = T.__file__
print(open(tsrc, encoding="utf-8").read().split('"""')[1][:400])
