"""PCR2 probe: scenario plans against the real reel 1 cue sheet and bible. Read-only; prints results."""
import copy, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from score import plan_check as pc
from score.tests import test_plan_check as T

cue = json.load(open(T.CUE_PATH, encoding="utf-8"))
bible = json.load(open(T.BIBLE_PATH, encoding="utf-8"))

def show(name, plan, b=bible):
    r = pc.check_plan(plan, cue, b)
    print(f"{name}: ok={r['ok']} errors={sorted({e['code'] for e in r['errors']})} warnings={sorted({w['code'] for w in r['warnings']})}")
    for e in r["errors"]:
        if e["code"] in ("CHECK_CRASH",):
            print("   ", e)
    return r

base = copy.deepcopy(T.GOOD)
show("S0 GOOD baseline", base)

# S1: one BUILD section 0-70 at 128 hypnotic (no act boundaries at all)
p = copy.deepcopy(T.GOOD)
p["sections"] = [dict(p["sections"][1], start_s=0.0, end_s=70.0, why="whole reel one section")]
p["events"] = [e for e in p["events"] if not (e["type"] == "theme_entry" and e["theme"] == "KALI")]
show("S1 one 128 BUILD section over whole reel", p)

# S2: the DROP region (34-64, bible 176 drum_and_bass) relabelled OUTRO at 60 unplugged; SHIVA at 48 now in a slow section
p = copy.deepcopy(T.GOOD)
p["sections"] = p["sections"][:4] + [dict(p["sections"][4], start_s=34.0, end_s=70.0, act="OUTRO", bpm=60,
                                          genre="unplugged", feel="normal", why="relabelled")]
# drop the 6th/7th old sections
show("S2 DROP region relabelled OUTRO 60, Shiva in slow section, no dropout", p)

# S3: DROP region relabelled BUILD at 128 hypnotic (128 is NOT a DROP candidate in the cue sheet)
p = copy.deepcopy(T.GOOD)
for k in (4, 5):
    p["sections"][k]["act"] = "BUILD"
    p["sections"][k]["bpm"] = 128
    p["sections"][k]["genre"] = "hypnotic_techno"
p["sections"][5]["feel"] = "normal"
show("S3 DROP sections relabelled BUILD 128 hypnotic", p)

# S4: act_change cut (34) transition bed_continues (same-act palette) instead of act_change
p = copy.deepcopy(T.GOOD)
p["cuts"][4]["transition"] = "bed_continues"
show("S4 act_change cut at 34 with bed_continues", p)

# S5: section missing intensity, density_per_beat, harmony (SKILL lists them)
p = copy.deepcopy(T.GOOD)
for s in p["sections"]:
    s.pop("intensity", None); s.pop("density_per_beat", None); s.pop("harmony", None)
show("S5 sections without harmony/density/intensity", p)

# S6: shot boundary where nothing changes (48 cut: same roles, same genre, same bpm, no event)
p = copy.deepcopy(T.GOOD)
p["sections"][5]["end_s"] = 56.0
p["sections"].insert(6, dict(p["sections"][5], start_s=56.0, end_s=64.0))
p["sections"][5]["end_s"] = 48.0
p["sections"][5]["start_s"] = 34.0
p["sections"][5]["end_s"] = 48.0
show("S6 info only (not used)", p)  # placeholder, replaced below
p = copy.deepcopy(T.GOOD)
p["sections"][6]["roles_on"] = list(p["sections"][5]["roles_on"])  # no-op
p["sections"][6]["genre"] = p["sections"][5]["genre"]
p["sections"][6]["feel"] = p["sections"][5]["feel"]
show("S6b shot 009 is identical to 008 (nothing new enters or leaves), 56 cut plain", p)

# S7: bible shot_genres with a list value (malformed bible)
b = copy.deepcopy(bible)
b["tempo_map"]["shot_genres"]["SHOT-003"] = ["hypnotic_techno"]
show("S7 bible shot_genres list value (malformed bible)", copy.deepcopy(T.GOOD), b)

# S8: end sting before last_voice_end_s (SKILL names last_voice_end_s), checker uses last_speech_end_s
c2 = copy.deepcopy(cue)
c2["retention"]["last_voice_end_s"] = 70.0
p = copy.deepcopy(T.GOOD)
p["events"][-1]["at_s"] = 69.9
r = pc.check_plan(p, c2, bible)
print("S8 sting 69.9 bright, last_voice_end_s=70.0, last_speech_end_s=69.846:", "ok=", r["ok"], sorted({e["code"] for e in r["errors"]}))

# S9: SKILL example end_sting without tail_s
p = copy.deepcopy(T.GOOD)
del p["events"][-1]["tail_s"]
show("S9 end_sting without tail_s (SKILL example form)", p)

# S10: GOD role case: hits with role Hits next to Shiva
p = copy.deepcopy(T.GOOD)
p["events"].append({"at_s": 47.5, "type": "hit", "preceded_by_dropout_s": 0.4, "role": "Hits", "band": "bright"})
show("S10 bright hit role 'Hits' 0.5 s before Shiva", p)
