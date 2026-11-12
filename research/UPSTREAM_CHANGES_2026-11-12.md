# Upstream changes since 2026-11-06, and the one-frame (start-image-only) question

Date of research: 2026-11-12. Window: 2026-11-06 to 2026-11-12. Mode: read-only, public web plus local read-only files. Nothing cloned, installed, pulled or run. No keys printed.

Legend: FACT = quoted from a file, API response or page (link or file:line given). INFERENCE = our reasoning from those facts. Confidence is stated per section.

---

## 1. Repositories checked

| # | Repo | Window commits | Checked how | Status |
|---|---|---|---|---|
| 1 | https://github.com/deepbeepmeep/Wan2GP | 13 (2026-11-06 to 2026-11-11) | GitHub API commits?since, compare bd1ff59...main, commit detail for 0e0a06f, 9f30419, 1e0f487, releases | Commit list complete (13 ahead, 0 behind). File lists truncated for 0e0a06f and 9f30419. |
| 2 | Pika H3 Flex: https://github.com/Pika-Labs/Pika-H3-Flex and https://huggingface.co/Pika-Labs/Pika-H3-Flex | 9 commits after 2026-11-06 (README/CODEOWNERS only) | API commits; HF model card via fetch | No model-code repo; no weights change visible. |
| 2b | MiniMax H3 on HF: https://huggingface.co/MiniMaxAI/MiniMax-H3 and https://huggingface.co/Comfy-Org/MiniMax-H3 | not checked (no API access in this session) | not fetched | Not checked. |
| 3a | https://github.com/Comfy-Org/ComfyUI | 23 commits fetched, list truncated (earliest 2026-11-07) | API commits | Partial. |
| 3b | https://github.com/kijai/ComfyUI-WanVideoWrapper | API returned an empty list `[]` | API commits | Could not verify (empty result; repo or rate-limit issue not separated). |
| 4 | https://github.com/Wan-Video/Wan2.2 | API returned empty `[]` for releases | releases API | Empty result; no releases found in window. Not confirmed as "none exists". |
| 5 | https://github.com/satviksangamkar11/Anime-Studio | 104 commits since 2026-11-06 in the local worktree log (4 on 11-06, 66 on 11-07, 30 on 11-08, 2 on 11-09, 1 on 11-10, 1 on 11-11) | local `git log --since` (read-only) | Local only. Other repos of this account not checked. |
| 6 | https://github.com/googlecolab/google-colab-cli | 11 commits fetched since 2026-11-06 (2026-11-09 and 11-10) | API commits | Release tags not checked. |
| 7 | Other H3 repos referenced in research (github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo, alisson-anjos/ComfyUI-Molmo2-H3, matlowai/ComfyUI-Dials, etc.) | not checked | none | Not checked. |

Not checked at all: Hugging Face model-page revision history, issue and PR tracker search for Wan2GP (the API search returned HTTP 422 and no retry was made), Comfy-Org/workflow_templates commit history.

---

## 2. Dated change tables

### 2.1 deepbeepmeep/Wan2GP (13 commits, all in window)

| Date | SHA | Title | Why it matters to us |
|---|---|---|---|
| 2026-11-06 | 545d196 | viggle remake cp | Viggle, not our route. |
| 2026-11-06 | ad9e417 | added viggle remake, relayvsr | Not our route. |
| 2026-11-06 | f0b54e0 | fixed deepy crash | Not H3-specific. |
| 2026-11-08 | 665e4cf | manager 0.1.15: update notice | Manager app only. |
| 2026-11-08 | 0e0a06f | fixes, H3 Hyperflow Flash, H3 Image pDMD | Adds `defaults/minimax_h3_fl2va_hyperflow.json` (+17) and `defaults/minimax_h3_ref2va_hyperflow.json` (+18), and modifies `defaults/minimax_h3_image.json`. FACT (API patch excerpt): no `image_prompt_type` or end-frame change in the visible patch. A new faster sampler profile, not a new prompt mode. Our pin does not have it. |
| 2026-11-09 | 9f30419 | VMM graph pools ..., WGPKernels 1.4.3, DSpine drafter, Deepy / MCP / H3 HyperFlow updates | FACT: touches `models/minimax_h3/pipeline.py` (+90/-23), `minimax_h3_handler.py` (+31/-13), `transformer.py`, `hyperflow.py` (+59/-4), `constants.py` (+6), plus `H3_HYPERFLOW_LORA` and `H3_REGENERATE_IC_LORA` constants. Visible patch excerpt has no `image_prompt_type` or end-frame change, but the file list is truncated after the first 100 kB. Pipeline changes to `generate()` are a possible conflict with our pin. Needs a full diff read to close. |
| 2026-11-09 | 4331e1a | bonus track | Not H3. |
| 2026-11-09 | 5b63ae9 | tuning | Not H3-specific (no file detail read). |
| 2026-11-10 | 15f7355 | qwen3.8 speedup + H3 Image | Commit message only; version bump. |
| 2026-11-10 | 1e0f487 | qwen3.8 speedup + H3 Image | FACT: `shared/version.json` only, 19.25 to 19.28. No H3 logic in this commit. |
| 2026-11-10 | 56319ec | fixed version no | Version metadata. |
| 2026-11-11 | 31bf263 | fix yue2 crash | Not H3. |
| 2026-11-11 | 49f128d | manager 0.1.16: Linux AppImage | Manager app only. |

