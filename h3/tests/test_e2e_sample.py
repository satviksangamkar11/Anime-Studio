import json
import os

import pytest

import h3.e2e_sample as e2e
from h3.schema_and_linter import SHOT_KEYS

QUIET = lambda *a, **k: None  # noqa: E731


class FakeScheduler:
    """Stands in for NvidiaScheduler: replies in order (the last one repeats), records every prompt. No network."""

    def __init__(self, replies, status="OK"):
        self.replies, self.status, self.prompts = list(replies), status, []

    def call(self, content, *, max_tokens=3500):
        self.prompts.append(content)
        if self.status != "OK":
            return {"status": self.status, "text": "", "usage": None, "http_status": 404}
        text = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return {"status": "OK", "text": text, "usage": None}


def _valid():
    return json.dumps({"shots": e2e.build_shots()})


def _bad():
    shots = e2e.build_shots()
    shots[1]["timing_and_lattice"]["pixel_frames"] = 176   # PF-02: must be 17*6+5 = 107
    return json.dumps({"shots": shots})


def _ready_count(out):
    with open(os.path.join(out, "build", e2e.EPISODE_ID, "readiness.json"), encoding="utf-8") as f:
        return json.load(f)["totals"]["ready"]


def test_offline_end_to_end_is_3_of_3_ready(tmp_path):
    out = str(tmp_path / "e2e")
    res = e2e.run_e2e(out_dir=out, offline=True, log=QUIET)
    assert res["exit_code"] == 0 and res["ready"] == 3 and res["total"] == 3 and res["rounds"] == 0
    assert _ready_count(out) == 3
    assert os.path.isfile(res["story_path"])
    pics = os.listdir(os.path.join(out, "pics"))
    assert sorted(pics) == sorted(["e2e_s1_start.png", "e2e_s1_end.png", "e2e_s2_start.png",
                                   "e2e_s2_end.png", "e2e_s3_end.png"])


def test_offline_main_prints_the_summary_line(tmp_path, capsys):
    assert e2e.main(["--offline", "--out-dir", str(tmp_path / "m")]) == 0
    text = capsys.readouterr().out
    assert "E2E: rounds=0 ready=3/3" in text and "no model call" in text


def test_repair_loop_fixes_on_the_second_round(tmp_path):
    fake = FakeScheduler([_bad(), _valid()])
    res = e2e.run_e2e(out_dir=str(tmp_path / "r"), scheduler=fake, log=QUIET)
    assert res["exit_code"] == 0 and res["rounds"] == 2 and res["ready"] == 3
    assert len(fake.prompts) == 2
    assert "LINT MESSAGES" not in fake.prompts[0] and "LINT MESSAGES" in fake.prompts[1]
    assert "PF-02" in fake.prompts[1] and "RULES:" in fake.prompts[1]


def test_gives_up_after_four_repair_rounds_and_reports_codes(tmp_path):
    fake = FakeScheduler([_bad()])
    res = e2e.run_e2e(out_dir=str(tmp_path / "g"), scheduler=fake, log=QUIET)
    assert res["exit_code"] == 1 and res["rounds"] == 5 and len(fake.prompts) == 5
    assert res["ready"] == 0 and "PF-02" in res["codes"]


def test_unparseable_reply_is_a_repair_round(tmp_path):
    fake = FakeScheduler(["sorry, here is some prose", _valid()])
    res = e2e.run_e2e(out_dir=str(tmp_path / "p"), scheduler=fake, log=QUIET)
    assert res["exit_code"] == 0 and res["rounds"] == 2
    assert "PARSE reply is not valid JSON" in fake.prompts[1]


def test_think_block_and_code_fence_are_stripped(tmp_path):
    fake = FakeScheduler(["<think>plan the shots</think>\n```json\n" + _valid() + "\n```"])
    res = e2e.run_e2e(out_dir=str(tmp_path / "f"), scheduler=fake, log=QUIET)
    assert res["exit_code"] == 0 and res["rounds"] == 1


def test_scheduler_error_stops_at_once(tmp_path):
    fake = FakeScheduler([_valid()], status="CLIENT_ERROR")
    res = e2e.run_e2e(out_dir=str(tmp_path / "s"), scheduler=fake, log=QUIET)
    assert res["exit_code"] == 1 and res["rounds"] == 1 and len(fake.prompts) == 1


def test_missing_keys_refuse_without_any_call(tmp_path, monkeypatch):
    def no_keys():
        raise ValueError("Expected 14 distinct NVIDIA_API_KEY_01..14 values")
    monkeypatch.setattr(e2e, "live_scheduler", no_keys)
    res = e2e.run_e2e(out_dir=str(tmp_path / "k"), log=QUIET)
    assert res["exit_code"] == 1 and res["rounds"] == 0


def test_bad_picture_path_is_rejected_before_any_file_is_written(tmp_path):
    shots = e2e.build_shots()
    shots[0]["fl2va_keyframes"]["picture_1_path"] = "../escape.png"
    shots_out, messages = e2e.check_reply(json.dumps({"shots": shots}), str(tmp_path))
    assert shots_out is None and messages and messages[0].startswith("PATH picture_1_path")
    assert not os.path.exists(tmp_path.parent / "escape.png")


def test_prompt_carries_exact_key_names_and_the_blueprint():
    p = e2e.build_prompt("a made-up premise")
    for key in SHOT_KEYS:
        assert key in p
    assert '"pixel_frames": 107' in p and '"lattice_n": 6' in p
    assert "DYNAMIC_MATCH_ON_ACTION" in p and "CHAINED_POSE_HOLD" in p
