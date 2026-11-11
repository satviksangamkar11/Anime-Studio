import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.edit_runner import (
    EditError,
    apply_edits,
    backup,
    build_prompt,
    parse_edits,
    restore,
    run,
    run_tests,
    write_all,
)


def _write(path, text):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


def test_parse_edits_one_block():
    text = "intro\n```edit a.py\n<<<<<<< OLD\nx = 1\n=======\nx = 2\n>>>>>>> NEW\n```\noutro"
    edits = parse_edits(text)
    assert edits == [('a.py', 'x = 1', 'x = 2')]


def test_parse_edits_two_pairs():
    text = "```edit a.py\n<<<<<<< OLD\nold1\n=======\nnew1\n>>>>>>> NEW\n<<<<<<< OLD\nold2\n=======\nnew2\n>>>>>>> NEW\n```"
    edits = parse_edits(text)
    assert edits == [('a.py', 'old1', 'new1'), ('a.py', 'old2', 'new2')]


def test_parse_edits_final_section():
    text = "garbage\n```edit b.py\n<<<<<<< OLD\nold\n=======\nnew\n>>>>>>> NEW\n```\nFINAL:\n```edit c.py\n<<<<<<< OLD\noldc\n=======\nnewc\n>>>>>>> NEW\n```"
    edits = parse_edits(text)
    assert edits == [('c.py', 'oldc', 'newc')]


def test_parse_edits_no_block():
    assert parse_edits("just text") == []


def test_parse_edits_missing_marker():
    try:
        parse_edits("```edit a.py\n<<<<<<< OLD\nold\n=======\nnew\n```")
        assert False
    except EditError:
        pass


def test_apply_refusals(tmp_path):
    _write(tmp_path / 'keep.py', 'x = 1\n')
    edits = [('keep.py', 'x = 1', 'x = 2')]
    try:
        apply_edits(str(tmp_path), edits, ['other.py'])
        assert False
    except EditError:
        pass
    try:
        apply_edits(str(tmp_path), [('../keep.py', 'x = 1', 'x = 2')], ['keep.py'])
        assert False
    except EditError:
        pass
    try:
        apply_edits(str(tmp_path), [('keep.py', '', 'x = 2')], ['keep.py'])
        assert False
    except EditError:
        pass
    _write(tmp_path / 'test_keep.py', 'x = 1\n')
    try:
        apply_edits(str(tmp_path), [('test_keep.py', 'x = 1', 'x = 2')], ['test_keep.py'])
        assert False
    except EditError:
        pass
    ok = apply_edits(str(tmp_path), [('test_keep.py', 'x = 1', 'x = 2')], ['test_keep.py'], allow_tests=True)
    assert ok == {'test_keep.py': 'x = 2\n'}


def test_apply_missing_file(tmp_path):
    try:
        apply_edits(str(tmp_path), [('nope.py', 'x = 1', 'x = 2')], ['nope.py'])
        assert False
    except EditError:
        pass


def test_apply_zero_and_two_matches(tmp_path):
    _write(tmp_path / 'a.py', 'x = 1\nx = 1\n')
    try:
        apply_edits(str(tmp_path), [('a.py', 'x = 9', 'x = 2')], ['a.py'])
        assert False
    except EditError as exc:
        assert 'old text not found in a.py: x = 9' in str(exc)
    try:
        apply_edits(str(tmp_path), [('a.py', 'x = 1', 'x = 2')], ['a.py'])
        assert False
    except EditError as exc:
        assert 'old text is not unique in a.py: 2 matches' in str(exc)


def test_apply_crlf_kept(tmp_path):
    _write(tmp_path / 'a.py', 'x = 1\r\ny = 2\r\n')
    new_texts = apply_edits(str(tmp_path), [('a.py', 'x = 1', 'x = 9')], ['a.py'])
    assert new_texts['a.py'] == 'x = 9\r\ny = 2\r\n'
    write_all(str(tmp_path), new_texts)
    with open(tmp_path / 'a.py', 'rb') as f:
        data = f.read()
    assert data == b'x = 9\r\ny = 2\r\n'


def test_apply_second_edit_matches_first_result(tmp_path):
    _write(tmp_path / 'a.py', 'x = 1\n')
    new_texts = apply_edits(
        str(tmp_path),
        [('a.py', 'x = 1', 'x = 2'), ('a.py', 'x = 2', 'x = 3')],
        ['a.py'],
    )
    assert new_texts['a.py'] == 'x = 3\n'


