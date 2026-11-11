import json
import os
import shlex
import shutil
import subprocess
import sys


class EditError(ValueError):
    pass


def parse_edits(text):
    edits = []
    final_marker = 'FINAL:'
    final_idx = text.find(final_marker)
    if final_idx != -1 and '```edit' in text[final_idx:]:
        section = text[final_idx + len(final_marker):]
    else:
        section = text
    start = 0
    while True:
        fence = section.find('```edit', start)
        if fence == -1:
            break
        end_fence = section.find('```', fence + 3)
        if end_fence == -1:
            end_fence = len(section)
        block = section[fence:end_fence]
        if '<<<<<<< OLD' not in block and '\n=======' in block and '>>>>>>> NEW' in block:
            # lenient: models often drop the OLD marker line; the text before ======= is the old text
            head, rest = block.split('\n', 1)
            block = head + '\n<<<<<<< OLD\n' + rest
        lines = block.split('\n')
        first = lines[0]
        parts = first.split(None, 1)
        if len(parts) < 2:
            raise EditError('edit block missing path')
        path = parts[1]
        pos = 0
        found = 0
        while True:
            old_idx = block.find('<<<<<<< OLD', pos)
            if old_idx == -1:
                break
            new_idx = block.find('\n=======', old_idx)
            fin_idx = block.find('>>>>>>> NEW', old_idx)
            if new_idx == -1 or fin_idx == -1 or not (old_idx < new_idx < fin_idx):
                raise EditError('edit block missing marker')
            old_text = block[old_idx + len('<<<<<<< OLD'):new_idx]
            new_text = block[new_idx + len('\n======='):fin_idx]
            if old_text.startswith('\n'):
                old_text = old_text[1:]
            if new_text.startswith('\n'):
                new_text = new_text[1:]
            if new_text.endswith('\n'):
                new_text = new_text[:-1]
            edits.append((path, old_text, new_text))
            found += 1
            pos = fin_idx + len('>>>>>>> NEW')
        if found == 0:
            raise EditError('edit block missing marker')
        start = end_fence + 3
    return edits


def _normalise_newlines(s):
    return s.replace('\r\n', '\n')


def _detect_style(text):
    if '\r\n' in text:
        return '\r\n'
    return '\n'


def _to_style(s, style):
    s = _normalise_newlines(s)
    return s.replace('\n', style)


def _read_text(path):
    with open(path, 'rb') as f:
        data = f.read()
    return data.decode('utf-8')


def _write_text(path, text, style):
    out = text.replace('\r\n', '\n').replace('\n', style)
    with open(path, 'wb') as f:
        f.write(out.encode('utf-8'))


def _check_path(root, path):
    if os.path.isabs(path):
        raise EditError('path must be relative: ' + path)
    norm = path.replace('\\', '/')
    parts = norm.split('/')
    if '..' in parts:
        raise EditError('path must not contain ..: ' + path)
    full = os.path.join(root, path)
    if not os.path.normpath(full).startswith(os.path.normpath(root) + os.sep) and os.path.normpath(full) != os.path.normpath(root):
        raise EditError('path outside root: ' + path)
    return full


def apply_edits(root, edits, allow, allow_tests=False):
    allow_norm = set()
    for a in allow:
        allow_norm.add(a.replace('\\', '/'))
    current = {}
    result = {}
    for (path, old, new) in edits:
        norm = path.replace('\\', '/')
        if norm not in allow_norm:
            raise EditError('path not in allow list: ' + path)
        full = _check_path(root, path)
        if not os.path.isfile(full):
            raise EditError('file does not exist: ' + path)
        base = os.path.basename(norm)
        if base.startswith('test_') and not allow_tests:
            raise EditError('test file refused unless allow_tests: ' + path)
        if old == '':
            raise EditError('empty OLD text refused: ' + path)
        if path in current:
            text = current[path]
        else:
            text = _read_text(full)
            current[path] = text
        style = _detect_style(text)
        old_styled = _to_style(old, style)
        new_styled = _to_style(new, style)
        count = text.count(old_styled)
        if count == 0:
            preview = old_styled[:60]
            raise EditError('old text not found in ' + path + ': ' + preview)
        if count > 1:
            raise EditError('old text is not unique in ' + path + ': ' + str(count) + ' matches')
        text = text.replace(old_styled, new_styled, 1)
        current[path] = text
        result[path] = text
    return result


def write_all(root, new_texts):
    for path, text in new_texts.items():
        full = os.path.join(root, path)
        style = _detect_style(_read_text(full)) if os.path.isfile(full) else '\n'
        _write_text(full, text, style)


def backup(root, paths, backup_dir):
    for path in paths:
        src = os.path.join(root, path)
        dst = os.path.join(backup_dir, path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)


