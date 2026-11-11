`export_wavs` writes the edged audio directly to `dst`:

> `audio_edge.write_wav_mono(dst, edged, sr)`

The card requires writing to a temporary file and then replacing `dst`. Write to a temporary WAV in the same directory, call `require_wav` on it, then `os.replace(tmp, dst)`.

VERDICT: FIX-FIRST.