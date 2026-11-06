"""The story writer (Gates 1-5): story text in, production pack out. Three paths, any model on each:
  --via claude      the Claude CLI on the owner's subscription (no API key, no tools, no MCP, empty folder); --model opus|sonnet|haiku|<id>
  --via nvidia      NVIDIA build API (free tier); keys from secrets/nvidia/nvidia_api_key*.txt; --model e.g. nvidia/nemotron-3-ultra-550b-a55b
  --via openrouter  OpenRouter; key from OPENROUTER_KEY_FILE (default loop_p0/secrets/openrouter_paid_key.txt); --model any id.
                    Only models whose price is 0 are sent, unless --allow-paid is given (owner rule: no paid calls).
  --writer NAME     a shortcut that sets --via and --model (owner order 2026-11-06); it is the DEFAULT when no path is given:
                    super-vl (default)  openrouter nvidia/nemotron-3.5-super-vl:free
                    ultra               openrouter nvidia/nemotron-3-ultra-550b-a55b:free
                    opus                claude, --model opus, effort medium
Every run is recorded in stories/<slug>/RUNS.jsonl by director/run_registry.py (when the story is stories/<slug>/SOURCE.md);
a registry error never stops the writer. A NEW run needs a new pack folder: a folder with PACK.md is never written again.
Single-call mode (default): ONE call with MASTER_PROMPT_v2.1.md as the brief. Writes into out_dir:
  raw_response.json  the answer, saved before anything is parsed (a re-run with it present makes no call)
  PACK.md            the full production pack (raw material for every later step)
  shots.json         the machine-readable shot list, checked against h3_director.settings_for
Staged mode (--staged): one call per gate, in order: 1 (markdown), 2 (style bible: one ```json bible block), 3e<N> per episode
  listed by stage 1 (one ```json shots block), 5 (markdown). Each stage gets the brief, the story and the saved text of the earlier
  stages. Each answer is saved as stage_<name>_raw.json before parsing, and an existing file is not sent again (resume).
  Writes PACK.md (all stage texts in order), bible.json and shots.json (all episodes merged).
  --stage-via 2=nvidia,3=claude and --stage-model 3=opus route per stage ("3" covers 3e1, 3e2 ...; "3e2" overrides it).
Usage: python write_pack.py story.md out_dir [--writer super-vl|ultra|opus] [--via claude|nvidia|openrouter] [--model M] [--effort low|medium|high] [--allow-paid]
       python write_pack.py story.md out_dir --staged [--writer ...] [--via ...] [--model M] [--stage-via 2=nvidia,3=claude] [--stage-model 3=opus]
                                                       [--prompt-version v2.2|v2.3] [--style-pack ID]
  --prompt-version v2.3 (staged only) uses MASTER_PROMPT_v2.3.md and appends the STYLE PACK RULES of the pack named by --style-pack,
  else by the story.json next to the story. The default stays v2.2."""
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
import run_registry

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]                                    # D:\aai work
BRIEF = HERE / "MASTER_PROMPT_v2.1.md"
BRIEF_V22 = HERE / "MASTER_PROMPT_v2.2.md"                # staged mode reads this when it exists
BRIEF_V23 = HERE / "MASTER_PROMPT_v2.3.md"                # --prompt-version v2.3
STYLES_DIR = HERE.parent / "styles"                       # style pack JSON files, read as plain JSON
PACK_ID = re.compile(r"[A-Za-z0-9_-]+")
SHOTS_BLOCK = re.compile(r"```json shots\s*\n(.*?)\s*```", re.DOTALL)
BIBLE_BLOCK = re.compile(r"```json bible\s*\n(.*?)\s*```", re.DOTALL)
EPISODES_BLOCK = re.compile(r"```json episodes\s*\n(.*?)\s*```", re.DOTALL)
UNTAGGED_JSON = re.compile(r"```json[ \t]*\n(.*?)\s*```", re.DOTALL)   # a ```json block with no tag word
EPISODE_LINE = re.compile(r"^[ \t>#*_-]*(?:Episode|Ep\.?)\s*(\d+)\b", re.IGNORECASE | re.MULTILINE)
# a markdown table row whose first cell is just the number, "| **3** | title | ..." (seen in a real stage 1 answer, 2026-11-06); used only when no "Episode N" line exists
EPISODE_ROW = re.compile(r"^\|[ \t*_]*(\d{1,2})[ \t*_]*\|", re.MULTILINE)
VIAS = ("claude", "nvidia", "openrouter")
TIMEOUT_S = 3600
DEFAULT_MODEL = {"claude": "opus", "nvidia": "nvidia/nemotron-3-ultra-550b-a55b", "openrouter": None}
WRITERS = {   # --writer NAME: the path and the model (the UI's server.py WRITER_ROUTE mirrors the two OpenRouter rows; a test checks it)
    "super-vl": {"via": "openrouter", "model": "nvidia/nemotron-3.5-super-vl:free", "effort": None},
    "ultra": {"via": "openrouter", "model": "nvidia/nemotron-3-ultra-550b-a55b:free", "effort": None},
    "opus": {"via": "claude", "model": "opus", "effort": "medium"},
}
DEFAULT_WRITER = "super-vl"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_KEYS = Path(os.environ.get("NVIDIA_KEYS_DIR") or WORK / "secrets" / "nvidia")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_KEY = Path(os.environ.get("OPENROUTER_KEY_FILE") or WORK / "loop_p0" / "secrets" / "openrouter_paid_key.txt")
STAGE_INSTRUCTION = {
    "1": "Stage 1 only: write Gate 1 (story autopsy, scene list, episode split). Markdown only. Name each episode on its own line "
         "as 'Episode N: title'. Do not write the later gates.",
    "2": "Stage 2 only: write Gate 2 (style bible, Flow sheet prompts, acting notes). End with exactly one ```json bible block "
         "holding the style bible as one JSON object.",
    "5": "Stage 5 only: write Gate 5 (sound, captions, QA). Markdown only.",
}


