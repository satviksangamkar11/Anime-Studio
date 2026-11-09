# RENDER V1 (Nemotron Super, NVIDIA)

FINDINGS

1. SEVERITY: BLOCK | CAUSE: ffprobe rejection (duration outside 0.3–90 s) stops the run and leaves the credit reservation open; ElevenLabs already charged for the call but the clip is not accepted. A restart either remains blocked or regenerates the clip, double-charging. | FIX: On ffprobe failure, settle the reservation as consumed, mark the clip failed, and halt; never auto-regenerate.

2. SEVERITY: BLOCK | CAUSE: ffmpeg atempo rewrites an accepted mp3 to fit the slot. The file on disk no longer matches the sha256 job key, so a restart or manifest check treats it as missing and regenerates it, wasting credits. | FIX: Never modify an accepted mp3. Pre-validate estimated duration before calling; skip and flag any clip needing more than 1.08× speedup or padding.

3. SEVERITY: BLOCK | CAUSE: Starter plan has 10 voice slots. Batch 1 adds 10 voices, filling all slots. The plan removes only voices named KP-*, so any non-KP-* batch-1 voice stays occupied and batch 2 (6 voices) cannot be added fully. | FIX:
