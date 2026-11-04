"""The story writer (Gates 1-5): story text in, production pack out, in ONE model call with MASTER_PROMPT_v2.1.md as the brief.
Three paths, any model on each:
  --via claude      the Claude CLI on the owner's subscription (no API key, no tools, no MCP, empty folder); --model opus|sonnet|haiku|<id>
  --via nvidia      NVIDIA build API (free tier); keys from secrets/nvidia/nvidia_api_key*.txt; --model e.g. nvidia/nemotron-3-ultra-550b-a55b
  --via openrouter  OpenRouter; key from OPENROUTER_KEY_FILE (default loop_p0/secrets/openrouter_paid_key.txt); --model any id.
                    Only models whose price is 0 are sent, unless --allow-paid is given (owner rule: no paid calls).
Keys are read inside this process and never printed or written. Writes into out_dir:
  raw_response.json  the answer, saved before anything is parsed (a re-run with it present makes no call)
  PACK.md            the full production pack (raw material for every later step)
  shots.json         the machine-readable shot list, checked against h3_director.settings_for
Usage: python write_pack.py story.md out_dir --via claude|nvidia|openrouter [--model M] [--effort low|medium|high] [--allow-paid]"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from h3_director import settings_for

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]                                    # D:\aai work
BRIEF = HERE / "MASTER_PROMPT_v2.1.md"
SHOTS_BLOCK = re.compile(r"```json shots\s*\n(.*?)\s*```", re.DOTALL)
TIMEOUT_S = 3600
DEFAULT_MODEL = {"claude": "opus", "nvidia": "nvidia/nemotron-3-ultra-550b-a55b", "openrouter": None}
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_KEYS = Path(os.environ.get("NVIDIA_KEYS_DIR") or WORK / "secrets" / "nvidia")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_KEY = Path(os.environ.get("OPENROUTER_KEY_FILE") or WORK / "loop_p0" / "secrets" / "openrouter_paid_key.txt")


def build_prompt(story_text):
    return BRIEF.read_text(encoding="utf-8") + "\n\n## THE STORY / SOURCE\n\n" + story_text.strip() + "\n"


def envelope(text, finish, via, model):
    """Every path returns the same JSON shape, so parse() reads them all."""
    return json.dumps({"type": "result", "is_error": finish != "stop" or not text.strip(), "result": text, "via": via, "model": model,
                       "finish_reason": finish})


def call_claude(prompt, model, effort):
    with tempfile.TemporaryDirectory() as empty:
        mcp = Path(empty).parent / "empty_mcp_anime.json"
        mcp.write_text('{"mcpServers": {}}', encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY" and not k.startswith("OPENROUTER")}
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "64000"
        r = subprocess.run([shutil.which("claude") or "claude", "-p", "--model", model, "--effort", effort, "--output-format", "json",
                            "--tools", "", "--mcp-config", str(mcp), "--strict-mcp-config", "--no-session-persistence"],
                           input=prompt, capture_output=True, text=True, encoding="utf-8", cwd=empty, env=env, timeout=TIMEOUT_S)
    if r.returncode != 0:
        raise RuntimeError(f"claude exited {r.returncode}: {r.stderr[-800:]}")
    return r.stdout


def stream_chat(url, key, body, extra_headers=None):
    """One OpenAI-style streamed chat call. Returns (text, finish_reason); raises urllib.error.HTTPError."""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "text/event-stream", **(extra_headers or {})}
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST", headers=headers)
    parts, finish = [], None
    with urllib.request.urlopen(req, timeout=600) as resp:              # timeout per socket read
        for line in resp:
            line = line.decode("utf-8", "replace").strip()
            if not line.startswith("data:") or line == "data: [DONE]":
                continue
            choices = json.loads(line[5:]).get("choices") or [{}]
            parts.append((choices[0].get("delta") or {}).get("content") or "")
            finish = choices[0].get("finish_reason") or finish
    return "".join(parts), finish


def body_for(model, prompt, max_tokens=65536):
    return {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.6, "top_p": 0.95,
            "max_tokens": max_tokens, "stream": True}


def call_nvidia(prompt, model):
    """Every nvidia_api_key*.txt in turn: a refused or busy key (HTTP error) moves to the next one."""
    keys = [k for k in (p.read_text(encoding="utf-8").strip() for p in sorted(NVIDIA_KEYS.glob("nvidia_api_key*.txt"))) if k]
    if not keys:
        raise RuntimeError(f"no NVIDIA key files in {NVIDIA_KEYS}")
    errors = []
    for n, key in enumerate(keys, 1):
        try:
            return envelope(*stream_chat(NVIDIA_URL, key, body_for(model, prompt)), "nvidia", model)
        except urllib.error.HTTPError as exc:
            errors.append(f"key {n}: HTTP {exc.code}")
    raise RuntimeError("every NVIDIA key failed: " + "; ".join(errors))


def openrouter_is_free(model, catalog=None):
    """True when every price field of `model` in OpenRouter's public catalog is 0."""
    catalog = catalog or json.load(urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=60))["data"]
    entry = next((m for m in catalog if m["id"] == model), None)
    if entry is None:
        raise ValueError(f"{model} is not in OpenRouter's catalog")
    return all(float(v or 0) == 0 for v in entry.get("pricing", {}).values() if isinstance(v, (str, int, float)))


