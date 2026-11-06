# Google Colab CLI (`colab`) - Team Reference

Source: https://github.com/googlecolab/google-colab-cli (main branch). Fetched 2026-11-05.
Read: README.md, docs/01_session_management.md, docs/02_execution_and_interactive.md, docs/03_file_management.md, docs/04_automation_and_utility.md, docs/05_run_command.md, docs/demos.md. No 404s. Repo also contains docs/06_ssh_access.md (not read for this reference).

"Not stated" = the docs do not say this.

**Platform: Linux and macOS only. Windows is not supported (README). Our team is on Windows 11.**

---

## 1. Install and auth

**Install** (README):
```
uv tool install google-colab-cli     # recommended
pip install google-colab-cli
```
Update: `colab update` (check), `colab update --install` (in-place, Linux/macOS only).

**Auth strategies** (global flag `--auth {oauth2,adc}`):

| Item | Value | Source |
|---|---|---|
| Default auth | **Conflict in docs.** README says `adc`. docs/04 says `oauth2` is the default. Demos always pass `--auth=adc`. Treat `adc` as the safe choice and verify with `colab --help`. | README vs docs/04 |
| `oauth2` | Copy-paste flow. CLI prints an authorization URL (redirect `https://sdk.cloud.google.com/applicationdefaultauthcode.html`, `token_usage=remote`), you sign in, copy the code Google shows, paste it at the `input()` prompt. No local browser or port needed. | docs/04 log 2026-06-11 |
| `adc` | Application Default Credentials: `GOOGLE_APPLICATION_CREDENTIALS`, `gcloud auth application-default login`, or GCE/GKE metadata. | docs/04 |
| Client config | `-c, --client-oauth-config PATH`, default `~/.colab-cli-oauth-config.json`; falls back to bundled `oauth_config.json`. | README, docs/04 |

**Where credentials/config live:**

| What | Location |
|---|---|
| OAuth token (oauth2) | OS keyring, service `google-colab-cli`, user `oauth_token`. Legacy `~/.config/colab-cli/token.json` is migrated then deleted. |
| Session state (tokens, endpoints) | `~/.config/colab-cli/sessions.json` (override `--config PATH`) |
| CLI settings (update check etc.) | `~/.config/colab-cli/settings.json` |
| Session history (for `colab log`) | `~/.config/colab-cli/history/<session>.jsonl` (docs/04) |

**What sign-in prints:** for oauth2, an authorization URL followed by a prompt to paste the code. Exact wording: not stated. For adc, nothing is stated.

**Required Google scopes** (docs/04):
- `https://www.googleapis.com/auth/userinfo.email` - REQUIRED. Without it assign/unassign/sessions return HTTP 401.
- `https://www.googleapis.com/auth/colaboratory` - kept for compatibility.
- `openid`, `https://www.googleapis.com/auth/cloud-platform` - required by gcloud.

Re-auth for adc user credentials:
```
gcloud auth application-default login --scopes=openid,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/colaboratory
```
Cached tokens minted before a scope change must be cleared to get a new consent (oauth2).

**Check identity:** `colab whoami` (hidden command) prints provider, email, audience, expiry, scopes.

---

## 2. Commands (one line each, options from README)

Global: `--auth {oauth2,adc}`, `-c, --client-oauth-config PATH`, `--config PATH`, `--logtostderr`. Run `colab <cmd> --help` for details.

**Session management**
- `colab new [-s NAME] [--gpu GPU] [--tpu TPU] [--high-mem]` - allocate a CPU/GPU/TPU VM.
- `colab sessions` - list active sessions on the backend.
- `colab status [-s NAME]` - hardware, machine shape, status, local metadata.
- `colab restart-kernel [-s NAME]` - restart the Jupyter kernel.
- `colab stop [-s NAME]` - terminate VM and release resources.
- `colab url [-s NAME] [--open]` - print or open a browser URL to the session.

**Execution**
- `colab run [--gpu GPU] [--tpu TPU] [--high-mem] [--keep] [-s NAME] [--timeout SEC] SCRIPT [ARGS...]` - fresh VM, run local script with args, release VM. (`-s`, `--timeout` per docs/05.)
- `colab exec [-s NAME] [-f FILE] [--output-image PATH] [--timeout SEC]` - run code from stdin, a local `.py`, or `.ipynb`.
- `colab repl [-s NAME] [--output-image PATH]` - interactive Python REPL; needs a TTY (piped stdin = one-shot).
- `colab console [-s NAME]` - raw bash (tmux-wrapped) on the VM; needs TTY or piped stdin.
- `colab ssh [-s NAME] [--proxy-mode] [-i KEY] [--gpu GPU] [--tpu TPU] [--high-mem]` - SSH shell or OpenSSH ProxyCommand for IDEs.

