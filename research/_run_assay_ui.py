"""Run Assay (pip assay-ui: deterministic, no LLM) on the real control-panel UI against a FAKE-TOOLS server.

Assay serves a folder with its own static server, so /api calls would fail. Here its `serve` is pointed at our server,
started on the test_ui.py fake world (every script is a fake, spend off, Claude off, no network), so Assay may click every
control without touching a real story. Gate A is approved INSIDE the fake world only, so step 3 (pictures) is open.

Usage (the assay venv python, from anime_studio_merge):
  python research/_run_assay_ui.py OUT_DIR            run Assay, write OUT_DIR/assay_report.html
  python research/_run_assay_ui.py OUT_DIR --serve    only start the fake server and wait (for a browser check)
"""
import contextlib
import json
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "ui"))
import server     # noqa: E402
import test_ui    # noqa: E402  make_world = the fake studio the UI tests use

REAL_CHECK = Path("D:/aai work/flow_outputs/anime_kaliya/adhyay_01/final/_sparkle_check3")


out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=True)
root = Path(tempfile.mkdtemp(prefix="assay_world_"))
S, F, fakes = test_ui.make_world(root)
shutil.copytree(HERE / "ui/static", S / "ui/static", dirs_exist_ok=True)       # the real UI files
check = F / "adhyay_01/final/_sparkle_check3"                                   # three real watermark sheets for step 3
check.mkdir(parents=True, exist_ok=True)
report = json.loads((REAL_CHECK / "report.json").read_text())
keep = sorted(report)[:3]
(check / "report.json").write_text(json.dumps({t: report[t] for t in keep}))
for t in keep:
    shutil.copy2(REAL_CHECK / f"{t}__sheet.png", check / f"{t}__sheet.png")

cfg = server.Config(studio=S, flow=F, downloads=root / "Downloads", python=sys.executable,
                    colab=[sys.executable, str(fakes / "colab_fake.py")], spend=False)
srv = server.make_server(cfg, 0)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}"
story, pack = test_ui.GOOD_PACK.split("/")[1], test_ui.GOOD_PACK.split("/")[2]
api = server.Api(cfg)            # in-process: the HTTP guard refuses requests that do not come from the page (403)


def call(path, body):
    try:
        return server.dispatch(api, "POST", path, {}, body)
    except Exception as exc:
        return {"error": str(exc)}


print("project:", call("/api/pipeline/project", {"story_slug": story, "pack": pack}))
# the fake pack fails one plan check, so the real gate refuses it; for this display check the approval line is written
# straight into the FAKE world's approvals file (never the real one)
server._pipeline().record_gate(cfg.runs, "A", "approve", "owner", "assay fake world", story_slug=story, pack=pack)
print("gate A written in the fake world:", cfg.runs / "approvals.jsonl")
print("fake-tools server:", url, "world:", root, flush=True)

if "--serve" in sys.argv:
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    sys.exit(0)

import assay.browser  # noqa: E402
from assay import cli  # noqa: E402


@contextlib.contextmanager
def ours(_folder):
    yield url


assay.browser.serve = ours
code = cli.main([str(S / "ui/static"), "--report", str(out / "assay_report.html")])
code_line = cli.main([str(S / "ui/static"), "--one-line"])
srv.shutdown()
shutil.rmtree(root, ignore_errors=True)
sys.exit(code or code_line)
