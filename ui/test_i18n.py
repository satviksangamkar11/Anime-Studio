"""English / Marathi checks for the Anime Studio UI (docs/UI_REDESIGN_PLAN_2026-11-07.md section 3.8, task T2).

Offline: reads static files and calls server.dispatch for the two data routes. No server is started, no network.
  1 the two string tables parse, have the same keys, no empty values, the same {placeholders};
  2 every literal t('key') and every data-i18n key used in the page exists in en.json;
  3 no orphan keys (every key is used by the page or by i18n.js);
  4 every Marathi value has Devanagari, except MR_LATIN_OK (names that stay in Latin letters);
  5 app.js and pipeline.js have no hard-coded English;
  6 index.html: every visible text sits under a data-i18n key; a data-i18n element has no child elements;
  7 the font and the string routes are served (the font check is skipped when the file is missing).
"""
import json
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
STATIC = HERE / "static"
I18N_DIR = STATIC / "i18n"

INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "style.css").read_text(encoding="utf-8")
I18N_JS = (STATIC / "i18n.js").read_text(encoding="utf-8")
APP = (STATIC / "app.js").read_text(encoding="utf-8")
PIPE = (STATIC / "pipeline.js").read_text(encoding="utf-8")

# Marathi values that stay in Latin letters on purpose (names, file paths). Keep this set under 25 keys.
MR_LATIN_OK = {"lang.ui_en", "adv.bridge.dir_final", "adv.bridge.dir_out"}

# The one line that wraps the helper in app.js and pipeline.js (its first argument is a variable, by design).
T_WRAPPER = "var t = function (k, v) { return window.I18N.t(k, v); };"

# Hard-coded English exceptions for check 5: quoted text that is code, not UI text. One reason each.
EXEMPT = {
    "X-UI": "HTTP header name",
    "application/json": "MIME type",
}


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


EN = _load(I18N_DIR / "en.json")
MR = _load(I18N_DIR / "mr.json")
KEY_RX = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")
PLACE_RX = re.compile(r"\{(\w+)\}")
DEVA_RX = re.compile(r"[ऀ-ॿ]")
LIT_T_RX = re.compile(r"(?<![\w$.])(?:I\.)?t\(\s*(['\"])([^'\"]*)\1")
ANY_T_RX = re.compile(r"(?<![\w$.])(?:I\.)?t\(")


def _code_text(text):
    """The text with // comments removed, for the scans that look at code."""
    return re.sub(r"//[^\n]*", "", text)


def _used_keys():
    """Every key the page or the helper uses: data-i18n, data-i18n-attr and quoted literals in the four files."""
    keys = set(re.findall(r'data-i18n="([^"]+)"', INDEX))
    for value in re.findall(r'data-i18n-attr="([^"]+)"', INDEX):
        for pair in value.split(";"):
            keys.add(pair.split(":", 1)[1].strip())
    for text in (I18N_JS, APP, PIPE):
        for lit in LIT_T_RX.findall(text):
            keys.add(lit[1])
    # the helper's STATUS_KEY and ERR_MAP tables name their keys as quoted literals, not as t() calls
    keys.update(re.findall(r"'([a-z0-9_]+(?:\.[a-z0-9_]+)+)'", I18N_JS))
    return keys


# ---------------------------------------------------------------- 1. the tables
def test_1_tables_parse_flat_and_have_the_same_keys():
    for name, table in [("en", EN), ("mr", MR)]:
        assert isinstance(table, dict), name + ".json is not an object"
        for key, value in table.items():
            assert isinstance(value, str), "%s.json: %s is not a string" % (name, key)
            if not key.startswith("_"):
                assert value.strip(), "%s.json: %s is empty" % (name, key)
                assert KEY_RX.match(key), "%s.json: key %r breaks the naming rule" % (name, key)
    assert set(EN) == set(MR), "keys only in en: %s; only in mr: %s" % (sorted(set(EN) - set(MR)), sorted(set(MR) - set(EN)))


def test_1b_placeholders_match_in_both_languages():
    for key, value in EN.items():
        if key.startswith("_"):
            continue
        assert sorted(PLACE_RX.findall(value)) == sorted(PLACE_RX.findall(MR[key])), "placeholders differ for " + key


