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
IMG_SIDE, IMG_QUALITY = 1600, 85
_http_post = requests.post                                  # the scheduler's transport; tests replace it

QUESTIONS = [
    ("Q1", "PEOPLE: exactly {n} visible people, each once, nobody extra (count partial figures and tiny distant people too; on a REFERENCE SHEET the repeated views or panels of the same character are ONE person and are never a defect; in a WIDE or HIGH-ANGLE shot where the character is small, judge identity by silhouette and colours (hair shape, feather, skin colour, costume colours, sash) and do NOT block for details too small to read, such as the tilak, pearls, flute or eye shape); each person's face, age, build and clothes match the reference sheet and the sentence in the prompt"),
    ("Q2", "ACTION AND GAZE: each person does what the prompt's action text says and looks where it says (a left/right hand choice is NOT a blocker unless the prompt requires it)"),
    ("Q3", "PLACE AND PROPS: same place and props as the place sheet and the neighbouring shots; every prop the prompt names is present and in the stated state"),
    ("Q4", "CONTINUITY: the candidate cuts cleanly from PREVIOUS and into NEXT: same place, same clothes, the same props beside each person, consistent positions and facing, same light and time of day. A prop's left/right side compared with a neighbour taken from a DIFFERENT camera angle or framing (close-up vs wide) is ADVISORY, not a blocker, unless the prompt states the side; if the two neighbours disagree with each other, follow the prompt"),
    ("Q5", "STYLE AND FRAME: Indian classical figure proportions and faces with 2D cel-shaded anime rendering (clean ink lines, cel shading with hard-edged shadow planes, motivated light, painterly background depth). BLOCK if it reads as a generic Japanese anime character, as Western cartoon, 3D/plastic CGI or photoreal, or if it has no cel-shaded rendering at all; the framing and layout the prompt asks for (a reference sheet's panels count as one frame); no text, letters, border or modern objects. The small four-point Flow sparkle watermark in the lower-right corner is REMOVED LATER by the studio's watermark tool: it is NEVER a defect, a blocker or an advisory; do not mention it"),
    ("Q6", "STORY FIT: nothing invented beyond the prompt (no extra people, props or actions that change the story)"),
]
FIELDS = ("VERDICT", "FIX", "EDIT_INSTRUCTION", "REGEN_SENTENCE")


def review_prompt(job: dict, labels: list) -> str:
    qs = "\n".join(f"{q}: {t.format(n=job['people_count'])}" for q, t in QUESTIONS)
    prev, nxt = job.get("previous_shot") or {}, job.get("next_shot") or {}
    shown = " | ".join(["PREVIOUS (" + prev.get("flow_title", "none") + ")"] + [f"CANDIDATE {l}" for l in labels] + ["NEXT (" + nxt.get("flow_title", "none") + ")"])
    full = ", ".join(f"image {k + 2} = CANDIDATE {l} at full size" for k, l in enumerate(labels))
    return f"""You are a READ-ONLY image reviewer. Do not create, edit, move or delete any file and do not run commands that change anything.

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
               for m in re.finditer(rf"^\s*{pre}(Q[1-6])\s*[:\-]\s*(PASS|BLOCK|ADVISORY|UNSURE)\b\s*[-:]?\s*(.*)$", text or "", re.M)}
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

    def __init__(self, inner):
        self.inner = inner
        self.model_missing = False

    def __call__(self, url, **kwargs):
        kwargs["json"] = dict(kwargs["json"], temperature=TEMPERATURE, top_p=TOP_P, seed=SEED, chat_template_kwargs={"enable_thinking": True})
        response = self.inner(url, **kwargs)
        low = (getattr(response, "text", "") or "").lower()
        if response.status_code in (400, 404) and ("not found" in low or "does not exist" in low):
            self.model_missing = True
        return response


def make_scheduler(keys: list, *, clock=time.monotonic, sleep=time.sleep):
    params = _Params(_http_post)
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
        res = sched.call(parts, max_tokens=MAX_TOKENS)
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
    sched, params = make_scheduler(keys, clock=clock, sleep=sleep)
    reply = call_review(parts, sched, params)
    text = reply.get("text") or ""
    report.write_text(text, encoding="utf-8")
    base.with_name(base.stem + "__raw.txt").write_text(reply.get("raw") or "", encoding="utf-8")   # the full reply incl. thinking, for calibration
    results = []
    for lab, c in zip(labels, cands):
        r = parse(text, lab) if text.strip() else {"verdict": "UNSURE", "answers": {}, "missing": [q for q, _ in QUESTIONS], "fix": "none",
                                                   "edit_instruction": None, "regen_sentence": None, "error": reply.get("error") or "empty reply"}
        r.update(label=lab, candidate=str(c))
        results.append(r)
    out = {"shot_id": job["shot_id"], "flow_title": job["flow_title"], "results": results, "choice": choose(results), "sheet": str(sheet), "report": str(report),
           "model": reply["model"], "key_used": reply["key_used"], "tries": reply["tries"], "advisory_only": True, "backend": "nvidia-scheduler",
           "prompt_sha256": job["prompt_sha256"], "time": datetime.datetime.now().astimezone().isoformat()}
    if reply.get("error"):
        out["error"] = reply["error"]
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
