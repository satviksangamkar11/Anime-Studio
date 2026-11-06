You are the coder of the studio's OWN Flow job builder (the old one lives in another project and must not be imported or copied). Python 3.14, stdlib only, offline.
READ the context: flow_series_kaliya.json (series data: characters, places, style chip, model), A_KM_image_spec_keyframesA.json (a SHOT SPEC: slot_order + shots with method, characters, place, action, light, reference_sentence, base_edit_id, edit_instruction), A_KM_flow_jobs_keyframesA.json (the JOB FILE the builder produced from them: use it as the reference for the exact output format and prompt wording), IMAGE_SYSTEM_FULL.md (how jobs are used).
WRITE: flow/scripts/build_jobs.py and flow/scripts/test_build_jobs.py.
CLI: python build_jobs.py --adhyay 1 --spec SPEC.json --series SERIES.json --out JOBS.json [--model-name "Nano Banana 2.1"]  (no network; refuses to overwrite --out unless --overwrite). Also importable: build_jobs(spec: dict, series: dict, adhyay: int) -> list[dict].
Output: a JSON list, one job per shot in slot_order, with the SAME keys as the reference job file (adhyay, shot_id, scene, method, file_version, flow_title, characters, people_count, props, chips, unaccepted_sheets, prompt, prompt_sha256, base_edit_id, edit_instruction, previous_shot, next_shot, sheets, attempt_cap, neighbour_chips, neighbour_sentence, model, status). Derive the rules from the reference file and state them in a module docstring: flow_title = <shot_id>__v<NN> (next free version 01 unless the spec says otherwise); chips order = characters (series ids), then the place chip, then props, then exactly ONE style chip (series style.chip); a character or place sheet that is not accepted in the series goes to unaccepted_sheets; people_count = number of characters; prompt = the series strict character sentence(s) + place + action + light + reference_sentence exactly as the reference jobs compose them (inspect several reference prompts and reproduce the pattern; prompt_sha256 = sha256 of the prompt text); previous_shot/next_shot from slot_order (None at the ends); attempt_cap 8; method 'generate' or 'edit' as in the spec; an 'edit' job with an empty or placeholder base_edit_id (empty, null, or containing 'PENDING') is REFUSED with ValueError; forbidden words from the series (key forbidden or the list found in the series/spec if any; if none exist use ["loincloth","naked","nude","bare-chested"]) refused with ValueError naming the shot; unknown character/place id refused; duplicate shot ids refused.
Tests (offline): (1) build from the real A_KM_image_spec_keyframesA.json + flow_series_kaliya.json (read them from the flow/ folder by path relative to the test file's grandparent) and assert for each of the 5 shots that shot_id, flow_title, method, characters, people_count, chips, attempt_cap, model and the previous/next shot ids EQUAL the reference A_KM_flow_jobs_keyframesA.json, that the prompt contains the action text and the light text of the spec, and that prompt_sha256 matches the prompt; (2) synthetic cases for every refusal; (3) CLI writes the file and refuses to overwrite.

STATE: flow/scripts/build_jobs.py and test_build_jobs.py already exist (context), 9 of 10 tests pass. Keep them; make the minimal change so test_build_jobs_matches_reference passes against the real reference file (do not weaken that test). Failing output follows:
        series = load_json(SERIES_PATH)
        reference_jobs = load_json(REFERENCE_JOBS_PATH)
    
        jobs = build_jobs(spec, series, adhyay=1)
    
        assert len(jobs) == len(reference_jobs) == 5, "Expected 5 jobs"
    
        for i, (job, ref_job) in enumerate(zip(jobs, reference_jobs)):
            shot_id = ref_job["shot_id"]
            assert job["shot_id"] == shot_id, f"Shot {i}: shot_id mismatch"
            assert job["flow_title"] == ref_job["flow_title"], f"{shot_id}: flow_title mismatch"
            assert job["method"] == ref_job["method"], f"{shot_id}: method mismatch"
            assert job["characters"] == ref_job["characters"], f"{shot_id}: characters mismatch"
            assert job["people_count"] == ref_job["people_count"], f"{shot_id}: people_count mismatch"
            assert job["chips"] == ref_job["chips"], f"{shot_id}: chips mismatch"
            assert job["attempt_cap"] == ref_job["attempt_cap"], f"{shot_id}: attempt_cap mismatch"
            assert job["model"] == ref_job["model"], f"{shot_id}: model mismatch"
            assert job["previous_shot"] == ref_job["previous_shot"], f"{shot_id}: previous_shot mismatch"
            assert job["next_shot"] == ref_job["next_shot"], f"{shot_id}: next_shot mismatch"
    
            # Prompt contains the action text and light text from the spec
            spec_shot = spec["shots"][i]
            assert spec_shot["action"] in job["prompt"], f"{shot_id}: action text not in prompt"
            assert spec_shot["light"] in job["prompt"], f"{shot_id}: light text not in prompt"
    
            # Prompt SHA256 matches the prompt content
            expected_sha = hashlib.sha256(job["prompt"].encode("utf-8")).hexdigest()
            assert job["prompt_sha256"] == expected_sha, f"{shot_id}: prompt_sha256 does not match prompt"
            # And matches the reference
>           assert job["prompt_sha256"] == ref_job["prompt_sha256"], f"{shot_id}: prompt_sha256 != reference"
E           AssertionError: LEAP-01A: prompt_sha256 != reference
E           assert '84ec1631d2d7...fcb9ecc84ef6c' == '78db59b4073c...4737396f642d2'
E             
E             - 78db59b4073c7663933f6af13959763386c67cf41ed94a6b6fa4737396f642d2
E             + 84ec1631d2d7f4d3363fc033c531e5b637169bbc7c744c34e25fcb9ecc84ef6c

flow\scripts\test_build_jobs.py:64: AssertionError
=========================== short test summary info ===========================
FAILED flow/scripts/test_build_jobs.py::test_build_jobs_matches_reference - A...
1 failed, 9 passed in 0.37s
