"""Review finished gap cards with Nemotron Super, thinking ON and a big token budget, over the shared 14-key NVIDIA pool.
Replaces the Dots review where Dots had too little budget. One call per card, all cards in parallel.

  python tools/card_review_super.py W-03 W-09 X-04 ...        (writes research/card_results/<card>_review_super.md and <card>.super.json)
"""
import concurrent.futures
import json
import os
import pathlib
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "research", "card_results")
sys.path.insert(0, HERE)
sys.path.insert(0, "D:/aai work/animation_research_tool")
import card_runner

MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODULE_CAP = 16000
TEST_CAP = 12000


def read(rel, cap):
    try:
        text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
    except OSError:
        return "(missing)"
    return text if len(text) <= cap else text[:cap] + "\n...(cut)"


def build_prompt(res):
    plans = {"P3": "research/OPUS_PLAN_P3_BLOCKING_WRITER_ASSEMBLY_CLOSURE_2026-11-11.md",
             "P2": "research/OPUS_PLAN_P2_WIRING_2026-11-11.md"}
    plan = plans.get(res.get("plan"), res.get("plan") or "")
    try:
        card = card_runner.card_text(os.path.join(ROOT, plan), res["card"])
    except (OSError, SystemExit):
        card = "(no plan card text; owner spec) " + str(res.get("note") or res.get("card"))
    parts = ["You are a strict, hostile code reviewer for ONE gap-closure card of a Python animation pipeline. Think carefully, then list REAL "
             "defects only: a card requirement not met, a wrong result, a crash path, bad input that passes silently, a test that cannot "
             "fail or does not cover a test name the card lists. For each: quote the faulty line, say why it is wrong, give the exact fix. "
             "Do not invent problems, do not praise, ignore style. Note that delivery loudness is -14 LUFS from core/core.json since the "
             "owner decision of 2026-11-11 (a card text that says -16 is superseded). End with exactly one line: VERDICT: OK or "
             "VERDICT: FIX-FIRST.\n\nCARD (the problem statement):\n" + card]
    for rel in res.get("files", []):
        parts.append("MODULE " + rel + ":\n" + read(rel, MODULE_CAP))
    parts.append("TEST FILE " + res.get("test_file", "") + ":\n" + read(res.get("test_file", ""), TEST_CAP))
    return "\n\n".join(parts)


def call(prompt, state, tries=8):
    import requests
    last = ""
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 32000, "stream": False}
    for _ in range(tries):
        idx = state["pool"].acquire()
        try:
            resp = requests.post(URL, headers={"Authorization": "Bearer " + state["keys"][idx]}, json=body, timeout=(15, 1500))
        except requests.RequestException as exc:
            last = type(exc).__name__
            time.sleep(5)
            continue
        if resp.status_code == 429:
            state["pool"].cooldown(idx, 60)
            last = "429"
            continue
        if resp.status_code in (401, 403):
            state["pool"].disable(idx)
            last = "auth"
            continue
        if resp.status_code >= 400:
            last = "HTTP %d" % resp.status_code
            if resp.status_code < 500:
                break
            time.sleep(5)
            continue
        try:
            choice = resp.json()["choices"][0]
            text = re.sub(r"<think>.*?</think>", "", choice["message"].get("content") or "", flags=re.S).strip()
        except (ValueError, KeyError, IndexError):
            last = "bad json"
            continue
        if text:
            return text
        last = "empty (finish_reason %s)" % choice.get("finish_reason")
        body["max_tokens"] = min(body["max_tokens"] + 8000, 60000)      # the thinking ate the budget: ask again with more room
    return "NO_REVIEW: " + last


def review_one(card, state):
    res = json.load(open(os.path.join(RES, card + ".json"), encoding="utf-8"))
    text = call(build_prompt(res), state)
    out = os.path.join(RES, card + "_review_super.md")
    open(out, "w", encoding="utf-8").write(text)
    m = re.findall(r"VERDICT:\s*(OK|FIX-FIRST)", text)
    verdict = m[-1] if m else ("NO_REVIEW" if text.startswith("NO_REVIEW") else "UNCLEAR")
    json.dump({"card": card, "super": verdict}, open(os.path.join(RES, card + ".super.json"), "w"))
    return card, verdict


def main(argv=None):
    cards = list(argv if argv is not None else sys.argv[1:])
    if not cards:
        print(__doc__)
        return 2
    import key_pool
    from nvidia_scheduler import load_env_keys
    state = {"keys": load_env_keys(pathlib.Path("D:/aai work/animation_research_tool/.env")),
             "pool": key_pool.KeyPool("D:/aai work/anime_studio_merge/ledgers/nvidia_pool.json")}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(14, len(cards))) as ex:
        futs = [ex.submit(review_one, c, state) for c in cards]
        for f in concurrent.futures.as_completed(futs):
            try:
                print(*f.result(), flush=True)
            except Exception as exc:
                print("error", type(exc).__name__, exc, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
