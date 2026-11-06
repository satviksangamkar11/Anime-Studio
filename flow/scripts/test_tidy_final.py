"""Checks tidy_final: dry run moves nothing; --apply moves variants, keeps __final.png, never overwrites or deletes. Tmp folders only."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tidy_final as tf  # noqa: E402


def make_final(tmp_path: Path) -> Path:
    final = tmp_path / "anime_kaliya" / "adhyay_01" / "final"
    final.mkdir(parents=True)
    for v in tf.VARIANTS:
        (final / f"LEAP-01A{v}").write_bytes(v.encode())
    (final / f"LEAP-01A{tf.FINAL}").write_bytes(b"final")
    (final / "_superseded").mkdir()
    (final / "_superseded" / "OLD__candidate_v01.png").write_bytes(b"old")
    return final


def run(tmp_path: Path, *extra) -> int:
    return tf.main(["--root", str(tmp_path / "anime_kaliya"), "--adhyay", "1", *extra])


def test_dry_run_moves_nothing(tmp_path):
    final = make_final(tmp_path)
    before = sorted(p.name for p in final.iterdir())
    assert run(tmp_path) == 0
    assert sorted(p.name for p in final.iterdir()) == before
    assert not (final / tf.INTERMEDIATES).exists()


def test_apply_moves_variants_and_keeps_final(tmp_path):
    final = make_final(tmp_path)
    assert run(tmp_path, "--apply") == 0
    inter = final / tf.INTERMEDIATES
    for v in tf.VARIANTS:
        assert not (final / f"LEAP-01A{v}").exists()
        assert (inter / f"LEAP-01A{v}").read_bytes() == v.encode()
    assert (final / f"LEAP-01A{tf.FINAL}").read_bytes() == b"final"
    assert (final / "_superseded" / "OLD__candidate_v01.png").read_bytes() == b"old"


def test_never_overwrites_and_skips_titles_without_final(tmp_path):
    final = make_final(tmp_path)
    inter = final / tf.INTERMEDIATES
    inter.mkdir()
    (inter / "LEAP-01A__candidate_v01__clean.png").write_bytes(b"earlier copy")
    (final / "KRISHNA_X__candidate_v01.png").write_bytes(b"no final yet")
    assert run(tmp_path, "--apply") == 0
    assert (inter / "LEAP-01A__candidate_v01__clean.png").read_bytes() == b"earlier copy"
    assert (final / "LEAP-01A__candidate_v01__clean.png").read_bytes() == b"__candidate_v01__clean.png"
    assert (final / "KRISHNA_X__candidate_v01.png").read_bytes() == b"no final yet"
    assert (inter / "LEAP-01A__candidate_v01.png").is_file()
