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
Staged mode (--staged): one call per gate, in order: 1 (story spine, six gate checks, reel plan: one ```json story block),
  2 (ONE canonical art bible: one ```json bible block), 3e<N> per episode listed by stage 1 (the 6-column shot table: one ```json shots
  block), 5 (captions and narration language: optional ```json captions block). The V4 prompts are in director/writer_prompts.py.
  Each stage gets the brief, the story, the saved text of the earlier stages and the V4 rules. Each answer is saved as
  stage_<name>_raw.json before it is read, and an existing file is not sent again (resume).
  Every stage is checked by director/pack_validator.py validate_stage (when that module exists; when it does not, a warning is
  printed and the stage is not checked). A failed check gets ONE repair retry (MAX_REPAIR_RETRIES) with the error list appended to
  the prompt. A second failure saves stage_<name>_validation.json next to the raw answer and stops the run with a clear message.
  Writes PACK.md (all stage texts in order), bible.json (the canonical layout), shots.json (all episodes merged, V4 rows with the old
  fields derived for legacy readers) and story_plan.json (the stage 1 block).
  --stage-via 2=nvidia,3=claude and --stage-model 3=opus route per stage ("3" covers 3e1, 3e2 ...; "3e2" overrides it).
Usage: python write_pack.py story.md out_dir [--writer super-vl|ultra|opus] [--via claude|nvidia|openrouter] [--model M] [--effort low|medium|high] [--allow-paid]
       python write_pack.py story.md out_dir --staged [--writer ...] [--via ...] [--model M] [--stage-via 2=nvidia,3=claude] [--stage-model 3=opus]
                                                    [--out-lang en|hi|mr|en,hi|all]   (default hi; staged only)
                                                       [--prompt-version v2.2|v2.3] [--style-pack ID]
  --prompt-version v2.3 (staged only) uses MASTER_PROMPT_v2.3.md and appends the STYLE PACK RULES of the pack named by --style-pack,
  else by the story.json next to the story. The staged default is v2.3 (owner decision Q5, 2026-11-07); v2.2 stays available."""
import argparse
import importlib
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
import retry_policy
import run_registry
import writer_prompts as wp

spec = wp.spec                                            # h3/shot_table_spec.py: the V4 numbers (never copied here)
HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]                                    # D:\aai work
BRIEF = HERE / "MASTER_PROMPT_v2.1.md"
BRIEF_V22 = HERE / "MASTER_PROMPT_v2.2.md"                # staged mode reads this when it exists
BRIEF_V23 = HERE / "MASTER_PROMPT_v2.3.md"                # --prompt-version v2.3
STYLES_DIR = HERE.parent / "styles"                       # style pack JSON files, read as plain JSON
PACK_ID = re.compile(r"[A-Za-z0-9_-]+")
SHOTS_BLOCK = re.compile(r"```json shots\s*\n(.*?)\s*```", re.DOTALL)
BIBLE_BLOCK = re.compile(r"```json bible\s*\n(.*?)\s*```", re.DOTALL)
STORY_BLOCK = re.compile(r"```json story\s*\n(.*?)\s*```", re.DOTALL)
CAPTIONS_BLOCK = re.compile(r"```json captions\s*\n(.*?)\s*```", re.DOTALL)
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
def build_prompt(story_text):
    return BRIEF.read_text(encoding="utf-8") + "\n\n## THE STORY / SOURCE\n\n" + story_text.strip() + "\n"


DEFAULT_PROMPT_VERSION = "v2.3"


def staged_brief(version=DEFAULT_PROMPT_VERSION):
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


def load_style_pack(pack_id, styles_dir=None):
    """The pack as a dict, or None (empty or unsafe id, missing or unreadable file)."""
    if not isinstance(pack_id, str) or not PACK_ID.fullmatch(pack_id):
        return None
    try:
        pack = json.loads((Path(styles_dir or STYLES_DIR) / f"{pack_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return pack if isinstance(pack, dict) else None


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
    lines += _look_rules(pack)
    return "\n".join(lines).rstrip() + "\n"


def _look_rules(pack):
    """The pack's look as writer rules (owner 2026-11-08: the writer must follow the chosen style): grade ranges per act, frame law,
    and every palette with its colours and roles. The style_lock colour line and the locked swatches come from here."""
    out = []
    acts = pack.get("acts") if isinstance(pack.get("acts"), dict) else {}
    act_lines = []
    for name, a in acts.items():
        if isinstance(a, dict) and isinstance(a.get("luma_mean"), list) and isinstance(a.get("sat_mean"), list):
            act_lines.append(f"- {name}: brightness {a['luma_mean'][0]}-{a['luma_mean'][1]}, saturation {a['sat_mean'][0]}-{a['sat_mean'][1]}")
    if act_lines:
        out += ["Look per act (mean brightness and saturation, 0-1; write light and colour to land inside these):"] + act_lines + [""]
    fl = pack.get("frame_law") if isinstance(pack.get("frame_law"), dict) else {}
    law = []
    if fl.get("max_neon_hues_per_shot") is not None:
        law.append(f"at most {fl['max_neon_hues_per_shot']} neon colour per shot")
    if isinstance(fl.get("area_split"), list) and len(fl["area_split"]) == 3:
        law.append("colour area split {}/{}/{} (dominant/secondary/accent)".format(*fl["area_split"]))
    if fl.get("min_dL_focal_vs_bg") is not None:
        law.append(f"the hero must stand out from the background by lightness (dL* at least {fl['min_dL_focal_vs_bg']})")
    if fl.get("pure_white_area_cap_frac") is not None:
        law.append(f"pure white covers at most {round(fl['pure_white_area_cap_frac'] * 100)} percent of the frame")
    if law:
        out += ["Frame law: " + "; ".join(law) + ".", ""]
    pals = pack.get("palettes") if isinstance(pack.get("palettes"), dict) else {}
    if pals:
        out += ["Palettes. The style_lock colour line, every CHAR sheet's locked swatches and every shot's colours use these. A palette",
                "belongs to the characters listed AND to every form or avatar of them (for example any form of Kali, Durga or Chandika",
                "uses the Kali palette). A character with no palette takes the colours of the palette nearest to its role, never a",
                "generic earth-tone set. Neon colours are accents only and follow the frame law."]
        for pid, p in pals.items():
            if not isinstance(p, dict):
                continue
            cols = p.get("colors") if isinstance(p.get("colors"), dict) else {}
            col = "; ".join(f"{n} {c.get('hex')} ({c.get('role')}{', neon' if c.get('neon') else ''})"
                            for n, c in cols.items() if isinstance(c, dict))
            who = ", ".join(_strings(p.get("characters")))
            out.append(f"- {pid} [{who}]: {col}")
            for law_ in p.get("special_laws") or []:
                if isinstance(law_, dict) and law_.get("color") and law_.get("only_roles"):
                    out.append(f"  rule: {law_['color']} only for {', '.join(_strings(law_['only_roles']))}")
            fh = p.get("focal_hints")
            if isinstance(fh, dict) and fh.get("hero") and fh.get("bg"):
                out.append(f"  hero colour {fh['hero']} against background {fh['bg']}")
        out.append("")
    return out


STYLE_PACK = None   # the chosen style pack (dict), set in main; stage 2 is checked against it (STYLE-01, STYLE-02)
HEX = re.compile(r"#[0-9A-Fa-f]{6}(?![0-9A-Fa-f])")


def style_pack_errors(bible, pack):
    """Owner 2026-11-08: the plan must follow the chosen style. STYLE-01: a character covered by a palette (by id, or a form of it:
    CHAR-ADYA-KALI is a form of CHAR-KALI) takes at least 3 locked swatches from that palette. STYLE-02: the style lock uses at
    least 2 of the pack's colours. Empty when the pack has no palettes."""
    pals = pack.get("palettes") if isinstance(pack, dict) and isinstance(pack.get("palettes"), dict) else {}
    if not pals or not isinstance(bible, dict):
        return []
    by_char, every = {}, set()
    for pid, p in pals.items():
        hexes = {c.get("hex", "").upper() for c in (p.get("colors") or {}).values() if isinstance(c, dict)}
        every |= hexes
        for cid in _strings(p.get("characters")):
            by_char[cid.split("-", 1)[-1]] = (pid, hexes)
    errs = []
    chars = bible.get("characters") if isinstance(bible.get("characters"), dict) else {}
    for cid, c in chars.items():
        words = set(str(cid).upper().split("-")[1:])
        hit = next((v for k, v in by_char.items() if k in words), None)
        if hit is None or not isinstance(c, dict):
            continue
        used = {h.upper() for h in HEX.findall(str(c.get("sheet_prompt", "")))}
        if len(used & hit[1]) < 3:
            errs.append(f"STYLE-01 at characters.{cid}: locked swatches must take at least 3 colours from the {hit[0]} palette "
                        f"({', '.join(sorted(hit[1]))}); found {len(used & hit[1])}")
    lock = json.dumps(bible.get("style_lock", ""), ensure_ascii=False)
    names = {n.lower() for p in pals.values() for n in (p.get("colors") or {})}
    found = {h.upper() for h in HEX.findall(lock)} & every
    found_names = {n for n in names if n in lock.lower()}
    if len(found) + len(found_names) < 2:
        errs.append("STYLE-02 at style_lock: the colour line must use the style pack's palette colours (at least 2 hex values or "
                    "colour names from STYLE PACK RULES), not a generic palette")
    return errs


