"""Pre-push guard for the PUBLIC repo (stdlib only): blocks secrets, story sources, transcripts, media and big files.

  python tools/secret_scan.py [--remote origin] [--no-worktree]

Scans the files a push would send:
  - the commits in `<remote>/<branch>..HEAD` (every file of HEAD when that remote branch does not exist yet);
  - unless --no-worktree: the working-tree list (modified, staged and untracked files that git does not ignore).
Exit 0 = clean. Exit 1 = findings (printed as file:line and rule only; the secret text is NEVER printed).
Exit 2 = git or usage error (the pre-push hook treats every non-zero exit as a block).

Allowlist: tools/secret_scan_allowlist.txt, lines `path | rule | literal`: a match is ignored only when it is on that path,
has that rule and the literal text appears in its line (fake test fixtures only).
The hook is .githooks/pre-push. Install once with `git config core.hooksPath .githooks` (the owner runs it)."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = Path(__file__).with_name("secret_scan_allowlist.txt")
MAX_BYTES = 1024 * 1024                                    # 1 MB
BLOCKED_EXT = frozenset({".mp4", ".mov", ".wav", ".mp3", ".safetensors", ".gguf", ".pt", ".ckpt", ".zip",
                         ".png", ".jpg", ".jpeg", ".webp", ".vtt"})
STORY_EXEMPT = "stories/kaliya_mardan/"                    # its tracked files may stay (already on the remote)


def _named_ok(value: str) -> bool:
    """A long token after a key/token word must mix letters and digits, and must not be a git SHA-1 or a sha256 digest."""
    if len(value) in (40, 64) and re.fullmatch(r"[0-9a-fA-F]+", value):
        return False
    return bool(re.search(r"\d", value) and re.search(r"[A-Za-z]", value))


# (rule id, what it is, pattern, optional check on group 1)
RULES = [
    ("K-NVIDIA", "NVIDIA API key", re.compile(r"nvapi-[A-Za-z0-9_\-]{8,}"), None),
    ("K-OPENROUTER", "OpenRouter key", re.compile(r"sk-or-v1-[A-Za-z0-9_\-]{16,}"), None),
    ("K-OPENAI", "sk- style API key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"), None),
    ("K-HF", "Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{20,}"), None),
    ("K-GOOGLE", "Google API key", re.compile(r"AIza[0-9A-Za-z_\-]{35}"), None),
    ("K-GROQ", "Groq key", re.compile(r"\bgsk_[A-Za-z0-9]{20,}"), None),
    ("K-GITHUB", "GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"), None),
    ("K-SLACK", "Slack token", re.compile(r"\bxox[bpars]-[A-Za-z0-9\-]{10,}"), None),
    ("K-PRIVKEY", "private key block", re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----"), None),
    ("K-BEARER", "Bearer token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{30,}"), None),
    ("K-NAMED", "long token next to key/token/secret/password",
     re.compile(r"(?i)(?:key|token|secret|passw(?:or)?d)[\w\-]*[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9+/_\-=.]{32,})"), _named_ok),
]


def path_findings(rel: str, size: int, upstream: frozenset) -> list[tuple[str, str]]:
    parts = rel.split("/")
    found = []
    if "secrets" in parts:
        found.append(("P-SECRETS", "path under secrets/"))
    if "flow_outputs" in parts:
        found.append(("P-FLOW", "flow_outputs/ (generated images and clips)"))
    if rel.startswith("stories/"):
        if parts[-1] == "SOURCE.md":
            found.append(("P-TRANSCRIPT", "SOURCE.md under stories/ (transcript)"))
        if not (rel.startswith(STORY_EXEMPT) and rel in upstream):
            found.append(("P-STORIES", "stories/ path (source, pack or run data)"))
    ext = Path(rel).suffix.lower()
    if ext in BLOCKED_EXT:
        found.append(("P-MEDIA", f"blocked file type {ext}"))
    if size > MAX_BYTES:
        found.append(("P-SIZE", "file over 1 MB"))
    return found


def content_findings(data: bytes):
    """Yield (line number, rule, description, line text). The line text is for the allowlist only; never print it."""
    for n, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
        for rule, what, rx, check in RULES:
            for m in rx.finditer(line):
                if check is None or check(m.group(1)):
                    yield n, rule, what, line
                    break


def load_allowlist(path: Path = ALLOWLIST) -> list[tuple[str, str, str]]:
    if not path.is_file():
        return []
    out = []
    for no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        parts = [p.strip() for p in s.split("|")]
        if len(parts) != 3 or not all(parts):
            raise ValueError(f"allowlist line {no}: need 'path | rule | literal'")
        out.append((parts[0], parts[1], parts[2]))
    return out


def scan(files, upstream: frozenset, allow) -> tuple[list[tuple], int]:
    """files: [(relative posix path, size in bytes, content bytes or b'' when too big to read)].
    Returns (findings as (path, line or None, rule, description), allowlisted match count)."""
    findings, allowed, seen = [], 0, set()

    def add(rel, line, rule, what):
        if (rel, line, rule) not in seen:
            seen.add((rel, line, rule))
            findings.append((rel, line, rule, what))

    for rel, size, data in files:
        for rule, what in path_findings(rel, size, upstream):
            add(rel, None, rule, what)
        for n, rule, what, text in content_findings(data):
            if any(p == rel and r == rule and lit in text for p, r, lit in allow):
                allowed += 1
            else:
                add(rel, n, rule, what)
    return findings, allowed


class GitError(RuntimeError):
    pass


def git(args: list[str], root: Path = ROOT) -> bytes:
    r = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=str(root), capture_output=True)
    if r.returncode != 0:
        raise GitError(f"git {args[0]} failed: {r.stderr.decode('utf-8', 'replace').strip()[:200]}")
    return r.stdout


def _z(out: bytes) -> list[str]:
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def gather(remote: str = "origin", worktree: bool = True, root: Path = ROOT, run=git):
    """-> (files for scan(), upstream paths). `run(args, root)` is injectable for tests."""
    branch = run(["rev-parse", "--abbrev-ref", "HEAD"], root).decode().strip()
    upstream_ref = f"refs/remotes/{remote}/{branch}"
    try:
        run(["rev-parse", "--verify", "-q", upstream_ref], root)
        has_upstream = True
    except GitError:
        has_upstream = False
    if has_upstream:
        upstream = frozenset(_z(run(["ls-tree", "-r", "-z", "--name-only", upstream_ref], root)))
        committed = _z(run(["diff", "--name-only", "-z", "--diff-filter=ACMR", f"{upstream_ref}..HEAD"], root))
    else:
        upstream = frozenset()
        committed = _z(run(["ls-tree", "-r", "-z", "--name-only", "HEAD"], root))
    files = []
    for rel in committed:
        data = run(["cat-file", "blob", f"HEAD:{rel}"], root)
        files.append((rel, len(data), data))
    if worktree:
        names = (_z(run(["diff", "--name-only", "-z", "--diff-filter=ACMR"], root))
                 + _z(run(["diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"], root))
                 + _z(run(["ls-files", "-o", "--exclude-standard", "-z"], root)))
        for rel in dict.fromkeys(names):
            path = root / rel
            if path.is_file():
                size = path.stat().st_size
                files.append((rel, size, path.read_bytes() if size <= MAX_BYTES else b""))
    return files, upstream


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--no-worktree", action="store_true", help="scan only the commits to push")
    a = ap.parse_args(argv)
    try:
        files, upstream = gather(a.remote, worktree=not a.no_worktree)
        allow = load_allowlist()
    except (GitError, ValueError, OSError) as exc:
        print(f"secret_scan: cannot read the push set: {exc}")
        return 2
    findings, allowed = scan(files, upstream, allow)
    for rel, line, rule, what in findings:
        print(f"BLOCK {rel}{'' if line is None else ':' + str(line)} {rule}: {what}")
    if findings:
        print(f"secret_scan: BLOCKED: {len(findings)} finding(s) in {len({f[0] for f in findings})} file(s). "
              "Unstage or remove the file (git rm --cached), or fix the line. Never paste a secret anywhere.")
        return 1
    print(f"secret_scan: clean ({len({f[0] for f in files})} file(s) checked, {allowed} allowlisted match(es))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