**Files**
- `colab ls [-s NAME] [PATH]` - list remote files.
- `colab upload [-s NAME] LOCAL REMOTE` - upload a file.
- `colab download [-s NAME] REMOTE LOCAL` - download a file.
- `colab rm [-s NAME] PATH` - delete remote file.
- `colab edit [-s NAME] PATH` - edit remote file via `$EDITOR`.

**Automation and utilities**
- `colab auth [-s NAME]` - Colab/GCP sign-in on the VM (interactive, for BigQuery/GCS).
- `colab drivemount [-s NAME] [PATH]` - mount Google Drive (default `/content/drive`); interactive consent.
- `colab install [-s NAME] [-r FILE | PKG...]` - install packages on the VM via uv (falls back to pip).
- `colab log [-s NAME] [-n N] [-o FILE]` - view or export history (`.ipynb`, `.md`, `.txt`, `.jsonl`).
- `colab usage` - compute-unit usage rate and balance.
- `colab pay` - open the Colab subscription page.
- `colab version` - print version.
- `colab update [--install]` - check for newer release; `--install` upgrades in place.
- `colab whoami` - hidden, developer-only identity/scope check.
- `colab README` / `colab AGENT` - print bundled README / AGENTS.md.

**Note:** `-s` is optional when only one session is active (README).

---

## 3. Sessions

- **Naming:** `-s/--session NAME`. Auto-generated `run-<6 hex>` for `colab run`. Naming rules for `new` (length, allowed chars): not stated.
- **Liveness:** the Colab backend keeps the VM alive based on kernel activity. The CLI has no keep-alive daemon (removed 2026-09-25).
- **Idle timeout:** the backend reclaims sessions for inactivity. Duration: not stated.
- **Max runtime:** not stated.
- **Reconnect:** a session persists until `colab stop` or backend reclaim. Use `colab sessions`, `colab status`, `colab url`, then `exec/repl/console -s NAME`. `colab run --keep` leaves the VM for reuse.
- **Token:** the runtime proxy token expires after about 1 hour. The CLI refreshes it automatically before commands that talk to the VM (within 5 min of expiry). Long-lived `repl`, `console`, `ssh` connections are NOT refreshed mid-session.
- **Kernel restart:** `colab restart-kernel` restarts the Jupyter kernel. Whether Python variables are lost: implied, not explicitly stated.
- **What survives a kernel restart / VM stop:** not stated for kernel state or files.
- **`/content` is ephemeral:** NOT explicitly stated in these docs. Assume files are lost when the VM stops. Drive mount persistence: not stated.
- **Stale local entries:** `colab sessions` / `status` sync and prune local entries no longer assigned.

---

## 4. Running long scripts

**Modes:**

| Command | Behaviour |
|---|---|
| `colab exec -f FILE` | Reads the local file, sends its code to the kernel. Waits for completion. Streams output. |
| `colab run SCRIPT ARGS` | Allocates new VM, runs script (sys.argv and `__name__=="__main__"` mirror `python script.py`), stops VM at end unless `--keep`. Exit code: non-zero on uncaught error; `sys.exit(N)` gives N. |
| `colab repl` / `colab console` | Interactive. Not for batch. |

**Timeouts (important):**
- `--timeout` on `exec` and `run` is an **IDLE limit**: fails only after that many seconds with NO output. Default **30 s**. `--timeout 0` = no limit.
- Print progress regularly; each output line resets the idle timer.
- `repl` and `install` wait without a timeout until done or kernel dies.
- HTTP timeout for backend calls: env `COLAB_CLI_REQUEST_TIMEOUT` (seconds, default 120 per AuthorizedSession). Does NOT change kernel timeouts.

**Background / detached execution:** NOT stated. No daemon is described. `colab run` is a foreground fire-and-forget process with no background threads.

**If the local terminal closes:** not stated. `colab run` tears down in a `finally` block, but whether that runs when the local process is killed is not stated. Do not assume the VM survives. Use `--keep` if you need the VM after the local process ends.

**Progress and logs:**
- Live progress: stdout of `exec`/`run`.
- `colab status -s NAME` - state (IDLE/BUSY from CLI bookkeeping).
- `colab log -s NAME -n N` - recent history; `-o FILE` exports `.ipynb`, `.md`, `.txt` or `.jsonl`.
- Script logs written to files on the VM: download them with `colab download`.

