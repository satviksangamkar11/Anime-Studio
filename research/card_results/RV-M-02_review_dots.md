**Real defects found**

1. **`test_linter_accepts_start_only_shot` can never fail.**  
   The test pops `picture_2_path` from `fl2va_keyframes`, but the linter never reads that key; it validates `shot["fl2va_keyframes"]["picture_2"]` (the key the router/`compile_comfyui_workflow` use). The assertion `KF-06 not in found` is tautological: the linter has no way to emit KF-06 for this change.  
   *Faulty line:* `sh["fl2va_keyframes"].pop("picture_2_path", None)   # route I2VA: start picture only`  
   *Fix:* pop the key the linter actually inspects:  
   `sh["fl2va_keyframes"].pop("picture_2", None)`

2. **`compile_comfyui_workflow` raises `KeyError` for the S LoRA.**  
   The card requires an `I2VA_S` workflow with a distinct LoRA; the profile is expected to hold `I2VA_SINGULARITY_REF_FUSION` (test asserts it). The code looks up `f"{workflow_mode(route)}_{ns}"` with `route="I2VA"`, producing `I2VA_<ns>`, which is not in the map. The caller catches `KeyError` and converts it to a generic `ValueError`, so the missing entry is reported as a profile error instead of being detected here.  
   *Faulty line:* `lora_name=prof["mode_to_lora_map"][f"{workflow_mode(route)}_{ns}"],`  
   *Fix:* use the card’s profile key: `prof["mode_to_lora_map"]["I2VA_SINGULARITY_REF_FUSION"]` when `route == "I2VA"`.

3. **`test_s_flag_off_refuses_s_row` uses an incomplete shot dict.**  
   `frame_row` requires `"start"` and `"pixel_frames"`; the test omits `"start"`, so the `ShotModeError` for the missing flag is unreachable — the test passes regardless of the flag logic.  
   *Faulty line:* `shot = {"id": "s1", "start": "a.png", "image_prompt_type": "S", "pixel_frames": 175}` (missing `"start"`)  
   *Fix:* add `"start": "a.png"`.

VERDICT: FIX-FIRST