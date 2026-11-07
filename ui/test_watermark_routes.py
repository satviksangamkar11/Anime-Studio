"""Watermark pick backend (owner 2026-11-07: watermark removal in the wizard). Offline: temp folders, no model call."""
import json
import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import server  # noqa: E402
from server import ApiError, Config  # noqa: E402


@pytest.fixture()
def api(tmp_path):
    studio = tmp_path / "anime_studio"
    (studio / "ui" / "runs").mkdir(parents=True)
    check = tmp_path / "flow" / "adhyay_01" / "final" / "_sparkle_check3"
    check.mkdir(parents=True)
    (check / "report.json").write_text(json.dumps({"LEAP-01A": {"method": "lama"}, "LEAP-02A": {}}), encoding="utf-8")
    (check / "LEAP-01A__sheet.png").write_bytes(b"x")
    cfg = Config(studio=studio, flow=tmp_path / "flow", downloads=tmp_path / "dl", python=sys.executable,
                 colab=[str(tmp_path / "colab.exe")], disk_paths=(str(tmp_path), str(tmp_path)))
    return server.Api(cfg)


def test_list_and_save_picks(api):
    d = server.dispatch(api, "GET", "/api/watermark", {"adhyay": "1"}, {})
    assert [r["title"] for r in d["rows"]] == ["LEAP-01A", "LEAP-02A"]
    assert d["rows"][0]["sheet"].endswith("LEAP-01A__sheet.png") and d["rows"][1]["sheet"] == ""
    r = server.dispatch(api, "POST", "/api/watermark/choices", {}, {"adhyay": 1, "choices": {"LEAP-01A": "lama_on_clean"}})
    saved = json.loads(Path(r["file"]).read_text(encoding="utf-8"))
    assert saved == {"LEAP-01A": {"method": "lama_on_clean", "verdict": "owner pick in the UI"}}


@pytest.mark.parametrize("choices", [{}, {"NOPE": "lama"}, {"LEAP-01A": "magic"}, "x"])
def test_bad_picks_refused(api, choices):
    with pytest.raises(ApiError):
        server.dispatch(api, "POST", "/api/watermark/choices", {}, {"adhyay": 1, "choices": choices})


def test_finalize_command_reads_the_saved_choices(api):
    argv = server.command_spec("wm_finalize").build(api.cfg, {"adhyay": 1})
    assert argv[-3:-1] == ["finalize", str(api.cfg.flow / "adhyay_01" / "final")] and argv[-1].endswith("watermark_choices.json")
