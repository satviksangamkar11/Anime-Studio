"""Codex review of the x2 candidates of one Flow submit against the job, the reference sheets and the previous/next shots (universal Flow image system, 2026-11-01).

  python scripts/flow/review_shot.py --jobs canon/drafts/A1_flow_jobs_v2.json --shot SH_S2_09 --candidate <A> [<B>]

A candidate may be a browser screenshot of the Flow tile (no download is needed to review) or a filed 2K image.
ONE Codex call per submit (owner 2026-11-01: least tokens, no shortcut): the continuity sheet PREVIOUS | A | B | NEXT + reference sheets,
plus each candidate at full size. Codex: model gpt-6-luna, reasoning effort medium, READ-ONLY. Every question is answered for every candidate.
Writes <A>__review.json (+ the sheet and the raw report). Fails closed per candidate: any BLOCK -> BLOCK; a missing answer, a missing verdict
or a verdict contradicting the answers -> UNSURE. CHOICE: only a PASS can be kept. Exit 0 PASS (keep), 1 BLOCK (fix), 3 UNSURE (stop, report), 2 refused."""
from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from neighbour_sheet import build_sheet  # noqa: E402

MODEL, EFFORT = "gpt-6-luna", "medium"   # anime studio copy: owner 2026-11-05 asked for GPT Luna medium
QUESTIONS = [
    ("Q1", "PEOPLE: exactly {n} visible people, each once, nobody extra (count partial figures and tiny distant people too; on a REFERENCE SHEET the repeated views or panels of the same character are ONE person and are never a defect); each person's face, age, build and clothes match the reference sheet and the sentence in the prompt"),
    ("Q2", "ACTION AND GAZE: each person does what the prompt's action text says and looks where it says (a left/right hand choice is NOT a blocker unless the prompt requires it)"),
    ("Q3", "PLACE AND PROPS: same place as the place sheet and the neighbouring shots (house, door, step, road, well, trough, trees); every prop the prompt names is present and in the stated state"),
    ("Q4", "CONTINUITY: the candidate cuts cleanly from PREVIOUS and into NEXT: same place, same clothes, the same props beside each person, consistent positions and facing, same light and time of day. A prop's left/right side compared with a neighbour taken from a DIFFERENT camera angle or framing (close-up vs wide) is ADVISORY, not a blocker, unless the prompt states the side; if the two neighbours disagree with each other, follow the prompt"),
    ("Q5", "STYLE AND FRAME: Indian-first, with a light anime touch: Indian faces, proportions, costume, ornaments and setting (Indian painting and devotional iconography), drawn with anime craft: clean variable-weight ink lines, expressive anime eyes, cel shading with hard-edged shadow planes, motivated light, painterly background depth. BLOCK if it reads as a generic Japanese anime character, as Western cartoon, 3D/plastic CGI or photoreal, or if it has no anime craft at all; the framing and layout the prompt asks for (a reference sheet's panels count as one frame); no text, letters, border or modern objects. The small four-point Flow sparkle watermark in the lower-right corner is REMOVED LATER by the studio's watermark tool: it is NEVER a defect, a blocker or an advisory; do not mention it"),
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

For EACH candidate ({', '.join(labels)}) answer every question with exactly one line `<candidate> Q<n>: PASS|BLOCK|ADVISORY|UNSURE - <short reason>` (for example `A Q1: PASS - one person, open vest`).
BLOCK = a wrong, extra or missing person, wrong clothes/age/face against the sheet, wrong action or facing, place jump, a needed prop missing, wrong framing, text/inset/border, wrong style, or a cut that does not match the neighbours. ADVISORY = a harmless detail the prompt does not fix. UNSURE = you cannot see it well enough.
{qs}

Then for EACH candidate exactly these lines:
<candidate> FIX: none | edit | regenerate      (edit = one local defect in a good composition; regenerate = wrong person/identity/age/framing/pose)
<candidate> EDIT_INSTRUCTION: Change only <the defect>. Keep everything else exactly the same: <people, pose, place, props, style>.   (or: none)
<candidate> REGEN_SENTENCE: <one sentence to add to the prompt that fixes it>   (or: none)
<candidate> VERDICT: PASS | BLOCK | UNSURE
Use plain words only; never write the words loincloth, naked, bare, bandi, digambar or Maharaj (say "the young ascetic", "short white cloth wrapped at the hips, legs uncovered")."""


def parse(text: str, label: str = "") -> dict:
    """The answers of one candidate. `label` "A"/"B" reads the `A Q1: ...` lines; "" reads unlabelled lines."""
    pre = rf"{re.escape(label)}\s+" if label else ""
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


def codex_command(images: list, out: Path, codex: str | None = None) -> list:
    exe = codex or shutil.which("codex.cmd") or shutil.which("codex") or "codex"
    cmd = [exe, "exec", "-m", MODEL, "-c", f"model_reasoning_effort={EFFORT}", "-s", "read-only", "--skip-git-repo-check", "-o", str(out)]
    for i in images:
        cmd += ["-i", str(i)]
    return cmd + ["-"]


def run_codex(cmd: list, prompt: str, timeout: int = 900) -> tuple[int, str]:
    p = subprocess.run(cmd, input=prompt, text=True, encoding="utf-8", capture_output=True, timeout=timeout)
    return p.returncode, p.stderr[-2000:]


def review(job: dict, candidates, runner=run_codex) -> dict:
    cands = [Path(candidates)] if isinstance(candidates, (str, Path)) else [Path(c) for c in candidates]
    labels = list("AB"[: len(cands)])
    base = cands[0]
    sheet = base.with_name(base.stem + "__neighbours.jpg")
    build_sheet(job, [str(c) for c in cands], sheet)
    report = base.with_name(base.stem + "__review.md")
    code, err = runner(codex_command([sheet, *cands], report), review_prompt(job, labels))
    text = report.read_text(encoding="utf-8") if report.is_file() else ""
    results = []
    for lab, c in zip(labels, cands):
        r = parse(text, lab) if code == 0 and text.strip() else {"verdict": "UNSURE", "answers": {}, "missing": [q for q, _ in QUESTIONS], "fix": "none",
                                                               "edit_instruction": None, "regen_sentence": None, "error": f"codex exit {code}: {err[-400:]}"}
        r.update(label=lab, candidate=str(c))
        results.append(r)
    out = {"shot_id": job["shot_id"], "flow_title": job["flow_title"], "results": results, "choice": choose(results), "sheet": str(sheet), "report": str(report),
           "model": MODEL, "effort": EFFORT, "prompt_sha256": job["prompt_sha256"], "time": datetime.datetime.now().astimezone().isoformat()}
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
    out = review(job, a.candidate)
    for r in out["results"]:
        print(f"{r['label']} {r['verdict']}  fix={r['fix']}  regen={r['regen_sentence']}  edit={r['edit_instruction']}")
        for q, x in sorted(r.get("answers", {}).items()):
            print(f"  {q} {x['result']}: {x['reason'][:140]}")
        if r.get("error"):
            print("  error:", r["error"])
    print("CHOICE:", json.dumps(out["choice"], ensure_ascii=False))
    print("sheet:", out["sheet"])
    return {"PASS": 0, "BLOCK": 1}.get(out["choice"]["decision"], 3)


if __name__ == "__main__":
    sys.exit(main())
