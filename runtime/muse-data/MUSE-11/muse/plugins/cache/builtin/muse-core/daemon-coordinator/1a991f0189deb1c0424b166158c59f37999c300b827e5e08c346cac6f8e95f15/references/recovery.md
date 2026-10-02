# Daemon reference: startup recovery and lane lifecycle

Background for the "Startup sequence" and "Delegating" sections of
`daemon/SKILL.md`: why the recovery pass judges rows the way it does, what the
registry does and does not know about a lane, and the reasoning behind the
`delegate` outcomes. Nothing here is needed on the dispatch path.

## What a restart loses and keeps

That a restart runs `start` FIRST, arms only what it reports `absent`, and
prefers `resume <your daemon session id>` is the body's rule (`daemon/SKILL.md`
§ Startup sequence). Why that order: a restart loses your Monitors and your
context but NOT the coordinators — independent tmux sessions — and NOT the
registry, so the ONE bounded recovery pass can decide from live evidence
which coordinators are still yours, and each transport's listener state,
before anything is armed. Why `resume`: it keeps this session's own context
and log, which is worth more than any lane bookkeeping.

Why a restart is a refresh and not a re-arm (owner ruling, 2026-09-20; spec
25011 Clarifications "Session 2026-09-20 (#38715 QA round 9 lane DM3, a
daemon restart is a refresh)"): the owner's bare `/daemon` after a restart
armed a stream connector's row whose sources that connector's cached catalog
no longer knew — the Monitor exited 2, was armed again, exited 1 — and then
relaunched the fleet-steward lane with a twenty-message handoff nobody asked
for. Nothing live had changed; the restart itself did the damage. So `start`
tells the two cases apart and the body arms once: a live listener or lane is
adopted as it stands; an `enabled` connector with no listener is armed exactly
once, and a Monitor that exits non-zero after that arm is ONE call — `intent
arm-exit --connector <id> --exit <code>`, which writes the exit and the time
on that row — then one line (connector id, exit code, its last stderr line,
the `intent set --connector <id> --desired disabled` that turns it off) and
no second arm in that turn: the stderr line says why and a second arm
reproduces it (ADR 25011 D21 Amendment 1; owner ruling 15, 2026-09-20). The
recorded exit outlives the session (the owner's second run showed a bare
`/daemon` arming the same failed row on every restart because nothing did),
and what the next `start` does with it is owner ruling 27 (2026-09-22,
superseding ruling 15's never-retry): the human's restart — step 1's `start
--retry` — gives the row ONE fresh try and names the earlier failure under
`retry` ("last arm exited N at T: <the connector's own reason>"), because a
row nobody retries was the weird experience ("re-connect to try again" on
every `/daemon`, nothing tried); only a bare `start` (a recovery, a same-turn
re-run) lists it `stale`. Why `start` judges a row `stale` (its recorded
script gone — a plugin refresh moved the skill cache — or a recorded source
missing from the connector's non-empty `sources_available` list, or from its
named listener records when it gives no list; an empty list is no evidence,
because the one producer prints it when it cannot read its own catalog; or a
`last_arm` record on a bare `start`, "last arm exited N at T: <reason>;
re-connect to try again: intent set --connector <id> --desired enabled")
instead of arming it: an arm the connector will refuse is a failed Monitor,
a wake and a retry loop; the verdict rides `stale` beside the record and
clears when the human disables that connector or connects it again (any
`enabled` write — `start --connector <id> …`, the bare `/daemon` for the
mailbox, `intent set … --desired enabled` — forgets the recorded exit: the
human asked for a fresh try) or when the row's listener runs (the fresh try
worked). The reason is the connector's: the bundled listener leaves its
failure line's `reason` in its ended record beside the exit, and `start`
writes both onto the row without a model call; an end a human connect
already answered is remembered as answered, so the connector's record of it
(reported until its next listener) is never written back — the owner's
2026-09-22 re-connect did not stick for exactly that. Why the default connector
is armed first: the owner's mailbox was never armed because a stream
connector's arm, listed first by id, failed and the model stopped there; one
row's failure stops nothing beyond that row: the remaining arms, the one line
and the hand-off line still happen.
Why a gone steward lane is report-only from a start, like an
`orphaned` conversation row: the steward is a human's opt-in (FR-31985-7),
and the human's "restart the fleet steward" is the one relaunch (§ Lifecycle
asks below).

## How `recover` judges a row

The startup `start --daemon-session-id <id>` (the whole-registry `recover`
pass it runs) takes your id for ONE reason: it infers a lane's Muse identity
from the live session list only when it can rule your own session out.
Without the flag the pass infers no identities, says so under `unbound`, and
everything else is unchanged. `--daemon-session-name` is a display label
only.

How each `active` row is judged (`daemon/SKILL.md` § Startup sequence, step 1 says
only the outcome words): the pass checks whether the row's exact tmux
session name or Herdr pane is live through its recorded backend (never a
prefix probe) and judges the row from that — a gone lane is `orphaned` and
report-only (its next line reaches the daemon `[unattended]`, and the one
delegate call handles it); an identity it already records is validated against
the live Session registry, and one no longer listed orphans the row even
under a live tmux name; a row recording none (the usual case) is REUSED, its
identity filled when exactly one unclaimed session sits in that lane's
workspace, else listed `unbound` and left alone; a Herdr row with no
recorded pane id is `unlocated` (liveness unknown, left active; its `next`
names the check). A failing evidence command changes nothing (exit 6),
except the closed ingress gate, where `start` still exits 0 with
`recover.skipped = ingress_closed` and `hint` first. Why a live conversation
is never orphaned for being unidentified: that would open a second coordinator for a conversation that
already has one. Why a recorded identity that the live list no longer shows
orphans a row although its tmux name is still there: the process behind that
name is not the one the row recorded, and a name alone proves nothing. Why
`readdress` writes nothing: no message can address the daemon, so a lane
whose handoff names an earlier daemon id has nothing to be told.

## Recovery follows the recorded backend

Since ADR 25011 D29 (#31985; ADR 31985 D5/D7) a row records where its lane
lives: `backend` (`tmux` or `herdr`), `lane_ref` (the tmux session name, or
the Herdr pane id) and `backend_server` (the Herdr socket; null for tmux). A
row written before schema v2 has no `backend`: it is tmux and its `lane_ref`
is its `tmux_session`. `tmux_session` never carries a Herdr id, so a reader
that only knows tmux never mistakes a pane for a session. Why every liveness
read goes through the recorded backend: `recover`, `lookup --live` (a plain
`lookup` is a pure row read and never probes), `mark …
retired` and `bind` ask the runtime's `list` (tmux) or `status --mode herdr
--ref … --server …` (Herdr), never the daemon's CURRENT context
— a daemon restarted in a plain terminal still judges its Herdr lanes through
their recorded server, and one restarted inside Herdr never reselects or
migrates a tmux lane. Why unknown is never dead: a server that cannot be read
is `tmux_unavailable`/`herdr_unavailable` (exit 6), `lookup` says `live:
null`, and nothing is orphaned, retired or relaunched on it; the connector's
re-entry treats such a Herdr claim as `owner_unknown` and keeps it. Why an
`active` Herdr row without a `lane_ref` is unknown, not gone: the launch
died between `tab create` and its `launched` line (or the registry itself
died before the pane id was written), so a pane running the coordinator may
exist that no row names; `launch` refuses (`conflict`, exit 3, its reason
saying the liveness is unknown), `mark … --state retired` refuses too
(`lane_unknown`, exit 6: retired means proven gone), `recover` leaves the
row and lists it under its own bucket, `unlocated` (liveness unknown, no
recorded pane id; its `next` names the check — never `unbound`, which is a
live lane with no inferable identity), and a human who has looked at Herdr
ends any pane serving it (`bind` writes identity fields only and cannot
supply a pane id) and runs `mark … --state orphaned` (after which `retired`
writes without a backend call), and the next `[unattended]` line
re-dispatches. A `failed`
launch that did create the pane keeps the pane id on the row so `mark …
retired` can prove it gone later.

## Rollback boundary and drain

An older helper refuses a `user_version 2` file for every write verb and for
`launch` (exit 5) while it still reads rows; that refusal is the documented
rollback boundary, not a transparent downgrade, and no feature switch stands
in for it. Nothing in an older helper re-adopts a v2 file (its only
`conversation_owner` INSERT is `launch`), so an in-place downgrade does not
exist. The drain is operator-run, with the NEW helper, in this order: run
`recover` (each `lane_ref`-less Herdr row is listed under `unlocated`;
check Herdr and `mark … --state orphaned` it by hand); end every lane, Herdr
and tmux, and only then `mark … --state retired` every row (`retired` on a
live lane is refused); record each transport's intent with `intent get`;
stop the daemon session and the connector listener so no `delegate`,
`recover` or `start` recreates the file at v2; move the v2 registry file
aside — keep it, never delete it — and install the older helper; restart the
daemon (its first `start` creates a fresh v1 file), re-issue `intent set
--transport <t> --desired <value>` for each recorded transport and run
`start` again. Only then do claimed conversations re-delegate on their next
message. The exit-5 `next` line ("never delete or recreate the registry") is
the daemon's own rule on an unexpectedly newer file, not this drain (ADR
25011 D29 item 7).

## Messages after a restart

What the daemon does with messages after a restart — that nothing is replayed
(ADR 25011 D20), where a claimed conversation's messages go, what happens to
one that reaches the daemon anyway, and why an `orphaned` or `[unattended]`
one is a new delegation — is the body's rule (`daemon/SKILL.md` § Event loop).
Why the old lane's partial work is never redone silently: the coordinator that
did it is gone with its context, and a quiet second attempt would hide from
the requester that the first one died.

## The registry identifies lanes; nothing reports in

Why the registry, not the coordinator, is the source of a lane's identity: no
coordinator-to-daemon channel exists in this version, so identity comes from
what `delegate` wrote at launch and what `recover` can read off the live
session list; a lane the pass cannot tell apart from its neighbour is
labelled, not faulted, and keeps working. `delegate` records the row and the
lane (`backend`, `lane_ref`) at launch; `recover` fills in the coordinator's
Muse session id when it can tell which one it is, else lists the lane
`unbound` and it keeps working. No peer message triggers anything the daemon
does; the helper's `bind` verb is the HUMAN repair path for an identity the
registry could not infer, and nothing in the event loop calls it.

## Nested work and workers are the coordinator's

Why fan-out and workers stay the coordinator's: its subagents and workflows
are its own tools and never touch the daemon, and since ADR 25011 D29 (ADR
31985 D6) an independent worker is too — launched through the same lane
runtime with an explicit backend and lane name, judged and retired by its
`backend` + `lane_ref`, never through a registry row (the registry maps
CONVERSATIONS to coordinators and only the daemon writes it). The thread
supplies the context and where replies go; it does not make every worker on
the host the coordinator's, and a worker another coordinator or the human
started is not its to touch. A coordinator sends no peer message at all —
not to the daemon, not to another lane (a Monitor-woken turn's send is
refused, #27816); a worker is driven through the lane runtime,
never through a peer channel. The coordinator never runs `tmux new-session`
by hand: a worker is opened through the lane runtime with an explicit target
and a name without the daemon's `muse-lane-` prefix (any taken `muse-lane-*`
name is another conversation's lane). A tmux coordinator asked about a Herdr
pane (`w<n>:p<n>`) says it is out of a tmux lane's reach and names a new
thread; it never hunts tmux servers or runs `kill-pane` (a coordinator-read
copy of these rules: #39465). Host-manager, when loaded, supplies resource
admission and contention policy; its absence from the catalog no longer stops
a lane, because ownership, duplicate prevention and liveness live in the
registry and the runtime.

## The handoff document

`delegate` writes one immutable handoff to
`<registry-dir>/handoffs/<handoff_id>.json` (`daemon/SKILL.md` § Delegating, step 3).
Its fields: `schema_version`, `handoff_id`, `connector`, `conversation`,
`lane`, `conversation_ref`, `address` (the mailbox they write to), `event_id`,
`watermark`, `acknowledgement.posted`
and `progress_reply_id`, `daemon.session_id` and `daemon.session_name` (audit
only: `daemon.session_id` is a record of who started the lane, not an address —
a session id is always routable, a name routes only while the name authority
is up, and a tmux name is never a Muse session name, #27815), `posture`,
`workspace`, `connector_script`, the `snapshot`, and `created_at`. Why it is shaped that way: `handoff_id` is
built from the connector, the conversation and the `event_id`, which is what
makes a redelivered dispatch land on the same file; the snapshot holds both
directions of the conversation up to the watermark, with the daemon's own
sends marked `sent`, so the coordinator repeats nothing; and tmux caps a
command line, so the starter prompt stays short and the full snapshot lives in
the file — never in the registry database or the tmux argv.

## `delegate` outcomes, the reasoning

- `launched`, `already_owned`, the no-unanswered-line refusal and `failed`
  are the body's rules (`daemon/SKILL.md` § Delegating); `reused` and `conflict` are
  taught here, and every outcome's `next` names the daemon's one line.
- `reused`: the same trigger was already delegated; the lane is live; nothing
  to do. A relaunch over an `orphaned`/`retired` row comes back `launched`
  and the daemon's one line ends `, relaunched`; `lane_ref` is read from the
  answer, never the derived name. A relaunch replaces the dead row and keeps
  the old handoff beside the new one, under the same trigger, as
  `<handoff_id>.<created_at>.….retired.json`: the earlier lane's record stays
  inspectable, and its partial work is never replayed.
- `conflict` (exit 3): the answer names the cause — a live coordinator under
  a DIFFERENT trigger (served; leave it alone); the SAME trigger's row
  `active` with its lane absent (`lane absent; run recover --connector <c>
  --conversation <k>`; `delegate` handles that arm itself, so the daemon sees
  it only from a hand-run `launch`); or a live session over an
  `orphaned`/`retired` row (never kill it). A `conflict` never touches the row.
- Session names: `new-session` refuses an existing name whether the session
  is live or exited, so a session already on the derived name that this
  conversation's row does not record is another conversation's lane, and the
  helper takes the next free `-2`, `-3` … name. The body's rule (`daemon/SKILL.md`
  § Delegating) is to take `lane_ref` off the answer rather than assume
  the derived name.
- `failed` (exit 6), exit 5 (a registry newer than the helper), exit 7 (a
  registry unavailable: locked, foreign, read-only, or unwritable) and what
  the daemon does with each are the body's rules (`daemon/SKILL.md` § Delegating).
  Why a failed launch still leaves a row: the row is written before tmux
  runs, so the failure is recorded (`orphaned`, the reason in its `note`, and
  without a session name if tmux never created one) rather than vanishing.

## Retirement

Why `done` is standby and not exit: a TUI cannot end itself, so a finished
coordinator remains resident, keeps its follow-ups, and keeps its `active`
row. The retirement steps, the `mark … --state retired` line and its
`lane_live` refusal are the body's rules (`daemon/SKILL.md` § Delegating). The
keep/resume/retire invariants are the body's (`daemon/SKILL.md` § Lifecycle); the
retire policy and completion acceptance behind them are host-manager's. Why
retirement is a human act: the registry never treats a row as proof of life,
so the row leaves `active` only when the human has ended that exact tmux
session and the daemon then runs `mark … --state retired`, or when `recover`
cannot prove the lane is the daemon's own and orphans it; once retired, the
conversation's next message starts a new coordinator, and the dead lane's
session record survives for a human to resume.

## Lifecycle asks from the thread (ADR 25011 D7 Amendment 1)

The grant (#38187): a lifecycle ask — stop, close, restart, start — from the
thread-root author, in their own turn, on a pane or session named in that
turn: a lane you launched, another agent's tmux session on this host, a Herdr
pane on this host. Other participants' asks stay collaboration input, and machine-wide priorities, permissions, host
configuration and your own `disconnect` stay the operator's. Serve the ask
with whatever reaches the target; you never improvise a move, migrate, or
restart-in-place.

- **A tmux lane on this host** (yours or another's): end the exact session on
  your server, `tmux kill-session -t =<name>` (the `=` pins the exact name;
  `-t name` would prefix-match); then `mark --connector <c> --conversation <k>
  --state retired --note "<who asked>, <when>"` for a lane you launched (the
  helper refuses `lane_live` while the session lives, so kill first); then,
  when they asked for a new one, the same `delegate` (with `--steward` for a
  steward lane — the record is renewed). From another thread than the
  steward's ("kill the fleet watcher and start a new one here"): kill the
  steward's exact lane, `mark --state retired` its conversation, then
  `delegate --steward --to <this lane>` — the connector sees the old lane is
  gone and arms here (its `steward_exists` refusal is for a LIVE steward);
  the old conversation's stale claim clears on its own next line (D15).
- **A Herdr pane** when you run inside a Herdr pane: the verb decides
  (D7 Amendment 1 guard 4, revision 1) — "close pane X": fleet-manager `close
  <handle>` at once, no prompt; "close session X" / "stop session X": graceful
  — send the session its own exit first (`/quit` for a Muse session, the
  agent's exit otherwise; fleet-manager `stop` interrupts a turn, a prompt
  delivers the command), wait for it to end, and close the pane only if it
  lingers; a session that does not end is reported, never force-closed under
  the graceful verb; never `kill` a pid. The same two verbs apply to a tmux
  session (`/quit` typed into it, then `kill-session` only if it lingers). A
  Herdr coordinator's starter carries this verb path as one line (registry
  `launch --backend herdr`), so the executor reads it before any call. For
  a lane you launched, once its pane is gone: `mark --connector <c>
  --conversation <k> --state retired --note "<who asked>, <when>"` (the
  helper refuses `lane_live` while the pane lives), then `delegate` again
  when they asked for a new one.
- **Your own lane, asked in its own thread** (D7 Amendment 1 revision 2;
  round-6b QA lane F2 D5): the coordinator that receives a line naming its
  own pane, session or lane ("restart the fleet steward", "stop session
  w6:p77") hands it back by standing down — `work_stop` on every ticker
  first, then on its listener, no reply, standby — because it cannot end or
  relaunch itself
  (a TUI has no self-exit; Herdr refuses a self-prompt, `agent_not_ready`:
  while a session runs a tool, its pane foreground is the tool) and it has
  no peer channel to you (a Monitor-woken turn's `send_session_message` or
  `muse session-message send` is refused `causal_metadata_invalid`, #27816;
  F2-fix attempts 3 and 4). The connector's liveness sweep (D20 item 4,
  spec 23499 FR-27816-2(f)) then returns the unanswered line to you marked
  `[unattended]` within about a minute (the lock is free, the claim past its
  grace, the line unanswered). You serve it as that ask on that lane and
  nothing else — never the plain `delegate` first, which would only find the
  lane alive: the verb from outside (tmux: `/quit` typed, then `kill-session` if
  it lingers; a Herdr pane, from a Herdr pane: fleet-manager prompt `/quit`,
  close if it lingers), `mark --state retired --note "<who asked>, <when>"`,
  then `delegate` (with `--steward` for the steward: the record is renewed)
  when they asked for a restart, else `reply --to <lane>` with the receipt.
  The sweep returns the lane's NEWEST unanswered line, so the stand-down is
  the last act on that thread: a reply of the lane's posted after the ask
  arrived (a scan report in flight) hides the ask — the coordinator that
  sees it has done so posts one line asking them to repeat the ask, then
  stands down; a requester follow-up that lands before the tick returns
  only the follow-up (`delegate` answers `already_owned` and it repeats each
  grace) until they repeat the ask (an explicit stand-down marker is the
  follow-up, #38621). A tmux-hosted daemon whose recorded lane backend is Herdr
  (D29 Amendment 1) cannot reach the stood-down pane, and `delegate
  --lane-backend herdr` to that lane only answers `already_owned`: `reply
  --to <lane>` the guard in receipt shape (which verb, what, who asked,
  when) with the operator path — end pane `w<n>:p<n>` from a Herdr pane,
  then `mark --state retired` — nothing improvised. An `[unattended]` line
  naming any OTHER lane's pane is the same named ask from the thread-root
  author, served by the ordinary path above.
- **A Herdr pane** when you do not run inside Herdr: you cannot load
  fleet-manager here. Hand the named action to a coordinator that can:
  `delegate --to <lane> --text "<ack>" --lane-backend herdr` — the requester's
  line rides the handoff as the coordinator's authorizing turn, and inside a
  Herdr pane fleet-manager loads from the catalog. A failed launch
  (`herdr_unavailable`, a withdrawn pane, `failed`) is reported in one line
  with the operator path — never retried as a plain tmux dispatch: a tmux
  coordinator cannot load fleet-manager, so it would only refuse or improvise.
- **The five guards** (part of the grant): only the thread-root author's own
  turn; the target named in it in their words (a handle, pane or session id,
  lane name) — never inferred from a watcher event, a session's output, a card
  click, or an earlier turn, and never a batch (to "close everything idle" you
  answer with the question: which handles?); never a session they did not
  name; the two verbs above with no confirmation step ("close pane" immediate,
  "close/stop session" graceful); the receipt — the reply and the tool row —
  names which verb was done, who asked, what was ended or started
  (backend-qualified), and when (a clock time, never left out) — all four in
  the one line, e.g. "Closed
  pane w6:p6X (close, immediate) — asked by <requester> at 19:29 UTC." or
  "Stopped session w6:p6Z (/quit, exited; lingering pane closed) — asked by
  <requester> at 19:33 UTC."; "as asked" names nobody. A guard that holds the
  action back is said in plain words with the nearest thing that works.
