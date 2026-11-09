# RENDER R1 (xing) 11-09 00:18

The user wants me to act as a strict pre-flight reviewer for a paid GPU render. I need to find REAL defects that would waste compute units, hang, lose clips, leave a session running, or give wrong video. The context is a Colab batch run on a G4 GPU.

Let me analyze the files carefully:

1. `build_h3_batch.py` - builds the batch run.py from an H3 story
2. `run_colab_batch.py` - runs the built batch using the `colab` CLI
3. `t0_pack/run_t0_colab.py` - the sequence it reuses (the actual run logic)
4. `run.py AS BUILT` - what actually runs on the Colab G4
5. Settings of SHOT-001 and SHOT-002
6. All frames counts
7. Last run failure facts

Key facts from the failure:
- run.py was 19.7 MB; never reached the VM (colab exec hung)
- New run.py is 11.3 MB (JPEG q90 keyframes, 768x1344)
- T0's 7 MB run.py worked on 2026-11-05
- ~1.7 compute units burned
- colab log shows no EXEC of run.py
- /content had no out/ and no Wan2GP after 13 min

So the first attempt failed because the script never reached the VM. The second attempt (11.3 MB) presumably worked. But I need to find defects that would waste compute units, hang, lose clips, leave a session running, or give wrong video.

Let me look at each file carefully.

### File 1: `director/build_h3_batch.py`

Line 6-16: imports. `from h3.compile_h3_sing8 import compile_fl2va_prompt`. This is fine.

Line 19-39: `jpeg_b64` function. This converts keyframes to JPEG q90 base64. The comment says "Wan2GP opens the file by content, so the .png name run_kaggle gives it does no harm." This is a workaround. But wait - the settings reference `keyframes__SHOT-001-A.png` as the image path. The run.py writes these to `inputs/name` where name comes from the base64 blob keys. So the file names are like `keyframes__SHOT-001-A.png`. That's fine.

Actually wait, let me re-read. In `legacy_rows`, line 55: `"start": f"keyframes/{sid}-A.png", "end": f"keyframes/{sid}-B.png"`. These are relative paths. Then in `main`, line 72: `run_kaggle.png_b64 = lambda path: jpeg_b64(path, (w, h))`. So `run_kaggle.build` uses this to convert the PNG paths to base64 JPEG strings. The run.py then decodes them and writes to `inputs/<name>` where name is the key from the blob.

Hmm, but the settings have `image_start` and `image_end` pointing to `/content/Wan2GP/inputs/keyframes__SHOT-001-A.png`. So the file written by run.py is named `keyframes__SHOT-001-A.png` and placed in `/content/Wan2GP/inputs/`. That matches.

But wait - the JPEG bytes are stored under `.png` names. The comment says "Wan2GP opens the file by content, so the .png name run_kaggle gives it does no harm." This is a hack but might work. However, there's a potential issue: if Wan2GP checks the file extension or tries to parse it as PNG, the JPEG bytes under a .png name could cause issues. But the comment claims it works, so maybe it's fine. Actually, this could be a real defect if Wan2GP validates the file format by extension. But the comment says it works, so I'll note it as low severity but potentially real.

Actually, let me think about this more carefully. The JPEG is ~0.3 MB vs PNG ~2.7 MB. The run.py is 11.3 MB after this change. The original was 19.7 MB. So the JPEG conversion reduced size significantly. But the question is whether storing JPEG bytes under .png names causes problems. If Wan2GP reads the file by content (as the comment states), it should be fine. But if it checks the extension or tries to open with PIL expecting PNG, it could fail. This is a potential defect but the comment suggests it's been tested. Let me flag it as low.

Line 42-58: `legacy_rows`. Looks correct. It iterates episodes, shots, filters by ids, compiles prompt, builds rows.

Line 61-78: `main`. Parses args, loads story, calls legacy_rows, sets png_b64, calls run_kaggle.build, writes run.py and manifest. Looks correct.

Wait, line 72: `script, _ = run_kaggle.build(...)`. The return value - what does run_kaggle.build return? It returns the script string. The `_` discards the second value. This seems fine.

### File 2: `director/run_colab_batch.py`

Line 94-96: Sets up t0 module. Fine.

Line 99-125: `main`. Sets RUN_PY, RESULTS, DRY. Checks if RUN_PY exists. Prints dry/live. Calls t0.batch. Catches CliError and OSError. Catches BaseException for interrupt/bug - prints session may still run message and re-raises.

Potential issue: Line 117-119: `except BaseException:` catches everything including KeyboardInterrupt, SystemExit, etc. If the process is interrupted (Ctrl+C), it prints the warning and re-raises. That's actually good behavior. But the concern is "leave a session running" - if an exception occurs mid-batch, the session might still be running. The code does print a warning to check sessions. But it doesn't actually stop the session. Hmm, but the t0.batch function has a finally block that stops the session. Wait, let me check t0.batch again.

Actually, looking at t0.batch (line 185-201):
```python
def batch(name, gpu):
    cli(["usage"])
    error = None
    try:
        cli(["new", "-s", name, "--gpu", gpu])
        try:
            cli(["exec", "-s", name, "-f", str(RUN_PY), "--timeout", str(EXEC_TIMEOUT)])
        except CliError as e:
            error = e   # the clips that finished still come home
        cli(["exec", "-s", name], stdin=LIST_CODE)
        fetch(name)
    except CliError as e:   # the clips exist only on the VM: keep it so they can be fetched by hand, then stop it
        print(f"SESSION KEPT (clips still on the VM): fix the download, then run: colab stop -s {name}")
        raise e
    cli(["stop", "-s", name])   # only after the clips are home; a running session keeps spending units
    if error:
        raise error
```

Wait, there's a problem here. The `cli(["exec", "-s", name], stdin=LIST_CODE)` on line 194 - this execs the run.py with stdin being the LIST_CODE. But the LIST_CODE lists mp4 files and other files. This exec command will run the entire run.py script which includes all the rendering. But wait - the run.py already does its own listing internally? No, looking at run.py, it doesn't list files; it just renders. The LIST_CODE is used to list output files after the exec completes.

Actually, the flow is:
1. `colab exec -f run.py --timeout 6*3600` - runs the full batch (renders all shots)
2. `colab exec -s name` with stdin=LIST_CODE - this runs... what? The stdin is Python code that lists files. But `colab exec` without `-f` runs the default command? Or does it run nothing? Actually, `colab exec -s name` without `-f` would run the default shell command or nothing meaningful. The stdin provides input to whatever command runs.

Hmm, this is confusing. Let me re-read. `cli(["exec", "-s", name], stdin=LIST_CODE)` - this runs `colab exec -s <session>` with stdin being the Python code. But `colab exec` without `-f` doesn't execute a specific file. It might run the default command which could be `python3` or something. The stdin would be piped to that command. This seems like it might not do what's intended.

Actually, looking more carefully at the docstring: "a list script on stdin names the .mp4 files and timeline.txt, RESULT.json, gpu.csv under /content/out into FILES.txt". So the intent is that after the exec completes, you run another exec that executes a Python script (LIST_CODE) which writes FILES.txt. But `colab exec -s name` without `-f` doesn't run a specific file. You'd need `colab exec -s name -f <script>` or use `colab exec -s name python3 -c "..."`.

Wait, actually `colab exec` can take stdin and run it as a command. Let me think... `colab exec -s <session>` with stdin piped to it would run the stdin as a command? No, `colab exec` expects either `-f <file>` or a command. Without `-f`, it might run the default command. The stdin is provided via `input=` parameter.

Actually, I think the intent might be that `colab exec -s name` runs the default command (maybe `python3`) and the stdin is the LIST_CODE. But that would execute the LIST_CODE as Python code, which would write FILES.txt. That could work if the default command is `python3`.

But this is fragile. More importantly, the bigger issue is:

The first attempt failed because run.py was 19.7 MB and never reached the VM. The second attempt is 11.3 MB. But the question asks about defects that waste compute units, hang, lose clips, leave a session running, or give wrong video.

Let me focus on the actual defects:

**Defect 1: `colab exec -f run.py` timeout vs script size.**
The EXEC_TIMEOUT is 6*3600 = 21600 seconds (6 hours). But the failure says the 19.7 MB script never reached the VM. Why? Possibly because the script is too large for the exec command to handle, or the upload/transfer failed. But the second attempt (11.3 MB) worked. So the size matters. But is there a defect in the timeout logic? The timeout is set to 6 hours, which should be plenty. But if the script is too large, colab might reject it before execution. This isn't really a code defect though - it's a packaging issue.

Actually, wait. Let me reconsider. The failure says "colab log shows no EXEC of run.py". This means the exec command never even started. This could be because:
- The script is too large (19.7 MB) and colab's exec has a size limit
- The transfer failed

But the question asks about defects in the code that waste compute units. Let me look for actual bugs.

**Defect 2: The `except BaseException` in run_colab_batch.py (line 117-119).**
This catches ALL exceptions including SystemExit and KeyboardInterrupt. If the batch fails for any reason, it prints a warning but doesn't stop the session. The t0.batch function has a finally block that stops the session, but wait - does it? Let me look again.

In t0.batch:
```python
def batch(name, gpu):
    cli(["usage"])
    error = None
    try:
        cli(["new", "-s", name, "--gpu", gpu])
        try:
            cli(["exec", "-s", name, "-f", str(RUN_PY), "--timeout", str(EXEC_TIMEOUT)])
        except CliError as e:
            error = e
        cli(["exec", "-s", name], stdin=LIST_CODE)
        fetch(name)
    except CliError as e:
        print(f"SESSION KEPT...")
        raise e
    cli(["stop", "-s", name])
    if error:
        raise error
```

There's NO finally block! The `cli(["stop", "-s", name])` is NOT inside a finally. If an exception occurs between `cli(["new", ...])` and `cli(["stop", ...])`, the session is left running. For example, if `cli(["exec", "-s", name, "-f", str(RUN_PY), "--timeout", str(EXEC_TIMEOUT)])` raises a non-CliError exception (like OSError from subprocess), then `error` is None, and we go to `cli(["exec", "-s", name], stdin=LIST_CODE)` which would also fail, then `fetch(name)` which would fail, then we hit the except CliError block... wait, no. If `cli(["exec", ...])` raises OSError (not CliError), it's not caught by `except CliError`. It would propagate up. Then `cli(["exec", "-s", name], stdin=LIST_CODE)` wouldn't run, and `cli(["stop", "-s", name])` wouldn't run. The session stays running!

This is a real defect: **no finally block to ensure `colab stop` always runs**. If any exception occurs during the batch (OSError, KeyboardInterrupt, etc.), the session is left running, wasting compute units.

Severity: HIGH. The session keeps spending units.

Fix: wrap the body in try/finally, or use a context manager pattern.

**Defect 3: `cli(["exec", "-s", name], stdin=LIST_CODE)` - this execs without `-f`.**
Looking at the docstring: "a list script on stdin names the .mp4 files...". But `colab exec -s name` without `-f` doesn't run a specific file. The stdin is piped to whatever command `colab exec` runs by default. This is likely not running the LIST_CODE as intended. The correct command should be `colab exec -s name -f <some_script>` or `colab exec -s name python3 -c "<code>"`. As written, this might not execute the listing code at all, meaning FILES.txt is never created, and subsequent downloads fail.

Wait, but the docstring says this worked for T0 on 2026-11-05. Maybe `colab exec` without `-f` does something with stdin? Let me think... Actually, `colab exec` without `-f` might run the default command which could be `python3`. If so, piping LIST_CODE as stdin to `python3` would execute it. But this is fragile and undocumented behavior.

Actually, I think the real issue is different. Let me re-read the docstring: "colab exec -f colab_batches/t0/run.py (long timeout); a list script on stdin names the .mp4 files...". So the second exec is meant to run a list script. But it's missing `-f`. This is a bug - it should be `colab exec -s name -f <list_script>` or similar.

But wait, maybe `colab exec` without `-f` and with stdin does run the stdin as a command? I'm not sure. Let me flag this as medium severity since it could mean FILES.txt is never created.

Actually, looking more carefully: `cli(["exec", "-s", name], stdin=LIST_CODE)` - the `stdin` parameter passes the LIST_CODE as input to the subprocess. If `colab exec` without `-f` runs `python3` by default, then `python3` would receive the LIST_CODE as stdin and execute it. This might actually work. But it's fragile.

Hmm, but there's another issue. The LIST_CODE writes FILES.txt and also prints the names. But the `fetch` function reads FILES.txt. If FILES.txt is never created, fetch fails. But the docstring says T0 worked on 2026-11-05, so maybe it does work.

Let me move on to other defects.

