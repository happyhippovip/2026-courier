#!/usr/bin/env python3
"""The daemon's routing registry: the ONE durable artifact the daemon owns.

`adr:25011-daemon-session-coordination#D4`: the daemon is the sole writer of a
small SQLite registry that maps a connector conversation to the lane — a tmux
session or, since #31985, a Herdr pane — and Muse session of the coordinator
that owns it, plus the human's desired state for each connector transport
(`#D6`). It stores no message text, credential, or task result, and a row is
never proof that anything is alive: `recover` re-checks the exact lane against
live evidence before a row is reused (`#D3`).

Two layers (`#D11`): the daemon hands a conversation over once and never reacts
to it again, so nothing addresses the daemon and no coordinator reports in
(`#D13`). `launch` therefore records the lane at once and writes a STARTER
prompt the coordinator can act on in its first turn — the request, what the
daemon already sent, and the exact conversation-scoped listen and reply
commands — and `recover` fills the coordinator's Muse session id in from the
live session list when it can tell which one it is.

Sole writer: only the daemon process runs the writing verbs (`launch`, `bind`,
`mark`, `recover`, `start`, `intent set`). Coordinators ask the daemon by peer message.
The helper still serialises its own writes — one `BEGIN IMMEDIATE` per verb
(`start --transport T` commits its intent row first, then runs the recovery
pass in a second) and an advisory lock file (`<registry>.launch.lock`) around a launch's
registry open, row judgment and tmux check-and-create — so a redelivered dispatch racing
itself cannot open two lanes, and a launch racing another launch waits on that one lock,
never on the SQLite busy timeout (#34042).

Verbs (each prints ONE JSON object on stdout, success or error):

  launch   record ownership, write the immutable handoff FILE (`#D5`) under
           `<registry dir>/handoffs/<handoff_id>.json` (0600), and start the
           coordinator's tmux session with a short prompt that points at it
           (a same-trigger relaunch over a non-active row keeps the previous
           document beside it as `<handoff_id>.<created_at>.<unique>.retired.json`)
  delegate the dispatch for a connector whose SKILL ships no `delegate` of its
           own (#37480): claim `(connector, alias)`, `launch` the coordinator
           with the generic starter, post the acknowledgement through that
           connector's `reply`; `already_owned` for a lane a live coordinator
           holds. The Slack connector's script has its own `delegate`.
  set      one per-daemon setting, `set delegation auto|thread|project`
           (#38715): recorded beside the registry, read by `start` and every
           `launch`
  bind     record the coordinator's Muse identity / peer address on its row
  lookup   the row for one conversation (read-only), plus `live`:
           true|false through the row's recorded backend, null when that
           evidence cannot be read (the connector's re-entry check)
  list     every row, optionally filtered by state (read-only)
  mark     set a row `orphaned` or `retired`, with a bounded diagnostic note;
           `retired` is refused (`lane_live`, exit 3, no write) while the row's
           lane is live — a lane is retired only after it is proven gone
           through its recorded backend, so a server that cannot answer is
           `tmux_unavailable` / `herdr_unavailable` (exit 6)
  recover  [--connector X --conversation Y] validate that row — or, without
           them, every active row — against tmux + the local Session registry;
           re-record the daemon's identity (with --daemon-session-id) and
           list lanes to re-address
  intent   set/get the human's desired connector state (`enabled`/`disabled`);
           `set` also reports `active_rows`, the count of rows still `active`
  start    the daemon's ONE startup call (#28176): on a human connect record
           the named transport `enabled` (`--transport T`; a bare `start` — a
           restart — writes nothing), ask the connector's own `status --json`
           whether each transport's ONE unscoped listener is live, then run
           the whole-registry `recover` pass, and print `{"intents": [every
           transport], "listeners": {"slack-connector": {"mailbox": {"listener":
           "live"|"absent", "pid", "mailbox_id"}, "slack": {…}}, "<connector id>":
           {…its own status…} | {"listener": "unreadable"}}, "active_rows": <rows
           still active after the pass>, "recover": {…recover's shape…}}` plus
           `listener_evidence` (a one-line reason) whenever the listener read
           was not a clean answer. The intent write commits before the pass
           gathers evidence, so a failed pass (exit 6) leaves the connect
           recorded — the same outcome as `intent set` then a failing `recover`.
           A session list closed by the ExternalAgentIngress gate does NOT
           fail it (#28774): the connect is live, the pass is skipped with
           every row untouched, and the line is `{"hint": "restart the daemon
           with MUSE_EXPERIMENTAL_EXTERNAL_AGENT_INGRESS=on …", …, "recover":
           {"skipped": "ingress_closed"}}` — `hint` FIRST so a truncated tool
           cell still shows it. Every other unavailable peer list is exit 6.

launch flags: --connector --conversation (the connector lane's stable `key`,
e.g. the peer mailbox id or `<channel>:<thread_ts>`, never the compact alias)
[--lane <c<n>> display alias, names the tmux session] [--conversation-ref
'<json object>' transport fields for the coordinator's own listener]
--event-id <connector event id of the trigger> [--watermark <last event id in
the snapshot; the coordinator's listen cursor>] --ack-posted yes|no
[--progress-reply-id] [--daemon-session-id / --daemon-session-name, recorded
for audit when known: nothing addresses the daemon] [--snapshot-file <path|->]
--workspace --connector-script [--tmux-session <the lane's logical name>]
[--backend auto|tmux|herdr (default: the `start --lane-backend` record, else auto)]
[--muse-bin PATH] [--muse-arg ...]
[--env KEY=VALUE ...] [--note] [--dry-run]

The snapshot is EITHER the connector's JSON LINES — one event object per line,
`{"direction": "inbound"|"outbound", "event_id"|"message_id", "from", "text",
"sent"}` (`#D12`; on a mailbox lane the newest outbound line's `from` is this
daemon's own mailbox, recorded in the handoff as `address` — the id the
requester writes to, #29738) — or plain text lines from a human handing a lane over. The
two are told apart by whether every line starts with `{`; such a line that
does not decode as a JSON object is a usage error (exit 2), and a mixed input
is plain text. Either way it lands
in the handoff FILE, never in the database, and the starter prompt quotes at
most one bounded line per direction from it.

recover: reuses an `active` row while its exact tmux session is live; orphans
it when that session is gone, or when an identity a human ASSERTED with `bind`
is no longer listed; and for a row that records none — the usual case, since
nothing reports in — INFERS the identity from the live list when exactly one
session that is neither another row's nor the daemon's own carries the lane's
published workspace label (the directory name), else reports it under
`unbound` and leaves the live lane alone. An inferred identity is a guess
(note `identity inferred by recover …`): if it stops being listed while the
lane is live it is withdrawn and the lane is `unbound` again, never orphaned,
and a human `bind` may overrule or confirm it (after which it is an assertion,
note `identity asserted by bind …`, and unlisted means gone). Without
`--daemon-session-id` nothing is inferred at all — the helper cannot tell the
daemon's own session from a lane's — and `unbound` says so.
The session list is consulted only when some row in scope has a LIVE tmux
session; a dead lane is orphaned on tmux evidence alone, so the
per-conversation form works with the ingress gate closed. Output: `checked`, `reused`, `orphaned`, `filled`,
`unbound`, `unlocated` (an active Herdr row with no recorded pane id: liveness
unknown, its `next` names the check), `readdress`. `--peers-json` takes the path to a JSON file, or `-`
for stdin; anything else is a usage error (exit 2) before any write.

Lane runtime (`adr:25011-daemon-session-coordination#D24`): the lane
mechanics — the tmux launch, lane listing, the live session list, the
proven-gone check — are host-manager's, in `lane_runtime.py` beside that
skill (`../../host-manager/scripts/lane_runtime.py` from this file: a sibling
in the bundled skills tree, the way the connector script is). `launch`,
`recover`, `start`, `mark --state retired`, `lookup` and `bind`'s re-attach
call its verbs (`context`, `list`, `open`, `status`, `status --lanes-json`, `forget`) as
subprocesses, one JSON line back; this file keeps the registry, the handoff,
the starter, and every row rule. A runtime that is not there is exit 6
`lane_runtime_missing`, nothing written.

Backend (#31985, `adr:31985-fleet-session-awareness#D5/#D7`): a new lane runs
where the daemon runs. `launch --backend auto` asks the runtime's `context`
first: a VERIFIED Herdr pane (the hint variables AND the pane's
shell in this process's ancestry) launches a Herdr pane; no hint, or a hint a
tmux child merely inherited, launches tmux; a hint the Herdr server cannot
verify is exit 6 `herdr_context_unverified` with nothing written — never a
silent tmux launch after an uncertain Herdr answer. The row records the
location in three v2 columns: `backend` (`tmux`|`herdr`), `lane_ref` (the
tmux session name, or the Herdr pane id once the runtime created it) and
`backend_server` (the Herdr socket); `tmux_session` stays the tmux name and
is NULL for a Herdr lane — never a Herdr id. A legacy v1 row has NULL
`backend`, which reads as tmux with `lane_ref` = `tmux_session`; the v2
migration adds the columns and rewrites no row, and an older helper refuses
to WRITE the newer file (exit 5) while its read-only verbs fail safe — exit 7
`registry_unavailable`, nothing written (the old read path never checks
`user_version`; #37480 QA round 6 lane B NOTE 3) — so downgrading means
`recover` then `mark … retired` first. Every liveness read (`launch`'s reuse and guards, `bind`'s
re-attach, `lookup`, `recover`, `mark retired`) goes through the RECORDED
backend and never reselects it; a Herdr lane whose server does not answer is
UNKNOWN, not gone: `launch` answers `conflict` and starts nothing. Launch
output carries `backend`, `lane_ref`, `backend_server` and `lane_name`, and
the one line to say is `<lane> → <lane_ref>`.
A daemon-wide choice (#37181, spec 25011 FR-37181-2; D5 selects a NEW lane's
default from the launching context, and `choose_backend`'s landed contract lets
an explicit backend skip that read): `start --lane-backend auto|tmux|herdr` — the flag,
else MUSE_DAEMON_LANE_BACKEND read at `start` — records the backend in
`lane-backend.json` beside the registry; a `launch` with no `--backend` of
its own follows the record and asks `context` only for `auto`. A bare
`start` keeps the record and names it (`lane backend tmux (recorded)`).

Posture: the lane is started with the daemon's own yolo-parity posture — the
lane runtime places `--yolo` (approvals and sandbox off, workspace trusted for
the run) right after `--workspace`, ahead of any `--muse-arg`; there is no
opt-out (FR-25011-13 forbids inventing a gated lane), and the posture is
recorded in the handoff as `posture` (`reused` reports the existing
handoff's). Address: a session
is addressed by id — always routable, unlike a name — but under `#D13` nothing
addresses the daemon, so its identity is optional and recorded for audit;
`recover` re-stamps a row's daemon identity only when it is given one.
The coordinator binary follows `MUSE_BIN` when set, otherwise the daemon's
own invocation path, and only then the packaged `muse` default.

launch outcomes: `launched` (new lane; when the derived tmux name already
exists on the server — live pane or not, tmux refuses it either way
— and this conversation's row does not record it, or another row of this
registry records it, that name is another conversation's lane and the next
free `<name>-2`, `-3`, … is used and recorded — read `tmux_session` from
stdout or the row, never re-derive it), `reused` (same trigger, lane live,
nothing started), `conflict` (exit 3, row NOT touched: a live coordinator
owns the conversation under another trigger, the row's own recorded lane is
live over a non-active row, the recorded lane's liveness is unknown because
its server did not answer, or the same trigger's lane is gone —
`lane absent; run recover`, which orphans it so the next dispatch re-derives
the handoff for the still-pending trigger, archiving the previous document),
`failed` (exit 6, `error: launch_failed`: tmux refused or the coordinator
exited within the launch grace; the freshly written row is left `orphaned`
with the reason in `note`, and with no `tmux_session` when tmux refused to
create the session, so the next launch picks the name afresh).

bind records a coordinator's identity on the ACTIVE row by hand — the repair
path for a lane `recover` could not identify. It also re-attaches a row a human
orphaned or retired while its tmux session still lives (`active`, note
`re-bound`). A row bound to another Muse session is never taken over:
a bind naming a different Muse id answers `identity_conflict` (exit 3)
whatever the row's state, and the row is left as it was.

Environment and arguments: a lane gets the SAME settings as the daemon that
opens it (owner ruling 2026-09-20, spec 25011 FR-31985-6 as amended). The
coordinator does NOT inherit the daemon's shell through tmux (an existing
server hands new panes ITS environment), so the launch passes the gates and
paths explicitly: the lane runtime's own XDG_*_HOME and every
MUSE_EXPERIMENTAL_* variable, the MUSE_DAEMON_* and SLACK_CONNECTOR_* names
this file hands it as `--pass` when present in the daemon's environment, the
admission gates the daemon itself runs under as explicit pairs
(`MUSE_EXPERIMENTAL_TAG=on` - what made this skill visible - and
`MUSE_EXPERIMENTAL_AGENTS=on` when the daemon's own gate read is open; a name
the environment already gives a non-blank value keeps that spelling), the
selected coordinator path as `MUSE_BIN`, plus each `--env KEY=VALUE`. No
reminder gate is forced off: the human's own values ride the passthrough.
The daemon session's own engine arguments (`--model`, `--reasoning-effort`,
`--provider`, `--preset`, `--base-url`, the tool-call switches) are read
from its command line and ride as engine args before any `--muse-arg`, which
wins for a flag it names; posture flags never copy (ADR 38715 D16: the lane
runtime sets `--yolo` under `--unattended`). `lane_settings` on the receipt
names what rode and, when the daemon's argv could not be read, why not.
Names are reported as `env_passthrough`; values are never written to the
registry or the handoff, and stdout carries ids, names and paths only — never
the handoff body, a snapshot line, or an env value (the daemon's context and
session log see stdout).

Exit codes: 0 ok, 2 usage (bad flags, unreadable snapshot), 3 conflict (launch:
another live owner or lane; bind: `identity_conflict`; mark: `lane_live`), 4 not found
(`no_active_row`), 5 registry newer than this helper (fail closed: no write, no new-lane
admission), 6 evidence unavailable or launch failed (no silent state change),
7 registry unavailable (locked, foreign, read-only, or unwritable file/dir).

Configuration: MUSE_DAEMON_REGISTRY (path; default
$XDG_DATA_HOME/muse/daemon/registry.sqlite), MUSE_DAEMON_TMUX (the tmux
command, default `tmux`; tests pass `tmux -L <socket>`),
MUSE_DAEMON_PEER_LIST_CMD (a TEST SEAM over the lane runtime's session-list
read, which needs MUSE_EXPERIMENTAL_EXTERNAL_AGENT_INGRESS=on; honored only
under MUSE_DAEMON_TEST_SEAMS=1 — in a live session it is ignored and named
under `ignored_env`, #28774), MUSE_DAEMON_CONNECTOR_STATUS_CMD (the DEFAULT
connector's `status --json` command only, #37480; default: the sibling
`../../<connector>/scripts/<connector_with_underscores>.py status --json`,
the connector's own verb — its lock file is connector-private; every other
connector is read through the script `start --connector-script` recorded on
its intent row, else that same sibling convention),
MUSE_DAEMON_CONNECTOR_STATUS_TIMEOUT_S (default 15; the connector's `status`
waits on its state lock, which a busy listener holds; `launch` reads the
connector's `env_pass` through the same verb under the same bound),
MUSE_DAEMON_LAUNCH_GRACE_S
(default 1.0), MUSE_LANE_SHELL_START_S (default 10; read HERE and passed to
the lane runtime as `--shell-start-s`; malformed or non-finite reads as 10,
negative as 0), MUSE_DAEMON_LANE_BACKEND (auto|tmux|herdr; read by `start` when
--lane-backend is absent, recorded, then followed by every launch; any other
non-empty value is named under `lane_backend.ignored` and changes nothing; an
empty export reads as unset),
MUSE_DAEMON_REGISTRY_TIMEOUT_S (SQLite busy timeout, default 5;
a launch waits for `<registry>.launch.lock` at most this plus twice the
launch grace plus the shell-start window, the time a healthy launch holds it
from the registry open through the lane start and the grace on either
backend). The busy-timeout, launch-grace and shell-start knobs each read a
malformed or non-finite value as their default and a negative one as 0.
Python 3 standard library only.
"""

import argparse
import datetime as _dt
import fcntl
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

SCHEMA_VERSION = 3
NOTE_MAX = 240
STATES = ("active", "orphaned", "retired")
DESIRED = ("enabled", "disabled")
# #37480 (adr:37480-connector-contract#D3): the connector every intent verb
# means when `--connector` is omitted — today's Slack connector, so every
# existing `start --transport mailbox` line is unchanged. A connector id is
# the connector skill's directory name; `launch --connector` may carry a
# connector-private suffix after `:` (`slack-connector:mailbox`) that the
# helper never interprets beyond splitting it off for the intent key.
DEFAULT_CONNECTOR = "slack-connector"
# adr:37480#D2: the ONE connector whose lane names keep the pre-#37480
# spelling `muse-lane-<suffix>-<alias>` so every recorded name and pin stays
# byte-identical; every other connector's lanes are
# `muse-lane-<connector>-<alias>`. History, not behaviour: it does not move
# with DEFAULT_CONNECTOR.
LEGACY_LANE_NAME_CONNECTOR = "slack-connector"
# The starter rides the tmux command line (capped near 16 KB together with the
# env passthrough). The D16 teaching is charged before QUOTE_LIMITS shrinks the
# quotes, so the cap must fit the worst measured shape — 400-char quotes plus
# the already-sent lines — or a relaunch cuts the requester's own words first.
# 6144 after #28427/#28429/#28428/#28432 (the plan-default, re-arm, short-call
# and monitor-tool teaching): the connector script path rides the prompt three
# times, and for the bundled skill it is ~170 characters
# (`…/plugins/cache/builtin/muse-core/slack-connector/<64-hex>/scripts/…`), so
# the worst shape measures ~5.8 KB with that path (review of #28537). 6656
# while the #27519 QA-round-3 chain lands (#28742): the union of the #28537,
# #28522 and #28448 starter prose does not fit the worst shape under 6144;
# trimming the teaching back is a follow-up. Still far under the ~16 KB tmux
# command-line cap the bound exists for.
PROMPT_MAX = 6656
# `recover` marks an identity it INFERRED (as opposed to one `bind` asserted)
# with this note prefix, so a later pass can tell a revocable guess from a fact.
INFERRED_NOTE = "identity inferred by recover"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_CONFLICT = 3
EXIT_NOT_FOUND = 4
EXIT_NEWER = 5
EXIT_EVIDENCE = 6
EXIT_IO = 7

# Names the daemon's lanes must see beyond the lane runtime's own passthrough
# (XDG_*_HOME and every MUSE_EXPERIMENTAL_*), handed to `launch` as `--pass
# NAME` — names only; the runtime reads each value from this process's
# environment when present. The helper's own names always ride; the
# connector's come from its `status --json` `env_pass` list
# (adr:37480-connector-contract#D1), and a connector that declares none gets
# the Slack tuple below, byte-identical to the pre-#37480 passthrough.
HELPER_ENV_PASS = (
    "MUSE_DAEMON_REGISTRY",
    "MUSE_DAEMON_TMUX",
    "MUSE_DAEMON_PEER_LIST_CMD",
)
LANE_ENV_PASS = HELPER_ENV_PASS + (
    "SLACK_CONNECTOR_STATE_DIR",
    "SLACK_CONNECTOR_MAILBOX_CLI",
    "SLACK_CONNECTOR_MAILBOX_CLI_FAKE",
    "SLACK_CONNECTOR_MAILBOX_STATE_FILE",
    # No mailbox edit/attach switch rides here (#30562): the lane's `reply`
    # decides both by the CLI capability probe alone.
)
# Engine arguments a lane inherits from the daemon session's own command line
# (owner ruling 2026-09-20: the same model, effort and session flags as the
# launcher; spec 25011 FR-31985-6 as amended). Posture flags (`--yolo`, trust,
# approval, sandbox, permission profile) are the lane runtime's under
# `--unattended` (ADR 38715 D16) and never copy; workspace, worktree, resume,
# image, the `daemon` keyword and every positional word are this session's.
INHERITED_ENGINE_FLAGS = ("--model", "--reasoning-effort", "--provider", "--preset", "--base-url")
INHERITED_ENGINE_SWITCHES = ("--parallel-tool-calls", "--no-parallel-tool-calls", "--subagent-worktree-isolation")
# TEST SEAM: a JSON list standing in for the daemon session's argv, honored
# under MUSE_DAEMON_TEST_SEAMS=1 only (named under `ignored_env` otherwise).
LAUNCHER_ARGV_ENV = "MUSE_DAEMON_LAUNCHER_ARGV"
# The lane runtime (adr:25011-daemon-session-coordination#D24): host-manager's
# Muse engine adapter, a sibling in the bundled skills tree the way the
# connector script is (`../host-manager/scripts/lane_runtime.py`, joined
# against the daemon skill dir).
LANE_RUNTIME_RELATIVE = ("..", "..", "host-manager", "scripts", "lane_runtime.py")
INGRESS_GATE = "MUSE_EXPERIMENTAL_EXTERNAL_AGENT_INGRESS=on"
# #28774: the one-line fix `start` puts FIRST on its line when the session
# list is closed by the gate — the connect itself is live, only lane recovery
# waits for a daemon started with the gate on.
INGRESS_CLOSED_HINT = f"restart the daemon with {INGRESS_GATE} to recover existing lanes; connect is live"
PEER_LIST_ENV = "MUSE_DAEMON_PEER_LIST_CMD"
# A daemon may be launched through `muse`, `tbh-dev`, or a locally built
# binary. Coordinators must use that same invocation rather than resolving the
# packaged `muse` from PATH.
DAEMON_BINARY_ENV = "MUSE_BIN"
DAEMON_BINARY_NAMES = frozenset({
    "muse", "muse.exe", "muse.real", "muse.real.exe",
    "tbh", "tbh.exe", "tbh-dev", "tbh-dev.exe", "tbh-bin", "tbh-dev-bin",
})
# The suite's explicit arming flag for the helper's test seams (the
# connector's `mailbox_seams_enabled()` pattern): a seam variable set without
# it is ignored and named on the line; not arming it live is the skill's rule.
TEST_SEAMS_ENV = "MUSE_DAEMON_TEST_SEAMS"

COLUMNS = (
    "connector",
    "conversation",
    "lane",
    "state",
    "handoff_id",
    "handoff_path",
    "event_id",
    "tmux_session",
    "muse_session_id",
    "muse_session_name",
    "peer_address",
    "daemon_session_id",
    "daemon_session_name",
    "created_at",
    "updated_at",
    "validated_at",
    "note",
    # v2 (#31985, adr:31985-fleet-session-awareness D5/D7): WHERE the lane
    # runs. NULL `backend` on a legacy row means tmux with `lane_ref` =
    # `tmux_session`; `tmux_session` never holds a Herdr id.
    "backend",
    "backend_server",
    "lane_ref",
)
BACKENDS = ("tmux", "herdr")
# #37181: the daemon-wide lane backend `start --lane-backend` records beside
# the registry (a sidecar, not a schema step: an older helper ignores it and
# keeps writing the v2 file) and the environment name that seeds it.
LANE_BACKEND_ENV = "MUSE_DAEMON_LANE_BACKEND"
LANE_BACKEND_CHOICES = ("auto", *BACKENDS)
LANE_BACKEND_RECORD = "lane-backend.json"
LANE_BACKEND_IGNORED_REASON = f" (not {'|'.join(LANE_BACKEND_CHOICES)})"  # appended to `lane_backend.ignored`; stripped by value on the summary line
V2_COLUMNS = ("backend", "backend_server", "lane_ref")
# #38715 PR 6 (spec 25011 FR-38715-60/-61; ADR 38715 D7 as amended by
# Amendment 1 D15): the project path. `launch --project` runs the external
# `agents` skill's `init` (its frozen verb contract, `references/verbs.md`
# beside that skill) and the conversation coordinator IS the project's
# coordinator. Opened by the `agents` gate alone; a per-daemon `set
# delegation` is the escape hatch (no environment knob). The agents helper is
# a sibling in the bundled skills tree, as the lane runtime is.
AGENTS_GATE_ENV = "MUSE_EXPERIMENTAL_AGENTS"
AGENTS_GATE_OPEN = ("on", "true", "1")  # the gate registry's parse (crates/config gate_registry/overrides.rs)
TAG_GATE_ENV = "MUSE_EXPERIMENTAL_TAG"
# The admission gates a lane must see, carried explicitly as the launcher
# resolves them (owner ruling 2026-09-20 (b)): `tag` is open for every daemon
# - it is what made this skill visible - and `agents` is the daemon's own
# read (`agents_gate_open`, ADR 38715 D15). The lane runtime's passthrough
# alone would carry only what happens to sit in this process's environment.
LAUNCHER_GATES = (TAG_GATE_ENV, AGENTS_GATE_ENV)
AGENTS_SCRIPT_RELATIVE = ("..", "..", "agents", "scripts", "agents.py")
DELEGATION_CHOICES = ("auto", "thread", "project")
DELEGATION_RECORD = "delegation.json"
AGENTS_TIMEOUT_ENV = "MUSE_DAEMON_AGENTS_TIMEOUT_S"  # the bound on one `agents init` (default DECLARATION_TIMEOUT_S)


class RegistryNewer(Exception):
    """The file's user_version is above what this helper knows."""


class MigrationFailed(Exception):
    """A migration step raised; the transaction was rolled back."""


class RegistryUnavailable(Exception):
    """The registry file or its directory cannot be used (locked, foreign,
    read-only, unwritable). Nothing was changed."""


class UsageError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class EvidenceUnavailable(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class IngressClosed(EvidenceUnavailable):
    """The live session list is closed by the ExternalAgentIngress gate
    (`external_agent_ingress_closed`). `start` catches this one and connects
    without the pass (#28774); every other verb sees plain unavailable
    evidence — `peer_evidence_unavailable`, exit 6 — so a standalone `recover`
    still fails closed."""

    def __init__(self, message):
        super().__init__("peer_evidence_unavailable", message)


# ---------------------------------------------------------------- schema ---


def migrate_to_v1(conn):
    conn.execute(
        """
        CREATE TABLE conversation_owner (
            connector TEXT NOT NULL,
            conversation TEXT NOT NULL,
            lane TEXT,
            state TEXT NOT NULL CHECK (state IN ('active', 'orphaned', 'retired')),
            handoff_id TEXT NOT NULL,
            handoff_path TEXT,
            event_id TEXT NOT NULL,
            tmux_session TEXT,
            muse_session_id TEXT,
            muse_session_name TEXT,
            peer_address TEXT,
            daemon_session_id TEXT,
            daemon_session_name TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            validated_at TEXT,
            note TEXT CHECK (note IS NULL OR length(note) <= 240),
            PRIMARY KEY (connector, conversation)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE connector_intent (
            transport TEXT PRIMARY KEY,
            desired TEXT NOT NULL CHECK (desired IN ('enabled', 'disabled')),
            updated_at TEXT NOT NULL
        )
        """
    )


def migrate_to_v2(conn):
    """#31985: the lane's backend-qualified location — additive, and
    idempotent over a half-applied step (a column already there is skipped).
    Legacy rows are not rewritten: NULL keeps the tmux meaning."""
    present = {row[1] for row in conn.execute("PRAGMA table_info(conversation_owner)").fetchall()}
    for column in V2_COLUMNS:
        if column not in present:
            # `backend` is a two-value enum (D29 item 1); SQLite can attach the
            # CHECK only while the column is added (later needs a rebuild).
            check = " CHECK (backend IS NULL OR backend IN ('tmux', 'herdr'))" if column == "backend" else ""
            conn.execute(f"ALTER TABLE conversation_owner ADD COLUMN {column} TEXT{check}")


def merge_v2_intent(rows, connector):
    """ONE v3 intent row from a v2 file's `connector_intent(transport,
    desired, updated_at)` rows — the migration and the v2 read fallback
    share it: `enabled` when any v2 row was (a recorded connect is never
    lost to a later `disabled` sibling), the newest `updated_at`, and the
    enabled transports as the subscription's source words (every transport
    when none was enabled, so a re-connect knows what was there)."""
    enabled = sorted({row["transport"] for row in rows if row["desired"] == "enabled"})
    sources = enabled or sorted({row["transport"] for row in rows})
    return {
        "connector": connector,
        "desired": "enabled" if enabled else "disabled",
        "updated_at": max(row["updated_at"] for row in rows),
        "script": None,
        "subscriptions": [{"connector": connector, "sources": sources, "filters": []}],
        "prompt": None,
    }


def migrate_to_v3(conn):
    """#37480 (adr:37480-connector-contract#D3/#D10, the destructive step
    ADR 25011 D4 reserves for a new accepted decision): `connector_intent`
    re-keyed from `transport` to the connector id, with the connector script
    and the resolved subscription set (plus the raw prompt) beside `desired`
    and `updated_at`. Runs inside `open_registry`'s one transaction, so a
    failure rolls the rename, the rebuild and `user_version` back together.
    Every v2 row was the Slack connector's: they map to the FROZEN literal
    written here — a migration is history and must not move when
    DEFAULT_CONNECTOR moves."""
    rows = conn.execute("SELECT transport, desired, updated_at FROM connector_intent").fetchall()
    conn.execute("ALTER TABLE connector_intent RENAME TO connector_intent_v2")
    conn.execute(
        """
        CREATE TABLE connector_intent (
            connector TEXT PRIMARY KEY,
            desired TEXT NOT NULL CHECK (desired IN ('enabled', 'disabled')),
            updated_at TEXT NOT NULL,
            script TEXT,
            subscriptions TEXT
        )
        """
    )
    if rows:
        merged = merge_v2_intent(rows, "slack-connector")
        conn.execute(
            "INSERT INTO connector_intent (connector, desired, updated_at, script, subscriptions) VALUES (?, ?, ?, NULL, ?)",
            (merged["connector"], merged["desired"], merged["updated_at"], encode_subscriptions(merged["subscriptions"], None)),
        )
    conn.execute("DROP TABLE connector_intent_v2")


# Known schema versions in ascending order. Additive steps only, except where
# an accepted decision names the destructive step (v3: adr:37480#D3).
MIGRATIONS = [(1, migrate_to_v1), (2, migrate_to_v2), (3, migrate_to_v3)]


def registry_path():
    configured = os.environ.get("MUSE_DAEMON_REGISTRY")
    if configured:
        return configured
    xdg = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(xdg, "muse", "daemon", "registry.sqlite")


def db_timeout():
    # `nan`/`inf` would poison the lock deadline compare (a contender spins
    # forever): non-finite reads as the default, like the other knobs.
    try:
        value = float(os.environ.get("MUSE_DAEMON_REGISTRY_TIMEOUT_S", "5"))
    except ValueError:
        return 5.0
    return max(value, 0.0) if math.isfinite(value) else 5.0


def open_registry(path, migrations=MIGRATIONS):
    """Open for WRITING: migrate a fresh or known-older file inside ONE
    transaction; refuse a newer one. `isolation_level=None` hands transaction
    control to the explicit BEGIN/COMMIT below so DDL and `user_version` roll
    back together. Every SQLite fault is reported as RegistryUnavailable."""
    exists = os.path.exists(path)
    directory = os.path.dirname(path) or "."
    if not exists:
        try:
            ensure_private_dir(directory)
        except OSError as error:
            raise RegistryUnavailable(f"registry directory {directory} unusable: {error}") from error
    try:
        conn = sqlite3.connect(path, isolation_level=None, timeout=db_timeout())
    except sqlite3.Error as error:
        raise RegistryUnavailable(f"registry {path} cannot be opened: {error}") from error
    conn.row_factory = sqlite3.Row
    target = max((version for version, _ in migrations), default=0)
    try:
        if not exists:
            os.chmod(path, 0o600)
        conn.execute("BEGIN IMMEDIATE")
    except (sqlite3.Error, OSError) as error:
        conn.close()
        raise RegistryUnavailable(f"registry {path} unavailable: {error}") from error
    try:
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        if current > target:
            raise RegistryNewer(f"registry user_version {current} is newer than supported {target}")
        for version, step in sorted(migrations, key=lambda item: item[0]):
            if version > current:
                step(conn)
                conn.execute(f"PRAGMA user_version = {int(version)}")
        conn.execute("COMMIT")
    except RegistryNewer:
        conn.execute("ROLLBACK")
        conn.close()
        raise
    except sqlite3.DatabaseError as error:
        _rollback_quietly(conn)
        conn.close()
        raise RegistryUnavailable(f"registry {path} unavailable: {error}") from error
    except Exception as error:  # noqa: BLE001 - every failure rolls back
        _rollback_quietly(conn)
        conn.close()
        raise MigrationFailed(str(error)) from error
    return conn


def _rollback_quietly(conn):
    try:
        conn.execute("ROLLBACK")
    except sqlite3.Error:
        pass


def open_readonly(path):
    if not os.path.exists(path):
        return None
    uri = "file:" + path + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=db_timeout())
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA user_version").fetchone()
    except sqlite3.Error as error:
        raise RegistryUnavailable(f"registry {path} unreadable: {error}") from error
    return conn


