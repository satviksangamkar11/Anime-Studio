"""Reviewer of the x2 candidates of one Flow submit against the job, the reference sheets and the previous/next shots (universal Flow image system, 2026-11-01; NVIDIA backend 2026-11-06).

  python scripts/flow/review_shot.py --jobs canon/drafts/A1_flow_jobs_v2.json --shot SH_S2_09 --candidate <A> [<B>]

A candidate may be a browser screenshot of the Flow tile (no download is needed to review) or a filed 2K image.
ONE NVIDIA multimodal call per submit through the existing 14-key scheduler (animation_research_tool/nvidia_scheduler.py: key rotation, 429
cooldown and retries live there): one user message holding the review prompt, then the continuity sheet PREVIOUS | A | B | NEXT + reference
sheets, plus each candidate, as JPEG data URLs (long side <= 1600). Model MODEL; FALLBACK_MODEL only on a model-not-found 404/400.
ADVISORY ONLY: the reviewer advises, Claude and the owner decide.
Writes <A>__review.json (+ the sheet and the raw report). Fails closed per candidate: any BLOCK -> BLOCK; a missing answer, a missing verdict
or a verdict contradicting the answers -> UNSURE. CHOICE: only a PASS can be kept. Exit 0 PASS (keep), 1 BLOCK (fix), 3 UNSURE (stop, report), 2 refused."""
from __future__ import annotations

import argparse
import base64
import datetime
import io
import json
import re
import sys
import time
from pathlib import Path

import requests
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from neighbour_sheet import build_sheet  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]                 # D:\aai work
SCHED_DIR = ROOT / "animation_research_tool"
ENV_FILE = SCHED_DIR / ".env"                               # the .env nvidia_scheduler.py reads
_dont_write = sys.dont_write_bytecode
sys.dont_write_bytecode = True                              # keep the scheduler folder free of new .pyc files
sys.path.append(str(SCHED_DIR))
try:
    from nvidia_scheduler import NvidiaScheduler, load_env_keys  # noqa: E402
finally:
    sys.dont_write_bytecode = _dont_write

MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"          # primary (owner 2026-11-08: Super VL replaces omni)
FALLBACK_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"  # used only on a model-not-found 404/400
TEMPERATURE, TOP_P, SEED, MAX_TOKENS = 0.0, 1.0, 108, 8192
SEP = chr(10) * 2 + "=== PASS 2 ===" + chr(10) * 2
PASSES = 2        # owner 2026-11-08: stricter and stronger. Two independent passes (different seeds); a candidate is PASS only if BOTH passes pass (worst answer per question wins)
IMG_SIDE, IMG_QUALITY = 1600, 85
_http_post = requests.post                                  # the scheduler's transport; tests replace it

