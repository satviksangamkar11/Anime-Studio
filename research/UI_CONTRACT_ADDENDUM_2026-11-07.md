# UI contract addendum (2026-11-07, integrator). Read AFTER research/UI_AUDIT_AND_UPDATE_PLAN_2026-11-07.md. Where they differ, THIS file wins.

## Blockers from section 4b that are now RESOLVED (use them, do not fake them)
director/story_state.py + story_links.py (S1), run_registry fields output_languages + voice_engine (GAP), validator kind, h3/v4_to_h3.py convert_pack (V4H3) + h3/h3_author.py derive/author (H3A), h3/render_controller.plan_pipeline + h3/pipeline_contract.build_plan (GAP), h3/voice_manifest.py (GAP), director/ops_checks.py + retry_policy.py (S2), director/pack_validator.py validate_pack (A), h3/voice_engine.py (EV), h3/gate_d_audio.plan_language_outputs (E/EV).
Still missing (UI shows "not run", fails closed): a Step 9 runner that writes a result file, a Gate D assembly runner, any real render, ElevenLabs calls, live author calls.

## Owner decisions that shape the UI (answers to audit section 5; recommended options adopted)
1. Languages: NO default; the owner ticks 1, 2 or 3 of EN/HI/MR (All button). English has a voice-engine choice (see below).
2. Gate A: approval blocked while the validator reports errors (no override).
3. Gate D: approval requires Step 9 QC pass and per-language checks.
4. Spend: stays OFF by default (typed confirm + cap); never call Colab from the UI code in tests; NO Colab call anywhere (owner rule, blot.md rule 4).
5. Public repo: stories/, images, clips, keys never committed (do not touch git).
6. "Prepare render" button: enabled only when convert_pack gives no problems (plan_pipeline says ready); otherwise show the precise problems list.
7. Kaliya: legacy project keeps its own roots; other stories use story_links. No Kaliya hard-codes for other stories.
8. Reel N = episode EP_0N.

## New features (owner option A, 2026-11-07)
(k) Voice engine per language: hi = ElevenLabs, mr = ElevenLabs (fixed, shown read-only); en = ElevenLabs (default) or "H3 built-in voice" (checkbox with warning text "extra English render, extra H3 cost"). Stored via POST /api/story/<slug>/voices {voice_engine:{"en":"elevenlabs"|"h3","hi":"elevenlabs","mr":"elevenlabs"}}; server validates with h3/voice_engine.py (VE-* codes) and writes it to story.json + a registry event (voice_engine field); hi/mr = h3 is rejected 400.
(l) Voice map: per character per selected language a voice id/name field (placeholder allowed, shown as "pending owner choice"); GET/POST /api/pack/voices?pack= reads/writes the bible voice_map through h3/voice_engine.py validation (VM-* codes). No ElevenLabs API call, ever, from the UI.
(m) Background music: toggle "Background music" default OFF; ON asks for the bgm_manifest path (track_id, path, license_type, bpm, lufs). Stored in story.json as bgm: {enabled, manifest}. Gate D status shows "no BGM (2-stem mix)" or "BGM on (3-stem)".
(n) H3 field author step panel: per shot derived fields, missing fields, authored cache status (fresh/stale), button "Preview author prompts (dry run)" calling h3/h3_author.py dry-run logic (no model call). A "Run author (free model)" button exists but is DISABLED unless the server env ANIME_STUDIO_ALLOW_FREE_MODEL=1 and the owner types a confirm phrase; tests never press it.
(o) Captions safe zone chip on Gate D: "bottom 896 / top 360 / sides 160 (Instagram Reels + YouTube Shorts)" from h3/shot_table_spec.CAPTION.
New endpoints: POST /api/story/<slug>/voices, GET/POST /api/pack/voices, POST /api/story/<slug>/bgm, GET /api/author/status?story=&pack=, POST /api/author/preview {pack}. Errors as {"error": ...}; 400 bad input, 403 guards, 409 scope mismatch.

## Rules for every UI agent
- Files are DISJOINT (U1: ui/server.py, ui/pipeline.py, ui/test_ui.py, ui/test_pipeline.py, ui/test_registry.py; U2: ui/static/pipeline.js, ui/static/app.js; U3: ui/static/style.css, ui/static/index.html, ui/test_static.py). Touch nothing else. U2/U3 code against the contract and fixtures until U1's endpoints exist; re-read ui/server.py before final wiring.
- No render, no Colab, no ElevenLabs, no model call, no network, no commit/push. Server binds 127.0.0.1 only. Tests offline, free of any model.
- Easy language in all UI copy (short plain English). Phone width 375 px: no horizontal page scroll, buttons >= 44 px, visible focus ring, status = colour + text.
- Keep the existing suites green: ui 178 now (they grow), director 622, h3 504, flow 116.
- Logging (blot.md): after EVERY step append ONE line to PROJECT_LOG.md LIVE LOG `MM-DD HH:MM | <AGENT>(haiku,medium) | TYPE | WHERE | RESULT` (max 200 chars, real clock from `date`). Add a ledger row (U1/U2/U3) to HANDOFF_2026-11-07.md section 9 (DONE-UNVERIFIED, public API, judgment calls, open questions). Final report: files, tests, counts, gaps.

