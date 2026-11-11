`test_one_sheet_drives_router_prompt_gate_clip` does not meet the “removing one cast member … changes all four” requirement. It never calls or asserts `cast_lock.cast`, and removing Raj leaves the clip QA classes unchanged:

> `assert blocking.known_classes(less["SHOT-002"]) == blocking.known_classes(base["SHOT-002"]) == {"person", "throne"}`

The later assertion removes *every* cast member, so it does not show one-member removal changing the classes:

> `empty["SHOT-002"]["cast"] = []`

**Fix:** add an assertion using the actual `cast_lock.cast` consumer for both sheets, and structure the before/after case so removing one member changes `known_classes` (for example, start with one cast member and remove that member). Keep the route, prompt, and `required_cast_count` before/after assertions for that same change.

VERDICT: FIX-FIRST.