# ---------------------------------------------------------------- 2. literal keys exist
def test_2_every_literal_key_and_data_i18n_key_exists_in_en():
    missing = set()
    for text in (I18N_JS, APP, PIPE):
        for _quote, lit in LIT_T_RX.findall(text):
            if lit not in EN:
                missing.add(lit)
    for key in re.findall(r'data-i18n="([^"]+)"', INDEX):
        if key not in EN:
            missing.add(key)
    for value in re.findall(r'data-i18n-attr="([^"]+)"', INDEX):
        for pair in value.split(";"):
            key = pair.split(":", 1)[1].strip()
            if key not in EN:
                missing.add(key)
    assert not missing, "keys used but not in en.json: " + ", ".join(sorted(missing))


def test_2b_t_is_only_called_with_a_literal_key_in_the_page_scripts():
    for name, text in [("app.js", APP), ("pipeline.js", PIPE)]:
        code = _code_text(text).replace(T_WRAPPER, "")
        literal_spans = {m.start() for m in LIT_T_RX.finditer(code)}
        for m in ANY_T_RX.finditer(code):
            assert m.start() in literal_spans, "%s: t( call without a string literal key at offset %d" % (name, m.start())


def test_2c_new_keys_follow_the_key_scheme():
    for key in list(EN) + list(MR):
        if key.startswith("_"):
            continue
        assert KEY_RX.match(key), "key breaks the scheme: " + key


# ---------------------------------------------------------------- 3. no orphan keys
def test_3_every_key_is_used_by_the_page_or_the_helper():
    used = _used_keys()
    orphans = []
    for key in EN:
        if key.startswith("_"):
            continue
        if key not in used:
            orphans.append(key)
    assert not orphans, "keys in en.json that nothing uses: " + ", ".join(sorted(orphans))


# ---------------------------------------------------------------- 4. Marathi is Devanagari
def test_4_every_marathi_value_has_devanagari_except_the_latin_names():
    assert len(MR_LATIN_OK) < 25
    for key, value in MR.items():
        if key.startswith("_") or key in MR_LATIN_OK:
            continue
        assert DEVA_RX.search(value), "Marathi value has no Devanagari: %s = %r" % (key, value)
    for key in MR_LATIN_OK:
        assert key in MR, "MR_LATIN_OK names a key that is not in mr.json: " + key


def test_4b_marathi_status_says_draft():
    assert "draft" in MR["_status"].lower()
    assert EN["_status"] == "source"


# ---------------------------------------------------------------- 5. no hard-coded English in the page scripts
def _english_literals(text):
    """Quoted text that reads as UI text: [A-Za-z]{2,} in a text, title, label, placeholder or message slot."""
    code = _code_text(text).replace(T_WRAPPER, "")
    # stageDetail() matches the server's English protocol strings (pipeline.py) and answers with t(); those literals are data, not UI text
    code = re.sub(r"function stageDetail\(.*?\n  \}\n", "", code, count=1, flags=re.S)
    word = r"'[^'\n]*[A-Za-z]{2,}[^'\n]*'"
    patterns = [
        r"(?:textContent|text|placeholder|title|label|hint|note|legend)\s*:\s*" + word,
        r"'(?:aria-label|data-label)'\s*:\s*" + word,
        r"\.(?:textContent|title|placeholder)\s*=\s*" + word,
        r"(?:showError|showSuccess|showMsg|showInline|confirmDialog|notice|chip|btn|openModal|new Error)\(\s*" + word,
        r"badge\(\s*[^,()]*,\s*" + word,
        r"(?:dataTable|fillTable|runsTable)\(\s*\[[^\]]*" + word,
        r"'[A-Z][a-z]+ [a-z]+[^'\n]*'",
    ]
    found = []
    for rx in patterns:
        for m in re.finditer(rx, code):
            if LIT_T_RX.match(code, m.start()) is None:
                found.append(m.group(0))
    return [f for f in found if not any(ex in f for ex in EXEMPT)]


def test_5_no_hard_coded_english_in_app_or_pipeline():
    for name, text in [("app.js", APP), ("pipeline.js", PIPE)]:
        found = _english_literals(text)
        assert not found, "%s has hard-coded English: %s" % (name, " | ".join(found[:20]))


