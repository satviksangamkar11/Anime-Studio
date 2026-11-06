FINAL:

## 1. Gaps you missed (M-gaps)

M1. `director/run_registry.py` appends to `RUNS.jsonl` with no story+pack composite key and no index. Lookups scan the whole file. (uncertain: exact field names)
M2. No per-stage checkpoint file for writer stages (`stage_*_raw.json`), image jobs, or render rungs. A crash leaves partial state and no resume marker. (uncertain: which function owns checkpoints)
M3. No centralized retry/backoff/circuit breaker for OpenRouter `429` and NVIDIA `PENDING_BUDGET`. Retries are ad hoc in each caller. (uncertain: file)
M4. No configuration file. Ports, paths, models, spend cap, and defaults are CLI flags or hardcoded. (uncertain: if a settings module exists)
M5. `stories/<slug>/story.json` has no `schema_version` and no source transcript hash. Packs cannot be proven immutable against source changes. (uncertain: exact fields)
M6. `bible.json` has no layout discriminator field. Dict vs list is only known by trying `pack_to_spec`. (uncertain: path)
M7. No voice `.wav` manifest mapping voices to characters or reels. Only `audio/bgm_manifest.json` is mentioned. (uncertain: file)
M8. No caption style spec (font, size, position, language) stored per story. Devanagari font is not bundled (G13) and no data model references it. (uncertain: file)
M9. No persistent per-shot image job status in `flow/scripts/download_queue.py`. The queue is not tied to story+pack for resume. (uncertain)
M10. `flow/scripts/build_jobs.py` and `pack_to_spec.py` have no "skip if output exists" check for old Flow outputs. (uncertain)
M11. No pre-commit or CI secret scan to block `secrets/`, `stories/`, transcripts, or keys from the public repo. `.gitignore` alone is not enforcement. (uncertain: if `.pre-commit-config.yaml` exists)
M12. Owner-pasted story text is not sanitized before use in slugs or folder names. Path traversal risk. (uncertain: slug function)
M13. No violence/rating field in pack or registry for the Mahadev nose-cutting decision. Owner must set the level but code has no place to store it. (uncertain: field)
M14. `ui/server.py` gate endpoints have no auth, CSRF, or rate limiting. Localhost only, but still exposed to local scripts. (uncertain)
M15. No per-story or per-session Colab spend tracker. The 15-unit cap is not accumulated across runs. (uncertain: file)
M16. No disk-space check before render or tile generation. C: is nearly full and D: has about 9 GB free. (uncertain: file)
M17. No process supervision, PID files, or health-check endpoint for background runs and the UI server. A stale server is noticed only manually (G3). (uncertain: file)
M18. No recorded model-response fixtures (VCR cassettes) for offline unit tests of writer or validator. Tests must be offline per owner rules. (uncertain: tests dir)
M19. No contract or snapshot tests between `flow/scripts/pack_to_spec.py` output and `h3/schema_and_linter.py` / H3 compiler input. (uncertain)
M20. `h3_director.py` or `compile_h3_sing8.py` may still contain V3 speech logic while V4 says H3 is SFX/Foley only. Dead or conflicting code risk. (uncertain)

## 2. All gaps ranked (integrator G + missed M)

Integrator gaps:

| ID | Gap | Severity | Blocks new story end to end |
|---|---|---|---|
| G1 | Approvals global, not scoped by story+pack | High | High |
| G2 | One project only; no where-stopped summary or Continue button | High | High |
| G3 | Stale UI server; no restart reminder or health check | Medium | Medium |
| G4 | `upanishad_ganga_ep4_ashtavakra` missing `story.json`/`RUN_REPORT.md`; empty pack folder | Medium | Medium |
| G5 | Images/results folders not linked to story or pack | High | High |
| G6 | No automatic validator between writer and Gate A | High | High |
| G7 | No simple Hindi/Marathi language rule check | Medium | Medium |
| G8 | H3 Hindi/Marathi unverified; ElevenLabs decision open | High | High |
| G9 | Free model reliability; ad hoc retries only | Medium | Medium |
| G10 | Colab render and UI Render never end-to-end; loudness, Step 9, manifest hashes, fallback not wired | High | High |
| G11 | Writer bible saved in two layouts (dict vs list) | Medium | Low |
| G12 | Whisper tested on one Hindi sample; Marathi and Groq untested | Medium | Low |
| G13 | Devanagari caption font not bundled; never rendered on real device | High | Medium |
| G14 | Runs panel and Whisper wiring not checked in real browser | Medium | Low |
| G15 | Concurrent writes to `RUNS.jsonl` not locked; registry titles not redacted | Medium | Low |
| G16 | Nothing pushed since `8b1119a`; public repo must not receive secrets/stories | Low | None |
| G17 | Gate decisions in registry but UI gate state does not read them | Medium | Medium |
| G18 | Image reviewer switch to Nemotron 3.5 Super VL undecided | Low | Low |

