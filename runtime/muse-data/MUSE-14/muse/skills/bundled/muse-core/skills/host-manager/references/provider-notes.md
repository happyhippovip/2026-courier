# Verified provider behaviours, by version

What the helper relies on, checked against the real tools rather than
assumed. Each row says the version it was checked on. When you meet a
different version, re-check the row before trusting it, and add the new
version beside the old one instead of overwriting it — the point of this
file is that a behaviour can change under you.

## tmux 3.7b (Linux)

| Behaviour | Verified |
| --- | --- |
| `tmux -V` prints `tmux <version>` on stdout | yes |
| `new-session -e KEY=VALUE` sets a session's environment | yes — arrived in tmux 3.2; on an older server the helper prefixes `env KEY=VALUE` to the command instead |
| `new-session -s <name>` refuses an existing name (`duplicate session: <name>`, exit 1), live pane or not | yes — so a taken name is another session's, and `open` picks the next free one unless `--exact-name` |
| `list-panes -a -F '#{session_name}\t#{pane_dead}\t#{pane_current_path}\t#{pane_current_command}\t#{window_active}\t#{pane_active}'` is one line per pane | yes — so the helper folds the lines into one row per session (QA r8 HM2 D3: a split session showed eleven rows) |
| `#{pane_current_command}` is the running process's name (`muse`), not the path it was started with | yes — so an engine recorded as a path matches by basename |
| `#{pane_current_path}` reads `<path> (deleted)` once the pane's directory is removed under it | yes — verified 2026-09-20 (`rmdir` under a live pane); the cwd identity check treats it as `<path>` when no directory of that literal name exists |
| An empty server answers `no server running on <socket>` (exit 1) | yes — that is zero sessions, NOT unreadable evidence |
| A socket that refuses answers `error connecting to <socket>` | yes — that IS unreadable evidence (exit 6) |
| `-t =<name>` targets one exact name (without `=`, tmux prefix-matches) | yes |
| A private server (`-L`/`-S`) reads the operator's `tmux.conf` unless `-f` is given | yes — the helper appends `-f /dev/null` to a private server it starts |
| `load-buffer -b NAME -` reads a buffer from stdin; `paste-buffer -d -p -b NAME -t =<name>:` pastes it into the pane as one paste and deletes the buffer | yes — verified 2026-09-19 with a two-line body; `send`'s `--type` uses this pair, then one `Enter` |
| `send-keys -l -- TEXT` and `display-message -t =<name>: -- TEXT` take a TEXT that starts with `-` after `--` | yes — verified 2026-09-19; the notification path passes `--` |
| `display-message` reads its message as a FORMAT: `#S` expands, `#(cmd)` forks a shell, `##` is a literal `#` (`-l` exists only from tmux 3.4) | yes — verified 2026-09-19 (`'issue ##S ####lit'` prints `issue #S ##lit`); `send`'s notification path doubles every `#` |
| `capture-pane -p -J -S -N` returns the last N scrollback lines plus the visible screen | yes — `read` caps N at 5000 |

## Herdr 0.9.0 (Linux, protocol 22)

