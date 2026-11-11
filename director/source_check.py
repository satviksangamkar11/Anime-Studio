import json
import hashlib
import os
import sys
from pathlib import Path


class SameModelError(ValueError):
    pass


def line_ids(source_text):
    result = {}
    lines = source_text.splitlines()
    for index, line in enumerate(lines, start=1):
        if line != "":
            result["L%d" % index] = line
    return result


def citations(source_text, rows, sheets):
    ids = line_ids(source_text)
    problems = []

    for sheet in sheets:
        cast = sheet.get("cast", [])
        for member in cast:
            if not isinstance(member, dict):
                problems.append("C1: cast member is not a dict")
                continue
            refs = member.get("source_refs", [])
            name = member.get("name", member.get("id", "unknown"))
            if not isinstance(refs, list):
                problems.append("C1: cast member %s refs must be a list" % name)
                continue
            if len(refs) == 0:
                problems.append("C1: cast member %s has no source_refs" % name)
            for ref in refs:
                if not isinstance(ref, str) or ref not in ids:
                    problems.append("C2: unknown ref %s for cast member %s" % (ref, name))

    for row in rows:
        if not isinstance(row, dict):
            problems.append("C3: row is not a dict")
            continue
        directives = row.get("per_second_directives", [])
        for directive in directives:
            if not isinstance(directive, dict):
                problems.append("C3: directive is not a dict")
                continue
            refs = directive.get("source_refs", [])
            if not isinstance(refs, list):
                problems.append("C3: directive at t0=%s refs must be a list" % directive.get("t0"))
                continue
            if len(refs) == 0:
                problems.append("C3: directive at t0=%s has no source_refs" % directive.get("t0"))
            for ref in refs:
                if not isinstance(ref, str) or ref not in ids:
                    problems.append("C2: unknown ref %s in directive at t0=%s" % (ref, directive.get("t0")))

    return problems


def review(items, reviewer_fn, writer_model, reviewer_model, source_text=''):
    if writer_model == reviewer_model:
        raise SameModelError("writer and reviewer must be different models")
    ids = line_ids(source_text)
    verdicts = []
    for item in items:
        claim = item.get("claim", "")
        refs = item.get("refs", [])
        cited_lines = {}
        for ref in refs:
            cited_lines[ref] = ids.get(ref, "")
        verdict = reviewer_fn(claim, cited_lines)
        verdicts.append({"kind": item.get("kind"), "claim": claim, "verdict": verdict})
    return verdicts


def write_report(path, source_text, shots_text, rows, sheets, items, reviewer_fn, writer_model, reviewer_model):
    source_sha = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    shots_sha = hashlib.sha256(shots_text.encode("utf-8")).hexdigest()
    citation_problems = citations(source_text, rows, sheets)
    verdicts = review(items, reviewer_fn, writer_model, reviewer_model, source_text)
    unsupported_cast = 0
    for verdict in verdicts:
        if verdict.get("verdict") == "unsupported" and verdict.get("kind") == "cast":
            unsupported_cast += 1
    bad_verdict = False
    for verdict in verdicts:
        if verdict.get('verdict') not in ('supported', 'unsupported', 'unclear'):
            bad_verdict = True
    covered = True
    sheet_list = sheets if isinstance(sheets, list) else []
    for sheet in sheet_list:
        cast = sheet.get('cast') if isinstance(sheet, dict) else None
        if not isinstance(cast, list):
            continue
        for member in cast:
            if not isinstance(member, dict):
                continue
            names = [member.get(key) for key in ('name', 'id') if isinstance(member.get(key), str) and member.get(key)]
            hit = False
            for verdict in verdicts:
                claim = str(verdict.get('claim', ''))
                if verdict.get('kind') == 'cast' and any(name in claim for name in names):
                    hit = True
            if not hit:
                covered = False
    passed = len(citation_problems) == 0 and unsupported_cast == 0 and not bad_verdict and covered
    report = {
        "source_sha256": source_sha,
        "shots_sha256": shots_sha,
        "citations": citation_problems,
        "verdicts": verdicts,
        "pass": passed,
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    return report


def main(argv):
    if len(argv) < 2 or argv[0] != "--citations-only":
        print("usage: source_check.py --citations-only source shots_json blocking_dir")
        return 1
    source_path = argv[1]
    shots_path = argv[2]
    blocking_dir = argv[3]
    with open(source_path, "r", encoding="utf-8") as handle:
        source_text = handle.read()
    with open(shots_path, "r", encoding="utf-8") as handle:
        rows = json.load(handle)
    sheets = []
    for entry in os.listdir(blocking_dir):
        if entry.endswith(".json"):
            full = os.path.join(blocking_dir, entry)
            with open(full, "r", encoding="utf-8") as handle:
                sheets.append(json.load(handle))
    problems = citations(source_text, rows, sheets)
    if len(problems) == 0:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
