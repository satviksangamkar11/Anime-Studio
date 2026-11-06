"""YouTube link -> transcript when the video has no usable captions (owner order 2026-11-06).

Order (get_transcript): 1) the video's own captions, free through yt-dlp (check_captions);
2) speech recognition of the audio (transcribe_url): faster-whisper on the local GPU (CPU int8 fallback) or,
optionally, the Groq whisper API. Languages: en, hi, mr, or auto. Devanagari is kept as it is (no transliteration).

  python director/asr_transcribe.py URL [--lang auto|en|hi|mr] [--engine local|groq] [--max-seconds N]
         [--model large-v3-turbo] [--out-dir DIR] [--captions-first]

All downloads, model caches and temp audio live on D: (ASR_CACHE, ASR_TMP). Outputs and work folders may only be
under ASR_TMP or inside the studio. The Groq key comes from GROQ_API_KEY or the secrets file and is never printed.
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
import wave
from collections import Counter
from pathlib import Path

STUDIO = Path(__file__).resolve().parent.parent
ASR_TMP = Path("D:/aai work/asr_tmp")
ASR_CACHE = Path("D:/aai work/asr_cache")
GROQ_KEY_FILE = Path("D:/aai work/reverse-video-engine/secrets/groq_key_1.txt")
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODELS = {"large-v3-turbo": "whisper-large-v3-turbo", "large-v3": "whisper-large-v3"}
GROQ_MAX_BYTES = 24 * 1024 * 1024
URL = re.compile(r"^https?://(www\.)?(youtube\.com|youtu\.be)/", re.I)
LANGS = ("en", "hi", "mr")
MODEL = "large-v3-turbo"
SR = 16000
CHUNK_S = 600          # ponytail: fixed 10-minute chunks; a word cut at a chunk edge can come out garbled
WINDOW_S = 30
LANG_ACCEPT = 0.9      # detection probability needed to accept a language without asking the owner
SCRIPT_MIN = 0.3       # share of letters in the expected script
CAP_MIN_WPM = 15       # captions with fewer words per minute are mostly missing
CAP_MAX_REPEAT = 0.5   # one caption line in more than half the cues = a broken track
CAP_MAX_SYMBOLS = 0.10
PROMPT = {"hi": "यह एक हिंदी वीडियो का लिखित पाठ है।", "mr": "हा एक मराठी व्हिडिओचा लिखित मजकूर आहे."}
MR_MARK = {"आहे", "आहेत", "आहोत", "आणि", "नाही", "होते", "केले", "त्यांनी", "आम्ही", "तुम्ही", "झाले", "मला", "माझ्या"}
HI_MARK = {"है", "हैं", "और", "में", "नहीं", "ये", "हम", "आप", "किया", "थे", "मुझे", "मेरे"}
PUNCT = set(".,?!;:'\"()-–—…।॥‘’“”")
TIME = re.compile(r"^((?:\d+:)?\d{1,2}:\d{2}(?:[.,]\d+)?)\s+-->\s+((?:\d+:)?\d{1,2}:\d{2}(?:[.,]\d+)?)")
TAG = re.compile(r"<[^>]+>")
DEV_WORD = re.compile(r"[\u0900-\u0963\u0966-\u097F]+")
_DLL: list = []  # keeps the os.add_dll_directory handle alive


def _log(msg: str) -> None:
    print(f"[asr] {msg}", file=sys.stderr, flush=True)


def _scrub(text: str, key: str | None) -> str:
    return text.replace(key, "***") if key else text


def _allowed(path) -> Path:
    """Work folders and outputs only under ASR_TMP or inside the studio."""
    p = Path(path).resolve()
    for root in (ASR_TMP.resolve(), STUDIO.resolve()):
        if p == root or root in p.parents:
            return p
    raise ValueError(f"REFUSED: {p} is outside {ASR_TMP} and the studio")


def _job_dir(work_dir) -> Path:
    job = _allowed(work_dir or ASR_TMP) / f"job-{uuid.uuid4().hex[:8]}"
    job.mkdir(parents=True)
    return job


def _cache_env() -> None:
    """Every model and Hugging Face file goes to D: (C: is nearly full)."""
    os.environ["HF_HOME"] = str(ASR_CACHE / "hf")
    os.environ["XDG_CACHE_HOME"] = str(ASR_CACHE / "xdg")


def _cuda_dlls() -> None:
    """Windows: CTranslate2 loads cublas64_12.dll, which the torch wheel ships. find_spec does not import torch."""
    spec = importlib.util.find_spec("torch") if os.name == "nt" else None
    lib = Path(spec.origin).parent / "lib" if spec and spec.origin else None
    if lib and lib.is_dir() and not _DLL:
        _DLL.append(os.add_dll_directory(str(lib)))


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)


def _check(r: subprocess.CompletedProcess, what: str) -> None:
    if r.returncode != 0:
        raise RuntimeError(f"{what} failed: {(r.stderr or '').strip()[-400:]}")


# ---------------------------------------------------------------- captions (free, yt-dlp)

def _meta(url: str) -> dict:
    r = _run(["yt-dlp", "--skip-download", "-J", "--no-playlist", "--no-cache-dir", url])
    _check(r, "yt-dlp metadata")
    return json.loads(r.stdout)


def _auto_track(lang: str, auto: dict, original) -> bool:
    """Auto captions only when they are the video's own speech (-orig track or original language), never machine translations."""
    return f"{lang}-orig" in auto or (lang == original and lang in auto)


