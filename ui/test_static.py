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


# ---------------------------------------------------------------------------
# U3 checks (2026-11-07): visual pass, labels, ids, endpoints, contrast.
# ---------------------------------------------------------------------------
from html.parser import HTMLParser

RESEARCH = HERE.parent / "research"
ADDENDUM = (RESEARCH / "UI_CONTRACT_ADDENDUM_2026-11-07.md").read_text(encoding="utf-8")
CONTRACT = (RESEARCH / "UI_AUDIT_AND_UPDATE_PLAN_2026-11-07.md").read_text(encoding="utf-8")


def _contract_endpoints():
    """Parse audit section 4a (the U1/U2 endpoint contract): returns list of (method, path)."""
    start = CONTRACT.index("### 4a.")
    end = CONTRACT.index("### 4b.", start)
    found = []
    for m in re.finditer(r"^\|\s*\d+\s*\|\s*(GET/POST|GET|POST)\s+(\S+)[^|]*\|", CONTRACT[start:end], re.M):
        for method in m.group(1).split("/"):
            found.append((method, m.group(2)))
    return found


def _literals(text):
    lits = set()
    for raw in re.findall(r"['\"`](/api/[^'\"`\s]*)", text):
        lits.add(re.sub(r"\$\{[^}]*\}", "{x}", raw).split("?")[0])
    return lits


def test_pipeline_js_endpoints_are_in_plan_or_contract():
    contract = _contract_endpoints()
    assert len(contract) >= 20, "audit section 4a did not parse (found %d rows)" % len(contract)
    # The addendum adds the voice, BGM and author endpoints (features k to n); they count as contract too.
    added = [m.group(1) for m in re.finditer(r"(?:GET/POST|GET|POST)\s+(/api/[^\s,{]+)", ADDENDUM)]
    paths = [p for _, p in _plan_endpoints()] + [p for _, p in contract] + [a.split("?")[0] for a in added]
    regexes = [_plan_path_regex(p) for p in paths]
    unknown = []
    for lit in sorted(_literals(PIPELINE_JS)):
        if lit in EXTRA_ENDPOINTS:
            continue
        ok = any(p.startswith(lit) for p in paths) if lit.endswith("/") else any(rx.match(lit) for rx in regexes)
        if not ok:
            unknown.append(lit)
    assert not unknown, "endpoints used by pipeline.js but not in PLAN section 4 or audit 4a: " + ", ".join(unknown)


def test_pipeline_js_is_es2018_syntax_only():
    assert not re.search(r"\?\.(?!\d)", PIPELINE_JS), "optional chaining is ES2020"
    assert "??" not in PIPELINE_JS, "nullish coalescing is ES2020"
    for newer in ["replaceAll(", ".flat(", ".flatMap(", "Object.fromEntries", "Promise.allSettled",
                  "matchAll(", "globalThis"]:
        assert newer not in PIPELINE_JS, "newer than ES2018 in pipeline.js: " + newer


class _LabelAudit(HTMLParser):
    """Collects label targets, controls and ids so that every label and control can be checked."""

    def __init__(self):
        super().__init__()
        self.ids = set()
        self.label_fors = set()
        self.empty_labels = []
        self.controls = []
        self._stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "label":
            self._stack.append({"for": a.get("for"), "control": False, "text": ""})
            if a.get("for"):
                self.label_fors.add(a["for"])
        elif tag in ("input", "select", "textarea") and a.get("type") not in ("hidden", "button", "submit"):
            for lbl in self._stack:
                lbl["control"] = True
            self.controls.append({"id": a.get("id"), "wrapped": bool(self._stack),
                                  "aria": "aria-label" in a or "aria-labelledby" in a})

    def handle_endtag(self, tag):
        if tag == "label" and self._stack:
            lbl = self._stack.pop()
            if not lbl["control"] and not lbl["for"]:
                self.empty_labels.append(lbl["text"].strip() or "(no text)")

    def handle_data(self, data):
        for lbl in self._stack:
            lbl["text"] += data


