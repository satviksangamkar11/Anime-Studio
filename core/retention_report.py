"""Retention dips -> shot ids (WP9, COLOUR_AUDIT 5.5). Usage:
  python -m core.retention_report EPISODE_BUILD_DIR ANALYTICS.json
Maps each dip (seconds from the episode start, from YouTube Studio) to the shot whose editorial window covers it and writes
retention_dips.json into the build dir. Windows come from the h3 story (timing_and_lattice.master_reel_window_sec) or from
shots.json (cumulative editorial frames per episode at 24 fps). Exit 0 ok, 2 bad input."""
import argparse
import json
import math
import sys
from pathlib import Path

FPS = 24
DIRECTOR = Path(__file__).resolve().parents[1] / "director"
OUT_NAME = "retention_dips.json"


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _load_json(path, label):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise ValueError(f"{label} not found: {path}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"{label} {path} is not valid JSON: {e}") from e
    except (OSError, UnicodeDecodeError) as e:
        raise ValueError(f"cannot read {label} {path}: {e}") from e


def _read_analytics(path):
    """(episode or None, [{"t", "drop_pct"}]) from the hand-filled analytics template; ValueError when malformed."""
    data = _load_json(path, "analytics")
    if not isinstance(data, dict):
        raise ValueError("analytics must be a JSON object")
    dips = data.get("dips")
    if not isinstance(dips, list):
        raise ValueError("analytics 'dips' must be a list")
    clean = []
    for i, dip in enumerate(dips):
        if not isinstance(dip, dict):
            raise ValueError(f"dip {i} must be an object with 't' and 'drop_pct'")
        for name in ("t", "drop_pct"):
            if not _is_number(dip.get(name)):
                raise ValueError(f"dip {i}: '{name}' must be a finite number, got {dip.get(name)!r}")
        if dip["t"] < 0:
            raise ValueError(f"dip {i}: 't' must be 0 or more seconds")
        clean.append({"t": dip["t"], "drop_pct": dip["drop_pct"]})
    return data.get("episode"), clean


def _h3_windows(data, name):
    """{episode_id: [(shot_id, start_s, end_s)]} from an h3 story; ValueError when the file is not one."""
    if not isinstance(data, dict) or not isinstance(data.get("episodes"), list) or not data["episodes"]:
        raise ValueError(f"{name} is not an h3 story")
    out = {}
    for ep in data["episodes"]:
        if not isinstance(ep, dict) or "episode_id" not in ep or not isinstance(ep.get("shots"), list):
            raise ValueError(f"{name}: each episode needs episode_id and shots")
        windows = []
        for shot in ep["shots"]:
            tl = shot.get("timing_and_lattice") if isinstance(shot, dict) else None
            win = tl.get("master_reel_window_sec") if isinstance(tl, dict) else None
            if not (isinstance(win, list) and len(win) == 2 and all(_is_number(x) for x in win) and win[0] <= win[1]):
                raise ValueError(f"{name}: a shot has no valid timing_and_lattice.master_reel_window_sec")
            windows.append((str(shot["shot_id"]), float(win[0]), float(win[1])))
        out[ep["episode_id"]] = windows
    return out


def _frames_for_shot(shot):
    if str(DIRECTOR) not in sys.path:
        sys.path.insert(0, str(DIRECTOR))
    try:
        from h3_director import frames_for_shot
    except Exception as e:
        raise ValueError(f"cannot load frames_for_shot from director/h3_director.py: {e}") from e
    try:
        return frames_for_shot(shot)
    except (KeyError, TypeError) as e:
        raise ValueError(f"shot {shot.get('id')!r} has no usable length: {e}") from e


def _v22_windows(shots, name):
    """{episode: [(shot_id, start_s, end_s)]}: editorial frames = edit_frames if present, else frames_for_shot (A6 / INTERFACES)."""
    if not isinstance(shots, list):
        raise ValueError(f"{name} must be a list of shots")
    out, cursor = {}, {}
    for shot in shots:
        if not isinstance(shot, dict):
            raise ValueError(f"{name}: every shot must be an object")
        if "edit_frames" in shot:
            frames = shot["edit_frames"]
            if isinstance(frames, bool) or not isinstance(frames, int) or frames < 1:
                raise ValueError(f"shot {shot.get('id')!r}: edit_frames must be a positive integer")
        else:
            frames = _frames_for_shot(shot)
        key = shot.get("episode")
        start = cursor.get(key, 0)
        cursor[key] = start + frames
        out.setdefault(key, []).append((str(shot.get("id")), start / FPS, (start + frames) / FPS))
    return out


def _load_windows(build):
    """(source file name, {episode: windows}). story_h3.json first, else the one h3 story in the dir, else shots.json."""
    story = build / "story_h3.json"
    if story.is_file():
        return story.name, _h3_windows(_load_json(story, "story_h3.json"), story.name)
    found = []
    for path in sorted(build.glob("*.json")):
        try:
            found.append((path.name, _h3_windows(json.loads(path.read_text(encoding="utf-8")), path.name)))
        except (ValueError, OSError, UnicodeDecodeError):
            continue
    if len(found) > 1:
        raise ValueError("more than one h3 story in the build dir: " + ", ".join(name for name, _ in found))
    if found:
        return found[0]
    shots = build / "shots.json"
    if shots.is_file():
        return shots.name, _v22_windows(_load_json(shots, "shots.json"), shots.name)
    raise ValueError(f"no story_h3.json, h3 story or shots.json in {build}")


def retention_report(build_dir, analytics_path):
    """Maps each analytics dip to a shot id, writes <build_dir>/retention_dips.json and returns the same dict.
    A dip exactly on a window boundary belongs to the shot that starts there."""
    build = Path(build_dir)
    if not build.is_dir():
        raise ValueError(f"build dir not found: {build}")
    wanted, dips = _read_analytics(analytics_path)
    source, episodes = _load_windows(build)
    if wanted is None:
        if len(episodes) != 1:
            raise ValueError(f"analytics has no 'episode' and {source} has {len(episodes)} episodes")
        key = next(iter(episodes))
    else:
        matches = [k for k in episodes if str(k) == str(wanted)]
        if not matches:
            raise ValueError(f"episode {wanted!r} is not in {source} (it has: {', '.join(map(str, episodes))})")
        key = matches[0]
    windows = episodes[key]
    mapped, unmapped = [], []
    for dip in sorted(dips, key=lambda d: d["t"]):
        t = dip["t"]
        hit = next(((sid, a, b) for sid, a, b in windows if a <= t < b), None)
        if hit is None:
            unmapped.append({"t": t, "drop_pct": dip["drop_pct"]})
        else:
            sid, a, b = hit
            mapped.append({"t": t, "drop_pct": dip["drop_pct"], "shot_id": sid, "window": [a, b],
                           "offset_in_shot_s": round(t - a, 3)})
    report = {"episode": key, "source": source, "dips": mapped, "unmapped": unmapped}
    (build / OUT_NAME).write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Map retention dips to shot ids; writes retention_dips.json into the build dir.")
    ap.add_argument("build_dir", help="episode build dir with story_h3.json or shots.json")
    ap.add_argument("analytics", help="analytics JSON: {episode, uploaded, viewed_pct, swiped_pct, avg_pct_viewed, dips: [{t, drop_pct}]}")
    a = ap.parse_args(argv)
    try:
        report = retention_report(a.build_dir, a.analytics)
    except ValueError as e:
        print(f"retention_report: {e}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