def _caption_text(url: str, lang: str, kind: str, job: Path) -> str | None:
    d = job / f"cap-{kind}-{lang}"
    d.mkdir()
    flag = "--write-subs" if kind == "manual" else "--write-auto-subs"
    _run(["yt-dlp", "--skip-download", flag, "--sub-langs", f"{lang},{lang}-orig", "--sub-format", "vtt",
          "--no-playlist", "--no-cache-dir", "-o", str(d / "cap.%(ext)s"), url])
    names = [f"cap.{lang}.vtt"] if kind == "manual" else [f"cap.{lang}-orig.vtt", f"cap.{lang}.vtt"]
    for n in names:
        if (d / n).exists():
            return (d / n).read_text(encoding="utf-8", errors="replace")
    return None


def _secs(t: str) -> float:
    return sum(v * 60 ** i for i, v in enumerate(reversed([float(x) for x in t.replace(",", ".").split(":")])))


def vtt_cues(vtt: str) -> list[dict]:
    """WebVTT -> [{start, end, text}] in seconds. Tags stripped, empty cues dropped."""
    cues, cur = [], None
    for raw in vtt.splitlines():
        line = raw.strip()
        m = TIME.match(line)
        if m:
            cur = {"start": _secs(m.group(1)), "end": _secs(m.group(2)), "lines": []}
            cues.append(cur)
        elif not line:
            cur = None
        elif cur is not None:
            cur["lines"].append(html.unescape(TAG.sub("", line)))
    out = []
    for c in cues:
        text = " ".join(" ".join(c["lines"]).split())
        if text:
            out.append({"start": c["start"], "end": c["end"], "text": text})
    return out


def roll_segments(cues: list[dict]) -> list[dict]:
    """Rolling auto captions repeat the words of the line before. Keep each new word once, with timing."""
    # ponytail: word-overlap roll; a word genuinely repeated at a cue edge is dropped too
    segs = []
    for c in cues:
        words = c["text"].split()
        prev = segs[-1]["text"].split() if segs else []
        k = next((k for k in range(min(len(prev), len(words)), 0, -1) if prev[-k:] == words[:k]), 0)
        new = words[k:]
        if new:
            segs.append({"start": c["start"], "end": c["end"], "text": " ".join(new)})
        elif segs:
            segs[-1]["end"] = c["end"]
    return segs


