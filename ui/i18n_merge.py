"""Merges a batch of UI strings into ui/static/i18n/en.json and mr.json under a lock, so two coders can add their own key groups
at the same time without overwriting each other (UI redesign T3 and T4, owner 2026-11-07: parallel agents).

usage: python ui/i18n_merge.py BATCH.json --prefix group1,group2 [--replace] [--dir DIR]
BATCH.json = {"en": {"key": "text", ...}, "mr": {"key": "text", ...}}   (either side may be empty or missing)
Rules (each refusal exits 2 and writes nothing):
  - every key must start with one of the --prefix groups followed by a dot (a coder may only add its own groups);
  - a key that already exists with a DIFFERENT text is refused unless --replace is given (nobody silently changes another task's text);
  - en and mr of one batch must hold the same keys (a missing Marathi string is a missing string);
  - keys are lower-case dotted names, texts are non-empty strings; the files must already exist (task T2 creates them).
Output: sorted keys, indent 2, UTF-8, LF, written atomically (temp file + os.replace) while holding ui/static/i18n/.lock.
Exit 0 prints one line: how many keys were added, kept and replaced per language."""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEY_RE = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")


class Refused(Exception):
    pass


STALE_LOCK_SEC = 120   # a merge takes milliseconds; an older .lock is left over from a killed process


def _lock(path, timeout=30.0):
    start = time.time()
    while True:
        try:
            return os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > STALE_LOCK_SEC:
                    path.unlink()
                    continue
            except OSError:
                pass
            if time.time() - start > timeout:
                raise Refused(f"lock {path.name} is held for more than {timeout:g} s; remove it only if no merge is running")
            time.sleep(0.1)


def _load(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refused(f"{path.name} is missing or not valid JSON ({exc}); task T2 creates it") from exc
    if not isinstance(data, dict):
        raise Refused(f"{path.name} must hold one JSON object")
    return data


def merge(batch, prefixes, i18n_dir, replace=False):
    """Returns {"en": (added, kept, replaced), "mr": (...)}. Raises Refused before anything is written."""
    d = Path(i18n_dir)
    if not isinstance(batch, dict):
        raise Refused("the batch must be a JSON object with en and mr")
    en_b, mr_b = batch.get("en") or {}, batch.get("mr") or {}
    if not isinstance(en_b, dict) or not isinstance(mr_b, dict):
        raise Refused("en and mr must be objects of key -> text")
    if set(en_b) != set(mr_b):
        missing = sorted(set(en_b) ^ set(mr_b))[:5]
        raise Refused(f"en and mr must have the same keys; differing: {missing}")
    if not en_b:
        raise Refused("the batch holds no keys")
    groups = tuple(p.strip() + "." for p in prefixes if p.strip())
    if not groups:
        raise Refused("--prefix needs at least one group")
    if not all(re.fullmatch(r"[a-z0-9_]+", g[:-1]) for g in groups):
        raise Refused("--prefix groups must be lower-case names like step,story (no dots)")
    for lang, b in (("en", en_b), ("mr", mr_b)):
        for k, v in b.items():
            if not isinstance(k, str) or not KEY_RE.match(k):
                raise Refused(f"{lang}: bad key {k!r} (lower-case dotted name like group.name)")
            if not k.startswith(groups):
                raise Refused(f"{lang}: key {k!r} is outside your groups {', '.join(g[:-1] for g in groups)}")
            if not isinstance(v, str) or not v.strip():
                raise Refused(f"{lang}: key {k!r} has an empty or non-text value")
    fd = _lock(d / ".lock")
    try:
        result, outputs = {}, {}
        for lang, b in (("en", en_b), ("mr", mr_b)):
            cur = _load(d / f"{lang}.json")
            added = kept = replaced = 0
            for k, v in b.items():
                if k not in cur:
                    cur[k] = v
                    added += 1
                elif cur[k] == v:
                    kept += 1
                elif replace:
                    cur[k] = v
                    replaced += 1
                else:
                    raise Refused(f"{lang}: key {k!r} already exists with a different text; use --replace only for your own keys")
            result[lang] = (added, kept, replaced)
            outputs[lang] = json.dumps(dict(sorted(cur.items())), ensure_ascii=False, indent=2) + "\n"
        tmps = {}
        for lang, text in outputs.items():      # stage both files first, so a write error leaves both languages unchanged
            tmps[lang] = d / f"{lang}.json.tmp"
            with open(tmps[lang], "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        backup = {lang: (d / f"{lang}.json").read_bytes() for lang in outputs}
        done = []
        try:
            for lang in outputs:
                os.replace(tmps[lang], d / f"{lang}.json")
                done.append(lang)
        except OSError:
            for lang in done:                   # undo the first replace if the second failed
                (d / f"{lang}.json").write_bytes(backup[lang])
            raise
        return result
    finally:
        os.close(fd)
        try:
            (d / ".lock").unlink()
        except OSError:
            pass


def main(argv=None):
    ap = argparse.ArgumentParser(description="Merge UI strings into en.json and mr.json under a lock.")
    ap.add_argument("batch")
    ap.add_argument("--prefix", required=True, help="comma list of key groups this coder owns, e.g. step,story,next")
    ap.add_argument("--replace", action="store_true")
    ap.add_argument("--dir", default=str(HERE / "static" / "i18n"))
    a = ap.parse_args(argv)
    try:
        batch = json.loads(Path(a.batch).read_text(encoding="utf-8"))
        res = merge(batch, a.prefix.split(","), a.dir, a.replace)
    except (Refused, OSError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print("; ".join(f"{k}: added {v[0]}, kept {v[1]}, replaced {v[2]}" for k, v in res.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