def has_table(conn, name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------- helpers ---


def utc_now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def row_dict(row):
    if row is None:
        return None
    # A read-only verb never migrates (`open_readonly`), so a v1 file lacks
    # the v2 columns: they read as NULL, the legacy meaning.
    present = row.keys()
    return {column: (row[column] if column in present else None) for column in COLUMNS}


def row_value(row, column):
    return row[column] if column in row.keys() else None


def row_backend(row):
    """The backend a row's lane runs in: tmux when the row predates v2."""
    return row_value(row, "backend") or "tmux"


def row_lane_ref(row):
    """The backend's handle for the lane — a tmux row's session name (a
    legacy row records it only as `tmux_session`), a Herdr row's pane id —
    or None when the launch created nothing."""
    ref = row_value(row, "lane_ref")
    if ref is None and row_backend(row) == "tmux":
        return row["tmux_session"]
    return ref


def row_backend_server(row):
    return row_value(row, "backend_server")


def lane_words(row):
    """The lane as the row's messages have always named it."""
    if row_backend(row) == "tmux":
        return f"tmux session {row_lane_ref(row)}"
    return f"{row_backend(row)} lane {row_lane_ref(row)}"


def key_of(connector, conversation):
    return f"{connector}/{conversation}"


def handoff_id_for(connector, conversation, event_id):
    digest = hashlib.sha256(f"{connector}\0{conversation}\0{event_id}".encode()).hexdigest()
    return digest[:16]


# ADR 37480 D1/D6 (#37480): what the starter and the handoff know about a
# connector comes from the connector's own `status --json` declaration —
# `reference` (its reference document), `env_pass` (the names a lane needs)
# and `capabilities.<connector id>.{cards, attach, edit}` — looked up by the
# opaque connector id the daemon already holds (D1 rule 1), never parsed
# from it: no transport word and no transport table (D1 Rejected, D3).
# The one exception is the frozen legacy id below: the Slack path renders
# byte-for-byte from this static table with no subprocess at launch (D6's
# byte-equality gate, `test_slack_byte_identity.py`), the same back-compat
# case D2 gives the lane names; the Slack connector declares the identical
# facts and `test_generic_starter.TestSlackDeclaration` keeps the two equal.
LEGACY_CONNECTOR = "slack-connector"
LEGACY_CAPABILITIES = {
    "slack-connector:mailbox": {"cards": True, "attach": True, "edit": True},
    "slack-connector:slack": {"cards": False, "attach": False, "edit": True},
}
LEGACY_REFERENCE = ("references", "slack-ui.md")
LEGACY_ENV_PASS = (
    "SLACK_CONNECTOR_STATE_DIR",
    "SLACK_CONNECTOR_MAILBOX_CLI",
    "SLACK_CONNECTOR_MAILBOX_CLI_FAKE",
    "SLACK_CONNECTOR_MAILBOX_STATE_FILE",
)
BARE_CAPABILITIES = {"cards": False, "attach": False, "edit": False}
DECLARATION_TIMEOUT_S = 15.0
ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def connector_skill(connector):
    """The connector's skill id: the part before the first `:` (a transport
    suffix is the connector's own word, opaque here)."""
    return str(connector or "").split(":", 1)[0]


def connector_transport(connector):
    parts = str(connector or "").split(":", 1)
    return parts[1] if len(parts) == 2 else ""


def connector_declaration(connector, connector_script):
    """What `launch` may say about this connector: `legacy`, `skill`,
    `reference` (absolute path or None), `env_pass` (names), and the three
    capabilities. Legacy id: the static table above (no subprocess). Any
    other id: one bounded `status --json`, and the capabilities are the entry
    under this exact connector id in its `capabilities` map — an id the
    connector did not declare, or a script that cannot answer (no such verb,
    non-zero exit, no JSON object), is the bare shape, never a guess from the
    id."""
    script = os.path.abspath(str(connector_script))
    skill_dir = os.path.dirname(os.path.dirname(script))
    skill = connector_skill(connector)
    if skill == LEGACY_CONNECTOR:
        capabilities = LEGACY_CAPABILITIES.get(str(connector), LEGACY_CAPABILITIES["slack-connector:slack"])
        # Absolute by construction (review of #36345): `--connector-script` is
        # required, and a relative path a caller passed is resolved here.
        return dict(capabilities, legacy=True, skill=skill, env_pass=LEGACY_ENV_PASS,
                    reference=os.path.join(skill_dir, *LEGACY_REFERENCE))
    declared = {}
    try:
        proc = subprocess.run(
            [sys.executable, script, "status", "--json"], capture_output=True, text=True,
            timeout=DECLARATION_TIMEOUT_S, check=False,
        )
        if proc.returncode == 0:
            declared = json.loads(proc.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        declared = {}
    if not isinstance(declared, dict):
        declared = {}
    declared_capabilities = declared.get("capabilities") if isinstance(declared.get("capabilities"), dict) else {}
    entry = declared_capabilities.get(str(connector))
    entry = entry if isinstance(entry, dict) else {}
    capabilities = {name: bool(entry.get(name)) for name in BARE_CAPABILITIES}
    reference = declared.get("reference")
    if isinstance(reference, str) and reference.strip():
        reference = reference if os.path.isabs(reference) else os.path.join(skill_dir, reference)
    else:
        reference = None
    env_pass = declared.get("env_pass")
    if isinstance(env_pass, list):
        env_pass = tuple(name for name in env_pass if isinstance(name, str) and ENV_NAME.match(name))
    else:
        env_pass = ()
    return dict(capabilities, legacy=False, skill=skill, env_pass=env_pass, reference=reference)


def reply_shapes(connector, lane, connector_script, declaration=None):
    """#31044 (owner, 2026-09-07 ~23:52Z, 2026-09-08 ~06:40Z and ~06:55Z): the
    requester reads the thread top-down as what will be done and how, a live
    checklist, then the result - and the plan comes first, not at the end.
    The starter shows the shape once (PROMPT_MAX); this section rides the
    handoff, the one file the starter tells the coordinator to read before a
    plan, so the worked plan and the rules fit in full at no prompt cost.
    Prose the model follows; the connector enforces none of it (D20). Mailbox
    lanes name the file on the summary (`reply --attach`, FR-30781-1); a
    Slack lane has no attach verb, so its two lines leave it out. The item
    marker is the glyph pair ☐ / ✅ at line start: the owner's real Slack
    thread (2026-09-08) showed every `- [ ]` / `- [x]` copy rendered as a
    bare title and lines - the relay's rendering strips markdown task lists,
    so even a working edit showed no progress.
    #35345 QA round 2 (the LAT and UX audits, 2026-09-15): 24/24 card
    journeys spent a median 6 calls (~20 s, worst 58 s) reading the connector
    script, slack_ui.py, the skills dir or --help before the card, because
    the starter bans the skill and nothing here named a card; 5/5 relaunches
    hunted the live card's id and revision (median 92 s) and one rewrote the
    card backwards from the post text quoted in its prompt. `card` gives a
    mailbox lane the contract in this one read, at zero PROMPT_MAX cost; a
    Slack-direct lane has no --message-json route and no entry. Round 3: one
    coordinator spent an `ls -R` on a relative "one level up" description,
    so the reference is named by the absolute path derived from the connector
    script's path (`<skill>/scripts/slack_connector.py` -> `<skill>/references/slack-ui.md`).
    Owner, 2026-09-16 (~04:20Z and ~04:30Z; ADR 35345 D7 Amendment 2): a
    second channel message after a delegated task "is gone" - routed to the
    busy coordinator, it got nothing under "no second acknowledgement" until
    the coordinator acted - and a design asked for before work got a
    card-sized answer. Both are judgment, not rules: `mid_task` is the one
    sentence for a message that lands mid-task, and `when` puts an asked-for
    design first, in full, waiting for the requester's word. Zero starter
    bytes; no timer, ledger or classifier (ADR 25011 D20).
    #35345 QA round 4 (Q2, 2026-09-16; the owner's brief ~13:35Z: the
    conversation "doing the best message type / format when necessary"):
    both yes/no decision samples got prose ending "Want me to delete it?" -
    the card shape had been tied to the word "card" - and the one real
    mid-task new ask got its what/when line as pane narration the requester
    never saw, the answer (already read) over a minute late. `card` now says
    a decision is a card whether or not they said so; `mid_task` says the
    line is a reply and a known answer goes now. Still prose, still zero
    starter bytes.
    Round-4 re-measure (RM, 2026-09-16; owner ~21:00Z, "I think we should
    also encourage the llm in skill to use rich blocks"): status and results
    came back as prose and one options ask as a numbered list, from a
    coordinator that had read slack-ui.md - `card` had tied the rich route
    to decisions. One clause says a status, result, list or choice is a rich
    card when it has more than a sentence of structure; RM F4's 67-71 s
    silences during a 50-s background step get one sentence in `plan`: mark
    the step running before it starts. Prose, zero starter bytes (D20).
    QA round 5 (Q4, 2026-09-17): with that clause in the handoff, 3/3
    coordinators still sent a five-fact status and a five-file list as plain
    text and opened slack-ui.md only at the first decision - the read was
    tied to "when a card is called for" - while every shape chosen after
    the read was the guided one. `card` now names the shapes inline and
    times the one read before the lane's first status, result or list
    reply. Same directive, guidance placement only, zero starter bytes.
    ADR 37480 D1/D6 (#37480): the attach, card and edit clauses ride the
    connector's declared capabilities, never its id; the Slack sentences
    render on the legacy id only (byte-identical) and any other connector's
    `card` entry is one pointer at ITS reference document."""
    declaration = declaration or connector_declaration(connector, connector_script)
    legacy, cards, attach, edit = (declaration[key] for key in ("legacy", "cards", "attach", "edit"))
    reference = declaration["reference"]
    # No backtick or $ anywhere in this text: on a printed-line lane the
    # first plan goes out inside --say "…", where bash runs them (#29766).
    example = (
        "*Plan*\nA wordstats CLI that prints the most frequent words of a text file: one Python script"
        " (argparse + collections.Counter) with unit tests, landing under wordstats/ in the workspace.\n"
        "☐ write wordstats/wordstats.py — argparse, Counter, --top N\n"
        "☐ write and run the tests — wordstats/test_wordstats.py, python3 -m unittest\n"
        "☐ write the README — two worked examples"
        + (", then attach the script to the summary" if attach else "")
    )
    shapes = {
        "when": (
            "More than one step, or expected to run over about a minute: the plan is your first outbound,"
            " right after the daemon's acknowledgement, before any tool work. One step under a minute: no plan,"
            " just the answer. Never a plan only at the end. When the requester asks for the plan or design itself"
            " before work starts, that design is your first outbound, written in full to the depth the problem"
            " needs (goal, what you found, options and trade-offs, recommendation, risks, steps), and you wait for"
            " their word or tap before the work begins; the *Plan* checklist then tracks the work."
        ),
        "plan": (
            "*Plan* on line 1; then ONE sentence: what you will build and how (approach, tools, where it lands);"
            " then one `☐ <step> — <how, or what it produces>` line per step, usually 3-6 (the ☐ glyph at line"
            " start, ✅ once done; never markdown - [ ] / - [x]" + (": Slack strips those" if legacy else "")
            + "); no heading, no lane id."
            # #35345 round-4 re-measure, F4: 3 of 4 tasks went 67-71 s silent
            # while a 50-s background build ran - the tick marks a finish and
            # nothing marked a start. D20 rules out a timer; this is a message.
            " A step you background for longer than about 20 s is marked running (⏳ at line start, or the clause"
            " reworded to running…) in a re-send before it starts, so the requester sees progress without a timer;"
            " the tick after it turns that ⏳ ✅."
        ),
        "example": example,
        # The same literal rule the daemon-coordinator skill carries (#41245; review round 3 of #31059:
        # "When a step finishes, re-send…" was the wording under which a live
        # run batched every ✅ into one edit).
        "tick": (
            TICK_RULE + " - through"
            + (f" `reply --to {lane} --replace-last` (text on stdin)" if edit else
               f" `reply --to {lane}` as a new message (this connector cannot edit a sent message)")
            + ": the sentence and every clause stay; reword a"
            " clause whose outcome changed (a step skipped, a file that landed elsewhere); never a second *Plan*"
            " while the plan is your newest message; tick the last step too, before the summary."
        ),
        # The worked re-send: the example with its first step turned ✅.
        "tick_example": example.replace("☐", "✅", 1),
        "summary": (
            "A new message (never an edit): what was built and where, how to use it, what was not done, and what"
            # #38715 QA r18 F-2: 3/3 daemon-born close-outs ended "want me to remove
            # the worktree?" - the leftover is named, and the requester decides.
            " stayed (a branch, a worktree, a PR) - named as a statement: the close-out never ends in a question;"
            " the requester decides what happens to leftovers afterwards"
            + ("; the deliverable rides it as `--attach <path>`" if attach else "") + "."
        ),
        # One judgment rule, no classifier: the coordinator reads the message
        # and decides; the daemon's acknowledgement covered the task, not this.
        "mid_task": (
            "A message that lands while you are mid-task is yours to read and judge: about the work in flight,"
            " fold it in silently (a question about it still gets its one short answer, then carry on); a new ask,"
            " one line telling the requester what you will do with it and when"
            " (now alongside, or after the current step) - that line is a reply to the requester, never narration"
            " in your own pane, which they cannot see; and if you already know the answer (a fact you just read),"
            " send it now rather than after the step. Never a second acknowledgement of the task already"
            # #38715 QA r17 F-3: two coordinators read the requester's answer to their
            # close-out as "a repeat of the delegation" and sent nothing.
            " acknowledged - but a later message from them is answered even when its words repeat an"
            " earlier one (a second yes after the go, their answer to your closing question): a new line"
            " is never a repeat."
        ),
    }
    if cards and not legacy and reference:
        # A connector that declares cards teaches them in its own reference
        # (ADR 37480 D1: markup and cards are connector-private); one without
        # a reference gives the coordinator nothing to read, so no entry.
        shapes["card"] = (
            "A yes/no or bounded decision you need from the requester is a card with controls whether or not"
            " they said card; a status, result, list or choice is a rich card when it has more than a sentence"
            " of structure, plain text for one-liners. The shapes, the copy-ready calls and what each result"
            f" line means: {reference} - read that one file once, before your first status, result or list"
            " reply in this lane and whenever a card is called for (a decision calls for one; a status or a"
            " list earns one too); never the connector's scripts, a SKILL.md or --help. When a card will carry"
            " the steps, the card IS the plan: post the card first, never a *Plan* list and a card for one job."
        )
    if cards and legacy:
        # No `$` here either: a clause copied into a shell must not expand.
        shapes["card"] = (
            "A Slack card (buttons, Approve/Cancel, a choice, a result with controls) is ONE call:"
            f" reply --to {lane} --message-json - with {{\"text\": ..., \"blocks\": [...]}} on stdin;"
            f" reply --to {lane} --replace-last --message-json - edits that card and needs no id or revision"
            " from you (the connector holds them); a click arrives as one line,"
            f" {lane} <user> [ui]: <action> (button) = <value>, and your next call answers it. A yes/no or"
            " bounded decision you need from the requester (delete this? which of these? approve?) is a card"
            " with buttons whether or not they said card: prose ending in want me to? leaves them typing; a"
            " card gives them a tap. A status, result, list or choice is a rich card - fields, lists, preformatted,"
            " select - when it has more than a sentence of structure; plain text for one-liners (the reference's"
            # #35345 QA round 5 (Q4): the shapes named inline, so a status or a
            # list is composed as a card without waiting for the word card.
            " layout section says which block fits which content): a status or result with more than two facts"
            " is a header, a fields section of label/value pairs and one context line, never paragraphs or a"
            " code fence; a list of files, steps or findings is a rich_text_list (a table when the items have"
            " columns), never dash bullets; command output and paths are rich_text_preformatted. A mailbox"
            " lane the relay did not originate refuses this call (ui_needs_relay_lane) - reply there with"
            " --text. When a card will carry the steps, the card IS the plan: arm without --say and post the card"
            " first, never a *Plan* list and a card for one job. Six copy-ready calls and what pending and"
            # QA round 5: the read used to wait for a card to be "called for",
            # so the layout section was never in context for a status or a list.
            f" each [ui] result line mean: {reference} - read that one file once, before your first status,"
            " result or list reply in this lane and whenever a card is called for (a decision calls for one; a"
            " status or a list earns one too); never"
            " slack_connector.py, slack_ui.py, a SKILL.md or"
            " --help. After a relaunch the card is still this lane's live card: the same --replace-last"
            " edits it, no status, state, log or script read first; derive its state from the clicks"
            " already answered (an answered Approve means that step ran), never move a card backwards,"
            " and if unsure say so in the update. The bracketed [card rev N, after ...] prefix on an Already"
            " sent line is provenance for you, never part of the text you send."
        )
    return shapes


def watch_shape(lane, slug):
    """#41802 (owner rulings 56/56a/57/59; spec 25011 FR-41802-1(j)): the
    project's watcher, said in the handoff of a PROJECT lane only — the agents
    skill sits behind its own gate, so a plain lane never hears of it. No
    backtick or $ (a clause may be pasted into a shell)."""
    return (
        f"go starts the project's watch: every 20 s it reads the threads' own records and sessions, edits your plan"
        " post in place by id once you have posted it (the daemon set the sink; nothing before that post is touched,"
        " and the same message a later answer of yours never displaces) -"
        " at once when a thread turns blocked, done, failed or stopped (an inbox event: the wake loop prints it, the"
        " Monitor wakes you) and on a decaying cadence otherwise (every minute for the first ten minutes, then less"
        f" often). You never post a rolling progress message. Another pace on the requester's word: set {slug} every"
        " 2m|10m|quiet|auto (quiet = transitions only); a periodic wake for yourself, only if they want one:"
        f" set {slug} heartbeat 5|off. The rows are the watcher's (mark, name, what it owns, elapsed, one fact from the"
        " thread's report or commit); your words go under them. The table and example rows: the daemon-coordinator"
        " skill's references/progress-and-replies.md, Progress edits."
    )


def handoff_address(connector, snapshot):
    """#29738: the id the requester writes to - this daemon's own mailbox, which
    the connector records as the `from` of every outbound line in its snapshot
    (its `client_mailbox_id`; the literal `connector` when it has none). The
    starter names it, so "which mailbox do I use?" is never answered with the
    requester's own id. Mailbox only - on Slack they write to a channel - and
    None when the snapshot shows no outbound line (a hand-written one). The
    word is the Slack connector's (ADR 37480 D1): any other connector's
    starter carries no address line."""
    if connector_skill(connector) != LEGACY_CONNECTOR or connector_transport(connector) != "mailbox":
        return None
    for event in reversed(snapshot):
        if isinstance(event, dict) and event.get("direction") == "outbound":
            sender = event.get("from")
            if isinstance(sender, str) and sender.strip() and sender != "connector":
                return sender
            return None
    return None


def sanitize(raw):
    return re.sub(r"[^A-Za-z0-9_-]+", "-", raw).strip("-")


def default_lane(conversation):
    return sanitize(conversation)[:40] or "lane"


def default_tmux_session(connector, lane):
    """`muse-lane-<connector>-<alias>` (adr:37480-connector-contract#D2): two
    connectors' `c1` are two names. The Slack connector keeps its pre-#37480
    spelling, `muse-lane-<the word after the colon>-<alias>`
    (`muse-lane-mailbox-c3`), so no recorded name or pin moves."""
    connector_id, _, suffix = connector.partition(":")
    short = (suffix or connector_id) if connector_id == LEGACY_LANE_NAME_CONNECTOR else connector
    return "muse-lane-" + sanitize(f"{short}-{lane}")


def connector_id_of(connector):
    """The intent key of a `--connector` value: the connector skill id before
    any connector-private `:suffix` (`slack-connector:mailbox` ->
    `slack-connector`); the suffix is never read."""
    return connector.partition(":")[0]


def daemon_namespace(registry_path):
    """Six hex characters that name THIS daemon: a stable digest of its
    registry path. Two daemons sharing one Herdr workspace both delegate to
    lane `c1`; without this suffix on the Herdr tab label the second launch is
    `name_taken` by the other daemon's live coordinator and the daemon answers
    the request itself (#35048). tmux lanes need none: each daemon owns a
    private tmux server. `realpath`, not `abspath`: one registry file reached
    through a symlink or a relative path is still ONE daemon (review of
    #35216)."""
    return hashlib.sha256(os.path.realpath(registry_path).encode("utf-8")).hexdigest()[:6]


def check_note(note):
    if note is not None and len(note) > NOTE_MAX:
        raise UsageError("note_too_long", f"--note must be at most {NOTE_MAX} characters")
    return note


def handoff_dir(registry):
    return os.path.join(os.path.dirname(registry) or ".", "handoffs")


def lane_backend_record_path(registry):
    return os.path.join(os.path.dirname(registry) or ".", LANE_BACKEND_RECORD)


def read_lane_backend(registry):
    """The daemon-wide lane backend `start --lane-backend` recorded (#37181),
    or None when nothing is recorded or the record is unreadable — no
    judgment, so `launch` asks `context` as `auto` does (ADR 31985 D5)."""
    try:
        with open(lane_backend_record_path(registry), encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError):
        return None
    backend = record.get("backend") if isinstance(record, dict) else None
    return backend if backend in LANE_BACKEND_CHOICES else None


def write_lane_backend(registry, backend, source):
    """Record the daemon-wide lane backend privately and atomically beside the
    registry (the directory `open_registry` already created)."""
    path = lane_backend_record_path(registry)
    directory = os.path.dirname(path) or "."
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".lane-backend-", suffix=".json", dir=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"backend": backend, "source": source, "updated_at": utc_now()}, handle)
            handle.write("\n")
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, path)
    except OSError as error:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)  # a failed chmod/replace must not leave a temp file per start
            except OSError:
                pass
        raise RegistryUnavailable(f"lane backend record {path} unwritable: {error}") from error


def start_lane_backend(requested, registry):
    """`start`'s lane backend (#37181): the flag, else `MUSE_DAEMON_LANE_BACKEND`,
    else the record a previous `start` left, else `auto` — as
    `{backend, source}`; a non-empty value outside auto|tmux|herdr is named
    under `ignored` and loses only the knob, never the connect (Constitution
    XIII); an empty export reads as unset."""
    if requested:
        return {"backend": requested, "source": "flag"}
    report = {}
    from_env = os.environ.get(LANE_BACKEND_ENV)
    if from_env:
        if from_env in LANE_BACKEND_CHOICES:
            return {"backend": from_env, "source": "env"}
        report["ignored"] = f"{LANE_BACKEND_ENV}={from_env}{LANE_BACKEND_IGNORED_REASON}"
    recorded = read_lane_backend(registry)
    if recorded is not None:
        report.update(backend=recorded, source="recorded")
    else:
        report.update(backend="auto", source="default")
    return report


def delegation_record_path(registry):
    return os.path.join(os.path.dirname(registry) or ".", DELEGATION_RECORD)


def read_delegation(registry):
    """The per-daemon `set delegation` record (FR-38715-60) as `{mode,
    source}`: `recorded` when a record names a known mode, else `{auto,
    default}` — an unreadable or malformed record is the default, never a
    refusal."""
    try:
        with open(delegation_record_path(registry), encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError):
        return {"mode": "auto", "source": "default"}
    mode = record.get("mode") if isinstance(record, dict) else None
    if mode not in DELEGATION_CHOICES:
        return {"mode": "auto", "source": "default"}
    return {"mode": mode, "source": "recorded"}   # the FR-37181-2 shape (spec 25011 FR-38715-30)


def write_delegation(registry, mode):
    """Record the human's explicit choice privately and atomically beside the
    registry (the same shape as the lane backend record)."""
    path = delegation_record_path(registry)
    directory = os.path.dirname(path) or "."
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".delegation-", suffix=".json", dir=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"mode": mode, "source": "recorded", "updated_at": utc_now()}, handle)
            handle.write("\n")
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, path)
    except OSError as error:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)  # a failed chmod/replace must not leave a temp file per set
            except OSError:
                pass
        raise RegistryUnavailable(f"delegation record {path} unwritable: {error}") from error


def agents_gate_open():
    return (os.environ.get(AGENTS_GATE_ENV) or "").strip().lower() in AGENTS_GATE_OPEN


def launcher_gates():
    """`{name: "on" | "closed"}` — the admission gates as this daemon resolves
    them: `tag` open by construction (the skill is visible only under it),
    `agents` by the daemon's own read."""
    return {TAG_GATE_ENV: "on", AGENTS_GATE_ENV: "on" if agents_gate_open() else "closed"}


def launcher_gate_pairs():
    """The explicit `--env NAME=on` pair for each open gate - explicit even
    when the environment already says so, so the lane's admission never rests
    on what happened to sit in this process's environment."""
    return [f"{name}=on" for name, state in launcher_gates().items() if state == "on"]


def lane_sees_agents_skill(pairs):
    """From the launch facts alone — the env pairs the lane gets, last value
    per name over the passthrough — whether the lane's catalog admits the
    agents skill (`tag` OR `agents` open, ADR 38715 D15)."""
    view = {name: os.environ.get(name, "") for name in LAUNCHER_GATES}
    for item in pairs:
        name, sep, value = item.partition("=")
        if sep and name in view:
            view[name] = value
    return any(view[name].strip().lower() in AGENTS_GATE_OPEN for name in LAUNCHER_GATES)


def inherited_engine_args(argv, explicit):
    """The launcher's session-shaping flags as one `--flag=value` token each
    (a repeatable flag keeps every value, in order), minus any flag the
    caller's own engine args name in either token shape. Nothing else of the
    launcher's argv is copied."""
    if not argv:
        return []
    named = {item.partition("=")[0] for item in explicit or []}
    out = []
    tokens = list(argv[1:])
    index = 0
    while index < len(tokens):
        token = tokens[index]
        flag, sep, value = token.partition("=")
        if flag in INHERITED_ENGINE_FLAGS:
            if not sep:
                if index + 1 >= len(tokens):
                    break
                index += 1
                value = tokens[index]
            if flag not in named:
                out.append(f"{flag}={value}")
        elif token in INHERITED_ENGINE_SWITCHES and token not in named:
            out.append(token)
        index += 1
    return out


