"""Parity guard for the UI redesign (docs/UI_REDESIGN_PLAN_2026-11-07.md section 9 and 9.2, task T0).

Offline: reads files only, starts no server, runs no command. It checks that
- every feature row of section 9.1 has an anchor (element id, class token or quoted literal) in the UI,
- every server command and route is reachable from the page, and every API route is listed,
- rows, commands and routes that a later task adds are checked only from that task on (BUILT / NEW_*).
When a task finishes, add its name to BUILT. Nothing is ever removed from the tables below (owner parity rule)."""
import inspect
import os
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import server  # noqa: E402

STATIC = HERE / "static"
PLAN_FILE = HERE.parent / "docs" / "UI_REDESIGN_PLAN_2026-11-07.md"
EN_JSON = STATIC / "i18n" / "en.json"

# Tasks whose work is in the tree. A NEW row, command or route is checked only once its task is in this set.
BUILT = {"T0", "T1", "T2", "T3", "T4"} | {x.strip() for x in os.environ.get("PARITY_BUILT", "").split(",") if x.strip()}  # lead/coder runs: PARITY_BUILT=T2,T3

# ---------------------------------------------------------------- section 9.1: (row id, anchor) for every row that exists today
INVENTORY = [
    ("H01", "header-chips"), ("H02", "chip-story"), ("H03", "chip-pack"), ("H04", "chip-languages"),
    ("H05", "spend-badge"), ("H06", "job-badge"), ("H07", "host"), ("H08", "server-state"), ("H09", "pipe-banner"),
    ("H10", "error-bar"), ("H11", "skip-link"), ("H13", "msg-bar"),
    ("T01", "step-analysis"), ("T03", "wizard-scope"), ("T04", "wizard-jobbar"),
    ("S01", "btn-continue"), ("S02", "wiz-story-slug"), ("S03", "wiz-story-new-slug"), ("S04", "wiz-story-text"),
    ("S05", "wiz-story-overwrite"), ("S06", "btn-save-story"),
    ("S07", "lang-"),                       # built as 'lang-' + code (en, hi, mr) in pipeline.js
    ("S08", "lang-all"), ("S09", "lang-save"), ("S10", "voice-save"), ("S11", "bgm-save"), ("S12", "voice-map-save"),
    ("S13", "link-run"), ("S14", "link-result"),
    ("A01", "analysis-pack"), ("A02", "analysis-run"), ("A04", "analysis-run"), ("A05", "validator-run"),
    ("A06", "gate-approve-"),               # built as 'gate-approve-' + id
    ("I01", "images-build-jobs"), ("I02", "images-packet"), ("I03", "images-packet"), ("I05", "gate-approve-"),
    ("R04", "gate-confirm-C"),
    ("V01", "render-prepare"), ("V02", "asset-panel"), ("V03", "choice-note-"), ("V04", "step9-panel"),
    ("V05", "author-panel"), ("V06", "gate-d-langs"),
    ("X01", "export-show"),
    ("P01", "ops-panel"), ("P02", "runs-panel"),
    ("D01", "confirm-run"), ("D02", "modal-start"), ("D03", "packet-copy"), ("D04", "lightbox-close"), ("D05", "modal-close"),
    ("E00", "advanced-tools"), ("E01", "nav-bridge"), ("ER", "risk-usd"),
    ("ES1", "story-pack"), ("ES2", "story-model"), ("ES3", "story-status"), ("ES4", "story-load"), ("ES5", "story-save"),
    ("ES6", "story-run-new"), ("ES7", "story-resume"), ("ES8", "story-check"), ("ES9", "story-stages"),
    ("ES10", "story-gate1"), ("ES11", "story-episodes"), ("ES12", "story-places"), ("ES13", "story-shots"),
    ("ES14", "story-check-json"),
    ("EI1", "img-refresh"), ("EI2", "tab-queue"), ("EI3", "series-table"), ("EI4", "act-packet"), ("EI5", "review-detail"),
    ("EI6", "act-neighbours"), ("EI7", "act-reviewer"), ("EI8", "act-queue-kept"), ("EI9", "act-accept"),
    ("EI10", "progress-table"), ("EI11", "queue-counts"), ("EI12", "btn-collect"), ("EI13", "btn-tidy"), ("EI14", "finals-grid"),
    ("EB1", "bridge-size"), ("EB2", "bridge-dry"), ("EB3", "bridge-write"), ("EB4", "bridge-table"),
    ("EV1", "video-batch"), ("EV2", "video-scope-reel"), ("EV3", "video-keyframes"), ("EV4", "video-prepare"),
    ("EV5", "video-batches"), ("EV6", "h3-run"), ("EV7", "colab-check"), ("EV8", "colab-run"), ("EV9", "act-stop-session"),
    ("EV10", "video-live"), ("EV11", "video-stop"), ("EV12", "clips-home"), ("EV13", "act-vqa"),
    ("EX1", "export-load"), ("EX2", "export-clips"), ("EX3", "export-assembly"), ("EX4", "export-files"), ("EX5", "export-open"),
    ("EL1", "log-tail"), ("EL2", "log-stop"),
]

