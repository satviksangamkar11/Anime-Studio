FINAL

high, write_pack.py:460, story path not validated — passing `../../../etc/passwd` as story argument reaches `run_registry.story_folder` without ensuring it lives under `stories/<safe-slug>/SOURCE.md`; fix: `story_path = Path(a.story).resolve(); assert story_path.parent.name == "stories" and story_path.name == "SOURCE.md" and re.fullmatch(r"[a-z0-9-]+", story_path.parent.parent.name)`

high, write_pack.py:459/366/414, output directory not confined — user-controlled `out_dir` (e.g. `/etc/cron.d/evil`) is passed to `mkdir(parents=True, exist_ok=True)` allowing arbitrary writes; fix: `out = _allowed(Path(a.out_dir))` with `_allowed` checking `STUDIO` or a designated packs root

medium, write_pack.py:366/414, pack folder overwrite — a previous failed run leaves `raw_response.json`/`shots.json` without `PACK.md`; a second run with same `out_dir` silently overwrites them because `refuse_finished` only checks for `PACK.md`; fix: at start of `run_single`/`run_staged` add `if out.exists() and any(out.glob("*.json")) or (out/"PACK.md").exists(): raise ValueError(f"{out} already contains output files")`

medium, write_pack.py:161/171, OpenRouter free-only check fetches catalog on every call with no caching — network failure or catalog change breaks all runs; fix: cache catalog in memory with TTL or fallback to a local allow-list for the three blessed free models

high, write_pack.py:383/426, recorder hooks can crash the writer — `rec.step` context manager (disk full, permission error, JSON encode error) propagates exceptions and aborts the real work; fix: wrap every `with rec.step(...):` in `try/except Exception: _log("recorder failed")` or make `Recorder.step` swallow all errors

medium, write_pack.py:132/181, redaction incomplete — `run_registry.redact` applied only to two error strings; keys/tokens in other logged fields (e.g. `envelope` result, `note`, `files`) may leak; fix: audit `run_registry.Recorder` and `envelope` to ensure no secret ever enters the JSONL

low, write_pack.py:321, `--stage-model` values not validated — `--stage-model 3=invalidmodel` passes `parse_stage_map` and later fails deep in the provider call; fix: `stage_model = parse_stage_map(a.stage_model, lambda v: v if v in KNOWN_MODELS else ap.error(f"unknown model {v}"))`

medium, asr_transcribe.py:519, Marathi-vs-Hindi `needs_choice` only triggered when `--lang auto` — user forces `--lang hi` on a Marathi video; `_rival` detects the mismatch but only adds a note, `needs_choice` stays `False`; fix: move the `needs_choice=True, cands=[language, rival]` block outside the `if lang == "auto":` guard

low, asr_transcribe.py:376-377, Groq key file parsing assumes `key=value` format — a file containing only the bare token `sk-xxx` yields empty key; fix: `key = first.split("=", 1)[-1].strip().strip("\"'") if "=" in first else first.strip().strip("\"'")`

low, asr_transcribe.py:65-66, `_scrub` only replaces exact key string — a logged error containing `Bearer sk-xxx` or upper-case variant leaks the token; fix: `return re.sub(rf"(?i)Bearer\s+{re.escape(key)}", "Bearer ***", text) if key else text`