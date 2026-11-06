"""Offline tests for tools/secret_scan.py. Fake tokens are built at run time so this file never contains a key-shaped literal."""
import secret_scan as ss

NV = "nvapi-" + "A1b2C3d4" * 2            # built from parts: no key-shaped literal in this source file
OR = "sk-or-v1-" + "x9" * 10
SK = "sk-" + "Q7w8E9r0" * 3
HF = "hf_" + "Zz9" * 8
GOOG = "AIza" + "Sy" + "0" * 33
PRIV = "-----BEGIN " + "RSA PRIVATE KEY-----"
NAMED = 'api_key = "' + "k3y" * 12 + '"'
NO_SUPPORT = frozenset()


def rules_for(text: str) -> list[str]:
    return [rule for _, _, rule, _ in ss.scan([("a.txt", len(text), text.encode())], NO_SUPPORT, [])[0]]


def test_key_shapes_are_blocked():
    for text, rule in [(NV, "K-NVIDIA"), (OR, "K-OPENROUTER"), (SK, "K-OPENAI"), (HF, "K-HF"),
                       (GOOG, "K-GOOGLE"), (PRIV, "K-PRIVKEY"), (NAMED, "K-NAMED")]:
        assert rule in rules_for(text), rule


def test_plain_words_and_hashes_are_not_flagged():
    assert rules_for("task-runner and desk-lamp and risk_score = 3") == []
    sha = "a" * 40
    assert rules_for(f'clip_key = "{sha}"') == []                  # a git sha-1 next to the word key
    assert rules_for('token_expiry_seconds_value_name = "abcdefghijklmnopqrstuvwxyzabcdefgh"') == []   # no digit: an identifier


def test_line_numbers_reported_and_secret_text_never_in_output():
    text = "ok line\n" + NV + "\n"
    findings, _ = ss.scan([("notes.md", len(text), text.encode())], NO_SUPPORT, [])
    assert findings == [("notes.md", 2, "K-NVIDIA", "NVIDIA API key")]
    assert NV not in repr(findings)


def test_path_rules():
    ex = frozenset({"stories/kaliya_mardan/story.json"})
    assert ("P-SECRETS", "path under secrets/") in ss.path_findings("secrets/nvidia/k.txt", 5, ex)
    assert ("P-STORIES", "stories/ path (source, pack or run data)") in ss.path_findings("stories/x/story.json", 5, ex)
    assert [r for r, _ in ss.path_findings("stories/kaliya_mardan/story.json", 5, ex)] == []     # tracked already
    assert [r for r, _ in ss.path_findings("stories/kaliya_mardan/new.json", 5, ex)] == ["P-STORIES"]
    assert "P-TRANSCRIPT" in [r for r, _ in ss.path_findings("stories/kaliya_mardan/SOURCE.md", 5, ex)]
    assert [r for r, _ in ss.path_findings("flow_outputs/a/b.txt", 5, ex)] == ["P-FLOW"]
    assert [r for r, _ in ss.path_findings("docs/clip.MP4", 5, ex)] == ["P-MEDIA"]
    assert [r for r, _ in ss.path_findings("docs/readme.md", 5, ex)] == []
    assert [r for r, _ in ss.path_findings("docs/big.bin", ss.MAX_BYTES + 1, ex)] == ["P-SIZE"]


def test_allowlist_only_for_its_path_rule_and_literal(tmp_path):
    fixture = "nvapi-" + "SECRETVALUE" + "0" * 16       # built from parts, like the other fakes
    allow = [("ui/test_ui.py", "K-NVIDIA", "SECRETVALUE")]
    findings, allowed = ss.scan([("ui/test_ui.py", len(fixture), fixture.encode())], NO_SUPPORT, allow)
    assert findings == [] and allowed == 1
    # the same text in another file is not allowed
    findings, allowed = ss.scan([("other.py", len(fixture), fixture.encode())], NO_SUPPORT, allow)
    assert findings and allowed == 0
    # a real-looking key in the allowed file, without the literal, is still blocked
    real = NV
    findings, _ = ss.scan([("ui/test_ui.py", len(real), real.encode())], NO_SUPPORT, allow)
    assert findings


def test_load_allowlist_reads_repo_file_and_rejects_bad_lines(tmp_path):
    good = ss.load_allowlist()
    assert ("ui/test_ui.py", "K-NVIDIA", "SECRETVALUE") in good
    bad = tmp_path / "allow.txt"
    bad.write_text("# comment\nui/test_ui.py | K-NVIDIA\n", encoding="utf-8")
    try:
        ss.load_allowlist(bad)
    except ValueError as exc:
        assert "need 'path | rule | literal'" in str(exc)
    else:
        raise AssertionError("bad allowlist line accepted")


def fake_git(outputs):
    """outputs: {first git arg or 'verify' key: bytes}; raises GitError for a missing ref."""
    def run(args, root):
        key = " ".join(args)
        for prefix, out in outputs.items():
            if key.startswith(prefix):
                return out
        if args[:2] == ["rev-parse", "--verify"]:
            raise ss.GitError("no such ref")
        raise AssertionError(f"unexpected git call: {key}")
    return run


def test_gather_uses_remote_branch_and_worktree(tmp_path):
    (tmp_path / "new.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_path / "gone.py").write_text("x", encoding="utf-8")   # listed as untracked; scanned from disk
    run = fake_git({
        "rev-parse --abbrev-ref": b"main\n",
        "rev-parse --verify": b"abc\n",
        "ls-tree -r -z --name-only refs/remotes/origin/main": b"old.py\0stories/kaliya_mardan/SOURCE.md\0",
        "diff --name-only -z --diff-filter=ACMR refs/remotes/origin/main..HEAD": b"ui/x.py\0",
        "cat-file blob HEAD:ui/x.py": b"print('hi')\n",
        "diff --name-only -z --diff-filter=ACMR": b"",
        "diff --cached": b"",
        "ls-files -o": b"new.py\0gone.py\0missing.py\0",
    })
    files, upstream = ss.gather("origin", worktree=True, root=tmp_path, run=run)
    names = [f[0] for f in files]
    assert names == ["ui/x.py", "new.py", "gone.py"]           # missing.py is deleted on disk: skipped
    assert "stories/kaliya_mardan/SOURCE.md" in upstream


def test_gather_without_remote_branch_scans_all_of_head(tmp_path):
    run = fake_git({
        "rev-parse --abbrev-ref": b"feature\n",
        "ls-tree -r -z --name-only HEAD": b"a.py\0b.py\0",
        "cat-file blob HEAD:a.py": b"1",
        "cat-file blob HEAD:b.py": b"2",
    })
    files, upstream = ss.gather("origin", worktree=False, root=tmp_path, run=run)
    assert [f[0] for f in files] == ["a.py", "b.py"] and upstream == frozenset()
