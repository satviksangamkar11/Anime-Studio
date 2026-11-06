"""Checks the anime Flow filer and download queue. Tmp folders only; fake JPEGs and PNGs made with PIL.
The filer reads no Granth file: the prompt hash comes only from the jobs file."""
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import pytest
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import download_queue as dq  # noqa: E402
from fingerprint import dhash_file, hamming  # noqa: E402

FILER = HERE / "file_flow_download.py"
TITLE = "KRISHNA_TURNAROUND__v01"
EDIT = "34ba531b-b5c7-43fa-82a5-7b7746b57016"
SIZE_16_9, SIZE_9_16 = (2752, 1536), (1536, 2752)


def make_jpg(path: Path, size, seed: int) -> Path:
    Image.new("RGB", size, (seed * 37 % 256, seed * 91 % 256, 40)).save(path, "JPEG", quality=90)
    return path


def pattern(size, seed: int) -> Image.Image:
    """Textured picture: random grey cells blown up. Solid colours all share one dHash, so fingerprint tests need this."""
    rnd = random.Random(seed)
    cells = Image.frombytes("L", (9, 8), bytes(rnd.randrange(256) for _ in range(72)))
    return cells.resize(size, Image.Resampling.NEAREST).convert("RGB")


def setup(tmp_path: Path):
    root = tmp_path / "anime_kaliya"
    dl = tmp_path / "Downloads"
    dl.mkdir()
    dq.add(root, 1, "KRISHNA_TURNAROUND", "v01", EDIT)
    return root, dl


def log_lines(root: Path) -> list[dict]:
    return [json.loads(l) for l in (root / "adhyay_01" / "flow_log.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def drop_aspect(root: Path) -> None:
    """Turn the queue into an OLD one (written before the aspect field existed)."""
    q = root / "adhyay_01" / "download_queue.jsonl"
    items = [json.loads(l) for l in q.read_text(encoding="utf-8").splitlines() if l.strip()]
    for it in items:
        it.pop("aspect", None)
    q.write_text("".join(json.dumps(it, ensure_ascii=False) + "\n" for it in items), encoding="utf-8")


def run_filer(src: Path, root: Path, iid="KRISHNA_TURNAROUND", ver="v01") -> subprocess.CompletedProcess:
    env = dict(os.environ, FLOW_OUT_ROOT=str(root), FLOW_ADHYAY="1", FLOW_MAX_AGE_S="300", PYTHONIOENCODING="utf-8",
               FLOW_ASPECT="", FLOW_APPROVED_DHASH="", FLOW_LINEAGE="", FLOW_DECIDED_BY="")
    args = [sys.executable, str(FILER), str(src), iid, ver, f"edit/{EDIT}", "", "references", "", "", ""]
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", env=env)


def test_exact_title_filed_into_final(tmp_path):
    root, dl = setup(tmp_path)
    make_jpg(dl / f"{TITLE}_a1b2c3_2K.jpg", SIZE_16_9, 1)
    make_jpg(dl / f"{TITLE}1_a1b2c3_2K.jpg", SIZE_16_9, 2)  # near-miss title: must be ignored
    out = dq.collect(root, 1, dl)
    assert out == [f"FILED {TITLE} <- {TITLE}_a1b2c3_2K.jpg"], out
    assert (root / "adhyay_01" / "final" / "KRISHNA_TURNAROUND__candidate_v01__2K_source.jpg").is_file()
    assert dq.status(root, 1)["pending"] == []


def test_duplicate_bytes_refused(tmp_path):
    root, dl = setup(tmp_path)
    make_jpg(dl / f"{TITLE}_a1b2c3_2K.jpg", SIZE_16_9, 1)
    dq.collect(root, 1, dl)
    dq.add(root, 1, "KRISHNA_ACTING_SHEET", "v01", EDIT)
    dl.joinpath("KRISHNA_ACTING_SHEET__v01_d4e5f6_2K.jpg").write_bytes((dl / f"{TITLE}_a1b2c3_2K.jpg").read_bytes())
    out = dq.collect(root, 1, dl)
    assert len(out) == 1 and out[0].startswith("REFUSED KRISHNA_ACTING_SHEET__v01") and "identical" in out[0], out


def test_wrong_size_refused_and_nothing_filed(tmp_path):
    root, dl = setup(tmp_path)
    make_jpg(dl / f"{TITLE}_a1b2c3_2K.jpg", (1024, 1024), 3)
    out = dq.collect(root, 1, dl)
    assert len(out) == 1 and out[0].startswith("REFUSED") and "not 2K" in out[0], out
    assert not (root / "adhyay_01" / "final").exists()
    assert len(dq.status(root, 1)["pending"]) == 1


@pytest.mark.parametrize("size", [SIZE_16_9, SIZE_9_16])
def test_old_item_without_aspect_accepts_both_orientations(tmp_path, size):
    root, dl = setup(tmp_path)
    drop_aspect(root)
    make_jpg(dl / f"{TITLE}_a1b2c3_2K.jpg", size, 4)
    out = dq.collect(root, 1, dl)
    assert out[0].startswith("FILED"), out


def test_orientation_must_match_aspect(tmp_path):
    root, dl = setup(tmp_path)  # no jobs file: aspect defaults to 16:9
    wrong = make_jpg(dl / f"{TITLE}_a1b2c3_2K.jpg", SIZE_9_16, 5)
    out = dq.collect(root, 1, dl)
    assert out == [f"REFUSED {TITLE}: wrong orientation: aspect 16:9 needs 2752x1536, got 1536x2752"], out
    assert not (root / "adhyay_01" / "final").exists()
    wrong.unlink()
    make_jpg(dl / f"{TITLE}_d4e5f6_2K.jpg", SIZE_16_9, 5)
    assert dq.collect(root, 1, dl) == [f"FILED {TITLE} <- {TITLE}_d4e5f6_2K.jpg"]


def test_aspect_default_comes_from_jobs_prompt(tmp_path):
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps([
        {"shot_id": "LEAP-01A", "prompt": "keyframe. Portrait 9:16 frame, vertical picture", "prompt_sha256": "p1", "chips": []},
        {"shot_id": "KRISHNA_TURNAROUND", "prompt": "a 16:9 sheet", "prompt_sha256": "p2", "chips": []},
    ]), encoding="utf-8")
    root = tmp_path / "anime_kaliya"
    assert dq.add(root, 1, "LEAP-01A", "v01", EDIT, jobs=jobs)["aspect"] == "9:16"
    assert dq.add(root, 1, "KRISHNA_TURNAROUND", "v01", EDIT, jobs=jobs)["aspect"] == "16:9"
    assert dq.add(root, 1, "KRISHNA_ACTING_SHEET", "v01", EDIT)["aspect"] == "16:9"  # no jobs file


def test_no_jobs_file_means_null_prompt_hash_and_no_granth_read(tmp_path):
    root, dl = setup(tmp_path)
    make_jpg(dl / f"{TITLE}_a1b2c3_2K.jpg", SIZE_16_9, 1)
    assert dq.collect(root, 1, dl)[0].startswith("FILED")
    rec = log_lines(root)[-1]
    assert rec["prompt_sha256"] is None and rec["prompt_source"] == "none" and rec["fingerprint"] == "none"
    assert "granthstudio" not in FILER.read_text(encoding="utf-8").lower()


def test_prompt_hash_comes_from_jobs_file(tmp_path):
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps([{"shot_id": "KRISHNA_TURNAROUND", "prompt": "a 16:9 sheet", "prompt_sha256": "abc123", "chips": ["CHAR-KRISHNA"]}]), encoding="utf-8")
    root = tmp_path / "anime_kaliya"
    dl = tmp_path / "Downloads"
    dl.mkdir()
    dq.add(root, 1, "KRISHNA_TURNAROUND", "v01", EDIT, jobs=jobs)
    make_jpg(dl / f"{TITLE}_a1b2c3_2K.jpg", SIZE_16_9, 1)
    assert dq.collect(root, 1, dl)[0].startswith("FILED")
    rec = log_lines(root)[-1]
    assert rec["prompt_sha256"] == "abc123" and rec["prompt_source"].startswith("jobs v2") and rec["chips"] == ["CHAR-KRISHNA"]


