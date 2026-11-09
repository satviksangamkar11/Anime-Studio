# RENDER V1 (supervl) 11-09 05:13

Reasoning: The plan is a single-pass, no-regeneration batch that adds shared-library voices in two groups, generates 54 clips, then post-processes length with ffmpeg. The ledger reserves credits before each call and holds reservations on ffprobe failure. Duration is checked only after payment, short clips are never padded, rate-2.0 voices can double cost against a 3000 cap, cleanup is by name prefix not voice ID, and there is no guarantee the per-job model is sent to the API. These create credit waste, sync failures, and stranded account state.

Preconditions that must be true before the first paid call:
- Concurrent voice slots never exceed 10 during the add/run/remove sequence.
- Per-job model is explicitly set: eleven_multilingual_v2 for Brahma/Markandeya/Munis hi; eleven_v4 for all other pairs.
- Rate is forced to 1.0 (or cost header confirms no 2.0 surcharge); total estimated cost is within cap.
- For every job, estimated duration <= slot * 1.08; otherwise the line is rewritten or rejected before any paid call.
- Ledger has no open reservations and the file lock is free.
- Voice IDs from POST /v1/voices/add are stored and used; no name-based resolution.
- ffmpeg and ffprobe are installed and the output directory is writable.
- Owner has signed off on exact text and pronunciations for all proper nouns.

FINAL:
high, _render_review_pkg.txt:8, Plan generates audio before validating slot fit; clips too long for atempo 1.08 are paid for and not regenerated, wasting credits and leaving missing audio. Fix: pre-estimate duration and reject any job where estimated duration > slot * 1.08 before calling ElevenLabs.
high, _render_review_pkg.txt:8, Plan only shortens over-long clips; clips shorter than the slot are left un-padded, causing sync gaps in the video. Fix: pad any clip shorter than its slot with silence to exactly the slot duration.
high, _render_review_pkg.txt:6, On ffprobe/duration failure the run stops and the credit reservation stays open; the ledger then blocks all further calls and voices/slots remain allocated, an inconsistent abort state. Fix: wrap each call in try/finally that releases or settles the reservation to zero on any failure before stopping.
high, _render_review_pkg.txt:8, Batch 1 fills all 10 Starter voice slots; cleanup removes only KP-* voices, so any non-KP-* voice remains and blocks adding batch 2, stranding the run with slots occupied. Fix: track added voice IDs and remove exactly those IDs after each batch, not by name prefix.
high, _render_review_pkg.txt:4, en Carter (Brahma), en Matthew Schmitz (Munis), hi Frederick (Markandeya) run at rate 2.0 and may double credit cost; cap 3000 can be exceeded mid-run, aborting with open reservations. Fix: force rate=1.0 in voice settings for all calls or raise cap to at least 4780 and verify per-call cost header before reserving.
high, _render_review_pkg.txt:6, Job key reuses any existing mp3 with the same sha256; if a prior aborted run left a corrupt or wrong-voice clip under that key, it is reused without regeneration, producing wrong audio. Fix: on reuse, verify existing mp3 decodes and duration matches expectation; otherwise delete and regenerate.
high, _render_review_pkg.txt:4, No evidence the per-job model (eleven_multilingual_v2 for Brahma/Markandeya/Munis hi) is passed to the API; defaults may use eleven_v4 and produce wrong language audio. Fix: assert and send model from the job row for every call; reject if model != multilingual_v2 for those three hi voices.
medium, _render_review_pkg.txt:8, ffmpeg atempo up to 1.08 is not sample-accurate; the result may still not equal the slot length, causing sync drift. Fix: after atempo, trim or pad the audio to exactly the slot duration.
medium, _render_review_pkg.txt:8, Voice selection may resolve by name after POST /v1/voices/add; shared-library voice name collisions could assign the wrong voice_id to a line. Fix: use the voice_id returned by add for all subsequent calls; never resolve by name.
medium, _render_review_pkg.txt:66-70, Approved text contains proper nouns (Kamadeva, Mahadeva, Brahma, Markandeya) and "Kamadevas" without possessive; no SSML/phonetic hints, so TTS will likely mispronounce names. Fix: add SSML <phoneme> or <say-as> for all proper nouns, or correct text to "Kamadeva's" before generation.
low, _render_review_pkg.txt:8, Removing voices after each batch deletes them from the account; if a clip later needs regeneration, the voice must be re-added, consuming a slot and complicating the one-shot run. Fix: keep voices in the account for the full run and remove only after all clips are finalized.
low, _render_review_pkg.txt:6, Ledger settles with API's character-cost header; if the header is missing or wrong, reserved vs settled credits diverge silently. Fix: validate the cost header is present and matches expected characters before settling; otherwise treat as failure and release reservation.
