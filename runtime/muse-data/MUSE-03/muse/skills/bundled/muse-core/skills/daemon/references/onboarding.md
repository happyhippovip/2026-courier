# Daemon reference: connector onboarding

Background for the "Connectors" and "Prerequisites" sections of `SKILL.md`:
the reasoning behind the block, repair, and disconnect rules. Nothing here is
needed on the connect path; the skill body names every command.

## Why a bare "Slack" means the mailbox

The routing rule — a bare "connect to slack" arms the mailbox, and the OAuth
`slack` transport opens only when the human names its machinery — is the
body's (`SKILL.md` § Connectors). Why: the word names the place the human's
messages originate, not the wire they travel, and today that wire is the
token-less mailbox. Reading the OAuth transport into the word alone sends a
session hunting for a bot token that does not exist.

## Prompt-mounted monitors: no words = Slack, words = the connectors named

The rule itself is the body's (`SKILL.md` § Onboard a connector): a bare
`/daemon` or `muse daemon` is the mailbox connect, byte for byte as before;
`/daemon <prompt>` (what `muse daemon <prompt>` submits as the first input)
names which connector monitors to open (ADR 37480 D4). Why the prompt and
not a flag: a `--connectors` list is a hard-coded vocabulary (ADR 37480 D4,
rejected) — the catalog descriptions and the connector SKILLs are what you
read. How the mount goes, per connector the prompt names:

1. Pick the connector from the catalog by its description; its SKILL states
   its connect words and the sources and filters its `listen` accepts. This is
   the ONE connect-path skill read the body allows (a connector you already
   know — `slack-connector` — is never re-read).
2. Resolve the subscription: the sources and filters the prompt asked for, in
   the words that connector's `listen` takes. A connector's default filter is
   "addressed to me" (mention, assigned, reply-to-me; ADR 37480 D5 item 5);
   a wider stream is armed only when the prompt asked for it.
3. Record before arming: ONE
   `start --daemon-session-id <id> --connector <id> --connector-script <its script> --source <s> --filter <f> --prompt '<the words>'`
   per connector (`--source` and `--filter` repeat; `--connector-script` is
   the script path derived from that skill's `skill-dir`, needed for a
   project skill that is not the registry helper's sibling). The row keeps
   the RESOLVED set, `[{"connector": "<id>", "sources": [...], "filters":
   [...]}]`, echoed as `subscriptions`, and `--prompt`, the raw words, kept
   for a human reading intent (ADR 37480 D10). Slack named beside another
   connector is still the ordinary `start --transport <mailbox|slack>`
   (`--transport` is the compatibility spelling of `--source` on the default
   connector).
4. Arm that connector's own `listen` with the resolved words under its own
   persistent Monitor - and pass that exact command to the `start` as
   `--listen '<command>'`, so the row remembers it and a restart's `start`
   prints it verbatim (#38715 QA round 10 D-META-1: a restart used to arm a
   bare `listen` and widen the human's `tasks` to the whole stream, because
   the startup sequence bans reading the connector's SKILL and `next` gave
   prose; the daemon still reads nothing of the connector, ADR 37480 D3) -
   `description="<connector id> <sources|all>[ (<hint>)]"`
   (the subscription in human form — connector id, its sources or `all`, and
   a short filter hint when one is set, e.g. `stream-connector tasks,chat
   (me)`; a fixed display label, never parsed, ADR 26855 D7; the Slack
   connector keeps its own `slack channel` / `slack thread` labels),
   `show_lines=true`, `wake_delay_ms=0`.

A restart re-arms the RECORDED set verbatim — `start` echoes every intent row
with its `subscriptions`, `prompt` and `script`, and Startup step 2 arms each
`enabled` connector whose listener is `absent` from those words — and never
re-reads or re-resolves the prompt: re-running model resolution on a restart
could arm a different set than the one the human saw armed. A different
prompt is a reconnect: the same `start` for that connector replaces its row.
To take a prompt-mounted connector down: `intent set --connector <id>
--desired disabled` first (with `--source <w>` to drop one source and keep
the rest), then that connector's own `disconnect` (the body's order for
Slack, ADR 25011 D6), then `work_stop` on its Monitor (round-10 N5: the
Monitor was stopped but the connector's own `disconnect` was skipped, so its
`connected` flag stayed true until the next arm).

