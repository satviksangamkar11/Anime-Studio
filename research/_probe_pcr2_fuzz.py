"""PCR2 probe: deep random mutation of plan, cue sheet and bible; counts CHECK_CRASH. Read-only."""
import copy, json, random, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from score import plan_check as pc
from score.tests import test_plan_check as T

cue0 = json.load(open(T.CUE_PATH, encoding="utf-8"))
bible0 = json.load(open(T.BIBLE_PATH, encoding="utf-8"))
JUNK = [None, "x", "", [], {}, True, False, -1, 0, 0.45, 1e9, float("nan"), float("inf"), [1, 2], {"a": 1},
        ["hypnotic_techno"], {"SHOT-004": "x"}, ["x"], 124, "low", "KALI", 0.0]

def paths(obj, prefix=(), depth=0, out=None):
    if out is None: out = []
    if depth > 6: return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append(prefix + (k,)); paths(v, prefix + (k,), depth + 1, out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.append(prefix + (i,)); paths(v, prefix + (i,), depth + 1, out)
    return out

def setp(root, path, value):
    cur = root
    for k in path[:-1]:
        cur = cur[k]
    cur[path[-1]] = value

def delp(root, path):
    cur = root
    for k in path[:-1]:
        cur = cur[k]
    if isinstance(cur, dict): cur.pop(path[-1], None)

rng = random.Random(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
crashes = []
N = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
targets = {"plan": T.GOOD, "cue": cue0, "bible": bible0}
allpaths = {k: paths(v) for k, v in targets.items()}
for n in range(N):
    which = rng.choice(["plan", "plan", "cue", "bible"])
    plan = copy.deepcopy(T.GOOD); cue = copy.deepcopy(cue0); bible = copy.deepcopy(bible0)
    objs = {"plan": plan, "cue": cue, "bible": bible}
    muts = []
    for _ in range(rng.randint(1, 3)):
        w = rng.choice(["plan", "cue", "bible"]) if which != "plan" or rng.random() < 0.3 else "plan"
        ps = paths(objs[w])
        if not ps: continue
        p = rng.choice(ps)
        if rng.random() < 0.15:
            delp(objs[w], p); muts.append((w, p, "DEL"))
        else:
            v = rng.choice(JUNK); setp(objs[w], p, copy.deepcopy(v)); muts.append((w, p, v))
    r = pc.check_plan(plan, cue, bible)
    if "CHECK_CRASH" in {e["code"] for e in r["errors"]}:
        crash = [e for e in r["errors"] if e["code"] == "CHECK_CRASH"][0]
        crashes.append((crash["message"], muts))
print("cases", N, "crashes", len(crashes))
seen = {}
for msg, muts in crashes:
    key = msg[:90]
    if key not in seen:
        seen[key] = muts
for k, m in list(seen.items())[:12]:
    print("CRASH:", k)
    print("   mutations:", m[:3])
