"""Style chooser backend tests (owner 2026-11-07: Deva Neon fixed default, a story can pick another look).
Offline: temp studio, no model call, no Colab."""
import json
import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import server  # noqa: E402
from server import ApiError, Config  # noqa: E402

SLUG = "demo_story"


def _w(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) if not isinstance(data, str) else data, encoding="utf-8")


@pytest.fixture()
def world(tmp_path):
    studio = tmp_path / "anime_studio"
    studio.mkdir()
    _w(studio / "stories" / SLUG / "SOURCE.md", "# SOURCE: test\n\nhello\n")
    (studio / "ui" / "runs").mkdir(parents=True)
    cfg = Config(studio=studio, flow=tmp_path / "flow", downloads=tmp_path / "dl", python=sys.executable,
                 colab=[str(tmp_path / "colab.exe")], disk_paths=(str(tmp_path), str(tmp_path)))
    return cfg, server.Api(cfg)


def _d(api, method, path, body=None):
    return server.dispatch(api, method, path, {}, body or {})


def _story_json(cfg):
    p = cfg.studio / "stories" / SLUG / "story.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def test_list_has_both_packs_and_exactly_one_default(world):
    _, api = world
    out = _d(api, "GET", "/api/styles")
    ids = {s["id"] for s in out["styles"]}
    assert ids == {"braj_earth", "deva_neon"}
    assert out["default"] == "deva_neon"
    assert [s["id"] for s in out["styles"] if s["default"]] == ["deva_neon"]


def test_state_of_a_story_without_a_style_is_the_default(world):
    _, api = world
    st = _d(api, "GET", f"/api/story/{SLUG}/state")
    assert st["style_pack"] == "deva_neon" and st["style_is_default"] is True


def test_set_style_writes_story_json_and_keeps_other_keys(world):
    cfg, api = world
    _w(cfg.studio / "stories" / SLUG / "story.json", {"slug": SLUG, "output_languages": ["en"]})
    out = _d(api, "POST", f"/api/story/{SLUG}/style", {"style_pack": "braj_earth"})
    assert out == {"style_pack": "braj_earth", "warning_code": None}
    sj = _story_json(cfg)
    assert sj["style_pack"] == "braj_earth" and sj["output_languages"] == ["en"] and sj["slug"] == SLUG
    st = _d(api, "GET", f"/api/story/{SLUG}/state")
    assert st["style_pack"] == "braj_earth" and st["style_is_default"] is False


def test_set_style_warns_when_a_plan_exists_under_another_look(world):
    cfg, api = world
    _w(cfg.studio / "stories" / SLUG / "pack_a" / "shots.json", [])
    out = _d(api, "POST", f"/api/story/{SLUG}/style", {"style_pack": "braj_earth"})   # default deva_neon -> braj_earth
    assert out["warning_code"] == "old_plans"
    again = _d(api, "POST", f"/api/story/{SLUG}/style", {"style_pack": "braj_earth"})  # same pick again: nothing changed
    assert again["warning_code"] is None


def test_set_style_refuses_unknown_and_unsafe_ids(world):
    cfg, api = world
    for bad in ("no_such_pack", "../core", "", None, 7):
        with pytest.raises(ApiError) as e:
            _d(api, "POST", f"/api/story/{SLUG}/style", {"style_pack": bad})
        assert e.value.code == 400
    assert "style_pack" not in _story_json(cfg)


def test_set_style_unknown_story_is_404_and_bad_slug_is_refused(world):
    _, api = world
    with pytest.raises(ApiError) as e:
        _d(api, "POST", "/api/story/no_such_story/style", {"style_pack": "deva_neon"})
    assert e.value.code == 404
    with pytest.raises(ApiError):
        _d(api, "POST", "/api/story/..%2Fx/style", {"style_pack": "deva_neon"})