def restore(root, backup_dir):
    restored = []
    for dirpath, dirnames, filenames in os.walk(backup_dir):
        for name in filenames:
            src = os.path.join(dirpath, name)
            rel = os.path.relpath(src, backup_dir).replace('\\', '/')
            dst = os.path.join(root, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            restored.append(rel)
    return sorted(restored)


def run_tests(argv, root, timeout=600):
    proc = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=timeout)
    output = proc.stdout + proc.stderr
    tail = output[-6000:] if len(output) > 6000 else output
    return (proc.returncode == 0, tail)


def build_prompt(task_text, files_text, allow, round_no, last_error=None):
    lines = []
    lines.append('Task:')
    lines.append(task_text)
    lines.append('')
    lines.append('Allowed files:')
    for a in sorted(allow):
        lines.append('  ' + a)
    lines.append('')
    lines.append('Current file contents:')
    for path in sorted(files_text.keys()):
        lines.append('--- ' + path + ' ---')
        lines.append(files_text[path])
        lines.append('--- end ---')
    lines.append('')
    lines.append('Answer format:')
    lines.append('Use one or more edit blocks like this:')
    lines.append('```edit relative/path/to/file.py')
    lines.append('<<<<<<< OLD')
    lines.append('exact old text')
    lines.append('=======')
    lines.append('new text')
    lines.append('>>>>>>> NEW')
    lines.append('```')
    lines.append('')
    lines.append('Every block MUST contain the three marker lines <<<<<<< OLD, ======= and >>>>>>> NEW, each alone on its line.')
    lines.append('OLD is a short exact piece of the CURRENT file (a few lines, enough to be unique); NEW replaces it.')
    lines.append('Never return whole files and never use a ```python block. Several edits = several OLD/NEW pairs.')
    lines.append('To INSERT code: use one existing anchor line as OLD and repeat it first in NEW, followed by the new code.')
    lines.append('An answer without the ======= and >>>>>>> NEW lines is rejected and nothing is applied.')
    lines.append('Example:')
    lines.append('```edit src/a.py')
    lines.append('<<<<<<< OLD')
    lines.append('def f(x):')
    lines.append('    return x')
    lines.append('=======')
    lines.append('def f(x, y=0):')
    lines.append('    return x + y')
    lines.append('>>>>>>> NEW')
    lines.append('```')
    lines.append('Put the final answer after a line containing FINAL: if you want.')
    if round_no > 1 and last_error is not None:
        lines.append('')
        lines.append('Last error (round ' + str(round_no - 1) + '):')
        lines.append(last_error)
    return '\n'.join(lines)


def _save_answer(root, round_no, answer):
    folder = os.path.join(root, '.edit_runner_backup' + os.environ.get('ER_TAG', ''))
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, 'answer_round%d.txt' % round_no), 'w', encoding='utf-8') as f:
        f.write(answer)


def run(task_text, root, allow, test_argv, ask, rounds=4, regions=None, allow_tests=False, backup_dir=None, report_path=None):
    if regions is None:
        regions = {}
    files_text = {}
    for path in allow:
        full = os.path.join(root, path)
        if os.path.isfile(full):
            size = os.path.getsize(full)
            if size < 60000:
                files_text[path] = _read_text(full)
            else:
                if path in regions:
                    text = _read_text(full)
                    lines = text.split('\n')
                    parts = []
                    for (start_line, end_line) in regions[path]:
                        chunk = '\n'.join(lines[start_line - 1:end_line])
                        parts.append(chunk)
                    files_text[path] = '\n'.join(parts)
                else:
                    raise EditError('file too large and no regions given: ' + path)
    backup_made = False
    last_error = None
    ok = False
    for round_no in range(1, rounds + 1):
        prompt = build_prompt(task_text, files_text, allow, round_no, last_error)
        answer = ask(prompt)
        _save_answer(root, round_no, answer)
        try:
            edits = parse_edits(answer)
        except EditError as exc:
            last_error = str(exc)
            continue
        if len(allow) == 1:
            edits = [(allow[0], o, n) for (_p, o, n) in edits]      # one allowed file: a wrong or placeholder path is the same file
        if len(edits) == 0:
            last_error = 'no usable edit block in model answer: use ```edit PATH blocks with <<<<<<< OLD / ======= / >>>>>>> NEW lines; to insert, repeat an anchor line in OLD and NEW'
            continue
        try:
            new_texts = apply_edits(root, edits, allow, allow_tests)
        except EditError as exc:
            last_error = str(exc)
            continue
        if not backup_made:
            paths_to_backup = [a for a in allow if os.path.isfile(os.path.join(root, a))]
            if backup_dir is None:
                backup_dir = os.path.join(root, '.edit_runner_backup' + os.environ.get('ER_TAG', ''))
            backup(root, paths_to_backup, backup_dir)
            backup_made = True
        write_all(root, new_texts)
        for path, text in new_texts.items():
            files_text[path] = text
        ok, output = run_tests(test_argv, root)
        if ok:
            changed = sorted(new_texts.keys())
            result = {'ok': True, 'rounds_used': round_no, 'error': None, 'files': changed}
            if report_path is not None:
                with open(report_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f)
            return result
        last_error = output
    if backup_made and backup_dir is not None:
        restore(root, backup_dir)
    result = {'ok': False, 'rounds_used': rounds, 'error': last_error, 'files': []}
    if report_path is not None:
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(result, f)
    return result


