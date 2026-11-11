Defect 1:
Line: `per_lang[lang] = bvt.needed_sec(lines, 1.0)`
Why: The card requires `editorial_by_lang.needed_sec` (restated under “Collisions: imports `needed_sec` from editorial_by_lang”). The code calls `build_vo_tracks.needed_sec`, the wrong module; it can crash with `AttributeError` and silently ignores the specified dependency.
Fix: Add `import editorial_by_lang` after the `build_vo_tracks as bvt` import and replace the call with `per_lang[lang] = editorial_by_lang.needed_sec(lines, 1.0)`.

Defect 2:
Line: `"min_seconds": min_seconds.get(row["id"]),`
Why: The card says to add `"min": min_seconds` to the shot dict handed to `plan_shots`. The code uses key `"min_seconds"`, so `plan_shots` never receives the blocking minimum and a silent shot is not lengthened by `min_seconds`.
Fix: Replace with `"min": min_seconds.get(row["id"]),`.

Defect 3:
Line:
```
        if i > 0 and (labels[i] != labels[i - 1] or not rows[i - 1].get("snap", False)):
            act_no += 1
```
Why: The `or not rows[i - 1].get("snap", False)` clause starts a new act after *every* non-snap shot, including exempt ones (bpm 60 or None) that share a cue/bpm with the next shot. The card defines an act as a run of shots with the same cue (or same bpm when no cue); the validation loop above already forces non-snap non-exempt shots to be last of their act. Over-segmenting here corrupts act grouping and `act_start_frame`.
Fix: Replace with `if i > 0 and labels[i] != labels[i - 1]: act_no += 1`.

VERDICT: FIX-FIRST