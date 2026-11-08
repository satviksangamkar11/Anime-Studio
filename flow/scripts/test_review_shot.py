"""review_shot (NVIDIA reviewer through the existing scheduler): fake HTTP post, no network, fake clock (no real waits).
Temp folders only; fake images made with PIL. Keys are placeholders, never printed."""
import base64
import io
import json
import sys
from pathlib import Path

import pytest
import requests
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import review_shot as rs  # noqa: E402

KEYS14 = [f"TEST-NOT-A-REAL-KEY-{i:02d}" for i in range(1, 15)]   # placeholders, not API keys
KEYS = KEYS14[:3]
PARTS = [{"type": "text", "text": "review"}]


@pytest.fixture(autouse=True)
def no_real_keys(monkeypatch):
    for name in [f"NVIDIA_API_KEY_{i:02d}" for i in range(1, 15)] + ["NVIDIA_API_KEY"]:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def env14(tmp_path_factory, monkeypatch):
    """A complete 14-key .env in its own temp folder (kept out of the job and output folders)."""
    env = tmp_path_factory.mktemp("keys") / ".env"
    env.write_text("".join(f"NVIDIA_API_KEY_{i:02d}={k}\n" for i, k in enumerate(KEYS14, 1)), encoding="utf-8")
    monkeypatch.setattr(rs, "ENV_FILE", env)
    return KEYS14


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


class FakeResponse:
    def __init__(self, status, body=None, text=None, headers=None):
        self.status_code = status
        self._body = body
        self.text = text if text is not None else json.dumps(body)
        self.headers = headers or {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def ok(text):
    return FakeResponse(200, body={"choices": [{"message": {"content": text}}]})


def canned(label="A", verdict="PASS", blocked=()):
    lines = [f"{label} {q}: {'BLOCK' if q in blocked else 'PASS'} - checked {q}" for q in ("Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8")]
    lines += [f"{label} FIX: none", f"{label} EDIT_INSTRUCTION: none", f"{label} REGEN_SENTENCE: none", f"{label} VERDICT: {verdict}"]
    return "\n".join(lines)


def partial(label="A"):
    return "\n".join(line for line in canned(label).splitlines() if not line.startswith((f"{label} Q7", f"{label} Q8")))


def make_jpg(path, size=(640, 480)):
    Image.new("RGB", size, (120, 60, 200)).save(path, "JPEG", quality=90)
    return path


def job_dict():
    return {"shot_id": "SH_T_01", "flow_title": "TEST_SHOT__v01", "prompt": "One test figure.", "prompt_sha256": "0" * 64,
            "people_count": 1, "previous_shot": None, "next_shot": None, "sheets": []}


def job_file(tmp_path):
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps([job_dict()]), encoding="utf-8")
    return jobs


def test_think_block_is_dropped_before_parse():
    raw = "<think>draft: A Q1: BLOCK - wrong\nA Q2: BLOCK - x</think>\n" + canned("A")
    text = rs.strip_think(raw)
    assert "<think>" not in text and "wrong" not in text
    r = rs.parse(text, "A")
    assert r["verdict"] == "PASS" and r["missing"] == []
    assert r["answers"]["Q1"]["reason"] == "checked Q1"


def test_bare_closing_tag_and_unclosed_block():
    assert rs.parse(rs.strip_think("A Q1: BLOCK - reasoning\n</think>\n" + canned("A")), "A")["verdict"] == "PASS"
    assert rs.strip_think("<think>only reasoning A Q1: PASS") == ""


def test_429_waits_then_next_key_answers(monkeypatch):
    clock, seen = FakeClock(), []

    def post(url, **kw):
        seen.append(kw["headers"]["Authorization"])
        return FakeResponse(429, text="rate limited") if len(seen) == 1 else ok(canned("A"))

    monkeypatch.setattr(rs, "_http_post", post)
    sched, params = rs.make_scheduler(KEYS, clock=clock, sleep=clock.sleep)
    t0 = clock()
    res = rs.call_review(PARTS, sched, params)
    assert seen == [f"Bearer {KEYS[0]}", f"Bearer {KEYS[1]}"]
    assert res["key_used"] == "key 2" and res["tries"] == 2 and "A Q1" in res["text"]
    assert clock() - t0 >= 60                                   # no Retry-After header: the scheduler's 60 s cooldown