def agents_script_path():
    here = os.path.dirname(os.path.realpath(__file__))
    return os.path.normpath(os.path.join(here, *AGENTS_SCRIPT_RELATIVE))


def project_slug(text, limit=28):
    words = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    slug = words[:limit].rstrip("-")
    return slug or "project"


def project_channel(connector, conversation):
    return f"{connector}/{conversation}"


def run_agents(argv, cwd):
    """One `agents` verb as a subprocess in the daemon's workspace:
    `(payload, exit code)`; a helper that prints no JSON line is unavailable
    evidence (`agents_unavailable`), a helper that cannot run is `agents_missing`."""
    script = agents_script_path()
    # The agents helper records its CALLER as the project's coordinator from
    # `MUSE_LANE_BACKEND`/`MUSE_LANE_REF`, else from its process tree; a
    # Herdr-bootstrapped daemon carries both, and with them stripped the walk
    # climbed to the daemon's own session (QA r11 DM D-R11-DM-2). The
    # coordinator must be the lane, never the daemon (INV-38715-61; review of
    # #38876): the daemon says it is a launcher opening that lane afterwards,
    # so `init` records no coordinator and the lane's first `resume` binds.
    # Nothing else of the environment moves.
    env = {key: value for key, value in os.environ.items() if key not in ("MUSE_LANE_BACKEND", "MUSE_LANE_REF")}
    env["MUSE_AGENTS_ROLE"] = "launcher"
    try:
        timeout = float(os.environ.get(AGENTS_TIMEOUT_ENV) or DECLARATION_TIMEOUT_S)
    except ValueError:
        timeout = DECLARATION_TIMEOUT_S
    try:
        # Bounded: this runs inside the launch transaction (review of #38876),
        # so a hung helper must not hold every other registry writer.
        proc = subprocess.run([sys.executable or "python3", script, *argv], capture_output=True, text=True,
                              check=False, cwd=cwd, stdin=subprocess.DEVNULL, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"outcome": "failed", "error": "agents_unavailable",
                "message": f"agents {argv[0]} printed no JSON line within {timeout:g}s (killed)"}, EXIT_EVIDENCE
    except OSError as error:
        return {"outcome": "failed", "error": "agents_missing", "message": f"agents helper could not run: {error}"}, EXIT_EVIDENCE
    for line in proc.stderr.splitlines()[-20:]:
        if line.strip():
            sys.stderr.write(f"agents: {line}\n")
    payload = last_json_line(proc.stdout)
    if not payload:
        return {"outcome": "failed", "error": "agents_unavailable",
                "message": f"agents {argv[0]} printed no JSON line (exit {proc.returncode})"}, EXIT_EVIDENCE
    return payload, proc.returncode


def create_project(request, slug, requester, workspace, retry_suffix):
    """`agents init` for one hand-off (FR-38715-61): the requester's line as
    the task — ONE argv token after `--`, verbatim, so a flag-shaped word in
    or at the head of the goal never reads as one of `init`'s flags (review of
    #38876) — the slug from
    its first words (one retry with the handoff's suffix when taken),
    unattended (the internal lanes' posture, passed explicitly), asked-by the
    requester when named. Returns the receipt's `project` value: `created`
    with `slug` and `path`, or `failed` with the first thing wrong — never
    raises: the thread launch goes on either way (Constitution XIII;
    FM-38715-60)."""
    script = agents_script_path()
    if not os.path.isfile(script):
        return {"outcome": "failed", "error": "agents_missing",
                "message": f"agents helper not found at {script}: the agents skill ships it beside the daemon"}
    candidates = (slug, f"{slug}-{retry_suffix}")
    for attempt, candidate in enumerate(candidates):
        # The flags first, then argparse's `--`, then the goal as ONE token: a
        # goal that IS or STARTS WITH a flag-shaped word still lands verbatim
        # (review of #38876; the frozen helper's `task` is a `nargs="+"` positional).
        argv = ["init", "--slug", candidate, "--unattended"]
        if requester:
            argv += ["--asked-by", requester]
        argv += ["--", request or "(no request text)"]
        payload, code = run_agents(argv, workspace)
        outcome = payload.get("outcome")
        if payload.get("error") == "agents_unavailable" and "(killed)" in str(payload.get("message", "")):
            # The helper makes the folder before it prints its line, so a kill
            # at the bound may leave a whole or torn project nobody is told
            # about (K-38715-3): name the slug it was given.
            payload["message"] += f"; project {candidate} may exist without a coordinator - archive it through the agents skill"
        if code == 0 and outcome == "initialized":
            return {"outcome": "created", "slug": payload.get("slug") or candidate, "path": payload.get("path") or ""}
        if outcome == "slug_taken":
            if attempt == 0:
                continue
            return {"outcome": "failed", "error": "slug_taken",
                    "message": f"projects {candidates[0]} and {candidates[1]} both exist"}
        error = payload.get("error") if outcome == "failed" else (outcome or "failed")
        message = payload.get("message") or (payload.get("error") if outcome != "failed" else None) or f"agents init exited {code}"
        return {"outcome": "failed", "error": str(error), "message": str(message)}


def resolve_project(asked, registry):
    """Whether this launch opens a project (FR-38715-61; ADR 38715 Amendment
    1 D15 as landed): a recorded `project` WINS over a closed gate — the
    human asked for it and the three skills are visible under `tag` — so it
    is checked first; `thread` refuses; `auto` follows the daemon's
    per-dispatch `--project`, which the gate must admit. `(wanted, project)`:
    `project` is the receipt's `skipped` value when the answer is no for a
    reason worth a line, None when nothing was asked."""
    mode = read_delegation(registry)["mode"]
    if mode == "project":
        return True, None
    if not asked:
        return False, None
    if mode == "thread":
        return False, {"outcome": "skipped", "reason": "delegation_thread"}
    if not agents_gate_open():
        return False, {"outcome": "skipped", "reason": "agents_gate_closed"}
    return True, None


def ensure_private_dir(directory):
    """Create `directory` 0700 (whatever the umask). A directory that already
    exists keeps its mode: `MUSE_DAEMON_REGISTRY` may point into a directory
    the operator shares, and the helper's files are private on their own
    (0600), so it never strips group/other access it did not grant (#27866)."""
    if os.path.isdir(directory):
        return
    os.makedirs(directory, mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)


def write_handoff_file(registry, handoff):
    """Write the immutable handoff privately and atomically; the coordinator
    reads it by path, so the snapshot never rides a command line."""
    directory = handoff_dir(registry)
    path = os.path.join(directory, f"{handoff['handoff_id']}.json")
    try:
        ensure_private_dir(directory)
        fd, tmp_path = tempfile.mkstemp(prefix=".handoff-", suffix=".json", dir=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            # ensure_ascii=False (#31044 review): the coordinator copies the
            # worked plan out of this file, so ☐ / ✅ / — must be the glyphs
            # on disk, never `\u2610` escapes.
            json.dump(handoff, handle, indent=1, ensure_ascii=False)
            handle.write("\n")
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, path)
    except OSError as error:
        raise RegistryUnavailable(f"handoff directory {directory} unwritable: {error}") from error
    return path


def archive_handoff_file(path, stamp):
    """A same-trigger relaunch derives the same handoff_id (FR-25011-17), so
    the previous lane's document at `path` is kept beside the new one as
    `<handoff_id>.<stamp>.<unique>.retired.json` (0600) instead of being
    overwritten (#27889). Returns the archive path, or None when nothing was
    there."""
    if not os.path.exists(path):
        return None
    directory = os.path.dirname(path)
    stem = os.path.basename(path)[: -len(".json")]
    try:
        fd, archive = tempfile.mkstemp(prefix=f"{stem}.{stamp}.", suffix=".retired.json", dir=directory)
        os.close(fd)
        os.replace(path, archive)
        os.chmod(archive, 0o600)
    except OSError as error:
        raise RegistryUnavailable(f"handoff {path} could not be archived: {error}") from error
    return archive


def lane_runtime_path():
    here = os.path.dirname(os.path.realpath(__file__))
    return os.path.normpath(os.path.join(here, *LANE_RUNTIME_RELATIVE))


def require_lane_runtime():
    """The lane runtime must be there before a verb writes anything: a
    daemon whose bundle lacks host-manager opens no lane and says why."""
    path = lane_runtime_path()
    if not os.path.isfile(path):
        raise EvidenceUnavailable(
            "lane_runtime_missing",
            f"lane runtime not found at {path}: the host-manager skill ships it beside the daemon; nothing was written",
        )
    return path


def herdr_offer_record_for(registry):
    return os.path.join(os.path.dirname(registry) or ".", "herdr-offer.json")


def lane_runtime_flags():
    """The global flags every lane runtime call from this helper carries -
    the ONE builder for `run_lane_runtime` and the prefix `start` prints
    (review of PR #39786: the two cannot drift apart). `MUSE_DAEMON_TMUX`
    rides as `--tmux`; the human's recorded `no` to Herdr (the D30 offer
    record beside this registry) is the one thing that keeps the runtime
    from selecting or starting Herdr for this daemon's lanes (ADR 38715 D3
    as ruled 2026-09-19); the runtime reads its own copy otherwise. `main`
    exports the resolved `--registry` as MUSE_DAEMON_REGISTRY, so the record
    beside it is the one `registry_path()` names (review of #38758)."""
    flags = []
    tmux = os.environ.get("MUSE_DAEMON_TMUX")
    if tmux:
        flags += ["--tmux", tmux]
    flags += ["--herdr-offer", herdr_offer_record_for(registry_path())]
    return flags


def host_manager_context():
    """`start`'s `context` (#38715 QA round 11 D-R11-DM-1): the prefix every
    host-manager verb the daemon runs by hand starts with - the sibling
    runtime plus the same flags the daemon's own runtime calls carry -
    quoted the way the runtime's own `command_prefix` is. A bare
    `lane_runtime.py list` shows the DEFAULT server (a stranger's session,
    the human's real Herdr panes) and never the daemon's own lanes; the
    daemon copies this prefix instead of an env var it never echoes."""
    return {"command_prefix": shlex.join(["python3", lane_runtime_path(), *lane_runtime_flags()])}


def run_lane_runtime(*verb, stdin=None):
    """One lane runtime verb as a subprocess: `(payload, exit code)`, the
    payload being its one JSON line. `MUSE_DAEMON_TMUX` rides as `--tmux`.
    Its stderr is relayed on this helper's stderr (the connector folds that
    into its diagnostics); a runtime that is missing, cannot run, or prints
    no JSON is unavailable evidence — exit 6; the verb decides what its row
    says (`launch` records a failed launch)."""
    argv = [sys.executable or "python3", require_lane_runtime(), *lane_runtime_flags(), *verb]
    io = {"input": stdin} if stdin is not None else {"stdin": subprocess.DEVNULL}
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, check=False, **io)
    except OSError as error:
        raise EvidenceUnavailable("lane_runtime_missing", f"lane runtime could not run: {error}") from error
    payload = None
    for line in reversed(proc.stdout.splitlines()):
        if line.strip().startswith("{"):
            try:
                payload = json.loads(line)
            except ValueError:
                payload = None
            break
    # The runtime writes each progress step to stderr as it happens AND
    # carries it in the line's `progress`; relaying the echo rode into a
    # connector's tool output (QA r8, #38715). Anything else it says stays.
    echoes = set(payload.get("progress") or []) if isinstance(payload, dict) else set()
    kept = [line for line in proc.stderr.splitlines() if line.strip() and line not in echoes]
    if kept:
        sys.stderr.write("\n".join(kept) + "\n")
    if not isinstance(payload, dict):
        raise EvidenceUnavailable(
            "lane_runtime_unavailable",
            f"lane runtime {verb[0]} printed no JSON line (exit {proc.returncode})",
        )
    return payload, proc.returncode


def lane_evidence_error(payload):
    """A lane runtime error line as this helper's exception: the same codes
    the verbs answered before the extraction, and the ingress-closed arm
    `start` handles on its own."""
    outcome = payload.get("outcome")
    message = str(payload.get("message") or "")
    if outcome == "peer_evidence_unavailable":
        if payload.get("code") == "ingress_closed":
            return IngressClosed(message)
        return EvidenceUnavailable("peer_evidence_unavailable", message)
    if outcome in ("tmux_unavailable", "herdr_unavailable"):
        return EvidenceUnavailable(outcome, message)
    return EvidenceUnavailable(outcome or "lane_runtime_unavailable", message or "lane runtime answered no outcome")


# ---------------------------------------------------------- daemon binary ---


def proc_parent(pid):
    """Return `(parent_pid, argv0)` for one local process."""
    if sys.platform == "darwin":
        try:
            proc = subprocess.run(
                ["ps", "-p", str(pid), "-o", "ppid=,comm="],
                capture_output=True,
                text=True,
                errors="replace",
                check=False,
                timeout=DECLARATION_TIMEOUT_S,  # one hop of a 32-hop walk: a stuck ps ends the walk, never the helper
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0:
            return None
        fields = proc.stdout.strip().split(None, 1)
        if len(fields) != 2:
            return None
        try:
            parent = int(fields[0])
        except ValueError:
            return None
        return parent, fields[1].strip()
    try:
        with open(f"/proc/{pid}/status", encoding="utf-8") as handle:
            parent = None
            for line in handle:
                if line.startswith("PPid:"):
                    fields = line.split()
                    parent = fields[1] if len(fields) > 1 else None
                    break
        with open(f"/proc/{pid}/cmdline", "rb") as handle:
            argv0 = handle.read().split(b"\0", 1)[0].decode(errors="replace")
        return int(parent) if parent else None, argv0
    except (OSError, ValueError):
        return None


def _proc_executable(pid):
    if sys.platform == "darwin":
        try:
            import ctypes

            libproc = ctypes.CDLL("/usr/lib/libproc.dylib")
            libproc.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
            libproc.proc_pidpath.restype = ctypes.c_int
            buffer = ctypes.create_string_buffer(4096)
            size = libproc.proc_pidpath(pid, buffer, len(buffer))
            if size > 0:
                return os.path.realpath(os.fsdecode(buffer.value))
        except (AttributeError, OSError, TypeError, ValueError):
            return None
        return None
    try:
        return os.path.realpath(f"/proc/{pid}/exe")
    except OSError:
        return None


def _executable_file(path):
    return bool(path and os.path.isfile(path) and os.access(path, os.X_OK))


def _proc_search_path(pid):
    """The PATH process `pid` runs with, from `/proc/<pid>/environ`; None when
    the environment is unreadable or carries no PATH."""
    try:
        with open(f"/proc/{pid}/environ", "rb") as handle:
            for entry in handle.read().split(b"\0"):
                if entry.startswith(b"PATH="):
                    return entry[len(b"PATH="):].decode(errors="replace")
    except OSError:
        return None
    return None


def _resolve_binary(argv0, pid):
    """The daemon process `pid`'s executable as a live path, or None.

    The running image `/proc/<pid>/exe` is that executable by definition and
    wins when it carries a daemon name. Otherwise argv0 is resolved the way
    the daemon's own exec did: a path against the daemon's working directory,
    a bare name through the daemon's PATH — never through this helper's
    directory or PATH, which can name a binary the daemon never ran. A
    daemon environment that is unreadable or carries no PATH resolves
    nothing: failing closed keeps the walk going (or ends on the loud miss
    line) instead of a silent wrong binary.
    """
    executable = _proc_executable(pid)
    if os.path.basename(executable or "") in DAEMON_BINARY_NAMES and _executable_file(executable):
        return executable
    if os.path.sep in argv0:
        candidate = argv0
        if not os.path.isabs(candidate):
            candidate = os.path.join(f"/proc/{pid}/cwd", candidate)
        candidate = os.path.realpath(candidate)
        return candidate if _executable_file(candidate) else None
    search = _proc_search_path(pid)
    if search is None:
        return None
    candidate = shutil.which(argv0, path=search)
    return os.path.realpath(candidate) if _executable_file(candidate) else None


def _parse_procargs2(raw):
    """argv out of a macOS `KERN_PROCARGS2` buffer: argc (a native int), the
    executable path, NUL padding, then argc NUL-terminated argument strings
    (the environment follows and is not read)."""
    if len(raw) < 4:
        return None
    import struct

    argc = struct.unpack("@i", raw[:4])[0]
    rest = raw[4:]
    end = rest.find(b"\0")
    if argc <= 0 or end < 0:
        return None
    parts = rest[end:].lstrip(b"\0").split(b"\0")
    argv = [part.decode(errors="replace") for part in parts[:argc]]
    return argv if len(argv) == argc else None


def _procargs2(pid):
    """The exact argv of one macOS process through `sysctl KERN_PROCARGS2`
    (same user), or None: `ps -o args=` joins the words with spaces and a
    path such as `/Applications/Muse Code.app/...` cannot be split back."""
    try:
        import ctypes

        libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
        argmax = ctypes.c_int(0)
        size = ctypes.c_size_t(ctypes.sizeof(argmax))
        mib = (ctypes.c_int * 2)(1, 8)  # CTL_KERN, KERN_ARGMAX
        if libc.sysctl(mib, 2, ctypes.byref(argmax), ctypes.byref(size), None, 0) != 0 or argmax.value <= 0:
            return None
        buffer = ctypes.create_string_buffer(argmax.value)
        size = ctypes.c_size_t(argmax.value)
        mib = (ctypes.c_int * 3)(1, 49, pid)  # CTL_KERN, KERN_PROCARGS2, pid
        if libc.sysctl(mib, 3, buffer, ctypes.byref(size), None, 0) != 0:
            return None
        return _parse_procargs2(buffer.raw[: size.value])
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _proc_argv(pid):
    """The full command line of one local process, or None."""
    if sys.platform == "darwin":
        argv = _procargs2(pid)
        if argv:
            return argv
        try:
            proc = subprocess.run(["ps", "-p", str(pid), "-o", "args="], capture_output=True, text=True,
                                  errors="replace", check=False, timeout=DECLARATION_TIMEOUT_S)
        except (OSError, subprocess.TimeoutExpired):
            return None
        line = proc.stdout.strip() if proc.returncode == 0 else ""
        if not line:
            return None
        try:
            return shlex.split(line)
        except ValueError:
            return line.split()
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as handle:
            raw = handle.read()
    except OSError:
        return None
    return [part.decode(errors="replace") for part in raw.split(b"\0") if part] or None


LAUNCHER_ARGV_SOURCE = "launcher argv"
NO_DAEMON_ANCESTOR = "no daemon ancestor: this helper was not run below a Muse session"


def walk_ancestors():
    """Every ancestor of this helper, nearest first: `(pid, argv0, is_daemon)`
    per hop, at most 32 hops, ending at pid 1, a repeated pid or a hop the
    process table cannot answer. The ONE walk both the binary resolution and
    the launcher-argv read make (review of #39393: two copies had diverged)."""
    pid = os.getppid()
    seen = set()
    for _ in range(32):
        if pid <= 1 or pid in seen:
            return
        seen.add(pid)
        info = proc_parent(pid)
        if info is None:
            return
        parent, argv0 = info
        yield pid, argv0, os.path.basename(argv0) in DAEMON_BINARY_NAMES
        if parent is None:
            return
        pid = parent


def launcher_argv():
    """`(argv, source)` of the daemon session this helper runs below: the seam
    under MUSE_DAEMON_TEST_SEAMS=1 (a JSON list; JSON `null` stands in for a
    walk that finds nothing), else the nearest daemon-named ancestor whose
    command line can be read - one that cannot is skipped, as the binary
    resolution skips a dead match. `(None, reason)` when it cannot be
    learned - nothing is guessed."""
    seam = os.environ.get(LAUNCHER_ARGV_ENV)
    if seam and test_seams_enabled():
        try:
            argv = json.loads(seam)
        except ValueError:
            argv = ""
        if argv is None:
            return None, NO_DAEMON_ANCESTOR
        if isinstance(argv, list) and all(isinstance(item, str) for item in argv):
            return argv, "seam"
        return None, f"{LAUNCHER_ARGV_ENV} is not a JSON list of strings"
    if not os.path.isdir("/proc") and sys.platform != "darwin":
        return None, "no process table on this platform"
    unreadable = []
    for pid, _argv0, is_daemon in walk_ancestors():
        if not is_daemon:
            continue
        argv = _proc_argv(pid)
        if argv:
            return argv, LAUNCHER_ARGV_SOURCE
        unreadable.append(str(pid))
    if unreadable:
        return None, f"the daemon process {', '.join(unreadable)} did not show a command line"
    return None, NO_DAEMON_ANCESTOR


def daemon_binary_path():
    """Use the explicit binary override, otherwise the daemon's invocation.

    The registry runs several process hops below the daemon, so inspect the
    parent chain rather than resolving the ambient `muse` PATH entry. An
    ancestor that carries a daemon name but no live executable is skipped, so
    a dead inner match cannot shadow a live outer one; when the walk ends
    with only dead matches, one stderr line names them (stdout stays the one
    JSON line) so the operator knows to set MUSE_BIN. A chain with no daemon
    in it is the normal direct-helper case and stays quiet, as does a missing
    process table: `muse` remains the direct-helper and non-Unix fallback.
    """
    configured = os.environ.get(DAEMON_BINARY_ENV)
    if configured:
        return configured
    if not os.path.isdir("/proc") and sys.platform != "darwin":
        return "muse"
    walked, dead = [], []
    for pid, argv0, is_daemon in walk_ancestors():
        walked.append(os.path.basename(argv0) or "?")
        if is_daemon:
            resolved = _resolve_binary(argv0, pid)
            if resolved:
                return resolved
            dead.append(argv0)
    if dead:
        print(
            f"daemon: no live executable behind the daemon ancestor {', '.join(dead)} "
            f"(parent chain: {', '.join(walked)}); falling back to muse; set {DAEMON_BINARY_ENV} to override",
            file=sys.stderr,
        )
    return "muse"


def lane_sessions(strict):
    """Exact tmux session name -> live (a pane that is not dead), from the
    lane runtime's `list` — the ONE tmux liveness listing `launch` and
    `lane_live` (`bind`, `lookup`) share. `strict=False` reads a tmux that
    cannot list as zero sessions (the picker lets tmux report a broken server
    as `launch_failed` on the row; `bind`'s re-attach sees no live lane);
    `strict=True` raises `tmux_unavailable`."""
    payload, code = run_lane_runtime("list")
    if code != 0 or payload.get("outcome") != "listed":
        if strict:
            raise lane_evidence_error(payload)
        return {}
    return {
        entry["name"]: bool(entry.get("live"))
        for entry in payload.get("tmux_sessions") or []
        if isinstance(entry, dict) and entry.get("name")
    }


def lane_live(row, names=None):
    """A row's liveness through its RECORDED backend (D5: recovery never
    reselects a lane's backend): True, False, or None when the evidence
    cannot be read. A tmux row is read from the lane runtime's `list` map —
    `names` when the caller already holds one listing, else a fresh strict
    one — and a Herdr row from its `status` (`herdr_unavailable` is None).
    The caller says what None means: `launch` fails closed, `lookup` reports
    null, `bind` re-attaches nothing."""
    ref = row_lane_ref(row)
    backend = row_backend(row)
    if not ref:
        # An ACTIVE Herdr row with no pane id: a launch in flight (create +
        # grace) or a runtime that died before its line. The pane may be
        # running under a ref nobody recorded, so nothing can be asked and
        # the answer is unknown; a human's `mark --state orphaned` (after
        # checking Herdr) is the judgment that turns it into "gone".
        return None if backend != "tmux" and row["state"] == "active" else False
    if backend == "tmux":
        if names is None:
            try:
                names = lane_sessions(strict=True)
            except EvidenceUnavailable:
                return None
        return bool(names.get(ref, False))
    verb = ["status", "--mode", backend, "--ref", ref]
    if row_backend_server(row):
        verb += ["--server", row_backend_server(row)]
    try:
        payload, code = run_lane_runtime(*verb)
    except EvidenceUnavailable:
        return None
    if code != 0 or payload.get("outcome") != "status":
        return None
    return bool(payload.get("live"))


def choose_backend(requested):
    """D5: the backend a NEW lane starts in, as `(backend, server)`. `auto`
    asks the lane runtime's `context`: a verified Herdr pane is Herdr; no hint
    (or a hint a tmux child merely inherited) is tmux; a hint the Herdr
    server cannot verify is `herdr_context_unverified` — exit 6 before any
    write, never a silent tmux launch after an uncertain Herdr answer. An
    explicit backend is the caller's judgment and skips the read."""
    if requested != "auto":
        return requested, (os.environ.get("HERDR_SOCKET_PATH") if requested == "herdr" else None)
    payload, code = run_lane_runtime("context")
    outcome = payload.get("outcome")
    if outcome == "herdr_context_unverified":
        raise EvidenceUnavailable("herdr_context_unverified", str(payload.get("message") or outcome))
    if code != 0 or outcome != "detected" or payload.get("launch_context") not in BACKENDS:
        raise lane_evidence_error(payload)
    backend = payload["launch_context"]
    herdr = payload.get("herdr") if isinstance(payload.get("herdr"), dict) else {}
    server = (herdr.get("socket") or os.environ.get("HERDR_SOCKET_PATH")) if backend == "herdr" else None
    return backend, server


def taken_session_names(conn, tmux_names, connector, conversation):
    """Names `launch` must not pick for this conversation: every session that
    exists on the tmux server (live pane or not — tmux refuses an existing
    name either way, so an exited lane under `remain-on-exit` still holds
    its name; `tmux_names` is the lane runtime's listing) and every name
    another row of this registry records (a dead lane's row keeps its name
    until it relaunches; handing that name to a third conversation would
    leave the row reading someone else's live lane as its own — two rows,
    one lane)."""
    taken = set(tmux_names)
    taken.update(
        row[0]
        for row in conn.execute(
            "SELECT tmux_session FROM conversation_owner WHERE tmux_session IS NOT NULL"
            " AND NOT (connector = ? AND conversation = ?)",
            (connector, conversation),
        )
    )
    return taken


def next_free_session_name(base, taken):
    """`base` is taken and no row of this conversation records it: another
    conversation's lane (aliases restart at c1 per connector state, and another
    registry may share the tmux server). Take the next free `-2`, `-3`, … name
    (#27864); the row records the chosen name and every later verb reads it
    there."""
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def launch_grace():
    try:
        value = float(os.environ.get("MUSE_DAEMON_LAUNCH_GRACE_S", "1.0"))
    except ValueError:
        return 1.0
    # non-finite -> default: the runtime rejects `--grace-s nan` (usage), and
    # the lock deadline would never fire (review of #33819).
    return max(value, 0.0) if math.isfinite(value) else 1.0


def shell_start_s():
    """The lane runtime's shell-start window (`MUSE_LANE_SHELL_START_S`,
    10 s), read HERE only and passed to the runtime as `--shell-start-s`
    beside `--grace-s`: a Herdr launch may hold the launch lock that long past
    the grace while a slow login shell reaches the launcher, so the lock's
    wait bound and the runtime's wait share one reading. Malformed or
    non-finite reads as 10 s, negative as 0."""
    try:
        value = float(os.environ.get("MUSE_LANE_SHELL_START_S", "10"))
    except ValueError:
        return 10.0
    return max(value, 0.0) if math.isfinite(value) else 10.0


def check_env_pairs(explicit):
    """`--env KEY=VALUE` syntax, checked before any write; the lane runtime
    applies the pairs (later wins) on top of its own passthrough."""
    for item in explicit or []:
        name, sep, _value = item.partition("=")
        if not sep or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise UsageError("usage", f"--env takes KEY=VALUE, got {item!r}")


def test_seams_enabled():
    """#28774: the helper's test seams are armed ONLY by this explicit flag; a
    seam variable leaked into — or set by the model in — a live session
    changes nothing unless the flag is set too, and the ignore is named."""
    return os.environ.get(TEST_SEAMS_ENV) == "1"


def peer_list_override(seam_armed):
    """The command the live session list is read with, when it is not the
    lane runtime's default. `MUSE_DAEMON_PEER_LIST_CMD` is a test seam (the
    suite's closed-gate and fake-list fixtures), honored only when the
    caller's seam is armed — a REQUIRED argument, as for the connector's
    `emit_format(seam_armed)` — so an override set in a live session is
    ignored and named unless the seam flag is set too (#28774:
    `echo '{"sessions": []}'` made the pass report live coordinators
    unbound; not arming the seam live is the skill's rule)."""
    if seam_armed and os.environ.get(PEER_LIST_ENV):
        return os.environ[PEER_LIST_ENV]
    return None


def ignored_env(seam_armed):
    """Seam-only variables present while the seam is NOT armed, named on
    stdout by the verb that would have read them: the ignore is visible, never
    silent."""
    if seam_armed:
        return []
    return [name for name in (PEER_LIST_ENV, LAUNCHER_ARGV_ENV) if os.environ.get(name)]


# adr:25011-daemon-session-coordination#D27 item 2: one JSON line per verb,
# self-describing — `outcome` names what happened and `next` is a short hint for
# the caller's one line (guidance in the tool result, never enforcement, D20).
# Audit #38191 D9 (adr:25011#D27 item 2: `next` is guidance, never a branch
# table): every error arm whose one line is "report this to your human" shares
# ONE sentence — `error` names the cause; only an arm with a different action
# keeps its own hint.
GENERIC_ERROR_NEXT = "report this one line to your human and open no lane; never retry blindly"
NEXT_FOR_ERROR = {
    "usage": "fix the flag the message names; nothing was written",
    "registry_newer_than_supported": "report this line to your human; never delete or recreate the registry",
    # #37687: what the orphaned row means for the conversation's next line —
    # this hint only when the runtime PROVED nothing is live (`created:
    # false`, or the launcher withdrawn); a kept lane reference gets
    # LAUNCH_FAILED_LANE_KEPT_NEXT below (review of PR #37700).
    "launch_failed": "report this one line to your human; nothing is live and the row is orphaned: the"
    " conversation's next inbound line reaches you as a fresh dispatch — do not relaunch now and do not hold it",
    # Audit #38191 D10: `delegate` has no `--backend`; the daemon-wide knob is
    # `start --lane-backend tmux` (spec 25011 FR-37181-2), a human's call.
    "herdr_context_unverified": "HERDR_ENV is set but the Herdr server could not verify this pane: report this one line"
    " to your human; if this daemon truly runs outside Herdr, their `start --lane-backend tmux` moves its lanes to tmux",
}


def error_next(error, code):
    """Total: a code without its own hint gets the usage or the generic one."""
    if error in NEXT_FOR_ERROR:
        return NEXT_FOR_ERROR[error]
    return NEXT_FOR_ERROR["usage"] if code == EXIT_USAGE else GENERIC_ERROR_NEXT


def emit(payload, code=EXIT_OK):
    if isinstance(payload, dict) and payload.get("error"):
        # A non-zero line keeps the vocabulary the connector already forwards
        # (review of #29764): `conflict` on exit 3, `failed` on every other
        # non-zero exit; `error` names the cause, `next` the caller's one line.
        payload.setdefault("outcome", "conflict" if code == EXIT_CONFLICT else "failed")
        payload.setdefault("next", error_next(payload["error"], code))
    sys.stdout.write(json.dumps(payload, sort_keys=False) + "\n")
    return code


def fetch_row(conn, connector, conversation):
    if not has_table(conn, "conversation_owner"):
        return None
    return conn.execute(
        "SELECT * FROM conversation_owner WHERE connector = ? AND conversation = ?",
        (connector, conversation),
    ).fetchone()


class LaunchLock:
    """Advisory lock around a launch — the registry open, the row judgment
    and the tmux check-and-create — so two launches for one registry never
    both observe "no session" and both create one, and a launch racing
    another launch waits here, on one bound, never on the SQLite busy
    timeout (#34042)."""

    def __init__(self, registry):
        self.path = registry + ".launch.lock"
        self.handle = None

    def __enter__(self):
        try:
            # The lock file lives beside the registry, and a first launch
            # takes the lock before the registry exists (#34042).
            ensure_private_dir(os.path.dirname(self.path) or ".")
            self.handle = open(self.path, "a+")  # noqa: SIM115 - held for the block
            os.chmod(self.path, 0o600)
        except OSError as error:
            raise RegistryUnavailable(f"launch lock {self.path} unusable: {error}") from error
        # Bounded like the SQLite busy timeout, plus the launch grace, plus
        # the lane runtime's shell-start window: a healthy launch holds this
        # lock from the registry open through the lane runtime's `launch`
        # (the lane start and the grace wait; a Herdr launch may wait the
        # whole shell window for a slow login shell and then the grace AGAIN
        # from the launcher's own start, so twice the grace), so a
        # same-trigger launch arriving meanwhile must outwait it and answer
        # `reused`, not exit 7; a holder that never returns (a wedged launch)
        # still cannot stall every later launch forever (#27865; review of
        # #33819).
        timeout = db_timeout() + 2 * launch_grace() + shell_start_s()
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    self.handle.close()
                    self.handle = None
                    raise RegistryUnavailable(
                        f"launch lock {self.path} held past {timeout:g}s by another launch"
                    ) from None
                time.sleep(0.05)
            except OSError as error:
                self.handle.close()
                self.handle = None
                raise RegistryUnavailable(f"launch lock {self.path} unusable: {error}") from error

    def __exit__(self, *_exc):
        if self.handle is not None:
            try:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            finally:
                self.handle.close()
        return False


# ------------------------------------------------------------------ verbs ---


def read_snapshot(path):
    if path is None:
        return []
    try:
        if path == "-":
            text = sys.stdin.read()
        else:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
    except (OSError, UnicodeDecodeError) as error:
        raise UsageError("snapshot_unreadable", f"snapshot file {path} unreadable: {error}") from error
    # The connector hands the conversation over as JSON LINES — one event per
    # line, in order, both directions, each outbound one marked `sent`
    # (`adr:25011-daemon-session-coordination#D12`), so the coordinator can see
    # what was already said and never repeat it. A human handing a lane over by
    # hand passes plain text lines instead. The two are told apart by whether
    # EVERY line starts with `{`; such a line that does not decode as a JSON
    # object is a usage error (exit 2), and a mixed input is plain text, so a
    # conversation that merely mentions JSON is still plain text and nothing
    # is dropped.
    lines = [line for line in text.splitlines() if line.strip()]
    if lines and all(line.lstrip().startswith("{") for line in lines):
        events = []
        for line in lines:
            try:
                event = json.loads(line)
            except ValueError as error:
                raise UsageError(
                    "snapshot_unreadable",
                    f"snapshot line in {path} starts with '{{' but is not a JSON object: {error}",
                ) from error
            events.append(event)
        return events
    return lines


def parse_conversation_ref(raw):
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except ValueError as error:
        raise UsageError("usage", f"--conversation-ref must be a JSON object: {error}") from error
    if not isinstance(value, dict):
        raise UsageError("usage", "--conversation-ref must be a JSON object")
    return value


POSTURE_FLAG = "--yolo"


def handoff_posture(path):
    """The posture recorded in an existing handoff, or None when the file has
    none (written before the field existed) or cannot be read: `reused` starts
    nothing, so it reports the LIVE lane's posture, never this call's."""
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle).get("posture")
    except (OSError, ValueError, AttributeError):
        return None
    return value if isinstance(value, list) else None