Keyword results over the 13 commit messages: H3 in 4 (0e0a06f, 9f30419, 15f7355, 1e0f487). MiniMax, Pika, image_prompt_type, start/end frame, last frame, continue, input_video_strength, Colab, VRAM, requirements, chumpy: none in messages.

Releases (WanGP Manager app, not the engine): manager-v0.1.15 (2026-11-08), manager-v0.1.16 (2026-11-11). No Wan2GP engine release in window (INFERENCE: the repo does not tag engine releases; the API result shows only manager tags).

FACT, pin status: `git` ref in the local pin is bd1ff59 (2026-11-04, "showrunner, taomate face refiner"). The compare API says main is 13 commits ahead, 0 behind. So our pin is 13 commits old, and all 13 are in the window.

### 2.2 Pika-Labs/Pika-H3-Flex (repo) and HF model card

| Date | SHA | Title | Why it matters to us |
|---|---|---|---|
| 2026-11-09 | 6dacb62 | Add CODEOWNERS | No model change. |
| 2026-11-09 | 6cb647e | Skip the text-encoder layers after the conditioning hidden state | Text-encoder speed change in the Pika repo. Not confirmed to be in our Wan2GP pin (pin uses its own Qwen3-VL path). |
| 2026-11-09 | 0eea927 | Merge PR #7 caoshiyi/te-truncation | As above. |
| 2026-11-10 | 457c20c, db8df40, 2bca9d7, 7095497, c3cb14e, f961d7e | README contribution section | Docs only. |
| 2026-11-02 | 06bd434 | Update Pika API link | Before the window. |

FACT (HF model card, via fetch): the card lists three modes: "Prompt and one opening frame" (`i2va`), "Prompt and one ending frame" (`l2va`), "Prompt and both endpoint frames" (`fl2va`). The Diffusers example "passes only `image=input_image`" and calls the workflow "first-frame to video+audio". The card has no changelog and no release date (BibTeX year 2026). The fetch summary was made by a small model, so the exact quotes should be re-checked on the page before use.

### 2.3 ComfyUI core (Comfy-Org/ComfyUI), H3 and video items only