**Shebang:** `#!/usr/bin/env -S colab run --gpu L4 --keep` then `chmod +x`.

---

## 5. File transfer

| Action | Command | Notes |
|---|---|---|
| Upload | `colab upload [-s NAME] LOCAL REMOTE` | Single file in the README. Directory upload: not stated. |
| Download | `colab download [-s NAME] REMOTE LOCAL` | Single file in the README. Directory download: not stated. |
| List | `colab ls [-s NAME] [PATH]` | |
| Delete | `colab rm [-s NAME] PATH` | |
| Edit | `colab edit [-s NAME] PATH` | Downloads, opens `$EDITOR`, uploads if hash changed. |
| Run local code on VM | `colab exec -f file.py` | Code is sent directly, no upload needed. |
| Size limits | Not stated (design doc notes the Contents API "may have limitations" for large files, with a planned kernel-streaming fallback; not confirmed as implemented). |
| MP4 handling | Not stated. No special handling documented. Treat as a binary download. |
| Images from exec | `--output-image PATH` saves image output (Kitty protocol inline only when stdout is a TTY). |

Windows paths: not applicable (CLI is not supported on Windows).

---

## 6. GPUs, TPUs, tiers, billing

**Accelerators:**
- GPU: `T4`, `L4`, `G4`, `H100`, `A100` (README). The design doc also lists `V2-8` for TPU.
- TPU: `v5e1`, `v6e1` (README). Design doc: `V2-8`, `V5E1`, `V6E1`.
- Which accelerators need Colab Pro / Pro+: **not stated per accelerator**. Docs say `--high-mem` needs Pro/Pro+ "for supported accelerators (CPU, T4, A100, etc.)". Quota is per account (demos.md), so requests may fail.

**High-memory:** `--high-mem` on `new`, `run`, `ssh` (auto-create). Sends `shape=hm`. Ignored for L4 and TPU (single shape). Shape shown in `colab sessions` and `colab status`.

**Compute units:**
- `colab usage` - current balance (compute units), usage rate per hour across assigned VMs, active assignment count.
- `colab pay` - opens `https://colab.research.google.com/signup` in the browser.
- Burn rate per accelerator type: not stated.

**Avoiding wasted units:**
- Always `colab stop -s NAME` when done. `colab run` stops automatically unless `--keep`.
- Check `colab sessions` for forgotten VMs.
- Idle VMs are reclaimed by the backend for inactivity, but the idle time before that is not stated and may still bill.

---

## 7. Limits, platform, errors

**Platform:** Linux and macOS only. Windows is NOT supported (README). A 2026-06-10 change fixed a Windows crash in the state store, but this does not make Windows supported. WSL: not stated. Plan to run from a Linux VM, WSL, or a Mac (WSL untested).

**Known limits:**
- Sessions: no max runtime stated. Idle timeout not stated.
- Exec/run idle timeout default 30 s.
- Token lifetime 1 h (auto-refreshed for normal commands only).
- Interactive commands (`repl`, `console`) need a TTY.
- Quota per account (demos.md).
- Long-lived `repl`/`console`/`ssh` do not refresh the token.

**Errors and fixes (from docs):**

| Symptom | Cause (docs) | Fix |
|---|---|---|
| HTTP 401 on assign/unassign/sessions | Missing `userinfo.email` scope | Re-auth with the scope list in section 1; clear cached token (oauth2). |
| `TooManyAssignmentsError` (HTTP 412) | Too many concurrent assignments | `colab sessions`, `colab stop` unused sessions. |
| HTTP 502/503/504 or ReadTimeout on new | Backend hiccup | Auto-retried 3x with 10/20/40 s backoff. Tune `COLAB_CLI_ASSIGN_RETRIES`, `COLAB_CLI_RETRY_BACKOFF`. |
| `TimeoutError` / "no output" from exec or run | Idle timeout 30 s | Print progress, or `--timeout 0` / larger value. |
| Keyring locked warning (Linux) | SecretService locked | Unlock keyring, or use `--auth=adc`. |
| Keyring failures on stderr | Keyring inaccessible | Token re-requested each run. Use `--auth=adc`. |
| `redirect_uri_mismatch` | Custom OAuth client not registered for the redirect URI | Use bundled client, or register a custom one. |
| `OOB flow has been blocked` | Old OOB redirect | Not used any more. |
| `USER_PROJECT_DENIED` 403 | Old keep-alive RPC (fixed 2026-06-15) | Update CLI. |
| `colab console` piped hang | Fixed 2026-05-07 | Update CLI. |
| Kitty escape codes in captured output | Fixed 2026-05-07 (no-op when not a TTY) | Update CLI. |