# ---------------------------------------------------------------- NEW rows: (row id, anchor, task that adds it)
# An anchor 'key:<name>' is an i18n key: it must be in i18n/en.json (checked from its task on).
NEW_ROWS = [
    ("H12", "ui-lang-mr", "T2"),
    ("T02", "progress-line", "T3"),
    ("A03", "writer-choice", "T3"),
    ("I04", "key:pics.rule_haiku", "T3"),
    ("R01", "key:sum.tile_parts", "T3"),
    ("R02", "key:sum.more_title", "T3"),
    ("R03", "key:sum.checks_title", "T3"),
    ("NEW-T3", "writer-opt-or-super-vl", "T3"),
    ("NEW-T3", "writer-claude-ack", "T3"),
    ("NEW-T3", "confirm-typed", "T3"),
    ("NEW-T3", "ops-colab-check", "T3"),
    ("NEW-T3", "banner-recheck", "T3"),
    ("NEW-T3", "plan-show-all", "T3"),
]

# ---------------------------------------------------------------- commands (section 9.2)
SERVER_ONLY = {   # no UI control today; reachable only as listed (T0 test_every_command_is_reachable)
    "check_pack": "reached by GET /api/pack?check=1 (Advanced Check pack)",
    "queue_status": "no UI today",
    "tidy_apply": "no UI today",
    "colab_sessions": "no UI today (GET /api/colab is used)",
    "colab_usage": "no UI today (GET /api/colab is used)",
    "colab_run_dry": "no UI today",
    "yt_transcript": "reached by POST /api/story/{slug}/link",
}
NEW_COMMANDS = {"write_pack_claude": "T3"}   # must be quoted in pipeline.js from T3 on

