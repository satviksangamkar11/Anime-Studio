"""Pure flash-check tests on hand-made grids (no ffmpeg)."""
import copy

from core.flash_check import REPORT_HEADER, f1_report, f2_report, find_transitions, with_header
from core.style_pack import load_core

FPS = 24
BLACK = [0.0] * 64
WHITE = [1.0] * 64
RED = [0.2126] * 64        # luma of pure red
RED_SHARE = [1.0] * 64
NO_RED = [0.0] * 64


def flashes(at, length, hi=WHITE, lo=BLACK):
    """Frames of `lo` with a 2-frame `hi` burst starting at each index in `at`."""
    seq = [lo] * length
    for s in at:
        seq[s] = hi
        seq[s + 1] = hi
    return seq


def test_steady_frames_have_no_transitions_and_no_flash():
    assert find_transitions(BLACK, BLACK) == 0
    assert f1_report([WHITE] * 48, FPS) == []


def test_one_two_frame_white_flash_passes():
    assert f1_report(flashes([10], 40), FPS) == []


def test_four_flashes_inside_one_second_fail_once():
    report = f1_report(flashes([2, 8, 14, 20], 40), FPS)
    assert len(report) == 1
    entry = report[0]
    assert entry["rule"] == "F1" and entry["level"] == "FAIL"
    assert "4 luminance flashes" in entry["message"] and "0.08 s" in entry["message"]


def test_four_flashes_spread_over_three_seconds_pass():
    assert f1_report(flashes([2, 20, 38, 56], 80), FPS) == []


def test_zero_and_full_grids_do_not_crash():
    assert find_transitions(BLACK, WHITE) == 1
    assert find_transitions(WHITE, BLACK) == -1
    assert f1_report([BLACK, WHITE] * 3, FPS) == []   # 5 transitions is not 4 flashes


def test_small_or_dark_changes_are_not_transitions():
    assert find_transitions([0.5] * 64, [0.55] * 64) == 0          # change below 0.10
    assert find_transitions([0.85] * 64, [1.0] * 64) == 0          # darker value not below 0.80


def test_fewer_than_quarter_of_cells_is_not_a_transition():
    partial = [1.0] * 15 + [0.0] * 49                                # 15/64 < 25 %
    assert find_transitions(BLACK, partial) == 0


def test_exempt_frames_are_ignored():
    seq = flashes([2, 8, 14, 20], 40)
    assert f1_report(seq, FPS, exempt_frames=range(0, 40)) == []


def test_steady_saturated_red_has_no_f2_warning():
    assert f2_report([RED] * 48, [RED_SHARE] * 48, FPS) == []


def test_alternating_saturated_red_and_black_warns_f2_only():
    red_seq = flashes([2, 8, 14, 20], 40, hi=RED, lo=NO_RED)
    red_share = flashes([2, 8, 14, 20], 40, hi=RED_SHARE, lo=NO_RED)
    report = f2_report(red_seq, red_share, FPS)
    assert len(report) == 1
    assert report[0]["rule"] == "F2" and report[0]["level"] == "WARN"


def test_red_below_minimum_ratio_or_luma_does_not_count():
    low_ratio = [0.5] * 64
    dark_red = [0.01] * 64
    seq = flashes([2, 8, 14, 20], 40, hi=RED, lo=NO_RED)
    assert f2_report(seq, flashes([2, 8, 14, 20], 40, hi=low_ratio, lo=NO_RED), FPS) == []
    assert f2_report(flashes([2, 8, 14, 20], 40, hi=dark_red, lo=NO_RED),
                     flashes([2, 8, 14, 20], 40, hi=RED_SHARE, lo=NO_RED), FPS) == []


def test_red_flash_switched_off_returns_nothing():
    core = copy.deepcopy(load_core())
    core["flash"]["red_flash"] = False
    seq = flashes([2, 8, 14, 20], 40, hi=RED, lo=NO_RED)
    assert f2_report(seq, flashes([2, 8, 14, 20], 40, hi=RED_SHARE, lo=NO_RED), FPS, core=core) == []


def test_report_header_and_wrapper():
    assert REPORT_HEADER == ("F1 is a screening check based on the WCAG general-flash definition. "
                             "It is not a certified Harding test.")
    assert with_header([]) == {"note": REPORT_HEADER, "entries": []}