def _is_word(ch: str) -> bool:
    return ch.isalpha() or unicodedata.category(ch).startswith("M")


def script_check(text: str, lang: str) -> dict:
    """Share of letters in the expected script: Devanagari for hi/mr, Latin for en."""
    want = "DEVANAGARI" if lang in ("hi", "mr") else "LATIN"
    letters = [c for c in text if c.isalpha()]
    share = round(sum(unicodedata.name(c, "").startswith(want) for c in letters) / len(letters), 3) if letters else 0.0
    ok = share >= SCRIPT_MIN
    return {"ok": ok, "share": share, "note": None if ok else f"script check: {share:.0%} of letters are {want.title()} for language {lang}"}


def caption_quality(text: str, cue_texts: list[str], duration: float, lang: str) -> dict:
    """Reject captions that look bad. cue_texts are the raw cues (repeats included), text is the running text."""
    reasons = []
    words = len(text.split())
    wpm = round(words / (duration / 60), 1) if duration >= 30 else None
    if not text.strip():
        reasons.append("no text")
    if wpm is not None and wpm < CAP_MIN_WPM:
        reasons.append(f"only {wpm} words/min for a {duration:.0f} s video")
    top = Counter(cue_texts).most_common(1)[0][1] / len(cue_texts) if len(cue_texts) >= 5 else 0.0
    if top > CAP_MAX_REPEAT:
        reasons.append(f"one caption line is {top:.0%} of the cues")
    chars = [c for c in text if not c.isspace()]
    sym = sum(1 for c in chars if not (_is_word(c) or c.isdigit() or c in PUNCT))
    sym_share = round(sym / len(chars), 3) if chars else 0.0
    if sym_share > CAP_MAX_SYMBOLS:
        reasons.append(f"{sym_share:.0%} non-letter symbols")
    sc = script_check(text, lang)
    if not sc["ok"]:
        reasons.append(f"wrong script: {sc['note']}")
    return {"ok": not reasons, "reasons": reasons, "words": words, "words_per_min": wpm, "cues": len(cue_texts),
            "top_cue_share": round(top, 3), "symbol_share": sym_share, "script": sc}


def check_captions(url: str, langs=("hi", "mr", "en"), *, meta: dict | None = None, work_dir=None) -> dict | None:
    """The video's own captions if one passes caption_quality, else None. Manual tracks come before auto tracks."""
    if not URL.match(url):
        raise ValueError("REFUSED: not a YouTube link")
    t0 = time.perf_counter()
    meta = meta if meta is not None else _meta(url)
    duration = float(meta.get("duration") or 0)
    manual = meta.get("subtitles") or {}
    auto = meta.get("automatic_captions") or {}
    picks = [("manual", l) for l in langs if manual.get(l)]
    picks += [("auto", l) for l in langs if _auto_track(l, auto, meta.get("language"))]
    if not picks:
        _log(f"no caption track for {','.join(langs)}")
        return None
    job = _job_dir(work_dir)
    try:
        for kind, lang in picks:
            vtt = _caption_text(url, lang, kind, job)
            if vtt is None:
                _log(f"{kind} {lang} captions: no file from yt-dlp")
                continue
            cues = vtt_cues(vtt)
            segs = roll_segments(cues)
            text = " ".join(s["text"] for s in segs)
            q = caption_quality(text, [c["text"] for c in cues], duration, lang)
            if q["ok"]:
                _log(f"using {kind} {lang} captions ({len(segs)} lines)")
                return {"source_url": url, "text": text, "segments": segs, "language": lang, "language_confidence": None,
                        "needs_choice": False, "candidates": None, "engine": "captions", "model": None,
                        "params": {"track": kind}, "detection": None, "seconds_audio": round(duration, 2),
                        "seconds_wall": round(time.perf_counter() - t0, 2), "asr_seconds": 0.0, "x_realtime": None,
                        "script": q["script"], "notes": [f"{kind} captions ({lang}) from yt-dlp"], "quality": q}
            _log(f"{kind} {lang} captions rejected: {'; '.join(q['reasons'])}")
        return None
    finally:
        shutil.rmtree(job, ignore_errors=True)


