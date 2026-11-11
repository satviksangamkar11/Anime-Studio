"""Review one finished gap card with two free-of-Claude reviewers at the same time: Dots (OpenRouter free) and Codex Luna medium (read-only).
Leaves research/card_results/<card>_review_dots.md, <card>_review_luna.md and <card>.review.json (verdicts).

  python tools/card_review.py --card X-20
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "research", "card_results")
sys.path.insert(0, HERE)
import card_runner


def read(rel, cap=40000):
    try:
        text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
    except OSError:
        return "(missing)"
    return text if len(text) <= cap else text[:cap] + "\n...(cut)"


def build_prompt(result):
    card = card_runner.card_text(os.path.join(ROOT, result["plan"]), result["card"])
    parts = ["You are a strict, hostile code reviewer for a gap-closure card in a Python animation pipeline. Find REAL defects only: "
             "wrong result, a card requirement not met, a crash path, input that passes silently, a test that cannot fail (weak or "
             "tautological), a test that does not cover a test name the card lists. Quote the faulty line and give the exact fix. "
             "Do not invent problems and do not praise. End with exactly one line: VERDICT: OK or VERDICT: FIX-FIRST.\n\nCARD (the full "
             "problem statement):\n" + card + "\n\nWHAT HAPPENED IN THE RUN: " + json.dumps(result.get("edit_report", {}))[:1500]]
    for rel in result.get("files", []):
        parts.append("MODULE " + rel + ":\n" + read(rel))
    parts.append("TEST FILE " + result.get("test_file", "") + ":\n" + read(result.get("test_file", "")))
    return "\n\n".join(parts)


def run_dots(prompt, out):
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("dots_review", os.path.join(ROOT, "flow", "scripts", "dots_review.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        text = mod.review(prompt, [], raw=True, max_tokens=16000, reasoning={"enabled": False})["text"]
    except Exception as exc:
        text = "NO_REVIEW: %s" % type(exc).__name__
    open(out, "w", encoding="utf-8").write(text)


def run_luna(prompt, out):
    exe = shutil.which("codex.cmd") or shutil.which("codex")
    text = "NO_REVIEW: codex not found"
    if exe:
        try:
            r = subprocess.run([exe, "exec", "-m", "gpt-6-luna", "-c", "model_reasoning_effort=medium", "--sandbox", "read-only",
                                "--skip-git-repo-check", "-"], input=prompt, capture_output=True, text=True, encoding="utf-8",
                               timeout=900, cwd=ROOT)
            text = r.stdout.strip() or "NO_REVIEW: empty answer (%s)" % r.stderr.strip()[-200:]
        except (OSError, subprocess.TimeoutExpired) as exc:
            text = "NO_REVIEW: %s" % type(exc).__name__
    open(out, "w", encoding="utf-8").write(text)


def verdict(path):
    text = open(path, encoding="utf-8").read()
    m = re.findall(r"VERDICT:\s*(OK|FIX-FIRST)", text)
    return m[-1] if m else ("NO_REVIEW" if text.startswith("NO_REVIEW") else "UNCLEAR")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", required=True)
    a = ap.parse_args(argv)
    result = json.load(open(os.path.join(RES, a.card + ".json"), encoding="utf-8"))
    prompt = build_prompt(result)
    dots = os.path.join(RES, a.card + "_review_dots.md")
    luna = os.path.join(RES, a.card + "_review_luna.md")
    threads = [threading.Thread(target=run_dots, args=(prompt, dots)), threading.Thread(target=run_luna, args=(prompt, luna))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    out = {"card": a.card, "dots": verdict(dots), "luna": verdict(luna)}
    json.dump(out, open(os.path.join(RES, a.card + ".review.json"), "w"), indent=1)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