def test_three_429s_give_up_with_error(monkeypatch):
    clock, seen = FakeClock(), []

    def post(url, **kw):
        seen.append(1)
        return FakeResponse(429, text="slow down")

    monkeypatch.setattr(rs, "_http_post", post)
    sched, params = rs.make_scheduler(KEYS, clock=clock, sleep=clock.sleep)
    res = rs.call_review(PARTS, sched, params)
    assert len(seen) == 3 and "text" not in res and res["error"] == "scheduler RATE_LIMITED"


def test_model_not_found_404_falls_back(monkeypatch):
    models = []

    def post(url, **kw):
        models.append(kw["json"]["model"])
        return FakeResponse(404, text='{"detail": "model not found"}') if kw["json"]["model"] == rs.MODEL else ok(canned("A"))

    monkeypatch.setattr(rs, "_http_post", post)
    clock = FakeClock()
    sched, params = rs.make_scheduler(KEYS, clock=clock, sleep=clock.sleep)
    res = rs.call_review(PARTS, sched, params)
    assert models == [rs.MODEL, rs.FALLBACK_MODEL]
    assert res["model"] == rs.FALLBACK_MODEL and "A Q1" in res["text"]


def test_empty_reply_is_retried_once(monkeypatch):
    replies = [ok("<think>only thinking</think>"), ok(canned("A"))]
    monkeypatch.setattr(rs, "_http_post", lambda url, **kw: replies.pop(0))
    clock = FakeClock()
    sched, params = rs.make_scheduler(KEYS, clock=clock, sleep=clock.sleep)
    res = rs.call_review(PARTS, sched, params)
    assert "A Q1" in res["text"] and not replies


def test_other_client_error_does_not_fall_back(monkeypatch):
    models = []

    def post(url, **kw):
        models.append(kw["json"]["model"])
        return FakeResponse(400, text="bad request: unknown field")

    monkeypatch.setattr(rs, "_http_post", post)
    clock = FakeClock()
    sched, params = rs.make_scheduler(KEYS, clock=clock, sleep=clock.sleep)
    res = rs.call_review(PARTS, sched, params)
    assert models == [rs.MODEL] and res["error"] == "scheduler CLIENT_ERROR HTTP 400"


def test_review_payload_fields_and_image_parts(tmp_path, monkeypatch):
    sent = []

    def post(url, **kw):
        sent.append((url, kw))
        return ok(canned("A"))

    monkeypatch.setattr(rs, "_http_post", post)
    big = tmp_path / "cand.png"
    Image.new("RGB", (3000, 2000), (10, 200, 30)).save(big)
    rs.review(job_dict(), [big], KEYS, clock=FakeClock(), sleep=lambda s: None)
    url, kw = sent[0]
    body = kw["json"]
    assert url.endswith("/v1/chat/completions")
    assert body["model"] == rs.MODEL and body["stream"] is False and body["max_tokens"] == rs.MAX_TOKENS
    assert body["temperature"] == 0.0 and body["top_p"] == 1.0 and body["seed"] == 108
    assert body["chat_template_kwargs"] == {"enable_thinking": True}
    msg = body["messages"][0]
    assert msg["role"] == "user" and msg["content"][0]["type"] == "text" and len(msg["content"]) == 3
    for part in msg["content"][1:]:
        assert part["type"] == "image_url" and part["image_url"]["url"].startswith("data:image/jpeg;base64,")
        im = Image.open(io.BytesIO(base64.b64decode(part["image_url"]["url"].split(",", 1)[1])))
        assert im.format == "JPEG" and max(im.size) <= 1600


def test_missing_answers_give_unsure(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "_http_post", lambda url, **kw: ok(partial("A")))
    cand = make_jpg(tmp_path / "cand.jpg")
    out = rs.review(job_dict(), [cand], KEYS, clock=FakeClock(), sleep=lambda s: None)
    assert out["results"][0]["verdict"] == "UNSURE" and out["results"][0]["missing"] == ["Q7", "Q8"]
    assert out["choice"]["decision"] == "UNSURE"


def test_empty_reply_gives_unsure_with_error(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "_http_post", lambda url, **kw: FakeResponse(200, body={"choices": [{"message": {"content": None}}]}))
    cand = make_jpg(tmp_path / "cand.jpg")
    out = rs.review(job_dict(), [cand], KEYS, clock=FakeClock(), sleep=lambda s: None)
    assert out["results"][0]["verdict"] == "UNSURE" and "empty reply" in out["results"][0]["error"]
    assert out["choice"]["decision"] == "UNSURE"