def story_pack_id(story_path):
    """style_pack from the story.json in the story's folder; the default pack (core/core.json default_style_pack, Deva Neon) when
    the story names none or the file is missing (owner 2026-11-07: one fixed style for every story, a story may still pick another)."""
    try:
        data = json.loads((Path(story_path).parent / "story.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    pack = data.get("style_pack") if isinstance(data, dict) else None
    return pack if isinstance(pack, str) and pack else default_style_pack()


def default_style_pack():
    try:
        value = json.loads((Path(__file__).resolve().parent.parent / "core" / "core.json").read_text(encoding="utf-8")).get("default_style_pack")
    except (OSError, ValueError):
        value = None
    return value if isinstance(value, str) and value else "deva_neon"


def build_stage_prompt(brief, story_text, earlier, instruction, errors=(), langs=wp.DEFAULT_OUT_LANG):
    """brief + story + the saved earlier stages + the V4 override and rules (in the story's output language lang) + THIS STAGE
    (+ the validation errors of a repair)."""
    saved = "\n\n".join(f"## SAVED OUTPUT OF STAGE {name}\n\n{text.strip()}" for name, text in earlier) or "(none yet)"
    prompt = (brief + "\n\n## THE STORY / SOURCE\n\n" + story_text.strip() + "\n\n## EARLIER STAGES (saved output)\n\n" + saved
              + "\n\n" + wp.OVERRIDE + "\n\n" + wp.rules_block(langs) + "\n\n## THIS STAGE\n\n" + instruction + "\n")
    return prompt + ("\n" + wp.repair_block(list(errors)) + "\n" if errors else "")


def gate_of(name):
    return "3" if name.startswith("3e") else name


def stage_setting(table, name, default):
    return table.get(name, table.get(gate_of(name), default))


def envelope(text, finish, via, model):
    """Every path returns the same JSON shape, so parse() reads them all."""
    return json.dumps({"type": "result", "is_error": finish != "stop" or not text.strip(), "result": text, "via": via, "model": model,
                       "finish_reason": finish})


def envelope_check(raw):
    """The retry check reads the saved envelope's text and finish reason (the envelope JSON itself is never empty)."""
    try:
        data = json.loads(raw)
    except ValueError:
        return retry_policy.answer_kind(raw)          # plain text (no envelope): judge the text itself
    if not isinstance(data, dict):
        return retry_policy.answer_kind(raw)
    return retry_policy.answer_kind(data.get("result"), data.get("finish_reason"))


# --web (owner 2026-11-07): web context for every writer. Claude searches live; free models (NVIDIA, OpenRouter) get WEB_NOTES.md,
# written once per story by a Haiku low agent with web search (owner: "for the free models, use a Haiku low agent")
WEB_TOOLS = "WebSearch,WebFetch"
WEB = False
WEB_NOTES = ""   # story folder WEB_NOTES.md, given to the free models when --web
WEB_RULE = """WEB CHECK (on). You may use WebSearch and WebFetch to check facts against the Puranas and other trusted sources: names,
family relations, the order of events, places, and the traditional look of each deity or person (skin colour, number of arms,
weapons, mount, clothing, ornaments). The story source in this brief stays the authority: keep its events, their order and its
meaning; use the web only to correct a clear factual or look mistake or to fill a missing detail, and never add new episodes or
scenes. Looks follow the traditional scripture description first, then the style rules of this brief. Your final answer is
still only what this brief asks for, with no links, citations or notes about the search.

"""


NOTES_PROMPT = """You prepare research notes for a script writer who turns the story below into an animated video. Use WebSearch
and WebFetch on trusted sources (the Puranas, scholarly and temple sources) to check: names and their spellings, family relations,
the order of events, places, and the traditional look of every deity, person, animal and place named (skin colour, number of
arms, weapons, mount, clothing, ornaments, setting). The story is the authority: only note where trusted sources confirm, add a
missing detail, or clearly disagree. Answer with plain Markdown notes only, at most 1500 words, grouped by name, each point
with its source link. No story retelling.

STORY:
"""


def make_web_notes(story_path):
    """WEB_NOTES.md next to the story, by Haiku low with web search; an existing file is reused (delete it to redo)."""
    notes = Path(story_path).parent / "WEB_NOTES.md"
    if not notes.exists():
        raw = call_claude(NOTES_PROMPT + Path(story_path).read_text(encoding="utf-8"), "haiku", "low", web=True, rule=False)
        text = (json.loads(raw).get("result") or "").strip()
        if not text:
            raise RuntimeError("the Haiku notes agent returned no notes")
        notes.write_text(text + "\n", encoding="utf-8")
    return notes.read_text(encoding="utf-8").strip()


def call_claude(prompt, model, effort, web=None, rule=True):
    web = WEB if web is None else web
    tools = ["--tools", WEB_TOOLS, "--allowedTools", WEB_TOOLS] if web else ["--tools", ""]
    prompt = WEB_RULE + prompt if web and rule else prompt
    with tempfile.TemporaryDirectory() as empty:
        mcp = Path(empty).parent / "empty_mcp_anime.json"
        mcp.write_text('{"mcpServers": {}}', encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY" and not k.startswith("OPENROUTER")}
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "64000"
        r = subprocess.run([shutil.which("claude") or "claude", "-p", "--model", model, "--effort", effort, "--output-format", "json",
                            *tools, "--mcp-config", str(mcp), "--strict-mcp-config", "--no-session-persistence"],
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
            try:
                event = json.loads(line[5:])
            except json.JSONDecodeError as exc:      # a broken line from the provider: a network-class error, so the retry policy tries again
                raise retry_policy.ModelError(retry_policy.NETWORK, f"malformed stream line from the provider ({exc.msg})") from exc
            if event.get("error"):   # OpenRouter reports a failure in the middle of the stream as an error event: keep its reason
                raise RuntimeError(f"stream error from the provider: {run_registry.redact(str(event['error'])[:300])}")
            choices = event.get("choices") or [{}]
            parts.append((choices[0].get("delta") or {}).get("content") or "")
            finish = choices[0].get("finish_reason") or finish
    return "".join(parts), finish


def body_for(model, prompt, max_tokens=65536, content=None):
    """content: the user message as a plain string (default: prompt) or a list of OpenAI-style parts (images)."""
    return {"model": model, "messages": [{"role": "user", "content": prompt if content is None else content}], "temperature": 0.6,
            "top_p": 0.95, "max_tokens": max_tokens, "stream": True}


class ModelRefused(retry_policy.ModelError, RuntimeError):
    """A refused model call with its kind (rate limit, budget, server ...): the shared retry policy reads `kind`."""


def call_nvidia(prompt, model, content=None):
    """Every nvidia_api_key*.txt in turn: a refused or busy key (HTTP error) moves to the next one."""
    keys = [k for k in (p.read_text(encoding="utf-8").strip() for p in sorted(NVIDIA_KEYS.glob("nvidia_api_key*.txt"))) if k]
    if not keys:
        raise RuntimeError(f"no NVIDIA key files in {NVIDIA_KEYS}")
    errors, last_code = [], None
    for n, key in enumerate(keys, 1):
        try:
            return envelope(*stream_chat(NVIDIA_URL, key, body_for(model, prompt, content=content)), "nvidia", model)
        except urllib.error.HTTPError as exc:
            errors.append(f"key {n}: HTTP {exc.code}")
            last_code = exc.code
    raise ModelRefused(retry_policy.classify_http(last_code, "") if last_code else retry_policy.FATAL,
                       "every NVIDIA key failed: " + "; ".join(errors))


def openrouter_is_free(model, catalog=None):
    """True when every price field of `model` in OpenRouter's public catalog is 0."""
    try:
        catalog = catalog or json.load(urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=60))["data"]
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ValueError(f"cannot check whether {model} is free (catalog unreachable: {type(exc).__name__}): refused") from exc
    if not any(m.get("id") == model for m in catalog):
        raise ValueError(f"{model} is not in OpenRouter's catalog")
    return retry_policy.is_free_model(model, catalog)      # the one free-price rule (every price field present and 0)


def call_openrouter(prompt, model, allow_paid=False, content=None):
    """Streamed (SSE) call, max_tokens 65536: the same body as NVIDIA. A cut-off answer (finish_reason other than stop) is
    an error in the envelope; an HTTP refusal (e.g. a max_tokens the model does not allow) is raised with OpenRouter's reason."""
    if not allow_paid and not openrouter_is_free(model):
        raise ValueError(f"{model} is a paid OpenRouter model: refused (no paid calls; pass --allow-paid only with the owner's OK)")
    try:
        key = OPENROUTER_KEY.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"no OpenRouter key file at {OPENROUTER_KEY}") from exc
    try:
        text, finish = stream_chat(OPENROUTER_URL, key, body_for(model, prompt, content=content), {"X-Title": "anime-studio-writer"})
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read(400).decode("utf-8", "replace")
        except Exception:
            detail = ""
        raise ModelRefused(retry_policy.classify_http(exc.code, detail),
                           f"OpenRouter refused the call for {model}: HTTP {exc.code} {run_registry.redact(detail)}") from None
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


def call_path(prompt, via, model, effort, allow_paid, policy=None, sleep=None):
    """One model call. Claude runs once. NVIDIA and OpenRouter go through the shared retry policy (director/retry_policy.py):
    rate limits, server errors, timeouts and empty answers are retried with growing waits (15-180 s, max 5 calls, 600 s cap);
    a refusal that retrying cannot fix (budget, bad request) stops at once. The error reaches the caller as ModelGaveUp."""
    if WEB and WEB_NOTES and via != "claude":
        prompt = "WEB RESEARCH NOTES (checked facts and traditional looks; the story source stays the authority):\n" + WEB_NOTES + "\n\n" + prompt
    if via == "claude":
        return call_claude(prompt, model, effort)
    one = (lambda: call_nvidia(prompt, model)) if via == "nvidia" else (lambda: call_openrouter(prompt, model, allow_paid))
    kw = {"policy": policy} if policy else {}
    if sleep:
        kw["sleep"] = sleep
    try:
        return retry_policy.call_with_retry(one, model=model, check=envelope_check, **kw)
    except retry_policy.ModelGaveUp as gave_up:
        if gave_up.kind == retry_policy.FATAL and gave_up.__cause__ is not None:
            raise gave_up.__cause__ from None            # a plain refusal (e.g. paid model): the caller sees the real error
        raise


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
    try:
        answer = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"the saved model answer is not valid JSON ({exc.msg}): delete the raw file and rerun") from exc
    if not isinstance(answer, dict) or "result" not in answer and not answer.get("is_error"):
        raise ValueError("the saved model answer has no 'result' field")
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
    if not all(isinstance(s, dict) and isinstance(s.get("id"), str) and s["id"] for s in shots):
        raise ValueError("every shot needs a string id")
    ids = [s["id"] for s in shots]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate shot ids")
    for shot in shots:
        if not is_v4_row(shot):                 # a legacy row must still be one the H3 director can run; V4 rows are checked by the validator
            try:
                settings_for(shot)
            except Exception as exc:           # KeyError, TypeError ... on a malformed row is a parse error, not a traceback
                raise ValueError(f"shot {shot.get('id')}: the H3 director cannot read this row ({type(exc).__name__}: {exc})") from exc
    return text, shots


def is_v4_row(shot):
    return "lattice_n" in shot


def parse_story(raw):
    """(text, data) from a stage 1 answer. data is the ```json story block plus the answer text; no block = {"text": ...} and
    the validator then reports the missing checks."""
    text = answer_text(raw)
    blocks = STORY_BLOCK.findall(text)
    if len(blocks) > 1:
        raise ValueError(f"expected at most one ```json story block, found {len(blocks)}")
    data = json.loads(blocks[0]) if blocks else {}
    if not isinstance(data, dict):
        raise ValueError("the ```json story block must be one JSON object")
    return text, dict(data, text=text)


def parse_captions(raw):
    """(text, data) from a stage 5 answer: data = {"text", "captions": [items]}. The ```json captions block is optional."""
    text = answer_text(raw)
    blocks = CAPTIONS_BLOCK.findall(text)
    if len(blocks) > 1:
        raise ValueError(f"expected at most one ```json captions block, found {len(blocks)}")
    items = json.loads(blocks[0]) if blocks else []
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise ValueError("the captions block must be a JSON list of objects")
    return text, {"text": text, "captions": items}


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
    """Episode numbers named by stage 1: its ```json story block (V4), else a ```json episodes block, else lines 'Episode N' / 'Ep N'."""
    story = STORY_BLOCK.search(text)
    block = EPISODES_BLOCK.search(text)
    story_data = json.loads(story.group(1)) if story else None
    if isinstance(story_data, dict) and isinstance(story_data.get("episodes"), list):   # a story block that is not an object is not used
        found = [e["episode"] for e in story_data["episodes"] if isinstance(e, dict) and isinstance(e.get("episode"), int) and not isinstance(e.get("episode"), bool)]
    elif block:
        try:
            values = json.loads(block.group(1))
        except json.JSONDecodeError as exc:
            raise ValueError(f"the ```json episodes block is not valid JSON ({exc.msg}): fix the block and rerun") from exc
        if not isinstance(values, list):   # null or a bare number: a stage failure, not a TypeError
            raise ValueError("the ```json episodes block must be a JSON list of episode numbers or objects")
        found = [v if isinstance(v, int) and not isinstance(v, bool) else v.get("episode") if isinstance(v, dict) else None
                 for v in values]
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in found):
            raise ValueError("the ```json episodes block must hold episode numbers or objects with an integer 'episode'")
    else:
        found = [int(n) for n in EPISODE_LINE.findall(text)] or [int(n) for n in EPISODE_ROW.findall(text)]
    episodes = sorted(set(found))
    if not episodes:
        raise ValueError("stage 1 names no episodes (write lines 'Episode N: title' or a ```json episodes block)")
    return episodes


