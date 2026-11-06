"""YouTube link -> story SOURCE.md (the pipeline's "give a link" step).

  python director/yt_transcript.py URL stories/<slug> [--lang hi]

Uses yt-dlp to fetch the video's own captions (manual first, then auto), turns the WebVTT into plain running text
(no timestamps, no duplicate rolling lines) and writes stories/<slug>/SOURCE.md in the studio's SOURCE format
(header with the video title/channel/URL, the standing format rules, then "## TRANSCRIPT (verbatim)").
Free, no key, no model call. Refuses a slug outside stories/ or an unsafe slug; never overwrites an existing SOURCE.md
without --overwrite."""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import run_registry

SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
URL = re.compile(r"^https?://(www\.)?(youtube\.com|youtu\.be)/", re.I)
TAG = re.compile(r"<[^>]+>")
STAMP = re.compile(r"^\d{1,2}:\d\d:\d\d[.,]\d+\s+-->\s+")


def vtt_to_text(vtt: str) -> str:
    """Plain text from WebVTT. Auto captions repeat each line while rolling, so a line is kept only when it is new."""
    out, last = [], ""
    for raw in vtt.splitlines():
        line = raw.strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or STAMP.match(line) or "-->" in line:
            continue
        line = html.unescape(TAG.sub("", line)).strip()
        if not line or line == last:
            continue
        if last and line.startswith(last):      # rolling caption: the longer line replaces the shorter one
            out[-1] = line
        elif last and last.endswith(line):      # the new line is a tail already present
            continue
        else:
            out.append(line)
        last = line
    return re.sub(r"\s+", " ", " ".join(out)).strip()


def fetch(url: str, lang: str, work: Path) -> tuple[dict, Path]:
    meta = json.loads(subprocess.run(["yt-dlp", "--skip-download", "-J", "--no-playlist", url], capture_output=True, text=True, check=True).stdout)
    subprocess.run(["yt-dlp", "--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", f"{lang},{lang}-orig", "--sub-format", "vtt",
                    "--no-playlist", "-o", str(work / "src.%(ext)s"), url], capture_output=True, text=True, check=False)
    found = sorted(work.glob("src.*.vtt"))
    manual = [p for p in found if not p.name.endswith("-orig.vtt")]
    pick = (manual or found or [None])[0]
    if pick is None:
        raise SystemExit(f"REFUSED: no {lang} captions on this video")
    return meta, pick


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("story_dir", type=Path)
    ap.add_argument("--lang", default="hi")
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args(argv)
    studio = Path(__file__).resolve().parent.parent
    story = (studio / a.story_dir).resolve() if not a.story_dir.is_absolute() else a.story_dir.resolve()
    if not URL.match(a.url):
        print("REFUSED: not a YouTube link")
        return 2
    if story.parent != (studio / "stories").resolve() or not SLUG.match(story.name):
        print("REFUSED: story_dir must be stories/<safe-slug>")
        return 2
    target = story / "SOURCE.md"
    if target.exists() and not a.overwrite:
        print(f"REFUSED: {target} exists (use --overwrite)")
        return 2
    with tempfile.TemporaryDirectory() as td:
        meta, vtt = fetch(a.url, a.lang, Path(td))
        text = vtt_to_text(vtt.read_text(encoding="utf-8", errors="replace"))
    head = f"""# SOURCE: {meta.get('title', 'untitled')} ({meta.get('channel') or meta.get('uploader') or 'unknown channel'})

Fetched from {a.url} on the owner's link (YouTube captions, language {a.lang}; `{vtt.name}`). The text below the line "## TRANSCRIPT (verbatim)" is the caption text unchanged except for joining the caption lines. It is a spoken discourse typed by speech-to-text: expect errors, run-on sentences and a long commentary part. Mark anything not in the transcript as UNVERIFIED.

## Owner's format and look (standing rules)
- Short-form connected anime, 9:16 vertical, about 60-75 s per episode. The NUMBER of episodes is decided by the story analysis (do not force a number).
- Look: Indian classical cultural soul and staging combined with modern 2.5D prestige action-anime compositing (hard rim light, volumetric light, 3D camera depth).
- Language: Hindi dialogue and narration, Sanskrit only where quoted; captions short (max 6-7 words), never repeating the spoken line.
- Tone: devotional and reverent; no clickbait.

## Notes for the analysis
1. Separate NARRATIVE EVENTS (things that can be shown on screen) from SERMON/COMMENTARY (the speaker talking to the audience). Commentary may become short voice-over, never scenes by itself.
2. List likely speech-to-text errors (names of gods, places, mantras) for verification; do not silently rewrite them.
3. State which parts are canon (Purana / epic) and which are this speaker's oral additions.

## TRANSCRIPT (verbatim)

{text}
"""
    story.mkdir(parents=True, exist_ok=True)
    target.write_text(head, encoding="utf-8")
    print(f"written {target} ({len(text)} chars of transcript)")
    run_registry.record_transcript(story, url=a.url, chars=len(text), lang=a.lang, title=meta.get("title"), file=target.name)   # best effort
    return 0


if __name__ == "__main__":
    sys.exit(main())