| Behaviour | Verified |
| --- | --- |
| `herdr status --json` answers `server.running`, `server.socket`, `server.version` without being inside a pane | yes — this is how the helper finds the server from outside |
| `herdr session list --json` lists named sessions with `socket_path` and `running` | yes — a named session's socket lives under `~/.config/herdr/sessions/<name>/` |
| `herdr server` runs a headless server and keeps running; it prints its api/client socket paths | yes |
| Every socket verb answers `{"id": …, "result": {…}}` on stdout; errors are `{"error": {"code", "message"}}` on stderr with exit 1 | yes |
| `pane run` answers nothing on success | yes |
| `herdr pane list` **without** `--workspace` returns only the current workspace's panes | yes — a lookup across workspaces asks per workspace |
| `workspace create --cwd D --label L --no-focus` answers `workspace`, `tab` and `root_pane` | yes |
| A workspace created outside a repository carries **no** `worktree` record; one created in a repository carries `worktree.checkout_path` and `repo_root` | yes (no current consumer: `open` looks nothing up by directory) |
| `worktree create --branch B --path P` makes the git worktree and a workspace for it | yes — `git worktree list` shows the checkout afterwards |
| `pane process-info --pane <id>` answers `shell_pid` and `foreground_processes` | yes — an answer with no readable process list means the tty could not be read, which is unreadable evidence, never "idle" |
| `agent list` answers `agent`, `agent_status`, `cwd`, `pane_id`, `tab_id`, `workspace_id` — for the panes whose command Herdr's detection recognises ONLY; a `python3 -i`, or a Muse binary not named `muse`, is absent | yes — verified 2026-09-19 on a private server (QA r8 HM2 D1), so the session table is built from the recorded panes and `agent list` only enriches it |
| `pane get <id>` / `pane list --workspace W` rows carry `agent` and a real `agent_status` only for a detected agent; an undetected pane has no `agent` key and `agent_status: unknown` | yes — verified 2026-09-19 |
| `pane get` reports `cwd` as `<path> (deleted)` once the pane's directory is removed under it | yes — verified 2026-09-20 on a private server (`rm -rf` under a live pane); same identity rule as tmux |
| `workspace close <id>` ends every pane in the workspace (their processes too) and removes it; a missing id is `workspace_not_found` | yes — verified 2026-09-19; `close`/`stop` use it for the workspace `open` created |
| `tab close` of a workspace's last tab removes the workspace on a headless server; with a UI client attached Herdr re-seeds a root tab instead, so the workspace stays | yes (headless, 2026-09-19) / observed by QA r8 RND on the desktop server — which is why `close` asks for the workspace itself |
| `agent start <name> --kind muse --pane <id>` returns `agent_not_ready` (exit 1) when the agent is blocked at startup — Muse's trust prompt does this — and the name still resolves for `agent read` / `send-keys` | yes, measured at ~3.6 s |
| `agent prompt … --wait` requires an observed `working`/`blocked` state within 5 s of submission, else `agent_prompt_stalled` | per the CLI's own documentation; not yet exercised here |
| `notification show` answers `{"reason": "disabled", "shown": false}` with exit 0 when notifications are off | yes — a delivered notification is not a read one |
| Pane, tab and workspace ids are opaque (`w6:p1`) and are **not** reused after a close; a server restart keeps the workspaces and keeps counting (next pane `w1:p7` after `herdr server stop` and a restart, QA r9 HM); only a fresh server state starts from `w1` again | yes — re-verified 2026-09-20; which is why a session's identity is a tuple, not a ref |
| Nested Herdr is refused by default (`nested herdr is disabled`) | yes |
| `pane run <pane> <command>` types a command line into the pane's shell and runs it (it is how `open` starts its launcher) | yes — the helper's `send --type` into a shell session (`--engine bash`, a hand-made pane asked for by id) uses it; an agent's composer keeps `agent prompt` |
| `pane send-keys` takes tmux-style key names: `c-c`, `enter`, `esc`/`escape` are accepted; `ctrl-c` is refused with `invalid_key` — and so is Ctrl-D in every spelling (`c-d`, `C-d`, `ctrl-d`: `unsupported key`) | yes — re-verified 2026-09-19 on a private server; the helper's generic quit gesture (`c-c` then `c-d`, Codex and shells) therefore stops at the refused second key and ends the session by the linger close instead; Claude Code's own table (`c-c` twice, then `/exit` through `agent prompt`) needs no Ctrl-D |
| `pane read --source visible` shows the agent's composer line (Muse draws `❯ <text>` inside a box, with the model line below it) | yes — so the composer guard reads the LAST prompt-glyph line, not the last line |

## Herdr 0.9.1 (Linux)

| Behaviour | Verified |
| --- | --- |
| A prompt submitted over half-typed composer text merges with it and submits both | yes — which is why `send --type` refuses a non-empty composer (`composer_not_empty`) instead of typing |

## Muse (the engine), 1.3.0

| Behaviour | Verified |
| --- | --- |
| `muse session-message send --target <id>` refuses a session that has not messaged this one first: `session-message send failed: unverified_target_receipt` (exit 1) | yes — verified 2026-09-19, so `send`'s peer path reaches a session that opened the conversation; `send --type` is the unattended path |
| `muse session-message list --json` reports `workspace_label` per session; two sessions in directories of the same name share a label | yes — `send` then answers `peer_unresolved` and asks for `--session` |

## What is not verified here

- macOS: the helper's Homebrew install arm and Herdr on macOS have not been
  exercised on this machine.
- Windows: reports `no_provider`; nothing is emulated and nothing is
  measured.
- Remote machines: out of scope for host-manager, which manages this machine
  only.