def parse_stage_map(spec_text, check):
    """'2=nvidia,3e2=claude' -> {'2': 'nvidia', '3e2': 'claude'}"""
    table = {}
    for item in (s.strip() for s in spec_text.split(",") if s.strip()):
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


class StageFailed(ValueError):
    """A stage whose answer still fails its checks after the one repair retry. The run stops; the stage's files say why."""


def checked_call(name, call, *args):
    """One model call. A refusal (ValueError, e.g. a paid model) passes through as before; any other failure (missing key files,
    ModelGaveUp, network) becomes StageFailed, so the run stops with a message and the registry step is marked failed."""
    try:
        return call(*args)
    except (ValueError, StageFailed):
        raise
    except Exception as exc:
        raise StageFailed(f"stage {name}: the model call failed ({type(exc).__name__}: {str(exc)[:300]}); nothing was saved for it, "
                          "rerun to retry") from exc


class _CheckFailed(Exception):
    """Raised inside a pack_check step so the run registry records it as failed; caught at once."""


def validator():
    """director/pack_validator.py (written by the validator agent), or None with a warning: the stages are then not checked."""
    try:
        return importlib.import_module("pack_validator")
    except ImportError as exc:
        print(f"write_pack: pack_validator unavailable ({exc}): the stage checks are skipped", file=sys.stderr)
        return None


