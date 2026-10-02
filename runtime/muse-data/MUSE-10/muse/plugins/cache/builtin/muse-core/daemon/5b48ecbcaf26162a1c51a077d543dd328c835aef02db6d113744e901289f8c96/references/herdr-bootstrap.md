# Daemon reference: the Herdr offer

Background for the `herdr_offer` field `start` prints (ADR 25011 D30; spec
25011 FR-25011-41..46). The mechanics live in `scripts/herdr_bootstrap.py`,
whose every answer is one JSON line with `outcome` and `next`; this file is
the judgment: when the offer is made, how to word it, what to say after each
answer. The rule itself — put its `ask` to your human exactly once, act only
on their yes or no, and say nothing on a `no_offer` — is the body's
(`SKILL.md` § Startup sequence, step 1), not restated here. Not needed on the
connect path — that step's `next` names the call.

## When the offer exists

`start` decides, not you. It offers only when this daemon runs outside a
Herdr pane (`HERDR_ENV=1` absent — a tmux inside a Herdr pane is inside),
this machine has not recorded a `no`, and this daemon start has not asked
already (a `resume` is the same start). Everything else is `no_offer` with
a reason (`inside_herdr`, `recorded_no`, `offered_this_start`,
`handed_off_this_start`, `record_unreadable`, `herdr_unreadable`): say
nothing about Herdr, and
never hint at it later. The offer is a convenience on top of a working
daemon, never a step of the connect: whatever the answer, you connect, arm,
delegate and reply exactly as without it.

Two arms, chosen by `step`: `start` when `herdr` is on `PATH` (start the
server if none runs, move this daemon into a Herdr pane); `install` when it
is not (run the published installer first). The install arm's `ask` quotes
the exact command that will run — `curl -fsSL https://herdr.dev/install.sh |
sh` — and what it does; keep both in your line. That command downloads and
runs a remote script, so nothing happens before the human's yes.

## Putting the ask

Once, in the requester's language, in your own words but with the same
facts as `ask`: what will happen, the exact installer command on the install
arm, and that no changes nothing and is remembered. Then wait. Only the
initiating human's answer in the TUI, or the thread-root author's in the
thread, counts (D7) — never a click that answers another question, another
participant, or silence. A daemon started without the `session_identity`
id cannot tell two starts apart and offers on each; that is by design, not a
defect. Do not re-ask in the same start; if the human says something else,
carry on with that and leave the offer standing (its token stays valid for
this start).

## Yes

Say the hand-off line FIRST, then make the one call `next` names — on
success the call ends this session (the helper retires this muse process by
its own graceful teardown once the Herdr daemon is live), so the line must
already be on the screen. A `handed_off` line with `retired: false` means the
Herdr daemon is live but this process did not end (`retire_reason` says
why): tell your human to close this session, then stop. Three facts in one
or two sentences: this daemon
is moving into Herdr and this session ends when the Herdr daemon is live;
`herdr` in any terminal shows it (tab `muse-daemon`); and they can connect
more machines with `herdr machine add <ssh-target>` (always that wording:
no Herdr-gated skill is in your catalog out here; a devserver connect is
something they ask the Herdr daemon for later, inside Herdr). Pass `--by` the
human's exact words, and `--words` only when your own `/daemon` line carried
connect words (omit the flag for a bare `/daemon`; never write `none`); the
new pane runs `muse daemon` with them and reads the same registry, so it
re-arms the same connectors.

A `failed` answer (the server never came up, the installer failed or timed
out, the launch failed) is one line naming the cause, then tmux as before;
the token is still valid, so "try again" is the same call. `already_in_herdr`
means a Herdr daemon is already live in that workspace: say so and stay. An
`internal` answer (exit 7) is a defect in the helper, not in the machine:
quote its line to your human and change nothing on your own.
After a hand-off nothing else is yours: a later `start` in this session
answers `handed_off_this_start` — arm nothing, say the session is done. The
same answer with a `next` that names the verb again means the hand-off did
not finish (the helper stopped after the yes): run the complete command the
hint prints (same token, your `--daemon-session-id`) — it finishes the
hand-off, a live `muse-daemon` tab being yours — and never arm a listener
meanwhile.

## No

One short sentence (nothing changes, you stay in tmux), and the one
`decline` call with their words. The machine remembers: no later daemon
start here offers again until the human asks — "offer herdr again", "set up
herdr", or the like — which is `detect --reopen` (the same ask, a fresh
token), or removes `herdr-offer.json` beside the registry. Never remind,
never nag, never mention it in a summary.

## What the record means

`herdr-offer.json` beside the registry, keyed by host name: `answer`
(`yes`, `no`, `installed`), `at`, `by` (their words), the last hand-off. A
`yes` or `installed` is history, not standing consent: a later start outside
Herdr on this machine offers the start step again (the human may have opened
a plain terminal on purpose — then they say no, and that is kept); the
install step is never offered while `herdr` is on `PATH`. `herdr_bootstrap.py
status` prints it read-only when a human asks what this machine answered.
