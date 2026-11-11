import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import writer_guard  # noqa: E402,F401
import blocking  # noqa: E402,F401
import blocking_lint  # noqa: E402,F401
import script_inspect  # noqa: E402,F401
import source_check  # noqa: E402,F401

_ID_RE = re.compile(r'SHOT-[0-9]{3}')


def error_shot_ids(errors):
    ids = []
    seen = set()
    for line in errors:
        match = _ID_RE.search(line)
        if match is None:
            return None
        shot_id = match.group(0)
        if shot_id not in seen:
            seen.add(shot_id)
            ids.append(shot_id)
    return ids


def repair_prompt(base_prompt, rows, ids, errors):
    selected = [row for row in rows if row.get('id') in ids]
    parts = [base_prompt]
    parts.append('Return ONLY a JSON list with the corrected objects for shots: ' + ', '.join(ids))
    parts.append(json.dumps(selected, ensure_ascii=False, indent=1))
    parts.extend(errors)
    return '\n'.join(parts)


def merge_repair(rows, repaired):
    if not isinstance(repaired, list):
        raise ValueError('repaired must be a list of dicts')
    repaired_by_id = {}
    for item in repaired:
        if not isinstance(item, dict):
            raise ValueError('repaired item is not a dict')
        rid = item.get('id')
        if not isinstance(rid, str):
            raise ValueError('repaired item missing id')
        repaired_by_id[rid] = item
    row_ids = set()
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get('id'), str):
            row_ids.add(row['id'])
    for rid in repaired_by_id:
        if rid not in row_ids:
            raise ValueError('repaired object for unknown id: %s' % rid)
    result = []
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get('id'), str) and row['id'] in repaired_by_id:
            result.append(repaired_by_id[row['id']])
        else:
            result.append(row)
    return result


def repair_file(out, name, k):
    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        raise ValueError('k must be an int >= 1')
    return Path(out) / ('stage_%s_repair%d.json' % (name, k))


def _answer_text(text):
    """The model text: a saved envelope gives its 'result' (a failed call raises); other text is returned as is."""
    try:
        data = json.loads(text)
    except ValueError:
        return text
    if not isinstance(data, dict) or 'result' not in data:
        return text
    if data.get('is_error'):
        raise ValueError('the model call failed or was cut off (%s)' % data.get('finish_reason'))
    if not isinstance(data.get('result'), str):
        raise ValueError('the saved envelope has no text result')
    return data['result']


def parse_repair(text):
    body = _answer_text(text)
    fenced = re.search(r'```(?:json)?\s*\n(.*?)\n```', body, re.DOTALL)
    if fenced is not None:
        candidate = fenced.group(1)
    else:
        candidate = body
    try:
        data = json.loads(candidate)
    except ValueError:
        data = None
    if not isinstance(data, list):
        raise ValueError('no JSON list found')
    for item in data:
        if not isinstance(item, dict):
            raise ValueError('list item is not a dict')
    return data


def claude_budget_args(max_budget_usd):
    if max_budget_usd is None:
        return []
    if isinstance(max_budget_usd, bool):
        raise ValueError('budget must be a number')
    if not isinstance(max_budget_usd, (int, float)):
        raise ValueError('budget must be a number')
    if not math.isfinite(max_budget_usd) or max_budget_usd <= 0:
        raise ValueError('budget must be > 0')
    return ['--max-budget-usd', '%.2f' % max_budget_usd]


def write_blocking_files(out, rows):
    blocking_dir = Path(out) / 'blocking'
    blocking_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('row is not an object')
        rid = row.get('id')
        if not isinstance(rid, str):
            raise ValueError('row missing id')
        sheet = row.get('blocking')
        if not isinstance(sheet, dict):
            raise ValueError('%s: missing dict blocking' % rid)
        path = blocking_dir / (rid + '.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(sheet, f, indent=1, ensure_ascii=False)
        paths.append(path)
    paths.sort(key=lambda p: p.stem)
    return paths


def writer_gate(out, rows, source_text, lang='en', lock=None, est_note=''):
    problems = []
    try:
        problems.extend(writer_guard.validate_pack(rows, os.path.join(out, 'blocking')))
    except Exception as exc:
        problems.append('writer_guard: ' + str(exc))

    sheets = []
    try:
        written = write_blocking_files(out, rows)
    except Exception as exc:
        written = []
        problems.append('write_blocking_files: ' + str(exc))
    for path in written:
        try:
            sheets.append(blocking.load_sheet(str(path)))
        except Exception as exc:
            problems.append('%s: blocking load error: %s' % (path.stem, exc))

    try:
        lint_problems = blocking_lint.lint(sheets, lock=lock)
        if lint_problems:
            problems.extend(lint_problems)
    except Exception as exc:
        problems.append('blocking_lint: ' + str(exc))

    try:
        shots = script_inspect.from_pack(rows, lang)
        result = script_inspect.inspect_script(shots, lang)
        if not result.get('pass', False):
            reasons = result.get('reasons', [])
            if isinstance(reasons, list):
                reasons = [str(r) for r in reasons]
            else:
                reasons = [str(reasons)]
            problems.append('script_inspect: FAIL ' + '; '.join(reasons))
    except ValueError as exc:
        problems.append('script_inspect: ' + str(exc))
    except Exception as exc:
        problems.append('script_inspect: ' + str(exc))

    try:
        citation_problems = source_check.citations(source_text, rows, sheets)
        if citation_problems:
            problems.extend(citation_problems)
    except Exception as exc:
        problems.append('source_check: ' + str(exc))

    shots_sha256 = hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
    result_dict = {
        'shots_sha256': shots_sha256,
        'ok': len(problems) == 0,
        'problems': problems,
    }
    try:
        gate_path = Path(out) / 'writer_gate.json'
        gate_path.parent.mkdir(parents=True, exist_ok=True)
        with open(gate_path, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, indent=1, ensure_ascii=False)
    except Exception:
        pass
    return result_dict


def stage_est_cents(name, env=None):
    if env is None:
        env = os.environ
    raw = env.get('WRITER_STAGE_EST_CENTS', '').strip()
    if raw == '':
        return 150
    if not raw.isdigit() or int(raw) <= 0:
        raise ValueError('WRITER_STAGE_EST_CENTS must be a positive integer')
    return int(raw)


def guarded_claude_call(stage, prompt, raw_call, ledger_path, usage_path, est_cents=None, env=None):
    if env is None:
        env = os.environ
    cap_raw = env.get('WRITER_CAP_CENTS', '').strip()
    if not cap_raw.isdigit() or int(cap_raw) <= 0:
        raise SystemExit('WRITER_CAP_CENTS must be a positive integer')
    cap_value = int(cap_raw)
    from voice_cast import Ledger
    ledger = Ledger(Path(ledger_path), cap_value)
    if est_cents is None:
        est_cents = stage_est_cents(stage, env)
    old_cap = os.environ.get('WRITER_CAP_CENTS')
    had_cap = 'WRITER_CAP_CENTS' in os.environ
    os.environ['WRITER_CAP_CENTS'] = str(cap_value)
    try:
        def call_fn(prompt, max_budget_usd=None):
            return raw_call(prompt, max_budget_usd)
        return writer_guard.guarded_call(stage, prompt, call_fn, ledger, est_cents, Path(usage_path))
    finally:
        if had_cap:
            os.environ['WRITER_CAP_CENTS'] = old_cap
        else:
            os.environ.pop('WRITER_CAP_CENTS', None)