def handoff_project(path):
    """Whether an existing handoff opened a project: `reused` starts nothing,
    so its receipt's tier is the LIVE lane's, never this call's (review of PR
    #39364). False when the file has no `project` or cannot be read."""
    try:
        with open(path, encoding="utf-8") as handle:
            return isinstance(json.load(handle).get("project"), dict)
    except (OSError, ValueError, AttributeError):
        return False


LISTEN_DESCRIPTIONS = {"mailbox": "peer inbox", "slack": "slack thread"}
QUOTE_LIMITS = (400, 200, 100, 40, 0)
# #31044: the per-step tick rule, one copy for the starter and the handoff's
# `reply_shapes.tick` (review round 4 of #31059: two hand copies had drifted).
TICK_RULE = (
    "Right after a step finishes, the call after it re-sends the whole plan with that step's ☐ turned ✅"
    " - after step 1 edit it, after step 2 edit it again, never batched at the end"
)


def listen_description(connector):
    """The Monitor label the coordinator's own listener carries: the FIXED
    per-transport label spec 4114 INV-17544-6 requires (a safe public string a
    human may screen-share), never an id and never an override. The legacy
    Slack labels stay as they are; any other connector's label is its skill
    id (ADR 37480 D2: connector-attributable, nothing connector-private)."""
    if connector_skill(connector) == LEGACY_CONNECTOR:
        return LISTEN_DESCRIPTIONS.get(connector_transport(connector), "peer inbox")
    return f"{connector_skill(connector)} inbox"


def split_attachment_lines(text):
    """The connector ends an inbound snapshot text with one `[attachment: …]`
    line per file (spec 23499 FR-28777-2) and then the room the relay's block
    carried: one combined `context: …` row plus one `[context] <who>: <text>`
    line per untagged post (spec 23499 FR-33022-1). All stay off the bounded
    quote: a long ask would cut the path first (review of #30651), and the
    conversation around the ask is context, never part of what was asked. Only
    the first exact `context: ` row splits out — a second one is body text
    (the connector mints at most one), as is the defused `(context): ` form."""
    body, files, context = [], [], []
    row = ""
    for line in str(text or "").splitlines():
        if line.startswith("[attachment: "):
            files.append(line)
        elif line.startswith("[context] "):
            context.append(line)
        elif line.startswith("context: ") and not row:
            row = line
        else:
            body.append(line)
    return "\n".join(body), files, row, context


def one_line(text, limit):
    """One quoted line, bounded: the prompt rides tmux's capped command line,
    and a 4000-character message must not push the coordinator's first command
    off the end."""
    collapsed = " ".join(str(text).split())
    if limit <= 0:
        return "…"
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


NATIVE_DELIVERY_ENV = "MUSE_EXPERIMENTAL_NATIVE_CONNECTOR_DELIVERY"


def native_delivery_enabled():
    """ADR 25011 D22: the gate that moves connector messages onto the runtime's
    session-message inbox. Read by the connector and this starter alike."""
    return (os.environ.get(NATIVE_DELIVERY_ENV) or "").strip().lower() in ("1", "on", "true", "yes")


COORDINATOR_SKILL = "/daemon-coordinator"


def build_prompt(handoff, handoff_path, connector_script, description, relaunched=False, declaration=None, backend=None):
    """The STARTER (`adr:25011-daemon-session-coordination#D13` as amended for
    #41245): the dynamic facts only. Line 1 invokes the `daemon-coordinator`
    skill - the runtime expands a leading `/<skill>` line into the first
    model message (proved live on the devserver, #41245: `Loaded skill`, no
    tool call), so the coordinator's rulebook is in its first turn at no
    extra step - and the lines after it are what only this lane knows: the
    identity and the mailbox they write to, a standing role or project, every
    message still unanswered (a D15 relaunch inherits several, #28200;
    `answered` is "a plain reply followed it", by time - `#D20` keeps no
    ledger), what the daemon ALREADY sent (so the acknowledgement is never
    doubled, `#D12`), the reply capabilities the connector declares (ADR
    37480 D1: `cards`, `attach`, `edit`, read off its declaration; the skill
    keys its form rules on these words), the two exact commands and the
    handoff path. Every rule the twenty QA rounds pinned on the old starter
    (#28427 … #39465) lives in that skill with its pin
    (core-skill-tests/daemon/test_coordinator_skill.py); the quote ladder and
    PROMPT_MAX stay because the prompt rides tmux's capped command line and a
    long ask shrinks before the commands do. The handoff file stays on disk
    for the earlier messages, recovery, and audit."""
    lane, conversation = handoff["lane"], handoff["conversation"]
    connector_id = handoff.get("connector") or "slack-connector:mailbox"
    declaration = declaration or connector_declaration(connector_id, connector_script)
    legacy, attach, edit, reference, cards = (declaration[key] for key in ("legacy", "attach", "edit", "reference", "cards"))
    address = handoff.get("address")  # #29738: the mailbox they write to (mailbox lanes only)
    # #30542: the connector's `--conversation-ref` carries the relay's
    # `requester` and `thread` facts when it has them (spec 23499 FR-30542-1).
    ref = handoff.get("conversation_ref") if isinstance(handoff.get("conversation_ref"), dict) else {}
    requester = ref.get("requester") if isinstance(ref.get("requester"), dict) else {}
    thread = ref.get("thread") if isinstance(ref.get("thread"), dict) else {}
    requester_name = one_line(requester.get("display_name") or "", 24) or None
    thread_ref = one_line(thread.get("ref") or "", 40) or None
    events = [event for event in handoff["snapshot"] if isinstance(event, dict)]
    inbound = [event for event in events if event.get("direction") != "outbound"]
    sent = [event for event in events if event.get("direction") == "outbound"]
    if inbound:
        # The connector marks each inbound `answered` (spec 23499
        # FR-27816-1(d)); a snapshot without the marks reads as before: the
        # newest inbound is the request; a marked snapshot whose every inbound
        # is answered asks nothing.
        marked = [event for event in inbound if "answered" in event]
        unanswered = [event for event in marked if event.get("answered") is False] if marked else inbound[-1:]
        asks = [(event.get("from") or "they", *split_attachment_lines(event.get("text", ""))) for event in unanswered]
    else:
        lines = [line for line in handoff["snapshot"] if isinstance(line, str) and line.strip()]
        asks = [("they", lines[-1], [], "", [])] if lines else []
    # The inner command is built for a shell (each argument quoted), then
    # embedded as a JSON string: a mailbox cursor carries `"` bytes, and the
    # reader is a model pasting this into a tool call. No `--status-markers`
    # (#28182); no `--say` placeholder (#29148: a literal token in a command
    # the model is told to copy was pasted verbatim ~1 boot in 8).
    inner = (
        f"python3 {connector_script} listen"
        f" --conversation {shlex.quote(conversation)} --cursor {shlex.quote(handoff['watermark'])}"
    )
    listen = (
        f"monitor(command={json.dumps(inner)},"
        f' description="{description}", persistent=true, wake_delay_ms=0, show_lines=true)'
    )
    # R21-DC-VERIFY D2 (#41245, v4): the plan-first rate fell when the --say
    # form left the starter (prose alone: 4 of 6 clean runs; the old starter,
    # which showed the form beside the arm, 3 of 3). The second exact line is
    # the same arm with --say "<plan>" inside the command and its one trigger;
    # the first arm stays bare (#29148: a literal placeholder in the ONE
    # copy-ready command was pasted verbatim; the connector still refuses a
    # literal <plan>, and the skill's § Arm says so).
    say_arm = inner + ' --say "<plan>"'   # outside the f-string: a backslash inside {…} needs Python 3.12 (review of #41359)
    listen_with_plan = (
        f"monitor(command={json.dumps(say_arm)},"
        f' description="{description}", persistent=true, wake_delay_ms=0, show_lines=true)'
    )
    # ADR 25011 D22 (native delivery, gated): the daemon's unscoped listener is
    # the one forwarder, so the coordinator arms nothing and binds once.
    native = native_delivery_enabled()
    reply_command = f"python3 {connector_script} reply --to {lane} <<'MSG'\n<text>\nMSG"

    def render(limit, kept):
        dropped = max(len(asks) - kept, 0)  # no ask at all is nothing dropped
        parts = [
            COORDINATOR_SKILL,
            f"You are the conversation coordinator for {handoff['connector']} lane {lane}"
            f" (conversation {conversation}"
            + (f"; they write to mailbox {address}" if address else "")
            + (f"; thread {thread_ref}" if thread_ref else "")
            + ").",
        ]
        if backend == "herdr":
            # #38187 (ADR 25011 D7 Amendment 1, guard 4 rev 1): the skill's
            # lifecycle rule keys on this fact (a tmux lane cannot reach a pane).
            parts.append("Lane backend: herdr.")
        if handoff.get("role") == "fleet-steward":
            # #31985 (ADR 31985 D1): the standing role rides one line; the
            # loop, the watcher and the evidence rules stay in the project
            # skill, which the coordinator reads from its own workspace.
            skill_path = os.path.join(handoff.get("workspace") or ".", ".agents/skills/fleet-steward/SKILL.md")
            parts.append(
                f"Standing role, asked for by {requester_name or 'the requester'} here: you are their fleet"
                f" steward. Before any plan, read {skill_path} and run its loop from this conversation -"
                " one watcher, every report a reply here, no other lane steered. \"Stop the fleet steward\""
                f" ends the role, not this conversation: python3 {connector_script} steward disarm, then"
                " carry on as an ordinary coordinator. On every wake after a resume or restart, re-read"
                f" {skill_path} first (its current text) and arm your scan ticker as it says."
                # #38187 round-6b QA lane F2 D5 (ADR 25011 D7 Amendment 1
                # revision 2): the hand-back rides the starter, the lever the
                # steward acted on.
                f" \"Restart the fleet steward\", or a stop/close of this lane's own pane or session, is the"
                " daemon's, not yours: work_stop your listener and your ticker, reply nothing and stand by -"
                " the connector hands the unanswered line back to the daemon, which ends this session from"
                " outside and relaunches."
            )
        project = handoff.get("project") if isinstance(handoff.get("project"), dict) else None
        if project:
            # #38715 PR 6 (FR-38715-61; ADR 38715 Amendment 1 D12/D15): the
            # conversation coordinator IS the project's coordinator. The facts
            # here are the slug, the folder, the helper and its three exact
            # calls; the rules are the skill's § Project lanes (#41245). Only
            # a handoff that names a project renders this: the thread path is
            # byte-identical.
            agents = project.get("agents_script") or "agents.py"
            slug = project["slug"]
            parts.append(
                f"Project {slug} ({project['path']}): you are its coordinator and this conversation is its channel."
                f" {'Listener first, then ' if not native else ''}python3 {agents} resume {slug}; context {slug} each round, once;"
                f" go: tick {slug} --arm monitor|scheduler --command \"<line>\"; a `PR:` report: follow {slug} --pr <url>."
            )

        def attachment_parts(files, indent=""):
            """Whole at the top tier - the path is the point - but the lines
            ride the ladder (review of #30651); below the top tier they
            collapse to one pointer at the handoff, which holds them all."""
            if not files:
                return []
            if limit >= QUOTE_LIMITS[0]:
                return [indent + one_line(line, 400) for line in files]
            rest = len(files) - 1
            kept = [indent + one_line(files[0], 400)]
            return kept + ([f"{indent}[+{rest} more attachment{'s' if rest != 1 else ''} in the handoff file]"] if rest else [])

        def context_parts(context, indent=""):
            """The untagged posts around the ask, oldest first (FR-33022-1):
            whole at the top tier, below it the newest one plus a count; the
            lead line says what they are, so a quoted post is never read as
            an ask (review of #33053)."""
            if not context:
                return []
            lead = indent + "The channel around it (background, never an ask):"
            if limit >= QUOTE_LIMITS[0]:
                return [lead] + [indent + one_line(line, 400) for line in context]
            rest = len(context) - 1
            earlier = ([f"{indent}[+{rest} earlier context line{'s' if rest != 1 else ''} in the handoff file]"]
                       if rest else [])
            return [lead] + earlier + [indent + one_line(context[-1], 400)]

        if len(asks) == 1:
            who, text, files, context_row, context = asks[0]
            if text or files or context_row or context:
                parts.append(f"{who} asked: {one_line(text, limit)}")
                parts.extend(attachment_parts(files))
                if context_row:
                    parts.append(one_line(context_row, 200))
                parts.extend(context_parts(context))
        elif asks:
            head = f"{len(asks)} unanswered messages — answer all of them in your first plain reply."
            if dropped:
                head += (
                    f" The {dropped} oldest are only in the handoff named below: read it before you reply."
                    f" The newest {kept}, oldest first:"
                )
            else:
                head += " Oldest first:"
            parts.append(head)
            for who, text, files, context_row, context in asks[dropped:]:
                parts.append(f"- {who} asked: {one_line(text, limit)}")
                parts.extend(attachment_parts(files, "  "))
                if context_row:
                    parts.append("  " + one_line(context_row, 200))
                parts.extend(context_parts(context, "  "))
        for event in sent[-2:]:
            parts.append(f"Already sent to them, do not repeat: {one_line(event.get('text', ''), limit)}")
        if relaunched:
            # #29971 (QA round 9): the lines above may be the dead lane's own
            # promise; the registry alone knows this launch replaced an
            # `orphaned`/`retired` row, so the fact rides here and the skill
            # says what it means.
            parts.append(
                "Your predecessor is gone: never wait on or promise a report on its steps"
                " - re-run or verify them."
            )
        # ADR 37480 D1: the three capabilities are the connector's declaration;
        # the skill's form rules (cards, attach, edit) key on these words.
        parts.append(
            f"Your replies go to {requester_name or 'the requester'}"
            + (" (greet them by name)" if requester_name else "")  # #30542
            + f"; cards {'yes' if cards else 'no'}; attach {'yes' if attach else 'no'}; edit {'yes' if edit else 'no'}."
        )
        if native:
            registry_script = os.path.abspath(__file__)
            parts += [
                "Arm nothing.",
                f"Your first call, once: python3 {registry_script} bind --connector {connector_id}"
                f" --conversation {conversation} --muse-session-id <Current session id: from the"
                " session_identity reminder>",
                f"Reply: {reply_command}",
            ]
        else:
            parts += [
                f"1. {listen}",
                f"   more than one step, or over about a minute: {listen_with_plan}  # the *Plan* checklist replaces <plan>",
                f"2. {reply_command}",
            ]
        parts.append(
            f"Earlier messages/ids, a worked plan (reply_shapes): {handoff_path}"
            + (" - read it before your first reply" if dropped else " - read first")
            # ADR 37480 D1: how replies render is the connector's own document;
            # the legacy Slack handoff already names it in `card`.
            + (f"; how this connector renders a reply and its richer shapes: {reference} - read once, before"
               " your first reply" if reference and not legacy else "")
            + "."
        )
        return "\n".join(parts) + "\n"

    # Shrink the quotes first (400 → 200 → 100 characters, every unanswered
    # message kept), then drop the oldest one at a time at 100 and say how
    # many went; the two shortest limits are the one-message last resort.
    count = max(len(asks), 1)
    plans = [(limit, count) for limit in QUOTE_LIMITS[:3]]
    plans += [(QUOTE_LIMITS[2], kept) for kept in range(count - 1, 0, -1)]
    plans += [(limit, 1) for limit in QUOTE_LIMITS[3:]]
    for limit, kept in plans:
        prompt = render(limit, kept)
        if len(prompt) <= PROMPT_MAX:
            return prompt
    return prompt[: PROMPT_MAX - 1] + "\n"


# #37687 (review of PR #37700): a failed launch that keeps a lane reference
# (`created: true`, or no runtime line at all — the tmux kill-after-create arm
# of #29552) may leave a live orphan; `launch` over the row answers `conflict`
# while it lives, so the daemon never relaunches and never holds the line.
LAUNCH_FAILED_LANE_KEPT_NEXT = (
    "report this one line to your human; {lane} may still be live (the orphaned row keeps it): never relaunch"
    " over it; the next inbound line re-dispatches by itself — do not hold it"
)
# The hint stays at or under 200 characters for any lane name (a `--lane`-less
# launch derives a 46-character tmux name from a Slack thread key): the token is
# clipped here; the receipt's `lane_ref` / `tmux_session` carry it whole.
HINT_TOKEN_MAX = 200 - len(LAUNCH_FAILED_LANE_KEPT_NEXT.format(lane=""))


def project_request(handoff):
    """The task an `agents init` is given (FR-38715-61): the newest unanswered
    inbound line's body (attachment and context lines off, as the starter
    quotes it), and who wrote it — the connector's display name when the
    ref names one, else the line's sender."""
    events = [event for event in handoff["snapshot"] if isinstance(event, dict)]
    inbound = [event for event in events if event.get("direction") != "outbound"]
    text, sender = "", None
    if inbound:
        marked = [event for event in inbound if "answered" in event]
        unanswered = [event for event in marked if event.get("answered") is False] if marked else inbound[-1:]
        newest = (unanswered or inbound)[-1]
        text, sender = split_attachment_lines(newest.get("text", ""))[0], newest.get("from")
    else:
        lines = [line for line in handoff["snapshot"] if isinstance(line, str) and line.strip()]
        if lines:
            text = re.sub(r"^\S+ [^:]+: ", "", lines[-1], count=1)
    ref = handoff.get("conversation_ref") if isinstance(handoff.get("conversation_ref"), dict) else {}
    requester = ref.get("requester") if isinstance(ref.get("requester"), dict) else {}
    named = one_line(requester.get("display_name") or "", 24) or None
    return " ".join(text.split()), named or (one_line(sender, 24) if sender else None)


def hint_token(text):
    text = str(text)
    return text if len(text) <= HINT_TOKEN_MAX else text[: HINT_TOKEN_MAX - 1] + "…"


UNKNOWN_PANE_NEXT = (
    "check Herdr for a pane serving this conversation; if none, `mark --connector {connector}"
    " --conversation {conversation} --state orphaned`, then launch again; never relaunch over an unknown lane"
)


