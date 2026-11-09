"""Add / remove ElevenLabs shared-library voices in the account (needed before text-to-speech can use them; Starter has 10 voice slots, so cast voices are added in batches).
  plan   --pack P            : which cast voices are not in the account, split into batches of <= slots
  add    --pack P --batch N  : POST /v1/voices/add/<owner>/<voice_id> for every voice of batch N (0 credits)
  remove --pack P --batch N  : DELETE the voices of batch N from the account (only voices THIS tool added, name starts with KP-); the generated mp3 files are kept
The API key is read from the secrets folder and never printed."""
import argparse
import json
import sys
from pathlib import Path

import voice_cast as vc

SLOTS = 10


def missing(cast: dict, account_ids: set) -> list:
    """Distinct cast voice ids not in the account, in a stable order."""
    out = []
    for lg in vc.LANGS:
        for vid in cast[lg].values():
            if vid not in account_ids and vid not in out:
                out.append(vid)
    return out


def batches(ids: list, slots: int = SLOTS) -> list:
    return [ids[i:i + slots] for i in range(0, len(ids), slots)]


def find_shared(key: str, vid: str) -> dict:
    vs = json.loads(vc.http("GET", f"/v1/shared-voices?search={vid}&page_size=5", key)[0])["voices"]
    v = next((x for x in vs if x["voice_id"] == vid), None)
    if not v:
        raise SystemExit(f"voice {vid} not found in the shared library")
    return v


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["plan", "add", "remove"])
    ap.add_argument("--pack", required=True)
    ap.add_argument("--batch", type=int, default=0)
    a = ap.parse_args(argv)
    key = vc.api_key()
    cast = json.loads(vc.paths(Path(a.pack))[0].read_text(encoding="utf-8"))
    acct = json.loads(vc.http("GET", "/v1/voices", key)[0])["voices"]
    ids = {v["voice_id"] for v in acct}
    todo = batches(missing(cast, ids) if a.cmd != "remove" else [v["voice_id"] for v in acct if v["name"].startswith("KP-")])
    if a.cmd == "plan":
        print(len(sum(todo, [])), "voices to add in", len(todo), "batches:")
        for i, b in enumerate(todo, 1):
            print(i, b)
        return 0
    batch = todo[a.batch - 1] if 0 < a.batch <= len(todo) else []
    for vid in batch:
        if a.cmd == "add":
            v = find_shared(key, vid)
            name = ("KP-" + v["name"].split(" - ")[0])[:40]
            vc.http("POST", f"/v1/voices/add/{v['public_owner_id']}/{vid}", key, {"new_name": name})
            print("added", vid, name)
        else:
            vc.http("DELETE", f"/v1/voices/{vid}", key)
            print("removed", vid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