def get_transcript(url: str, lang: str = "auto", engine: str = "local", max_seconds=None, model: str = MODEL,
                   work_dir=None) -> dict:
    """Owner order: the video's own captions first, speech recognition only when there are no usable captions.
    A max_seconds run is a bounded test, so it skips captions."""
    if max_seconds is None:
        try:
            cap = check_captions(url, ("hi", "mr", "en") if lang == "auto" else (lang,), work_dir=work_dir)
        except RuntimeError as e:
            _log(f"captions unavailable: {e}")
            cap = None
        if cap:
            return cap
    return transcribe_url(url, lang, engine, max_seconds, model, work_dir)


# ---------------------------------------------------------------- language choice (auto)

def window_starts(total: float, win: float = WINDOW_S) -> list[tuple[float, float]]:
    """Start, middle and end 30 s windows (one window when the audio is shorter)."""
    if total <= win:
        return [(0.0, float(total))]
    mid = total / 2 - win / 2
    return [(0.0, float(win)), (mid, mid + win), (total - win, float(total))]


def decide_language(window_probs: list[dict], allowed=LANGS, accept: float = LANG_ACCEPT) -> dict:
    """window_probs: one {lang: probability} per window (Whisper's all-language output).
    Accept only when every window agrees and the mean probability is high. Otherwise return two candidates for the owner."""
    picks = []
    for probs in window_probs:
        scored = {l: float(probs.get(l, 0.0)) for l in allowed}
        best = max(allowed, key=scored.__getitem__)
        picks.append((best, scored[best], scored))
    top, n = Counter(p[0] for p in picks).most_common(1)[0]
    conf = round(sum(p[1] for p in picks if p[0] == top) / n, 3)
    ranked = sorted(allowed, key=lambda l: -sum(p[2][l] for p in picks))
    info = {"windows": [{"lang": p[0], "prob": round(p[1], 3)} for p in picks], "confidence": conf}
    if n == len(picks) and conf >= accept:
        return {**info, "language": top, "needs_choice": False, "candidates": None}
    return {**info, "language": None, "needs_choice": True, "candidates": ranked[:2]}


def _rival(text: str, lang: str) -> str | None:
    """Whisper often labels Marathi as Hindi. Clear Marathi word markers in hi text (or the reverse) name the rival."""
    toks = DEV_WORD.findall(text)
    mr = sum(t in MR_MARK for t in toks)
    hi = sum(t in HI_MARK for t in toks)
    if lang == "hi" and mr >= 3 and mr >= 2 * hi:
        return "mr"
    if lang == "mr" and hi >= 3 and hi >= 2 * mr:
        return "hi"
    return None


# ---------------------------------------------------------------- audio and engines

def plan_chunks(total: float, chunk: float | None = None) -> list[tuple[float, float]]:
    chunk = chunk or CHUNK_S
    out, a = [], 0.0
    while a < total - 1e-9:
        b = min(total, a + chunk)
        out.append((a, b))
        a = b
    return out


def _download(url: str, job: Path) -> Path:
    _check(_run(["yt-dlp", "-f", "bestaudio", "--no-playlist", "--no-cache-dir", "-o", str(job / "src.%(ext)s"), url]),
           "yt-dlp audio")
    got = sorted(p for p in job.glob("src.*") if p.suffix != ".wav")
    if not got:
        raise RuntimeError("yt-dlp wrote no audio file")
    return got[0]


def _to_wav(src: Path, wav: Path, max_seconds) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le"]
    if max_seconds:
        cmd += ["-t", f"{max_seconds:g}"]
    _check(_run(cmd + [str(wav)]), "ffmpeg")


