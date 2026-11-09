"""PCR2 probe 3: voice-window rule for non-busy roles (brass, horn, pad, drone). Read-only."""
import copy, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from score import plan_check as pc
from score.tests import test_plan_check as T
cue = json.load(open(T.CUE_PATH, encoding="utf-8"))
bible = json.load(open(T.BIBLE_PATH, encoding="utf-8"))
def run(name, p):
    r = pc.check_plan(p, cue, bible)
    print(f"{name}: ok={r['ok']} errors={sorted({e['code'] for e in r['errors']})}")
p = copy.deepcopy(T.GOOD); p["events"].append({"at_s": 20.0, "type": "theme_entry", "theme": "SHIVA", "role": "brass", "feel": "half"})
run("V1 SHIVA theme on brass at 20.0 (inside voice, bright)", p)
p = copy.deepcopy(T.GOOD); p["events"].append({"at_s": 20.0, "type": "theme_entry", "theme": "KALI", "role": "pad", "feel": "normal"})
run("V2 KALI theme on pad at 20.0 (inside voice)", p)
p = copy.deepcopy(T.GOOD); p["events"].append({"at_s": 20.0, "type": "drop", "role": "horn"})
run("V3 drop event on horn at 20.0 (inside voice)", p)
p = copy.deepcopy(T.GOOD); p["events"].append({"at_s": 20.0, "type": "theme_entry", "theme": "MAIN", "role": "vocal", "feel": "normal"})
run("V4 MAIN theme on vocal at 20.0 (control, busy role)", p)
p = copy.deepcopy(T.GOOD); p["events"].append({"at_s": 20.0, "type": "theme_entry", "theme": "MAIN", "role": "brass", "feel": "normal"})
run("V5 MAIN theme on brass at 20.0 (inside voice, not a god)", p)
p = copy.deepcopy(T.GOOD); p["events"].append({"at_s": 20.0, "type": "theme_entry", "theme": "MAIN", "role": "pad", "feel": "normal"})
run("V6 MAIN theme on pad at 20.0 (inside voice, not a god)", p)
p = copy.deepcopy(T.GOOD); p["events"].append({"at_s": 20.0, "type": "hit", "band": "bright", "preceded_by_dropout_s": 0.4, "role": "horn"})
run("V7 bright hit on horn at 20.0 (inside voice)", p)
