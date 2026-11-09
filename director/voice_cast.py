"""Anime reel ElevenLabs speech runner (copied from GranthStudio scripts/source/a1_eleven.py; only plan loading, languages en/hi/mr and paths changed) (DRAFT; nothing is validated until the owner has listened).
  voices   : free read-only list of the voices the account can use (name, id, labels)
  jobs     : prints the job list and the credit estimate for a set of line ids (no network)
  run      : generates the clips. NEEDS --allow-paid. Reuses every already-accepted clip (same text, language, voice, model, settings): a re-run buys nothing twice.
  measured : writes canon/audio/A1_eleven_measured.json (durations re-measured from the audio) for `a1_audio.py build --measured`
The API key is read at run time from the env var ELEVENLABS_API_KEY or from the first file in D:/aai work/secrets/elevenlabs; it is never printed, logged or written.
Wording: the owner's EASY script (docs/pilot/A1_full_script_simple.md) by default; --wording original = the verse text of the audio plan. The voice map is
canon/audio/A1_eleven_voices.json: {"mr": {"narrator": "<voice_id>", ...}, "hi": {...}}. Each job's key = sha256(language|voice id|model|settings|text); a clip file is named after it,
so changing any of those makes a NEW clip and never overwrites an accepted one."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import re

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("en", "hi", "mr")
FLOW = Path("D:/aai work/flow_outputs")


def paths(pack: Path) -> tuple:
    """Universal layout, nothing story-specific in code. pack = <root>/stories/<story>/<pack>.
    cast = <story>/voices_cast.json (ONE voice per character per language for the whole story, every reel reuses it);
    out = flow_outputs/anime_<story>/voices/<pack> (clips, manifest, measured, wavs of that reel)."""
    pack = Path(pack)
    return pack.parent / "voices_cast.json", FLOW / f"anime_{pack.parent.name}" / "voices" / pack.name


class voices:                                                                                # copied from GranthStudio a1_voices.prep_text, unchanged
    @staticmethod
    def prep_text(text: str) -> str:
        t = text.replace(chr(0x2019), "'").replace(chr(0x2018), "'").replace(chr(0x201c), "").replace(chr(0x201d), "").replace('"', "")
        t = re.sub(r"(?<![A-Za-z])'|'(?![A-Za-z])", "", t)                                  # CHANGED from Granth: an apostrophe between letters stays (Kamadeva's, don't); quote marks go
        t = re.sub(r"\s*\u0964\s*(?=\S)", ", ", t)
        t = re.sub(r"\s*\u0964\s*$", ".", t)
        t = re.sub(r"\s*,\s*,", ",", t)
        t = " ".join(t.split())
        return t if re.search(r"[.?!]$", t) else t + "."


API = "https://api.elevenlabs.io"
SECRETS = Path("D:/aai work/secrets/elevenlabs")
LEDGER = FLOW / "eleven_ledger.jsonl"                                                       # ONE ledger for the whole account: credits are shared by every story
TEST_LINES = []                                                                              # the owner-approved test set is passed with --lines (real script lines incl. hard names)
DEFAULT_CAP = 400                                                                           # credits for the first test; the full run passes --cap 3000
SETTINGS = {}                                                                               # voice settings sent with every request (empty = the voice's own defaults); part of the job key


def api_key() -> str:
    k = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not k and SECRETS.is_dir():
        for p in sorted(SECRETS.iterdir()):
            if p.is_file():
                k = p.read_text(encoding="utf-8", errors="ignore").strip()
                break
    if len(k) < 16:
        raise SystemExit("NOT_RUN: no ElevenLabs key (set ELEVENLABS_API_KEY or put one file in D:/aai work/secrets/elevenlabs)")
    return k


def load_plan(pack: Path) -> dict:
    """The only new part: the plan comes from the pack's shots.json instead of A1_audio_plan.json. One line per narration or dialogue entry,
    id SHOT-nnn-N (narration) or SHOT-nnn-Dk (dialogue k); voice = NARRATOR or the speaker; text in en/hi/mr. A language missing for a line is an error."""
    shots = json.loads((pack / "shots.json").read_text(encoding="utf-8"))
    lines = []
    for s in shots:
        a, sid = s["audio_and_dialogue_track"], s["id"]
        if a["narration_by_lang"].get("en", {}).get("text"):
            lines.append({"id": f"{sid}-N", "voice": "NARRATOR", **{lg: a["narration_by_lang"][lg]["text"] for lg in LANGS}})
        for k, d in enumerate(a["dialogue_by_lang"]["en"], 1):
            lines.append({"id": f"{sid}-D{k}", "voice": d["speaker"].replace("CHAR-", ""),
                          **{lg: a["dialogue_by_lang"][lg][k - 1]["text"] for lg in LANGS}})
    return {"lines": lines}


def job_key(lang: str, voice_id: str, model: str, text: str, settings: dict | None = None) -> str:
    return hashlib.sha256(json.dumps([lang, voice_id, model, settings or SETTINGS, text], ensure_ascii=False).encode("utf-8")).hexdigest()


def build_jobs(plan: dict, ids: list, vmap: dict, model: str, models: dict | None = None, line_speed: dict | None = None) -> list:
    """models = optional {lang: {speaker: model_id}}: a voice that is only verified for a language on another model (e.g. Hindi on eleven_multilingual_v2) gets that model; every other line uses `model`."""
    by = {l["id"]: l for l in plan["lines"]}
    missing = [i for i in ids if i not in by]
    if missing:
        raise SystemExit(f"unknown line ids: {missing}")
    jobs = []
    for i in ids:
        l = by[i]
        for lang in LANGS:
            vid = (vmap.get(lang) or {}).get(l["voice"])
            if not vid:
                raise SystemExit(f"no voice id for {lang}/{l['voice']} in the voice map")
            text = voices.prep_text(l[lang])
            mdl = ((models or {}).get(lang) or {}).get(l["voice"], model)
            spd = (line_speed or {}).get(f"{i}.{lang}")
            st = {"speed": spd} if spd else dict(SETTINGS)                           # speed is part of the job key: a new speed is a NEW clip, an old accepted clip is never overwritten
            jobs.append({"id": f"{i}.{lang}", "line": i, "lang": lang, "voice": l["voice"], "voice_id": vid, "model": mdl, "text": text,
                         "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "credits": len(text), "settings": st, "key": job_key(lang, vid, mdl, text, st)})
    return jobs


class Ledger:
    """Append-only credit ledger: reserve the estimate BEFORE a call (under a file lock, so two processes cannot both pass the cap), settle after;
    refuses past the cap or while any reservation is open. `confirmed` = the cost came from the API's own report, not from our estimate."""
    def __init__(self, path: Path, cap: int):
        self.path, self.cap = path, cap

    def rows(self) -> dict:
        out = {}
        if self.path.exists():
            for ln in self.path.read_text(encoding="utf-8").splitlines():
                r = json.loads(ln)
                out[r["id"]] = r
        return out

    def committed(self) -> int:
        return sum(r["credits"] for r in self.rows().values())

    def unconfirmed(self) -> int:
        return sum(1 for r in self.rows().values() if r["state"] == "SETTLED" and not r.get("confirmed"))

    def _add(self, r: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(r) + "\n")

    def _lock(self):
        lock = self.path.with_suffix(".lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(100):
            try:
                return os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_RDWR), lock
            except FileExistsError:
                try:
                    if time.time() - lock.stat().st_mtime > 60:                  # a crashed process left it behind
                        lock.unlink(missing_ok=True)
                except FileNotFoundError:
                    pass
                time.sleep(0.1)
        raise SystemExit("the credit ledger is locked by another run")

    def reserve(self, jid: str, credits: int):
        fd, lock = self._lock()
        try:
            if any(r["state"] == "RESERVED" for r in self.rows().values()):
                raise SystemExit("an earlier reservation is still open: check the ElevenLabs usage page, then settle it by hand")
            if self.committed() + credits > self.cap:
                raise SystemExit(f"credit cap {self.cap} would be exceeded ({self.committed()} used + {credits})")
            self._add({"id": jid, "state": "RESERVED", "credits": credits, "t": time.time()})
        finally:
            os.close(fd)
            lock.unlink(missing_ok=True)

    def settle(self, jid: str, credits: int, confirmed: bool):
        self._add({"id": jid, "state": "SETTLED", "credits": credits, "confirmed": confirmed, "t": time.time()})


