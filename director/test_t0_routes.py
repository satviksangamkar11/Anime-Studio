"""T0 arms (RETHINK addendum, 2026-11-05): the sing4 and sing8 routes (Singularity v2 + Pika-Labs Turbo LoRA), the Turbo rules in
check_combo, the arm ids A-D, the 8-clip expansion, and the Colab wrapper's dry run. The route pika6 keeps the older Pika tests."""
import importlib.util
import json
from pathlib import Path

import pytest

import t0_variants
from h3_director import SING_MODEL, TURBO_URL, check_combo, check_shot_id, settings_for
from test_review2 import BASE, BIBLE, REF_SHAPE, T0_BASE

DIRECTOR = Path(__file__).resolve().parent
TURBO4 = TURBO_URL + "pika_h3_flex_turbo_4step_ref2va.safetensors"
TURBO8 = TURBO_URL + "pika_h3_flex_turbo_8step_hd_ref2va.safetensors"
OFFICIAL = "https://huggingface.co/DeepBeepMeep/MiniMax-H3/resolve/main/loras/pika_h3_flex_ref2va_6step_v1_bf16.safetensors"
T0_HD = dict(T0_BASE, resolution="768x1344")


@pytest.mark.parametrize("route, lora, steps", [("sing4", TURBO4, 4), ("sing8", TURBO8, 8)])
def test_sing_routes_build_the_turbo_presets(route, lora, steps):
    s = settings_for(dict(REF_SHAPE, route=route))
    assert s["model_type"] == SING_MODEL and s["activated_loras"] == [lora]
    assert (s["sample_solver"], s["num_inference_steps"], s["loras_multipliers"], s["guidance_scale"], s["guidance_phases"]) == \
        ("euler", steps, "1.0", 1, 1)
    assert (s["flow_shift"], s["custom_sigmas"], s["skip_steps_cache_type"], s["settings_version"]) == (12, "", "", 2.82)
    assert s["video_prompt_type"] == "I" and s["image_refs"] == ["k.png"] and "image_start" not in s


@pytest.mark.parametrize("route", ["sing4", "sing8"])
def test_sing_routes_keep_keyframes_like_arm_a(route):
    s = settings_for(dict(REF_SHAPE, route=route, start="a.png", end="b.png", seconds=5.2))
    assert s["image_start"] == "a.png" and s["image_end"] == "b.png" and s["image_prompt_type"] == "SE"


def test_pika6_is_the_default_route_and_stays_the_same():
    s = settings_for(REF_SHAPE)
    assert s == settings_for(dict(REF_SHAPE, route="pika6"))
    assert s["model_type"] == "minimax_h3_ref2va_pruned" and s["sample_solver"] == "pika_renoise" and s["num_inference_steps"] == 6


@pytest.mark.parametrize("bad", [dict(BASE, route="sing4"),                        # fl2va mode
                                 dict(REF_SHAPE, route="sing8", sampler="euler"),   # the route sets the sampler
                                 dict(REF_SHAPE, route="sing4", refs=[], subjects=[]),
                                 dict(REF_SHAPE, route="sing9"),
                                 dict(REF_SHAPE, route="")])
def test_sing_routes_refuse_the_wrong_shape(bad):
    with pytest.raises(ValueError):
        settings_for(bad)


def test_turbo_rules_refuse_each_mistake():
    ok = settings_for(dict(REF_SHAPE, route="sing4"))
    check_combo(ok)
    check_combo(settings_for(dict(REF_SHAPE, route="sing8")))
    bad = [dict(sample_solver="pika_renoise"), dict(num_inference_steps=6), dict(loras_multipliers="0.8"), dict(guidance_scale=3),
           dict(guidance_phases=2), dict(flow_shift=3), dict(custom_sigmas="0.9,0.5"), dict(skip_steps_cache_type="teacache"),
           dict(model_type="minimax_h3_ref2va_pruned"), dict(activated_loras=[TURBO4, OFFICIAL]), dict(activated_loras=[TURBO4, TURBO8]),
           dict(activated_loras=[]), dict(activated_loras=[OFFICIAL])]
    for change in bad:
        with pytest.raises(ValueError):
            check_combo(dict(ok, **change))


def test_the_turbo_file_must_match_its_step_count():
    with pytest.raises(ValueError, match="8-step"):
        check_combo(dict(settings_for(dict(REF_SHAPE, route="sing8")), num_inference_steps=4))
    with pytest.raises(ValueError, match="4-step"):
        check_combo(dict(settings_for(dict(REF_SHAPE, route="sing4")), num_inference_steps=8))


