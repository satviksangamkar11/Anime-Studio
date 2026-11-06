"""Offline tests for director/ops_checks.py: fake disk usage, fake UI fetch, temp ledger, fake sleep. No network."""
import datetime as dt
import json
import os
import time
import urllib.error
from types import SimpleNamespace

import pytest

import ops_checks as oc

TZ = dt.timezone(dt.timedelta(hours=5, minutes=30))
NOW = dt.datetime(2026, 11, 7, 12, 0, tzinfo=TZ)     # a Saturday; ISO week 45


def usage_gb(gb):
    return lambda path: SimpleNamespace(free=int(gb * oc.GB))


D_RENDER = "D:/aai work/renders"                 # tests run on C: (temp folder), so the big-file rule needs a D: path


def test_disk_free_thresholds():
    assert oc.disk_free(D_RENDER, usage_gb(1))["status"] == "block"
    assert oc.disk_free(D_RENDER, usage_gb(3))["status"] == "warn"
    ok = oc.disk_free(D_RENDER, usage_gb(9))
    assert ok["status"] == "ok" and ok["free_gb"] == 9.0


def test_disk_free_never_takes_c_for_big_files():
    res = oc.disk_free("C:/anything/render", usage_gb(200))      # the path does not need to exist: the drive is what counts
    if os.name == "nt":
        assert res["status"] == "block" and "D:" in res["reason"]
    else:
        assert res["drive"] == ""


def test_disk_free_asks_nearest_existing_folder(tmp_path):
    asked = []

    def usage(p):
        asked.append(p)
        return SimpleNamespace(free=10 * oc.GB)
    oc.disk_free(tmp_path / "not" / "yet", usage)
    assert asked == [str(tmp_path)]


def fake_fetch(pipeline, registry=None, fail=None):
    def fetch(url, timeout):
        assert timeout <= 5                              # short timeout
        if fail and url.endswith(fail):
            raise urllib.error.URLError("refused")
        return pipeline if url.endswith("/api/pipeline") else (registry or [])
    return fetch


def test_health_ok_stale_unverified_unreachable():
    assert oc.ui_server_health("http://127.0.0.1:8765", fetch=fake_fetch({"code_fingerprint": "abc"}), local="abc")["status"] == "ok"

    stale = oc.ui_server_health("http://127.0.0.1:8765", fetch=fake_fetch({"code_fingerprint": "old"}), local="abc")
    assert stale["status"] == "stale or unreachable" and "differs" in stale["reasons"][0]

    unverified = oc.ui_server_health("http://127.0.0.1:8765", fetch=fake_fetch({}), local="abc")
    assert unverified["status"] == "unverified" and unverified["server_fingerprint"] is None

    down = oc.ui_server_health("http://127.0.0.1:8765/", fetch=fake_fetch({}, fail="/api/registry"), local="abc")
    assert down["status"] == "stale or unreachable" and "/api/registry unreachable (URLError)" in down["reasons"]


def test_code_fingerprint_changes_with_the_file(tmp_path):
    (tmp_path / "ui" / "static").mkdir(parents=True)
    (tmp_path / "ui" / "server.py").write_text("a", encoding="utf-8")
    (tmp_path / "ui" / "static" / "pipeline.js").write_text("b", encoding="utf-8")
    first = oc.code_fingerprint(tmp_path)
    assert len(first) == 16 and first == oc.code_fingerprint(tmp_path)
    (tmp_path / "ui" / "server.py").write_text("changed", encoding="utf-8")
    assert oc.code_fingerprint(tmp_path) != first


def test_record_and_total_by_day_and_week(tmp_path):
    ledger = tmp_path / "runs" / "spend.jsonl"
    oc.record_spend(ledger, units=6.7, session="t0-a", story="s1", reason="T0 clips", now=NOW)
    oc.record_spend(ledger, units=2.5, session="t0-b", story="s1", reason="retry", now=NOW - dt.timedelta(hours=2))
    oc.record_spend(ledger, units=4.0, session="t0-c", story="s2", reason="older", now=NOW - dt.timedelta(days=3))
    oc.record_spend(ledger, units=1.0, session="t0-d", story="s2", reason="last week", now=NOW - dt.timedelta(days=9))
    t = oc.colab_spend_total(ledger, now=NOW)
    assert t == {"total": 14.2, "today": 9.2, "this_week": 13.2, "runs": 4, "bad_lines": 0}
    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4 and json.loads(lines[0])["session"] == "t0-a"        # append only, in order


