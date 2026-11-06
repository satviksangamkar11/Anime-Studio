# ASR fallback for YouTube links (director/asr_transcribe.py)

Owner order 2026-11-06: a YouTube link gives a transcript. First the video's own captions (free, yt-dlp), and only
when there are no usable captions, speech recognition of the audio (Whisper). Audio can be English, Hindi or Marathi.

## Use

```
python director/asr_transcribe.py URL --lang auto|en|hi|mr --engine local|groq --max-seconds N --out-dir DIR [--captions-first]
```

Prints a JSON summary (language, confidence, engine, model, speed, needs_choice, first 300 characters) and writes
`DIR/asr_segments.json` (segments with timestamps) and `DIR/asr_text.txt` (plain running text for SOURCE.md).
Default `DIR` is `D:/aai work/asr_tmp/out`. Without `--captions-first` it runs speech recognition only.

Python API for the integrator:

- `get_transcript(url, lang, engine, max_seconds, model, work_dir)`: captions first, then speech. Captions are skipped when `max_seconds` is set (bounded test).
- `check_captions(url, langs)`: manual track before auto; auto only when it is the video's own speech; returns text, segments and a quality report, or None.
- `transcribe_url(url, lang, engine, max_seconds, model, work_dir, keep_audio)`: download, 16 kHz mono wav, transcribe.
- `save_outputs(result, out_dir)`, `to_source_text(result)`.

## Language rules

- `en`, `hi`, `mr` are used as given (no detection). Hindi and Marathi get an initial Devanagari prompt so the script stays Devanagari.
- `auto` runs Whisper on three 30 s windows (start, middle, end), keeping only en/hi/mr.
  It accepts a language only when all three windows agree and the mean probability is at least 0.9.
  Otherwise the result has `needs_choice: true` and two `candidates`. The caller must ask the owner. Nothing is guessed.
- Marathi is often read as Hindi. If the text has clearly more Marathi word markers than Hindi ones (or the reverse), the
  result also returns `needs_choice`. With a forced language it only adds a note.
- Script check: at least 30 % of letters must be Devanagari (hi, mr) or Latin (en), else a note is added.

## Captions quality (check_captions)

A track is rejected when: fewer than 15 words per minute (videos of 30 s or more); one caption line in more than half the
cues; more than 10 % symbols; wrong script. Rejections are logged and the next track is tried.

## Engines and paths

- `local`: faster-whisper `large-v3-turbo`, `int8_float16` on the CUDA GPU, `int8` on CPU. Falls back to CPU if the GPU load fails (noted in `notes`).
  Long audio is done in 600 s chunks. Each chunk uses VAD and `condition_on_previous_text=False`, beam 5.
- `groq`: optional Groq whisper API, needs a forced language and a key. Key from `GROQ_API_KEY` or
  `D:/aai work/reverse-video-engine/secrets/groq_key_1.txt`. The key is never printed or logged. Upload chunks are at most 600 s (under 24 MB).
- Everything is free. Downloads, model cache (`D:/aai work/asr_cache`), temp audio (`D:/aai work/asr_tmp/job-*`) stay on D:.
  Temp audio is deleted after each run (`keep_audio=True` keeps it).
- Work folders and outputs must be under `D:/aai work/asr_tmp` or inside the studio folder. Other paths are refused.
- Non-YouTube links are refused.

## Tests

`C:/Python314/python.exe -m pytest -q -p no:cacheprovider director/test_asr_transcribe.py`. Offline: yt-dlp, ffmpeg,
Whisper and Groq are faked. The test scratch folders are on D:.

## Known ceilings

- Fixed 600 s chunks can cut a word at a chunk edge. Add an overlap if this shows up.
- Roll-up of auto captions drops a word that is genuinely repeated at a cue edge.
- Marathi/Hindi is decided by probability and word markers only. A confident wrong label (no markers) is accepted.
- The Hugging Face cache has no symlinks on this PC (Developer Mode is off), so Hugging Face warns about degraded storage. The measured cache for large-v3-turbo is 1.55 GB on D:.

Smoke test 2026-11-06: 90 s of Hindi audio (youtu.be/QIJ4qxo_Oz4), `--lang hi --engine local`, cuda int8_float16: ASR 11.3 s (7.9x realtime). Model load 346 s includes the first download. Output is Devanagari but has many word errors (for example "अधुथा", "बंदू", "इश्नान"), so the transcript needs owner review before SOURCE.md.