def test_singularity_never_runs_the_official_pika_adapter():
    with pytest.raises(ValueError):
        check_combo(dict(settings_for(REF_SHAPE), model_type=SING_MODEL))   # pika_renoise and the Pika adapter on Singularity


def test_the_turbo_lora_is_refused_on_the_standard_models():
    with pytest.raises(ValueError, match="Singularity"):
        check_combo(dict(settings_for(REF_SHAPE), activated_loras=[TURBO4]))


@pytest.mark.parametrize("sid", ["SHOT-T0-A-S42", "SHOT-T0-B-S123", "SHOT-T0-C-S42", "SHOT-T0-D-S123", "SHOT-T0-FL-S42", "SHOT-T0-REF-S123"])
def test_t0_ids_accept_the_arms_and_the_old_variants(sid):
    assert check_shot_id(sid) == sid


@pytest.mark.parametrize("bad", ["SHOT-T0-E-S42", "SHOT-T0-A", "SHOT-T0-A-42", "SHOT-T0-a-S42"])
def test_t0_ids_refuse_other_letters_and_missing_seeds(bad):
    with pytest.raises(ValueError, match="shot id"):
        check_shot_id(bad)


def test_arms_expand_into_eight_clips_that_all_build():
    v = t0_variants.expand_arms(T0_HD, BIBLE)
    assert [s["id"] for s in v] == [f"SHOT-T0-{a}-S{seed}" for a in "ABCD" for seed in (42, 123)]
    by_id = {s["id"]: s for s in v}
    built = {sid: settings_for(s, BIBLE) for sid, s in by_id.items()}
    assert all(b["video_length"] == 124 and b["resolution"] == "768x1344" for b in built.values())
    assert built["SHOT-T0-A-S42"]["model_type"] == "minimax_h3_ref2va_pruned" and built["SHOT-T0-A-S42"]["sample_solver"] == "pika_renoise"
    assert built["SHOT-T0-B-S42"]["model_type"] == SING_MODEL and built["SHOT-T0-B-S42"]["activated_loras"] == [TURBO4]
    assert built["SHOT-T0-C-S123"]["activated_loras"] == [TURBO8] and built["SHOT-T0-C-S123"]["num_inference_steps"] == 8
    assert built["SHOT-T0-C-S123"]["seed"] == 123
    assert built["SHOT-T0-D-S42"]["model_type"] == "minimax_h3_fl2va_pruned" and "image_refs" not in built["SHOT-T0-D-S42"]
    assert [sid for sid, s in by_id.items() if "refs" in s] == [f"SHOT-T0-{a}-S{seed}" for a in "ABC" for seed in (42, 123)]


def test_base_route_and_sampler_never_leak_into_the_arms():
    v = t0_variants.expand_arms(dict(T0_HD, route="sing8", sampler="euler"), BIBLE)
    built = {s["id"]: settings_for(s, BIBLE) for s in v}
    assert built["SHOT-T0-A-S42"]["model_type"] == "minimax_h3_ref2va_pruned" and built["SHOT-T0-B-S42"]["num_inference_steps"] == 4
    old = t0_variants.expand(dict(T0_HD, route="sing4", sampler="euler"), BIBLE)
    assert len(old) == 4 and all("route" not in s for s in old)
    assert all(settings_for(s, BIBLE)["sample_solver"] == "pika_renoise" for s in old if s["mode"] == "ref2va")


def test_arms_main_writes_eight_and_refuses_overwrite(tmp_path):
    base = tmp_path / "base.json"
    base.write_text(json.dumps(T0_HD), encoding="utf-8")
    out = tmp_path / "t0_arms.json"
    t0_variants.main(str(base), str(out), "kaliya_mardan", arms=True)
    assert len(json.loads(out.read_text(encoding="utf-8"))) == 8
    with pytest.raises(ValueError, match="exists"):
        t0_variants.main(str(base), str(out), "kaliya_mardan", arms=True)


def test_colab_wrapper_dry_run_starts_no_process(monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("run_t0_colab", DIRECTOR / "t0_pack" / "run_t0_colab.py")
    wrapper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wrapper)

    def no_process(*args, **kwargs):
        raise AssertionError("a dry run must not start a process")
    monkeypatch.setattr(wrapper.subprocess, "run", no_process)
    assert wrapper.main([]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "colab new" in out and "colab stop" in out and "--timeout" in out