def simple_hook():
    """The lang_check hook of the validator: director/simple_language.py check_text on each text (English is not run through it).
    None (with a warning) when that module is missing."""
    try:
        simple = importlib.import_module("simple_language")
    except ImportError as exc:
        print(f"write_pack: simple_language unavailable ({exc}): the language-quality hook is skipped", file=sys.stderr)
        return None

    def hook(text, lang):
        return None if lang == "en" else simple.check_text(text, lang)
    return hook


def stage_errors(mod, name, data, bible, output_languages=None, lang_check=None, voice_engines=None):
    """The error lines the validator reports for one stage's data; None when there is no validator. output_languages: the
    story's selected languages (validate_stage checks the language set and the ML-* rules against them); lang_check: simple_hook().
    Never raises."""
    if mod is None:
        return None
    try:
        report = mod.validate_stage(name, data, bible, output_languages=output_languages, lang_check=lang_check,
                                    voice_engines=voice_engines)
    except Exception as exc:                                    # a crashing check is a failed check, with its reason
        return [f"VALIDATOR at stage {name}: {type(exc).__name__}: {exc}"]
    for warning in report.get("warnings") or []:
        print(f"stage {name} warning: {warning}", file=sys.stderr)
    errors = [f"{e.get('code')} at {e.get('where')}: {e.get('message')}" for e in report.get("errors") or []]
    if not report.get("ok") and not errors:
        errors = [f"stage {name} is not ok (the validator gave no detail)"]
    return errors


def record_check(rec, name, errors):
    """One pack_check step in the run registry: ok, failed with the error lines, or not checked (no validator). Best effort."""
    note = "validator unavailable: stage not checked" if errors is None else ("; ".join(errors)[:300] if errors else "ok")
    try:
        with rec.step("pack_check", name, note=note):
            if errors:
                raise _CheckFailed(note)
    except _CheckFailed:
        pass


def run_stage(name, out, *, prompt_for, call, parse_fn, check_fn, rec):
    """One stage: a saved answer is reused (no call), else one call; the answer is parsed and checked. A failed check gets ONE repair
    retry (spec.MAX_REPAIR_RETRIES) with the error list appended to the prompt. Still failing: stage_<name>_validation.json is saved
    next to stage_<name>_raw.json and StageFailed is raised. A stage with both files is never called again (delete them to redo it).
    prompt_for(errors) -> prompt; call(prompt, raw_path) -> makes the model call and saves the answer to raw_path;
    parse_fn(raw) -> (text, data), ValueError on a parse problem; check_fn(data) -> error lines or None (no validator).
    Returns (text, data)."""
    raw_path = out / f"stage_{name}_raw.json"
    val_path = out / f"stage_{name}_validation.json"
    if raw_path.exists() and val_path.exists():
        raise stage_failed(name, run_registry.read_json(val_path, {}).get("errors") or ["see the validation file"], out)

    def judge(raw):
        try:
            text, data = parse_fn(raw)
        except ValueError as exc:
            errors = [f"PARSE at stage {name}: {exc}"]
            record_check(rec, name, errors)
            return None, None, errors
        errors = check_fn(data)
        record_check(rec, name, errors)
        return text, data, errors

    if raw_path.exists():
        info = run_registry.envelope_file(raw_path)
        with rec.step("analysis_stage", name, via=info.get("via"), model=info.get("model"), files=[f"{out.name}/{raw_path.name}"],
                      note="saved answer reused: no model call"):
            pass
    else:
        checked_call(name, call, prompt_for([]), raw_path)
    print(f"stage {name}: {raw_path}")
    text, data, errors = judge(raw_path.read_text(encoding="utf-8"))
    retries = 0
    while errors and retries < spec.MAX_REPAIR_RETRIES:
        retries += 1
        checked_call(name, call, prompt_for(errors), raw_path)
        print(f"stage {name}: repair retry {retries}: {raw_path}")
        text, data, errors = judge(raw_path.read_text(encoding="utf-8"))
    if errors:
        val_path.write_text(json.dumps({"stage": name, "errors": errors, "repair_retries": retries, "answer": raw_path.name},
                                       indent=1, ensure_ascii=False), encoding="utf-8")
        raise stage_failed(name, errors, out)
    val_path.unlink(missing_ok=True)
    return text, data