def call_openrouter(prompt, model, allow_paid=False):
    if not allow_paid and not openrouter_is_free(model):
        raise ValueError(f"{model} is a paid OpenRouter model: refused (no paid calls; pass --allow-paid only with the owner's OK)")
    key = OPENROUTER_KEY.read_text(encoding="utf-8").strip()
    text, finish = stream_chat(OPENROUTER_URL, key, body_for(model, prompt), {"X-Title": "anime-studio-writer"})
    return envelope(text, finish, "openrouter", model)


def parse(raw):
    """(pack_text, shots) from the saved answer; raises ValueError when the shot list is missing or invalid."""
    answer = json.loads(raw)
    if answer.get("is_error"):
        raise ValueError(f"the model call failed or was cut off ({answer.get('finish_reason')}): {str(answer.get('result'))[:500]}")
    text = answer["result"]
    blocks = SHOTS_BLOCK.findall(text)
    if len(blocks) != 1:
        raise ValueError(f"expected exactly one ```json shots block, found {len(blocks)}")
    shots = json.loads(blocks[0])
    if not isinstance(shots, list) or not all(isinstance(s, dict) for s in shots):
        raise ValueError("the shot list must be a JSON list of objects")
    ids = [s["id"] for s in shots]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate shot ids")
    for shot in shots:
        settings_for(shot)                      # raises on a shot the H3 director cannot run
    return text, shots


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("story"); ap.add_argument("out_dir")
    ap.add_argument("--via", default="claude", choices=("claude", "nvidia", "openrouter"))
    ap.add_argument("--model"); ap.add_argument("--effort", default="medium", choices=("low", "medium", "high"))
    ap.add_argument("--allow-paid", action="store_true")
    a = ap.parse_args(argv)
    model = a.model or DEFAULT_MODEL[a.via]
    if not model:
        ap.error("--model is required with --via openrouter")
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    raw_path = out / "raw_response.json"
    if not raw_path.exists():
        prompt = build_prompt(Path(a.story).read_text(encoding="utf-8"))
        raw = (call_claude(prompt, model, a.effort) if a.via == "claude" else call_nvidia(prompt, model) if a.via == "nvidia"
               else call_openrouter(prompt, model, a.allow_paid))
        raw_path.write_text(raw, encoding="utf-8")
    text, shots = parse(raw_path.read_text(encoding="utf-8"))
    (out / "PACK.md").write_text(text, encoding="utf-8")
    (out / "shots.json").write_text(json.dumps(shots, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(shots)} shots -> {out / 'shots.json'}")


if __name__ == "__main__":
    sys.exit(main())