---

## 8. Tips for a ~1 hour batch render (Python script to MP4)

Based on the docs. Items marked (untested) are our suggestions, not from the docs.

1. **Set the idle timeout.** `colab run ... --timeout 0`, or `colab exec ... --timeout 0`. Default 30 s will kill a silent render.
2. **Print progress often,** with `flush=True`. Each line resets the idle timer and gives `colab` something to show.
3. **Two-step is safer than `run`.** `colab new -s render --gpu T4`, then `colab install -r requirements.txt` (or `colab install PKG...`), then `colab upload` the script and assets, then `colab exec -s render -f render.py --timeout 0`. Whether the VM survives a dropped local terminal is not stated; see tip 4.
4. **Plan for local disconnect.** Docs do not say whether a local kill tears down the VM. Use `--keep` with `colab run` or the two-step flow, then reconnect with `colab exec -s render ...` or `colab log -s render`. Running the render detached on the VM (tmux or nohup): not stated; untested.
5. **Write outputs to a fixed folder,** e.g. `/content/out/`, and name files predictably. Use `colab ls -s render /content/out` to check.
6. **Bring MP4s home one by one.** `colab download -s render /content/out/NAME.mp4 ./out/NAME.mp4`. Directory download is not stated, so loop over `colab ls` output or zip on the VM first (zip works through exec with Python `zipfile`, as in demo 9).
7. **Verify before stopping.** Download, check file size and playability locally, then stop the VM.
8. **Always stop.** `colab stop -s render`. Check `colab usage` before and after to confirm units stopped burning.
9. **Check budget before starting.** `colab usage` for balance and rate. A one-hour GPU run should be estimated against this rate (rate per type: not stated).
10. **Keep the script re-runnable.** Skip finished clips on restart, because a dropped session loses VM disk (not stated, assume lost).
11. **Use `colab log -s render -o render_log.md`** to archive the session output for the team.
12. **Run from Linux, macOS, or WSL (untested), not native Windows.**

---

## Notes on doc conflicts and gaps

- Default auth: README says `adc`, docs/04 says `oauth2`. Verify with `colab --help`.
- `colab log`: docs/04 describes `colab log list` and `colab log show`, README shows `-n` and `-o`. Verify.
- docs/04 says `colab install` uses `uv` then `pip`; the README adds `-r FILE`.
- Several design docs are dated changelogs; behaviour may have changed since. Re-check against the installed version (`colab version`).

## 9. VERIFIED ON THIS PC (Claude, 2026-11-05) - these override any doc statement above
- Install: `uv tool install google-colab-cli` (v0.7.5) works on WINDOWS in an isolated tool env; binary `C:\Users\Satvik\.local\bin\colab.exe`. WSL Ubuntu here has no internet, so WSL install failed.
- Sign-in: first command prints a Google link; approve with the Colab Pro account; the code must be pasted into the SAME running terminal (each attempt has its own PKCE secret; a code from another attempt gives "Bad Request"). Login is then saved; later commands need no sign-in. Scopes asked: openid, userinfo.email/profile, cloud-platform, colaboratory, drive.file.
- NEVER use `--logtostderr`: it prints the `Authorization: Bearer ya29...` token and the runtime proxy token into the output.
- `colab usage` -> balance 199.91 units (Colab Pro plus the Google AI plan units), rate 0.08/hr, "Active assignments: 1" (an idle CPU session `m-s-ase1a8-...` exists, ~0.08 units/hr).
- `colab new -s NAME --gpu G4` WORKS on this account: allocation took ~55 s; GPU = NVIDIA RTX PRO 6000 Blackwell Server Edition, 97,887 MiB VRAM, compute cap 12.0, driver 580.82, host RAM ~185 GB, /content disk ~235 GB free.
- `echo 'python code' | colab exec -s NAME` runs code; `colab stop -s NAME` ends billing. A first `colab new` with no --logtostderr printed only "Creating session" for several minutes and, when run under `timeout`, was killed before the session existed (nothing was billed, balance 199.91 -> 199.90). Give `new` 2+ minutes.
- ALWAYS stop sessions the moment work ends. G4 rate is about 8.7 units/hour (estimate from third-party notes, not measured here).
- `exec --timeout` is an IDLE limit (default 30 s): pass a large value or print progress.