def test_refusals_print_reason_and_exit_2(tmp_path):
    root, dl = setup(tmp_path)
    bad = dl / "bad.jpg"
    bad.write_bytes(b"not a jpeg")
    r = run_filer(bad, root)
    assert r.returncode == 2 and r.stderr.strip() == "REFUSED: not a complete JPEG", r.stderr

    old = make_jpg(dl / "old.jpg", SIZE_16_9, 6)
    t = time.time() - 3600
    os.utime(old, (t, t))
    r = run_filer(old, root)
    assert r.returncode == 2 and "older than 300 s" in r.stderr and "Traceback" not in r.stderr, r.stderr

    assert run_filer(make_jpg(dl / "first.jpg", SIZE_16_9, 7), root).returncode == 0
    r = run_filer(make_jpg(dl / "other.jpg", SIZE_16_9, 8), root)
    assert r.returncode == 2 and "refusing to overwrite" in r.stderr, r.stderr


def test_dhash_same_picture_close_other_picture_far(tmp_path):
    approved = tmp_path / "approved.png"
    pattern((1200, 700), 11).save(approved)
    same = tmp_path / "same.jpg"
    pattern(SIZE_16_9, 11).save(same, "JPEG", quality=90)
    other = tmp_path / "other.jpg"
    pattern(SIZE_16_9, 12).save(other, "JPEG", quality=90)
    assert hamming(dhash_file(approved), dhash_file(same)) <= 14 < hamming(dhash_file(approved), dhash_file(other))


