"""WP4 regression fixtures for check_pack.py (pack rules P0-P13, retention R1-R10, A8 issues, --strict).
Packs are built in tmp_path; styles come from the real styles/*.json. No network, no model calls."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import check_pack as cp

REPO = Path(__file__).resolve().parents[1]
CHECK = Path(__file__).resolve().parent / "check_pack.py"
T0_SHOTS = Path(__file__).resolve().parent / "t0_pack" / "t0_shots.json"
DEVA_TEMPLATE = REPO / "core" / "tests" / "fixtures" / "deva_shots_template.json"

_spec = importlib.util.spec_from_file_location("convert_deva_shots", REPO / "tools" / "convert_deva_shots.py")
conv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conv)

SHIVA_STORY = {"slug": "shiva_demo", "style_pack": "deva_neon", "platform": "shorts_9x16", "language": "en",
               "episode_target_s": [65, 75]}


def shot(sid, ep=1, seconds=5, **extra):
    base = {"id": sid, "episode": ep, "mode": "fl2va", "seconds": seconds, "aspect": "9:16",
            "style": "Flat 2D cel anime.", "world": "Kailash summit at night.", "action": "0-2s he holds still.",
            "camera": "static", "sound": "wind"}
    base.update(extra)
    return base


def look(act="HOOK", phase="PH-HOOK", palette="shiva_neelkanth", focal="CHAR-SHIVA", hook=None, **extra):
    lk = {"palette_id": palette, "act": act, "phase": phase, "focal": focal, "focal_value": "lightest",
          "accent_use": False, "hold_purpose": None}
    if hook is not None:
        lk["hook"] = hook
    lk.update(extra)
    return lk


HOOK = {"type": "H-03", "caption": "Who drank the poison?"}


def make_pack(tmp_path, shots, story=None, pack_md="# PACK\n", pack_name="pack"):
    """shots.json + PACK.md in tmp_path/pack_name; story.json (if given) one level up in tmp_path."""
    d = tmp_path / pack_name
    d.mkdir(parents=True, exist_ok=True)
    (d / "shots.json").write_text(json.dumps(shots, ensure_ascii=False), encoding="utf-8")
    (d / "PACK.md").write_text(pack_md, encoding="utf-8")
    if story is not None:
        (tmp_path / "story.json").write_text(json.dumps(story), encoding="utf-8")
    return d


def entries(result, rule=None, level=None):
    return [e for e in result["rules"]
            if (rule is None or e["rule"] == rule) and (level is None or e["level"] == level)]


def run_cli(args):
    return subprocess.run([sys.executable, str(CHECK), *[str(a) for a in args]], cwd=str(CHECK.parent),
                          capture_output=True, text=True, encoding="utf-8", timeout=120)


# ---- multi_ep: two correct episodes, no P6/P7 FAIL ----
def test_multi_ep_gives_no_p6_or_p7_fail(tmp_path):
    shots = []
    for ep in (1, 2):
        shots += [
            shot(f"E{ep}-01", ep, look=look("HOOK", "PH-HOOK", hook=HOOK)),
            shot(f"E{ep}-02", ep, look=look("BUILD", "PH-BUILD")),
            shot(f"E{ep}-03", ep, look=look("OUTRO", "PH-OUTRO")),
        ]
    d = make_pack(tmp_path, shots, SHIVA_STORY)
    res = cp.check(d)
    assert [e for e in res["rules"] if e["rule"] in ("P6", "P7") and e["level"] == "FAIL"] == []
    assert set(res["episode_seconds"]) == {1, 2}


# ---- strobe: 4 alternating impacts in 1 s of a 31 s reel -> P6 FAIL ----
def test_strobe_four_impacts_in_one_second_is_p6_fail(tmp_path):
    impacts = [{"at_s": 5.0 + 0.2 * i, "type": "white_out" if i % 2 == 0 else "inverted", "frames": 2}
               for i in range(4)]
    # edit_frames without seconds: a 15.5 s editorial length (the director caps one render at 15.08 s)
    shots = [shot("S1", look=look("HOOK", "PH-HOOK", hook=HOOK, impact_frames=impacts), edit_frames=372),
             shot("S2", look=look("OUTRO", "PH-OUTRO"), edit_frames=372)]
    for s in shots:
        del s["seconds"]
    res = cp.check(make_pack(tmp_path, shots, SHIVA_STORY))
    assert res["total_seconds"] == 31.0
    assert entries(res, "P6", "FAIL"), res["rules"]


# ---- tokens: Shiva saffron off its third-eye role + 2 neons -> P5 FAIL ----
def test_saffron_off_role_and_two_neons_is_p5_fail(tmp_path):
    vfx = [{"color": "Trialokya Saffron", "role": "trishul"}, {"color": "Neel Cyan", "role": "energy"}]
    shots = [shot("T1", look=look("HOOK", "PH-HOOK", hook=HOOK, vfx=vfx)),
             shot("T2", look=look("OUTRO", "PH-OUTRO"))]
    res = cp.check(make_pack(tmp_path, shots, SHIVA_STORY))
    p5 = entries(res, "P5", "FAIL")
    assert {e["shot"] for e in p5} == {"T1"}
    assert len(p5) == 2   # law (saffron off third_eye) and neon count


# ---- slow: a 20 s single hook shot -> R6 FAIL ----
def test_twenty_second_single_hook_shot_is_r6_fail(tmp_path):
    # edit_frames without seconds: 480 frames = 20 s (frames_for caps one render at 15.08 s)
    single = shot("L1", look=look("HOOK", "PH-HOOK", hook=HOOK), edit_frames=480)
    del single["seconds"]
    res = cp.check(make_pack(tmp_path, [single], SHIVA_STORY))
    assert res["total_seconds"] == 20.0
    assert entries(res, "R6", "FAIL"), res["rules"]


# ---- bad_frames, bad_secs, strings -> P0 FAIL, never a traceback ----
BAD = {
    "bad_frames": [shot("B1", edit_frames="x")],
    "bad_secs": [shot("B2", seconds="five")],
    "strings": [shot("B3", beats=["just a string"])],
}


@pytest.mark.parametrize("name", sorted(BAD))
def test_malformed_shots_give_p0_fail_without_traceback(tmp_path, name):
    d = make_pack(tmp_path, BAD[name], pack_name=name)
    res = cp.check(d)
    assert res["fail"] is True
    p0 = entries(res, "P0", "FAIL")
    assert p0 and all(isinstance(e["message"], str) for e in p0)
    assert any(e["message"] for e in p0)


def test_malformed_shots_cli_prints_json_and_no_traceback(tmp_path):
    d = make_pack(tmp_path, BAD["bad_frames"], pack_name="cli_bad")
    r = run_cli([d])
    assert r.returncode == 0, r.stderr
    assert "Traceback" not in r.stderr
    out = json.loads(r.stdout)
    assert out["fail"] is True and any(e["rule"] == "P0" for e in out["rules"])


# ---- no story.json anywhere near the pack -> P1 entry that names story.json ----
def test_pack_without_story_json_reports_p1_naming_story_json(tmp_path):
    t0 = json.loads(T0_SHOTS.read_text(encoding="utf-8"))
    d = tmp_path / "t0pack"
    d.mkdir()
    (d / "shots.json").write_text(json.dumps(t0), encoding="utf-8")
    res = cp.check(d)
    p1 = entries(res, "P1")
    assert len(p1) == 1 and "story.json" in p1[0]["message"]
    assert p1[0]["level"] == "FAIL"   # spec 6.1 line 619: t0_shots without story.json -> P1 FAIL


# ---- DEVA template converted + Shiva story: only the SHOT-02 P5 FAILs among P-rules (plus the fonts gap) ----
def test_deva_template_after_convert_gives_only_the_known_p5_fails(tmp_path):
    shots = conv.convert(json.loads(DEVA_TEMPLATE.read_text(encoding="utf-8")), cp.load_pack("deva_neon"))
    d = make_pack(tmp_path, shots, SHIVA_STORY, pack_md="# DEVA\n", pack_name="deva")
    res = cp.check(d)
    p_fail = [e for e in res["rules"] if e["rule"].startswith("P") and e["level"] == "FAIL"]
    p5 = [e for e in p_fail if e["rule"] == "P5"]
    assert [e["shot"] for e in p5] == ["SHOT-02", "SHOT-02"]
    assert "Neel Cyan" in p5[1]["message"] and "Trialokya Saffron" in p5[1]["message"]
    assert "role 'edge'" in p5[0]["message"]
    # Real finding: styles/fonts is not in the repo (owner supplies fonts), so P10 FAILs for any deva_neon pack.
    rest = [e for e in p_fail if e["rule"] != "P5"]
    assert [(e["rule"], e["shot"]) for e in rest] == [("P10", None)]


# ---- Kaliya sample with Krishna: no P1, P2 or P4 FAIL ----
def test_kaliya_krishna_sample_passes_p1_p2_p4(tmp_path):
    story = {"slug": "kaliya_mardan", "style_pack": "braj_earth", "platform": "shorts_9x16", "language": "hi",
             "episode_target_s": [65, 75]}
    shots = [shot("K-01", seconds=5, cast=[{"id": "CHAR-KRISHNA"}],
                  look=look("HOOK", "PH-DAWN-PLAY", palette="char_krishna", focal="CHAR-KRISHNA",
                            hook={"type": "H-03", "caption": "Who drank the poison?"}),
                  sound="river hush")]
    res = cp.check(make_pack(tmp_path, shots, story))
    assert [e for e in res["rules"] if e["rule"] in ("P1", "P2", "P4") and e["level"] == "FAIL"] == []


# ---- A8: every FAIL/WARN rule entry appears in issues as "<rule> <LEVEL>: <message>" ----
def test_every_fail_and_warn_rule_entry_is_copied_into_issues(tmp_path):
    impacts = [{"at_s": 5.0 + 0.2 * i, "type": "white_out", "frames": 2} for i in range(4)]
    shots = [shot("S1", seconds=15, look=look("HOOK", "PH-HOOK", hook=HOOK, impact_frames=impacts)),
             shot("S2", seconds=16, look=look("OUTRO", "PH-OUTRO"))]
    res = cp.check(make_pack(tmp_path, shots, SHIVA_STORY))
    flagged = [e for e in res["rules"] if e["level"] in ("FAIL", "WARN")]
    assert flagged
    for e in flagged:
        assert f"{e['rule']} {e['level']}: {e['message']}" in res["issues"]


# ---- --strict exit codes ----
def test_default_exit_is_zero_even_with_fail(tmp_path):
    d = make_pack(tmp_path, BAD["bad_frames"], pack_name="default_exit")
    assert run_cli([d]).returncode == 0


def test_strict_exit_is_one_with_fail_and_zero_without(tmp_path, monkeypatch, capsys):
    d = make_pack(tmp_path, BAD["bad_frames"], pack_name="strict_fail")
    assert run_cli([d, "--strict"]).returncode == 1
    monkeypatch.setattr(cp, "check", lambda pack_dir, story_path=None: {"fail": False, "issues": [], "rules": []})
    assert cp.main([str(d), "--strict"]) == 0
    assert json.loads(capsys.readouterr().out)["fail"] is False


# ---- ramayana alone is not banned; the full film title is ----
def test_ramayana_alone_is_not_the_film_but_the_full_title_is(tmp_path):
    shots = [shot("R1", style="a Ramayana-inspired temple costume", action="0-2s she turns."),
             shot("R2", action="0-2s the card reads Ramayana: The Legend of Prince Rama.")]
    res = cp.check(make_pack(tmp_path, shots, pack_name="ramayana"))
    film = [i for i in res["issues"] if "names a film/studio" in i]
    assert len(film) == 1 and film[0].startswith("R2:")
    assert res["code_blocks_naming_a_film"] == 0


def test_valid_flat_pack_keeps_the_existing_result_keys(tmp_path):
    shots = [shot("V1", seconds=5), shot("V2", seconds=5)]
    res = cp.check(make_pack(tmp_path, shots, pack_name="keys"))
    for key in ("shots", "modes", "episode_seconds", "total_seconds", "code_blocks_naming_a_film", "issues",
                "rules", "fail"):
        assert key in res
    assert res["modes"] == {"fl2va": 2}
    assert isinstance(res["issues"], list) and all(isinstance(i, str) for i in res["issues"])
