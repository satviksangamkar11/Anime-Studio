"""Code review by the free Dots model (replaces the Codex review, owner 2026-11-06).

  python dots_review.py --prompt "what to check" FILE [FILE ...] [--out report.md]

Model: dots-studio/dots-3-note-preview:free on OpenRouter (free, 512K context, reads text and images). Read-only: it only sends the files' text and
prints the answer. The key is read from the OpenRouter key file (never printed, never logged). Free models are rate limited: a 429 or 5xx is retried
with a growing wait. If the response reports a cost above 0 the script says so loudly (a :free model must cost 0)."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "dots-studio/dots-3-note-preview:free"
KEY_FILE = Path("D:/aai work/loop_p0/secrets/openrouter_paid_key.txt")   # the only OpenRouter key on this PC; a :free model costs 0 with it
MAX_FILE_CHARS = 120_000


def read_key(path: Path = KEY_FILE) -> str:
    key = path.read_text(encoding="utf-8").strip().splitlines()[0].strip() if path.is_file() else ""
    if not key:
        raise SystemExit(f"REFUSED: no OpenRouter key in {path}")
    return key


def build_messages(prompt: str, files: list[Path], raw: bool = False) -> list[dict]:
    if raw:   # coder mode: the caller's prompt is sent unchanged
        return [{"role": "user", "content": prompt}]
    parts = [prompt.strip(), "Think briefly (under 1500 words of reasoning), then give the answer. Report concrete bugs only, each as: severity (high/medium/low), file:line, why, and a one-line fix. Say 'no findings' if clean. Do not rewrite the files. Put the final list after a line that says exactly FINAL:"]
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        if len(text) > MAX_FILE_CHARS:
            text = text[:MAX_FILE_CHARS] + "\n[truncated]"
        numbered = "\n".join(f"{i}: {l}" for i, l in enumerate(text.splitlines(), 1))
        parts.append(f"=== FILE {f.name} ===\n{numbered}")
    return [{"role": "user", "content": "\n\n".join(parts)}]


def post(body: dict, key: str, timeout: int = 600) -> dict:
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "anime-studio-dots-review"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def review(prompt: str, files: list[Path], key: str | None = None, poster=post, sleep=time.sleep, tries: int = 5, raw: bool = False, max_tokens: int = 16000) -> dict:
    key = key or read_key()
    body = {"model": MODEL, "messages": build_messages(prompt, files, raw), "temperature": 0 if not raw else 0.2, "max_tokens": max_tokens}
    last = ""
    for attempt in range(1, tries + 1):
        try:
            out = poster(body, key)
            text = (out.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            if not text.strip():
                cut = (out.get("choices") or [{}])[0].get("finish_reason") == "length"
                last = "empty answer (reasoning used the whole token budget)" if cut else "empty answer"
                if cut:   # the model is a reasoning model: its thinking counts against max_tokens, so give it more room and ask again
                    body["max_tokens"] = min(body["max_tokens"] * 2, 64000)
                print(f"dots: attempt {attempt}: {last}; next max_tokens={body['max_tokens']}", file=sys.stderr, flush=True)
            else:
                cost = (out.get("usage") or {}).get("cost")
                cut = (out.get("choices") or [{}])[0].get("finish_reason") == "length"
                return {"text": text, "model": out.get("model", MODEL), "cost": cost, "paid": bool(cost), "truncated": cut}
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            print(f"dots: attempt {attempt}: {last}", file=sys.stderr, flush=True)
            if e.code not in (408, 429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError) as e:
            last = type(e).__name__
        if attempt < tries:
            sleep(30 * attempt)
    raise RuntimeError(f"dots review failed after retries: {last}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    missing = [str(f) for f in a.files if not f.is_file()]
    if missing:
        print("REFUSED: missing", missing)
        return 2
    res = review(a.prompt, a.files)
    if res["paid"]:
        print(f"WARNING: the response reports cost {res['cost']}: a :free model should cost 0. Stop and check the key.", file=sys.stderr)
    if res.get("truncated") or "FINAL:" not in res["text"]:
        print("WARNING: no FINAL: section (answer cut off or not given): treat this review as INCOMPLETE and run it again on fewer files.", file=sys.stderr)
    if a.out:
        a.out.write_text(res["text"], encoding="utf-8")
    print(res["text"])
    return 0 if not res["paid"] else 3


if __name__ == "__main__":
    sys.exit(main())