def _wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def _decode_wav(path: Path):
    import numpy as np
    with wave.open(str(path), "rb") as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


def _slice_wav(src: Path, a: float, b: float, dst: Path) -> None:
    with wave.open(str(src), "rb") as r:
        p = r.getparams()
        r.setpos(int(a * p.framerate))
        frames = r.readframes(int((b - a) * p.framerate))
    with wave.open(str(dst), "wb") as w:
        w.setnchannels(p.nchannels)
        w.setsampwidth(p.sampwidth)
        w.setframerate(p.framerate)
        w.writeframes(frames)


def pick_device() -> tuple[str, str]:
    """GPU when CTranslate2 sees CUDA (int8_float16 fits the 6 GB card), else CPU int8."""
    _cuda_dlls()
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "int8_float16"
    except Exception:
        pass
    return "cpu", "int8"


def _load_whisper(name: str, device: str, ctype: str):
    from faster_whisper import WhisperModel
    return WhisperModel(name, device=device, compute_type=ctype, download_root=str(ASR_CACHE))


def _groq_key() -> str | None:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key and GROQ_KEY_FILE.exists():
        text = GROQ_KEY_FILE.read_text(encoding="utf-8", errors="replace")
        first = next((l.strip() for l in text.splitlines() if l.strip()), "")
        key = first.split("=", 1)[-1].strip().strip("\"'")
    return key or None


def _post_groq(wav: Path, lang: str, key: str, api_model: str) -> dict:
    if wav.stat().st_size > GROQ_MAX_BYTES:
        raise ValueError(f"groq upload {wav.name} is over 24 MB")
    b = uuid.uuid4().hex
    fields = {"model": api_model, "response_format": "verbose_json", "temperature": "0", "language": lang}
    head = "".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in fields.items())
    head += f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{wav.name}"\r\nContent-Type: audio/wav\r\n\r\n'
    body = head.encode() + wav.read_bytes() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(GROQ_URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={b}",
        "User-Agent": "anime-studio-asr/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        raise RuntimeError(f"groq HTTP {e.code}: {_scrub(detail, key)}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"groq unreachable: {_scrub(str(e.reason), key)}") from None


def _run_groq(wav: Path, secs: float, lang: str, model: str, job: Path, notes: list) -> dict:
    key = _groq_key()
    api_model = GROQ_MODELS[model]
    segs, spent = [], 0.0
    chunks = plan_chunks(secs)
    notes.append(f"groq API {api_model}: {len(chunks)} chunk(s) of at most {CHUNK_S} s")
    for i, (a, b) in enumerate(chunks, 1):
        part = job / f"part{i:03d}.wav"
        _slice_wav(wav, a, b, part)
        t = time.perf_counter()
        data = _post_groq(part, lang, key, api_model)
        spent += time.perf_counter() - t
        part.unlink()
        rows = data.get("segments") or [{"start": 0, "end": b - a, "text": data.get("text", "")}]
        for s in rows:
            txt = str(s.get("text", "")).strip()
            if txt:
                segs.append({"start": round(float(s.get("start", 0)) + a, 2), "end": round(float(s.get("end", b - a)) + a, 2), "text": txt})
        _log(f"groq chunk {i}/{len(chunks)} done")
    return {"language": lang, "language_confidence": None, "needs_choice": False, "candidates": None, "detection": None,
            "segments": segs, "params": {"api_model": api_model, "chunk_seconds": CHUNK_S}, "asr_seconds": spent}