QUESTIONS = [
    ("Q1", "PEOPLE: exactly {n} visible people, each once, nobody extra (count partial figures and tiny distant people too; on a REFERENCE SHEET the repeated views or panels of the same character are ONE person and are never a defect; in a WIDE or HIGH-ANGLE shot where the character is small, judge identity by silhouette and colours (hair shape, feather, skin colour, costume colours, sash) and do NOT block for details too small to read, such as the tilak, pearls, flute or eye shape); each person's face, age, build and clothes match the reference sheet and the sentence in the prompt"),
    ("Q2", "ACTION AND GAZE: each person does what the prompt's action text says and looks where it says (a left/right hand choice is NOT a blocker unless the prompt requires it)"),
    ("Q3", "PLACE AND PROPS: same place and props as the place sheet and the neighbouring shots; every prop the prompt names is present and in the stated state"),
    ("Q4", "CONTINUITY: the candidate cuts cleanly from PREVIOUS and into NEXT: same place, same clothes, the same props beside each person, consistent positions and facing, same light and time of day. A prop's left/right side compared with a neighbour taken from a DIFFERENT camera angle or framing (close-up vs wide) is ADVISORY, not a blocker, unless the prompt states the side; if the two neighbours disagree with each other, follow the prompt"),
    ("Q5", "STYLE AND FRAME: Indian classical figure proportions and faces with 2D cel-shaded anime rendering (clean ink lines, cel shading with hard-edged shadow planes, motivated light, painterly background depth). BLOCK if it reads as a generic Japanese anime character, as Western cartoon, 3D/plastic CGI or photoreal, or if it has no cel-shaded rendering at all; the framing and layout the prompt asks for (a reference sheet's panels count as one frame); no text, letters, border or modern objects. The small four-point Flow sparkle watermark in the lower-right corner is REMOVED LATER by the studio's watermark tool: it is NEVER a defect, a blocker or an advisory; do not mention it"),
    ("Q6", "STORY FIT: nothing invented beyond the prompt (no extra people, props or actions that change the story)"),
    ("Q7", "ANATOMY AND TEXT: every person has the right number of heads, eyes, arms, hands and fingers as in the sheet and the prompt (a four-armed deity has exactly four distinct arms, no merged, doubled, missing or melted limbs, hands with five readable fingers or a clean mudra), natural pose, no warped faces, AND no readable or letter-like glyphs, captions, labels, logos or fake script anywhere unless the prompt asks for them (BLOCK on any visible letters, even small drifting ones)"),
    ("Q8", "COLOUR AND CANON: skin, clothes, jewellery, eyes and props use the colours of the reference sheets and the style palette (no off-palette skin tint, no recoloured hands or garments, no extra ornaments that the sheet does not show, no pale or plastic 3D look)"),
]
STRICT = ("BE STRICT. This is a quality gate for a paid production, not a courtesy review. Look at the picture at full size, zone by zone (face, hands, props, background edges), before answering. "
          "A visible defect or a doubt about one = BLOCK, never PASS. PASS only when you actually checked the item and found it correct. Each reason must name what you SAW (for example 'four arms: sword, trident, bowl, open palm'), "
          "never just 'ok' or 'matches'. Use UNSURE only when the picture cannot be seen at all.")
FIELDS = ("VERDICT", "FIX", "EDIT_INSTRUCTION", "REGEN_SENTENCE")


def review_prompt(job: dict, labels: list) -> str:
    qs = "\n".join(f"{q}: {t.format(n=job['people_count'])}" for q, t in QUESTIONS)
    prev, nxt = job.get("previous_shot") or {}, job.get("next_shot") or {}
    shown = " | ".join(["PREVIOUS (" + prev.get("flow_title", "none") + ")"] + [f"CANDIDATE {l}" for l in labels] + ["NEXT (" + nxt.get("flow_title", "none") + ")"])
    full = ", ".join(f"image {k + 2} = CANDIDATE {l} at full size" for k, l in enumerate(labels))
    return f"""You are a READ-ONLY image reviewer. Do not create, edit, move or delete any file and do not run commands that change anything.

{STRICT}

Image 1 is a continuity sheet, top row: {shown}; bottom row: the reference sheets (characters, then the place, then story props: compare props with their sheet exactly).
IGNORE the small Flow sparkle watermark at the lower right of every picture: the studio removes it afterwards with its own watermark tool, so it is never a defect, never a blocker and never an advisory, and a candidate must never be blocked, edited or regenerated because of it. Then {full}: judge faces, clothes, hands and small details there.

Every candidate was made from this prompt (the contract):
<<<{job['prompt']}>>>

For EACH candidate ({', '.join(labels)}) answer every question with exactly one line `<L> Q<n>: PASS|BLOCK|ADVISORY|UNSURE - <short reason>` where <L> is the candidate letter written plainly WITHOUT angle brackets or the word candidate (for example `A Q1: PASS - one person, open vest`). Answer ALL six questions Q1 to Q6 for EACH candidate BEFORE the FIX lines, in the final answer (not only inside your thinking).
BLOCK = a wrong, extra or missing person, wrong clothes/age/face against the sheet, wrong action or facing, place jump, a needed prop missing, wrong framing, text/inset/border, wrong style, or a cut that does not match the neighbours. ADVISORY = a harmless detail the prompt does not fix. UNSURE = you cannot see it well enough.
{qs}

Then for EACH candidate exactly these lines:
<L> FIX: none | edit | regenerate      (edit = one local defect in a good composition; regenerate = wrong person/identity/age/framing/pose)
<L> EDIT_INSTRUCTION: Change only <the defect>. Keep everything else exactly the same: <people, pose, place, props, style>.   (or: none)
<L> REGEN_SENTENCE: <one sentence to add to the prompt that fixes it>   (or: none)
<L> VERDICT: PASS | BLOCK | UNSURE"""