## U3 element ids (published by U3 on 2026-11-07; U2 adopts these in pipeline.js/app.js)
Static containers live in index.html inside `<div id="wiz-panels">`, a sibling of `<main id="wizard">` (the wizard rebuild must not clear them). Cards and job bar are placed in `<div class="wizard-col">`.
- Header: `chip-story`, `chip-pack`, `chip-languages`, `spend-badge` (in `header-chips`); `stale-banner` (role=alert, hidden) with text in `stale-banner-text`.
- Job bar (top of wizard col, one line): `job-bar`, `job-bar-text` (aria-live), `job-bar-toggle` (aria-expanded), `job-bar-log` (pre, hidden until expanded, last 12 lines), `job-bar-stop`.
- `next-step`, `next-step-text`, `next-step-warnings` (ul), `next-step-continue` (button).
- Languages: `story-languages` (fieldset), `lang-en`, `lang-hi`, `lang-mr` (checkboxes), `lang-all` (button), `lang-status` (aria-live).
- English voice engine: `voice-en-h3` (checkbox), `voice-en-warning`, `voice-hi-note`, `voice-mr-note`, `voice-save`, `voice-status`.
- Voice map: `voice-map` (container for per-character rows), `voice-map-status`, `voice-map-save`.
- BGM: `bgm-enabled` (checkbox), `bgm-manifest` (text input), `bgm-status`, `bgm-save`.
- Validator: `validator-panel`, `validator-chip`, `validator-stats`, `validator-errors` (table), `validator-repair`, `validator-run`.
- YouTube link: `yt-url`, `yt-lang` (auto/en/hi/mr), `yt-asr` (auto/off/force), `yt-overwrite` (checkbox), `yt-run`, `yt-choices` (candidate buttons), `yt-result` (aria-live).
- Render: `render-panel`, `render-assets`, `render-fallback` (table), `render-choices` (container for the 4 human-choice buttons), `render-choice-note`, `render-status`, `step9-status`, `step9-list`, `render-prepare`, `render-prepare-reason`.
- Gate D: `gate-d-panel`, `gate-d-languages` (table, one row per language), `gate-d-safezone` (chip), `gate-d-bgm`.
- H3 author: `author-panel`, `author-missing` (table), `author-cache-status`, `author-preview`, `author-run` (disabled by default), `author-confirm` (text input), `author-output` (pre).
- Ops: `ops-panel`, `ops-disk`, `ops-server`, `ops-colab`, `ops-refresh`.
- Runs and documents: `runs-docs` (container; pipeline.js fills it).
Gate and story cards stay dynamic inside `#wizard` (U2 owns their ids, e.g. `gate-note-<id>`, `gate-confirm-<id>`).
- Note (U3): `chip-story` wraps `project-name`; set the `project-name` text only, not `chip-story`. Stepper li-element structure unchanged (L2 keyboard buttons not done; U2 may add them).

## U1 deviations (2026-11-07, U1 backend)
Routes are as in section 4a and the (k)-(o) list. Where U1 differs:
1. Author live run: NOT built. POST /api/author/preview and GET /api/author/status are dry run only (h3_author --dry-run argv, no model call). status returns run_allowed false always. A live route, the typed confirm phrase AUTHOR FIELDS and ANIME_STUDIO_ALLOW_FREE_MODEL=1 check wait for the owner's go.
2. Command h3_author is in the command table (dry run argv only); --live is never passed.
3. Gate A approve re-runs the validator at approve time (not a stored report): a stored report is shown, the gate uses a fresh run.
4. Gate D approve needs render/step9_qc.json with status pass (no runner writes it yet, so Gate D stays closed) and a ready gate_d plan.
5. GET /api/render/status: prepare_ready (bool) on top; gate_d.languages[] rows = {lang, vo:{present,expected}, captions_ass, final_mp4, checks:[{name,ok,detail}]}; bgm = {enabled, manifest, label}; caption_safe_zone text; human_choices list.
6. Voice map: GET/POST /api/pack/voices?pack=stories/<slug>/<pack> returns/accepts {characters:[{id,name}], voices:{id:{en,hi,mr}}}. Keys must be bible character ids or NARRATOR; placeholders are fine.
7. Link result (GET /api/jobs/<id>/result for yt_transcript): {status ok|needs_choice|refused|failed, candidates, engine, chars, file, reason, overwrite_offer}. Parsed from the log text (yt_transcript has no --json).
8. POST /api/story/<slug>/voices writes story.json voice_engine and one registry event (kind story_saved, voice_engine field) - judgment call.
9. write_pack needs out_lang (en, hi, mr, a comma list or all); no default.
10. run_kaggle_prepare: style defaults to kaliya_mardan only for that story's folder; other stories must send style. profile optional 1-5.
11. h3_prepare: story must be an H3 story file (episodes + registry); reel N is sent as EP_0N.
12. Export: GET /api/export?reel=&story=&pack= (pack NAME); clips only from that story's results links.
13. Packet: POST /api/packet {story, pack, jobs, shots}; jobs must be in flow/generated/<story>/.
14. Images: GET /api/images?adhyay=&story= (default kaliya_mardan = legacy roots); other stories use story_links images folder and flow/generated/<story>/.
15. /api/pipeline and /api/pipeline/summary take ?story=&pack= (default project pointer); /api/pipeline also returns code_fingerprint.
16. Spend: cumulative cap is Config.total_cap (None until the owner sets it); ledger file ui/runs/colab_spend.jsonl (ops_checks format).