# ---------------------------------------------------------------- routes (section 9.2): (method, route, needle, where, ui task, server task)
ROUTES = [
    ("GET", "/", "(served page)", "", None, None),
    ("GET", "/*.css", "(served assets)", "", None, None),
    ("GET", "/*.js", "(served assets)", "", None, None),
    ("GET", "/i18n/{lang}.json", "'i18n/'", "i18n.js", "T2", None),
    ("GET", "/fonts/NotoSansDevanagari-Variable.ttf", "fonts/NotoSansDevanagari-Variable.ttf", "style.css", "T2", None),
    ("GET", "/api/pipeline", "'/api/pipeline'", "", None, None),
    ("GET", "/api/pipeline/summary", "'/api/pipeline/summary'", "", None, None),
    ("GET", "/api/version", "'/api/version'", "", None, None),
    ("GET", "/api/ops", "'/api/ops'", "", None, None),
    ("GET", "/api/story/{slug}/state", "'/state'", "", None, None),
    ("GET", "/api/pack/voices", "'/api/pack/voices", "", None, None),
    ("POST", "/api/pack/voices", "'/api/pack/voices", "", None, None),
    ("GET", "/api/pack/validate", "'/api/pack/validate", "", None, None),
    ("POST", "/api/pack/validate", "'/api/pack/validate", "", None, None),
    ("GET", "/api/render/status", "'/api/render/status", "", None, None),
    ("GET", "/api/author/status", "'/api/author/status", "", None, None),
    ("GET", "/api/status", "'/api/status'", "", None, None),
    ("GET", "/api/h3", "'/api/h3'", "", None, None),
    ("GET", "/api/story", "'/api/story'", "", None, None),
    ("GET", "/api/story/{slug}", "'/api/story/'", "", None, None),
    ("POST", "/api/story/{slug}", "'/api/story/'", "", None, None),
    ("GET", "/api/registry", "'/api/registry'", "", None, None),
    ("GET", "/api/registry/{slug}", "'/api/registry/'", "", None, None),
    ("GET", "/api/pack", "'/api/pack?pack='", "", None, None),
    ("GET", "/api/jobs", "'/api/jobs'", "", None, None),
    ("GET", "/api/jobs/{id}/log", "'/log?tail=", "", None, None),
    ("GET", "/api/jobs/{id}/result", "'/result'", "", None, None),
    ("POST", "/api/jobs/{id}/stop", "'/stop'", "", None, None),
    ("GET", "/api/images", "'/api/images?", "", None, None),
    ("GET", "/api/review", "'/api/review?", "", None, None),
    ("GET", "/api/video", "'/api/video'", "", None, None),
    ("GET", "/api/colab", "'/api/colab'", "", None, None),
    ("GET", "/api/export", "'/api/export?", "", None, None),
    ("GET", "/api/file", "'/api/file?path='", "", None, None),
    ("GET", "/api/writers", "'/api/writers'", "", "T3", "T1"),
    ("POST", "/api/preview", "'/api/preview'", "", None, None),
    ("POST", "/api/run", "'/api/run'", "", None, None),
    ("POST", "/api/packet", "'/api/packet'", "", None, None),
    ("POST", "/api/pipeline/gate", "'/api/pipeline/gate'", "", None, None),
    ("POST", "/api/pipeline/project", "'/api/pipeline/project'", "", None, None),
    ("POST", "/api/story/{slug}/languages", "'/languages'", "", None, None),
    ("POST", "/api/story/{slug}/voices", "'/voices'", "", None, None),
    ("POST", "/api/story/{slug}/bgm", "'/bgm'", "", None, None),
    ("POST", "/api/story/{slug}/link", "'/link'", "", None, None),
    ("POST", "/api/render/choice", "'/api/render/choice'", "", None, None),
    ("POST", "/api/author/preview", "'/api/author/preview'", "", None, None),
]
SERVER_ONLY_ROUTES = {}   # API routes that the page never calls; empty today


# ---------------------------------------------------------------- helpers
def _read(name):
    f = STATIC / name
    return f.read_text(encoding="utf-8") if f.is_file() else ""


INDEX = _read("index.html")
APP = _read("app.js")
PIPE = _read("pipeline.js")


def in_index(anchor):
    if re.search(r"""\bid=["']%s["']""" % re.escape(anchor), INDEX):
        return True
    return any(anchor in value.split() for value in re.findall(r'class="([^"]*)"', INDEX))


def in_script(anchor, text):
    """The anchor sits inside one quoted literal ('act act-packet', 'gate-approve-' + id)."""
    return re.search(r"""(['"])[^'"\n]*%s[^'"\n]*\1""" % re.escape(anchor), text) is not None


def key_in_en(key):
    if not EN_JSON.is_file():
        return False
    import json
    data = json.loads(EN_JSON.read_text(encoding="utf-8"))
    return isinstance(data, dict) and key in data


def anchor_found(anchor):
    if anchor.startswith("key:"):
        return key_in_en(anchor[len("key:"):])
    return in_index(anchor) or in_script(anchor, APP) or in_script(anchor, PIPE)


def quoted(name, text):
    return re.search(r"""(['"])%s\1""" % re.escape(name), text) is not None


def canon(path):
    """Comparable forms of a route: (a|b) alternations are expanded, other regex groups and {placeholders} become '*'."""
    out, todo = set(), [path]
    while todo:
        f = todo.pop()
        m = re.search(r"\(([a-z|]+)\)", f)
        if m and "|" in m.group(1):
            todo += [f[:m.start()] + alt + f[m.end():] for alt in m.group(1).split("|")]
            continue
        f = re.sub(r"\([^)]*\)", "*", f)
        f = re.sub(r"\{[^}]*\}", "*", f)
        out.add(f)
    return out


def dispatch_routes():
    """The /api/ literals of server.dispatch (the only place routes are decided)."""
    return set(re.findall(r'"(/api/[^"]*)"', inspect.getsource(server.dispatch)))


