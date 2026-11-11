"""One gap card, free models only: (1) Dots writes the frozen test file from the card, (2) edit_runner + Nemotron changes the
module files until the tests pass, (3) a result json is left in research/card_results/. No Claude, no paid call.

  python tools/card_runner.py --card X-20 --plan research/OPUS_PLAN_P3_....md --files score/stem_builder.py \
      --test-file score/tests/test_loudness_targets.py [--more-tests score/tests/test_stem_builder.py] [--model super]
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable


def card_text(plan_path, card):
    text = open(plan_path, encoding="utf-8").read()
    m = re.search(r"^(?:\*\*|### )" + re.escape(card) + r"[ |:].*?(?=^(?:\*\*|### )[A-Z]-\d\d[ |:]|^## |\Z)", text, re.S | re.M)
    if not m:
        raise SystemExit("card not found: " + card)
    return m.group(0)


def run(argv):
    return subprocess.run(argv, cwd=ROOT).returncode


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--files", nargs="+", required=True)
    ap.add_argument("--test-file", required=True)
    ap.add_argument("--more-tests", nargs="*", default=[])
    ap.add_argument("--model", default="super", choices=["dots", "super", "ultra"])
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--hint", default="")
    ap.add_argument("--slot", default="")      # K/N: use only keys K, K+N, ... of the 14 (parallel jobs must not share keys)
    a = ap.parse_args(argv)
    if a.slot:
        os.environ["ER_KEY_SLOT"] = a.slot
    work = os.path.join(ROOT, "research", "card_results")
    os.makedirs(work, exist_ok=True)
    card = card_text(os.path.join(ROOT, a.plan), a.card)
    result = {"card": a.card, "tests_written": False, "ok": False, "plan": a.plan, "files": a.files, "test_file": a.test_file, "more_tests": a.more_tests}
    for rel in a.files:
        mod = os.path.join(ROOT, rel)
        if not os.path.isfile(mod):
            with open(mod, "w", encoding="utf-8", newline="\n") as f:
                f.write('"""STUB: replace this whole docstring line with the module (new file for card ' + a.card + ')."""\n')
    test_abs = os.path.join(ROOT, a.test_file)
    if not os.path.isfile(test_abs):
        task = os.path.join(work, a.card + "_tests_task.md")
        with open(task, "w", encoding="utf-8") as f:
            f.write("Write ONLY the test file " + a.test_file + " (plain pytest, standard library, tmp_path, no network, "
                    "no model call; start with sys.path.insert of its own folder and the project root so the modules import by "
                    "bare name or package as the neighbouring tests do). It is the frozen test gate for this gap card; the "
                    "module change is made later by someone else, so the tests must FAIL on the current code and pass on a "
                    "correct implementation. Use the hand-computed values written in the card; do not copy code from the "
                    "module under test. Cover every test name the card lists.\n\nCARD:\n" + card + "\n\nEXTRA HINT: " + a.hint)
        with open(test_abs, "w", encoding="utf-8", newline="\n") as f:
            f.write("# STUB: replace this line with the test file for card " + a.card + "\n")
        os.environ["ER_TAG"] = "_" + a.card + "_tests"
        code = run([PY, "tools/edit_runner.py", "--task", task, "--allow", a.test_file, "--allow-tests", "--test",
                    PY.replace("\\", "/") + " -m py_compile " + a.test_file, "--root", ROOT.replace("\\", "/"),
                    "--model", "super", "--rounds", "4", "--report", os.path.join(work, a.card + "_tests_report.json")])
        if code != 0 and os.path.isfile(test_abs) and open(test_abs, encoding="utf-8").read().startswith("# STUB"):
            os.remove(test_abs)
        if code != 0 or not os.path.isfile(test_abs):
            result["error"] = "test writing failed (exit %s)" % code
            json.dump(result, open(os.path.join(work, a.card + ".json"), "w"), indent=1)
            return 2
    result["tests_written"] = True
    task = os.path.join(work, a.card + "_code_task.md")
    with open(task, "w", encoding="utf-8") as f:
        f.write("Implement this gap card by editing ONLY the allowed module files; the test file " + a.test_file
                + " is frozen (do not touch it). Keep everything else byte-identical. Do NOT add code that runs at "
                "import time and reads files (the module must still import in a bare checkout).\n\nCARD:\n" + card
                + "\n\nEXTRA HINT: " + a.hint)
    test_cmd = PY + " -m pytest -q -p no:cacheprovider " + " ".join([a.test_file] + a.more_tests)
    report = os.path.join(work, a.card + "_report.json")
    os.environ["ER_TAG"] = "_" + a.card
    order = ["super", "super"]          # owner 2026-11-11: Super is the only coder (Dots reviews only)
    code = 1
    for model in order:
        code = run([PY, "tools/edit_runner.py", "--task", task, "--allow"] + a.files + ["--test", test_cmd.replace("\\", "/"),
                    "--root", ROOT.replace("\\", "/"), "--model", model, "--rounds", str(a.rounds), "--report", report])
        result.setdefault("tried", []).append(model)
        if code == 0:
            break
    result["ok"] = code == 0
    if os.path.isfile(report):
        result["edit_report"] = json.load(open(report, encoding="utf-8"))
    json.dump(result, open(os.path.join(work, a.card + ".json"), "w"), indent=1)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
