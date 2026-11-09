"""NWR3 review probe: fuzz malformed plans, cues and bibles. Each case runs in its own subprocess with a time limit,
so a hang shows up as TIMEOUT instead of freezing the review. Read-only: writes no file."""
import subprocess
import sys

CASE_SRC = r'''
import importlib.util, json, sys, copy, time
from pathlib import Path
ROOT = Path("D:/aai work/anime_studio_merge")
sys.path.insert(0, str(ROOT))
from score import note_writer as nw
spec = importlib.util.spec_from_file_location("tnw", ROOT / "score" / "tests" / "test_note_writer.py")
T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)
bible = json.loads(T.BIBLE.read_text(encoding="utf-8"))
cue = json.loads(T.CUE.read_text(encoding="utf-8"))
plan = copy.deepcopy(T.REEL_PLAN)
exec(sys.argv[1])
t0 = time.time()
rep = nw.write_notes(plan, cue, bible)
print(json.dumps({"ok": rep["ok"], "codes": sorted({e["code"] for e in rep["errors"]}),
                  "notes": sum(len(v) for v in rep["tracks"].values()), "secs": round(time.time() - t0, 2)}))
'''

CASES = {
    "bpm_1e6": "plan['sections'][0]['bpm'] = 1e6",
    "bpm_1e9": "plan['sections'][0]['bpm'] = 1e9",
    "density_1e9": "plan['sections'][1]['density_per_beat'] = [1e9, 1e9]",
    "bpm_1e300": "plan['sections'][0]['bpm'] = 1e300",
    "bpm_bool": "plan['sections'][0]['bpm'] = True",
    "cue_cuts_int": "cue['cuts'] = 5",
    "cue_shots_end_before_start": "cue['shots'][1]['end_s'] = 2.0",
    "bible_quiet_str": "bible['quiet_moment'] = 'x'",
    "bible_theme_degrees_none": "bible['themes']['MAIN']['degrees'] = None",
    "bible_theme_roles_str": "bible['themes']['MAIN']['roles'] = 'lead'",
    "plan_events_dict": "plan['events'] = {'a': 1}",
    "section_roles_none": "plan['sections'][0]['roles_on'] = None",
    "plan_at_nan": "plan['events'][1]['at_s'] = float('nan')",
    "plan_theme_entry_no_role": "plan['events'].append({'at_s': 1.0, 'type': 'theme_entry', 'theme': 'KALI'})",
    "sonic_length_huge": "bible['sonic_logo']['length_s'] = 1e12",
    "hit_negative_drop": "plan['events'][5]['preceded_by_dropout_s'] = -1",
    "end_sting_at_70": "plan['events'][-1]['at_s'] = 70.0",
    "auto_points_bool": "plan['automation'] = [{'role': 'pad', 'macro': 1, 'points': [[True, 0.5]]}]",
}


def run_case(snippet):
    try:
        p = subprocess.run([sys.executable, "-c", CASE_SRC, snippet], capture_output=True, text=True, timeout=25)
    except subprocess.TimeoutExpired:
        return "TIMEOUT >25 s (hang or memory blow-up)"
    out = (p.stdout or "").strip().splitlines()
    if p.returncode != 0:
        return f"CRASH rc={p.returncode} {(p.stderr or '').strip().splitlines()[-1:]}"
    return out[-1] if out else "NO OUTPUT"


if __name__ == "__main__":
    only = sys.argv[1:] or list(CASES)
    for name in only:
        print(f"{name:30s} {run_case(CASES[name])}", flush=True)
