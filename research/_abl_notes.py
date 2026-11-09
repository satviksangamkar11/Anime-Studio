import json, sys, os
ROOT = "D:/aai work/anime_studio_merge"
sys.path.insert(0, ROOT)
from score.note_writer import write_notes

EP = os.path.join(ROOT, "stories/kalika_puran_bhag1/pack_opus_high_20261108_v4_deva/score/ep1")

def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

plan = load(os.path.join(EP, "score_plan.json"))
cue = load(os.path.join(EP, "cue_sheet.json"))
bible = load(os.path.join(ROOT, "stories/kalika_puran_bhag1/music_bible.json"))

res = write_notes(plan, cue, bible)
print("ok:", res.get("ok"))
print("errors:", res.get("errors"))
print("warnings:", len(res.get("warnings", [])))
tracks = res.get("tracks", {})
total = 0
out = {}
for role, notes in tracks.items():
    out[role] = [{"pitch": n["pitch"], "start_time": n["t_s"], "duration": n["dur_s"], "velocity": n["vel"]} for n in notes]
    total += len(notes)
    print(f"{role}: {len(notes)} notes")
print("total:", total)
with open(os.path.join(ROOT, "research/_abl_notes_reel1.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1)