def _run_local(wav: Path, secs: float, lang: str, model: str, notes: list) -> dict:
    if secs < 1:
        raise RuntimeError("audio is shorter than 1 s")
    device, ctype = pick_device()
    t = time.perf_counter()
    try:
        whisper = _load_whisper(model, device, ctype)
    except Exception as e:
        if device == "cpu":
            raise
        notes.append(f"cuda load failed ({str(e)[:160]}); fell back to cpu int8")
        device, ctype = "cpu", "int8"
        whisper = _load_whisper(model, device, ctype)
    load_s = time.perf_counter() - t
    _log(f"model {model} ready on {device} ({ctype}) in {load_s:.1f} s")
    audio = _decode_wav(wav)
    t_asr = time.perf_counter()
    detection, conf, n_windows = None, None, 0
    if lang == "auto":
        probs = []
        for a, b in window_starts(secs):
            _, _, all_probs = whisper.detect_language(audio=audio[int(a * SR):int(b * SR)])
            probs.append(dict(all_probs))
        detection = decide_language(probs)
        n_windows = len(probs)
        _log(f"language windows {detection['windows']} -> {detection['language'] or 'needs choice'}")
        if detection["needs_choice"]:
            return {"language": None, "language_confidence": detection["confidence"], "needs_choice": True,
                    "candidates": detection["candidates"], "detection": detection, "segments": [],
                    "params": {"device": device, "compute_type": ctype, "load_seconds": round(load_s, 2)},
                    "asr_seconds": time.perf_counter() - t_asr}
        lang, conf = detection["language"], detection["confidence"]
    else:
        notes.append("language forced by the caller (no detection run)")
    prompt = PROMPT.get(lang)
    segs = []
    chunks = plan_chunks(secs)
    for i, (a, b) in enumerate(chunks, 1):
        it, _info = whisper.transcribe(audio[int(a * SR):int(b * SR)], language=lang, beam_size=5, vad_filter=True,
                                       condition_on_previous_text=False, initial_prompt=prompt)
        for s in it:
            txt = s.text.strip()
            if txt and txt != (prompt or ""):  # a prompt echoed back on silence is not speech
                segs.append({"start": round(s.start + a, 2), "end": round(s.end + a, 2), "text": txt})
        _log(f"chunk {i}/{len(chunks)} done ({b:.0f} of {secs:.0f} s)")
    return {"language": lang, "language_confidence": conf, "needs_choice": False, "candidates": None,
            "detection": detection, "segments": segs,
            "params": {"device": device, "compute_type": ctype, "beam_size": 5, "vad_filter": True,
                       "condition_on_previous_text": False, "chunk_seconds": CHUNK_S, "initial_prompt": prompt is not None,
                       "detection_windows": n_windows, "load_seconds": round(load_s, 2)},
            "asr_seconds": time.perf_counter() - t_asr}


def _check_args(url: str, lang: str, engine: str, max_seconds, model: str) -> None:
    if not URL.match(url):
        raise ValueError("REFUSED: not a YouTube link")
    if lang not in ("auto",) + LANGS:
        raise ValueError("REFUSED: lang must be auto, en, hi or mr")
    if engine not in ("local", "groq"):
        raise ValueError("REFUSED: engine must be local or groq")
    if engine == "groq" and lang == "auto":
        raise ValueError("REFUSED: engine groq needs --lang en|hi|mr (auto detection runs on the local model)")
    if engine == "groq" and model not in GROQ_MODELS:
        raise ValueError(f"REFUSED: no groq model for {model}")
    if max_seconds is not None and max_seconds <= 0:
        raise ValueError("REFUSED: max_seconds must be > 0")


