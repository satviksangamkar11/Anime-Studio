# Anime Studio control panel: redesign plan (2026-11-07)

Author: Opus planner (read-only pass; this file is the only file written).
Code planned against: `D:\aai work\anime_studio_merge` (integration branch): `ui/server.py`, `ui/pipeline.py`, `ui/static/{index.html, app.js, pipeline.js, style.css}`, `ui/PLAN.md`, `ui/test_*.py`, `director/write_pack.py`, `director/run_registry.py`, `director/retry_policy.py`, `director/story_state.py`, `h3/shot_table_spec.py`.
Evidence: `D:\aai work\anime_studio\research\UI_REVIEW_HAIKU_2026-11-07.md` (read in full).
Who uses it: a 60-year-old non-technical woman. She reads English and Marathi.
Who builds it: one Haiku extra-high coder, tasks T0 to T5 in order. Free reviewers (Super VL, Dots) check the result.

Words used in this plan:
- **main button**: the one big filled button of a step card (CSS class `btn-main`).
- **quiet button**: a secondary action (class `btn-quiet`, outline only).
- **helper details**: a closed `<details class="expert">` box inside a step card, label "Details for the helper". Raw codes, file names, commands and server text live here.
- **Experts area**: the old "Advanced tools" `<details id="advanced-tools">` at the bottom, renamed "For the helper: expert tools". Every old Advanced feature stays inside it.
- **key**: an i18n string key, for example `story.save_btn`.

Hard rules (from the brief; every task obeys them):
1. No Colab, GPU, render or paid model call anywhere, and none in tests. Claude never runs by default and never in tests. Tests replace `Api._start` with a fake (as `test_r3_fixes.py` already does) when they reach `/api/run`.
2. Never print, return or log a key. Availability checks count files or test `is_file()`; they never read a key file.
3. Do not touch Granth Studio or any story data (`stories/**`, `flow_outputs/**`). Browser checks press only read-only controls (listed per task).
4. Existing suites stay green: ui 252 pass + 1 known real-pack failure; h3 615; director 781; core 418. New tests are added on top.
5. Server stays on 127.0.0.1; keep the Host, Origin and `X-UI: 1` checks unchanged.
6. **Parity rule (owner, binding):** no existing feature may be dropped or reduced. Layout, wording and structure may change; every function in the parity inventory (section 9) must still exist and be reachable. Merging or moving is fine; deleting is not. Element ids that exist today are never renamed (tests and the parity check use them).
7. No external fonts, icons or scripts. Inline SVG icons only. The Devanagari font is the bundled `styles/fonts/NotoSansDevanagari-Variable.ttf`, served by the local server.
8. ES2018 only in JS (the tests ban `?.`, `??`, `replaceAll`, `flat`, `Object.fromEntries`, `matchAll`, `globalThis`, `Promise.allSettled`). No `innerHTML`, no `eval`, no `http(s)://` in any static file.

---

## 1. Haiku report: what I confirmed and what I rejected

Checked by reading the code. I did not open the page and did not re-take measurements.

| # | Haiku claim | Verdict | Evidence in the code |
|---|---|---|---|
| 1 | "[object Object]" in Advanced > Images > Shots, Q1-Q6 | **Confirmed** | `app.js fillReview` runs `String(a['Q1'])`; a real `*__review.json` holds `{"Q1": {"result": "PASS", "reason": "..."}}` (seen in `flow_outputs/anime_kaliya/adhyay_01/shots/ENV_KADAMBA_BANK_DAWN__v01__candA__review.json`). |
| 2 | Two story pickers disagree | **Confirmed, root cause found** | `app.js loadStory` keeps `S.story.slug` (starts `''`), so it falls back to `S.slugs[0]` (alphabetical first), never to the wizard's project story. Also `init()` calls `showSection('#story')` on page load, so this runs even while Advanced is closed. |
| 3 | Finals 0/114 (step 3) vs 18 (Advanced) | **Confirmed, root cause found: two different stories** | `app.js loadImages` calls `/api/images?adhyay=N` with no `story`, so `server.images()` defaults to `LEGACY_STORY = "kaliya_mardan"` (18 finals in `adhyay_01/final`). The wizard summary counts the project story. |
| 4 | Approve Gate A enabled while the stale banner says restart | **Confirmed** | `pipeline.js mkGateCard` never reads `State.version.stale`; `server.pipeline_gate` has no stale guard either. |
| 5 | Phone step list shows only step 1 | **Confirmed by CSS** | `style.css` phone block (`max-width: 759px`) lays `.stepper ol` out as one horizontal row. Pixel numbers not re-measured. |
| 6 | Small text | **Confirmed** | body `16px`; hints `0.92rem`; phone `.step-status` `0.7rem`, `0.65rem` below 390 px. |
| 7 | Step 2 writer is hard-wired; Claude/OpenRouter blocked | **Confirmed** | `pipeline.js WRITER_NAME = 'super-vl'`; `server.BANNED_PAIRS = {("--via","claude"),("--via","openrouter")}`; `WRITER_NAME` enum = super-vl, ultra. |
| 8 | Advanced "Writer model" dropdown is a second control | **Confirmed, plus a new bug** | `app.js writerRun` sends `{slug, pack, writer}` with **no `out_lang`**, and `server.b_write_pack` refuses that ("choose at least one output language"). So "Run writer: new pack" and "Resume pack" in Advanced fail every time today. |
| 9 | Stray bullets in Advanced nav | **Confirmed** | `.navlist` has no `list-style: none`. |
| 10 | Sticky log footer covers content | **Confirmed** | `.logbar { position: sticky }`. |
| 11 | Dead `#wiz-panels` CSS | **Confirmed, but must stay** | `test_static.test_css_breakpoints_one_column_phone_two_columns_desktop` asserts the `#wiz-panels { grid-template-columns: 1fr; }` rule. Keep the rule (harmless). |
| 12 | `_wiz_panels_removed.html` is served by the server | **Rejected** | `dispatch` serves `/` (index.html) and only `*.css` / `*.js` names. The file sits in the folder but is not reachable. Leave it. |
| 13 | Opening Advanced > Video calls Colab | **Confirmed** | `app.js loadVideo` ends with `loadColab(true)` (`colab sessions` + `colab usage`). |
| 14 | Approve confirmation button says "Run" | **Confirmed** | `pipeline.js confirmDialog` button text `'Run'`. |
| 15 | Contrast acceptable | **Partly rejected for the new target** | `--muted #555555` on `--page-bg #f6f4f1` = 6.78:1. Passes the old 4.5 test, fails the new 7:1 body-text target. |
| 16 | No language switch | **Confirmed** | none in `index.html`, `app.js`, `pipeline.js`. |
| 17 | 127.0.0.1, pid and "job: none" on the main screen | **Confirmed** | `index.html` header `.host`, `pipeline.js opsPanel`. |
| 18 | Claude path untested from the UI | **Cannot verify fully** | `stories/*/pack_opus_medium_v1` exists (so `--writer opus` ran from the command line), but no UI run exists, as the report says. |

New findings the report missed (all verified in code):

| # | Finding | Evidence | Handling |
|---|---|---|---|
| N1 | The main page calls the Colab CLI every ~30 s | `pipeline.js tick()` -> `loadOps()` every 6th poll -> `GET /api/ops` -> `Api.ops()` runs `colab sessions` | Fix B9: `/api/ops` checks sessions only with `?colab=1` (a button). |
| N2 | `#stale-banner` in index.html is dead | No JS shows it; the stale text is put into `#pipe-banner` by `pipeline.js renderBanner` | Merge into one banner (B7). |
| N3 | Wizard "Prepare render" sends `story: <pack>/shots.json`, but `b_h3` refuses shots.json ("must be an H3 story") | `pipeline.js renderActions` vs `server.b_h3` | Out of scope (needs the H3 story path). Plain error message only. Open question Q4. |
| N4 | The author panel says the server must start with `ANIME_STUDIO_ALLOW_FREE_MODEL=1`, but no code reads that variable; `author_status` always returns `run_allowed: False` | `server.author_status` | Keep behaviour (parity); show a plain "Not switched on yet" message; raw note in helper details. |
| N5 | Errors auto-hide after 8 s | `pipeline.js showError` timer | Errors stay until closed; successes still hide after 8 s (B10). |

---

## 2. Model chooser for step 2 ("Plan the story")

### 2.1 Options (display order: group NVIDIA, then OpenRouter, then Claude)

Speed and quality words are expectations, not measurements. The owner should confirm them (Q1). All Marathi text: **needs a native speaker to confirm**.

| id | Group | Plain English name | Marathi name (draft) | Cost label | Speed / quality (expected) | write_pack arguments the server builds | Availability check | tested flag |
|---|---|---|---|---|---|---|---|---|
| `nv-ultra` | nvidia | Free NVIDIA AI: Ultra (big, careful) | मोफत NVIDIA AI: Ultra (मोठा, काळजीपूर्वक) | Free | slow / high | command `write_pack`, args `{model: "nvidia/nemotron-3-ultra-550b-a55b"}` -> `--staged --via nvidia --model nvidia/nemotron-3-ultra-550b-a55b --out-lang L` | `nvidia_key_files > 0` (count of `<studio parent>/secrets/nvidia/nvidia_api_key*.txt`, same as `/api/status`) | true |
| `nv-super-vl` | nvidia | Free NVIDIA AI: Super VL (quicker) | मोफत NVIDIA AI: Super VL (जलद) | Free | medium / good | `write_pack`, `{model: "nvidia/nemotron-3.5-super-vl-120b-a12b"}` -> `--via nvidia --model nvidia/nemotron-3.5-super-vl-120b-a12b` | same as above | false (shown as "New: not tried yet for story plans") |
| `or-super-vl` | openrouter | Free AI: Super VL (recommended) | मोफत AI: Super VL (शिफारस केलेले) | Free | medium / good | `write_pack`, `{writer: "super-vl"}` -> `--writer super-vl` | OpenRouter key file exists: `Path(os.environ.get("OPENROUTER_KEY_FILE") or <studio parent>/loop_p0/secrets/openrouter_paid_key.txt).is_file()` (same path `write_pack.OPENROUTER_KEY` uses) | true (`pack_super-vl_20261106_v1`) |
| `or-ultra` | openrouter | Free AI: Ultra (slower, sometimes busy) | मोफत AI: Ultra (हळू, कधी कधी व्यस्त) | Free | slow / high | `write_pack`, `{writer: "ultra"}` -> `--writer ultra` | same as above | false |
| `claude-opus` | claude | Claude (may cost money; asks you first) | Claude (पैसे लागू शकतात; आधी विचारते) | May use the Claude subscription or cost money | medium / highest | command **`write_pack_claude`**, args `{}` -> `--staged --writer opus --out-lang L` (write_pack maps opus = via claude, model opus, effort medium) | `cfg.allow_claude` (server started with `--allow-claude`) **and** `shutil.which("claude") is not None` | true (`pack_opus_medium_v1` from the command line) |