def section9_rows():
    if not PLAN_FILE.is_file():
        return None
    text = PLAN_FILE.read_text(encoding="utf-8")
    part = text.split("### 9.1 Rows", 1)[1].split("### 9.2", 1)[0]
    return re.findall(r"^\| ([A-Z]{1,2}[0-9]{0,2}) \|", part, re.M)


# ---------------------------------------------------------------- tests
@pytest.mark.parametrize("row,anchor", INVENTORY, ids=[f"{r}:{a}" for r, a in INVENTORY])
def test_every_inventory_anchor_exists(row, anchor):
    assert anchor_found(anchor), f"row {row}: anchor {anchor!r} is not an id, a class or a quoted literal in the UI"


@pytest.mark.parametrize("row,anchor,task", NEW_ROWS, ids=[f"{r}:{a}" for r, a, _ in NEW_ROWS])
def test_new_rows_are_checked_from_their_task(row, anchor, task):
    if task not in BUILT:
        pytest.skip(f"{row} is added by {task}")
    assert anchor_found(anchor), f"row {row} ({task}): anchor {anchor!r} is missing"


def test_inventory_lists_every_section9_row():
    rows = section9_rows()
    if rows is None:
        pytest.skip("the redesign plan is not in the tree")
    listed = [r for r, _ in INVENTORY] + [r for r, _, _ in NEW_ROWS if r != "NEW-T3"]
    assert len(listed) == len(set(listed)), "a row id is listed twice"
    assert set(rows) == set(listed), f"rows missing from the test: {sorted(set(rows) - set(listed))}; extra: {sorted(set(listed) - set(rows))}"
    assert len(rows) == len(set(rows)), "a row id appears twice in section 9.1"


ALL_COMMANDS = sorted(set(server.COMMANDS) | set(getattr(server, "CLAUDE_COMMANDS", {})))


@pytest.mark.parametrize("cmd", ALL_COMMANDS)
def test_every_command_is_reachable(cmd):
    if cmd in NEW_COMMANDS and NEW_COMMANDS[cmd] not in BUILT:
        pytest.skip(f"{cmd} is added by {NEW_COMMANDS[cmd]}")
    if cmd in SERVER_ONLY:
        pytest.skip("server only: " + SERVER_ONLY[cmd])
    texts = [PIPE] if cmd in NEW_COMMANDS else [APP, PIPE]
    assert any(quoted(cmd, t) for t in texts), f"command {cmd} is not quoted in the UI"


def test_server_only_names_are_real_commands():
    assert set(SERVER_ONLY) <= set(ALL_COMMANDS)


@pytest.mark.parametrize("method,route,needle,where,ui_task,server_task", ROUTES, ids=[f"{m} {r}" for m, r, *_ in ROUTES])
def test_every_route_is_reachable(method, route, needle, where, ui_task, server_task):
    if needle.startswith("("):
        pytest.skip("served by the server, not called from the page")
    if ui_task and ui_task not in BUILT:
        pytest.skip(f"{route} is wired by {ui_task}")
    if where == "i18n.js":
        text = _read("i18n.js")
    elif where == "style.css":
        text = _read("style.css")
    else:
        text = APP + PIPE
    assert needle in text, f"{method} {route}: needle {needle} is not in {where or 'app.js or pipeline.js'}"


def test_no_unlisted_route():
    listed = set()
    for _m, route, _n, _w, _u, _s in ROUTES:
        listed |= canon(route)
    for lit in dispatch_routes():
        if lit in SERVER_ONLY_ROUTES:
            continue
        assert canon(lit) <= listed, f"server route {lit} is not in the parity table (section 9.2)"


@pytest.mark.parametrize("method,route,needle,where,ui_task,server_task", [r for r in ROUTES if r[1].startswith("/api/")],
                         ids=[f"{m} {r}" for m, r, *_ in ROUTES if r.startswith("/api/")])
def test_every_listed_api_route_is_dispatched(method, route, needle, where, ui_task, server_task):
    if server_task and server_task not in BUILT:
        pytest.skip(f"{route} is added by {server_task}")
    served = set()
    for lit in dispatch_routes():
        served |= canon(lit)
    assert canon(route) <= served, f"{route} is listed in section 9.2 but server.dispatch does not serve it"