**Defect 4: HF 429 handling in run.py (line 267-273).**
```python
for attempt in range(1, 5):   # Hugging Face answers 429 (Too Many Requests) at times and fails in under a minute: wait and retry, resumes partial files
    lg = OUT / f"wgp_{sid}.log"; start = lg.stat().st_size if lg.exists() else 0   # only THIS attempt's output may trigger a retry
    rc = sh(f"cd {APP} && python wgp.py --process {f} --output-dir {od} --profile 5 --verbose 2", f"wgp_{sid}.log")
    files = sorted(p.name for p in od.iterdir())
    if any(n.endswith(".mp4") for n in files): break
    if "429 Too Many Requests" not in lg.read_bytes()[start:].decode(errors="replace") or attempt == 4: break
    note(f"HF 429 on {sid}, attempt {attempt}: waiting {60 * attempt}s"); time.sleep(60 * attempt)
```

Issues:
1. The 429 detection reads the log from `start` offset, but `lg.stat().st_size` is the total file size. If the log grows during the attempt, `lg.read_bytes()[start:]` reads from the old start position. But `start` is updated each attempt, so this should be OK for detecting new 429 messages. However, if the log file is appended to, and the 429 message appears before `start`, it won't be detected. But typically 429 appears in the log output.

2. More importantly: `sh()` runs `python wgp.py` and captures output to `wgp_{sid}.log`. But `wgp.py` might write to stderr/stdout which goes to the log. The 429 detection looks for "429 Too Many Requests" in the log. But what if wgp.py doesn't print 429 to stdout? It might raise an exception instead. The code only checks for the string "429 Too Many Requests" - if wgp.py raises a different error or HTTP error, it won't be caught.

3. The retry logic: if 429 is detected, it waits `60 * attempt` seconds (60, 120, 180, 240). But it doesn't check if the previous attempt partially completed. The `start` offset is meant to resume from where it left off, but `wgp.py` might not support resuming from a partial output. Also, `files = sorted(p.name for p in od.iterdir())` checks if any .mp4 exists. If a previous attempt created partial .mp4 files, they'd be detected and break. But if wgp.py overwrites or appends, this could be wrong.

4. The bigger issue: `sh()` uses `subprocess.run(cmd, shell=True, ...)`. The command is `cd {APP} && python wgp.py ...`. This is a shell command. If wgp.py hangs (e.g., waiting for HF API), the `--timeout` from colab exec (6 hours) would eventually kill it, but during that time, 429 handling doesn't help because the process is hanging, not getting 429.

Actually, the most critical issue with the 429 handling: the code breaks out of the loop when 429 is NOT in the log OR attempt == 4. But if the first attempt gets 429 and the second attempt also gets 429, it waits 120s. But if wgp.py hangs indefinitely (not returning), the loop never progresses. The `--timeout` of 6 hours would eventually kill it, but that's 6 hours of wasted compute.

But more importantly: the 429 detection is fragile. If wgp.py outputs errors to stderr and the log capture doesn't include them properly, or if the 429 message format differs, the detection fails. Also, `lg.read_bytes()[start:]` - if the log file was truncated or rewritten, `start` becomes invalid.

Severity: MEDIUM. Could cause unnecessary retries or infinite loops.

**Defect 5: `finish()` function (line 257-262).**
```python
def finish(results):
    (OUT / "RESULT.json").write_text(json.dumps(results, indent=1))
    failed = sorted(s for s, v in results.items() if v != "ok")
    if failed:
        note("FAILED: " + ", ".join(failed)); raise SystemExit(1)
    note("ALL DONE")
```

If any shot fails, it raises SystemExit(1). But the session might still be running (if wgp.py is still processing). The `colab stop` in t0.batch would stop it, but if the exception propagates, the stop might not happen (due to the missing finally block - Defect 2).

Also, `finish()` is called at the end of the loop. But if an exception occurs during rendering (e.g., wgp.py crashes), the loop continues to the next shot. Wait, no - if `sh()` raises an exception (not CliError), it would propagate up and skip remaining shots. But `sh()` uses `subprocess.run` which shouldn't raise unless there's a system error.

Actually, the bigger issue: `finish()` raises SystemExit(1) if any shot fails. But SystemExit is caught by `except BaseException` in run_colab_batch.py, which prints the "SESSION MAY STILL RUN" warning. And due to Defect 2 (no finally), the session isn't stopped. So the session keeps running until the 6-hour timeout.

**Defect 6: Missing `finally` block in t0.batch - already covered as Defect 2.**

**Defect 7: `cli(["exec", "-s", name], stdin=LIST_CODE)` - missing `-f`.**
As discussed, this might not execute the listing code properly. If FILES.txt is never created, `fetch(name)` fails with "FILES.txt did not come back: nothing to fetch", and the session is kept running (Defect 2).

Actually wait, let me re-examine. The `cli` function:
```python
def cli(args, stdin=None):
    print(("DRY RUN: " if DRY else "$ ") + "colab " + " ".join(args) + ("  (code on stdin)" if stdin else ""), flush=True)
    if DRY:
        return
    kwargs = {"input": stdin} if stdin is not None else {"stdin": subprocess.DEVNULL}
    if subprocess.run(["colab", *args], text=True, **kwargs).returncode:
        raise CliError(f"colab {args[0]} failed: stopping, no retries")
```

So `cli(["exec", "-s", name], stdin=LIST_CODE)` runs `colab exec -s name` with stdin=LIST_CODE. The `colab exec` command without `-f`... I need to think about what this does. According to Colab CLI docs, `colab exec` requires either `-f <file>` or a command. Without `-f`, it might error or run the default command. If it errors, CliError is raised, and the except CliError block keeps the session.

But the docstring says this worked for T0 on 2026-11-05. So maybe `colab exec -s name` without `-f` does something with stdin. Or maybe the LIST_CODE is executed as a command somehow. This is uncertain.

Regardless, this is fragile. The proper way would be to write the LIST_CODE to a temp file and use `-f`. Let me flag this as medium.

**Defect 8: Path issues on Windows Git Bash.**
The user mentions: "paths (Windows Git Bash turns /content into C:/Program Files/Git/content unless MSYS_NO_PATHCONV=1)". 

Looking at the code:
- `OUT = Path("/content/out")` - hardcoded Linux path
- `TMP = Path("/content/cache")` - hardcoded Linux path
- `APP = Path("/content/Wan2GP")` - hardcoded Linux path
- `image_start`: "/content/Wan2GP/inputs/keyframes__SHOT-001-A.png" - hardcoded Linux path

On Windows with Git Bash, `/content` might become `C:/Program Files/Git/content`. This would cause all paths to be wrong. But the docstring says "Never run the CLI with --logtostderr" and mentions Windows worked on 2026-11-05. So maybe this is handled somehow, or maybe the user is running on WSL/Linux.

Actually, the user specifically mentions this as a concern. Let me flag it. But the code hardcodes `/content/...` paths. On Windows Git Bash, these would be wrong. The fix would be to use environment variables or detect the platform.

Severity: HIGH. All paths are hardcoded to `/content/...` which breaks on Windows Git Bash.

Wait, but the docstring says "The Colab CLI README says Linux and macOS only; it installed and signed in on Windows (2026-11-05: usage, new --gpu G4, exec, stop all worked)." So it did work on Windows. How? Maybe through WSL or a Linux VM. Or maybe the `/content` path is correct in the Colab environment regardless of host OS. The paths are inside the Colab VM, not on the host. So `/content` is the Colab VM's filesystem, which is Linux. The Windows Git Bash issue is about the HOST machine, not the VM.

Hmm, but the user says "Windows Git Bash turns /content into C:/Program Files/Git/content". This suggests the paths are being passed through the host somehow. But `colab` CLI runs inside the VM. Unless the script is being run on the host...

Actually, I think the concern is about how the run.py script is invoked. If `colab exec -f run.py` is run from a Windows Git Bash terminal, the `/content` paths inside run.py are interpreted by the Colab VM, which is Linux. So the Windows Git Bash path conversion shouldn't affect the VM's internal paths.

But wait - maybe the issue is about the `image_start` and `image_end` paths in the settings. These are written into the run.py as JSON strings. When run.py runs inside the VM, it uses these paths directly. They should be `/content/Wan2GP/inputs/...` which is correct in the VM.

I think the Windows Git Bash concern might be about the host-side path handling, not the VM. Since the code runs inside the Colab VM (Linux), the `/content` paths are correct. But if someone copies the run.py to their Windows machine and tries to run it locally, the paths would break. However, the code is designed to run inside Colab, so this might not be a real defect.

Let me reconsider. The user explicitly mentions this as a concern: "paths (Windows Git Bash turns /content into C:/Program Files/Git/content unless MSYS_NO_PATHCONV=1)". This suggests they're worried about path conversion. But since the code runs in the VM, this shouldn't matter. Unless the build step (`build_h3_batch.py`) runs on the host and generates paths that get embedded in run.py, and those paths are then used by the VM. But the paths in run.py are `/content/...` which are VM paths.

I'll flag this as LOW since it's about host-side concerns that don't affect the VM execution.

**Defect 9: `jpeg_b64` stores JPEG under .png names.**
As discussed, this could cause issues if Wan2GP validates file extensions. But the comment says it works. Let me flag as LOW.

Actually, wait. Let me re-read the comment: "Wan2GP opens the file by content, so the .png name run_kaggle gives it does no harm." This is a claim that it works. But is it verified? The failure was about the script size, not about image loading. So maybe this works. I'll flag as LOW.

**Defect 10: `run_kaggle.png_b64` monkeypatch.**
Line 71: `run_kaggle.png_b64 = lambda path: jpeg_b64(path, (w, h))`. This replaces the function globally. If run_kaggle uses png_b64 elsewhere, this could affect other things. But it's set before `run_kaggle.build` is called, so it should be fine. LOW.

**Defect 11: `legacy_rows` - `ids` filtering.**
Line 68: `set(filter(None, a.ids.split(",")))`. If `a.ids` is empty string, this gives an empty set, and all shots are included. If `a.ids` is "SHOT-001,SHOT-002", this gives {"SHOT-001", "SHOT-002"}. This looks correct.

But wait - the story has 10 shots (SHOT-001 through SHOT-010). The user says "10 anime shots" but the settings only show SHOT-001 and SHOT-002. The "all frames" section shows 10 shots with frame counts. So the build includes all 10 shots. The `--ids` parameter defaults to empty, so all shots are included. This is correct.

**Defect 12: Frame count mismatch.**
The "all frames" section shows:
- SHOT-001: 175
- SHOT-002: 158
- SHOT-003: 209
- SHOT-004: 243
- SHOT-005: 243
- SHOT-006: 209
- SHOT-007: 209
- SHOT-008: 243
- SHOT-009: 243
- SHOT-010: 158

Total: 175+158+209+243+243+209+209+243+243+158 = 2090. The user says "frames 107+17k, 2090 total". 17k might mean 17000? No, 2090 total. "107+17k" might mean 107 + 17000? That doesn't add up. Or maybe "107+17k" means 107 + 17*1000 = 17007? No. Or maybe it's "107+17k" meaning 107 frames + 17k frames? 107 + 17000 = 17107, not 2090. 

Actually, "frames 107+17k" might mean "frames 107-17k" i.e., frames numbered 107 to 17000? But the total is 2090. Or maybe "107+17k" is a typo for "107-17k" meaning the frame range. Or maybe it means 107 + 17*1000 = 17107? No, total is 2090.

Wait, maybe "107+17k" means 107 + 17000? No. Let me just accept that the total is 2090 frames across 10 shots. The frame counts per shot seem reasonable for anime (158-243 frames per shot).

But here's a potential issue: the settings show `video_length: 175` for SHOT-001 and `video_length: 158` for SHOT-002. But the "all frames" section shows SHOT-001: 175 and SHOT-002: 158. These match. Good.

However, SHOT-003 through SHOT-010 don't have settings shown. Their frame counts are 209, 243, 243, 209, 209, 243, 243, 158. These need to match their settings. If the settings for these shots have different video_length values, there could be a mismatch. But since we don't see their settings, we can't verify. This is a potential issue but not a code defect per se.

**Defect 13: `finish()` doesn't handle partial results.**
If some shots succeed and some fail, `finish()` writes RESULT.json with mixed results and raises SystemExit(1). The successful clips are already downloaded (via fetch), but the failed ones aren't. This is correct behavior. But the session might still be running for the failed shot (Defect 2).

**Defect 14: `sh()` function doesn't handle non-zero exit codes properly.**
Line 241-244:
```python
def sh(cmd, log="shell.log"):
    note("$ " + cmd); t = time.time()
    with open(OUT / log, "a") as f: rc = subprocess.run(cmd, shell=True, stdout=f, stderr=subprocess.STDOUT).returncode
    note(f"  exit {rc} in {time.time() - t:.1f}s"); return rc
```
It returns the return code but doesn't raise on non-zero. The caller checks `rc == 0` later. This is fine.

