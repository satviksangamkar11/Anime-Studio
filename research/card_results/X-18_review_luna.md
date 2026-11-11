`director/build_final_reel.py` applies the SFX policy only in the no-`--mix` branch:

> `else:`
> `    vo_rep = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else []`
> `    policy, levels = sfx_policy_for(rows, clips, a.vo, lg, vo_rep)`

When `--mix` is supplied, the preceding branch uses `mix_filter_text(...)` directly, so its audio bypasses the per-shot `sfx_keep` windows and bed gain. That leaves a path where the build can mix model SFX without rule 50(6).

**Fix:** Apply the SFX policy to the `--mix` audio path before muxing, or reject `--mix` when that path cannot enforce the policy.

VERDICT: FIX-FIRST.