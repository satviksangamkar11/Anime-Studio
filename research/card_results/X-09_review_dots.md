**Defects found:**

1. **`test_job_keys_match_build_jobs` is weak/tautological.** It checks key-set equality against a hardcoded set of strings, not against the actual `build_jobs.py` fixture as the card requires ("key set equality with a build_jobs fixture job"). The test cannot fail if the implementation drifts from the real `build_jobs.py` schema.  
   *Faulty line:* `expected_keys = {"method", "chips", "prompt", "base_edit_id", "edit_instruction", "people_count"}`  
   *Fix:* Import the real job key set from `flow/scripts/build_jobs.py` (e.g., `from build_jobs import JOB_KEYS` or parse the source) and compare `set(job.keys()) == JOB_KEYS`.

2. **`test_b_instruction_from_change_list` does not cover the X-03 hand case.** The card explicitly demands "exact text from the X-03 hand case", but the test uses a generic two-item list instead of the specific X-03 scenario.  
   *Faulty line:* `changes = ["add a dog at (10,20)", "remove the car"]`  
   *Fix:* Replace with the exact X-03 change list (e.g., `changes = ["add person Alice at (100,200) scale 1.2 facing camera pose standing"]`) and assert the exact expected string from the X-03 hand case.

3. **`plates_index` silently passes when `plates.json` entry is a string and the file is missing.** If `entry` is a string, `rel_path = str(entry)`, and the fallback `candidate = os.path.join(flow_root, rel_path)` may point to a non-existent file; `open()` will raise `FileNotFoundError`, but the card requires a `KeyframeJobError` for missing plates, not a raw `FileNotFoundError`. However, this is a crash path, not a silent pass. The bigger issue is that `plates_index` does not validate that `entry` has a `"path"` key when it is a dict, leading to a `KeyError` crash if `"path"` is missing.  
   *Faulty line:* `rel_path = entry["path"] if isinstance(entry, dict) else str(entry)`  
   *Fix:* Add validation: `if isinstance(entry, dict) and "path" in entry: rel_path = entry["path"] else: raise KeyframeJobError(...)`.

4. **`jobs_for_shot` uses `change_list(sheet)` but the test mocks `blocking.change_list` globally, not the imported reference.** The module does `from blocking import change_list`, so the test's `monkeypatch.setitem(sys.modules, "blocking", blocking)` only affects future imports. Since `_setup_module` does `sys.modules.pop("keyframe_jobs", None)` and re-imports, it works, but if the module was already imported, the mock is ignored. This is a test fragility, not a code defect.

5. **`main()` passes `bible_names=[]` to `jobs_for_shot`, ignoring the CLI argument.** The card says `bible_names` is a parameter, but the CLI hardcodes `[]`.  
   *Faulty line:* `job_a, job_b = jobs_for_shot(sheet, sheet["plate_id"], [])`  
   *Fix:* Parse `bible_names` from the CLI or from the sheet, e.g., `bible_names = sheet.get("bible_names", [])`.

**VERDICT: FIX-FIRST**