def _audit_index():
    audit = _LabelAudit()
    audit.feed(INDEX)
    audit.close()
    return audit


def test_every_label_is_bound_to_a_control():
    audit = _audit_index()
    assert not audit.empty_labels, "labels with no control: " + " | ".join(audit.empty_labels)
    dangling = sorted(f for f in audit.label_fors if f not in audit.ids)
    assert not dangling, "label for= points at a missing id: " + ", ".join(dangling)


def test_every_control_has_a_label():
    audit = _audit_index()
    unlabelled = [c["id"] or "(no id)" for c in audit.controls
                  if not c["wrapped"] and c["id"] not in audit.label_fors and not c["aria"]]
    assert not unlabelled, "controls with no label: " + ", ".join(unlabelled)


def _id_source(elem_id):
    """'html' when index.html holds the id, 'js' when pipeline.js builds it, else None."""
    if re.search(r"\sid=\"%s\"" % re.escape(elem_id), INDEX):
        return "html"
    if re.search(r"""['"]%s['"]""" % re.escape(elem_id), PIPELINE_JS):
        return "js"
    return None


def test_status_text_is_announced_to_screen_readers():
    for elem_id in ["story-status"]:           # static ids in index.html
        tag = re.search(r"<[^>]*\sid=\"%s\"[^>]*>" % re.escape(elem_id), INDEX)
        assert tag, "status element missing: " + elem_id
        assert re.search(r"aria-live=|role=\"(status|alert)\"", tag.group(0)), "not announced: " + elem_id
    assert "aria-live" in PIPELINE_JS, "pipeline.js builds status regions without aria-live"
    assert INDEX.count('role="alert"') <= 2, "too many alert regions (double announce)"


def test_wizard_controls_are_built_by_pipeline_js():
    """pipeline.js builds the wizard panels (the static copies were removed after the 2026-11-07 browser check)."""
    for elem_id in ["lang-all", "voice-save", "bgm-save", "render-prepare", "images-build-jobs", "analysis-run"]:
        assert _id_source(elem_id) == "js", elem_id + " is not built by pipeline.js"


def test_no_id_is_both_static_html_and_built_by_pipeline_js():
    """Browser check 2026-11-07: static copies of the wizard panels duplicated every id. One owner per id."""
    html_ids = re.findall(r'\sid="([^"]+)"', INDEX)
    assert len(html_ids) == len(set(html_ids)), "duplicate ids inside index.html"
    both = sorted(i for i in set(html_ids) if re.search(r"""id:\s*['"]%s['"]""" % re.escape(i), PIPELINE_JS))
    assert not both, "ids in index.html AND built by pipeline.js: " + ", ".join(both)


def test_no_kaliya_or_stale_copy_in_index():
    assert "Kaliya" not in INDEX, "project name must not be hard-coded in generic UI copy"
    assert "writer via" not in INDEX and "free NVIDIA tier" not in INDEX, "stale writer copy (M13)"
    assert "gap G1" not in INDEX, "stale build-jobs copy (M19)"


def test_dialog_and_lightbox_have_focus_and_close():
    assert re.search(r'class="dialog"[^>]*tabindex="-1"', INDEX), "dialog needs tabindex -1 (L5)"
    assert 'id="lightbox-close"' in INDEX, "lightbox needs a visible close button (L6)"


def test_css_has_no_unused_toast_and_keeps_reduced_motion():
    assert "success-toast" not in CSS, "unused toast must be removed (L9)"
    assert "prefers-reduced-motion: reduce" in CSS


def test_css_breakpoints_one_column_phone_two_columns_desktop():
    assert "@media (min-width: 900px)" in CSS and "@media (max-width: 759px)" in CSS
    assert re.search(r"#wiz-panels\s*\{[^}]*grid-template-columns:\s*1fr\s*;", CSS), "phone: one column"
    assert "grid-template-columns: 1fr 1fr" in CSS, "desktop: two columns"


