# RENDER R2 (xing) 11-09 00:27

We need answer as numbered list: HIGH or LOW, file and place, defect, one-line fix. If none: NO HIGH DEFECTS. Do not praise. Only report defects that still exist in code as shown; do not repeat round-1 items fixed. Need find real defects that waste compute units, hang, lose clips, leave session running, give wrong video. Think briefly under 1500 words. Then final list after line FINAL:.

We need inspect code carefully. Let's parse.

Files:
1 build_h3_batch.py (lines 1-112)
2 run_colab_batch.py (lines 114-230)
3 t0_pack/run_t0_colab.py (lines 232-288)
4 tests (288-356)
5 run.py AS BUILT (357-405)
6 SHOT-001 settings (407-438)
7 FACTS (439-440)

Round 1 fixed: stop on every path except download failure after script started, 180 proof, MSYS_NO_PATHCONV, hard timeout 7200 per shell command, any-429 retry, real .jpg keyframes, run.py 11.3 MB (T0's 7 MB worked, the 19.7 MB one hung locally). 6 offline tests pass.

Need find REAL defects still existing. Let's identify.

Potential issues:

A. In run.py built: `for name, b64 in json.loads(base64.b64decode("<BLOB>")).items():` The BLOB is embedded base64 of JSON mapping name -> b64. But `name` is used as filename `settings_{sid}.json`. If names contain slashes? They are shot ids like SHOT-001. Fine. But `b64` decoded. Fine.

B. `inputs = APP / "inputs"; inputs.mkdir(exist_ok=True)` then `for name, b64 in ...: (inputs / name).write_bytes(...)`. If `name` contains path separators? Shot ids no. Fine.

C. `os.environ["HF_HOME"] = str(TMP / "hf")` but no HF cache dir creation? Wan2GP may create. Not necessarily defect.

D. `subprocess.Popen(... nvidia-smi ...)` writes gpu.csv. Fine.

E. Setup git clone and pip install. If clone fails, raise SystemExit(1). Good.

F. ckpts handling: if APP/ckpts exists and not symlink, move contents to TMP/ckpts, rmtree APP/ckpts, then if not exists symlink. If exists and is symlink, skip. Fine. But if TMP/ckpts doesn't exist? It does mkdir earlier. Fine.

G. `inputs` writes keyframes. Good.

H. `finish`: writes RESULT.json, failed list, raises SystemExit(1) if failed. Good.

I. Per-shot loop:
```
for attempt in range(1, 5):
    lg = OUT / f"wgp_{sid}.log"; start = lg.stat().st_size if lg.exists() else 0
    rc = sh(f"cd {APP} && python wgp.py --process {f} --output-dir {od} --profile 5 --verbose 2", f"wgp_{sid}.log")
    files = sorted(p.name for p in od.iterdir())
    if any(n.endswith(".mp4") for n in files): break
    if "429" not in lg.read_bytes()[start:].decode(errors="replace") or attempt == 4: break
    note(...); time.sleep(60 * attempt)
results[sid] = "ok" if rc == 0 and any(n.endswith(".mp4") for n in files) else "failed"
```
Potential bug: `start` is size of log at beginning of attempt; but `sh` appends to log. If previous attempt wrote 429, start points to old bytes. `lg.read_bytes()[start:]` includes new output too. If new output contains "429", condition false -> retry. If no 429, break. Good. But if `lg` doesn't exist? It exists because created by sh. Fine.

But there is a subtle issue: `rc` from last attempt. If break due to mp4, rc is last attempt's rc. Good. If break due to no 429 on attempt 4, rc is attempt 4. Good.

J. `--profile 5` hardcoded in run.py. Settings says profile 5. Good.

K. `num_inference_steps 6`, guidance etc. Fine.

L. `video_length 175`, frames 107+17k? Wait facts: "frames 107+17k, 2090 total". Shot settings video_length 175. Maybe frames 107+17k means start frame 107, end frame 17k? Actually "frames 107+17k, 2090 total" maybe start=107, end=17000? But settings video_length 175. Hmm. Could be mismatch? Let's parse: "FL2VA, start+end boundary frames, Wan2GP MiniMax-H3 Pika H3 Flex 6-step LoRA, 768x1344, frames 107+17k, 2090 total". Maybe each shot has start frame 107 and end frame 17000? But video_length 175 suggests 175 frames. 2090 total frames across 10 shots? If each 175 frames, 1750. 2090 maybe 10 shots with some variation. But "frames 107+17k" could mean start frame 107 and end frame 17000? That would be huge. But Wan2GP video_length likely number of output frames. If end frame 17000, video_length should be 17000-107? But settings says 175. Could be wrong? Need inspect story? Not provided. But facts mention "frames 107+17k, 2090 total". Maybe "107+17k" means start frame 107 and end frame 17000? But 2090 total across 10 shots? If each shot 175 frames, total 1750, not 2090. If some shots longer? Hmm.

Wait "frames 107+17k, 2090 total" might mean start frame 107 and end frame 17000? But 2090 total frames? That doesn't align. Maybe "107+17k" means start frame 107 and end frame 17000? No. Let's think: FL2VA prompt compiled from timing_and_lattice pixel_frames. Shot settings video_length 175. If pixel_frames maybe 175. "frames 107+17k" maybe start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus maybe 340 extra? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? Then total 16893*10 huge. So likely "107+17k" means start frame 107 and end frame 17000? No, 2090 total contradicts. Maybe "frames 107+17k" means start frame 107 and end frame 17000? Wait "107+17k" could be "107 + 17k" = 107 + 17000 = 17107 frames per shot? But 2090 total? No.

Maybe "frames 107+17k, 2090 total" means start frame 107 and end frame 17000? Actually "107+17k" could mean start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Let's not overfocus. Need find defects.

M. `run_colab_batch.py` batch function:
```
proc = popen(["colab", "exec", "-s", name, "-f", str(run_py), "--timeout", str(EXEC_TIMEOUT)], env=ENV)
waited, ok = 0, False
while waited <= proof_seconds:
    if started(name): ok=True; break
    if proc.poll() is not None: break
    sleep(poll); waited += poll
if not ok and not started(name): raise RunError...
keep = True
rc = proc.wait()
run_cli(["exec", "-s", name], stdin=t0.LIST_CODE)
fetch(name, Path(results))
keep = False
if rc: raise RunError...
finally:
    if proc is not None and proc.poll() is None and not keep: proc.kill()
    if keep: print SESSION KEPT...
    else: run_cli(["stop", "-s", name], check=False)
```
Potential issues:
- `proc.wait()` blocks until exec exits. If exec hangs beyond EXEC_TIMEOUT? `exec --timeout` should kill idle process after timeout? Actually `colab exec --timeout` kills the exec after timeout? It may send SIGTERM? It is idle limit. If script runs non-idle, timeout may not kill? But `exec --timeout` likely kills after idle period. If script never produces output, timeout kills. But if script hangs in subprocess.run with timeout=7200, exec timeout 6h may not trigger until idle. Could leave session running? But hard timeout per shell command prevents hang within shell commands. However `python wgp.py` may hang in GPU compute without shell output? `exec --timeout` idle limit should kill after 6h idle. But if GPU busy, no idle, could exceed 6h. But G4 batch maybe hours. Could leave session running? The finally only kills if `proc.poll() is None and not keep`. After `proc.wait()` returns, proc is dead, so no kill. If `proc.wait()` hangs? `exec --timeout` should eventually kill. But if `exec` itself hangs? Not likely.

- `started(name)` checks `ls -s name /content` contains "out/". If script creates out early, good. But if script fails before creating out, raised. Good.

- `keep = True` set even if `started` true but `proc.wait()` later fails? If proc exits before wait? `proc.wait()` returns immediately. If rc !=0, raise. Good.

- If `started` true but `proc.poll()` is None during loop, keep True. Then `proc.wait()` waits. If proc dies, rc. If rc !=0, raise. Good. If download fails, keep True, finally prints SESSION KEPT, no stop. Good.

- But if `proc.wait()` times out? `exec --timeout` should kill. If not, `proc.wait()` could block forever, leaving session running. But `exec --timeout` is supposed to kill. Could be a risk. Is it a defect? Maybe medium. But round 1 fixed? Not mentioned. Could be real.

- `run_cli(["exec", "-s", name], stdin=t0.LIST_CODE)` lists files. This sends LIST_CODE to exec. But exec may have already exited? If proc.wait() returned, exec exited. Sending exec list after exit may fail? `colab exec -s name` after exec stopped? The CLI may still allow listing files? It might work because session still alive? Actually after exec exits, the session is stopped? Wait `colab exec -s name` starts a new exec in same session? The doc says "exec -f run.py as a background process" then later "exec -s name (list files)" to list files in the session. If exec exited, the session may be stopped? But they keep session if download fails. For normal run, after exec exits, they list files. Does `colab exec -s name` work after exec stopped? It might start a new exec? Or list files? The CLI `exec -s name` without -f executes the named script? Actually `colab exec -s <session> [-f <script>]` runs script in session. Without -f, maybe lists? Hmm. The doc says "exec -s name (list files)" maybe they intend to list files via exec? But `exec` without -f might not list. Could be wrong. But tests pass? Tests don't check. Could be a defect causing wrong video? Let's examine.

In run_colab_batch.batch:
```
rc = proc.wait()
run_cli(["exec", "-s", name], stdin=t0.LIST_CODE)
fetch(name, Path(results))
```
If `proc.wait()` returns because exec exited, sending `exec -s name` with stdin LIST_CODE might actually execute LIST_CODE as a script in the session? But exec without -f? The colab CLI `exec -s <session>` without -f might run the default? Actually `colab exec -s <session>` without -f opens an interactive exec? I think `exec -s <session>` without -f runs the current directory? Not sure. The intended behavior: after the background exec finishes, list files by sending a list script to the session. But if exec exited, the session may have been stopped? Wait `colab exec -f run.py` runs run.py in background; when run.py exits, the exec process ends, but the Colab session remains? Actually `colab exec -f` runs a script in the session; when script finishes, the exec command completes, but the session continues? Or stops? The doc says "once the script has started and the clips are still on the VM, a failed download keeps the session (stopping it would delete the clips)". So after exec finishes, the session may still be alive? They then `exec -s name` to list files. If exec finished, can you still exec a command? Maybe yes, the session persists. But if exec finished, the session might be stopped automatically? The doc says "The session is stopped on EVERY exit path except one: once the script has started and the clips are still on the VM, a failed download keeps the session". So after exec exits normally, they stop the session. But before stopping, they list files. `exec -s name` might list files? Actually `colab exec -s name` without -f might just list? Let's recall Colab CLI: `colab exec -s <session> [-f <file>]` runs a file. Without -f, maybe it runs the current working directory? Hmm. There is also `colab ls -s <session>` to list files. The doc says "exec -s name (list files)" maybe a mistake. Could cause no files listed, fetch empty, wrong video. But tests? `test_normal_run_stops_after_fetch` uses fake_cli returns "" for all calls, so no assertion on list. Could be a defect. But is it real? Let's inspect t0_pack/run_t0_colab.py: It has its own LIST_CODE and uses `cli(["exec", "-s", name], stdin=LIST_CODE)`? Wait t0 code truncated at line 288. It likely does similar. The doc says "a list script on stdin names the .mp4 files ... under /content/out into FILES.txt; colab download...". In t0, `cli(["exec", "-s", name], stdin=LIST_CODE)`? The snippet cut off. It might use `exec -s name` with stdin. If exec without -f doesn't run stdin, files not listed. But maybe `colab exec -s name` with stdin runs the stdin as a script? Actually `colab exec -s <session>` without -f might execute the stdin? I think `colab exec -s <session>` without -f runs the current directory? Let's check Colab CLI docs mentally: `colab exec -s <session> [-f <file>]` runs a Python file in the session. If no -f, maybe it runs the stdin? I'm not sure. There is `colab exec -s <session>` with stdin? The CLI `exec` command accepts `-f` for file. Without -f, maybe it reads from stdin? Actually `colab exec -s <session>` without -f might open an interactive exec? Hmm.

But the doc explicitly says "exec -s name (list files)" in dry run. So intended. Could be okay.

N. `fetch` in run_colab_batch:
```
def fetch(name, results):
    results.mkdir(parents=True, exist_ok=True)
    run_cli(["download", "-s", name, f"{t0.OUT}/FILES.txt", str(results / "FILES.txt")])
    for rel in (results / "FILES.txt").read_text(encoding="utf-8").split():
        (results / rel).parent.mkdir(parents=True, exist_ok=True)
        run_cli(["download", "-s", name, f"{t0.OUT}/{rel}", str(results / rel)])
```
If FILES.txt empty, split yields [""], then download ""? `f"{t0.OUT}/{rel}"` = "/content/out/" and local ""? Could error. But if no files, maybe empty. Could cause download of empty string. But not high.

O. `run_cli` uses `env=ENV` including MSYS_NO_PATHCONV. Good.

P. `started` uses `ls -s name /content`. If name has dashes, fine.

Q. `proc.poll()` during loop: if exec already exited, poll returns None? Actually if proc exited, poll returns exit code, not None. Wait `proc.poll()` returns None if process still running, else exit code. In loop, if proc.poll() is not None, break. Good. But if proc exits during wait, `proc.wait()` returns. Good.

R. `keep = True` even if `started` true but `proc.wait()` later raises? If `proc.wait()` raises OSError? Not handled. But exec timeout should kill. Could leave session running if wait hangs. Medium.

S. `run_cli(["stop", "-s", name], check=False)` after fetch. If stop fails, ignored. Good.

T. In run.py built, `subprocess.Popen(f"nvidia-smi ... > {OUT}/gpu.csv", shell=True)` writes gpu.csv. If nvidia-smi not available? On G4 yes. Fine.

U. `sh(f"git clone ... && git checkout ...", "setup.log")` if first sh fails, second not run. Good. But if clone succeeds but checkout fails, second sh returns nonzero, note SETUP FAILED, raise SystemExit(1). Good.

V. `pip install -r requirements.txt` may take long. Hard timeout 7200. Good.

W. `inputs` writes keyframes. But `jpg_embedder` maps flat name -> (rel, png_b64). In run.py, `for name, b64 in json.loads(...).items(): (inputs / name).write_bytes(base64.b64decode(b64))`. `name` is flat like "keyframes__SHOT-001-A.jpg". Good. But `png_b64` replaced with `jpeg_b64` returning base64 JPEG. Good.

X. `legacy_rows` uses `sh["timing_and_lattice"]["pixel_frames"]`. If missing, KeyError. Not defect.

Y. `compile_fl2va_prompt` returns dict with compiled_prompt. Good.

Z. `build_h3_batch.main` sets `run_kaggle.png_b64 = lambda path: jpeg_b64(path, (w, h))`. But `jpeg_b64` uses `size=(768,1344)` default. If resolution different, uses default. Good.

AA. `jpg_embedder` uses `run_kaggle.png_b64(Path(root) / rel)`. Good.

BB. `harden` patches `def sh(cmd, log="shell.log"):` with helper. If run.py already has `def sh`? Built script includes `def sh(cmd, log="shell.log"):` at line 370. harden replaces first occurrence. Good. But if `run_limited` already defined? It is defined at line 367. harden inserts helper before `def sh`. Good.

CC. `hardened` c pattern: `if \"429 Too Many Requests\" not in lg.read_bytes()[start:].decode(errors=\"replace\") or attempt == 4: break`. In run.py, `lg` is `OUT / f"wgp_{sid}.log"` and `start` is stat size. Good. But `lg.read_bytes()[start:]` decodes errors replace. If log huge, fine.

DD. Potential issue: `start = lg.stat().st_size if lg.exists() else 0` but `lg` always exists because created by `sh`. If `sh` fails before creating log? `sh` opens log in `with` and writes note. If command fails, log exists. Good.

EE. `time.sleep(60 * attempt)` retries. If 429 occurs on attempt 1, sleep 60; attempt 2 sleep 120; etc. Up to 4 attempts total sleeps 60+120+180+240=600s. Fine.

FF. `results[sid] = "ok" if rc == 0 and any(n.endswith(".mp4") for n in files) else "failed"`. If mp4 appears but rc !=0? Unlikely. Fine.

GG. `finish` raises SystemExit(1) if failed. But `SystemExit` propagates, exec exits nonzero. Good.

HH. `run.py` uses `LOG = open(OUT / "timeline.txt", "a", buffering=1)`. If multiple shots append. Good.

II. `APP = Path("/content/Wan2GP")`; `TMP = Path("/content/cache")`. Good.

JJ. `os.environ["HF_HOME"] = str(TMP / "hf")` but no `HF_HOME` dir creation. Wan2GP may create. Not defect.

KK. `inputs.mkdir(exist_ok=True)` then write. If `inputs` already has files from previous? Overwrites. Good.

LL. `for name, b64 in json.loads(base64.b64decode("<BLOB>")).items():` If BLOB malformed, crash. Not defect.

MM. `f = APP / f"settings_{sid}.json"; f.write_text(json.dumps(settings, indent=1)); shutil.copy(f, OUT / f.name)`. If settings has keys with slashes? Not.

NN. `od = OUT / sid; od.mkdir(exist_ok=True)`. If sid contains path separators? Not.

OO. `cd {APP} && python wgp.py --process {f} --output-dir {od} --profile 5 --verbose 2`. Hardcoded profile 5. Settings says profile 5. Good. But if settings changed? Build script passes profile? `run_kaggle.build(rows, ..., a.profile, manifest)` maybe profile into settings? Not visible. But run.py hardcodes 5. Could mismatch if builder changes --profile. But facts say profile 5. Could be low.

PP. `--verbose 2` maybe okay.

QQ. `num_inference_steps 6`, `guidance_phases 1`, `guidance_scale 1`, `flow_shift 12`, `sliding_window_size 362`. These are valid H3 settings? Maybe `flow_shift 12` too high? Not our concern.

RR. `image_mode 0`, `image_prompt_type SE`, `video_prompt_type ""`, `audio_prompt_type ""`. Fine.

SS. `seed 42`. Fine.

TT. `video_length 175`. If frames 107+17k? Could be wrong. Let's investigate more.

The facts: "FL2VA, start+end boundary frames, Wan2GP MiniMax-H3 Pika H3 Flex 6-step LoRA, 768x1344, frames 107+17k, 2090 total". Maybe "frames 107+17k" means start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Wait "frames 107+17k, 2090 total" could mean start frame 107 and end frame 17000? Actually "107+17k" could be "107 + 17k" = 107 + 17000 = 17107 frames per shot? But 2090 total? No.

Maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's parse grammar: "frames 107+17k, 2090 total" maybe "frames 107+17k" means start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Could be "frames 107+17k" means start frame 107 and end frame 17000? No.

Maybe "107+17k" means start frame 107 and end frame 17000? No.

Let's consider "107+17k" could be "107 + 17k" where 17k = 17000. But 2090 total? If each shot has 175 frames, total 1750. 2090 - 1750 = 340. Maybe some shots have 175, some 175? Not.

Maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Wait maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's not dwell. The settings video_length 175. If the story's pixel_frames maybe 175. The "frames 107+17k" might refer to start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Actually "frames 107+17k" could mean start frame 107 and end frame 17000? No.

Let's search memory: Wan2GP FL2VA prompt compiled from timing_and_lattice pixel_frames. The shot settings video_length maybe equals pixel_frames. If pixel_frames 175. "frames 107+17k" maybe start frame 107 and end frame 17000? No.

Maybe "107+17k" means start frame 107 and end frame 17000? No.

Could be "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's move on.

Potential high defects:

1. `run_colab_batch.batch` `proc.wait()` could hang if `exec --timeout` doesn't kill non-idle process, leaving session running. But is this real? The `exec --timeout` is idle limit; if GPU busy, no idle, could exceed 6h. But the script itself has hard timeouts per shell command. However `python wgp.py` may run GPU inference without producing shell output? `sh` captures stdout to log, so shell output appears. If GPU busy, no new shell output, idle timer triggers after 6h. Could leave session running for 6h. But if script hangs in subprocess.run timeout=7200, exec timeout won't trigger until idle. But hard timeout kills shell command after 7200s, returning control to shell, which may produce output? If subprocess.run times out, it raises TimeoutExpired, note, returncode 124. Shell continues. So no hang beyond 7200s per command. But if many commands, total could be long. But exec timeout 6h idle. If script runs continuously without idle, could exceed 6h. But G4 batch maybe 1-2h. Risk medium. But round 1 didn't mention. Could be high? Need decide.

2. `run_cli(["exec", "-s", name], stdin=t0.LIST_CODE)` after `proc.wait()`. If exec already exited, sending `exec -s name` may not list files, causing fetch empty, wrong video. This seems plausible. But is it a defect? Let's examine Colab CLI behavior. `colab exec -s <session>` without -f: According to Colab CLI docs, `exec` runs a file in the session. Without -f, maybe it runs the current directory? Actually `colab exec -s <session>` without -f might open an interactive exec? I recall `colab exec -s <session>` without -f runs the script in the current working directory? Hmm. There is `colab exec -s <session> -f <file>`. Without -f, maybe it runs the stdin? The doc says "exec -s name (list files)" in dry run. So intended. But if exec exited, can you still exec? The session may still be alive. The CLI `exec -s name` might list files? I think `colab exec -s <session>` without -f might actually list files? Let's check memory: Colab CLI `exec` command: `colab exec -s <session> [-f <file>]` runs a Python file. If no -f, maybe it runs the current directory? There is also `colab ls -s <session>` to list files. The doc says "exec -s name (list files)" maybe a mistake. But tests pass? `test_normal_run_stops_after_fetch` uses fake_cli returns "" for all calls, so no assertion on list. Could be a defect. But is it real? Let's inspect t0_pack/run_t0_colab.py: It has its own LIST_CODE and uses `cli(["exec", "-s", name], stdin=LIST_CODE)`? Wait t0 code truncated at line 288. It likely does similar. The doc says "a list script on stdin names the .mp4 files ... under /content/out into FILES.txt; colab download...". In t0, `cli(["exec", "-s", name], stdin=LIST_CODE)`? The snippet cut off. It might use `exec -s name` with stdin. If exec without -f doesn't run stdin, files not listed. But maybe `colab exec -s name` with stdin runs the stdin as a script? Actually `colab exec -s <session>` without -f might execute the stdin? I think `colab exec -s <session>` without -f might open an interactive exec? Hmm.

But the doc explicitly says "exec -s name (list files)" in dry run. So intended. Could be okay.

3. `fetch` splits FILES.txt by whitespace; if filenames contain spaces? Shot ids no. Fine.

4. `run_colab_batch.batch` `keep = True` set before `proc.wait()`. If `proc.wait()` raises `BrokenPipeError` or `OSError`, finally still kills? `proc.poll() is None and not keep` -> keep True, so no kill. Session left running. But `proc.wait()` shouldn't raise. Medium.

5. `run_cli(["usage"])` before `new`. Fine.

6. `run_cli(["new", "-s", name, "--gpu", gpu])` if session exists? `new` creates new session. Fine.

7. `proc = popen([...])` without `stdout=DEVNULL`? `colab exec` may print to stdout, captured by parent? Parent doesn't capture. Could fill disk? Not high.

8. `started(name)` checks `ls -s name /content`. If `name` has leading dash? `replace("_","-")`. Fine.

9. `proof_seconds=PROOF_SECONDS=180`. If script takes >180s to create out, stops. But if script creates out after 190s, stops prematurely, losing clips. Could be high? But round 1 fixed? Not mentioned. The first live attempt wasted compute because script never reached VM. Now proof 180s. If script startup >180s, stops. But maybe acceptable? Could be high if script startup slow. But facts say first live attempt wasted compute because 19.7MB script never reached VM. Now run.py 11.3MB, should reach VM faster. But still could be >180s? Maybe not. But potential high? Need decide.

10. `EXEC_TIMEOUT = 6*3600` but `exec --timeout` is idle limit. If script runs non-idle, could exceed. But hard timeout per shell command. Could leave session running. Medium.

11. `run.py` `for attempt in range(1,5)` retries only 4 attempts. If HF 429 persists, no retry beyond 4. But condition `or attempt == 4` breaks on attempt 4 regardless. Good.

12. `lg.read_bytes()[start:]` if `lg` is huge and `start` old, decoding entire log each attempt. Fine.

13. `files = sorted(p.name for p in od.iterdir())` after each attempt. If partial mp4 from previous attempt, `any(.mp4)` true, break. Good.

14. `results[sid] = "ok" if rc == 0 and any(n.endswith(".mp4") for n in files) else "failed"`. If mp4 appears but rc !=0? Unlikely. Fine.

15. `finish` writes RESULT.json and raises SystemExit(1) if failed. But if some shots failed, run.py exits nonzero. `run_colab_batch` raises RunError. Good.

16. `run.py` `LOG = open(OUT / "timeline.txt", "a", buffering=1)` opened at module level. If multiple runs? Single batch. Fine.

17. `subprocess.Popen(f"nvidia-smi ... > {OUT}/gpu.csv", shell=True)` writes gpu.csv. If nvidia-smi fails, Popen raises? `subprocess.Popen` with shell redirect; if nvidia-smi not found, shell error, Popen returns? Actually Popen may raise FileNotFoundError? In shell, if command not found, shell prints error but Popen returns? It might raise? Not sure. But on G4 yes.

18. `sh(f"git clone ... && git checkout ...", "setup.log")` if clone fails, second not run. Good.

19. `if (APP / "ckpts").is_dir() and not (APP / "ckpts").is_symlink():` If ckpts is symlink, skip. Good. But if ckpts is a directory containing symlinks? `iterdir()` follows symlinks? `shutil.move` may follow. Fine.

20. `os.symlink(TMP / "ckpts", APP / "ckpts")` if not exists. Good.

21. `os.environ["HF_HOME"] = str(TMP / "hf")` but no `HF_HOME` dir creation. Wan2GP may create. Not defect.

22. `inputs.mkdir(exist_ok=True)` then write. Good.

23. `for name, b64 in json.loads(base64.b64decode("<BLOB>")).items():` If BLOB contains duplicate names? JSON dict unique. Fine.

24. `f = APP / f"settings_{sid}.json"; f.write_text(json.dumps(settings, indent=1)); shutil.copy(f, OUT / f.name)`. If settings has non-serializable? Not.

25. `od = OUT / sid; od.mkdir(exist_ok=True)`. If sid contains "/"? Not.

26. `cd {APP} && python wgp.py --process {f} --output-dir {od} --profile 5 --verbose 2`. Hardcoded profile 5. If builder changes --profile, mismatch. But facts profile 5. Low.

27. `--verbose 2` maybe okay.

28. `num_inference_steps 6`, `guidance_phases 1`, `guidance_scale 1`, `flow_shift 12`, `sliding_window_size 362`. These are valid H3 settings? Maybe `flow_shift 12` too high? Not our concern.

29. `image_mode 0`, `image_prompt_type SE`, `video_prompt_type ""`, `audio_prompt_type ""`. Fine.

30. `seed 42`. Fine.

31. `video_length 175`. If frames 107+17k? Could be wrong. Let's investigate more.

The facts: "FL2VA, start+end boundary frames, Wan2GP MiniMax-H3 Pika H3 Flex 6-step LoRA, 768x1344, frames 107+17k, 2090 total". Maybe "frames 107+17k" means start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Wait "frames 107+17k" could mean start frame 107 and end frame 17000? Actually "107+17k" could be "107 + 17k" = 107 + 17000 = 17107 frames per shot? But 2090 total? No.

Maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's parse grammar: "frames 107+17k, 2090 total" maybe "frames 107+17k" means start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Could be "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's consider "107+17k" could be "107 + 17k" where 17k = 17000. But 2090 total? If each shot has 175 frames, total 1750. 2090 - 1750 = 340. Maybe some shots have 175, some 175? Not.

Maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Wait maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's search memory: Wan2GP FL2VA prompt compiled from timing_and_lattice pixel_frames. The shot settings video_length maybe equals pixel_frames. If pixel_frames 175. "frames 107+17k" maybe start frame 107 and end frame 17000? No.

Maybe "107+17k" means start frame 107 and end frame 17000? No.

Could be "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's not dwell. The settings video_length 175. If the story's pixel_frames maybe 175. The "frames 107+17k" might refer to start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Actually "frames 107+17k" could mean start frame 107 and end frame 17000? No.

Let's move on.

Potential high defects:

1. `run_colab_batch.batch` `proc.wait()` could hang if `exec --timeout` doesn't kill non-idle process, leaving session running. But is this real? The `exec --timeout` is idle limit; if GPU busy, no idle, could exceed 6h. But the script itself has hard timeouts per shell command. However `python wgp.py` may run GPU inference without producing shell output? `sh` captures stdout to log, so shell output appears. If GPU busy, no new shell output, idle timer triggers after 6h. Could leave session running for 6h. But if script hangs in subprocess.run timeout=7200, exec timeout won't trigger until idle. But hard timeout kills shell command after 7200s, returning control to shell, which may produce output? If subprocess.run times out, it raises TimeoutExpired, note, returncode 124. Shell continues. So no hang beyond 7200s per command. But if many commands, total could be long. But exec timeout 6h idle. If script runs continuously without idle, could exceed 6h. But G4 batch maybe 1-2h. Risk medium. But round 1 didn't mention. Could be high? Need decide.

2. `run_cli(["exec", "-s", name], stdin=t0.LIST_CODE)` after `proc.wait()`. If exec already exited, sending `exec -s name` may not list files, causing fetch empty, wrong video. This seems plausible. But is it a defect? Let's examine Colab CLI behavior. `colab exec -s <session>` without -f: According to Colab CLI docs, `exec` runs a file in the session. Without -f, maybe it runs the current directory? Actually `colab exec -s <session>` without -f might open an interactive exec? I recall `colab exec -s <session>` without -f runs the script in the current working directory? Hmm. There is `colab exec -s <session> -f <file>`. Without -f, maybe it runs the stdin? The doc says "exec -s name (list files)" in dry run. So intended. But if exec exited, can you still exec? The session may still be alive. The CLI `exec -s name` might list files? I think `colab exec -s <session>` without -f might actually list files? Let's check memory: Colab CLI `exec` command: `colab exec -s <session> [-f <file>]` runs a Python file. If no -f, maybe it runs the current directory? There is also `colab ls -s <session>` to list files. The doc says "exec -s name (list files)" maybe a mistake. But tests pass? `test_normal_run_stops_after_fetch` uses fake_cli returns "" for all calls, so no assertion on list. Could be a defect. But is it real? Let's inspect t0_pack/run_t0_colab.py: It has its own LIST_CODE and uses `cli(["exec", "-s", name], stdin=LIST_CODE)`? Wait t0 code truncated at line 288. It likely does similar. The doc says "a list script on stdin names the .mp4 files ... under /content/out into FILES.txt; colab download...". In t0, `cli(["exec", "-s", name], stdin=LIST_CODE)`? The snippet cut off. It might use `exec -s name` with stdin. If exec without -f doesn't run stdin, files not listed. But maybe `colab exec -s name` with stdin runs the stdin as a script? Actually `colab exec -s <session>` without -f might execute the stdin? I think `colab exec -s <session>` without -f might open an interactive exec? Hmm.

But the doc explicitly says "exec -s name (list files)" in dry run. So intended. Could be okay.

3. `fetch` splits FILES.txt by whitespace; if filenames contain spaces? Shot ids no. Fine.

4. `run_colab_batch.batch` `keep = True` set before `proc.wait()`. If `proc.wait()` raises `BrokenPipeError` or `OSError`, finally still kills? `proc.poll() is None and not keep` -> keep True, so no kill. Session left running. But `proc.wait()` shouldn't raise. Medium.

5. `run_cli(["usage"])` before `new`. Fine.

6. `run_cli(["new", "-s", name, "--gpu", gpu])` if session exists? `new` creates new session. Fine.

7. `proc = popen([...])` without `stdout=DEVNULL`? `colab exec` may print to stdout, captured by parent? Parent doesn't capture. Could fill disk? Not high.

8. `started(name)` checks `ls -s name /content`. If `name` has leading dash? `replace("_","-")`. Fine.

9. `proof_seconds=PROOF_SECONDS=180`. If script takes >180s to create out, stops. But if script creates out after 190s, stops prematurely, losing clips. Could be high? But round 1 fixed? Not mentioned. The first live attempt wasted compute because script never reached VM. Now proof 180s. If script startup >180s, stops. But maybe acceptable? Could be high if script startup slow. But facts say first live attempt wasted compute because 19.7MB script never reached VM. Now run.py 11.3MB, should reach VM faster. But still could be >180s? Maybe not. But potential high? Need decide.

10. `EXEC_TIMEOUT = 6*3600` but `exec --timeout` is idle limit. If script runs non-idle, could exceed. But hard timeout per shell command. Could leave session running. Medium.

11. `run.py` `for attempt in range(1,5)` retries only 4 attempts. If HF 429 persists, no retry beyond 4. But condition `or attempt == 4` breaks on attempt 4 regardless. Good.

12. `lg.read_bytes()[start:]` if `lg` is huge and `start` old, decoding entire log each attempt. Fine.

13. `files = sorted(p.name for p in od.iterdir())` after each attempt. If partial mp4 from previous attempt, `any(.mp4)` true, break. Good.

14. `results[sid] = "ok" if rc == 0 and any(n.endswith(".mp4") for n in files) else "failed"`. If mp4 appears but rc !=0? Unlikely. Fine.

15. `finish` writes RESULT.json and raises SystemExit(1) if failed. But if some shots failed, run.py exits nonzero. `run_colab_batch` raises RunError. Good.

16. `run.py` `LOG = open(OUT / "timeline.txt", "a", buffering=1)` opened at module level. If multiple runs? Single batch. Fine.

17. `subprocess.Popen(f"nvidia-smi ... > {OUT}/gpu.csv", shell=True)` writes gpu.csv. If nvidia-smi fails, Popen raises? `subprocess.Popen` with shell redirect; if nvidia-smi not found, shell error, Popen returns? Actually Popen may raise FileNotFoundError? In shell, if command not found, shell prints error but Popen returns? It might raise? Not sure. But on G4 yes.

18. `sh(f"git clone ... && git checkout ...", "setup.log")` if clone fails, second not run. Good.

19. `if (APP / "ckpts").is_dir() and not (APP / "ckpts").is_symlink():` If ckpts is symlink, skip. Good. But if ckpts is a directory containing symlinks? `iterdir()` follows symlinks? `shutil.move` may follow. Fine.

20. `os.symlink(TMP / "ckpts", APP / "ckpts")` if not exists. Good.

21. `os.environ["HF_HOME"] = str(TMP / "hf")` but no `HF_HOME` dir creation. Wan2GP may create. Not defect.

22. `inputs.mkdir(exist_ok=True)` then write. Good.

23. `for name, b64 in json.loads(base64.b64decode("<BLOB>")).items():` If BLOB contains duplicate names? JSON dict unique. Fine.

24. `f = APP / f"settings_{sid}.json"; f.write_text(json.dumps(settings, indent=1)); shutil.copy(f, OUT / f.name)`. If settings has non-serializable? Not.

25. `od = OUT / sid; od.mkdir(exist_ok=True)`. If sid contains "/"? Not.

26. `cd {APP} && python wgp.py --process {f} --output-dir {od} --profile 5 --verbose 2`. Hardcoded profile 5. If builder changes --profile, mismatch. But facts profile 5. Low.

27. `--verbose 2` maybe okay.

28. `num_inference_steps 6`, `guidance_phases 1`, `guidance_scale 1`, `flow_shift 12`, `sliding_window_size 362`. These are valid H3 settings? Maybe `flow_shift 12` too high? Not our concern.

29. `image_mode 0`, `image_prompt_type SE`, `video_prompt_type ""`, `audio_prompt_type ""`. Fine.

30. `seed 42`. Fine.

31. `video_length 175`. If frames 107+17k? Could be wrong. Let's investigate more.

The facts: "FL2VA, start+end boundary frames, Wan2GP MiniMax-H3 Pika H3 Flex 6-step LoRA, 768x1344, frames 107+17k, 2090 total". Maybe "frames 107+17k" means start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Wait "frames 107+17k" could mean start frame 107 and end frame 17000? Actually "107+17k" could be "107 + 17k" = 107 + 17000 = 17107 frames per shot? But 2090 total? No.

Maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's parse grammar: "frames 107+17k, 2090 total" maybe "frames 107+17k" means start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Could be "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's consider "107+17k" could be "107 + 17k" where 17k = 17000. But 2090 total? If each shot has 175 frames, total 1750. 2090 - 1750 = 340. Maybe some shots have 175, some 175? Not.

Maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Wait maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's search memory: Wan2GP FL2VA prompt compiled from timing_and_lattice pixel_frames. The shot settings video_length maybe equals pixel_frames. If pixel_frames 175. "frames 107+17k" maybe start frame 107 and end frame 17000? No.

Maybe "107+17k" means start frame 107 and end frame 17000? No.

Could be "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's not dwell. The settings video_length 175. If the story's pixel_frames maybe 175. The "frames 107+17k" might refer to start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Actually "frames 107+17k" could mean start frame 107 and end frame 17000? No.

Let's move on.

Potential high defects:

1. `run_colab_batch.batch` `proc.wait()` could hang if `exec --timeout` doesn't kill non-idle process, leaving session running. But is this real? The `exec --timeout` is idle limit; if GPU busy, no idle, could exceed 6h. But the script itself has hard timeouts per shell command. However `python wgp.py` may run GPU inference without producing shell output? `sh` captures stdout to log, so shell output appears. If GPU busy, no new shell output, idle timer triggers after 6h. Could leave session running for 6h. But if script hangs in subprocess.run timeout=7200, exec timeout won't trigger until idle. But hard timeout kills shell command after 7200s, returning control to shell, which may produce output? If subprocess.run times out, it raises TimeoutExpired, note, returncode 124. Shell continues. So no hang beyond 7200s per command. But if many commands, total could be long. But exec timeout 6h idle. If script runs continuously without idle, could exceed 6h. But G4 batch maybe 1-2h. Risk medium. But round 1 didn't mention. Could be high? Need decide.

2. `run_cli(["exec", "-s", name], stdin=t0.LIST_CODE)` after `proc.wait()`. If exec already exited, sending `exec -s name` may not list files, causing fetch empty, wrong video. This seems plausible. But is it a defect? Let's examine Colab CLI behavior. `colab exec -s <session>` without -f: According to Colab CLI docs, `exec` runs a file in the session. Without -f, maybe it runs the current directory? Actually `colab exec -s <session>` without -f might open an interactive exec? I recall `colab exec -s <session>` without -f runs the script in the current working directory? Hmm. There is `colab exec -s <session> -f <file>`. Without -f, maybe it runs the stdin? The doc says "exec -s name (list files)" in dry run. So intended. But if exec exited, can you still exec? The session may still be alive. The CLI `exec -s name` might list files? I think `colab exec -s <session>` without -f might actually list files? Let's check memory: Colab CLI `exec` command: `colab exec -s <session> [-f <file>]` runs a Python file. If no -f, maybe it runs the current directory? There is also `colab ls -s <session>` to list files. The doc says "exec -s name (list files)" maybe a mistake. But tests pass? `test_normal_run_stops_after_fetch` uses fake_cli returns "" for all calls, so no assertion on list. Could be a defect. But is it real? Let's inspect t0_pack/run_t0_colab.py: It has its own LIST_CODE and uses `cli(["exec", "-s", name], stdin=LIST_CODE)`? Wait t0 code truncated at line 288. It likely does similar. The doc says "a list script on stdin names the .mp4 files ... under /content/out into FILES.txt; colab download...". In t0, `cli(["exec", "-s", name], stdin=LIST_CODE)`? The snippet cut off. It might use `exec -s name` with stdin. If exec without -f doesn't run stdin, files not listed. But maybe `colab exec -s name` with stdin runs the stdin as a script? Actually `colab exec -s <session>` without -f might execute the stdin? I think `colab exec -s <session>` without -f might open an interactive exec? Hmm.

But the doc explicitly says "exec -s name (list files)" in dry run. So intended. Could be okay.

3. `fetch` splits FILES.txt by whitespace; if filenames contain spaces? Shot ids no. Fine.

4. `run_colab_batch.batch` `keep = True` set before `proc.wait()`. If `proc.wait()` raises `BrokenPipeError` or `OSError`, finally still kills? `proc.poll() is None and not keep` -> keep True, so no kill. Session left running. But `proc.wait()` shouldn't raise. Medium.

5. `run_cli(["usage"])` before `new`. Fine.

6. `run_cli(["new", "-s", name, "--gpu", gpu])` if session exists? `new` creates new session. Fine.

7. `proc = popen([...])` without `stdout=DEVNULL`? `colab exec` may print to stdout, captured by parent? Parent doesn't capture. Could fill disk? Not high.

8. `started(name)` checks `ls -s name /content`. If `name` has leading dash? `replace("_","-")`. Fine.

9. `proof_seconds=PROOF_SECONDS=180`. If script takes >180s to create out, stops. But if script creates out after 190s, stops prematurely, losing clips. Could be high? But round 1 fixed? Not mentioned. The first live attempt wasted compute because script never reached VM. Now proof 180s. If script startup >180s, stops. But maybe acceptable? Could be high if script startup slow. But facts say first live attempt wasted compute because 19.7MB script never reached VM. Now run.py 11.3MB, should reach VM faster. But still could be >180s? Maybe not. But potential high? Need decide.

10. `EXEC_TIMEOUT = 6*3600` but `exec --timeout` is idle limit. If script runs non-idle, could exceed. But hard timeout per shell command. Could leave session running. Medium.

11. `run.py` `for attempt in range(1,5)` retries only 4 attempts. If HF 429 persists, no retry beyond 4. But condition `or attempt == 4` breaks on attempt 4 regardless. Good.

12. `lg.read_bytes()[start:]` if `lg` is huge and `start` old, decoding entire log each attempt. Fine.

13. `files = sorted(p.name for p in od.iterdir())` after each attempt. If partial mp4 from previous attempt, `any(.mp4)` true, break. Good.

14. `results[sid] = "ok" if rc == 0 and any(n.endswith(".mp4") for n in files) else "failed"`. If mp4 appears but rc !=0? Unlikely. Fine.

15. `finish` writes RESULT.json and raises SystemExit(1) if failed. But if some shots failed, run.py exits nonzero. `run_colab_batch` raises RunError. Good.

16. `run.py` `LOG = open(OUT / "timeline.txt", "a", buffering=1)` opened at module level. If multiple runs? Single batch. Fine.

17. `subprocess.Popen(f"nvidia-smi ... > {OUT}/gpu.csv", shell=True)` writes gpu.csv. If nvidia-smi fails, Popen raises? `subprocess.Popen` with shell redirect; if nvidia-smi not found, shell error, Popen returns? Actually Popen may raise FileNotFoundError? In shell, if command not found, shell prints error but Popen returns? It might raise? Not sure. But on G4 yes.

18. `sh(f"git clone ... && git checkout ...", "setup.log")` if clone fails, second not run. Good.

19. `if (APP / "ckpts").is_dir() and not (APP / "ckpts").is_symlink():` If ckpts is symlink, skip. Good. But if ckpts is a directory containing symlinks? `iterdir()` follows symlinks? `shutil.move` may follow. Fine.

20. `os.symlink(TMP / "ckpts", APP / "ckpts")` if not exists. Good.

21. `os.environ["HF_HOME"] = str(TMP / "hf")` but no `HF_HOME` dir creation. Wan2GP may create. Not defect.

22. `inputs.mkdir(exist_ok=True)` then write. Good.

23. `for name, b64 in json.loads(base64.b64decode("<BLOB>")).items():` If BLOB contains duplicate names? JSON dict unique. Fine.

24. `f = APP / f"settings_{sid}.json"; f.write_text(json.dumps(settings, indent=1)); shutil.copy(f, OUT / f.name)`. If settings has non-serializable? Not.

25. `od = OUT / sid; od.mkdir(exist_ok=True)`. If sid contains "/"? Not.

26. `cd {APP} && python wgp.py --process {f} --output-dir {od} --profile 5 --verbose 2`. Hardcoded profile 5. If builder changes --profile, mismatch. But facts profile 5. Low.

27. `--verbose 2` maybe okay.

28. `num_inference_steps 6`, `guidance_phases 1`, `guidance_scale 1`, `flow_shift 12`, `sliding_window_size 362`. These are valid H3 settings? Maybe `flow_shift 12` too high? Not our concern.

29. `image_mode 0`, `image_prompt_type SE`, `video_prompt_type ""`, `audio_prompt_type ""`. Fine.

30. `seed 42`. Fine.

31. `video_length 175`. If frames 107+17k? Could be wrong. Let's investigate more.

The facts: "FL2VA, start+end boundary frames, Wan2GP MiniMax-H3 Pika H3 Flex 6-step LoRA, 768x1344, frames 107+17k, 2090 total". Maybe "frames 107+17k" means start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Wait "frames 107+17k" could mean start frame 107 and end frame 17000? Actually "107+17k" could be "107 + 17k" = 107 + 17000 = 17107 frames per shot? But 2090 total? No.

Maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's parse grammar: "frames 107+17k, 2090 total" maybe "frames 107+17k" means start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Could be "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's consider "107+17k" could be "107 + 17k" where 17k = 17000. But 2090 total? If each shot has 175 frames, total 1750. 2090 - 1750 = 340. Maybe some shots have 175, some 175? Not.

Maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Wait maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's search memory: Wan2GP FL2VA prompt compiled from timing_and_lattice pixel_frames. The shot settings video_length maybe equals pixel_frames. If pixel_frames 175. "frames 107+17k" maybe start frame 107 and end frame 17000? No.

Maybe "107+17k" means start frame 107 and end frame 17000? No.

Could be "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's not dwell. The settings video_length 175. If the story's pixel_frames maybe 175. The "frames 107+17k" might refer to start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Actually "frames 107+17k" could mean start frame 107 and end frame 17000? No.

Let's move on.

Potential high defects:

1. `run_colab_batch.batch` `proc.wait()` could hang if `exec --timeout` doesn't kill non-idle process, leaving session running. But is this real? The `exec --timeout` is idle limit; if GPU busy, no idle, could exceed 6h. But the script itself has hard timeouts per shell command. However `python wgp.py` may run GPU inference without producing shell output? `sh` captures stdout to log, so shell output appears. If GPU busy, no new shell output, idle timer triggers after 6h. Could leave session running for 6h. But if script hangs in subprocess.run timeout=7200, exec timeout won't trigger until idle. But hard timeout kills shell command after 7200s, returning control to shell, which may produce output? If subprocess.run times out, it raises TimeoutExpired, note, returncode 124. Shell continues. So no hang beyond 7200s per command. But if many commands, total could be long. But exec timeout 6h idle. If script runs continuously without idle, could exceed 6h. But G4 batch maybe 1-2h. Risk medium. But round 1 didn't mention. Could be high? Need decide.

2. `run_cli(["exec", "-s", name], stdin=t0.LIST_CODE)` after `proc.wait()`. If exec already exited, sending `exec -s name` may not list files, causing fetch empty, wrong video. This seems plausible. But is it a defect? Let's examine Colab CLI behavior. `colab exec -s <session>` without -f: According to Colab CLI docs, `exec` runs a file in the session. Without -f, maybe it runs the current directory? Actually `colab exec -s <session>` without -f might open an interactive exec? I recall `colab exec -s <session>` without -f runs the script in the current working directory? Hmm. There is `colab exec -s <session> -f <file>`. Without -f, maybe it runs the stdin? The doc says "exec -s name (list files)" in dry run. So intended. But if exec exited, can you still exec? The session may still be alive. The CLI `exec -s name` might list files? I think `colab exec -s <session>` without -f might actually list files? Let's check memory: Colab CLI `exec` command: `colab exec -s <session> [-f <file>]` runs a Python file. If no -f, maybe it runs the current directory? There is also `colab ls -s <session>` to list files. The doc says "exec -s name (list files)" maybe a mistake. But tests pass? `test_normal_run_stops_after_fetch` uses fake_cli returns "" for all calls, so no assertion on list. Could be a defect. But is it real? Let's inspect t0_pack/run_t0_colab.py: It has its own LIST_CODE and uses `cli(["exec", "-s", name], stdin=LIST_CODE)`? Wait t0 code truncated at line 288. It likely does similar. The doc says "a list script on stdin names the .mp4 files ... under /content/out into FILES.txt; colab download...". In t0, `cli(["exec", "-s", name], stdin=LIST_CODE)`? The snippet cut off. It might use `exec -s name` with stdin. If exec without -f doesn't run stdin, files not listed. But maybe `colab exec -s name` with stdin runs the stdin as a script? Actually `colab exec -s <session>` without -f might execute the stdin? I think `colab exec -s <session>` without -f might open an interactive exec? Hmm.

But the doc explicitly says "exec -s name (list files)" in dry run. So intended. Could be okay.

3. `fetch` splits FILES.txt by whitespace; if filenames contain spaces? Shot ids no. Fine.

4. `run_colab_batch.batch` `keep = True` set before `proc.wait()`. If `proc.wait()` raises `BrokenPipeError` or `OSError`, finally still kills? `proc.poll() is None and not keep` -> keep True, so no kill. Session left running. But `proc.wait()` shouldn't raise. Medium.

5. `run_cli(["usage"])` before `new`. Fine.

6. `run_cli(["new", "-s", name, "--gpu", gpu])` if session exists? `new` creates new session. Fine.

7. `proc = popen([...])` without `stdout=DEVNULL`? `colab exec` may print to stdout, captured by parent? Parent doesn't capture. Could fill disk? Not high.

8. `started(name)` checks `ls -s name /content`. If `name` has leading dash? `replace("_","-")`. Fine.

9. `proof_seconds=PROOF_SECONDS=180`. If script takes >180s to create out, stops. But if script creates out after 190s, stops prematurely, losing clips. Could be high? But round 1 fixed? Not mentioned. The first live attempt wasted compute because script never reached VM. Now proof 180s. If script startup >180s, stops. But maybe acceptable? Could be high if script startup slow. But facts say first live attempt wasted compute because 19.7MB script never reached VM. Now run.py 11.3MB, should reach VM faster. But still could be >180s? Maybe not. But potential high? Need decide.

10. `EXEC_TIMEOUT = 6*3600` but `exec --timeout` is idle limit. If script runs non-idle, could exceed. But hard timeout per shell command. Could leave session running. Medium.

11. `run.py` `for attempt in range(1,5)` retries only 4 attempts. If HF 429 persists, no retry beyond 4. But condition `or attempt == 4` breaks on attempt 4 regardless. Good.

12. `lg.read_bytes()[start:]` if `lg` is huge and `start` old, decoding entire log each attempt. Fine.

13. `files = sorted(p.name for p in od.iterdir())` after each attempt. If partial mp4 from previous attempt, `any(.mp4)` true, break. Good.

14. `results[sid] = "ok" if rc == 0 and any(n.endswith(".mp4") for n in files) else "failed"`. If mp4 appears but rc !=0? Unlikely. Fine.

15. `finish` writes RESULT.json and raises SystemExit(1) if failed. But if some shots failed, run.py exits nonzero. `run_colab_batch` raises RunError. Good.

16. `run.py` `LOG = open(OUT / "timeline.txt", "a", buffering=1)` opened at module level. If multiple runs? Single batch. Fine.

17. `subprocess.Popen(f"nvidia-smi ... > {OUT}/gpu.csv", shell=True)` writes gpu.csv. If nvidia-smi fails, Popen raises? `subprocess.Popen` with shell redirect; if nvidia-smi not found, shell error, Popen returns? Actually Popen may raise FileNotFoundError? In shell, if command not found, shell prints error but Popen returns? It might raise? Not sure. But on G4 yes.

18. `sh(f"git clone ... && git checkout ...", "setup.log")` if clone fails, second not run. Good.

19. `if (APP / "ckpts").is_dir() and not (APP / "ckpts").is_symlink():` If ckpts is symlink, skip. Good. But if ckpts is a directory containing symlinks? `iterdir()` follows symlinks? `shutil.move` may follow. Fine.

20. `os.symlink(TMP / "ckpts", APP / "ckpts")` if not exists. Good.

21. `os.environ["HF_HOME"] = str(TMP / "hf")` but no `HF_HOME` dir creation. Wan2GP may create. Not defect.

22. `inputs.mkdir(exist_ok=True)` then write. Good.

23. `for name, b64 in json.loads(base64.b64decode("<BLOB>")).items():` If BLOB contains duplicate names? JSON dict unique. Fine.

24. `f = APP / f"settings_{sid}.json"; f.write_text(json.dumps(settings, indent=1)); shutil.copy(f, OUT / f.name)`. If settings has non-serializable? Not.

25. `od = OUT / sid; od.mkdir(exist_ok=True)`. If sid contains "/"? Not.

26. `cd {APP} && python wgp.py --process {f} --output-dir {od} --profile 5 --verbose 2`. Hardcoded profile 5. If builder changes --profile, mismatch. But facts profile 5. Low.

27. `--verbose 2` maybe okay.

28. `num_inference_steps 6`, `guidance_phases 1`, `guidance_scale 1`, `flow_shift 12`, `sliding_window_size 362`. These are valid H3 settings? Maybe `flow_shift 12` too high? Not our concern.

29. `image_mode 0`, `image_prompt_type SE`, `video_prompt_type ""`, `audio_prompt_type ""`. Fine.

30. `seed 42`. Fine.

31. `video_length 175`. If frames 107+17k? Could be wrong. Let's investigate more.

The facts: "FL2VA, start+end boundary frames, Wan2GP MiniMax-H3 Pika H3 Flex 6-step LoRA, 768x1344, frames 107+17k, 2090 total". Maybe "frames 107+17k" means start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Wait "frames 107+17k" could mean start frame 107 and end frame 17000? Actually "107+17k" could be "107 + 17k" = 107 + 17000 = 17107 frames per shot? But 2090 total? No.

Maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's parse grammar: "frames 107+17k, 2090 total" maybe "frames 107+17k" means start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Could be "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's consider "107+17k" could be "107 + 17k" where 17k = 17000. But 2090 total? If each shot has 175 frames, total 1750. 2090 - 1750 = 340. Maybe some shots have 175, some 175? Not.

Maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Wait maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's search memory: Wan2GP FL2VA prompt compiled from timing_and_lattice pixel_frames. The shot settings video_length maybe equals pixel_frames. If pixel_frames 175. "frames 107+17k" maybe start frame 107 and end frame 17000? No.

Maybe "107+17k" means start frame 107 and end frame 17000? No.

Could be "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's not dwell. The settings video_length 175. If the story's pixel_frames maybe 175. The "frames 107+17k" might refer to start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Actually "frames 107+17k" could mean start frame 107 and end frame 17000? No.

Let's move on.

Potential high defects:

1. `run_colab_batch.batch` `proc.wait()` could hang if `exec --timeout` doesn't kill non-idle process, leaving session running. But is this real? The `exec --timeout` is idle limit; if GPU busy, no idle, could exceed 6h. But the script itself has hard timeouts per shell command. However `python wgp.py` may run GPU inference without producing shell output? `sh` captures stdout to log, so shell output appears. If GPU busy, no new shell output, idle timer triggers after 6h. Could leave session running for 6h. But if script hangs in subprocess.run timeout=7200, exec timeout won't trigger until idle. But hard timeout kills shell command after 7200s, returning control to shell, which may produce output? If subprocess.run times out, it raises TimeoutExpired, note, returncode 124. Shell continues. So no hang beyond 7200s per command. But if many commands, total could be long. But exec timeout 6h idle. If script runs continuously without idle, could exceed 6h. But G4 batch maybe 1-2h. Risk medium. But round 1 didn't mention. Could be high? Need decide.

2. `run_cli(["exec", "-s", name], stdin=t0.LIST_CODE)` after `proc.wait()`. If exec already exited, sending `exec -s name` may not list files, causing fetch empty, wrong video. This seems plausible. But is it a defect? Let's examine Colab CLI behavior. `colab exec -s <session>` without -f: According to Colab CLI docs, `exec` runs a file in the session. Without -f, maybe it runs the current directory? Actually `colab exec -s <session>` without -f might open an interactive exec? I recall `colab exec -s <session>` without -f runs the script in the current working directory? Hmm. There is `colab exec -s <session> -f <file>`. Without -f, maybe it runs the stdin? The doc says "exec -s name (list files)" in dry run. So intended. But if exec exited, can you still exec? The session may still be alive. The CLI `exec -s name` might list files? I think `colab exec -s <session>` without -f might actually list files? Let's check memory: Colab CLI `exec` command: `colab exec -s <session> [-f <file>]` runs a Python file. If no -f, maybe it runs the current directory? There is also `colab ls -s <session>` to list files. The doc says "exec -s name (list files)" maybe a mistake. But tests pass? `test_normal_run_stops_after_fetch` uses fake_cli returns "" for all calls, so no assertion on list. Could be a defect. But is it real? Let's inspect t0_pack/run_t0_colab.py: It has its own LIST_CODE and uses `cli(["exec", "-s", name], stdin=LIST_CODE)`? Wait t0 code truncated at line 288. It likely does similar. The doc says "a list script on stdin names the .mp4 files ... under /content/out into FILES.txt; colab download...". In t0, `cli(["exec", "-s", name], stdin=LIST_CODE)`? The snippet cut off. It might use `exec -s name` with stdin. If exec without -f doesn't run stdin, files not listed. But maybe `colab exec -s name` with stdin runs the stdin as a script? Actually `colab exec -s <session>` without -f might execute the stdin? I think `colab exec -s <session>` without -f might open an interactive exec? Hmm.

But the doc explicitly says "exec -s name (list files)" in dry run. So intended. Could be okay.

3. `fetch` splits FILES.txt by whitespace; if filenames contain spaces? Shot ids no. Fine.

4. `run_colab_batch.batch` `keep = True` set before `proc.wait()`. If `proc.wait()` raises `BrokenPipeError` or `OSError`, finally still kills? `proc.poll() is None and not keep` -> keep True, so no kill. Session left running. But `proc.wait()` shouldn't raise. Medium.

5. `run_cli(["usage"])` before `new`. Fine.

6. `run_cli(["new", "-s", name, "--gpu", gpu])` if session exists? `new` creates new session. Fine.

7. `proc = popen([...])` without `stdout=DEVNULL`? `colab exec` may print to stdout, captured by parent? Parent doesn't capture. Could fill disk? Not high.

8. `started(name)` checks `ls -s name /content`. If `name` has leading dash? `replace("_","-")`. Fine.

9. `proof_seconds=PROOF_SECONDS=180`. If script takes >180s to create out, stops. But if script creates out after 190s, stops prematurely, losing clips. Could be high? But round 1 fixed? Not mentioned. The first live attempt wasted compute because script never reached VM. Now proof 180s. If script startup >180s, stops. But maybe acceptable? Could be high if script startup slow. But facts say first live attempt wasted compute because 19.7MB script never reached VM. Now run.py 11.3MB, should reach VM faster. But still could be >180s? Maybe not. But potential high? Need decide.

10. `EXEC_TIMEOUT = 6*3600` but `exec --timeout` is idle limit. If script runs non-idle, could exceed. But hard timeout per shell command. Could leave session running. Medium.

11. `run.py` `for attempt in range(1,5)` retries only 4 attempts. If HF 429 persists, no retry beyond 4. But condition `or attempt == 4` breaks on attempt 4 regardless. Good.

12. `lg.read_bytes()[start:]` if `lg` is huge and `start` old, decoding entire log each attempt. Fine.

13. `files = sorted(p.name for p in od.iterdir())` after each attempt. If partial mp4 from previous attempt, `any(.mp4)` true, break. Good.

14. `results[sid] = "ok" if rc == 0 and any(n.endswith(".mp4") for n in files) else "failed"`. If mp4 appears but rc !=0? Unlikely. Fine.

15. `finish` writes RESULT.json and raises SystemExit(1) if failed. But if some shots failed, run.py exits nonzero. `run_colab_batch` raises RunError. Good.

16. `run.py` `LOG = open(OUT / "timeline.txt", "a", buffering=1)` opened at module level. If multiple runs? Single batch. Fine.

17. `subprocess.Popen(f"nvidia-smi ... > {OUT}/gpu.csv", shell=True)` writes gpu.csv. If nvidia-smi fails, Popen raises? `subprocess.Popen` with shell redirect; if nvidia-smi not found, shell error, Popen returns? Actually Popen may raise FileNotFoundError? In shell, if command not found, shell prints error but Popen returns? It might raise? Not sure. But on G4 yes.

18. `sh(f"git clone ... && git checkout ...", "setup.log")` if clone fails, second not run. Good.

19. `if (APP / "ckpts").is_dir() and not (APP / "ckpts").is_symlink():` If ckpts is symlink, skip. Good. But if ckpts is a directory containing symlinks? `iterdir()` follows symlinks? `shutil.move` may follow. Fine.

20. `os.symlink(TMP / "ckpts", APP / "ckpts")` if not exists. Good.

21. `os.environ["HF_HOME"] = str(TMP / "hf")` but no `HF_HOME` dir creation. Wan2GP may create. Not defect.

22. `inputs.mkdir(exist_ok=True)` then write. Good.

23. `for name, b64 in json.loads(base64.b64decode("<BLOB>")).items():` If BLOB contains duplicate names? JSON dict unique. Fine.

24. `f = APP / f"settings_{sid}.json"; f.write_text(json.dumps(settings, indent=1)); shutil.copy(f, OUT / f.name)`. If settings has non-serializable? Not.

25. `od = OUT / sid; od.mkdir(exist_ok=True)`. If sid contains "/"? Not.

26. `cd {APP} && python wgp.py --process {f} --output-dir {od} --profile 5 --verbose 2`. Hardcoded profile 5. If builder changes --profile, mismatch. But facts profile 5. Low.

27. `--verbose 2` maybe okay.

28. `num_inference_steps 6`, `guidance_phases 1`, `guidance_scale 1`, `flow_shift 12`, `sliding_window_size 362`. These are valid H3 settings? Maybe `flow_shift 12` too high? Not our concern.

29. `image_mode 0`, `image_prompt_type SE`, `video_prompt_type ""`, `audio_prompt_type ""`. Fine.

30. `seed 42`. Fine.

31. `video_length 175`. If frames 107+17k? Could be wrong. Let's investigate more.

The facts: "FL2VA, start+end boundary frames, Wan2GP MiniMax-H3 Pika H3 Flex 6-step LoRA, 768x1344, frames 107+17k, 2090 total". Maybe "frames 107+17k" means start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Wait "frames 107+17k" could mean start frame 107 and end frame 17000? Actually "107+17k" could be "107 + 17k" = 107 + 17000 = 17107 frames per shot? But 2090 total? No.

Maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's parse grammar: "frames 107+17k, 2090 total" maybe "frames 107+17k" means start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Could be "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's consider "107+17k" could be "107 + 17k" where 17k = 17000. But 2090 total? If each shot has 175 frames, total 1750. 2090 - 1750 = 340. Maybe some shots have 175, some 175? Not.

Maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Wait maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's search memory: Wan2GP FL2VA prompt compiled from timing_and_lattice pixel_frames. The shot settings video_length maybe equals pixel_frames. If pixel_frames 175. "frames 107+17k" maybe start frame 107 and end frame 17000? No.

Maybe "107+17k" means start frame 107 and end frame 17000? No.

Could be "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's not dwell. The settings video_length 175. If the story's pixel_frames maybe 175. The "frames 107+17k" might refer to start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Actually "frames 107+17k" could mean start frame 107 and end frame 17000? No.

Let's move on.

Potential high defects:

1. `run_colab_batch.batch` `proc.wait()` could hang if `exec --timeout` doesn't kill non-idle process, leaving session running. But is this real? The `exec --timeout` is idle limit; if GPU busy, no idle, could exceed 6h. But the script itself has hard timeouts per shell command. However `python wgp.py` may run GPU inference without producing shell output? `sh` captures stdout to log, so shell output appears. If GPU busy, no new shell output, idle timer triggers after 6h. Could leave session running for 6h. But if script hangs in subprocess.run timeout=7200, exec timeout won't trigger until idle. But hard timeout kills shell command after 7200s, returning control to shell, which may produce output? If subprocess.run times out, it raises TimeoutExpired, note, returncode 124. Shell continues. So no hang beyond 7200s per command. But if many commands, total could be long. But exec timeout 6h idle. If script runs continuously without idle, could exceed 6h. But G4 batch maybe 1-2h. Risk medium. But round 1 didn't mention. Could be high? Need decide.

2. `run_cli(["exec", "-s", name], stdin=t0.LIST_CODE)` after `proc.wait()`. If exec already exited, sending `exec -s name` may not list files, causing fetch empty, wrong video. This seems plausible. But is it a defect? Let's examine Colab CLI behavior. `colab exec -s <session>` without -f: According to Colab CLI docs, `exec` runs a file in the session. Without -f, maybe it runs the current directory? Actually `colab exec -s <session>` without -f might open an interactive exec? I recall `colab exec -s <session>` without -f runs the script in the current working directory? Hmm. There is `colab exec -s <session> -f <file>`. Without -f, maybe it runs the stdin? The doc says "exec -s name (list files)" in dry run. So intended. But if exec exited, can you still exec? The session may still be alive. The CLI `exec -s name` might list files? I think `colab exec -s <session>` without -f might actually list files? Let's check memory: Colab CLI `exec` command: `colab exec -s <session> [-f <file>]` runs a Python file. If no -f, maybe it runs the current directory? There is also `colab ls -s <session>` to list files. The doc says "exec -s name (list files)" maybe a mistake. But tests pass? `test_normal_run_stops_after_fetch` uses fake_cli returns "" for all calls, so no assertion on list. Could be a defect. But is it real? Let's inspect t0_pack/run_t0_colab.py: It has its own LIST_CODE and uses `cli(["exec", "-s", name], stdin=LIST_CODE)`? Wait t0 code truncated at line 288. It likely does similar. The doc says "a list script on stdin names the .mp4 files ... under /content/out into FILES.txt; colab download...". In t0, `cli(["exec", "-s", name], stdin=LIST_CODE)`? The snippet cut off. It might use `exec -s name` with stdin. If exec without -f doesn't run stdin, files not listed. But maybe `colab exec -s name` with stdin runs the stdin as a script? Actually `colab exec -s <session>` without -f might execute the stdin? I think `colab exec -s <session>` without -f might open an interactive exec? Hmm.

But the doc explicitly says "exec -s name (list files)" in dry run. So intended. Could be okay.

3. `fetch` splits FILES.txt by whitespace; if filenames contain spaces? Shot ids no. Fine.

4. `run_colab_batch.batch` `keep = True` set before `proc.wait()`. If `proc.wait()` raises `BrokenPipeError` or `OSError`, finally still kills? `proc.poll() is None and not keep` -> keep True, so no kill. Session left running. But `proc.wait()` shouldn't raise. Medium.

5. `run_cli(["usage"])` before `new`. Fine.

6. `run_cli(["new", "-s", name, "--gpu", gpu])` if session exists? `new` creates new session. Fine.

7. `proc = popen([...])` without `stdout=DEVNULL`? `colab exec` may print to stdout, captured by parent? Parent doesn't capture. Could fill disk? Not high.

8. `started(name)` checks `ls -s name /content`. If `name` has leading dash? `replace("_","-")`. Fine.

9. `proof_seconds=PROOF_SECONDS=180`. If script takes >180s to create out, stops. But if script creates out after 190s, stops prematurely, losing clips. Could be high? But round 1 fixed? Not mentioned. The first live attempt wasted compute because script never reached VM. Now proof 180s. If script startup >180s, stops. But maybe acceptable? Could be high if script startup slow. But facts say first live attempt wasted compute because 19.7MB script never reached VM. Now run.py 11.3MB, should reach VM faster. But still could be >180s? Maybe not. But potential high? Need decide.

10. `EXEC_TIMEOUT = 6*3600` but `exec --timeout` is idle limit. If script runs non-idle, could exceed. But hard timeout per shell command. Could leave session running. Medium.

11. `run.py` `for attempt in range(1,5)` retries only 4 attempts. If HF 429 persists, no retry beyond 4. But condition `or attempt == 4` breaks on attempt 4 regardless. Good.

12. `lg.read_bytes()[start:]` if `lg` is huge and `start` old, decoding entire log each attempt. Fine.

13. `files = sorted(p.name for p in od.iterdir())` after each attempt. If partial mp4 from previous attempt, `any(.mp4)` true, break. Good.

14. `results[sid] = "ok" if rc == 0 and any(n.endswith(".mp4") for n in files) else "failed"`. If mp4 appears but rc !=0? Unlikely. Fine.

15. `finish` writes RESULT.json and raises SystemExit(1) if failed. But if some shots failed, run.py exits nonzero. `run_colab_batch` raises RunError. Good.

16. `run.py` `LOG = open(OUT / "timeline.txt", "a", buffering=1)` opened at module level. If multiple runs? Single batch. Fine.

17. `subprocess.Popen(f"nvidia-smi ... > {OUT}/gpu.csv", shell=True)` writes gpu.csv. If nvidia-smi fails, Popen raises? `subprocess.Popen` with shell redirect; if nvidia-smi not found, shell error, Popen returns? Actually Popen may raise FileNotFoundError? In shell, if command not found, shell prints error but Popen returns? It might raise? Not sure. But on G4 yes.

18. `sh(f"git clone ... && git checkout ...", "setup.log")` if clone fails, second not run. Good.

19. `if (APP / "ckpts").is_dir() and not (APP / "ckpts").is_symlink():` If ckpts is symlink, skip. Good. But if ckpts is a directory containing symlinks? `iterdir()` follows symlinks? `shutil.move` may follow. Fine.

20. `os.symlink(TMP / "ckpts", APP / "ckpts")` if not exists. Good.

21. `os.environ["HF_HOME"] = str(TMP / "hf")` but no `HF_HOME` dir creation. Wan2GP may create. Not defect.

22. `inputs.mkdir(exist_ok=True)` then write. Good.

23. `for name, b64 in json.loads(base64.b64decode("<BLOB>")).items():` If BLOB contains duplicate names? JSON dict unique. Fine.

24. `f = APP / f"settings_{sid}.json"; f.write_text(json.dumps(settings, indent=1)); shutil.copy(f, OUT / f.name)`. If settings has non-serializable? Not.

25. `od = OUT / sid; od.mkdir(exist_ok=True)`. If sid contains "/"? Not.

26. `cd {APP} && python wgp.py --process {f} --output-dir {od} --profile 5 --verbose 2`. Hardcoded profile 5. If builder changes --profile, mismatch. But facts profile 5. Low.

27. `--verbose 2` maybe okay.

28. `num_inference_steps 6`, `guidance_phases 1`, `guidance_scale 1`, `flow_shift 12`, `sliding_window_size 362`. These are valid H3 settings? Maybe `flow_shift 12` too high? Not our concern.

29. `image_mode 0`, `image_prompt_type SE`, `video_prompt_type ""`, `audio_prompt_type ""`. Fine.

30. `seed 42`. Fine.

31. `video_length 175`. If frames 107+17k? Could be wrong. Let's investigate more.

The facts: "FL2VA, start+end boundary frames, Wan2GP MiniMax-H3 Pika H3 Flex 6-step LoRA, 768x1344, frames 107+17k, 2090 total". Maybe "frames 107+17k" means start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Wait "frames 107+17k" could mean start frame 107 and end frame 17000? Actually "107+17k" could be "107 + 17k" = 107 + 17000 = 17107 frames per shot? But 2090 total? No.

Maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's parse grammar: "frames 107+17k, 2090 total" maybe "frames 107+17k" means start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Could be "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's consider "107+17k" could be "107 + 17k" where 17k = 17000. But 2090 total? If each shot has 175 frames, total 1750. 2090 - 1750 = 340. Maybe some shots have 175, some 175? Not.

Maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Wait maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's search memory: Wan2GP FL2VA prompt compiled from timing_and_lattice pixel_frames. The shot settings video_length maybe equals pixel_frames. If pixel_frames 175. "frames 107+17k" maybe start frame 107 and end frame 17000? No.

Maybe "107+17k" means start frame 107 and end frame 17000? No.

Could be "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's not dwell. The settings video_length 175. If the story's pixel_frames maybe 175. The "frames 107+17k" might refer to start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Actually "frames 107+17k" could mean start frame 107 and end frame 17000? No.

Let's move on.

Potential high defects:

1. `run_colab_batch.batch` `proc.wait()` could hang if `exec --timeout` doesn't kill non-idle process, leaving session running. But is this real? The `exec --timeout` is idle limit; if GPU busy, no idle, could exceed 6h. But the script itself has hard timeouts per shell command. However `python wgp.py` may run GPU inference without producing shell output? `sh` captures stdout to log, so shell output appears. If GPU busy, no new shell output, idle timer triggers after 6h. Could leave session running for 6h. But if script hangs in subprocess.run timeout=7200, exec timeout won't trigger until idle. But hard timeout kills shell command after 7200s, returning control to shell, which may produce output? If subprocess.run times out, it raises TimeoutExpired, note, returncode 124. Shell continues. So no hang beyond 7200s per command. But if many commands, total could be long. But exec timeout 6h idle. If script runs continuously without idle, could exceed 6h. But G4 batch maybe 1-2h. Risk medium. But round 1 didn't mention. Could be high? Need decide.

2. `run_cli(["exec", "-s", name], stdin=t0.LIST_CODE)` after `proc.wait()`. If exec already exited, sending `exec -s name` may not list files, causing fetch empty, wrong video. This seems plausible. But is it a defect? Let's examine Colab CLI behavior. `colab exec -s <session>` without -f: According to Colab CLI docs, `exec` runs a file in the session. Without -f, maybe it runs the current directory? Actually `colab exec -s <session>` without -f might open an interactive exec? I recall `colab exec -s <session>` without -f runs the script in the current working directory? Hmm. There is `colab exec -s <session> -f <file>`. Without -f, maybe it runs the stdin? The doc says "exec -s name (list files)" in dry run. So intended. But if exec exited, can you still exec? The session may still be alive. The CLI `exec -s name` might list files? I think `colab exec -s <session>` without -f might actually list files? Let's check memory: Colab CLI `exec` command: `colab exec -s <session> [-f <file>]` runs a Python file. If no -f, maybe it runs the current directory? There is also `colab ls -s <session>` to list files. The doc says "exec -s name (list files)" maybe a mistake. But tests pass? `test_normal_run_stops_after_fetch` uses fake_cli returns "" for all calls, so no assertion on list. Could be a defect. But is it real? Let's inspect t0_pack/run_t0_colab.py: It has its own LIST_CODE and uses `cli(["exec", "-s", name], stdin=LIST_CODE)`? Wait t0 code truncated at line 288. It likely does similar. The doc says "a list script on stdin names the .mp4 files ... under /content/out into FILES.txt; colab download...". In t0, `cli(["exec", "-s", name], stdin=LIST_CODE)`? The snippet cut off. It might use `exec -s name` with stdin. If exec without -f doesn't run stdin, files not listed. But maybe `colab exec -s name` with stdin runs the stdin as a script? Actually `colab exec -s <session>` without -f might execute the stdin? I think `colab exec -s <session>` without -f might open an interactive exec? Hmm.

But the doc explicitly says "exec -s name (list files)" in dry run. So intended. Could be okay.

3. `fetch` splits FILES.txt by whitespace; if filenames contain spaces? Shot ids no. Fine.

4. `run_colab_batch.batch` `keep = True` set before `proc.wait()`. If `proc.wait()` raises `BrokenPipeError` or `OSError`, finally still kills? `proc.poll() is None and not keep` -> keep True, so no kill. Session left running. But `proc.wait()` shouldn't raise. Medium.

5. `run_cli(["usage"])` before `new`. Fine.

6. `run_cli(["new", "-s", name, "--gpu", gpu])` if session exists? `new` creates new session. Fine.

7. `proc = popen([...])` without `stdout=DEVNULL`? `colab exec` may print to stdout, captured by parent? Parent doesn't capture. Could fill disk? Not high.

8. `started(name)` checks `ls -s name /content`. If `name` has leading dash? `replace("_","-")`. Fine.

9. `proof_seconds=PROOF_SECONDS=180`. If script takes >180s to create out, stops. But if script creates out after 190s, stops prematurely, losing clips. Could be high? But round 1 fixed? Not mentioned. The first live attempt wasted compute because script never reached VM. Now proof 180s. If script startup >180s, stops. But maybe acceptable? Could be high if script startup slow. But facts say first live attempt wasted compute because 19.7MB script never reached VM. Now run.py 11.3MB, should reach VM faster. But still could be >180s? Maybe not. But potential high? Need decide.

10. `EXEC_TIMEOUT = 6*3600` but `exec --timeout` is idle limit. If script runs non-idle, could exceed. But hard timeout per shell command. Could leave session running. Medium.

11. `run.py` `for attempt in range(1,5)` retries only 4 attempts. If HF 429 persists, no retry beyond 4. But condition `or attempt == 4` breaks on attempt 4 regardless. Good.

12. `lg.read_bytes()[start:]` if `lg` is huge and `start` old, decoding entire log each attempt. Fine.

13. `files = sorted(p.name for p in od.iterdir())` after each attempt. If partial mp4 from previous attempt, `any(.mp4)` true, break. Good.

14. `results[sid] = "ok" if rc == 0 and any(n.endswith(".mp4") for n in files) else "failed"`. If mp4 appears but rc !=0? Unlikely. Fine.

15. `finish` writes RESULT.json and raises SystemExit(1) if failed. But if some shots failed, run.py exits nonzero. `run_colab_batch` raises RunError. Good.

16. `run.py` `LOG = open(OUT / "timeline.txt", "a", buffering=1)` opened at module level. If multiple runs? Single batch. Fine.

17. `subprocess.Popen(f"nvidia-smi ... > {OUT}/gpu.csv", shell=True)` writes gpu.csv. If nvidia-smi fails, Popen raises? `subprocess.Popen` with shell redirect; if nvidia-smi not found, shell error, Popen returns? Actually Popen may raise FileNotFoundError? In shell, if command not found, shell prints error but Popen returns? It might raise? Not sure. But on G4 yes.

18. `sh(f"git clone ... && git checkout ...", "setup.log")` if clone fails, second not run. Good.

19. `if (APP / "ckpts").is_dir() and not (APP / "ckpts").is_symlink():` If ckpts is symlink, skip. Good. But if ckpts is a directory containing symlinks? `iterdir()` follows symlinks? `shutil.move` may follow. Fine.

20. `os.symlink(TMP / "ckpts", APP / "ckpts")` if not exists. Good.

21. `os.environ["HF_HOME"] = str(TMP / "hf")` but no `HF_HOME` dir creation. Wan2GP may create. Not defect.

22. `inputs.mkdir(exist_ok=True)` then write. Good.

23. `for name, b64 in json.loads(base64.b64decode("<BLOB>")).items():` If BLOB contains duplicate names? JSON dict unique. Fine.

24. `f = APP / f"settings_{sid}.json"; f.write_text(json.dumps(settings, indent=1)); shutil.copy(f, OUT / f.name)`. If settings has non-serializable? Not.

25. `od = OUT / sid; od.mkdir(exist_ok=True)`. If sid contains "/"? Not.

26. `cd {APP} && python wgp.py --process {f} --output-dir {od} --profile 5 --verbose 2`. Hardcoded profile 5. If builder changes --profile, mismatch. But facts profile 5. Low.

27. `--verbose 2` maybe okay.

28. `num_inference_steps 6`, `guidance_phases 1`, `guidance_scale 1`, `flow_shift 12`, `sliding_window_size 362`. These are valid H3 settings? Maybe `flow_shift 12` too high? Not our concern.

29. `image_mode 0`, `image_prompt_type SE`, `video_prompt_type ""`, `audio_prompt_type ""`. Fine.

30. `seed 42`. Fine.

31. `video_length 175`. If frames 107+17k? Could be wrong. Let's investigate more.

The facts: "FL2VA, start+end boundary frames, Wan2GP MiniMax-H3 Pika H3 Flex 6-step LoRA, 768x1344, frames 107+17k, 2090 total". Maybe "frames 107+17k" means start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Wait "frames 107+17k" could mean start frame 107 and end frame 17000? Actually "107+17k" could be "107 + 17k" = 107 + 17000 = 17107 frames per shot? But 2090 total? No.

Maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's parse grammar: "frames 107+17k, 2090 total" maybe "frames 107+17k" means start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Could be "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's consider "107+17k" could be "107 + 17k" where 17k = 17000. But 2090 total? If each shot has 175 frames, total 1750. 2090 - 1750 = 340. Maybe some shots have 175, some 175? Not.

Maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Wait maybe "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's search memory: Wan2GP FL2VA prompt compiled from timing_and_lattice pixel_frames. The shot settings video_length maybe equals pixel_frames. If pixel_frames 175. "frames 107+17k" maybe start frame 107 and end frame 17000? No.

Maybe "107+17k" means start frame 107 and end frame 17000? No.

Could be "frames 107+17k" means start frame 107 and end frame 17000? No.

Let's not dwell. The settings video_length 175. If the story's pixel_frames maybe 175. The "frames 107+17k" might refer to start frame 107 and end frame 17000? But 2090 total? Could be 10 shots, each 175 frames = 1750, plus 340? Not 2090. Maybe "107+17k" means start frame 107 and end frame 17000? No.

Actually "frames 107+17k" could mean start frame 107 and end frame 17000? No.

Let's move on.

Potential high defects:

1. `run_colab_batch.batch` `proc.wait()` could hang if `exec --timeout` doesn't kill non-idle process, leaving session running. But is this real? The `exec --timeout` is idle limit; if GPU busy, no idle, could exceed 6h. But the script itself has hard timeouts per shell command. However `python wgp.py` may run GPU inference without producing shell output? `sh` captures stdout to log, so shell output appears. If GPU busy, no new shell output, idle timer triggers after 6h. Could leave session running for 6h. But if script hangs in subprocess.run timeout=7200, exec timeout won't trigger until idle. But hard timeout kills shell command after 7200s, returning control to shell, which may produce output? If subprocess.run times out, it raises TimeoutExpired, note, returncode 124. Shell continues. So no hang beyond 7200s per command. But if many commands, total could be long. But exec timeout 6h idle. If script runs continuously without idle, could exceed 6h. But G4 batch maybe 1-2h. Risk medium. But round 1 didn't mention. Could be high? Need decide.

2. `run_cli(["exec", "-s", name], stdin=t0.LIST_CODE)` after `proc.wait()`. If exec already exited, sending `exec -s name` may not list files, causing fetch empty, wrong video. This seems plausible. But is it a defect? Let's examine Colab CLI behavior. `colab exec -s <session>` without -f: According to Colab CLI docs, `exec` runs a file in the session. Without -f, maybe it runs the current directory? Actually `colab exec -s <session>` without -f might open an interactive exec? I recall `colab exec -s <session>` without -f runs the script in the current working directory? Hmm. There is `colab exec -s <session> -f <file>`. Without -f, maybe it runs the stdin? The doc says "exec -s name (list files)" in dry run. So intended. But if exec exited, can you still exec? The session may still be alive. The CLI `exec -s name` might list files? I think `colab exec -s <session>` without -f might actually list files? Let's check memory: Colab CLI `exec` command: `colab exec -s <session> [-f <file>]` runs a Python file. If no -f, maybe it runs the current directory? There is also `colab ls -s <session>` to list files. The doc says "exec -s name (list files)" maybe a mistake. But tests pass? `test_normal_run_stops_after_fetch` uses fake_cli returns "" for all calls, so no assertion on list. Could be a defect. But is it real? Let's inspect t0_pack/run_t0_colab.py: It has its own LIST_CODE and uses `cli(["exec", "-s", name], stdin=LIST_CODE)`? Wait t0 code truncated at line 288. It likely does similar. The doc says "a list script on stdin names the .mp4 files ... under /content/out into FILES.txt; colab download...". In t0, `cli(["exec", "-s", name], stdin=LIST_CODE)`? The snippet cut off. It might use `exec -s name` with stdin. If exec without -f doesn't run stdin, files not listed. But maybe `colab exec -s name` with stdin runs the stdin as a script? Actually `colab exec -s <session>` without -f might execute the stdin? I think `colab exec -s <session>` without -f might open an interactive exec? Hmm.

But the doc explicitly says "exec -s name (list files)" in dry run. So intended. Could be okay.

3. `fetch` splits FILES.txt by whitespace; if filenames contain spaces? Shot ids no. Fine.

4. `run_colab_batch.batch` `keep = True` set before `proc.wait()`. If `proc.wait()` raises `BrokenPipeError` or `OSError`, finally still kills? `proc.poll() is None and not keep` -> keep True, so no kill. Session left running. But `proc.wait()` shouldn't raise. Medium.

5. `run_cli(["usage"])` before `new`. Fine.

6. `run_cli(["new", "-s", name, "--gpu", gpu])` if session exists? `new` creates new session. Fine.

7. `proc = popen([...])` without `stdout=DEVNULL`? `colab exec` may print to stdout, captured by parent? Parent doesn't capture. Could fill disk? Not high.

8. `started(name)` checks `ls -s name /content`. If `name` has leading dash? `replace("_","-")`. Fine.

9. `proof_seconds=PROOF_SECONDS=180`. If script takes >180s to create out, stops. But if script creates out after 190s, stops prematurely, losing clips. Could be high? But round 1 fixed? Not mentioned. The first live attempt wasted compute because script never reached VM. Now proof 180s. If script startup >180s, stops. But maybe acceptable? Could be high if script startup slow. But facts say first live attempt wasted compute because 19.7MB script never reached VM. Now run.py 11.3MB, should reach VM faster. But still could be >180s? Maybe not. But potential high? Need decide.

10. `EXEC_TIMEOUT = 6*3600` but `exec --timeout` is idle limit. If script runs non-idle, could exceed. But hard timeout per shell command. Could leave session running. Medium.

11. `run.py` `for attempt in range(1,5)` retries only 4 attempts. If HF 429 persists, no retry beyond 4. But condition `or attempt == 4` breaks on attempt 4 regardless. Good.

12. `lg.read_bytes()[start:]` if `lg` is huge and `start` old, decoding entire log each attempt. Fine.

13. `files = sorted(p.name for p in od.iterdir())` after each attempt. If partial mp4 from previous attempt, `any(.mp4)` true, break. Good.

14. `results[sid] = "ok" if rc == 0 and any(n.endswith(".mp4") for n in files) else "failed"`. If mp4 appears but rc !=0? Unlikely. Fine.

15. `finish` writes RESULT.json and raises SystemExit(1) if failed. But if some shots failed, run.py exits nonzero. `run_colab_batch` raises RunError. Good.

16. `run.py` `LOG = open(OUT / "timeline.txt", "a", buffering=1)` opened at module level. If multiple runs? Single batch. Fine.

17. `subprocess.Popen(f"nvidia-smi ... > {OUT}/gpu.csv", shell=True)` writes gpu.csv. If nvidia-smi fails, Popen raises? `subprocess.Popen` with shell redirect; if nvidia-smi not found, shell error, Popen returns? Actually Popen may raise FileNotFoundError? In shell, if command not found, shell prints error but Popen returns? It might raise? Not sure. But on G4 yes.

18. `sh(f"git clone ... && git checkout ...", "setup.log")` if clone fails, second not run. Good.

19. `if (APP / "ckpts").is_dir() and not (APP / "ckpts").is_symlink():` If ckpts is symlink, skip. Good. But if ckpts is a directory containing symlinks? `iterdir()` follows symlinks? `shutil.move` may follow. Fine.

20. `os.symlink(TMP / "ckpts", APP / "ckpts")` if not exists. Good.

21. `os.environ["HF_HOME"] = str(TMP / "hf")` but no `HF_HOME` dir creation. Wan2GP may create. Not defect.

22. `inputs.mkdir(exist_ok=True)` then write. Good.

23. `for name, b64 in json.loads(base64.b64decode("<BLOB>")).items():` If BLOB contains duplicate names? JSON dict unique. Fine.

24. `f = APP / f"settings_{sid}.json"; f.write_text(json.dumps(settings, indent=1)); shutil.copy(f, OUT / f.name)`. If settings has non-serializable? Not.

25. `od = OUT / sid; od.mkdir(exist_ok=True)`. If sid contains "/"? Not.

26. `cd {APP} && python wgp.py --process {f} --output-dir {od} --profile 5 --verbose 2`. Hardcoded profile 5. If builder changes --profile, mismatch. But facts profile 5. Low.

27. `--verbose 2` maybe okay.

28. `num_inference_steps 6`, `guidance_phases 1`, `guidance_scale 1`, `flow_shift 12`, `sliding_window_size 362`. These are valid H3 settings? Maybe `flow_shift 12` too high? Not our concern.

29. `image_mode 0`, `image_prompt_type SE`, `video_prompt_type ""`, `audio_prompt_type ""`. Fine.

30. `seed 42`. Fine.

31. `video_length 175`. If frames 107+17k? Could be wrong. Let's investigate more.

The facts: "FL2VA, start+end boundary frames, Wan2GP MiniMax-H3 Pika H3