def parse(text: str, label: str = "") -> dict:
    """The answers of one candidate. `label` "A"/"B" reads the `A Q1: ...` lines; "" reads unlabelled lines."""
    pre = rf"[<*`\[]*(?:candidate\s+)?{re.escape(label)}[>*`\]]*[:\s]+" if label else ""
    answers = {m[1]: {"result": m[2], "reason": m[3].strip()}
               for m in re.finditer(rf"^\s*{pre}(Q[1-8])\s*[:\-]\s*(PASS|BLOCK|ADVISORY|UNSURE)\b\s*[-:]?\s*(.*)$", text or "", re.M)}
    fields = {m[1]: m[2].strip() for m in re.finditer(rf"^\s*{pre}({'|'.join(FIELDS)})\s*:\s*(.*)$", text or "", re.M)}
    missing = [q for q, _ in QUESTIONS if q not in answers]
    results = [a["result"] for a in answers.values()]
    derived = "BLOCK" if "BLOCK" in results else ("UNSURE" if missing or "UNSURE" in results else "PASS")
    stated = fields["VERDICT"].split()[0].upper() if fields.get("VERDICT") else None
    verdict = derived if stated == derived else ("BLOCK" if derived == "BLOCK" else "UNSURE")
    fix = (fields.get("FIX") or "none").split()[0].lower() if fields.get("FIX") else "none"
    if fix not in ("none", "edit", "regenerate"):
        fix = "regenerate"
    ins = fields.get("EDIT_INSTRUCTION", "")
    if fix == "edit" and not (ins.startswith("Change only") and "Keep everything else exactly the same" in ins):
        fix = "regenerate"                                        # an unusable edit instruction never reaches Flow
    if verdict == "BLOCK" and fix == "none":
        fix = "regenerate"
    regen = fields.get("REGEN_SENTENCE")
    return {"verdict": verdict, "stated_verdict": stated, "answers": answers, "missing": missing, "fix": fix if verdict == "BLOCK" else "none",
            "edit_instruction": ins if verdict == "BLOCK" and fix == "edit" else None, "regen_sentence": regen if regen and regen.lower() != "none" else None}


_RANK = {"PASS": 0, "ADVISORY": 1, "UNSURE": 2, "BLOCK": 3}


def expected_ratio(job: dict):
    """Width/height the picture must have: keyframes are 9:16 portrait, sheets and plates 16:9 landscape (owner 2026-11-08: always keep the ratios in mind)."""
    prompt = job.get("prompt", "")
    if "Portrait 9:16" in prompt or job.get("aspect") == "9:16" or str(job.get("model", {}).get("aspect", "")).startswith("9:16"):
        return 9 / 16
    if "16:9" in prompt or job.get("aspect") == "16:9":
        return 16 / 9
    return None


def ratio_problem(job: dict, path) -> str | None:
    want = expected_ratio(job)
    if want is None:
        return None
    with Image.open(path) as im:
        w, h = im.size
    got = w / h
    return None if abs(got - want) / want <= 0.03 else f"wrong aspect ratio {w}x{h} ({got:.3f}), expected {want:.3f} ({'9:16' if want < 1 else '16:9'})"


def merge_passes(runs: list[dict]) -> dict:
    """Worst case of several passes over one candidate: any BLOCK blocks, any UNSURE (without a BLOCK) is UNSURE, per question the worst answer wins;
    the fix, edit and regen text come from the first blocking pass."""
    if len(runs) == 1:
        return runs[0]
    answers = {}
    for r in runs:
        for q, a in r["answers"].items():
            if q not in answers or _RANK[a["result"]] > _RANK[answers[q]["result"]]:
                answers[q] = a
    rank = {"PASS": 0, "UNSURE": 1, "BLOCK": 2}
    worst = max(runs, key=lambda r: rank[r["verdict"]])
    first_block = next((r for r in runs if r["verdict"] == "BLOCK"), worst)
    out = dict(worst, answers=answers, passes=[r["verdict"] for r in runs],
               missing=sorted({q for r in runs for q in r.get("missing", [])}),
               fix=first_block["fix"], edit_instruction=first_block["edit_instruction"], regen_sentence=first_block["regen_sentence"])
    if worst["verdict"] != "BLOCK" and any(r["verdict"] == "UNSURE" for r in runs):
        out["verdict"] = "UNSURE"
    return out


