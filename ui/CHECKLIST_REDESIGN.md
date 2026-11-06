# UI redesign checklist: guided full pipeline with human gates (owner order 2026-11-06)

Owner: "the UI looks too basic. I give the story, the full pipeline runs, reels/shots/characters are decided, THEN ask for human approval; if OK, image generation (Flow), after every generation and correction a final check; if approved, show everything read from the story (reels, shots, every expected detail); I say START; only after all checks the full render."
Roles for this build (owner order): **Dots (free model, OpenRouter) is the CODER**, tests are the gate, **a Haiku xhigh agent REVIEWS** the result. Claude supervises and integrates. No Claude call in the UI or its tests.
Root cause of "looks bad" found 2026-11-06: `index.html` linked `style.css` and `app.js` relative to `/` but the server served only `/static/*` -> 404 -> no CSS, no JS. Fixed in `server.py` (serves both paths); the redesign below still stands.

## Pipeline (one page, left stepper, locked until the previous gate is approved)
| # | Stage | What runs (existing tools) | Gate |
|---|---|---|---|
| 1 | STORY | paste or load story, save as SOURCE.md | none (must be saved) |
| 2 | ANALYSIS | staged writer (free NVIDIA) -> reels, shots, characters, places, props, durations, sermon vs story events, validators | **GATE A: approve story plan** (human) |
| 3 | IMAGES | job packets for the Flow agents (Haiku LOW), reviewer (NVIDIA) on every candidate, corrections, queue, 2K download, watermark, finals | **GATE B: approve images** (human, after Claude's full-size check) |
| 4 | READ-OUT | everything read from the story: reels, shots, seconds, takes, images done, estimates, checks | **GATE C: START** (typed confirm) |
| 5 | RENDER | prepare (linter + payloads), spend gate, Colab run, clips home, QA | **GATE D: approve clips** |
| 6 | EXPORT | assembly plan, final reel files | none |
Gates are recorded append-only in `ui/runs/approvals.jsonl` (time, gate, decision, who=owner, note). A rejected gate re-opens its stage. Flow generation is done by Haiku-LOW agents that Claude starts from the chat; the UI shows the packet and the live progress, it never starts a Claude model.

## API contract (fixed; frontend and backend are written against this)
- `GET /api/pipeline` -> `{"project":{"story_slug":str|null,"pack":str|null},"stages":[{"id":"story|analysis|images|readout|render|export","title":str,"status":"locked|ready|running|waiting_approval|approved|rejected|done|failed","detail":str,"progress":{"done":int,"total":int}|null}],"gates":[{"id":"A|B|C|D","title":str,"stage":str,"state":"locked|open|approved|rejected","by":str|null,"at":str|null,"note":str|null}],"current":str}`
- `POST /api/pipeline/gate` body `{"gate":"A","decision":"approve|reject","note":str,"confirm":str?}` -> `{"ok":true,"gate":{...}}` or `{"error":str}` (409 if the stage is not complete or the gate is locked; Gate C needs `confirm` == "START"). Needs header `X-UI: 1` like every POST.
- `GET /api/pipeline/summary` -> `{"reels":int,"episodes":[{"n":int,"shots":int,"seconds":float}],"shots":int,"seconds":float,"characters":[str],"places":[str],"props":[str],"modes":{mode:int},"images":{"expected":int,"final":int,"pending":int,"reviewed":int},"video":{"shots":int,"takes":int,"clips_home":int},"estimate":{"g4_units":float,"minutes":float},"checks":[{"name":str,"ok":bool,"detail":str}],"warnings":[str]}`
- Stage runs reuse the existing `POST /api/preview` + `/api/run` commands (the page chains them); the backend only DERIVES status from disk plus approvals.

## Checklist (tick when done and verified)
- [ ] C1 `ui/pipeline.py` + `ui/test_pipeline.py`: derive stage status from files (story saved, pack stages, shots.json, finals, queue, clips) and approvals; gate rules (locked/open/approved/rejected, Gate C typed START, reject re-opens the stage); `summary()` from pack + folders; pure functions with injected roots; offline tests (coder: Dots)
- [ ] C2 `server.py` hooks: GET /api/pipeline, POST /api/pipeline/gate, GET /api/pipeline/summary (integrator: Claude; X-UI and Host guards, no new write path except `ui/runs/approvals.jsonl`)
- [ ] C3 `ui/static/style.css` + `index.html`: modern readable design: dark header with stepper, cards, big status chips, gate banners, responsive; keep the old tool panels reachable under "Advanced tools" (coder: Dots)
- [ ] C4 `ui/static/pipeline.js`: the wizard view (stepper, stage cards, gate approve/reject with note, Gate C typed START, summary read-out, progress bars, auto-refresh every 5 s, error bar), plain JS, textContent only (coder: Dots)
- [ ] C5 `flow/scripts/build_jobs.py` + test: the studio's OWN Flow job builder (spec + series -> jobs file in the existing format, forbidden words refused, chips order, base_edit_id rule); no Granth import (coder: Dots)
- [ ] C6 `ui/test_static.py` updated for the new files; all suites pass (ui, flow/scripts, h3, director)
- [ ] C7 Visual check in the browser pane at desktop and phone width (Claude, screenshots)
- [ ] C8 Dots security/correctness review of pipeline.py and the hooks
- [ ] C9 Haiku xhigh review of everything against this checklist; findings fixed
- [ ] C10 Docs: STATUS.md, README line, memory note; report to the owner

## Contract additions (2026-11-06, after the round-2 review)
- `POST /api/pipeline/project` body `{"story_slug":str?,"pack":str?,"images_dir":str?,"results_dir":str?,"takes":int?}` -> `{"ok":true,"project":{...}}`. Saving a story (`POST /api/story/<slug>`) also sets `project.story_slug`. The wizard posts `{"story_slug","pack"}` BEFORE it starts the analysis so the page and the server agree on the pack name.
- `GET /api/story` -> `{"slugs":[{"slug":str,"packs":[str],"has_source":bool}]}` (NOT `stories`).
- `GET /api/pack?pack=stories/<slug>/<pack>` additionally returns `props` ([{id,name}]), `character_names`, `place_names`, `prop_names` (plain string lists), `modes` ({mode:count}) and each shot row carries `purpose` (max 200 chars). `episodes[i]` has `n` (episode number), `shots`, `seconds`.
- `GET /api/pipeline/summary` episode rows are `{"episode":int,"n":int,"shots":int,"seconds":float}` (read `n`, fall back to `episode`).
- A rejected gate re-opens as soon as its stage is complete again (the decision after a rejection can be approve); a stage with saved partial analysis files but no shots.json is `ready` (detail says "N stages saved, run again to resume"), never stuck.
- Image jobs for the packet: read `GET /api/images` and use the jobs file names it lists; if none exist for the current story show "Image jobs are not built yet (job builder + image spec needed)" instead of sending a request.