Missed gaps:

| ID | Gap | Severity | Blocks new story end to end |
|---|---|---|---|
| M1 | Registry has no story+pack key or index | High | High |
| M2 | No per-stage checkpoints for writer, images, render | High | High |
| M3 | No centralized retry/backoff for 429 / PENDING_BUDGET | Medium | Medium |
| M4 | No configuration file | Low | Low |
| M5 | `story.json` has no schema version or source hash | Medium | Medium |
| M6 | `bible.json` has no layout discriminator | Low | Low |
| M7 | No voice `.wav` manifest for characters/reels | Medium | Medium |
| M8 | No caption style spec per story | Medium | Medium |
| M9 | No per-shot image job status tied to story+pack | Medium | Medium |
| M10 | No skip-if-exists for old Flow outputs | Low | Low |
| M11 | No pre-commit/CI secret scan for public repo | High | Low |
| M12 | Story text not sanitized for slugs/folders | Medium | Low |
| M13 | No violence/rating field for Mahadev decision | Medium | Low |
| M14 | UI gate endpoints no auth/CSRF/rate limit | Low | Low |
| M15 | No Colab spend tracker across runs | Medium | Medium |
| M16 | No disk-space check before render | Medium | Medium |
| M17 | No process supervision or health check | Medium | Low |
| M18 | No offline model fixtures for tests | Medium | Low |
| M19 | No contract tests pack_to_spec <-> H3 schema | Medium | Medium |
| M20 | Possible V3 speech code left in H3 SFX-only modules | Medium | Medium |

## 3. Fastest path: work packages

Files owned are disjoint so separate coder agents can run in parallel.