def choose(results: list[dict]) -> dict:
    """Only a PASS can be kept (fewest ADVISORY answers wins, then the first). No PASS -> BLOCK (fix it) if any BLOCK, else UNSURE (stop, report)."""
    passed = [r for r in results if r["verdict"] == "PASS"]
    if passed:
        best = min(passed, key=lambda r: sum(a["result"] == "ADVISORY" for a in r["answers"].values()))
        return {"decision": "PASS", "chosen": best["candidate"], "label": best.get("label")}
    if any(r["verdict"] == "BLOCK" for r in results):
        return {"decision": "BLOCK", "chosen": None, "fixes": [{"label": r.get("label"), "candidate": r["candidate"], "fix": r["fix"], "edit_instruction": r["edit_instruction"],
                                                                  "regen_sentence": r["regen_sentence"]} for r in results if r["verdict"] == "BLOCK"]}
    return {"decision": "UNSURE", "chosen": None}


def image_part(path) -> dict:
    """An image as a JPEG data URL, long side <= IMG_SIDE (keeps the request small)."""
    with Image.open(path) as src:
        im = src.convert("RGB")
    im.thumbnail((IMG_SIDE, IMG_SIDE))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=IMG_QUALITY)
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")}}


def strip_think(text: str) -> str:
    """The answer only: <think>...</think> blocks are dropped; a bare closing tag (opening tag in the prompt) cuts the reasoning before it;
    an unclosed <think> has no answer after it."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    return text.split("<think>", 1)[0].strip()


class _Params:
    """Wraps the scheduler's post: adds the fields its call() does not set (it hardcodes temperature 0.2) and notes a model-not-found reply."""

    def __init__(self, inner, seed=SEED):
        self.inner = inner
        self.seed = seed
        self.model_missing = False

    def __call__(self, url, **kwargs):
        kwargs["json"] = dict(kwargs["json"], temperature=TEMPERATURE, top_p=TOP_P, seed=self.seed, chat_template_kwargs={"enable_thinking": True})
        response = self.inner(url, **kwargs)
        low = (getattr(response, "text", "") or "").lower()
        if response.status_code in (400, 404) and ("not found" in low or "does not exist" in low):
            self.model_missing = True
        return response


def make_scheduler(keys: list, *, clock=time.monotonic, sleep=time.sleep, seed=SEED):
    params = _Params(_http_post, seed)
    return NvidiaScheduler(keys, model=MODEL, clock=clock, sleep=sleep, post=params), params


def call_review(parts: list, sched, params: _Params) -> dict:
    """ONE review call through the scheduler (it owns key rotation, 429 cooldown and retries). Falls back once to FALLBACK_MODEL on a model-not-found reply."""
    res = sched.call(parts, max_tokens=MAX_TOKENS)
    if res["status"] == "CLIENT_ERROR" and params.model_missing and sched.model == MODEL:
        sched.model, params.model_missing = FALLBACK_MODEL, False
        res = sched.call(parts, max_tokens=MAX_TOKENS)
    info = {"model": sched.model, "key_used": f"key {res['key_index']}" if "key_index" in res else None, "tries": sched.snapshot()["http_attempts"]}
    if res["status"] != "OK":
        code = f" HTTP {res['http_status']}" if res.get("http_status") else ""
        return {"error": f"scheduler {res['status']}{code}", **info}
    text = strip_think(res["text"])
    if not text:   # reasoning can eat max_tokens on a busy call: one more try before failing closed (2026-11-08, Super VL gave an empty reply once, then answered twice)
        res = sched.call(parts, max_tokens=MAX_TOKENS * 2)   # second try gets double room: the reasoning had used up the first budget
        text = strip_think(res["text"]) if res["status"] == "OK" else ""
    if not text:
        return {"error": "empty reply (no content outside <think>; reasoning may have used max_tokens)", **info}
    return {"text": text, "raw": res["text"], **info}