def stage_failed(name, errors, out):
    return StageFailed(f"stage {name} fails its checks after the repair retry: " + "; ".join(errors[:5])
                       + f" (answer: {out.name}/stage_{name}_raw.json, errors: {out.name}/stage_{name}_validation.json;"
                       + " delete both files to redo this stage)")


def episode_seconds(plan):
    """{episode: seconds} from the stage 1 story block (empty when the block has none)."""
    out = {}
    for e in plan.get("episodes") or []:
        if isinstance(e, dict) and isinstance(e.get("episode"), int) and isinstance(e.get("seconds"), (int, float)):
            out[e["episode"]] = float(e["seconds"])
    return out


def is_card_group(value):
    return isinstance(value, dict)


CANON_KEYS = ("style_lock", "characters", "environments", "props")


def canonical_bible(bible):
    """The one canonical layout (V4): style_lock, characters, environments and props first, in that order, always present. A bible
    whose card groups are not objects (the older list form) is written as it came."""
    if not any(is_card_group(bible.get(k)) for k in CANON_KEYS[1:]):
        return bible
    head = {k: bible.get(k, {}) for k in CANON_KEYS}
    return {**head, **{k: v for k, v in bible.items() if k not in head}}


def legacy_fields(shot, bible=None):
    """A V4 row plus the old fields the legacy readers use (mode, seconds, aspect, style, action, camera, sound), derived from the V4
    columns. The row's own values win. A legacy row is returned unchanged."""
    if not is_v4_row(shot):
        return shot
    dirs = [d for d in shot.get("per_second_directives") or [] if isinstance(d, dict)]
    track = shot.get("audio_and_dialogue_track") if isinstance(shot.get("audio_and_dialogue_track"), dict) else {}
    lock = (bible or {}).get("style_lock")
    derived = {
        "mode": "ref2va" if shot.get("route") == "Ref2VA" else "fl2va",
        "seconds": shot.get("editorial_duration_sec"),
        "aspect": "9:16",
        "style": lock.get("prefix", "") if is_card_group(lock) else "",
        "action": " ".join(f"{d.get('t0')}-{d.get('t1')}s {d.get('action_pose_expression', '')}" for d in dirs),
        "camera": " ".join(str(d.get("camera", "")) for d in dirs),
        "sound": " ".join(str(c.get("description", "")) for c in track.get("sfx_cues") or [] if isinstance(c, dict)),
    }
    return {**derived, **shot}


def with_language(errors, language_errors):
    """The validator's error lines (None = no validator) plus the writer's language errors. None only when both are empty
    and there is no validator: the stage is then recorded as not checked."""
    if errors is None:
        return language_errors or None
    return language_errors + [e for e in errors if e not in language_errors]     # an identical line from both is reported once


def text_language_errors(pairs, lang):
    """LANG-02: each (where, text) must be simple everyday text of the story's language (director/simple_language.py, the two-tier
    validator). English is not checked this way. A missing or crashing simple_language module is a warning, never a failure."""
    if lang == "en" or not pairs:
        return []
    try:
        simple = importlib.import_module("simple_language")
    except ImportError as exc:
        print(f"write_pack: simple_language unavailable ({exc}): the text language check is skipped", file=sys.stderr)
        return []
    errors = []
    for where, text in pairs:
        if not isinstance(text, str) or not text.strip():
            continue
        try:
            result = simple.check_text(text, lang)
        except Exception as exc:
            print(f"write_pack: simple_language check failed at {where} ({type(exc).__name__}: {exc}): skipped", file=sys.stderr)
            continue
        if not result.get("ok", True):
            words = ", ".join(str(f.get("word", "?")) for f in result.get("flags") or [] if isinstance(f, dict)) or "?"
            errors.append(f"LANG-02 at {where}: not simple {wp.lang_rule(lang)['name']} text ({words})")
    return errors


def multi_lang(langs):
    return len(langs) > 1


def _card_text(card):
    """A caption card is {text, time_range} (multi-language rows) or a plain string (single language)."""
    return card.get("text") if isinstance(card, dict) else card


def _card_time(card):
    return tuple(card.get("time_range") or ()) if isinstance(card, dict) else None


def _word_errors(where, cards):
    """CAP-01: a caption card over the word limit."""
    return [f"CAP-01 at {where}: {len(_card_text(c).split())} words, the limit is {spec.CAPTION['max_words']}"
            for c in cards if isinstance(_card_text(c), str) and len(_card_text(c).split()) > spec.CAPTION["max_words"]]


def _dialogue_pairs(sid, lines, prefix):
    return [(f"{sid}.{prefix}[{j}]", d.get("text")) for j, d in enumerate(lines or []) if isinstance(d, dict)]


def shot_language_errors(shots, langs):
    """The narration and dialogue of each shot in the story's output languages. One language: narration.language must be that
    language. Several: narration_by_lang and dialogue_by_lang hold one entry per language with the SAME time ranges (LANG-03 = shape,
    LANG-01 = language code, LANG-04 = timing, LANG-02 = not simple text of its language)."""
    langs = wp.lang_list(langs)
    errors = []
    for shot in shots:
        sid = shot.get("id")
        track = shot.get("audio_and_dialogue_track") if isinstance(shot.get("audio_and_dialogue_track"), dict) else {}
        if not multi_lang(langs):
            narration = track.get("narration")
            pairs = []
            if is_card_group(narration):
                if narration.get("language") != langs[0]:
                    errors.append(f"LANG-01 at {sid}.audio_and_dialogue_track.narration.language: {narration.get('language')!r}, "
                                  f"the story's output language is {langs[0]!r}")
                pairs.append((f"{sid}.narration", narration.get("text")))
            errors += text_language_errors(pairs + _dialogue_pairs(sid, track.get("dialogue"), "dialogue"), langs[0])
            continue
        errors += _narration_by_lang_errors(sid, track, langs)
        errors += _dialogue_by_lang_errors(sid, track, langs)
        errors += _captions_by_lang_errors(sid, track, langs)
    return errors