def cmd_launch(args):
    check_note(args.note)
    conversation_ref = parse_conversation_ref(args.conversation_ref)
    # `--event-id` / `--watermark` are the connector's bytes, stored and
    # compared by equality only (adr:37480#D1 rule 1): the connector emits
    # one rendering and canonicalises nothing here.
    check_env_pairs(args.env)
    snapshot = read_snapshot(args.snapshot_file)
    require_lane_runtime()
    # D5: the backend is decided before the transaction, from the launching
    # context; an unverifiable Herdr context is exit 6 with nothing written.
    # #37181: an explicit `--backend` wins; else the daemon-wide record
    # `start --lane-backend` left; else `auto`.
    backend, backend_server = choose_backend(args.backend or read_lane_backend(args.registry) or "auto")
    muse_bin = args.muse_bin or daemon_binary_path()
    connector, conversation = args.connector, args.conversation
    lane = args.lane or default_lane(conversation)
    handoff_id = handoff_id_for(connector, conversation, args.event_id)
    # The lane's logical name for both backends: the tmux session name; the
    # Herdr tab label is this plus `@<daemon namespace>` (#35048). Only a tmux
    # lane records it as `tmux_session`.
    lane_name = args.tmux_session or default_tmux_session(connector, lane)

    def tmux_name():
        return lane_name if backend == "tmux" else None
    handoff_path = os.path.join(handoff_dir(args.registry), f"{handoff_id}.json")
    posture = [POSTURE_FLAG]
    # ADR 37480 D1: what the starter and the handoff may say about this
    # connector (legacy Slack: the static table; any other: its `status --json`).
    declaration = connector_declaration(connector, args.connector_script)
    handoff = {
        "schema_version": 1,
        "handoff_id": handoff_id,
        "connector": connector,
        "conversation": conversation,
        "conversation_ref": conversation_ref,
        "address": handoff_address(connector, snapshot),
        "lane": lane,
        "event_id": args.event_id,
        "watermark": args.watermark or args.event_id,
        "acknowledgement": {
            "posted": args.ack_posted == "yes",
            "progress_reply_id": args.progress_reply_id or None,
        },
        "daemon": {"session_id": args.daemon_session_id, "session_name": args.daemon_session_name},
        "posture": posture,
        "workspace": args.workspace,
        "connector_script": args.connector_script,
        "snapshot": snapshot,
        "created_at": utc_now(),
        # #31044: the worked plan and the reply rules, read before a plan
        # (`reply_shapes` in the starter's last line); prose only, so no
        # schema bump - an older reader ignores the key.
        "reply_shapes": reply_shapes(connector, lane, args.connector_script, declaration),
    }
    if args.steward:
        # #31985 (ADR 31985 D1): the standing role, only when asked for; an
        # older reader ignores the key, an ordinary launch never writes it.
        handoff["role"] = "fleet-steward"
    # #38715 PR 6 (FR-38715-61): does this hand-off open a project? Decided
    # before the lock from the gate and the `set delegation` record; the
    # `init` itself runs after the row guards, so a `reused`/`conflict`
    # launch never creates a folder. `project_report` is the receipt's
    # `project` (None when nothing was asked: the thread path, byte-identical).
    project_wanted, project_report = resolve_project(args.project, args.registry)
    # #38715 (audit daemon PR-B): the sizing decision, echoed on the receipt
    # whenever the tier was a choice — the `agents` gate open, or a recorded
    # `set delegation` — so the operator sees which tier this hand-off took
    # and why. Under a closed gate with `auto` the receipt stays byte-identical.
    delegation_mode = read_delegation(args.registry)["mode"]
    sizing = None
    if agents_gate_open() or delegation_mode != "auto":
        sizing = {
            "agents_gate": "open" if agents_gate_open() else "closed",
            "delegation": delegation_mode,
            "asked": bool(args.project),
        }
    # What the lane inherits from this daemon (owner ruling 2026-09-20): read
    # once, reported on the receipt as facts - the gates as the daemon
    # resolves them, the engine args its own argv carried, and the reason
    # when that argv could not be read.
    daemon_argv, argv_source = launcher_argv()
    lane_settings = {
        "gates": launcher_gates(),
        "engine_args": inherited_engine_args(daemon_argv, args.muse_arg),
        "engine_args_source": argv_source,
    }

    def starter():
        """Built when the runtime needs it, after the row is judged: a launch
        over an `orphaned`/`retired` row is a relaunch, and only that starter
        carries the dead lane's step rule (#29971)."""
        return build_prompt(
            handoff, handoff_path, args.connector_script, listen_description(connector), relaunched=relaunched,
            declaration=declaration, backend=backend,
        )

    def runtime_launch(dry_run):
        """The lane runtime's `launch` (adr:25011 D24): the muse argv, the
        posture, the environment passthrough, the tmux start and the launch
        grace are its. The starter rides its stdin and lands once, on the
        lane's tmux command line; `--dry-run` builds and starts nothing."""
        verb = [
            "open", "--mode", backend, "--name", lane_name, "--exact-name",
            # The Herdr tab label is namespaced per daemon (#35048); the logical
            # lane name (and the tmux session name) stays `lane_name`.
            "--label", lane_name if backend == "tmux" else f"{lane_name}@{daemon_namespace(args.registry)}",
            "--cwd", args.workspace, "--prompt-file", "-", "--engine", muse_bin,
            # A daemon lane is unattended by definition: it must never sit on a
            # trust or approval prompt (ADR 38715 D8 keeps this behaviour; the
            # runtime's default became the engine's own prompts on 2026-09-19).
            "--unattended",
            "--grace-s", f"{launch_grace():g}", "--shell-start-s", f"{shell_start_s():g}",
        ]
        # The daemon session's own engine args first, then the caller's: one
        # token per arg (a value that starts with `--` would otherwise read as
        # an option to the runtime's argparse); a flag the caller names is not
        # inherited, so the caller's value is the only one the engine sees.
        if handoff.get("project") and backend == "herdr":
            # ADR 38715 Amendment 7 (FR-38715-61): a project's coordinator is
            # the first tab of a Herdr workspace named by the project, the one
            # its threads join; a thread launch passes nothing (the runtime's
            # default is a workspace of its own) and tmux has no workspace.
            verb += ["--workspace", handoff["project"]["slug"]]
        verb += [f"--engine-arg={extra}" for extra in lane_settings["engine_args"] + list(args.muse_arg or [])]
        for name in pass_names():
            verb += ["--pass", name]
        # The launcher's admission gates, before the caller's `--env` pairs:
        # the runtime keeps the last value for a name, so an explicit `--env`
        # for a gate still wins (owner ruling 2026-09-20 (b)).
        for pair in launcher_gate_pairs():
            verb += ["--env", pair]
        # A project's threads live where its coordinator lane lives (QA round 8
        # lane DM, D4): the agents helper reads its own `MUSE_AGENTS_TMUX` and
        # rides it as host-manager's `--tmux`, so the lane server's teardown
        # covers them. Only a project launch hands it over (INV-38715-60), and
        # before the caller's pairs, so an explicit `--env` still wins.
        if handoff.get("project") and os.environ.get("MUSE_DAEMON_TMUX"):
            verb += ["--env", f"MUSE_AGENTS_TMUX={os.environ['MUSE_DAEMON_TMUX']}"]
        for item in args.env or []:
            verb += ["--env", item]
        # Keep native connector delivery and any coordinator child launches on
        # the same binary as the lane itself.
        verb += ["--env", f"{DAEMON_BINARY_ENV}={muse_bin}"]
        if dry_run:
            verb.append("--dry-run")
        return run_lane_runtime(*verb, stdin=starter())

    built = None
    declared_pass = []

    def pass_names():
        """The connector's `env_pass` (adr:37480#D1), read once per launch
        through its own `status --json`; the Slack tuple when it declares
        none."""
        if not declared_pass:
            declared_pass.append(lane_env_pass(args.connector_script))
        return declared_pass[0]

    def result(outcome, row, path):
        # Ids, names and paths only: the handoff body (snapshot included) and
        # the tmux command (env VALUES) never reach stdout, which the daemon's
        # context and session log record. `command` is the muse argv the lane
        # runtime built (the short prompt names the handoff path; it carries
        # no env value). `posture` is the LIVE lane's: this call's for a
        # launch, the existing handoff's for `reused` (omitted when that
        # handoff predates the field).
        nonlocal built
        if built is None:
            built, _code = runtime_launch(dry_run=True)
        # The lane's location is the ROW's (a `reused` lane keeps the backend
        # it was started in, whatever this launch would have chosen).
        lane_ref = row_lane_ref(row)
        out = {
            "outcome": outcome,
            "handoff_id": handoff_id,
            "handoff_path": path,
            "tmux_session": row["tmux_session"],
            "backend": row_backend(row),
            "lane_ref": lane_ref,
            "backend_server": row_backend_server(row),
            "lane_name": row["tmux_session"] or lane_name,
            "row": row_dict(row),
            "command": built.get("command"),
            "env_passthrough": built.get("env_passthrough"),
        }
        reported = posture if outcome == "launched" else handoff_posture(path)
        if reported is not None:
            out["posture"] = reported
        # Owner ruling 28 (#38715, 2026-09-22): how a person sits in front of
        # the lane — the runtime's `attach` for the session this row names (a
        # `reused` lane's dry run knows the name only when it is the row's own).
        # A runtime that names none leaves the key out and the line as before.
        attach = built.get("attach")
        if isinstance(attach, str) and attach.strip() and built.get("ref") == lane_ref:
            out["attach"] = attach.strip()
        out["lane_settings"] = lane_settings
        if project_report is not None:
            out["project"] = project_report
        if sizing is not None:
            # The tier the lane HAS, not the one asked for: a launch says what
            # it took (a project that fell back to a thread says `thread`); a
            # `reused` lane says what its handoff opened (review of PR #39364).
            if outcome == "launched":
                took_project = project_report is not None and project_report.get("outcome") == "created"
            else:
                took_project = handoff_project(path)
            out["sizing"] = {"tier": "project" if took_project else "thread", **sizing}
        if project_report is not None and project_report.get("outcome") == "created":
            # Ruling 2026-09-20 (c): a project coordinator must come up as the
            # agents coordinator; from the launch facts alone, does this
            # lane's catalog admit the agents skill?
            out["agents_gate"] = "in lane" if lane_sees_agents_skill(launcher_gate_pairs() + list(args.env or [])) else "absent in lane"
        # A relaunch over an orphaned/retired row is the `launched` whose one
        # line ends `, relaunched` (SKILL.md § Delegating); the hint says so.
        suffix = ", relaunched" if relaunched else ""
        if project_report is not None and project_report.get("outcome") == "created":
            suffix += f" · project {project_report['slug']}"
        if out.get("attach"):
            suffix += f" · attach: {out['attach']}"  # ruling 28: the line tells them how to sit in front of it
        out["next"] = (
            # #29739 (QA round 8): the lines drained right after this result
            # were already in the snapshot; the hint says so where the daemon
            # decides.
            f"say `{args.lane} → {lane_ref}{suffix}` and end the turn; never poll or drive the lane;"
            " a line from this lane that lands after this result is already the coordinator's - no second delegate"
            if outcome == "launched"
            else "the lane is live and already holds this trigger; say one line and end the turn"
        )
        if project_report is not None and project_report.get("outcome") != "created":
            # FM-38715-60: only the project was refused; the lane is an
            # ordinary conversation coordinator and the daemon says so.
            why = project_report.get("reason") or project_report.get("error")
            out["next"] += f"; no project: the lane is an ordinary conversation coordinator ({why}) - say so in that line"
        if out.get("agents_gate") == "absent in lane":
            out["next"] += ("; launch defect: the coordinator cannot see the agents skill (agents_gate absent in lane) -"
                            " say so in that line; it is not acting as the agents coordinator")
        return emit(out)

    def unknown_conflict(row):
        # D5: lost evidence is never a duplicate launch. A lane whose server
        # did not answer, or whose pane id was never recorded, may still be
        # live, so the row is left alone.
        if row_lane_ref(row):
            reason = (
                f"liveness of {lane_words(row)} is unknown (its server did not answer);"
                " a lane that may still be live is never relaunched over"
            )
            next_hint = "report this one line to your human: the lane's server must answer before this conversation moves; never relaunch over an unknown lane"
        else:
            reason = (
                f"liveness of the {row_backend(row)} lane is unknown (no pane id was recorded: its launch never"
                " reported one); a lane that may still be live is never relaunched over"
            )
            next_hint = UNKNOWN_PANE_NEXT.format(connector=connector, conversation=conversation)
        return {
            "outcome": "conflict",
            "handoff_id": handoff_id,
            "tmux_session": row["tmux_session"],
            "backend": row_backend(row),
            "lane_ref": row_lane_ref(row),
            "row": row_dict(row),
            "reason": reason,
            "next": next_hint,
        }

    relaunched = False
    # #34042: the lock comes first. Every registry write a launch performs,
    # the migration transaction of `open_registry` included, sits under the
    # lock the loser waits on, so a launch racing another launch has ONE
    # bound (busy timeout + twice the launch grace + the shell-start window)
    # and never spends its SQLite busy timeout on the other launch's
    # transaction (`database is locked`, exit 7).
    with LaunchLock(args.registry):
        conn = open_registry(args.registry)
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                existing = fetch_row(conn, connector, conversation)
                now = utc_now()
                same_trigger = (
                    existing is not None
                    and existing["state"] == "active"
                    and existing["handoff_id"] == handoff_id
                )
                # ONE listing from the lane runtime feeds the trigger, the
                # recorded-lane guard and the tmux name picker — read only
                # when something here is a tmux lane.
                tmux_involved = backend == "tmux" or (existing is not None and row_backend(existing) == "tmux")
                names = lane_sessions(strict=False) if tmux_involved and not args.dry_run else {}
                if same_trigger:
                    live = True if args.dry_run else lane_live(existing, names=names)
                    if live:
                        conn.execute("COMMIT")
                        return result("reused", existing, existing["handoff_path"] or handoff_path)
                    conn.execute("ROLLBACK")
                    if live is None:
                        return emit(unknown_conflict(existing), EXIT_CONFLICT)
                    # FM-2 / FM-5: a dead lane is never silently relaunched over
                    # its active row; `recover` orphans it and the next dispatch
                    # re-derives the handoff for the still-pending trigger
                    # (the previous document is archived beside it).
                    return emit(
                        {
                            "outcome": "conflict",
                            "handoff_id": handoff_id,
                            "tmux_session": existing["tmux_session"],
                            "backend": row_backend(existing),
                            "lane_ref": row_lane_ref(existing),
                            "row": row_dict(existing),
                            "reason": (
                                f"lane absent; run recover --connector {connector}"
                                f" --conversation {conversation} ({lane_words(existing)} is gone)"
                            ),
                            "next": "`delegate` runs that per-conversation recover and the relaunch itself; from a hand-run `launch` run nothing else",
                        },
                        EXIT_CONFLICT,
                    )
                else:
                    if existing is not None and existing["state"] == "active":
                        conn.execute("ROLLBACK")
                        return emit(
                            {
                                "outcome": "conflict",
                                "handoff_id": handoff_id,
                                "row": row_dict(existing),
                                "reason": "a live coordinator owns this conversation under another trigger",
                                "next": "leave it alone: a live coordinator serves this conversation; end the turn",
                            },
                            EXIT_CONFLICT,
                        )
                    live = False
                    if not args.dry_run:
                        # The guard is per CONVERSATION, not per name. A live
                        # lane this conversation's row RECORDS (the K3 window
                        # over an orphaned/retired row, or the same
                        # conversation under a new alias after a connector
                        # reset) is never relaunched over: the coordinator's
                        # `bind` repair re-attaches it. A derived tmux name
                        # that is taken (an existing session this
                        # conversation's row does not record, or a name
                        # another row records) is ANOTHER conversation's lane
                        # (#27864): take the next free name rather than refuse.
                        # The registry half runs on both backends (#37480: a
                        # Herdr launch never offers a label another row's
                        # recorded name holds); tmux's own listing counts
                        # only for a tmux launch (a dead tmux session of the
                        # same name is no obstacle to a Herdr tab).
                        if existing is not None:
                            live = lane_live(existing, names=names)
                            if live is None:
                                conn.execute("ROLLBACK")
                                return emit(unknown_conflict(existing), EXIT_CONFLICT)
                        if not live:
                            taken = taken_session_names(conn, names if backend == "tmux" else (), connector, conversation)
                            if lane_name in taken:
                                lane_name = next_free_session_name(lane_name, taken)
                    if live:
                        conn.execute("ROLLBACK")
                        state = existing["state"]
                        return emit(
                            {
                                "outcome": "conflict",
                                "handoff_id": handoff_id,
                                "tmux_session": existing["tmux_session"],
                                "backend": row_backend(existing),
                                "lane_ref": row_lane_ref(existing),
                                "row": row_dict(existing),
                                "reason": (
                                    f"{lane_words(existing)} is live but the registry row is {state};"
                                    " a human can `bind` it by hand or end the session deliberately;"
                                    " never relaunch over it"
                                ),
                                "next": "never kill or relaunch over it; tell your human, who can bind or end that session",
                            },
                            EXIT_CONFLICT,
                        )
                created = now
                note = args.note
                stamp = re.sub(r"[^0-9A-Za-z]", "", existing["created_at"] if existing is not None else now)
                relaunched = existing is not None
                if project_wanted:
                    # FR-38715-61: the one `agents init`, after the guards and
                    # before the handoff so the starter can name the project.
                    # A refusal changes nothing below: the thread launches
                    # and the receipt carries the cause (FM-38715-60).
                    request, requester = project_request(handoff)
                    project_report = create_project(request, project_slug(request), requester, args.workspace, handoff_id[:6])
                    if project_report.get("outcome") == "created":
                        # The channel is the handoff's fact (the receipt stays
                        # `{outcome, slug, path}`, review of #38876).
                        handoff["project"] = {
                            "slug": project_report["slug"], "path": project_report["path"],
                            "channel": project_channel(connector, conversation), "agents_script": agents_script_path(),
                        }
                        # #41802 (FR-41802-1(j)): the watcher's channel end is
                        # this connector's `progress-sink` on this lane, recorded
                        # as the project's `sink` setting so `go` starts the
                        # watch with it; a refused `set` costs the channel its
                        # in-place list, never the launch (Constitution XIII).
                        sink = f"python3 {args.connector_script} progress-sink --to {lane}"
                        set_line, set_code = run_agents(["set", project_report["slug"], "sink", sink], args.workspace)
                        if set_code != 0 or set_line.get("outcome") != "set":
                            sys.stderr.write(f"agents: the project's sink was not set ({set_line.get('error') or set_line.get('outcome')}); "
                                             "the status file keeps the list\n")
                        handoff["reply_shapes"]["watch"] = watch_shape(lane, project_report["slug"])
                archive_handoff_file(handoff_path, stamp)
                path = write_handoff_file(args.registry, handoff)
                conn.execute(
                    "INSERT OR REPLACE INTO conversation_owner (connector, conversation, lane, state,"
                    " handoff_id, handoff_path, event_id, tmux_session, muse_session_id, muse_session_name,"
                    " peer_address, daemon_session_id, daemon_session_name, created_at, updated_at,"
                    " validated_at, note, backend, backend_server, lane_ref)"
                    " VALUES (?, ?, ?, 'active', ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?, NULL, ?, ?, ?, ?)",
                    (
                        connector,
                        conversation,
                        lane,
                        handoff_id,
                        path,
                        args.event_id,
                        tmux_name(),
                        args.daemon_session_id,
                        args.daemon_session_name,
                        created,
                        now,
                        note,
                        # A tmux lane's ref is its name, known now; a Herdr
                        # pane id exists only once the runtime created it.
                        backend,
                        backend_server,
                        tmux_name(),
                    ),
                )
                conn.execute("COMMIT")
            except BaseException as error:
                _rollback_quietly(conn)
                if (project_report is not None and project_report.get("outcome") == "created"
                        and isinstance(error, (RegistryUnavailable, sqlite3.Error, OSError))):
                    # The folder exists and nothing else does (FM-38715-64,
                    # review of #38876): the refusal names it so the human can
                    # archive it; the next launch's `init` retries with the suffix.
                    return emit({"error": "registry_unavailable", "message": str(error), "project": project_report,
                                 "next": f"nothing claimed or launched; project {project_report['slug']} was created and has no"
                                         " coordinator: tell your human; the requester's next line re-dispatches"}, EXIT_IO)
                raise
            try:
                payload, code = runtime_launch(dry_run=args.dry_run)
            except EvidenceUnavailable as error:
                # The runtime answered no JSON line after the row was
                # committed (a crash, a kill in the grace window): the ONE
                # `failed` branch below records it (review of #29552).
                payload, code = {"outcome": error.code, "message": str(error)}, EXIT_EVIDENCE
            if code != 0 or payload.get("outcome") not in ("opened", "dry_run"):
                failure = str(payload.get("message") or f"lane runtime answered {payload.get('outcome')}")
                # A name tmux refused to create (another registry took it
                # between the pick and the create, or tmux failed) is not
                # this row's lane: record none, so the next launch picks
                # afresh instead of reading someone else's live session as
                # its own and answering `conflict` for good. Only an explicit
                # `created: false` says so: a runtime that died without a
                # line may have created the session first, and that live
                # orphan stays this conversation's, so the row keeps the
                # name and the next launch meets the live-owner guard.
                created = payload.get("created")
                state = "orphaned"
                note = f"launch failed: {failure}"
                if backend == "tmux":
                    kept = None if created is False else lane_name
                    kept_ref = kept
                else:
                    # A Herdr pane id is known only from the runtime's line:
                    # `created: true` names the pane retire/recover must
                    # find; `created: false` left nothing. No line at all
                    # (the runtime died in the create or grace window) may
                    # have left a running pane under a ref nobody recorded:
                    # the row stays ACTIVE and unknown — `launch` refuses,
                    # `recover` leaves it — until a human checks Herdr and
                    # marks it orphaned by hand (review of #31985).
                    kept = None
                    kept_ref = payload.get("ref") if created is not False else None
                    if created is None and kept_ref is None:
                        state = "active"
                        note = f"launch failed, pane id unknown (check Herdr, then mark --state orphaned): {failure}"
                server = payload.get("server") or backend_server
                conn.execute(
                    "UPDATE conversation_owner SET state = ?, updated_at = ?, note = ?,"
                    " tmux_session = ?, lane_ref = ?, backend_server = ? WHERE connector = ? AND conversation = ?",
                    (state, utc_now(), note[:NOTE_MAX], kept, kept_ref, server, connector, conversation),
                )
                failed = {
                    "outcome": "failed",
                    "error": "launch_failed",
                    "message": failure,
                    "handoff_id": handoff_id,
                    "handoff_path": path,
                    "tmux_session": kept,
                    "backend": backend,
                    "lane_ref": kept_ref,
                    "backend_server": server,
                    "lane_name": lane_name,
                }
                if project_report is not None:
                    failed["project"] = project_report  # a folder may exist with no coordinator; the next dispatch names it
                if state == "active":
                    failed["next"] = UNKNOWN_PANE_NEXT.format(connector=connector, conversation=conversation)
                elif created is not False and payload.get("withdrawn") is not True:
                    # #37687: only a runtime-verified failure keeps the
                    # "nothing is live" hint `emit` adds; a kept reference
                    # may still be live (review of PR #37700).
                    failed["next"] = LAUNCH_FAILED_LANE_KEPT_NEXT.format(lane=hint_token(kept_ref or kept or lane_name))
                return emit(failed, EXIT_EVIDENCE)
            built = payload
            if backend != "tmux" and payload.get("outcome") == "opened":
                # The pane id the runtime created lands on the row it was
                # written for (the launch parity the ADR asks for: a Herdr
                # id is `lane_ref`, never `tmux_session`).
                conn.execute(
                    "UPDATE conversation_owner SET lane_ref = ?, backend_server = COALESCE(?, backend_server),"
                    " updated_at = ? WHERE connector = ? AND conversation = ?",
                    (payload.get("ref"), payload.get("server"), utc_now(), connector, conversation),
                )
            row = fetch_row(conn, connector, conversation)
        finally:
            conn.close()
    return result("launched", row, path)


def cmd_bind(args):
    check_note(args.note)
    fields = {
        "muse_session_id": args.muse_session_id,
        "muse_session_name": args.muse_session_name,
        "peer_address": args.peer_address,
        "daemon_session_id": args.daemon_session_id,
        "daemon_session_name": args.daemon_session_name,
        "note": args.note,
    }
    updates = {name: value for name, value in fields.items() if value is not None}
    if not updates:
        raise UsageError(
            "usage",
            "bind needs at least one of --muse-session-id, --muse-session-name, --peer-address,"
            " --daemon-session-id, --daemon-session-name, --note",
        )
    conn = open_registry(args.registry)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = fetch_row(conn, args.connector, args.conversation)
        if row is None:
            conn.execute("ROLLBACK")
            return emit({"error": "no_active_row", "row": None}, EXIT_NOT_FOUND)
        inferred = bool(row["muse_session_id"]) and str(row["note"] or "").startswith(INFERRED_NOTE)
        if (
            row["muse_session_id"]
            and not inferred
            and args.muse_session_id is not None
            and args.muse_session_id != row["muse_session_id"]
        ):
            # A row bound to one Muse session is never taken over by another
            # (INV-2/INV-4), whatever its state: a mis-addressed repair must
            # not redirect the conversation. An identity `recover` merely
            # INFERRED is a guess the human may overrule.
            conn.execute("ROLLBACK")
            return emit(
                {
                    "error": "identity_conflict",
                    "row": row_dict(row),
                    "message": f"row is bound to muse session {row['muse_session_id']}",
                },
                EXIT_CONFLICT,
            )
        if row["state"] != "active":
            # The K3 window: recover orphaned an unbound row while its lane
            # lives. A hand `bind` re-attaches it.
            same_identity = row["muse_session_id"] is None or args.muse_session_id == row["muse_session_id"]
            live = lane_live(row) is True
            if not (same_identity and live and args.muse_session_id):
                conn.execute("ROLLBACK")
                return emit({"error": "no_active_row", "row": row_dict(row)}, EXIT_NOT_FOUND)
            updates["state"] = "active"
            updates["validated_at"] = utc_now()
            reattached = f"re-bound {utc_now()}: {lane_words(row)} live after recover"
            updates["note"] = (args.note or reattached)[:NOTE_MAX]
        else:
            reattached = None
        if args.muse_session_id is not None:
            # A human-asserted identity is a fact, not a guess: it replaces or
            # confirms an inferred one, is what `recover` validates from now
            # on, and orphans the lane when it goes unlisted. The id is the
            # address unless one is given. The provenance stamp always leads
            # the note, so a free-text note can neither counterfeit the
            # inferred marker nor hide the assertion.
            stamp = f"identity asserted by bind {utc_now()}"
            detail = args.note or reattached
            updates["note"] = (f"{stamp}; {detail}" if detail else stamp)[:NOTE_MAX]
            if inferred and args.peer_address is None:
                updates["peer_address"] = args.muse_session_id
            if inferred and args.muse_session_name is None and args.muse_session_id != row["muse_session_id"]:
                updates["muse_session_name"] = None
        elif inferred and args.note is not None and row["state"] == "active":
            # No id asserted, so the guess stays a guess: the inferred marker
            # survives in front of the human's note, and `recover` can still
            # withdraw the identity instead of orphaning a live lane.
            updates["note"] = f"{INFERRED_NOTE}; {args.note}"[:NOTE_MAX]
        elif args.note is not None and args.note.startswith(INFERRED_NOTE):
            # A note on an asserted (or unidentified) row must not read as
            # the inferred marker.
            updates["note"] = f"note; {args.note}"[:NOTE_MAX]
        assignments = ", ".join(f"{name} = ?" for name in updates)
        conn.execute(
            f"UPDATE conversation_owner SET {assignments}, updated_at = ? WHERE connector = ? AND conversation = ?",
            (*updates.values(), utc_now(), args.connector, args.conversation),
        )
        conn.execute("COMMIT")
        return emit({"row": row_dict(fetch_row(conn, args.connector, args.conversation))})
    finally:
        conn.close()


LOOKUP_NEXT = {
    "found": "route by the row's state: active means its coordinator owns the conversation;"
    " orphaned or retired means the next line is a new delegation",
    "not_found": "no row: nobody owns this conversation; a delegate creates the row",
}


def cmd_lookup(args):
    conn = open_readonly(args.registry)
    if conn is None:
        out = {"outcome": "not_found", "row": None, "next": LOOKUP_NEXT["not_found"]}
        if args.live:
            out["live"] = None
        return emit(out)
    try:
        row = fetch_row(conn, args.connector, args.conversation)
        outcome = "found" if row is not None else "not_found"
        out = {"outcome": outcome, "row": row_dict(row), "next": LOOKUP_NEXT[outcome]}
        if args.live:
            # `live` is the connector's re-entry read (#31985), opt-in: it
            # asks the lane runtime through the row's recorded backend (a
            # subprocess the per-message forwarder path must not pay for);
            # null when the evidence cannot be read — never a false that
            # would relaunch over an unknown lane.
            out["live"] = lane_live(row) if row is not None else None
        return emit(out)
    finally:
        conn.close()


def cmd_list(args):
    conn = open_readonly(args.registry)
    if conn is None or not has_table(conn, "conversation_owner"):
        return emit({"rows": []})
    try:
        if args.state:
            rows = conn.execute(
                "SELECT * FROM conversation_owner WHERE state = ? ORDER BY connector, conversation",
                (args.state,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM conversation_owner ORDER BY connector, conversation"
            ).fetchall()
        return emit({"rows": [row_dict(row) for row in rows]})
    finally:
        conn.close()


def cmd_mark(args):
    check_note(args.note)
    if args.state not in ("orphaned", "retired"):
        raise UsageError("usage", "--state must be orphaned or retired (active is only ever set by launch)")
    conn = open_registry(args.registry)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = fetch_row(conn, args.connector, args.conversation)
        if row is None:
            conn.execute("ROLLBACK")
            return emit(
                {"error": "no_active_row", "row": None, "next": "no row for this conversation; nothing was written"},
                EXIT_NOT_FOUND,
            )
        if args.state == "retired" and not row_lane_ref(row) and lane_live(row) is None:
            # FM-31985-2: an ACTIVE Herdr row with no recorded pane id is
            # unknown, never proven gone — `lookup --live` says null and
            # `launch` refuses the same row — so `retired` is refused too;
            # a human's `mark --state orphaned` (after checking Herdr) is the
            # judgment, and orphaned -> retired then writes.
            conn.execute("ROLLBACK")
            return emit(
                {
                    "error": "lane_unknown",
                    "row": row_dict(row),
                    "message": (
                        f"liveness of the {row_backend(row)} lane is unknown (no pane id was recorded); a row is"
                        " retired only after its lane is proven gone"
                    ),
                    "next": UNKNOWN_PANE_NEXT.format(connector=args.connector, conversation=args.conversation),
                },
                EXIT_EVIDENCE,
            )
        if args.state == "retired" and row_lane_ref(row):
            # FR-25011-20: `retired` means the lane is PROVEN gone. The lane
            # runtime's `forget` says so through the row's RECORDED backend,
            # refuses `session_live` while the exact session or pane is live,
            # and reads a server that cannot answer as unavailable evidence
            # (exit 6; `finally` rolls back) — never as "lane gone".
            verb = ["forget", "--mode", row_backend(row), "--ref", row_lane_ref(row)]
            if row_backend_server(row):
                verb += ["--server", row_backend_server(row)]
            payload, code = run_lane_runtime(*verb)
            if payload.get("outcome") == "session_live":
                # Two live daemons retired rows over running coordinators
                # (#27872); the row is the only thing that routes a follow-up,
                # so refuse and write nothing.
                conn.execute("ROLLBACK")
                return emit(
                    {
                        "error": "lane_live",
                        "row": row_dict(row),
                        "message": (
                            f"{lane_words(row)} is live; a row is retired only after"
                            " its lane is gone — the human ends the session deliberately first"
                        ),
                        "next": (
                            "end the tmux session deliberately first, then retire; never retire a live lane"
                            if row_backend(row) == "tmux"
                            else "end the Herdr pane deliberately first, then retire; never retire a live lane"
                        ),
                    },
                    EXIT_CONFLICT,
                )
            if code != 0 or payload.get("outcome") != "forgotten":
                raise lane_evidence_error(payload)
        conn.execute(
            "UPDATE conversation_owner SET state = ?, updated_at = ?, note = COALESCE(?, note)"
            " WHERE connector = ? AND conversation = ?",
            (args.state, utc_now(), args.note, args.connector, args.conversation),
        )
        conn.execute("COMMIT")
        return emit(
            {
                "outcome": "marked",
                "row": row_dict(fetch_row(conn, args.connector, args.conversation)),
                "next": f"row is {args.state}; this conversation's next line is a new delegation",
            }
        )
    finally:
        conn.close()


def handoff_workspace(path):
    """The workspace a lane was started in, from its handoff file. `recover`
    needs it to tell which live Muse session belongs to which lane; the
    registry stores no workspace column."""
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle).get("workspace")
    except (OSError, ValueError, AttributeError):
        return None
    return value if isinstance(value, str) else None


def encode_subscriptions(subscriptions, prompt, last_arm=None, listen=None, answered=None):
    value = {"subscriptions": subscriptions, "prompt": prompt}
    if last_arm:
        value["last_arm"] = last_arm
    if listen:
        value["listen"] = listen
    if answered:
        value["answered"] = answered
    return json.dumps(value, separators=(",", ":"))


def answered_end(raw):
    """The `at` of the last remembered arm failure a human connect (or a
    live listener) cleared: the connector's own ended record keeps reporting
    that end until its next listener takes the lease, and `start` must not
    write the end the human already answered back onto the row (owner's
    Mac, 2026-09-22: "last arm exited 3 at 08:19:04Z" after a re-connect).
    Kept beside the row's facts, never printed."""
    try:
        value = json.loads(raw) if raw else None
    except ValueError:
        return None
    answered = value.get("answered") if isinstance(value, dict) else None
    return answered if isinstance(answered, str) and answered else None


def decode_subscriptions(raw, connector):
    """The `subscriptions` column as `(subscriptions, prompt, last_arm,
    listen)`: the resolved subscription set `[{connector, sources,
    filters}]`, the raw prompt (adr:37480#D10), the row's remembered arm
    outcome `{"exit", "at", "reason"?}` (owner ruling 15, 2026-09-20, as
    amended by ruling 27, 2026-09-22; FR-38715-64(c)) - None until recorded,
    None again after a human connect or a listener that runs - and the exact
    `listen` command the human connect armed (#38715 QA r10 D-META-1: a
    restart replays it verbatim; the daemon stays word-blind, adr:37480#D3).
    The facts ride this column so the v3 schema stands (no migration). NULL
    or malformed reads as one empty subscription."""
    try:
        value = json.loads(raw) if raw else None
    except ValueError:
        value = None
    if not isinstance(value, dict):
        value = {}
    subscriptions = [
        entry for entry in (value.get("subscriptions") or []) if isinstance(entry, dict)
    ] if isinstance(value.get("subscriptions"), list) else []
    if not subscriptions:
        subscriptions = [{"connector": connector, "sources": [], "filters": []}]
    prompt = value.get("prompt")
    last_arm = value.get("last_arm")
    if not (isinstance(last_arm, dict) and isinstance(last_arm.get("exit"), int) and isinstance(last_arm.get("at"), str)):
        last_arm = None
    elif not (isinstance(last_arm.get("reason"), str) and last_arm["reason"]):
        last_arm = {"exit": last_arm["exit"], "at": last_arm["at"]}
    listen = value.get("listen")
    listen = listen if isinstance(listen, str) and listen.strip() else None
    return subscriptions, (prompt if isinstance(prompt, str) else None), last_arm, listen


