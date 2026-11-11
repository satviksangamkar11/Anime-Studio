"""One poll of the card runs (the Haiku watcher calls this every 2 minutes).
For every research/card_results/<card>.json with ok=true and no review yet, start tools/card_review.py in the background
(both reviewers at once). Prints one compact status table.

  python tools/card_watch.py
"""
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "research", "card_results")


def main():
    rows = []
    started = []
    for path in sorted(glob.glob(os.path.join(RES, "*.json"))):
        name = os.path.basename(path)
        if name.endswith("_report.json") or name.endswith(".review.json") or name.endswith("_tests_report.json"):
            continue
        card = name[:-5]
        try:
            res = json.load(open(path, encoding="utf-8"))
        except ValueError:
            continue
        review = os.path.join(RES, card + ".review.json")
        started_flag = os.path.join(RES, card + ".review.started")
        status = "ok" if res.get("ok") else "FAILED: " + str(res.get("error") or (res.get("edit_report") or {}).get("error", ""))[:80].replace("\n", " ")
        rev = ""
        if os.path.isfile(review):
            r = json.load(open(review, encoding="utf-8"))
            rev = "dots=%s luna=%s" % (r.get("dots"), r.get("luna"))
        elif res.get("ok") and os.path.isfile(started_flag):
            rev = "review running"
        elif res.get("ok"):
            open(started_flag, "w").write("1")
            subprocess.Popen([sys.executable, os.path.join(HERE, "card_review.py"), "--card", card], cwd=ROOT,
                             stdout=open(os.path.join(RES, card + "_review.out"), "w"), stderr=subprocess.STDOUT,
                             creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
            started.append(card)
            rev = "review STARTED now"
        rows.append("%-6s %-60s %s" % (card, status, rev))
    running = [p for p in glob.glob(os.path.join(RES, "*.out")) if not p.endswith("_review.out")]
    print("\n".join(rows) if rows else "no finished cards yet")
    print("review started this poll:", started or "none")
    print("run logs (still working or failed without json): %d" % len([p for p in running if not os.path.isfile(p[:-4] + ".json")]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