# ---------------------------------------------------------------- 6. index.html: visible text is keyed
class _TextAudit(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
    SKIP = {"script", "style", "noscript"}

    def __init__(self):
        super().__init__()
        self.stack = []        # open elements: dict(tag, attrs, keyed, has_child)
        self.unkeyed = []      # visible text that has no data-i18n ancestor
        self.keyed_with_children = []
        self.skip_depth = 0

    def _mark_child(self):
        for el in self.stack:
            if el["keyed"]:
                el["has_child"] = True

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self.skip_depth += 1
        if tag in self.VOID:
            self._mark_child()
            return
        self._mark_child()
        self.stack.append({"tag": tag, "attrs": a, "keyed": "data-i18n" in a, "has_child": False})

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in self.SKIP:
            self.skip_depth -= 1
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                el = self.stack.pop(i)
                if el["keyed"] and el["has_child"]:
                    self.keyed_with_children.append(tag + " " + str(el["attrs"].get("id", "")))
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.skip_depth or not re.search(r"[A-Za-z]{2,}", data):
            return
        keyed = any(el["keyed"] for el in self.stack)
        risk = bool(self.stack) and "risk" in (self.stack[-1]["attrs"].get("class") or "").split()
        if not keyed and not risk:
            self.unkeyed.append(data.strip()[:60])


def _audit():
    audit = _TextAudit()
    audit.feed(INDEX)
    audit.close()
    return audit


def test_6_every_visible_word_in_index_has_a_key():
    audit = _audit()
    assert not audit.unkeyed, "visible text with no data-i18n key: " + " | ".join(audit.unkeyed)


def test_6b_a_keyed_element_has_no_child_elements():
    audit = _audit()
    assert not audit.keyed_with_children, "data-i18n element with child elements: " + ", ".join(audit.keyed_with_children)


def test_6c_the_language_switch_and_the_draft_note_exist():
    for elem_id in ["ui-lang-en", "ui-lang-mr"]:
        assert re.search(r'\sid="%s"' % elem_id, INDEX), elem_id + " missing"
    assert 'data-show-lang="mr"' in INDEX, "Marathi draft note missing"
    assert '<script src="i18n.js"></script>' in INDEX and INDEX.index("i18n.js") < INDEX.index("app.js")


# ---------------------------------------------------------------- 7. the i18n helper, the font and the routes
def test_7_i18n_js_has_no_outside_links_and_is_es2018():
    assert not re.search(r"https?://", I18N_JS), "i18n.js contains an http(s) URL"
    assert "fetch('i18n/'" in I18N_JS, "i18n.js must load the tables from the relative path i18n/"
    assert not re.search(r"\?\.(?!\d)", I18N_JS) and "??" not in I18N_JS
    for newer in ["replaceAll(", ".flat(", ".flatMap(", "Object.fromEntries", "Promise.allSettled", "matchAll(", "globalThis"]:
        assert newer not in I18N_JS, "newer than ES2018 in i18n.js: " + newer
    assert not re.search(r"\.(inner|outer)HTML\s*\+?=(?!=)", I18N_JS), "innerHTML assignment in i18n.js"


def test_7b_i18n_js_parses_with_node():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; syntax check skipped")
    proc = subprocess.run([node, "--check", str(STATIC / "i18n.js")], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_7c_font_face_is_bundled_and_relative():
    assert "@font-face" in CSS and 'font-family: "Noto Sans Devanagari"' in CSS
    assert 'url("fonts/NotoSansDevanagari-Variable.ttf")' in CSS
    assert "http" not in CSS.split("@font-face", 1)[1].split("}", 1)[0]


def test_7d_the_string_and_font_routes_are_served():
    import server
    api = server.Api(server.Config())
    for lang in ["en", "mr"]:
        raw = server.dispatch(api, "GET", "/i18n/%s.json" % lang, {}, {})
        assert isinstance(json.loads(raw.data.decode("utf-8")), dict), lang
    with pytest.raises(server.ApiError) as e:
        server.dispatch(api, "GET", "/i18n/xx.json", {}, {})
    assert e.value.code == 404


def test_7e_the_devanagari_font_is_served_when_present():
    import server
    font = HERE.parent / "styles" / "fonts" / "NotoSansDevanagari-Variable.ttf"
    if not font.is_file():
        pytest.skip("the Devanagari font is not in the tree")
    api = server.Api(server.Config())
    raw = server.dispatch(api, "GET", "/fonts/NotoSansDevanagari-Variable.ttf", {}, {})
    assert raw.ctype == "font/ttf"
    assert raw.data[:4] == b"\x00\x01\x00\x00"