What "connector" means here (ADR 37480 D1): a skill directory whose SKILL
names one script. The daemon depends on three mechanical rules only —
ownership through the registry keyed `(connector, conversation)` (both opaque);
`listen` under a Monitor printing `c<n> <sender>: <text>`; `listen` turning
away a second live listener on one subscription, `reply` idempotent — and
addresses a conversation as `(connector, alias)`, replying through the
connector whose Monitor delivered the line (D2: two connectors may both mint
`c1`; the wire never carries a connector prefix). Channels, markup, cards,
event-id shapes, lane environment and liveness are the connector's SKILL's to
teach. A connector author proves the three rules with the daemon contract
suite's second-connector tests (`fake_second_connector.py` beside `run.sh`;
the stand-alone conformance script is tracked in #38242); the daemon never
runs any of it at onboarding.

## Coordinator streams: input freely, reply only where delegated

Other streams are input, not yours to answer: a coordinator may arm another
connector's `listen` as input and replies only in the conversation the daemon
delegated to it (ADR 37480 D5, D7, D8; owner ruling 2026-09-18T05:16Z,
verbatim in that ADR's acceptance records). The starter's one-sentence form is open task T-37480-46;
until it lands this section is the rule's home (#39465). Why:

- A coordinator may arm any connector's `listen` under its own Monitor as
  INPUT for a pipeline stage — the diff a thread is about, a task queue — and
  produce into another stream through that connector's `reply` or create
  verb with `--origin <connector>/<conversation>` naming the conversation
  that caused it, so a bridged message stays traceable.
- It replies INTO a conversation only after the daemon delegated that
  conversation to it (`delegate` / `claim`): one owner per
  `(connector, conversation)` is the load-bearing invariant (ADR 25011 D3,
  D11, D13). Two observers of one stream racing for the first reply is the
  case this forbids; the daemon's claim is the one serialisation point. To
  answer in a stream it only observes, the coordinator asks the daemon to
  delegate it and never claims it itself.
- Listener uniqueness is per subscription key
  `(connector, sources, filter, consumer session)`: the daemon's Slack
  listener and a coordinator's other-stream tail coexist; two `listen` calls
  with the same key from one session are refused (D1 rule 3), and two
  concurrent subscriptions on one source must have disjoint filters — an
  overlap is a configuration error the connector's `listen` reports, naming
  the live subscription, exit non-zero (D8).
- Budget: the Monitor render budget is fair-shared per delivery while the
  backlog cap is per task, so every extra live listener in a session shortens
  the others' visible tails. Narrow filters are the mitigation until a budget
  change is separately decided.

## Why the script path comes from `skill-dir`

The wrapper that delivers a skill body carries `skill-dir="<absolute path>"`,
the directory the SKILL.md was read from. For a bundled skill the `path`
attribute is a `bundled://…` DISPLAY LOCATOR that no tool can open, so a
helper path derived from it becomes a filesystem search. Arming is itself the
path check: a wrong path fails on that first call with an error naming it, so
an `ls` before the arm buys nothing. The examples in the skill body spell the
helper path out in full so nothing has to be derived twice.

## Why nothing precedes the arm

Every pre-flight probe — locating the connector script, re-reading its
SKILL.md, reading `describe`/`status`/state, echoing env vars, hunting for a
bot token — buys the human seconds of dead air and learns nothing the
listener would not report by itself: it checks auth and scope as it starts
and dies with a diagnostic that arrives as a Monitor notification. Messages
persist on the transport, so nothing is lost by connecting first.

## `listen` is the start

Registration or binding, scope validation, and the reset of the connector's
own observed-down flag all happen inside `listen`, which is why the body has
no separate connect step and nothing to ask before arming. Which conditions
BLOCK, and the daemon surfaces (never hijacks) them: the id is HELD by another
LIVE client (a remote held / 409, e.g. the mailbox reporting "already held by
another client") — report it; the connector derives its own id, and a
different one is the human's call, passed as `--mailbox-id <id>`; the daemon
is SWITCHING ids while the current one is still connected — run
`disconnect --transport <mailbox|slack>` first, then arm the new id; and a
`live` listener this session shows no Monitor for — arm nothing, tell the
human its pid (the body's Startup step 2). The daemon never touches the
connector's private state files. Why they are the only blockers: the
connector derives its own id and cleans up its own dead prior-run local
state, so nothing else stands between the human's line and the arm.

## Repair paths

Only if the listener says it is not ready — it exits fatal with one line
naming what is missing, the only readiness signal the daemon ever acts on
(the body's pointer: `SKILL.md` § Onboard a connector):

- *no token* (Slack only): run `auth --token-stdin`, which the HUMAN feeds
  — a bot token must never ride a Monitor'd command line.
- *no channel bound* (Slack, first bind on this machine): ask the human for
  the channel AND owner user ids — neither is the daemon's to find — then ARM
  the binding form under the Monitor —
  `monitor(command="python3 <connector-script> listen --channel {container_id} --owner {owner_user_id} --only-owner", persistent=true, wake_delay_ms=0, show_lines=true, description="slack channel")`.
  Never guess a channel or owner id, and never dig either out of state, env,
  or a manifest. The binding form is NOT a bounded command: `listen` binds
  and then STREAMS, so it goes under a Monitor — repair, not pre-flight.
- a human-directed channel SWITCH is ORDERED, and the order is the whole
  safety property: `disconnect --transport slack` FIRST, then WAIT for the
  old Monitor to print `stopping the listener`, and only THEN arm the new
  channel — `disconnect` only sets a flag the listener reads once per poll
  cycle and a new `listen` sets it back, so armed before that line appears
  the two double-reply. A later line naming a different mailbox id is the
  same ordered switch on the mailbox: `disconnect --transport mailbox`, the
  stop line, then the arm with the new `--mailbox-id`.
- an id HELD by another live client, or a `live` listener this session shows
  no Monitor for: report it, arm nothing (see § `listen` is the start).

## The Slack rebind is repair, not pre-flight

The token-less mailbox never reaches the binding form; a Slack machine that
has connected before reaches it only by a deliberate human-directed switch;
and a later `listen` may drop `--owner` — the connector inherits the recorded
owner on a same-channel rebind. Why the rebind goes under a Monitor rather
than a shell call: once bound, the binding `listen` streams exactly like any
other listen, so a foreground call never returns, and muse permits no
unmanaged shell backgrounding — the Monitor is the one long-running listener
there is. Only a CHECK, never the listen, may run foreground and bounded.

## Disconnect semantics

The `disconnect --transport <t>` line, its required `--transport`, the STICKY
registry row, and "desired state is yours; observed state is the connector's"
are the body's rules (`SKILL.md` § Onboard a connector). Why the stickiness
lives in the registry and not in the connector: a fresh `listen` clears the
connector's observed-down flag, so only the intent row can remember that a
human meant the transport to stay off until they re-connect. Why the
connector marks the transport observed-down at all: the Monitor tool has no
model-actionable stop yet (#16370), so the armed `listen` has to exit on its
own.

## The closed ingress gate

What `start` does under a closed `MUSE_EXPERIMENTAL_EXTERNAL_AGENT_INGRESS`
gate, and the ban on a guessed retry, are the body's rules (`SKILL.md`
§ Onboard a connector). Why the connect goes ahead (#28774): the gate closes
only the peer-evidence read that `recover` needs, so the intent row and the
listener are untouched, and the `hint` line already carries the restart that
recovers existing lanes. Why a retry with flags is pointless: `--peers-json`
takes a file path and `MUSE_DAEMON_PEER_LIST_CMD` is a test seam; a live
helper lists such an override under `ignored_env` rather than honouring it,
and any other exit 6 `peer_evidence_unavailable` is one line to the human.

## Environment the lanes inherit

The gates themselves are the body's rule (`SKILL.md` § Prerequisites 1);
coordinators need the same ones. With the `tag` gate on (an exported
`MUSE_EXPERIMENTAL_TAG=on`, or the served remote value with nothing
exported), a human can skip the typed `/daemon` by starting the session as
`muse daemon [connect words]`: it exports no gate and sets no reasoning
effort (owner directive 2026-09-21), defaults `--yolo`, and submits
`/daemon <connect words>` first (with the gate closed there is no keyword).
Why the passthrough exists: a tmux server hands new panes ITS environment, not
your shell's, so `delegate` copies every `MUSE_EXPERIMENTAL_*`, `XDG_*_HOME`,
`MUSE_DAEMON_*`, and `SLACK_CONNECTOR_*`
variable in your environment into the lane explicitly — a Herdr pane the
same way, through `tab create --env`. Two names are never copied: `TMUX`, so
a launcher inside tmux never nests, and every `HERDR_*`, because Herdr
injects the child's own pane context and an inherited one would make a tmux
child believe it sits in its parent's pane (ADR 31985 D5). The runtime adds
`MUSE_LANE_BACKEND` (`tmux` or `herdr`) and, for tmux, `MUSE_LANE_REF` (the
session name); `launch` lists every name it set under `env_passthrough`.
A lane gets the same settings as this session (owner ruling 2026-09-20):
`launch` adds the admission gates you run under as explicit pairs —
`MUSE_EXPERIMENTAL_TAG=on` always, `MUSE_EXPERIMENTAL_AGENTS=on` when your
own read of that gate is open — and copies your session's model, reasoning
effort, provider, presets, base URL and tool-call switches from its command
line as engine args (never `--yolo` or another posture flag: the lane's
posture is the runtime's under `--unattended`; never workspace, worktree,
resume or the `daemon` words). No reminder gate is forced off: your own
`MUSE_EXPERIMENTAL_*_REMINDER` values ride the passthrough as they are. The
receipt's `lane_settings` names what rode and, when your command line could
not be read (a sandboxed tool shell, no Muse ancestor), says so instead of
guessing; a project lane that would see neither admission gate is
`agents_gate: absent in lane` — a launch defect, said in `next`. On a
devserver the TUI needs internet mode for the model gateway. Local Session
Messaging is on by default in every build; nothing in the daemon skill sends a peer message.

## Which backend a lane gets

Since ADR 25011 D29 (#31985) `launch --backend auto` — what `delegate` runs —
asks the runtime's `context` once: Herdr only when the calling process is
VERIFIED inside a Herdr pane (`HERDR_ENV=1`, `HERDR_PANE_ID` and
`HERDR_SOCKET_PATH` set, `herdr pane process-info` answers, and that pane's
shell pid is in the caller's own ancestor chain); tmux when there is no hint
or the hint is inherited by a process outside the pane (a tmux session
started from a Herdr pane inherits every `HERDR_*` and is still tmux). Why a
hint the server cannot confirm is a refusal (`herdr_context_unverified`, exit
6) and not a tmux launch: the human asked for a lane where the daemon runs,
and a silent switch after an uncertain Herdr attempt is the double launch ADR
31985 D5 forbids. D7 rules out gating Herdr itself behind an opt-in or mode;
two explicit paths exist: per launch, `launch --backend tmux|herdr` (wins over
everything), and the one recorded daemon-wide choice (#37181, spec 25011
FR-37181-2):
`start --lane-backend tmux|herdr` — or `MUSE_DAEMON_LANE_BACKEND` read at
`start` — is the explicit backend `launch --backend` already admits (D5
selects only a NEW lane's default from the launching context), so every
later launch skips the context read; a bare `start` keeps it and says `lane backend tmux
(recorded)`; `start --lane-backend auto` returns to the read. The daemon's
one line after a launch is `<lane> → <lane_ref>` — the tmux session name, or
the Herdr pane id.

## Building a new connector from the thread

"Build / create / make me a connector for X" said in a conversation is
non-immediate work like any other (ADR 37480 D12; spec 25011 FR-37480-44):
your one `delegate` hands it to a coordinator and you are done with it. The
coordinator reads the bundled `connector-author` skill (the same `tag` gate
as this one), runs its eight-question interview in the thread — source,
delivery, auth, what one conversation is, the reply verb, default filters,
gate, name and placement; one question per turn, a card for a finite choice,
a summary and a confirm before anything is written — scaffolds a connector
skill from the starter template with `new_connector.py scaffold`, fills the
`TODO(answer …)` stubs itself from the answers, runs `new_connector.py check`
(the D1 conformance script plus the generated tests), commits on a branch
`feat/connector-<name>` in the workspace and hands the branch (and a PR only
when asked) back in the thread with the connect words. A source an installed
event-stream connector already lists is redirected to that connector's
connect words, never built. Nothing here changes your connect path: the new
connector is a project skill (or a plugin package) the human mounts later
with `/daemon connect <name>`.