| WP | Goal | Files owned | Tests that prove it | Depends on | Size | Runs parallel with | Must wait for | Owner decision needed |
|---|---|---|---|---|---|---|---|---|
| WP1 | Registry core: story+pack scoped events and approvals; per-story where-stopped/next-step summary; fix `approvals.jsonl` filtering | `director/run_registry.py`, new `director/story_state.py`, `ui/runs/approvals.jsonl` (schema only) | Unit tests: write/query by story+pack; approvals return only matching story+pack; `story_state` summary matches last event; append lock under concurrent writes | None | L | WP2, WP3, WP6 | None | `approvals.jsonl` extra fields (timestamp, actor) |
| WP2 | Writer V4, pack_validator, simple language: validator before Gate A (six checks + six red lines + repair loop); canonical bible dict layout; simple Hindi/Marathi two-tier validator | `director/pack_validator.py`, `director/write_pack.py`, `director/writer_prompts.py`, `director/simple_language.py`, `director/data/*` | `test_pack_validator.py` (Kaliya defects, red lines, repair loop); `test_writer_v4.py` (canonical bible, one retry); simple language unit tests on Hindi/Marathi samples; regression that `pack_to_spec` still accepts legacy list layout | WP1 interface (stub OK) | L | WP1, WP3, WP6 | WP1 interface | None (word lists are owner-extended starter only) |
| WP3 | H3 audio/QC: H3 as SFX/Foley only (no speech); 5-mode router; Ref2VA compile; 4-rung fallback; asset manifest hashes; resolution ladder; Step 9 QC; Gate D voice/narration/3-stem mix/loudness/.ass captions | `h3/router.py`, `h3/compile_h3_sing8.py`, `h3/schema_and_linter.py`, `h3/fallback_policy.py`, `h3/asset_manifest.py`, `h3/step9_qc.py`, `h3/gate_d_audio.py`, `h3/profiles/`, `assets/fonts/README.md` | h3 suite (159); fallback tests force each rung; asset manifest hash verify tests; `step9_qc` tests; `gate_d_audio` loudness-after-AAC tests; caption font presence test (fails until owner downloads font) | None for code | L | WP1, WP2, WP6 | None | Confirm ElevenLabs is NOT called (open decision 5); approve font download `NotoSansDevanagari-Bold.ttf` (open decision 7) |
| WP4 | UI integration: wire validator before Gate A; render_controller uses router/lint/manifest/loudness; Step 9 gate in UI; registry events; per-story Continue button loads story+pack; scoped approvals UI; spend gate dialog (`--allow-spend`, typed confirm, 15-unit cap); stale-server/health check | `ui/pipeline.py`, `ui/server.py`, `ui/static/pipeline.js` | UI suite (178); end-to-end dummy story through Gates A-D in UI; Continue button loads correct story+pack; spend gate dialog blocks render without typed confirm; `/api/registry` returns known path after restart | WP1, WP2, WP3, WP5 | L | None | WP1, WP2, WP3, WP5 | Spend gate dialog copy/behavior; Gate A go/no-go for Upanishad and Mahadev (content decision) |
| WP5 | Render pipeline and Colab: link images/results to story+pack; skip already-rendered Flow jobs; per-shot image status; Colab render e2e dry-run; loudness in `render_controller`; disk-space check before render; centralized retry/backoff for free models | `h3/render_controller.py`, `h3/assemble_reel.py`, `director/run_kaggle.py`, `flow/scripts/build_jobs.py`, `flow/scripts/pack_to_spec.py`, `flow/scripts/download_queue.py` | `render_controller` unit tests; `build_jobs` skip-existing test; Colab dry-run with `--allow-spend` off; `run_kaggle.py` verifies `colab stop` at end and never uses `colab --logtostderr`; disk-space check fails gracefully below 2 GB free; retry/backoff unit tests for 429/PENDING_BUDGET | WP3 interfaces (WP2 `pack_to_spec` already exists) | L | WP1, WP2, WP3, WP6 after WP3 interface stable | WP3 interfaces | None |
| WP6 | Safety, docs, offline tests: pre-commit secret scan; slug sanitization; violence/rating field; offline model fixtures; contract tests pack_to_spec <-> H3 schema; docs: `story.json` schema, `RUN_REPORT` template, runbook for 429/Colab failure, ADRs for V4 audio and bible layout | New `.pre-commit-config.yaml`, new `tests/fixtures/`, new `docs/story_json_schema.md`, new `docs/RUN_REPORT_TEMPLATE.md`, new `docs/runbook_429_colab.md`, new `docs/ADR_v4_audio.md`, new `docs/ADR_bible_layout.md` | Pre-commit scan blocks `sk-`/`hf_` and `stories/`; slug sanitization unit tests; contract tests between pack spec and H3 schema; fixture-based writer/validator tests with no model calls | WP2, WP3 for contract tests; docs/safety can start now | M | WP1, WP2, WP3 (docs/safety parts) | WP2, WP3 (contract tests) | Violence/rating field values (open decision 2); push timing (open decision 4) |

Parallel plan:
- Batch 1 (start now): WP1, WP2, WP3, WP6 docs and safety.
- Batch 2 (after WP1 and WP3 interfaces stable): WP5; WP6 contract tests.
- Batch 3 (after WP1, WP2, WP3, WP5): WP4.

WP4 is the integration gate and must be last because it touches `ui/pipeline.py`, which WP1 and WP2 also integrate with through the registry and validator APIs.

## 4. Top 5 risks and cheap checks

R1. Owner does not confirm ElevenLabs/no-paid decision; audio step stalls. Cheap check: send one yes/no question; grep `h3/gate_d_audio.py` and `h3/router.py` for `elevenlabs` or API call code — must be absent.
R2. Free model `429` / `PENDING_BUDGET` stalls the writer with no resume. Cheap check: run `director/write_pack.py --writer super-vl` on a two-paragraph dummy story with a mocked `429`; verify it deletes bad `stage_*_raw.json` and resumes from saved stages.
R3. Colab render spends units without owner confirmation or never stops. Cheap check: dry-run `director/run_kaggle.py` with `--allow-spend` off; verify UI refuses; verify code calls `colab stop` on finish.
R4. Public repo accidentally tracks `stories/`, `secrets/`, or keys. Cheap check: run `git status --porcelain` and `git diff --stat` before any push; grep tracked files for `sk-`, `hf_`, `AIza`; confirm `.gitignore` covers `stories/` and `secrets/`.
R5. Stale UI server causes wrong gate approvals. Cheap check: restart `ui/server.py`; call `/api/registry?story=<slug>&pack=<pack>`; verify it returns a known path and scoped approvals, not "unknown path".