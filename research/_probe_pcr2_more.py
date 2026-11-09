"""PCR2 probe 2: more scenario checks. Read-only."""
import copy, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from score import plan_check as pc
from score.tests import test_plan_check as T
cue = json.load(open(T.CUE_PATH, encoding="utf-8"))
bible = json.load(open(T.BIBLE_PATH, encoding="utf-8"))

def run(name, plan, c=cue, b=bible):
    r = pc.check_plan(plan, c, b)
    print(f"{name}: ok={r['ok']} errors={sorted({e['code'] for e in r['errors']})} warnings={sorted({w['code'] for w in r['warnings']})}")
    return r

# S6b clean: split 48-64 into 48-56 and 56-64, identical section content (nothing new enters or leaves at 56)
p = copy.deepcopy(T.GOOD)
s = p["sections"][5]
s2 = copy.deepcopy(s); s2["start_s"] = 56.0; s2["end_s"] = 64.0; s2["why"] = "same"
s["end_s"] = 56.0
p["sections"].insert(6, s2)
p["cuts"][7]["transition"] = "theme_handover"
run("S6c shot 008->009 boundary: nothing changes, plain cut", p)

# S7b: malformed bible, shot_genres list on the shot the section overlaps (section 18-26 genre melodic != hypnotic)
b = copy.deepcopy(bible)
b["tempo_map"]["shot_genres"]["SHOT-004"] = ["melodic_techno"]
run("S7b bible shot_genres list on SHOT-004 (malformed bible)", copy.deepcopy(T.GOOD), b=b)

# S13: in_voice impact (cue) paired with a bright hit, hit outside union
c = copy.deepcopy(cue)
for shot in c["shots"]:
    for imp in shot["impacts"]:
        if abs(imp["at_s"] - 43.083) < 1e-6:
            imp["in_voice"] = True
run("S13 cue impact 43.083 marked in_voice, plan hit bright", copy.deepcopy(T.GOOD), c=c)

# S19: end sting runs past the picture: at 69.95 with tail 0.45 (ends 70.40 > total 70.0)
p = copy.deepcopy(T.GOOD)
p["events"][-1]["at_s"] = 69.95
p["events"][-1]["band"] = "low"
p["events"][-1]["tail_s"] = 0.45
run("S19 end sting 69.95 + tail 0.45 runs past total_s 70.0", p)

# S20: busy role section listed with voice_gated true but a busy 'drums' event in voice (role-less event type hit excluded)
p = copy.deepcopy(T.GOOD)
p["events"].append({"at_s": 20.0, "type": "theme_entry", "theme": "KALI", "role": "drums", "feel": "normal"})
run("S20 theme_entry on busy role 'drums' inside voice (20.0)", p)

# S21: plan cut duplicate of a paired cut with 'none' transition; check vocab only
p = copy.deepcopy(T.GOOD)
p["cuts"].append({"at_s": 26.0, "transition": "none"})
run("S21 extra plan cut at 26.0 with transition none", p)

# S22: god entry exactly at a section start where the section below is slow (34: DROP begins; SHIVA-like at 34 in 60 section)
p = copy.deepcopy(T.GOOD)
p["events"].append({"at_s": 0.0, "type": "theme_entry", "theme": "SHIVA", "role": "brass", "feel": "normal"})
run("S22 SHIVA entry at 0.0 (slow HOOK section), no dropout, feel normal", p)
