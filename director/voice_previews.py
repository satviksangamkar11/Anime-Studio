"""Free step: download each cast voice's own preview sample (GET /v1/voices + the preview_url mp3; 0 credits, no text-to-speech call).
  python voice_previews.py --pack <root>/stories/<story>/<pack>   -> <out>/previews/<LANG>_<SPEAKER>_<VoiceName>.mp3"""
import argparse
import json
import re
import urllib.request
from pathlib import Path

import voice_cast as vc

ap = argparse.ArgumentParser()
ap.add_argument("--pack", required=True)
a = ap.parse_args()
cast_path, out = vc.paths(Path(a.pack))
cast = json.loads(cast_path.read_text(encoding="utf-8"))
data, _ = vc.http("GET", "/v1/voices", vc.api_key())
by = {v["voice_id"]: v for v in json.loads(data)["voices"]}
d = out / "previews"
d.mkdir(parents=True, exist_ok=True)
seen = {}
for lang in vc.LANGS:
    for who, vid in cast[lang].items():
        v = by.get(vid)
        if not v or not v.get("preview_url"):
            print("NO SAMPLE", lang, who, vid, "in account" if v else "NOT IN ACCOUNT")
            continue
        if vid not in seen:                                    # one download per voice; mr and hi share a voice
            seen[vid] = urllib.request.urlopen(v["preview_url"], timeout=60).read()
        name = re.sub(r"[^A-Za-z0-9]+", "_", v["name"].split(" - ")[0])
        (d / f"{lang}_{who}_{name}.mp3").write_bytes(seen[vid])
        print(lang, who, v["name"], len(seen[vid]), "bytes")
print("->", d)
