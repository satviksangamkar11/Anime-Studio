"""F1 counting at the 3-per-second boundary (owner acceptance: a 4-flash second must refuse)."""
from core.flash_check import f1_report

WHITE = [[1.0] * 8 for _ in range(8)]
BLACK = [[0.0] * 8 for _ in range(8)]


def alternating(n_bright_or_changes_frames, fps=24):
    """n frames alternating black/white starting black, then black up to one full second."""
    frames = [WHITE if i % 2 else BLACK for i in range(n_bright_or_changes_frames)]
    frames += [BLACK] * (fps - len(frames))
    return frames


def test_eight_alternating_frames_are_four_flashes_and_fail():
    report = f1_report(alternating(8), 24)
    assert len(report) == 1 and report[0]["level"] == "FAIL" and report[0]["rule"] == "F1"
    assert report[0]["message"].startswith("4 luminance flashes")


def test_six_alternating_frames_are_three_flashes_and_pass():
    assert f1_report(alternating(6), 24) == []


def test_single_two_frame_white_flash_passes():
    frames = [BLACK, WHITE, BLACK] + [BLACK] * 21
    assert f1_report(frames, 24) == []
