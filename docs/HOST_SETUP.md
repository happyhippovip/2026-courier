# Host setup: one line per machine

`scripts/setup/courier-setup.sh` (macOS) and `scripts/setup/courier-setup.ps1`
(Windows) prepare a machine for Courier. You paste one line, and the script
checks the machine, installs missing light tools for your user only, clones
the repository, writes a host config, and registers the Courier worker
without starting it. At the end it prints a short report and copies it to
the clipboard so you can paste it into the chat.

## The two lines

macOS (Terminal, normal user):

```
curl -fsSL https://raw.githubusercontent.com/happyhippovip/2026-courier/lane/L6-host-setup/scripts/setup/courier-setup.sh | bash
```

Windows (PowerShell, normal window, not "Run as administrator"):

```
irm https://raw.githubusercontent.com/happyhippovip/2026-courier/lane/L6-host-setup/scripts/setup/courier-setup.ps1 | iex
```

Once this branch is merged, replace `lane/L6-host-setup` with `integration/v1`.

## Flags

| Flag | Effect |
|---|---|
| `--check` | Doctor only. Nothing is written, installed, registered or copied. |
| `--with-godot` | Also install Godot 4: Homebrew cask into `~/Applications`, or winget user scope. Off by default. |
| `--uninstall` | Remove the worker registration (see below). Checkouts, config and data stay. |

Passing flags through the pipe:

```
curl -fsSL <raw>/scripts/setup/courier-setup.sh | bash -s -- --check
$env:COURIER_SETUP_ARGS='--check'; irm <raw>/scripts/setup/courier-setup.ps1 | iex
```

A saved copy also takes `-Check`, `-WithGodot` and `-Uninstall`:
`powershell -File courier-setup.ps1 -Check`.

## What it does, in order

1. **Doctor.** OS, CPU, RAM total and free, free disk, swap (macOS) or
   pagefile (Windows), git, Python 3.12, `gh` and whether it is signed in
   (yes/no only), the `muse` version, whether `agy` and Godot are present,
   the number of running Courier processes, and the number of dirty
   worktrees under `~/Courier`. Worktrees inside Desktop, Documents or
   Downloads are counted as skipped and never opened.
2. **Prerequisites, user scope only, and only when missing.**
   - macOS: `git`, `python@3.12` and `gh` through Homebrew, with auto-update
     and cleanup turned off. Homebrew itself is not installed, because its
     installer asks for an admin password. Without the Xcode Command Line
     Tools and without Homebrew the run reports BLOCKED and names the fix.
   - Windows: `Git.Git`, `Python.Python.3.12` and `GitHub.cli` through
     `winget --scope user`. A package without a user-scope installer is
     skipped and reported; nothing asks for elevation.
3. **Repository.** `~/Courier/2026-courier` (`%USERPROFILE%\Courier\2026-courier`)
   on `integration/v1`. A clean checkout of that branch is fast-forwarded. A
   checkout with local changes, local commits, another branch or another
   remote is left exactly as it is and a fresh sibling clone is used:
   `2026-courier-host`, then `2026-courier-host-<UTC time>` if that one is
   also in use.
4. **Host config.** `~/Courier/host-config.json` with resource admission:
   at most **one heavy builder**, and new work is parked when free RAM is
   below 2048 MB, swap/pagefile free is below 1024 MB, disk free is below
   10 GB, or metrics cannot be read. Running work is never stopped by
   admission. On macOS a swap total of 0 means no swap is in use and does
   not park. No runtime reads this file yet; wiring a consumer is a
   follow-up.
5. **Worker registration**, through the existing installers, never started:
   - macOS: `scripts/mac_worker/install.sh` is called with
     `COURIER_NO_START=1` and `PYTHON_BIN=<python 3.12>`. The setup calls it
     only when the installer in the checkout supports that no-start mode
     (job written with `RunAtLoad` and `KeepAlive` false, an already loaded
     job left alone). Today's installer loads the job and starts the worker
     at once, so until the no-start mode lands the setup skips this step
     and reports PARTIAL. A job that is already loaded is left alone. An
     existing job file that is not loaded may belong to another install and
     is not replaced.
   - Windows: `scripts/windows_worker/install_service.ps1` registers the
     `CourierWindowsWorker` logon task for the current user with
     `RunLevel Limited`. It is not started now. The setup only calls the
     user-level installer; a checkout whose installer registers a SYSTEM
     boot task (needs admin) is skipped and reported as PARTIAL. An existing
     task of another account is left untouched.
6. **Report.** `~/Courier/setup-report.txt`, printed and copied to the
   clipboard. The report has no user name, home path, host name, e-mail
   address or token: paths are shown relative to `~`, the host name is
   replaced by `h-` plus 12 hex characters of a SHA-256 hash, and the text is
   filtered for token and e-mail shapes before it is shown, written or
   copied.

The last line is `HOST READY`, `HOST PARTIAL` or `HOST BLOCKED`.

| Result | Meaning | Exit code |
|---|---|---|
| HOST READY | Git, Python 3.12, checkout, host config and worker registration are in place. | 0 |
| HOST PARTIAL | Usable, but something was skipped; the `next:` lines say what. | 2 |
| HOST BLOCKED | A required step could not run (wrong OS, admin window, no git, clone failed). | 3 |

Under `irm | iex` the code is in `$LASTEXITCODE`; the window stays open.
`gh auth`, `muse` and `agy` are reported but never configured: signing in is
yours to do.

## Uninstall

- macOS: delegates to `scripts/mac_worker/uninstall.sh`, which unloads the
  launchd job and removes its job file. It refuses when the worker is
  running or when the job points outside `~/Courier`.
- Windows: `scripts/windows_worker/uninstall.ps1` needs admin and also
  removes the program folder, so the setup does not run it. It removes only
  this user's `CourierWindowsWorker` task, and refuses when the task is
  running or belongs to another account.

## Safety rules the scripts follow

- No elevation of any kind: no `sudo`, no "Run as administrator", no UAC
  prompt. A PowerShell window that already runs as administrator is refused.
- No permission, ownership, ACL, registry, Defender, firewall or sandbox
  changes, and no permission-skipping flags for any agent CLI.
- No process is stopped or signalled. Nothing is deleted, stashed, reset or
  cleaned. Files the script did not write (host config, report) are never
  overwritten.
- No credential, token or browser session is read, printed or copied
  between machines.
- Desktop, Documents and Downloads are never opened.
- Unknown state fails closed with a message.
- On Windows the saved installer runs in a child process with
  `-ExecutionPolicy Bypass`, which applies to that process only; machine and
  user policy are not changed.

## Overrides for testing

`COURIER_REPO_URL` and `COURIER_BRANCH` choose another repository or branch.
`COURIER_SETUP_UNAME` (macOS script) and `COURIER_SETUP_OS` (Windows script)
let the tests run the scripts with stub tools on Linux.