def _dots_call(prompt):
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'flow', 'scripts', 'dots_review.py')
    spec = importlib.util.spec_from_file_location('dots_review', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.review(prompt, [], raw=True, max_tokens=24000)['text']


def _my_keys(keys):
    slot = os.environ.get('ER_KEY_SLOT', '')
    if '/' not in slot:
        return keys
    k, n = slot.split('/', 1)
    mine = keys[int(k)::int(n)]
    return mine or keys


def _nvidia_call(model_id, env_path, prompt):
    """One Nemotron call. The key comes from the cross-process pool (tools/key_pool.py), so any number of parallel jobs
    share the 14 keys with one rolling window per key (9 calls / 60 s) and one cooldown list."""
    import pathlib
    import re
    import time
    import requests
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.dirname(env_path))
    from nvidia_scheduler import load_env_keys, URL
    import key_pool
    keys = load_env_keys(pathlib.Path(env_path))
    pool = key_pool.KeyPool(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ledgers', 'nvidia_pool.json'))
    body = {'model': model_id, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.2,
            'max_tokens': 24000, 'stream': False}
    for _ in range(12):
        idx = pool.acquire()
        try:
            resp = requests.post(URL, headers={'Authorization': 'Bearer ' + keys[idx]}, json=body, timeout=(15, 900))
        except requests.RequestException as exc:
            print('nvidia: %s on key %d' % (type(exc).__name__, idx + 1), file=sys.stderr, flush=True)
            time.sleep(5)
            continue
        if resp.status_code == 429:
            pool.cooldown(idx, 60)
            continue
        if resp.status_code in (401, 403):
            pool.disable(idx)
            continue
        if resp.status_code >= 400:
            print('nvidia: HTTP %d on key %d' % (resp.status_code, idx + 1), file=sys.stderr, flush=True)
            time.sleep(5)
            continue
        try:
            text = resp.json()['choices'][0]['message'].get('content') or ''
        except (ValueError, KeyError, IndexError):
            continue
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.S).strip()
        if text:
            return text
    raise EditError('model gave no usable answer')


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', required=True)
    parser.add_argument('--allow', nargs='+', required=True)
    parser.add_argument('--test', required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--model', required=True, choices=['dots', 'super', 'ultra'])
    parser.add_argument('--rounds', type=int, default=4)
    parser.add_argument('--region', nargs='*', default=[])
    parser.add_argument('--allow-tests', action='store_true')
    parser.add_argument('--report', default=None)
    args = parser.parse_args(argv)
    with open(args.task, 'r', encoding='utf-8') as f:
        task_text = f.read()
    regions = {}
    for r in args.region:
        if ':' not in r:
            print('bad region: ' + r, file=sys.stderr)
            return 2
        path, rest = r.split(':', 1)
        if '-' not in rest:
            print('bad region: ' + r, file=sys.stderr)
            return 2
        start_s, end_s = rest.split('-', 1)
        try:
            start = int(start_s)
            end = int(end_s)
        except ValueError:
            print('bad region: ' + r, file=sys.stderr)
            return 2
        regions[path] = [(start, end)]
    test_argv = shlex.split(args.test)
    if args.model == 'dots':
        def ask(prompt):
            return _dots_call(prompt)
    else:
        env_path = 'D:/aai work/animation_research_tool/.env'
        if args.model == 'super':
            model_id = 'nvidia/nemotron-3.5-super-vl-120b-a12b'
        else:
            model_id = 'nvidia/nemotron-3-ultra-550b-a55b'

        def ask(prompt, model_id=model_id, env_path=env_path):
            return _nvidia_call(model_id, env_path, prompt)
    backup_dir = os.path.join(args.root, '.edit_runner_backup' + os.environ.get('ER_TAG', ''))
    result = run(task_text, args.root, args.allow, test_argv, ask, rounds=args.rounds, regions=regions, allow_tests=args.allow_tests, backup_dir=backup_dir, report_path=args.report)
    if result['ok']:
        return 0
    return 1


if __name__ == '__main__':
    sys.exit(main())