**Defect 15: `subprocess.Popen` for nvidia-smi (line 245).**
```python
subprocess.Popen(f"nvidia-smi --query-gpu=timestamp,index,memory.used,memory.total,utilization.gpu --format=csv -l 5 > {OUT}/gpu.csv", shell=True)
```
This starts a background process that writes to gpu.csv every 5 seconds. But it's never waited on or cleaned up. If the script exits, this background process might keep running. But since it's writing to a file in /content/out, it shouldn't waste much. LOW.

Actually, this could be a problem: if the script is killed, the Popen process might continue. But it's writing to a file, not consuming GPU resources. LOW.

**Defect 16: The `except BaseException` in run_colab_batch.py catches SystemExit.**
When `finish()` raises SystemExit(1), it's caught by `except BaseException`, which prints "SESSION MAY STILL RUN" and re-raises. The re-raised SystemExit propagates up, and the process exits. But the session is still running (wgp.py is still processing). The user needs to manually stop it. This wastes compute units.

But this is related to Defect 2 (no finally in t0.batch). If t0.batch had a finally block, the session would be stopped before the exception propagates.

**Defect 17: `cli(["exec", "-s", name], stdin=LIST_CODE)` - the LIST_CODE might not execute.**
As discussed, `colab exec` without `-f` might not run the stdin as a Python script. If it doesn't, FILES.txt is never created, and `fetch(name)` fails. This leads to the session being kept running (Defect 2).

Actually, let me reconsider. Looking at the Colab CLI documentation, `colab exec` without `-f` runs the default command. The default command might be `python3` or empty. If it's `python3`, then piping LIST_CODE as stdin would execute it. But this is undocumented behavior.

More importantly, even if FILES.txt IS created, the `fetch` function downloads FILES.txt and then each file listed in it. But the `fetch` function is called once with the session name, and it downloads FILES.txt first, then iterates over the files. This seems correct.

But wait - there's a subtle bug. `fetch(name)` is called with `name` (the session name), but `fetch` uses `RESULTS / "FILES.txt"` and downloads from `OUT/FILES.txt`. The `name` parameter isn't used in `fetch` except... let me check. `fetch(name)` - the `name` parameter is passed but not used in the function body. The function uses `RESULTS` and `OUT`. So `name` is unused. This is a minor issue.

**Defect 18: The `cli` function in t0_pack doesn't handle `colab exec` timeout properly.**
Line 191: `cli(["exec", "-s", name, "-f", str(RUN_PY), "--timeout", str(EXEC_TIMEOUT)])`. The EXEC_TIMEOUT is 6*3600 = 21600 seconds. But the failure says the 19.7 MB script never reached the VM. This could be because:
- The script is too large for colab exec to handle
- The transfer failed

But the second attempt (11.3 MB) worked. So the size is the issue, not the timeout. However, there's no check for script size before running. If the script is too large, colab exec might hang or fail silently. This isn't a code defect per se, but it's a design flaw.

Actually, the failure says "colab log shows no EXEC of run.py". This means the exec command never started. This could be because:
1. The script is too large (19.7 MB > some limit)
2. The transfer failed
3. The colab CLI couldn't handle the file

The fix would be to reduce the script size (which was done - 11.3 MB) or check the size before running. But this is more of a packaging issue than a code defect.

**Defect 19: `run_kaggle.build` return value.**
Line 72: `script, _ = run_kaggle.build(...)`. The `_` discards the second return value. What does run_kaggle.build return? It returns (script, something). If the second value is important, it's discarded. But the code only uses the first value (script). This seems intentional. LOW.

**Defect 20: Missing `--go` check in run_colab_batch.py.**
Line 113: `t0.batch(a.batch.replace("_", "-"), a.gpu)`. This always runs the batch, even in dry run. But `t0.DRY` is set based on `a.go`. Wait, let me check. In run_colab_batch.py:
```python
t0.DRY = not a.go
```
And in t0.batch, `DRY` is used in `cli()` to skip actual execution. So even though `run_colab_batch.py` calls `t0.batch`, the `DRY` flag is set correctly. This is fine.

But wait - in run_colab_batch.py, line 111: `print("DRY RUN: nothing is started" if t0.DRY else "LIVE RUN: this spends compute units", flush=True)`. Then line 113: `t0.batch(...)`. The `t0.DRY` is set before this call. So in dry run, `cli()` skips execution. Good.

**Defect 21: The `except BaseException` in run_colab_batch.py (line 117-119).**
This catches ALL exceptions including SystemExit, KeyboardInterrupt, etc. If the batch fails, it warns about the session. But it doesn't stop the session. Combined with Defect 2 (no finally in t0.batch), this means the session is never stopped on failure.

This is the same as Defect 2 but at a higher level. The root cause is the missing finally in t0.batch.

**Defect 22: `finish()` raises SystemExit(1) but doesn't clean up.**
If `finish()` raises SystemExit(1), the exception propagates through the loop (but the loop is already done - finish is called after the loop). Actually, `finish()` is called after the for loop, so all shots have been processed. The SystemExit(1) propagates up through t0.batch, then through run_colab_batch.py's `except BaseException`, which warns about the session. The session is still running (wgp.py finished or is finishing). The `colab stop` in t0.batch doesn't run because the exception propagated before reaching it.

Wait, let me trace the flow:
1. run.py finishes rendering all shots
2. `finish(results)` is called
3. If any shot failed, `SystemExit(1)` is raised
4. This propagates up through run.py (which is the exec target)
5. The exec command completes (with error)
6. t0.batch's `cli(["exec", "-s", name], stdin=LIST_CODE)` returns normally (exec completed)
7. `fetch(name)` runs - downloads clips
8. `cli(["stop", "-s", name])` runs - stops session
9. Back in run_colab_batch.py, `t0.batch` returns normally
10. `print("done: clips and logs in {RESULTS}")` prints

Wait, that doesn't match. If `finish()` raises SystemExit(1), it would propagate through run.py, which is the exec target. The exec would complete with an error. Then t0.batch continues: `cli(["exec", "-s", name], stdin=LIST_CODE)` runs the listing, `fetch(name)` downloads clips, `cli(["stop", "-s", name])` stops the session. Then the error from finish propagates up through t0.batch... but t0.batch doesn't catch SystemExit. It would propagate to run_colab_batch.py's `except BaseException`, which warns about the session.

But wait - `cli(["stop", "-s", name])` runs BEFORE the error propagates. So the session IS stopped. Then the error propagates, and the warning is printed. But the session is already stopped. So the warning is misleading.

Hmm, but actually, the `finish()` is called at the end of run.py. If it raises SystemExit(1), the exec command completes with exit code 1. t0.batch continues normally (listing, fetching, stopping). Then the SystemExit propagates to run_colab_batch.py, which catches it in `except BaseException` and warns. But the session is already stopped. So the warning is wrong/misleading.

But this is only if `finish()` is the last thing called. If an exception occurs DURING rendering (not at the end), then t0.batch might not reach `cli(["stop", "-s", name])`.

Actually, looking at run.py more carefully:
```python
for sid, settings in json.loads(...).items():
    ...
    for attempt in range(1, 5):
        ...
        rc = sh(...)
        ...
    results[sid] = ...
    note(...)
finish(results)
```

If `sh()` raises an exception (e.g., OSError), it propagates up, skipping remaining shots and `finish()`. Then the exec completes with an error. t0.batch continues: listing, fetching, stopping. Then the error propagates.

But if `sh()` succeeds for all shots and `finish()` raises SystemExit(1), the same flow applies.

The issue is: if an exception occurs during the loop (not at finish), the session might still be running when `cli(["stop", "-s", name])` is called. But actually, `cli(["exec", "-s", name, "-f", str(RUN_PY), "--timeout", str(EXEC_TIMEOUT)])` would have completed (either successfully or with error) before the listing exec. So by the time we reach `cli(["stop", "-s", name])`, the exec has finished. The session should be stopped by then.

Unless the exec itself hangs (timeout). If the exec times out, `cli(["exec", ...])` raises CliError, `error = e`, then `cli(["exec", "-s", name], stdin=LIST_CODE)` runs (but the session might still be running from the timed-out exec), then `fetch(name)` might fail, then `cli(["stop", "-s", name])` stops it. So the finally-like behavior is partially there.

But if `cli(["exec", "-s", name], stdin=LIST_CODE)` raises an exception (not CliError), then `cli(["stop", "-s", name])` doesn't run. Session left running.

OK, I think the main defects are:

