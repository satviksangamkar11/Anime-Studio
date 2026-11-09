# RENDER shot 7 rework pre-flight, Nemotron Super NVIDIA (run.py + prompt, text) 11-09 12:27

HIGH | `OUT = Path("/content/out"); OUT.mkdir(parents=True, exist_ok=True)` | All renders are written only to ephemeral Colab local disk with no copy to Drive or durable storage; a disconnect or VM recycle loses finished clips. | Copy `/content/out` to Google Drive or a bucket inside `finish()` and after each successful `sid`.

HIGH | `if not (APP / "ckpts").exists(): os.symlink(TMP / "ckpts", APP / "ckpts")` | Checkpoints are symlinked but never downloaded or verified; if `/content/cache/ckpts` is empty, `wgp.py` fails late after wasting setup/queue time. | Add a checkpoint download and integrity check before launching `wgp.py`.

LOW | `subprocess.Popen(f"nvidia-smi ... > {OUT}/gpu.csv", shell=True)` | The background GPU monitor is never terminated, so the session stays running after the script ends, wasting paid Colab time. | Store the `Popen` object and call `terminate()` in a `finally` block at script end.

HIGH | "the figure's mouth stays closed except for non-verbal breaths at second 2. Silent performance: the figure never speaks, and his mouth stays shut while his lips remain completely closed for the whole shot." | Contradictory mouth instructions (open at second 2 vs. shut for the whole shot) can make the model animate lips or imply speech despite SFX-only audio, ruining the silent performance. | Remove the exception; state lips are fully closed for all 10 seconds.

HIGH | "Picture 2 (from Shot 1) aligns with the 8.71-second mark of the target video." | The end picture is anchored at 8.71s in a 10s clip, leaving the final ~1.3s unconstrained; the ending can drift away from Picture B. | Change alignment to the 10.00-second mark.

LOW | "the bees on the string hum louder." | Naming bees in the visual description risks summoning bees into the frame (cf. “serpents hiss” → cobras), adding unwanted visual elements. | Keep bees in `overall_soundscape` only or remove from the visual description.

none | PART 2 blank lines | No blank lines appear in the decoded prompt, so that known failure mode is not triggered. | none