def test_css_44px_touch_targets_and_pills():
    assert re.search(r"(^|\n)button\s*\{[^}]*min-height:\s*44px", CSS), "button min-height 44px missing"
    assert re.search(r"\n\.pill,\s*\.pill-btn\s*\{[^}]*min-height:\s*44px", CSS), "language pill min-height 44px missing"


def test_css_focus_ring_is_three_pixels_on_every_control():
    assert re.search(r":focus-visible\s*\{[^}]*outline:\s*3px solid var\(--focus\)", CSS), "3 px focus ring missing"
    assert re.search(r"input:focus-visible[^{]*\{[^}]*outline:\s*3px solid", CSS), "inputs need the focus ring"
    assert not re.search(r"\.overlay:focus-within \.dialog\s*\{\s*outline:\s*none", CSS), "dialog outline removed (L7)"


def test_css_no_horizontal_page_scroll_rules():
    assert re.search(r"html,\s*body\s*\{[^}]*max-width:\s*100%", CSS), "html/body max-width 100%"
    assert re.search(r"\.tablewrap\s*\{[^}]*overflow-x:\s*auto", CSS), "wide tables scroll inside their box"
    assert re.search(r"input,\s*select,\s*textarea\s*\{[^}]*max-width:\s*100%", CSS), "form controls max-width 100%"
    assert re.search(r"img,\s*video\s*\{[^}]*max-width:\s*100%", CSS), "media max-width 100%"
    assert "overflow-wrap: anywhere" in CSS, "long words must wrap"


def test_css_tables_stack_on_phone_with_data_labels():
    phone = CSS.index("@media (max-width: 759px)")
    assert re.search(r"content:\s*attr\(data-label\)", CSS), "td data-label rule missing"
    assert CSS.index("content: attr(data-label)") > phone, "data-label rule must sit in the phone block"


def _css_tokens(block_start):
    """Return the custom properties of the first {...} block after block_start."""
    i = CSS.index(block_start)
    j = CSS.index("}", i)
    return {k: v for k, v in re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;", CSS[i:j])}


LIGHT_TOKENS = _css_tokens(":root {")
DARK_TOKENS = [_css_tokens(':root:not([data-theme="light"])'), _css_tokens(':root[data-theme="dark"]')]


def _lum(hexcol):
    vals = [int(hexcol[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in vals]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _ratio(a, b):
    la, lb = sorted([_lum(a), _lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


TEXT_ON_BG = [("fg", "panel"), ("muted", "panel"), ("muted", "page-bg"), ("ok-fg", "tint-green"),
              ("err-fg", "tint-error-bar"), ("amber-fg", "amber-bg"), ("red-fg", "red"),
              ("blue-fg", "blue"), ("accent-fg", "accent"), ("#ffffff", "ok"), ("#ffffff", "grey"),
              ("#ffffff", "indigo")]


def _resolve(tokens, name):
    return name if name.startswith("#") else tokens[name]


def test_contrast_tokens_defined_for_light_and_dark():
    for name in ["fg", "page-bg", "panel", "muted", "focus", "ok-fg", "err-fg", "amber-fg", "amber-bg",
                 "red", "red-fg", "blue", "blue-fg", "accent", "accent-fg", "ok", "grey", "indigo"]:
        assert name in LIGHT_TOKENS, "light token missing: " + name
    for tokens in DARK_TOKENS:
        assert tokens, "dark token block not found"
        for name in ["fg", "page-bg", "panel", "muted", "focus", "err-fg", "red", "red-fg", "ok", "grey"]:
            assert name in tokens, "dark token missing: " + name


def test_text_contrast_meets_wcag_aa_in_light_and_dark():
    for label, tokens in [("light", LIGHT_TOKENS), ("dark", DARK_TOKENS[1])]:
        for fg, bg in TEXT_ON_BG:
            ratio = _ratio(_resolve(tokens, fg), _resolve(tokens, bg))
            assert ratio >= 4.5, "%s: %s on %s is %.2f:1 (need 4.5)" % (label, fg, bg, ratio)