def _captions_by_lang_errors(sid, track, langs):
    """The shot's captions per language (inside its audio_and_dialogue_track): one list per language, the same count, simple text."""
    by_lang = track.get("captions_by_lang")
    if not is_card_group(by_lang) or set(by_lang) != set(langs):
        return [f"LANG-03 at {sid}.captions_by_lang: needs exactly one list per output language ({', '.join(langs)})"]
    errors = []
    if len({len(by_lang[c]) if isinstance(by_lang[c], list) else -1 for c in langs}) > 1:
        errors.append(f"LANG-04 at {sid}.captions_by_lang: every language needs the same number of cards")
    reference = [_card_time(c) for c in by_lang[langs[0]]] if isinstance(by_lang[langs[0]], list) else []
    for c in langs:
        cards = by_lang[c] if isinstance(by_lang[c], list) else []
        if [_card_time(x) for x in cards] != reference:
            errors.append(f"LANG-04 at {sid}.captions_by_lang.{c}: time ranges differ from the primary (same timing in every language)")
        errors += _word_errors(f"{sid}.captions_by_lang.{c}", cards)
        errors += text_language_errors([(f"{sid}.captions_by_lang.{c}[{j}]", _card_text(x)) for j, x in enumerate(cards)], c)
    return errors


def _narration_by_lang_errors(sid, track, langs):
    errors, by_lang = [], track.get("narration_by_lang")
    if not is_card_group(by_lang) or set(by_lang) != set(langs):
        return [f"LANG-03 at {sid}.narration_by_lang: needs exactly one entry per output language ({', '.join(langs)})"]
    entries = {c: by_lang.get(c) for c in langs}
    if all(v is None for v in entries.values()):                     # no narration in this shot
        return []
    reference = entries[langs[0]] if is_card_group(entries[langs[0]]) else {}
    for c in langs:
        entry = entries[c]
        if not is_card_group(entry):
            errors.append(f"LANG-03 at {sid}.narration_by_lang.{c}: missing narration object for {c}")
            continue
        if entry.get("language") != c:
            errors.append(f"LANG-01 at {sid}.narration_by_lang.{c}.language: {entry.get('language')!r}, expected {c!r}")
        if entry.get("time_range") != reference.get("time_range"):
            errors.append(f"LANG-04 at {sid}.narration_by_lang.{c}.time_range: {entry.get('time_range')!r} differs from the primary "
                          f"{reference.get('time_range')!r} (every language keeps the same time range)")
        errors += text_language_errors([(f"{sid}.narration_by_lang.{c}", entry.get("text"))], c)
    return errors


def _dialogue_by_lang_errors(sid, track, langs):
    errors, by_lang = [], track.get("dialogue_by_lang")
    if not is_card_group(by_lang) or set(by_lang) != set(langs):
        return [f"LANG-03 at {sid}.dialogue_by_lang: needs exactly one list per output language ({', '.join(langs)})"]
    reference = by_lang.get(langs[0]) if isinstance(by_lang.get(langs[0]), list) else []
    for c in langs:
        lines = by_lang.get(c)
        if not isinstance(lines, list):
            errors.append(f"LANG-03 at {sid}.dialogue_by_lang.{c}: must be a list (use [] for none)")
            continue
        if len(lines) != len(reference):
            errors.append(f"LANG-04 at {sid}.dialogue_by_lang.{c}: {len(lines)} lines, the primary has {len(reference)}")
            continue
        for j, (line, ref) in enumerate(zip(lines, reference)):
            if not is_card_group(line) or not is_card_group(ref):
                continue
            if line.get("time_range") != ref.get("time_range") or line.get("speaker") != ref.get("speaker"):
                errors.append(f"LANG-04 at {sid}.dialogue_by_lang.{c}[{j}]: speaker and time_range must match the primary line")
        errors += text_language_errors(_dialogue_pairs(sid, lines, f"dialogue_by_lang.{c}"), c)
    return errors


def caption_language_errors(items, langs):
    """The stage 5 captions and texts. One language: the cards and texts are in that language. Several: captions_by_lang has one
    list per language, all the same length, every card at most the word limit (CAP-01) and simple text of its language."""
    langs = wp.lang_list(langs)
    errors, per_lang = [], {c: [] for c in langs}
    for item in items:
        sid = item.get("shot_id")
        if not multi_lang(langs):
            cards = item.get("cards") or []
            errors += _word_errors(f"{sid}.cards", cards)
            per_lang[langs[0]] += [(f"{sid}.cards[{j}]", c) for j, c in enumerate(cards)]
            if item.get("narration_text"):
                per_lang[langs[0]].append((f"{sid}.narration_text", item["narration_text"]))
            per_lang[langs[0]] += [(f"{sid}.dialogue_texts[{j}]", t) for j, t in enumerate(item.get("dialogue_texts") or [])]
            continue
        cbl = item.get("captions_by_lang")
        if not is_card_group(cbl) or set(cbl) != set(langs):
            errors.append(f"LANG-03 at {sid}.captions_by_lang: needs exactly one list per output language ({', '.join(langs)})")
            cbl = {}
        if len({len(cbl.get(c) or []) for c in cbl}) > 1:
            errors.append(f"LANG-04 at {sid}.captions_by_lang: every language needs the same number of cards")
        for c in cbl:
            errors += _word_errors(f"{sid}.captions_by_lang.{c}", cbl.get(c) or [])
            per_lang[c] += [(f"{sid}.captions_by_lang.{c}[{j}]", _card_text(card)) for j, card in enumerate(cbl.get(c) or [])]
        for key, field in (("narration_text_by_lang", None), ("dialogue_texts_by_lang", None)):
            by = item.get(key)
            if is_card_group(by):
                for c, value in by.items():
                    values = value if isinstance(value, list) else [value]
                    if c in per_lang:
                        per_lang[c] += [(f"{sid}.{key}.{c}[{j}]", t) for j, t in enumerate(values)]
    for c in langs:
        errors += text_language_errors(per_lang[c], c)
    return errors


def voice_mod():
    """h3/voice_engine.py (the voice rules shared with pack_validator and the H3 linter). The repo root goes on sys.path here."""
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    return importlib.import_module("h3.voice_engine")


def voice_setting(langs, overrides=None):
    """The story's voice_engine dict: owner defaults en=elevenlabs, hi=elevenlabs, mr=elevenlabs, overrides applied for the selected
    languages. Never None: the rules are pure and always available."""
    return voice_mod().resolve_engines(wp.lang_list(langs), overrides)


def record_output_language(story_dir, langs, engines=None):
    """story.json: output_languages (the list, priority order), output_language (the first, for old readers) and voice_engine.
    Best effort: a failure is a warning, never a stop. No story folder = nothing written."""
    if story_dir is None:
        return
    try:
        langs = wp.lang_list(langs)
        path = Path(story_dir) / run_registry.STORY_FILE
        meta = run_registry.read_story(story_dir) or run_registry.default_story(story_dir)
        meta["output_languages"] = list(langs)
        meta["output_language"] = langs[0]
        if engines is not None:
            meta["voice_engine"] = dict(engines)
        path.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"write_pack: output_language not recorded in story.json ({type(exc).__name__}: {exc})", file=sys.stderr)