Default: `or-super-vl` (today's writer, so nothing changes unless she picks another card).

Group names: `writer.group.nvidia` "Free AI from NVIDIA" / "NVIDIA चे मोफत AI"; `writer.group.openrouter` "Free AI through OpenRouter" / "OpenRouter मार्फत मोफत AI"; `writer.group.claude` "Claude (asks you first)" / "Claude (आधी तुम्हाला विचारते)".

### 2.2 New read-only endpoint `GET /api/writers`

Response (exact shape; names and descriptions are NOT sent; the page takes them from i18n keys `writer.<id>.name` and `writer.<id>.desc`):

```json
{
  "default": "or-super-vl",
  "claude_allowed": false,
  "confirm_word": "CLAUDE",
  "checks": {"nvidia_key_files": 15, "openrouter_key_file": true, "claude_cli": true},
  "options": [
    {"id": "nv-ultra", "group": "nvidia", "command": "write_pack",
     "args": {"model": "nvidia/nemotron-3-ultra-550b-a55b"},
     "cost": "free", "speed": "slow", "quality": "high", "tested": true,
     "available": true, "reason": ""},
    {"id": "claude-opus", "group": "claude", "command": "write_pack_claude", "args": {},
     "cost": "subscription", "speed": "medium", "quality": "highest", "tested": true,
     "available": false, "reason": "claude_off"}
  ]
}
```

- `reason` is one of `""`, `"no_nvidia_key"`, `"no_openrouter_key"`, `"claude_off"`, `"claude_missing"`. The page shows `t('writer.reason.' ...)` through a literal map (section 3.4 rule: no built keys).
- `cost` is one of `"free"`, `"subscription"`; `speed` one of `"fast"`, `"medium"`, `"slow"`; `quality` one of `"good"`, `"high"`, `"highest"`.
- No key text, no file path, no file size. A test (T1) puts `nvapi-TESTSECRET123` in a fake key file and asserts the response text does not contain it.

### 2.3 Exact server changes (`ui/server.py`, task T1)

1. `Config`: add `allow_claude: bool = False`. `main()`: add `ap.add_argument("--allow-claude", action="store_true", help="owner only: the Claude writer becomes possible; each run still needs a preview and the typed word CLAUDE")`; `cfg = Config(spend=a.allow_spend, allow_claude=a.allow_claude)`. Startup print adds `claude ON|OFF`.
2. `WRITER_MODEL = _enum("model", "nvidia/nemotron-3-ultra-550b-a55b", "nvidia/nemotron-3.5-super-vl-120b-a12b")`. **Do not change** `WRITER_NAME` or `WRITER_ROUTE` (`test_registry` asserts `set(WRITER_ROUTE) == {"super-vl","ultra"}` and that `writer: "opus"` is refused by `write_pack`).
3. Add constants:
   ```python
   CLAUDE_CONFIRM = "CLAUDE"
   DEFAULT_WRITER_CHOICE = "or-super-vl"
   WRITER_CHOICES = (   # GET /api/writers; display order; the page names them with i18n keys writer.<id>.name
       {"id": "nv-ultra", "group": "nvidia", "command": "write_pack", "args": {"model": "nvidia/nemotron-3-ultra-550b-a55b"},
        "cost": "free", "speed": "slow", "quality": "high", "tested": True, "needs": "nvidia"},
       {"id": "nv-super-vl", "group": "nvidia", "command": "write_pack", "args": {"model": "nvidia/nemotron-3.5-super-vl-120b-a12b"},
        "cost": "free", "speed": "medium", "quality": "good", "tested": False, "needs": "nvidia"},
       {"id": "or-super-vl", "group": "openrouter", "command": "write_pack", "args": {"writer": "super-vl"},
        "cost": "free", "speed": "medium", "quality": "good", "tested": True, "needs": "openrouter"},
       {"id": "or-ultra", "group": "openrouter", "command": "write_pack", "args": {"writer": "ultra"},
        "cost": "free", "speed": "slow", "quality": "high", "tested": False, "needs": "openrouter"},
       {"id": "claude-opus", "group": "claude", "command": "write_pack_claude", "args": {},
        "cost": "subscription", "speed": "medium", "quality": "highest", "tested": True, "needs": "claude"},
   )
   ```
4. `BANNED_PAIRS = {("--via", "claude"), ("--via", "openrouter"), ("--writer", "opus")}`. `check_argv(argv, allow=frozenset())`: skip a pair when `(argv[i-1], tok) in allow`. Messages: keep the old one for `--via`; for `("--writer","opus")` raise `bad("claude runs only through the Claude choice (write_pack_claude)")`. This keeps every old block and adds one; the only way to `--writer opus` is the one command whose `allow` names it.
5. `Cmd` dataclass: add `confirm: str = ""` (typed word for a non-spend command), `needs: str = ""` (`"claude"` = needs `cfg.allow_claude`), `allow: frozenset = frozenset()` (pairs this command may carry).
6. `b_write_pack(cfg, a, writer=None)`: `name = writer or a.get("writer") or DEFAULT_WRITER`; use `name` in the finished-pack hint and in the final `["--writer", name]`. Add `def b_write_pack_claude(cfg, a): return b_write_pack(cfg, {**a, "writer": None, "model": None}, writer="opus")`.
7. `write_pack_route(a, writer=None)`: if `writer == "opus"` return `"writer opus: claude opus, effort medium (Claude subscription; may cost money)"`; legacy NVIDIA and writer lines unchanged (test_registry checks the super-vl text exactly).
8. New command row (after `write_pack`):
   ```python
   Cmd("write_pack_claude", "C, W", False, {"slug": A(SLUG, True), "pack": A(NAME, True), "out_lang": A(out_lang_arg)},
       b_write_pack_claude, confirm=CLAUDE_CONFIRM, needs="claude", allow=frozenset({("--writer", "opus")})),
   ```
9. `Api.preview`: after `normalize`, `if spec.needs == "claude" and not self.cfg.allow_claude: raise ApiError(403, "claude is off: the server was not started with --allow-claude")`. Call `check_argv(argv, spec.allow)`. `route = write_pack_route(args, "opus" if spec.id == "write_pack_claude" else None) if spec.id in ("write_pack", "write_pack_claude") else None`. Confirm: spend keeps `EXECUTE n`; else `confirm = spec.confirm or None`. Store `"needs": spec.needs` in the token record. Return `"needs_confirm": bool(confirm)` (was `spec.spend`; same value for every old command).
10. `Api.run`: replace `if rec["spend"] and body.get("confirm") != rec["confirm"]:` with `if rec["confirm"] and body.get("confirm") != rec["confirm"]:` (same message `type exactly: ...`). Before that: `if rec.get("needs") == "claude" and not self.cfg.allow_claude: raise ApiError(403, "claude is off: the server was not started with --allow-claude")`.
11. `Api.writers()`:
    ```python
    def writers(self) -> dict:
        c = self.cfg
        nv = len(list((c.studio.parent / "secrets" / "nvidia").glob("nvidia_api_key*.txt")))
        orf = Path(os.environ.get("OPENROUTER_KEY_FILE") or c.studio.parent / "loop_p0" / "secrets" / "openrouter_paid_key.txt").is_file()
        cli = shutil.which("claude") is not None
        def reason(o):
            if o["needs"] == "nvidia": return "" if nv else "no_nvidia_key"
            if o["needs"] == "openrouter": return "" if orf else "no_openrouter_key"
            return "claude_off" if not c.allow_claude else ("" if cli else "claude_missing")
        opts = [{**{k: v for k, v in o.items() if k != "needs"}, "available": not reason(o), "reason": reason(o)} for o in WRITER_CHOICES]
        return {"default": DEFAULT_WRITER_CHOICE, "claude_allowed": c.allow_claude, "confirm_word": CLAUDE_CONFIRM,
                "checks": {"nvidia_key_files": nv, "openrouter_key_file": orf, "claude_cli": cli}, "options": opts}
    ```
    (`import shutil` at the top.) `dispatch` GET: `if path == "/api/writers": return api.writers()`.
12. `Api.status()`: add `"claude_allowed": c.allow_claude`.
13. Audit: no change needed; `preview` and `run` already audit the argv (which shows the model). The run registry already records `via`, `model`, `effort` per run through `run_registry.Recorder` in `write_pack.main` (writer tag `super-vl`, `ultra`, `opus` or `nvidia-<model short name>`). So "which model ran" is recorded with no registry change. The page shows it from `/api/story` `latest_model` and the Past work table.
14. `ui/PLAN.md` section 4 table: add rows (the static test parses this table):
    - `| GET | `/api/writers` | none | `{default, claude_allowed, confirm_word, checks: {nvidia_key_files, openrouter_key_file, claude_cli}, options: [{id, group, command, args, cost, speed, quality, tested, available, reason}]}`; read only; never key text |`
    - `| GET | `/i18n/{lang}.json` | none | the UI string table for en or mr |`
    - `| GET | `/fonts/NotoSansDevanagari-Variable.ttf` | none | the bundled Devanagari font (font/ttf) |`
    - Edit the `/api/run` row: `confirm` also for commands with a typed word (`write_pack_claude`: "CLAUDE").

### 2.4 Front-end behaviour (`pipeline.js`, task T3)

- `State.writers = null`, loaded once by `loadWriters()` (`GET /api/writers`) in `init()` and on the slow tick (every 6th poll).
- `State.writerChoice`: on load read `localStorage['studio.writer']` in try/catch. If the stored id is `claude-opus`, missing, unknown or not `available`, use `State.writers.default`. **Claude is never restored from storage**: it must be picked again on every page load. Save to storage on change only for free options.
- The chooser is built inside the step 2 card, above the main button, by `writerChooser(project)`:
  - container `div#writer-choice` (role `radiogroup`, `aria-labelledby` its heading).
  - three `fieldset.writer-group` with legend = group name, each holding cards: `label.writer-card` with `input type=radio name=writer-opt id="writer-opt-<id>"`, name (`writer.<id>.name`), one plain line (`writer.<id>.desc`), and three small tags: cost (`writer.cost.free` "Free" / `writer.cost.subscription` "May cost money"), speed (`writer.speed.*`), quality (`writer.quality.*`), plus `writer.tag.new` "New: not tried yet for story plans" when `tested` is false.
  - not available: radio `disabled`, card class `is-off`, reason line `writer.reason.<code>` (for example "Off: no NVIDIA key file found. Ask your helper." / "बंद: NVIDIA ची चावी-फाइल सापडली नाही. मदतनीसाला विचारा.").
  - Claude card picked: an amber warning box `div#writer-claude-warn` appears under the cards: `writer.claude.warn` "Claude is not a free AI. It may use your Claude subscription or cost money. It runs only after you type CLAUDE." plus a checkbox `input#writer-claude-ack` labelled `writer.claude.ack` "I understand. It may cost money." The main button stays disabled until the box is ticked.
- Main button label follows the choice: `plan.run_btn` "Make the story plan with {name}" (name = short name `writer.<id>.short`, for example "Super VL").
- Press:
  1. Same checks as today (story saved, pack name, saved languages, stage ready or rejected). Also: chosen option `available`.
  2. `POST /api/pipeline/project {story_slug, pack}` (unchanged).
  3. `POST /api/preview {command: opt.command, args: Object.assign({slug, pack, out_lang: savedLangs.join(',')}, opt.args)}`.
  4. Free option: `confirmDialog` with `plan.confirm_free` "Make the story plan for "{story}" with {name}? It is free. It takes about 10 to 40 minutes." Yes label `dialog.yes_start` "Yes, start". The route and argv go into the dialog's helper details.
  5. Claude: `confirmDialog` with `plan.confirm_claude` "Use Claude to make the story plan for "{story}"? This may use your Claude subscription or cost money.", option `typed: data.confirm_text` ("CLAUDE"). The dialog shows `input#confirm-typed` with label `dialog.type_word` "To go ahead, type the word {word} (English letters)". "Yes, use Claude" (`dialog.yes_claude`) stays disabled until `value.trim().toUpperCase() === word`. Then `POST /api/run {token, confirm: word}`.
  6. Two steps for Claude: tick the warning box, then type the word. The server refuses without `--allow-claude` (403) and without the exact word (400).
- The working-on line (old scope bar, id `wizard-scope`) shows `scope.writer` "AI for the plan: {name}". After a plan exists, step 2 shows `plan.written_by` "This plan was written by: {model}" from `State.storyList` row `latest_model` (already sent by `/api/story`).
- Error messages (through the server-error map, section 3.5): `claude is off` -> `err.srv.claude_off` "Claude is switched off on this computer. Ask your helper to switch it on, or choose a free AI." / "या संगणकावर Claude बंद आहे. मदतनीसाला सुरू करायला सांगा, किंवा मोफत AI निवडा."; `type exactly: CLAUDE` -> `err.srv.type_exactly`; key missing -> the card is disabled before any call.

### 2.5 Advanced writer controls (`app.js`, task T4)

`#story-model` stays (parity) but is filled from `GET /api/writers` with the **free** options only (`command === 'write_pack'`), labels `t('writer.<id>.name')`, value = option id. Keep the line `var WRITER_NAMES = ['super-vl', 'ultra'];` (`test_registry` asserts it) as the fallback list when `/api/writers` fails. `writerRun` sends `Object.assign({slug, pack, out_lang: <saved languages of the story, from GET /api/story row output_languages>}, opt.args)`; if the story has no saved languages it shows `adv.story.err_no_langs` and does not call the server. This also fixes the N8 bug. Claude is not offered in Advanced (one Claude path only, in step 2).

---

## 3. English / Marathi (i18n)

### 3.1 Files

- `ui/static/i18n.js` (new, loaded first): the helper.
- `ui/static/i18n/en.json`, `ui/static/i18n/mr.json` (new): flat objects `{"key": "text"}`. Placeholders `{name}`. One meta key in each: `"_status"`: en `"source"`, mr `"draft: every string needs a native Marathi speaker to confirm"`. Keys starting with `_` are not UI text.
- Server routes (T1): `GET /i18n/(en|mr).json` -> `ui/static/i18n/<lang>.json` (`Raw(JSON_CT, bytes)`, 404 when missing); `GET /fonts/NotoSansDevanagari-Variable.ttf` -> `<studio>/styles/fonts/NotoSansDevanagari-Variable.ttf` (`Raw("font/ttf", bytes)`). Both are fixed whitelists; no user text reaches a path.

### 3.2 `i18n.js` (exact behaviour)

```js
(function () {
  'use strict';
  var LANGS = ['en', 'mr'];
  var STORE = 'studio.lang';
  var I = { lang: 'en', en: {}, mr: {}, missing: [] };
  function stored() { try { var v = localStorage.getItem(STORE); return LANGS.indexOf(v) >= 0 ? v : 'en'; } catch (e) { return 'en'; } }
  function load(lang) {
    return fetch('i18n/' + lang + '.json', { headers: { 'X-UI': '1' } })
      .then(function (r) { return r.ok ? r.json() : {}; }, function () { return {}; });
  }
  I.t = function (key, vars) {
    var s = I[I.lang][key];
    if (s === undefined) {
      s = I.en[key];
      if (s === undefined) { I.missing.push(key); return '[' + key + ']'; }
      if (I.lang !== 'en') I.missing.push(I.lang + ':' + key);
    }
    if (!vars) return s;
    return s.replace(/\{(\w+)\}/g, function (m, k) { return vars[k] === undefined || vars[k] === null ? m : String(vars[k]); });
  };
  I.apply = function (root) { /* every [data-i18n] -> textContent = t(key);
     every [data-i18n-attr="placeholder:key;title:key;aria-label:key"] -> setAttribute */ };
  I.setLang = function (lang) { /* guard LANGS; I.lang = lang; try localStorage.setItem; document.documentElement.lang = lang;
     I.apply(document); set aria-pressed on #ui-lang-en / #ui-lang-mr;
     window.dispatchEvent(new CustomEvent('studio:lang', { detail: lang })); */ };
  I.serverError = function (msg) { /* section 3.5: returns {text, raw} */ };
  I.ready = Promise.all([load('en'), load('mr')]).then(function (r) {
    I.en = r[0]; I.mr = r[1]; I.lang = stored(); document.documentElement.lang = I.lang; I.apply(document);
    /* bind click on #ui-lang-en and #ui-lang-mr -> I.setLang(...) ; set aria-pressed */
  });
  window.I18N = I;
})();
```

- Language switch ids are `ui-lang-en` / `ui-lang-mr`. **Never** start them with `lang-`: those ids are the output-language pills and `pipeline.js captureDraft` skips `lang-*`.
- `app.js` and `pipeline.js`: first line inside the IIFE `var t = function (k, v) { return window.I18N.t(k, v); };`. Their `init` runs after `window.I18N.ready.then(init, init)` (instead of the `DOMContentLoaded` call; keep the `readyState` guard around it).
- `pipeline.js`: `window.addEventListener('studio:lang', function () { render(true); renderBanner(); updateStepper(...) via render })`. `app.js`: listener re-runs `renderHeader()` and `showSection(S.section)` (data reload; after T4, `showSection('video')` no longer calls Colab).
- `index.html`: `<html lang="en">`; scripts in this order: `i18n.js`, `app.js`, `pipeline.js`.

### 3.3 index.html marking rules

- Every element with visible text gets `data-i18n="key"` and keeps its English text as the default content (works before JS and keeps old literal checks readable).
- An element with `data-i18n` must have **no child elements** (textContent replaces them). Labels that wrap a control get a `<span data-i18n="...">` for their text, for example `<label class="field"><span data-i18n="adv.story.slug">Story</span> <select id="story-slug"></select></label>`.
- Attributes: `data-i18n-attr="title:key"`, `placeholder:key`, `aria-label:key`, separated by `;`.
- Risk tag spans (`.risk`) keep their one-letter code as text (it is a code, inside the Experts area) and get `data-i18n-attr="title:risk.R"` etc.

### 3.4 Key naming and the initial table outline

Scheme: `<area>.<thing>[_<kind>]`, lower case, digits, `_` and `.` only (regex `^[a-z0-9_]+(\.[a-z0-9_]+)+$`). Kinds: `_btn` button, `_label` field label, `_hint` hint, `_title` heading, `_ph` placeholder, `_say` the one sentence of a card. **No built keys**: never `t('status.' + s)`. Use a literal map object, for example `var STATUS_KEY = { locked: 'status.locked', ready: 'status.ready', ... }` and `t(STATUS_KEY[s] || 'status.unknown')`. This keeps every key visible to the tests.

Key groups (approximate counts; the coder fills English from the existing UI text plus the wording in sections 5 and 9, then Marathi):

| Group | Prefix | Owner task | ~Keys | Content |
|---|---|---|---|---|
| App shell | `app.` | T2 | 12 | title, skip link, noscript, loading, working-on line, footer "Marathi text is a draft" notice |
| Language | `lang.` | T2 | 8 | switch labels ("English", "मराठी"), output languages en/hi/mr names, "all three" |
| Common | `common.` | T2 | 30 | close, cancel, yes, no, open, show, hide, details for the helper, loading, none, unknown, saved, yes/no words, minutes, seconds |
| Status words | `status.` | T2 | 12 | locked, ready, running, waiting_approval, approved, rejected, done, failed, open, stopped, unknown, not_run |
| Banner | `banner.` | T2 | 6 | stale server, low disk, check again |
| Dialog | `dialog.` | T2 | 16 | please check, yes start, yes approve, yes use Claude, no go back, type the word, show exact command, preview expires, preview expired |
| Errors (client + server map) | `err.` | T2 | 45 | network down, timeout, generic, details; `err.srv.*` (section 3.5) |
| Success | `ok.` | T3 | 15 | story saved, languages saved, voices saved, music saved, voice map saved, gate approved/sent back, choice recorded, image jobs built |
| Header/scope | `scope.` | T3 | 8 | story, draft, languages, AI for the plan, paid work on/off, nothing running, running |
| Steps | `step.` | T3 | 70 | 6 names, 6 short names, 6 one-sentence intros, `step.<id>.say.<status>` (about 30 combos), progress line, open this step |
| Story (step 1) | `story.` | T3 | 55 | picker, new name, text, replace, save, languages box, voices, music, voice map, YouTube link, results |
| Next step box | `next.` | T3 | 18 | 15 story_state keys + title + continue + nothing to do |
| Warnings | `warn.` | T3 | 8 | no_story_json, no_run_report, source_changed_since_save, empty_pack, other |
| Plan (step 2) | `plan.` | T3 | 40 | pack name, run button, confirms, what to check, scenes table headers, parts table, people/places/things/style, validator texts, written by |
| Writer chooser | `writer.` | T3 | 45 | groups, 5 x (name, short, desc), cost/speed/quality words, reasons, Claude warning and tick box, new tag |
| Gates | `gate.` | T3 | 35 | approval 1-4 titles, scope line, note label, approve, send back, type START, blocks (validator, stale, Step 9, language rows), what happens next, by/when/note |
| Pictures (step 3) | `pics.` | T3 | 20 | build button, helper instructions, counts, notes, packet modal |
| Summary (step 4) | `sum.` | T3 | 30 | tiles, tables, checks (6 known names), warnings |
| Video (step 5) | `video.` | T3 | 45 | prepare, assets, fallback table + 4 human choices, final check, detail writer (author) panel, Gate D rows, BGM, safe zone |
| Files (step 6) | `files.` | T3 | 10 | part number, show clips, clip line, not put together yet |
| Past work | `runs.` | T3 | 30 | table headers, statuses, detail headings, report link |
| Computer check | `ops.` | T3 | 15 | disk, server, Colab ledger, sessions not checked, check sessions button |
| Experts area | `adv.*` | T2 (index.html text) + T4 (app.js text) | 170 | `adv.nav.*`, `adv.story.*`, `adv.images.*`, `adv.bridge.*`, `adv.video.*`, `adv.export.*`, `adv.log.*`, `adv.modal.*` |
| Risk tags | `risk.` | T2 | 6 | R, W, N, $, OPS, X explanations |
| Icons alt | `icon.` | T3 | 8 | aria labels for SVG icons |

Total about 760 keys. Append-only ownership: a task adds keys only in its own groups, in both `en.json` and `mr.json`, and never edits another task's groups.

### 3.5 Server error map (`I18N.serverError(msg)`)

Returns `{text, raw}`. `text` is plain and translated; `raw` is the original English (shown only inside the error bar's helper details `#error-details`). Order matters (first match wins). Patterns are tested against the server's `error` string:

| Pattern (JS regex) | Key | English |
|---|---|---|
| `/^save the story first/` | `err.srv.save_story_first` | Save your story first. |
| `/choose at least one output language/` | `err.srv.no_languages` | Choose the video languages and press "Save languages" first. |
| `/is already finished \(PACK\.md exists\): use (\S+)/` | `err.srv.pack_finished` {name} | This plan name is already used. Use the new name {name}. |
| `/SOURCE\.md exists: tick overwrite/` | `err.srv.story_exists` | A story is already saved here. Tick "Replace the saved story" to replace it. |
| `/story is over 200 KB/` | `err.srv.story_too_big` | The story is too long (more than about 200 KB). |
| `/another job is running/` | `err.srv.job_running` | Other work is still running. Wait until it finishes. |
| `/preview expired/` | `err.srv.preview_expired` | You waited too long. Press the button again. |
| `/this preview was already used/` | `err.srv.preview_used` | This was already started. Press the button again for a new start. |
| `/unknown preview token/` | `err.srv.preview_unknown` | The page and the program lost track. Press the button again. |
| `/arguments changed since the preview/` | `err.srv.args_changed` | Something changed. Press the button again. |
| `/spend is OFF/` | `err.srv.spend_off` | Paid work is switched off. Only your helper can switch it on. |
| `/^type exactly: (.+)$/` | `err.srv.type_exactly` {word} | Type the word {word} exactly. |
| `/claude is off/` | `err.srv.claude_off` | (section 2.4) |
| `/out of date: restart/` | `err.srv.stale` | The program is out of date. Ask your helper to restart it. |
| `/host not allowed\|origin not allowed\|X-UI/` | `err.srv.guard` | The page was blocked for safety. Open it from this computer only. |
| `/^no such story/` | `err.srv.no_story` | This story was not found. |
| `/^no such pack\|pack folder does not exist/` | `err.srv.no_pack` | This plan was not found. Make the story plan first. |
| `/no validator report/` | `err.srv.no_validator` | The plan has not been checked yet. |
| `/h3 engine not built yet/` | `err.srv.h3_missing` | The video engine is not installed yet. |
| `/must be an H3 story/` | `err.srv.h3_story_needed` | The video plan file is not ready yet. Ask your helper. |
| `/slug\|pack name: lower-case/` | `err.srv.bad_name` | Use small English letters, numbers and _ only (no spaces). |
| `/balance unknown\|below 1\.5 x\|above the cap/` | `err.srv.spend_refused` | The paid check said no. Nothing was started. |
| `/unknown job/` | `err.srv.unknown_job` | That work is no longer listed. |
| (client) `Cannot reach the studio server` | `err.net.down` | The program is not answering. Ask your helper to start it. |
| (client) `did not answer in 2 minutes` | `err.net.timeout` | The program took too long. Try again. |
| anything else | `err.generic` | Something did not work. The details for your helper are below. |

Both JS files get `showApiError(err)` = `showError(I18N.serverError(errText(err)))` and replace **every** `showError(errText(e|err))` with `showApiError(e|err)`. Client-side checks call `showError(t('...'))` (no raw part).

### 3.6 Devanagari font, offline

In `style.css` (T2):

```css
@font-face {
  font-family: "Noto Sans Devanagari";
  src: url("fonts/NotoSansDevanagari-Variable.ttf") format("truetype");
  font-weight: 100 900;
  font-display: swap;
  unicode-range: U+0900-097F, U+1CD0-1CFF, U+200C-200D, U+20B9, U+25CC, U+A830-A83F, U+A8E0-A8FF;
}
body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial, "Noto Sans Devanagari", sans-serif; }
:lang(mr) body, html[lang="mr"] body { font-family: "Noto Sans Devanagari", system-ui, "Segoe UI", Roboto, Arial, sans-serif; line-height: 1.7; }
```

The URL is relative; the page is served at `/`, so it resolves to `/fonts/...`, which T1 serves. The licence `styles/fonts/LICENSES/OFL_notosansdevanagari.txt` already exists.

### 3.7 Marathi wording guidance (for the coder and the native speaker)

- Simple everyday spoken Marathi, polite `तुम्ही` form, short sentences (one idea each).
- Prefer common words: चित्र (not प्रतिमा), आराखडा (plan), मंजूर करा (approve), परत पाठवा (send back), जतन करा (save), तपासा (check), थांबवा (stop).
- Keep words she already knows in English or as loanwords: व्हिडिओ, फाइल, AI, YouTube, Claude, NVIDIA, OpenRouter, GPU, Colab. Model names stay in Latin letters.
- Digits: Western 0-9 in both languages (no conversion code). Native speaker to confirm (Q3).
- Typed words (START, CLAUDE, AUTHOR FIELDS, EXECUTE n) stay in English letters; the Marathi label says "इंग्रजी अक्षरांत टाइप करा".
- Starting points: the Haiku report section B columns MR. Every Marathi string is a draft; `mr.json` `_status` says so, and in Marathi mode the page footer shows `app.mr_draft` "मराठी मजकूर अजून तपासायचा आहे (draft)".

### 3.8 Automatic completeness checks (new `ui/test_i18n.py`, T2; extended by later tasks only through the data files)

1. `en.json` and `mr.json` parse; flat `str -> str`; same key set; no empty value; for every key the `{placeholder}` sets are equal.
2. Every `t('<key>')` / `t("<key>")` first-argument literal in `i18n.js`, `app.js`, `pipeline.js`, and every `data-i18n` / `data-i18n-attr` key in `index.html`, exists in `en.json`. A `t(` call whose first argument is not a string literal fails the test (except inside `i18n.js` itself and the one `var t = function (k, v)` line).
3. No orphan keys: every non-`_` key of `en.json` appears as a quoted literal in one of the four files.
4. Every `mr.json` value contains a Devanagari character (`[\u0900-\u097F]`), except keys in an explicit `MR_LATIN_OK` set in the test (for example `lang.ui_en`, `writer.*.short` model names). The set must stay under 25 keys.
5. Hard-coded English scan on `app.js` and `pipeline.js` (comments `// ...` stripped first). Fail when a quoted literal with `[A-Za-z]{2,}` appears in:
   - `(textContent|text|placeholder|title|label|hint|note|legend)\s*:\s*'...'`, `'aria-label'\s*:\s*'...'`, `'data-label'\s*:\s*'...'`;
   - `\.textContent\s*=\s*'...'`, `\.title\s*=\s*'...'`, `\.placeholder\s*=\s*'...'`;
   - first argument of `showError|showSuccess|showMsg|showInline|confirmDialog|notice|chip|btn|openModal|new Error` and the second argument of `badge(`;
   - array literals passed to `dataTable(`, `fillTable(`, `runsTable(`.
   - Any literal matching `'[A-Z][a-z]+ [a-z]+[^']*'` (an English sentence) that is not the argument of `t(` and not in `EXEMPT` (a small set in the test with a one-line reason each, for example `'Content-Type'`).
6. Hard-coded English scan on `index.html`: every text node with `[A-Za-z]{2,}` outside `<script>`, `<style>`, `<noscript>` must sit in an element (or ancestor) carrying `data-i18n`; elements with `data-i18n` have no child elements; `.risk` spans are exempt (one-letter codes).
7. Font and routes: `style.css` contains the `@font-face` block above and no `http`; `dispatch(api, "GET", "/fonts/NotoSansDevanagari-Variable.ttf")` returns `Raw` with `ctype == "font/ttf"` and bytes starting `b"\x00\x01\x00\x00"` (skip when the real file is missing); `/i18n/en.json` and `/i18n/mr.json` return JSON objects; `/i18n/xx.json` is 404.

---

## 4. Visual design spec (`style.css`, task T2)

### 4.1 Tokens (keep every existing token name; the tests read them)

Root size: `html { font-size: 125%; }` (1rem = 20px). Every size in the file is in rem, so the whole page scales; no `font-size` below `0.85rem` (17px) anywhere (new test).

Light (`:root`) and the two dark blocks (`@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {...} }` and `:root[data-theme="dark"] {...}` - keep both, the tests read both):

| Token | Light | Dark | Use | Contrast (computed) |
|---|---|---|---|---|
| `--page-bg` | `#f7f5f0` | `#14130f` | page | - |
| `--panel` | `#ffffff` | `#1e1d19` | cards | - |
| `--fg` | `#1c1b1a` | `#f3f1ec` | body text | 17.2 / 14.9 on panel |
| `--muted` | `#4a4744` | `#c9c4ba` | hints | 9.2 panel, 8.5 page (light); 9.7 / 10.7 (dark) |
| `--line` | `#8a847b` | `#5a564f` | borders | non-text |
| `--field-line` | `#6b6660` | `#8a8a94` | input borders | non-text |
| `--focus` | `#0b57d0` | `#8ab4ff` | focus ring | 6.4 / 8.1 (non-text, needs 3) |
| `--primary` (new) | `#1f4e8c` | `#9ec1ff` | main button | white on it 8.3; dark `--primary-fg #0d1b2e` 9.5 |
| `--primary-fg` (new) | `#ffffff` | `#0d1b2e` | main button text | - |
| `--blue` / `--blue-fg` | `#1f4e8c` / `#ffffff` | `#9ec1ff` / `#0d1b2e` | running chip | 8.3 / 9.5 |
| `--ok` | `#165c33` | `#165c33` | done chip bg (white text) | 8.0 |
| `--ok-fg` / `--tint-green` | `#14532d` / `#e7f5ec` | `#bdf0cf` / `#163626` | success text on tint | 8.1 / 10.4 |
| `--err-fg` / `--tint-error-bar` | `#7a1010` / `#fde8e8` | `#ffd9d6` / `#3e1715` | error bar | 9.4 / 12.1 |
| `--amber-fg` / `--amber-bg` | `#3d2c00` / `#ffe2a8` | `#2a1f00` / `#ffd27a` | waiting chip, Claude warning | 10.7 / 11.4 |
| `--red` / `--red-fg` | `#a8231b` / `#ffffff` | `#ff9b91` / `#1a0606` | danger button | 7.2 / 9.7 |
| `--grey` | `#55524e` | `#55524e` | locked chip (white text) | 7.8 |
| `--indigo` | `#1d1b3a` | `#2d2b5c` | header | white 16.5 / 13.0 |
| `--accent` / `--accent-fg` | `#f0b45a` / `#1c1b1a` | same | current step marker | 9.3 |
| other existing tokens | keep names; adjust values so every text pair in `TEXT_ON_BG` of `test_static.py` is >= 7:1 | | | |

Spacing: `--s1 4px; --s2 8px; --s3 12px; --s4 16px; --s5 24px; --s6 32px; --s7 48px`. Radius: `--r-sm 8px; --radius 12px` (existing name); `--r-lg 16px`. Shadow: keep `--shadow`.

Type scale (rem at 20px root): body `1rem` (20px) line-height 1.55 (1.7 in Marathi); hint `0.9rem` (18px); chip/tag `0.85rem` (17px); h1 brand `1.2rem`; step card title h3 `1.3rem` (26px); section h2 `1.4rem`; tile value `1.6rem`; main button `1.1rem` bold.

Focus: keep `:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; }` and `input:focus-visible, select:focus-visible, textarea:focus-visible { outline: 3px solid var(--focus); }` (tests assert these).

### 4.2 Components (class names the coder uses)

| Component | Spec | States |
|---|---|---|
| Button base `button` | `min-height: 48px` (**change the test regex in `test_css_44px_touch_targets_and_pills` from 44px to 48px**, T2), padding `0 var(--s5)`, radius `--r-sm`, border 2px `--field-line`, bg `--panel`, text `--fg`, font 1rem | `:hover` bg `--hover`; `:disabled` opacity .55, cursor not-allowed, and the reason is always written in text next to it (never only a tooltip); focus ring |
| Main button `.btn-main` | `min-height: 56px`, bg `--primary`, text `--primary-fg`, bold 1.1rem, full width on phone, min-width 280px desktop, leading inline SVG icon 24px | disabled: grey bg `--grey`, white text + reason line `.btn-reason` under it |
| Quiet button `.btn-quiet` | transparent bg, 2px border `--line`, text `--fg` | as base |
| Danger button `.danger` | bg `--red`, text `--red-fg` | Experts area only (Colab run) |
| Step card `.card.step` | bg `--panel`, radius `--r-lg`, padding `--s5`, shadow; header row: number circle 40px, title h3, status chip on the right, status icon | `.is-open` shows the body; `.is-current` 4px left border `--accent`; collapsed card = header + one sentence + quiet button "Open this step" (`id="open-step-<id>"`) |
| Stepper `#stepper` | desktop >= 900px: left column, vertical list, each item a `button.step-btn` (min-height 56px) with number, name, status word; phone < 760px: grid `repeat(3, 1fr)`, two rows, each tile min-height 64px, number + short name + status icon (no status word), all six visible, no horizontal scroll | current: accent border; done: green check icon; waiting: amber clock icon; locked: grey lock icon; failed: red alert icon |
| Progress line `#progress-line` | one sentence above the cards: "Step 2 of 6: Plan the story - needs your OK" (1.1rem, bold) | - |
| Banner `#pipe-banner` | amber/red full-width box under the header, icon + plain text + quiet button "Check again" (`id="banner-recheck"`, calls `loadOps()` + `/api/version`) | stale = red tint; low disk = amber |
| Error bar `#error-bar` | under header, `--tint-error-bar` bg, `--err-fg` text, icon, text `#error-text`, `details#error-details` > `pre#error-raw` (hidden when no raw text), button "Close" | `.success` = green tint; errors stay until closed; success hides after 8 s; on show `scrollIntoView({block: 'nearest'})` |
| Chip `.chip` | 0.85rem, padding `2px 10px`, radius 999px, always icon + word (colour is never the only signal) | status classes keep their current names (`status-locked`, ...) |
| Dialog `#modal .dialog` | max-width 640px, padding `--s5`, title h2, message 1.1rem, buttons row: "No, go back" first (quiet, receives focus), then the yes button (main) | typed-word input `#confirm-typed` 1.2rem, uppercase letter-spacing; yes disabled until it matches |
| Form field | label above control, label 1rem bold, control min-height 48px, 2px border, `max-width: 100%` (test), hint under it in `--muted` | error: 2px `--red` border + message under the field |
| Writer card `.writer-card` | full-width radio card, min-height 72px, radio 24px, name bold, desc, tags row | `:has(input:checked)` not used (old browsers): add class `.is-picked` in JS; `.is-off` dims + reason |
| Helper details `details.expert` | summary "Details for the helper" (0.9rem, muted, with an info icon), body monospace for raw text | closed by default; open state kept in `State.openDetails[id]` across re-renders |
| Log footer `.logbar` | **not sticky** (`position: static`), inside the Experts area only | - |
| Advanced nav `.navlist` | `list-style: none; margin: 0; padding: 0; flex-wrap: wrap` (fixes stray bullets and cut-off "Export") | - |

### 4.3 Icons (inline SVG, built with `document.createElementNS`, no innerHTML)

`pipeline.js` gets `function icon(name)` returning an `<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" focusable="false">` with `stroke="currentColor" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"` and these paths:

| name | elements |
|---|---|
| `check` | path `M5 13l4 4L19 7` |
| `x` | path `M6 6l12 12M18 6L6 18` |
| `lock` | rect x5 y11 w14 h10 rx2; path `M8 11V7a4 4 0 0 1 8 0v4` |
| `clock` | circle cx12 cy12 r9; path `M12 7v5l3 3` |
| `alert` | circle cx12 cy12 r9; path `M12 7v6M12 17h.01` |
| `arrow` | path `M5 12h14M13 6l6 6-6 6` |
| `info` | circle cx12 cy12 r9; path `M12 11v6M12 7h.01` |
| `globe` | circle cx12 cy12 r9; path `M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18` |

The header language switch uses the `globe` icon written inline in `index.html`.

### 4.4 Page layout (top to bottom)

```
+--------------------------------------------------------------+
| [Anime Studio]        (globe) [English] [मराठी]   Paid work: OFF |   header (sticky on desktop only)
+--------------------------------------------------------------+
| ! The program is out of date. Ask your helper to restart it. [Check again] |  banner (only when needed)
| x Error text ....                     [Details for the helper] [Close]     |  error bar (only when needed)
+--------------------------------------------------------------+
| Working on: upanishad_ganga_ep4_ashtavakra   Plan: pack_...  Languages: Marathi   AI for the plan: Super VL |
| Nothing is running. Nothing starts until you say yes.        |  job line
+-----------+--------------------------------------------------+
| 1 Story  v| Step 2 of 6: Plan the story - needs your OK       |
| 2 Plan   *|  [ step 2 card, open ]                             |
| 3 Pictures|  [ step 3 card, closed: one line + Open ]          |
| 4 Summary |  ...                                               |
| 5 Video   |  > Past work (records)            (closed)         |
| 6 Files   |                                                    |
+-----------+--------------------------------------------------+
| > For the helper: expert tools   (closed: computer check, old Advanced sections, log) |
+--------------------------------------------------------------+
```

Phone (375 px): header two rows (brand + switch; paid chip); stepper 3x2 grid; cards full width; buttons full width; nothing sticky except the error bar while visible.

Open step rule: `State.openStep` (null = server `current`). Stepper button or "Open this step" sets it and scrolls to the card. `continueStory` sets it too. Only the open card shows its body; all other cards show header + one sentence.

---

## 5. Per-step spec

Format per step: names (EN / MR, MR = draft), the one sentence, wireframe, main button, what pressing does, what can go wrong (key: plain English), what is protected. Gates sit inside their step card as a box "Your OK".

### 5.1 Step 1 Story / कथा

Sentence `step.story.intro`: "Paste your story, choose the video languages, and save." / "तुमची कथा पेस्ट करा, व्हिडिओच्या भाषा निवडा आणि जतन करा."

```
[1] Story                                   (check) Finished
Where we are now: Next: check the plan for mistakes.   [Go to that step]
  > Details for the helper  (raw next-step text, warnings with file names)
Which story?        [ upanishad_ganga_ep4_ashtavakra      v ]
Short name for a new story (small English letters, numbers, _)  [________]
Paste your story here (up to about 200 KB)
[                                                             ]
[ ] Replace the story already saved (careful)
Which languages should the video be in? The first one you tick is the main one.
 [x] English  [ ] Hindi  [x] Marathi   (Select all three)
 Saved languages: English, Marathi
  [========  MAIN BUTTON  ========]
> More choices: voices and music        (closed)
    Voice settings / Background music / Which voice speaks for each character
> Get the story from a YouTube video instead   (closed)
```

Main button (one at a time, by state):
- text unsaved or no story yet -> `story.save_btn` "Save my story" (`#btn-save-story`).
- story saved, languages ticked but differ from saved (or none saved) -> `story.lang_save_btn` "Save my language choice" (`#lang-save`, styled main).
- both saved -> `story.next_btn` "Go to step 2: Plan the story" (`#btn-continue` when the next-step box offers it; otherwise a new `#btn-story-next` that sets `State.openStep = 'analysis'`).
The two other buttons render as quiet buttons in place (same ids, same handlers).

Press: unchanged handlers (`POST /api/story/{slug}`, then `POST /api/pipeline/project`; `POST /api/story/{slug}/languages`).
Errors: `story.err_bad_name` "Use small English letters, numbers and _ only, 1 to 40 characters."; `story.err_too_long`; `err.srv.story_exists`; `story.err_unsaved_switch` "Your text has changes that are not saved. Save first, then switch story."; `story.err_pick_lang` "Tick at least one language first."
Protected: overwrite needs the tick box (server keeps `SOURCE.md.bak-<stamp>`); no model call; no money.
"More choices" contents unchanged in function: voice engine checkbox `#voice-en-h3` with plain text `story.voice_h3_label` "Use the program's own English voice (takes extra time; leave off)"; music `#bgm-on`, `#bgm-manifest` (label `story.bgm_file_label` "Music list file (the file that lists your songs)"), `#bgm-save`; voice map rows and `#voice-map-save`. YouTube box unchanged in function (`#link-url`, `#link-lang`, `#link-asr` with plain options, `#link-overwrite`, `#link-run`, candidates `#link-cand-*`, `#link-replace`).
Warnings from story_state: plain line via `WARN_KEY` map on `w.key.split(':')[0]` (`warn.no_story_json` "A record file is missing. Ask your helper to fix it."), raw text in helper details.

### 5.2 Step 2 Plan the story / कथेचा आराखडा

Sentence: "Choose an AI. It reads your story and writes a plan of scenes. Then you check it." / "AI निवडा. तो तुमची कथा वाचून दृश्यांचा आराखडा लिहील. मग तुम्ही तो तपासा."

```
[2] Plan the story                          (clock) Needs your OK
Which AI should write the plan?
 Free AI from NVIDIA
  ( ) Free NVIDIA AI: Ultra (big, careful)        Free  Slow  High quality
  ( ) Free NVIDIA AI: Super VL (quicker)          Free  Medium  Good   New: not tried yet
 Free AI through OpenRouter
  (o) Free AI: Super VL (recommended)             Free  Medium  Good
  ( ) Free AI: Ultra (slower, sometimes busy)     Free  Slow  High
 Claude (asks you first)
  ( ) Claude (may cost money)   Off: ask your helper to switch it on.
Name of this plan (leave as shown)   [pack_super-vl_20261107_v1]
  [====  Make the story plan with Super VL  ====]
This plan was written by: nemotron-3.5-super-vl
What you need to check: 57 scenes in 6 parts, 404 seconds
  Parts table (Part, Scenes, Seconds)
  First 5 scenes (Scene, Part, Seconds, What happens)   [Show all 57 scenes]
  People / Places / Things
Check the plan for mistakes:  (check) No mistakes found   [Check again]
--- Your OK 1: the scene list ---- (see 5.3)
  > Details for the helper  (route + argv of the last preview, server detail, method column,
                              validator codes and warnings, pack.check JSON, modes)
```

Main button by state: `ready`/`rejected` -> `plan.run_btn` (`#analysis-run`); plan written but validator not run or failed -> `plan.check_btn` "Check the plan for mistakes" (`#validator-run`); validator clean and Gate A open -> Gate A approve is the main button.
Press: section 2.4. Validator: unchanged (`POST /api/pack/validate`).
Errors: `plan.err_no_story` "Save your story first."; `plan.err_no_pack` "Type a name for this plan."; `err.srv.no_languages`; `plan.err_not_ready` "This step cannot start yet."; `err.srv.pack_finished`; `err.srv.claude_off`.
Protected: free by default; Claude needs server flag + tick + typed CLAUDE; finished plans are never overwritten (server).
Phone: the shot list shows the first 5 rows grouped by part, button `#plan-show-all` "Show all {n} scenes" toggles `State.showAllShots` (new id, built by pipeline.js).

### 5.3 Your OK 1 (Gate A) / पहिली मंजुरी: दृश्यांची यादी

Sentence: "Look at the scene list. If it is right, approve it. If not, write what is wrong and send it back."

```
Your OK 1: the scene list                  (clock) Waiting for you
For story upanishad_ganga..., plan pack_...
Your note (needed only to send back, up to 300 letters)  [__________]
  [====  Yes, approve the scene list  ====]    [ Send back ]
After you approve, the pictures step opens.
```

Main button `gate.approve_btn_A` (`#gate-approve-A`) -> confirm dialog `gate.confirm_A` "Approve the scene list for "{story}"?" with yes `dialog.yes_approve` "Yes, approve" and "No, go back" -> `POST /api/pipeline/gate`.
Blocks (button disabled + reason written under it): validator not run `gate.off_no_check` "First check the plan for mistakes."; validator errors `gate.off_errors` "The check found mistakes. They must be fixed first."; **stale server** `gate.off_stale` "The program is out of date. Ask your helper to restart it before you approve." (new, B1; also disables Send back).
Errors: `gate.err_note` "Write a note of 1 to 300 letters to send it back."; `err.srv.stale`.
Protected: decision written only to `runs/approvals.jsonl`; server refuses when stale (409) and when the story/pack is not the project pointer (existing).
Approved/rejected info stays: by, when, note (`gate.by`, `gate.when`, `gate.note`).

### 5.4 Step 3 Pictures / चित्रे

Sentence: "Make the list of pictures to draw. The picture helpers draw them; you check them."

```
[3] Pictures                                (lock) Not open yet: waiting for your OK 1
Finished pictures: 0 of 114    [=====-----]   Waiting: 0   Checked: 0
  [====  Prepare the picture list (no payment)  ====]
  [ Make the instruction sheet for the picture helpers ]
The picture helpers are started by Claude in the chat. This page shows their progress.
--- Your OK 2: the pictures ---
  > Details for the helper  ("Flow agents run on Haiku, effort LOW", spec/jobs file paths, "Full-size check by Claude")
```

Main: `pics.build_btn` (`#images-build-jobs`) until jobs exist (`/api/images` jobs for this story > 0), then `pics.packet_btn` (`#images-packet`) becomes main.
Press: unchanged (`build_spec` then `build_jobs_cmd` through preview/run; packet via `/api/packet`, modal with Copy / Close).
Errors: `pics.err_gate_a` "Approve the scene list first."; `pics.err_no_jobs` "The picture list is not made yet. Press "Prepare the picture list" first."; `pics.err_no_full_jobs` "No list covers every scene yet."; build failure `pics.err_build` "Making the picture list did not work." + raw in details.
Protected: writes files only; no model call; existing spec/series never overwritten from the page (`overwrite: false`).

### 5.5 Your OK 2 (Gate B) / दुसरी मंजुरी: चित्रे

Sentence: "When every picture is finished and checked, approve them." Same box as 5.3 with `gate.approve_btn_B` "Yes, approve the pictures". Blocks: stale server. After: "After you approve, the summary step opens."

### 5.6 Step 4 Check the summary / सारांश तपासा

Sentence: "Read the numbers. If they look right, type START to approve the video plan."

```
[4] Check the summary                       (clock) Needs your OK
 Parts 6 | Scenes 57 | Seconds 403.5 | People 8 | Places 7
 Pictures finished 0 of 114 | Clips planned 171 | Minutes to make (estimate) 388
 > More numbers (parts table, people/places/things, tries per clip, clips ready, picture states)
 Checks:  (check) Scene file is there  (check) Every scene has a length  ...
 Warning: Pictures are not finished: 0 of 114
--- Your OK 3: the video plan ---
 Type START (English letters) to approve:  [_____]
  [====  Yes, approve the video plan  ====]   [ Send back ]
  > Details for the helper (estimated GPU units tile "Est. G4 units", raw check names)
```

Main: Gate C approve (`#gate-approve-C`), enabled only when `#gate-confirm-C` value is `START` (unchanged rule; also blocked when stale).
Errors: `gate.err_start` "Type START exactly."
Protected: typed word; decision file only.
Check names: `SUM_CHECK_KEY` literal map for the 6 server names (`shots.json present` -> `sum.check.shots_file` ...), unknown names shown raw inside helper details only.

### 5.7 Step 5 Make the video / व्हिडिओ बनवा

Sentence: "Get the video plan ready. The paid video making is done by your helper, not from this page."

```
[5] Make the video                          (lock) Not open yet
  [====  Get the video ready (no payment)  ====]
  Not ready yet: the video plan file is missing. The problems are listed below.
Pictures and sound files: Pictures 0 of 114, Clips 0, Stand-ins 0, Out of date: no
  No problems stop the video.
Scenes that need your decision (only when present):
  Scene | Tries | Level | What next | Your choice [Try other AI] [Relax the rules] [Skip, use a stand-in] [Give a sample video]  Note [___]
Final video check: not run yet
> Automatic detail writer (for the helper)   (closed: author panel, unchanged function)
--- Your OK 4: final check ---
  Background music: off   Subtitles stay inside the safe edges
  English: not ready yet  (voice files 0 of 0, subtitle file missing, video file missing)
  [====  Yes, approve the final check  ====]   [ Send back ]
  Approve is off: the final video check has not passed yet.
```

Main: `video.prepare_btn` (`#render-prepare`) until prepared; Gate D approve when open.
Human choice labels: `video.choice.switch_models` "Try another AI", `video.choice.relax_requirements` "Relax the rules", `video.choice.skip_with_placeholder_missing_clip` "Skip it and use a stand-in", `video.choice.supply_reference_video` "I will give a sample video" (literal map `CHOICE_KEY`; buttons send the same codes as today).
Errors: `err.srv.h3_story_needed` (N3); `err.srv.h3_missing`.
Protected: prepare-only (no GPU); author run stays off (`run_allowed` false, plain text `video.author_off` "Not switched on yet. Nothing is sent."); Gate D blocked until Step 9 passes and every language row is ready (unchanged); stale block.

### 5.8 Step 6 Final files / अंतिम फाइली

Sentence: "See the clips of one part in order. The final joined video is not made here yet."

```
[6] Final files                             (lock) Not open yet
Part number [ 1 ]
  [====  Show the clips of this part  ====]
Part 1: 12 clips. SHOT-001 (try 1) ...
Not joined yet.
```

Main: `files.show_btn` (`#export-show`). Errors: `files.err_part` "The part number must be 1 or more." Protected: read only.

### 5.9 Experts area (old Advanced) / मदतनीसासाठी: तज्ञ साधने

Summary text `adv.title` "For the helper: expert tools" / "मदतनीसासाठी: तज्ञ साधने". Closed by default. Contents, in order:
1. `#expert-ops` (new static container in index.html, filled by `pipeline.js opsPanel()` instead of the wizard): computer check (disk C/D, server started time, pid, out-of-date flag, host 127.0.0.1, Colab ledger units, sessions: "not checked" + quiet button `#ops-colab-check` "Check Colab sessions (contacts Google, free)" -> `GET /api/ops?colab=1`).
2. `#msg-bar` (unchanged).
3. Nav (5 buttons, same ids; texts `adv.nav.story` "Story text", `adv.nav.images` "Pictures", `adv.nav.bridge` "Key frames", `adv.nav.video` "Video clips", `adv.nav.export` "Final files") and the five sections with every control unchanged in function (inventory rows E*).
4. The log footer (not sticky): `adv.log.title` "What the program is doing (last lines)", Stop button `adv.log.stop_btn` "Stop the work now".
Every Advanced risk tag stays, with a translated `title`. A short line at the top `adv.intro`: "These tools are for your helper. Some of them change files. Paid tools stay off unless the helper switched them on."

### 5.10 Past work / मागील कामे

`<details id="runs-details">` closed by default, around the existing `#runs-panel` (pipeline.js builds the panel inside it). Table columns on desktop: Story, Result, Last time (others move into the row details: Where the story came from, AI used, Plans, Times run). Row click unchanged.

---

## 6. Bug-fix list

| id | Defect (verified) | File | Fix |
|---|---|---|---|
| B1 | Approve/Send back enabled while the server is out of date | `pipeline.js mkGateCard`; `server.py pipeline_gate` | Client: if `State.version && State.version.stale`, set `blockReason = t('gate.off_stale')` and disable both buttons. Server: at the top of `pipeline_gate`, `if api.version()["stale"]: raise ApiError(409, "the studio server is out of date: restart it before you approve or reject")`. |
| B2 | "[object Object]" in Q1-Q6 | `app.js fillReview` | `var v = a['Q' + (i+1)]; var res = v && typeof v === 'object' ? v.result : v; var why = v && typeof v === 'object' ? v.reason : '';` cell text = `t(Q_KEY[res] || 'adv.images.q_unknown')` where `Q_KEY = {PASS: 'adv.images.q_pass', BLOCK: 'adv.images.q_block', ADVISORY: 'adv.images.q_advisory', UNSURE: 'adv.images.q_unsure'}`; cell `title = why`; unknown string values shown as-is; `-` when missing. `showReview` lists the six reasons. |
| B3 | Two story pickers disagree | `app.js loadStory`, `selectSlug`, `#story-slug` change | Default slug = `window.StudioWizard.project().story_slug` when set (else the first slug). Changing `#story-slug` posts `POST /api/pipeline/project {story_slug, pack: ''}` then `window.StudioWizard.refresh()`, so both pickers always show one story. Section heading shows `adv.story.following` "Story: {slug} (the same as at the top)". |
| B4 | Finals 0/114 vs 18 | `app.js loadImages` | Send `&story=` + project slug (`window.StudioWizard.project().story_slug`; omit when empty, which keeps the legacy default). Images heading shows `adv.images.for_story` "Pictures of story: {slug}". If the two numbers still differ for the same story, report it (server folder resolution differs: `read_images` vs `pipeline.facts`); do not change server logic in this redesign. |
| B5 | Phone step list off-screen | `style.css` phone block; `index.html` stepper | 3x2 grid (section 4.2); `.step-btn` buttons. |
| B6 | Small text | `style.css` | Section 4.1 (root 125%, no size below 0.85rem). |
| B7 | Dead `#stale-banner` plus `#pipe-banner` | `index.html`, `pipeline.js renderBanner` | Remove the dead `#stale-banner` element from index.html (its text moves to `banner.stale`), keep the `#stale-banner` CSS selector harmlessly or delete it; `#pipe-banner` gains the "Check again" button. `test_status_text_is_announced` limit (<= 2 `role="alert"` in index.html) still holds. |
| B8 | Advanced writer runs always refused (no `out_lang`) | `app.js writerRun` | Section 2.5. |
| B9 | Page calls Colab every ~30 s; Video section calls Colab on open | `server.py Api.ops`, `dispatch`; `app.js loadVideo` | `def ops(self, q=None)`: `listed = self._cli_text(["sessions"]) if (q or {}).get("colab") == "1" else None`; add `"sessions_checked": listed is not None` in `colab`; dispatch `return api.ops(q)`. `loadVideo` no longer calls `loadColab`; the "Check Colab" button still does (parity). |
| B10 | Errors vanish after 8 s | `pipeline.js showError` | No timer for errors; success keeps 8 s. |
| B11 | Approve confirmation says "Run" | `pipeline.js confirmDialog` | New signature `confirmDialog(message, argvText, onConfirm, onCancel, opts)`; `opts.yesKey` (default `dialog.yes_start`), `opts.typed`. Cancel text `dialog.no_back` "No, go back". argv goes in a `details.expert` inside the dialog. Keep `State.confirmPending` logic and the ids `confirm-cancel`, `confirm-run` (tests). |
| B12 | Stray bullets, "Export" cut off | `style.css .navlist` | `list-style: none; margin: 0; padding: 0;` plus `flex-wrap: wrap`. |
| B13 | Sticky log footer covers content | `style.css .logbar` | `position: static`. |
| B14 | Raw codes on main screens (R/W/N/$, gate, stage, pack, validator, H3, 127.0.0.1, pid, argv) | `pipeline.js`, `index.html` | Plain words on cards; raw values only in helper details or the Experts area. |
| B15 | Disabled "Build*" with "gap G1" | `app.js renderJobs` | Keep the disabled button (parity, id class `act-build`) with label `adv.images.build_off` "Not available yet"; the "gap G1" note goes to its title attribute text in en.json (the old test `"gap G1" in JS` is retargeted to app.js + en.json, section 7 T2). |

---

## 7. Implementation tasks (run one after another; each ends with all suites green)

Common to every task:
- Run before and after: `C:\Python314\python.exe -m pytest -q -p no:cacheprovider ui` (expect 252 pass + 1 known real-pack failure + new tests), and once at the end of T1 and T5 the h3, director and core suites with the commands the project already uses (record counts in PROJECT_LOG.md).
- `node --check ui\static\app.js ui\static\pipeline.js ui\static\i18n.js` (pass).
- Append one line to `PROJECT_LOG.md` per step (blot.md rule 1).
- A task is **not done** until every parity row it owns (column "Task" in section 9) is ticked in the task report, with how it was checked.
- Key-file rule: never open, print or copy anything under `secrets/` or `loop_p0/secrets/`.

### T0 Parity guard (first, before any product change)

Files owned: `ui/test_parity.py` (new).
Done when:
- [ ] `test_parity.py` exists and passes on the **unchanged** code.
- [ ] It holds `INVENTORY` = list of `(row_id, anchor)` for every row of section 9 (anchor = element id, class token such as `act-packet`, or command id). Rows marked NEW in section 9 are in a separate `NEW_ROWS` list, checked only from the task that adds them (`pytest.skip` until the anchor exists is **not** allowed after T3/T4: the T5 run must find every anchor).
- [ ] Test `test_every_inventory_anchor_exists`: each anchor is found as `id="anchor"` or inside a `class="..."` value in index.html, or inside a quoted literal in app.js / pipeline.js (so `'act act-packet'` and `'gate-approve-' + id` both match). Anchors written `key:<name>` (rows I04, R01-R03) are i18n keys: they go in `NEW_ROWS` and are checked against `en.json` from T3 on. Anchors marked NEW in section 9 also go in `NEW_ROWS`.
- [ ] Test `test_every_command_is_reachable`: for every key of `server.COMMANDS`, the id appears quoted in app.js or pipeline.js, or is in `SERVER_ONLY = {"check_pack": "reached by GET /api/pack?check=1 (Advanced Check pack)", "queue_status": "no UI today", "tidy_apply": "no UI today", "colab_sessions": "no UI today (GET /api/colab is used)", "colab_usage": "no UI today (GET /api/colab is used)", "colab_run_dry": "no UI today", "yt_transcript": "reached by POST /api/story/{slug}/link"}`. A command missing from both fails. A new command (`write_pack_claude`) must be quoted in pipeline.js.
- [ ] Test `test_every_route_is_reachable`: `ROUTES` table = (method, route, needle substring that must appear in app.js + pipeline.js). Use exactly section 9.2. Plus `test_no_unlisted_route`: scan `inspect.getsource(server.dispatch)` for `path == "/api/...` and `re.fullmatch(r"/api/...` and assert each appears in `ROUTES` (normalised) or in `SERVER_ONLY_ROUTES = {}` (empty today).
Tests to write: the four above. Browser checks: none.

### T1 Server (model chooser, i18n and font routes, stale guard, ops without Colab)

Files owned: `ui/server.py`, `ui/PLAN.md` (section 4 rows only), `ui/test_redesign_server.py` (new).
Done when:
- [ ] Section 2.3 items 1-14 done exactly; B1 (server half) and B9 (server half) done.
- [ ] Routes `/i18n/(en|mr).json` and `/fonts/NotoSansDevanagari-Variable.ttf` (section 3.1).
- [ ] No change to Host/Origin/X-UI checks, `BANNED_TOKENS`, spend logic, `WRITER_NAME`, `WRITER_ROUTE`.
- [ ] Parity rows owned: R-routes for `/api/writers`, `/api/ops` (sessions still reachable with `?colab=1`).
Tests to write (`test_redesign_server.py`; reuse the fake-studio fixtures style of `test_ui.py` / `test_registry.py`; **no real process**: `monkeypatch.setattr(api, "_start", lambda *a, **k: SimpleNamespace(id="job1"))` wherever `/api/run` is reached):
1. `/api/writers` shape: keys, 5 options in the order of section 2.1, default `or-super-vl`; with 2 fake NVIDIA key files `nvidia_key_files == 2`; with no OpenRouter file (`monkeypatch.setenv("OPENROUTER_KEY_FILE", str(tmp/"none.txt"))`) the two `or-*` options are unavailable with `no_openrouter_key`; Claude unavailable with `claude_off` when `allow_claude=False`; with `allow_claude=True` and `monkeypatch.setattr(server.shutil, "which", lambda n: None)` reason `claude_missing`.
2. No key leak: a fake key file containing `nvapi-TESTSECRET123` and an OpenRouter file containing `sk-or-TESTSECRET456`; `json.dumps(api.writers())` contains neither string and contains no path text `secrets`.
3. Preview `write_pack` with `{model: "nvidia/nemotron-3.5-super-vl-120b-a12b"}` builds `--via nvidia --model ...`; with `{writer: "opus"}` still refused (existing behaviour).
4. `write_pack_claude`: with `allow_claude=False` preview -> 403 `claude is off`; with True -> argv contains `--writer opus`, `needs_confirm is True`, `confirm_text == "CLAUDE"`, route text mentions Claude; run with `confirm` missing or `"claude "` -> 400; run with `"CLAUDE"` -> `{"job_id": "job1"}` via the fake `_start`; run after flipping `cfg.allow_claude = False` -> 403.
5. `check_argv(["x", "--writer", "opus"])` raises; `check_argv([...], frozenset({("--writer","opus")}))` passes; `("--via","claude")` still raises with the allow set.
6. Spend path unchanged: an existing spend test still passes (do not edit it); add one asserting `needs_confirm` is False for `check_pack`.
7. Stale guard: `monkeypatch.setattr(server, "SERVER_MTIME0", 0)` -> `pipeline_gate` raises 409; normal -> unchanged.
8. Ops: `api.ops({})` does not call `_cli_text` (monkeypatch it to raise) and returns `sessions_listed None`, `sessions_checked False`; `api.ops({"colab": "1"})` calls it once.
9. i18n/font routes (create fake files under the test studio): en/mr served as JSON; unknown lang 404; font served with `font/ttf`.
10. PLAN.md section 4 contains the three new rows (the existing static tests also parse it).
Browser checks: none (server only). Do not restart the owner's running server; tests use the fake server.

### T2 Shell: styles, static page, i18n core

Files owned: `ui/static/style.css`, `ui/static/index.html`, `ui/static/i18n.js` (new), `ui/static/i18n/en.json` and `mr.json` (new; groups `app, lang, common, status, banner, dialog, err, risk`, and `adv.*` keys for **index.html** text), `ui/test_i18n.py` (new), `ui/test_static.py` (retargets listed below only).
Done when:
- [ ] Section 3.2 `i18n.js`, 3.3 marking, 3.5 map, 3.6 font, 4.1 tokens, 4.2 components CSS, 4.4 layout skeleton in index.html: header with `#ui-lang-en` / `#ui-lang-mr` (buttons, `aria-pressed`), `#working-on` line container (filled by pipeline.js), stepper `li` items each containing `button.step-btn` with id `step-btn-<stage>` (keep the `li` ids `step-story`..`step-export` and the `.step-num/.step-title/.step-status` spans), `#expert-ops` container inside `#advanced-tools`, `details#runs-details` container wrapping a `div#runs-slot` (pipeline.js puts the panel there), error bar with `#error-details` / `#error-raw`, dead `#stale-banner` removed (B7).
- [ ] B5, B6, B12, B13 done.
- [ ] Every visible text node in index.html has a key (test 3.8.6 passes).
- [ ] `test_static.py` retargets (only these; never weaken a check):
  1. `test_index_has_five_sections_and_nav`: replace the `>\s*%s\s*</button>` text check with `'id="nav-%s"' % key in INDEX`; keep the `data-section` and `sec-` checks.
  2. `test_owner_rules_are_on_the_page`: build `TEXT = JS + PIPELINE_JS + "\n".join(EN.values())` where `EN` = `json.loads(en.json)` (empty dict if the file is missing); assert each listed phrase `in TEXT` (same phrases: "Flow agents run on Haiku, effort LOW", "Copy", "not available yet"/"Not available yet", "--allow-spend", "gap G1", "gap G12", "EXECUTE ", "I looked at full size"). **These exact English phrases must stay in en.json values** (Experts strings).
  3. `test_image_jobs_button_id_and_commands_are_in_pipeline_js`: keep the id, command and no-innerHTML/no-URL checks; replace the two literal-text checks with `("textContent: 'Build image jobs'" in PIPELINE_JS) or ("'pics.build_btn'" in PIPELINE_JS and EN.get("pics.build_btn"))` and `("Image jobs are not built yet (" in PIPELINE_JS) or ("'pics.err_no_jobs'" in PIPELINE_JS and EN.get("pics.err_no_jobs"))`.
  4. `test_css_44px_touch_targets_and_pills`: `44px` -> `48px` in both regexes.
  5. Add `test_body_text_contrast_is_at_least_7`: pairs `("fg","panel"), ("fg","page-bg"), ("muted","panel"), ("muted","page-bg"), ("err-fg","tint-error-bar"), ("ok-fg","tint-green"), ("amber-fg","amber-bg")` >= 7.0 in light and both dark blocks.
  6. Add `test_no_font_size_below_17px`: every `font-size: Xrem` >= 0.85, every `font-size: Npx` >= 17.
- [ ] Parity rows owned: H01-H13, T01, D04, D05, E00, E01, all `adv.*` static labels in index.html (rows ES*, EI*, EB*, EV*, EX*, EL* as far as their static text goes).
Tests to write: `test_i18n.py` checks 3.8.1-3.8.7. At the end of T2, checks 2/3/5 only scan what exists; they will catch every literal that T3/T4 convert. (Check 5 on app.js/pipeline.js is marked `xfail(strict=False)` in T2 with reason "converted in T3/T4" and the marker is removed by T4: T4 is not done while it is xfail.)
Browser checks (start the UI with the project launch config; **press only**: language switch, stepper buttons, "Open this step", details/summary toggles, Experts summary, Advanced nav Story/Images/Bridge/Export; **do not open Video before T4**, do not press any save/run/approve/check button):
- Desktop 1280x800 and phone 375x812, English and Marathi: header, banner, stepper 3x2 on phone with all 6 visible, no horizontal scroll, Devanagari renders with the bundled font (DevTools network shows `/fonts/NotoSansDevanagari-Variable.ttf` 200, no other host), language choice survives reload.

### T3 Wizard (`pipeline.js`): steps, chooser, gates, plain words, bug fixes

Files owned: `ui/static/pipeline.js`; en/mr groups `ok, scope, step, story, next, warn, plan, writer, gate, pics, sum, video, files, runs, ops, icon`.
Done when:
- [ ] Sections 2.4, 4.3, 4.4 (open-step rule), 5.1-5.8, 5.10 implemented; Ops panel rendered into `#expert-ops` (5.9 item 1) with `#ops-colab-check`.
- [ ] B1 (client), B10, B11, B14 done; `NEXT_STAGE` gains `await_gate_A: 'analysis', await_gate_B: 'images', await_gate_C: 'readout', await_gate_D: 'render'`.
- [ ] Every visible literal goes through `t()`; literal maps for statuses, next keys, warnings, checks, human choices, writer reasons/costs/speeds/qualities.
- [ ] `State.openDetails` keeps every `details` open state across re-renders (ids: `details-<name>`).
- [ ] Keep (tests): `State.confirmPending = true` line, at least 4 `if (!State.confirmPending) State.busy = false;`, `registryPanel`, `/api/registry`, `'build_spec'`, `'build_jobs_cmd'`, `id: 'images-build-jobs'`, ids `lang-all, voice-save, bgm-save, render-prepare, images-build-jobs, analysis-run`, `aria-live`. No id built here may also be in index.html.
- [ ] Parity rows owned: T02-T04, S01-S14, A01-A06, I01-I05, R01-R04, V01-V06, X01, P01, P02, D01, D03 (wizard packet modal).
Tests to write: add to `test_i18n.py`'s data only (no new test file needed); add to `test_parity.py` `NEW_ROWS` anchors: `writer-choice`, `writer-opt-or-super-vl`, `writer-claude-ack`, `confirm-typed`, `ops-colab-check`, `banner-recheck`, `plan-show-all`, `progress-line`, `write_pack_claude`.
Browser checks (same allowed clicks as T2, plus selecting writer radio cards and ticking/unticking `#writer-claude-ack`; never press the main button of step 2):
- Each step opens from the stepper; each card shows exactly one `.btn-main`; Claude card disabled with the plain reason (server runs without `--allow-claude`); the stale banner disables Approve/Send back (check by reading the DOM `disabled` flags when the server reports stale; if not stale, skip and say so); English and Marathi show no English sentence on main cards in Marathi mode except names, model names and typed words.

### T4 Experts area (`app.js`)

Files owned: `ui/static/app.js`; en/mr group `adv.*` keys for app.js text; `ui/test_r3_fixes.py` (one retarget).
Done when:
- [ ] Every visible literal goes through `t()` (runCommand titles, notes, field labels and hints, table headers, badges `KIND_TEXT` via literal key map, messages, modal texts "Show what will happen (nothing starts yet)" `adv.modal.preview_btn`, "Yes, start" `adv.modal.start_btn`, "No, go back" `adv.modal.cancel_btn`, expiry lines).
- [ ] B2, B3, B4, B8 (section 2.5), B9 (client half: `loadVideo` without `loadColab`), B15 done; `showApiError` used in every catch.
- [ ] Keep (tests): `var WRITER_NAMES = ['super-vl', 'ultra'];`, `WRITER_MODELS` absent, `AbortController` and `120000`, `'X-UI'` set on non-GET, `spend_allowed`, risk codes in `RISK_TEXT` keys, badge kinds `'ok','notrun','review','failed','running'`, all ids and class tokens of CONTROL_MAP.
- [ ] `test_r3_fixes.test_app_api_has_timeout_and_h3run_guard`: replace `assert "Pick a shot file." in body` with `assert "Pick a shot file." in body or "'adv.video.err_pick_shot_file'" in body` and ensure en.json `adv.video.err_pick_shot_file` = "Pick a shot file." (the `h3Run` body must keep that key within its first 400 characters).
- [ ] Remove the `xfail` marker from `test_i18n.py` check 5 (allowed edit of that one marker).
- [ ] Parity rows owned: D02, ES1-ES14, EI1-EI14, EB1-EB4, EV1-EV13, EX1-EX5, EL1-EL2, ER.
Tests: none new beyond the retarget; all i18n checks must now pass without xfail.
Browser checks: open every Advanced section including Video (now safe: no Colab call on open; DevTools network must show no `/api/colab` request until "Check Colab" is pressed; **do not press it**); Images > Shots shows words (Good / Not good enough / Note / Not sure) not "[object Object]"; Advanced story picker shows the same story as the top; Finals count equal in step 3 and Advanced for the same story (or report the numbers).

### T5 Verification pass (no product edits)

Files owned: none (report only; defects go back to the owning task's coder run).
Done when:
- [ ] Full suites: ui (252 + 1 known failure + new tests all pass), h3 615, director 781, core 418.
- [ ] `node --check` on the three JS files.
- [ ] Every row of section 9 ticked from the browser checklist (9.3) at desktop and phone width, in English and Marathi, with a screenshot path per row group.
- [ ] Screenshots for the reviewers saved to `research/ui_redesign_shots_2026-11-07/` (desktop-en, desktop-mr, phone-en, phone-mr, each step open, Experts open, writer chooser with Claude selected, a gate blocked).

---

## 8. Review plan, acceptance checklist, risks and questions

### 8.1 Free reviewer bench (after T5; no Claude, no paid call)

- Runner: copy `research/_run_ui_reviews.py` to `research/_run_ui_redesign_reviews.py` and change only: prompt file `research/_review_prompt_ui_redesign.txt`, batches file `research/_review_batches_ui_redesign.json`, output `research/UI_REDESIGN_REVIEW_<WHICH>_2026-11-07.md` (the old script would overwrite the earlier review files).
- Batches: (1) `ui/server.py` diff + `ui/test_redesign_server.py` + `ui/test_parity.py`; (2) `ui/static/i18n.js` + `en.json` + `mr.json` + `ui/test_i18n.py`; (3) `pipeline.js`; (4) `app.js` + `index.html` + `style.css`; (5) this plan file (the reviewer checks the code against it).
- Dots (code): security of the Claude path and `check_argv`, key leaks, ES2018, innerHTML, broken features versus the parity inventory.
- Super VL (vision): the screenshots set from T5 against the acceptance table below; Marathi readability (as a non-native check only).
- Rule (blot.md rule 5): fix, then review again, until both reviewers report no blocking item.

### 8.2 Acceptance checklist (for the owner)

| # | What you should see | How to check | Pass? |
|---|---|---|---|
| 1 | A language switch at the top: English / मराठी. The page remembers it. | Press मराठी, reload the page. | |
| 2 | In Marathi mode, every word on the main steps is Marathi (names of AI models and typed words like START stay English). | Look through all six steps. | |
| 3 | Text is large and easy to read; buttons are big. | Read on the phone. | |
| 4 | On the phone, all six steps are visible at the top. | Open on the phone. | |
| 5 | Each step has one big main button with plain words. | Open each step. | |
| 6 | Step 2 lets you choose the AI: NVIDIA free, OpenRouter free, Claude. Free Super VL is already chosen. | Open step 2. | |
| 7 | Claude says it may cost money, needs a tick, and then needs the typed word CLAUDE. It is off unless your helper switched it on. | Choose Claude. | |
| 8 | Approve buttons are off while the program is out of date, with a plain sentence. | Helper edits server.py while the page is open. | |
| 9 | No codes (R, W, N, $, gate, pack, H3, 127.0.0.1) on the main steps; they are inside "Details for the helper" or the expert tools. | Look through the steps. | |
| 10 | Every old tool still exists in "For the helper: expert tools". | Helper uses the parity list (section 9). | |
| 11 | Picture review answers show words, not "[object Object]". | Expert tools > Pictures > Pictures per scene. | |
| 12 | The expert tools show the same story as the top. | Open expert tools > Story text. | |
| 13 | Nothing calls Colab unless you press a "Check Colab" button. | Helper watches the network list. | |
| 14 | Errors stay on screen until you close them, in plain words. | Try "Save" with an empty name. | |
| 15 | All tests pass (numbers in the report). | Helper reads the T5 report. | |

### 8.3 Risks (top first)

1. **i18n conversion breadth**: about 450 literal sites across 3,500 lines of JS; a missed literal or a broken handler during conversion is likely. Mitigation: the scans in 3.8, the parity test, and the browser checklist in both languages.
2. **Claude path safety**: a new command that can reach a model that may cost money. Mitigation: server flag `--allow-claude` off by default, separate command with an allow-list pair, `--writer opus` banned everywhere else, typed word checked on the server, never restored from storage, tests use a fake `_start`.
3. **Re-render loses state**: `render()` rebuilds the wizard on every data change (5 s poll). Open details, the open step, the picked writer and typed words must live in `State`, or the page will "jump" for her. Mitigation: `State.openStep`, `State.openDetails`, `State.writerChoice`, existing `State.drafts`.
4. Existing tests assert some English literals; the plan retargets exactly five assertions (T2 list, T4 one). Any other failing test means a feature was broken, not a test to edit.
5. Marathi is a draft until a native speaker confirms it.

### 8.4 Open questions for the owner (few)

- Q1. Speed/quality words of the five AI choices are my expectation. Keep "NVIDIA Super VL" (never tried for story plans) in the list, or hide it?
- Q2. Claude needs the helper to start the server with `--allow-claude`. Is that the switch you want, or should Claude be possible without it (still with the tick and the typed word)?
- Q3. Marathi numbers: keep 0-9 (planned) or show Devanagari digits ०-९?
- Q4. N3: the wizard's "Get the video ready" sends the scene file, which the video-prep step refuses. Fix it in a later task once the H3 story file path is settled?

### 8.5 What I could not verify

- I did not open the live page or take screenshots; layout claims are from CSS and code.
- Speed and quality of each model, and whether the NVIDIA Super VL 120B model handles the staged brief, are untested.
- Whether `read_images` and the pipeline summary count the same finals for a non-legacy story after B4 (two different folder resolutions in the server).
- The test counts (252/615/781/418) are taken from the brief; I did not run any suite.

---

## 9. Feature parity inventory (built from the code)

Columns: id | current name (as in code) | what it does | new English name | new Marathi name (draft, needs a native speaker) | where in the new design | anchor (for `test_parity.py`) | task.
Locations: **HDR** header; **BAN** banner/error bar; **WON** working-on line; **STP** stepper/progress; **S1..S6** step cards; **GA..GD** "Your OK" box inside S2/S3/S4/S5; **HD** helper details inside that card; **PW** Past work; **EXP-OPS / EXP-STORY / EXP-PICS / EXP-KEY / EXP-VIDEO / EXP-FILES / EXP-LOG** inside the Experts area; **DLG** dialogs. No row is removed.

### 9.1 Rows

**Header, banners, shell**

| id | Current | Does | New EN | New MR | Where | Anchor | Task |
|---|---|---|---|---|---|---|---|
| H01 | "ANIME STUDIO" | program name | Anime Studio | ॲनिमे स्टुडिओ | HDR | `header-chips` | T2 |
| H02 | chip "Story: x" | open story | Working on: x | सध्याची कथा: x | WON (header chip kept for desktop, same id) | `chip-story` | T2/T3 |
| H03 | chip "Pack: x" | open plan | Plan: x | आराखडा: x | WON | `chip-pack` | T2/T3 |
| H04 | chip "Languages:" | chosen languages | Languages: | भाषा: | WON | `chip-languages` | T2/T3 |
| H05 | "SPEND OFF/ON" | paid work allowed? | Paid work: OFF (safe) / ON | पैसे लागणारे काम: बंद (सुरक्षित) / सुरू | HDR | `spend-badge` | T2/T4 |
| H06 | "job: none" | background work | Nothing is running / Running: … | आत्ता काहीही चालू नाही | WON job line + EXP-LOG | `job-badge` | T2/T4 |
| H07 | "127.0.0.1" | host | This computer only (127.0.0.1) | फक्त हा संगणक | EXP-OPS | `host` (class) | T2 |
| H08 | server-state text | server not reachable | The program is not answering | प्रोग्राम उत्तर देत नाही | HDR (small) + error bar | `server-state` | T2/T4 |
| H09 | stale/low-disk banner (`pipe-banner`; dead `stale-banner` merged) | warns before approving | The program is out of date… / Little disk space… + Check again | प्रोग्राम जुना आहे… / जागा कमी… + पुन्हा तपासा | BAN | `pipe-banner` | T3 |
| H10 | error bar + Dismiss | errors, success | Message + Close + Details for the helper | संदेश + बंद करा + मदतनीसासाठी तपशील | BAN | `error-bar` | T2 |
| H11 | skip link | keyboard skip | Go to the steps | टप्प्यांवर जा | HDR | `skip-link` (class) | T2 |
| H12 | NEW language switch | UI language | English / मराठी | English / मराठी | HDR | `ui-lang-mr` (NEW) | T2 |
| H13 | Advanced msg-bar | Advanced success line | (same) | (same) | EXP top | `msg-bar` | T2 |

**Stepper and wizard frame**

| id | Current | Does | New EN | New MR | Where | Anchor | Task |
|---|---|---|---|---|---|---|---|
| T01 | stepper items 1-6 | progress | 1 Story, 2 Plan the story, 3 Pictures, 4 Check the summary, 5 Make the video, 6 Final files (buttons) | १ कथा, २ कथेचा आराखडा, ३ चित्रे, ४ सारांश तपासा, ५ व्हिडिओ बनवा, ६ अंतिम फाइली | STP | `step-analysis` | T2/T3 |
| T02 | NEW progress line | "Step 2 of 6: …" | Step {n} of 6: {name} - {status} | टप्पा {n} / ६: {name} - {status} | STP | `progress-line` (NEW) | T3 |
| T03 | scope bar chips | story/pack/languages/writer | Working on … / AI for the plan … | … / आराखड्यासाठी AI … | WON | `wizard-scope` | T3 |
| T04 | job bar | running job text | Nothing is running. Nothing starts until you say yes. | काहीही चालू नाही. तुम्ही हो म्हटल्याशिवाय काही सुरू होत नाही. | WON | `wizard-jobbar` | T3 |

**Step 1 Story**

| id | Current | Does | New EN | New MR | Where | Anchor | Task |
|---|---|---|---|---|---|---|---|
| S01 | "Where you stopped" + Continue + warnings | next step | Where we are now + Go to that step; warnings plain, raw in HD | आत्ता आपण कुठे आहोत + त्या टप्प्यावर जा | S1 / HD | `btn-continue` | T3 |
| S02 | story picker (+ "-- new story --") | pick story | Which story? / Start a new story | कोणती कथा? / नवीन कथा सुरू करा | S1 | `wiz-story-slug` | T3 |
| S03 | "New slug" | new story name | Short name for a new story | नवीन कथेचे छोटे नाव | S1 | `wiz-story-new-slug` | T3 |
| S04 | story text | paste story | Paste your story here | तुमची कथा इथे पेस्ट करा | S1 | `wiz-story-text` | T3 |
| S05 | overwrite tick | allow replace | Replace the story already saved (careful) | आधी जतन केलेली कथा बदला (काळजीपूर्वक) | S1 | `wiz-story-overwrite` | T3 |
| S06 | Save story | save SOURCE.md | Save my story | माझी कथा जतन करा | S1 main/quiet | `btn-save-story` | T3 |
| S07 | language pills | tick languages | English / Hindi / Marathi | इंग्रजी / हिंदी / मराठी | S1 | `lang-mr` | T3 |
| S08 | "All (…)" | tick all | Select all three | तिन्ही निवडा | S1 | `lang-all` | T3 |
| S09 | Save languages + "Saved:" | save languages | Save my language choice / Saved languages: | माझी भाषा निवड जतन करा / जतन केलेल्या भाषा: | S1 | `lang-save` | T3 |
| S10 | H3 English voice + Save voices | voice engine | Use the program's own English voice (takes extra time) / Save voice choice | प्रोग्रामचा स्वतःचा इंग्रजी आवाज / आवाज निवड जतन करा | S1 > More choices | `voice-save` | T3 |
| S11 | Background music on, manifest, Save | BGM | Background music (optional) / Music list file / Save music choice | पार्श्वसंगीत (ऐच्छिक) / संगीत यादीची फाइल / संगीत निवड जतन करा | S1 > More choices | `bgm-save` | T3 |
| S12 | Voice map + Save voice map | voice per character | Which voice speaks for each character / Save these voice names | प्रत्येक पात्राला कोणता आवाज / ही आवाज नावे जतन करा | S1 > More choices | `voice-map-save` | T3 |
| S13 | YouTube link, language, ASR, replace, Get transcript | story from video | Get the story from a YouTube video / Get the words from this video | YouTube व्हिडिओवरून कथा घ्या / या व्हिडिओतले शब्द घ्या | S1 > YouTube box | `link-run` | T3 |
| S14 | link result, Use <lang>, Replace SOURCE.md | result/choices | Done: story saved / Use this language / Yes, replace the saved story | झाले / ही भाषा वापरा / होय, जतन केलेली कथा बदला | S1 > YouTube box | `link-result` | T3 |

**Step 2 Plan + Gate A**

| id | Current | Does | New EN | New MR | Where | Anchor | Task |
|---|---|---|---|---|---|---|---|
| A01 | Pack name | plan folder name | Name of this plan (leave as shown) | या आराखड्याचे नाव (आहे तसे ठेवा) | S2 | `analysis-pack` | T3 |
| A02 | Run story analysis (+ confirm) | write_pack | Make the story plan with {AI} | {AI} वापरून कथेचा आराखडा बनवा | S2 main | `analysis-run` | T3 |
| A03 | NEW writer chooser | pick model | Which AI should write the plan? | आराखडा कोणता AI लिहील? | S2 | `writer-choice` (NEW) | T3 |
| A04 | What you must approve (shots, episodes, names, check JSON) | review plan | What you need to check (scenes, parts, people/places/things; JSON in HD) | तुम्हाला काय तपासायचे आहे | S2 / HD | `analysis-run` (same card; tables have no id) | T3 |
| A05 | validator panel + Run validator | mistake check | Check the plan for mistakes / Check again | आराखडा चुकांसाठी तपासा / पुन्हा तपासा | S2 | `validator-run` | T3 |
| A06 | Gate A card (note, Approve, Reject, by/when/note, next hint) | approval 1 | Your OK 1: the scene list / Yes, approve / Send back | पहिली मंजुरी: दृश्यांची यादी / होय, मंजूर करा / परत पाठवा | GA | `gate-approve-` (built `'gate-approve-' + id`) | T3 |

**Step 3 Pictures + Gate B**

| id | Current | Does | New EN | New MR | Where | Anchor | Task |
|---|---|---|---|---|---|---|---|
| I01 | Build image jobs | build_spec + build_jobs_cmd | Prepare the picture list (no payment) | चित्रांची यादी तयार करा (पैसे नाहीत) | S3 main | `images-build-jobs` | T3 |
| I02 | Make Flow agent packet (+ modal Copy/Close) | helper instructions | Make the instruction sheet for the picture helpers | चित्र मदतनीसांसाठी सूचना-पत्र बनवा | S3 | `images-packet` | T3 |
| I03 | Finals/Pending/Reviewed + progress bar | counts | Finished pictures {a} of {b} / Waiting / Checked | पूर्ण चित्रे {a} / {b} / प्रलंबित / तपासलेली | S3 | `images-packet` (same card) | T3 |
| I04 | notes "Flow agents run on Haiku, effort LOW", "Full-size check by Claude" | owner rules | The picture helpers are started by Claude… (raw rule in HD) | चित्र मदतनीस Claude सुरू करतो… | S3 / HD | `key:pics.rule_haiku` | T3 |
| I05 | Gate B card | approval 2 | Your OK 2: the pictures | दुसरी मंजुरी: चित्रे | GB | `gate-approve-` | T3 |

**Step 4 Summary + Gate C**

| id | Current | Does | New EN | New MR | Where | Anchor | Task |
|---|---|---|---|---|---|---|---|
| R01 | stat tiles (Reels, Shots, Seconds, Characters, Places, Images, Clips planned, Est. G4 units, Est. minutes) | numbers | Parts, Scenes, Seconds, People, Places, Pictures finished, Clips planned, Minutes to make; GPU units in HD | भाग, दृश्ये, सेकंद, माणसे, ठिकाणे, पूर्ण चित्रे, नियोजित क्लिप्स, लागणारी मिनिटे | S4 / HD | `key:sum.tile_parts` | T3 |
| R02 | episode table, names, Takes, Clips home, Finals/Pending/Reviewed | detail | More numbers | आणखी आकडे | S4 > More numbers | `key:sum.more_title` | T3 |
| R03 | checks list + warnings | auto checks | Checks (plain names) / Warnings | तपासण्या / सूचना | S4 | `key:sum.checks_title` | T3 |
| R04 | Gate C + type START | approval 3 | Your OK 3: the video plan / Type START | तिसरी मंजुरी: व्हिडिओ आराखडा / START टाइप करा | GC | `gate-confirm-C` | T3 |

**Step 5 Video + Gate D**

| id | Current | Does | New EN | New MR | Where | Anchor | Task |
|---|---|---|---|---|---|---|---|
| V01 | Prepare render (no GPU) | h3_prepare | Get the video ready (no payment) | व्हिडिओ तयार करा (पैसे नाहीत) | S5 main | `render-prepare` | T3 |
| V02 | Image jobs and assets panel | asset counts, blocking problems | Pictures and sound files | चित्रे आणि आवाज फाइली | S5 | `asset-panel` | T3 |
| V03 | fallback table + choices + note | human choice | Scenes that need your decision | ज्या दृश्यांना तुमचा निर्णय हवा | S5 | `choice-note-` | T3 |
| V04 | Step 9 render check | final QC result | Final video check | अंतिम व्हिडिओ तपासणी | S5 | `step9-panel` | T3 |
| V05 | H3 field author panel (derived, missing, cache, preview, phrase, run) | author dry run | Automatic detail writer (for the helper) | व्हिडिओसाठी राहिलेली माहिती भरणारा | S5 > HD box | `author-panel` | T3 |
| V06 | Gate D card + language rows, BGM chip, safe zone | approval 4 | Your OK 4: final check | चौथी मंजुरी: अंतिम तपासणी | GD | `gate-d-langs` | T3 |

**Step 6, bottom panels, dialogs**

| id | Current | Does | New EN | New MR | Where | Anchor | Task |
|---|---|---|---|---|---|---|---|
| X01 | Reel number + Show clips + clip list + assembly chip | clips per reel | Part number / Show the clips of this part / Not joined yet | भाग क्रमांक / या भागाच्या क्लिप्स दाखवा / अजून जोडलेले नाही | S6 | `export-show` | T3 |
| P01 | Ops panel (disk, server, Colab ledger, sessions) | health | Computer and spending check (+ Check Colab sessions button) | संगणक आणि खर्च तपासणी | EXP-OPS | `ops-panel` | T3 |
| P02 | Runs & documents (table, row click, runs/steps tables, RUN_REPORT link + text) | history | Past work (records) | मागील कामे (नोंदी) | PW | `runs-panel` | T3 |
| D01 | confirm dialog (Cancel / Run) | confirm | Please check / No, go back / Yes, approve · Yes, start · Yes, use Claude | कृपया तपासा / नाही, मागे जा / होय, … | DLG | `confirm-run` | T3 |
| D02 | command modal (Preview, Cancel, argv, estimate, balance, expiry, typed EXECUTE, Start, fields, check box) | preview + run | Show what will happen (nothing starts yet) / Yes, start / No, go back; exact command in HD | काय होईल ते दाखवा / होय, सुरू करा / नाही, मागे जा | DLG | `modal-start` | T4 |
| D03 | packet modal (Copy, Close, path) | instruction sheet | Instruction sheet / Copy / Close | सूचना-पत्र / कॉपी करा / बंद करा | DLG | `packet-copy` | T4 (app.js) / T3 (wizard) |
| D04 | lightbox + Close picture | full-size picture | Close | बंद करा | DLG | `lightbox-close` | T2 |
| D05 | modal Close | close dialog | Close | बंद करा | DLG | `modal-close` | T2 |

**Experts area (old Advanced): frame**

| id | Current | Does | New EN | New MR | Where | Anchor | Task |
|---|---|---|---|---|---|---|---|
| E00 | "Advanced tools (manual controls)" | open expert tools | For the helper: expert tools | मदतनीसासाठी: तज्ञ साधने | EXP | `advanced-tools` | T2 |
| E01 | nav Story/Images/Bridge/Video/Export | sections | Story text / Pictures / Key frames / Video clips / Final files | कथा मजकूर / चित्रे / मुख्य फ्रेम / व्हिडिओ क्लिप्स / अंतिम फाइली | EXP | `nav-bridge` | T2 |
| ER | risk tags R/W/N/$/OPS/X | risk hints | same letters, plain titles | तेच, साधे स्पष्टीकरण | EXP | `risk-usd` (class) | T2/T4 |

**Experts > Story text**

| id | Current | Does | New EN | New MR | Where | Anchor | Task |
|---|---|---|---|---|---|---|---|
| ES1 | Story (slug), Pack | pick story/plan | Story (the same as at the top) / Plan | कथा (वरच्यासारखीच) / आराखडा | EXP-STORY | `story-pack` | T4 |
| ES2 | Writer fixed text + Writer model | AI for the two buttons | AI writer (free choices) | AI लेखक (मोफत पर्याय) | EXP-STORY | `story-model` | T4 |
| ES3 | status line (Studio OK, flow OK, Colab CLI, key count) | connections | Connections: program, picture tool, GPU tool, free AI keys found: n | जोडण्या: … मोफत AI च्या चाव्या: n | EXP-STORY | `story-status` | T4 |
| ES4 | Story text + bytes + Load story | read SOURCE.md | Story text / Load the saved story | कथा मजकूर / जतन केलेली कथा आणा | EXP-STORY | `story-load` | T4 |
| ES5 | Replace tick + Save story | write SOURCE.md | Replace the saved story / Save story (writes the file) | जतन केलेली कथा बदला / कथा जतन करा | EXP-STORY | `story-save` | T4 |
| ES6 | New pack name + Run writer: new pack | write_pack new | New plan name / Make a new plan with the free AI | नवीन आराखड्याचे नाव / मोफत AI ने नवीन आराखडा | EXP-STORY | `story-run-new` | T4 |
| ES7 | Resume pack | write_pack resume | Continue an unfinished plan | अर्धवट आराखडा पुढे चालवा | EXP-STORY | `story-resume` | T4 |
| ES8 | Check pack | check_pack (GET /api/pack?check=1) | Check the plan (changes nothing) | आराखडा तपासा (काही बदलत नाही) | EXP-STORY | `story-check` | T4 |
| ES9 | Stages badges | stage status | Parts of the plan | आराखड्याचे भाग | EXP-STORY | `story-stages` | T4 |
| ES10 | Gate 1 text | plan as written | Plan text as written | लिहिलेला आराखडा | EXP-STORY | `story-gate1` | T4 |
| ES11 | Episodes table | per part | Parts | भाग | EXP-STORY | `story-episodes` | T4 |
| ES12 | Characters / Places (bible) | names | People / Places in this story | माणसे / ठिकाणे | EXP-STORY | `story-places` | T4 |
| ES13 | Shots table | per scene | Scenes | दृश्ये | EXP-STORY | `story-shots` | T4 |
| ES14 | Check pack result (JSON) | raw result | Check result (for the helper) | तपासणीचा निकाल | EXP-STORY | `story-check-json` | T4 |

**Experts > Pictures**

| id | Current | Does | New EN | New MR | Where | Anchor | Task |
|---|---|---|---|---|---|---|---|
| EI1 | Adhyay + Refresh | chapter, reload | Chapter / Reload the list | अध्याय / यादी पुन्हा आणा | EXP-PICS | `img-refresh` | T4 |
| EI2 | tabs Series/Jobs/Shots/Progress/Queue/Finals | views | Characters and places / Work list / Pictures per scene / Progress / Waiting / Finished | पात्रे-ठिकाणे / कामाची यादी / दृश्यानुसार चित्रे / प्रगती / प्रलंबित / पूर्ण | EXP-PICS | `tab-queue` | T4 |
| EI3 | series table | sheets | (headers plain) | | EXP-PICS | `series-table` | T4 |
| EI4 | jobs table + Packet + Build* (disabled) | per job | Make instruction sheet / Not available yet | सूचना-पत्र बनवा / अजून उपलब्ध नाही | EXP-PICS | `act-packet` | T4 |
| EI5 | shots table Q1-Q6, verdict, details, review detail | reviewer answers | Questions 1-6 (Good / Not good enough / Note / Not sure), Result, See notes | प्रश्न १-६, निकाल, नोंदी पाहा | EXP-PICS | `review-detail` | T4 |
| EI6 | Neighbour sheet | neighbour_sheet | Make a side-by-side sheet | शेजारी-शेजारी पत्रक बनवा | EXP-PICS | `act-neighbours` | T4 |
| EI7 | Run reviewer | review_shot | Ask the reviewer to check (free AI) | परीक्षकाला तपासायला सांगा | EXP-PICS | `act-reviewer` | T4 |
| EI8 | Queue kept (version, edit id, note) | queue_add | Keep this picture for the final list | हे चित्र अंतिम यादीसाठी ठेवा | EXP-PICS | `act-queue-kept` | T4 |
| EI9 | Accept (owner) + "I looked at full size" | queue_accept | I approve this picture (I looked at it full size) | मी हे चित्र मंजूर करते (पूर्ण आकारात पाहिले) | EXP-PICS | `act-accept` | T4 |
| EI10 | progress table (legacy greyed) | progress log | Progress (old records greyed) | प्रगती (जुन्या नोंदी फिकट) | EXP-PICS | `progress-table` | T4 |
| EI11 | queue counts | counts | Waiting / moved to final / approved | प्रलंबित / अंतिममध्ये / मंजूर | EXP-PICS | `queue-counts` | T4 |
| EI12 | Collect | queue_collect | Copy finished pictures in from Downloads | डाउनलोडमधून पूर्ण चित्रे आत कॉपी करा | EXP-PICS | `btn-collect` | T4 |
| EI13 | Tidy plan + output | tidy_plan (dry) | Show what would be moved (moves nothing) | काय हलेल ते दाखवा | EXP-PICS | `btn-tidy` | T4 |
| EI14 | finals count + grid + lightbox | finished pictures | {n} finished pictures. Tap one to see it big. | {n} पूर्ण चित्रे. मोठे पाहण्यासाठी टॅप करा. | EXP-PICS | `finals-grid` | T4 |

**Experts > Key frames, Video clips, Final files, Log**

| id | Current | Does | New EN | New MR | Where | Anchor | Task |
|---|---|---|---|---|---|---|---|
| EB1 | Target size | size | Picture size (use the first one) | चित्राचा आकार (पहिला वापरा) | EXP-KEY | `bridge-size` | T4 |
| EB2 | Dry run | bridge_dry | See what would be made (nothing changes) | काय बनेल ते पाहा | EXP-KEY | `bridge-dry` | T4 |
| EB3 | Write keyframes | bridge_write | Make the key frames (writes files) | मुख्य फ्रेम बनवा | EXP-KEY | `bridge-write` | T4 |
| EB4 | bridge table | result | File, Result, Note, Pixels removed | फाइल, निकाल, नोंद, काढलेले पिक्सेल | EXP-KEY | `bridge-table` | T4 |
| EV1 | Shot file, Batch, Route | clip group setup | Which scene list / Name of this clip group / Method | कोणती दृश्य यादी / क्लिप गटाचे नाव / पद्धत | EXP-VIDEO | `video-batch` | T4 |
| EV2 | Scope radios + ids + reel | which clips | Which clips: some scenes / one part / all | कोणत्या क्लिप्स | EXP-VIDEO | `video-scope-reel` | T4 |
| EV3 | Keyframes folder, profile, resolution | settings | Key frames folder (leave empty) / Quality 5 for Colab / Size | मुख्य फ्रेम फोल्डर / गुणवत्ता / आकार | EXP-VIDEO | `video-keyframes` | T4 |
| EV4 | 1 Prepare batch (no GPU) | run_kaggle_prepare | Get the clip group ready (no payment) | क्लिप गट तयार करा (पैसे नाहीत) | EXP-VIDEO | `video-prepare` | T4 |
| EV5 | batches table | groups | Groups ready | तयार गट | EXP-VIDEO | `video-batches` | T4 |
| EV6 | H3 engine status + cmd + Prepare (H3) | h3_prepare | Video engine: status / Prepare the video engine files (no payment) | व्हिडिओ इंजिन / फाइली तयार करा | EXP-VIDEO | `h3-run` | T4 |
| EV7 | Colab balance, rate, Check Colab | colab read | Google Colab (paid GPU service) / Check the Colab account (contacts Google, free) | Google Colab / Colab खाते तपासा | EXP-VIDEO | `colab-check` | T4 |
| EV8 | Run on Colab (spend gate; GPU, session, EXECUTE) | colab_run | Start a paid GPU session (costs money) | पैसे लागणारे GPU सत्र सुरू करा | EXP-VIDEO | `colab-run` | T4 |
| EV9 | sessions table + Stop session | colab_stop | Open sessions / Stop session {name} | सुरू असलेली सत्रे / सत्र थांबवा | EXP-VIDEO | `act-stop-session` | T4 |
| EV10 | Live box | live log | What is happening now | आत्ता काय चालले आहे | EXP-VIDEO | `video-live` | T4 |
| EV11 | Stop job (local process only) | stop | Stop the work on this computer (the cloud part may keep running) | या संगणकावरील काम थांबवा | EXP-VIDEO | `video-stop` | T4 |
| EV12 | Clips home | count | Clips ready here | इथे तयार क्लिप्स | EXP-VIDEO | `clips-home` | T4 |
| EV13 | clips table + Sheet + Visual QA (direction, vision model) | clip_qa, visual_qa | Make a check sheet / Picture check (free AI) | तपासणी पत्रक / चित्र तपासणी (मोफत AI) | EXP-VIDEO | `act-vqa` | T4 |
| EX1 | Reel + Load | export read | Part number / Show | भाग क्रमांक / दाखवा | EXP-FILES | `export-load` | T4 |
| EX2 | Clips in order | list | Clips in order | क्लिप्स क्रमाने | EXP-FILES | `export-clips` | T4 |
| EX3 | Assembly plan | join plan | How the video will be joined (not yet) | व्हिडिओ कसा जोडला जाईल | EXP-FILES | `export-assembly` | T4 |
| EX4 | Reel files | files | Final files for this part | या भागाच्या अंतिम फाइली | EXP-FILES | `export-files` | T4 |
| EX5 | Open folder (disabled) | not available | Open folder (not available yet) | फोल्डर उघडा (अजून नाही) | EXP-FILES | `export-open` | T4 |
| EL1 | Job log tail + job line | log | What the program is doing (last lines) | प्रोग्राम काय करत आहे | EXP-LOG | `log-tail` | T4 |
| EL2 | Stop job (footer) | stop | Stop the work now | आता काम थांबवा | EXP-LOG | `log-stop` | T4 |

### 9.2 Routes and commands (the parity test's tables)

Routes (method, route, needle that must appear in app.js + pipeline.js):

| Method | Route | Needle | Used by |
|---|---|---|---|
| GET | `/` | (served page) | browser |
| GET | `/*.css`, `/*.js` | (served assets) | browser |
| GET | `/i18n/{lang}.json` NEW | `'i18n/'` in i18n.js | i18n.js |
| GET | `/fonts/NotoSansDevanagari-Variable.ttf` NEW | `fonts/NotoSansDevanagari-Variable.ttf` in style.css | CSS |
| GET | `/api/pipeline` | `'/api/pipeline'` | pipeline.js |
| GET | `/api/pipeline/summary` | `'/api/pipeline/summary'` | pipeline.js |
| GET | `/api/version` | `'/api/version'` | pipeline.js |
| GET | `/api/ops` | `'/api/ops'` | pipeline.js (EXP-OPS) |
| GET | `/api/story/{slug}/state` | `'/state'` | pipeline.js |
| GET/POST | `/api/pack/voices` | `'/api/pack/voices` | pipeline.js |
| GET/POST | `/api/pack/validate` | `'/api/pack/validate` | pipeline.js |
| GET | `/api/render/status` | `'/api/render/status` | pipeline.js |
| GET | `/api/author/status` | `'/api/author/status` | pipeline.js |
| GET | `/api/status` | `'/api/status'` | both |
| GET | `/api/h3` | `'/api/h3'` | app.js |
| GET | `/api/story` | `'/api/story'` | both |
| GET/POST | `/api/story/{slug}` | `'/api/story/'` | both |
| GET | `/api/registry` | `'/api/registry'` | pipeline.js |
| GET | `/api/registry/{slug}` | `'/api/registry/'` | pipeline.js |
| GET | `/api/pack` | `'/api/pack?pack=` | both |
| GET | `/api/jobs` | `'/api/jobs'` | both |
| GET | `/api/jobs/{id}/log` | `'/log?tail=` | app.js |
| GET | `/api/jobs/{id}/result` | `'/result'` | both |
| POST | `/api/jobs/{id}/stop` | `'/stop'` | app.js |
| GET | `/api/images` | `'/api/images?` | both |
| GET | `/api/review` | `'/api/review?` | app.js |
| GET | `/api/video` | `'/api/video'` | app.js |
| GET | `/api/colab` | `'/api/colab'` | app.js |
| GET | `/api/export` | `'/api/export?` | both |
| GET | `/api/file` | `'/api/file?path=` | both |
| GET | `/api/writers` NEW | `'/api/writers'` | pipeline.js, app.js |
| POST | `/api/preview` | `'/api/preview'` | both |
| POST | `/api/run` | `'/api/run'` | both |
| POST | `/api/packet` | `'/api/packet'` | both |
| POST | `/api/pipeline/gate` | `'/api/pipeline/gate'` | pipeline.js |
| POST | `/api/pipeline/project` | `'/api/pipeline/project'` | both (app.js after B3) |
| POST | `/api/story/{slug}/languages` | `'/languages'` | pipeline.js |
| POST | `/api/story/{slug}/voices` | `'/voices'` | pipeline.js |
| POST | `/api/story/{slug}/bgm` | `'/bgm'` | pipeline.js |
| POST | `/api/story/{slug}/link` | `'/link'` | pipeline.js |
| POST | `/api/render/choice` | `'/api/render/choice'` | pipeline.js |
| POST | `/api/author/preview` | `'/api/author/preview'` | pipeline.js |

Commands (`server.COMMANDS`): reachable from the front end today and after: `write_pack`, `neighbour_sheet`, `review_shot`, `queue_add`, `queue_accept`, `queue_collect`, `tidy_plan`, `clip_qa`, `visual_qa`, `run_kaggle_prepare`, `colab_run`, `colab_stop`, `bridge_dry`, `bridge_write`, `h3_prepare`, `h3_author`, `build_spec`, `build_jobs_cmd`; NEW `write_pack_claude`. Server-only (no UI control today, unchanged, listed in `SERVER_ONLY`): `check_pack` (reached through `GET /api/pack?check=1`), `queue_status`, `tidy_apply`, `colab_sessions`, `colab_usage`, `colab_run_dry`, `yt_transcript` (reached through `POST /api/story/{slug}/link`).

### 9.3 Manual browser checklist (reviewer bench and T5)

For each row group, at desktop 1280x800 and phone 375x812, in English and in Marathi: the control is visible after opening its location (step, details box or Experts section), its label is in the chosen language, it is enabled or shows a written reason, and (for read-only controls only) pressing it shows the expected result. Controls that write, spend, approve, call a model or call Colab are checked for **presence, label and enabled/disabled reason only** - never pressed.

| Group | Rows | Allowed to press |
|---|---|---|
| Header and banners | H01-H13 | language switch, Check again, Close, Details for the helper |
| Stepper | T01-T04 | stepper buttons, Open this step |
| Step 1 | S01-S14 | details boxes only (no Save, no Get words) |
| Step 2 | A01-A06 | writer cards, Claude tick box, Show all scenes, details boxes |
| Step 3 | I01-I05 | details boxes |
| Step 4 | R01-R04 | More numbers, details boxes (typing START is allowed; do not press Approve) |
| Step 5 | V01-V06 | details boxes, author "Preview" (dry run, read-only) |
| Step 6 | X01 | Show the clips of this part (read-only) |
| Bottom | P01, P02 | Past work open, a row (read-only), RUN_REPORT link; not Check Colab sessions |
| Dialogs | D01-D05 | open a picture in the lightbox and close it |
| Experts frame | E00, E01, ER | Experts summary, nav buttons |
| Experts Story | ES1-ES14 | Load the saved story, Check the plan (read-only) |
| Experts Pictures | EI1-EI14 | Reload, tabs, See notes, a finished picture |
| Experts Key frames | EB1-EB4 | nothing |
| Experts Video | EV1-EV13 | nothing (not Check Colab) |
| Experts Files | EX1-EX5 | Show (read-only) |
| Experts Log | EL1-EL2 | nothing |