def test_write_all_backup_restore(tmp_path):
    _write(tmp_path / 'a.py', 'x = 1\n')
    _write(tmp_path / 'b.py', 'y = 2\n')
    new_texts = {'a.py': 'x = 9\n', 'b.py': 'y = 8\n'}
    backup_dir = tmp_path / 'backup'
    backup(str(tmp_path), ['a.py', 'b.py'], str(backup_dir))
    write_all(str(tmp_path), new_texts)
    _write(tmp_path / 'a.py', 'x = 0\n')
    restored = restore(str(tmp_path), str(backup_dir))
    assert restored == ['a.py', 'b.py']
    with open(tmp_path / 'a.py', 'r', encoding='utf-8') as f:
        assert f.read() == 'x = 1\n'


def test_run_tests_ok_and_fail(tmp_path):
    ok, out = run_tests([sys.executable, '-c', 'import sys; sys.exit(0)'], str(tmp_path))
    assert ok is True
    ok, out = run_tests([sys.executable, '-c', 'import sys; sys.exit(1)'], str(tmp_path))
    assert ok is False


def test_run_success_round_1(tmp_path):
    _write(tmp_path / 'a.py', 'x = 1\n')
    calls = []

    def ask(prompt):
        calls.append(prompt)
        return "```edit a.py\n<<<<<<< OLD\nx = 1\n=======\nx = 2\n>>>>>>> NEW\n```"

    result = run('task', str(tmp_path), ['a.py'], [sys.executable, '-c', 'import sys; sys.exit(0)'], ask, rounds=4)
    assert result['ok'] is True
    assert result['rounds_used'] == 1
    assert result['error'] is None
    assert result['files'] == ['a.py']
    with open(tmp_path / 'a.py', 'r', encoding='utf-8') as f:
        assert f.read() == 'x = 2\n'


def test_run_edit_error_then_success(tmp_path):
    _write(tmp_path / 'a.py', 'x = 1\n')
    states = []

    def ask(prompt):
        states.append(prompt)
        if len(states) == 1:
            return "```edit a.py\n<<<<<<< OLD\nnope\n=======\nyes\n>>>>>>> NEW\n```"
        return "```edit a.py\n<<<<<<< OLD\nx = 1\n=======\nx = 2\n>>>>>>> NEW\n```"

    result = run('task', str(tmp_path), ['a.py'], [sys.executable, '-c', 'import sys; sys.exit(0)'], ask, rounds=4)
    assert result['ok'] is True
    assert result['rounds_used'] == 2
    assert 'old text not found' in states[1]
    with open(tmp_path / 'a.py', 'r', encoding='utf-8') as f:
        assert f.read() == 'x = 2\n'


def test_run_all_rounds_fail_files_restored(tmp_path):
    _write(tmp_path / 'a.py', 'x = 1\n')
    original = (tmp_path / 'a.py').read_bytes()

    def ask(prompt):
        return "```edit a.py\n<<<<<<< OLD\nx = 1\n=======\nx = 2\n>>>>>>> NEW\n```"

    result = run('task', str(tmp_path), ['a.py'], [sys.executable, '-c', 'import sys; sys.exit(1)'], ask, rounds=2)
    assert result['ok'] is False
    assert result['rounds_used'] == 2
    assert result['error'] is not None
    assert result['files'] == []
    assert (tmp_path / 'a.py').read_bytes() == original


def test_run_failing_test_then_fixed(tmp_path):
    _write(tmp_path / 'a.py', 'x = 1\n')
    seen = []

    def ask(prompt):
        seen.append(prompt)
        if 'Last error' in prompt:
            return "```edit a.py\n<<<<<<< OLD\nx = 3\n=======\nx = 2\n>>>>>>> NEW\n```"
        return "```edit a.py\n<<<<<<< OLD\nx = 1\n=======\nx = 3\n>>>>>>> NEW\n```"

    def test_cmd():
        return [sys.executable, '-c', 'import sys; content=open(r"' + str(tmp_path / 'a.py') + '").read(); sys.exit(0 if "x = 2" in content else 1)']

    result = run('task', str(tmp_path), ['a.py'], test_cmd(), ask, rounds=4)
    assert result['ok'] is True
    assert 'Last error' in seen[1]


def test_run_report_written(tmp_path):
    _write(tmp_path / 'a.py', 'x = 1\n')
    report = tmp_path / 'report.json'

    def ask(prompt):
        return "```edit a.py\n<<<<<<< OLD\nx = 1\n=======\nx = 2\n>>>>>>> NEW\n```"

    run('task', str(tmp_path), ['a.py'], [sys.executable, '-c', 'import sys; sys.exit(0)'], ask, rounds=4, report_path=str(report))
    with open(report, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert data['ok'] is True
    assert data['files'] == ['a.py']
