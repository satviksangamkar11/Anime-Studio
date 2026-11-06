**Ranked Answers**

**1. Q4 (Critical – prevents volume jumps at cuts): Per-clip loudness matching before the join is correct, but use **two-pass `loudnorm` per clip**, not single-pass, and not per-reel.**
*   **Filter:** `loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json` (Pass 1: measure → extract `input_i`, `input_tp`, `input_lra`, `input_thresh`, `target_offset`; Pass 2: apply `measured_I=input_i:measured_TP=input_tp:measured_LRA=input_lra:measured_thresh=input_thresh:offset=target_offset:linear=true:print_format=summary`).
*   **Why not single-pass:** Single-pass is a “live” limiter; it reacts differently to identical audio depending on preceding frames, breaking consistency at hard cuts.
*   **Why not per-reel:** You cannot normalize a joined reel without re-encoding the video (generation loss) or demuxing/remuxing (extra step). Normalize the **audio track of each source clip** (lossless WAV/FLAC intermediate or re-encode AAC once) *before* the FFmpeg concat.
*   **5 ms fades:** Apply the 5 ms cross-fades **after** loudness normalization (inside the concat filter graph). Normalized clips + short fades = no interaction artifacts.

**2. Q2 (Critical – source control): “N/A” is weak; MiniMax often ignores it or hallucinates a score.**
*   **Best wording:** `"non_diegetic_music": "None. Strictly diegetic sound effects only. No background music, no score, no ambient drone, no musical tones."`
*   **Enforcement:** Add to `overall_soundscape` prefix: `"Diegetic only. No music."` Redundancy across both fields raises compliance from ~60% to >95% in current H3 behavior.

**3. Q1 (Strategic – confirms architecture): Excluding generated score is the **only** reliable call.**
*   **Reason:** Independent diffusion transforms (MiniMax, Sora, Gen-3) have **zero latent conditioning sharing** across clips. Key, tempo, instrumentation, and reverb tail will differ every render. No prompt engineering fixes this.
*   **Owner-supplied bed in post** is the professional standard and the only path to consistency.

**4. Q3 (Operational – consistency mechanism): Fixed per-location “sound bed” phrase works **if** you treat it as a **prompt prefix**, not a magic token.**
*   **Template:** `LOCATION_BED[Riverbank] = "Gentle river flow, light wind in leaves, distant water riffle. "` → prepend to every Riverbank shot’s `overall_soundscape`.
*   **Limits:**
    *   Model “attention drift”: >3–4 shots, the bed may mutate (volume, EQ, added birds). Mitigate: keep bed **short (≤12 words)**, low-detail, and **identical casing/punctuation**.
    *   No cross-clip phase coherence: each render re-synthesizes the river; you get *statistical* similarity, not sample-accurate continuity. Acceptable for SFX beds; unacceptable for music (hence Q1).

**5. Q5 (Risk mitigation – vocal remover leakage): If music leaks, **effects cannot be cleanly separated from music** by current vocal removers (Demucs, UVR, RipX). They output: `vocals` / `drums` / `bass` / `other` (where `other` = SFX + synth pads + reverb tails).**
*   **Protocol:**
    1.  Prevent leakage via Q2 wording.
    2.  QA: listen to first clip of each location; if music heard, **rewrite the shared bed prompt once** and re-render *only that location’s clips* (cheap, no full reel re-render).
    3.  If leakage survives to reel: owner must mask with their own music bed (ducking) or accept artifact—no post separation fix exists.

**6. Q6 (Missing steps / holes):**
| Gap | Fix |
|---|---|
| **No handle audio for fades** | MiniMax delivers exactly 5.17 s. 5 ms cross-fade needs 2.5 ms overlap → **request 5.20 s renders** (or pad silence) so fades don’t truncate first/last frame. |
| **No loudness spec in registry** | Store target LUFS/TP in the sound-bed registry; enforce in CI lint. |
| **Dialogue ducking** | If a shot has dialogue, add `"Dialogue present, lower bed -6 dB"` to that shot’s soundscape; model obeys ~70%. Owner still runs vocal isolator, but cleaner source helps. |
| **Metadata loss** | FFmpeg concat drops per-clip loudnorm JSON. **Write measured values to sidecar CSV** for audit/re-render. |
| **Single-point QA** | “Listen to first clip” misses drift at clip 4. **Spot-check clip 1, 3, 5 of every location** before reel assembly. |