def test_load_keys_refuses_incomplete_env(tmp_path, monkeypatch, capsys):
    env = tmp_path / ".env"
    env.write_text("".join(f"NVIDIA_API_KEY_{i:02d}={k}\n" for i, k in enumerate(KEYS14[:3], 1)), encoding="utf-8")
    monkeypatch.setattr(rs, "ENV_FILE", env)
    cand = make_jpg(tmp_path / "cand.jpg")
    assert rs.main(["--jobs", str(job_file(tmp_path)), "--shot", "SH_T_01", "--candidate", str(cand)]) == 2
    assert "REFUSED" in capsys.readouterr().out


@pytest.mark.parametrize("reply_text, code", [
    ("<think>draft A Q1: BLOCK</think>\n" + canned("A"), 0),
    (canned("A", verdict="BLOCK", blocked=("Q3",)), 1),
    (partial("A"), 3),
], ids=["pass", "block", "unsure"])
def test_main_exit_codes_and_record(tmp_path, monkeypatch, capsys, env14, reply_text, code):
    monkeypatch.setattr(rs, "_http_post", lambda url, **kw: ok(reply_text))
    cand = make_jpg(tmp_path / "cand.jpg")
    assert rs.main(["--jobs", str(job_file(tmp_path)), "--shot", "SH_T_01", "--candidate", str(cand)]) == code
    rec = json.loads((tmp_path / "cand__review.json").read_text(encoding="utf-8"))
    assert rec["advisory_only"] is True and rec["model"] == rs.MODEL and rec["key_used"] == "key 1"
    assert rec["choice"]["decision"] == {0: "PASS", 1: "BLOCK", 3: "UNSURE"}[code]
    assert not any(k in capsys.readouterr().out + json.dumps(rec) for k in env14)


def test_no_key_in_any_output(tmp_path, monkeypatch, capsys, env14):
    monkeypatch.setattr(rs, "_http_post", lambda url, **kw: FakeResponse(400, text="echo " + kw["headers"]["Authorization"]))
    cand = make_jpg(tmp_path / "cand.jpg")
    assert rs.main(["--jobs", str(job_file(tmp_path)), "--shot", "SH_T_01", "--candidate", str(cand)]) == 3
    printed = capsys.readouterr().out
    assert env14[0] not in printed
    for f in tmp_path.iterdir():
        for k in env14:
            assert k.encode("utf-8") not in f.read_bytes(), f.name


def test_two_passes_merge_to_the_worst_answer():
    ok_run = rs.parse(canned("A"), "A")
    bad_run = rs.parse(canned("A", blocked=("Q7",)), "A")
    m = rs.merge_passes([ok_run, bad_run])
    assert m["verdict"] == "BLOCK" and m["answers"]["Q7"]["result"] == "BLOCK" and m["passes"] == ["PASS", "BLOCK"]
    assert rs.merge_passes([ok_run, rs.parse(canned("A"), "A")])["verdict"] == "PASS"
    unsure = rs.parse(canned("A").replace("A Q8: PASS", "A Q8: UNSURE"), "A")
    assert rs.merge_passes([ok_run, unsure])["verdict"] == "UNSURE"


def test_prompt_is_strict_and_asks_anatomy_text_colour():
    prompt = rs.review_prompt({"people_count": 1, "prompt": "x", "previous_shot": None, "next_shot": None}, ["A"])
    assert "BE STRICT" in prompt and "Q7:" in prompt and "Q8:" in prompt and "letter-like glyphs" in prompt


def test_ratio_guard_blocks_wrong_frame_shape(tmp_path):
    from PIL import Image
    key = {"prompt": "x Portrait 9:16 frame, vertical picture.", "model": {}}
    sheet = {"prompt": "x 16:9 labeled character sheet", "model": {}}
    good, bad = tmp_path / "g.png", tmp_path / "b.png"
    Image.new("RGB", (768, 1376)).save(good)
    Image.new("RGB", (1376, 768)).save(bad)
    assert rs.ratio_problem(key, good) is None and "wrong aspect ratio" in rs.ratio_problem(key, bad)
    assert rs.ratio_problem(sheet, bad) is None and rs.ratio_problem(sheet, good) is not None
    assert rs.ratio_problem({"prompt": "no shape", "model": {}}, bad) is None
