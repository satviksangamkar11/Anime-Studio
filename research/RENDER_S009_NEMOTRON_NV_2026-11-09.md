# RENDER shot 9 rework pre-flight, Nemotron Super NVIDIA (run.py + prompt, text) 11-09 10:58

HIGH | `git clone https://github.com/deepbeepmeep/Wan2GP.git {APP} && git -C {APP} checkout bd1ff5903cbc18b46c3cce3b75bd140870b536a2` | `git clone` aborts when `/content/Wan2GP` already exists; on a reused Colab runtime (session left running) setup exits before rendering. | Remove the directory first (`rm -rf {APP}`) or pull/fetch instead of clone.

HIGH | `(OUT / "RESULT.json").write_text(json.dumps(results, indent=1))` | All outputs stay only in ephemeral `/content/out`; no copy to Drive or download, so a disconnected session or failed download loses finished clips. | Copy `/content/out` to mounted Drive or enable download before `finish`.

LOW | `for name, b64 in json.loads(base64.b64decode(open("/content/_blob0.txt").read())).items(): (inputs / name).write_bytes(base64.b64decode(b64))` | Images are written but never validated; missing or corrupt start/end picture wastes the full render. | Verify both input files exist and decode as valid images before the settings loop.

HIGH | `Picture 2 (from Shot 1) aligns with the 10.12-second mark of the target video.` | End frame is placed at 10.12s on a 10s clip; out-of-range alignment can break interpolation or ruin the final frame. | Change to `10.00-second mark`.

LOW | `The figure's mouth stays closed except for non-verbal breaths at seconds 5 and 7.` / `his lips remain completely closed for the whole shot.` | Contradictory lip instructions can confuse the model and produce inconsistent mouth animation. | Remove the breath exception or state breaths are nasal with sealed lips.