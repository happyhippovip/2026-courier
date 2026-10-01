# Projects: the daemon's third tier

Read off the hot path. The dispatch rule is stated once (`daemon/SKILL.md` § Event loop): `--project` rides the one `delegate`. This file says why it is shaped that way and what the helper does.

## Two gates, four shapes (#38715; ADR 38715 D7 as amended by Amendment 1)

| tag | agents | what exists |
| --- | --- | --- |
| tag off, agents off | — | nothing: no daemon, no `agents` skill |
| tag off, agents on | — | an external user has `host-manager`, `fleet-manager`, `agents`; no daemon |
| tag on, agents off | — | today's daemon under `auto` or `thread`: every hand-off is a thread; the Slack starter, the receipts and the registry rows are byte-identical to the shape before projects existed (`test_slack_byte_identity.py`; `test_projects.py`); only a recorded `project` opens the project path |
| tag on, agents on | — | the daemon SIZES each non-immediate ask: a bounded task is a thread, a goal is a project |

The daemon is visible under `MUSE_EXPERIMENTAL_TAG` only; whether a goal
becomes a project depends on the `agents` gate (`MUSE_EXPERIMENTAL_AGENTS`)
alone. The helper reads the gate itself and `start` reports it as
`agents_gate: open|closed` — never the catalog: under `tag` the three
external skills are always listed (ADR 38715 D15), so their presence says
nothing. A `--project` under a closed gate is `skipped (agents_gate_closed)`
and the lane is an ordinary thread coordinator. No environment knob decides
delegation: the setting below is per daemon, recorded.

## The three tiers

The judgment is yours, per ask, and no number decides it:

- **do it now** — the immediate path: a greeting, a bounded question you can
  answer from what you know (daemon/SKILL.md, Event loop step 2);
- **a thread** — one executor, one conversation, no memory to keep: today's
  `delegate` (a conversation coordinator that does the work itself or fans
  out inside its lane);
- **a project** — a goal: several PRs to open, land or follow (review, CI,
  merge), more than one independent slice, several sittings, decisions and
  memory worth keeping.
  Several fixes that one PR can carry are a thread even when they come as
  a list ("fix these three findings, open one PR"); a bounded ask (one
  question, one file, one command) is a thread. The words of the ask do
  not decide the size — the shape of the work does — except when the
  requester asks for the shape: asking for agents, threads, lanes or a
  project as the means (not as the subject) makes it one by request,
  whatever its size — "summarize the comment threads on this PR" names
  no shape. The same one
  `delegate` plus `--project`: `python3 <connector-script> delegate --to
  <lane> --text "<ack>" --project`; a bare `delegate` for such a goal makes
  a lane that does the work itself, with no threads and no wake.

## `set delegation auto|thread|project`

A per-daemon setting, recorded privately beside the registry
(`delegation.json`, 0600), read by `start` (its `delegation` field; the
summary says `· delegation thread` when it is not `auto`) and by every
`launch`:

- `auto` (default) — the tiers above: a project when you pass `--project`
  and the gate is open;
- `thread` — every hand-off is a thread; `--project` is `skipped
  (delegation_thread)` — the Monday shape, chosen by hand;
- `project` — every hand-off opens a project (a launch that did not pass
  `--project` still gets one), and this wins over a closed gate: the human
  asked for it and the three skills are visible under `tag` (D15); `set`'s
  line says so.

The human says it in this terminal ("set delegation thread"); your one call
is `python3 scripts/daemon_registry.py set delegation <mode>`, and its line
says what the mode means. The byte-identity promise holds for `auto` and
`thread`.

## What `--project` does (the registry's `launch`)

After the row guards and before the handoff is written, ONE call to the
external skill's helper, a sibling of this one:
`../agents/scripts/agents.py init --slug <first words> --unattended
[--asked-by <their name>] -- <the requester's line>` (the line is ONE argv
token after `--`, so a flag-shaped word in it is never an `init` flag) in
the daemon's workspace
(`MUSE_PROJECTS_HOME` passes through; the folder lands under
`~/.muse/projects/<slug>/`). `--unattended` is the internal lanes' posture,
passed explicitly — the external default is the engine's own prompts. A
taken slug is retried once with the handoff's six-character suffix. Nothing
Slack-shaped reaches the agents helper: the task, a slug, who asked, the
posture.

On `initialized` the handoff gains `project: {slug, path, channel,
agents_script}` and the starter tells the coordinator it IS that project's
coordinator and that this conversation is the project's channel. The
starter carries the coordinator rules in the agents skill's own sentences
(the listener armed first — none under native connector delivery — then
`resume <slug>`: the folder records the helper's process as the coordinator
at `init` and `resume` re-records the lane; then the turn protocol); the
full rules are the agents skill's `SKILL.md` (an unclear goal: its § 2 runs
the grill skill's interview before any plan), not restated here. The
receipt's `project` is `{"outcome": "created", "slug", "path"}`
and your line ends `· project <slug>`.

One coordinator per project: the conversation coordinator. The daemon never
becomes one, never messages one, never reads the folder; the agents skill's
own `resume` refuses a second live coordinator.

## Keeping the requester informed (ADR 38715 Amendment 7)

The requester is in Slack and sees none of the threads, so the coordinator
tells them as it goes — through the connector's `reply`, the same call the
starter names, and nothing else. The shape is the agents skill's own (its
`SKILL.md`, step 4): the plan when the threads open (each thread by name
and what it owns); at every wake and every `accept`, one line first —
name first: what moved, what is next, whether they must act (**wait**,
**answer** or **attach**) — and only what changed; one close-out line when
the done-means is met: a statement of what closed and what stayed (a
branch, a worktree, a PR), never a question — the requester decides
afterwards. The wake is the trigger: never a poll or a sleep
inside a turn to have something to say, and a wake with nothing new sends
nothing. A text plan is one post: when the split is not plain it ends with
the question that opens the threads ("Open all three now?"), and later
updates edit it (`reply --replace-last`) while it is your newest message,
else re-post it. One example of the
wake line:

> Tester [tester] finished 4/5 scenarios; the last one needs the fixture
> you mentioned — Implementer is on it, nothing for you to do yet.

Never a silent start: a status line within the first turn, then `go`'s
`channel_line` as printed (the ☐ plan, one per thread; it replaces the `--say`
steps), and after each `ack` or `accept` its `channel_line` (an edit when the
plan is your newest lane message, else a re-post — `--replace-last` moves
with every post) — never a batched or duplicate plan (V-AG22 channel rows:
the plan came ~4 min after the ack and the ticked list arrived as a new
message; the helper's `channel_line` is the one call).

No count, cadence or template beyond that: the judgement is the
coordinator's.

## When the agents helper fails (Constitution XIII)

The project is the only thing refused: an `init` that fails refuses only the project and the same launch still opens the thread. `init` exiting non-zero (`error`,
`slug_taken` twice), printing no JSON line (`agents_unavailable`) or not
being there at all (`agents_missing`) leaves the receipt's `project` as
`{"outcome": "failed", "error", "message"}` and the launch goes on exactly
as a thread launch: the claim, the handoff without a `project` key, the
thread starter, the `launched` line. Your one line says so ("no project —
<error>; the lane runs it as a thread"). Nothing is retried on the daemon's
side; the requester's next goal-shaped ask asks again.

## The steward's view

`fleet-steward`'s `scan` reads every project folder read-only and its
digest carries one line per project (state, threads running / waiting on
you / done, last change) after the machine blocks. It steers nothing; only
the project's coordinator writes there.
