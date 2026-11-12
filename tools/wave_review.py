"""Run the free review system (Dots + Luna medium via card_review.py, Super thinking-on via card_review_super.py) over the cards of the
2026-11-12 implementation checklist. No Claude calls. Writes card_results/RV-<card>.json (input), RV-<card>.review.json (verdicts).

  python tools/wave_review.py [--cards M-04 M-05 ...] [--workers 3]
"""
import argparse
import concurrent.futures
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "research", "card_results")
PLAN = "research/IMPLEMENTATION_CHECKLIST_2026-11-12.md"

CARDS = {
    "M-01": (["h3/v4_to_h3.py", "h3/schema_and_linter.py", "h3/compile_h3_sing8.py"], "h3/tests/test_prompt_wiring.py"),
    "M-02": (["h3/compile_h3_sing8.py", "h3/shot_mode.py", "director/shot_router.py", "director/build_h3_batch.py"], "h3/tests/test_m02_start_only.py"),
    "M-03": (["h3/v4_to_h3.py", "h3/schema_and_linter.py"], "h3/tests/test_opus_examples.py"),
    "M-04": (["director/blocking.py", "director/blocking_lint.py"], "director/test_blocking_11.py"),
    "M-05": (["director/MASTER_PROMPT_v2.4.md", "director/write_pack.py"], "director/test_master_prompt_v24.py"),
    "M-06": (["director/keyframe_jobs.py"], "director/test_keyframe_jobs_m06.py"),
    "M-07": (["director/script_pacing.py", "director/script_hook.py"], "director/test_script_pacing.py"),
    "M-09": (["h3/gate_d_audio.py"], "h3/tests/test_gate_d_no_silence.py"),
    "M-11": (["director/clip_qa.py"], "director/test_clip_qa_m11.py"),
    "M-12": (["director/write_timeline_lock.py", "director/timeline_lock_core.py"], "director/test_timeline_lock_m12.py"),
    "M-13": (["director/chain_step.py"], "director/test_chain_step.py"),
    "M-15": (["score/cue_sheet.py"], "score/tests/test_cue_sheet_rows.py"),
    "M-16": (["director/write_timeline_lock.py"], "director/test_write_timeline_lock.py"),
    "M-17": (["director/text_card_qa.py"], "director/test_text_card_qa.py"),
    "M-18": (["tools/animatic.py"], "tools/test_animatic.py"),
    "M-19": (["director/continuity_sheet.py", "flow/scripts/bible_to_sheet_jobs.py"], "director/test_continuity_sheet.py"),
    "M-23": (["director/story_shape.py", "director/write_pack_glue.py"], "director/test_story_shape.py"),
    "M-24": (["director/keyframe_gate.py", "director/build_h3_batch.py", "h3/render_controller.py"], "director/test_keyframe_gate_m24.py"),
    "M-25": (["director/pack_validator.py", "director/writer_prompts.py"], "director/test_pack_validator.py"),
    "M-26": (["director/build_final_reel.py", "director/run_colab_batch.py"], "director/test_m26_wiring.py"),
    "M-28": (["director/post_fetch_qa.py", "director/run_colab_batch.py"], "director/test_post_fetch_qa.py"),
}


def one(card):
    rv = "RV-" + card
    files, test = CARDS[card]
    json.dump({"plan": PLAN, "card": card, "files": files, "test_file": test, "edit_report": {"note": "implemented by a Claude subagent; see research/card_results/%s*.md" % card}},
              open(os.path.join(RES, rv + ".json"), "w", encoding="utf-8"), indent=1)
    r = subprocess.run([sys.executable, os.path.join(HERE, "card_review.py"), "--card", rv], capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    return card, (r.stdout.strip().splitlines() or [r.stderr.strip()[-200:]])[-1]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", nargs="*", default=list(CARDS))
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args(argv)
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for card, out in ex.map(one, a.cards):
            print(card, out, flush=True)
    r = subprocess.run([sys.executable, os.path.join(HERE, "card_review_super.py")] + ["RV-" + c for c in a.cards], capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    print("super:", r.stdout.strip()[-1500:], r.stderr.strip()[-300:], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
