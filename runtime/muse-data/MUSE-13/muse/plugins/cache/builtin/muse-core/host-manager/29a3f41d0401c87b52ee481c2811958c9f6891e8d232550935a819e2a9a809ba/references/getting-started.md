# From nothing to your first session, in five steps

You need a machine with Python 3 and a terminal; Herdr and tmux need not be
installed yet. How to run the helper (the real skill directory, from the
repository you want the session in or with `--cwd`, global flags before the
verb) is in `SKILL.md` § Run it; below, `<skill-dir>` is that directory.
Every command answers one JSON line whose `next` is the command to run now.

## 1. Ask what this machine can do

```
python3 <skill-dir>/scripts/lane_runtime.py doctor
```

`provider` is what your sessions will run in, `checks` is what it looked
at. `doctor` changes nothing: with no tmux, `install` names the rung
`open` will take (`would_run`), and `needs_user_action` with a `command`
means no rung can do it without asking you (`install.detail` says why) —
run that command yourself, then `doctor` again.

## 2. Open a session

```
python3 <skill-dir>/scripts/lane_runtime.py open
```

No arguments needed: engine `muse`, the repository you are standing in, a
name from that directory; one `progress` line per step and a `receipt` at
the end. Useful options: `--name mine`, `--cwd /path/to/repo`,
`--engine claude`, `--purpose "review PR 42"`, `--prompt-file starter.txt`
(`-` for stdin), `--dry-run` to see what would run without starting it.

## 3. See what is running

```
python3 <skill-dir>/scripts/lane_runtime.py context
```

Providers, every session with its `group` (`working`, `idle`,
`waiting-on-you`, `gone`), resources, and `changed` since you last asked.

## 4. Take a session over

```
python3 <skill-dir>/scripts/lane_runtime.py attach <name>
```

Prints the exact command for your provider (`tmux attach -t =<name>` with
the server flags the helper ran with, or `herdr agent attach <pane>`). Run
it yourself; the helper never takes your terminal, and it refuses when the
session behind that name is not the one it opened.

## 5. Leave it, or end it

Detach with your provider's own key (tmux: `ctrl-b d`); the session keeps
running. Ending one is deliberate and never implicit:

```
python3 <skill-dir>/scripts/lane_runtime.py stop <name>                          # the engine's own quit, then close
python3 <skill-dir>/scripts/lane_runtime.py close <name> --confirm "yes, close it"  # end it now
python3 <skill-dir>/scripts/lane_runtime.py forget --mode tmux --ref <name>   # drop the record once it is gone
```

`read <name>` shows what a session is doing; `send <name> --text "…"`
delivers a message beside it; `adopt <name>` records a session you started
by hand.

---

# When something goes wrong

**`needs_user_action`, `tmux is not installed`** — from `doctor`/`detect`
with `install.rung` other than `needs_user_action`: run `open`, it installs
tmux first (no password prompt). Otherwise Homebrew, passwordless `sudo -n`
and a user-space copy under `~/.local/opt/tmux` all failed (`install.detail`
says why each did); the helper never prompts for a password. Run the
command in `command` yourself, then `doctor` again.

**`no_provider`, Windows** — there is no session provider on Windows and
nothing is emulated. Use this skill from macOS, Linux, or WSL.

**`provider_unreachable`** — Herdr is installed but its server did not
answer even after the helper tried to start it. Start it yourself
(`herdr server`, or the Herdr app), or run the verb with `--mode tmux`.

**`herdr_context_unverified`** — this looks like a Herdr pane but the
server could not confirm it, so nothing was started. Fix the Herdr
connection, or state the provider with `--mode tmux`.

**`unsupported_by_provider`** — this provider cannot do that (a worktree on
tmux, for instance). `next` names the alternative.

**`identity_mismatch`** — the session behind that name is no longer the one
this helper opened; `error` names the field that moved (usually `cwd`). Run
`list` and use the ref you actually meant.

**`no_such_session` on a session you just opened** — it lives on a private
tmux server and this call did not carry the same `--tmux "tmux -L <socket>"`
prefix (or the `MUSE_*_TMUX` variable that set it). Repeat with the prefix
from the `open` receipt's `server`; the session is not gone.

**A dialog is on the screen** (workspace trust, a permission prompt) and
`send --type` refused with `agent_blocked`, `composer_not_empty` or
`composer_unreadable` — a person answers it: `read <name> --tail`, tell the
user what is asked, and give them the `attach` command. Never answer it
with raw `tmux send-keys` or `herdr pane send-keys`.

**`failed`, the session died at once** — the engine exited inside the
grace window. The line names the engine and its arguments; `--dry-run`
builds the exact command and starts nothing.

**The ledger warning** — `~/.muse/host-manager/sessions.json` could not be
written. Sessions still open; they are just not remembered. Fix the
permissions on `~/.muse` when you want the record back.