def _stage5_item(item):
    """A stage 5 item with a wrong JSON type in a text field becomes empty there: the validator reports the missing text; the run does not crash."""
    def lists(d):
        return {k: (v if isinstance(v, list) else []) for k, v in d.items()} if isinstance(d, dict) else {}
    out = dict(item)
    out["cards"] = out["cards"] if isinstance(out.get("cards"), list) else []
    out["dialogue_texts"] = out["dialogue_texts"] if isinstance(out.get("dialogue_texts"), list) else []
    out["captions_by_lang"] = lists(out.get("captions_by_lang"))
    out["dialogue_texts_by_lang"] = lists(out.get("dialogue_texts_by_lang"))
    out["narration_text_by_lang"] = out["narration_text_by_lang"] if isinstance(out.get("narration_text_by_lang"), dict) else {}
    return out


def apply_captions(shots, items, langs):
    """Stage 5 onto the shot rows. One language: captions (the cards), narration text and dialogue texts. Several languages: the per
    language captions_by_lang, narration_by_lang and dialogue_by_lang texts, and the flat narration, dialogue and captions mirror the
    primary language. Unknown shot ids are left for the validator to report."""
    langs = wp.lang_list(langs)
    by_id = {i.get("shot_id"): i for i in items}
    for shot in shots:
        # stage 5 names the original per-episode id; merge_episodes has renumbered the shot and kept that id as source_id
        item = by_id.get(shot.get("source_id")) or by_id.get(shot.get("id"))
        if not item:
            continue
        item = _stage5_item(item)
        track = shot.get("audio_and_dialogue_track") if isinstance(shot.get("audio_and_dialogue_track"), dict) else None
        if not multi_lang(langs):
            shot["captions"] = list(item.get("cards") or [])
            if track is None:
                continue
            if item.get("narration_text") and is_card_group(track.get("narration")):
                track["narration"]["text"] = item["narration_text"]
            for line, text in zip([d for d in track.get("dialogue") or [] if isinstance(d, dict)], item.get("dialogue_texts") or []):
                line["text"] = text
            continue
        shot["captions"] = [_card_text(card) for card in (item.get("captions_by_lang") or {}).get(langs[0]) or []]
        if track is None:
            continue
        track["captions_by_lang"] = {c: list((item.get("captions_by_lang") or {}).get(c) or []) for c in langs}
        for c, text in (item.get("narration_text_by_lang") or {}).items():
            entry = (track.get("narration_by_lang") or {}).get(c)
            if is_card_group(entry) and isinstance(text, str):
                entry["text"] = text
        for c, texts in (item.get("dialogue_texts_by_lang") or {}).items():
            lines = [d for d in (track.get("dialogue_by_lang") or {}).get(c) or [] if isinstance(d, dict)]
            for line, text in zip(lines, texts or []):
                line["text"] = text
        primary = langs[0]
        if is_card_group((track.get("narration_by_lang") or {}).get(primary)):
            track["narration"] = dict(track["narration_by_lang"][primary])
        if isinstance((track.get("dialogue_by_lang") or {}).get(primary), list):
            track["dialogue"] = [dict(d) for d in track["dialogue_by_lang"][primary]]
    return shots


def run_staged(story_text, out, via, model, effort, allow_paid, stage_via, stage_model, rec=None, out_langs=wp.DEFAULT_OUT_LANG,
               voice=None, prompt_version=DEFAULT_PROMPT_VERSION, style_rules=""):
    """Stages 1, 2, 3e<N> per episode, 5, each checked (see run_stage). Writes PACK.md, bible.json, shots.json and story_plan.json;
    returns the merged shots. rec: the run registry Recorder of this run (default: records nothing). out_langs: the story's output
    languages (a code or a list, primary first): narration, dialogue and captions are written in each and checked against them. prompt_version: which staged brief to send; style_rules: text appended
    to that brief (empty = nothing appended)."""
    langs = wp.lang_list(out_langs)
    rec = rec or run_registry.Recorder(None, "none")
    brief = staged_brief(prompt_version).read_text(encoding="utf-8")
    if style_rules:
        brief += "\n\n" + style_rules
    out.mkdir(parents=True, exist_ok=True)
    mod = validator()
    hook = simple_hook() if mod is not None else None
    done = []                                                   # (stage name, saved text), in order
    engines = voice_setting(langs, voice)                       # voice_engine per language (owner defaults + --voice)
    record_output_language(rec.dir, langs, engines)

    def call_for(name, prompt, raw_path):
        v = stage_setting(stage_via, name, via)
        m = stage_setting(stage_model, name, model if v == via else None) or DEFAULT_MODEL[v]
        if not m:
            raise ValueError(f"stage {name}: --model is required with --via openrouter")
        refuse_finished(out)
        # ponytail: stages and episodes run one after another; parallel episodes when a run gets slow
        with rec.step("analysis_stage", name, via=v, model=m, effort=effort, files=[f"{out.name}/{raw_path.name}"]) as st:
            text = call_path(prompt, v, m, effort, allow_paid)
            raw_path.write_text(text, encoding="utf-8")
            st.chars = run_registry.envelope_info(text).get("chars")

    def stage(name, parse_fn, check_fn, first=1, seconds=None):
        def prompt_for(errors):
            return build_stage_prompt(brief, story_text, done, wp.stage_instruction(name, seconds, first, langs, voice=engines),
                                      errors, langs=langs)
        return run_stage(name, out, prompt_for=prompt_for, call=lambda prompt, path: call_for(name, prompt, path),
                         parse_fn=parse_fn, check_fn=check_fn, rec=rec)

    def gate(name, data, bible_for, fallback=lambda: [], merge=False):
        """The validator's checks, with the story's languages and the simple-language hook, when there is a validator. Without one,
        the writer's own language checks (fallback) run and the stage is recorded as not checked by the validator. merge=True also
        runs the fallback next to the validator: stage 5 is a passthrough in the validator (no rule), so its caption checks are only
        here. Stages with a validator rule keep the validator alone (its own LANG checks; the fallback would contradict it)."""
        if mod is None:
            return with_language(None, fallback())
        errors = stage_errors(mod, name, data, bible_for, output_languages=langs, lang_check=hook, voice_engines=engines)
        return with_language(errors, fallback()) if merge else errors

    def story_parse(raw):
        text, data = parse_story(raw)
        extra = {"voice_engine": dict(engines)} if engines is not None else {}
        return text, dict(data, output_languages=list(langs), output_language=langs[0], **extra)   # the selection, for the validator

    with rec.step("analysis_done", None, via=via, model=model, effort=effort) as run:
        text1, plan = stage("1", story_parse, lambda d: gate("1", d, None))
        done.append(("1", text1))
        text2, bible = stage("2", parse_bible, lambda d: with_language(gate("2", d, None), style_pack_errors(d, STYLE_PACK)))
        done.append(("2", text2))
        try:
            episodes = episodes_from(text1)
        except ValueError as exc:       # stage 1 passed its checks but names no usable episodes: a failed stage, not a traceback
            raise StageFailed(f"stage 1 answer is unusable: {exc}; delete {out.name}/stage_1_raw.json to redo it") from exc
        per_episode, seconds = [], episode_seconds(plan)
        for ep in episodes:
            first = 1 + sum(len(s) for s in per_episode)
            check = (lambda shots, ep=ep: gate("3", {"episode": ep, "shots": shots}, bible,
                                               lambda: shot_language_errors(shots, langs)))
            text, ep_shots = stage(f"3e{ep}", parse, check, first=first, seconds=seconds.get(ep))
            done.append((f"3e{ep}", text))
            per_episode.append(ep_shots)
        text5, captions = stage("5", parse_captions,
                                lambda d: gate("5", d, bible, lambda: caption_language_errors(d["captions"], langs), merge=True))
        done.append(("5", text5))
        shots = [legacy_fields(s, bible) for s in apply_captions(merge_episodes(per_episode), captions["captions"], langs)]
        (out / "PACK.md").write_text("\n\n".join(text for _, text in done), encoding="utf-8")
        (out / "bible.json").write_text(json.dumps(canonical_bible(bible), indent=1, ensure_ascii=False), encoding="utf-8")
        (out / "shots.json").write_text(json.dumps(shots, indent=1, ensure_ascii=False), encoding="utf-8")
        (out / "story_plan.json").write_text(json.dumps({k: v for k, v in plan.items() if k != "text"}, indent=1, ensure_ascii=False),
                                             encoding="utf-8")
        run.files = [f"{out.name}/{n}" for n in ("PACK.md", "bible.json", "shots.json", "story_plan.json")]
        run.note = f"{len(episodes)} episodes, {len(shots)} shots, output languages {','.join(langs)}"
    print(f"{len(episodes)} episodes, {len(shots)} shots, output languages {','.join(langs)} -> {out}")
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
                text = checked_call("single", call_path, prompt, via, model, effort, allow_paid)
                raw_path.write_text(text, encoding="utf-8")
                st.chars = run_registry.envelope_info(text).get("chars")
        try:
            text, shots = parse(raw_path.read_text(encoding="utf-8"))
        except ValueError as exc:       # a bad saved answer stops the run with a message, not a traceback
            raise StageFailed(f"the saved answer is unusable: {exc}; delete {out.name}/raw_response.json to redo it") from exc
        (out / "PACK.md").write_text(text, encoding="utf-8")
        (out / "shots.json").write_text(json.dumps(shots, indent=1, ensure_ascii=False), encoding="utf-8")
        run.files = [f"{out.name}/{n}" for n in ("PACK.md", "shots.json")]
        run.note = f"{len(shots)} shots"
    print(f"{len(shots)} shots -> {out / 'shots.json'}")
    return shots


