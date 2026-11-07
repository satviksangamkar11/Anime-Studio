"""ui/i18n_merge.py: locked, group-limited merging of UI strings (parallel coders T3 and T4)."""
import json
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import i18n_merge as im  # noqa: E402


def make(tmp_path, en=None, mr=None):
    (tmp_path / "en.json").write_text(json.dumps(en or {"app.title": "Studio"}), encoding="utf-8")
    (tmp_path / "mr.json").write_text(json.dumps(mr or {"app.title": "स्टुडिओ"}), encoding="utf-8")
    return tmp_path


def read(d, lang):
    return json.loads((d / f"{lang}.json").read_text(encoding="utf-8"))


def test_adds_keys_to_both_languages_sorted_and_keeps_old(tmp_path):
    d = make(tmp_path)
    res = im.merge({"en": {"step.go": "Go"}, "mr": {"step.go": "जा"}}, ["step"], d)
    assert res == {"en": (1, 0, 0), "mr": (1, 0, 0)}
    assert list(read(d, "en")) == ["app.title", "step.go"] and read(d, "mr")["step.go"] == "जा"
    assert im.merge({"en": {"step.go": "Go"}, "mr": {"step.go": "जा"}}, ["step"], d)["en"] == (0, 1, 0)   # idempotent


def test_refuses_keys_outside_the_group_and_nothing_is_written(tmp_path):
    d = make(tmp_path)
    before = (d / "en.json").read_bytes()
    with pytest.raises(im.Refused, match="outside your groups"):
        im.merge({"en": {"adv.x": "X"}, "mr": {"adv.x": "क्ष"}}, ["step"], d)
    assert (d / "en.json").read_bytes() == before


def test_refuses_a_changed_text_unless_replace(tmp_path):
    d = make(tmp_path)
    with pytest.raises(im.Refused, match="different text"):
        im.merge({"en": {"app.title": "Other"}, "mr": {"app.title": "दुसरे"}}, ["app"], d)
    assert im.merge({"en": {"app.title": "Other"}, "mr": {"app.title": "दुसरे"}}, ["app"], d, replace=True)["en"] == (0, 0, 1)


def test_refuses_unequal_key_sets_bad_keys_and_empty_text(tmp_path):
    d = make(tmp_path)
    for batch, msg in (({"en": {"step.a": "A"}, "mr": {}}, "same keys"), ({"en": {"Step.A": "A"}, "mr": {"Step.A": "ए"}}, "bad key"),
                       ({"en": {"step.a": " "}, "mr": {"step.a": "ए"}}, "empty"), ({}, "no keys")):
        with pytest.raises(im.Refused, match=msg):
            im.merge(batch, ["step"], d)
    with pytest.raises(im.Refused, match="lower-case names"):
        im.merge({"en": {"step.a": "A"}, "mr": {"step.a": "ए"}}, ["Step"], d)
    assert im.merge({"en": {"step.a": "A"}, "mr": {"step.a": "ए"}}, ["step", ""], d)["en"][0] == 1   # a trailing comma is harmless


def test_stale_lock_is_removed_and_a_failed_second_replace_changes_neither_file(tmp_path, monkeypatch):
    import os
    d = make(tmp_path)
    lock = d / ".lock"
    lock.write_text("")
    os.utime(lock, (0, 0))                                            # left behind by a killed process
    batch = {"en": {"step.a": "A"}, "mr": {"step.a": "ए"}}
    real, calls = os.replace, []

    def flaky(src, dst):
        calls.append(dst)
        if len(calls) == 2:
            raise PermissionError("locked")
        return real(src, dst)
    monkeypatch.setattr(im.os, "replace", flaky)
    before = ((d / "en.json").read_bytes(), (d / "mr.json").read_bytes())
    with pytest.raises(PermissionError):
        im.merge(batch, ["step"], d)
    assert ((d / "en.json").read_bytes(), (d / "mr.json").read_bytes()) == before and not lock.exists()


def test_missing_files_are_refused(tmp_path):
    with pytest.raises(im.Refused, match="missing"):
        im.merge({"en": {"step.a": "A"}, "mr": {"step.a": "ए"}}, ["step"], tmp_path)


def test_two_coders_merging_at_once_lose_nothing(tmp_path):
    d = make(tmp_path)
    errors = []

    def run(group, n):
        try:
            for i in range(n):
                im.merge({"en": {f"{group}.k{i}": "x"}, "mr": {f"{group}.k{i}": "य"}}, [group], d)
        except Exception as exc:   # pragma: no cover
            errors.append(exc)
    ts = [threading.Thread(target=run, args=(g, 15)) for g in ("step", "adv")]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors and len(read(d, "en")) == 31 and len(read(d, "mr")) == 31 and not (d / ".lock").exists()


def test_cli_exit_codes(tmp_path):
    d = make(tmp_path)
    batch = tmp_path / "b.json"
    batch.write_text(json.dumps({"en": {"step.a": "A"}, "mr": {"step.a": "ए"}}), encoding="utf-8")
    assert im.main([str(batch), "--prefix", "step", "--dir", str(d)]) == 0
    assert im.main([str(batch), "--prefix", "adv", "--dir", str(d)]) == 2