def http(method: str, path: str, key: str, body: dict | None = None, timeout: int = 120):
    req = urllib.request.Request(API + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'ignore')}") from None


def probe_seconds(path: Path) -> float:
    """Decoded duration of the clip (ffprobe); an undecodable file raises."""
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=60)
    if out.returncode != 0 or not out.stdout.strip():
        raise RuntimeError(f"the audio does not decode: {out.stderr.strip()[:120]}")
    return float(out.stdout.strip())


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _save(man: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def run(jobs: list, out: Path, cap: int, key: str, post=http, ledger: Ledger | None = None, probe=probe_seconds) -> dict:
    led = ledger or Ledger(LEDGER, cap)
    mpath = out / "eleven_manifest.json"
    prev = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {"lines": []}
    rows = {r["key"]: r for r in prev["lines"] if r.get("ok") and r.get("key") and (out / r["file"]).exists() and sha256_file(out / r["file"]) == r["mp3_sha256"]}      # accepted clips are reused, never re-bought
    reused = 0
    failed = None
    for j in jobs:
        if j["key"] in rows:
            reused += 1
            continue
        row = {k: j[k] for k in ("id", "line", "lang", "voice", "voice_id", "model", "text", "text_sha256", "key", "settings")}
        f = out / "mp3" / j["lang"] / f"{j['id']}.{j['key'][:10]}.mp3"
        jid = f"{j['id']}#{time.time_ns()}"                                   # unique per attempt, so a re-take never overwrites an earlier charge
        led.reserve(jid, j["credits"])
        try:
            data, hdr = post("POST", f"/v1/text-to-speech/{j['voice_id']}?output_format=mp3_44100_128", key, {"text": j["text"], "model_id": j["model"], **({"voice_settings": j["settings"]} if j.get("settings") else {})})
            h = {k.lower(): v for k, v in hdr.items()}
            confirmed = "character-cost" in h
            used = int(h["character-cost"]) if confirmed else j["credits"]
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(data)
            secs = probe(f)                                                      # a 200 reply is not audio until it decodes
            if not 0.3 <= secs <= 90:
                raise RuntimeError(f"implausible duration {secs:.2f} s")
            led.settle(jid, used, confirmed)
            row.update(ok=True, file=str(f.relative_to(out)).replace("\\", "/"), mp3_sha256=sha256_file(f), seconds=round(secs, 3), credits_used=used, credits_confirmed=confirmed)
            rows[j["key"]] = row
            _save({"status": "DRAFT, NOT VALIDATED until the owner has listened", "lines": list(rows.values())}, mpath)      # checkpoint after every clip
        except RuntimeError as exc:                                          # the reservation stays open: the owner must look at the usage page
            row.update(ok=False, error=str(exc).replace(key, "[key]"))
            failed = row
            break
    man = {"status": "DRAFT, NOT VALIDATED until the owner has listened", "lines": list(rows.values()) + ([failed] if failed else []), "ok": len(rows), "reused": reused,
           "credits_committed": led.committed(), "credits_unconfirmed_clips": led.unconfirmed()}
    _save(man, mpath)
    return man


def measured(man: dict, plan: dict, script_sha256: str, model: str) -> dict:
    """The measured-durations file in the shape a1_audio.py expects, from the accepted clips of a run: every line of the plan needs a clip in both languages."""
    clips = {}
    for r in latest_ok(man):
        if True:
            clips[r["id"]] = {"lang": r["lang"], "voice": r["voice"], "speaker": r["voice_id"], "seconds": r["seconds"], "mp3_sha256": r["mp3_sha256"], "text": r["text"], "key": r["key"]}
    lines, problems = {}, []
    for l in plan["lines"]:
        for lang in LANGS:
            c = clips.get(f"{l['id']}.{lang}")
            if not c:
                problems.append(f"{l['id']}.{lang}: no accepted clip")
            elif c["voice"] != l["voice"]:                                   # a take in another voice never counts (owner 2026-11-01: speaker changes)
                problems.append(f"{l['id']}.{lang}: clip voice {c['voice']} but the plan says {l['voice']}")
            else:
                lines.setdefault(l["id"], {})[lang] = c["seconds"]
    return {"status": "MEASURED from ElevenLabs speech (DRAFT voices, NOT VALIDATED until the owner has listened)", "engine": "elevenlabs", "model": model, "script_sha256": script_sha256,
            "problems": problems, "clips": clips, "lines": lines}


def latest_ok(man: dict) -> list:
    """One accepted clip per line id: the NEWEST one (a re-generated line with new text or speed replaces the earlier clip in the mix; the earlier file stays on disk)."""
    d = {}
    for r in man["lines"]:
        if r.get("ok"):
            d[r["id"]] = r
    return list(d.values())


MAX_TEMPO = 1.15                                                                            # local speed-up limit (owner 2026-11-09: up to about 20 pct is acceptable; texts are sized for 1.08); the accepted mp3 is never modified
TRIM = "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse"      # cuts only the silence at both ends of the wav copy


def load_slots(pack: Path, windows: Path | None = None) -> dict:
    """{line id: slot seconds} from the pack: the time window each line owns in its shot.
    windows = optional FINAL_TEXT_v2.json ({"<line>.<lang>": {"window_s": ..}}): the audio window (free time inside the shot) replaces the scripted speaking window."""
    out = {}
    for s in json.loads((pack / "shots.json").read_text(encoding="utf-8")):
        a = s["audio_and_dialogue_track"]
        if a["narration_by_lang"]["en"].get("text"):
            t = a["narration_by_lang"]["en"]["time_range"]
            out[s["id"] + "-N"] = t[1] - t[0]
        for k, d in enumerate(a["dialogue_by_lang"]["en"], 1):
            out[s["id"] + "-D" + str(k)] = d["time_range"][1] - d["time_range"][0]
    if windows and Path(windows).exists():
        for k, v in json.loads(Path(windows).read_text(encoding="utf-8")).items():
            out[k.rsplit(".", 1)[0]] = v["window_s"]
    return out


def fit_report(man: dict, slots: dict) -> list:
    """One row per accepted clip: measured seconds, slot, tempo needed (>1 = too long), verdict. A too-long clip is fitted locally up to MAX_TEMPO; beyond that it is reported, never regenerated."""
    rows = []
    for r in latest_ok(man):
        if True:
            slot = slots[r["line"]]
            tempo = max(1.0, r["seconds"] / slot)
            rows.append({"id": r["id"], "seconds": r["seconds"], "slot": round(slot, 2), "tempo": round(tempo, 3), "verdict": "fits" if tempo == 1.0 else ("fit by atempo" if tempo <= MAX_TEMPO else "TOO LONG: owner decision")})
    return rows


def export_wavs(man: dict, out: Path, wav_dir: Path, model: str, rate: int = 44100, slots: dict | None = None, report: list | None = None) -> int:
    """Decode every accepted clip to mono 16-bit wav named <line>.<lang>.wav (the layout a1_voice.py mix reads), edge silence cut (TRIM); with slots, a clip longer than its slot
    (measured on the trimmed wav) is sped up by at most MAX_TEMPO in the wav copy. report (a list) receives one row per clip: trimmed seconds, slot, tempo, verdict."""
    n = 0
    for r in latest_ok(man):
        dst = wav_dir / "wav" / r["lang"] / f"{r['id']}.wav"
        dst.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(out / r["file"]), "-ac", "1", "-ar", str(rate), "-sample_fmt", "s16", "-af", TRIM, str(dst)], check=True)
        if slots:
            secs, slot = probe_seconds(dst), slots[r["line"]]
            tempo = max(1.0, secs / slot)
            if 1.0 < tempo <= MAX_TEMPO:
                tmp = dst.with_name(dst.stem + ".fit.wav")
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(dst), "-af", f"atempo={tempo:.4f}", str(tmp)], check=True)
                os.replace(tmp, dst)
            if report is not None:
                report.append({"id": r["id"], "seconds": round(secs, 2), "slot": round(slot, 2), "tempo": round(tempo, 3),
                               "verdict": "fits" if tempo == 1.0 else ("fit by atempo" if tempo <= MAX_TEMPO else "TOO LONG: owner decision")})
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("voices").add_argument("--pack", default=str(ROOT))
    ex = sub.add_parser("export")
    ex.add_argument("--pack", required=True)
    ex.add_argument("--out")
    ex.add_argument("--wav-dir")
    ex.add_argument("--model", default="eleven_v4")
    for n in ("jobs", "run", "measured"):
        p = sub.add_parser(n)
        p.add_argument("--lines", default=",".join(TEST_LINES) if n != "measured" else "ALL")
        p.add_argument("--model", default="eleven_v4", help="eleven_v4 or eleven_v3 (both support hi and mr, x1.0)")
        p.add_argument("--voices", help="default <story>/voices_cast.json = {lang: {SPEAKER: voice_id}}")
        p.add_argument("--pack", required=True, help="<root>/stories/<story>/<pack>")
        if n in ("run", "measured"):
            p.add_argument("--out")
        if n == "run":
            p.add_argument("--allow-paid", action="store_true")
            p.add_argument("--cap", type=int, default=DEFAULT_CAP)
            p.add_argument("--only-voices", help="comma list of voice ids: only their clips (used while the voice slots are rotated)")
        if n == "measured":
            p.add_argument("--to")
    a = ap.parse_args()
    cast, out = paths(Path(a.pack))
    a.out = getattr(a, "out", None) or str(out)
    a.voices = getattr(a, "voices", None) or str(cast)
    a.wav_dir = getattr(a, "wav_dir", None) or str(Path(a.out) / "wav_export")
    a.to = getattr(a, "to", None) or str(Path(a.out) / "eleven_measured.json")
    if a.cmd in ("jobs", "run") and not a.lines:
        raise SystemExit("pass --lines (comma list of line ids, or ALL): there is no default set, so nothing is bought by accident")
    if a.cmd == "voices":
        data, _ = http("GET", "/v1/voices", api_key())
        for v in json.loads(data)["voices"]:
            print(v["voice_id"], "|", v["name"], "|", v.get("labels"))
        return 0
    if a.cmd == "export":
        man = json.loads((Path(a.out) / "eleven_manifest.json").read_text(encoding="utf-8"))
        slots = load_slots(Path(a.pack), Path(a.out) / "FINAL_TEXT_v2.json")
        rep = []
        print(export_wavs(man, Path(a.out), Path(a.wav_dir), a.model, slots=slots, report=rep), "wavs ->", a.wav_dir)
        Path(a.out, "fit_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
        for r in rep:
            if r["verdict"] != "fits":
                print(r)
        return 0
    plan = load_plan(Path(a.pack))
    if a.cmd == "measured":
        man = json.loads((Path(a.out) / "eleven_manifest.json").read_text(encoding="utf-8"))
        res = measured(man, plan, hashlib.sha256((Path(a.pack) / "shots.json").read_bytes()).hexdigest(), a.model)
        Path(a.to).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(res['clips'])} clips, {len(res['problems'])} problems -> {a.to}")
        return 0 if not res["problems"] else 1
    ids = [l["id"] for l in plan["lines"]] if a.lines == "ALL" else a.lines.split(",")
    cast = json.loads(Path(a.voices).read_text(encoding="utf-8"))
    jobs = build_jobs(plan, ids, cast, a.model, cast.get("_models"), cast.get("_line_speed"))
    if getattr(a, "only_voices", None):
        keep = set(a.only_voices.split(","))
        jobs = [j for j in jobs if j["voice_id"] in keep]
    print(f"{len(jobs)} clips, about {sum(j['credits'] for j in jobs)} credits (an estimate: the API reports the real cost)")
    if a.cmd == "jobs":
        return 0
    if not a.allow_paid:
        raise SystemExit("this spends ElevenLabs credits: add --allow-paid")
    man = run(jobs, Path(a.out), a.cap, api_key())
    print(json.dumps({k: man[k] for k in ("ok", "reused", "credits_committed", "credits_unconfirmed_clips")}), "all ok" if man["ok"] >= len(jobs) else "STOPPED: see the manifest")
    return 0 if man["ok"] >= len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main())
