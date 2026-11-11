"""Fix the findings of the two reviewers (Dots + Codex Luna) for one finished card, with Super through edit_runner.
The module files AND the card's test file may change (new tests for each fixed defect). Gate = the card's tests + more tests.

  python tools/card_fix.py --card X-09 [--model super]
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "research", "card_results")
PY = sys.executable
sys.path.insert(0, HERE)
import card_runner


def read(path, cap):
    try:
        return open(path, encoding="utf-8").read()[:cap]
    except OSError:
        return "(missing)"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", required=True)
    ap.add_argument("--model", default="super")
    ap.add_argument("--rounds", type=int, default=4)
    a = ap.parse_args(argv)
    res = json.load(open(os.path.join(RES, a.card + ".json"), encoding="utf-8"))
    card = card_runner.card_text(os.path.join(ROOT, res["plan"]), a.card)
    dots = read(os.path.join(RES, a.card + "_review_dots.md"), 6000)
    luna = read(os.path.join(RES, a.card + "_review_luna.md"), 6000)
    task = os.path.join(RES, a.card + "_fix_task.md")
    with open(task, "w", encoding="utf-8") as f:
        f.write("Two independent reviewers found problems in the finished gap card below. Fix every finding that is CORRECT (check it "
                "against the code first; the Dots review is noisier than the Luna review and may be wrong or describe a line that does "
                "not exist: ignore a finding you can show is wrong). For each fixed defect add or strengthen a test in the card's test "
                "file so the test fails before the fix. Keep every existing test passing. Edit only the allowed files; keep everything "
                "else byte-identical; do not add code that reads files at import time.\n\nCARD:\n" + card
                + "\n\nREVIEW BY LUNA:\n" + luna + "\n\nREVIEW BY DOTS:\n" + dots)
    allow = list(res["files"]) + [res["test_file"]]
    tests = [res["test_file"]] + list(res.get("more_tests", []))
    report = os.path.join(RES, a.card + "_fix_report.json")
    os.environ["ER_TAG"] = "_" + a.card + "_fix"
    code = subprocess.run([PY, "tools/edit_runner.py", "--task", task, "--allow"] + allow + ["--allow-tests", "--test",
                           PY.replace("\\", "/") + " -m pytest -q -p no:cacheprovider " + " ".join(tests),
                           "--root", ROOT.replace("\\", "/"), "--model", a.model, "--rounds", str(a.rounds),
                           "--report", report], cwd=ROOT).returncode
    out = {"card": a.card, "fix_ok": code == 0}
    json.dump(out, open(os.path.join(RES, a.card + ".fix.json"), "w"), indent=1)
    print(json.dumps(out))
    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