1. **No finally block in t0.batch** - session left running on any exception (HIGH)
2. **`cli(["exec", "-s", name], stdin=LIST_CODE)` missing `-f`** - might not create FILES.txt, causing fetch to fail (MEDIUM)
3. **Hardcoded `/content` paths** - breaks on Windows Git Bash (LOW, but the user specifically mentioned this)
4. **JPEG bytes under .png names** - potential format validation issue (LOW)
5. **HF 429 detection is fragile** - might not detect 429 if format differs, causing unnecessary retries or infinite loops (MEDIUM)
6. **`except BaseException` catches SystemExit** - misleading warning about session (MEDIUM, related to #1)

Wait, let me reconsider the Windows Git Bash issue. The user says "Windows Git Bash turns /content into C:/Program Files/Git/content unless MSYS_NO_PATHCONV=1". This is about the HOST machine's path conversion. But the code runs inside the Colab VM. The `/content` paths are VM paths. So this shouldn't be an issue when running inside Colab.

BUT - the `build_h3_batch.py` runs on the HOST (where the user is sitting). It generates the run.py script. The run.py contains `/content/...` paths. These are VM paths and are correct. The build step doesn't need to resolve these paths; it just embeds them as strings.

So the Windows Git Bash issue is about the HOST, not the VM. The code is designed to run inside the VM. I'll flag this as LOW.

Actually, wait. Let me re-read the user's concern: "paths (Windows Git Bash turns /content into C:/Program Files/Git/content unless MSYS_NO_PATHCONV=1)". This might be about how the `colab` CLI is invoked from the host. If the user types `python run_colab_batch.py BATCH --go --gpu G4` in Git Bash, the script runs on the host, but it invokes `colab` which connects to the VM. The `/content` paths in the script are VM paths. The host's path conversion shouldn't affect the VM.

Unless... the script is being run on the host somehow? No, `colab exec -f run.py` runs run.py inside the VM. The paths inside run.py are VM paths.

I think this is a non-issue for the VM execution. But the user specifically asked about it, so I should mention it. Let me flag it as LOW with the explanation that it's about host-side path conversion that doesn't affect VM execution.

Actually, I just realized something. The `image_start` and `image_end` in the settings are `/content/Wan2GP/inputs/keyframes__SHOT-001-A.png`. These are written into run.py as JSON. When run.py runs in the VM, it uses these paths directly. They're correct VM paths. The Windows Git Bash issue doesn't apply here.

But what if the user is running `build_h3_batch.py` on Windows Git Bash, and the script generates paths that include `/content/...`? The build step just embeds these strings; it doesn't resolve them. So the generated run.py has correct VM paths.

OK, I'll flag the Windows Git Bash issue as LOW, noting that the paths are VM paths and the host conversion doesn't affect VM execution, but if anyone runs the script outside Colab, it would break.

Let me also look for other defects:

**Defect: `subprocess.Popen` for nvidia-smi never cleaned up.**
Line 245: `subprocess.Popen(...)` starts a background process. If the script exits, this process might continue. But it's writing to a file, not consuming GPU. LOW.

**Defect: `LOG = open(OUT / "timeline.txt", "a", buffering=1)` - file opened but never explicitly closed.**
If the script exits, the file might not be flushed. But `buffering=1` means line buffered, and `flush=True` is used in `note()`. So it should be fine. LOW.

**Defect: `os.environ["HF_HOME"] = str(TMP / "hf")` - HF cache location.**
This sets HF cache to `/content/cache/hf`. But the ckpts are moved to `TMP / "ckpts"` and symlinked. The HF cache might not be set up correctly. But this is probably fine since Wan2GP downloads models to HF cache. LOW.

**Defect: `inputs = APP / "inputs"` and writing keyframes.**
Line 255-256: Creates `/content/Wan2GP/inputs` directory and writes keyframe files. The filenames come from the base64 blob keys. These are like `keyframes__SHOT-001-A.png`. The settings reference these exact paths. This is correct.

But wait - the JPEG bytes are stored under `.png` names. If Wan2GP checks the file extension or tries to parse as PNG, it could fail. The comment says "Wan2GP opens the file by content, so the .png name run_kaggle gives it does no harm." But this hasn't been verified in the failure case. The failure was about script size, not image loading. So maybe it works. LOW.

**Defect: `for attempt in range(1, 5)` - only 4 attempts.**
If all 4 attempts get 429, the shot fails. But 4 attempts with 60, 120, 180, 240 seconds = 600 seconds (10 minutes) of waiting. This might not be enough for HF rate limits. MEDIUM.

**Defect: `time.sleep(60 * attempt)` - exponential backoff but no max cap.**
After 4 attempts (240 seconds), if still failing, the shot fails. But the wait could be longer. MEDIUM.

**Defect: `lg.read_bytes()[start:]` - reading from offset.**
If the log file is appended to, `start` is the old size. Reading from `start` gives new content. But if the log is rotated or truncated, `start` could be invalid. Also, `lg.stat().st_size` is checked at the start of each attempt, but if the file was modified between attempts, the size might have changed. This is a potential issue but probably rare. LOW.

**Defect: `files = sorted(p.name for p in od.iterdir())` - checking for .mp4.**
If a previous attempt created partial .mp4 files, they'd be detected and the loop breaks. But if wgp.py creates partial files with non-.mp4 extensions (e.g., .part), they wouldn't be detected. MEDIUM.

Actually, let me look at this more carefully. The `od` directory is the output directory for the shot. Each attempt writes to the same `od` directory. If wgp.py creates partial files, they accumulate. The check `any(n.endswith(".mp4") for n in files)` detects if any .mp4 was created. But if wgp.py creates a .part file and renames it to .mp4 at the end, the .part file would remain. Next attempt, the .part file is still there, and wgp.py might append to it or overwrite. This could cause issues.

But this is speculative. The actual wgp.py behavior is unknown. LOW.

**Defect: `sh()` uses `shell=True` which is a security risk but not relevant here.**
LOW.

**Defect: No check for script size before `colab exec`.**
The 19.7 MB script caused the exec to never start. There's no size check. But this is a packaging issue, not a code defect. The fix was to reduce the size. LOW.

**Defect: `run_kaggle.build` might not exist or might have different signature.**
Line 72: `script, _ = run_kaggle.build(rows, a.pack, a.batch, None, None, False, "colab", a.profile, manifest)`. The signature might be different. But the docstring says it works. LOW.

**Defect: `compile_fl2va_prompt` might fail for some shots.**
Line 53: `prompt = compile_fl2va_prompt(sh, story["registry"])["compiled_prompt"]`. If this fails for some shots, the build fails. But the user says the build succeeded (11.3 MB run.py). LOW.

**Defect: `manifest["embed_mb_total"]` - manifest might not have this key.**
Line 77: `print("built", folder, "|", len(rows), "shots,", sum(r["render_frames"] for r in rows), "frames,", manifest["embed_mb_total"], "MB embedded")`. If `embed_mb_total` is not in the manifest, this would raise KeyError. But the docstring says it works. LOW.

**Defect: `--profile` default is 5.**
Line 65: `ap.add_argument("--profile", type=int, default=5)`. The settings show `--profile 5`. This matches. But what if the user needs a different profile? They can specify it. LOW.

**Defect: `--resolution` default is "768x1344".**
Line 65: `ap.add_argument("--resolution", default="768x1344")`. The settings show "768x1344". This matches. LOW.

**Defect: `video_length` in settings vs `render_frames` in rows.**
The settings show `video_length: 175` for SHOT-001, and the "all frames" section shows SHOT-001: 175. These match. But for SHOT-002, settings show `video_length: 158` and frames show 158. Match. For other shots, we don't see settings, but the frame counts are given. If the settings for other shots have different video_length, there could be a mismatch. But this is data, not code. LOW.

**Defect: `sliding_window_size: 362` - might not match video_length.**
For SHOT-001, sliding_window_size is 362 but video_length is 175. 362 > 175, which might be OK (sliding window can be larger than video length). But this could cause issues if Wan2GP expects sliding_window_size <= video_length. MEDIUM.

Actually, let me think about this. Sliding window size of 362 with video length of 175 means the window is larger than the video. This could cause Wan2GP to behave unexpectedly. But the comment says this is the "proven Pika H3 Flex 6-step preset", so it should work. LOW.

**Defect: `guidance_phases: 1` and `guidance_scale: 1`.**
These are standard settings. LOW.

**Defect: `flow_shift: 12`.**
Standard for H3. LOW.

**Defect: `seed: 42` for both shots.**
Same seed for different shots could cause visual artifacts if the shots share similar features. But this is a content choice, not a code defect. LOW.

**Defect: `image_mode: 0` and `image_prompt_type: "SE"`.**
Standard settings. LOW.

**Defect: `custom_settings: {"audio_refinement": "none"}`.**
Standard. LOW.

OK, let me also look at the `run_colab_batch.py` more carefully.

Line 105: `t0.RUN_PY = HERE / "colab_batches" / a.batch / "run.py"`. This sets the run.py path. But `a.batch` might contain underscores (e.g., "h3_batch"), which would be converted to hyphens: `a.batch.replace("_", "-")`. So "h3_batch" becomes "h3-batch". The run.py is at `colab_batches/h3-batch/run.py`. This is correct.

But wait - `t0.RUN_PY` is set to `HERE / "colab_batches" / a.batch / "run.py"` where `a.batch` is the original (with underscores). So `t0.RUN_PY` points to `colab_batches/h3_batch/run.py` (with underscore). But the actual file is at `colab_batches/h3-batch/run.py` (with hyphen). This is a BUG!

Let me verify:
- `a.batch` = "h3_batch" (user passes this)
- `t0.RUN_PY = HERE / "colab_batches" / a.batch / "run.py"` = `.../colab_batches/h3_batch/run.py`
- But the actual directory is `colab_batches/h3-batch/` (hyphens, because `a.batch.replace("_", "-")` is used for the session name but not for the path)

Wait, let me re-read:
```python
t0.RUN_PY = HERE / "colab_batches" / a.batch / "run.py"
```
This uses `a.batch` directly, which might have underscores. But the directory was created with hyphens:
```python
folder = HERE / "colab_batches" / a.batch
folder.mkdir(parents=True, exist_ok=True)
```
Wait, no. In `build_h3_batch.py`:
```python
folder = HERE / "colab_batches" / a.batch
folder.mkdir(parents=True, exist_ok=True)
```
Here `a.batch` is the argument passed to build_h3_batch.py. If the user passes "h3_batch", the folder is `colab_batches/h3_batch/`. So the directory name matches the argument.

But in `run_colab_batch.py`:
```python
t0.RUN_PY = HERE / "colab_batches" / a.batch / "run.py"
```
This also uses `a.batch` directly. So if the user passes "h3_batch", `t0.RUN_PY` points to `colab_batches/h3_batch/run.py`. This matches the directory created by build_h3_batch.py.

But then:
```python
t0.batch(a.batch.replace("_", "-"), a.gpu)
```
This passes the hyphenated version to `t0.batch`, which uses it as the session name. So the session name is "h3-batch" but the run.py path is `colab_batches/h3_batch/run.py`. This is consistent.

Wait, but what if the user passes "h3-batch" (with hyphen) to run_colab_batch.py? Then `a.batch` = "h3-batch", `t0.RUN_PY` = `colab_batches/h3-batch/run.py`, and `t0.batch("h3-batch", ...)`. This is also consistent.

So the path handling is correct as long as the user passes the same name to both build and run. LOW.

Actually, wait. Let me re-check. In `build_h3_batch.py`:
```python
ap.add_argument("story"); ap.add_argument("pack"); ap.add_argument("batch")
```
The `batch` argument is positional. The user passes "h3_batch" or "h3-batch". The folder is created with this name.

In `run_colab_batch.py`:
```python
ap.add_argument("batch")
```
Same. `t0.RUN_PY` uses `a.batch` directly. So the path matches.

But there's a subtle issue: if the user passes "h3_batch" to build, the folder is `colab_batches/h3_batch/`. If they then pass "h3-batch" to run, `t0.RUN_PY` points to `colab_batches/h3-batch/run.py` which doesn't exist. But this is user error, not a code defect.

OK, moving on.

**Defect: `t0.batch` doesn't check if `RUN_PY` exists before calling.**
In `run_colab_batch.py`, line 108-110 checks if `t0.RUN_PY.exists()` and prints an error if missing. But `t0.batch` also checks (in t0.batch, line 185+). Wait, t0.batch doesn't check RUN_PY. It's checked in run_colab_batch.py before calling t0.batch. But t0.batch also has a check (line 212-214 in t0.batch):
```python
if not RUN_PY.exists():
    print(f"missing {RUN_PY}: build it first with run_kaggle.py --target colab (see README)")
    if not DRY:
        return 1
```
This is redundant but not harmful. LOW.

**Defect: `cli(["exec", "-s", name, "-f", str(RUN_PY), "--timeout", str(EXEC_TIMEOUT)])` - the timeout is 6 hours.**
For 10 shots with ~2090 frames total, 6 hours should be plenty. But if the script is too large (19.7 MB), the exec might not start at all. The second attempt (11.3 MB) worked. So the timeout is fine for the working case. LOW.

**Defect: `fetch` function downloads FILES.txt and then each file.**
Line 170-182:
```python
def fetch(name):
    if not DRY:
        RESULTS.mkdir(parents=True, exist_ok=True)
    cli(["download", "-s", name, f"{OUT}/FILES.txt", str(RESULTS / "FILES.txt")])
    if DRY:
        cli(["download", "-s", name, f"{OUT}/<each file named in FILES.txt>", "results/<same path>"])
        return
    if not (RESULTS / "FILES.txt").exists():
        raise CliError("FILES.txt did not come back: nothing to fetch")
    for rel in (RESULTS / "FILES.txt").read_text(encoding="utf-8").split():
        (RESULTS / rel).parent.mkdir(parents=True, exist_ok=True)
        cli(["download", "-s", name, f"{OUT}/{rel}", str(RESULTS / rel)])
```

Issues:
1. `cli(["download", "-s", name, f"{OUT}/FILES.txt", str(RESULTS / "FILES.txt")])` - the `-s` flag specifies the source file on the VM. But `FILES.txt` is at `/content/out/FILES.txt`. The download command downloads from the VM to local. The source is `/content/out/FILES.txt`. This seems correct.

2. `cli(["download", "-s", name, f"{OUT}/{rel}", str(RESULTS / rel)])` - for each file in FILES.txt, downloads from `/content/out/<rel>` to `results/<rel>`. This seems correct.

3. But `name` parameter is unused in `fetch`. The function uses `RESULTS` and `OUT`. This is a minor issue. LOW.

**Defect: `cli(["exec", "-s", name], stdin=LIST_CODE)` - the LIST_CODE might not execute.**
As discussed, this is the most significant defect. If `colab exec` without `-f` doesn't run the stdin as a Python script, FILES.txt is never created, and `fetch` fails. This leads to the session being kept running (Defect 2).

Actually, I just realized something. Looking at the Colab CLI docs more carefully: `colab exec` without `-f` runs the default command. The default command might be `python3`. If so, piping LIST_CODE as stdin to `python3` would execute it. But this is undocumented and fragile.

But actually, there's another interpretation. Maybe `colab exec -s name` without `-f` is supposed to run a command that's specified elsewhere, and the stdin is input to that command. But without knowing the default command, it's unclear.

The safer approach would be to write the LIST_CODE to a temporary file and use `colab exec -s name -f <tempfile>`. But the current code doesn't do this.

Let me flag this as MEDIUM.

**Defect: No `finally` block in `t0.batch`.**
Already flagged as HIGH.

**Defect: `except CliError` in t0.batch keeps session running.**
Line 196-198:
```python
except CliError as e:   # the clips exist only on the VM: keep it so they can be fetched by hand, then stop it
    print(f"SESSION KEPT (clips still on the VM): fix the download, then run: colab stop -s {name}")
    raise e
```
This catches CliError and keeps the session running. But it doesn't stop the session! The comment says "then stop it" but the code doesn't stop it. The `cli(["stop", "-s", name])` is after the except block, so it doesn't run.

Wait, let me re-read the structure:
```python
def batch(name, gpu):
    cli(["usage"])
    error = None
    try:
        cli(["new", "-s", name, "--gpu", gpu])
        try:
            cli(["exec", "-s", name, "-f", str(RUN_PY), "--timeout", str(EXEC_TIMEOUT)])
        except CliError as e:
            error = e   # the clips that finished still come home
        cli(["exec", "-s", name], stdin=LIST_CODE)
        fetch(name)
    except CliError as e:   # the clips exist only on the VM: keep it so they can be fetched by hand, then stop it
        print(f"SESSION KEPT (clips still on the VM): fix the download, then run: colab stop -s {name}")
        raise e
    cli(["stop", "-s", name])   # only after the clips are home; a running session keeps spending units
    if error:
        raise error
```

If `cli(["exec", "-s", name, "-f", str(RUN_PY), "--timeout", str(EXEC_TIMEOUT)])` raises CliError:
- `error = e`
- `cli(["exec", "-s", name], stdin=LIST_CODE)` runs (but the session might still be running from the timed-out exec)
- `fetch(name)` runs
- If fetch succeeds, `cli(["stop", "-s", name])` runs - session stopped
- If fetch fails (CliError), the outer except catches it, prints "SESSION KEPT", and re-raises
- `cli(["stop", "-s", name])` does NOT run

So if fetch fails, the session is kept running. This is by design (to allow manual fetching), but it wastes compute units. The comment says "then stop it" but the code doesn't stop it. This is a bug.

But wait - the inner `except CliError` catches the error from the exec timeout. The `error = e` captures it. Then `cli(["exec", "-s", name], stdin=LIST_CODE)` runs. If this succeeds, `fetch(name)` runs. If fetch succeeds, `cli(["stop", "-s", name])` runs. If fetch fails, the outer except catches it and keeps the session.

So the session is only kept running if fetch fails. This is intentional for manual recovery, but it wastes compute units. The fix would be to stop the session in the except block too, or use a finally block.

Actually, the comment says "keep it so they can be fetched by hand, then stop it". The intent is to keep the session for manual fetching, then stop it. But the code doesn't stop it. This is a bug.

Severity: HIGH. Session left running when fetch fails.

Fix: Add `cli(["stop", "-s", name])` in the except block, or use a finally block.

**Defect: `cli(["exec", "-s", name], stdin=LIST_CODE)` might fail.**
If this command fails (non-CliError), the outer except doesn't catch it (it only catches CliError and OSError). The exception propagates, and `cli(["stop", "-s", name])` doesn't run. Session left running.

But this is less likely since `colab exec` without `-f` probably doesn't fail. Still, it's a potential issue. MEDIUM.

**Defect: `fetch(name)` uses `name` but `name` is the session name.**
The `fetch` function doesn't use `name` at all. It uses `RESULTS` and `OUT`. This is fine but confusing. LOW.

**Defect: `RESULTS.mkdir(parents=True, exist_ok=True)` in fetch.**
This creates the results directory. But `RESULTS` is defined at module level as `HERE / "results"`. If the script is run from a different directory, this might point to the wrong place. But `HERE` is computed from `__file__`, so it should be correct. LOW.

**Defect: `OUT = Path("/content/out")` - hardcoded.**
Already discussed. LOW (VM paths are correct).

**Defect: `TMP = Path("/content/cache")` - hardcoded.**
Already discussed. LOW.

**Defect: `APP = Path("/content/Wan2GP")` - hardcoded.**
Already discussed. LOW.

**Defect: `os.environ["HF_HOME"] = str(TMP / "hf")` - HF cache.**
This sets HF cache to `/content/cache/hf`. But Wan2GP might expect HF cache at a different location. If models are already cached, this is fine. If not, Wan2GP will download them. LOW.

**Defect: `git clone https://github.com/deepbeepmeep/Wan2GP.git {APP}` - network dependency.**
If the network is down, the clone fails. But this is expected for a render script. LOW.

**Defect: `git checkout bd1ff5903cbc18b46c3cce3b75bd140870b536a2` - specific commit.**
If this commit doesn't exist, the checkout fails. But the docstring says it worked. LOW.

**Defect: `pip install -r requirements.txt` - dependency installation.**
If dependencies fail, setup fails. Expected. LOW.

**Defect: `shutil.move(str(p), TMP / "ckpts" / p.name)` - moving ckpts.**
If the APP/ckpts directory has files, they're moved to TMP/ckpts. Then a symlink is created. This is for caching. LOW.

**Defect: `os.symlink(TMP / "ckpts", APP / "ckpts")` - symlink.**
On Windows, symlinks might require admin privileges. But the docstring says it worked on Windows. LOW.

**Defect: `json.loads(base64.b64decode("<BLOB %d chars>"))` - base64 blobs.**
The blobs are elided in the review, but they represent the keyframe data and settings. If the blobs are corrupted, the script fails. But this is a data issue, not a code defect. LOW.

**Defect: `for name, b64 in json.loads(...).items(): (inputs / name).write_bytes(base64.b64decode(b64))` - writing keyframes.**
The keyframe data is decoded from base64 and written to files. The filenames come from the JSON keys. These are like `keyframes__SHOT-001-A.png`. The settings reference these exact paths. This is correct.

But wait - the JPEG bytes are stored under `.png` names. If Wan2GP validates the file format, this could fail. The comment says it works, but it's unverified. LOW.

**Defect: `for sid, settings in json.loads(...).items():` - iterating settings.**
The settings dict has keys like "SHOT-001" and values with settings. The `sid` is used as the key for output directory and log file. This is correct.

**Defect: `f = APP / f"settings_{sid}.json"` - writing settings file.**
The settings are written to `/content/Wan2GP/settings_SHOT-001.json`. These are copied to `/content/out/settings_SHOT-001.json`. This is for debugging. LOW.

**Defect: `od = OUT / sid; od.mkdir(exist_ok=True)` - output directory.**
The output directory is `/content/out/SHOT-001`. This is correct.

**Defect: `for attempt in range(1, 5)` - 4 attempts.**
Already discussed. MEDIUM.

**Defect: `if "429 Too Many Requests" not in lg.read_bytes()[start:].decode(errors="replace") or attempt == 4: break`**
The condition is: break if 429 is NOT in the log OR attempt == 4. So:
- Attempt 1: run wgp.py. If 429 in log, don't break, wait 60s. If no 429, break.
- Attempt 2: run wgp.py. If 429 in log, don't break, wait 120s. If no 429, break.
- Attempt 3: run wgp.py. If 429 in log, don't break, wait 180s. If no 429, break.
- Attempt 4: run wgp.py. Even if 429, break (attempt == 4).

This seems reasonable. But the 429 detection is fragile. If wgp.py outputs 429 to stderr and the log capture doesn't include stderr properly, the detection fails. Also, `lg.read_bytes()[start:]` reads from the old start position. If the log file was truncated between attempts, `start` might be beyond the new file size, causing an IndexError. But `decode(errors="replace")` handles this.

Actually, `lg.read_bytes()[start:]` - if `start` > file size, this returns an empty bytes object, and `"" not in ""` is True, so it breaks. This is safe.

But the bigger issue: `lg.stat().st_size` is checked at the start of each attempt. If the log file is modified between the stat and the read, the size might be wrong. But this is unlikely. LOW.

**Defect: `rc = sh(...)` - return code.**
`sh()` returns the return code. `rc == 0` is checked. But `sh()` uses `subprocess.run` which might not raise on non-zero exit. The return code is captured. This is correct.

**Defect: `results[sid] = "ok" if rc == 0 and any(n.endswith(".mp4") for n in files) else "failed"`**
This checks if the render succeeded. Correct.

**Defect: `finish(results)` - writes RESULT.json and checks for failures.**
Already discussed.

**Defect: `note(f"END {sid} rc={rc} files={files}")` - logging.**
Correct.

**Defect: `subprocess.Popen(f"nvidia-smi ... > {OUT}/gpu.csv", shell=True)` - background process.**
Already discussed. LOW.

**Defect: `LOG = open(OUT / "timeline.txt", "a", buffering=1)` - file handle.**
Already discussed. LOW.

**Defect: `T0 = time.time()` - timing.**
Used in `note()` for elapsed time. Correct.

**Defect: `APP = Path("/content/Wan2GP")` - variable name.**
`APP` is used for the Wan2GP directory. But `APP` is also used in `run_kaggle.build` as the pack directory. Wait, no - in `build_h3_batch.py`, `APP` is not defined. In run.py, `APP = Path("/content/Wan2GP")`. This is local to run.py. No conflict. LOW.

**Defect: `T0 = time.time()` and `note(f"[{time.time() - T0:8.1f}s] {m}")` - timing format.**
The format `{time.time() - T0:8.1f}` produces something like "   12.3s". This is fine. LOW.

**Defect: `sh(f"cd {APP} && python wgp.py --process {f} --output-dir {od} --profile 5 --verbose 2", f"wgp_{sid}.log")` - command construction.**
The command uses f-strings with `{APP}`, `{f}`, `{od}`. These are Path objects. `str(Path)` is called implicitly in f-string. This is correct.

But wait - `--profile 5` is hardcoded. The settings don't have a profile field. The `--profile` argument to `run_kaggle.build` is 5. This matches. But if the user changes the profile, the run.py still has `--profile 5`. This is a bug!

Let me check: in `build_h3_batch.py`, line 72: `run_kaggle.build(rows, a.pack, a.batch, None, None, False, "colab", a.profile, manifest)`. The `a.profile` is passed to `run_kaggle.build`. The built run.py should include the profile setting. But in run.py, line 269: `sh(f"cd {APP} && python wgp.py --process {f} --output-dir {od} --profile 5 --verbose 2", ...)`. The `--profile 5` is hardcoded!

If the user changes `--profile` to 3, the built run.py still has `--profile 5`. This is a BUG!

Severity: HIGH. Wrong profile setting wastes compute units (different profiles give different quality/speed).

Fix: Use the profile from the settings or embed it in the run.py generation.

Wait, let me double-check. The settings show `settings_version: 2.82`. Does this include a profile field? Looking at the settings, I don't see a `profile` field. The profile is passed as a CLI argument to `run_kaggle.build` and then to `wgp.py`. But the built run.py hardcodes `--profile 5`.

So if the user builds with `--profile 3`, the run.py still uses `--profile 5`. This is definitely a bug.

But wait - maybe `run_kaggle.build` embeds the profile in the run.py script. Let me look at the run.py code again. The run.py is generated by `run_kaggle.build`. The generated run.py has `--profile 5` hardcoded. This suggests `run_kaggle.build` hardcodes the profile, ignoring the passed `a.profile`.

Actually, looking at line 72: `script, _ = run_kaggle.build(rows, a.pack, a.batch, None, None, False, "colab", a.profile, manifest)`. The `a.profile` is the 8th positional argument. The generated run.py has `--profile 5`. If `a.profile` is 5 (default), this matches. But if the user passes `--profile 3`, the generated run.py should have `--profile 3`, but it has `--profile 5`.

This is a real bug. Severity: HIGH.

Fix: Ensure `run_kaggle.build` uses the passed profile, or pass the profile through the settings.

Actually, wait. Let me reconsider. The `run_kaggle.build` function might have a fixed signature where the profile is always 5. Or it might ignore the passed profile. Either way, the generated run.py has `--profile 5` regardless of the CLI argument. This is a bug.

But the user said "the settings as built" and showed the settings. The settings don't include a profile. The `--profile 5` in run.py matches the default `--profile 5` in build_h3_batch.py. So if the user didn't change the profile, it works. But if they did, it's wrong.

The question is: does the user typically change the profile? The docstring says `--profile 5` is the default. The settings show `settings_version: 2.82` which might correspond to profile 5. So this might not be an issue in practice. But it's still a latent bug.

I'll flag it as MEDIUM since it only manifests if the user changes the profile.

Actually, let me reconsider. The user says "10 anime shots ... into one Colab batch". They didn't mention changing the profile. The default is 5, and the run.py uses 5. So this might not be an issue. But it's still a latent bug that could waste compute units if the user changes the profile.

I'll flag it as MEDIUM.

**Defect: `--verbose 2` in the wgp.py command.**
This enables verbose logging. The log file captures this output. This is fine. LOW.

**Defect: `wgp.py --process {f} --output-dir {od} --profile 5 --verbose 2` - the `--process` flag.**
The `f` is the settings file path. `wgp.py --process <settings_file>` processes the shot. This is correct.

**Defect: `files = sorted(p.name for p in od.iterdir())` - listing output files.**
This lists all files in the output directory. If there are partial files from previous attempts, they're included. The check `any(n.endswith(".mp4") for n in files)` detects if any .mp4 was created. This is correct.

But if wgp.py creates a partial .mp4 file (e.g., .mp4.part), it wouldn't be detected. The next attempt might overwrite it or append. This could cause issues. MEDIUM.

Actually, let me think about this more. If wgp.py creates `output.mp4.part` and then renames it to `output.mp4` at the end, the `.part` file remains. Next attempt, wgp.py might create a new `output.mp4.part` and append to it. At the end, it renames to `output.mp4`. But the old `.part` file is still there. The `files` list would include both `output.mp4` (from previous attempt) and `output.mp4.part` (from current attempt). The check `any(n.endswith(".mp4"))` would find `output.mp4` and break. But the `.part` file is stale.

This could cause issues if wgp.py doesn't clean up partial files. But this is speculative. LOW.

**Defect: `if any(n.endswith(".mp4") for n in files): break` - early termination.**
If a .mp4 is found, the loop breaks. But what if the .mp4 is incomplete? The check doesn't verify completeness. MEDIUM.

Actually, the `--timeout` of 6 hours should ensure the process completes. If it times out, the exec command fails and the session is stopped. So incomplete .mp4 files shouldn't persist. LOW.

**Defect: `note(f"HF 429 on {sid}, attempt {attempt}: waiting {60 * attempt}s"); time.sleep(60 * attempt)`**
The wait time is 60, 120, 180, 240 seconds. Total wait: 600 seconds (10 minutes). This might not be enough for HF rate limits. MEDIUM.

**Defect: No maximum wait time cap.**
If all 4 attempts get 429, the shot fails after ~10 minutes of waiting. This could waste compute units. MEDIUM.

**Defect: `lg.read_bytes()[start:]` - reading log from offset.**
If the log file is appended to, this reads new content. But if the log is rotated, `start` might be invalid. LOW.

**Defect: `lg.stat().st_size if lg.exists() else 0` - stat check.**
If the log file doesn't exist, `start = 0`. This is correct. LOW.

**Defect: `subprocess.Popen(f"nvidia-smi ... > {OUT}/gpu.csv", shell=True)` - background process never waited.**
If the script exits, this process continues. But it's writing to a file, not consuming GPU. LOW.

**Defect: `LOG = open(OUT / "timeline.txt", "a", buffering=1)` - file opened at module level.**
If the script is imported (not run as main), the file is opened but might not be closed. But the script is run as main. LOW.

**Defect: `import run_kaggle` and `from h3.compile_h3_sing8 import compile_fl2va_prompt` - imports.**
These are local imports. If the modules don't exist, the build fails. But the docstring says it works. LOW.

**Defect: `sys.path.insert(0, str(HERE))` and `sys.path.insert(0, str(HERE.parent))` - path manipulation.**
This adds the script's directory and parent to sys.path. This allows importing `run_kaggle` and `h3`. Correct. LOW.

**Defect: `import run_kaggle  # noqa: E402` - import after non-import statements.**
Line 15 is after lines 6-13 which are imports. Line 15 is `import run_kaggle`. The `# noqa: E402` suppresses the E402 lint error. This is fine. LOW.

**Defect: `from h3.compile_h3_sing8 import compile_fl2va_prompt  # noqa: E402` - same.**
Fine. LOW.

**Defect: `def jpeg_b64(path, size=(768, 1344))` - default size.**
The default is (768, 1344). But the build might use a different resolution. Line 70-71: `w, h = (int(v) for v in a.resolution.split("x")); run_kaggle.png_b64 = lambda path: jpeg_b64(path, (w, h))`. The size is set from `a.resolution`. So the default in the function definition is overridden. LOW.

**Defect: `if w * th > h * tw:` - aspect ratio check.**
The condition checks if the image is wider than the target aspect ratio. If so, center crop horizontally. This is correct for maintaining aspect ratio. LOW.

**Defect: `im = im.resize(size, Image.LANCZOS)` - resize with LANCZOS.**
LANCZOS is high quality. Correct. LOW.

**Defect: `im.save(buf, "JPEG", quality=90)` - JPEG quality 90.**
Standard quality. LOW.

**Defect: `base64.b64encode(buf.getvalue()).decode("ascii")` - base64 encoding.**
Correct. LOW.

**Defect: `legacy_rows` - `frames = sh["timing_and_lattice"]["pixel_frames"]`**
This gets the frame count from the story. Correct. LOW.

**Defect: `prompt = compile_fl2va_prompt(sh, story["registry"])["compiled_prompt"]`**
This compiles the prompt. Correct. LOW.

**Defect: `rows.append({"id": sid, "mode": "fl2va", "route": "pika6", "aspect": "9:16", "resolution": resolution, "render_frames": frames, "start": ..., "end": ..., "prompt_override": prompt})`**
The row includes all necessary fields. Correct. LOW.

**Defect: `if not rows: raise ValueError("no shots selected")`**
If no shots are selected, raises an error. Correct. LOW.

**Defect: `manifest = {}` - empty manifest.**
The manifest is populated by `run_kaggle.build`. The `embed_mb_total` is added. Correct. LOW.

**Defect: `(folder / "run.py").write_text(script, encoding="utf-8")` - writing run.py.**
Correct. LOW.

**Defect: `(folder / "render_manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")` - writing manifest.**
Correct. LOW.

**Defect: `print("built", folder, "|", len(rows), "shots,", sum(r["render_frames"] for r in rows), "frames,", manifest["embed_mb_total"], "MB embedded")` - print summary.**
Correct. LOW.

OK, I think I've found the main defects. Let me also look for any I might have missed.

**Defect: `run_colab_batch.py` line 113: `t0.batch(a.batch.replace("_", "-"), a.gpu)`**
This passes the hyphenated batch name to `t0.batch`. But `t0.batch` uses `name` for the session name and `RUN_PY` for the script path. `RUN_PY` is set to `HERE / "colab_batches" / a.batch / "run.py"` (original name with underscores). So the session name is "h3-batch" but the script path is `colab_batches/h3_batch/run.py`. This is consistent as long as the user passes the same name to both build and run. LOW.

But wait - what if the user passes "h3-batch" (with hyphen) to run_colab_batch.py? Then `a.batch` = "h3-batch", `t0.RUN_PY` = `colab_batches/h3-batch/run.py`, and `t0.batch("h3-batch", ...)`. This is also consistent. So no issue.

**Defect: `t0.RUN_PY = HERE / "colab_batches" / a.batch / "run.py"` - uses original batch name.**
If the user passes "h3_batch" to run, `t0.RUN_PY` points to `colab_batches/h3_batch/run.py`. But the directory was created by build with the same name. So this is correct. LOW.

**Defect: `t0.RESULTS = Path(a.results)` - results directory.**
The results directory is specified by the user. Correct. LOW.

**Defect: `t0.DRY = not a.go` - dry run flag.**
Correct. LOW.

**Defect: `if not t0.RUN_PY.exists(): print(...); return 1` - missing run.py check.**
Correct. LOW.

**Defect: `print("DRY RUN: nothing is started" if t0.DRY else "LIVE RUN: this spends compute units", flush=True)` - print statement.**
Correct. LOW.

**Defect: `try: t0.batch(...) except (t0.CliError, OSError) as e: print("STOPPED:", e); return 1 except BaseException: print(...); raise`**
The first except catches CliError and OSError. The second catches everything else (KeyboardInterrupt, SystemExit, etc.). If a BaseException occurs, it warns about the session and re-raises. This is correct for cleanup warnings. LOW.

But the issue is: if `t0.batch` raises a BaseException (e.g., SystemExit from finish()), the warning is printed but the session isn't stopped (due to Defect 2). This is the same as Defect 2.

**Defect: `print("dry run printed" if t0.DRY else f"done: clips and logs in {t0.RESULTS}")` - final print.**
Correct. LOW.

**Defect: `sys.exit(main())` - exit code.**
Correct. LOW.

Now let me also consider the `run.py` defects more carefully.

**Defect: `subprocess.Popen(f"nvidia-smi ... > {OUT}/gpu.csv", shell=True)` - background process.**
This starts a background process that writes gpu.csv every 5 seconds. If the script exits, this process continues. But it's writing to a file, not consuming GPU. LOW.

But actually, if the script is killed (e.g., by colab timeout), the Popen process might continue and write to the file. This is harmless. LOW.

**Defect: `if sh(f"git clone ...", "setup.log") or sh(f"cd {APP} && pip install -r requirements.txt", "setup.log"):`**
If either command fails, the script raises SystemExit(1). But the `or` means if the first succeeds, the second runs. If the first fails, the second doesn't run. This is correct. LOW.

But wait - `sh()` returns the return code. `if sh(...) or sh(...)` - if the first returns 0 (success), the second runs. If the first returns non-zero, the second doesn't run. This is correct. LOW.

**Defect: `(TMP / "ckpts").mkdir(exist_ok=True)` - creating ckpts dir.**
Correct. LOW.

**Defect: `if (APP / "ckpts").is_dir() and not (APP / "ckpts").is_symlink():`**
If APP/ckpts is a regular directory (not symlink), move its contents to TMP/ckpts and remove it. Then create a symlink. This is for caching. LOW.

But on Windows, `is_symlink()` might behave differently. The docstring says it worked on Windows. LOW.

**Defect: `os.environ["HF_HOME"] = str(TMP / "hf")` - HF cache.**
This sets HF cache to `/content/cache/hf`. But Wan2GP might use a different HF cache location. If models are already cached, this is fine. If not, Wan2GP will download them to this location. LOW.

**Defect: `inputs = APP / "inputs"; inputs.mkdir(exist_ok=True)` - creating inputs dir.**
Correct. LOW.

**Defect: `for name, b64 in json.loads(base64.b64decode("<BLOB %d chars>")).items(): (inputs / name).write_bytes(base64.b64decode(b64))`**
Writes keyframe files. The filenames come from the JSON keys. Correct.

But the JPEG bytes are stored under `.png` names. If Wan2GP validates the file extension, this could fail. The comment says it works. LOW.

**Defect: `def finish(results):` - finish function.**
Already discussed. LOW.

**Defect: `(OUT / "RESULT.json").write_text(json.dumps(results, indent=1))` - writing RESULT.json.**
Correct. LOW.

**Defect: `failed = sorted(s for s, v in results.items() if v != "ok")` - finding failures.**
Correct. LOW.

**Defect: `if failed: note("FAILED: " + ", ".join(failed)); raise SystemExit(1)` - raising on failure.**
Already discussed. Related to Defect 2.

**Defect: `results = {}` - empty results dict.**
Correct. LOW.

**Defect: `for sid, settings in json.loads(base64.b64decode("<BLOB %d chars>")).items():`**
Iterates over settings. Correct. LOW.

**Defect: `f = APP / f"settings_{sid}.json"; f.write_text(json.dumps(settings, indent=1)); shutil.copy(f, OUT / f.name)`**
Writes and copies settings files. Correct. LOW.

**Defect: `od = OUT / sid; od.mkdir(exist_ok=True); note(f"START {sid}")`**
Creates output directory and logs start. Correct. LOW.

**Defect: `for attempt in range(1, 5):` - 4 attempts.**
Already discussed. MEDIUM.

**Defect: `lg = OUT / f"wgp_{sid}.log"; start = lg.stat().st_size if lg.exists() else 0`**
Gets log file size. Correct. LOW.

**Defect: `rc = sh(f"cd {APP} && python wgp.py --process {f} --output-dir {od} --profile 5 --verbose 2", f"wgp_{sid}.log")`**
Runs wgp.py. The `--profile 5` is hardcoded. Already discussed as MEDIUM.

**Defect: `files = sorted(p.name for p in od.iterdir())`**
Lists output files. Correct. LOW.

**Defect: `if any(n.endswith(".mp4") for n in files): break`**
Checks for .mp4. Correct. LOW.

**Defect: `if "429 Too Many Requests" not in lg.read_bytes()[start:].decode(errors="replace") or attempt == 4: break`**
Checks for 429. Already discussed. MEDIUM.

**Defect: `note(f"HF 429 on {sid}, attempt {attempt}: waiting {60 * attempt}s"); time.sleep(60 * attempt)`**
Waits and sleeps. Already discussed. MEDIUM.

**Defect: `results[sid] = "ok" if rc == 0 and any(n.endswith(".mp4") for n in files) else "failed"`**
Sets result. Correct. LOW.

**Defect: `note(f"END {sid} rc={rc} files={files}")`**
Logs end. Correct. LOW.

**Defect: `finish(results)`**
Calls finish. Already discussed. LOW.

OK, let me also check the `t0_pack/run_t0_colab.py` for defects.

**Defect: `EXEC_TIMEOUT = 6 * 3600` - 6 hour timeout.**
For 10 shots with ~2090 frames, 6 hours should be plenty. But if the script is too large (19.7 MB), the exec might not start. The second attempt (11.3 MB) worked. So the timeout is fine for the working case. LOW.

But actually, the failure was about the script not reaching the VM, not about timeout. So the timeout isn't the issue. LOW.

**Defect: `LIST_CODE` - the listing code.**
```python
LIST_CODE = """
import os
out = "/content/out"
names = sorted(os.path.relpath(os.path.join(d, f), out) for d, _, fs in os.walk(out) for f in fs if f.endswith(".mp4"))
names += [n for n in sorted(os.listdir(out)) if n in ("timeline.txt", "RESULT.json", "gpu.csv") or (n.startswith("wgp_") and n.endswith(".log"))]
open(os.path.join(out, "FILES.txt"), "w").write("\\n".join(names) + "\\n")
print("\\n".join(names))
"""
```
This walks `/content/out` and lists .mp4 files, plus timeline.txt, RESULT.json, gpu.csv, and wgp_*.log files. It writes these to FILES.txt. This seems correct.

But the `\\n` in the triple-quoted string - in Python, `\\n` in a regular string is a backslash followed by 'n'. But in a triple-quoted string, `\\n` is still a backslash followed by 'n'. Wait, no. In a triple-quoted string, `\\n` is an escaped backslash followed by 'n', which produces `\n` (backslash-n) in the actual string. But the code uses `"\\n".join(names)` which joins with newline characters. Wait, let me think again.

In the LIST_CODE string:
```python
LIST_CODE = """
import os
out = "/content/out"
names = sorted(...)
names += [...]
open(os.path.join(out, "FILES.txt"), "w").write("\\n".join(names) + "\\n")
print("\\n".join(names))
"""
```

The `\\n` in the triple-quoted string is an escaped backslash followed by 'n', which produces the two-character sequence `\n` (backslash + n) in the actual string. Then `"\\n".join(names)` would join names with the literal two-character sequence `\n`, not a newline. This is a BUG!

Wait, let me re-check. In Python:
- `"\n"` is a newline character
- `"\\n"` is a backslash followed by 'n' (two characters)
- In a triple-quoted string `"""..."""`, `\\n` is still `\\n` (backslash + n), because the backslash needs to be escaped.

So `"\\n".join(names)` joins names with the literal string `\n` (backslash + n), not a newline. This means FILES.txt would have names separated by literal `\n` characters, not actual newlines. When `fetch` reads FILES.txt with `.split()`, it splits on whitespace (including newlines), so the names would still be separated correctly. But the FILES.txt file would have literal `\n` characters instead of newlines, which is messy but functional.

Actually, `.split()` without arguments splits on any whitespace, including newlines. So even if FILES.txt has literal `\n` characters, `.split()` would split correctly. So this is a cosmetic issue, not a functional bug. LOW.

But wait - the `print("\\n".join(names))` would print names separated by literal `\n`, not newlines. This is cosmetic. LOW.

Actually, I need to be more careful. In the triple-quoted string:
```python
LIST_CODE = """
...
open(os.path.join(out, "FILES.txt"), "w").write("\\n".join(names) + "\\n")
...
"""
```

The `\\n` in the triple-quoted string is the two characters: backslash and 'n'. So the actual string contains `\n` (backslash + n). When this string is executed as Python code, `"\\n"` in the executed code is... wait, no. The LIST_CODE is a string that contains Python code. When the code is executed, `"\\n"` is evaluated as a Python string literal, which produces `\n` (backslash + n). So `"\\n".join(names)` joins names with the literal two-character sequence `\n`, not a newline.

This is indeed a bug. FILES.txt would have names separated by literal `\n` characters. But `.split()` handles this correctly. So it's a cosmetic issue. LOW.

But actually, let me reconsider. The LIST_CODE is a multi-line string. The `\\n` appears twice:
1. `open(...).write("\\n".join(names) + "\\n")` - writes names joined by `\n` (literal) plus a trailing `\n` (literal)
2. `print("\\n".join(names))` - prints names joined by `\n` (literal)

So FILES.txt would have:
```
name1\nname2\nname3\n
```
Where `\n` is the literal two characters backslash + n. When `fetch` reads this with `.split()`, it splits on whitespace, so it gets ["name1", "name2", "name3"]. This works.

But the FILES.txt file is messy. It's not a functional bug, but it's ugly. LOW.

Actually, I realize I should double-check. In Python, within a triple-quoted string, `\\n` is:
- `\\` → single backslash
- `n` → letter n
So `\\n` → `\n` (backslash + n, two characters)

Then when this string is executed as Python code, `"\\n"` is a string literal that evaluates to `\n` (backslash + n, two characters). So `"\\n".join(names)` joins names with the two-character sequence `\n`, not a newline.

Yes, this is a cosmetic bug. LOW.

**Defect: `cli(["exec", "-s", name], stdin=LIST_CODE)` - missing `-f`.**
Already discussed as MEDIUM.

**Defect: `RESULTS = HERE / "results"` - results directory.**
Defined at module level. Correct. LOW.

**Defect: `OUT = "/content/out"` - hardcoded.**
Already discussed. LOW.

**Defect: `RUN_PY = HERE.parent / "colab_batches" / "t0" / "run.py"` - hardcoded path.**
This is specific to the T0 batch. For the H3 batch, the path is different. But `run_colab_batch.py` sets `t0.RUN_PY` dynamically. So this is fine. LOW.

**Defect: `class CliError(Exception): pass` - custom exception.**
Correct. LOW.

**Defect: `def cli(args, stdin=None):` - CLI wrapper.**
Correct. LOW.

**Defect: `print(("DRY RUN: " if DRY else "$ ") + "colab " + " ".join(args) + ("  (code on stdin)" if stdin else ""), flush=True)` - print command.**
Correct. LOW.

**Defect: `kwargs = {"input": stdin} if stdin is not None else {"stdin": subprocess.DEVNULL}` - stdin handling.**
Correct. LOW.

**Defect: `if subprocess.run(["colab", *args], text=True, **kwargs).returncode:` - check return code.**
Correct. LOW.

**Defect: `raise CliError(f"colab {args[0]} failed: stopping, no retries")` - raise on failure.**
Correct. LOW.

**Defect: `def fetch(name):` - fetch function.**
Already discussed. LOW.

**Defect: `RESULTS.mkdir(parents=True, exist_ok=True)` - create results dir.**
Correct. LOW.

**Defect: `cli(["download", "-s", name, f"{OUT}/FILES.txt", str(RESULTS / "FILES.txt")])` - download FILES.txt.**
Correct. LOW.

**Defect: `if DRY: cli(["download", "-s", name, f"{OUT}/<each file named in FILES.txt>", "results/<same path>"]); return`**
In dry run, downloads FILES.txt and each file. But the `<each file named in FILES.txt>` is a placeholder that doesn't actually iterate over FILES.txt. This is a BUG!

In dry run, the code tries to download each file named in FILES.txt, but it doesn't actually read FILES.txt to get the list of files. The `<each file named in FILES.txt>` is a literal string, not a loop. So in dry run, no files are downloaded. This is a BUG.

Wait, let me re-read:
```python
if DRY:
    cli(["download", "-s", name, f"{OUT}/<each file named in FILES.txt>", "results/<same path>"])
    return
```

This is a single `cli` call with the literal string `<each file named in FILES.txt>`. It doesn't iterate over FILES.txt. So in dry run, no files are downloaded. The dry run is supposed to "prints the commands only" but doesn't actually print the download commands for each file.

This is a BUG. In dry run, the user expects to see the download commands for each file, but the code doesn't generate them.

Severity: MEDIUM. Dry run is broken - it doesn't show the actual download commands.

Fix: Iterate over FILES.txt and generate download commands for each file.

Actually, wait. Let me re-read the docstring: "DRY RUN unless --go (a real run spends units)". And "python run_colab_batch.py BATCH --results OUT_DIR -> prints the commands only". So in dry run, it should print the commands. But the current code doesn't print download commands for individual files in dry run. It only prints the FILES.txt download command.

This is a real defect. MEDIUM.

Fix: In dry run, iterate over FILES.txt and print download commands for each file.

**Defect: `if not (RESULTS / "FILES.txt").exists(): raise CliError("FILES.txt did not come back: nothing to fetch")` - check FILES.txt.**
Correct. LOW.

**Defect: `for rel in (RESULTS / "FILES.txt").read_text(encoding="utf-8").split():` - iterate files.**
Correct. LOW.

**Defect: `(RESULTS / rel).parent.mkdir(parents=True, exist_ok=True)` - create parent dirs.**
Correct. LOW.

**Defect: `cli(["download", "-s", name, f"{OUT}/{rel}", str(RESULTS / rel)])` - download each file.**
Correct. LOW.

**Defect: `def batch(name, gpu):` - batch function.**
Already discussed. HIGH (no finally).

**Defect: `cli(["usage"])` - usage command.**
Correct. LOW.

**Defect: `error = None` - error tracking.**
Correct. LOW.

**Defect: `try: cli(["new", "-s", name, "--gpu", gpu])` - new session.**
Correct. LOW.

**Defect: `try: cli(["exec", "-s", name, "-f", str(RUN_PY), "--timeout", str(EXEC_TIMEOUT)])` - exec run.py.**
Correct. LOW.

**Defect: `except CliError as e: error = e` - capture exec error.**
Correct. LOW.

**Defect: `cli(["exec", "-s", name], stdin=LIST_CODE)` - list files.**
Already discussed as MEDIUM.

**Defect: `fetch(name)` - fetch clips.**
Already discussed. LOW.

**Defect: `except CliError as e: print(...); raise e` - keep session on fetch failure.**
Already discussed as HIGH.

**Defect: `cli(["stop", "-s", name])` - stop session.**
Already discussed. Not reached on exception.

**Defect: `if error: raise error` - re-raise captured error.**
Correct. LOW.

**Defect: `def main(argv=None):` - main function.**
Correct. LOW.

**Defect: `global DRY` - global variable.**
Correct. LOW.

**Defect: `ap.add_argument("--go", action="store_true", help="really run the commands (spends compute units)")` - --go flag.**
Correct. LOW.

**Defect: `ap.add_argument("--gpu", default="G4", choices=("G4", "A100", "L4", "T4"))` - GPU choice.**
Correct. LOW.

**Defect: `ap.add_argument("--name", default="t0-kaliya", help="Colab session name")` - --name flag.**
Correct. LOW.

**Defect: `DRY = not a.go` - dry run flag.**
Correct. LOW.

**Defect: `if not RUN_PY.exists(): print(...); if not DRY: return 1` - missing run.py check.**
Correct. LOW.

**Defect: `if sys.platform == "win32": print(...)` - Windows note.**
Correct. LOW.

**Defect: `print("DRY RUN: nothing is started" if DRY else "LIVE RUN: this spends compute units", flush=True)` - print.**
Correct. LOW.

**Defect: `try: batch(a.name, a.gpu) except (CliError, OSError) as e: print("STOPPED:", e); return 1` - error handling.**
Correct. LOW.

**Defect: `print("dry run printed" if DRY else f"done: clips and logs in {RESULTS}")` - final print.**
Correct. LOW.

**Defect: `sys.exit(main())` - exit.**
Correct. LOW.

OK, now let me also look at the `run.py` for the `--profile 5` issue more carefully.

The run.py is generated by `run_kaggle.build`. The generated run.py has `--profile 5` hardcoded. But `build_h3_batch.py` passes `a.profile` to `run_kaggle.build`. If `a.profile` is 5 (default), this matches. But if the user changes `--profile`, the generated run.py still has `--profile 5`.

This is a real bug. But is it HIGH or MEDIUM? If the user typically uses the default profile (5), this isn't an issue. But if they change it, it wastes compute units with the wrong profile. I'll flag it as MEDIUM.

Actually, wait. Let me reconsider. The user says "10 anime shots ... into one Colab batch". They didn't mention changing the profile. The default is 5, and the run.py uses 5. So this might not be an issue in practice. But it's still a latent bug.

The question asks for defects that "would waste compute units, hang, lose clips, leave a session running, or give wrong video". Using the wrong profile could give wrong video (different quality/speed). So this qualifies. MEDIUM.

Let me also check: are there any defects related to the "19.7 MB script never reached the VM" issue?

The 19.7 MB script was too large for `colab exec -f run.py`. The second attempt (11.3 MB) worked. There's no code defect that causes the script to be too large - it's a packaging issue. The fix was to reduce the size by converting PNG to JPEG. But the code doesn't check the script size before running. If the script is too large, `colab exec` might hang or fail silently.

This isn't really a code defect - it's a design flaw. The code assumes the script will fit. I'll flag it as LOW.

Actually, the user specifically mentions "payload size/transport" as a concern. Let me think about this. The 19.7 MB script caused the exec to never start. Is there a code defect that prevents checking the payload size? No - the code doesn't check the script size. But this is more of a packaging issue than a code defect.

I'll flag it as LOW.

Now let me also consider: the user mentions "start/end image paths and formats (JPEG bytes stored under .png names)". This is about the JPEG-under-.png issue. I've already flagged this as LOW.

The user also mentions "frame counts". Let me check if the frame counts are correct. The "all frames" section shows 10 shots with frame counts summing to 2090. The settings show video_length for SHOT-001 (175) and SHOT-002 (158). These match the frame counts. For other shots, we don't see settings, but the frame counts are given. If the settings for other shots have different video_length, there could be a mismatch. But this is data, not code. LOW.

The user also mentions "output collection". The `fetch` function collects output files. If FILES.txt is not created (due to the missing `-f` issue), no files are collected. This is already covered.

The user also mentions "stop-after-download logic". The `cli(["stop", "-s", name])` is called after fetch. If fetch fails, the session is kept running. This is already covered as HIGH.

The user also mentions "anything missing a 3-minute proof that the script started". The script starts with `subprocess.Popen(f"nvidia-smi ...")` and then `sh(f"git clone ...")`. The git clone takes some time. There's no explicit proof that the script started within 3 minutes. But the `note()` function logs timestamps. The first `note()` call would show the elapsed time. If the script starts within 3 minutes, the first note would show < 180s. But if the git clone takes longer, the first note would show > 180s.

Actually, the `note()` function is called after the Popen and git clone. So the first `note()` call shows the time since T0 (which is set at the beginning). If the git clone takes 2 minutes, the first note shows ~120s. This is within 3 minutes. But if the git clone takes 5 minutes, the first note shows ~300s, which is > 3 minutes.

But the user asks for "anything missing a 3-minute proof that the script started". This suggests there should be a proof that the script started within 3 minutes. The current code doesn't provide such a proof. But this is more of a monitoring concern than a code defect.

Actually, I think the concern is about the `colab exec` command. If the script takes more than 3 minutes to start (e.g., due to large script size), the user has no proof that it started. The `colab log` would show no EXEC. But this is a packaging issue, not a code defect.

I'll skip this as it's not a code defect.

Let me also check: is there a defect in the `except BaseException` handler in `run_colab_batch.py`?

Line 117-119:
```python
except BaseException:    # interrupt or a bug: the GPU session may still be running and spending units
    print(f"SESSION MAY STILL RUN: check `colab sessions`, then `colab stop -s {a.batch.replace('_', '-')}`", flush=True)
    raise
```

This catches ALL exceptions including SystemExit, KeyboardInterrupt, etc. If the batch fails for any reason, it warns about the session. But due to Defect 2 (no finally in t0.batch), the session isn't stopped. So the warning is accurate.

But the warning says "check `colab sessions`, then `colab stop -s {name}`". This tells the user to manually stop the session. This is correct behavior given the lack of finally. LOW.

OK, I think I've found all the major defects. Let me summarize:

1. **HIGH: No finally block in t0.batch** - session left running on any exception (including OSError, CliError from fetch, etc.)
   - File: director/t0_pack/run_t0_colab.py:185-201
   - Fix: wrap the body in try/finally, ensuring `cli(["stop", "-s", name])` always runs

2. **HIGH: `except CliError` in t0.batch keeps session running** - when fetch fails, session is not stopped
   - File: director/t0_pack/run_t0_colab.py:196-198
   - Fix: add `cli(["stop", "-s", name])` in the except block, or use finally

3. **MEDIUM: `cli(["exec", "-s", name], stdin=LIST_CODE)` missing `-f`** - might not execute LIST_CODE, FILES.txt never created
   - File: director/t0_pack/run_t0_colab.py:194
   - Fix: write LIST_CODE to a temp file and use `colab exec -s name -f <tempfile>`

4. **MEDIUM: Dry run doesn't print download commands for individual files** - `if DRY: cli(["download", "-s", name, f"{OUT}/<each file named in FILES.txt>", ...])` doesn't iterate
   - File: director/t0_pack/run_t0_colab.py:175-177
   - Fix: iterate over FILES.txt and print download commands for each file

5. **MEDIUM: `--profile 5` hardcoded in run.py** - ignores `--profile` CLI argument
   - File: director/run.py (built):269
   - Fix: embed the profile from settings or pass it through run_kaggle.build

6. **MEDIUM: HF 429 detection is fragile** - might not detect 429 if format differs, causing unnecessary retries or infinite loops
   - File: director/run.py (built):272
   - Fix: improve 429 detection (e.g., check HTTP status code, use regex)

7. **LOW: JPEG bytes under .png names** - potential format validation issue
   - File: director/build_h3_batch.py:19-39 (jpeg_b64) and director/run.py (built):256
   - Fix: rename files to .jpg or ensure Wan2GP reads by content

8. **LOW: Hardcoded `/content` paths** - breaks if script runs outside Colab VM
   - File: director/run.py (built):235-237
   - Fix: use environment variables or platform detection

Wait, I should also check: is there a defect in the `except BaseException` catching SystemExit? When `finish()` raises SystemExit(1), it's caught by `except BaseException`, which warns about the session. But the session might already be stopped (if t0.batch reached `cli(["stop", "-s", name])`). The warning is misleading. But this is a minor issue.

Also, I should check: does the `except BaseException` in `run_colab_batch.py` properly handle the case where the session is still running? It prints a warning and re-raises. The re-raised SystemExit propagates to `sys.exit(main())`, which exits the process. The session is still running. The user needs to manually stop it. This is correct behavior given the lack of finally. LOW.

Let me also reconsider the `cli(["exec", "-s", name], stdin=LIST_CODE)` issue. Looking at the Colab CLI documentation:

`colab exec` options:
- `-f, --file FILE` - Run the specified file
- Without `-f`, it runs the default command

The default command might be `python3` or empty. If it's `python3`, piping LIST_CODE as stdin would execute it. But this is undocumented.

Actually, I just realized: `colab exec` without `-f` might not do anything useful. It might print help or error. If it errors, CliError is raised, and the session is kept running (Defect 2). This is a cascading effect.

But the docstring says T0 worked on 2026-11-05. So maybe `colab exec -s name` without `-f` does something with stdin. Or maybe the LIST_CODE is executed as a command somehow.

Regardless, this is fragile. I'll flag it as MEDIUM.

Actually, let me reconsider. Maybe `colab exec` without `-f` runs the default command which is `python3`, and the stdin is piped to it. In that case, LIST_CODE would be executed as Python code. This would create FILES.txt. Then `fetch` would work.

But this is undocumented behavior. The safer approach is to use `-f` with a temp file. I'll flag it as MEDIUM.

Let me also check: is there a defect in the `fetch` function's dry run path?

```python
if DRY:
    cli(["download", "-s", name, f"{OUT}/<each file named in FILES.txt>", "results/<same path>"])
    return
```

This is a single `cli` call with the literal string `<each file named in FILES.txt>`. It doesn't iterate over FILES.txt. So in dry run:
1. Download FILES.txt is printed (but not actually executed in dry run, since `cli` returns early in DRY mode)
2. The individual file download is printed as a literal string, not as actual commands

So in dry run, the user sees:
```
$ colab download -s <each file named in FILES.txt> /content/out/FILES.txt results/FILES.txt
```

This is not useful - it's a literal string, not the actual file names. This is a BUG.

Fix: In dry run, read FILES.txt (if it exists) and print download commands for each file. Or, better yet, in dry run, just print the FILES.txt download command and skip individual files (since they don't exist locally).

Actually, in dry run, the individual files don't exist locally, so downloading them doesn't make sense. The dry run should just print the FILES.txt download command and maybe indicate that individual files would be downloaded. But the current code prints a literal string instead of actual commands.

This is a real defect. MEDIUM.

Fix: In dry run, iterate over FILES.txt and print download commands for each file. Or, simpler: in dry run, just print the FILES.txt download command and a note that individual files would be downloaded.

Actually, the simplest fix: in dry run, just print the FILES.txt download command and return. Don't try to download individual files (they don't exist locally). The user can see what would be downloaded by inspecting FILES.txt.

But the current code tries to download individual files in dry run, which doesn't work. The fix is to either:
1. Skip individual file downloads in dry run (just print FILES.txt download)
2. Iterate over FILES.txt and print commands for each file

Option 1 is simpler and more correct. I'll suggest that.

OK, let me also look for one more defect:

**Defect: `subprocess.Popen(f"nvidia-smi ... > {OUT}/gpu.csv", shell=True)` - background process.**
This starts a background process. If the script is killed, the process might continue. But it's writing to a file, not consuming GPU. LOW.

But actually, if the script is killed by colab timeout, the Popen process might continue and hold a file handle. This could prevent the file from being cleaned up. But it's not a compute unit issue. LOW.

**Defect: `LOG = open(OUT / "timeline.txt", "a", buffering=1)` - file handle at module level.**
If the script is imported (not run as main), the file is opened but might not be closed. But the script is run as main. LOW.

**Defect: `APP = Path("/content/Wan2GP")` - variable shadowing.**
`APP` is used in run.py for the Wan2GP directory. But `APP` is also used in `run_kaggle.build` as the pack directory. Wait, no - in `build_h3_batch.py`, `APP` is not defined. In run.py, `APP = Path("/content/Wan2GP")`. This is local to run.py. No conflict. LOW.

**Defect: `T0 = time.time()` - timing variable.**
Used in `note()`. Correct. LOW.

**Defect: `note(f"[{time.time() - T0:8.1f}s] {m}")` - timing format.**
The format `{time.time() - T0:8.1f}` produces something like "   12.3s". This is fine. LOW.

**Defect: `sh(f"cd {APP} && python wgp.py --process {f} --output-dir {od} --profile 5 --verbose 2", f"wgp_{sid}.log")` - command.**
The `--profile 5` is hardcoded. Already discussed as MEDIUM.

**Defect: `files = sorted(p.name for p in od.iterdir())` - listing files.**
Correct. LOW.

**Defect: `if any(n.endswith(".mp4") for n in files): break` - check for .mp4.**
Correct. LOW.

**Defect: `if "429 Too Many Requests" not in lg.read_bytes()[start:].decode(errors="replace") or attempt == 4: break` - 429 check.**
Already discussed as MEDIUM.

**Defect: `note(f"HF 429 on {sid}, attempt {attempt}: waiting {60 * attempt}s"); time.sleep(60 * attempt)` - wait.**
Already discussed as MEDIUM.

**Defect: `results[sid] = "ok" if rc == 0 and any(n.endswith(".mp4") for n in files) else "failed"` - result.**
Correct. LOW.

**Defect: `note(f"END {sid} rc={rc} files={files}")` - log.**
Correct. LOW.

**Defect: `finish(results)` - finish.**
Already discussed. LOW.

OK, I think I've been thorough enough. Let me also check one more thing: the `except BaseException` in `run_colab_batch.py` catches SystemExit. When `finish()` raises SystemExit(1), the warning is printed. But the session might already be stopped (if t0.batch reached `cli(["stop", "-s", name])`). The warning is misleading. But this is a minor issue.

Actually, let me trace the flow more carefully:

1. run.py finishes rendering all shots
2. `finish(results)` is called
3. If any shot failed, `SystemExit(1)` is raised
4. This propagates through run.py (the exec target)
5. The exec command completes with exit code 1
6. t0.batch continues: `cli(["exec", "-s", name], stdin=LIST_CODE)` runs (executes LIST_CODE, creates FILES.txt)
7. `fetch(name)` runs (downloads clips)
8. `cli(["stop", "-s", name])` runs (stops session)
9. t0.batch returns normally (no exception)
10. run_colab_batch.py prints "done: clips and logs in {RESULTS}"

Wait, but `finish()` raises SystemExit(1), which propagates through run.py. Does t0.batch catch it? No - t0.batch doesn't catch SystemExit. It propagates through t0.batch, through run_colab_batch.py's `except BaseException`, which catches it and prints the warning. Then it re-raises, and `sys.exit(main())` exits with code 1.

But wait - steps 6-8 happen BEFORE the SystemExit propagates. Because `finish()` is called at the end of run.py, after the for loop. The exec command completes (with error), then t0.batch continues with listing, fetching, and stopping. Then the SystemExit propagates.

So the session IS stopped before the warning. The warning is misleading but not harmful. LOW.

But if an exception occurs DURING the loop (not at finish), the flow is different:
1. Exception occurs during rendering (e.g., wgp.py crashes)
2. Exception propagates through run.py
3. Exec command completes with error
4. t0.batch continues: listing, fetching, stopping
5. Exception propagates through t0.batch
6. run_colab_batch.py catches in `except BaseException`, warns

In this case, the session is stopped (step 4). The warning is accurate. LOW.

But if the exception occurs during `cli(["exec", "-s", name, "-f", str(RUN_PY), "--timeout", str(EXEC_TIMEOUT)])` (e.g., OSError), then:
1. OSError occurs
2. Not caught by inner `except CliError`
3. Propagates through t0.batch
4. `cli(["exec", "-s", name], stdin=LIST_CODE)` doesn't run
5. `fetch(name)` doesn't run
6. `cli(["stop", "-s", name"])` doesn't run
7. Session left running!

This is the HIGH defect. The OSError from the exec command leaves the session running
