"""post.py caption wiring: SRT/VTT sidecars, platform template, hook-word emphasis (checklist 9.1, 9.2, 9.4)."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import test_post as tp  # noqa: E402  (helpers and the skip-if-no-ffmpeg setup)


def test_sidecars_are_written_next_to_the_final_file(tmp_path):
    build, story, styles = tp._setup(tmp_path)
    report = tp._run(build, story, styles)
    assert report["written"] is True
    srt = list(build.glob("EP1_final.*.srt"))
    vtt = list(build.glob("EP1_final.*.vtt"))
    assert len(srt) == 1 and len(vtt) == 1
    assert "Hook line" in srt[0].read_text(encoding="utf-8") and vtt[0].read_text(encoding="utf-8").startswith("WEBVTT")


def test_no_sidecars_when_turned_off(tmp_path):
    build, story, styles = tp._setup(tmp_path)
    tp._run(build, story, styles, sidecars=False)
    assert not list(build.glob("EP1_final.*.srt")) and not list(build.glob("EP1_final.*.vtt"))


def test_a_refused_episode_writes_no_sidecars(tmp_path):
    flash = ([(255, 255, 255)] * 1 + [(0, 0, 0)] * 1) * 8 + [tp.GREY] * 32
    build, story, styles = tp._setup(tmp_path, clips={"SHOT_A": flash, "SHOT_B": [tp.GREY] * 48})
    report = tp._run(build, story, styles)
    assert report["written"] is False
    assert not list(build.glob("EP1_final.*.srt"))


def test_platform_template_moves_the_caption(tmp_path):
    build, story, styles = tp._setup(tmp_path)
    tp._run(build, story, styles, platform="youtube")
    ass = (build / "post" / "captions.ass").read_text(encoding="utf-8")
    y = int(re.search(r"\\pos\(\d+,(\d+)\)", ass).group(1))
    height = int(re.search(r"PlayResY: (\d+)", ass).group(1))
    assert abs(y - round(0.86 * height)) <= 1


def test_hook_emphasis_reaches_the_ass_file(tmp_path):
    shots = [tp._shot("SHOT_A"), tp._shot("SHOT_B")]
    shots[0]["metadata"]["look"]["hook"]["emphasis"] = ["Hook"]
    build, story, styles = tp._setup(tmp_path, shots=shots)
    tp._run(build, story, styles)
    ass = (build / "post" / "captions.ass").read_text(encoding="utf-8")
    assert "\\fscx112\\fscy112}Hook" in ass