def test_bad_lines_are_counted_not_fatal(tmp_path):
    ledger = tmp_path / "l.jsonl"
    ledger.write_text('{"time": "2026-11-07T10:00:00+05:30", "units": 3}\nnot json\n{"units": 2}\n', encoding="utf-8")
    t = oc.colab_spend_total(ledger, now=NOW)
    assert t["total"] == 3.0 and t["bad_lines"] == 2


def test_missing_ledger_is_zero(tmp_path):
    assert oc.colab_spend_total(tmp_path / "none.jsonl", now=NOW)["total"] == 0


def test_record_refuses_bad_input(tmp_path):
    for units in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            oc.record_spend(tmp_path / "l.jsonl", units=units, session="s", story="x", reason="r", now=NOW)
    with pytest.raises(ValueError):
        oc.record_spend(tmp_path / "l.jsonl", units=1, session="s", story="x", reason="  ", now=NOW)


def test_lock_fresh_holder_times_out_with_fake_sleep(tmp_path):
    ledger = tmp_path / "l.jsonl"
    (tmp_path / "l.jsonl.lock").write_text("held", encoding="utf-8")       # a live writer holds it
    waits = []
    with pytest.raises(TimeoutError):
        oc.record_spend(ledger, units=1, session="s", story="x", reason="r", now=NOW, sleep=waits.append, tries=3)
    assert waits == [0.1, 0.1, 0.1] and not ledger.exists()


def test_stale_lock_from_a_crashed_writer_is_removed(tmp_path):
    lock = tmp_path / "l.jsonl.lock"
    lock.write_text("crashed", encoding="utf-8")
    old = time.time() - oc.LOCK_STALE_SECONDS - 30
    os.utime(lock, (old, old))
    oc.record_spend(tmp_path / "l.jsonl", units=1, session="s", story="x", reason="r", now=NOW, sleep=lambda d: None)
    assert not lock.exists() and oc.colab_spend_total(tmp_path / "l.jsonl", now=NOW)["total"] == 1.0


def test_check_spend_caps():
    ledger = "no-such-ledger.jsonl"
    assert oc.check_spend(15, ledger, NOW)["ok"]
    assert not oc.check_spend(15.1, ledger, NOW)["ok"]
    assert "per-run cap" in oc.check_spend(16, ledger, NOW)["blockers"][0]
    assert not oc.check_spend(1, ledger, NOW, day_cap=0.5)["ok"]          # a day cap is enforced once the owner sets it
    assert not oc.check_spend(1, ledger, NOW, week_cap=0.5)["ok"]
    assert not oc.check_spend(0, ledger, NOW)["ok"]


def test_check_before_render_combines_disk_spend_and_reminder(tmp_path):
    ledger = tmp_path / "l.jsonl"
    good = oc.check_before_render(D_RENDER, estimate_units=6.7, session="t0-a", ledger_path=ledger, now=NOW, usage=usage_gb(20))
    assert good["ok"] and good["blockers"] == [] and "colab stop -s t0-a" in good["reminder"]
    assert "never use --logtostderr" in good["reminder"]

    low = oc.check_before_render(D_RENDER, ledger_path=ledger, now=NOW, usage=usage_gb(1))
    assert not low["ok"] and low["spend"] is None                          # local render: no Colab spend check

    warn = oc.check_before_render(D_RENDER, ledger_path=ledger, now=NOW, usage=usage_gb(3))
    assert warn["ok"] and warn["warnings"]

    capped = oc.check_before_render(D_RENDER, estimate_units=20, ledger_path=ledger, now=NOW, usage=usage_gb(20))
    assert not capped["ok"] and any("per-run cap" in b for b in capped["blockers"])