def out_langs_arg(text):
    """argparse type for --out-lang: one code, a comma list (priority order) or 'all'."""
    try:
        return wp.parse_langs(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("story"); ap.add_argument("out_dir")
    ap.add_argument("--writer", choices=tuple(WRITERS), default=None,
                    help="shortcut that sets --via and --model: super-vl (default), ultra (OpenRouter, free) or opus (Claude, effort medium)")
    ap.add_argument("--via", default=None, choices=VIAS)
    ap.add_argument("--model"); ap.add_argument("--effort", default=None, choices=("low", "medium", "high"))
    ap.add_argument("--allow-paid", action="store_true")
    ap.add_argument("--web", action="store_true", help="web context: Claude searches live; free models get WEB_NOTES.md made by a Haiku low agent with web search")
    ap.add_argument("--staged", action="store_true", help="one call per gate: 1, 2, 3e<N> per episode, 5")
    ap.add_argument("--stage-via", default="", help="staged only: per-stage path, e.g. 2=nvidia,3=claude")
    ap.add_argument("--stage-model", default="", help="staged only: per-stage model, e.g. 3=opus")
    ap.add_argument("--voice", default="", metavar="LANG=ENGINE,...",
                    help="staged only: voice engine per language, e.g. en=elevenlabs (defaults en=elevenlabs, hi=elevenlabs, mr=elevenlabs; "
                         "hi/mr may never be h3)")
    ap.add_argument("--out-lang", default=None, type=out_langs_arg, metavar="LANGS",
                    help=f"staged only: output languages of narration, dialogue and captions: en, hi, mr, a comma list in priority order "
                         f"(en,hi) or all (default {wp.DEFAULT_OUT_LANG})")
    ap.add_argument("--prompt-version", default=None, choices=("v2.2", "v2.3"),
                    help="staged only: the brief. v2.3 (default: look and hook rules, plus the style pack rules) or v2.2 (the old brief)")
    ap.add_argument("--style-pack", default=None,
                    help="staged + v2.3 only: style pack id (styles/<id>.json). Default: style_pack in the story.json next to the story")
    a = ap.parse_args(argv)
    if not a.staged and (a.stage_via or a.stage_model or a.prompt_version or a.style_pack):
        ap.error("--stage-via, --stage-model, --prompt-version and --style-pack need --staged")
    if not a.staged and a.out_lang is not None:
        ap.error("--out-lang needs --staged (the single-call brief does not use it)")
    if not a.staged and a.voice:
        ap.error("--voice needs --staged (the single-call brief does not use it)")
    out_langs = a.out_lang or [wp.DEFAULT_OUT_LANG]
    try:
        writer, via, model, effort = resolve_route(a.writer, a.via, a.model, a.effort)
        stage_via = parse_stage_map(a.stage_via, check_via) if a.staged else {}
        stage_model = parse_stage_map(a.stage_model, str) if a.staged else {}
    except ValueError as exc:
        ap.error(str(exc))
    global WEB, WEB_NOTES
    WEB = a.web
    if WEB:
        free = via != "claude" or any(v != "claude" for v in stage_via.values())
        WEB_NOTES = make_web_notes(a.story) if free else ""
        print(f"web check: on (Claude searches live; free models get WEB_NOTES.md: {'yes' if WEB_NOTES else 'not needed'})")
    prompt_version = a.prompt_version or DEFAULT_PROMPT_VERSION   # Q5 (2026-11-07): the staged default is v2.3
    style = ""
    if a.staged and prompt_version == "v2.3":
        pack_id = a.style_pack or story_pack_id(Path(a.story))
        style = style_rules(pack_id) if pack_id else ""
        global STYLE_PACK
        STYLE_PACK = load_style_pack(pack_id)
    out = Path(a.out_dir)
    rec = run_registry.Recorder(run_registry.story_folder(Path(a.story)), run_registry.writer_tag(writer, via, model),
                                pack=out.name, via=via, model=model, effort=effort)
    if a.staged:
        try:
            voice = voice_mod().parse_overrides(a.voice) if a.voice else None
        except (ValueError, AttributeError) as exc:
            ap.error(str(exc))
        run_staged(Path(a.story).read_text(encoding="utf-8"), out, via, model, effort, a.allow_paid, stage_via, stage_model, rec,
                   out_langs=out_langs, voice=voice, prompt_version=prompt_version, style_rules=style)
        return
    run_single(Path(a.story).read_text(encoding="utf-8"), out, via, model, effort, a.allow_paid, rec)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except StageFailed as exc:                  # the stage files are on disk; the message says which to delete to redo it
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
