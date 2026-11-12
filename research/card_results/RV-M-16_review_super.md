Defect: bad input passes silently.

- Faulty line: `if per_lang[worst] > edit_seconds[sid] + 1e-9:`
- Why it is wrong: `edit_seconds[sid]` can be `float("nan")` (e.g. JSON `NaN` parsed into a sheet/writer-seconds value). Every comparison with NaN is False, so the M-16 over-length check never fires and a shot with an undefined edit second passes silently instead of raising the required writer-visible error.
- Exact fix: replace the comparison with `if not (per_lang[worst] <= edit_seconds[sid] + 1e-9):`. This preserves the `<=` tolerance for normal values while treating NaN as a violation.

VERDICT: FIX-FIRST