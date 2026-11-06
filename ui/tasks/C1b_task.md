You are the coder of ONE Python module for a local studio control UI. Python 3.14, stdlib only, pure functions, offline. Read CHECKLIST_REDESIGN.md (the API contract is binding) and the two sample files (shape of a real shots.json and bible.json).
WRITE: ui/pipeline.py and ui/test_pipeline.py (pytest, tmp_path fixtures that build a synthetic studio: stories/<slug>/SOURCE.md, a pack folder with stage_*_raw.json + shots.json + bible.json, a flow-output "images dir" with final/*__final.png, shots/*__review.json, download_queue.jsonl, flow_log.jsonl, and a results dir with .mp4 files).

Module API (exact names):
- STAGES = ["story","analysis","images","readout","render","export"]; GATES = {"A":"analysis","B":"images","C":"readout","D":"render"}; class GateError(Exception) with .code (int, 409 or 400) and a message.
- load_project(runs: Path) -> dict. runs/project.json holds {"story_slug","pack"(relative to stories/<slug>),"images_dir"(absolute path of the chapter folder holding final/, shots/, download_queue.jsonl, flow_log.jsonl),"results_dir"(absolute, clips),"takes"(int, default 3)}; a missing file gives defaults with None values.
- save_project(runs, project); read_approvals(runs) -> list[dict] (runs/approvals.jsonl, skip malformed lines); record_gate(runs, gate, decision, who, note, now=None) -> dict (append one JSON line {time,gate,decision,by,note}; creates the folder).
- facts(studio: Path, runs: Path) -> dict with: story_saved, pack_stage_files (count of stage_*_raw.json), shots_ready (shots.json AND bible.json exist and parse), n_shots, expected_images (2 * n_shots: a START and an END keyframe per shot), finals (count of *__final.png in <images_dir>/final), pending (latest line per (shot_id,version) in download_queue.jsonl whose (image_id,version) pair is not in flow_log.jsonl), reviewed (count of *__review.json in <images_dir>/shots), clips_home (count of *.mp4 under results_dir, recursive), planned_clips (n_shots * takes).
- pipeline_state(studio, runs, now=None) -> {"project","stages","gates","current"} exactly per the contract.
  Stage rules: story = done if SOURCE.md exists else ready. analysis = locked until story done; running if pack_stage_files>0 and not shots_ready (progress {"done":files,"total":None}); waiting_approval if shots_ready and gate A not approved; approved if A approved; ready otherwise; rejected if the latest A decision is reject. images = locked until A approved; ready if finals==0; running if 0<finals<expected or pending>0 (progress {"done":finals,"total":expected}); waiting_approval if finals>=expected>0 and pending==0 and B not approved; approved/rejected like A. readout = locked until B approved; waiting_approval until C approved; approved after. render = locked until C approved; ready if clips_home==0; running if 0<clips_home<planned (progress); waiting_approval if clips_home>=planned>0 and D not approved; approved/rejected like A. export = locked until D approved, else ready.
  CASCADE: a gate's approval only counts if every earlier gate currently counts as approved (rejecting A later invalidates later approvals); the latest decision per gate wins. gates[i].state = locked | open (its stage is waiting_approval) | approved | rejected. "current" = id of the first stage that is not approved/done.
- apply_gate(studio, runs, gate, decision, note, confirm=None, who="owner", now=None) -> gate dict. decision must be "approve" or "reject" else GateError 400; the gate must be open else GateError 409 ("gate is locked" / "stage not complete"); reject needs a non-empty note of at most 300 printable characters without newlines (else 400); gate "C" approve needs confirm == "START" exactly (else 400); on success call record_gate and return the new gate dict from pipeline_state.
- summary(studio, runs) -> the contract dict. episodes = per distinct shot["episode"] the shot count and the summed shot["seconds"]; seconds = total; characters = names from bible["characters"]; places = names from bible["environments"]; props = names (or ids) from bible["props"] if present else []; modes = count by shot["mode"]; images from facts; video {shots, takes, clips_home}; estimate g4_units = 10.05 * minutes / 60 with minutes = 7 + planned_clips*2.2 + 5 (round to 1 decimal); checks = list of {name, ok, detail} for: shots.json present, bible.json present, every shot has seconds>0, every shot has an episode, at least one episode, no duplicate shot ids; warnings = a text for each episode whose total seconds is outside 55..80 and, when finals < expected_images, a text saying so. If there is no pack, return zeros and empty lists and the warning "no pack yet".

Tests must cover: every stage status path above, the cascade, locked/open/approved/rejected gates, Gate C typed START, reject requires a note, malformed approvals lines skipped, the pending computation, summary numbers on the synthetic data, the estimate formula, the no-pack case. Never write outside the given runs folder. No network, no subprocess.

STATE: ui/pipeline.py and ui/test_pipeline.py already exist (context) and nearly pass. Keep them; make the MINIMAL edit that makes the failing tests pass. Failing output follows:
            {"id": "S3", "episode": 2, "seconds": 30.0, "mode": "gen"},
        ]
        bible = {
            "characters": [{"name": "Krishna"}, {"name": "Kaliya"}],
            "environments": [{"name": "River"}],
            "props": [{"id": "P1", "name": "Ball"}],
        }
        make_story(studio, slug)
        make_pack(studio, slug, "p", shots=shots, bible=bible)
        img_dir = make_images_dir(tmp_path, "img", finals=4, reviews=2)
        res_dir = make_results_dir(tmp_path, "res", clips=3)
        runs = make_runs(tmp_path, slug=slug, pack="p",
                         images_dir=str(img_dir), results_dir=str(res_dir), takes=2)
        s = summary(studio, runs)
        assert s["reels"] == 2
        assert len(s["episodes"]) == 2
        assert s["shots"] == 3
        assert s["seconds"] == 60.0
        assert s["characters"] == ["Krishna", "Kaliya"]
        assert s["places"] == ["River"]
        assert s["props"] == ["Ball"]
        assert s["modes"]["fl2va"] == 2
        assert s["modes"]["gen"] == 1
        assert s["images"]["expected"] == 6
        assert s["images"]["final"] == 4
        assert s["images"]["reviewed"] == 2
        assert s["video"]["shots"] == 3
        assert s["video"]["takes"] == 2
        assert s["video"]["clips_home"] == 3
        # estimate: planned_clips = 3*2=6, minutes = 7 + 6*2.2 + 5 = 7+13.2+5=25.2
        # g4 = round(10.05 * 25.2 / 60, 1) = round(253.26/60=4.221, 1) = 4.2
        assert s["estimate"]["minutes"] == 25.2
        assert s["estimate"]["g4_units"] == 4.2
        # checks
        assert len(s["checks"]) == 6
        assert all(c["ok"] for c in s["checks"])
        # warnings: episode 1 seconds=30 (ok), episode 2 seconds=30 (ok), finals 4 < 6 -> warning
>       assert len(s["warnings"]) == 1
E       AssertionError: assert 3 == 1
E        +  where 3 = len(['Episode 1 total seconds 30.0 outside 55..80 range', 'Episode 2 total seconds 30.0 outside 55..80 range', 'Finals 4 < expected images 6'])

ui\test_pipeline.py:811: AssertionError
=========================== short test summary info ===========================
FAILED ui/test_pipeline.py::test_summary_numbers - AssertionError: assert 3 == 1
1 failed, 43 passed in 0.67s

ALSO apply these changes required by the UI review (add tests): (1) a rejected gate re-opens when its stage is complete again: apply_gate must accept approve/reject when the latest decision is a reject and the stage is waiting_approval again; (2) analysis with saved stage files but no shots.json is status ready with detail 'N stages saved, run again to resume', never running; (3) summary episode rows are {episode, n, shots, seconds} with both keys; summary must not raise on null seconds/episode (treat as 0 / skip); (4) gate notes may be any printable text including Hindi (str.isprintable), no newlines, max 300 chars; approve notes are validated the same way; (5) summary video.planned_clips = shots * takes and expose it as video.planned_clips as well.
