"""dots_review: no network, no key file. Fake poster."""
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dots_review as dr  # noqa: E402


def test_messages_number_lines_and_name_files(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("x = 1\ny = 2\n")
    m = dr.build_messages("check it", [f])
    assert "=== FILE a.py ===" in m[0]["content"] and "2: y = 2" in m[0]["content"]


def test_retry_on_429_then_ok(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("x = 1\n")
    calls = []

    def poster(body, key):
        calls.append(body["model"])
        if len(calls) == 1:
            raise urllib.error.HTTPError("u", 429, "too many", {}, None)
        return {"choices": [{"message": {"content": "no findings"}}], "model": dr.MODEL, "usage": {"cost": 0}}

    out = dr.review("p", [f], key="k", poster=poster, sleep=lambda s: None)
    assert out["text"] == "no findings" and out["paid"] is False and len(calls) == 2


def test_paid_cost_is_flagged(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("x = 1\n")
    out = dr.review("p", [f], key="k", poster=lambda b, k: {"choices": [{"message": {"content": "ok"}}], "usage": {"cost": 0.01}}, sleep=lambda s: None)
    assert out["paid"] is True


def test_gives_up_after_tries(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("x = 1\n")

    def poster(b, k):
        raise urllib.error.HTTPError("u", 503, "x", {}, None)

    try:
        dr.review("p", [f], key="k", poster=poster, sleep=lambda s: None, tries=2)
        assert False
    except RuntimeError as e:
        assert "HTTP 503" in str(e)


def test_empty_length_answer_retries_with_more_tokens(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("x = 1\n")
    seen = []

    def poster(body, key):
        seen.append(body["max_tokens"])
        if len(seen) == 1:
            return {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}
        return {"choices": [{"message": {"content": "FINAL: no findings"}, "finish_reason": "stop"}], "usage": {"cost": 0}}

    out = dr.review("p", [f], key="k", poster=poster, sleep=lambda s: None, max_tokens=1000)
    assert out["text"].startswith("FINAL") and seen == [1000, 2000]