def transcribe_url(url: str, lang: str = "auto", engine: str = "local", max_seconds=None, model: str = MODEL,
                   work_dir=None, keep_audio: bool = False) -> dict:
    """Download the audio of a YouTube link, convert it to 16 kHz mono wav and transcribe it.
    Temp audio is deleted unless keep_audio. See the module docstring for the result fields."""
    _check_args(url, lang, engine, max_seconds, model)
    if engine == "groq" and not _groq_key():
        raise RuntimeError("engine groq needs GROQ_API_KEY or the secrets file (none found)")
    t0 = time.perf_counter()
    job = _job_dir(work_dir)
    notes: list[str] = []
    _cache_env()
    try:
        _log(f"downloading audio: {url}")
        src = _download(url, job)
        wav = job / "audio16k.wav"
        _to_wav(src, wav, max_seconds)
        secs = _wav_seconds(wav)
        _log(f"audio {secs:.1f} s, 16 kHz mono")
        run = _run_groq(wav, secs, lang, model, job, notes) if engine == "groq" else _run_local(wav, secs, lang, model, notes)
        language, needs, cands = run["language"], run["needs_choice"], run["candidates"]
        text = " ".join(s["text"] for s in run["segments"])
        if needs:
            text = ""
        elif language in ("hi", "mr"):
            rival = _rival(text, language)
            if rival:
                if lang == "auto":
                    needs, cands = True, [language, rival]
                notes.append(f"word markers point to {rival} more than {language} (Whisper often labels Marathi as Hindi)")
        script = script_check(text, language) if text and language else None
        if script and not script["ok"]:
            notes.append(script["note"])
        asr_s = run["asr_seconds"]
        return {"source_url": url, "text": text, "segments": run["segments"], "language": language,
                "language_confidence": run["language_confidence"], "needs_choice": needs, "candidates": cands,
                "engine": engine, "model": model, "params": {**run["params"], "max_seconds": max_seconds},
                "detection": run["detection"], "seconds_audio": round(secs, 2),
                "seconds_wall": round(time.perf_counter() - t0, 2), "asr_seconds": round(asr_s, 2),
                "x_realtime": round(secs / asr_s, 2) if asr_s else None, "script": script, "notes": notes}
    finally:
        if not keep_audio:
            shutil.rmtree(job, ignore_errors=True)


def to_source_text(result: dict) -> str:
    """Plain running text (no timestamps) for stories/<slug>/SOURCE.md."""
    parts = [s["text"] for s in result.get("segments") or []] or [result.get("text") or ""]
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def save_outputs(result: dict, out_dir) -> tuple[Path, Path]:
    """Side files: segments with timestamps (JSON) and the plain running text."""
    d = _allowed(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    seg_path, txt_path = d / "asr_segments.json", d / "asr_text.txt"
    keep = ("source_url", "language", "language_confidence", "engine", "model", "params", "needs_choice", "candidates", "notes", "segments")
    seg_path.write_text(json.dumps({k: result.get(k) for k in keep}, ensure_ascii=False, indent=1), encoding="utf-8")
    txt_path.write_text(to_source_text(result) + "\n", encoding="utf-8")
    return seg_path, txt_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--lang", default="auto", choices=("auto",) + LANGS)
    ap.add_argument("--engine", default="local", choices=("local", "groq"))
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--out-dir", type=Path, default=None, help="default D:/aai work/asr_tmp/out")
    ap.add_argument("--captions-first", action="store_true", help="try the video's own captions before speech recognition")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    try:
        res = get_transcript(a.url, a.lang, a.engine, a.max_seconds, a.model) if a.captions_first \
            else transcribe_url(a.url, a.lang, a.engine, a.max_seconds, a.model)
        seg_path, txt_path = save_outputs(res, a.out_dir or ASR_TMP / "out")
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    except Exception as e:  # yt-dlp, ffmpeg, the model or Groq failed
        print(f"ERROR: {_scrub(str(e), _groq_key())}", file=sys.stderr)
        return 1
    text = to_source_text(res)
    summary = {k: res.get(k) for k in ("language", "language_confidence", "engine", "model", "needs_choice", "candidates",
                                        "seconds_audio", "seconds_wall", "asr_seconds", "x_realtime", "notes")}
    summary.update(params=res.get("params"), chars=len(text), segments=len(res.get("segments") or []),
                   segments_file=str(seg_path), text_file=str(txt_path), text_head=text[:300])
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