| Date | SHA | Title | Why it matters to us |
|---|---|---|---|
| 2026-11-10 | ede4e5f | feat: Support MiniMax-H3-image (CORE-708) (#17655) | ComfyUI H3 Image node. An image model, not our video route. |
| 2026-11-10 | d9238b2 | [Partner Nodes] feat(MiniMax): add MiniMax H3 Image node (#17661) | Partner API node for H3 Image. Not used by us. |
| 2026-11-11 | 74eb0c4 | [Partner Nodes] feat(Wan): move Wan nodes to Comfy Router (#17639) | Partner API routing only. |
| 2026-11-11 | 4d64a8b | Conform Concatenate Video clips to the first clip's frame rate and audio (#17621) | Generic video concat; could help our clip joins, not an H3 change. |
| 2026-11-08 | dd196a9 | Get Video Components: hold the decoded frames once (#17562) | Memory change in a generic node; not H3-specific. |

Not found in the 23 fetched commits: any mention of I2V, first frame, last frame, end frame, or image_to_video. List is truncated (ends 2026-11-07), so older commits in the window may be missing.

### 2.4 kijai/ComfyUI-WanVideoWrapper

Empty result (`[]`). Not verified. Do not assume "no changes".

### 2.5 Wan-Video/Wan2.2

Releases API returned `[]`. No release found in the window. Not confirmed as "no Wan2.2 release exists". No newer Wan (Wan 3.x) repo was found in the checked sources.

### 2.6 satviksangamkar11/Anime-Studio (local git, read-only)

104 commits since 2026-11-06 in the worktree log. Relevant H3/render-path items from the local log:

| Date | SHA | Title | Why it matters to us |
|---|---|---|---|
| 2026-11-08 | 5fbfe27 | H3 author runs before Gate B; reel 1 shot 10 follows the source | Shot-level H3 authoring. |
| 2026-11-08 | e0c187d | H3 converter: editorial time is shifted by the head handle | Timing; relevant to tail handling. |
| 2026-11-09 | 5c58cc3 | H3 author: Super model option, Opus option, tests | Authoring options. |
| 2026-11-11 | feb7355 | Gap-closing session 2026-11-11: blocking sheet, timeline lock wiring | Pipeline wiring. |

The local commits are not upstream, so they do not change the engine. Other repos of the satviksangamkar11 account were not checked.

### 2.7 googlecolab/google-colab-cli

| Date | SHA | Title | Why it matters to us |
|---|---|---|---|
| 2026-11-10 | 6045e34 | refactor: remove `colab console` in favour of `colab ssh` (#205) | FACT: our `research/COLAB_CLI_REFERENCE.md` lines 72, 121 and 207 document `colab console` as the raw shell. Our code (`*.py`, `*.ps1`, `*.sh` outside research/) has no `colab console` or `colab repl` call (grep, 2026-11-12). INFERENCE: no break in running code; the reference doc is stale and must say `colab ssh`. |
| 2026-11-10 | 2033952 | feat(ssh): accept public key for --identity (#225) | New SSH identity option. |
| 2026-11-10 | 7f08a74 | fix: serialize format=json downloads (#232) | Download fix. |
| 2026-11-09 | 9d45981 | fix(cli): reject unknown --gpu/--tpu values (#211) | If our GPU name is not on the accepted list (we use G4), the CLI now rejects it. Check the exact GPU string we pass before the next session. |
| 2026-11-09 | f658cd8 | fix(security): state, log and history files readable only by the owner (#196) | Local file permissions only. |

Release tags not checked.

---

## 3. The one-frame (start-image-only) question

### (a) Does H3 in Wan2GP support start-image-only (image_prompt_type "S") as a normal workflow?

FACT, pinned source (bd1ff59 in `D:\aai work\kaggle_h3_test\wan2gp_src`):
- `models/minimax_h3/minimax_h3_handler.py:844` and `:921`: `"image_prompt_types_allowed": "TSEVL"` for both H3 FL2VA and Ref2VA. "S" is allowed.
- `wgp.py:1616-1619`: `if "S" in image_prompt_type: if "S" not in image_prompt_types_allowed: return err(...)`. Passes for H3.
- `wgp.py:1622-1625`: black-frame substitution only when `model_def["black_frame"]` is set. H3 does not set it (INFERENCE from the grep; not re-read in full).
- `wgp.py:1638-1639`: end frame is removed from the prompt type unless `end_frames_always_enabled` or an S/V/L letter is present. H3 sets `end_frames_always_enabled: True` (`handler:846` area), so the E letter would survive, but with S only and no E letter, `image_end` stays None (`wgp.py:1640-1656` only runs when "E" is in the type).
- `models/minimax_h3/pipeline.py:1004-1006`: `elif image_start is not None ... add_image_condition(prepare_stage_video(image_start), 0)`. The start-only branch is a normal code path.
- `pipeline.py:1008-1016`: end conditioning runs only `if image_end is not None`. With no end image, no end anchor is added.

INFERENCE: the start-only path is a supported, normal branch in the pinned code, not a hack. The code does not write any "tail snap" when there is no end image, because the snap is caused by an end anchor (`handler:117` and `:196`: "each window lands exactly on its end image").

Known issues: none found in upstream issues or PRs (the issue search returned HTTP 422; a web search returned no H3 start-only issue). Drift and colour shift for start-only: NOT FOUND in any source. Untested in our setup. Confidence: high for "code path exists in pin"; low for "quality is fine".

Our own guard: `h3/shot_mode.py:18-33` refuses "S" unless env `SHOT_MODE_S_ALLOW=1` (owner approval gate, message "start-only mode 'S' is not approved"). This is a local rule, not an engine limit.

### (b) What do upstream sources say about single-image I2V quality vs start+end for H3 or similar?

FACT: the Pika H3 Flex HF card offers first-frame (`i2va`), last-frame (`l2va`) and both-frame (`fl2va`) modes as separate options, and its Diffusers example uses only the first frame (see 2.2). It does not say that morphing happens with disagreeing frames.

FACT: the H3 help text in our pin (`handler:73`, `:117`, `:196`) warns that "each window lands exactly on its end image. When the action has drifted away from that picture, the last few frames jump to it." This is the morph/snap mechanism, and it exists only when an end image is given.

FACT: hosted providers (Atlas Cloud, RunComfy, Segmind, Wavespeed; see Sources) offer H3 first-frame-only generation, with last frame optional.

Not found: an upstream issue or discussion describing morphing for start-only vs start+end specifically for H3. The searches returned fork READMEs and changelogs only. INFERENCE from the code: morphing is an end-anchor effect, so start-only should not morph toward a fixed end picture. That is inference, not measured.

### (c) What would it take in our code (list only, nothing written)

- `h3/compile_h3_sing8.py:180`: `if route not in ("FL2VA", REF2VA): raise ValueError(...)`. Add a route (for example "I2VA") or allow start-only inside FL2VA when no end image. Also `compile_fl2va_prompt` at `:159-168` picks the FL2VA layout by `route_shot`.
- `h3/compile_h3_sing8.py:199`: the node `"5_FL2VAConditioning"` (MiniMaxH3ImageToVideo) is wired with both images. The start-only workflow needs the same node with the end input left empty (confirm the ComfyUI node accepts an empty end; this is the ComfyUI side, not Wan2GP).
- `h3/shot_mode.py:18-33`: `image_prompt_type()` allows "S" only with `SHOT_MODE_S_ALLOW=1`. This is the owner gate. Keep it or move the approval into the plan.
- `director/h3_director.py:346`: `image_prompt_type = ("S" if start_of(shot) else "") + ("E" if end_of(shot) else "")`. This already yields "S" alone when there is no end image. So the director can emit S-only today; the blocker is the route guard in the compiler and the shot_mode gate.
- `director/h3_director.py:348`: `"settings_version": 2.82`. Pin current version is 2.82 (`wgp.py:208`, per W3). The W3 note said the director wrote 2.73 at line 298; the current line is 348 with 2.82, so the W3 note is out of date on this point. Re-check before relying on it.
- Linter profile: not located in this pass. Grep for the FL2VA linter profile in `h3/` and add an S-only profile (no end-frame rule, no `fl2va_keyframes.end` requirement).
- `director/h3_director.py:346` and `:348` also carry `image_prompt_type` into settings; no change needed for S-only.

### (d) Does "continue from the last frame of the previous clip" (chaining) exist in Wan2GP?

FACT, pin: `handler:73`: "`video_source` continues an existing video; sliding windows carry overlapping video and audio forward." `handler:115`: "Sliding windows can continue a video beyond one generation. Choose any overlap amount ... It automatically reuses the overlap". `handler:192`: an injected frame on a window's first or last frame acts as that window's start or end image.

FACT, pin limits: `window_min` 124, `window_max` 481, `window_default` 362, `window_step` 17, overlap 1-120 step 17, default 18 (`handler:840-842`, `:918-921`). `frames_minimum` 107 (`handler:689-691`).

FACT, upstream (fork READMEs via search, not the official repo): "If you Continue a Video, you just need 'L L L' since the first frame is the last frame of the Source Video." Treat as unverified against the official repo.

INFERENCE: chaining is supported as `video_source` plus sliding windows, with the overlap carrying state. That is the feature our current FL2VA chaining uses. The official repo does not have a visible "continue from last frame" button name in the pinned docs that I could verify.

### (e) Anything new in the last 6 days that changes our options?

- 2026-11-08 to 11-10 (Wan2GP 0e0a06f, 9f30419, 1e0f487): new H3 HyperFlow fast profiles (FL2VA, Ref2VA) and H3 Image profiles. FACT: no `image_prompt_type` or end-frame change in the visible patch excerpts. Not a start-only change. Could change speed and quality of our route if we moved the pin; that is a separate decision. The file lists for 0e0a06f and 9f30419 are truncated, so a full read of `pipeline.py` and `minimax_h3_handler.py` diffs is needed before any pin move.
- 2026-11-10 ComfyUI d9238b2, ede4e5f: H3 Image node. Not a video change.
- 2026-11-10 colab-cli 6045e34: `colab console` removed. Our reference doc is stale; our code does not call it.
- Pika repo 2026-11-09: no model change.
- No upstream commit in the window touches the end-frame soft handling (`input_video_strength`), which our trace `research/WAN2GP_SOFT_END_TRACE_2026-11-11.md` says is forced to 1.0 on the pin (`wgp.py:1510-1511`). Still true for the window as far as the visible patches show. Not confirmed for the full pipeline diff.

---

## 4. Recommendation

YES, with conditions. A start-image-only (single-frame, I2V) structure is supported by the pinned H3 code path: "S" is allowed (`handler:844`, `wgp.py:1616-1619`), and the pipeline has a start-only branch with no end anchor (`pipeline.py:1004-1006`, `:1008`). Our director already emits "S" alone when there is no end image (`h3_director.py:346`). The blockers are on our side: the route guard (`compile_h3_sing8.py:180`) and the owner gate (`shot_mode.py:18-33`, env `SHOT_MODE_S_ALLOW=1`).

Conditions:
1. Owner sets `SHOT_MODE_S_ALLOW=1` (or approves the S gate in the plan). Required by our own rule.
2. The compiler accepts a start-only route (new route or FL2VA with no end image) and the linter has an S-only profile.
3. Drift and colour shift for start-only are not measured anywhere (upstream or ours). Must be tested on our 9:16 anime frames before use.
4. The 13 pinned-to-main commits are reviewed: the H3 HyperFlow changes in `pipeline.py` and `minimax_h3_handler.py` (truncated diff) could alter the start-only path. Do not move the pin without that read.

Cheapest verification (no GPU, no render, no Colab call, consistent with our no-Colab-calls rule): build one S-only settings JSON (`image_prompt_type: "S"`, no end image) and run it through the pinned `wgp.py --process <file> --dry-run` (`wgp.py:15147-15230`) to confirm validation passes and the end-frame path is not triggered. Then ONE owner-approved H3 render of a single shot, compared against the existing FL2VA render of the same shot (frame 0 match, last-frame drift, colour histogram). The render step needs owner approval; it is not run by this research.

---

## 5. What could NOT be checked

- Full diffs of Wan2GP 0e0a06f and 9f30419 (truncated; `pipeline.py`, `handler`, `transformer.py`, `hyperflow.py` not fully read).
- Wan2GP issue and PR tracker (search API returned HTTP 422; no retry).
- kijai/ComfyUI-WanVideoWrapper (empty API response).
- Wan-Video/Wan2.2 releases (empty API response).
- Comfy-Org/ComfyUI commits before 2026-11-07 (truncated at 23).
- Hugging Face model revision histories for MiniMax-H3 and Comfy-Org/MiniMax-H3.
- Colab-cli release tags.
- Other repos of satviksangamkar11 (only the local Anime-Studio worktree was read).
- Linter profile file location in `h3/` (not found in this pass).
- Quality of start-only output (no run; no upstream measurement).

Sources (upstream):
- https://api.github.com/repos/deepbeepmeep/Wan2GP/commits?since=2026-11-06T00:00:00Z
- https://api.github.com/repos/deepbeepmeep/Wan2GP/compare/bd1ff59...main
- https://api.github.com/repos/deepbeepmeep/Wan2GP/commits/0e0a06f
- https://api.github.com/repos/deepbeepmeep/Wan2GP/commits/9f30419
- https://api.github.com/repos/deepbeepmeep/Wan2GP/commits/1e0f487
- https://api.github.com/repos/Pika-Labs/Pika-H3-Flex/commits
- https://huggingface.co/Pika-Labs/Pika-H3-Flex
- https://api.github.com/repos/Comfy-Org/ComfyUI/commits?since=2026-11-06T00:00:00Z
- https://api.github.com/repos/googlecolab/google-colab-cli/commits?since=2026-11-06T00:00:00Z
- https://huggingface.co/MiniMaxAI/MiniMax-H3