def build_prompt(story_text):
    return BRIEF.read_text(encoding="utf-8") + "\n\n## THE STORY / SOURCE\n\n" + story_text.strip() + "\n"


def staged_brief(version="v2.2"):
    """Path of the staged brief. v2.2: today's file (BRIEF_V22, or BRIEF when that is missing). v2.3: MASTER_PROMPT_v2.3.md.
    Returns a Path for both (read it with .read_text), as before."""
    if version == "v2.2":
        return BRIEF_V22 if BRIEF_V22.exists() else BRIEF
    if version == "v2.3":
        if not BRIEF_V23.exists():
            raise ValueError(f"{BRIEF_V23.name} is missing")
        return BRIEF_V23
    raise ValueError(f"unknown prompt version {version!r}: use v2.2 or v2.3")


def _strings(value):
    return [x for x in value if isinstance(x, str)] if isinstance(value, list) else []


def style_rules(pack_id, styles_dir=None):
    """The '## STYLE PACK RULES' section for a pack: guardrails, forbidden words, act names and phase ids.
    "" when the pack id is empty or unsafe, the file is missing, or it is not a readable JSON object. Never raises."""
    if not isinstance(pack_id, str) or not PACK_ID.fullmatch(pack_id):
        return ""
    try:
        pack = json.loads((Path(styles_dir or STYLES_DIR) / f"{pack_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(pack, dict):
        return ""
    lines = ["## STYLE PACK RULES", "", f"Style pack: {pack_id}", ""]
    guardrails = _strings(pack.get("guardrails"))
    if guardrails:
        lines += ["Guardrails (the writer must not produce what these forbid):"] + [f"- {g}" for g in guardrails] + [""]
    words = _strings(pack.get("prompt_forbidden_words"))
    if words:
        lines += [f"Never write these words or phrases in any prompt text: {', '.join(words)}", ""]
    acts = list(pack["acts"]) if isinstance(pack.get("acts"), dict) else []
    cs = pack.get("colour_script")
    phases = [ph["id"] for ph in cs.get("phases") or [] if isinstance(ph, dict) and isinstance(ph.get("id"), str)] \
        if isinstance(cs, dict) and isinstance(cs.get("phases"), list) else []
    if acts:
        lines += [f"Act names for look.act: {', '.join(acts)}", ""]
    if phases:
        lines += [f"Phase ids for look.phase: {', '.join(phases)}", ""]
    return "\n".join(lines).rstrip() + "\n"


def story_pack_id(story_path):
    """style_pack from the story.json in the story's folder, or None."""
    try:
        data = json.loads((Path(story_path).parent / "story.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    pack = data.get("style_pack") if isinstance(data, dict) else None
    return pack if isinstance(pack, str) else None


def build_stage_prompt(brief, story_text, earlier, instruction):
    saved = "\n\n".join(f"## SAVED OUTPUT OF STAGE {name}\n\n{text.strip()}" for name, text in earlier) or "(none yet)"
    return (brief + "\n\n## THE STORY / SOURCE\n\n" + story_text.strip() + "\n\n## EARLIER STAGES (saved output)\n\n" + saved
            + "\n\n## THIS STAGE\n\n" + instruction + "\n")


def stage_instruction(name):
    if name.startswith("3e"):
        return (f"Stage {name} only: write Gates 3+4 for Episode {name[2:]} only (rich shots, Flow Frame_A prompt and Frame_B edit "
                f"per shot). End with exactly one ```json shots block: a JSON list of that episode's rich shot objects.")
    return STAGE_INSTRUCTION[name]


def gate_of(name):
    return "3" if name.startswith("3e") else name


def stage_setting(table, name, default):
    return table.get(name, table.get(gate_of(name), default))


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


def body_for(model, prompt, max_tokens=65536, content=None):
    """content: the user message as a plain string (default: prompt) or a list of OpenAI-style parts (images)."""
    return {"model": model, "messages": [{"role": "user", "content": prompt if content is None else content}], "temperature": 0.6,
            "top_p": 0.95, "max_tokens": max_tokens, "stream": True}


def call_nvidia(prompt, model, content=None):
    """Every nvidia_api_key*.txt in turn: a refused or busy key (HTTP error) moves to the next one."""
    keys = [k for k in (p.read_text(encoding="utf-8").strip() for p in sorted(NVIDIA_KEYS.glob("nvidia_api_key*.txt"))) if k]
    if not keys:
        raise RuntimeError(f"no NVIDIA key files in {NVIDIA_KEYS}")
    errors = []
    for n, key in enumerate(keys, 1):
        try:
            return envelope(*stream_chat(NVIDIA_URL, key, body_for(model, prompt, content=content)), "nvidia", model)
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


def call_openrouter(prompt, model, allow_paid=False, content=None):
    """Streamed (SSE) call, max_tokens 65536: the same body as NVIDIA. A cut-off answer (finish_reason other than stop) is
    an error in the envelope; an HTTP refusal (e.g. a max_tokens the model does not allow) is raised with OpenRouter's reason."""
    if not allow_paid and not openrouter_is_free(model):
        raise ValueError(f"{model} is a paid OpenRouter model: refused (no paid calls; pass --allow-paid only with the owner's OK)")
    key = OPENROUTER_KEY.read_text(encoding="utf-8").strip()
    try:
        text, finish = stream_chat(OPENROUTER_URL, key, body_for(model, prompt, content=content), {"X-Title": "anime-studio-writer"})
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read(400).decode("utf-8", "replace")
        except Exception:
            detail = ""
        raise RuntimeError(f"OpenRouter refused the call for {model}: HTTP {exc.code} {run_registry.redact(detail)}") from None
    return envelope(text, finish, "openrouter", model)


def resolve_route(writer=None, via=None, model=None, effort=None):
    """(writer, via, model, effort) from the options. No option at all = the default writer. --writer excludes --via and --model."""
    if writer is None and via is None and model is None:
        writer = DEFAULT_WRITER
    if writer is not None:
        if via is not None or model is not None:
            raise ValueError("--writer sets the path and the model: do not pass --via or --model with it")
        if writer not in WRITERS:
            raise ValueError(f"unknown writer {writer!r}: use one of {', '.join(WRITERS)}")
        route = WRITERS[writer]
        return writer, route["via"], route["model"], effort or route["effort"] or "medium"
    if via is None:
        raise ValueError("--model needs --via (or use --writer)")
    check_via(via)
    model = model or DEFAULT_MODEL[via]
    if not model:
        raise ValueError("--model is required with --via openrouter")
    return None, via, model, effort or "medium"


def refuse_finished(out):
    """A new model call never writes into a finished pack folder (PACK.md exists): the caller needs a new folder."""
    if (out / "PACK.md").exists():
        raise ValueError(f"{out.name} is already finished (PACK.md exists): a new call needs a new pack folder")


def call_path(prompt, via, model, effort, allow_paid):
    if via == "claude":
        return call_claude(prompt, model, effort)
    if via == "nvidia":
        return call_nvidia(prompt, model)
    return call_openrouter(prompt, model, allow_paid)


def json_lines(block):
    """One JSON value per line (Nemotron 3 Ultra wrote one per line on 2026-11-04)."""
    return [json.loads(line.strip().rstrip(",")) for line in block.splitlines() if line.strip()]


def shots_from(block):
    try:
        shots = json.loads(block)
    except json.JSONDecodeError:
        shots = []
        for value in json_lines(block):
            shots.extend(value if isinstance(value, list) else [value])
    if not isinstance(shots, list) or not all(isinstance(s, dict) for s in shots):
        raise ValueError("the shot list must be a JSON list of objects")
    return shots


def bible_from(block):
    """The style bible: one JSON object, or one object per line (merged)."""
    try:
        bible = json.loads(block)
    except json.JSONDecodeError:
        bible = {}
        for value in json_lines(block):
            if not isinstance(value, dict):
                raise ValueError("each bible line must be a JSON object")
            bible.update(value)
    if not isinstance(bible, dict):
        raise ValueError("the style bible must be one JSON object")
    return bible


def answer_text(raw):
    """The answer's text; raises when the model call failed or was cut off."""
    answer = json.loads(raw)
    if answer.get("is_error"):
        raise ValueError(f"the model call failed or was cut off ({answer.get('finish_reason')}): {str(answer.get('result'))[:500]}")
    return answer["result"]


def untagged_last(text, want):
    """The last untagged ```json block whose JSON value passes want(), or None."""
    for block in reversed(UNTAGGED_JSON.findall(text)):
        try:
            value = json.loads(block)
        except json.JSONDecodeError:
            continue
        if want(value):
            return block
    return None


def parse(raw):
    """(pack_text, shots) from the saved answer; raises ValueError when the shot list is missing or invalid."""
    text = answer_text(raw)
    blocks = SHOTS_BLOCK.findall(text)
    if not blocks:                              # no tagged block: accept an untagged list of objects
        fallback = untagged_last(text, lambda v: isinstance(v, list) and all(isinstance(s, dict) for s in v))
        blocks = [fallback] if fallback else []
    if len(blocks) != 1:
        raise ValueError(f"expected exactly one ```json shots block, found {len(blocks)}")
    shots = shots_from(blocks[0])
    ids = [s["id"] for s in shots]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate shot ids")
    for shot in shots:
        settings_for(shot)                      # raises on a shot the H3 director cannot run
    return text, shots


def parse_bible(raw):
    """(text, bible) from a stage 2 answer: exactly one ```json bible block, and the answer ends with it."""
    text = answer_text(raw)
    blocks = BIBLE_BLOCK.findall(text)
    if not blocks:                              # no tagged block: accept an untagged JSON object
        fallback = untagged_last(text, lambda v: isinstance(v, dict))
        blocks = [fallback] if fallback else []
    if len(blocks) != 1:
        raise ValueError(f"expected exactly one ```json bible block, found {len(blocks)}")
    if not text.rstrip().endswith("```"):
        raise ValueError("stage 2 must end with the ```json bible block")
    return text, bible_from(blocks[0])


def episodes_from(text):
    """Episode numbers named by stage 1: a ```json episodes block, else lines 'Episode N' / 'Ep N'."""
    block = EPISODES_BLOCK.search(text)
    found = [v if isinstance(v, int) else v["episode"] for v in json.loads(block.group(1))] if block else \
        [int(n) for n in EPISODE_LINE.findall(text)] or [int(n) for n in EPISODE_ROW.findall(text)]
    episodes = sorted(set(found))
    if not episodes:
        raise ValueError("stage 1 names no episodes (write lines 'Episode N: title' or a ```json episodes block)")
    return episodes


def parse_stage_map(spec, check):
    """'2=nvidia,3e2=claude' -> {'2': 'nvidia', '3e2': 'claude'}"""
    table = {}
    for item in (s.strip() for s in spec.split(",") if s.strip()):
        key, sep, value = item.partition("=")
        if not sep or not value.strip() or not re.fullmatch(r"[1235]|3e\d+", key.strip()):
            raise ValueError(f"bad stage option {item!r}: use STAGE=VALUE, e.g. 2=nvidia or 3e2=opus")
        table[key.strip()] = check(value.strip())
    return table


def check_via(value):
    if value not in VIAS:
        raise ValueError(f"unknown path {value!r}")
    return value


SHOT_MENTION = re.compile(r"\bSHOT-\d{2,3}[A-Z]?\b")


def merge_episodes(per_episode):
    """One shot list in film order. When ids repeat across episodes (each episode numbers from SHOT-01), every shot gets
    SHOT-001, SHOT-002 ... and its model id as source_id; cut_in / cut_out / keyframe paths follow within their episode."""
    flat = [s for ep in per_episode for s in ep]
    if len({s["id"] for s in flat}) == len(flat):
        return flat
    if len(flat) > 999:
        raise ValueError(f"{len(flat)} shots: the SHOT-NNN id rule allows 999")
    merged, number = [], 0
    for ep in per_episode:
        new_ids = {}
        for s in ep:
            number += 1
            new_ids[s["id"]] = f"SHOT-{number:03d}"
        for s in ep:
            fixed = dict(s, id=new_ids[s["id"]], source_id=s["id"])
            for key in ("cut_in", "cut_out", "start", "end"):
                if isinstance(fixed.get(key), str):
                    fixed[key] = SHOT_MENTION.sub(lambda m: new_ids.get(m.group(0), m.group(0)), fixed[key])
            if isinstance(fixed.get("keyframes"), dict):
                fixed["keyframes"] = {k: SHOT_MENTION.sub(lambda m: new_ids.get(m.group(0), m.group(0)), v) if isinstance(v, str)
                                      else v for k, v in fixed["keyframes"].items()}
            merged.append(fixed)
    return merged


def run_staged(story_text, out, via, model, effort, allow_paid, stage_via, stage_model, rec=None, prompt_version="v2.2", style_rules=""):
    """Stages 1, 2, 3e<N> per episode, 5. Writes PACK.md, bible.json, shots.json; returns the merged shots.
    rec: the run registry Recorder of this run (default: records nothing). Every stage and the whole run are steps in it.
    prompt_version: which staged brief to send; style_rules: text appended to that brief (empty = nothing appended)."""
    rec = rec or run_registry.Recorder(None, "none")
    brief = staged_brief(prompt_version).read_text(encoding="utf-8")
    if style_rules:
        brief += "\n\n" + style_rules
    done = []                                                   # (stage name, saved text), in order
    out.mkdir(parents=True, exist_ok=True)

    def raw_for(name):
        raw_path = out / f"stage_{name}_raw.json"
        if raw_path.exists():
            info = run_registry.envelope_file(raw_path)
            with rec.step("analysis_stage", name, via=info.get("via"), model=info.get("model"), files=[f"{out.name}/{raw_path.name}"],
                          note="saved answer reused: no model call"):
                pass
        else:
            v = stage_setting(stage_via, name, via)
            m = stage_setting(stage_model, name, model if v == via else None) or DEFAULT_MODEL[v]
            if not m:
                raise ValueError(f"stage {name}: --model is required with --via openrouter")
            refuse_finished(out)
            prompt = build_stage_prompt(brief, story_text, done, stage_instruction(name))
            # ponytail: stages and episodes run one after another; parallel episodes when a run gets slow
            with rec.step("analysis_stage", name, via=v, model=m, effort=effort, files=[f"{out.name}/{raw_path.name}"]) as st:
                text = call_path(prompt, v, m, effort, allow_paid)
                raw_path.write_text(text, encoding="utf-8")
                st.chars = run_registry.envelope_info(text).get("chars")
        print(f"stage {name}: {raw_path}")
        return raw_path.read_text(encoding="utf-8")

    with rec.step("analysis_done", None, via=via, model=model, effort=effort) as run:
        text1 = answer_text(raw_for("1"))
        done.append(("1", text1))
        text2, bible = parse_bible(raw_for("2"))
        done.append(("2", text2))
        per_episode, episodes = [], episodes_from(text1)
        for ep in episodes:
            text, ep_shots = parse(raw_for(f"3e{ep}"))
            done.append((f"3e{ep}", text))
            per_episode.append(ep_shots)
        done.append(("5", answer_text(raw_for("5"))))
        shots = merge_episodes(per_episode)
        (out / "PACK.md").write_text("\n\n".join(text for _, text in done), encoding="utf-8")
        (out / "bible.json").write_text(json.dumps(bible, indent=1, ensure_ascii=False), encoding="utf-8")
        (out / "shots.json").write_text(json.dumps(shots, indent=1, ensure_ascii=False), encoding="utf-8")
        run.files = [f"{out.name}/{n}" for n in ("PACK.md", "bible.json", "shots.json")]
        run.note = f"{len(episodes)} episodes, {len(shots)} shots"
    print(f"{len(episodes)} episodes, {len(shots)} shots -> {out}")
    return shots


def run_single(story_text, out, via, model, effort, allow_paid, rec=None):
    """Single call: raw_response.json, PACK.md, shots.json. A saved raw_response.json is parsed again without a call."""
    rec = rec or run_registry.Recorder(None, "none")
    out.mkdir(parents=True, exist_ok=True)
    raw_path = out / "raw_response.json"
    with rec.step("analysis_done", None, via=via, model=model, effort=effort) as run:
        if raw_path.exists():
            info = run_registry.envelope_file(raw_path)
            with rec.step("analysis_stage", "single", via=info.get("via"), model=info.get("model"),
                          files=[f"{out.name}/raw_response.json"], note="saved answer reused: no model call"):
                pass
        else:
            refuse_finished(out)
            prompt = build_prompt(story_text)
            with rec.step("analysis_stage", "single", via=via, model=model, effort=effort,
                          files=[f"{out.name}/raw_response.json"]) as st:
                text = call_path(prompt, via, model, effort, allow_paid)
                raw_path.write_text(text, encoding="utf-8")
                st.chars = run_registry.envelope_info(text).get("chars")
        text, shots = parse(raw_path.read_text(encoding="utf-8"))
        (out / "PACK.md").write_text(text, encoding="utf-8")
        (out / "shots.json").write_text(json.dumps(shots, indent=1, ensure_ascii=False), encoding="utf-8")
        run.files = [f"{out.name}/{n}" for n in ("PACK.md", "shots.json")]
        run.note = f"{len(shots)} shots"
    print(f"{len(shots)} shots -> {out / 'shots.json'}")
    return shots


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("story"); ap.add_argument("out_dir")
    ap.add_argument("--writer", choices=tuple(WRITERS), default=None,
                    help="shortcut that sets --via and --model: super-vl (default), ultra (OpenRouter, free) or opus (Claude, effort medium)")
    ap.add_argument("--via", default=None, choices=VIAS)
    ap.add_argument("--model"); ap.add_argument("--effort", default=None, choices=("low", "medium", "high"))
    ap.add_argument("--allow-paid", action="store_true")
    ap.add_argument("--staged", action="store_true", help="one call per gate: 1, 2, 3e<N> per episode, 5")
    ap.add_argument("--stage-via", default="", help="staged only: per-stage path, e.g. 2=nvidia,3=claude")
    ap.add_argument("--stage-model", default="", help="staged only: per-stage model, e.g. 3=opus")
    ap.add_argument("--prompt-version", default=None, choices=("v2.2", "v2.3"),
                    help="staged only: the brief. v2.2 (default) or v2.3 (look and hook rules, plus the style pack rules)")
    ap.add_argument("--style-pack", default=None,
                    help="staged + v2.3 only: style pack id (styles/<id>.json). Default: style_pack in the story.json next to the story")
    a = ap.parse_args(argv)
    if not a.staged and (a.stage_via or a.stage_model or a.prompt_version or a.style_pack):
        ap.error("--stage-via, --stage-model, --prompt-version and --style-pack need --staged")
    try:
        writer, via, model, effort = resolve_route(a.writer, a.via, a.model, a.effort)
        stage_via = parse_stage_map(a.stage_via, check_via) if a.staged else {}
        stage_model = parse_stage_map(a.stage_model, str) if a.staged else {}
    except ValueError as exc:
        ap.error(str(exc))
    prompt_version = a.prompt_version or "v2.2"
    style = ""
    if a.staged and prompt_version == "v2.3":
        pack_id = a.style_pack or story_pack_id(Path(a.story))
        style = style_rules(pack_id) if pack_id else ""
    out = Path(a.out_dir)
    rec = run_registry.Recorder(run_registry.story_folder(Path(a.story)), run_registry.writer_tag(writer, via, model),
                                pack=out.name, via=via, model=model, effort=effort)
    if a.staged:
        run_staged(Path(a.story).read_text(encoding="utf-8"), out, via, model, effort, a.allow_paid, stage_via, stage_model, rec,
                   prompt_version=prompt_version, style_rules=style)
        return
    run_single(Path(a.story).read_text(encoding="utf-8"), out, via, model, effort, a.allow_paid, rec)


if __name__ == "__main__":
    sys.exit(main())