def review(job: dict, candidates, keys: list, *, clock=time.monotonic, sleep=time.sleep) -> dict:
    cands = [Path(candidates)] if isinstance(candidates, (str, Path)) else [Path(c) for c in candidates]
    labels = list("AB"[: len(cands)])
    base = cands[0]
    sheet = base.with_name(base.stem + "__neighbours.jpg")
    build_sheet(job, [str(c) for c in cands], sheet)
    report = base.with_name(base.stem + "__review.md")
    parts = [{"type": "text", "text": review_prompt(job, labels)}] + [image_part(p) for p in [sheet, *cands]]
    replies, texts = [], []
    for k in range(PASSES):
        sched, params = make_scheduler(keys, clock=clock, sleep=sleep, seed=SEED + k)
        reply = call_review(parts, sched, params)
        replies.append(reply)
        texts.append(reply.get("text") or "")
    reply, text = replies[0], texts[0]
    report.write_text(SEP.join(texts), encoding="utf-8")
    base.with_name(base.stem + "__raw.txt").write_text(SEP.join(r.get("raw") or "" for r in replies), encoding="utf-8")   # the full replies incl. thinking, for calibration
    results = []
    for lab, c in zip(labels, cands):
        runs = [parse(tx, lab) if tx.strip() else {"verdict": "UNSURE", "answers": {}, "missing": [q for q, _ in QUESTIONS], "fix": "none",
                                                   "edit_instruction": None, "regen_sentence": None, "error": rp.get("error") or "empty reply"}
                for tx, rp in zip(texts, replies)]
        r = merge_passes(runs)
        bad = ratio_problem(job, c)
        if bad:   # a wrong frame shape can never be kept, whatever the model says
            r = dict(r, verdict="BLOCK", fix="regenerate", edit_instruction=None, ratio_error=bad,
                     regen_sentence=r.get("regen_sentence") or "Generate the picture in the correct aspect ratio.")
        r.update(label=lab, candidate=str(c))
        results.append(r)
    out = {"shot_id": job["shot_id"], "flow_title": job["flow_title"], "results": results, "choice": choose(results), "sheet": str(sheet), "report": str(report),
           "model": reply["model"], "key_used": reply["key_used"], "tries": reply["tries"], "advisory_only": True, "backend": "nvidia-scheduler",
           "prompt_sha256": job["prompt_sha256"], "time": datetime.datetime.now().astimezone().isoformat()}
    errs = [rp["error"] for rp in replies if rp.get("error")]
    if errs:
        out["error"] = errs[0]
    base.with_name(base.stem + "__review.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", type=Path, required=True)
    ap.add_argument("--shot", required=True)
    ap.add_argument("--candidate", type=Path, required=True, nargs="+", help="one or both images of the x2 submit (screenshots are fine)")
    a = ap.parse_args(argv)
    job = next((j for j in json.loads(a.jobs.read_text(encoding="utf-8")) if j["shot_id"] == a.shot), None)
    if job is None or not all(c.is_file() for c in a.candidate) or len(a.candidate) > 2:
        print("REFUSED: shot not in the job file, a candidate file is missing, or more than two candidates")
        return 2
    try:
        keys = load_env_keys(ENV_FILE)
    except ValueError as e:
        print(f"REFUSED: {e}")
        return 2
    out = review(job, a.candidate, keys)
    for r in out["results"]:
        print(f"{r['label']} {r['verdict']}  fix={r['fix']}  regen={r['regen_sentence']}  edit={r['edit_instruction']}")
        for q, x in sorted(r.get("answers", {}).items()):
            print(f"  {q} {x['result']}: {x['reason'][:140]}")
        if r.get("ratio_error"):
            print("  RATIO BLOCK:", r["ratio_error"])
        if r.get("error"):
            print("  error:", r["error"])
    if out.get("error"):
        print("error:", out["error"])
    print(f"model: {out['model']}  {out['key_used']}  tries: {out['tries']}  advisory_only: True")
    print("CHOICE:", json.dumps(out["choice"], ensure_ascii=False))
    print("sheet:", out["sheet"])
    return {"PASS": 0, "BLOCK": 1}.get(out["choice"]["decision"], 3)


if __name__ == "__main__":
    sys.exit(main())