def test_filer_refuses_download_that_is_not_the_approved_picture(tmp_path):
    root = tmp_path / "anime_kaliya"
    dl = tmp_path / "Downloads"
    dl.mkdir()
    approved = tmp_path / "approved_zoom.png"
    pattern((1200, 700), 11).save(approved)
    dq.add(root, 1, "KRISHNA_TURNAROUND", "v01", EDIT, approved_image=approved)
    pattern(SIZE_16_9, 12).save(dl / f"{TITLE}_a1b2c3_2K.jpg", "JPEG", quality=90)
    out = dq.collect(root, 1, dl)
    assert len(out) == 1 and "does not match the approved picture" in out[0], out
    (dl / f"{TITLE}_a1b2c3_2K.jpg").unlink()
    pattern(SIZE_16_9, 11).save(dl / f"{TITLE}_d4e5f6_2K.jpg", "JPEG", quality=90)
    assert dq.collect(root, 1, dl) == [f"FILED {TITLE} <- {TITLE}_d4e5f6_2K.jpg"]
    fp = log_lines(root)[-1]["fingerprint"]
    assert fp["approved_dhash"] == dhash_file(approved) and fp["hamming"] <= 14


def test_lineage_decided_by_and_final_model_logged(tmp_path):
    root = tmp_path / "anime_kaliya"
    dl = tmp_path / "Downloads"
    dl.mkdir()
    dq.add(root, 1, "KRISHNA_TURNAROUND", "v01", EDIT, model="Nano Banana Pro x2",
           lineage="tile edit of cand B, then Pro regenerate", decided_by="owner")
    with pytest.raises(ValueError):
        dq.add(root, 1, "KRISHNA_ACTING_SHEET", "v01", EDIT, decided_by="robot")
    make_jpg(dl / f"{TITLE}_a1b2c3_2K.jpg", SIZE_16_9, 1)
    assert dq.collect(root, 1, dl)[0].startswith("FILED")
    rec = log_lines(root)[-1]
    assert rec["lineage"] == "tile edit of cand B, then Pro regenerate"
    assert rec["decided_by"] == "owner" and rec["final_model"] == "Nano Banana Pro x2"


def test_accept_is_append_only_and_status_shows_it(tmp_path, capsys):
    root, dl = setup(tmp_path)
    make_jpg(dl / f"{TITLE}_a1b2c3_2K.jpg", SIZE_16_9, 1)
    dq.collect(root, 1, dl)
    dq.accept(root, 1, "KRISHNA_TURNAROUND", "v01", "owner", "looks right")
    dq.accept(root, 1, "KRISHNA_TURNAROUND", "v01", "claude", "second look")
    lines = [json.loads(l) for l in (root / "adhyay_01" / "accepted.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2 and set(lines[0]) == {"time", "shot_id", "version", "accepted_by", "note"} and lines[0]["accepted_by"] == "owner"
    with pytest.raises(ValueError):
        dq.accept(root, 1, "NOT_QUEUED", "v01", "owner")
    assert dq.main(["status", "--root", str(root), "--adhyay", "1"]) == 0
    assert "KRISHNA_TURNAROUND__v01  ACCEPTED by claude" in capsys.readouterr().out


def test_filer_refuses_sub_folder_outside_chapter(tmp_path):
    import subprocess
    root, dl = setup(tmp_path)
    f = make_jpg(dl / f"{TITLE}_a1b2c3_2K.jpg", (2752, 1536), 7)
    r = subprocess.run([sys.executable, str(HERE / "file_flow_download.py"), str(f), "X", "v01", "edit/x", "", "n", "../escape"],
                       capture_output=True, text=True, env={**__import__("os").environ, "FLOW_OUT_ROOT": str(root)})
    assert r.returncode == 2 and "REFUSED" in r.stderr


def test_status_json_lists_pending_filed_and_accepted(tmp_path, capsys):
    """G7: status --json gives the same pending/filed split as the text status (one queued shot filed, one pending, one accepted)."""
    root, dl = setup(tmp_path)
    dq.add(root, 1, "KRISHNA_TURNAROUND", "v01", EDIT)
    dq.add(root, 1, "KRISHNA_ACTING_SHEET", "v01", "34ba531b-b5c7-43fa-82a5-7b7746b57099")
    flow_log = root / "adhyay_01" / "flow_log.jsonl"
    flow_log.write_text(json.dumps({"image_id": "KRISHNA_ACTING_SHEET", "version": "v01"}) + "\n", encoding="utf-8")
    dq.accept(root, 1, "KRISHNA_ACTING_SHEET", "v01", "owner", "ok")
    capsys.readouterr()
    assert dq.main(["status", "--root", str(root), "--adhyay", "1", "--json"]) == 1   # something is still pending
    out = json.loads(capsys.readouterr().out)
    assert [i["shot_id"] for i in out["pending"]] == ["KRISHNA_TURNAROUND"]
    assert [i["shot_id"] for i in out["filed"]] == ["KRISHNA_ACTING_SHEET"]
    assert out["accepted"][0]["accepted_by"] == "owner" and out["accepted"][0]["shot_id"] == "KRISHNA_ACTING_SHEET"
    assert "PENDING" not in json.dumps(out)   # JSON only, no text lines