def intent_row_dict(row):
    subscriptions, prompt, last_arm, listen = decode_subscriptions(row["subscriptions"], row["connector"])
    out = {
        "connector": row["connector"],
        "desired": row["desired"],
        "updated_at": row["updated_at"],
        "script": row["script"],
        "subscriptions": subscriptions,
        "prompt": prompt,
    }
    if last_arm:
        out["last_arm"] = last_arm  # present only once recorded, like `start`'s `stale`
    if listen:
        out["listen"] = listen
    return out


def upsert_intent(conn, connector, desired, now, sources=(), filters=(), prompt=None, script=None, merge=False, listen=None):
    """One row per connector (adr:37480#D3). `enabled` WITH a prompt is a
    prompt-mounted connect or reconnect (adr:37480#D10, FR-37480-41(c)): the
    named source words REPLACE the row's sources and the named filter words
    its filters — each set only when the reconnect names it, so a
    filter-only narrowing keeps the source it narrows (review of PR #38451)
    — and a restart re-arms exactly the set the human last asked for (#37480
    QA round 6 D1: `mention` -> `''` -> `assigned` used to leave the
    self-overlapping union `["", "assigned", "mention"]`); `merge=True` is
    the one additive spelling, for a prompt that says "also"/"add"; a prompt
    that names no words keeps the recorded ones. `enabled` WITHOUT a prompt
    - the Slack transports' `start --transport <t>` - adds the named words
    as before (adr:37480#D6). `disabled` WITH source words removes just
    those and reads `disabled` only when none is left — today's
    per-transport disconnect, on one row — while a bare `disabled` records
    it and keeps the words for a later re-connect. A new prompt replaces the
    old one (D10); a script is recorded when given and kept otherwise. Any
    `enabled` write is a human connect and clears the row's remembered arm
    failure (`last_arm`, owner ruling 15): the human asked for a fresh try;
    a `disabled` keeps it. `listen` is the exact command the connect arms
    (D-META-1): a prompt-mounted connect or reconnect records the one it
    passes and drops the old one when it passes none (the words moved); an
    additive or word-less write keeps it. Returns the row as `intent get`
    reads it."""
    existing = conn.execute("SELECT * FROM connector_intent WHERE connector = ?", (connector,)).fetchone()
    subscriptions, old_prompt, last_arm, old_listen = decode_subscriptions(existing["subscriptions"] if existing else None, connector)
    answered = answered_end(existing["subscriptions"]) if existing else None
    head = subscriptions[0]
    have_sources = set(head.get("sources") or [])
    have_filters = set(head.get("filters") or [])
    if desired == "enabled":
        # The end the human answered stays known, so the connector's record
        # of it (reported until its next listener) is never written back.
        answered = last_arm["at"] if last_arm else answered
        last_arm = None
        if (prompt is not None and not merge) or listen:
            old_listen = listen
        if prompt is not None and not merge:
            if sources:
                have_sources = set(sources)
            if filters:
                have_filters = set(filters)
        else:
            have_sources |= set(sources)
            have_filters |= set(filters)
    elif sources:
        have_sources -= set(sources)
        have_filters -= set(filters)
        desired = existing["desired"] if (existing is not None and have_sources) else "disabled"
    subscriptions[0] = {"connector": connector, "sources": sorted(have_sources), "filters": sorted(have_filters)}
    if prompt is None:
        prompt = old_prompt
    if script is None and existing is not None:
        script = existing["script"]
    conn.execute(
        "INSERT INTO connector_intent (connector, desired, updated_at, script, subscriptions) VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(connector) DO UPDATE SET desired = excluded.desired, updated_at = excluded.updated_at,"
        " script = excluded.script, subscriptions = excluded.subscriptions",
        (connector, desired, now, script, encode_subscriptions(subscriptions, prompt, last_arm, old_listen, answered)),
    )
    return intent_rows(conn, connector)[0]


def record_arm_exit(conn, connector, code, now, reason=None):
    """`intent arm-exit` (owner ruling 15, 2026-09-20; FR-38715-64(c)): the
    listener Monitor the daemon armed from this row exited non-zero. The
    fact `{"exit": <code>, "at": <now>, "reason"?: <the connector's one
    line>}` is written beside the record - desired, words, prompt and script
    untouched, `updated_at` too (that is the human's last word, this is the
    machine's) - so every later bare `start` lists the row `stale` until a
    human connect clears it or the human's restart (`start --retry`) gives
    it one fresh try (owner ruling 27, 2026-09-22). None when the connector
    has no row: nothing was armed from one."""
    existing = conn.execute("SELECT * FROM connector_intent WHERE connector = ?", (connector,)).fetchone()
    if existing is None:
        return None
    subscriptions, prompt, _old, listen = decode_subscriptions(existing["subscriptions"], connector)
    last_arm = {"exit": code, "at": now}
    if reason:
        last_arm["reason"] = reason
    conn.execute(
        "UPDATE connector_intent SET subscriptions = ? WHERE connector = ?",
        (encode_subscriptions(subscriptions, prompt, last_arm, listen, answered_end(existing["subscriptions"])), connector),
    )
    return intent_rows(conn, connector)[0]


def forget_arm_exit(conn, connector):
    """The row's remembered failure is over: its listener runs (the fresh
    try worked, or a human armed it by hand). The memory goes, and the end
    it stood for counts as answered, so a later clean stop never resurrects
    it from the connector's record."""
    existing = conn.execute("SELECT * FROM connector_intent WHERE connector = ?", (connector,)).fetchone()
    subscriptions, prompt, last_arm, listen = decode_subscriptions(existing["subscriptions"], connector)
    answered = last_arm["at"] if last_arm else answered_end(existing["subscriptions"])
    conn.execute(
        "UPDATE connector_intent SET subscriptions = ? WHERE connector = ?",
        (encode_subscriptions(subscriptions, prompt, None, listen, answered), connector),
    )


def reported_listener_exit(entry, sources):
    """`(exit, ended_at, reason)` when one of the connector's own listener
    records for this row says its last listener ended NON-ZERO (D-META-3:
    the `intent arm-exit` call is a model call and was skipped in a busy
    turn, so `start` records what the connector's status already reports) -
    a record covering one of the row's words, or any record when the row
    has none; `reason` is the record's one-line cause when it carries one
    (ruling 27), else None. None without such a record: the bundled
    connectors report it (round-11 N2), a third-party one need not, and
    exit 0 is D21's re-arm through `start`."""
    for name, record in listener_records(entry):
        code, ended, reason = record.get("exit"), record.get("ended_at"), record.get("reason")
        if not (isinstance(code, int) and code != 0 and isinstance(ended, str) and ended):
            continue
        if sources and not any(record_covers(name, record, word) for word in sources):
            continue
        return code, ended, (reason if isinstance(reason, str) and reason else None)
    return None


