"""Offline static checks for the Anime Studio control UI frontend.

No server, no browser, no network. Reads static/index.html, static/style.css, static/app.js and PLAN.md.
Run from D:\\aai work\\anime_studio\\ui:
    C:\\Python314\\python.exe -m pytest -q -p no:cacheprovider test_static.py
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
PLAN = HERE / "PLAN.md"
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "style.css").read_text(encoding="utf-8")
JS = (STATIC / "app.js").read_text(encoding="utf-8")
PLAN_TEXT = PLAN.read_text(encoding="utf-8")

SECTIONS = ["Story", "Images", "Bridge", "Video", "Export"]

# Owner brief (2026-11-06) adds GET /api/h3. It is not in PLAN section 4 yet, so it is allowed here on purpose.
EXTRA_ENDPOINTS = {"/api/h3"}

REQUIRED_ENDPOINTS = [
    "/api/status", "/api/jobs", "/api/story", "/api/pack", "/api/preview", "/api/run",
    "/api/images", "/api/review", "/api/packet", "/api/video", "/api/colab", "/api/export",
    "/api/file", "/api/h3",
]

# (label as written in PLAN section 1, id or token that must exist in index.html or app.js)
CONTROL_MAP = [
    ("SPEND", "spend-badge"), ("job:", "job-badge"), ("log tail", "log-tail"),
    ("Story", "nav-story"), ("Images", "nav-images"), ("Bridge", "nav-bridge"),
    ("Video", "nav-video"), ("Export", "nav-export"),
    ("slug [", "story-slug"), ("pack [", "story-pack"), ("Save as SOURCE.md", "story-save"),
    ("Run writer: new pack", "story-run-new"), ("Resume pack", "story-resume"), ("Check pack", "story-check"),
    ("Stages", "story-stages"), ("Gate 1", "story-gate1"), ("Episodes", "story-episodes"),
    ("Characters (bible)", "story-characters"), ("Places (bible)", "story-places"),
    ("check_pack JSON", "story-check-json"),
    ("adhyay [", "img-adhyay"), ("[Series]", "tab-series"), ("[Jobs]", "tab-jobs"),
    ("[Shots]", "tab-shots"), ("[Progress]", "tab-progress"), ("[Queue]", "tab-queue"), ("[Finals]", "tab-finals"),
    ("pending", "queue-counts"), ("[Packet]", "act-packet"), ("[Build*]", "act-build"),
    ("[Neighbours]", "act-neighbours"), ("[Run reviewer]", "act-reviewer"),
    ("[Queue kept]", "act-queue-kept"), ("[Accept (owner)]", "act-accept"), ("[Collect]", "btn-collect"),
    ("target [", "bridge-size"), ("[Dry run]", "bridge-dry"), ("[Write keyframes]", "bridge-write"),
    ("shot file [", "video-shotfile"), ("batch [", "video-batch"), ("route [", "video-route"),
    ("(o) shots", "video-scope-shots"), ("( ) reel", "video-scope-reel"), ("( ) all", "video-scope-all"),
    ("Keyframes root", "video-keyframes"), ("resolution", "video-resolution"),
    ("[1 Prepare batch (no GPU)]", "video-prepare"),
    ("Colab sessions", "colab-sessions"), ("balance", "colab-balance"), ("rate:", "colab-rate"),
    ("[Check Colab]", "colab-check"), ("[Run on Colab... (spend gate)]", "colab-run"),
    ("[Stop session", "act-stop-session"),
    ("Live", "video-live"), ("clips home", "clips-home"), ("Clips", "clips-table"),
    ("[Sheet]", "act-sheet"), ("[Visual QA]", "act-vqa"),
    ("reel [1 v]", "export-reel"), ("Clips in order", "export-clips"), ("Assembly plan", "export-assembly"),
    ("Reel files", "export-files"), ("[Open folder]", "export-open"),
    ("CONFIRM SPEND", "modal"), ("argv", "modal-argv"), ("Type EXECUTE", "modal-confirm-input"),
    ("[Start]", "modal-start"), ("[Cancel]", "modal-cancel"),
]


def _plan_section(number_heading, next_heading):
    start = PLAN_TEXT.index(number_heading)
    end = PLAN_TEXT.index(next_heading, start)
    return PLAN_TEXT[start:end]


def _plan_path_regex(path):
    """Turn a PLAN section 4 path like /api/story/{slug} into a regex. Query strings are ignored."""
    path = path.split("?")[0]
    out = []
    for part in re.split(r"(\{[^}]*\}|<[^>]*>|\*)", path):
        if not part:
            continue
        if part == "*":
            out.append(".*")
        elif part[0] in "{<":
            out.append("[^/]+")
        else:
            out.append(re.escape(part))
    return re.compile("^" + "".join(out) + "$")


def _plan_endpoints():
    """Parse the PLAN section 4 table: returns list of (method, path)."""
    sec = _plan_section("## 4. Local API", "## 5. Files")
    found = []
    for m in re.finditer(r"^\|\s*(GET|POST)\s*\|([^|]*)\|", sec, re.M):
        for path in re.findall(r"`([^`]+)`", m.group(2)):
            found.append((m.group(1), path))
    return found


def _app_endpoint_literals():
    """Literal /api/... paths used in app.js, normalised: template slots become {x}, query strings dropped."""
    lits = set()
    for raw in re.findall(r"['\"`](/api/[^'\"`\s]*)", JS):
        lit = re.sub(r"\$\{[^}]*\}", "{x}", raw).split("?")[0]
        lits.add(lit)
    return lits


def test_no_external_urls_in_any_asset():
    for name, text in [("index.html", INDEX), ("style.css", CSS), ("app.js", JS)]:
        assert not re.search(r"https?://", text), name + " contains an http(s) URL"
    assert not re.search(r"@import|url\(\s*['\"]?https?:", CSS)


def test_index_references_assets_relatively():
    for f in ["index.html", "style.css", "app.js"]:
        assert (STATIC / f).is_file(), f + " is missing"
    assert re.search(r'<link\s+rel="stylesheet"\s+href="style\.css"\s*>', INDEX)
    assert re.search(r'<script\s+src="app\.js"\s*>\s*</script>', INDEX)
    assert not re.search(r'(src|href)="/', INDEX), "asset paths must be relative"


def test_index_has_five_sections_and_nav():
    for name in SECTIONS:
        key = name.lower()
        assert re.search(r">\s*%s\s*</button>" % name, INDEX), "nav button text missing: " + name
        assert 'data-section="%s"' % key in INDEX, "data-section missing: " + key
        assert 'id="sec-%s"' % key in INDEX, "section container missing: " + key


def test_index_static_ids_are_unique():
    ids = re.findall(r'\sid="([^"]+)"', INDEX)
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, "duplicate ids: " + ", ".join(dupes)


def test_no_html_string_assignment_or_eval():
    assert not re.search(r"\.(inner|outer)HTML\s*\+?=(?!=)", JS), "assignment to innerHTML/outerHTML"
    for banned in ["insertAdjacentHTML", "document.write", "eval(", "new Function("]:
        assert banned not in JS, "banned call in app.js: " + banned


def test_fetch_targets_are_relative():
    for literal in re.findall(r"fetch\(\s*['\"`]([^'\"`]*)", JS):
        assert literal.startswith("/") and not literal.startswith("//"), "absolute fetch target: " + literal
    for banned in ["XMLHttpRequest", "WebSocket", "EventSource", "importScripts", "import("]:
        assert banned not in JS, "banned network API in app.js: " + banned


def test_posts_send_x_ui_header_and_json():
    assert re.search(r"\[['\"]X-UI['\"]\]\s*=\s*['\"]1['\"]", JS), "X-UI: 1 header is not set on POST"
    assert "application/json" in JS and "JSON.stringify(" in JS, "POST body must be JSON"
    assert re.search(r"method\s*!==\s*['\"]GET['\"]", JS), "X-UI must be set on every non-GET request"


def test_app_js_is_es2018_syntax_only():
    assert not re.search(r"\?\.(?!\d)", JS), "optional chaining is ES2020"
    assert "??" not in JS, "nullish coalescing is ES2020"
    for newer in ["replaceAll(", ".flat(", ".flatMap(", "Object.fromEntries", "Promise.allSettled",
                  "matchAll(", "globalThis"]:
        assert newer not in JS, "newer than ES2018: " + newer


def test_app_js_parses_with_node():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; syntax check skipped")
    proc = subprocess.run([node, "--check", str(STATIC / "app.js")], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_app_endpoints_exist_in_plan_section_4():
    plan = _plan_endpoints()
    assert len(plan) >= 18, "PLAN section 4 table did not parse (found %d rows)" % len(plan)
    plan_paths = [p for _, p in plan]
    regexes = [_plan_path_regex(p) for p in plan_paths]
    unknown = []
    for lit in sorted(_app_endpoint_literals()):
        if lit in EXTRA_ENDPOINTS:
            continue
        if lit.endswith("/"):
            ok = any(p.startswith(lit) for p in plan_paths)
        else:
            ok = any(rx.match(lit) for rx in regexes)
        if not ok:
            unknown.append(lit)
    assert not unknown, "endpoints used by app.js but not in PLAN section 4: " + ", ".join(unknown)


def test_app_uses_every_required_endpoint():
    lits = _app_endpoint_literals()
    missing = [e for e in REQUIRED_ENDPOINTS if e not in lits and e + "/" not in lits]
    assert not missing, "app.js never calls: " + ", ".join(missing)


def test_preview_and_run_are_the_only_command_path():
    assert "'/api/preview'" in JS and "'/api/run'" in JS
    assert "spend_allowed" in JS, "spend gate must read /api/status spend_allowed"
    assert re.search(r'id="colab-run"[^>]*data-gate="[^"]*spend', INDEX), "colab-run must carry the spend gate"


def test_control_ids_from_section_1_exist():
    sec1 = re.sub(r"\s+", " ", _plan_section("## 1. Screens", "## 2. Controls"))
    missing_label = [label for label, _ in CONTROL_MAP if label not in sec1]
    assert not missing_label, "labels not found in PLAN section 1: " + " | ".join(missing_label)
    missing_token = [tok for _, tok in CONTROL_MAP if tok not in INDEX and tok not in JS]
    assert not missing_token, "control ids/tokens not in index.html or app.js: " + ", ".join(missing_token)


def test_risk_badge_classes_exist():
    for cls in ["risk-R", "risk-W", "risk-N", "risk-usd", "risk-OPS", "risk-X"]:
        assert "." + cls in CSS, "missing CSS class " + cls
    for code in ["R", "W", "N", "$", "OPS", "X"]:
        assert code in JS, "risk code not described in app.js: " + code


def test_status_badge_colours_exist_for_every_kind():
    # The five colours from the brief: green OK, grey NOT RUN, amber NEEDS REVIEW, red FAILED, blue RUNNING.
    for cls in ["b-ok", "b-notrun", "b-review", "b-failed", "b-running"]:
        assert "." + cls in CSS, "missing badge colour " + cls
    for kind in ["ok", "notrun", "review", "failed", "running"]:
        assert "'" + kind + "'" in JS, "badge kind never used: " + kind


PIPELINE_JS = (STATIC / "pipeline.js").read_text(encoding="utf-8")


def test_image_jobs_button_id_and_commands_are_in_pipeline_js():
    assert "id: 'images-build-jobs'" in PIPELINE_JS and "textContent: 'Build image jobs'" in PIPELINE_JS
    assert "'build_spec'" in PIPELINE_JS and "'build_jobs_cmd'" in PIPELINE_JS
    assert "Image jobs are not built yet (" in PIPELINE_JS
    assert not re.search(r"\.(inner|outer)HTML\s*\+?=(?!=)", PIPELINE_JS), "assignment to innerHTML/outerHTML in pipeline.js"
    assert not re.search(r"https?://", PIPELINE_JS), "pipeline.js contains an http(s) URL"


def test_pipeline_js_parses_with_node():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; syntax check skipped")
    proc = subprocess.run([node, "--check", str(STATIC / "pipeline.js")], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_owner_rules_are_on_the_page():
    assert "Flow agents run on Haiku, effort LOW" in JS
    assert "Copy" in JS
    assert "not available yet" in JS.lower() or "Not available yet" in JS
    assert "--allow-spend" in JS
    assert "gap G1" in JS and "gap G12" in JS
    assert "EXECUTE " in JS
    assert "I looked at full size" in JS
