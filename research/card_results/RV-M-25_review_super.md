Defect 1 — director/pack_validator.py
Faulty line: `REHOOK_WINDOW_FRAC = (0.45, 0.60)     # mirrors core.json retention.rehook_window_frac; a test keeps them equal`
Why wrong: M-25 requires the re-hook window to be taken from script_pacing ("use the same core fraction [0.45, 0.60] of total as script_pacing"). The module imports script_pacing with a comment saying the window comes from core.json via script_pacing, then hard-codes the fraction locally and never reads script_pacing for it. This duplicates the value instead of sourcing it, so the validator can drift from script_pacing/core.json and does not satisfy the required change.
Fix: Replace the local tuple with `REHOOK_WINDOW_FRAC = script_pacing.REHOOK_WINDOW_FRAC` (remove the hard-coded `(0.45, 0.60)`), so the validator uses script_pacing's value.

Defect 2 — director/writer_prompts.py
Faulty line: `8. Characters. At most {spec.MAX_CHARS_PER_SHOT} significant characters in a shot. Use only ids that exist in the Stage 2 bible."""` (the `rules_block` f-string ends at rule 8 with no re-hook/fraction sentence)
Why wrong: M-25 requires writer prompt text to state the re-hook fraction [0.45, 0.60] of total with no fixed seconds. The visible `rules_block` contains no re-hook window text at all, so the card requirement "writer prompt text states the fraction, no fixed seconds" is not met.
Fix: Insert a new rule into `rules_block` (renumbering subsequent rules) stating the re-hook window as the core fraction of total reel seconds with no fixed seconds, e.g. `9. Re-hook window: place a strong re-hook within {spec.REHOOK_WINDOW_FRAC[0]:.0%} to {spec.REHOOK_WINDOW_FRAC[1]:.0%} of total reel seconds (core retention fraction; no fixed seconds).`, sourced from spec/script_pacing rather than fixed seconds.

VERDICT: FIX-FIRST