def intent_rows(conn, connector=None):
    """Every intent row (or one connector's) as `intent get` prints them. An
    un-migrated v2 file (a read-only verb never migrates) is read through
    the same merge the migration applies, under the same frozen literal, so
    an older file still answers and a v3 SELECT never turns the daemon's own
    onboarding read into exit 7 (adr:37480#D3)."""
    present = [row[1] for row in conn.execute("PRAGMA table_info(connector_intent)").fetchall()]
    if "connector" not in present and "transport" in present:
        rows = conn.execute("SELECT transport, desired, updated_at FROM connector_intent").fetchall()
        merged = [merge_v2_intent(rows, "slack-connector")] if rows else []
        return [row for row in merged if connector is None or row["connector"] == connector]
    if connector:
        rows = conn.execute("SELECT * FROM connector_intent WHERE connector = ?", (connector,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM connector_intent ORDER BY connector").fetchall()
    return [intent_row_dict(row) for row in rows]


def intent_sources(row):
    """The source words of a row's first subscription (the connector's own
    listener names, matched by byte equality against its `listeners` map)."""
    head = (row.get("subscriptions") or [{}])[0]
    return [word for word in (head.get("sources") or []) if isinstance(word, str)]


def active_row_count(conn):
    return conn.execute("SELECT COUNT(*) FROM conversation_owner WHERE state = 'active'").fetchone()[0]


def recover_summary(report):
    """One line for the `recover` / `start` tool row (ADR 25011 D22 item 4)."""
    if report.get("skipped"):
        return f"recover skipped ({report['skipped']})"
    counts = []
    for key in ("reused", "orphaned", "filled", "unbound", "unlocated", "readdress"):
        value = report.get(key)
        if key == "unlocated" and not value:
            continue  # D29 item 4: its own bucket; an empty one keeps the line as it always read
        if isinstance(value, list):
            counts.append(f"{key} {len(value)}")
        elif isinstance(value, int):
            counts.append(f"{key} {value}")
    return "recover " + (" · ".join(counts) if counts else "done")


def describe_recover(report, with_next=True):
    """ADR 25011 D22 item 4 (`summary`) and adr:25011#D27 item 2 (`outcome`,
    `next`): the recover verb's shape, shared with `start`'s recover half —
    which carries no nested `next`: one voice per line, `start`'s own."""
    report["summary"] = recover_summary(report)
    report["outcome"] = "judged"
    if not with_next:
        return report
    # Audit #38191 D11: the counts ride `summary` (rendered by the runtime) and
    # `recover.lanes[]`; `next` names the one line, never a second tally.
    report["next"] = "say the summary in one line; an orphaned conversation's next line is a new delegation"
    return report


def cmd_recover(args):
    conn = open_registry(args.registry)
    try:
        report = recover_pass(conn, args)
        ignored = ignored_env(test_seams_enabled())
        if ignored:
            report["ignored_env"] = ignored
        describe_recover(report)
        return emit(report)
    finally:
        conn.close()


def lane_verdicts(lanes, args, claimed):
    """The lane runtime's `status --lanes-json` over `lanes` (adr:25011 D24): a verdict
    by key. A row with no tmux session was never a lane (`failed` with
    nothing created) and is gone without asking; every other row rides the
    ONE call — the lanes on stdin, the session list as `--peers-json` (a
    stdin list is staged in a private file) or the armed seam's
    `--peer-list-cmd`. Evidence the runtime cannot read is this helper's
    exit 6, the ingress-closed arm as `IngressClosed` for `start`."""
    verdicts = {
        lane["key"]: {"session": "gone", "identity": None} for lane in lanes if not lane["ref"]
    }
    request = {
        "lanes": [lane for lane in lanes if lane["ref"]],
        # The daemon's own session is never a lane's, however its workspace
        # is named — and the runtime can exclude it only when told which one
        # it is. Without `--daemon-session-id` nothing is inferred: a guess
        # that could be the daemon itself is worse than no guess.
        "exclude_session_ids": [args.daemon_session_id] if args.daemon_session_id else [],
        "claimed_session_ids": [str(identity) for identity in claimed],
        "infer": bool(args.daemon_session_id),
    }
    verb = ["status", "--lanes-json", "-"]
    staged = None
    try:
        if args.peers_json == "-":
            fd, staged = tempfile.mkstemp(prefix=".peers-", suffix=".json")
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(sys.stdin.read())
            verb += ["--peers-json", staged]
        elif args.peers_json:
            verb += ["--peers-json", args.peers_json]
        else:
            override = peer_list_override(test_seams_enabled())
            if override:
                verb += ["--peer-list-cmd", override]
        payload, code = run_lane_runtime(*verb, stdin=json.dumps(request))
    finally:
        if staged:
            try:
                os.unlink(staged)
            except OSError:
                pass
    if code != 0 or payload.get("outcome") != "judged":
        raise lane_evidence_error(payload)
    for verdict in payload.get("lanes") or []:
        if isinstance(verdict, dict):
            verdicts[verdict.get("key")] = verdict
    missing = [lane["key"] for lane in lanes if lane["key"] not in verdicts]
    if missing:
        raise EvidenceUnavailable("lane_runtime_unavailable", f"lane runtime returned no verdict for {', '.join(missing)}")
    return verdicts


def identity_failure(verdict, row):
    """Why a recorded identity no longer holds, in the words the row's note
    has always carried."""
    identity = row["muse_session_id"]
    detail = verdict.get("detail")
    if detail == "listed_twice":
        return f"muse session {identity} listed twice"
    if detail == "name_mismatch":
        return f"muse session name {verdict.get('listed_name')} does not match {row['muse_session_name']}"
    return f"muse session {identity} not listed"


def unbound_reason(verdict):
    detail = verdict.get("detail")
    if detail == "inference_off":
        return (
            "identity not inferred: pass --daemon-session-id so the daemon's own"
            " session can be excluded from the candidates"
        )
    if detail == "workspace_unknown":
        return "the lane's workspace is unknown"
    return f"{verdict.get('candidates', 0)} live sessions in workspace {verdict.get('label')}"


def recover_pass(conn, args):
    """The recovery judgment `recover` and `start` share: every `active` row
    in scope is judged from live evidence and the pass's report is returned
    (never emitted here, so `start` can fold it into its one line)."""
    if args.conversation:
        rows = [fetch_row(conn, args.connector, args.conversation)]
        rows = [row for row in rows if row is not None and row["state"] == "active"]
    else:
        rows = conn.execute(
            "SELECT * FROM conversation_owner WHERE state = 'active' ORDER BY connector, conversation"
        ).fetchall()
    # Gather EVERY piece of evidence a judgment needs before the first
    # write: unavailable evidence must leave the registry exactly as it
    # was. The lane runtime's ONE `recover` judges every row in scope from
    # tmux — the SAME exact-name, live-pane predicate `launch`, `bind` and
    # `mark` use; under `remain-on-exit` a crashed coordinator keeps its
    # session name, and a name is not a lane — and reads the session list
    # only for a row whose tmux session is LIVE (to validate or infer its
    # identity), so a dead lane is judged on tmux evidence alone: the
    # per-conversation recover `delegate` runs on a dead lane must never be
    # blocked by a closed ingress gate, or the row stays `active` and the
    # relaunch meets the live-owner guard.
    # An id another row already records is that lane's, never a candidate
    # for a second one — two lanes in one workspace never collapse onto
    # one identity; the runtime claims ids in row order and frees a guess
    # it withdraws.
    claimed = [
        row[0]
        for row in conn.execute(
            "SELECT muse_session_id FROM conversation_owner WHERE muse_session_id IS NOT NULL"
        ).fetchall()
    ]
    # An active Herdr row with no pane id (a launch in flight, or a runtime
    # that died before its line) has nothing the runtime can be asked about
    # and may still own a running pane: it is left exactly as it is and
    # reported, never orphaned — the human checks Herdr and marks it by hand.
    unknown = [row for row in rows if row_backend(row) != "tmux" and not row_lane_ref(row)]
    rows = [row for row in rows if not (row_backend(row) != "tmux" and not row_lane_ref(row))]
    lanes = [
        {
            "key": key_of(row["connector"], row["conversation"]),
            # #31985: the runtime judges each session through its RECORDED
            # provider; a legacy row reads as tmux (D5: never reselected).
            # The row's own column names stay; the runtime's words are
            # `provider`/`ref`/`server` (adr:38715#D4).
            "provider": row_backend(row),
            "ref": row_lane_ref(row),
            "server": row_backend_server(row),
            "muse_session_id": row["muse_session_id"],
            "muse_session_name": row["muse_session_name"],
            "identity_inferred": bool(row["muse_session_id"]) and str(row["note"] or "").startswith(INFERRED_NOTE),
            "workspace": handoff_workspace(row["handoff_path"]) if row["handoff_path"] else None,
        }
        for row in rows
    ]
    verdicts = lane_verdicts(lanes, args, claimed)
    reused, orphaned, readdress, unbound, filled, unlocated = [], [], [], [], [], []
    now = utc_now()
    conn.execute("BEGIN IMMEDIATE")
    for row in rows:
        key = key_of(row["connector"], row["conversation"])
        verdict = verdicts[key]
        # The lane's liveness is its exact tmux session or Herdr pane — the
        # one thing `launch` created and the one thing a dead coordinator
        # loses.
        if verdict["session"] != "live":
            if row_backend(row) == "tmux":
                reason = f"tmux session {row['tmux_session']} absent or its pane dead"
            else:
                reason = f"{lane_words(row)} absent or its agent gone"
            conn.execute(
                "UPDATE conversation_owner SET state = 'orphaned', updated_at = ?, note = ?"
                " WHERE connector = ? AND conversation = ?",
                (now, reason[:NOTE_MAX], row["connector"], row["conversation"]),
            )
            orphaned.append({"key": key, "reason": reason})
            continue
        identity = row["muse_session_id"]
        judged = verdict.get("identity")
        fill = None
        withdraw = None
        if judged == "invalid":
            # A recorded identity is VALIDATED: the process the row named
            # is either still listed or gone. Gone is orphaned even with a
            # live tmux session of that name — when a human ASSERTED the
            # identity (`bind`).
            reason = identity_failure(verdict, row)
            conn.execute(
                "UPDATE conversation_owner SET state = 'orphaned', updated_at = ?, note = ?"
                " WHERE connector = ? AND conversation = ?",
                (now, reason[:NOTE_MAX], row["connector"], row["conversation"]),
            )
            orphaned.append({"key": key, "reason": reason})
            continue
        if judged == "withdrawn":
            # An identity `recover` itself INFERRED is a guess, so a guess
            # that stops being listed while the lane is live is withdrawn,
            # and the lane goes on as `unbound`.
            withdraw = f"inferred identity {identity} withdrawn: {identity_failure(verdict, row)}"
            unbound.append({"key": key, "reason": withdraw})
        elif judged == "inferred":
            # `adr:25011-daemon-session-coordination#D13`: nothing reports
            # in, so a live lane usually has no identity yet. Fill it when
            # the live list leaves exactly one candidate in that lane's
            # workspace; otherwise keep the lane and SAY it is
            # unidentified. Orphaning it would open a second coordinator
            # for a conversation that already has a live one.
            fill = verdict
            filled.append({"key": key, "muse_session_id": str(verdict["muse_session_id"])})
        elif judged == "unbound":
            unbound.append({"key": key, "reason": unbound_reason(verdict)})
        daemon_id = args.daemon_session_id or row["daemon_session_id"]
        daemon_name = args.daemon_session_name or row["daemon_session_name"]
        if args.daemon_session_id and row["daemon_session_id"] != args.daemon_session_id:
            # A new daemon: the stored display name belonged to the old
            # one, so it is replaced by the name given now — None when
            # none was — never kept next to an id it never had.
            daemon_name = args.daemon_session_name
            # The lane's handoff still names the previous daemon session
            # id. Nothing addresses the daemon any more (`#D11`), so this
            # is an audit line, not an errand.
            readdress.append(
                {
                    "key": key,
                    "peer_address": row["peer_address"],
                    "stored_daemon_session_id": row["daemon_session_id"],
                    "stored_daemon_session_name": row["daemon_session_name"],
                }
            )
        if fill is not None:
            conn.execute(
                "UPDATE conversation_owner SET validated_at = ?, updated_at = ?, daemon_session_id = ?,"
                " daemon_session_name = ?, muse_session_id = ?, muse_session_name = ?, peer_address = ?,"
                " note = ? WHERE connector = ? AND conversation = ?",
                (
                    now, now, daemon_id, daemon_name,
                    str(fill["muse_session_id"]),
                    fill.get("muse_session_name"),
                    str(fill["muse_session_id"]),
                    f"{INFERRED_NOTE} from workspace label {fill.get('label')}"[:NOTE_MAX],
                    row["connector"], row["conversation"],
                ),
            )
        elif withdraw is not None:
            conn.execute(
                "UPDATE conversation_owner SET validated_at = ?, updated_at = ?, daemon_session_id = ?,"
                " daemon_session_name = ?, muse_session_id = NULL, muse_session_name = NULL,"
                " peer_address = NULL, note = ? WHERE connector = ? AND conversation = ?",
                (now, now, daemon_id, daemon_name, withdraw[:NOTE_MAX], row["connector"], row["conversation"]),
            )
        else:
            conn.execute(
                "UPDATE conversation_owner SET validated_at = ?, updated_at = ?, daemon_session_id = ?,"
                " daemon_session_name = ? WHERE connector = ? AND conversation = ?",
                (now, now, daemon_id, daemon_name, row["connector"], row["conversation"]),
            )
        reused.append(key)
    conn.execute("COMMIT")
    for row in unknown:
        # D29 item 4: neither live nor gone, so neither `unbound` (a live lane
        # with no inferable identity, asking for nothing) nor `orphaned`.
        unlocated.append({
            "key": key_of(row["connector"], row["conversation"]),
            "reason": (
                f"{row_backend(row)} lane has no recorded pane id (its launch is in flight or never reported one):"
                " liveness unknown, left active"
            ),
            "next": (
                "check Herdr for a pane serving this conversation; end it by hand if it is live (no verb can"
                " supply the missing pane id), then `mark --state orphaned`"
            ),
        })
    return {
        "checked": len(rows) + len(unknown),
        "reused": reused,
        "orphaned": orphaned,
        "filled": filled,
        "unbound": unbound,
        "unlocated": unlocated,
        "readdress": readdress,
    }


UNREADABLE_LISTENER = {"listener": "unreadable"}
STATUS_CMD_ENV = "MUSE_DAEMON_CONNECTOR_STATUS_CMD"


def sibling_connector_script(connector_id):
    """The bundled-skills convention: `../../<connector>/scripts/<connector
    with underscores>.py`, joined against this helper's own directory."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", connector_id, "scripts", connector_id.replace("-", "_") + ".py"))


def connector_status_argv(connector_id, script=None):
    """ONE connector's `status --json` command. The DEFAULT connector honours
    MUSE_DAEMON_CONNECTOR_STATUS_CMD (the suite's seam, an operator's
    override); every connector otherwise runs the script its intent row
    recorded, else the sibling convention. FileNotFoundError names the path
    that was tried."""
    if connector_id == DEFAULT_CONNECTOR:
        configured = os.environ.get(STATUS_CMD_ENV)
        if configured:
            return shlex.split(configured)
    script = script or sibling_connector_script(connector_id)
    if not os.path.isfile(script):
        raise FileNotFoundError(script)
    return [sys.executable, script, "status", "--json"]


def status_timeout_s():
    try:
        return float(os.environ.get("MUSE_DAEMON_CONNECTOR_STATUS_TIMEOUT_S", "15"))
    except ValueError:
        return 15.0


def run_connector_status(argv):
    """`(status, None)` — the JSON object on the command's last stdout line —
    or `(None, reason)`: a command that cannot run or outlives the bounded
    wait, one that exits non-zero (a state fault; a cold connector answers
    exit 0, #30502), or one that prints no JSON object."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=status_timeout_s(), check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, f"{argv[0]}: {type(error).__name__}: {error}"
    if proc.returncode != 0:
        last = (proc.stderr.strip().splitlines() or [""])[-1]
        return None, f"connector status exited {proc.returncode}: {last}"[:NOTE_MAX]
    try:
        status = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None, "connector status printed no JSON"
    if not isinstance(status, dict):
        return None, "connector status printed no JSON object"
    return status, None


def connector_status(connector_id, script=None):
    try:
        argv = connector_status_argv(connector_id, script)
    except FileNotFoundError as error:
        return None, f"connector script not found at {error}"
    return run_connector_status(argv)


def lane_env_pass(script):
    """The env NAMES a coordinator lane must see (adr:37480#D1): the helper's
    own plus the list the connector's `status --json` declares under
    `env_pass`; a connector that declares none — the script missing, a
    non-zero exit, no JSON, no such field — gets the Slack tuple, so the
    pre-#37480 passthrough is byte-identical. Values never travel."""
    status, _reason = run_connector_status([sys.executable, str(script), "status", "--json"])
    names = status.get("env_pass") if isinstance(status, dict) else None
    if isinstance(names, list) and names and all(isinstance(name, str) and name for name in names):
        return HELPER_ENV_PASS + tuple(dict.fromkeys(names))
    return LANE_ENV_PASS


def connector_listeners(connector_id, script=None):
    """ONE connector's listener report (adr:37480#D4), read through its own
    `status --json` — never its private files. Returns `(entry, reason,
    steward, binding, known)`: a clean read passes the connector's `listeners`
    object through verbatim with no reason; a status that cannot be read, or
    one without the field (an older connector), is `{"listener":
    "unreadable"}` WITH the reason — never a guess at `absent`. `steward`
    is the connector's standing fleet-steward record (#31985) and `binding`
    its `mailbox.recent_binding` verdict (#37011) when the status carries
    them. `known` is the source names the connector answers for
    (FR-38715-64): its `sources_available` list when the status carries one
    (a stream connector's generated catalog), else the source words its
    listener records name under `sources` (never the record KEYS, which are
    subscriptions - D-META-2/N6); None when the status gives no evidence
    either way — unreadable, no `listeners` map, records without `sources`,
    or an EMPTY `sources_available`: the one producer prints `[]` exactly
    when it cannot read its own catalog (#39373), so an empty list is no
    evidence until a producer promises otherwise (review of PR #39385)."""
    status, reason = connector_status(connector_id, script)
    if status is None:
        return dict(UNREADABLE_LISTENER), reason, None, None, None
    listeners = status.get("listeners")
    steward = status.get("steward") if isinstance(status.get("steward"), dict) else None
    binding = None
    if isinstance(status.get("mailbox"), dict):
        candidate = status["mailbox"].get("recent_binding")
        binding = candidate if isinstance(candidate, dict) else None
    available = status.get("sources_available")
    if isinstance(available, list) and all(isinstance(name, str) for name in available):
        known = sorted(set(available)) or None
    else:
        # The records' own source words, never their keys: a key is a
        # subscription (`<source>|<filter>`, a digest), which judged a live
        # connector-author connector stale (D-META-2) and hid a re-worded
        # source behind a live sibling (N6).
        words = {word for _name, record in listener_records(listeners)
                 for word in (record.get("sources") or []) if isinstance(word, str)}
        known = sorted(words) or None
    if not isinstance(listeners, dict):
        return dict(UNREADABLE_LISTENER), "connector status carries no `listeners` field (older connector)", steward, binding, known
    return listeners, None, steward, binding, known


def listener_records(entry):
    """The `{"listener": "live"|"absent", ..}` records inside one connector's
    entry as `(name, record)` pairs: a flat record is one unnamed record; a
    map of named records (Slack's `mailbox`/`slack`) is each of them."""
    if not isinstance(entry, dict):
        return []
    if isinstance(entry.get("listener"), str):
        return [(None, entry)]
    return [(name, record) for name, record in sorted(entry.items())
            if isinstance(record, dict) and isinstance(record.get("listener"), str)]


def listener_word(name, record):
    return f"{name} listener {record['listener']}" if name else f"listener {record['listener']}"


def row_word(name, record):
    """The summary's word for one record (#41206, owner ruling 41): the
    connector's durable `row` text when it reports one — `connected`,
    `reconnecting since <t> (attempt n, last error: <e>, next try in Ns)`,
    `stopped: <reason>` — else the bare `live`/`absent`. The arm words
    (`listener_word`) stay `absent`: a row stopped by a FAILURE is still armed
    by a human's restart (ruling 27); one stopped by a human's `disconnect`
    is `start`'s `stopped` verdict (`human_disconnect`), armed by no restart."""
    row = record.get("row")
    state = row if isinstance(row, str) and row else record["listener"]
    return f"{name} listener {state}" if name else f"listener {state}"


def reconnecting_listeners(listeners):
    """`{connector: "reconnecting since <t> (...)"}` for every connector whose
    LIVE listener record carries `reconnecting_since` (#41206): the listener
    is inside its own re-attach ladder, so the row is neither armed nor
    `stale`; `stale` stays for the ends the ladder does not cover (a foreign
    holder, a rejected credential, a stop, an exit)."""
    out = {}
    for connector, entry in sorted(listeners.items()):
        if entry.get("listener") == "unreadable":
            continue
        for _name, record in listener_records(entry):
            since = record.get("reconnecting_since")
            if record.get("listener") == "live" and isinstance(since, str) and since:
                row = record.get("row")
                out[connector] = row if isinstance(row, str) and row.startswith("reconnecting since") else f"reconnecting since {since}"
                break
    return out


def record_covers(name, record, word):
    """Does this listener record speak for the row's source `word`? By key
    (Slack's `mailbox` intent against its `mailbox` record) or by the
    record's own `sources` list (a stream connector keys its records by
    subscription and names the words inside)."""
    return name == word or word in (record.get("sources") or [])


def listeners_to_arm(entry, sources):
    """What `start` must arm for ONE enabled connector, as the words `next`
    prints: nothing when every listener that counts is live. Each row word
    is covered by a LIVE record that names it (`record_covers`); an
    uncovered word is `<word> listener absent` - so a row re-worded to a new
    source beside a live sibling subscription is armed (N6), and a record
    keyed by subscription counts for the words it names (D-META-2). With no
    word matched at all on a connector whose records name no sources (a
    name-only map, Slack), any live record means nothing to arm. `unreadable`
    and an empty map are named as such — an unavailable read is never
    `live`."""
    if not isinstance(entry, dict) or entry.get("listener") == "unreadable":
        return ["listener unreadable"]
    records = listener_records(entry)
    if not records:
        return ["listener absent"]
    source_aware = any(isinstance(record.get("sources"), list) for _name, record in records)
    matched = {word: [(name, record) for name, record in records if record_covers(name, record, word)] for word in sources}
    if source_aware or any(matched.values()):
        words = []
        for word, covering in matched.items():
            if any(record["listener"] == "live" for _name, record in covering):
                continue
            words.append(listener_word(word, covering[0][1]) if len(covering) == 1 else f"{word} listener absent")
        return words
    if any(record["listener"] == "live" for _, record in records):
        return []
    return [listener_word(name, record) for name, record in records]


def disable_command(connector_id):
    """The whole-row `--desired disabled`, never `--source <w>`: a bare
    disable keeps the recorded words, so a later re-connect (a refreshed
    catalog, a restored script) re-enables the same subscription."""
    return f"intent set --connector {connector_id} --desired disabled"


def connect_command(connector_id):
    """The whole-row `--desired enabled` a human re-connect runs: it clears
    the remembered arm failure and arms the recorded words again."""
    return f"intent set --connector {connector_id} --desired enabled"


def stale_intent(row, known, live=False, retry=False):
    """Why an `enabled` row cannot be armed as recorded (FR-38715-64; owner
    rulings 9 and 15, 2026-09-20, and 27, 2026-09-22: a restart is a
    refresh, and a row the connector can no longer honour is reported, never
    armed). Three causes, all read from evidence `start` already has: the
    recorded connector script is gone (a plugin refresh moved the skill
    cache); a recorded source is not among the names the connector answers
    for; or the row remembers its last arm exiting non-zero (`intent
    arm-exit`, or the connector's own ended record) and this is a bare
    `start` - the human's restart passes `retry` and gives that row one
    fresh try instead (ruling 27: the owner's Mac showed "re-connect to try
    again" on every `/daemon` with nothing tried). The reason names the
    exit, the time, the connector's own one-line cause when it reported
    one, and the exact re-connect command. Unknown is never stale: a status
    with no source evidence (`known` None, an empty list included) or a row
    with no source words passes the source check, and so does a row whose
    words a LIVE listener covers (`live`, judged per row - D-R11-META-2): a
    listener that runs is the proof it honours THAT row, whatever the
    catalog says (D-META-2) and whatever an earlier arm did."""
    script = row.get("script")
    if script and not os.path.isfile(script):
        return f"connector script missing: {script}"
    sources = intent_sources(row)
    if sources and known and not live:
        unknown = [word for word in sources if word not in set(known)]
        if unknown:
            return f"sources not among the connector's known sources: {', '.join(unknown)} (known: {', '.join(known)})"
    last_arm = row.get("last_arm")
    if last_arm and not (live or retry):
        return f"{arm_failure_words(last_arm)}; re-connect to try again: {connect_command(row['connector'])}"
    return None


def human_disconnect(entry, sources, updated_at):
    """The stamp of a human's `disconnect` newer than the row's last human
    write (r22 SR-DAEMON R-5): an ABSENT listener record covering one of the
    row's words (any record when the row has none) whose `row` reads
    `stopped: disconnected` and whose `disconnected_at` is later than
    `updated_at`. A stop is not a failure: `start` — bare or `--retry` —
    lists such a row under `stopped` and arms nothing for it; a human connect
    (a newer `updated_at`) arms it again and that arm clears the stamp.
    None otherwise, an older stamp included: the later human action wins."""
    newest = None
    for name, record in listener_records(entry):
        stamp = record.get("disconnected_at")
        row = record.get("row")
        if record.get("listener") != "absent" or not (isinstance(stamp, str) and stamp):
            continue
        if not (isinstance(row, str) and row.startswith("stopped: disconnected")):
            continue
        if sources and not any(record_covers(name, record, word) for word in sources):
            continue
        if stamp > updated_at and (newest is None or stamp > newest):
            newest = stamp
    return newest


def arm_failure_words(last_arm):
    """`last arm exited <code> at <time>[: <the connector's reason>]`."""
    words = f"last arm exited {last_arm['exit']} at {last_arm['at']}"
    return f"{words}: {last_arm['reason']}" if last_arm.get("reason") else words


def arm_order(intents):
    """The rows in the order `start` judges and arms them: the default
    connector first, ahead of every other row whatever the ids sort to
    (owner ruling 15: the owner's mailbox was never armed because a stream
    connector's arm, listed first, failed and the model stopped there)."""
    return sorted(intents, key=lambda row: (row["connector"] != DEFAULT_CONNECTOR, row["connector"]))


def listener_names_to_arm(words, sources):
    """The DEFAULT connector's listener names behind `listeners_to_arm`'s
    words, one Monitor call each: a named word (`mailbox listener absent`)
    names itself; an unnamed one (`listener absent`, `listener unreadable`)
    means every recorded source, else the mailbox."""
    named = [word.split(" ", 1)[0] for word in words if word.split(" ", 1)[0] != "listener"]
    if named:
        return named
    return list(sources) or ["mailbox"]


def arm_record(connector_id, script, listener, sources, filters, daemon_session_id, listen=None):
    """One arm the daemon must make, as facts it can act on without a second
    call (D27 item 2: guidance in the result, no enforcement): one Monitor
    record per default-connector listener, one command-less facts record per
    other connector's intent row. For the default connector the exact
    `monitor(...)` line the skill body
    teaches — `listen --deliver-to <daemon session id>` under `peer inbox`
    for the mailbox (the flag is omitted only when no id is known), `listen
    --only-owner` under `slack channel` for Slack. Any other connector's
    `listen` takes words this helper never parses (adr:37480#D3), so its
    record names the script, the recorded words and the label and no
    command."""
    script = os.path.normpath(script) if script else sibling_connector_script(connector_id)
    if connector_id == DEFAULT_CONNECTOR and listener in ("mailbox", "slack"):
        record = {"connector": connector_id, "listener": listener, "script": script}
        if listener == "mailbox":
            command = f"python3 {script} listen --daemon-skill" + (
                f" --deliver-to {daemon_session_id}" if daemon_session_id else ""
            )
            description = "peer inbox"
        else:
            command = f"python3 {script} listen --only-owner"
            description = "slack channel"
        record["description"] = description
        record["monitor"] = (
            f'monitor(command="{command}", persistent=true, wake_delay_ms=0, show_lines=true, description="{description}")'
        )
        return record
    # One record per intent row, whatever its listeners are called: its
    # `listen` is one call (review of PR #39364: a record per absent name
    # invited the second arm the connector refuses).
    record = {"connector": connector_id, "script": script, "sources": list(sources), "filters": list(filters)}
    hint = f" ({', '.join(filters)})" if filters else ""
    record["description"] = f"{connector_id} {','.join(sources) or 'all'}{hint}"
    if listen:
        # D-META-1: the exact command the human connect armed, replayed
        # verbatim - a restart used to arm a bare `listen` and widen the
        # human's `tasks` to the whole stream. The daemon reads nothing of
        # the connector to print it (adr:37480#D3).
        record["command"] = listen
        record["monitor"] = (
            f'monitor(command="{listen}", persistent=true, wake_delay_ms=0, show_lines=true, description="{record["description"]}")'
        )
    return record


def arm_words(record):
    """How `next` names one arm record: the exact Monitor call when there is
    one, else the facts (its own `listen`, the script, the recorded words,
    the label)."""
    if record.get("monitor"):
        return record["monitor"]
    words = f"sources: {', '.join(record['sources']) or 'all'}"
    if record["filters"]:
        words += f"; filters: {', '.join(record['filters'])}"
    return f"its own listen from {record['script']} with the recorded words ({words}) under description=\"{record['description']}\""


def listener_summary(listeners):
    """The tool row's `└` words (ADR 25011 D22 item 4): each connector's
    listeners as its status reported them, `unreadable` when it could not."""
    parts = []
    for connector, entry in sorted(listeners.items()):
        records = listener_records(entry) if entry.get("listener") != "unreadable" else []
        if not records:
            parts.append(f"{connector}: listener {'unreadable' if entry.get('listener') == 'unreadable' else 'absent'}")
        else:
            parts.append(f"{connector}: " + " · ".join(row_word(name, record) for name, record in records))
    return " · ".join(parts) or "no listener report"


def recent_binding_hint(listeners, binding):
    """#37011 (ADR 23499 D21, ADR 25011 D21): when no mailbox listener is
    live but the connector's `status` says this host bound an id and its
    listener was active within the connector's self-held window
    (`mailbox.recent_binding`), the previous session's relay registration
    may still be live — the relay refuses the first attach until it expires
    (real transport: a clean exit, refused 66 s later, attached at 94 s).
    `start` cannot see the relay; it names the evidence and the window the
    connector's own re-attach covers, so an early `retrying` line is read as
    expected, not as a failed arm. None without the evidence."""
    if not isinstance(binding, dict) or not binding.get("mailbox_id"):
        return None
    mailbox = (listeners or {}).get("mailbox") if isinstance(listeners, dict) else None
    if isinstance(mailbox, dict) and mailbox.get("listener") == "live":
        return None
    try:
        age_s = int(binding.get("last_active_s"))
        window_s = int(binding.get("retry_window_s"))
    except (TypeError, ValueError):
        return None
    return (
        f"mailbox {binding['mailbox_id']} was bound by this host and last active {age_s} s ago; "
        f"the relay may refuse the first attach for up to ~{window_s} s "
        "(the listen retries it by itself; arm it once)"
    )


def steward_start_report(conn, record, connector_id):
    """#31985 (ADR 31985 D1): the connector's standing fleet-steward record,
    judged against the registry AFTER the recovery pass - `live` when its
    conversation's row is still `active`. None when no human armed one:
    nothing here infers a steward into being. The ownership key is the
    record's own `connector` when it names one; else the id of the connector
    whose status carried the record, qualified by the record's `transport`
    the way that connector's `delegate` qualifies it (#37480: no literal)."""
    if not isinstance(record, dict) or not record.get("lane") or not record.get("key"):
        return None
    connector = record.get("connector") if isinstance(record.get("connector"), str) and record.get("connector") else None
    if connector is None:
        connector = f"{connector_id}:{record['transport']}" if record.get("transport") else connector_id
    row = fetch_row(conn, connector, record["key"])
    return {
        "lane": record["lane"],
        "conversation": record["key"],
        "transport": record.get("transport"),
        "armed_at": record.get("armed_at"),
        "live": bool(row is not None and row["state"] == "active"),
    }


def connect_words_of(connector, args):
    """A connect's `(connector id, source words)`. `--transport <t>` is the
    default connector's spelling of `--source` (adr:37480#D3): on any other
    connector it is a usage error naming the rule, so a transport word never
    lands in a second connector's row (#37480 QA round 6 NOTE 7)."""
    connector_id = connector_id_of(connector or DEFAULT_CONNECTOR)
    transports = list(getattr(args, "transport", None) or [])
    if transports and connector_id != DEFAULT_CONNECTOR:
        raise UsageError(
            "usage",
            f"--transport is the {DEFAULT_CONNECTOR} spelling of --source; {connector_id} takes its own --source words",
        )
    if getattr(args, "listen", None) and connector_id == DEFAULT_CONNECTOR:
        raise UsageError(
            "usage",
            f"--listen records a prompt-mounted connector's own listen command; the {DEFAULT_CONNECTOR} Monitor line is the skill body's",
        )
    return connector_id, list(args.source or []) + transports


def last_json_line(stdout):
    """The last stdout line that is a JSON object, as a dict; `{}` when
    none decodes (a child's diagnostics may follow its one JSON line)."""
    for line in reversed(stdout.splitlines()):
        if line.strip().startswith("{"):
            try:
                body = json.loads(line)
            except ValueError:
                return {}
            return body if isinstance(body, dict) else {}
    return {}


def run_connector_reply(script, alias, text):
    """The connector's own `reply --to <alias>` with the text on stdin (the
    one shape every connector's reply takes; a `--text` flag is a
    connector's own extra). Returns `(payload, exit code)`; a script that
    prints no JSON object is `{}`."""
    try:
        proc = subprocess.run(
            [sys.executable or "python3", str(script), "reply", "--to", alias], input=text, capture_output=True,
            text=True, timeout=DECLARATION_TIMEOUT_S, check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return {"outcome": "error", "message": str(error)}, EXIT_EVIDENCE
    return last_json_line(proc.stdout), proc.returncode


def cmd_delegate(args):
    """#37480 QA round 6 D2 (spec 25011 FR-37480-42; adr:37480#D1 rule 1,
    #D2, #D7): the dispatch for a connector whose SKILL ships no `delegate`
    of its own — everything but the Slack connector, whose script's verb is
    unchanged (#D6). One call, the Slack receipt shape: it refuses an alias
    a live coordinator already owns (`already_owned`), recovers a dead
    lane's row and relaunches, records `(connector, alias)` as owned and
    launches the coordinator lane through this helper's own `launch` (the
    generic starter, the recorded `start --lane-backend`), then posts the
    daemon's acknowledgement through the connector's `reply`. The
    conversation key IS the alias the feed line showed: the daemon knows
    nothing else about a conversation it never parsed (D1 rule 1); a
    connector that wants a stable key ships its own `delegate`. The row
    comes before the acknowledgement because a connector can tell the
    conversation is delegated only once the registry says so; a refused
    acknowledgement is named on the line, never hidden."""
    connector = args.connector
    if connector_id_of(connector) == DEFAULT_CONNECTOR:
        raise UsageError(
            "usage",
            f"{DEFAULT_CONNECTOR} ships its own delegate: run its script's `delegate --to {args.to} --text …`",
        )
    text = (args.text or "").strip()
    if not text:
        raise UsageError("usage", "delegate needs --text: the acknowledgement the requester sees")
    request = (args.request or "").strip()
    if not request:
        raise UsageError("usage", "delegate needs --request: the requester's line, verbatim (the coordinator starts from it)")
    alias = args.to
    sender = args.sender or "they"
    event_id = args.event_id or f"{alias}:{hashlib.sha256(request.encode()).hexdigest()[:12]}"
    report = {
        "outcome": None,
        "handoff_id": None,
        "tmux_session": None,
        "backend": None,
        "lane_ref": None,
        "conversation": alias,
        "lane": alias,
        "connector": connector,
        "event_id": event_id,
        "watermark": event_id,
        "ack_message_id": None,
        "muse_session_id": None,
    }

    def finish(outcome, code, **extra):
        report["outcome"] = outcome
        report.update(extra)
        lane_session = report.get("lane_ref") or report.get("tmux_session") or alias
        if outcome in ("launched", "reused"):
            backend_word = f" · {report['backend']}" if report.get("backend") else ""
            report["summary"] = f"lane {lane_session}{backend_word} · handoff {report.get('snapshot_count', 0)} messages"
            report["summary"] += sizing_words(report.get("project"), report.get("sizing"))
        elif outcome == "already_owned":
            report["summary"] = f"lane {lane_session} · already owned"
            report.setdefault("next", "nothing to do: a live coordinator serves this lane; say one line and end the turn")
        else:
            report["summary"] = f"{alias} · {outcome}" + (f" · {report['error']}" if report.get("error") else "")
        return emit(report, code)

    conn = open_registry(args.registry)
    try:
        existing = fetch_row(conn, connector, alias)
    finally:
        conn.close()
    if existing is not None and existing["state"] == "active":
        live = lane_live(existing)
        owner = {
            "handoff_id": existing["handoff_id"], "tmux_session": existing["tmux_session"],
            "backend": row_backend(existing), "lane_ref": row_lane_ref(existing),
        }
        if live is None:
            return finish(
                "owner_unknown", EXIT_EVIDENCE, error="owner_unknown", **owner,
                next=f"report this one line to your human: whether {row_backend(existing)} lane {row_lane_ref(existing)}"
                     " is alive cannot be told; run recover when its server answers; open no lane yourself",
            )
        if live:
            return finish("already_owned", EXIT_OK, **owner)
        # A dead lane: the registry's own per-conversation recover orphans
        # the row, and the dispatch below runs afresh (the relaunch). Its
        # result is read like launch's (review of PR #38451 round 3): a
        # recover that cannot judge leaves the row active, and falling
        # through would tell the daemon a live coordinator owns a
        # conversation it just saw dead.
        recovered = subprocess.run(
            [sys.executable or "python3", os.path.abspath(__file__), "--registry", args.registry, "recover",
             "--connector", connector, "--conversation", alias], capture_output=True, text=True, check=False,
        )
        for line in recovered.stderr.splitlines()[-20:]:
            if line.strip():
                sys.stderr.write(f"recover: {line}\n")
        verdict = last_json_line(recovered.stdout)
        if recovered.returncode != 0 or verdict.get("outcome") not in ("judged", "started"):
            message = verdict.get("message") or verdict.get("reason") or verdict.get("hint")
            return finish(
                "recover_failed", recovered.returncode or EXIT_EVIDENCE,
                error=str(verdict.get("error") or verdict.get("outcome") or "recover_failed"),
                **({"message": message} if message else {}), **owner,
                next=f"the lane {row_lane_ref(existing)} is gone but its row could not be recovered: run recover when"
                     " its evidence answers, then delegate again; open no lane yourself",
            )
    snapshot = [
        {"direction": "inbound", "event_id": event_id, "from": sender, "text": request, "answered": False},
        {"direction": "outbound", "text": text, "sent": True},
    ]
    argv = [
        sys.executable or "python3", os.path.abspath(__file__), "--registry", args.registry, "launch",
        "--connector", connector, "--conversation", alias, "--lane", alias,
        "--event-id", event_id, "--watermark", event_id, "--ack-posted", "yes",
        "--workspace", args.workspace or os.getcwd(), "--connector-script", os.path.abspath(args.connector_script),
        "--snapshot-file", "-",
    ]
    if args.daemon_session_id:
        argv += ["--daemon-session-id", args.daemon_session_id]
    if args.daemon_session_name:
        argv += ["--daemon-session-name", args.daemon_session_name]
    if args.muse_bin:
        argv += ["--muse-bin", args.muse_bin]
    argv += [f"--muse-arg={extra}" for extra in (args.muse_arg or [])]
    if getattr(args, "project", False):
        argv.append("--project")  # #38715 PR 6: the daemon sized this ask as a project
    stdin = "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in snapshot)
    run = subprocess.run(argv, input=stdin, capture_output=True, text=True, check=False)
    for line in run.stderr.splitlines()[-20:]:
        if line.strip():
            sys.stderr.write(f"launch: {line}\n")
    body = last_json_line(run.stdout)
    extra = {key: body.get(key) for key in ("handoff_id", "tmux_session", "backend", "lane_ref")}
    if body.get("handoff_path"):
        extra["handoff_path"] = body["handoff_path"]
    if isinstance(body.get("project"), dict):
        extra["project"] = body["project"]  # FR-38715-61: created, skipped or failed, for the daemon's one line
    if isinstance(body.get("sizing"), dict):
        extra["sizing"] = body["sizing"]  # the tier this hand-off took and why (open gate / recorded delegation)
    if isinstance(body.get("attach"), str) and body["attach"].strip():
        extra["attach"] = body["attach"].strip()  # ruling 28: how a person sits in front of the lane
    if isinstance(body.get("next"), str) and body["next"].strip():
        extra["next"] = body["next"]
    if run.returncode != 0 or body.get("outcome") not in ("launched", "reused"):
        outcome = body.get("outcome") or "failed"
        error = body.get("error") or ("conflict" if outcome == "conflict" else "launch_failed")
        message = body.get("message") or body.get("reason")
        return finish(outcome, run.returncode or EXIT_EVIDENCE, error=error, **({"message": message} if message else {}), **extra)
    extra["snapshot_count"] = len(snapshot)
    # (d) the acknowledgement, through the connector's own reply, now that
    # the registry row lets it through.
    receipt, code = run_connector_reply(args.connector_script, alias, text)
    if code == 0 and receipt.get("outcome") not in (None, "error"):
        extra["ack_message_id"] = receipt.get("message_id") or receipt.get("remote_message_id")
    else:
        extra["ack_error"] = str(receipt.get("outcome") or receipt.get("error") or f"exit {code}")
        extra["next"] = (
            f"the acknowledgement was refused ({extra['ack_error']}): say one line to the requester through the"
            f" connector yourself; then {extra.get('next') or 'end the turn'}"
        )
        # The durable record tells the truth (review of PR #38451): the
        # requester got nothing, so `acknowledgement.posted` is false and
        # the outbound line is not `sent`; the coordinator's handoff never
        # lists it under "already sent". Only the handoff THIS call wrote:
        # a `reused` answer is the first dispatch's handoff, whose
        # acknowledgement did land (review round 4).
        if body.get("outcome") == "launched":
            unpost_acknowledgement(body.get("handoff_path"), extra["ack_error"], text)
        else:
            extra["reack_refused"] = extra["ack_error"]
    return finish(body["outcome"], EXIT_OK, **extra)


def sizing_words(project, sizing):
    """The receipt line's sizing echo: `· project <slug>` (or the refusal the
    daemon must say) when a project was asked, else `· sized thread (...)`
    when the tier was a choice (the `agents` gate open or a recorded
    delegation); nothing on the closed-gate `auto` path. Mirrored by hand in
    `slack_connector.py`'s `delegate` (it runs this helper as a subprocess
    and cannot import it): change both."""
    if isinstance(project, dict):
        if project.get("outcome") == "created":
            return f" · project {project.get('slug')}"
        why = project.get("reason") or project.get("error") or "refused"
        return f" · project {project.get('outcome') or 'refused'} ({why})"
    if isinstance(sizing, dict) and sizing.get("tier") == "thread":
        why = f"agents gate {sizing.get('agents_gate')}"
        if sizing.get("delegation") not in (None, "auto"):
            why += f", delegation {sizing['delegation']}"
        return f" · sized thread ({why})"
    return ""


def unpost_acknowledgement(handoff_path, reason, text):
    """Rewrite a just-written handoff after the connector refused the
    acknowledgement `launch` recorded as sent: `posted` false, the refusal
    named, and ONLY the acknowledgement's own outbound line (matched by its
    text) un-`sent`. Best effort: an unreadable or missing file is left
    alone (the receipt line already names the refusal)."""
    if not handoff_path or not os.path.isfile(handoff_path):
        return
    try:
        with open(handoff_path, encoding="utf-8") as handle:
            handoff = json.load(handle)
        handoff.setdefault("acknowledgement", {})["posted"] = False
        handoff["acknowledgement"]["refused"] = reason
        for event in handoff.get("snapshot") or []:
            if isinstance(event, dict) and event.get("direction") == "outbound" and event.get("text") == text:
                event["sent"] = False
        tmp = f"{handoff_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(handoff, handle, indent=2, sort_keys=True)
        os.replace(tmp, handoff_path)
    except (OSError, ValueError):
        return


def cmd_start(args):
    """#28176: a (re)start is this ONE call, then the arm(s) it calls for — the
    intent record/read of `intent`, each connector's listener liveness, and
    the whole-registry pass of `recover`, folded, so the daemon spends no
    separate call on any of them. Naming a connect (`--connector`, a
    `--source`/`--transport` word, or a `--prompt`) IS the human connect's
    `enabled` record (review of #28195: a second flag to complete it let a
    dropped word record nothing and lose the connect on the next restart); a
    bare `start` is a restart and writes nothing. `intents` always lists
    EVERY connector: the daemon arms each `enabled` one whose listener is
    not `live`, never one that is, and a deliberate `disabled` stays off
    (`#D6`). #37480 (adr:37480#D3/#D4): intent and `listeners` are keyed by
    connector id; every intent row's connector (and the default) is asked
    for its own `status --json`, and an unreadable one is reported as such
    under its own id without touching another's entry."""
    connector_id, sources = connect_words_of(args.connect_connector, args)
    connect = bool(args.connect_connector or sources or args.filter or args.prompt is not None)
    if args.connector_script and not connect:
        raise UsageError(
            "usage",
            "--connector-script records the connector's script on a connect: name the connect with"
            " --connector <id> (and its --source words) or --transport <t>",
        )
    conn = open_registry(args.registry)
    try:
        if connect:
            # Committed before the pass touches tmux or the session list: a
            # human connect stays recorded even when that evidence fails.
            conn.execute("BEGIN IMMEDIATE")
            upsert_intent(
                conn, connector_id, "enabled", utc_now(),
                sources=sources, filters=args.filter, prompt=args.prompt, script=args.connector_script, merge=args.merge,
                listen=args.listen,
            )
            conn.execute("COMMIT")
        # #37181: the daemon-wide lane backend, recorded on the same beat as
        # the intent (a flag or env choice is written; a bare restart reads).
        lane_backend = start_lane_backend(args.lane_backend, args.registry)
        if lane_backend["source"] in ("flag", "env"):
            try:
                write_lane_backend(args.registry, lane_backend["backend"], lane_backend["source"])
            except RegistryUnavailable as error:
                # FM-37181-2 write side: an unrecordable choice loses only its
                # persistence, never the connect; the loss is named on the line.
                lane_backend["unrecorded"] = str(error)
        intents = intent_rows(conn)
        # The default connector is always asked (a bare `/daemon` connect
        # announces the id its cold status names, #30502); every intent
        # row's connector is asked through the script it recorded.
        probe = {DEFAULT_CONNECTOR: None}
        probe.update((row["connector"], row["script"]) for row in intents)
        listeners, evidence, steward_record, binding, known_sources = {}, {}, None, None, {}
        for connector_id, script in sorted(probe.items()):
            entry, reason, steward, recent, known = connector_listeners(connector_id, script)
            listeners[connector_id] = entry
            known_sources[connector_id] = known
            if reason:
                evidence[connector_id] = reason
            if steward_record is None and steward is not None:
                steward_record = (connector_id, steward)
            if binding is None and recent is not None:
                binding = (connector_id, recent)
        # D-META-3: a listener the connector itself reports as ended
        # NON-ZERO after the human's last write is recorded here, so the
        # memory does not depend on the daemon spending the `intent
        # arm-exit` call in a busy turn. A connect newer than the exit keeps
        # the human's fresh try, and an end a human connect already answered
        # (`answered`) is never written back whatever the clocks say
        # (ruling 27: the owner's re-connect did not stick); the same `at`
        # is re-written only to add the connector's reason. A row whose
        # listener RUNS forgets its failure: the fresh try worked.
        recorded_now = False
        for row in intents:
            if row.get("desired") != "enabled":
                continue
            remembered = row.get("last_arm") or {}
            if remembered and not listeners_to_arm(listeners.get(row["connector"]), intent_sources(row)):
                conn.execute("BEGIN IMMEDIATE")
                forget_arm_exit(conn, row["connector"])
                conn.execute("COMMIT")
                recorded_now = True
                continue
            reported = reported_listener_exit(listeners.get(row["connector"]), intent_sources(row))
            if reported is None:
                continue
            code, ended, reason = reported
            raw = conn.execute("SELECT subscriptions FROM connector_intent WHERE connector = ?", (row["connector"],)).fetchone()
            if ended <= row["updated_at"] or ended == answered_end(raw["subscriptions"] if raw else None):
                continue
            if remembered.get("at") == ended and (remembered.get("reason") or not reason):
                continue
            conn.execute("BEGIN IMMEDIATE")
            record_arm_exit(conn, row["connector"], code, ended, reason)
            conn.execute("COMMIT")
            recorded_now = True
        if recorded_now:
            intents = intent_rows(conn)
        payload = {}
        try:
            recover = recover_pass(conn, args)
        except IngressClosed:
            # #28774: the gate closes only the session list, which the pass
            # needs to judge a LIVE lane. The human asked for a connect: the
            # intent is recorded and the listener report is in hand, so the
            # connect goes ahead and the pass waits for a daemon started with
            # the gate on. Every row stays exactly as it was (a verdict without
            # evidence would orphan or unbind live coordinators), and the fix
            # rides FIRST so a truncated tool cell still shows it.
            payload["hint"] = INGRESS_CLOSED_HINT
            recover = {"skipped": "ingress_closed"}
        if "skipped" not in recover:
            describe_recover(recover, with_next=False)  # the verb's shape; the line's one `next` is start's
        # #25011 D30 (FR-25011-41): the Herdr offer read — outside a Herdr
        # pane, once per daemon start, never a gate over the connect; the
        # ask itself rides `next` so the daemon spends no second call on it.
        herdr_offer = herdr_bootstrap_detect(args.registry, args.daemon_session_id)
        delegation = read_delegation(args.registry)  # #38715 PR 6 (FR-38715-60): read, never written here
        agents_gate = "open" if agents_gate_open() else "closed"   # D15: the daemon reads the gate itself, never its catalog
        payload.update(
            {
                "intents": intents,
                "listeners": listeners,
                "active_rows": active_row_count(conn),
                "recover": recover,
                "lane_backend": lane_backend,
                "herdr_offer": herdr_offer,
                "delegation": delegation,
                "agents_gate": agents_gate,
                "context": host_manager_context(),
            }
        )
        if evidence:
            payload["listener_evidence"] = evidence
        # FR-38715-64: a judgment beside the record, never a write - present
        # only when a row it would otherwise arm cannot be honoured. Under
        # `--retry` (the human's restart, ruling 27) a remembered failure is
        # not a verdict but a `retry` entry: the row is armed once more and
        # `next` names what failed before.
        stale, retry, stopped = {}, {}, {}
        for row in arm_order(intents):
            # #38715 QA round 11 D-R11-META-2: `live` is judged per ROW - a live
            # record that covers this row's own words (the same coverage the arm
            # list uses), never any live listener under the connector: two rows
            # on one script let a sibling's listener hide a rejected source.
            live = not listeners_to_arm(listeners.get(row["connector"]), intent_sources(row))
            reason = stale_intent(row, known_sources.get(row["connector"]), live, args.retry) if row.get("desired") == "enabled" else None
            if reason:
                stale[row["connector"]] = {"reason": reason, "next": disable_command(row["connector"])}
                continue
            # r22 SR-DAEMON R-5: a human's `disconnect` after the row's last
            # human write is a stop, not a failure - never re-armed by a
            # restart, `--retry` included, until a human connects it again.
            stamp = human_disconnect(listeners.get(row["connector"]), intent_sources(row), row["updated_at"]) if row.get("desired") == "enabled" and not live else None
            if stamp:
                stopped[row["connector"]] = {"reason": f"stopped: disconnected at {stamp} by a human's `disconnect`",
                                             "next": connect_command(row["connector"])}
            elif args.retry and row.get("desired") == "enabled" and row.get("last_arm") and not live:
                retry[row["connector"]] = row["last_arm"]
        if stale:
            payload["stale"] = stale
        if retry:
            payload["retry"] = retry
        if stopped:
            payload["stopped"] = stopped
        reconnecting = reconnecting_listeners(listeners)
        if reconnecting:
            payload["reconnecting"] = reconnecting
        if binding is not None:
            mailbox_hint = recent_binding_hint(listeners.get(binding[0]), binding[1])
            if mailbox_hint:
                payload["mailbox_hint"] = mailbox_hint
        steward = steward_start_report(conn, steward_record[1], steward_record[0]) if steward_record else None
        if steward is not None:
            payload["steward"] = steward
        ignored = ignored_env(test_seams_enabled())
        if ignored:
            payload["ignored_env"] = ignored
        # ADR 25011 D22 item 4: the tool row's `└` line, each connector's
        # listeners as its own status reported them (#37459).
        payload["summary"] = f"{listener_summary(listeners)} · rows {payload.get('active_rows', 0)} · {recover_summary(recover)}"
        if steward is not None:
            payload["summary"] += f" · steward {'live' if steward['live'] else 'gone'}"
        for connector_id in stale:
            payload["summary"] += f" · stale {connector_id}"
        for connector_id in retry:
            payload["summary"] += f" · retry {connector_id}"
        for connector_id in stopped:
            payload["summary"] += f" · stopped {connector_id}"
        for connector_id in reconnecting:
            payload["summary"] += f" · reconnecting {connector_id}"
        if lane_backend["backend"] != "auto" or lane_backend.get("unrecorded") or lane_backend.get("ignored"):
            tag = lane_backend["source"]
            if lane_backend.get("unrecorded"):
                tag += ", unrecorded"
            if lane_backend.get("ignored"):
                tag += f", {lane_backend['ignored'].removesuffix(LANE_BACKEND_IGNORED_REASON)} ignored"
            payload["summary"] += f" · lane backend {lane_backend['backend']} ({tag})"
        if herdr_offer.get("outcome") == "offer":
            payload["summary"] += f" · herdr offer: {herdr_offer['step']}"
        if delegation["mode"] != "auto":
            payload["summary"] += f" · delegation {delegation['mode']}"
        if agents_gate == "open" or delegation["mode"] == "project":
            payload["summary"] += f" · agents gate {agents_gate}"
        payload["outcome"] = "started"
        to_arm, arms = [], []
        for row in arm_order(intents):
            if row.get("desired") != "enabled" or row["connector"] in stale or row["connector"] in stopped:
                continue
            # `row_sources`, never `sources`: that name is this call's connect
            # words, which the prompt_hint check below still needs (review of
            # PR #39385: the rebind made the hint vanish beside another row).
            row_sources = intent_sources(row)
            words = listeners_to_arm(listeners.get(row["connector"]), row_sources)
            if not words:
                continue
            filters = [f for sub in (row.get("subscriptions") or []) if isinstance(sub, dict) for f in sub.get("filters", [])]
            # The default connector arms one Monitor per named listener; any
            # other connector's `listen` is ONE call, so one record per row.
            names = listener_names_to_arm(words, row_sources) if row["connector"] == DEFAULT_CONNECTOR else [None]
            records = [
                arm_record(row["connector"], row.get("script"), name, row_sources, filters, args.daemon_session_id,
                           listen=row.get("listen"))
                for name in names
            ]
            arms.extend(records)
            # The connector and its absent listeners first (the words a reader
            # skims), then the exact call(s): what `next` prints IS the arm.
            to_arm.append(f"{row['connector']} ({', '.join(words)}): " + "; ".join(arm_words(r) for r in records))
        if arms:
            # One Monitor record per default-connector listener, one facts record per other connector row.
            payload["arm"] = arms
        hint = ("relay the hint first, then " if payload.get("hint") else "")
        stale_words = "".join(
            f"intent {connector_id} is stale ({verdict['reason']}): arm nothing for it; to turn it off: {verdict['next']}; "
            for connector_id, verdict in stale.items()
        ) + "".join(
            f"{connector_id}: {arm_failure_words(last_arm)} - one fresh try now, and say so in your line; "
            for connector_id, last_arm in retry.items()
        ) + "".join(
            f"{connector_id} is stopped ({verdict['reason'][len('stopped: '):]}): arm nothing for it; to start it again: {verdict['next']}; "
            for connector_id, verdict in stopped.items()
        ) + "".join(
            f"{connector_id} is {words} (its listener re-attaches by itself and says one line when it is back): arm nothing for it; "
            for connector_id, words in reconnecting.items()
        )
        # #38715 QA round 11 D-R11-META-1: several arms are ONE checklist for
        # this turn; a listener that exits is recorded and the next arm follows.
        lead = "arm " if len(to_arm) == 1 else (
            f"arm all {len(to_arm)} in this turn - a listener that exits is recorded (`intent arm-exit`)"
            " and the next arm still follows: ")
        payload["next"] = hint + stale_words + (
            f"{lead}{'; '.join(to_arm)}, then say the summary line" if to_arm
            # A stale row was skipped for being stale, not for having a listener:
            # the tail must not give the human a false reason (review of PR #39385).
            else ("arm nothing else; say the summary line" if stale
                  else "arm nothing: no enabled connector is without a listener; say the summary line")
        )
        prompt_word = (args.prompt or "").strip()
        named = set(sources) | set(args.filter or [])
        if connect and args.prompt is not None and (
            prompt_word in named or (prompt_word.isascii() and len(prompt_word.split()) == 1)
        ):
            # #37480 QA round 6 D3 (FR-37480-41(b)): a prompt that is one of
            # the named words, or a single ASCII token, is a paraphrase, not
            # the human's line; the row keeps their words verbatim. Whole
            # CJK lines carry no spaces and are not one word (review of PR
            # #38451). A hint the model reads, never a refusal (D20).
            payload["prompt_hint"] = (
                f"--prompt was one word ({args.prompt!r}): the row keeps the human's connect line verbatim -"
                " next time pass their whole line, quoted"
            )
            payload["next"] = f"{payload['prompt_hint']}; {payload['next']}"
        if herdr_offer.get("outcome") == "offer":
            payload["next"] += f"; then the Herdr offer (once, in the human's language): {herdr_offer['ask']} — {herdr_offer['next']}"
        if steward is not None and not steward["live"]:
            # Owner ruling 2026-09-20 (#38715 QA r9): report-only, like an
            # orphaned conversation row - the human's ask relaunches it, a
            # start never does (the earlier line relaunched lane c80 unasked).
            payload["next"] += f"; steward lane {steward['lane']} gone; say 'restart the fleet steward' to relaunch"
        elif steward is not None:
            # #38175: a text to a live lane is not deliverable from here (delegate answers
            # already_owned); an older lane re-arms its ticker on its human's thread line.
            payload["next"] += (
                f"; the fleet steward lane {steward['lane']} is live: nothing to send (a lane whose transcript predates"
                " the scan ticker re-arms when its human says in the thread: re-read the fleet-steward skill and arm your scan ticker)"
            )
        if herdr_offer.get("reason") == "handed_off_this_start":
            # The last word (FR-25011-41, INV-25011-3): a handed-over daemon
            # arms nothing, a gone steward lane included (review of #38456).
            payload["next"] = herdr_offer["next"]
        return emit(payload)
    finally:
        conn.close()


def herdr_bootstrap_detect(registry, daemon_session_id):
    """`start`'s `herdr_offer` (#25011 D30): the sibling module beside this
    script; a bundle without it, or any failure in the read, is `no_offer`
    and the connect goes ahead (FM-25011-1)."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
        import herdr_bootstrap  # noqa: PLC0415 - sibling script, imported lazily
        return herdr_bootstrap.detect(registry, daemon_session_id)
    except Exception as error:  # noqa: BLE001 - never a lost connect over the offer
        return {"outcome": "no_offer", "reason": "herdr_unreadable", "detail": f"{type(error).__name__}: {error}",
                "next": "the connect goes ahead; say nothing about Herdr"}


def cmd_set(args):
    """#38715 PR 6 (FR-38715-60): `set delegation auto|thread|project` — the
    per-daemon escape hatch over the `agents` gate's project path, recorded
    privately beside the registry and read by `start` and `launch`. An
    explicit choice that cannot be kept is refused on the line (exit 7),
    never applied once and forgotten (FM-38715-63)."""
    if args.setting != "delegation":
        raise UsageError("usage", f"set knows `delegation`, not {args.setting!r}")
    if args.value not in DELEGATION_CHOICES:
        raise UsageError("usage", f"set delegation takes {'|'.join(DELEGATION_CHOICES)}, not {args.value!r}")
    open_registry(args.registry).close()  # the directory the record lives in, created as for every write verb
    write_delegation(args.registry, args.value)
    gate = "open" if agents_gate_open() else "closed"
    words = {
        "auto": f"a goal-shaped ask is a project when you pass --project and `start` said `agents_gate: open` (it is {gate} now); anything else a thread",
        "thread": "every hand-off is a thread; --project is skipped (delegation_thread)",
        "project": f"every hand-off opens a project; the `agents` gate is {gate} and this wins over a closed gate (ADR 38715 D15)",
    }[args.value]
    return emit({
        "outcome": "set",
        "delegation": {"mode": args.value, "source": "recorded"},
        "agents_gate": gate,
        "summary": f"delegation {args.value} · agents gate {gate}",
        "next": f"say one line: delegation is {args.value} - {words}; `start` reports it as `delegation`",
    })


def cmd_intent(args):
    if args.intent_command == "arm-exit":
        if args.exit_code == 0:
            raise UsageError(
                "usage",
                "arm-exit records a NON-ZERO listener exit; a listener that ended with exit 0 or by process"
                " loss is re-armed through `start` (ADR 25011 D21), nothing to record",
            )
        connector_id = connector_id_of(args.connector)
        conn = open_registry(args.registry)
        try:
            now = utc_now()
            conn.execute("BEGIN IMMEDIATE")
            intent = record_arm_exit(conn, connector_id, args.exit_code, now)
            if intent is None:
                conn.execute("ROLLBACK")
                return emit({"error": "intent_unknown",
                             "message": f"no intent row for {connector_id}: nothing was armed from one"}, EXIT_NOT_FOUND)
            conn.execute("COMMIT")
        finally:
            conn.close()
        return emit({
            "intent": intent,
            "summary": f"{connector_id} listener exited {args.exit_code} at {now} · recorded",
            "next": (
                f"say one line: {connector_id} listener exited {args.exit_code} (its `reason` or last stderr line);"
                f" to turn it off: {disable_command(connector_id)}; every later bare `start` lists it stale until a human"
                f" re-connects it ({connect_command(connector_id)}) or the next `/daemon`'s"
                f" `start --retry` gives it one fresh try; then go on with the startup sequence - arm what `start`'s"
                " next still lists (the default connector first) and say the summary line; never a second arm for it now"
            ),
        })
    if args.intent_command == "set":
        if args.desired not in DESIRED:
            raise UsageError("usage", "--desired must be enabled or disabled")
        connector_id, sources = connect_words_of(args.connector, args)
        conn = open_registry(args.registry)
        try:
            now = utc_now()
            conn.execute("BEGIN IMMEDIATE")
            intent = upsert_intent(
                conn, connector_id, args.desired, now,
                sources=sources, filters=args.filter, prompt=args.prompt, script=args.connector_script, merge=args.merge,
                listen=args.listen,
            )
            # A connecting daemon learns on the same beat whether `recover`
            # has lanes to reclaim (#27874): a fresh session cannot tell a
            # cold start from a restart by its intent row alone.
            active_rows = active_row_count(conn)
            conn.execute("COMMIT")
            return emit({"intent": intent, "active_rows": active_rows})
        finally:
            conn.close()
    conn = open_readonly(args.registry)
    if conn is None or not has_table(conn, "connector_intent"):
        return emit({"intents": []})
    try:
        # `--transport` on a read means the default connector's row (the
        # word itself is inside that row, not a key).
        connector = args.connector or (DEFAULT_CONNECTOR if args.transport else None)
        return emit({"intents": intent_rows(conn, connector_id_of(connector) if connector else None)})
    finally:
        conn.close()


# ------------------------------------------------------------------- main ---


def peers_json_arg(value):
    """`--peers-json` takes the path to a JSON file, or `-` for stdin — checked
    at parse time, before any write (#28774: inline JSON was accepted and
    failed later as exit-6 evidence, which a live model read as the gate)."""
    # `exists and not a directory`, not `isfile`: a `<(…)` process substitution
    # is a pipe under /dev/fd and reads fine.
    if value == "-" or (os.path.exists(value) and not os.path.isdir(value)):
        return value
    shown = value if len(value) <= 60 else value[:57] + "..."
    raise argparse.ArgumentTypeError(
        f"takes the path to a JSON file, or - for stdin; {shown!r} is neither (inline JSON is not accepted)"
    )


class NamingParser(argparse.ArgumentParser):
    """argparse's own diagnostic, as this helper's one JSON error line. The
    generic "see --help" it replaced sent a live daemon to `--help` (#27886);
    the flag's name is what the operator needs."""

    def error(self, message):
        raise UsageError("usage", message)


# The one verb roster `--help` prints (the module docstring's table is prose
# for a reader of the source): a forgiving `--help` that answers the one
# question a stray `--help` asks - which verb, which flag - without inviting
# a second call (D27 item 2).
VERB_HELP = {
    "launch": "record ownership, write the handoff file, start the coordinator lane (delegate runs this)",
    "delegate": "the one dispatch call for a connector whose SKILL ships no delegate of its own",
    "set": "a per-daemon setting: `set delegation auto|thread|project`",
    "bind": "record the coordinator's Muse identity on its row (the human repair path)",
    "lookup": "one conversation's row, read-only; --live also judges its lane",
    "list": "every row, read-only; --state filters",
    "mark": "set a row orphaned or retired (retired refuses while the lane lives)",
    "recover": "judge one active row, or every one, against live lane evidence",
    "start": "the daemon's ONE startup call: intent, listener liveness, the recovery pass, and what to arm",
    "intent": "set/get the human's desired connector state (enabled/disabled)",
}


def build_parser():
    parser = NamingParser(
        prog="daemon_registry.py", add_help=True,
        description=__doc__.splitlines()[0]
        + " Every verb takes --help; every answer is one JSON line with `outcome`, `summary` and `next`.",
    )
    parser.add_argument("--registry", default=None, help="registry path (default: MUSE_DAEMON_REGISTRY)")
    sub = parser.add_subparsers(dest="command", parser_class=NamingParser, title="verbs", metavar="<verb>")

    def verb(name):
        # Every verb carries the same one-liner in `--help` and as its own description.
        return sub.add_parser(name, help=VERB_HELP[name], description=VERB_HELP[name])

    def conversation_args(p):
        p.add_argument("--connector", required=True, help="connector identity, e.g. slack-connector:mailbox")
        p.add_argument(
            "--conversation",
            required=True,
            help="the connector lane's stable key (status --json lanes[].key), e.g. the peer mailbox id",
        )

    launch = verb("launch")
    conversation_args(launch)
    launch.add_argument("--lane", default=None, help="the compact lane alias (c3), display and tmux name only")
    launch.add_argument("--conversation-ref", default=None, help="JSON object of transport fields for the coordinator")
    launch.add_argument("--event-id", required=True, help="connector event id of the trigger (the lane's newest inbound line; `delegate` reads it from the feed)")
    launch.add_argument("--watermark", default=None, help="last connector event id in the snapshot")
    launch.add_argument("--ack-posted", required=True, choices=("yes", "no"),
                        help="whether the daemon's acknowledgement was already posted to the requester")
    launch.add_argument("--progress-reply-id", default=None, help="the posted acknowledgement's message id (rides the handoff)")
    launch.add_argument(
        "--daemon-session-id", default=None,
        help="this daemon's Muse session id, recorded for audit when it happens to be known"
             " (nothing addresses the daemon: adr:25011-daemon-session-coordination#D13)",
    )
    launch.add_argument(
        "--daemon-session-name", default=None,
        help="this daemon's Muse session name, display only (sessions are addressed by id, never by name)",
    )
    launch.add_argument("--snapshot-file", default=None, help="conversation lines through the watermark (- = stdin)")
    launch.add_argument("--workspace", required=True, help="the lane's working directory (the coordinator's cwd)")
    launch.add_argument("--tmux-session", default=None, help="the lane's logical name (the tmux session name); the Herdr tab label is this plus `@<daemon namespace>` (#35048)")
    launch.add_argument(
        "--backend", choices=LANE_BACKEND_CHOICES, default=None,
        help="where the lane runs (default: the `start --lane-backend` record, else auto): auto asks the lane"
             " runtime's context — a verified Herdr pane launches in Herdr, anything else in tmux; an unverifiable"
             " Herdr hint is exit 6 herdr_context_unverified",
    )
    launch.add_argument(
        "--muse-bin", default=None,
        help="coordinator binary path (default: MUSE_BIN, then the daemon's invocation, then muse)",
    )
    launch.add_argument("--muse-arg", action="append", default=[], help="one Muse argv token for the coordinator (repeatable; e.g. --muse-arg=--reasoning-effort --muse-arg=high)")
    launch.add_argument("--env", action="append", default=[], help="KEY=VALUE the coordinator must see (repeatable)")
    launch.add_argument(
        "--connector-script", required=True,
        help="the connector script the coordinator listens and replies with; the starter prompt IS those"
             " two commands, so a lane without it could neither hear nor answer",
    )
    launch.add_argument("--note", default=None, help="a bounded diagnostic note on the row (at most 240 characters)")
    launch.add_argument("--dry-run", action="store_true", help="record and build everything; start no tmux session")
    launch.add_argument(
        "--steward", action="store_true",
        help="the coordinator is also this person's standing fleet steward (ADR 31985 D1): the handoff records"
             " `role: fleet-steward` and the starter names the project skill; only the connector's"
             " `delegate --steward` - a human's ask in that conversation - passes it",
    )
    launch.add_argument(
        "--project", action="store_true",
        help="the daemon sized this ask as a project (#38715 PR 6): with the `agents` gate open and `set delegation`"
             " not `thread`, run the agents skill's `init` and make the coordinator that project's coordinator;"
             " otherwise the launch is the ordinary thread and the line's `project` says why (skipped/failed)",
    )

    delegate = verb("delegate")
    delegate.add_argument("--connector", required=True, help="the connector skill id the line arrived on (its Monitor's label)")
    delegate.add_argument("--connector-script", required=True, help="that connector's script (listen/reply); the coordinator's two commands")
    delegate.add_argument("--to", required=True, metavar="LANE", help="the alias on the feed line (c3); it is the conversation key")
    delegate.add_argument("--from", dest="sender", default=None, help="who wrote the line (the feed line's sender)")
    delegate.add_argument("--request", default=None, help="the requester's line, verbatim: what the coordinator starts from")
    delegate.add_argument("--text", required=True, help="your acknowledgement, posted through the connector's reply")
    delegate.add_argument("--event-id", default=None, help="the trigger's id when the connector's feed shows one (default: derived from the alias and the request)")
    delegate.add_argument("--daemon-session-id", default=None, help="as for start: from the session_identity reminder, else omitted")
    delegate.add_argument("--daemon-session-name", default=None, help="as for start, display only")
    delegate.add_argument("--workspace", default=None, help="the coordinator's workspace (default: the current directory, the daemon's own)")
    delegate.add_argument("--muse-bin", default=None, help="coordinator binary path (default: MUSE_BIN, then the daemon's invocation, then muse)")
    delegate.add_argument("--muse-arg", action="append", default=[], help="one Muse argv token for the coordinator (repeatable)")
    delegate.add_argument("--project", action="store_true", help="as launch --project: the daemon sized this ask as a project")

    setting = verb("set")
    setting.add_argument("setting", help="the per-daemon setting: `delegation`")
    setting.add_argument("value", help="delegation: auto (default) | thread | project")

    bind = verb("bind")
    conversation_args(bind)
    bind.add_argument("--muse-session-id", default=None, help="the coordinator's Muse session id (an assertion: unlisted later means gone)")
    bind.add_argument("--muse-session-name", default=None, help="the coordinator's Muse session name, display only")
    bind.add_argument("--peer-address", default=None, help="the coordinator's peer address, recorded for audit")
    bind.add_argument("--daemon-session-id", default=None, help="this daemon's Muse session id, recorded for audit")
    bind.add_argument("--daemon-session-name", default=None, help="this daemon's Muse session name, display only")
    bind.add_argument("--note", default=None, help="a bounded diagnostic note on the row (at most 240 characters)")

    lookup = verb("lookup")
    lookup.add_argument(
        "--live", action="store_true",
        help="also judge the lane's liveness through its recorded backend (`live`: true|false|null); without it no lane probe runs",
    )
    conversation_args(lookup)

    listing = verb("list")
    listing.add_argument("--state", choices=STATES, default=None, help="only rows in this state (default: every row)")

    mark = verb("mark")
    conversation_args(mark)
    mark.add_argument("--state", required=True, help="orphaned (the lane is gone or unproven) or retired (the lane is proven gone; refused lane_live while it lives)")
    mark.add_argument("--note", default=None, help="why, in at most 240 characters (e.g. who asked, when)")

    recover = verb("recover")
    recover.add_argument("--connector", default=None, help="with --conversation: judge that one row (the form delegate runs itself)")
    recover.add_argument("--conversation", default=None, help="with --connector: the conversation's stable key")
    recover.add_argument(
        "--peers-json", default=None, type=peers_json_arg,
        help="the live session list: path to a JSON file, or - for stdin (default: the live"
             " session list the lane runtime reads)",
    )
    recover.add_argument(
        "--daemon-session-id", default=None,
        help="this daemon's current Muse session id, when it happens to be known: given, it is recorded and"
             " lanes started under another id are listed under `readdress`; omitted, no row's daemon"
             " identity is touched (never re-stamped with the previous daemon's id)",
    )
    recover.add_argument("--daemon-session-name", default=None, help="this daemon's current Muse session name, display only")

    def connect_words(p, connector_dest):
        """The connect's words (adr:37480#D3/#D10): the connector id, its
        opaque subscription words, the raw prompt, and the script `status`
        and `listen` run as. No enumeration anywhere: a transport word is
        the connector's own business."""
        p.add_argument(
            "--connector", dest=connector_dest, default=None,
            help=f"the connector skill id (default {DEFAULT_CONNECTOR}); its intent row is keyed by this",
        )
        p.add_argument(
            "--source", action="append", default=[],
            help="a subscription word the connector's own listen takes (repeatable; opaque to this helper)",
        )
        p.add_argument(
            "--transport", dest="transport", action="append", default=[],
            help=f"the {DEFAULT_CONNECTOR} spelling of --source (adr:37480#D3); a usage error on any other connector",
        )
        p.add_argument("--filter", action="append", default=[], help="a filter word for the subscription (repeatable; opaque)")
        p.add_argument(
            "--prompt", default=None,
            help="the human's connect line verbatim, kept beside the resolved words for a human reading intent; with it,"
                 " the named --source/--filter words REPLACE the row's (a different prompt is a reconnect)",
        )
        p.add_argument(
            "--merge", action="store_true",
            help="add the named words to the row instead of replacing them (a prompt that says \"also\"/\"add\")",
        )
        p.add_argument(
            "--connector-script", default=None,
            help="the connector script `start` runs `status --json` with (recorded on the row; default: the sibling"
                 " ../../<connector>/scripts/<connector_with_underscores>.py beside this helper)",
        )
        p.add_argument(
            "--listen", default=None,
            help="the exact `listen` command this connect arms (a prompt-mounted connector only; recorded on the row"
                 " so a restart's `start` prints it verbatim as the Monitor call, never a bare `listen`)",
        )

    start = verb("start")
    connect_words(start, "connect_connector")
    start.add_argument(
        "--peers-json", default=None, type=peers_json_arg,
        help="as for recover: path to a JSON file, or - for stdin",
    )
    start.add_argument("--daemon-session-id", default=None, help="as for recover: from the session_identity reminder, else omitted")
    start.add_argument("--daemon-session-name", default=None, help="as for recover, display only")
    start.add_argument(
        "--lane-backend", choices=LANE_BACKEND_CHOICES, default=None,
        help="where every lane this daemon launches runs, recorded beside the registry (#37181): tmux or herdr"
             " skips the context read; auto (the default) asks it; omitted reads MUSE_DAEMON_LANE_BACKEND, else the record a previous start left",
    )
    start.add_argument(
        "--retry", action="store_true",
        help="the human's (re)start - step 1's `start`: a row whose last arm failed gets ONE fresh try, its earlier"
             " failure named under `retry`; a bare `start` (a recovery, a same-turn re-run) lists such a row stale instead",
    )
    start.set_defaults(connector=None, conversation=None)

    intent = verb("intent")
    intent_sub = intent.add_subparsers(dest="intent_command")
    intent_set = intent_sub.add_parser("set")
    connect_words(intent_set, "connector")
    intent_set.add_argument("--desired", required=True, help="enabled or disabled (disabled is sticky across restarts)")
    intent_get = intent_sub.add_parser("get")
    intent_get.add_argument("--connector", default=None, help="one connector's row (default: every row)")
    intent_get.add_argument("--transport", default=None, help=f"compatibility spelling: the {DEFAULT_CONNECTOR} row")
    intent_arm_exit = intent_sub.add_parser("arm-exit")
    intent_arm_exit.add_argument(
        "--connector", required=True,
        help="the connector whose listener Monitor (armed from its intent row) exited non-zero",
    )
    intent_arm_exit.add_argument(
        "--exit", dest="exit_code", type=int, required=True,
        help="the Monitor's exit code (non-zero); recorded on the row with the time, so every later bare `start`"
             " lists the row stale until a human re-connects the connector or `start --retry` gives it one fresh try",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except UsageError as error:
        return emit({"error": error.code, "message": str(error)}, EXIT_USAGE)
    except SystemExit as error:
        if error.code == 0:
            return 0
        return emit({"error": "usage", "message": "invalid arguments"}, EXIT_USAGE)
    if args.registry is None:
        args.registry = registry_path()
    # Absolute, because every lane's helper starts in its own workspace: a
    # relative `--registry` would split the daemon from its lanes' records.
    args.registry = os.path.abspath(args.registry)
    # The record, the runtime's `--herdr-offer`, `HELPER_ENV_PASS` and the
    # self-spawned children all derive the registry the same way once the
    # resolved value is the environment's too (review of #38758).
    os.environ["MUSE_DAEMON_REGISTRY"] = args.registry
    handlers = {
        "launch": cmd_launch,
        "delegate": cmd_delegate,
        "bind": cmd_bind,
        "lookup": cmd_lookup,
        "list": cmd_list,
        "mark": cmd_mark,
        "recover": cmd_recover,
        "start": cmd_start,
        "intent": cmd_intent,
        "set": cmd_set,
    }
    handler = handlers.get(args.command)
    if handler is None or (args.command == "intent" and args.intent_command not in ("set", "get", "arm-exit")):
        return emit({"error": "usage", "message": "missing or unknown verb"}, EXIT_USAGE)
    if args.command == "recover" and bool(args.connector) != bool(args.conversation):
        return emit({"error": "usage", "message": "recover takes both --connector and --conversation or neither"}, EXIT_USAGE)
    try:
        return handler(args)
    except UsageError as error:
        return emit({"error": error.code, "message": str(error)}, EXIT_USAGE)
    except RegistryNewer as error:
        return emit({"error": "registry_newer_than_supported", "message": str(error)}, EXIT_NEWER)
    except EvidenceUnavailable as error:
        line = {"error": error.code, "message": str(error)}
        # Named on the exit-6 line too (review of #28794): a retry with the
        # override set under a closed gate must not read as the same failure.
        # Only the peer-list path raises this code, so a `tmux_unavailable`
        # from a verb that never reads the list stays free of the seam name.
        if error.code == "peer_evidence_unavailable":
            ignored = ignored_env(test_seams_enabled())
            if ignored:
                line["ignored_env"] = ignored
        return emit(line, EXIT_EVIDENCE)
    except (RegistryUnavailable, sqlite3.Error) as error:
        return emit({"error": "registry_unavailable", "message": str(error)}, EXIT_IO)
    except Exception as error:  # noqa: BLE001 - never a traceback on the daemon's stdout
        return emit({"error": "internal", "message": f"{type(error).__name__}: {error}"}, EXIT_IO)


if __name__ == "__main__":
    sys.exit(main())
