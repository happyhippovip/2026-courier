#!/usr/bin/env python3
"""Slack connector CLI for the Muse Daemon prototype (#23499).

Source-specific connector skill script: owns Slack auth, polling, cursoring,
normalization, deduplication, ACK bookkeeping, reactions, and reply receipts.
The consuming session (the daemon skill) drives it only through these
subcommands; `listen` is the single long-running verb and is designed to run
under the Monitor command source (stdout = one compact line per event).

The surface is six verbs plus the two-layer daemon's (see the D1/D17
decision records): `listen`, `reply`, and `show` are the model's hot path;
`auth`, `status`, and `disconnect` sit off it; `ack` is retired with the
acknowledgement ledger (D18 — audit #38191 C19). Answering a message costs one
call — `reply` addresses a lane alias the listener already printed and is
keyed on the lane's newest inbound line (D18 item 3).

Token resolution (per call, so rotation needs no restart): the
SLACK_CONNECTOR_BOT_TOKEN environment variable, then the token stored by
`auth --token-stdin` in the connector state, then the muse `auth.json`
`providers.slack_connector.bot_token` entry (the product/launcher injection
point). The connector never writes auth.json.

Contract: specs/23499-slack-connector/spec.md. Stdlib only (D4).

Decision cites: a bare `Dn` in this file names the pre-cutover spec-local
ledger (frozen history, redirected under specs/23499-slack-connector/decisions/);
`adr:23499-slack-connector-runtime-contract#Dn` names the current runtime ADR
node.
"""

import argparse
import collections
import fcntl
import glob
import hashlib
import json
import math
import os
import queue
import random
import re
import shlex
import signal
import string
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

PROTOCOL_VERSION = 1
CONNECTOR_ID = "slack"
CONNECTOR_VERSION = "0.2.0"
SCHEMA_VERSION = 1

TOKEN_ENV = "SLACK_CONNECTOR_BOT_TOKEN"
AUTH_JSON_PROVIDER = "slack_connector"

TEXT_BOUND = 4000
FULL_TEXT_BOUND = 64_000
RECENT_MAX = 1000
RETAINED_MAX = 100
THREADS_MAX = 20
RECEIPTS_MAX = 200
ATTEMPTS_MAX = 200
OUTBOUND_MAX = 500
RETRY_AFTER_CAP_S = 60
TRANSCRIPT_WAIT_MS = 10_000  # FR-23499-2 eager wait for Slack's clip transcription
# D10: retained lane aliases. Aliases themselves are never recycled — only the
# oldest routing rows are dropped — so an evicted `c7` stays dead instead of
# silently addressing a different conversation later.
LANES_MAX = 512
# #27816 two-layer daemon (`adr:25011-daemon-session-coordination#D11-D13`):
# claimed conversations, the per-conversation feed fan-out, the delegate snapshot.
LANE_OUTBOUND_MAX = 50  # per-lane ledger of what the connector sent (snapshot source)
FEED_DIR_NAME = "conversations"
FEED_POLL_S_DEFAULT = 0.35  # scoped listener tail interval (D12: 250-500 ms)
# #28433: opt-in hop trace. With SLACK_CONNECTOR_TRACE_HOPS=1 every mailbox
# event carries epoch-ms stamps for each connector hop (CLI read, state lock,
# feed write, persist, print, a coordinator's tail) on its feed line, on the
# printed line and in <state_dir>/hops.jsonl; scripts/hop_report.py reads them.
TRACE_HOPS_ENV = "SLACK_CONNECTOR_TRACE_HOPS"
HOPS_FILE_NAME = "hops.jsonl"
SNAPSHOT_LIMIT_DEFAULT = 20
DAEMON_REGISTRY_HELPER_ENV = "MUSE_DAEMON_REGISTRY_HELPER"
# D15: a claimed conversation nobody tails wakes the daemon again once
# its claim is older than this — long enough for a launched coordinator to arm
# its scoped listener, short enough that a dead one does not deafen the human.
UNATTENDED_GRACE_S_DEFAULT = 60.0
DAEMON_TMUX_ENV = "MUSE_DAEMON_TMUX"  # the daemon registry helper's tmux argv
REGISTRY_HELPER_TIMEOUT_S = 180.0  # `delegate` waits this long for `daemon_registry.py launch`
HTTP_TIMEOUT_S = 10
# The listener's one-shot `register` gets its own, longer bound (owner,
# 2026-09-22: "can we increase the registration timeout to 30seconds"): a
# controller round trip under load outran the 10 s HTTP bound and the arm
# failed fatally; every other one-shot call keeps HTTP_TIMEOUT_S.
MAILBOX_REGISTER_TIMEOUT_S = 30
MAX_HISTORY_PAGES = 10  # bounded catch-up per poll window (FR-021)
DEFAULT_POLL_MS = 1000  # FR-022: near-real-time feed for the Monitor wake path
# INV-6 / FR-017: a same-key send younger than this is treated as in flight
# and refused. 240 s exceeds the nominal worst-case recovery duration — 21
# bounded HTTP calls (1 repost + TWO recovery scans: the floored scan plus the
# skew-bounded fallback, each up to MAX_HISTORY_PAGES pages) x 10 s
# HTTP_TIMEOUT_S = 210 s. That is not a hard bound: the urlopen timeout is per
# socket read, not per request, so a slow-drip response can stretch a call past
# HTTP_TIMEOUT_S. Recovery therefore re-checks this deadline via
# repost_refused() and refuses to repost once its grace has lapsed.
# The re-check bounds the recovery-scan phase only; the single in-flight
# repost after a passed re-check remains the accepted residual FM-6 window
# (DECISIONS D13).
SEND_IN_FLIGHT_GRACE_S = 240
# FM-6 recovery floors its message scan this far before the attempt's start so
# the just-posted reply is reached on the first page(s) of a huge thread; the
# margin absorbs skew between the marker's wall clock and Slack's message ts.
RECOVERY_SCAN_MARGIN_S = 60
# The floored scan is anchored on the LOCAL clock; a host running ahead of Slack
# by more than RECOVERY_SCAN_MARGIN_S would exclude the reply. The fallback scan
# widens the floor to `started_unix - MAX_CLOCK_SKEW_S` so it tolerates a host
# up to this far ahead while STILL skipping a huge thread's much-older replies
# (a full oldest=0 rescan would reopen the >1000-reply double-post).
MAX_CLOCK_SKEW_S = 3600

# Slack error names that make the listener unrecoverable (Monitor terminal).
FATAL_API_ERRORS = {
    "invalid_auth",
    "not_authed",
    "account_inactive",
    "token_revoked",
    "token_expired",
    "missing_scope",
    "channel_not_found",
    "not_in_channel",
}

EXIT_ERROR = 1
EXIT_INPUT = 2
EXIT_NOT_APPLICABLE = 3   # #41802: `progress-sink` on a card — the caller learns it once and stops calling
EXIT_FATAL_LISTEN = 3
# #29361: the streaming child's LAST non-empty stderr line is quoted (repr) in
# the stream-ended diagnostic, cut to this many characters first.
LISTEN_STDERR_TAIL = 200
EXIT_CRASH_AFTER_PERSIST = 86
EXIT_CRASH_AFTER_POST = 87

# ---------------------------------------------------------------------------
# Mailbox transport: the `muse-mailbox` CLI (FR-23499-9 / D21, amended; now
# `adr:23499-slack-connector-runtime-contract#D6`)
# The connector shells out to the `muse-mailbox` CLI instead of talking HTTP to
# the Muse Code Session Mailbox REST API. The CLI owns the transport, the
# cursor, and its own auth, so NO OAuth token is needed on the worker. The
# canonical `peer_message` client envelope is unchanged; only the transport
# moved from urllib to subprocess. The real CLI is a vendor binary that is not
# installable in the offline gate, so the merge gate runs against a stdlib fake
# CLI (crates/plugins/core-skill-tests/slack-connector/fake_muse_mailbox.py);
# where an operator obtains the real CLI is product onboarding, documented
# outside this bundle.
# ---------------------------------------------------------------------------
MAILBOX_CLI_ENV = "SLACK_CONNECTOR_MAILBOX_CLI"
MAILBOX_CLI_STATE_FILE_ENV = "SLACK_CONNECTOR_MAILBOX_STATE_FILE"
MAILBOX_CLI_DEFAULT = "muse-mailbox"
# Explicit test-seam gate for the CLI mailbox transport. Tests point the CLI at the
# stdlib fake and set this to "1" so the bounded-listen / crash-injection seams
# are honored; production never sets it, so a leaked test var cannot alter
# production behavior even when an operator points MAILBOX_CLI at the real CLI
# (FR-020).
MAILBOX_CLI_FAKE_ENV = "SLACK_CONNECTOR_MAILBOX_CLI_FAKE"
CLIENT_ENVELOPE_VERSION = 1
CLIENT_PAYLOAD_MAX_BYTES = 16 * 1024  # outgoing compatibility limit
CLIENT_RECEIVED_PAYLOAD_MAX_BYTES = 16 * 1024 * 1024
DAEMON_SKILL_MAILBOX_TAGS = ("agent", "daemon-skill")
MAILBOX_TAG_ERROR_KEY = "tag_error"
MAILBOX_TAG_PUBLISH_ATTEMPTS = 3
MAILBOX_TAG_RETRY_DELAY_S = 2.0
# Canonical `peer_message` client-envelope body: the message kind and the exact
# policy strings the connector emits and requires on decode.
PEER_MESSAGE_KIND = "peer_message"
PEER_DELIVERY_POLICY = "queue_next_turn"
PEER_WAKE_POLICY = "wake_when_idle"
# `adr:23499-slack-connector-runtime-contract#D20` (#28777): the Session
# Mailbox stack's edit kind and attachment reference scheme, used only when the
# installed `muse-mailbox` proved it has them (capability probe, cached in
# state). The verdict is the whole rule (#30562): no environment switch opts
# in or forces off; a rollback is a CLI without the verb.
MESSAGE_EDIT_KIND = "message_edit"
# #35345 (ADR 35345 D6/D8/D9; spec 23499 FR-35345-1/-2/-6): `reply --message-json`
# posts / updates a Slack Block Kit card through the relay's `custom.slack.ui`
# capability. The lane's `last_outbound.kind` is `ui` for a card (absent for a
# plain message), operation records live under `checkpoint.ui.operations`.
UI_OUTBOUND_KIND = "ui"
# #38715 (ADR 35345 D15): the relay's advertised `custom.slack.ui` versions per mailbox id, learned
# once per listener registration (`list --all`, D2 Amendment 1) and read by `reply` without a probe.
RELAY_UI_VERSIONS_KEY = "relay_ui_versions"
# Ruling 25 (#38715, owner 2026-09-22): the lane's card capability in the
# connector's own words, on every `reply` line, the `delegate` receipt and the
# `status --json` lane row, so the model states the truth and never a guess.
# Derived from the registration probe (`mailbox.relay_ui_versions`) and from
# what a relay's own `disabled` answer taught since (`learn_relay_ui_disabled`).
CARDS_V2 = "yes (version 2: early reply at the tap)"
CARDS_V1 = "yes (version 1)"
CARDS_NONE_MAILBOX = "no — text and files only"
CARDS_NONE_SLACK = "no — text only"
CARDS_UNVERIFIED = "unverified — the relay was not listed at connect; a card goes out as version 1"
# #41245 (ADR 25011 D20 as amended: form-based replies by default, guideline
# over mechanism): the lane's reply SHAPE in one sentence, beside `cards` on
# every `reply` line and on the `delegate` receipt, so the lane that answers
# — and the lane it hands the conversation to — reads it at the point of use.
# Real verbs only; nothing is blocked or throttled.
REPLY_SHAPE_CARDS = ("this lane renders cards: a choice, a status or a plan goes out as `reply --to {lane} --message-json -` "
                     "(Block Kit `{{\"text\", \"blocks\"}}` on stdin); a one-line answer as plain `reply --to {lane}`")
REPLY_SHAPE_NO_CARDS = ("this lane renders no cards: a choice is a numbered list and a status or a plan is short plain text, "
                        "all as plain `reply --to {lane}`")
# The relay's `unavailable · disabled` answer to a post is a capability verdict
# for this identity, not a transient: the `next` names what was learned.
UI_DISABLED_REASON = "disabled"
UI_V2_DISABLED_NEXT = ("version 2 is switched off on this relay for you; send the card again without `behavior` — it goes "
                       "out as version 1 (taps still reach you; the card does not react by itself)")
UI_V1_DISABLED_NEXT = "cards are switched off on this relay; answer in a plain --text reply (a numbered list for a choice)"
UI_RECONCILE_NEXT = ("the relay renders the settled view asynchronously; keep working — a failure reaches you as a "
                     "`[ui]` line in this lane")
UI_RECONCILE_FAILED_NEXT = "the card kept its pressed view; say the outcome in a plain reply"
UI_NEW_CARD_NOTE = ("a card with controls is not edited in place (custom.slack.ui version 2): this view was posted as a "
                    "new card below it, after settling any tap the old card held")
UI_TERMINAL_RETENTION_S = 604800             # the relay's receipt retention: no same-id retry after it
UI_NOW_ENV = "SLACK_CONNECTOR_UI_NOW"        # FR-35345-6: the one UI clock seam (ISO-8601), mailbox seams only
UI_PENDING_NEXT = ("the relay confirms rendering asynchronously; keep working — a click reaches you as a "
                   "`[ui]` line in this lane, a failure as a `[ui]` line too; do not repost")
# #35345 inbound (ADR 35345 D8/D10/D12; spec 23499 FR-35345-3/-4/-6): the relay's
# `capability_result` settles an operation, its `capability_event` is a human's
# click. Both ride the daemon's one mailbox subscription and are correlated
# here; the parameters are FR-35345-6's.
UI_RESULT_ROLE = "capability_result"
UI_EVENT_ROLE = "capability_event"
UI_RESULT_KIND = "ui.result"                 # a surfaced result on the conversation feed
UI_ACTION_KIND = "ui.action"                 # a human interaction on the conversation feed
UI_LINE_KINDS = (UI_RESULT_KIND, UI_ACTION_KIND)
UI_ACTION_RETENTION_S = 86400                # the relay's action redelivery window
UI_UNCERTAIN_NEXT = ("the card may exist; do not repost; clicks are not routed until the relay's "
                     "confirmation is read")
ATTACHMENT_SCHEME = "muse_attachment"
ATTACHMENTS_MAX = 20                       # the CLI's per-message cap
MAILBOX_PROBE_TIMEOUT_S = 15

_test_monotonic_s = 0.0


class ConnectorError(Exception):
    """Operator-visible failure; message must stay secret-free."""


class CapabilityRejected(ConnectorError):
    """The CLI rejected `edit`/`--attach` at reply time (argparse exit 2): the
    cached capability verdict was stale; it is cleared and the caller takes
    the fallback in the same call (D20 item 1)."""


class InputError(ConnectorError):
    pass


class ApiError(ConnectorError):
    def __init__(self, error_name, needed_scope=None):
        detail = f" (needed scope: {needed_scope})" if needed_scope else ""
        super().__init__(f"slack api error: {error_name}{detail}")
        self.error_name = error_name
        self.needed_scope = needed_scope


class TransientError(ConnectorError):
    pass


class RateLimited(ConnectorError):
    def __init__(self, retry_after_s):
        super().__init__(f"rate limited for {retry_after_s}s")
        self.retry_after_s = retry_after_s


def clamp_retry_after(header_value):
    """Bound a 429 Retry-After header at BOTH ends. The header is external,
    untrusted input: a hostile/misbehaving upstream (proxy, CDN, edge) can send
    a negative, NaN, or -inf value that a one-sided min() clamp would pass
    straight into time.sleep(), crashing the long-running listener. Non-numeric
    or HTTP-date headers fall back to the bounded default (FR-018/FM-4)."""
    try:
        value = float(header_value or 1)
    except (TypeError, ValueError):
        return 1.0  # HTTP-date or garbage header: bounded default
    if not math.isfinite(value) or value < 0:
        value = 1.0
    return min(value, RETRY_AFTER_CAP_S)


def diag(message):
    try:
        print(f"slack-connector: {message}", file=sys.stderr, flush=True)
    except OSError:
        # The reader of our stderr is gone (the owning process died, #27885): a
        # diagnostic must never abort the shutdown or the persist it narrates.
        pass


def test_seams_enabled():
    # Slack-transport seams (crash/grace/pending/spool/transcript, the poll
    # bound) are honored ONLY when the Slack API base is redirected to the fake
    # server, so a leaked test variable can never alter production behavior
    # (FR-020). The mailbox fake-CLI flag does NOT arm these — it is scoped to
    # mailbox_seams_enabled() below.
    return bool(os.environ.get("SLACK_CONNECTOR_API_BASE"))


def mailbox_seams_enabled():
    # Mailbox-transport seams (the bounded listen and the mailbox crash window) are
    # honored only under the explicit fake-CLI flag the mailbox test harness sets.
    # It arms mailbox seams ONLY — never the Slack seams above — so a leaked flag
    # cannot alter a Slack production run (FR-020). Pointing MAILBOX_CLI at the
    # real CLI does not arm anything.
    return os.environ.get(MAILBOX_CLI_FAKE_ENV) == "1"


def _monotonic():
    if test_seams_enabled() and os.environ.get("SLACK_CONNECTOR_TEST_DELAY_LOG"):
        return _test_monotonic_s
    return time.monotonic()


def _sleep(delay_s):
    if test_seams_enabled() and os.environ.get("SLACK_CONNECTOR_TEST_DELAY_LOG"):
        global _test_monotonic_s
        with open(os.environ["SLACK_CONNECTOR_TEST_DELAY_LOG"], "a", encoding="utf-8") as handle:
            handle.write(json.dumps(delay_s) + "\n")
        _test_monotonic_s += delay_s
        return
    time.sleep(delay_s)


_test_transcript_now = 0.0


def transcript_now():
    if test_seams_enabled() and os.environ.get("SLACK_CONNECTOR_TEST_VIRTUAL_TRANSCRIPT_CLOCK"):
        return _test_transcript_now
    return _monotonic()


def transcript_pause(seconds):
    global _test_transcript_now
    if test_seams_enabled() and os.environ.get("SLACK_CONNECTOR_TEST_VIRTUAL_TRANSCRIPT_CLOCK"):
        _test_transcript_now += seconds
    else:
        _sleep(seconds)


RECEIPT_EMOJIS = ("thumbsup", "eyes", "raised_hands", "fire", "brain")


def receipt_react(envelope, token):
    """FR-23499-8: mechanical receipt on admission — a random emoji from the
    fixed pool, fired by the listener itself so no model sits in the receipt
    path. Best-effort: any failure is a diagnostic, never a listen failure,
    and never touches cursor/pending state. Replayed events are not
    re-reacted (this is called only on fresh admission). Returns False on a
    429 or a network-class transient failure — batch-wide conditions where
    the caller drops the rest of the batch's receipts (never sleeps here;
    Retry-After belongs to the poll ladder). A per-message ApiError returns
    True and the batch continues."""
    channel, ts = parse_event_id(envelope["event_id"])
    emoji = random.choice(RECEIPT_EMOJIS)
    try:
        slack_call(
            "reactions.add",
            token,
            json_body={"channel": channel, "timestamp": ts, "name": emoji},
        )
    except RateLimited as limited:
        diag(
            f"receipt reaction rate limited (Retry-After {limited.retry_after_s}s); "
            "dropping this batch's remaining receipts"
        )
        return False
    except TransientError as error:
        # Network-class failure: batch-wide, unlike a per-message ApiError.
        # Continuing would stall the listener HTTP_TIMEOUT_S per remaining
        # receipt on a black-holed network; receipts are blessed-lossy.
        diag(f"receipt reaction failed ({error}); dropping this batch's remaining receipts")
        return False
    except ApiError as error:
        if error.error_name != "already_reacted":
            diag(f"receipt reaction failed ({error.error_name}); continuing")
    except Exception as error:
        diag(f"receipt reaction failed ({error.__class__.__name__}); continuing")
    return True


def crash_if(window, seams_enabled):
    # `seams_enabled` is the caller's OWN transport seam so a leaked flag from one
    # transport can never inject a crash into the other's production path: the mailbox
    # emit passes mailbox_seams_enabled(), every Slack path passes test_seams_enabled().
    # A single OR here would let SLACK_CONNECTOR_MAILBOX_CLI_FAKE=1 hard-exit a real
    # chat.postMessage between the post and the receipt write (duplicate Slack post).
    if seams_enabled and os.environ.get("SLACK_CONNECTOR_TEST_CRASH") == window:
        os._exit(EXIT_CRASH_AFTER_PERSIST if window == "after_persist" else EXIT_CRASH_AFTER_POST)


def repost_refused(monotonic_elapsed, wall_elapsed, grace):
    """True when an FM-6 recovery has outlived its grace on either clock.

    Past that point the marker this process armed no longer protects the key:
    a concurrent same-key retry may legally have re-armed it and be
    mid-recovery itself, so reposting here could double-post (INV-6). Rivals
    are admitted on wall-clock marker age while monotonic keeps ticking
    through wall-clock steps, so each clock catches what the other misses
    (suspend freezes monotonic; NTP can rewind wall). The caller must refuse
    the repost, leave the marker armed, and let a later retry recover.
    """
    return monotonic_elapsed >= grace or wall_elapsed >= grace


def transcript_wait_ms():
    if test_seams_enabled() and os.environ.get("SLACK_CONNECTOR_TRANSCRIPT_WAIT_MS"):
        return int(os.environ["SLACK_CONNECTOR_TRANSCRIPT_WAIT_MS"])
    return TRANSCRIPT_WAIT_MS


def send_grace_s():
    if test_seams_enabled() and os.environ.get("SLACK_CONNECTOR_SEND_GRACE_S"):
        return float(os.environ["SLACK_CONNECTOR_SEND_GRACE_S"])
    return SEND_IN_FLIGHT_GRACE_S


def api_base():
    return os.environ.get("SLACK_CONNECTOR_API_BASE", "https://slack.com/api").rstrip("/")


def state_dir():
    configured = os.environ.get("SLACK_CONNECTOR_STATE_DIR")
    if configured:
        return configured
    xdg = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(xdg, "muse", "connectors", "slack")


def muse_auth_json_path():
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(xdg, "muse", "auth.json")


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now_precise():
    """`utc_now()` to the microsecond: a claim's grace is measured from this
    stamp, and a whole-second one gave it up to a second less (#28181 review)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def now_ms():
    return int(time.time() * 1000)


def trace_hops_enabled():
    """#28433: the hop trace is an operator diagnostic, never on by default —
    the default line and feed line stay byte-identical (INV-2)."""
    return os.environ.get(TRACE_HOPS_ENV) == "1"


def hops_path():
    return os.path.join(state_dir(), HOPS_FILE_NAME)


def record_hops(record):
    """Append one hop record (one O_APPEND write under a flock, like a feed
    line) to the private hops ledger. Trace-only; never raises into the
    listener — a diagnostic must not stop the stream."""
    if not trace_hops_enabled():
        return
    try:
        data = (json.dumps(record, separators=(",", ":")) + "\n").encode("utf-8")
        os.makedirs(state_dir(), mode=0o700, exist_ok=True)
        fd = os.open(hops_path(), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            os.write(fd, data)
        finally:
            os.close(fd)
    except OSError as error:
        diag(f"hop trace write failed: {error}")


def hops_suffix(hops):
    """The per-line hop summary: ` [hops cli=<ms> admit=<ms> [tail=<ms>] print=<ms> at=<printed_at_ms>]`.
    cli = server accept -> CLI line read; admit = read -> feed line written
    (lock wait + state load + feed append); tail = feed -> a coordinator's
    tail read; print = the last of those -> this print (the daemon's includes
    the state persist). Each delta is omitted when its stamps are missing."""
    def delta(later, earlier):
        if hops.get(later) is None or hops.get(earlier) is None:
            return None
        return int(hops[later]) - int(hops[earlier])

    parts = []
    cli = delta("read_at_ms", "accepted_at_ms")
    if cli is not None:
        parts.append(f"cli={cli}ms")
    admit = delta("feed_written_at_ms", "read_at_ms")
    if admit is not None:
        parts.append(f"admit={admit}ms")
    if hops.get("tail_read_at_ms") is not None:
        tail = delta("tail_read_at_ms", "feed_written_at_ms")
        if tail is not None:
            parts.append(f"tail={tail}ms")
        printed = delta("printed_at_ms", "tail_read_at_ms")
    else:
        printed = delta("printed_at_ms", "feed_written_at_ms")
    if printed is not None:
        parts.append(f"print={printed}ms")
    parts.append(f"at={hops.get('printed_at_ms')}")
    return " [hops " + " ".join(parts) + "]"


def validate_token_text(token, source):
    if not token:
        raise ConnectorError(f"empty token from {source}")
    if not all(0x21 <= ord(ch) <= 0x7E for ch in token):
        # An interior control char would make header construction raise with
        # the full value embedded in the exception (INV-3); reject up front.
        raise ConnectorError(
            f"token from {source} contains whitespace or non-printable characters; refusing to use it"
        )
    return token


def resolve_token(state):
    """Token source order: env injection, manual state, muse auth.json."""
    env_token = os.environ.get(TOKEN_ENV)
    if env_token:
        return validate_token_text(env_token.strip(), "environment"), "env"
    stored = ((state or {}).get("connector") or {}).get("auth") or {}
    if stored.get("bot_token"):
        return stored["bot_token"], "state"
    try:
        with open(muse_auth_json_path(), "r", encoding="utf-8") as handle:
            auth_doc = json.load(handle)
        entry = (auth_doc.get("providers") or {}).get(AUTH_JSON_PROVIDER) or {}
        config_token = entry.get("bot_token")
    except (OSError, ValueError):
        config_token = None
    if config_token:
        return validate_token_text(str(config_token).strip(), "auth.json"), "config"
    raise ConnectorError(
        f"no bot token available: set {TOKEN_ENV}, run `auth --token-stdin`, or add "
        f"providers.{AUTH_JSON_PROVIDER}.bot_token to muse auth.json"
    )


# ---------------------------------------------------------------------------
# State store: one JSON file, flock, temp + fsync + atomic rename (FR-005/006)
# ---------------------------------------------------------------------------


class StateStore:
    def __init__(self):
        self.dir = state_dir()
        self.path = os.path.join(self.dir, "state.json")
        self._lock_file = None

    def _ensure_dir(self):
        os.makedirs(self.dir, mode=0o700, exist_ok=True)
        os.chmod(self.dir, 0o700)

    def __enter__(self):
        self._ensure_dir()
        self._lock_file = open(os.path.join(self.dir, ".state.lock"), "w")
        fcntl.flock(self._lock_file, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self._lock_file, fcntl.LOCK_UN)
        self._lock_file.close()
        self._lock_file = None

    def load(self, require=False):
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = handle.read()
        except FileNotFoundError:
            if require:
                raise ConnectorError("no connector state: run `auth` first")
            return None
        try:
            state = json.loads(raw)
        except ValueError:
            raise ConnectorError("state file is malformed; failing closed (FR-006)")
        version = state.get("schema_version")
        # `type(version) is not int` before the equality: Python coerces
        # True == 1 and 1.0 == 1 (bool is an int subclass), so a wrong-typed
        # schema_version (JSON true or 1.0) would otherwise slip through the
        # gate and be silently read + rewritten as v1 (FR-006 fail-closed).
        if type(version) is not int or version != SCHEMA_VERSION:
            raise ConnectorError(
                f"state schema_version {version!r} is not supported (expected {SCHEMA_VERSION}); failing closed"
            )
        return state

    def save(self, state):
        self._ensure_dir()
        fd, tmp_path = tempfile.mkstemp(prefix=".state-", dir=self.dir)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state, handle, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self.path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


def fresh_checkpoint(cursor):
    return {
        "cursor": cursor,
        "recent_event_ids": [],
        "retained_events": {},
        "tracked_threads": {},
        "reply_receipts": {},
        "send_attempts": {},
        # D10 lane aliases: alias -> {key, route, last_seen, last_outbound}.
        # `lane_seq` only counts up so an alias is never reused.
        "lanes": {},
        "lane_seq": 0,
        "outbound_ts": [],
        "last_poll_at": None,
        # #27816: conversation claims (transport -> key -> claim). D20 keeps no
        # ledger of answered messages: the feed and the outbound ledger are the
        # whole record, and liveness (the claim, the lock) drives recovery.
        "claims": {},
    }


# ---------------------------------------------------------------------------
# Slack Web API (urllib only)
# ---------------------------------------------------------------------------


def slack_call(method, token, params=None, json_body=None):
    url = f"{api_base()}/{method}"
    headers = {"Authorization": f"Bearer {token}"}
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    else:
        data = urllib.parse.urlencode(params or {}).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as response:
            payload = json.loads(response.read().decode("utf-8"))
            response_headers = response.headers  # case-insensitive mapping
    except urllib.error.HTTPError as error:
        if error.code == 429:
            raise RateLimited(clamp_retry_after(error.headers.get("Retry-After")))
        if 500 <= error.code < 600:
            raise TransientError(f"slack http {error.code}")
        raise ConnectorError(f"slack http {error.code}")
    except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
        raise TransientError(f"network failure: {getattr(error, 'reason', error.__class__.__name__)}")
    if not payload.get("ok"):
        raise ApiError(payload.get("error", "unknown_error"), payload.get("needed"))
    return payload, response_headers


def fetch_messages(method, token, params):
    """Fetch one bounded window with cursor pagination (FR-021)."""
    messages = []
    page_cursor = None
    for _ in range(MAX_HISTORY_PAGES):
        call_params = dict(params)
        if page_cursor:
            call_params["cursor"] = page_cursor
        payload, _ = slack_call(method, token, call_params)
        messages.extend(payload.get("messages") or [])
        page_cursor = (payload.get("response_metadata") or {}).get("next_cursor")
        if not payload.get("has_more") or not page_cursor:
            return messages
    diag(f"{method}: catch-up exceeded {MAX_HISTORY_PAGES} pages; advancing past the unfetched remainder")
    return messages


def message_is_in_thread(message):
    """One shared predicate for "this row is a thread reply" — admission
    scope, envelope thread_id, and replay scope must never disagree."""
    thread_ts = message.get("thread_ts")
    return bool(thread_ts) and thread_ts != message["ts"]


def attachment_kind(mime):
    prefix = (mime or "").split("/")[0]
    return prefix if prefix in ("image", "audio", "video") else "file"


def attachment_from_file(file_object):
    """FR-23499-1: bounded, secret-free attachment metadata for the envelope.
    Metadata only, never url_private: the model reads what the attachment IS
    (kind, name, size, a clip's transcript) and never downloads its bytes."""
    meta = {
        "file_id": file_object.get("id"),
        "kind": attachment_kind(file_object.get("mimetype")),
        "mime": file_object.get("mimetype"),
        "name": file_object.get("name"),
        "size": file_object.get("size"),
    }
    transcription = file_object.get("transcription")
    if transcription is not None or file_object.get("subtype") == "slack_audio":
        # `transcription` is an external Slack field: the `or {}` idiom only
        # coerces FALSY values, so a truthy non-dict (Slack sending the string
        # "processing", a list, or a number) would raise on .get() and crash
        # the poll loop, wedging the channel. Coerce to dict at this owning
        # boundary so any malformed shape degrades to "unavailable" (FR-23499-1).
        tdict = transcription if isinstance(transcription, dict) else {}
        status = tdict.get("status")
        if status == "complete":
            meta["transcript_status"] = "complete"
            preview = tdict.get("preview")
            meta["transcript"] = preview.get("content") if isinstance(preview, dict) else None
        elif status == "processing":
            meta["transcript_status"] = "pending"
        else:
            # Live Slack's third state: {"status": "none"} (or no
            # transcription object at all on a clip) means Slack will never
            # transcribe this file. Final, not retryable — the listener must
            # not spend its wait budget on it (FR-23499-2).
            meta["transcript_status"] = "unavailable"
    return meta


def enrich_attachments(message, token, deadline):
    """FR-23499-1/2: build attachment metadata during the poll (network phase,
    never under the lock). Audio clips wait for Slack's own transcription
    only until the poll's SHARED deadline: one wait budget per poll cycle, so
    N slow clips never stall a batch N x the wait (FR-23499-2); late clips
    emit with transcript_status "pending"."""
    files = message.get("files")
    if not files or message.get("bot_id") or not message.get("user"):
        return
    metas = [attachment_from_file(f) for f in files]
    for index, file_object in enumerate(files):
        needs_wait = (
            metas[index].get("transcript_status") == "pending"
            and file_object.get("subtype") == "slack_audio"
        )
        while needs_wait and transcript_now() < deadline:
            transcript_pause(0.2)
            try:
                payload, _ = slack_call("files.info", token, {"file": file_object.get("id")})
            except ConnectorError:
                break
            refreshed = attachment_from_file(dict(payload.get("file") or {}, subtype="slack_audio"))
            if refreshed.get("transcript_status") in ("complete", "unavailable"):
                # complete adopts the transcript; unavailable is final — stop
                # spending the shared budget on a clip Slack will never do.
                metas[index] = dict(refreshed, file_id=metas[index]["file_id"])
                needs_wait = False
    message["_attachments"] = metas


def parse_event_id(event_id):
    parts = (event_id or "").split(":")
    if len(parts) != 3 or parts[0] != CONNECTOR_ID or not parts[1] or not parts[2]:
        raise InputError(f"event_id must look like slack:<channel>:<ts>, got {event_id!r}")
    return parts[1], parts[2]


# ---------------------------------------------------------------------------
# Envelope construction (FR-011..015)
# ---------------------------------------------------------------------------


def occurred_at_from_ts(ts):
    seconds = int(float(ts))
    return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_envelope(message, binding, container_type):
    container_id = binding["container_id"]
    ts = message["ts"]
    thread_id = message.get("thread_ts") if message_is_in_thread(message) else None
    # The "" default only guards a MISSING key; a present-but-null text (an
    # everyday no-caption file_share, subtype file_share) is JSON null → None,
    # and None[:N] would raise TypeError under the lock before the cursor
    # advances, wedging the channel. `or ""` matches the mailbox idiom below.
    # #30674: both arms defuse at admission — a Slack user's text is the same
    # trust boundary and the daemon's reader keys on the line shape alone.
    full_text = defuse_peer_text(message.get("text") or "")[:FULL_TEXT_BOUND]
    truncated = len(full_text) > TEXT_BOUND
    user = message.get("user")
    if thread_id:
        reply_target = {"type": "thread", "id": f"{container_id}:{thread_id}"}
    else:
        reply_target = {"type": "message", "id": f"{container_id}:{ts}"}
    envelope = {
        "protocol_version": PROTOCOL_VERSION,
        "event_id": f"slack:{container_id}:{ts}",
        "source": CONNECTOR_ID,
        "binding_id": binding["id"],
        "kind": "message.created",
        "actor": {
            "id": user,
            "display": message.get("username") or user,
            "is_owner": user == binding["owner_user_id"],
            "is_bot": bool(message.get("bot_id")),
        },
        "container": {"type": container_type, "id": container_id, "thread_id": thread_id},
        "content": {"text": full_text[:TEXT_BOUND], "truncated": truncated},
        "reply_target": reply_target,
        "attachments": message.get("_attachments") or [],
        "occurred_at": occurred_at_from_ts(ts),
    }
    return envelope, full_text


def bound_fifo(items, cap):
    return items[-cap:] if len(items) > cap else items


def evict_bounded(checkpoint):
    checkpoint["recent_event_ids"] = bound_fifo(checkpoint["recent_event_ids"], RECENT_MAX)
    checkpoint["outbound_ts"] = bound_fifo(checkpoint["outbound_ts"], OUTBOUND_MAX)
    if len(checkpoint["send_attempts"]) > ATTEMPTS_MAX:
        for key in list(checkpoint["send_attempts"])[: len(checkpoint["send_attempts"]) - ATTEMPTS_MAX]:
            del checkpoint["send_attempts"][key]
    if len(checkpoint["reply_receipts"]) > RECEIPTS_MAX:
        for key in list(checkpoint["reply_receipts"])[: len(checkpoint["reply_receipts"]) - RECEIPTS_MAX]:
            del checkpoint["reply_receipts"][key]
    for lane in (checkpoint.get("lanes") or {}).values():
        if len(lane.get("outbound") or []) > LANE_OUTBOUND_MAX:
            lane["outbound"] = bound_fifo(lane["outbound"], LANE_OUTBOUND_MAX)
    retained = checkpoint["retained_events"]
    if len(retained) > RETAINED_MAX:
        # Oldest first (insertion order): D20 keeps no pending set, so nothing
        # pins a retained event; the feed is the durable record.
        for key in list(retained)[: len(retained) - RETAINED_MAX]:
            del retained[key]
    threads = checkpoint["tracked_threads"]
    if len(threads) > THREADS_MAX:
        by_activity = sorted(threads.items(), key=lambda item: float(item[1].get("last_active") or 0))
        for key, _ in by_activity[: len(threads) - THREADS_MAX]:
            del threads[key]
    lanes = checkpoint.setdefault("lanes", {})
    if len(lanes) > LANES_MAX:
        # A claimed conversation is a coordinator's; its lane must outlive the cap.
        live = {c.get("lane") for per in (checkpoint.get("claims") or {}).values() for c in per.values()}
        by_age = sorted(lanes.items(), key=lambda item: item[1].get("last_seen") or "")
        for alias, lane in by_age[: len(lanes) - LANES_MAX]:
            if alias not in live:
                # The lane's feed (and its D15 lock) go with it: an orphaned
                # feed would grow the state dir without bound and replay lines
                # stamped with a dead alias when the conversation returns.
                transport = (lane.get("route") or {}).get("transport")
                for path in (feed_path(transport, lane.get("key")), conversation_lock_path(transport, lane.get("key"))):
                    try:
                        os.unlink(path)
                    except FileNotFoundError:
                        pass
                del lanes[alias]


# ---------------------------------------------------------------------------
# Lane aliases (D10) and the compact listener line (D11)
# ---------------------------------------------------------------------------


def lane_key_for(envelope):
    """This envelope's conversation identity: the reply target on Slack, the
    container on mailbox. One alias table over both is what lets the daemon
    address a conversation without knowing which transport it arrived on."""
    reply_target = envelope.get("reply_target") or {}
    if reply_target.get("type") == "mailbox":
        return (envelope.get("container") or {}).get("id")
    return reply_target.get("id")


def lane_route_for(envelope):
    """Everything `reply` needs to address this lane, frozen at admission. The
    model never carries a reply target between calls — that round-trip of
    connector state through the model is the ceremony D10 deletes."""
    reply_target = envelope.get("reply_target") or {}
    if reply_target.get("type") == "mailbox":
        return {
            "transport": "mailbox",
            "target_client_mailbox_id": reply_target.get("target_client_mailbox_id"),
            "conversation_id": reply_target.get("conversation_id"),
        }
    container_id, _, ref = str(reply_target.get("id") or "").partition(":")
    # A `thread` target refs the thread root; a top-level `message` target refs
    # its own ts, and replying to it opens that message's thread. Both are the
    # same `thread_ts` argument to chat.postMessage.
    return {"transport": "slack", "container_id": container_id, "thread_ts": ref or None}


def assign_lane(checkpoint, envelope):
    """Stamp `envelope["lane"]` with this conversation's stable alias, minting
    one on first sight. Returns the alias, or None when the envelope carries no
    resolvable key (in which case the event still emits, just without a lane)."""
    key = lane_key_for(envelope)
    if not key:
        return None
    route = lane_route_for(envelope)
    lanes = checkpoint.setdefault("lanes", {})
    for alias, lane in lanes.items():
        # Both transports share one alias table, and a mailbox peer picks its
        # own `conversation_id` — so the key alone is not an identity. Matching
        # transport too is what stops a mailbox envelope whose id happens to
        # equal a Slack lane's `<channel>:<ts>` from seizing that lane and
        # rerouting the human's reply. Event ids are namespaced by transport
        # for the same reason.
        if lane.get("key") == key and (lane.get("route") or {}).get("transport") == route["transport"]:
            lane["last_seen"] = utc_now()
            lane["route"] = route
            note_relay_facts(lane, envelope)
            note_relay_history(lane, envelope)
            if relay_originated(envelope):
                # D20 item 2: a LANE fact (the route is rebuilt per admission),
                # set by any message that carried the relay's `context` block
                # or its conversation-token prefix (#31078), never cleared; a
                # lane from before this node earns it on its next relay
                # message and takes the successor until then.
                lane["relay"] = True
            envelope["lane"] = alias
            return alias
    checkpoint["lane_seq"] = int(checkpoint.get("lane_seq") or 0) + 1
    alias = f"c{checkpoint['lane_seq']}"
    lanes[alias] = {
        "key": key,
        "route": route,
        "last_seen": utc_now(),
        "last_outbound": None,
    }
    note_relay_facts(lanes[alias], envelope)
    note_relay_history(lanes[alias], envelope)
    if relay_originated(envelope):
        lanes[alias]["relay"] = True
    envelope["lane"] = alias
    return alias


def note_relay_facts(lane, envelope):
    """#30542: the lane remembers the `requester` and `thread` facts its events
    carried (`relay_facts`), so `status --json` can name the person and the
    thread off the hot path and `delegate` can hand them to the launch. A
    later block adds to the `requester` only when both sides carry the same
    id (an id-only delta whose window holds only other people's posts must
    not forget the name); a different id, or no id on either side to compare,
    replaces — two people never merge into one (review of #30549). The
    `thread` is taken whole
    from the newest block that carries one, so `ref` always agrees with its
    parts. An event without a block changes nothing
    the lane learned — and, so that one person on one lane has one name on
    every surface (the compact line, the feed and snapshot `from`, the reply
    summary, the native cell), the remembered display name becomes the
    event's `actor.display` when the event itself names none."""
    relay = envelope.get("relay") if isinstance(envelope.get("relay"), dict) else {}
    for fact in ("requester", "thread"):
        new = relay.get(fact)
        if not (isinstance(new, dict) and new):
            continue
        old = lane.get(fact) if isinstance(lane.get(fact), dict) else {}
        # Same person only when BOTH sides carry the same id (round 3 of the
        # review): a name-only block and an id-only one are different people
        # until an id says otherwise, so they replace rather than merge.
        same = old.get("id") is not None and old.get("id") == new.get("id")
        lane[fact] = dict(old, **new) if fact == "requester" and same else dict(new)
    remembered = (lane.get("requester") or {}).get("display_name") if isinstance(lane.get("requester"), dict) else None
    named = (relay.get("requester") or {}).get("display_name") if isinstance(relay.get("requester"), dict) else None
    if remembered and not named and isinstance(envelope.get("actor"), dict):
        envelope["actor"]["display"] = remembered


def history_mark(text):
    """One post's identity in the seen set: a digest of its bounded text, never
    the text. Text alone, not text plus author: the SAME post reaches the lane
    both ways — as a routed `peer_message` (whose sender is the relay mailbox or
    the requester's display name) and, later, as an entry in someone else's
    window (whose author is whatever the relay's block calls them) — and the
    two namings need not agree. The cost is that a bare "+1" from a second
    person is not shown twice as context; the gain is that an ask the
    coordinator already answered never comes back as background."""
    bounded = bounded_fact(text)
    return hashlib.sha256(bounded.encode("utf-8")).hexdigest()[:16] if bounded else None


def note_relay_history(lane, envelope):
    """Drop the posts this lane has already been shown, and remember this
    message's own text so a later window does not replay it either. The relay's
    window slides — two tagged asks a minute apart carry most of the same posts,
    and the older ask is itself one of them — so without this the monitored
    channel would repeat the conversation under every message, and an ask the
    coordinator answered would come back as room context. The lane keeps a
    bounded FIFO of digests; an envelope whose whole window is already seen
    carries no history at all. Runs under the state lock, from `assign_lane`,
    before the envelope is retained, fed and emitted."""
    if not relay_originated(envelope):
        return  # only the relay's own messages carry (or come back as) a window
    seen = lane.get("relay_history_seen")
    seen = [mark for mark in seen if isinstance(mark, str)] if isinstance(seen, list) else []
    known = set(seen)
    minted = []
    routed = history_mark((envelope.get("content") or {}).get("text") or "")
    if routed and routed not in known:
        known.add(routed)
        minted.append(routed)
    history = envelope.get("relay_history")
    if isinstance(history, list) and history:
        fresh = []
        for entry in history:
            digest = history_mark(entry.get("text") or "")
            if digest is None or digest in known:
                continue
            known.add(digest)
            fresh.append(entry)
            minted.append(digest)
        if fresh:
            envelope["relay_history"] = fresh
        else:
            del envelope["relay_history"]
    if minted:
        lane["relay_history_seen"] = bound_fifo(seen + minted, RELAY_HISTORY_SEEN_MAX)


def relay_originated(envelope):
    """D20 item 2: the Muse Tag relay is the one peer that understands
    `message_edit`; it shows itself by the `context` block on its messages
    (D19 item 5) or by its conversation-token prefix as the conversation id
    (#31078), which the decoder marks on the reply target."""
    return bool((envelope.get("reply_target") or {}).get("relay"))


# ---------------------------------------------------------------------------
# Two-layer daemon (#27816, `adr:25011-daemon-session-coordination#D11-D13`):
# per-conversation feeds, claims and the handed-off ledger
# ---------------------------------------------------------------------------


def feed_dir():
    return os.path.join(state_dir(), FEED_DIR_NAME)


def feed_path(transport, key):
    """One append-only JSONL feed per conversation. The name carries a readable
    slug of the key plus a digest, so two keys that slug alike never share a
    file. Private to the connector: no verb prints it and the skill never names
    it — `listen --conversation` is the interface."""
    slug = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(key))[:80]
    digest = hashlib.sha256(f"{transport}\x00{key}".encode("utf-8")).hexdigest()[:8]
    return os.path.join(feed_dir(), f"{transport}--{slug}--{digest}.jsonl")


def delivered_mark_path(transport, key):
    """Beside the conversation's feed: the newest event id its scoped listener
    printed (r22 SR-DAEMON R-4). A later `listen --conversation` resumes after
    whichever of `--cursor` and this mark is later in the feed, so a re-arm
    with the starter's original cursor replays nothing already delivered."""
    return feed_path(transport, key) + ".delivered"


def read_delivered_mark(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, ValueError):
        return None
    event_id = value.get("event_id") if isinstance(value, dict) else None
    return event_id if isinstance(event_id, str) and event_id else None


def write_delivered_mark(path, event_id):
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump({"event_id": event_id, "at": utc_now()}, handle)
    os.replace(tmp, path)


def append_feed(envelope, cursor=None, hops=None):
    """D12 fan-out: the one subscription is tee'd into the conversation's feed
    at admission, under the state lock and BEFORE the checkpoint persists, so
    any event the checkpoint knows is in its feed. One `write` on an O_APPEND
    fd under a per-file flock: a line is never interleaved or torn. `hops`
    (#28433, trace only) is stamped `feed_written_at_ms` here and rides on the
    line so a coordinator's tail can carry the upstream stamps forward."""
    key = lane_key_for(envelope)
    if not key:
        return
    transport = lane_route_for(envelope)["transport"]
    actor = envelope.get("actor") or {}
    line = {
        "event_id": envelope.get("event_id"),
        "lane": envelope.get("lane"),
        "from": actor.get("display") or actor.get("id") or "unknown",
        "text": (envelope.get("content") or {}).get("text") or "",
        "received_at_ms": int(time.time() * 1000),
        "cursor": cursor,
        "occurred_at": envelope.get("occurred_at"),
        "envelope": envelope,
    }
    if hops is not None:
        hops["feed_written_at_ms"] = now_ms()
        line["hops"] = dict(hops)
    directory = feed_dir()
    os.makedirs(directory, mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    data = (json.dumps(line, separators=(",", ":")) + "\n").encode("utf-8")
    fd = os.open(feed_path(transport, key), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, data)
    finally:
        os.close(fd)


def parse_feed_lines(raw):
    """Decoded feed lines from raw text; a torn or foreign line is skipped."""
    items = []
    for text in raw.splitlines():
        if not text.strip():
            continue
        try:
            item = json.loads(text)
        except ValueError:
            continue
        if isinstance(item, dict) and item.get("event_id"):
            items.append(item)
    return items


def read_feed(transport, key):
    try:
        with open(feed_path(transport, key), "r", encoding="utf-8") as handle:
            return parse_feed_lines(handle.read())
    except FileNotFoundError:
        return []


def read_feed_last(transport, key):
    """The feed's newest decoded record, reading from the end of the file
    (#29108 review): the liveness sweep asks this for every claimed lane on
    every tick, so it must not re-parse a 1000-line feed per lane per second.
    Reads backwards in chunks until the tail holds a complete, decodable line;
    None for a missing or empty feed."""
    try:
        with open(feed_path(transport, key), "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            span = 0
            while True:
                span = min(size, span * 2 if span else 65536)
                handle.seek(size - span)
                tail = handle.read(span).decode("utf-8", "replace")
                # Drop a leading partial line unless the chunk is the whole file.
                if span < size:
                    tail = tail.split("\n", 1)[1] if "\n" in tail else ""
                items = parse_feed_lines(tail)
                if items:
                    return items[-1]
                if span >= size:
                    return None
    except FileNotFoundError:
        return None


class FeedTail:
    """Follow one feed file: complete new lines per call, reopening from the
    start when the file is recreated or truncated (the reader's event-id dedupe
    makes a re-read harmless)."""

    def __init__(self, path):
        self.path = path
        self.handle = None
        self.ino = None
        self.buffer = b""

    def _open(self):
        try:
            handle = open(self.path, "rb")
        except FileNotFoundError:
            return False
        self.handle = handle
        self.ino = os.fstat(handle.fileno()).st_ino
        self.buffer = b""
        return True

    def close(self):
        if self.handle is not None:
            self.handle.close()
            self.handle = None

    def read_new(self):
        if self.handle is None and not self._open():
            return []
        try:
            stat = os.stat(self.path)
        except FileNotFoundError:
            stat = None
        if stat is None or stat.st_ino != self.ino or stat.st_size < self.handle.tell():
            self.close()
            if stat is None or not self._open():
                return []
        self.buffer += self.handle.read()
        items = []
        while True:
            newline = self.buffer.find(b"\n")
            if newline < 0:
                break
            raw, self.buffer = self.buffer[:newline], self.buffer[newline + 1:]
            try:
                items.extend(parse_feed_lines(raw.decode("utf-8")))
            except UnicodeDecodeError:
                continue
        return items


def claim_for(checkpoint, transport, key):
    return ((checkpoint.get("claims") or {}).get(transport) or {}).get(key)


def lane_is_claimed(checkpoint, alias):
    lane = (checkpoint.get("lanes") or {}).get(alias) or {}
    transport = (lane.get("route") or {}).get("transport")
    return bool(transport and claim_for(checkpoint, transport, lane.get("key")))


def lane_for_conversation(checkpoint, key, transport=None):
    """(alias, lane) for a conversation key. `transport` disambiguates the
    (theoretical) case of one key on both transports. InputError when the
    connector has never seen the conversation."""
    matches = [
        (alias, lane)
        for alias, lane in (checkpoint.get("lanes") or {}).items()
        if lane.get("key") == key
        and (transport is None or (lane.get("route") or {}).get("transport") == transport)
    ]
    if len(matches) > 1:
        raise InputError(f"conversation {key!r} exists on more than one transport; pass --transport")
    if not matches:
        raise InputError(f"no conversation {key!r} has been seen by this connector")
    return matches[0]


def apply_claim(checkpoint, alias, lane, handoff_id, tmux_session=None, backend=None, lane_ref=None):
    """Claim the lane's conversation (D11): from now on its events feed the
    coordinator and never the daemon's stream. A repeat keeps the existing
    handoff id (and lane location) unless a new one is given. #31985: the
    location is `backend` + `lane_ref` (tmux: the session name; herdr: the
    pane id); `tmux_session` stays for a tmux lane and for older readers. A
    claim without `backend` is a tmux lane (adr:31985#D7)."""
    transport = (lane.get("route") or {}).get("transport")
    key = lane.get("key")
    claims = checkpoint.setdefault("claims", {}).setdefault(transport, {})
    claim = claims.get(key) or {"claimed_at": utc_now_precise()}
    claim.update({"key": key, "transport": transport, "lane": alias})
    if handoff_id is not None or "handoff_id" not in claim:
        claim["handoff_id"] = handoff_id
    if tmux_session is not None:
        claim["tmux_session"] = tmux_session  # D15: what the legacy tmux probe asks about
    if backend is not None:
        claim["backend"] = backend
    if lane_ref is not None:
        claim["lane_ref"] = lane_ref
    claims[key] = claim
    return claim


def release_claim(checkpoint, lane):
    """Undo a claim: the conversation wakes the daemon again."""
    transport = (lane.get("route") or {}).get("transport")
    claims = (checkpoint.get("claims") or {}).get(transport) or {}
    return claims.pop(lane.get("key"), None)


def steward_record_for(checkpoint):
    """The one standing fleet-steward engagement this daemon keeps (#31985,
    ADR 31985 D1), or None. Written only by `delegate --steward` - a human's
    ask in that conversation - never by a default or a config key."""
    record = checkpoint.get("steward")
    return record if isinstance(record, dict) and record.get("lane") else None


def steward_record(alias, lane, event_id, envelope):
    text = ((envelope or {}).get("content") or {}).get("text") or ""
    return {
        "lane": alias,
        "key": lane.get("key"),
        "transport": (lane.get("route") or {}).get("transport"),
        "event_id": event_id,
        "armed_at": utc_now(),
        "directive": " ".join(str(text).split())[:200],
    }


def steward_lane_live(record):
    """Whether the recorded steward's lane still lives, by the registry's own
    judgment of its conversation (`lookup --live`). Unknown (the helper could
    not judge or did not answer) reads as live: a claim is never taken over
    an uncertain answer (D15)."""
    answer = registry_lookup(record.get("transport"), record.get("key"), live=True)
    if answer == REGISTRY_LOOKUP_FAILED:
        return True
    if answer["row"] is None or answer["row"].get("state") in ("retired", "orphaned"):
        return False  # no owner row: the registry's own verdict, no probe needed
    return answer["live"] is not False


def steward_status(checkpoint):
    """The record plus `claimed`: whether its conversation is still a
    coordinator's. Liveness beyond that is the registry's to judge (`start`)."""
    record = steward_record_for(checkpoint)
    if record is None:
        return None
    return dict(record, claimed=claim_for(checkpoint, record.get("transport"), record.get("key")) is not None)


def newest_inbound(transport, key, checkpoint, alias):
    """The lane's newest inbound line as (event_id, received_at_ms, envelope)
    from its feed — the retained window when a lane predates feeds — or
    (None, None, None) for a lane with no inbound line. D20: this is the
    reply key's scope, `delegate`'s trigger, and the line the liveness sweep
    surfaces."""
    item = read_feed_last(transport, key)
    if item is not None:
        return item.get("event_id"), int(item.get("received_at_ms") or 0), item.get("envelope")
    for event_id, entry in reversed(list((checkpoint.get("retained_events") or {}).items())):
        envelope = (entry or {}).get("envelope") or {}
        if envelope.get("lane") == alias:
            return event_id, 0, envelope
    return None, None, None


def answered_at_ms(lane):
    """When the lane last got a plain reply (ms), from its outbound ledger:
    an entry that is not `interim` (an arm-time `--say` post, a
    `--replace-last` successor, the daemon's `delegate` acknowledgement).
    A pre-D20 ledger wrote those same rows as `no_ack: true` and state.json
    is not rewritten on upgrade, so that flag reads as interim too — else a
    lane whose coordinator died after an old plan post would read FINISHED
    and never be swept. None when the lane never got a plain reply."""
    stamps = [
        # A card's entry answers twice: at its post (`sent_at_ms`) and at each
        # confirmed update, whose send instant rides `answered_at_ms`
        # (FR-35345-3(b)); the entry itself stays where the post put it.
        max(int(e.get("sent_at_ms") or 0), int(e.get("answered_at_ms") or 0))
        for e in (lane.get("outbound") or [])
        if not (e.get("interim") or e.get("no_ack"))
    ]
    return max(stamps) if stamps else None


def lane_answered(lane, inbound_received_at_ms):
    """D20 item 4: a lane is answered when a plain reply followed its newest
    inbound line. A same-millisecond tie reads as answered (the quiet side)."""
    if inbound_received_at_ms is None:
        return True
    replied = answered_at_ms(lane)
    return replied is not None and replied >= inbound_received_at_ms


# --- D15: a claim is only as good as the listener behind it -------------------


def conversation_lock_path(transport, key):
    """The feed's lock sibling: held (flock) by the conversation's ONE scoped
    listener for its whole life, so its presence is the liveness signal a claim
    itself cannot give."""
    return feed_path(transport, key)[: -len(".jsonl")] + ".lock"


def acquire_conversation_lock(transport, key, heartbeat):
    """Take the conversation lock for this process, or None when another scoped
    listener holds it. The fd is the lease: it is released when the process
    exits, however it exits. `heartbeat` (#28432, required: no holder takes
    the lock without a verdict inside) is written inside the lock file — the
    holder's pid and whether it runs under the Monitor tool — so
    `scoped_listener_probe` can tell a listener that can wake its session
    from one that only holds the lock."""
    os.makedirs(feed_dir(), mode=0o700, exist_ok=True)
    fd = os.open(conversation_lock_path(transport, key), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    if heartbeat is not None:
        os.ftruncate(fd, 0)
        os.write(fd, json.dumps(heartbeat, separators=(",", ":")).encode("utf-8"))
    return fd


# --- #28432: a scoped listener runs only under the Monitor tool ---------------


TOOL_USE_ID_ENV = "MUSE_TOOL_USE_ID"
MONITOR_STDOUT_KIND = "monitor-stdout"
NOT_UNDER_MONITOR_HINT = "arm this command with the monitor tool (persistent, wake_delay_ms 0); bash cannot wake you"


def live_switch_refusal(prior_id, mailbox_id):
    """FR-002b's live-switch refusal as the ONE stdout line the model reads
    (#29361, #27519 QA round 10): the Monitor's `exit status: 1` was all the
    daemon learned, so the line names the branch and the exact recovery; the
    exit code and the stderr line stay. Since #37686 the guard fires only
    for a LIVE listener (one holding the transport lease); a stopped or
    dead one is taken over, so the reason names the live holder."""
    return {
        "outcome": "refused",
        "transport": "mailbox",
        "connected_mailbox_id": prior_id,
        "requested_mailbox_id": mailbox_id,
        "reason": (
            f"mailbox {prior_id!r} is still connected: a live listener holds it, "
            "so this listen would clobber it"
        ),
        "next": (
            f"run `disconnect --transport mailbox` with this script (bash), then re-arm this "
            f"exact listen with --mailbox-id {mailbox_id!r} under the monitor; to keep "
            f"{prior_id!r}, re-arm without --mailbox-id"
        ),
    }


def mailbox_conflict_held(last_line):
    """Is the CLI's last stderr line a held/409 conflict — the id is held by
    another live client? ONE test for both places it can surface: a failed
    `register`, and (#37012) a `listen` stream the relay refuses right after
    a successful register because the previous holder's registration has
    not expired yet. Only `conflict`: the relay's own wording is `The request
    conflicts with current mailbox state.`; the `409` / `already` substrings
    the register path once also matched are gone because the stream path
    sees whatever the child leaked last, and `Address already in use` is a
    crash to escalate, not a hold to wait out (review of PR #37035)."""
    return "conflict" in (last_line or "").strip().lower()


def register_failure_line(mailbox_id, register_failure, held):
    """The register-failure exit (FR-002b (a) held/409, or a transport, auth or
    install failure) as the ONE stdout line the model reads (#29361, review of
    PR #30269): the diagnostic already quotes the CLI's cause; the Monitor's
    `exit status: 3` dropped it. `refused` when this connector declined to
    hijack a held id, `failed` otherwise; exit EXIT_FATAL_LISTEN unchanged."""
    if held:
        # ADR 23499 D21 item 3 (foreign-held, byte-for-byte refusal); the
        # stream path's held line (`stream_ended_line`) is this host's OWN
        # previous session, which is why that one keeps the id (#38191 C10).
        next_hint = (
            "another client holds this id and it is not this host's recent session: re-arm this listen "
            "with a different --mailbox-id, or wait for the holder's registration to expire; do not retry the same id"
        )
    else:
        next_hint = (
            "fix what `reason` names (the transport, auth, or the muse-mailbox install), then "
            "re-arm this exact listen; if it fails the same way again, report `reason` to your human"
        )
    return {
        "outcome": "refused" if held else "failed",
        "transport": "mailbox",
        "requested_mailbox_id": mailbox_id,
        "reason": register_failure,
        "next": next_hint,
    }


def stream_ended_line(mailbox_id, diagnostic, held=False):
    """A `listen` stream that DIED (EOF with a non-zero exit, or any exit in
    production) as the ONE stdout line the model reads (#29361, #27519 QA
    round 7 lane `q7b-listen`): the diagnostic already quotes the child's
    last stderr line, but the Monitor hands the model stdout and the bare
    `exit status: 3`, so the daemon re-armed blind and its human learned
    nothing. `next` is ADR 25011 D21's re-arm rule; exit EXIT_FATAL_LISTEN
    unchanged. A `disconnect`, SIGTERM, parent-death or bounded stop is not
    a death and prints no line. `held` (#37012): the relay refused the
    stream because another client still holds the id — a hold that clears
    itself when the holder's registration expires, so `next` says wait and
    re-arm the same id, never switch ids; its tail keeps D21 (one re-arm,
    then one line to the human and stop) with the held diagnosis in it."""
    if held:
        # #38191 C10: the register path's held line (`register_failure_line`)
        # says switch ids because ITS holder is foreign; here the holder is this
        # host's own previous session, so the id is kept — each line names why.
        next_hint = (
            "held by your own previous session, whose registration expires on its own: wait, then run "
            "the one bare `start` (the daemon skill's startup sequence) and re-arm this exact listen if "
            "it reports the mailbox listener `absent`; keep this --mailbox-id; if it is refused again at "
            "once, tell your human in one line that the id is waiting on the previous holder's expiry "
            "and stop re-arming until they say so"
        )
    else:
        next_hint = (
            "run the one bare `start` (the daemon skill's startup sequence), then re-arm this exact "
            "listen if it reports the mailbox listener `absent`; if the re-armed listener ends "
            "again at once, report `reason` to your human and stop re-arming"
        )
    return {
        "outcome": "refused" if held else "failed",
        "transport": "mailbox",
        "mailbox_id": mailbox_id,
        "reason": diagnostic,
        "next": next_hint,
    }


def say_outcome(payload):
    """Print one stdout JSON line for the model (`outcome` + `next`). The reader
    may already be gone (#27885: the Monitor died first), so a broken pipe must
    never abort the rollback or change the exit code (review of PR #30269);
    stdout is then pointed at /dev/null so the interpreter's exit-time flush
    of the unsent line cannot raise either. A failure line's `reason` is kept
    for the listener end record (`note_listener_end`), so the daemon's next
    `start` can say why, not just the code (owner ruling 27, 2026-09-22)."""
    global LISTENER_END_REASON
    if payload.get("outcome") in ("failed", "refused") and isinstance(payload.get("reason"), str):
        LISTENER_END_REASON = payload["reason"]
    try:
        print(json.dumps(payload), flush=True)
    except OSError:
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
            os.close(devnull)
        except OSError:
            pass


def muse_sessions_dir():
    """The runtime's session store (`crates/agent/src/session_paths.rs`):
    `<XDG_DATA_HOME | ~/.local/share>/muse/sessions/<yyyy>/<mm>/<dd>/<session>`,
    the same data home `state_dir` derives the connector's own root from."""
    xdg = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(xdg, "muse", "sessions")


def monitor_artifact_for(call_id):
    """The monitor tool's stdout artifact for tool call `call_id`, or None.

    The runtime gives every tool child its call id as `MUSE_TOOL_USE_ID` and
    nothing that names the tool; both the monitor and the bash seam spawn
    `sh -c`, detached, stdin closed, so the child cannot tell them apart from
    its environment or its parent (bash execs a simple command, so the parent
    is the session process either way). What differs is on disk: the monitor
    tool opens its stdout spool BEFORE it spawns the child
    (`MonitorStdoutCapture::open`) — staged as
    `<session>/tool-outputs/.spool/<call>-monitor-stdout.txt.tmp` until the
    start result commits it to `<session>/tool-outputs/<task>/<call>-monitor-stdout.txt`,
    where it stays and grows for the source's whole life; the bash tool's
    spool for its own call is `<call>-bash.txt.tmp`. One `lstat` per session
    directory for the staged form, one listing of `tool-outputs/` per session
    for the committed one."""
    # CONTRACT (spec 23499 FR-27816-1(c), 2026-09-03 clarification): the layout
    # below is the runtime's tool-output store, owned by
    # crates/agent/src/tools/workspace/monitor/stdout_capture.rs
    # (`MonitorStdoutCapture::open`: kind "monitor-stdout", extension "txt"),
    # crates/agent/src/tools/workspace/output_spool.rs (`SPOOL_DIR_NAME`
    # ".spool", `SPOOL_SUFFIX` ".tmp") and crates/agent/src/tool/output_store.rs
    # (`output_path`: `<store>/<task id>/<call id>-<kind>.<ext>`). The runtime
    # does not yet pin these shapes for this reader (#28737 asks its owners
    # for the producer-side comment and unit pin); renaming any part there
    # without following it here makes every coordinator listener refuse
    # `not_under_monitor` (loud, never silent).
    if not call_id or not re.fullmatch(r"[A-Za-z0-9_.-]+", call_id):
        return None
    name = f"{call_id}-{MONITOR_STDOUT_KIND}.txt"
    root = glob.escape(muse_sessions_dir())  # a data home with `[`, `*` or `?` is a path, not a pattern
    for layout in (("*", "*", "*", "*"), ("*",)):  # dated canonical, then the legacy flat store
        for tail in ((".spool", name + ".tmp"), ("*", name)):  # staged, then committed
            found = glob.glob(os.path.join(root, *layout, "tool-outputs", *tail))
            if found:
                return found[0]
    return None


def listener_arm():
    """How this process was armed: `under_monitor` is True only when the
    runtime's monitor stdout artifact for THIS tool call exists. No
    `MUSE_TOOL_USE_ID` is a plain shell; an id without it is another tool
    (bash)."""
    call_id = os.environ.get(TOOL_USE_ID_ENV) or None
    return {"under_monitor": monitor_artifact_for(call_id) is not None, "tool_use_id": call_id}


# --- #28176: the ONE unscoped listener per transport announces itself ---------


TRANSPORT_LISTENER_TRANSPORTS = ("mailbox", "slack")
# ADR 37480 D1 (#37480): what this connector declares about itself in
# `status --json`, for the daemon's connector-generic starter — its own
# reference document, the environment NAMES a coordinator lane needs (the
# daemon passes them through, never their values), and, keyed by the
# connector ids this connector mints for the daemon (`delegate`'s
# `slack-connector:<transport>`), whether a lane there can post cards (`reply
# --message-json`), attach files (`reply --attach`) and edit a sent message
# (`reply --replace-last`). Never a transport table (ADR 37480 D1 Rejected,
# D3): the transport is this connector's own word; the daemon looks the map
# up by the opaque id it already holds. The daemon's legacy Slack table
# renders the same facts byte-for-byte; the daemon suite keeps the two equal.
CONNECTOR_REFERENCE = ("references", "slack-ui.md")
LANE_ENV_PASS = (
    "SLACK_CONNECTOR_STATE_DIR",
    "SLACK_CONNECTOR_MAILBOX_CLI",
    "SLACK_CONNECTOR_MAILBOX_CLI_FAKE",
    "SLACK_CONNECTOR_MAILBOX_STATE_FILE",
)
TRANSPORT_CAPABILITIES = {
    "mailbox": {"cards": True, "attach": True, "edit": True},
    "slack": {"cards": False, "attach": False, "edit": True},
}


def connector_reference_path():
    """Absolute path of this connector's reference document, from this script's
    own location (`<skill>/scripts/slack_connector.py` -> `<skill>/references/slack-ui.md`)."""
    skill_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    return os.path.join(skill_dir, *CONNECTOR_REFERENCE)


def transport_listener_lock_path(transport):
    """The unscoped listener's lease: held (flock) by a transport's ONE
    `listen` for its whole life with its pid inside, so `status --json` can say
    whether that listener is live. The daemon's `start` reads it before arming
    — a second `peer inbox` Monitor delivered every message twice (#28176)."""
    return os.path.join(feed_dir(), f"listener-{transport}.lock")


LEASE_ATTEMPTS = 20
LEASE_RETRY_S = 0.025
# #37686 (review of PR #37691): the proceed branch's second take outlasts a
# holder draining a `disconnect` — gone within one poll — by this margin.
LEASE_DRAIN_MARGIN_S = 1.0
# The unscoped listener's lease fd (None: not held). `cmd_listen` takes it;
# `ensure_mailbox_listener_lease` re-takes it on the mailbox proceed branch.
LISTENER_LEASE = None
# The transport whose lease this process holds: `main` records how the
# listener ended under it (#38715 round-11 daemon report N2).
LISTENER_LEASE_TRANSPORT = None
# Set on the parent-death arms before they return EXIT_FATAL_LISTEN: the
# owner died (the Monitor under `kill -9`/OOM), the listener did not fail, and
# the restart re-arms it (ADR 25011 D21 Amendment 1) - so no end is recorded.
LISTENER_OWNER_DIED = False
# The one-line `reason` of the last failure line this process printed
# (`say_outcome`), recorded beside the exit so `status --json` can repeat it.
LISTENER_END_REASON = None


def transport_listener_end_path(transport):
    """Where the unscoped listener leaves how it last ended: `{"pid", "exit",
    "ended_at", "reason"?}` beside its lease, written by `main` when the
    holder returns NON-ZERO and dropped by a clean return or the next lease
    take. A listener stopped by a signal (a Monitor's SIGTERM, a Ctrl-C) or
    by its owner's death (the parent-death arms' EXIT_FATAL_LISTEN, which the
    restart re-arms) writes nothing - a stop is not a failure. `status --json`
    reports it on the transport's record as `exit`, `ended_at` and, when the
    failing listen printed one, `reason` (its stdout line's one-line cause),
    the fields the daemon's `start` reads to write `last_arm` without a model
    call (spec 25011 FR-38715-64(g); owner ruling 27, 2026-09-22)."""
    return os.path.join(feed_dir(), f"listener-{transport}.ended.json")


def owner_died_exit():
    """The parent-death arms' exit: EXIT_FATAL_LISTEN so a Monitor that is
    somehow still reading restarts, flagged so `note_listener_end` records no
    failed end - the daemon's next `start` arms the transport again instead of
    listing it stale (review of PR #39800, P0)."""
    global LISTENER_OWNER_DIED
    LISTENER_OWNER_DIED = True
    return EXIT_FATAL_LISTEN


def note_listener_end(code):
    """Record the exit code this process returns with, when it holds a
    transport's listener lease: a non-zero code is written, a zero one drops
    any earlier record (the clean end supersedes the failure)."""
    if LISTENER_LEASE is None or LISTENER_LEASE_TRANSPORT is None or LISTENER_OWNER_DIED:
        return
    path = transport_listener_end_path(LISTENER_LEASE_TRANSPORT)
    code = 0 if code is None else code  # a handler's bare `return` exits 0
    try:
        if code == 0:
            if os.path.exists(path):
                os.unlink(path)
            return
        record = {"pid": os.getpid(), "exit": int(code), "ended_at": utc_now()}
        if LISTENER_END_REASON:
            record["reason"] = LISTENER_END_REASON
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(record, handle)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except OSError as error:
        diag(f"could not record the listener end: {error}")


def reported_listener_end(transport):
    """`{"exit", "ended_at", "reason"?}` for a transport whose last unscoped
    listener ended non-zero, else `{}`: the record `note_listener_end` left,
    read only while no listener is live (a live one already dropped it)."""
    try:
        with open(transport_listener_end_path(transport), encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError):
        return {}
    code, ended, reason = record.get("exit"), record.get("ended_at"), record.get("reason")
    if isinstance(code, int) and code != 0 and isinstance(ended, str) and ended:
        out = {"exit": code, "ended_at": ended}
        if isinstance(reason, str) and reason:
            out["reason"] = reason
        return out
    return {}


def acquire_transport_listener_lock(transport, wait_s=None):
    """Take the transport's listener lease for this process, or None when
    another unscoped listener holds it. A `status --json` probe takes the same
    lock for microseconds, so one `LOCK_NB` try could lose to a passing probe
    and leave a real listener unleased for its whole life (review of #28195);
    the try is repeated over ~500 ms (or `wait_s`), long enough for any probe
    (and for a stalled test's stand-in) and far short of a real holder's life.
    The caller keeps streaming either way (refusing would be a new `listen`
    block, which the connector contract reserves for a remote hold and a
    live-id switch) — but since #37686 the lease is what the live-switch
    guard reads, so the mailbox proceed branch re-takes a lost one
    (`ensure_mailbox_listener_lease`)."""
    attempts = LEASE_ATTEMPTS if wait_s is None else max(LEASE_ATTEMPTS, int(wait_s / LEASE_RETRY_S) + 1)
    os.makedirs(feed_dir(), mode=0o700, exist_ok=True)
    fd = os.open(transport_listener_lock_path(transport), os.O_RDWR | os.O_CREAT, 0o600)
    for attempt in range(attempts):
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError:
            if attempt == attempts - 1:
                os.close(fd)
                return None
            time.sleep(LEASE_RETRY_S)
    os.ftruncate(fd, 0)
    os.write(fd, f"{os.getpid()}\n".encode("ascii"))
    # This listener is the transport's newest: an earlier holder's end is
    # history, and `status` must not report it beside a live record.
    global LISTENER_LEASE_TRANSPORT
    LISTENER_LEASE_TRANSPORT = transport
    try:
        os.unlink(transport_listener_end_path(transport))
    except FileNotFoundError:
        pass
    except OSError as error:
        diag(f"could not drop the previous listener end record: {error}")
    return fd


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def transport_listener(transport):
    """`{"listener": "live"|"absent", "pid": <holder>|None}`: a non-blocking
    probe of the lease (taken and dropped at once, never created). The holder
    is the pid the lease records, and only a LIVE pid counts — the lock is
    held for an instant by a concurrent probe too, whose "holder" would be
    the previous listener's stale pid."""
    absent = {"listener": "absent", "pid": None, **reported_listener_end(transport)}
    try:
        fd = os.open(transport_listener_lock_path(transport), os.O_RDONLY)
    except FileNotFoundError:
        return absent
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raw = os.read(fd, 32).decode("ascii", errors="replace").strip()
            if raw.isdigit() and pid_alive(int(raw)):
                return {"listener": "live", "pid": int(raw)}
    finally:
        os.close(fd)
    return absent


def another_mailbox_listener_is_live():
    """Does a DIFFERENT live process hold the mailbox listener lease? The
    FR-002b (b) live-switch guard's predicate (#37686): `mailbox.connected`
    is a flag only `disconnect` clears and nothing runs at exit (ADR 23499
    D21), so after every restart it stood for a listener that was gone and a
    switch to another id was refused once per restart. `cmd_listen` takes
    the lease before `listen_mailbox` runs, so the holder the probe reports
    is THIS process unless another listener beat it; only that other holder
    counts."""
    probe = transport_listener("mailbox")
    return probe["listener"] == "live" and probe["pid"] != os.getpid()


def ensure_mailbox_listener_lease():
    """A mailbox listen that goes ahead MUST hold the lease the live-switch
    guard reads (#37686, review of PR #37691): one that streams unleased is
    invisible to the next guard and gets clobbered. `cmd_listen`'s take is
    short so a live holder is refused promptly; a take that lost there lost
    to a holder now dead or draining a `disconnect` — the refusal's own
    `next` re-arms right behind one — which lets go within one poll, so
    wait that long plus margin here. Still held after that: the #28176
    double arm; report it and stream, as before."""
    global LISTENER_LEASE
    if LISTENER_LEASE is not None:
        return
    wait_s = mailbox_disconnect_poll_s() + LEASE_DRAIN_MARGIN_S
    diag(
        f"waiting up to {wait_s:g}s for the mailbox listener lease (held by pid "
        f"{transport_listener('mailbox').get('pid')}; a holder draining a `disconnect` lets go within one poll)"
    )
    LISTENER_LEASE = acquire_transport_listener_lock("mailbox", wait_s=wait_s)
    if LISTENER_LEASE is None:
        holder = transport_listener("mailbox").get("pid")
        diag(
            f"mailbox listener lease still held by pid {holder} after {wait_s:g}s; streaming "
            "unleased — two unscoped listeners deliver every message twice, arm only once"
        )
    else:
        diag("mailbox listener lease taken once the previous holder let go")


def scoped_listener_probe(transport, key):
    """`{"alive", "under_monitor"}`: whether a scoped listener holds the
    conversation lock (a probe: taken non-blocking and dropped at once, never
    created) and, from the heartbeat it wrote inside (#28432), whether it runs
    under the Monitor tool — None for a holder that wrote none (a listener
    from before the heartbeat, or a probe that beat the write by a moment)."""
    absent = {"alive": False, "under_monitor": None}
    try:
        fd = os.open(conversation_lock_path(transport, key), os.O_RDONLY)
    except FileNotFoundError:
        return absent
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            try:
                beat = json.loads(os.read(fd, 1024).decode("utf-8", errors="replace") or "null")
            except ValueError:
                beat = None
            under = beat.get("under_monitor") if isinstance(beat, dict) else None
            return {"alive": True, "under_monitor": under if isinstance(under, bool) else None}
    finally:
        os.close(fd)
    return absent


def scoped_listener_tails(transport, key):
    """True while a scoped listener holds the lock AND can wake its session
    (#28432): a holder whose heartbeat says it is not under the Monitor tool
    prints into a spool nobody reads, so for FR-27816-2(b) it is absent."""
    probe = scoped_listener_probe(transport, key)
    return probe["alive"] and probe["under_monitor"] is not False


def parse_stamp(stamp):
    """A connector timestamp as an aware datetime; None when it is unreadable.
    Reads the sub-second stamp and the whole-second one older state files hold."""
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(stamp or "", fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def stamp_age_s(stamp):
    """Seconds since a connector timestamp; None when it is unreadable."""
    made = parse_stamp(stamp)
    if made is None:
        return None
    return max((datetime.now(timezone.utc) - made).total_seconds(), 0.0)


def claim_age_s(claim):
    """Seconds since the claim was made; None when it carries no readable time
    (treated as old: an undatable claim must not deafen a conversation)."""
    return stamp_age_s(claim.get("claimed_at"))


def claim_tmux_session(claim, alias):
    """The coordinator's tmux session: the one the launch reported, else the
    name the daemon registry helper derives by default (a bare `claim` never
    saw a launch)."""
    if claim.get("tmux_session"):
        return claim["tmux_session"]
    raw = f"{claim.get('transport')}-{alias}"
    return "muse-lane-" + re.sub(r"[^A-Za-z0-9_-]+", "-", raw).strip("-")


def claim_backend(claim):
    """`tmux` unless the claim records another backend (adr:31985#D7: a claim
    written before backends existed keeps its tmux meaning)."""
    return claim.get("backend") or "tmux"


def claim_lane_ref(claim, alias):
    """The lane's backend-qualified location: the launch's `lane_ref` (tmux
    session name or Herdr pane id), else the legacy tmux name."""
    return claim.get("lane_ref") or claim_tmux_session(claim, alias)


def claimed_by(claim, alias):
    return {
        "lane": alias,
        "tmux_session": claim_tmux_session(claim, alias),
        "handoff_id": claim.get("handoff_id"),
    }


def claim_is_unattended(claim, grace_s):
    """A claimed conversation nobody tails, past its grace: the coordinator is
    gone (or never armed its listener), so the event is the daemon's again.
    While `delegate`'s launch is still running (`launching`, #28181) the grace
    is at least the helper's own timeout: a follow-up that lands mid-launch is
    the coordinator's, and a connector killed mid-launch can hold the
    conversation no longer than the launch could have run."""
    if scoped_listener_tails(claim.get("transport"), claim.get("key")):
        return False
    age = claim_age_s(claim)
    if age is None:
        return True
    if claim.get("launching"):
        grace_s = max(grace_s, REGISTRY_HELPER_TIMEOUT_S)
    return age > grace_s


def dispatch_receipt(claim):
    """#29739: the recorded receipt of the dispatch that made this claim, while
    the claim is still fresh (within the default unattended grace of its
    launch). A second `delegate` for a live lane inside that window is the
    same dispatch again: the line it was sent for is either inside the
    launched snapshot (drained to the daemon after the result) or newer than
    the claim, which routed it to the coordinator's feed (harness lane
    o-kill-c2: a goal reminder asked for a `delegate` on the second follow-up
    30 s after the relaunch) — so it gets the same answer. None past the
    grace (the liveness sweep's re-print of an unanswered line on a lane that
    never armed, FR-27816-2(f): `already_owned` stands) and for a claim
    written by an older connector without the field (no schema bump)."""
    receipt = claim.get("receipt")
    if not isinstance(receipt, dict):
        return None
    age = claim_age_s(claim)
    if age is None or age > UNATTENDED_GRACE_S_DEFAULT:
        return None
    swept_at, claimed_at = parse_stamp(claim.get("unattended_at")), parse_stamp(claim.get("claimed_at"))
    if swept_at is not None and claimed_at is not None and swept_at > claimed_at:
        # The (f) sweep re-printed this lane after the launch returned (a
        # listener running a shorter --unattended-grace): the sweep's
        # `already_owned` stands (review of #29887). The two stamps are
        # compared directly, not through two clock reads.
        return None
    return dict(receipt)


def unattended_envelope(envelope, claim, alias):
    """The emitted copy of an unattended event: the normal envelope plus the
    two fields that say whose conversation it was. The retained envelope is
    unchanged; the compact line renders the `[unattended]` marker off `claim`
    (`compact_line`, #28197)."""
    return dict(envelope, claim="unattended", claimed_by=claimed_by(claim, alias))


def unattended_grace_s(args):
    value = getattr(args, "unattended_grace", None)
    return UNATTENDED_GRACE_S_DEFAULT if value is None else max(float(value), 0.0)


def note_unattended_emission(claim):
    """Stamp the claim with this unattended emission (FR-27816-2(f)): the idle
    sweep repeats a line for one claim at most once per grace. Sub-second like
    `claimed_at` (#28181): a floored stamp let the line repeat up to 1 s early."""
    claim["unattended_at"] = utc_now_precise()


def sweep_unattended_claims(transport, grace_s, in_scope=None):
    """`adr:25011-daemon-session-coordination#D20` item 4 (replacing D17's
    ledger sweep; spec 23499 FR-27816-2(f)): on its own tick the unscoped
    listener judges every claimed conversation of its transport from
    liveness alone — the lock is free, the claim is past the grace, no
    unattended line went out for it within the last grace, and the lane's
    newest inbound line has no plain reply after it (DEAD) — and returns that
    newest inbound line marked `[unattended]`, so the daemon's one `delegate`
    relaunches the lane with no new message needed. An answered lane
    (FINISHED, or merely idle) is left alone until the requester writes
    again (D15). The stamp is persisted before the line is emitted (INV-1)."""
    emitted = []
    with StateStore() as store:
        state = store.load(require=True)
        checkpoint = state["checkpoint"]
        claims = (checkpoint.get("claims") or {}).get(transport) or {}
        lanes = checkpoint.get("lanes") or {}
        for key in sorted(claims):
            claim = claims[key]
            alias = claim.get("lane")
            lane = lanes.get(alias)
            if lane is None:
                continue
            # Cheapest test first (#29108 review): a line went out within the
            # grace, so nothing to do — before the flock probe and the feed read.
            since = stamp_age_s(claim.get("unattended_at"))
            if since is not None and since <= grace_s:
                continue
            if not claim_is_unattended(claim, grace_s):
                continue
            event_id, received_at_ms, envelope = newest_inbound(transport, key, checkpoint, alias)
            if not event_id or lane_answered(lane, received_at_ms):
                continue
            if in_scope is not None and not in_scope(envelope):
                continue
            note_unattended_emission(claim)
            emitted.append(unattended_envelope(envelope, claim, alias))
        if emitted:
            store.save(state)
    return emitted


def tmux_session_is_live(name):
    """EXACT-name liveness through the daemon registry helper's own tmux argv
    (`MUSE_DAEMON_TMUX`) and predicate: list every pane on that server and
    match the session name byte for byte with a pane that is not dead — `-t`
    targets prefix-match, so `has-session` would say yes to `name-extra`.
    Only "no server / no sessions" (the helper's `live_tmux_sessions` rule) is
    "dead"; a tmux that cannot run or fails otherwise (bad `MUSE_DAEMON_TMUX`,
    socket permission, protocol error) raises OSError — unknown, not dead — so
    the caller never takes a live coordinator's conversation over it."""
    env = dict(os.environ)
    env.pop("TMUX", None)
    proc = subprocess.run(
        [*shlex.split(os.environ.get(DAEMON_TMUX_ENV) or "tmux"), "list-panes", "-a", "-F",
         "#{session_name}\t#{pane_dead}"],
        capture_output=True, text=True, env=env, check=False, timeout=30,
    )
    if proc.returncode != 0:
        err = proc.stderr.strip()
        if any(s in err for s in ("no server running", "no sessions", "No such file or directory")):
            return False
        raise OSError(f"tmux list-panes failed (exit {proc.returncode}): {err or 'no stderr'}")
    for line in proc.stdout.splitlines():
        session, _, dead = line.partition("\t")
        if session == name and dead.strip() == "0":
            return True
    return False


def lane_sort_key(alias):
    """Mint order (`c10` after `c9`), matching FR-23499-11's `status --json`."""
    return int(alias[1:]) if alias[1:].isdigit() else 0


def compact_sender(who):
    """The sender slot of the compact grammar, made safe where the grammar is
    minted. A display name is free text — the mailbox path type-checks the
    peer's id as a non-empty string and nothing more — and this slot is the
    one the connector's own facts share:

    - #29146: one event is ONE lane-prefixed line. A name carrying a newline
      (`zed\\nc9 alice`) made the event two listener lines — a text-less
      `c5 zed` and a forged `c9 alice: hey` for a lane that does not exist —
      so every non-printable code point (`str.isprintable()` false: control,
      format, separator, private-use — wider than Cc on purpose, so a bidi
      override or a zero-width split `[unat\\u200btended]` cannot reach the
      slot either) becomes a space and whitespace runs collapse.
    - #29030 (review of #28602): ` [unattended]` before the colon is the
      connector's dead-lane fact alone. `alice [unattended]` made a LIVE
      lane's line byte-for-byte a dead lane's line for `alice`, and the TUI's
      feed cell lifted the suffix as the dead-lane title fact.
    - #30542: the slot carries the requester's DISPLAY NAME when the relay
      names one, so a colon is scrubbed too — the grammar (and the TUI's
      `parse_feed_line`) ends the sender at the first `": "`, and a name
      `Alice: OOO` would move `OOO` into the text and the split before it.
    - #30674 (review of #30662): ` [+<name> <size>]` is the connector's file
      marker (D20 item 5), so `[+` inside a name is written `(+` the same way
      `[unattended]` is."""
    who = "".join(ch if ch.isprintable() and ch != ":" else " " for ch in who)
    who = " ".join(who.split())
    # #35345: ` [ui]` before the colon is the connector's own fact too (a
    # click or a surfaced card result), written `(ui)` when a name carries it.
    return UI_MARK.sub("(ui)", who.replace("[unattended]", "(unattended)").replace("[+", "(+")) or "unknown"


def compact_line(envelope):
    """D11: the listener's default output — one human transcript line per event,
    prefixed with the lane alias `reply --to` takes. This stdout IS the
    monitored stream, so the same rendering that cuts the model's per-message
    read cost is what makes the TUI's monitor view readable.

    The event ref appears only when the text was truncated past TEXT_BOUND,
    because that is the only case where the model needs `show` at all."""
    lane = envelope.get("lane") or "c?"
    actor = envelope.get("actor") or {}
    who = compact_sender(actor.get("display") or actor.get("id") or "unknown")
    content = envelope.get("content") or {}
    body = (content.get("text") or "").splitlines() or [""]
    # D15 / #28197: an unattended event is marked ON the line, between the
    # sender and the colon. The daemon reads this stream through a Monitor and
    # never the envelope JSON, so a `claim` that lived only there left a dead
    # lane's follow-up byte-identical to a live coordinator's and the model
    # left it pending. The line is still a message by shape (`": "` follows).
    marker = " [unattended]" if envelope.get("claim") == "unattended" else ""
    if envelope.get("kind") in UI_LINE_KINDS:
        # #35345 (spec 23499 FR-35345-4(c)): a click or a surfaced card result
        # is marked ` [ui]` in the same slot, before ` [unattended]`.
        marker = " [ui]" + marker
    # #30643: where each mailbox attachment landed rides under the header as a
    # 4-space continuation (the D20 item 5 forward text), so the Monitor's
    # reader needs no `show` to find the file. Mailbox arm only: a Slack file
    # drop's line is untouched (D20 item 7, #29131 is separate).
    if (envelope.get("container") or {}).get("type") == "mailbox":
        body = with_message_lines(content.get("text") or "", envelope).splitlines() or body
    lines = [f"{lane} {who}{attachment_markers(envelope)}{marker}: {body[0]}"]
    # Continuation lines indent under the header so a multi-line paste stays
    # readable and still visibly belongs to its lane.
    lines.extend(f"    {line}" for line in body[1:])
    if content.get("truncated"):
        lines.append("    " + show_hint(envelope.get("event_id")))
    return "\n".join(lines)


def show_hint(event_id):
    """The one line that names a text cut at TEXT_BOUND and the call that
    completes it — the compact line's trailer and the native forward's
    (#30788); both run while the event is still retained, so `show` answers.
    The delegate snapshot never prints it: it carries the whole retained text,
    and once the window has dropped the event it says so instead."""
    return f"… truncated; show --event-id {event_id} --json"


def emit_format(seam_armed):
    """D11: the listener has ONE output shape — the compact line. Envelope JSON
    is a test seam, not a flag: no production caller reads it (the daemon reads
    this stream as a model, through a Monitor), and a `--format` in `--help`
    would advertise a mode whose whole cost is the per-message read budget this
    surface exists to cut. A model that needs one envelope runs `show`.

    The caller passes ITS OWN transport's seam (FR-020, as for `crash_if` and
    `pending_max`): a leaked mailbox fake flag must not turn a real Slack
    listener's output to JSON under a Monitor that expects transcript lines."""
    if not seam_armed:
        return "compact"
    return "json" if os.environ.get("SLACK_CONNECTOR_EMIT") == "json" else "compact"


def emit_event(envelope, output_format, hops=None):
    """The listener's one emit seam. Returns the printed text. With `hops`
    (#28433, trace only) the print is stamped `printed_at_ms` and the line
    carries the hop summary — a suffix on the compact line's header, a `hops`
    field on the envelope JSON."""
    if hops is not None:
        hops["printed_at_ms"] = now_ms()
        if output_format == "json":
            text = json.dumps(dict(envelope, hops=dict(hops)))
        else:
            # On the HEADER line (review of #28516): a continuation or the
            # `… truncated; show …` hint must stay pasteable, and the Monitor
            # queues one body per stdout line, so the header — the line with
            # `": "` — is what the report joins to `inbox_item_queued`.
            head, sep, rest = compact_line(envelope).partition("\n")
            text = head + hops_suffix(hops) + sep + rest
    else:
        text = json.dumps(envelope) if output_format == "json" else compact_line(envelope)
    if NATIVE_FORWARDER is not None:
        # ADR 25011 D22 item 1 / ADR 23499 D19 item 1: under native delivery
        # the listener's stdout is never model input, and only the mailbox
        # admission path (`process_cli_item`) decides who owns an event —
        # nothing is forwarded from here, ownerless.
        diag(f"native delivery: no Monitor line for {envelope.get('event_id')} (not an admission path)")
        return None
    print(text, flush=True)
    return text


# --- ADR 25011 D22: native delivery -------------------------------------------
# The connector's unscoped listener is the ONE forwarder (ADR 23499 D19 item 1):
# each admitted event becomes a session message to the session that owns its
# conversation — the daemon, or the coordinator the registry names — through
# the product CLI (`muse session-message send --display-context <json>`), which
# owns discovery and authentication (ADR 23499 D1). The caller selects no
# delivery policy (spec 23992 INV-003A): the trusted boundary lowers a copy
# whose `owner.state` is `owned` to the daemon's operator-only notify-only row.
# Liveness is the owner session's endpoint: a delivery refused because the
# coordinator's session is gone, past the D15 grace, goes to the daemon as
# `owner: gone` and the daemon's one `delegate` relaunches (D22 item 1).
NATIVE_DELIVERY_ENV = "MUSE_EXPERIMENTAL_NATIVE_CONNECTOR_DELIVERY"
MUSE_BIN_ENV = "MUSE_BIN"
DISPLAY_CONTEXT_FACT_MAX_BYTES = 200   # one title segment / forensic row (D22 item 1)
DISPLAY_CONTEXT_MAX_BYTES = 4096       # the whole object, relay block included
RELAY_CONTEXT_MAX_BYTES = 3072         # what the connector retains of the relay's block
# ADR 23499 D20 item 2 as amended 2026-09-08 (#31078): the production relay
# puts no `context` block on the wire (its contextual payload is gated on the
# relay's side), so the mark also reads the one fact every routed relay
# message carries — the relay's signed conversation token as the
# `conversation_id`, `<prefix>.<base64url payload>.<base64url mac>`, which the
# relay's own decoder admits only when it starts with the prefix AND the dot.
# Provenance (the relay's token constant and its decode rule): spec 23499
# FR-31078-1. The connector reads exactly that prefix and never decodes the
# token. The sender mailbox id (`musetag-central-relay-<unixname>`) is a relay
# SETTING, not a constant, so it is not read.
RELAY_CONVERSATION_ID_PREFIX = "musetag-conversation-v1."
NATIVE_SEND_TIMEOUT_S = 20.0
NATIVE_RETRY_MIN_S = 60                # floor of the transient retry window (seconds from the first attempt)
REGISTRY_LOOKUP_FAILED = "__registry_lookup_failed__"  # the helper did not answer; not "no coordinator"
NATIVE_FORWARDER = None                # set by `listen` under the gate; None = the Monitor line path


def native_delivery_enabled():
    return (os.environ.get(NATIVE_DELIVERY_ENV) or "").strip().lower() in ("1", "on", "true", "yes")


def bounded_fact(value):
    """One display fact: a non-empty single line of at most
    DISPLAY_CONTEXT_FACT_MAX_BYTES bytes INCLUDING the `…` that marks a cut, or
    None (the fact and its separator disappear together — the receiver rejects
    a control byte outright, and refuses a fact over the bound rather than
    cutting it, so an over-long display name failed the native send when the
    marker rode outside the bound; review of #33053)."""
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    encoded = text.encode("utf-8")
    if len(encoded) > DISPLAY_CONTEXT_FACT_MAX_BYTES:
        text = encoded[: DISPLAY_CONTEXT_FACT_MAX_BYTES - 3].decode("utf-8", "ignore").rstrip() + "…"
    return text


# #30542: the keys the connector reads out of the relay's `context` block — the
# observed set only (review of #30549): the relay's `conversation_delta`
# bundle (`requester: {id}`, the display name on the matching
# `messages[].author`, `source.provider`) plus the tier-1 fields #30544 asks
# for (`requester.display_name`, `source.channel_id/thread_ts/team_id`), read
# on the block itself and then under `source`. A key the live relay names
# differently is added here, with a `test_relay_context` case, in a follow-up.
RELAY_NAME_KEYS = ("display_name", "name", "real_name")
RELAY_ID_KEYS = ("id",)
RELAY_THREAD_KEYS = (
    ("channel_id", ("channel_id",)),
    ("thread_ts", ("thread_ts",)),
    ("team_id", ("team_id",)),
    ("surface", ("provider",)),
)
# The relay's `context.messages` window is the monitored channel's own
# conversation: the posts around the tagged one, which carry no Muse tag and so
# are never routed as their own `peer_message`. They were read for a display
# name and then dropped, so a coordinator answered a tagged ask with no sight of
# the thread it was asked in. They ride the model-read seams as one combined
# `context:` row plus `[context]` lines (`with_context_lines`), bounded here.
RELAY_HISTORY_MAX = 10                 # untagged posts kept per routed message
# Per-lane digests, so a repeated window is injected once. Deliberately small:
# the whole checkpoint is rewritten under the lock on every admission, and the
# set only has to outlive the relay's sliding window (a few windows' worth),
# not the conversation — at LANES_MAX lanes this is the difference between a
# few hundred KB of state and a few MB.
RELAY_HISTORY_SEEN_MAX = 50
# The observed `conversation_delta` entry names only these two — the same
# house rule as RELAY_NAME_KEYS: a key the live relay names differently is
# added here together with a `test_relay_context` case, never pre-accepted
# (review of #33053; Principle XI).
RELAY_HISTORY_TEXT_KEYS = ("text",)
RELAY_HISTORY_AUTHOR_KEYS = ("author",)


def _relay_text(mapping, keys):
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return bounded_fact(value)
    return None


def relay_facts(context):
    """#30542: who asked, and which thread — the two presentation facts the
    connector keeps out of the relay's `body.context`, whatever the block's
    size. Tolerant on purpose: the block is relay-asserted (never authority,
    ADR 23499 D19 / ADR 25011 D22), every key is a candidate, an unknown key
    is ignored, a non-string value is not a fact, and no block — or one of an
    unknown shape — yields None. Returns `{"requester": {display_name?, id?},
    "thread": {surface?, channel_id?, thread_ts?, team_id?, ref}}` with only
    the members it found; each string is one bounded line."""
    if not isinstance(context, dict):
        return None
    requester = {}
    raw = context.get("requester")
    if isinstance(raw, dict):
        name = _relay_text(raw, RELAY_NAME_KEYS)
        ident = _relay_text(raw, RELAY_ID_KEYS)
        if name is None and ident is not None:
            # The delta shape names the requester only as an author.
            messages = context.get("messages")
            for message in messages if isinstance(messages, list) else []:
                author = message.get("author") if isinstance(message, dict) else None
                if isinstance(author, dict) and _relay_text(author, RELAY_ID_KEYS) == ident:
                    name = _relay_text(author, RELAY_NAME_KEYS)
                    if name:
                        break
        if name:
            requester["display_name"] = name
        if ident:
            requester["id"] = ident
    elif isinstance(raw, str) and raw.strip():
        requester["display_name"] = bounded_fact(raw)
    thread = {}
    holders = [context] + ([context["source"]] if isinstance(context.get("source"), dict) else [])
    for holder in holders:
        for fact, keys in RELAY_THREAD_KEYS:
            if fact not in thread:
                value = _relay_text(holder, keys)
                if value:
                    thread[fact] = value
    if thread.get("channel_id") or thread.get("thread_ts"):
        thread["ref"] = "/".join(part for part in (thread.get("channel_id"), thread.get("thread_ts")) if part)
    else:
        thread = {}
    facts = {}
    if requester:
        facts["requester"] = requester
    if thread:
        facts["thread"] = thread
    return facts or None


def relay_history(context, routed_text=None):
    """The untagged conversation the relay's `context` block carries: one
    bounded `{from, text}` per message in `context.messages` EXCEPT the tagged
    post that was routed as this `peer_message` (matched on its text, the only
    identity the block and the body share).

    Only a tagged post becomes a message of its own, so without this the posts
    between two tags never reach the monitored channel at all — the block was
    read for a display name (`relay_facts`) and dropped. Tolerant on purpose,
    exactly like `relay_facts`: the block is relay-asserted and never authority
    (ADR 23499 D19 / ADR 25011 D22), an entry of an unknown shape or with no
    text is skipped, and no block yields []. Remote text, so it is defused at
    this admission seam like every other peer byte (#30674) and bounded to one
    line each; the newest RELAY_HISTORY_MAX are kept, oldest first, because the
    window grows with the thread while the prompt and the line do not."""
    if not isinstance(context, dict):
        return []
    messages = context.get("messages")
    if not isinstance(messages, list):
        return []
    routed = bounded_fact(defuse_peer_text(routed_text or ""))
    history = []
    for entry in messages:
        if not isinstance(entry, dict):
            continue
        text = _relay_text(entry, RELAY_HISTORY_TEXT_KEYS)
        if text is None:
            continue
        text = bounded_fact(defuse_peer_text(text))
        if text is None or (routed is not None and text == routed):
            # The tagged post is the message itself: it is already the body.
            continue
        who = None
        for key in RELAY_HISTORY_AUTHOR_KEYS:
            value = entry.get(key)
            if isinstance(value, dict):
                who = _relay_text(value, RELAY_NAME_KEYS) or _relay_text(value, RELAY_ID_KEYS)
            elif isinstance(value, str):
                who = bounded_fact(value)
            if who:
                break
        history.append({"from": who or "unknown", "text": text})
    return history[-RELAY_HISTORY_MAX:]


def display_context_for(envelope, transport, owner=None):
    """The `display_context` object ADR 25011 D22 item 1 pins, built from the
    connector envelope: display name (the relay's requester when it names one,
    else the transport author), lane, inbox description (ADR 26855 D7),
    transport, mailbox/channel id, conversation key, transport message id, the
    ownership fact and the relay's block."""
    actor = envelope.get("actor") or {}
    container = envelope.get("container") or {}
    relay = envelope.get("relay_context") if isinstance(envelope.get("relay_context"), dict) else None
    requester = relay.get("requester") if relay else None
    # #30542: the name rides the bounded `relay` facts (whatever the block's
    # size); the block itself is the fallback for an envelope retained before
    # the facts existed.
    facts = envelope.get("relay") if isinstance(envelope.get("relay"), dict) else {}
    named = facts.get("requester") if isinstance(facts.get("requester"), dict) else {}
    name = named.get("display_name")
    if not name and isinstance(requester, dict):
        name = requester.get("display_name") or requester.get("name") or requester.get("real_name")
    elif not name and isinstance(requester, str):
        name = requester
    name = name or actor.get("display") or actor.get("id")
    if transport == "mailbox":
        inbox, mailbox_id = "peer inbox", actor.get("id")
    else:
        inbox = "slack thread" if container.get("thread_id") else "slack channel"
        mailbox_id = container.get("id")
    reply_target = envelope.get("reply_target") or {}
    context = {
        "sender_display_name": bounded_fact(name),
        "lane": bounded_fact(envelope.get("lane")),
        "inbox": inbox,
        "transport": transport,
        "mailbox_id": bounded_fact(mailbox_id),
        "conversation_key": bounded_fact(lane_key_for(envelope)),
        "transport_message_id": bounded_fact(
            reply_target.get("message_id") or reply_target.get("ts") or envelope.get("event_id")
        ),
    }
    if owner:
        context["owner"] = {"lane_session": bounded_fact(owner["lane_session"]) or "unknown", "state": owner["state"]}
    if relay:
        context["relay_context"] = relay
    context = {key: value for key, value in context.items() if value is not None}
    encoded = json.dumps(context, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > DISPLAY_CONTEXT_MAX_BYTES and "relay_context" in context:
        context.pop("relay_context")  # the block is the only unbounded member; the facts stay
    return context


def registry_lookup(transport, key, live=False):
    """The daemon registry's `lookup` line for a conversation (ADR 25011 D4 —
    read-only), normalized: `{"outcome": "found"|"not_found", "row": dict|None,
    "live": True|False|None}`. `row` is None when the registry holds no row
    (`not_found`: nobody owns the conversation — definitive). `live` is the
    helper's own top-level judgment of the lane through its recorded backend
    (#31985) and is asked for only with `live=True` (`lookup --live`: a lane
    probe the per-message forwarder path must not pay for); None when it was
    not asked, the helper could not judge, or an older helper answered.
    REGISTRY_LOOKUP_FAILED when the helper did not answer (exit non-zero,
    timeout, unreadable output) — a transient, never "gone"."""
    helper = daemon_registry_helper()
    argv = [sys.executable or "python3", helper, "lookup",
            "--connector", f"slack-connector:{transport}", "--conversation", key]
    if live:
        argv.append("--live")
    try:
        run = subprocess.run(argv, input="", text=True, capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as error:
        diag(f"daemon_registry lookup did not run ({error})")
        return REGISTRY_LOOKUP_FAILED
    if run.returncode != 0:
        diag(f"daemon_registry lookup failed (exit {run.returncode}): {(run.stderr or run.stdout).strip()[:200]}")
        return REGISTRY_LOOKUP_FAILED
    try:
        payload = json.loads(run.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        payload = None
    if not isinstance(payload, dict):
        diag("daemon_registry lookup printed no JSON row")
        return REGISTRY_LOOKUP_FAILED
    row = payload.get("row") if isinstance(payload.get("row"), dict) else None
    judged = payload.get("live") if live else None
    return {
        "outcome": payload.get("outcome") or ("found" if row is not None else "not_found"),
        "row": row,
        "live": judged if isinstance(judged, bool) else None,
    }


def coordinator_session_for(transport, key):
    """The Muse session id the daemon's registry records for a claimed
    conversation. None while the lane has not bound its session yet (a clean
    row without `muse_session_id`, or no active row); REGISTRY_LOOKUP_FAILED
    when the helper did not answer."""
    answer = registry_lookup(transport, key)
    if answer == REGISTRY_LOOKUP_FAILED:
        return REGISTRY_LOOKUP_FAILED
    row = answer["row"] or {}
    if row.get("state") not in (None, "active"):
        return None
    return row.get("muse_session_id") or None


def native_retry_budget_s(grace_s):
    """How long a transient send failure keeps an event on the tick, measured
    from its first attempt: at least the unattended grace, never under
    NATIVE_RETRY_MIN_S. The mailbox test seams may shorten it."""
    raw = os.environ.get("SLACK_CONNECTOR_NATIVE_RETRY_BUDGET_S") if mailbox_seams_enabled() else None
    if raw:
        return float(raw)
    return max(float(grace_s or 0.0), float(NATIVE_RETRY_MIN_S))


class NativeForwarder:
    """One forwarder per unscoped listener (ADR 23499 D19 item 1). The queue
    is the checkpoint, never memory: every admitted event's retained entry
    carries a `native` record — `pending` until a send is accepted, then
    `forwarded`, or `dropped` past the transient budget — so a listener
    restart re-scans the retained entries (feed order) and re-forwards what
    never arrived."""

    def __init__(self, deliver_to, muse_bin, transport, grace_s):
        self.deliver_to = deliver_to
        self.muse_bin = muse_bin
        self.transport = transport
        self.grace_s = grace_s

    def _send(self, target, envelope, context):
        # #30788: the session message is a model-read surface like the compact
        # line, so a text cut at TEXT_BOUND names the cut the same way — the
        # marker after the text, the attachment lines still last.
        content = envelope.get("content") or {}
        text = content.get("text") or ""
        if content.get("truncated"):
            text = f"{text}\n{show_hint(envelope.get('event_id'))}"
        text = with_message_lines(text, envelope)
        argv = [self.muse_bin, "session-message", "send", "--target", target,
                "--display-context", json.dumps(context, separators=(",", ":")), "--json"]
        try:
            run = subprocess.run(argv, input=text, text=True, capture_output=True, timeout=NATIVE_SEND_TIMEOUT_S)
        except FileNotFoundError:
            return {"status": "error", "error_code": "muse_bin_not_found", "detail": self.muse_bin}
        except subprocess.TimeoutExpired:
            return {"status": "error", "error_code": "send_timeout"}
        body = {}
        for line in reversed(run.stdout.strip().splitlines()):
            try:
                body = json.loads(line)
                break
            except ValueError:
                continue
        if not isinstance(body, dict):
            body = {}
        body.setdefault("status", "error" if run.returncode else "accepted")
        if run.returncode and not body.get("error_code"):
            body["error_code"] = (run.stderr.strip().splitlines() or ["send_failed"])[-1][:200]
        return body

    @staticmethod
    def _accepted(result):
        return result.get("status") in ("accepted", "duplicate") or (
            result.get("claimed_outcome") or {}
        ).get("status") == "accepted"

    @staticmethod
    def _held(result):
        """`status: pending` (`pending_admission`, `pending_router_delivery`): the
        target holds the message and decides later — handed off, never re-sent
        (a re-send would mint a second copy behind the first). A refused
        admission is `unavailable` / `admission_unavailable`, a transient."""
        return result.get("status") == "pending"

    @staticmethod
    def _target_gone(result):
        """Only the CLI's dead-target status (`target_gone`: `target_not_found`,
        `wrong_target`); the registry-unknown case synthesizes the same status.
        `unavailable` (admission refused for now, an unverified peer) is a LIVE
        target and stays on the tick."""
        return result.get("status") == "target_gone"

    def forward(self, event_id):
        """Deliver one just-admitted event now; what is not accepted stays
        `pending` in the checkpoint for the tick."""
        self._attempt(event_id)

    def tick(self):
        """Retry every `pending` retained entry in feed order — the same pass
        at start-up, so a restart inside the grace loses nothing."""
        with StateStore() as store:
            state = store.load()
            retained = ((state or {}).get("checkpoint") or {}).get("retained_events") or {}
            pending = [event_id for event_id, entry in retained.items()
                       if (entry.get("native") or {}).get("state") == "pending"]
        for event_id in pending:
            self._attempt(event_id)

    def _entry(self, event_id):
        with StateStore() as store:
            state = store.load()
            entry = (((state or {}).get("checkpoint") or {}).get("retained_events") or {}).get(event_id)
        return json.loads(json.dumps(entry)) if entry else None

    def _mark(self, event_id, **fields):
        with StateStore() as store:
            state = store.load(require=True)
            entry = (state["checkpoint"].get("retained_events") or {}).get(event_id)
            if entry is None:
                return  # evicted by bounded retention: nothing left to retry
            entry.setdefault("native", {"state": "pending", "attempts": 0}).update(fields)
            store.save(state)

    def _attempt(self, event_id):
        entry = self._entry(event_id)
        native = (entry or {}).get("native") or {}
        if entry is None or native.get("state") != "pending":
            return
        envelope, claim = entry["envelope"], native.get("claim")
        if claim is None:
            result = self._deliver_to_daemon(envelope, owner=None)
            self._settle(event_id, envelope, native, result, self.deliver_to)
            return
        key = lane_key_for(envelope)
        lane_session = claim_lane_ref(claim, envelope.get("lane"))
        target = coordinator_session_for(self.transport, key)
        if target == REGISTRY_LOOKUP_FAILED:
            # The registry did not answer: nothing is known about the owner,
            # so this is a transient on the tick, never a gone coordinator.
            self._settle(event_id, envelope, native, {"status": "error", "error_code": "registry_lookup_failed"}, "registry")
            return
        result = self._send(target, envelope, display_context_for(envelope, self.transport)) if target else {
            "status": "target_gone", "error_code": "coordinator_session_unknown"}
        if self._accepted(result) or self._held(result):
            diag(f"{'forwarded' if self._accepted(result) else 'held'} {envelope.get('event_id')} at coordinator {target} ({envelope.get('lane')})")
            # The operator's copy: the boundary lowers it to notify_only (D22
            # item 1). Best effort — the coordinator already has the message.
            self._deliver_to_daemon(envelope, owner={"lane_session": lane_session, "state": "owned"})
            self._settle(event_id, envelope, native, result, target)
            return
        if self._target_gone(result):
            # D15/D22: the grace is the CLAIM's age, never this listener's wait
            # — a long-dead coordinator's follow-up reaches the daemon on the
            # first attempt; a fresh claim whose lane has not bound its session
            # yet waits on the tick without spending the transient window. An
            # undatable claim is OLD (the D15 rule: it must not deafen a
            # conversation).
            age_s = stamp_age_s(claim.get("claimed_at"))
            if age_s is None or age_s >= self.grace_s:
                diag(f"coordinator for {envelope.get('lane')} is gone ({result.get('error_code')}); handing {envelope.get('event_id')} to the daemon")
                result = self._deliver_to_daemon(envelope, owner={"lane_session": lane_session, "state": "gone"})
                self._settle(event_id, envelope, native, result, self.deliver_to)
            else:
                diag(f"coordinator for {envelope.get('lane')} not reachable yet ({result.get('error_code')}); {envelope.get('event_id')} waits for the tick ({age_s:.0f}s of {self.grace_s:.0f}s grace)")
                self._mark(event_id, error=str(result.get("error_code") or result.get("status")))
            return
        self._settle(event_id, envelope, native, result, target)

    def _settle(self, event_id, envelope, native, result, target):
        """Record one send's outcome. A transient failure stays on the tick
        until the retry window (from the first attempt) has elapsed; then the
        event leaves the queue with a diagnostic — no liveness is asserted,
        the retained record still holds it (`show <event id>`)."""
        attempts = int(native.get("attempts") or 0) + 1
        error = str(result.get("error_code") or result.get("status"))
        if self._accepted(result):
            self._mark(event_id, state="forwarded", attempts=attempts, target=target)
            return
        if self._held(result):
            self._mark(event_id, state="held", attempts=attempts, target=target)
            return
        # The window starts at the first COUNTED attempt, not at admission: an
        # in-grace wait for a lane that has not bound yet sends nothing and
        # must not spend it.
        first_ms = now_ms() if attempts == 1 else int(native["first_ms"])
        elapsed_s = max(0.0, (now_ms() - first_ms) / 1000.0)
        budget_s = native_retry_budget_s(self.grace_s)
        if elapsed_s >= budget_s:
            diag(f"giving up on {envelope.get('event_id')} after {attempts} sends to {target} over {elapsed_s:.0f}s: {error}; it leaves the retry queue (retained, not delivered)")
            self._mark(event_id, state="dropped", attempts=attempts, first_ms=first_ms, error=error)
        else:
            self._mark(event_id, state="pending", attempts=attempts, first_ms=first_ms, error=error)

    def _deliver_to_daemon(self, envelope, owner):
        result = self._send(self.deliver_to, envelope, display_context_for(envelope, self.transport, owner=owner))
        if self._accepted(result) or self._held(result):
            diag(f"{'forwarded' if self._accepted(result) else 'held'} {envelope.get('event_id')} at {self.deliver_to} ({envelope.get('lane')}{', owner ' + owner['state'] if owner else ''})")
        else:
            diag(f"session-message send to {self.deliver_to} failed for {envelope.get('event_id')}: {result.get('status')} {result.get('error_code')}")
        return result


def track_thread(checkpoint, root_ts, cursor_ts, advance_cursor=True):
    entry = checkpoint["tracked_threads"].get(root_ts) or {"cursor": root_ts, "last_active": root_ts}
    # The read cursor may only advance over messages the listener has actually
    # processed. Registering/keeping a thread alive on SEND (advance_cursor
    # False) must not move it past inbound user replies that arrived before the
    # bot's reply — doing so silently drops those replies forever.
    if advance_cursor and float(cursor_ts) > float(entry["cursor"]):
        entry["cursor"] = cursor_ts
    if float(cursor_ts) > float(entry["last_active"]):
        entry["last_active"] = cursor_ts
    checkpoint["tracked_threads"][root_ts] = entry


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_auth(args):
    if args.token_stdin:
        token = validate_token_text(sys.stdin.read().strip(), "stdin")
        token_source = "state"
    else:
        token = None
        token_source = None
    with StateStore() as store:
        state = store.load()  # FR-006/FM-3: fail closed on corrupt/newer state before network
    if token is None:
        token, token_source = resolve_token(state)
    payload, headers = slack_call("auth.test", token)
    scopes = [s for s in (headers.get("x-oauth-scopes") or "").split(",") if s]
    with StateStore() as store:
        state = store.load() or {"schema_version": SCHEMA_VERSION}
        prior_connector = state.get("connector") or {}
        previous_auth = prior_connector.get("auth") or {}
        connector = {
            "id": CONNECTOR_ID,
            "protocol_version": PROTOCOL_VERSION,
            # The token itself is stored only for the manual stdin path; env
            # and auth.json tokens stay in their source. A plain re-auth
            # preserves whatever the stdin path stored earlier.
            "auth": {"bot_token": token} if args.token_stdin else previous_auth,
            "identity": {"team_id": payload.get("team_id"), "bot_user_id": payload.get("user_id")},
            "scopes": scopes,
            "validated_at": utc_now(),
        }
        # Carry the connection down-flag across the rebuild (same replace-vs-merge
        # class as the mailbox register fix): a routine re-auth (token rotation)
        # MUST NOT erase the connected:False a `disconnect` set, or a listener
        # under a persistent Monitor would resurrect a stream the human tore down
        # (FR-002b).
        if "connected" in prior_connector:
            connector["connected"] = prior_connector["connected"]
        state["connector"] = connector
        store.save(state)
    print(
        json.dumps(
            {
                "status": "authenticated",
                "token_source": token_source,
                "team_id": payload.get("team_id"),
                "bot_user_id": payload.get("user_id"),
                "scopes": scopes,
            }
        )
    )
    return 0


NO_IDENTITY_MSG = "no validated identity: run `auth` first"


def require_identity(state, message=NO_IDENTITY_MSG):
    """The single predicate for "this machine has a validated bot identity".
    A caller that wants to name a longer first-run sequence overrides the
    message rather than re-testing the same fields, so what counts as a
    validated identity is defined once."""
    identity = ((state or {}).get("connector") or {}).get("identity") or {}
    if not identity.get("bot_user_id"):
        raise ConnectorError(message)
    return identity


def bind_channel(container_id, owner_user_id=None, require_owner=False):
    """Bind the Slack listener to one channel: join it if needed, check scopes,
    and start the cursor at the channel head so a first listen replays no
    history. Folded into `listen` per D7 — a channel id is not a secret, so
    unlike `auth` it costs no extra foreground call.

    Re-binding the same channel is a cheap no-op on the replay state (the
    existing checkpoint is kept), so a persistent Monitor that restarts the
    listener does not rewind or skip the feed.

    `require_owner` is `--only-owner`'s precondition, resolved HERE under the
    one lock that owns the inheritance rule: checking it from the caller meant
    two copies of that rule and a released flock between check and write, so a
    concurrent rebind could still leave the refused command half-applied."""
    # Binding is a rare startup action: holding the lock across its validation
    # calls is accepted (listen/reply keep network outside the lock instead).
    with StateStore() as store:
        state = store.load(require=True)
        require_identity(state)
        previous = state.get("binding")
        # A later `listen` may drop `--owner` and reuse the stored binding
        # (SKILL.md), so a same-channel rebind INHERITS the recorded owner
        # instead of clearing it. Without this, the documented Slack start
        # rewrote `owner_user_id` to None and downgraded every retained
        # envelope to `is_owner: false` — losing the authority attribution a
        # good bind had established (FR-012). A DIFFERENT channel still starts
        # with whatever owner the caller passed, because its owner is not the
        # old channel's.
        if (
            owner_user_id is None
            and previous
            and previous.get("container_id") == container_id
        ):
            owner_user_id = previous.get("owner_user_id")
        if require_owner and not owner_user_id:
            # Refuse before the join and before any write: the whole point of
            # resolving this inside the lock is that a refused `--only-owner`
            # leaves Slack and state untouched.
            raise InputError(
                "--only-owner needs an owner: pass `listen --channel <C…> --owner <U…>`"
            )
        token, _ = resolve_token(state)
        info, _headers = slack_call("conversations.info", token, {"channel": container_id})
        channel = info["channel"]
        if not channel.get("is_member"):
            if channel.get("is_private"):
                raise ConnectorError("bot is not a member of the private conversation; invite it first")
            slack_call("conversations.join", token, {"channel": container_id})
        container_type = "channel" if not channel.get("is_private") else "private_channel"
        granted = set(state["connector"].get("scopes") or [])
        required = {"chat:write", "groups:history" if channel.get("is_private") else "channels:history"}
        missing_scopes = sorted(required - granted)
        if missing_scopes:
            raise ConnectorError(f"token lacks required scope(s): {', '.join(missing_scopes)}")
        if previous and previous.get("container_id") == container_id and state.get("checkpoint"):
            checkpoint = state["checkpoint"]  # rebind of the same conversation keeps replay state
        else:
            history, _headers = slack_call(
                "conversations.history", token, {"channel": container_id, "limit": 1}
            )
            messages = history.get("messages") or []
            cursor = messages[0]["ts"] if messages else "0"
            checkpoint = fresh_checkpoint(cursor)
        # The channel IS the binding, so its id is the binding id — one fewer
        # value for the caller to invent and keep consistent.
        binding_id = f"slack:{container_id}"
        state["binding"] = {
            "id": binding_id,
            "container_id": container_id,
            "container_type": container_type,
            "owner_user_id": owner_user_id,
        }
        # A rebind may change the owner: frozen retained envelopes must not
        # replay stale authority attribution (FR-012).
        for entry in checkpoint["retained_events"].values():
            envelope = entry["envelope"]
            envelope["binding_id"] = binding_id
            envelope["actor"]["is_owner"] = bool(owner_user_id) and (
                envelope["actor"]["id"] == owner_user_id
            )
        state["checkpoint"] = checkpoint
        store.save(state)
    diag(f"bound {container_id} at cursor {checkpoint['cursor']}")
    return checkpoint["cursor"]


def admit_message(message, state):
    """Return True when a raw Slack message should become an event."""
    checkpoint = state["checkpoint"]
    bot_user_id = state["connector"]["identity"].get("bot_user_id")
    subtype = message.get("subtype")
    if subtype and subtype not in ("thread_broadcast", "file_share"):
        # thread_broadcast is a genuine user reply ("also send to channel");
        # file_share is how live Slack stamps a user message carrying an
        # uploaded file or clip (FR-014); every other subtype (joins, edits,
        # deletions, ...) is not an event.
        return False
    if subtype == "file_share" and not message.get("files"):
        return False
    if message.get("bot_id") or not message.get("user"):
        return False
    if message.get("user") == bot_user_id:
        return False
    if message["ts"] in checkpoint["outbound_ts"]:
        return False
    event_id = f"slack:{state['binding']['container_id']}:{message['ts']}"
    # A redelivered event still dedups even if its id rolled out of the bounded
    # recent FIFO while it is retained. Mirrors the mailbox admission guard
    # (process_cli_item).
    return (
        event_id not in checkpoint["recent_event_ids"]
        and event_id not in checkpoint["retained_events"]
    )


def poll_once(state, token, thread_root=None):
    """One poll cycle against a state SNAPSHOT. Pure network reads; returns
    (candidates, dead_threads). Admission and persistence happen later under
    the lock against freshly reloaded state, so the flock is never held
    across network calls.

    One listener, one scope (FR-025): without --thread this reads the bound
    channel's top-level messages; with --thread it reads exactly that thread.
    The daemon skill composes any topology it wants by running several
    listeners (e.g. one channel monitor plus one monitor per active task
    thread); each listener costs one API call per tick."""
    binding = state["binding"]
    checkpoint = state["checkpoint"]
    container_id = binding["container_id"]
    candidates = []  # (message, thread_root_or_None)
    dead_threads = []
    # One shared transcript-wait budget for the whole poll cycle (FR-23499-2).
    enrich_deadline = transcript_now() + transcript_wait_ms() / 1000.0

    if thread_root is None:
        top_level = sorted(
            fetch_messages(
                "conversations.history",
                token,
                {"channel": container_id, "oldest": checkpoint["cursor"], "limit": 100},
            ),
            key=lambda m: float(m["ts"]),
        )
        for message in top_level:
            enrich_attachments(message, token, enrich_deadline)
            candidates.append((message, None))
        return candidates, dead_threads

    entry = checkpoint["tracked_threads"].get(thread_root)
    thread_cursor = entry["cursor"] if entry else thread_root
    try:
        replies = fetch_messages(
            "conversations.replies",
            token,
            {"channel": container_id, "ts": thread_root, "oldest": thread_cursor, "limit": 100},
        )
    except ApiError as error:
        if error.error_name == "thread_not_found":
            return candidates, [thread_root]  # e.g. the root message was deleted
        raise
    for message in sorted(replies, key=lambda m: float(m["ts"])):
        if message["ts"] == thread_root:
            continue
        enrich_attachments(message, token, enrich_deadline)
        candidates.append((message, thread_root))
    return candidates, dead_threads


def merge_poll_results(
    store, snapshot, candidates, dead_threads, ensure_thread=None, only_owner=False,
    unattended_grace_s=UNATTENDED_GRACE_S_DEFAULT,
):
    """Apply one poll's candidates to freshly reloaded state under the lock.
    Returns the envelopes to emit. With only_owner (FR-23499-6), non-owner
    channel messages are another daemon's responsibility: they are skipped
    without being admitted, but the cursor still advances past them."""
    state = store.load(require=True)
    checkpoint = state["checkpoint"]
    binding = state["binding"]
    if binding["container_id"] != snapshot["binding"]["container_id"]:
        diag("binding changed during the poll; discarding the polled batch")
        return []
    emitted = []
    changed = False
    for message, thread_root in candidates:
        in_thread = message_is_in_thread(message)
        listener_scope_matches = (ensure_thread is None and not in_thread) or (
            ensure_thread is not None and in_thread
        )
        claim_matches = not only_owner or message.get("user") == binding["owner_user_id"]
        admissible = listener_scope_matches and claim_matches and admit_message(message, state)
        envelope = full_text = conversation_claim = unattended_claim = None
        if admissible:
            envelope, full_text = build_envelope(message, binding, binding["container_type"])
            conversation_claim = claim_for(checkpoint, "slack", lane_key_for(envelope))
            if conversation_claim is not None and claim_is_unattended(conversation_claim, unattended_grace_s):
                unattended_claim, conversation_claim = conversation_claim, None  # D15: the daemon's again
            alias = assign_lane(checkpoint, envelope)
            event_id = envelope["event_id"]
            checkpoint["recent_event_ids"].append(event_id)
            checkpoint["retained_events"][event_id] = {"envelope": envelope, "full_text": full_text}
            append_feed(envelope, cursor=message.get("ts"))
            # D11: a claimed conversation never wakes the daemon again; the
            # event is the coordinator's, read from the feed.
            if conversation_claim is None:
                if unattended_claim is not None:
                    note_unattended_emission(unattended_claim)
                    envelope = unattended_envelope(envelope, unattended_claim, alias)
                emitted.append(envelope)
            if thread_root is None:
                track_thread(checkpoint, message["ts"], message["ts"])
            changed = True
        if thread_root is None:
            if float(message["ts"]) > float(checkpoint["cursor"]):
                checkpoint["cursor"] = message["ts"]
                changed = True
        else:
            entry = checkpoint["tracked_threads"].get(thread_root)
            if entry is None and thread_root == ensure_thread:
                # A dedicated thread listener keeps its thread tracked even
                # if bounded eviction dropped the entry meanwhile.
                track_thread(checkpoint, thread_root, thread_root)
                entry = checkpoint["tracked_threads"][thread_root]
                changed = True
            if entry is not None and float(message["ts"]) > float(entry["cursor"]):
                track_thread(checkpoint, thread_root, message["ts"])
                changed = True
    for root_ts in dead_threads:
        if root_ts in checkpoint["tracked_threads"]:
            del checkpoint["tracked_threads"][root_ts]
            diag(f"thread {root_ts} no longer exists; untracking it")
            changed = True
    if changed:
        evict_bounded(checkpoint)
        checkpoint["last_poll_at"] = utc_now()
        store.save(state)  # INV-1: persist before emit
    return emitted


# ---------------------------------------------------------------------------
# Mailbox transport: the `muse-mailbox` CLI (FR-23499-9 / D21, amended; now
# `adr:23499-slack-connector-runtime-contract#D6`)
# The connector shells out to `muse-mailbox` instead of talking HTTP to the Muse
# Code Session Mailbox REST API. The CLI owns the transport, the cursor, and its
# own auth, so NO OAuth token is needed on the worker — the whole point (it
# drops the manual-token dependency on every host). The canonical
# `peer_message` client envelope is unchanged.
# ---------------------------------------------------------------------------


def mailbox_cli():
    return os.environ.get(MAILBOX_CLI_ENV) or MAILBOX_CLI_DEFAULT


def mailbox_cli_state_file():
    configured = os.environ.get(MAILBOX_CLI_STATE_FILE_ENV)
    if configured:
        return configured
    return os.path.join(state_dir(), "mailbox-cli.json")


MAILBOX_ID_MAX = 48  # keep a derived id short enough to read in a chat line


def mailbox_id_slug(raw):
    """Lowercase `raw` to `[a-z0-9-]`, collapsing every other run to one dash."""
    out = []
    for ch in (raw or "").lower():
        if ch.isascii() and (ch.isalnum()):
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")[:MAILBOX_ID_MAX].strip("-")


def login_name():
    """The unixname for the derived mailbox id: USER, then LOGNAME, then the
    passwd entry for this uid (a Monitor-spawned listener can run with a
    scrubbed environment); empty when none answers."""
    name = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    if not name:
        try:
            import pwd

            name = pwd.getpwuid(os.getuid()).pw_name
        except (ImportError, KeyError, OSError):
            name = ""
    return name


def derive_mailbox_id():
    """The default mailbox id, so a bare `listen` needs no id at all (D13).

    `daemon-<unixname>-<short hostname>-1` (owner directive #30502, 2026-09-07,
    verbatim in spec 23499 FR-23499-9): `jakege` on `devvm10856.dkl0…` →
    `daemon-jakege-devvm10856-1`, so the id a human picks in the Slack
    `/connect` list names its owner and its machine. Each part is slugged, an
    empty part is left out (`daemon-<host>-1`, `daemon-<unixname>-1`, at worst
    `daemon-1`), and the stem is capped so the id keeps its `-1` suffix within
    MAILBOX_ID_MAX. The caller PERSISTS the result: macOS hostnames flap
    (DHCP/Wi-Fi renames), and a listener that re-derived a different id every
    restart would abandon its mailbox."""
    user = mailbox_id_slug(login_name())
    host = mailbox_id_slug((os.uname().nodename if hasattr(os, "uname") else "").split(".")[0])
    stem = mailbox_id_slug("-".join(part for part in ("daemon", user, host) if part))
    return stem[: MAILBOX_ID_MAX - 2].rstrip("-") + "-1"


MAILBOX_DISCONNECT_POLL_S = 3  # how often a running mailbox listen re-checks the disconnect flag


def mailbox_disconnect_poll_s():
    """Poll interval for the running mailbox listen's disconnect re-check. Test
    seams (only under the fake-CLI flag) may shorten it so the mid-stream
    disconnect path runs fast; production is always MAILBOX_DISCONNECT_POLL_S so a
    leaked dev-shell value can never alter a real run (FR-020)."""
    raw = os.environ.get("SLACK_CONNECTOR_MAILBOX_DISCONNECT_POLL_S") if mailbox_seams_enabled() else None
    return float(raw) if raw else MAILBOX_DISCONNECT_POLL_S


# #37011: a daemon restarted inside the relay's registration-expiry window is
# refused its OWN mailbox (the previous session's registration is still live;
# real transport: refused 66 s after a clean exit, attached at 94 s). Nothing is
# written at exit — owner ruling: shutdown speed is untouchable, and a clean
# exit, SIGTERM, SIGKILL and a crash are one problem — so the NEXT start reads
# two records the listener writes while it runs: the FR-002b binding
# (`mailbox.client_mailbox_id`) and the mailbox's OWN heartbeat
# (`mailbox.last_poll_at`, while streaming with gaps of no more than
# SELF_HELD_HEARTBEAT_S plus one disconnect poll, and on every admitted message; `checkpoint.last_poll_at` is the Slack
# poller's and both transports share one state.json, so it cannot serve).
# Bound to this id and active within SELF_HELD_FRESH_S → self-held: re-attach
# with backoff inside SELF_HELD_RETRY_WINDOW_S, the ONE knob; anything else →
# foreign-held, the FR-002b (a) refusal unchanged.
SELF_HELD_FRESH_S = 600
SELF_HELD_RETRY_WINDOW_S = 120
SELF_HELD_RETRY_BACKOFF_S = (5, 10, 20, 30)  # then 30 s steps until the window is spent
SELF_HELD_HEARTBEAT_S = 60


def self_held_backoff_schedule():
    """The waits between self-held re-attaches: 5, 10, 20, 30 s, then 30 s
    steps, as many as fit SELF_HELD_RETRY_WINDOW_S (95 s of waiting at the
    defaults). A test seam replaces the list outright."""
    raw = os.environ.get("SLACK_CONNECTOR_SELF_HELD_BACKOFF_S") if mailbox_seams_enabled() else None
    if raw:
        return [float(part) for part in raw.split(",") if part.strip()]
    schedule, total, steps = [], 0.0, list(SELF_HELD_RETRY_BACKOFF_S)
    while True:
        delay = steps.pop(0) if steps else SELF_HELD_RETRY_BACKOFF_S[-1]
        if total + delay > SELF_HELD_RETRY_WINDOW_S:
            return schedule
        schedule.append(delay)
        total += delay


def self_held_heartbeat_s():
    """How often a streaming listener rewrites `mailbox.last_poll_at` at most
    (SELF_HELD_HEARTBEAT_S); a test seam replaces the figure so the first
    tick's write can be proven to be the only one."""
    raw = os.environ.get("SLACK_CONNECTOR_SELF_HELD_HEARTBEAT_S") if mailbox_seams_enabled() else None
    return float(raw) if raw else SELF_HELD_HEARTBEAT_S


def self_held_retrying_line(mailbox_id, age_s, delay_s):
    """The ONE stdout line a self-held retry prints (`outcome` + `next`, the
    shape of the other pre-stream lines): the model learns the hold is its own
    previous session's and that nothing is to be armed. The window figure is
    the one the daemon's `start` hint names too (SELF_HELD_RETRY_WINDOW_S)."""
    return {
        "outcome": "retrying",
        "transport": "mailbox",
        "mailbox_id": mailbox_id,
        "reason": (
            f"mailbox {mailbox_id!r} is held by this host's previous session "
            f"(last active {int(age_s)} s ago); retrying in {delay_s:g} s"
        ),
        "next": (
            f"nothing to arm: this listen retries by itself for up to ~{SELF_HELD_RETRY_WINDOW_S} s and "
            "streams when the hold clears; if it ends refused after that, follow that line's `next`"
        ),
    }


def recent_mailbox_binding(mailbox):
    """`status --json` `mailbox.recent_binding` (#37011): the self-held
    evidence as the daemon's `start` reads it — the bound id, how long ago
    this host's listener was last active, and the connector's re-attach
    window — or None without a binding active within SELF_HELD_FRESH_S. ONE
    verdict, computed here, so the daemon formats and never re-derives it."""
    bound_id = (mailbox or {}).get("client_mailbox_id")
    age = stamp_age_s((mailbox or {}).get("last_poll_at"))
    if not bound_id or age is None or age > SELF_HELD_FRESH_S:
        return None
    return {"mailbox_id": bound_id, "last_active_s": int(age), "retry_window_s": SELF_HELD_RETRY_WINDOW_S}


class SelfHeldRetry:
    """The re-attach budget of one `listen` (#37011): decides ONCE, from the
    records read before this listen wrote anything, whether a held id is this
    host's own dead session, and then serves both refusal paths (`register`
    and the stream) with one schedule and one progress line, so the verdict
    cannot flip to the foreign form mid-window and the two paths cannot
    drift."""

    def __init__(self, mailbox_id, prior_mailbox):
        self.mailbox_id = mailbox_id
        # ONE verdict: the same `recent_mailbox_binding` that `status --json`
        # publishes and the daemon's `start` formats, computed from the
        # pre-write snapshot (review of PR #37071: two copies of the
        # freshness test would let `start` promise `retrying` while `listen`
        # refuses as foreign).
        binding = recent_mailbox_binding(prior_mailbox)
        self.self_held = binding is not None and binding["mailbox_id"] == mailbox_id
        self.age_s = binding["last_active_s"] if binding else 0
        self.schedule = self_held_backoff_schedule()
        self.announced = False
        self.start_ppid = os.getppid()

    def next_step(self):
        """None: a foreign hold, or the window is spent — refuse as before.
        "retry": the wait is done, attach again. "disconnect" / "parent
        death": the wait was cut short by the stop that owns the listener."""
        if not self.self_held or not self.schedule:
            return None
        delay = self.schedule.pop(0)
        if not self.announced:
            self.announced = True
            say_outcome(self_held_retrying_line(self.mailbox_id, self.age_s, delay))
        diag(f"mailbox {self.mailbox_id!r} is held by this host's previous session "
             f"(last active {int(self.age_s)} s ago); retrying in {delay:g} s")
        deadline = time.monotonic() + delay
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return "retry"
            time.sleep(min(remaining, mailbox_disconnect_poll_s()))
            if os.getppid() != self.start_ppid:
                return "parent death"
            if mailbox_connection_disconnected():
                return "disconnect"


# #41206 (owner ruling 39, ADR 25011 reconnect node): a mailbox listener whose
# stream dies (EOF, a child that exits, a hang the probe confirms) never gives
# up while the id is still this host's. It re-attaches in-process on a fixed
# backoff capped at RECONNECT_BACKOFF_CAP_S, says ONE stdout line once the
# relay has been unreachable for RECONNECT_UNREACHABLE_AFTER_S and ONE line
# when it is back, and stops only for a foreign holder, a `disconnect`, or the
# owner's death. A quiet stream is not a dead one: after
# MAILBOX_IDLE_PROBE_S without a line, one cheap relay read decides.
RECONNECT_BACKOFF_S = (2, 5, 10, 30, 60)
RECONNECT_BACKOFF_CAP_S = 60
RECONNECT_UNREACHABLE_AFTER_S = 120
MAILBOX_IDLE_PROBE_S = 90
# A stream child that outlives this window is ATTACHED (the relay took the
# stream) even when no line arrived: longer than the relay's observed refusal
# latency (~2 s after the attach, #37011), so a refusal never reads as a
# served stream; a line attaches at once.
MAILBOX_ATTACH_SETTLE_S = 5
# The name a human says to end the listener while it is unreachable
# (the daemon's connector id, `intent set --connector <id> --desired disabled`).
DAEMON_CONNECTOR_ID = "slack-connector"
MAILBOX_DELAY_LOG_ENV = "SLACK_CONNECTOR_MAILBOX_DELAY_LOG"
# Under the delay-log seam the ladder's clock is PURELY the waits it skipped
# (real time never leaks in), so "down N s" and "after N min" are exact
# functions of the logged waits — a test asserts them causally, never against
# how long the host took to spawn the fake (#25315). Production reads
# `time.monotonic()`.
_MAILBOX_VIRTUAL_OFFSET_S = 0.0


def mailbox_delay_log():
    """The ladder's sleep seam (fake CLI only): a file the ladder appends each
    backoff to instead of sleeping it. Production never skips a wait."""
    return os.environ.get(MAILBOX_DELAY_LOG_ENV) if mailbox_seams_enabled() else None


def reconnect_clock():
    if mailbox_delay_log():
        return _MAILBOX_VIRTUAL_OFFSET_S
    return time.monotonic()


def reconnect_backoff_schedule():
    """2, 5, 10, 30, 60 s, then 60 s for ever (no bound, no give-up); a test
    seam replaces the ramp (the last value repeats)."""
    raw = os.environ.get("SLACK_CONNECTOR_RECONNECT_BACKOFF_S") if mailbox_seams_enabled() else None
    ramp = [float(part) for part in raw.split(",") if part.strip()] if raw else list(RECONNECT_BACKOFF_S)
    ramp = ramp or list(RECONNECT_BACKOFF_S)
    cap = ramp[-1] if raw else RECONNECT_BACKOFF_CAP_S
    for delay in ramp:
        yield min(delay, cap)
    while True:
        yield cap


def reconnect_unreachable_after_s():
    raw = os.environ.get("SLACK_CONNECTOR_RECONNECT_UNREACHABLE_AFTER_S") if mailbox_seams_enabled() else None
    return float(raw) if raw else RECONNECT_UNREACHABLE_AFTER_S


def mailbox_idle_probe_s():
    raw = os.environ.get("SLACK_CONNECTOR_MAILBOX_IDLE_PROBE_S") if mailbox_seams_enabled() else None
    return float(raw) if raw else MAILBOX_IDLE_PROBE_S


def mailbox_attach_settle_s():
    raw = os.environ.get("SLACK_CONNECTOR_MAILBOX_SETTLE_S") if mailbox_seams_enabled() else None
    return float(raw) if raw else MAILBOX_ATTACH_SETTLE_S


def mailbox_unreachable_line(mailbox_id, since):
    return {
        "outcome": "retrying",
        "transport": "mailbox",
        "mailbox_id": mailbox_id,
        "reason": f"mailbox unreachable since {since}, still retrying; `stop {DAEMON_CONNECTOR_ID}` ends it",
        "next": (
            "nothing to arm: this listen keeps re-attaching by itself and says one line when it is back; "
            "tell your human this line once; `disconnect --transport mailbox` ends it"
        ),
    }


def mailbox_reconnected_line(mailbox_id, minutes):
    return {
        "outcome": "reconnected",
        "transport": "mailbox",
        "mailbox_id": mailbox_id,
        "reason": f"reconnected after {minutes} min, catching up",
        "next": "nothing to arm: the stream is live again and the messages sent meanwhile arrive now; tell your human in one line",
    }


# #41206 (owner ruling 41): only a TRANSIENT cause enters the ladder — a
# network failure, a timeout, a relay 5xx, an expired registration (made
# again under the same id), a child that simply ended. A cause that a retry
# cannot cure stops the listener at once with today's exit code: the relay
# rejecting this client's credential, a broken install or configuration, a
# foreign holder (`mailbox_conflict_held`, classified first). Unknown wording
# is transient: the listener never gives up on a cause it cannot name.
AUTH_FAILURE_MARKERS = (
    "unauthorized", "forbidden", "not authenticated", "authentication failed",
    "invalid token", "token_expired", "certificate", "x509", "permission denied",
)
# The HTTP status words stand alone (`\b`): a port or an id that merely
# contains `401` must not stop the listener (review of PR #41268).
AUTH_STATUS_RE = re.compile(r"\b40[13]\b")
CONFIG_FAILURE_MARKERS = (
    "cli not found", "no such file or directory", "usage:", "unrecognized arguments",
    "invalid choice", "no such option", "state belongs to another mailbox",
)
# The one command a human runs once the named cause is fixed (ADR 25011 D21:
# the daemon's restart re-arms the listener; ruling 27: it retries a
# remembered failure once).
REARM_COMMAND = "/daemon"


def stream_death_class(last_line):
    """`"held"`, `"auth"`, `"config"` or `"transient"` for the CLI's last
    stderr line (or the connector's own register diagnostic)."""
    text = (last_line or "").strip().lower()
    if mailbox_conflict_held(text):
        return "held"
    if AUTH_STATUS_RE.search(text) or any(marker in text for marker in AUTH_FAILURE_MARKERS):
        return "auth"
    if any(marker in text for marker in CONFIG_FAILURE_MARKERS):
        return "config"
    return "transient"


def mailbox_stopped_line(mailbox_id, reason, cause_class):
    """The ONE stdout line for a stop the ladder does not cover (ruling 41):
    `stopped: <reason>` and the one command that fixes it. `outcome: failed`
    keeps the ended record and the daemon's stale row (ruling 27) as today."""
    fix = (
        f"renew the credential `muse-mailbox` uses (the cert or token the reason names), then `{REARM_COMMAND}` re-arms this listen"
        if cause_class == "auth" else
        f"fix what the reason names (the muse-mailbox install or its configuration), then `{REARM_COMMAND}` re-arms this listen"
    )
    return {
        "outcome": "failed",
        "transport": "mailbox",
        "mailbox_id": mailbox_id,
        "reason": f"stopped: {reason}",
        "next": f"tell your human in one line: the reason, and that {fix}; do not re-arm it yourself",
    }


def mailbox_listener_row(mailbox, listener):
    """The durable row text the daemon shows for this transport (ruling 41),
    derived from the connector's own records: `connected` for a live stream,
    `reconnecting since <t> (attempt n, last error: <e>, next try in Ns)`
    while the live listener is on its ladder, `stopped: <reason>` for an
    ended listener (its ended record's reason, or `disconnected` after a
    `disconnect`), None when the transport never ran or ended clean."""
    if listener.get("listener") == "live":
        ladder = mailbox.get("reconnecting")
        if isinstance(ladder, dict) and ladder.get("since"):
            return (
                f"reconnecting since {ladder['since']} (attempt {ladder.get('attempt', 0)}, "
                f"last error: {ladder.get('last_error') or 'unknown'}, next try in {ladder.get('next_try_s', 0):g} s)"
            )
        return "connected"
    if listener.get("listener") == "absent":
        if listener.get("exit") is not None:
            reason = listener.get("reason") or "exit %s" % listener["exit"]
            return reason if reason.startswith("stopped: ") else f"stopped: {reason}"
        if mailbox.get("client_mailbox_id") and mailbox.get("connected") is False:
            return "stopped: disconnected"
    return None


def set_mailbox_reconnecting(mailbox_id, ladder):
    """`mailbox.reconnecting` (`{"since", "attempt", "last_error",
    "next_try_s"}`, the daemon row's `reconnecting since <t> (...)` through
    `status --json`): written before every ladder wait, dropped when the
    stream is back or the listen ends; only while the record is this id's."""
    with StateStore() as store:
        state = store.load()
        mailbox = (state or {}).get("mailbox") or {}
        if not state or mailbox.get("client_mailbox_id") != mailbox_id:
            return
        if ladder is None:
            if "reconnecting" not in mailbox:
                return
            mailbox.pop("reconnecting", None)
        else:
            mailbox["reconnecting"] = ladder
        store.save(state)


class ReconnectLadder:
    """One outage of the mailbox stream (#41206): its start on the ladder's
    clock, the backoff ramp, whether the unreachable line was said, and the
    held budget (`self_held_backoff_schedule`, the SelfHeldRetry window
    unchanged) a run of consecutive conflict refusals spends before the id
    counts as another client's."""

    def __init__(self, mailbox_id, start_ppid):
        self.mailbox_id = mailbox_id
        self.start_ppid = start_ppid
        self.started_at = reconnect_clock()
        self.since = utc_now()
        self.said_unreachable = False
        self.schedule = reconnect_backoff_schedule()
        self.hold_budget = None
        self.attempts = 0
        self.last_error = None

    def down_for_s(self):
        return reconnect_clock() - self.started_at

    def delay_for(self, held):
        """The next wait, or None when a held refusal outlived the budget."""
        if not held:
            self.hold_budget = None
            return next(self.schedule)
        if self.hold_budget is None:
            self.hold_budget = self_held_backoff_schedule()
        if not self.hold_budget:
            return None
        return self.hold_budget.pop(0)

    def say_unreachable_if_due(self):
        if not self.said_unreachable and self.down_for_s() >= reconnect_unreachable_after_s():
            self.said_unreachable = True
            say_outcome(mailbox_unreachable_line(self.mailbox_id, self.since))

    def wait(self, delay):
        """Wait `delay` s, saying the unreachable line the moment it is due;
        "retry" when the wait is done, "disconnect" / "parent death" when the
        stop that owns the listener cut it short (checked every disconnect
        poll on real sleeps, once per skipped wait under the delay-log seam)."""
        global _MAILBOX_VIRTUAL_OFFSET_S
        self.attempts += 1
        set_mailbox_reconnecting(self.mailbox_id, {
            "since": self.since, "attempt": self.attempts,
            "last_error": self.last_error, "next_try_s": delay,
        })
        log = mailbox_delay_log()
        if log:
            with open(log, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(delay) + "\n")
        deadline = reconnect_clock() + delay
        while True:
            self.say_unreachable_if_due()
            remaining = deadline - reconnect_clock()
            if remaining <= 0:
                return "retry"
            chunk = remaining if log else min(remaining, mailbox_disconnect_poll_s())
            if not self.said_unreachable:
                to_line = self.started_at + reconnect_unreachable_after_s() - reconnect_clock()
                if 0 < to_line < chunk:
                    chunk = to_line
            if log:
                _MAILBOX_VIRTUAL_OFFSET_S += chunk
            else:
                time.sleep(chunk)
            if os.getppid() != self.start_ppid:
                return "parent death"
            if mailbox_connection_disconnected():
                return "disconnect"

    def recovered(self):
        """The stream is attached again: the row's record goes; the reconnected
        line is said only after the unreachable line was (a short blip says
        nothing), with the outage in whole minutes."""
        minutes = max(1, int((self.down_for_s() + 30) // 60))
        set_mailbox_reconnecting(self.mailbox_id, None)
        if self.said_unreachable:
            say_outcome(mailbox_reconnected_line(self.mailbox_id, minutes))


def restore_mailbox_heartbeat(mailbox_id, prior_last_poll_at):
    """#37011 (review of PR #37071): a held refusal never streamed, but the
    disconnect-poll tick may already have written `mailbox.last_poll_at`
    while the relay's refusal was in flight; left standing, a FOREIGN hold
    would read as this host's own session on the next listen and the one id
    FR-002b (a) says never to retry would be retried. Put the pre-read stamp
    back, only while the record still names this id (the guard
    `restore_mailbox_record` uses)."""
    with StateStore() as store:
        state = store.load()
        mailbox = (state or {}).get("mailbox") or {}
        if not state or mailbox.get("client_mailbox_id") != mailbox_id:
            return
        if prior_last_poll_at is None:
            mailbox.pop("last_poll_at", None)
        else:
            mailbox["last_poll_at"] = prior_last_poll_at
        store.save(state)


def touch_mailbox_heartbeat():
    """#37011: the mailbox listener's own heartbeat, `mailbox.last_poll_at`
    (never the Slack poller's `checkpoint.last_poll_at`), written while
    streaming with gaps of no more than SELF_HELD_HEARTBEAT_S plus one
    disconnect poll; the next start reads it to
    tell its own previous session from a foreign holder. Nothing at exit."""
    with StateStore() as store:
        state = store.load()
        if not state or not state.get("mailbox"):
            return
        state["mailbox"]["last_poll_at"] = utc_now()
        store.save(state)


def mailbox_connection_disconnected():
    """True when `disconnect` has marked this mailbox connection down, so a running
    `listen` can self-terminate (the CLI has no release verb to break the stream)."""
    with StateStore() as store:
        state = store.load()
    return bool(state and (state.get("mailbox") or {}).get("connected") is False)


def restore_mailbox_record(prior_mailbox, attempted_id, state_file=None):
    """Undo the pre-`register` `connected`/`client_mailbox_id` write when the
    register that was supposed to justify it failed.

    Left standing, that write advertises a live connection to a mailbox this
    process never held, and the FR-002b no-clobber guard then defends the
    phantom: the operator's follow-up `listen --mailbox-id <other>` is refused
    with "still connected; run `disconnect`". Restores only while the record
    still names THIS attempt's id, so a concurrent `disconnect` or a newer
    `listen` that already moved on is not clobbered.

    #30326: the CLI binds `state_file` to `attempted_id` BEFORE its request, so
    a held/409 or a transport failure leaves the file naming an id the
    restored record will not, and the hinted re-arm under another id (or a
    bare `listen`) was then refused locally — `mailbox state belongs to
    another mailbox` — for good. When the record rolls back to a different id
    (or to none) the file goes aside here, inside the same guard and lock:
    rename first, then save, so a crash between the two leaves the attempted
    id's `connected` record (FR-002b's `disconnect` + re-arm recovers it) and
    never a bound file no record names (nothing recovers that). A retry of the
    record's own id keeps its file, which is bound to that very id; a newer
    listener's file (the early return above) is never touched."""
    with StateStore() as store:
        state = store.load()
        if not state:
            return
        if (state.get("mailbox") or {}).get("client_mailbox_id") != attempted_id:
            return
        prior_id = (prior_mailbox or {}).get("client_mailbox_id")
        if state_file and prior_id != attempted_id:
            # One stderr line ties the refusal to the file set aside — #30326
            # was triaged by reading exactly that file (review of PR #30339).
            diag(
                f"register of {attempted_id!r} failed after the CLI bound its state file; "
                f"setting it aside (the record rolls back to {prior_id!r})"
            )
            reset_mailbox_cli_state(state_file)
        if prior_mailbox:
            state["mailbox"] = prior_mailbox
        else:
            state.pop("mailbox", None)
        store.save(state)


def reset_mailbox_cli_state(state_file):
    """Reset the connector-OWNED muse-mailbox CLI --state-file. The connector picks
    where the CLI keeps its state, so clearing a dead prior-run's file is the
    connector's own layer, not a reach into a foreign file (finding #7): a stale
    file bound to a DIFFERENT mailbox id would make the CLI refuse to reattach a
    new id (a LOCAL conflict, not a remote 409). A `register` that failed after
    the CLI bound the file to the attempted id leaves the same state (#30326).
    The cursor there is throwaway (the skill is unreleased). Renamed aside (not
    deleted) for post-mortem."""
    if not os.path.exists(state_file):
        return
    try:
        os.replace(state_file, state_file + ".stale")
    except OSError:
        try:
            os.remove(state_file)
        except OSError:
            pass


def mailbox_cli_hint_args(args):
    """Optional register/listen hints as muse-mailbox CLI flags. The CLI takes
    --session-hint and --workspace-hint; unset hints are omitted."""
    hint_args = []
    session_hint = getattr(args, "session_name_hint", None)
    if session_hint:
        hint_args += ["--session-hint", session_hint]
    workspace_hint = getattr(args, "workspace_hint", None)
    if workspace_hint:
        hint_args += ["--workspace-hint", workspace_hint]
    return hint_args


def mailbox_register_timeout_s():
    """Bound for the listener's one-shot register. Test seams (only under the
    fake-CLI flag) may move it so a parked register outlives the test's own
    subprocess steps under host load (#38350); production is always
    MAILBOX_REGISTER_TIMEOUT_S so a leaked dev-shell value can never alter a
    real run (FR-020)."""
    raw = os.environ.get("SLACK_CONNECTOR_MAILBOX_REGISTER_TIMEOUT_S") if mailbox_seams_enabled() else None
    return float(raw) if raw else MAILBOX_REGISTER_TIMEOUT_S


def mailbox_tag_retry_delay_s():
    """Pause between tag-publication attempts. A test seam (fake CLI only, per
    `mailbox_seams_enabled`) may zero it; production always waits so a retry
    can outlast a directory blip rather than burning all attempts inside one
    (FR-020, same seam discipline as `mailbox_register_timeout_s`)."""
    raw = os.environ.get("SLACK_CONNECTOR_MAILBOX_TAG_RETRY_DELAY_S") if mailbox_seams_enabled() else None
    return float(raw) if raw is not None else MAILBOX_TAG_RETRY_DELAY_S


def run_mailbox_cli(cli, cli_args, timeout=None):
    """Run a one-shot `muse-mailbox` subcommand and return the CompletedProcess.
    A missing CLI or a timeout surfaces as a fail-closed ConnectorError rather
    than a raw traceback (INV-3: the diagnostic stays secret-free); the timeout
    names the bound it used, so a failure line says how long the CLI had."""
    bound = HTTP_TIMEOUT_S if timeout is None else timeout
    try:
        return subprocess.run(
            [cli, *cli_args],
            capture_output=True, text=True,
            timeout=bound,
        )
    except FileNotFoundError:
        raise ConnectorError(f"muse-mailbox CLI not found: {cli!r} (set {MAILBOX_CLI_ENV})")
    except subprocess.TimeoutExpired:
        raise ConnectorError(f"muse-mailbox CLI timed out after {float(bound):g} s")


def probe_mailbox_cli_capabilities(cli):
    """`adr:23499-slack-connector-runtime-contract#D20` item 1: what THIS
    `muse-mailbox` can do, read from its own `--help` (no network): `edit
    --help` exits 0 only on a CLI that has the verb (the installed 2026-09-02
    build answers with argparse's `invalid choice`, exit 2), and `send --help`
    names `--attach` only once the attachment stack is in. A missing binary or
    a hung probe reads as neither — unsure means OFF."""
    def help_of(verb):
        try:
            run = subprocess.run(
                [cli, verb, "--help"], capture_output=True, text=True, timeout=MAILBOX_PROBE_TIMEOUT_S,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None, ""
        return run.returncode, run.stdout or ""
    edit_rc, _ = help_of("edit")
    send_rc, send_help = help_of("send")
    return {
        "edit": edit_rc == 0,
        "attach": send_rc == 0 and "--attach" in send_help,
        "cli": cli,
    }


def probe_mailbox_listing(cli):
    """Read the one directory snapshot shared by registration and relay discovery."""
    try:
        run = subprocess.run(
            [cli, "list", "--all"],
            capture_output=True,
            text=True,
            timeout=MAILBOX_PROBE_TIMEOUT_S,
        )
        listing = json.loads(run.stdout) if run.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    return (
        listing
        if isinstance(listing, dict) and isinstance(listing.get("data"), list)
        else None
    )


def probe_relay_ui_versions(cli):
    """ADR 35345 D15 item 1 / D2 Amendment 1: one bounded `list --all` at
    listener registration — the mailbox ids visible to this employee and the
    `custom.slack.ui` versions each advertises — so a `reply` knows without
    a network call whether the lane's relay takes a version 2 card. Every
    listed mailbox is recorded — `[]` for one that advertises no UI, so the
    capability line can say `cards: no` from the listing (ruling 25) and an
    unlisted relay stays unknown. Any failure (no verb, timeout, malformed
    output) reads as nothing learned: every relay is version 1 until the
    next registration."""
    return relay_ui_versions_from_listing(probe_mailbox_listing(cli))


def relay_ui_versions_from_listing(listing):
    versions = {}
    for entry in (listing or {}).get("data") or [] if isinstance(listing, dict) else []:
        if not isinstance(entry, dict) or not isinstance(entry.get("client_mailbox_id"), str):
            continue
        found = sorted({cap.get("version") for cap in ((entry.get("metadata") or {}).get("capabilities") or [])
                        if isinstance(cap, dict) and cap.get("name") == "custom.slack.ui"
                        and isinstance(cap.get("version"), int)})
        versions[entry["client_mailbox_id"]] = found
    return versions


def publish_daemon_skill_tags(cli, mailbox_id, state_file, hint_args, listing):
    """Preserve owner labels while publishing this endpoint's agent role and origin."""
    rows = [] if listing is None else listing["data"]
    own = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("client_mailbox_id") == mailbox_id
    ]
    if len(own) != 1:
        raise ConnectorError(
            "could not read this mailbox's current tags; retry registration"
        )
    metadata = own[0].get("metadata")
    if metadata is None:
        metadata = {}
    tags = metadata.get("tags", []) if isinstance(metadata, dict) else None
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise ConnectorError(
            "mailbox returned invalid tags; preserved existing metadata"
        )
    merged = list(dict.fromkeys([*tags, *DAEMON_SKILL_MAILBOX_TAGS]))
    if len(merged) > 32:
        raise ConnectorError(
            "mailbox has no room for agent and daemon-skill tags; remove an unused owner tag"
        )
    if merged == tags:
        return merged
    help_result = run_mailbox_cli(
        cli, ["register", "--help"], timeout=MAILBOX_PROBE_TIMEOUT_S
    )
    if help_result.returncode != 0 or not re.search(
        r"(?<![\w-])--tag(?:\s|=|$)", help_result.stdout
    ):
        raise ConnectorError(
            "muse-mailbox does not support registration tags; use the current deployed CLI"
        )
    # --tag replaces the complete tag set; reuse the current directory snapshot.
    argv = [
        "register",
        "--mailbox-id",
        mailbox_id,
        "--state-file",
        state_file,
        *hint_args,
    ]
    for tag in merged:
        argv += ["--tag", tag]
    result = run_mailbox_cli(cli, argv, timeout=mailbox_register_timeout_s())
    if result.returncode != 0:
        raise ConnectorError(
            f"mailbox tag publication failed (exit {result.returncode}); retry registration"
        )
    return merged


def relay_ui_versions(state, relay):
    """The cached verdict for one relay mailbox id: its advertised versions, `[]` when unknown."""
    return list((((state or {}).get("mailbox") or {}).get(RELAY_UI_VERSIONS_KEY) or {}).get(relay) or [])


def cards_line(state, lane):
    """Ruling 25: the lane's card capability as one plain value. A Slack-direct
    lane and a mailbox lane the relay did not originate carry no cards
    (`ui_needs_relay_lane`); a relay lane reads the cached probe — version 2,
    version 1, listed without UI, or not listed at all (never a guess)."""
    route = (lane or {}).get("route") or {}
    if route.get("transport") != "mailbox":
        return CARDS_NONE_SLACK
    if not (lane or {}).get("relay"):
        return CARDS_NONE_MAILBOX
    cache = ((state or {}).get("mailbox") or {}).get(RELAY_UI_VERSIONS_KEY) or {}
    relay = route.get("target_client_mailbox_id")
    if relay not in cache:
        return CARDS_UNVERIFIED
    versions = cache.get(relay) or []
    if 2 in versions:
        return CARDS_V2
    if 1 in versions:
        return CARDS_V1
    return CARDS_NONE_MAILBOX


def reply_shape_line(cards, alias):
    """The one-sentence reply shape for `cards` (#41245): the card sentence for
    any lane a card can reach (version 2, version 1, or unverified — a card
    goes out as version 1), the plain-text sentence for `no — …`."""
    template = REPLY_SHAPE_NO_CARDS if str(cards).startswith("no") else REPLY_SHAPE_CARDS
    return template.format(lane=alias)


def learn_relay_ui_disabled(mailbox, relay, version):
    """A post the relay answered `unavailable · disabled` is this identity's
    verdict for that version and every higher one (ruling 25): drop them from
    the cached facts so the next card takes what the relay does serve — the
    next registration re-probes. Returns the `next` sentence for the line."""
    cache = (mailbox or {}).setdefault(RELAY_UI_VERSIONS_KEY, {}) if isinstance(mailbox, dict) else {}
    if isinstance(cache, dict):
        cache[relay] = [v for v in (cache.get(relay) or []) if v < version]
    return UI_V2_DISABLED_NEXT if version == 2 else UI_V1_DISABLED_NEXT


def capability_rejected(run, name):
    """The same fact the registration probe reads from `--help` — the verb or
    flag is absent from this CLI — read at reply time from argparse's own
    words (review round 2 of #30528): only a rejection that NAMES the
    capability, `invalid choice: 'edit'` / `unrecognized arguments: --attach`,
    means the CLI lacks it. Every other non-zero exit, exit 2 included (a
    usage error on some other argument), is an ordinary send failure."""
    if run.returncode != 2:
        return False
    stderr = run.stderr or ""
    needle = "invalid choice: 'edit'" if name == "edit" else "unrecognized arguments: --attach"
    return needle in stderr


def clear_mailbox_capability(name):
    """The CLI rejected the verb/flag at reply time (argparse exit 2): the
    cached verdict was stale (a rolled-back or re-pointed CLI). Flip it OFF so
    the next call does not fail the same way (D20 item 1)."""
    with StateStore() as store:
        state = store.load()
        caps = ((state or {}).get("mailbox") or {}).get("cli_capabilities")
        if isinstance(caps, dict):
            caps[name] = False
            store.save(state)
    diag(f"muse-mailbox rejected `{name}`; the cached {name} verdict is cleared")


def mailbox_capability(name):
    """The cached verdict for `edit` / `attach` (D20 item 1), keyed by the
    resolved CLI path. The listener probes at registration and persists it; a
    one-shot `reply` reads it here and probes only when there is none for the
    configured CLI (a re-pointed `SLACK_CONNECTOR_MAILBOX_CLI` re-probes), so a
    reply never pays a CLI start-up per call. The verdict is the whole rule
    (#30562): no environment variable opts in or forces off."""
    cli = mailbox_cli()
    with StateStore() as store:
        state = store.load()
        caps = ((state or {}).get("mailbox") or {}).get("cli_capabilities")
    if isinstance(caps, dict) and caps.get("cli") == cli and isinstance(caps.get(name), bool):
        return caps[name]
    caps = probe_mailbox_cli_capabilities(cli)
    with StateStore() as store:
        state = store.load()
        if state is not None:
            mailbox = state.get("mailbox") or {}
            mailbox["cli_capabilities"] = caps
            state["mailbox"] = mailbox
            store.save(state)
    return bool(caps.get(name))


try:  # Linux-only parent-death binding for the streaming CLI child (#27885)
    import ctypes

    _LIBC = ctypes.CDLL(None, use_errno=True) if sys.platform == "linux" else None
except Exception:  # ctypes absent or libc unresolvable: the ppid poll alone covers it
    _LIBC = None


def _bind_child_to_our_death(listener_pid):
    """`preexec_fn` for the streaming CLI child (#27885). On Linux, ask the
    kernel to SIGTERM the child when THIS listener dies (PR_SET_PDEATHSIG), so
    an uncatchable kill of the listener cannot leave `muse-mailbox listen`
    consuming the stream with nobody reading it. SIGTERM rather than SIGKILL:
    where `python3` is a forking shim, the shim is the process the kernel
    signals, and it forwards a catchable signal to the real CLI but cannot
    forward SIGKILL. Best-effort (an exotic seccomp profile must not turn a
    lifetime binding into a spawn outage); the ppid re-check closes the window
    where the listener died before the prctl ran."""
    if _LIBC is None:
        return
    try:
        _LIBC.prctl(1, signal.SIGTERM, 0, 0, 0)  # PR_SET_PDEATHSIG == 1
        if os.getppid() != listener_pid:
            os._exit(1)
    except Exception:
        pass


def _terminate_child(proc):
    """Best-effort stop of the streaming listen subprocess on any exit path."""
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


# --- TBH-owned client envelope (opaque to the provider) --------------------


MAILBOX_EVENT_ID_PREFIX = "mailbox:"


def mailbox_event_id(sender_mailbox_id, message_id):
    """Dedup key (sender mailbox id, message id) folded into the event id — the
    doc's receiver-side dedup rule. The parts are JSON-encoded (not colon-joined)
    so a colon inside either field cannot make two distinct (sender, message_id)
    pairs collide: sender `s:1`+msg `m` and sender `s`+msg `1:m` stay distinct."""
    return MAILBOX_EVENT_ID_PREFIX + json.dumps([sender_mailbox_id, message_id], separators=(",", ":"))


def canonical_event_id(value):
    """The ONE rendering of a mailbox event id: `mailbox:` + the compact JSON
    list `mailbox_event_id` mints. ADR 37480 D1 rule 1 (#37480): the daemon
    compares event ids by bytes only, so this connector canonicalises its own
    before emitting one (`delegate`) or looking one up (`show`) — a shell
    transcription (`\\"` typed for `"`), an outer-quoted id, or a re-spaced
    list names the same event (#27868, which the daemon used to refuse). Any
    other id, and any `mailbox:` id that does not decode to two strings, is
    returned untouched."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        text = text[1:-1]
    text = text.replace('\\"', '"')
    if not text.startswith(MAILBOX_EVENT_ID_PREFIX):
        return value
    try:
        parts = json.loads(text[len(MAILBOX_EVENT_ID_PREFIX):])
    except ValueError:
        return value
    if isinstance(parts, list) and len(parts) == 2 and all(isinstance(part, str) for part in parts):
        return mailbox_event_id(parts[0], parts[1])
    return value


def occurred_at_from_ms(ms):
    try:
        seconds = int(ms) / 1000.0
        return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OverflowError, OSError):
        # A provider timestamp out of datetime's range must not crash the
        # listener; fall back to now (the transport time is best-effort).
        return utc_now()


def message_id_from_key(idempotency_key):
    """Stable message id from the idempotency key. The connector passes this to the
    CLI as `--message-id` (and keeps it in the receipt), so a crash/retry or a
    concurrent same-key send reuses the id and the receiver dedups on
    `(sender, message_id)`."""
    return "muse-" + hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:32]


def validate_client_envelope(client_env):
    """Validate a decoded TBH client envelope BEFORE admission against the
    canonical `peer_message` shape: size, version, and a `body` dict with
    `kind=="peer_message"`, a non-empty `text` str, and the exact
    `delivery_policy`/`wake_policy` values. `client_env` is the already-decoded
    object the `muse-mailbox` CLI hands back under `payload_json`. Returns the
    dict, or raises InputError to fail closed. Role admission is the caller's
    decision."""
    if not isinstance(client_env, dict):
        raise InputError("client envelope must be a JSON object; failing closed")
    # The CLI can deliver decoded envelopes through its 16 MiB attachment carrier.
    encoded = json.dumps(client_env, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    if len(encoded) > CLIENT_RECEIVED_PAYLOAD_MAX_BYTES:
        raise InputError(
            f"client payload exceeds {CLIENT_RECEIVED_PAYLOAD_MAX_BYTES} bytes; failing closed"
        )
    if client_env.get("version") != CLIENT_ENVELOPE_VERSION:
        raise InputError(f"unsupported client envelope version {client_env.get('version')!r}; failing closed")
    body = client_env.get("body")
    if not isinstance(body, dict):
        raise InputError("client envelope body must be a JSON object; failing closed")
    if body.get("kind") != PEER_MESSAGE_KIND:
        raise InputError(f"client envelope body.kind {body.get('kind')!r} is not {PEER_MESSAGE_KIND!r}; failing closed")
    text = body.get("text")
    if not isinstance(text, str) or not text.strip():
        raise InputError("client envelope body.text must be a non-empty string; failing closed")
    # conversation_id is optional but, when present, must be a string: a hostile
    # peer could send a non-string (e.g. 1e400 → float Infinity) that
    # normalize_client_envelope carries into the envelope, making json.dumps emit
    # the bare token `Infinity` — invalid JSON on the listener's stdout (INV-2).
    conversation_id = body.get("conversation_id")
    if conversation_id is not None and not isinstance(conversation_id, str):
        raise InputError("client envelope body.conversation_id must be a string; failing closed")
    # Policy-value gate: only the canonical delivery/wake policies are admitted.
    if body.get("delivery_policy") != PEER_DELIVERY_POLICY or body.get("wake_policy") != PEER_WAKE_POLICY:
        raise InputError(
            "client envelope body carries a non-canonical delivery_policy/wake_policy; failing closed"
        )
    return client_env


def attachment_from_reference(ref):
    """One `muse_attachment` logical reference (the Session Mailbox stack's shape,
    plus the CLI's `local_path` stamp once it materialised the file) as the
    envelope's bounded metadata — FR-23499-1's shape, no digest, no bytes."""
    if not isinstance(ref, dict):
        return None
    content = ref.get("content")
    if not isinstance(content, dict) or content.get("scheme") != ATTACHMENT_SCHEME:
        return None
    attachment_id, name = content.get("attachment_id"), ref.get("filename")
    if not isinstance(attachment_id, str) or not attachment_id or not isinstance(name, str) or not name:
        return None
    kind = ref.get("kind")
    # FR-23499-1's one key set on both transports: `file_id` carries the
    # mailbox attachment id the way `name`/`mime`/`size` carry the CLI's
    # `filename`/`content_type`/`byte_size` (review of #30528).
    meta = {
        "file_id": attachment_id,
        "kind": kind if kind in ("image", "video", "file") else "file",
        "name": marker_name(name),
    }
    mime, size = ref.get("content_type"), ref.get("byte_size")
    if isinstance(mime, str) and mime:
        meta["mime"] = mime[:100]
    if isinstance(size, int) and not isinstance(size, bool) and size >= 0:
        meta["size"] = size
    local_path = ref.get("local_path")
    if isinstance(local_path, str) and local_path:
        # The CLI's default directory is relative to its state file as given
        # (real-CLI smoke, #28777); ours is absolute, but resolve a relative
        # path against that file's directory, never the connector's cwd, and
        # hand the daemon an absolute path even under a relative state-file
        # override (review of #30546).
        if not os.path.isabs(local_path):
            local_path = os.path.join(os.path.dirname(mailbox_cli_state_file()), local_path)
        local_path = os.path.abspath(local_path)
        # #30869: the path on the line must be one a model retypes byte for
        # byte; the CLI's name embeds the peer's (a macOS screenshot carries
        # U+202F). Alias it under a model-safe name, keep the CLI's own path
        # beside it for `show`; no alias when the name is already safe or
        # none can be made.
        alias = attachment_alias(local_path, name)
        if alias is not None:
            meta["cli_path"] = local_path
            local_path = alias
        meta["local_path"] = local_path
    return meta


ATTACHMENT_ALIAS_CHARS = frozenset(string.ascii_letters + string.digits + "._-")
ATTACHMENT_ALIAS_STEM_MAX = 60
# #30869: the directory the alias step writes into — set by the mailbox
# listener when it hands the CLI `--attachment-dir` (the `attach` verdict),
# None otherwise, so aliasing rides exactly that gate.
ATTACHMENT_ALIAS_DIR = None


def attachment_alias_name(name):
    """#30869: the model-safe form of a peer's file name — ASCII letters,
    digits, `.`, `-`, `_` kept; every whitespace character (U+202F and U+00A0
    included) and `_` runs folded to one `_`; anything else dropped (so the
    result is one path component); the extension kept; bounded. Only called
    for a name that is NOT already safe (`attachment_alias`)."""
    def fold(part):
        out = []
        for ch in part:
            if ch == "_" or ch.isspace():
                if out and out[-1] != "_":
                    out.append("_")
            elif ch in ATTACHMENT_ALIAS_CHARS:
                out.append(ch)
        return "".join(out).strip("_")
    stem, ext = os.path.splitext(name)
    return (fold(stem)[:ATTACHMENT_ALIAS_STEM_MAX].strip("_") or "file") + fold(ext)[:16]


def attachments_dir():
    """The connector's own attachments directory (FR-28777-2: what the
    listener passes as `--attachment-dir`; #30869: where aliases live)."""
    return os.path.abspath(os.path.join(state_dir(), "attachments"))


def attachment_alias(local_path, name):
    """#30869: a model-safe alias of the file the CLI materialised at
    `local_path` for the peer's `name`, in the connector's own attachments
    directory: `<first 12 of the CLI stem>-<safe name>`, a symlink to the
    CLI's file and nothing else (no copy: a regular file here would have no
    remover — the CLI prunes only its own `<64 hex>-…` names and the sweep
    only symlinks; it dangles once the CLI's expiry prune removes its file,
    and the next listener start drops it). None when the listener did not
    arm the directory (no `attach` verdict), the name is already made of
    safe characters, the file is not there, or the symlink cannot be made —
    the caller keeps the CLI path unchanged."""
    directory = ATTACHMENT_ALIAS_DIR
    if directory is None or all(ch in ATTACHMENT_ALIAS_CHARS for ch in name) or not os.path.isfile(local_path):
        return None
    safe = attachment_alias_name(name)
    prefix = "".join(ch for ch in os.path.basename(local_path)[:12] if ch in ATTACHMENT_ALIAS_CHARS) or "att"
    alias = os.path.join(directory, f"{prefix}-{safe}")
    try:
        if os.path.lexists(alias) and not os.path.exists(alias):
            # The CLI pruned the file mid-listener (hourly) and an attachment
            # for this alias name arrived with its file present: re-point it
            # (`os.symlink` would refuse the existing name).
            os.unlink(alias)
        if not os.path.exists(alias):  # the same attachment re-admitted (a later `context` block) reuses it
            os.makedirs(directory, mode=0o700, exist_ok=True)
            os.symlink(local_path, alias)
    except OSError:
        return None
    return alias


def drop_dangling_attachment_aliases(directory):
    """#30869: the connector's one cleanup — at a mailbox listener's start,
    remove every symlink in its own attachments directory whose target is
    gone (the CLI's expiry prune removed its file). One bounded pass over one
    directory; regular files and live aliases are never touched. Best
    effort: an unreadable directory or a failing unlink is said once on
    stderr and the listener starts anyway; an entry that vanishes mid-pass
    is not an error."""
    try:
        entries = list(os.scandir(directory))
    except OSError as error:
        diag(f"attachment alias sweep skipped: {type(error).__name__} reading {directory}")
        return
    failed = 0
    for entry in entries:
        try:
            if entry.is_symlink() and not os.path.exists(entry.path):
                os.unlink(entry.path)
        except FileNotFoundError:
            continue
        except OSError:
            failed += 1
    if failed:
        diag(f"attachment alias sweep: {failed} dangling alias(es) could not be removed under {directory}")


def mailbox_attachments(body):
    """D20 item 5: `body.attachments`, then any reference inside the relay's
    `context` block, once each by id, at most ATTACHMENTS_MAX. The walk is
    bounded so a hostile block cannot spin the listener."""
    found = {}

    def take(ref):
        meta = attachment_from_reference(ref)
        if meta is not None and meta["file_id"] not in found and len(found) < ATTACHMENTS_MAX:
            found[meta["file_id"]] = meta
        return meta is not None

    direct = body.get("attachments")
    for ref in (direct if isinstance(direct, list) else [])[:ATTACHMENTS_MAX * 2]:
        take(ref)
    pending = collections.deque([body.get("context")])
    steps = 0
    while pending and steps < 4096 and len(found) < ATTACHMENTS_MAX:
        node = pending.popleft()
        steps += 1
        if isinstance(node, dict):
            if not take(node):
                pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    return list(found.values())


ATTACHMENT_NAME_MAX = 80


def marker_name(name):
    """A peer's file name in the sender slot (D20 item 5, INV-2 amended): the
    slot's sanitisation (`compact_sender`: non-printables and whitespace runs
    to one space, `[unattended]` defused — #29146/#29030) plus `:`, `[` and
    `]` → space — the connector mints the slot's punctuation, so a name can
    neither end the slot early nor close the marker to forge a dead-lane
    ` [unattended]` — and a length bound."""
    cleaned = compact_sender(str(name))
    for ch in (":", "[", "]"):  # the connector mints the slot's punctuation; a name never does
        cleaned = cleaned.replace(ch, " ")
    cleaned = " ".join(cleaned.split())
    return cleaned[:ATTACHMENT_NAME_MAX] or "file"


def human_size(size):
    if not isinstance(size, int):
        return None
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def attachment_markers(envelope):
    """The compact line's ` [+name size]` per attachment (D20 item 5, #29131),
    between the sender and ` [unattended]`, the name sanitised for the slot."""
    if (envelope.get("container") or {}).get("type") != "mailbox":
        return ""  # D20 item 7: the Slack arm's line is untouched (#29131 is separate)
    markers = []
    for meta in envelope.get("attachments") or []:
        if not isinstance(meta, dict) or not meta.get("name"):
            continue
        size = human_size(meta.get("size"))
        markers.append(f" [+{marker_name(meta.get('name'))}{' ' + size if size else ''}]")
    return "".join(markers)


def with_attachment_lines(text, envelope):
    """The text a native forward carries (D20 item 5): one trailing line per
    mailbox attachment naming the file, its kind and size, and where the CLI
    put it — a presentation fact, never an instruction."""
    # Mailbox envelopes only by construction: the forwarder exists only under
    # the native gate, which `cmd_listen` refuses for the Slack transport.
    lines = []
    for meta in envelope.get("attachments") or []:
        if not isinstance(meta, dict) or not meta.get("name"):
            continue
        size = human_size(meta.get("size"))
        shape = f"{meta.get('kind')}, {size}" if size else str(meta.get("kind"))
        where = meta.get("local_path")
        if where:
            # The CLI's file name embeds the peer's filename: same rule as the
            # name (non-printables to a space); `show` keeps the path verbatim.
            where = "".join(ch if ch.isprintable() else " " for ch in str(where))
        lines.append(f"[attachment: {marker_name(meta.get('name'))} ({shape}) → {where or 'not downloaded'}]")
    return "\n".join([text, *lines]) if lines else text


CONTEXT_ONELINER_MAX_BYTES = 200  # FR-33022-1: the collapsed row is one forensic row (D22 item 1)
CONTEXT_ROW_PREFIX = "context: "  # minted here, guarded in defuse_context_rows: one constant, no desync


def context_oneliner(history):
    """FR-33022-1: the collapsed form of `relay_history` — every post as
    `<who>: <text>`, oldest first, joined with ` | ` and cut to one bounded
    line with `…`. The expanded `[context]` block below carries each post
    whole; this row is what a collapsed view shows. \"\" for no posts."""
    pairs = []
    for entry in history or []:
        if not isinstance(entry, dict) or not entry.get("text"):
            continue
        pairs.append(f"{marker_name(entry.get('from') or 'unknown')}: {entry['text']}")
    if not pairs:
        return ""
    joined = " | ".join(pairs)
    budget = CONTEXT_ONELINER_MAX_BYTES - len(CONTEXT_ROW_PREFIX)
    if len(joined.encode("utf-8")) > budget:
        joined = joined.encode("utf-8")[: budget - 3].decode("utf-8", "ignore").rstrip() + "…"
    return f"{CONTEXT_ROW_PREFIX}{joined}"


def with_context_lines(text, envelope):
    """The untagged posts around this message (`relay_history`): one combined
    `context:` row (the collapsed one-liner) plus one trailing
    `[context] <who>: <text>` line per post (the expanded block), oldest
    first — presentation facts about the monitored channel, never an
    instruction and never asks of their own. They come last, after any
    attachment line, so the message the coordinator must answer is still the
    first line at every seam."""
    history = [entry for entry in envelope.get("relay_history") or []
               if isinstance(entry, dict) and entry.get("text")]
    if not history:
        return text
    row = context_oneliner(history)
    lines = [f"[context] {marker_name(entry.get('from') or 'unknown')}: {entry['text']}"
             for entry in history]
    return "\n".join([text, row, *lines])


def with_message_lines(text, envelope):
    """Both model-read tails in the one order FR-33022-1 fixes: the attachment
    lines (FR-28777-2) first, then the `context:` row and the `[context]`
    lines — the message the coordinator must answer stays the first line, its
    files next, the room last. The compact line, the native forward and the
    `delegate` snapshot all go through here, so the order is written once
    (review of #33053)."""
    return with_context_lines(with_attachment_lines(text, envelope), envelope)


ATTACHMENT_MARK = re.compile(r"\[attachment:", re.IGNORECASE)
UI_MARK = re.compile(r"\[ui\]", re.IGNORECASE)  # #35345: the connector's click / result marker (FR-35345-4(c))


def defuse_attachment_lines(text):
    """ADR 23499 D20 item 5 / INV-2 (#30674): the `[attachment: …]` line is the
    connector's alone. A peer's text prints verbatim as continuation lines and
    the connector appends its own line to the same body, so a forged line
    would read byte-identical to the real one and the daemon's "read the file
    where it landed" rule would read any path a remote peer types. `[attachment:`
    ANYWHERE in a peer's text, in any letter case, is written `(attachment:`
    (the rest unchanged) — the `[unattended]` → `(unattended)` rule, #29030,
    applied the same way: anywhere, not at line start, because an indent or a
    zero-width space would defeat a line-start rule (review of #30662) — ONCE
    here, before any renderer runs, so the compact continuation, the native
    forward, the delegate snapshot and `show` all carry the defused text."""
    return ATTACHMENT_MARK.sub("(attachment:", text)


SHOW_HINT_MARK = re.compile(r"… truncated;", re.IGNORECASE)


def defuse_show_hint_lines(text):
    """Review of #30799: the `… truncated; show --event-id <id> --json` trailer
    is the connector's alone too. The native forward now carries it, `show`
    looks any id up with no lane scoping, and a peer's text prints verbatim,
    so a forged trailer would have the coordinator read another lane's text.
    `… truncated;` ANYWHERE in a peer's text, in any letter case, is written
    `(… truncated;` (the rest unchanged) — the `[attachment:` rule above,
    applied the same way and at the same seams (FR-30674-1 as amended)."""
    return SHOW_HINT_MARK.sub("(… truncated;", text)


CONTEXT_MARK = re.compile(r"\[context\]", re.IGNORECASE)


def defuse_context_lines(text):
    """`[context] <who>: <text>` is the connector's line too (the untagged posts
    the relay's block carries), so the `[attachment:` rule applies to it
    verbatim: a peer's text prints as continuation lines at the same seams, and
    a forged one would let remote content put words in a named colleague's
    mouth. `[context]` ANYWHERE, in any letter case, is written `(context)`."""
    return CONTEXT_MARK.sub("(context)", text)


def defuse_context_rows(text):
    """FR-33022-1: `context: ` at a line start is the connector's combined row.
    A peer's line starting that way is written `(context): ` — strict and
    case-sensitive, because `context:` starts ordinary sentences and the
    daemon's split keys on the exact minted bytes: an indent, a capital or a
    zero-width space matches nothing there (contrast the anywhere rule #30662
    needed for `[attachment:`, whose matcher normalizes first). "Line" is the
    consumers' definition — `str.splitlines()`, which breaks on `\\r`, `\\v`,
    `\\f`, U+2028… as well as `\\n` — never `^` under `re.MULTILINE`, which
    sees `\\n` alone: a `\\r`-broken `context:` line reached the compact line
    undefused and the daemon promoted it to the room (review of #33053, P0)."""
    return "".join(
        "(context): " + line[len(CONTEXT_ROW_PREFIX):] if line.startswith(CONTEXT_ROW_PREFIX) else line
        for line in (text or "").splitlines(keepends=True)
    )


def defuse_peer_text(text):
    """The one admission-seam rewrite of a peer's or a Slack user's text: the
    connector's own lines (`[attachment: …]`, `[context] …`, `context: …`,
    `… truncated; show …`) cannot be forged (#30674; review of #30799;
    FR-33022-1)."""
    return defuse_context_rows(defuse_context_lines(defuse_show_hint_lines(defuse_attachment_lines(
        UI_MARK.sub("(ui)", text)))))


def normalize_client_envelope(item, sender, message_id, event_id, client_env):
    """Map a validated agent-role client envelope to the connector's standard
    envelope. reply_target carries the sender mailbox id + message id so
    replies can target the sender. Remote content enters as remote
    runtime context, NEVER user authority: is_owner is always False in mailbox mode
    (there is no bound owner)."""
    body = client_env.get("body") or {}
    # Canonical peer_message: text + optional conversation_id live inside body.
    text = defuse_peer_text(body.get("text") or "")  # #30674 / #30799: once, at the mailbox admission seam
    full_text = text[:FULL_TEXT_BOUND]
    conversation_id = body.get("conversation_id")
    reply_target = {
        "type": "mailbox",
        "target_client_mailbox_id": sender,
        "message_id": message_id,
    }
    if conversation_id:
        # Carry the conversation/thread id through so `reply` can echo it.
        reply_target["conversation_id"] = conversation_id
    envelope = {
        "protocol_version": PROTOCOL_VERSION,
        "event_id": event_id,
        "source": CONNECTOR_ID,
        "binding_id": "mailbox",
        "kind": "message.created",
        "actor": {
            "id": sender,
            "display": sender,
            "is_owner": False,
            "is_bot": False,
        },
        "container": {"type": "mailbox", "id": conversation_id or sender, "thread_id": conversation_id},
        "content": {"text": full_text[:TEXT_BOUND], "truncated": len(full_text) > TEXT_BOUND},
        "reply_target": reply_target,
        "attachments": mailbox_attachments(body),
        "occurred_at": occurred_at_from_ms(item.get("accepted_at_ms")),
    }
    # ADR 25011 D22 / #29113: the relay's `context` block (requester display
    # name, channel, thread) rides the connector envelope opaque and bounded;
    # it is a presentation fact for the native cell, never authority.
    relay_context = body.get("context")
    if isinstance(relay_context, dict) and relay_context:
        # D20 item 2: a non-empty `context` block marks the sender as the Muse
        # Tag relay — the one peer that understands `message_edit` (an empty
        # `{}` carries no relay fact and sets nothing). The mark rides the
        # reply target onto the LANE (`lane.relay`, sticky; `assign_lane`).
        reply_target["relay"] = True
        if len(json.dumps(relay_context, separators=(",", ":"))) <= RELAY_CONTEXT_MAX_BYTES:
            envelope["relay_context"] = relay_context
    if isinstance(conversation_id, str) and conversation_id.startswith(RELAY_CONVERSATION_ID_PREFIX):
        # #31078: the production relay sends no `context` block, so the mark
        # also reads the one fact every relay message carries — its signed
        # conversation token as the conversation id (D20 item 2 as amended
        # 2026-09-08). Same mark, same lane fact; nothing else changes.
        reply_target["relay"] = True
    # #30542: the two facts survive whatever the block's size, and the
    # requester's display name becomes the sender the line, the feed, the
    # snapshot and the reply summary show; `actor.id` stays the mailbox id
    # (the reply address), `is_owner` stays False (presentation, not authority).
    # The same block's untagged posts (the monitored channel's own
    # conversation) ride the envelope as bounded `relay_history` and print as
    # one combined `context:` row plus `[context]` lines wherever the model
    # reads this message; `assign_lane` drops the ones this lane has already
    # been shown.
    history = relay_history(relay_context, text)
    if history:
        envelope["relay_history"] = history
    relay = relay_facts(relay_context)
    if relay:
        envelope["relay"] = relay
        name = (relay.get("requester") or {}).get("display_name")
        if name:
            envelope["actor"]["display"] = name
    return envelope, full_text


def admit_cli_item(line_obj, own_id):
    """One decoded `muse-mailbox listen --decode-json` line -> (event_id,
    envelope, full_text) to admit an agent-role message, or None to
    intentionally discard (malformed, oversize, oob, an unknown/unsupported
    role, or this worker's own echo) — fail closed, never surface non-agent or
    invalid content to the model. `own_id` is the mailbox id this listener
    registered — required, like `admit_message`'s `bot_user_id`, so no call
    site can skip the self-echo guard by omission (#27890 review). Dedup by
    (sender, message_id) is the caller's job."""
    if not isinstance(line_obj, dict):
        diag("mailbox line is not a JSON object; discarding (fail closed)")
        return None
    sender = line_obj.get("sender_client_mailbox_id")
    message_id = line_obj.get("message_id")
    client_env = line_obj.get("payload_json")
    # Type-check sender/message_id as non-empty strings, not just truthy: a
    # non-finite float (1e400 → Infinity) is truthy and would flow into the
    # event_id/actor.id and make json.dumps emit the bare `Infinity` token —
    # invalid JSON on stdout (INV-2), the same hole as body.conversation_id.
    if (
        not isinstance(sender, str) or not sender
        or not isinstance(message_id, str) or not message_id
        or not isinstance(client_env, dict)
    ):
        diag("mailbox line missing sender/message_id or a decoded payload_json; discarding")
        return None
    if sender == own_id:
        # #27890: a line from our own mailbox id is not a peer conversation.
        # Admitting it minted a lane keyed on our own id and the daemon replied
        # to itself. The mailbox twin of admit_message's bot_user_id check.
        diag("mailbox line from this worker's own mailbox id; discarding (self-echo)")
        return None
    if client_env.get("to_role") in (UI_RESULT_ROLE, UI_EVENT_ROLE):
        # #35345 (spec 23499 FR-35345-3(a)/-4(a)): the relay's UI result and
        # event lines are the connector's own to correlate — never a peer
        # message, never a lane of their own. `process_ui_item` decides.
        return UiInbound(client_env["to_role"], sender, message_id, client_env, line_obj.get("accepted_at_ms"))
    kind = (client_env.get("body") or {}).get("kind") if isinstance(client_env.get("body"), dict) else None
    if isinstance(kind, str) and kind != PEER_MESSAGE_KIND:
        # D20 item 5: another envelope kind (the stack's `message_edit`, or a
        # later one) is not a message for the model — one self-describing skip
        # line, no lane, no wake (ADR 25011 D27's posture).
        diag(
            f"mailbox line skipped: body.kind {kind!r} is not a peer_message "
            f"(sender {sender}, message {message_id}); nothing to reply to"
        )
        return None
    try:
        client_env = validate_client_envelope(client_env)
    except InputError as error:
        diag(f"client envelope rejected ({error}); discarding (fail closed)")
        return None
    if client_env.get("to_role") != "agent":
        diag(f"client envelope to_role={client_env.get('to_role')!r} is not agent; discarding (fail closed)")
        return None
    event_id = mailbox_event_id(sender, message_id)
    envelope, full_text = normalize_client_envelope(line_obj, sender, message_id, event_id, client_env)
    return event_id, envelope, full_text


def route_inbound(checkpoint, event_id, candidate, full_text, unattended_grace_s, cursor=None, hops=None):
    """One inbound line under the caller's state lock (D11/D12 fan-out; the
    caller's save is INV-1's persist-before-emit): dedupe, lane, retained
    window, feed, then who reads it — a live claim: the coordinator's scoped
    tail (nothing printed here); no claim or one past its grace: the daemon's
    stream (`[unattended]`); the native forwarder when on. Returns `(envelope
    to emit or None, admitted)`. Peer messages and #35345 UI lines share it,
    so a click reaches its conversation's owner by the message path (D10)."""
    conversation_claim = claim_for(checkpoint, "mailbox", lane_key_for(candidate))
    unattended_claim = None
    if conversation_claim is not None and claim_is_unattended(conversation_claim, unattended_grace_s):
        unattended_claim, conversation_claim = conversation_claim, None  # D15: the daemon's again
    if event_id in checkpoint["recent_event_ids"] or event_id in checkpoint["retained_events"]:
        # (sender, message_id) dedup: a redelivered event still dedups even
        # if its id rolled out of the recent FIFO (retained membership).
        diag(f"duplicate mailbox message {event_id}; discarding")
        return None, False
    alias = assign_lane(checkpoint, candidate)
    checkpoint["recent_event_ids"].append(event_id)
    checkpoint["retained_events"][event_id] = {"envelope": candidate, "full_text": full_text}
    append_feed(candidate, cursor=cursor, hops=hops)
    envelope = None
    # D11: a claimed conversation never wakes the daemon again; the
    # event is the coordinator's, read from the feed.
    if NATIVE_FORWARDER is not None:
        # ADR 25011 D22: the forwarder delivers to the owning session;
        # liveness is decided at delivery, not by the lock or the grace.
        # The queue entry is persisted with the event (INV-1), so a
        # listener that dies before the send re-forwards on restart.
        forwarded_claim = conversation_claim or unattended_claim
        checkpoint["retained_events"][event_id]["native"] = {
            "state": "pending", "attempts": 0,
            "claim": dict(forwarded_claim) if forwarded_claim else None,
        }
        envelope = candidate
    elif conversation_claim is None:
        envelope = candidate
        if unattended_claim is not None:
            note_unattended_emission(unattended_claim)
            envelope = unattended_envelope(candidate, unattended_claim, alias)
    return envelope, True


def process_cli_item(line_obj, output_format, own_id, unattended_grace_s=UNATTENDED_GRACE_S_DEFAULT,
                     read_at_ms=None, admit=None):
    """Admit one decoded mailbox line under the lock (persist-before-emit) and
    emit it. Unlike the old REST poll page, the `muse-mailbox` CLI owns the
    transport cursor via its --state-file, so a bad line is discarded with a
    diagnostic and never wedges the listener: there is no connector cursor to
    advance and no re-delivery of the same poison item. Dedup is by
    (sender, message_id). Returns the emitted envelope, or None on discard.
    `read_at_ms` (#28433) is when the listener read the CLI line; under the
    hop trace the admission stamps ride the feed line and hops.jsonl.
    `admit` (#37011): the caller's own `admit_cli_item` verdict, so the
    listener can tell an ADMITTED peer message (the only line that writes the
    mailbox heartbeat) from a line it read and discarded, without classifying
    twice; None classifies here."""
    if admit is None:
        admit = admit_cli_item(line_obj, own_id)
    if admit is None:
        return None
    if isinstance(admit, UiInbound):
        return process_ui_item(admit, output_format, unattended_grace_s)
    event_id, candidate, full_text = admit
    hops = None
    if trace_hops_enabled():
        hops = {"accepted_at_ms": line_obj.get("accepted_at_ms"), "read_at_ms": read_at_ms}
    with StateStore() as store:
        if hops is not None:
            hops["lock_at_ms"] = now_ms()
        state = store.load(require=True)
        checkpoint = state["checkpoint"]
        envelope, admitted = route_inbound(checkpoint, event_id, candidate, full_text, unattended_grace_s,
                                           cursor=line_obj.get("cursor"), hops=hops)
        evict_bounded(checkpoint)
        state.setdefault("mailbox", {})["last_poll_at"] = utc_now()  # #37011: the mailbox's own heartbeat
        store.save(state)  # INV-1: persist before emit
        if hops is not None:
            hops["persisted_at_ms"] = now_ms()
    crash_if("after_persist", mailbox_seams_enabled())  # INV-1 teeth: a crash here must not lose or double the emit
    line = None
    if envelope is not None and NATIVE_FORWARDER is not None and admitted:
        NATIVE_FORWARDER.forward(event_id)
    elif envelope is not None:
        line = emit_event(envelope, output_format, hops=hops if admitted else None)
    if hops is not None and admitted:
        # A claimed conversation's event is admitted and fed but never printed
        # here (D11): its record has no print, the coordinator's tail adds one.
        record_hops(hop_record(candidate, "unscoped", hops, line))
    return envelope


def hop_record(envelope, role, hops, line, conversation=None):
    """One hops.jsonl line: identity, role (`unscoped` or `conversation`), the
    stamps and the printed text (None when nothing was printed)."""
    actor = envelope.get("actor") or {}
    record = {
        "event_id": envelope.get("event_id"),
        "role": role,
        "conversation": conversation if conversation is not None else lane_key_for(envelope),
        "lane": envelope.get("lane"),
        "from": actor.get("display") or actor.get("id") or "unknown",
        "occurred_at": envelope.get("occurred_at"),
        "pid": os.getpid(),
    }
    for key in ("accepted_at_ms", "read_at_ms", "lock_at_ms", "feed_written_at_ms",
                "persisted_at_ms", "tail_read_at_ms", "printed_at_ms"):
        record[key] = hops.get(key)
    record["line"] = line
    return record


# ---------------------------------------------------------------------------
# #35345 inbound: the relay's capability_result / capability_event lines
# (ADR 35345 D8/D9/D10/D12; spec 23499 FR-35345-3/-4/-6)
# ---------------------------------------------------------------------------


class UiInbound(collections.namedtuple("UiInbound", "role sender message_id payload accepted_at_ms")):
    """A decoded listen line addressed to the connector's UI arm: the relay's
    `capability_result` (an operation's outcome) or `capability_event` (a
    human's click). Never a peer message (`admit_cli_item`)."""

    @property
    def noun(self):
        return "result" if self.role == UI_RESULT_ROLE else "event"

    @property
    def where(self):
        return f"sender {self.sender}, message {self.message_id}"


def ui_line_envelope(kind, event_id, lane, message_id, actor_id, text, ui, accepted_at_ms=None):
    """The envelope of a UI line (`ui.action` / `ui.result`): the card's
    conversation as container and reply target (so it takes the card's lane),
    the relay-authenticated actor (`is_owner` False: attributable input, no
    extra authority, D10), the correlation facts under `ui` (INV-35345-5)."""
    route = lane.get("route") or {}
    relay = route.get("target_client_mailbox_id")
    conversation_id = route.get("conversation_id")
    reply_target = {"type": "mailbox", "target_client_mailbox_id": relay, "message_id": message_id}
    if conversation_id:
        reply_target["conversation_id"] = conversation_id
    if lane.get("relay"):
        reply_target["relay"] = True
    full_text = text[:FULL_TEXT_BOUND]
    envelope = {
        "protocol_version": PROTOCOL_VERSION,
        "event_id": event_id,
        "source": CONNECTOR_ID,
        "binding_id": "mailbox",
        "kind": kind,
        "actor": {"id": actor_id, "display": actor_id, "is_owner": False, "is_bot": False},
        "container": {"type": "mailbox", "id": conversation_id or relay, "thread_id": conversation_id},
        "content": {"text": full_text[:TEXT_BOUND], "truncated": len(full_text) > TEXT_BOUND},
        "reply_target": reply_target,
        "attachments": [],
        "occurred_at": occurred_at_from_ms(accepted_at_ms) if accepted_at_ms is not None else utc_now(),
        "ui": ui,
    }
    return envelope, full_text


def ui_next_sentence(status, kind_word, *, revision_known=False, previous=None):
    """The `next` clause of a surfaced result line (FR-35345-4(f)): what the
    owner can do, per arm. `previous` names the outcome the owner was already
    told when a late definitive result lands (FR-35345-3(a))."""
    if kind_word == "reconcile" and status not in ("confirmed", "fallback_sent"):
        return UI_RECONCILE_FAILED_NEXT  # ADR 35345 D15 item 7
    if previous is not None and status == "confirmed":
        return "the card is live; clicks now reach this lane"
    if previous is not None and status == "fallback_sent":
        return "the fallback text was posted; there is no card to update"
    if status == "rejected":
        if kind_word == "post":
            return "fix the blocks and send a new post; nothing was posted"
        return "the card is unchanged; fix the blocks and update again, or send a new post"
    if status == "conflict":
        if revision_known:
            return "the card moved; re-read it and update again"
        return "the card moved and its revision is unknown; send a new post"
    if status == "unavailable":
        return "wait, then send a new post"
    if status == "not_sent":
        return "send the post again"
    return UI_UNCERTAIN_NEXT


def ui_result_text(status_words, reason, errors, next_text):
    """`<post|update> <status> · reason: <reason or -> [· errors: path:code, …] · next: <sentence>`."""
    text = f"{status_words} · reason: {reason or '-'}"
    shown = [f"{e['path']}:{e['code']}" for e in errors]  # parsed `{path, code}` items, already bounded by slack_ui
    if shown:
        text += " · errors: " + ", ".join(shown)
    return f"{text} · next: {next_text}"


def surface_ui_operation(checkpoint, op_id, operation, status, reason, unattended_grace_s, *,
                         event_id=None, message_id=None, errors=(), revision=None, ui_id=None, note=None,
                         previous=None, accepted_at_ms=None, next_text=None):
    """FR-35345-3(e): a result the owner must judge is admitted as an inbound
    line of the card's conversation through `route_inbound`, never a second
    reply. The event id is the transport's for a relayed result and
    `ui:[<operation>,<status>]` for one the connector classified itself, so
    one classification is never surfaced twice. Returns the lines to emit."""
    lane = (checkpoint.get("lanes") or {}).get(operation.get("lane"))
    if lane is None:
        diag(f"ui result {status} for operation {op_id} has no lane; nothing to surface")
        return []
    kind_word = operation.get("kind")
    revision_known = isinstance(revision, int) and not isinstance(revision, bool)
    text = ui_result_text(note or f"{kind_word} {status}", reason, errors,
                          next_text or ui_next_sentence(status, kind_word, revision_known=revision_known, previous=previous))
    ui_fields = {
        "operation_id": op_id, "kind": kind_word, "status": status, "reason": reason,
        "errors": [dict(e) for e in errors],
        "retry_after_seconds": operation.get("retry_after_seconds"), "revision": revision, "ui_id": ui_id,
    }
    if event_id is None:
        event_id = "ui:" + json.dumps([op_id, status], separators=(",", ":"))
    relay = operation.get("relay") or (lane.get("route") or {}).get("target_client_mailbox_id") or "relay"
    candidate, full_text = ui_line_envelope(UI_RESULT_KIND, event_id, lane, message_id or op_id, relay, text, ui_fields,
                                            accepted_at_ms)
    envelope, admitted = route_inbound(checkpoint, event_id, candidate, full_text, unattended_grace_s)
    return [(event_id, envelope, admitted)] if envelope is not None else []


def clear_pending_pointer(ui, op_id):
    """FR-35345-3(b): a settled update no longer pends on its card — cleared
    by key, so a late result for U1 never wipes U2's pointer."""
    for card in ui["presentations"].values():
        if card.get("pending_operation_id") == op_id:
            card["pending_operation_id"] = None


def ui_instant_ms(stamp, now, wall_ms):
    """A UI-clock ISO stamp (`ui_now()`, FR-35345-6) as wall-clock ms beside
    the ledger's `sent_at_ms`/`received_at_ms`: `wall_ms` less the stamp's
    age on the UI clock, both clocks sampled together BEFORE the state lock
    (`process_ui_item`), so a lock wait never moves the instant — seam off
    this is `submitted_at` exactly; under a pinned test clock the age is
    what the test moved."""
    return wall_ms - int((now - slack_ui_module().epoch(stamp)) * 1000)


CARD_MARKER_PREFIX = re.compile(r"^(?:\[card rev \d+(?:, after [^\]]*)?\] ?)+")


def card_entry_text(lane, ui_id, revision, answered_at_ms, text):
    """#36324: the card's ledger entry reads as the requester now sees the
    card — the newest confirmed update's text under a marker naming the
    revision and the click it answered (the newest `ui.action` line on this
    card at or before the update's send instant), so the `delegate`
    snapshot and the relaunched coordinator's "Already sent" line never
    quote a superseded card (M23 D1: the coordinator rebuilt rev 3 from the
    post's words and moved the card backwards). Idempotent: a model that
    copied the starter's provenance prefix into the card it sent (M2R r1)
    has that leading marker — or a stack of them — stripped first, so the
    entry carries exactly one marker instead of compounding per relaunch."""
    text = CARD_MARKER_PREFIX.sub("", text)
    route = lane.get("route") or {}
    click = None
    for item in read_feed(route.get("transport"), lane.get("key")):
        envelope = item.get("envelope") or {}
        if (envelope.get("kind") == UI_ACTION_KIND and (envelope.get("ui") or {}).get("ui_id") == ui_id
                and int(item.get("received_at_ms") or 0) <= int(answered_at_ms)):
            click = item
    marker = f"card rev {revision}"
    if click is not None:
        marker += f", after {click.get('from') or 'unknown'} {click.get('text') or ''}".rstrip()
    return f"[{marker}] {text}"


def stamp_ui_entry(lane, op_id):
    """Mark the ledger entry just appended for `op_id` as the card's: `kind: ui`
    plus the operation id, so the entry names its family."""
    for entry in lane["outbound"]:
        if entry.get("message_id") == op_id:
            entry["kind"] = UI_OUTBOUND_KIND
            entry["operation_id"] = op_id


def restamp_ledger_entry(lane, previous_op_id, op_id, answered_at_ms, text):
    """FR-35345-3(b): a confirmed update takes over the card's ledger entry —
    the entry whose `operation_id` was the card's previous operation now
    names the update, so the entry/presentation join holds. Its `sent_at_ms`
    and position stay the post's; its `text` becomes the update's marked
    text (`card_entry_text`, #36324) so the snapshot quotes the card as it
    stands; and it gains `answered_at_ms` = the update's SEND instant: the
    update is the lane's answer to the lines before it and to none after
    it, read by `answered_at_ms` exactly like a plain reply, so the idle
    sweep (FR-27816-2(f)) never re-dispatches the click it applied (#35345
    post-merge E2E, defect 1). When the bounded ledger has already evicted
    the card's entry, a fresh `kind: ui` entry with the same text is
    appended at that instant and becomes the card's entry. `text` None
    means the update's words are unknown (a record that never carried them:
    admitted before #36324, or a late `confirmed` after the deadline arm
    already went `uncertain` and dropped them, FR-35345-3(a)) — the entry's
    words then stay as they are, and the evicted arm appends a wordless
    entry the snapshot skips; a card's words are never cut to a bare marker."""
    for entry in lane.get("outbound") or []:
        if entry.get("kind") == UI_OUTBOUND_KIND and entry.get("operation_id") == previous_op_id:
            entry["operation_id"] = op_id
            if text is not None:
                entry["text"] = text
            entry["answered_at_ms"] = int(answered_at_ms)
            return
    if append_outbound_entry(lane, op_id, text or "", interim=False,
                             sent_at=slack_ui_module().iso(answered_at_ms / 1000.0), sent_at_ms=answered_at_ms):
        stamp_ui_entry(lane, op_id)


def emit_ui_lines(emitted, output_format):
    for event_id, envelope, admitted in emitted:
        if NATIVE_FORWARDER is not None and admitted:
            NATIVE_FORWARDER.forward(event_id)
        else:
            emit_event(envelope, output_format)


def apply_ui_result(slack_ui, checkpoint, item, now, unattended_grace_s, wall_ms, mailbox=None):
    """FR-35345-3 / D12 under the state lock: correlate one `capability_result`
    to its operation and apply the matrix (confirmed / fallback_sent silent, a
    rate limit schedules the same-id retry, the rest surfaced once). Returns
    None when dropped (one diag), else the lines to emit ([] when silent)."""
    body = item.payload.get("body") if isinstance(item.payload, dict) else None
    version = body.get("version") if isinstance(body, dict) else None
    if not isinstance(body, dict) or body.get("name") != slack_ui.CAPABILITY_NAME or version not in (1, 2):
        diag(f"ui result dropped (not {slack_ui.CAPABILITY_NAME} v1/v2; {item.where})")
        return None
    try:
        raw_status = None
        if version == 2:
            # ADR 35345 D15 item 7: `model_revision` is the card's revision; `queued` is silent.
            v2 = slack_ui_v2_module()
            parsed = v2.parse_capability_result(item.payload)
            raw_status, result = parsed.status, v2.as_v1_result(parsed)
        else:
            result = slack_ui.parse_capability_result(item.payload)
    except (slack_ui.SlackUiInputError, ConnectorError) as error:
        diag(f"ui result dropped (malformed: {error}; {item.where})")
        return None
    ui = ui_tables(checkpoint)
    op_id = result.request_message_id
    operation = ui["operations"].get(op_id)
    if operation is None:
        diag(f"ui result dropped (unknown request_message_id {op_id}; {item.where})")
        return None
    if operation.get("relay") and item.sender != operation["relay"]:
        diag(f"ui result dropped (wrong_relay: operation {op_id} belongs to {operation['relay']}; {item.where})")
        return None
    alias = operation.get("lane")
    lane = (checkpoint.get("lanes") or {}).get(alias)
    if lane is None:
        diag(f"ui result dropped (lane {alias} of operation {op_id} is gone; {item.where})")
        return None
    if (operation.get("stage") == slack_ui.STAGE_RETRY_WAIT and operation.get("retry_at")
            and slack_ui.classify_result(result, retries=0) == "retry"):
        # Nothing new was asked of the relay while the retry is still pending,
        # so another rate-limit answer can only be a redelivery under a new
        # transport id: it must not re-arm the delay or burn the retry budget.
        diag(f"ui result dropped (redelivered rate_limited before the retry of operation {op_id} went out; "
             f"{item.where})")
        return None
    if operation.get("version", 1) != version:
        diag(f"ui result dropped (version {version} result for a version {operation.get('version', 1)} operation {op_id}; {item.where})")
        return None
    if operation.get("kind") in (slack_ui.UPDATE, slack_ui.RECONCILE) and result.status == "fallback_sent":
        # FR-35345-3(a), FM-35345-13: the one status an update can never
        # receive (the relay posts a fallback only for a post); dropped so an
        # echoed ui_id cannot turn the live card into a fallback record.
        diag(f"ui result dropped (kind-mismatch fallback_sent for update operation {op_id}; {item.where})")
        return None
    card = ui["presentations"].get(operation.get("ui_id")) if operation.get("ui_id") else None
    transition = slack_ui.next_state(op_id, operation, result, presentation=card, now=now)
    if transition.operation is operation:
        # FR-35345-3(a): a redelivery of a terminal outcome, or a contradiction
        # of a settled one — the record stands, nothing wakes.
        diag(f"ui result dropped (redelivered {result.status}: operation {op_id} is already "
             f"{operation.get('status')}; {item.where})")
        return None
    previous = operation.get("status") if operation.get("stage") == slack_ui.STAGE_TERMINAL else None
    updated = transition.operation
    if raw_status == "queued" and updated.get("stage") == slack_ui.STAGE_TERMINAL:
        updated["status"] = raw_status  # the record keeps the relay's word; the disposition was `confirmed`'s
    # #36324: an update's words ride its record only while in flight (D9).
    pending_text = updated.pop("text", None) if updated.get("stage") == slack_ui.STAGE_TERMINAL else None
    ui["operations"][op_id] = updated
    if updated.get("stage") == slack_ui.STAGE_TERMINAL:
        clear_pending_pointer(ui, op_id)
    if (result.status == "confirmed" and operation.get("kind") == slack_ui.UPDATE and card is not None
            and transition.presentation is not None):
        sent_ms = ui_instant_ms(updated.get("submitted_at") or updated.get("started_at"), now, wall_ms)
        restamp_ledger_entry(lane, card.get("operation_id"), op_id, sent_ms,
                             None if pending_text is None else
                             card_entry_text(lane, transition.presentation_id, transition.presentation.get("revision"),
                                             sent_ms, pending_text))
    if transition.presentation is not None:
        if operation.get("kind") == slack_ui.POST and operation.get("seq") is not None:
            # FR-35345-6: the post's send-order `seq` rides onto its card — the
            # live-card tie-break lane F's `lane_live_presentation` reads.
            transition.presentation.setdefault("seq", operation["seq"])
        if operation.get("version") == 2 and result.status == "confirmed":
            # ADR 35345 D15 item 7: the version 2 card keeps the bounded facts a
            # later settlement needs — template digests and the per-control
            # `done:` names — never the blocks (D9).
            transition.presentation["version"] = 2
            transition.presentation["model_revision"] = result.revision
            if operation.get("kind") == slack_ui.POST:
                transition.presentation["template_digests"] = dict(operation.get("template_digests") or {})
                transition.presentation["done_templates"] = dict(operation.get("done_templates") or {})
                transition.presentation.setdefault("pending_submission", None)
        ui["presentations"][transition.presentation_id] = transition.presentation
    if result.status == "confirmed" and transition.presentation is not None:
        # `last_outbound` never names the card (#35474): the presentation record alone does.
        diag(f"ui result confirmed (op {op_id}, ui {transition.presentation_id}, "
             f"rev {transition.presentation.get('revision')}, lane {alias})")
    elif result.status == "fallback_sent":
        diag(f"ui result fallback_sent (op {op_id}, lane {alias}); no controls to wait for")
    elif transition.disposition == "retry":
        diag(f"ui result unavailable, retry {updated['retries']}/{slack_ui.UI_RETRY_MAX} in "
             f"{transition.retry_after_seconds} s (op {op_id}, lane {alias})")
    if transition.disposition != "surface":
        return []
    next_text = None
    if (operation.get("kind") == slack_ui.POST and result.status == "unavailable"
            and result.reason == UI_DISABLED_REASON and previous is None):
        # Ruling 25: the owner's prod relay advertised version 2 but had its
        # admission off for them, so every controls card was refused `disabled`
        # and re-sent as version 2 again; the coordinator read that as a channel
        # with no interactive blocks. Learn it once, say what the next card takes.
        next_text = learn_relay_ui_disabled(mailbox, item.sender, int(operation.get("version") or 1))
    return surface_ui_operation(
        checkpoint, op_id, updated, result.status, result.reason, unattended_grace_s,
        event_id=mailbox_event_id(item.sender, item.message_id), message_id=item.message_id,
        errors=result.errors, revision=result.revision, ui_id=result.ui_id or operation.get("ui_id"),
        note=transition.note, previous=previous, accepted_at_ms=item.accepted_at_ms, next_text=next_text)


def apply_ui_event(slack_ui, checkpoint, item, now, unattended_grace_s):
    """FR-35345-4 / D10 under the state lock: validate one `capability_event`
    against its presentation (known `ui_id`, the card's relay, the revision,
    an unconsumed `event_id`) and admit the click as an inbound line of that
    conversation, interpreting nothing. Returns None when dropped, an empty
    list when held (a multi-pick tick, owner ruling 49: consumed, no line),
    else the lines to emit."""
    body = item.payload.get("body") if isinstance(item.payload, dict) else None
    if isinstance(body, dict) and body.get("name") == slack_ui.CAPABILITY_NAME and body.get("version") == 2:
        return apply_ui_event_v2(slack_ui, checkpoint, item, now, unattended_grace_s)
    if (not isinstance(body, dict) or body.get("name") != slack_ui.CAPABILITY_NAME
            or body.get("version") != slack_ui.CAPABILITY_VERSION):
        diag(f"ui event dropped (not {slack_ui.CAPABILITY_NAME} v{slack_ui.CAPABILITY_VERSION}; {item.where})")
        return None
    try:
        event = slack_ui.parse_capability_event(item.payload)
    except slack_ui.SlackUiInputError as error:
        diag(f"ui event dropped (malformed: {error}; {item.where})")
        return None
    ui = ui_tables(checkpoint)
    card = ui["presentations"].get(event.ui_id)
    if card is None:
        diag(f"ui event dropped (unknown_ui_id {event.ui_id}; {item.where})")
        return None
    relay = card.get("relay") or (ui["operations"].get(card.get("operation_id")) or {}).get("relay")
    if relay and item.sender != relay:
        diag(f"ui event dropped (wrong_relay: card {event.ui_id} belongs to {relay}; {item.where})")
        return None
    alias = card.get("lane")
    lane = (checkpoint.get("lanes") or {}).get(alias)
    if lane is None:
        diag(f"ui event dropped (lane {alias} of card {event.ui_id} is gone; {item.where})")
        return None
    # FR-35345-4(a): a click may land on the next revision while an update on
    # this card is still `submitted` (it beat its own `confirmed`).
    pending_update = next((op for op in ui["operations"].values()
                           if op.get("kind") == slack_ui.UPDATE and op.get("ui_id") == event.ui_id
                           and op.get("stage") == slack_ui.STAGE_SUBMITTED), None)
    transition = slack_ui.next_state(event.ui_id, card, event, pending_update=pending_update, now=now)
    if transition.disposition == "stale":
        diag(f"ui event dropped (stale_revision {event.revision} != {card.get('revision')} for {event.ui_id}; "
             f"{item.where})")
        return None
    seen, consumed = slack_ui.event_seen(ui["consumed_event_ids"], event.event_id)
    if seen:
        diag(f"ui event dropped (duplicate_event {event.event_id}; {item.where})")
        return None
    ui["consumed_event_ids"] = consumed
    ui["presentations"][event.ui_id] = transition.presentation
    if event.action_type in slack_ui.MULTI_PICK_ELEMENT_TYPES:
        # Owner ruling 49 (2026-09-23 19:45Z): a multi-pick's ticks never reach the coordinator — no line, no
        # inbox item, no wake; the Submit press carries the completed `state`. Consumed, so a redelivery stays
        # silent. The set is slack_ui's: a version 1 click must not need slack_ui_v2.py (review of PR #41509).
        diag(f"ui tick held (multi-pick {event.action_type} {event.action_id} on {event.ui_id} = "
             f"{', '.join(event.values) or '-'}; delivered with the Submit press; {item.where})")
        return []
    values = ", ".join(event.values) or "-"
    text = f"{event.action_id} ({event.action_type}) = {values}"
    for key in sorted(event.state):
        items = [str(v) for v in event.state[key] if v not in (None, "")]
        if items:
            text += f" · state {key}={','.join(items)}"
    text = defuse_peer_text(text)  # human-typed values: the connector's own lines cannot be forged
    ui_fields = {
        "ui_id": event.ui_id, "revision": event.revision, "event_id": event.event_id,
        "action_id": event.action_id, "action_type": event.action_type, "values": list(event.values),
        "state": dict(event.state), "action_ts": event.action_ts,
    }
    event_id = mailbox_event_id(item.sender, item.message_id)
    candidate, full_text = ui_line_envelope(UI_ACTION_KIND, event_id, lane, item.message_id, event.actor_slack_id,
                                            text, ui_fields, item.accepted_at_ms)
    envelope, admitted = route_inbound(checkpoint, event_id, candidate, full_text, unattended_grace_s)
    return [(event_id, envelope, admitted)] if envelope is not None else []


def apply_ui_event_v2(slack_ui, checkpoint, item, now, unattended_grace_s):
    """ADR 35345 D15 item 4: a version 2 action reaches the owner as today's
    line; `kind`, `action_seq` and `model_revision` ride the envelope; a
    `presentation` event's line ends ` · presentation`; a business submission
    is noted on the card as its one outstanding submission. Dedupe is by
    `event_id` (the relay serializes submissions; no revision arm)."""
    try:
        v2 = slack_ui_v2_module()
        event = v2.parse_capability_event(item.payload)
    except (slack_ui.SlackUiInputError, ConnectorError) as error:
        diag(f"ui event dropped (malformed: {error}; {item.where})")
        return None
    ui = ui_tables(checkpoint)
    card = ui["presentations"].get(event.ui_id)
    if card is None:
        diag(f"ui event dropped (unknown_ui_id {event.ui_id}; {item.where})")
        return None
    if card.get("version") != 2:
        diag(f"ui event dropped (version 2 event for a version {card.get('version', 1)} card {event.ui_id}; {item.where})")
        return None
    relay = card.get("relay") or (ui["operations"].get(card.get("operation_id")) or {}).get("relay")
    if relay and item.sender != relay:
        diag(f"ui event dropped (wrong_relay: card {event.ui_id} belongs to {relay}; {item.where})")
        return None
    alias = card.get("lane")
    lane = (checkpoint.get("lanes") or {}).get(alias)
    if lane is None:
        diag(f"ui event dropped (lane {alias} of card {event.ui_id} is gone; {item.where})")
        return None
    seen, consumed = slack_ui.event_seen(ui["consumed_event_ids"], event.event_id)
    if seen:
        diag(f"ui event dropped (duplicate_event {event.event_id}; {item.where})")
        return None
    ui["consumed_event_ids"] = consumed
    card = dict(card, last_event_at=slack_ui.iso(now), model_revision=event.model_revision, action_seq=event.action_seq)
    if event.kind == v2.BUSINESS:
        card["pending_submission"] = v2.pending_submission(event)
        card["state"] = slack_ui.PRESENTATION_LIVE
    ui["presentations"][event.ui_id] = card
    if event.kind == v2.PRESENTATION and event.action_type in v2.MULTI_PICK_ELEMENT_TYPES:
        # Owner ruling 49 (2026-09-23 19:45Z): a multi-pick's ticks never reach the coordinator — no line, no
        # inbox item, no wake; the Submit press carries the completed `state`. Consumed, so a redelivery stays silent.
        diag(f"ui tick held (multi-pick {event.action_type} {event.action_id} on {event.ui_id} = "
             f"{', '.join(event.values) or '-'}; delivered with the Submit press; {item.where})")
        return []
    values = ", ".join(event.values) or "-"
    text = f"{event.action_id} ({event.action_type}) = {values}"
    for key in sorted(event.state):
        items = [str(v) for v in event.state[key] if v not in (None, "")]
        if items:
            text += f" · state {key}={','.join(items)}"
    text = defuse_peer_text(text)  # human-typed values: the connector's own lines cannot be forged
    if event.kind == v2.PRESENTATION:
        text += v2.PRESENTATION_SUFFIX
    ui_fields = {
        "ui_id": event.ui_id, "revision": event.model_revision, "event_id": event.event_id,
        "action_id": event.action_id, "action_type": event.action_type, "values": list(event.values),
        "state": dict(event.state), "action_ts": event.action_ts, "version": 2, "kind": event.kind,
        "action_seq": event.action_seq, "model_revision": event.model_revision,
    }
    event_id = mailbox_event_id(item.sender, item.message_id)
    candidate, full_text = ui_line_envelope(UI_ACTION_KIND, event_id, lane, item.message_id, event.actor_slack_id,
                                            text, ui_fields, item.accepted_at_ms)
    envelope, admitted = route_inbound(checkpoint, event_id, candidate, full_text, unattended_grace_s)
    return [(event_id, envelope, admitted)] if envelope is not None else []


def process_ui_item(item, output_format, unattended_grace_s):
    """One `capability_result` / `capability_event` line (persist-before-emit,
    INV-35345-9): the correlation and the feed line land in one save, then
    the line is printed — or forwarded — to whoever owns the conversation."""
    try:
        slack_ui = slack_ui_module()
    except ConnectorError as error:
        diag(f"ui {item.noun} dropped ({error}; {item.where})")
        return None
    event_id = mailbox_event_id(item.sender, item.message_id)
    now = ui_now()
    wall_ms = now_ms()  # beside the UI clock, before the lock: `ui_instant_ms` needs both from one instant
    with StateStore() as store:
        state = store.load(require=True)
        checkpoint = state["checkpoint"]
        if event_id in checkpoint["recent_event_ids"] or event_id in checkpoint["retained_events"]:
            # The transport redelivered the same line (INV-4); the UI-level
            # keys (`event_id`, the operation's status) would drop it too.
            body = item.payload.get("body") if isinstance(item.payload.get("body"), dict) else {}
            what = (f"duplicate_event {body.get('event_id')}" if item.role == UI_EVENT_ROLE
                    else f"duplicate result for {body.get('request_message_id')}")
            diag(f"ui {item.noun} dropped ({what}: mailbox message {event_id} already consumed)")
            return None
        if item.role == UI_RESULT_ROLE:
            emitted = apply_ui_result(slack_ui, checkpoint, item, now, unattended_grace_s, wall_ms=wall_ms,
                                      mailbox=state.setdefault("mailbox", {}))
        else:
            emitted = apply_ui_event(slack_ui, checkpoint, item, now, unattended_grace_s)
        if emitted is None:
            return None
        if event_id not in checkpoint["recent_event_ids"]:
            checkpoint["recent_event_ids"].append(event_id)  # a silent result still dedups on redelivery
        prune_ui_tables(slack_ui, ui_tables(checkpoint), now)
        evict_bounded(checkpoint)
        store.save(state)  # INV-1: persist before emit
    crash_if("after_persist", mailbox_seams_enabled())
    emit_ui_lines(emitted, output_format)
    return emitted[0][1] if emitted else None


def evict_ui_operations(slack_ui, ui, now, cap=None):
    """FR-35345-6: a terminal record older than the relay's receipt retention
    goes; then terminal records oldest-first down to `cap`. An open record is
    never evicted (the tick settles it). Returns whether anything went."""
    cap = slack_ui.UI_OPERATIONS_MAX if cap is None else cap
    operations = ui["operations"]
    stale = [op_id for op_id, rec in operations.items()
             if not ui_stage_open(rec.get("stage")) and now - ui_operation_age(rec) > UI_TERMINAL_RETENTION_S]
    for op_id in stale:
        del operations[op_id]
    evicted = list(stale)
    if len(operations) > cap:
        evictable = sorted((op_id for op_id, rec in operations.items() if not ui_stage_open(rec.get("stage"))),
                           key=lambda op_id: ui_operation_age(operations[op_id]))
        for op_id in evictable[: len(operations) - cap]:
            del operations[op_id]
            evicted.append(op_id)
    return bool(evicted)


def ui_stamp_epoch(slack_ui, stamp):
    try:
        return slack_ui.epoch(stamp) if stamp else 0.0
    except ValueError:
        return 0.0


def prune_ui_tables(slack_ui, ui, now):
    """FR-35345-6 on every save that touches `checkpoint.ui`: operations
    (above); presentations past `expires_at` + the action retention marked
    `expired`, then to the cap — `expired` first, then `fallback`, then the
    least recently active live card; consumed event ids to their FIFO cap."""
    changed = evict_ui_operations(slack_ui, ui, now)
    cards = ui["presentations"]
    for card in cards.values():
        expires_at = ui_stamp_epoch(slack_ui, card.get("expires_at"))
        if (card.get("state") in (slack_ui.PRESENTATION_LIVE, slack_ui.PRESENTATION_REVISION_UNKNOWN,
                                  slack_ui.PRESENTATION_SETTLED)
                and expires_at and now > expires_at + UI_ACTION_RETENTION_S):
            card["state"] = slack_ui.PRESENTATION_EXPIRED
            changed = True
    if len(cards) > slack_ui.UI_PRESENTATIONS_MAX:
        def rank(item):
            card = item[1]
            if card.get("state") == slack_ui.PRESENTATION_EXPIRED:
                return (0, ui_stamp_epoch(slack_ui, card.get("expires_at")))
            if card.get("state") == slack_ui.PRESENTATION_FALLBACK:
                return (1, ui_stamp_epoch(slack_ui, card.get("posted_at")))
            return (2, ui_stamp_epoch(slack_ui, card.get("last_event_at") or card.get("posted_at")))
        for ui_id, _ in sorted(cards.items(), key=rank)[: len(cards) - slack_ui.UI_PRESENTATIONS_MAX]:
            del cards[ui_id]
        changed = True
    if len(ui["consumed_event_ids"]) > slack_ui.UI_CONSUMED_EVENTS_MAX:
        ui["consumed_event_ids"] = ui["consumed_event_ids"][-slack_ui.UI_CONSUMED_EVENTS_MAX:]
        changed = True
    return changed


def retry_ui_operation(slack_ui, cli, own_id, state_file, op_id, output_format, unattended_grace_s, *, surface=True):
    """FR-35345-3(b)/(c), FM-35345-7: re-send ONE operation by its original id
    through `muse-mailbox retry` (saved ciphertext; INV-35345-8), outside the
    lock. Exit 0 returns it to `submitted` with a fresh deadline; the CLI
    naming the missing saved message is terminal `not_sent` (the operation's
    marks undone by key); any other failure is `uncertain`, never `not_sent`
    (the send may have completed). Both are surfaced once — by this call from
    the listener, or (`surface=False`, the next `reply` on the lane taking up
    a stale record) left `surfaced_at: null` for the listener's next tick: a
    `reply` process has no conversation stream to print to. A record a result
    settled while the retry ran is left as the result left it."""
    with StateStore() as store:
        state = store.load(require=True)
        operation = ui_tables(state["checkpoint"])["operations"].get(op_id)
    if operation is None or operation.get("stage") not in (slack_ui.STAGE_RETRY_WAIT, slack_ui.STAGE_SUBMITTING):
        return  # a result landed between the sweep and now
    try:
        proc = run_mailbox_cli(cli, [
            "retry", "--mailbox-id", own_id, "--state-file", state_file,
            "--message-id", op_id, "--target-mailbox-id", operation.get("relay") or "",
        ])
        code, stderr = proc.returncode, proc.stderr or ""
    except ConnectorError as error:
        code, stderr = -1, str(error)
    lines = [line for line in stderr.strip().splitlines() if line.strip()]
    cause = lines[-1].strip() if lines else f"exit {code}"
    now = ui_now()
    emitted = []
    with StateStore() as store:
        state = store.load(require=True)
        checkpoint = state["checkpoint"]
        ui = ui_tables(checkpoint)
        operation = ui["operations"].get(op_id)
        if operation is None or operation.get("stage") not in (slack_ui.STAGE_RETRY_WAIT, slack_ui.STAGE_SUBMITTING):
            return  # a result settled the record while the retry ran: it stands
        alias = operation.get("lane")
        lane = (checkpoint.get("lanes") or {}).get(alias)
        if code == 0:
            ui["operations"][op_id] = slack_ui.mark_submitted(operation, now=now)
            diag(f"ui retry sent (op {op_id}, lane {alias})")
        else:
            if "no saved message" in cause.lower():
                status, reason = slack_ui.NOT_SENT, "no saved message"
            else:
                status, reason = "uncertain", f"retry failed: {cause}"
            terminal = slack_ui.mark_terminal(operation, now=now, status=status, reason=reason).operation
            terminal.pop("text", None)  # #36324: in-flight words only
            if not surface:
                terminal["surfaced_at"] = None  # the listener's tick surfaces it
            ui["operations"][op_id] = terminal  # kept terminal for the retention window (FR-35345-6)
            clear_pending_pointer(ui, op_id)
            if status == slack_ui.NOT_SENT and lane is not None:
                ui_undo_operation_marks(lane, ui, op_id)
            diag(f"ui operation {status}: {reason} (op {op_id}, lane {alias}); "
                 f"{'surfaced' if surface else 'surfaced on the next tick'}")
            if surface:
                emitted = surface_ui_operation(checkpoint, op_id, terminal, status, reason, unattended_grace_s)
        evict_bounded(checkpoint)
        store.save(state)
    emit_ui_lines(emitted, output_format)


def stale_submitting_operations(slack_ui, ui, now, alias=None):
    """FM-35345-7: the `submitting` records (of one lane, or any) older than
    the deadline — a `reply` that died between its record and `send` returning."""
    return [op_id for op_id, rec in ui["operations"].items()
            if (alias is None or rec.get("lane") == alias) and rec.get("stage") == slack_ui.STAGE_SUBMITTING
            and now - (ui_stamp_epoch(slack_ui, rec.get("started_at")) or now) > slack_ui.UI_RESULT_DEADLINE_S]


def take_up_stale_operations(slack_ui, cli, alias):
    """FM-35345-7's third taker: the next `reply` on the lane retries its
    stale `submitting` records by id before that reply is judged. Outcomes
    are recorded, not printed (this is the tool call's process); the
    listener's tick surfaces a `not_sent` / `uncertain` it left."""
    now = ui_now()
    with StateStore() as store:
        state = store.load(require=True)
        stale = stale_submitting_operations(slack_ui, ui_tables(state["checkpoint"]), now, alias=alias)
        mailbox = state.get("mailbox") or {}
        own_id, state_file = mailbox.get("client_mailbox_id"), mailbox.get("state_file") or mailbox_cli_state_file()
    for op_id in stale:
        if own_id:
            retry_ui_operation(slack_ui, cli, own_id, state_file, op_id, None, UNATTENDED_GRACE_S_DEFAULT,
                               surface=False)


def ui_tick(cli, own_id, state_file, output_format, unattended_grace_s):
    """The listener's UI sweep (FR-35345-3(b), FR-35345-6, FM-35345-7) at
    start-up and every disconnect-poll tick: a `submitted` operation past its
    deadline is `uncertain`, surfaced once; a `retry_wait` one past `retry_at`,
    or a `submitting` record older than the deadline (a `reply` that died
    mid-send), is retried by its original id; the tables are pruned. No
    thread, no timer."""
    try:
        slack_ui = slack_ui_module()
    except ConnectorError:
        return  # a script without slack_ui.py serves every plain verb (Constitution XIII)
    now = ui_now()
    emitted = []
    due = []
    with StateStore() as store:
        state = store.load(require=True)
        checkpoint = state["checkpoint"]
        tables = checkpoint.get("ui") or {}
        if not tables.get("operations") and not tables.get("presentations"):
            return  # nothing in flight, nothing to write
        ui = ui_tables(checkpoint)
        changed = False
        due.extend(stale_submitting_operations(slack_ui, ui, now))  # FM-35345-7: no `reply` is still sending these
        for op_id, operation in list(ui["operations"].items()):
            stage = operation.get("stage")
            if stage == slack_ui.STAGE_RETRY_WAIT:
                if slack_ui.retry_due(operation, now=now):
                    due.append(op_id)
                continue
            if (stage == slack_ui.STAGE_TERMINAL and operation.get("status") in (slack_ui.NOT_SENT, "uncertain")
                    and not operation.get("surfaced_at")):
                # A reply's take-up (FM-35345-7) classified it; this tick tells the owner.
                surfaced = dict(operation, surfaced_at=slack_ui.iso(now))
                ui["operations"][op_id] = surfaced
                changed = True
                emitted.extend(surface_ui_operation(checkpoint, op_id, surfaced, surfaced["status"],
                                                    surfaced.get("reason"), unattended_grace_s))
                continue
            if stage == slack_ui.STAGE_SUBMITTING:
                continue  # collected above
            if stage == slack_ui.STAGE_SUBMITTED and slack_ui.operation_deadline_passed(operation, now=now):
                expired = slack_ui.expire_operation(operation, now=now).operation
                expired.pop("text", None)  # #36324: in-flight words only
                ui["operations"][op_id] = expired
                clear_pending_pointer(ui, op_id)
                changed = True
                diag(f"ui operation uncertain: {expired['reason']} (op {op_id}, lane {operation.get('lane')}); surfaced")
                emitted.extend(surface_ui_operation(checkpoint, op_id, expired, "uncertain",
                                                    expired["reason"], unattended_grace_s))
        if prune_ui_tables(slack_ui, ui, now):
            changed = True
        if changed:
            evict_bounded(checkpoint)
            store.save(state)  # INV-1: persist before emit
    emit_ui_lines(emitted, output_format)
    for op_id in due:
        retry_ui_operation(slack_ui, cli, own_id, state_file, op_id, output_format, unattended_grace_s)


def listen_mailbox(args):
    """Worker-side Mailbox transport (FR-23499-9 / D21, amended; now
    `adr:23499-slack-connector-runtime-contract#D6`): shell out to the
    `muse-mailbox` CLI, which reaches the Muse Code Session Mailbox with its own
    transport auth — no OAuth token on the worker. The
    connector registers the mailbox, then streams the CLI's `listen
    --decode-json` output, mapping each decoded line to the standard envelope.
    Persist-before-emit reuses the shared checkpoint; the CLI owns the
    transport cursor via its --state-file (the resume point — D20 replays
    nothing), so the connector's own cursor field stays unused (vestigial) in
    mailbox mode."""
    mailbox_id = getattr(args, "mailbox_id", None)
    output_format = emit_format(mailbox_seams_enabled())
    cli = mailbox_cli()
    state_file = mailbox_cli_state_file()
    hint_args = mailbox_cli_hint_args(args)
    max_lines_raw = os.environ.get("SLACK_CONNECTOR_MAX_POLLS") if mailbox_seams_enabled() else None
    max_lines = int(max_lines_raw) if max_lines_raw else None

    # Ensure the shared checkpoint exists and mark this transport up. The CLI
    # owns the transport cursor, so the connector cursor stays None/vestigial in
    # mailbox mode.
    with StateStore() as store:
        state = store.load() or {"schema_version": SCHEMA_VERSION}
        mailbox = state.get("mailbox") or {}
        prior_id = mailbox.get("client_mailbox_id")
        # #37011: the previous session's last mailbox heartbeat, read BEFORE
        # this listen writes anything — with `prior_id` it is the whole
        # evidence that a held id is this host's own dead session
        # (`SelfHeldRetry`; `checkpoint.last_poll_at` is the Slack poller's).
        prior_last_poll_at = mailbox.get("last_poll_at")
        # Snapshot for the register-failure rollback below: the `connected`
        # write ahead of `register` is only justified once that register wins.
        prior_mailbox = dict(mailbox)
        if not mailbox_id:
            # D13: `--mailbox-id` is optional. Prefer the id this worker already
            # registered, so a restart reattaches its own mailbox and the peers
            # addressing it keep working; derive one only when there is none.
            # Derivation is a FALLBACK, never an override — a Mac that gets
            # renamed mid-session must not orphan its live mailbox.
            mailbox_id = prior_id or derive_mailbox_id()
            diag(f"no --mailbox-id given; using {mailbox_id!r}")
        daemon_skill = bool(
            getattr(args, "daemon_skill", False)
            or (prior_id == mailbox_id and mailbox.get("daemon_skill"))
        )
        # FR-002b no-clobber: a LIVE connection to a DIFFERENT id must not be
        # silently replaced by a bare `listen <other>`. Evaluated BEFORE this
        # listen marks itself up, so the guard reads the previous connection's
        # state rather than its own. #37686: "live" is the listener lease
        # another process holds, not the `connected` flag alone — the flag
        # survives every exit, so a flag-only guard refused each id switch
        # after a restart; a `connected` record with no live listener is a
        # dead session's and is taken over (the binding moves below).
        if (
            prior_id
            and prior_id != mailbox_id
            and mailbox.get("connected") is True
            and another_mailbox_listener_is_live()
        ):
            # #29361 (QA round 10): under a Monitor the model reads stdout, never
            # stderr, so the refusal is one self-describing stdout line first
            # (outcome + next, ADR 25011 D27 item 2); the guard, its stderr
            # wording and the exit code are unchanged.
            say_outcome(live_switch_refusal(prior_id, mailbox_id))
            raise ConnectorError(
                f"listen: mailbox {prior_id!r} is still connected; run `disconnect` before "
                f"streaming {mailbox_id!r} (refusing to clobber a live connection)"
            )
        stale_local_id = bool(prior_id) and prior_id != mailbox_id
    # #37686: this listen is going ahead, so it holds the lease the guard
    # reads (see `ensure_mailbox_listener_lease`) — taken BEFORE the write
    # below and outside the state lock. A holder draining a `disconnect`
    # stops on the down flag that write raises again and reads it under the
    # lock, so writing first kept it streaming the old id for the whole
    # budget and this listen streamed unleased (addendum review of PR #37691).
    ensure_mailbox_listener_lease()
    with StateStore() as store:
        state = store.load() or {"schema_version": SCHEMA_VERSION}
        if "checkpoint" not in state:
            state["checkpoint"] = fresh_checkpoint(None)
        mailbox = state.get("mailbox") or {}
        # #37686 (round-4 review of PR #37691): a `disconnect` that landed
        # DURING the lease wait must not be wiped by the write below. Up in
        # the pre-wait snapshot and down now is a stop aimed at this start —
        # honored, as a disconnect during register is. A record already down
        # before the wait is the ADR 23499 D9 start-verb case this listen clears.
        disconnected_during_wait = (
            prior_mailbox.get("connected") is not False and mailbox.get("connected") is False
        )
        if not disconnected_during_wait:
            if stale_local_id:
                # #37011 (review of PR #37071): the heartbeat travels with its id.
                # The pre-register write below renames the binding; the OLD id's
                # stamp must not ride under the NEW one, or a foreign hold on the
                # new id would read as this host's own session on the next
                # listen. `prior_mailbox` (above) still restores the old record
                # whole on a failed register.
                mailbox.pop("last_poll_at", None)
                prior_last_poll_at = None
            # ADR 23499 D9: `listen` IS the start verb, so it clears a prior
            # `disconnect` instead of exiting on it. A `disconnect` against a
            # LIVE stream still stops that stream — the in-loop check below owns that.
            mailbox["connected"] = True
            mailbox.pop("disconnected_at", None)
            mailbox["client_mailbox_id"] = mailbox_id
            state["mailbox"] = mailbox
            store.save(state)
    if disconnected_during_wait:
        diag("mailbox transport disconnected during the lease wait (run `listen` again to resume); listener exiting")
        return 0
    if stale_local_id:
        # Finding #7, carried over from the deleted `connect`: our own
        # --state-file still records the DEAD prior run's mailbox id, and the
        # CLI would refuse to reattach a new id from it — a LOCAL conflict, not
        # a remote 409. The live case already raised above, so reaching here
        # means that connection is gone; reset the connector-owned file.
        diag(f"local state served mailbox {prior_id!r}; resetting it to attach {mailbox_id!r}")
        reset_mailbox_cli_state(state_file)

    # Register/reattach the mailbox (one-shot). `listen` also auto-registers, but
    # an explicit register surfaces a transport/auth failure before streaming and
    # lets `reply` (a separate process) learn this worker's own mailbox id.
    # #37011: one re-attach budget for both places a hold can surface.
    self_held_retry = SelfHeldRetry(mailbox_id, prior_mailbox)
    while True:
        register_failure = None
        held = False
        try:
            register = run_mailbox_cli(
                cli, ["register", "--mailbox-id", mailbox_id, "--state-file", state_file, *hint_args],
                timeout=mailbox_register_timeout_s(),
            )
        except ConnectorError as error:
            # A missing binary or a hung/timed-out register is still a fatal transport
            # failure: exit EXIT_FATAL_LISTEN so the coordinator restarts, matching the
            # non-zero-exit path below (NOT the generic EXIT_ERROR from main).
            register_failure = f"muse-mailbox register failed ({error}); ending the mailbox listener"
        else:
            if register.returncode != 0:
                lines = [ln for ln in (register.stderr or register.stdout or "").splitlines() if ln.strip()]
                if mailbox_conflict_held(lines[-1] if lines else ""):
                    # D7 folded `connect` in here, so its actionable conflict diagnostic
                    # has to survive: the operator must know to pick another id or wait
                    # for the holder's registration to expire, never that we hijacked it.
                    held = True
                    register_failure = (
                        f"mailbox {mailbox_id!r} is already held by another client; wait for its "
                        "registration to expire or choose a different mailbox id (refusing to hijack it)"
                    )
                else:
                    # #29361: carry the CLI's last stderr line (repr: one line,
                    # escapes kept) so the daemon can report the cause, not "exit 1".
                    cause = f": {lines[-1].strip()!r}" if lines else ""
                    register_failure = (
                        f"muse-mailbox register failed (exit {register.returncode}{cause}); "
                        "ending the mailbox listener"
                    )
        step = self_held_retry.next_step() if held else None
        if step == "retry":
            continue
        if step == "disconnect":
            diag("mailbox transport disconnected during the self-held retry (run `listen` again to resume); listener exiting")
            return 0
        if step == "parent death":
            restore_mailbox_record(prior_mailbox, mailbox_id, state_file)
            return owner_died_exit()
        break
    if register_failure:
        # The failure exit every register arm reaches (the one other exit, the
        # owner dying during a self-held wait above, runs the same rollback
        # without printing into a dead owner's stdout): the pre-register write
        # said "connected to `mailbox_id`", and that claim just proved false. Left standing, the FR-002b no-clobber guard defends the
        # phantom and refuses the operator's next `listen --mailbox-id <other>`.
        # #29361: the model reads stdout, never this stderr line — say it there
        # first (outcome + next, ADR 25011 D27 item 2); the exit is unchanged,
        # and a gone reader (#27885) must not skip the rollback below.
        say_outcome(register_failure_line(mailbox_id, register_failure, held))
        diag(register_failure)
        # #30326: the same rollback moves the CLI state file this register
        # bound to `mailbox_id` aside (see restore_mailbox_record).
        restore_mailbox_record(prior_mailbox, mailbox_id, state_file)
        return EXIT_FATAL_LISTEN
    # D20 item 1: one probe per listener, outside the state lock (two `--help`
    # runs), persisted with the registration so `reply` never re-probes.
    capabilities = probe_mailbox_cli_capabilities(cli)
    diag(f"muse-mailbox capabilities: edit={capabilities['edit']} attach={capabilities['attach']}")
    # One directory snapshot, shared by tag publication and relay discovery.
    listing = probe_mailbox_listing(cli)
    published_tags = None
    tag_error = None
    if daemon_skill:
        # Either half of the publication can blip: the directory read that
        # names our current tags, or the `register --tag` write itself. Retry
        # the whole thing — re-probing the snapshot each time, since a stale
        # one is exactly what a retry is for — and only settle for a warning
        # once every attempt has failed.
        for attempt in range(1, MAILBOX_TAG_PUBLISH_ATTEMPTS + 1):
            try:
                published_tags = publish_daemon_skill_tags(
                    cli, mailbox_id, state_file, hint_args, listing
                )
                tag_error = None
                break
            except ConnectorError as error:
                tag_error = str(error)
                if attempt == MAILBOX_TAG_PUBLISH_ATTEMPTS:
                    break
                diag(
                    f"tag publication attempt {attempt} of "
                    f"{MAILBOX_TAG_PUBLISH_ATTEMPTS} failed ({tag_error}); retrying"
                )
                time.sleep(mailbox_tag_retry_delay_s())
                listing = probe_mailbox_listing(cli)
    # ADR 35345 D15 item 1: the relays' `custom.slack.ui` versions, once per
    # registration — read from the last snapshot the retry loop obtained.
    ui_versions = relay_ui_versions_from_listing(listing)
    diag("relay custom.slack.ui versions: " + (", ".join(f"{k}={v}" for k, v in sorted(ui_versions.items())) or "none advertised"))
    # D20 item 5: a CLI that takes `--attach` also takes `--attachment-dir`
    # (same stack); name a private dir under the connector's state so every
    # inbound `local_path` is absolute and ours (an older CLI would reject the
    # flag, so it rides the probe verdict). Verified on the real CLI (#28777
    # smoke): the CLI materialises with or without the flag — without it the
    # path is relative to its state file — so the flag decides WHERE, never
    # WHETHER; the verdict alone names it (#30562).
    attachment_args = []
    if capabilities.get("attach"):
        attachment_dir = attachments_dir()
        os.makedirs(attachment_dir, mode=0o700, exist_ok=True)
        os.chmod(attachment_dir, 0o700)
        attachment_args = ["--attachment-dir", attachment_dir]
        # #30869: the alias step and its one cleanup ride this same gate — without
        # the verdict the connector stays out of that directory entirely.
        global ATTACHMENT_ALIAS_DIR
        ATTACHMENT_ALIAS_DIR = attachment_dir
        drop_dangling_attachment_aliases(attachment_dir)
    with StateStore() as store:
        state = store.load(require=True)
        # MERGE, don't replace: a concurrent `disconnect` may have set
        # connected=False during the (multi-second) register call. A wholesale
        # `state["mailbox"] = {...}` would drop that flag, so every later 3s poll
        # would see no flag and stream forever (finding #4). Preserve it, then
        # honor it below.
        mailbox = state.get("mailbox") or {}
        # The reload is what preserves a concurrent `disconnect`'s
        # connected=False; the register update deliberately does not touch that key. A
        # wholesale `state["mailbox"] = {...}` would drop it, so every later 3s
        # poll would see no flag and stream forever (finding #4).
        mailbox.update(
            {
                "client_mailbox_id": mailbox_id,
                "state_file": state_file,
                "cli_capabilities": capabilities,
                RELAY_UI_VERSIONS_KEY: ui_versions,
                "daemon_skill": daemon_skill,
            }
        )
        if published_tags is not None:
            mailbox["published_tags"] = published_tags
        if tag_error is not None:
            # A tag read or write failure is loud, not fatal: the listener keeps
            # serving on the tags the directory already holds, so one transient
            # directory flake cannot take the daemon's peer inbox down. Persist
            # the reason so `status --json` names the mis-tagged state rather
            # than leaving it silent.
            mailbox.pop("published_tags", None)
            mailbox[MAILBOX_TAG_ERROR_KEY] = tag_error
        else:
            mailbox.pop(MAILBOX_TAG_ERROR_KEY, None)
        state["mailbox"] = mailbox
        store.save(state)
        disconnected_during_register = mailbox.get("connected") is False
    if tag_error is not None:
        diag(
            f"WARNING: agent and daemon-skill discovery tags were NOT published "
            f"after {MAILBOX_TAG_PUBLISH_ATTEMPTS} attempts "
            f"({tag_error}); this listener keeps serving on the tags the mailbox "
            "directory already holds. Peers selecting by `daemon-skill` will not "
            "find it until a re-arm republishes them; `status --json` reports the "
            "reason under mailbox.tag_error."
        )
    if disconnected_during_register:
        diag("mailbox transport disconnected during register (run `listen` again to resume); listener exiting")
        return 0

    # D20: nothing is replayed — the CLI's cursor is the resume point. The
    # liveness sweep runs at start-up and on every disconnect-poll tick.
    grace_s = unattended_grace_s(args)

    def sweep_and_emit():
        # #35345: the UI operation deadline, the same-id retry and the
        # presentation expiry ride this tick too (spec 23499 FR-35345-6).
        ui_tick(cli, mailbox_id, state_file, output_format, grace_s)
        if NATIVE_FORWARDER is not None:
            # ADR 25011 D22: liveness is decided at delivery; the tick retries
            # a coordinator that has not registered yet (inside the grace).
            NATIVE_FORWARDER.tick()
            return
        # D20 item 4: a dead coordinator's unanswered conversation wakes the
        # daemon on this listener's own tick, not only on a new message.
        for envelope in sweep_unattended_claims("mailbox", grace_s):
            emit_event(envelope, output_format)

    sweep_and_emit()

    # A bounded run of zero lines is the register-only path (used to establish
    # registration without consuming the stream).
    if max_lines is not None and max_lines == 0:
        return 0

    def reattach_register():
        """The ladder's re-register (#41206): the same `register` the start
        ran, under the same id and state file, so an expired registration is
        made again and a live one is re-attached. `("ok", None)`, `("held",
        line)` on the relay's conflict wording, `("auth"|"config", cause)` for
        a cause no retry cures (ruling 41), `("failed", cause)` otherwise."""
        try:
            again = run_mailbox_cli(
                cli, ["register", "--mailbox-id", mailbox_id, "--state-file", state_file, *hint_args],
                timeout=mailbox_register_timeout_s(),
            )
        except ConnectorError as error:
            cause_class = stream_death_class(str(error))
            return (cause_class if cause_class in ("auth", "config") else "failed"), f"muse-mailbox register failed ({error})"
        if again.returncode == 0:
            if daemon_skill:
                # Best effort, once: a registration made afresh after expiry
                # has no tags; a re-attached one keeps them. The ladder is the retry.
                try:
                    publish_daemon_skill_tags(cli, mailbox_id, state_file, hint_args, probe_mailbox_listing(cli))
                except ConnectorError as error:
                    diag(f"tag publication after re-register failed ({error}); serving on the tags the directory holds")
            return "ok", None
        lines = [ln for ln in (again.stderr or again.stdout or "").splitlines() if ln.strip()]
        last = lines[-1].strip() if lines else ""
        cause_class = stream_death_class(last)
        if cause_class == "held":
            return "held", last
        cause = f": {last!r}" if last else ""
        return (cause_class if cause_class in ("auth", "config") else "failed"), f"muse-mailbox register failed (exit {again.returncode}{cause})"

    def held_refusal(stream_failure):
        """Today's foreign-holder end, byte for byte (#37012, #38191 C10):
        one `refused` stdout line, the stderr diagnostic, EXIT_FATAL_LISTEN."""
        if not admitted_any:
            restore_mailbox_heartbeat(mailbox_id, prior_last_poll_at)
        say_outcome(stream_ended_line(mailbox_id, stream_failure, True))
        diag(stream_failure)
        return EXIT_FATAL_LISTEN

    # Stream `muse-mailbox listen --decode-json`: one decoded JSON line per
    # received message. Read line-by-line so an event is admitted as it arrives.
    listener_pid = os.getpid()
    # A plain kill (the SKILL's "kill the stray listener PID") gets the same
    # orderly stop as parent death: flag it here, stop within one poll, reap +
    # drain, then re-raise with the default disposition so the killer sees the
    # conventional status. Installed BEFORE the child exists (review: a TERM in
    # the gap between the spawn and the loop got the default disposition — no
    # drain, the child reaped only by PDEATHSIG) and only around the stream.
    # #37011: the stream is attached again after a self-held refusal; every
    # attempt installs its own handler, pipes and threads. `admitted_any`
    # is listen-wide: once any attempt ADMITTED a peer message (the write of
    # a heartbeat stamp), the stamps stand whatever the later attempts do; a
    # line read and discarded (a self-echo, a malformed line) is not that.
    admitted_any = False
    # #41206: `attached_any` is listen-wide too — the relay served a stream to
    # THIS process (a line arrived, or the child outlived the attach settle). After
    # that, a conflict refusal on a re-attach is the relay still counting this
    # process's dead stream as the holder, not a foreign client: it is waited
    # out inside the SelfHeldRetry window before the foreign refusal stands.
    attached_any = False
    # The current outage (None while the stream is up).
    ladder = None
    listen_ppid = os.getppid()
    while True:
        signalled = []

        def _on_sigterm(signum, _frame):
            signalled.append(signum)

        previous_sigterm = signal.signal(signal.SIGTERM, _on_sigterm)
        try:
            proc = subprocess.Popen(
                [cli, "listen", "--mailbox-id", mailbox_id, "--state-file", state_file,
                 "--decode-json", *hint_args, *attachment_args],
                # INV-3: never inherit the child CLI's stderr - a CLI traceback
                # (local build paths), cert path, or proxy socket diagnostic would
                # surface verbatim on the connector's operator-facing stderr. It is
                # piped and drained below; only its last line is kept, bounded, to
                # name the cause when the stream ends (#29361).
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
                # #27885: the child dies with us, even when we die uncatchably.
                preexec_fn=lambda: _bind_child_to_our_death(listener_pid),
            )
        except FileNotFoundError:
            signal.signal(signal.SIGTERM, previous_sigterm)
            raise ConnectorError(f"muse-mailbox CLI not found: {cli!r} (set {MAILBOX_CLI_ENV})")

        # A dedicated reader thread does the BLOCKING readline; the main loop pulls
        # from a queue with a timeout. select() on proc.stdout was wrong (finding #1):
        # one readline can pull several lines' bytes off the fd into Python's stream
        # buffer, where select() can't see them, so a burst delivered in one write
        # stranded every line but the first until the next write woke select. A
        # blocking readline drains all buffered lines promptly; the queue timeout
        # still lets an explicit `disconnect` stop a live stream within a poll.
        line_queue: "queue.Queue" = queue.Queue()

        def _pump_lines():
            try:
                while True:
                    chunk = proc.stdout.readline()
                    if chunk == "":
                        break  # EOF
                    line_queue.put((chunk, now_ms()))  # #28433: read_at_ms, the CLI hop's end
            finally:
                line_queue.put(None)  # EOF sentinel

        reader = threading.Thread(target=_pump_lines, name="muse-mailbox-listen", daemon=True)
        reader.start()

        # #29361 (QA round 7, lane q7b-listen): the child died with `error: mailbox
        # stream reset by peer …` on its stderr and the connector said only `listen
        # ended (exit 1)`. The register path already quotes the CLI's last stderr
        # line; the stream does the same. Drained to EOF so the child never blocks
        # on a full pipe; only the last non-empty line survives, cut to the bound
        # and later repr'd (one line, escapes kept) - INV-3 for everything else.
        last_stderr = []

        def _pump_stderr():
            try:
                for raw in proc.stderr.buffer:
                    line = raw.decode("utf-8", "replace").strip()
                    if line:
                        cut = line[:LISTEN_STDERR_TAIL] + ("…" if len(line) > LISTEN_STDERR_TAIL else "")
                        last_stderr[:] = [cut]
            except (OSError, ValueError):
                pass  # the pipe closed under us: whatever was read stands

        stderr_reader = threading.Thread(target=_pump_stderr, name="muse-mailbox-listen-stderr", daemon=True)
        stderr_reader.start()

        def admit_line(raw, read_at_ms):
            """Admit one queued line (persist-before-emit). Shared by the stream loop
            and the disconnect drain so a stop never silently loses a line the CLI
            already advanced its cursor past. Returns True when the line was an
            ADMITTED peer message — the one case that writes the mailbox
            heartbeat (#37011); a discarded line (self-echo, malformed, a UI
            result) returns False."""
            raw = raw.strip()
            if not raw:
                return False
            try:
                line_obj = json.loads(raw)
            except ValueError:
                # A malformed line must not kill the listener: discard it and keep
                # serving (the CLI already advanced its own cursor past it).
                diag("muse-mailbox listen emitted a non-JSON line; discarding (fail closed)")
                return False
            admit = admit_cli_item(line_obj, mailbox_id)
            if admit is None:
                return False
            process_cli_item(line_obj, output_format, own_id=mailbox_id,
                             unattended_grace_s=grace_s, read_at_ms=read_at_ms, admit=admit)
            return not isinstance(admit, UiInbound)

        def attached():
            """The relay is serving this attempt: the outage (if any) is over."""
            nonlocal attached_any, ladder
            attached_any = True
            if ladder is not None:
                down_s = int(ladder.down_for_s())
                ladder.recovered()
                diag(f"mailbox stream re-attached after {down_s} s ({ladder.attempts} attempt(s)); catching up")
                ladder = None

        poll_s = mailbox_disconnect_poll_s()
        idle_probe_s = mailbox_idle_probe_s()
        settle_s = mailbox_attach_settle_s()
        spawned_at = time.monotonic()
        last_disconnect_check = time.monotonic()
        last_line_at = time.monotonic()  # #41206: the hang clock, reset by every line and every passing probe
        last_heartbeat = None  # #37011: the first tick writes (a never-written sentinel, not 0.0 — monotonic starts at boot), then every SELF_HELD_HEARTBEAT_S
        lines_read = 0
        reached_eof = False
        # The early-stop reasons that reap the child and DRAIN (see the finally):
        # "disconnect", "parent death", "SIGTERM", or "hang" (#41206: the probe
        # after an idle stretch failed). None on EOF or a bounded stop.
        stop_reason = None
        # #27885: this listener must not outlive its owner. The Monitor binds only
        # its DIRECT child to owner death, and where `python3` is a forking shim
        # that child is the shim — so after a `kill -9` of the daemon this
        # interpreter and its CLI child lived on under PID 1, admitted the next
        # inbound into the shared state, and only then died on the broken pipe.
        # A reparent moves getppid; check it every iteration (a trivial syscall).
        start_ppid = os.getppid()
        try:
            while True:
                if signalled:
                    diag("SIGTERM received; stopping the listener")
                    stop_reason = "SIGTERM"
                    break
                if os.getppid() != start_ppid:
                    diag("parent process exited; stopping the listener (a remnant must not consume the stream)")
                    stop_reason = "parent death"
                    break
                # Re-check the down flag once per poll_s ELAPSED regardless of queue
                # state (the queue.Empty branch alone let a peer sending >=1 line per
                # poll_s keep a disconnected listener streaming until the first quiet
                # gap). An explicit `disconnect` must stop a live stream within a poll
                # even under continuous traffic (the CLI has no release verb).
                if time.monotonic() - last_disconnect_check >= poll_s:
                    last_disconnect_check = time.monotonic()
                    if mailbox_connection_disconnected():
                        diag("mailbox transport disconnected (run `listen` again to resume); stopping the listener")
                        stop_reason = "disconnect"
                        break
                    if proc.poll() is None and time.monotonic() - spawned_at >= settle_s:
                        attached()  # the child outlived the attach settle: the relay took the stream
                    if last_heartbeat is None or time.monotonic() - last_heartbeat >= self_held_heartbeat_s():
                        last_heartbeat = time.monotonic()
                        touch_mailbox_heartbeat()  # #37011: the heartbeat the next start reads
                    sweep_and_emit()  # same cadence, traffic or not
                try:
                    queued = line_queue.get(timeout=poll_s)
                except queue.Empty:
                    # #41206 hang detection: no line for idle_probe_s while the
                    # child lives -> one cheap relay read (the directory listing
                    # the start already reads, bounded). Failed: a dead socket,
                    # treated as a stream death. Passed: quiet, keep waiting.
                    if proc.poll() is None and time.monotonic() - last_line_at >= idle_probe_s:
                        if probe_mailbox_listing(cli) is None:
                            diag(f"no line for {idle_probe_s:g} s and the relay probe failed; treating the stream as dead")
                            stop_reason = "hang"
                            break
                        diag(f"no line for {idle_probe_s:g} s; the relay probe passed, the stream is quiet")
                        last_line_at = time.monotonic()
                    continue
                if queued is None:
                    reached_eof = True
                    break  # EOF: the CLI process ended
                lines_read += 1
                last_line_at = time.monotonic()
                attached()
                admitted_any = admit_line(*queued) or admitted_any
                if max_lines is not None and lines_read >= max_lines:
                    break  # bounded test run: stop after N lines
        finally:
            signal.signal(signal.SIGTERM, previous_sigterm)
            # Only stop the child on an early/abnormal exit path (bounded stop,
            # disconnect, parent death, SIGTERM, hang, or a propagating exception). On a
            # clean EOF the child is already exiting, so terminating it here could
            # turn its real exit code into a SIGTERM. The reader thread is a daemon
            # and unblocks when the child's stdout closes.
            if not reached_eof and proc.poll() is None:
                _terminate_child(proc)
            if stop_reason is not None:
                # Drain AFTER killing the child (not before): a live producer can emit
                # faster than one admit (each admit rewrites all of state.json), so a
                # drain-while-alive either never ends (get_nowait always non-empty) or
                # drops lines written between a momentary empty and SIGTERM — the FR-010
                # loss it exists to prevent. Killing the child first BOUNDS the stream;
                # the reader then queues every line the CLI wrote before EOF and a final
                # None sentinel, so this BLOCKING drain admits them all (persist-before-
                # emit) and a resume replays them.
                drained = 0
                while True:
                    pending_line = line_queue.get()  # bounded: child is dead -> reader hits EOF -> None
                    if pending_line is None:
                        break
                    try:
                        admitted_any = admit_line(*pending_line) or admitted_any
                    except OSError:
                        # The emit after the persist hit a dead reader (our owner is
                        # gone): the line is already durable, keep draining.
                        pass
                    drained += 1
                diag(f"drained {drained} queued line(s) after {stop_reason} (persisted for resume replay)")

        if stop_reason == "SIGTERM":
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            os.kill(os.getpid(), signal.SIGTERM)
        if stop_reason == "parent death":
            return owner_died_exit()  # the stream has no consumer; a restart re-arms and replays
        if not reached_eof and stop_reason != "hang":
            return 0  # bounded test run drained its cap, or a `disconnect` stopped it cleanly

        # The stream ended (EOF, or the hang probe ended it): reap the true exit
        # code. In a bounded test run a clean CLI exit (rc 0) is a complete drain
        # and ends the listener cleanly; a non-zero exit — and, in production,
        # any exit at all — is a stream that died. #41206 (owner ruling 39): a
        # death is not the end of the listener. It re-attaches on the ladder
        # below for as long as the id is this host's; only a foreign holder,
        # a `disconnect` or the owner's death ends it.
        rc = proc.wait()
        if mailbox_seams_enabled() and rc == 0 and stop_reason != "hang":
            attached()  # a bounded drain served the stream: the outage (if any) is over
            return 0
        # The child is gone, so its stderr is at EOF or nothing was written; the
        # join is bounded in case a grandchild still holds the pipe's write end.
        stderr_reader.join(timeout=1.0)
        cause = f": {last_stderr[0]!r}" if last_stderr else ""
        if stop_reason == "hang":
            ended = f"muse-mailbox listen hung (no line for {idle_probe_s:g} s, relay probe failed; child ended with exit {rc}{cause})"
        else:
            ended = f"muse-mailbox listen ended (exit {rc}{cause})"
        # #37012: the relay refuses the stream (not the register) when the previous
        # holder's registration has not expired; same classifier as the register
        # path, so the model reads "held, wait for expiry", not raw relay JSON.
        # #41206 (ruling 41): the same last line names a cause no retry cures.
        cause_class = stream_death_class(last_stderr[0]) if last_stderr else "transient"
        held = cause_class == "held"
        if cause_class in ("auth", "config"):
            set_mailbox_reconnecting(mailbox_id, None)
            stream_failure = f"{ended}; ending the mailbox listener"
            say_outcome(mailbox_stopped_line(mailbox_id, stream_failure, cause_class))
            diag(stream_failure)
            return EXIT_FATAL_LISTEN
        if held and not attached_any:
            # #37011: never attached in this listen and the relay says held —
            # this host's own previous session (the pre-listen snapshot's
            # verdict) is waited out inside the window with today's one
            # `retrying` line; a foreign hold, or a spent window, is the
            # unchanged refusal.
            stream_failure = f"mailbox {mailbox_id!r} is already held by another client: {ended}; ending the mailbox listener"
            step = self_held_retry.next_step()
            if step == "retry":
                continue
            if step == "disconnect":
                diag("mailbox transport disconnected during the self-held retry (run `listen` again to resume); stopping the listener")
                return 0
            if step == "parent death":
                return owner_died_exit()
            return held_refusal(stream_failure)

        # --- the reconnect ladder (#41206) ---
        if ladder is None:
            ladder = ReconnectLadder(mailbox_id, listen_ppid)
        ladder.last_error = ended
        delay = ladder.delay_for(held)
        while True:
            if delay is None:
                # A run of conflict refusals outlived the SelfHeldRetry window:
                # the id is another client's now. Today's held end.
                set_mailbox_reconnecting(mailbox_id, None)
                return held_refusal(
                    f"mailbox {mailbox_id!r} is already held by another client: {ended}; ending the mailbox listener")
            diag(f"{ended}; re-attaching in {delay:g} s (attempt {ladder.attempts + 1}, down {int(ladder.down_for_s())} s)")
            step = ladder.wait(delay)
            if step == "disconnect":
                set_mailbox_reconnecting(mailbox_id, None)
                diag("mailbox transport disconnected while re-attaching (run `listen` again to resume); stopping the listener")
                return 0
            if step == "parent death":
                set_mailbox_reconnecting(mailbox_id, None)
                diag("parent process exited while re-attaching; stopping the listener")
                return owner_died_exit()
            verdict, detail = reattach_register()
            if verdict == "ok":
                break  # the outer loop attaches the stream again
            held = verdict == "held"
            ended = f"muse-mailbox register refused ({detail!r})" if held else detail
            if verdict in ("auth", "config"):
                set_mailbox_reconnecting(mailbox_id, None)
                stream_failure = f"{ended}; ending the mailbox listener"
                say_outcome(mailbox_stopped_line(mailbox_id, stream_failure, verdict))
                diag(stream_failure)
                return EXIT_FATAL_LISTEN
            ladder.last_error = ended
            delay = ladder.delay_for(held)


def build_peer_message_body(text, conversation_id=None):
    """Assemble the canonical `peer_message` body: kind + text + the fixed
    delivery/wake policies, with an optional conversation_id. These five keys
    are the WHOLE v1 body and nothing may be added to them.

    The mailbox edit (pre-cutover ledger D24, now
    `adr:23499-slack-connector-runtime-contract#D8`) does NOT ride here. An earlier draft put a
    `replaces_message_id` pointer in this body; spec 14516 closed v1 ("V1 is
    closed and never gains fields or enum values. An extension requires a new
    envelope version and explicit capability negotiation"), and the receiving
    decoder enforces it — `AgentBodyWire` is `#[serde(deny_unknown_fields)]`
    (`crates/agent-peer/src/session_message_routing/mailbox_provider/envelope.rs`),
    so an unaware receiver rejects the WHOLE envelope as malformed and loses
    the update outright. That is strictly worse than the silent drop D24 was
    written to avoid. Supersession is therefore CONNECTOR-side only: the lane
    remembers what it superseded, the edit goes out as a plain `peer_message`,
    and the caller learns what happened from the receipt's `supersedes` /
    `folded` fields."""
    body = {
        "kind": PEER_MESSAGE_KIND,
        "text": text,
        "delivery_policy": PEER_DELIVERY_POLICY,
        "wake_policy": PEER_WAKE_POLICY,
    }
    if conversation_id:
        body["conversation_id"] = conversation_id
    return body


def public_mailbox_receipt(receipt):
    return {
        key: receipt[key]
        for key in ("status", "message_id", "idempotency_key", "target_client_mailbox_id",
                    "target_message_id", "attachments")
        if key in receipt
    }


def last_json_line(stdout):
    """The CLI's receipt: its last stdout line that parses as a JSON object."""
    for line in reversed((stdout or "").strip().splitlines()):
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return {}


def mailbox_sender():
    """This worker's own mailbox id and the CLI state file the listener
    persisted (fall back to the env default only if no listen registered)."""
    with StateStore() as store:
        state = store.load() or {}
        mailbox = state.get("mailbox") or {}
    sender_id = mailbox.get("client_mailbox_id")
    if not sender_id:
        raise ConnectorError(
            "no mailbox registration: arm the mailbox `listen` first (the daemon's startup sequence; --mailbox-id optional)"
        )
    return sender_id, mailbox.get("state_file") or mailbox_cli_state_file()


def store_mailbox_receipt(idempotency_key, receipt):
    """First writer wins (FM-6): a same-key racer's receipt is the one kept."""
    with StateStore() as store:
        state = store.load(require=True)
        existing = state["checkpoint"]["reply_receipts"].get(idempotency_key)
        if existing is None:
            state["checkpoint"]["reply_receipts"][idempotency_key] = receipt
            evict_bounded(state["checkpoint"])
            store.save(state)
            return receipt
        return existing


def mailbox_edit(route, idempotency_key, target_message_id, text):
    """`adr:23499-slack-connector-runtime-contract#D20` item 2: ONE
    `message_edit` for the lane's original published message, through
    `muse-mailbox edit` (the Session Mailbox edit stack; the same authenticated
    send path and receipt as `send`). The body is exactly the stack's shape —
    conversation, kind, target, text — never a v1 field (D6 stands). Keyed
    like `send`: a same-key repeat returns the recorded receipt without a CLI
    call (the identical re-run that posted a duplicate on the successor path,
    #28777 QA round 11, now posts nothing); a same-key different text or
    target fails closed; a non-zero exit records nothing so a retry re-sends.
    The edit's own operation id is the connector's stable `message_id_from_key`,
    which the relay dedups on."""
    target = route.get("target_client_mailbox_id")
    conversation_id = route.get("conversation_id")
    if not target or not conversation_id or not target_message_id:
        raise ConnectorError("this lane cannot take a mailbox edit (no target, conversation or original id)")
    body = {
        "conversation_id": conversation_id,
        "kind": MESSAGE_EDIT_KIND,
        "target_message_id": target_message_id,
        "text": text,
    }
    client_env = {"version": CLIENT_ENVELOPE_VERSION, "to_role": "agent", "body": body}
    payload_json = json.dumps(client_env, separators=(",", ":"), sort_keys=True)
    if len(payload_json.encode("utf-8")) > CLIENT_PAYLOAD_MAX_BYTES:
        raise InputError(f"edit payload exceeds {CLIENT_PAYLOAD_MAX_BYTES} bytes; refusing to send")
    payload_sha = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    message_id = message_id_from_key(idempotency_key)
    with StateStore() as store:
        state = store.load(require=True)
        existing = state["checkpoint"]["reply_receipts"].get(idempotency_key)
    if existing is not None:
        if existing.get("status") != "edited":
            raise ConnectorError("idempotency key was already used by a non-edit receipt; refusing to reuse it")
        if existing.get("target_client_mailbox_id") != target or existing.get("target_message_id") != target_message_id:
            raise ConnectorError("idempotency key was already used with a different target; refusing to reuse it")
        if existing.get("payload_sha256") != payload_sha:
            raise ConnectorError("idempotency key was already used with a different payload; refusing to reuse it")
        return public_mailbox_receipt(existing)
    sender_id, send_state_file = mailbox_sender()
    if target == sender_id:
        raise ConnectorError("refusing to edit in this worker's own mailbox id (self-echo lane)")
    # `--text=<t>`: a dash-leading text (`--done`) must not read as a flag to
    # argparse (review round 2 of #30528).
    sent = run_mailbox_cli(mailbox_cli(), [
        "edit", "--mailbox-id", sender_id, "--state-file", send_state_file,
        "--target-mailbox-id", target, "--conversation-id", conversation_id,
        "--target-message-id", target_message_id, f"--text={text}", "--message-id", message_id,
    ])
    if capability_rejected(sent, "edit"):
        # argparse names the missing verb: this CLI has no `edit` (rolled back,
        # or another build) — the verdict was stale. Clear it; the caller posts
        # D8's successor now. Any other non-zero exit, exit 2 included, is the
        # ordinary send failure below: no receipt, verdict untouched.
        clear_mailbox_capability("edit")
        raise CapabilityRejected("muse-mailbox rejected `edit` (invalid choice); the cached edit verdict is cleared")
    if sent.returncode != 0:
        raise ConnectorError(
            f"muse-mailbox edit failed (exit {sent.returncode}); recorded no receipt so a retry re-sends the edit"
        )
    receipt = store_mailbox_receipt(idempotency_key, {
        "status": "edited",
        "idempotency_key": idempotency_key,
        "message_id": message_id,
        "target_message_id": target_message_id,
        "target_client_mailbox_id": target,
        "payload_sha256": payload_sha,
        "queued_at": utc_now(),
    })
    return public_mailbox_receipt(receipt)


def mailbox_reply(route, idempotency_key, text, attach=()):
    """Mailbox arm of `reply` (FR-23499-9 / D21, amended; now
    `adr:23499-slack-connector-runtime-contract#D6`): enqueue a canonical
    `peer_message` client envelope to the lane's mailbox by shelling out to
    `muse-mailbox send` — no OAuth token (the CLI owns transport and auth).
    Idempotent by key: a same-key repeat
    returns the recorded receipt WITHOUT re-invoking the CLI, a same-key
    DIFFERENT target/payload fails closed, and a non-zero CLI exit records NO
    receipt so a retry re-sends. The connector passes its stable
    `message_id_from_key` to the CLI as `--message-id` (and keeps it in the
    receipt), so a re-send after a crash reuses the id and the receiver dedups."""
    target = route.get("target_client_mailbox_id")
    if not target:
        raise ConnectorError("this lane has no mailbox target recorded; it cannot be replied to")
    body = build_peer_message_body(
        text, route.get("conversation_id")
    )
    cli = mailbox_cli()
    state_file = mailbox_cli_state_file()

    # Canonical envelope: only version + to_role at the top level; kind, text,
    # policies and any conversation_id live inside body.
    client_env = {
        "version": CLIENT_ENVELOPE_VERSION,
        "to_role": "agent",
        "body": body,
    }
    # The `muse-mailbox` CLI re-serializes the payload with
    # json.dumps (ensure_ascii=True), and the provider's 16 KiB bound is measured
    # on that ESCAPED form — verified live against the real CLI: a 2700-CJK
    # envelope is 16,351 escaped bytes and is accepted, 2714 is 16,435 and is
    # rejected ("opaque mailbox payload exceeds 16 KiB"), independent of how this
    # arg is serialized. Measure the same escaped form so the client-side guard
    # rejects exactly what the CLI would; compact UTF-8 would under-count and let
    # a payload through that the CLI then rejects at runtime.
    payload_json = json.dumps(client_env, separators=(",", ":"))
    if len(payload_json.encode("utf-8")) > CLIENT_PAYLOAD_MAX_BYTES:
        raise InputError(f"client payload exceeds {CLIENT_PAYLOAD_MAX_BYTES} bytes; refusing to enqueue")
    # D20 item 6: the files are part of what this key sent — a same-key repeat
    # with other files is another payload and fails closed like other text.
    attach = [str(path) for path in (attach or ())]
    digest_input = payload_json + ("\0" + "\n".join(sorted(attach)) if attach else "")
    payload_sha = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
    message_id = message_id_from_key(idempotency_key)

    with StateStore() as store:
        state = store.load() or {"schema_version": SCHEMA_VERSION}
        if "checkpoint" not in state:
            state["checkpoint"] = fresh_checkpoint(None)
            store.save(state)
        existing = state["checkpoint"]["reply_receipts"].get(idempotency_key)
        if existing is not None:
            # Only an exact mailbox receipt is reusable. Every receipt respond
            # writes has all three fields; a receipt another verb wrote (e.g. a
            # Slack reply) has none of them, and tolerating the missing fields
            # would claim success with zero sends (FR-23499-9 fail-closed).
            if existing.get("status") != "queued":
                raise ConnectorError(
                    "idempotency key was already used by a non-mailbox receipt; refusing to reuse it"
                )
            if existing.get("target_client_mailbox_id") != target:
                raise ConnectorError(
                    "idempotency key was already used with a different target; refusing to reuse it"
                )
            if existing.get("payload_sha256") != payload_sha:
                raise ConnectorError(
                    "idempotency key was already used with a different payload; refusing to reuse it"
                )
            return public_mailbox_receipt(existing)
        mailbox = state.get("mailbox") or {}
        sender_id = mailbox.get("client_mailbox_id")
        # Prefer the state-file the listener persisted at registration; fall back
        # to the env default only if respond runs before any listen registered.
        send_state_file = mailbox.get("state_file") or state_file
    if not sender_id:
        raise ConnectorError(
            "no mailbox registration: arm the mailbox `listen` first (the daemon's startup sequence; --mailbox-id optional)"
        )
    if target == sender_id:
        # #27890: state.json outlives the listener that wrote it, so a lane a
        # pre-guard listener admitted from our own echo can still be on disk.
        raise ConnectorError("refusing to reply to this worker's own mailbox id (self-echo lane)")

    # Pass the connector's STABLE message_id (derived from the idempotency key).
    # If a crash lands between the send and the receipt write, or two same-key
    # responds race, the retry reuses this id, so the receiver's
    # (sender, message_id) dedup collapses the redelivery to a single emit
    # (INV-6). Without it the CLI mints a fresh wire id per call and the reply
    # would be delivered twice.
    argv = [
        "send", "--mailbox-id", sender_id, "--state-file", send_state_file,
        "--target-mailbox-id", target, "--message-id", message_id,
        "--payload-json", payload_json,
    ]
    for path in attach:
        argv += ["--attach", path]  # the CLI uploads and adds the references (D20 item 6)
    sent = run_mailbox_cli(cli, argv)
    if attach and capability_rejected(sent, "attach"):
        # argparse names the unknown flag: this CLI takes no `--attach` — the
        # verdict was stale (D20 item 1). Clear it and say so; nothing was
        # sent, no receipt. Any other failure is the ordinary one below.
        clear_mailbox_capability("attach")
        raise InputError(
            "muse-mailbox rejected --attach (exit 2); the cached attach verdict is cleared — "
            "send the text without files, or re-run `listen` after upgrading the CLI"
        )
    if sent.returncode != 0:
        # Fail closed: record no receipt so a retry re-sends the same frozen
        # payload. The diagnostic stays secret-free (there is no token).
        raise ConnectorError(
            f"muse-mailbox send failed (exit {sent.returncode}); recorded no receipt so a retry re-sends"
        )
    receipt = {
        "status": "queued",
        "idempotency_key": idempotency_key,
        "message_id": message_id,
        "target_client_mailbox_id": target,
        "payload_sha256": payload_sha,
        "queued_at": utc_now(),
    }
    if attach:
        # What the CLI attached, as it reported it (kind, filename, byte size).
        cli_receipt = last_json_line(sent.stdout)
        receipt["attachments"] = [
            {key: item.get(key) for key in ("kind", "filename", "byte_size")}
            for item in (cli_receipt.get("attachments") or []) if isinstance(item, dict)
        ][:ATTACHMENTS_MAX]
    return public_mailbox_receipt(store_mailbox_receipt(idempotency_key, receipt))


SLACK_TRANSPORT_ALIASES = ("slack", "poll")


def canonical_transport(word):
    """The ONE word this connector uses for a transport, whichever alias the
    caller typed. Slack polling has two public names for historical reasons
    (`poll` on `listen`, `slack` on `disconnect`); `slack` wins, because that is
    already the word in the lane route, the `!= "slack"` reply check, the
    `status --json` lane rows, and the disconnect receipt. Both verbs
    canonicalize here so a future comparison cannot match the wrong one."""
    return "slack" if word in SLACK_TRANSPORT_ALIASES else word


def resolve_listen_transport(args):
    """Which transport a bare `listen` starts (D13).

    Mailbox is the default: it needs no OAuth token and, since `--mailbox-id` is
    optional too, `listen` alone is the entire setup. Slack polling costs an
    `auth` call and a bot token, so it is opt-in — either explicitly, or by
    passing a Slack scope flag, which keeps every pre-D13 Slack monitor command
    polling Slack instead of silently attaching to a mailbox."""
    explicit = getattr(args, "transport", None)
    if explicit:
        # Both aliases are accepted on both verbs (FR-002b addendum, review
        # P1: starting with `--transport poll` and having to stop with
        # `--transport slack` is a trap, and the D7 record's own
        # `listen --transport slack` example used to be an argparse error).
        return canonical_transport(explicit)
    slack_scoped = any(
        getattr(args, name, None) for name in ("channel", "owner", "thread", "only_owner")
    )
    return "slack" if slack_scoped else "mailbox"


def feed_poll_s():
    raw = os.environ.get("SLACK_CONNECTOR_FEED_POLL_S")
    try:
        value = float(raw) if raw else FEED_POLL_S_DEFAULT
    except ValueError:
        value = FEED_POLL_S_DEFAULT
    return min(max(value, 0.05), 5.0)


def edit_lane_message(alias, lane, target_id, text, key_scope):
    """The two-arm edit transport behind `--replace-last`
    (`adr:23499-slack-connector-runtime-contract#D8`). Slack rewrites
    `target_id` in place with `chat.update` (idempotent; `folded: true`); the
    mailbox has no update verb, so it posts an ordinary successor keyed on
    `key_scope` (the superseded id) plus the text — a retry of the same edit
    dedups through the receipt table — and the successor is the new message
    (`folded: false`). Returns (remote_message_id, folded)."""
    route = lane.get("route") or {}
    if route.get("transport") != "slack":
        key = reply_idempotency_key(lane.get("key") or alias, text, answering=key_scope)
        receipt = mailbox_reply(route, key, text)
        return receipt.get("message_id"), False
    with StateStore() as store:
        token, _ = resolve_token(store.load(require=True))
    # D20 item 1 / D18 item 5: the text rides as `markdown_text` (never beside
    # `text`); a rejection is the ordinary send error, no fallback.
    slack_call("chat.update", token, json_body={"channel": route.get("container_id"), "ts": target_id, "markdown_text": text})
    return target_id, True


def update_outbound_text(alias, remote_message_id, text):
    """Refresh one outbound-ledger entry's text after an in-place edit, without
    touching `last_outbound` (D8's cursor stays where the lane's newest post
    put it): the snapshot a relaunched coordinator reads then shows the plan
    as the requester last saw it."""
    with StateStore() as store:
        state = store.load(require=True)
        lane = (state["checkpoint"].get("lanes") or {}).get(alias)
        if lane is None:
            return
        for entry in lane.get("outbound") or []:
            if entry.get("message_id") == remote_message_id:
                entry["text"] = text
                # #41802: the watcher's backoff reads when the plan was last
                # edited by anyone else (FR-41802-1(g)).
                entry["edited_at_ms"] = now_ms()
        note_plan_post(lane, remote_message_id, text)
        store.save(state)


def append_outbound_entry(lane, remote_message_id, text, interim, sent_at=None, sent_at_ms=None):
    """The one writer of a lane's outbound-ledger entry (idempotent by message
    id; the snapshot sorts on `sent_at_ms`). `interim` marks a post that is
    not an answer — an arm-time `--say`, a `--replace-last` successor, the
    daemon's `delegate` acknowledgement — so `lane_answered` (D20 item 4)
    reads only plain replies. Returns True when it appended."""
    ledger = lane.setdefault("outbound", [])
    if any(entry.get("message_id") == remote_message_id for entry in ledger):
        return False
    entry = {
        "message_id": remote_message_id,
        "text": text,
        "sent_at": sent_at or utc_now(),
        "sent_at_ms": int(sent_at_ms if sent_at_ms is not None else time.time() * 1000),
        "interim": bool(interim),
    }
    ledger.append(entry)
    note_plan_post(lane, remote_message_id, text)
    if len(ledger) > LANE_OUTBOUND_MAX:
        # the plan post's entry is pinned while it is the sink's target (review of PR #41981): evicted, the next fold
        # ran against empty text and rewrote the plan message to bare rows, and `--stamp` answered 0 from then on
        plan = lane.get("plan_message_id")
        pinned = [e for e in ledger if e.get("message_id") == plan]
        rest = bound_fifo([e for e in ledger if e.get("message_id") != plan], LANE_OUTBOUND_MAX - len(pinned))
        ledger = sorted(pinned + rest, key=lambda e: (e.get("sent_at_ms") or 0, e.get("sent_at") or ""))
    lane["outbound"] = ledger
    return True


def note_plan_post(lane, message_id, text):
    """#41959 (FR-41802-2(a)): a post or in-place edit whose text carries an OPEN list row (`☐ ⏳ ◐ ⛔`) is the lane's
    plan post — the one message the watcher's `progress-sink` edits. Recorded here, by the writer, so the sink never
    guesses from "the newest message" (QA r25: that was the daemon's ACK, edited for the whole run while the real plan
    went stale). A later plan post moves it once; an ACK, a progress reply or a summary carries no row and leaves it."""
    if message_id and any(row and row[0] in SINK_OPEN_GLYPHS for row in map(sink_row, (text or "").split("\n"))):
        lane["plan_message_id"] = message_id


def say_post_key(alias, lane, text):
    """The one key of an arm-time post: the conversation and the text. Not the
    cursor, a handoff id, or anything that moves across a resume or a re-arm,
    so a listener re-armed with the same command re-sends nothing. Accepted
    residual: the same words posted again later in the conversation post
    nothing (the diagnostic says so)."""
    return reply_idempotency_key(lane.get("key") or alias, text, answering="say")


def post_say(alias, lane, text):
    """`listen --conversation <key> --cursor <id> --say <text>` (spec 23499
    FR-28175-1 as narrowed by `adr:25011-daemon-session-coordination#D20`):
    post `text` into the lane as the listener arms, so the requester sees it
    at lane boot and the list costs no extra call (`#D13`, #29147). It rides
    the reply path as an interim post (never the lane's
    plain reply) and becomes the lane's last outbound, so `reply
    --replace-last` edits it. Keyed by the
    conversation and the text alone (`say_post_key`), so a re-arm re-sends
    nothing. The receipt never rides stdout (INV-2): one stderr diagnostic. A
    failed post leaves no receipt, so the next arm retries it, and never stops
    the tail — a conversation must not go deaf for a post."""
    route = lane.get("route") or {}
    key = say_post_key(alias, lane, text)
    with StateStore() as store:
        state = store.load(require=True)
        recorded = (state["checkpoint"].get("reply_receipts") or {}).get(key)
    if recorded is not None:
        posted_id = recorded.get("message_id") or recorded.get("remote_message_id")
        diag(f"--say: this text is already posted in lane {alias} as {posted_id}; nothing sent")
        return
    container = route.get("container_id") or route.get("target_client_mailbox_id")
    try:
        if route.get("transport") == "mailbox":
            message_id = mailbox_reply(route, key, text).get("message_id")
        else:
            message_id = slack_reply(route, key, text).get("remote_message_id")
    except ConnectorError as error:
        diag(f"--say failed; listening anyway, the next arm retries it: {error}")
        return
    record_last_outbound(alias, container, message_id, text=text, interim=True)
    diag(f"--say posted to lane {alias} as {message_id}")



def listen_conversation(args):
    """A coordinator's Monitor (D12/D13): tail ONE conversation's feed and print
    every event strictly after `--cursor` in exactly the unscoped listener's
    line shape, so the coordinator reads what the daemon would have read and
    nothing else — never a status marker (#28182: the only lane this stream
    could report on is the coordinator's own, so a marker here woke the
    process that had just answered). The cursor is the handoff watermark (an
    event id, or a mailbox `cursor` value); the cursor event itself is never
    printed and an unknown cursor replays the whole feed. Follows the file
    (poll, reconnect on recreate), dedupes by event id, and exits only on a
    signal, `--once`, a `disconnect` of its transport, or the death of its
    parent (a tail with no reader is a stray)."""
    key = args.conversation
    cursor = getattr(args, "cursor", None)
    explicit = getattr(args, "transport", None)
    say = getattr(args, "say", None)
    if getattr(args, "unattended_grace", None) is not None:
        raise InputError("--unattended-grace applies to the unscoped `listen` only")
    if say is not None and not say.strip():
        raise InputError("--say needs text: what the requester reads as the listener arms")
    once = bool(getattr(args, "once", False))
    # #28432 (INV-28432-1): a persistent tail runs ONLY under the Monitor tool.
    # Armed with `bash`, the same command consumed the conversation into a
    # finished tool call's spool while holding the lock, so the lane never
    # woke and the connector never gave the conversation back. Refuse before
    # the state, the lock, the feed, and the `--say` post; `--once` is a bounded
    # peek that holds nothing after it returns, so it is exempt. The verdict is
    # the monitor tool's own stdout artifact for this call (`monitor_artifact_for`).
    arm = listener_arm()
    if not once and not arm["under_monitor"]:
        print(json.dumps({"outcome": "not_under_monitor", "hint": NOT_UNDER_MONITOR_HINT}), flush=True)
        return EXIT_INPUT
    if say is not None and "<plan>" in say:
        # #28427: the coordinator's starter teaches `--say "<plan>"` beside
        # its copy-ready arm command (#29148 took the placeholder out of the
        # command itself); a verbatim copy must never reach a human.
        raise InputError(
            "--say: <plan> is a placeholder; re-arm with your own text (a short todo list for the work)"
        )
    with StateStore() as store:
        state = store.load(require=True)
        checkpoint = state["checkpoint"]
        alias, lane = lane_for_conversation(
            checkpoint, key, canonical_transport(explicit) if explicit else None
        )
        transport = (lane.get("route") or {}).get("transport")
    # D15: one scoped listener per conversation. The lock it holds IS the
    # liveness signal the unscoped listener and `status` read, so a second tail
    # is refused rather than allowed to forge it; the heartbeat inside says
    # whether this holder can wake its session (#28432).
    lock_fd = acquire_conversation_lock(transport, key, heartbeat={
        "pid": os.getpid(), "under_monitor": arm["under_monitor"],
        "tool_use_id": arm["tool_use_id"], "armed_at": utc_now(),
    })
    if lock_fd is None:
        print(json.dumps({"outcome": "listener_conflict", "conversation": key}), flush=True)
        return EXIT_FATAL_LISTEN
    if say is not None:
        # After the lock: a refused second listener never posts; before the
        # tail: the requester reads it at lane boot.
        post_say(alias, lane, unescape_literal_newlines(say))
    seams = mailbox_seams_enabled() if transport == "mailbox" else test_seams_enabled()
    output_format = emit_format(seams)
    max_lines_raw = os.environ.get("SLACK_CONNECTOR_MAX_POLLS") if seams else None
    max_lines = int(max_lines_raw) if max_lines_raw else None
    poll_s = feed_poll_s()
    side_check_s = max(poll_s, 1.0)  # disconnect check: a flock and a parse, not per tick
    start_ppid = os.getppid()
    seen = set()
    emitted = 0
    mark_path = delivered_mark_path(transport, key)
    delivered = read_delivered_mark(mark_path)

    def emit_item(item, tail_read_at_ms=None):
        nonlocal emitted
        event_id = item.get("event_id")
        envelope = item.get("envelope")
        if event_id in seen or event_id == cursor or not isinstance(envelope, dict):
            return
        seen.add(event_id)
        hops = None
        if tail_read_at_ms is not None:
            # #28433: the upstream stamps ride the feed line; this tail adds its own.
            hops = dict(item.get("hops") or {}, tail_read_at_ms=tail_read_at_ms)
        line = emit_event(envelope, output_format, hops=hops)
        if hops is not None:
            record_hops(hop_record(envelope, "conversation", hops, line, conversation=key))
        emitted += 1
        if isinstance(event_id, str) and event_id:
            write_delivered_mark(mark_path, event_id)  # r22 SR-DAEMON R-4: delivered, so never re-sent by a re-arm

    def done():
        return once or (max_lines is not None and emitted >= max_lines)

    tail = FeedTail(feed_path(transport, key))
    try:
        # Pass 1: the feed as it stands. Find the cursor BEFORE printing, so an
        # unknown cursor replays everything rather than nothing.
        existing = tail.read_new()
        tail_read_at_ms = now_ms() if trace_hops_enabled() else None
        start = 0
        if cursor is not None:
            for index, item in enumerate(existing):
                if item.get("event_id") == cursor or (
                    item.get("cursor") is not None and str(item.get("cursor")) == str(cursor)
                ):
                    start = index + 1
        if delivered is not None:
            # r22 SR-DAEMON R-4: the later of the cursor and this listener's own
            # delivered mark wins; a mark the feed no longer holds is ignored.
            for index, item in enumerate(existing):
                if item.get("event_id") == delivered:
                    start = max(start, index + 1)
        for item in existing[:start]:
            seen.add(item.get("event_id"))
        for item in existing[start:]:
            emit_item(item, tail_read_at_ms)
        if done():
            return 0
        last_side_check = time.monotonic()
        while True:
            if os.getppid() != start_ppid:
                # D20 item 4 (FINISHED): the claim stays — an answered lane is
                # quiet until its next inbound line makes the claim DEAD for
                # the sweep; an exit-time release left that line to a dead
                # coordinator in the live proof.
                diag("parent process exited; stopping the conversation listener")
                return EXIT_FATAL_LISTEN
            fresh = tail.read_new()
            tail_read_at_ms = now_ms() if fresh and trace_hops_enabled() else None
            for item in fresh:
                emit_item(item, tail_read_at_ms)
                if done():
                    return 0
            if time.monotonic() - last_side_check >= side_check_s:
                last_side_check = time.monotonic()
                with StateStore() as store:
                    after = store.load()
                after = after or {}
                down = (
                    (after.get("mailbox") or {}).get("connected") is False
                    if transport == "mailbox"
                    else (after.get("connector") or {}).get("connected") is False
                )
                if down:
                    diag(f"{transport} transport disconnected; stopping the conversation listener")
                    return 0
            time.sleep(poll_s)
    finally:
        tail.close()
        os.close(lock_fd)


def cmd_listen(args):
    if getattr(args, "conversation", None):
        return listen_conversation(args)
    if getattr(args, "cursor", None) or getattr(args, "once", False) or getattr(args, "say", None) is not None:
        raise InputError("--cursor, --once and --say apply to `listen --conversation <key>` only")
    # #28176: announce this unscoped listener for its whole life (the fd is the
    # lease, kept in `LISTENER_LEASE`; it drops with the process, however the
    # process ends — a bounded register-only run included).
    lock_transport = "mailbox" if resolve_listen_transport(args) == "mailbox" else "slack"
    global NATIVE_FORWARDER, LISTENER_LEASE
    if native_delivery_enabled():
        # ADR 25011 D22 / ADR 23499 D19: the daemon names the session that
        # owns this listener; without it there is nowhere to deliver.
        if lock_transport != "mailbox":
            # The Slack poll path (`merge_poll_results`) keeps D11's line
            # semantics; forwarding it is a later slice (#27519).
            raise InputError(
                f"{NATIVE_DELIVERY_ENV} is on: native delivery is mailbox-only in this slice;"
                " arm the Slack listener with the gate off"
            )
        if not getattr(args, "deliver_to", None):
            raise InputError(
                f"{NATIVE_DELIVERY_ENV} is on: `listen` needs --deliver-to <the daemon's session id>"
                " (the `Current session id:` of the daemon session's session_identity reminder)"
            )
        NATIVE_FORWARDER = NativeForwarder(
            args.deliver_to,
            getattr(args, "muse_bin_listen", None) or os.environ.get(MUSE_BIN_ENV) or "muse",
            lock_transport,
            unattended_grace_s(args),
        )
        diag(f"native delivery on: forwarding {lock_transport} messages to session {args.deliver_to}")
    elif getattr(args, "deliver_to", None):
        diag(f"--deliver-to is ignored while {NATIVE_DELIVERY_ENV} is off (the Monitor line path)")
    LISTENER_LEASE = acquire_transport_listener_lock(lock_transport)  # held until exit
    if LISTENER_LEASE is None:
        holder = transport_listener(lock_transport).get("pid")
        diag(
            f"another {lock_transport} listener (pid {holder}) is already live; two unscoped "
            "listeners deliver every message twice — the daemon's `start` reports it, arm only once"
        )
    if lock_transport == "mailbox":
        # The poll/Slack-transport flags don't apply to mailbox; warn rather than
        # silently ignore them so `listen --transport mailbox --only-owner` isn't a
        # confusing no-op.
        ignored = [
            flag for flag, on in (
                ("--thread", getattr(args, "thread", None)),
                ("--only-owner", bool(getattr(args, "only_owner", False))),
                ("--no-auto-react", bool(getattr(args, "no_auto_react", False))),
            ) if on
        ]
        if ignored:
            diag(f"mailbox transport ignores poll-only flag(s): {', '.join(ignored)}")
        return listen_mailbox(args)
    thread_root = getattr(args, "thread", None)
    only_owner = bool(getattr(args, "only_owner", False))
    auto_react = not bool(getattr(args, "no_auto_react", False))
    output_format = emit_format(test_seams_enabled())
    if only_owner and thread_root:
        raise InputError(
            "--only-owner applies to channel listens only; a thread listen "
            "already claims its whole thread"
        )
    if thread_root:
        try:
            float(thread_root)
        except ValueError:
            raise InputError("--thread expects the thread root ts, e.g. 1712345678.001200")
    poll_ms = int(os.environ.get("SLACK_CONNECTOR_POLL_MS") or DEFAULT_POLL_MS)
    max_polls_raw = os.environ.get("SLACK_CONNECTOR_MAX_POLLS") if test_seams_enabled() else None
    max_polls = int(max_polls_raw) if max_polls_raw else None
    # D7: `listen` is the one-shot start. Given a channel it binds (join, scope
    # check, cursor at the channel head) before streaming, so Slack start costs
    # `auth` once plus this one call — never a separate `bind` and `connect`.
    if getattr(args, "channel", None):
        # Validate before mutating: binding first and checking after left a
        # refused command with a half-applied binding (P0, review PR #26509).
        # `bind_channel` owns that check because it owns the owner-inheritance
        # rule and the lock. An empty `--owner ""` — the daemon's template with
        # an unfilled placeholder — is NO owner, never an owner named "": the
        # `or None` is what routes it into the inherit-or-refuse path instead
        # of writing an empty owner and downgrading every retained envelope.
        bind_channel(
            args.channel,
            getattr(args, "owner", None) or None,
            require_owner=only_owner,
        )

    def in_scope(envelope):
        thread_id = envelope["container"]["thread_id"]
        if only_owner and not envelope["actor"]["is_owner"]:
            # FR-23499-6 replay half: a pending event admitted by an
            # unfiltered listener stays pending for whoever claims it.
            return False
        return thread_id == thread_root if thread_root else thread_id is None

    grace_s = unattended_grace_s(args)
    with StateStore() as store:
        state = store.load()
        # A cold machine is missing BOTH a token and a binding, and the daemon
        # learns that only from this exit (D15 deleted the probes). Naming one
        # step at a time costs an arm-and-fail round trip per step, so name the
        # whole first run here — one predicate, this caller's message.
        require_identity(
            state,
            "no validated identity: run `auth --token-stdin`, then one "
            "`listen --channel <C…> --owner <U…>` to bind",
        )
        if not state.get("binding"):
            # The daemon connects with a placeholder-free `listen --only-owner`
            # (D15) and never probes readiness, so this exit IS the ask: name
            # both values a first bind needs, `--owner` included, or the human
            # supplies a channel and hits the owner error on the next try.
            raise ConnectorError(
                "no channel bound: pass `listen --channel <C…> --owner <U…>` once"
            )
        if only_owner and not state["binding"].get("owner_user_id"):
            # Fail loud: with no owner recorded, `is_owner` is False for every
            # actor, so this listener would admit nothing and look like a dead
            # channel rather than a misconfigured filter.
            raise InputError("--only-owner needs an owner: pass `listen --channel <C…> --owner <U…>`")
        # D7: `listen` IS the start verb, so it clears a prior `disconnect`
        # instead of exiting on it. A `disconnect` against a LIVE stream still
        # stops that stream — the in-loop check below owns that.
        state.setdefault("connector", {})["connected"] = True
        if thread_root and thread_root not in state["checkpoint"]["tracked_threads"]:
            track_thread(state["checkpoint"], thread_root, thread_root)
        store.save(state)
    # D20 item 4: a dead coordinator's unanswered conversation in this
    # listener's scope wakes the daemon without waiting for a new message.
    for envelope in sweep_unattended_claims("slack", grace_s, in_scope):
        emit_event(envelope, output_format)

    polls = 0  # successful poll cycles only — error arms do not consume the
    attempts = 0  # bounded-listen budget (a hiccup must not yield a silent no-op)
    token = None
    while max_polls is None or polls < max_polls:
        attempts += 1
        if max_polls is not None and attempts > max_polls * 10:
            diag("bounded listen exceeded its attempt budget; exiting")
            break
        try:
            with StateStore() as store:
                snapshot = store.load(require=True)
            # Honor an explicit `disconnect` (finding #3): the daemon SKILL says
            # `disconnect` "is how you stop the stream" (#16370: the Monitor has
            # no other stop), so
            # the slack listener must actually stop when connected is False —
            # mirroring the mailbox listener — not poll forever while the connector
            # printed {"status":"disconnected"}. A never-connected listen has no
            # `connected` key and proceeds as before.
            if (snapshot.get("connector") or {}).get("connected") is False:
                diag("connector is disconnected (run `listen` again to resume); stopping the listener")
                return 0
            token, _source = resolve_token(snapshot)
            # Network happens against the snapshot, outside the flock, so
            # concurrent ack/send/react/status calls are never blocked.
            candidates, dead_threads = poll_once(snapshot, token, thread_root=thread_root)
            with StateStore() as store:
                emitted = merge_poll_results(
                    store,
                    snapshot,
                    candidates,
                    dead_threads,
                    ensure_thread=thread_root,
                    only_owner=only_owner,
                    unattended_grace_s=grace_s,
                )
            crash_if("after_persist", test_seams_enabled())
            polls += 1
            for envelope in emitted:
                emit_event(envelope, output_format)
            for envelope in sweep_unattended_claims("slack", grace_s, in_scope):
                emit_event(envelope, output_format)
            if auto_react:
                for envelope in emitted:
                    if not receipt_react(envelope, token):
                        break
            if thread_root and thread_root in dead_threads:
                diag(f"thread {thread_root} is gone; ending this thread listener")
                return 0
        except RateLimited as limited:
            diag(f"rate limited; sleeping {limited.retry_after_s}s per Retry-After")
            _sleep(limited.retry_after_s)
            continue
        except TransientError as transient:
            diag(f"transient failure ({transient}); retrying")
            _sleep(max(poll_ms / 1000.0, 0.2))
            continue
        except ApiError as error:
            if error.error_name in FATAL_API_ERRORS:
                fresh_token = None
                try:
                    with StateStore() as store:
                        fresh = store.load(require=True)
                    fresh_token, _ = resolve_token(fresh)
                except ConnectorError:
                    pass
                if fresh_token and fresh_token != token:
                    diag("token rotated during the poll; retrying with the new credential")
                    continue
                diag(f"fatal source error: {error.error_name}; exiting")
                return EXIT_FATAL_LISTEN
            diag(f"source error {error.error_name}; retrying")
            _sleep(max(poll_ms / 1000.0, 0.2))
            continue
        if max_polls is None or polls < max_polls:
            _sleep(poll_ms / 1000.0)
    return 0


def cmd_show(args):
    event_id = canonical_event_id(args.event_id)
    with StateStore() as store:
        state = store.load(require=True)
        retained = state["checkpoint"]["retained_events"].get(event_id)
    if retained is None:
        raise ConnectorError(f"event {event_id} is unknown or outside the retained window")
    print(
        json.dumps(
            {
                "event_id": event_id,
                "envelope": retained["envelope"],
                "content": {"text": retained["full_text"]},
            }
        )
    )
    return 0


def find_receipt_by_metadata(token, container_id, thread_ts, idempotency_key, since_unix):
    """FM-6 recovery: locate an already-posted reply by its metadata key.
    Metadata is only returned when include_all_metadata is requested, and a
    long thread needs pagination — both are load-bearing on real Slack.

    The reply we posted can only exist at/after the attempt started, so floor
    `oldest` near that time. conversations.replies returns OLDEST-first under a
    10-page cap, so scanning from 0 in a thread with >~1000 replies burns the
    whole budget on old messages and never reaches the just-posted one —
    returning None and double-posting (INV-6). Flooring the scan confines it to
    recent messages regardless of thread length.

    `since_unix` is REQUIRED (no default): passing 0.0 restores the scan-from-0
    behavior above, so the caller must opt into it explicitly (the recovery
    caller floors by the marker's start, then rescans once with the floor
    widened by MAX_CLOCK_SKEW_S on a miss — never 0.0, which would reopen the
    >1000-reply double-post)."""
    oldest = max(since_unix - RECOVERY_SCAN_MARGIN_S, 0.0)
    params = {"channel": container_id, "oldest": oldest, "limit": 100, "include_all_metadata": "true"}
    if thread_ts:
        messages = fetch_messages("conversations.replies", token, dict(params, ts=thread_ts))
    else:
        messages = fetch_messages("conversations.history", token, params)
    for message in messages:
        metadata = message.get("metadata") or {}
        event_payload = metadata.get("event_payload") or {}
        if (
            metadata.get("event_type") == "muse_connector_reply"
            and event_payload.get("idempotency_key") == idempotency_key
        ):
            return message["ts"]
    return None


def record_send_receipt(store, state, key, container_id, thread_ts, remote_ts):
    checkpoint = state["checkpoint"]
    existing = checkpoint["reply_receipts"].get(key)
    if existing is not None:
        # A concurrent same-key sender already recorded a receipt: keep the
        # first one (INV-6 first-writer-wins) and say so loudly.
        diag("duplicate remote message detected for an idempotency key; keeping the first receipt")
        return existing
    receipt = {
        "status": "sent",
        "remote_message_id": remote_ts,
        "idempotency_key": key,
        "container_id": container_id,
    }
    checkpoint["reply_receipts"][key] = receipt
    checkpoint["send_attempts"].pop(key, None)
    checkpoint["outbound_ts"].append(remote_ts)
    # Register/keep the thread alive but DO NOT advance the read cursor: the
    # bot's own reply is already deduped by outbound_ts + bot_user_id, and
    # advancing past it would skip user replies that landed before this send.
    track_thread(checkpoint, thread_ts or remote_ts, remote_ts, advance_cursor=False)
    evict_bounded(checkpoint)
    store.save(state)
    return receipt


def public_receipt(receipt):
    return {k: receipt[k] for k in ("status", "remote_message_id", "idempotency_key") if k in receipt}



def slack_reply(route, key, text):
    """Slack arm of `reply`: post `text` into the lane, with the FR-017 attempt
    marker and FM-6 recovery that make a same-key retry safe across a crash."""
    container_id = route.get("container_id")
    if not container_id:
        raise ConnectorError("this lane has no Slack container recorded; it cannot be replied to")
    thread_ts = route.get("thread_ts")
    text_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

    needs_recovery = False
    original_started_unix = 0.0
    with StateStore() as store:
        state = store.load(require=True)
        token, _ = resolve_token(state)
        checkpoint = state["checkpoint"]
        existing = checkpoint["reply_receipts"].get(key)
        if existing is not None:
            # Cross-transport guard (mirrors mailbox_reply): a mailbox receipt
            # carries `target_client_mailbox_id`; a Slack one never does.
            # Reusing that key for a Slack reply must fail closed, not return the
            # mailbox receipt as if the Slack post happened.
            if existing.get("target_client_mailbox_id") is not None:
                raise ConnectorError(
                    "idempotency key was already used by a mailbox respond receipt; refusing to reuse it"
                )
            return public_receipt(existing)
        marker = checkpoint["send_attempts"].get(key)
        if marker is not None:
            if (
                marker.get("container_id") != container_id
                or marker.get("thread_ts") != thread_ts
                or marker.get("text_sha256") != text_sha
            ):
                raise ConnectorError(
                    "idempotency key was already used with a different target or text; refusing to reuse it"
                )
            # Capture the ORIGINAL attempt time before re-arming: FM-6 recovery
            # floors its scan near it, so the just-posted reply is found even in
            # a huge thread. Re-arming first would lose that anchor.
            original_started_unix = float(marker.get("started_unix") or 0)
            age = time.time() - original_started_unix
            if age < send_grace_s():
                raise ConnectorError(
                    f"a send with this idempotency key appears to be in flight (started {int(age)}s ago); retry later"
                )
            # Re-arm the grace window under the lock so a concurrent same-key
            # retry fails closed instead of double-recovering (INV-6).
            marker["started_unix"] = time.time()
            marker["started_at"] = utc_now()
            store.save(state)
            needs_recovery = True
            # Both refusal clocks anchor inside the flock: monotonic for
            # ordinary elapsed time, the armed wall clock for suspend
            # (CLOCK_MONOTONIC freezes while the host sleeps, and rivals are
            # admitted on wall-clock marker age).
            armed_unix = float(marker["started_unix"])
            recovery_started = time.monotonic()
        else:
            # FR-017: the attempt marker is durable before the network call.
            fresh_armed_unix = time.time()
            checkpoint["send_attempts"][key] = {
                "started_at": utc_now(),
                "started_unix": fresh_armed_unix,
                "container_id": container_id,
                "thread_ts": thread_ts,
                "text_sha256": text_sha,
            }
            store.save(state)
            # Ownership token for the clear arm below: pop only a marker this
            # process still owns, never a rival's live re-arm (INV-6).
            armed_unix = fresh_armed_unix

    # Network happens outside the flock (same reasoning as listen).
    if needs_recovery:
        recovered_ts = find_receipt_by_metadata(
            token, container_id, thread_ts, key, since_unix=original_started_unix
        )
        if recovered_ts is None and original_started_unix - RECOVERY_SCAN_MARGIN_S > 0:
            # The floored scan is anchored on the LOCAL marker clock while the
            # reply carries Slack's server ts; a host running ahead of Slack by
            # more than RECOVERY_SCAN_MARGIN_S pushes the floor past a
            # legitimately-recent reply, so the scan misses it and recovery would
            # double-post (INV-6). Rescan once with a floor widened by
            # MAX_CLOCK_SKEW_S so it tolerates that skew — but NOT a full
            # oldest=0 rescan, which would reopen the >1000-reply double-post in
            # a huge thread. Accepted residual: a skew beyond MAX_CLOCK_SKEW_S
            # makes both scans miss and recovery reposts once (a bounded INV-6
            # duplicate, D13-class) — repost_refused bounds recovery DURATION,
            # not skew, which cancels out of both its clocks.
            recovered_ts = find_receipt_by_metadata(
                token, container_id, thread_ts, key,
                since_unix=max(original_started_unix - MAX_CLOCK_SKEW_S, 0.0),
            )
        if recovered_ts is not None:
            diag("recovered receipt for idempotency key after interrupted send")
            with StateStore() as store:
                state = store.load(require=True)
                receipt = record_send_receipt(store, state, key, container_id, thread_ts, recovered_ts)
            return public_receipt(receipt)
        # This refusal is not definitive: the marker stays armed so a later
        # retry can still recover. Extra refusals only mean "retry later" —
        # never an extra post.
        if repost_refused(
            time.monotonic() - recovery_started,
            time.time() - armed_unix,
            send_grace_s(),
        ):
            raise ConnectorError(
                "recovery outlived the in-flight grace; a concurrent same-key retry "
                "may own this key now — refusing to repost, retry later"
            )
        diag("interrupted send left no remote message; reposting once")

    body = {
        "channel": container_id,
        "metadata": {
            "event_type": "muse_connector_reply",
            "event_payload": {"idempotency_key": key},
        },
    }
    if thread_ts:
        body["thread_ts"] = thread_ts
    try:
        posted, _headers = slack_call("chat.postMessage", token, json_body=dict(body, markdown_text=text))
    except TransientError:
        # The response may be lost — the marker must stay armed so a
        # same-key retry inside the grace fails closed (FM-6).
        raise
    except ConnectorError:
        # Definitive refusal (ok:false ApiError, a 429 that posted nothing,
        # or a raw non-429/non-5xx HTTP failure): the marker must not linger
        # as a fake in-flight send. Pop only a marker this process still
        # owns — a late refusal must never delete a rival's live re-arm
        # (INV-6).
        with StateStore() as store:
            state = store.load(require=True)
            live = state["checkpoint"]["send_attempts"].get(key)
            if live is not None and live.get("started_unix") == armed_unix:
                state["checkpoint"]["send_attempts"].pop(key, None)
                store.save(state)
        raise
    crash_if("after_post", test_seams_enabled())
    with StateStore() as store:
        state = store.load(require=True)
        receipt = record_send_receipt(store, state, key, container_id, thread_ts, posted["ts"])
    return public_receipt(receipt)


def replace_last_reply(alias, lane, text):
    """`reply --to <lane> --replace-last`
    (`adr:23499-slack-connector-runtime-contract#D8`): replace the last message
    the connector itself sent in this lane — the live-checklist grammar, where the
    daemon keeps one thread message current instead of posting progress spam.

    Addressing is implicit on purpose: the only real consumer always means "edit
    MY last message here", and an explicit message ref would push connector
    state back through the model, which is the ceremony this surface deletes.

    Two arms, one intent. Slack edits in place with `chat.update`, which is
    idempotent, so that arm carries no idempotency key and no in-flight attempt
    marker. The mailbox has no update verb, so that arm posts an ordinary
    successor keyed on the superseded message id plus the new text: a retry of
    the SAME edit dedups through the receipt table and the CLI's `--message-id`
    (no attempt marker needed — the receiver dedups by id), while the next edit
    mints a new successor, and a re-run after the successor was recorded is a
    new edit."""
    route = lane.get("route") or {}
    last = lane.get("last_outbound")
    if not last:
        raise ConnectorError(f"nothing sent yet in lane {alias}; send a normal reply first")
    if route.get("transport") != "slack":
        edit_target = last.get("edit_target")
        receipt = None
        if (edit_target and route.get("conversation_id") and lane.get("relay")
                and mailbox_capability("edit")):
            # `adr:23499-slack-connector-runtime-contract#D20` item 2: the CLI
            # has the edit verb (the probe verdict alone, #30562), the relay originated
            # this lane (only the relay understands `message_edit`), its last
            # post is a message the relay published, and the route names the
            # conversation the relay binds the mapping to — so this is ONE
            # `message_edit` for the ORIGINAL id, never edit plus send. The op
            # id chains on the PREVIOUS edit (review of #30528): `A`, `B`, `A`
            # are three operations, while a retry of an edit that crashed
            # before its bookkeeping derives the same one and dedups.
            previous = last.get("edit_message_id") or edit_target
            # Its own scope word: the first edit's `previous` is the same id the
            # D8 arm keys `edit:` on, and the two arms share the receipt table.
            key = reply_idempotency_key(lane.get("key") or alias, text, answering=f"message_edit:{previous}")
            try:
                receipt = mailbox_edit(route, key, edit_target, text)
            except CapabilityRejected as error:
                # A stale verdict (rolled-back CLI): cleared; this same call
                # posts D8's successor below (D20 item 1).
                diag(f"{error}; posting a successor instead")
        if receipt is not None:
            # The edit IS the daemon speaking (#26855): bump `sent_at`; the
            # target stays the original id (`record_last_outbound` re-marks it
            # as the edit target) and remembers this op as the chain link; the
            # ledger shows the edited text (ADR 25011 D20: the relaunch
            # snapshot reads what the requester sees).
            record_last_outbound(
                alias, route.get("container_id") or route.get("target_client_mailbox_id"), edit_target,
                edit_message_id=receipt.get("message_id"),
            )
            update_outbound_text(alias, edit_target, text)
            return {
                "status": "updated",
                "lane": alias,
                "remote_message_id": edit_target,
                # Item 4 (honesty): `folded: true` here means the CLI accepted
                # an edit addressed to that message; the connector cannot see
                # the Slack update, and the relay ignores a target it no longer
                # maps without a word back. `edit_message_id` tells this arm
                # from Slack's own `chat.update`.
                "edit_message_id": receipt.get("message_id"),
                "supersedes": edit_target,
                "folded": True,
            }
        # `adr:23499-slack-connector-runtime-contract#D8`: the mailbox has no
        # update verb, so an edit is an ORDINARY `peer_message` successor. The closed v1 body carries no
        # predecessor field (build_peer_message_body), so the supersession lives
        # only in this connector's lane state and the receipt below. That
        # replaces the retired fail-closed arm (`adr:23499-slack-connector-runtime-contract#D15`), which was right while
        # the alternative was a SILENT new message: the caller asked to edit,
        # got a fresh message, and could not tell. The receipt removes that
        # ambiguity; what the far side renders is not promised.
        #
        # Reusing the previous `--message-id` is NOT an option: the provider
        # accepts the second send and silently drops it (probed 2026-09-01), so
        # the requester would keep reading a stale checklist while this returned
        # success. Each edit is therefore its own message, keyed on what it
        # supersedes plus its text so a retry of the SAME edit dedupes.
        superseded = last["remote_message_id"]
        new_id, _ = edit_lane_message(alias, lane, superseded, text, f"edit:{superseded}")
        record_last_outbound(
            alias,
            route.get("container_id") or route.get("target_client_mailbox_id"),
            new_id,
            text=text,
            interim=True,
        )
        return {
            "status": "updated",
            "lane": alias,
            "remote_message_id": new_id,
            "supersedes": superseded,
            # The connector edited nothing in place — it posted a plain
            # successor, and the wire does not name the predecessor. Whether the
            # READER shows one checklist or two is unknown here, so this reports
            # what WE did, never a guess about what the far side rendered.
            "folded": False,
        }
    edit_lane_message(alias, lane, last["remote_message_id"], text, f"edit:{last['remote_message_id']}")
    # #26855: an in-place edit IS the daemon speaking into the lane, so it has
    # to bump `sent_at` like every other send. Without this the Slack arm was
    # the one path that answered without ever reading as `working` (the mailbox
    # arm posts a successor and goes through `record_last_outbound` already).
    record_last_outbound(alias, last["container_id"], last["remote_message_id"])
    # D20: `--replace-last` is how a coordinator keeps its todo list current,
    # so the ledger a relaunch snapshot reads carries the edited text.
    update_outbound_text(alias, last["remote_message_id"], text)
    return {
        "status": "updated",
        "lane": alias,
        "remote_message_id": last["remote_message_id"],
        "container_id": last["container_id"],
        # Both arms return the same two fields so a caller never branches on
        # the transport name to know what happened (`adr:23499-slack-connector-runtime-contract#D8`). Here `chat.update`
        # rewrote the message in place: the superseded message and the live one
        # are the same message, and `folded` says so. The mailbox arm returns a
        # DIFFERENT successor id with `folded: False`, because it could not.
        "supersedes": last["remote_message_id"],
        "folded": True,
    }


def reply_idempotency_key(lane_key, text, answering=None, attach=()):
    """Derive the reply's idempotency key so the model never carries one (D2),
    scoped to the lane's newest inbound line (D18 item 3, replacing D14's
    oldest unacknowledged event).

    (lane, text) alone conflates two different things: a RETRY of one answer and
    a SECOND answer that happens to use the same words. Adding the newest
    inbound event id separates them — a retry before the next line derives the
    same key, the next line mints a new one. A lane with no inbound line is a
    proactive send, which keeps the (lane, text) key; a deliberate repeat there
    still needs `--key` to say so. Accepted residual: a retry that races a new
    inbound line double-posts once."""
    parts = [lane_key, text] if answering is None else [lane_key, answering, text]
    # D20 item 6: the files are part of the message — another file set is a
    # new message exactly as other words are (review of #30528).
    parts.extend(sorted(str(path) for path in (attach or ())))
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()[:32]


def record_last_outbound(alias, container_id, remote_message_id, text=None, interim=False, edit_message_id=None):
    """Remember the message `--replace-last` edits. Recorded from the RECEIPT,
    so a first-writer-wins or FM-6-recovered receipt points the edit at the
    message that actually exists rather than at one this process believed it
    posted. With `text`, also append the lane's outbound ledger (#27816): the
    delegate snapshot carries what the daemon already said, keyed by message
    id so an idempotent resend is one entry."""
    if not container_id or not remote_message_id:
        return
    with StateStore() as store:
        state = store.load(require=True)
        lane = (state["checkpoint"].get("lanes") or {}).get(alias)
        if lane is None:
            return
        if text is not None:
            append_outbound_entry(lane, remote_message_id, text, interim)
        lane["last_outbound"] = {
            "container_id": container_id,
            "remote_message_id": remote_message_id,
            # WHEN, not just what: `last_outbound` is never cleared — it backs
            # `--replace-last` — so its mere presence says nothing about time.
            "sent_at": utc_now(),
            # D20 item 2: the id the relay PUBLISHED and therefore maps for a
            # `message_edit` — every recorded post is one (a reply, `--say`, the
            # delegate acknowledgement, a D8 successor, or the original a
            # mailbox edit rewrote). A lane recorded before D20 lacks the key
            # and takes the successor path.
            "edit_target": remote_message_id,
        }
        if edit_message_id:
            # D20 item 2: the chain link for the next edit's op id; a plain post
            # rebuilds this dict without it, so the chain restarts at the id.
            lane["last_outbound"]["edit_message_id"] = edit_message_id
        store.save(state)


def unescape_literal_newlines(text):
    """Owner paste P2489980591 (2026-09-04, #29190): the model wrote
    `--text "*Plan*\\n- [ ] one"` in double quotes; the shell keeps the two
    characters and Slack shows a raw backslash-n. A text with no real newline
    gets its literal `\\n` turned into newlines; a text that already has a
    real newline (a heredoc, `$'…'`, a code block) is left exactly as written."""
    if not isinstance(text, str) or "\n" in text or "\\n" not in text:
        return text
    return text.replace("\\n", "\n")


def reply_attachments(args, route):
    """`reply --attach <path>` (D20 item 6): a usage error before anything is
    sent unless every file exists, the lane is a mailbox lane (D11: the Slack
    arm moves no bytes), it is not an edit (the edit wire carries no files),
    and the installed CLI proved it has `--attach`. Returns absolute paths."""
    attach = [str(path) for path in (getattr(args, "attach", None) or [])]
    if not attach:
        return []
    if getattr(args, "replace_last", False):
        raise InputError("--attach does not ride --replace-last: the edit wire carries no files; post them as a new reply")
    if route.get("transport") != "mailbox":
        raise InputError("--attach rides the mailbox only: the Slack arm moves no bytes (ADR 23499 D11/D20)")
    if len(attach) > ATTACHMENTS_MAX:
        raise InputError(f"--attach takes at most {ATTACHMENTS_MAX} files")
    for path in attach:
        if not os.path.isfile(path):
            raise InputError(f"--attach: not a regular file: {path}")
    if not mailbox_capability("attach"):
        raise InputError(
            "this muse-mailbox has no --attach (it comes with the Session Mailbox attachment stack); "
            "send the text without files or upgrade the CLI"
        )
    return [os.path.abspath(path) for path in attach]


_SLACK_UI = None


def slack_ui_module():
    """The `custom.slack.ui` contract module shipped beside this script
    (#35345), imported on first use so a copy of this script without it still
    serves every plain verb (Constitution XIII)."""
    global _SLACK_UI
    if _SLACK_UI is None:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        try:
            import slack_ui
        except ImportError as error:
            raise ConnectorError(f"slack_ui.py is missing beside slack_connector.py (the interactive-card arm "
                                 f"needs it; plain verbs do not): {error}")
        _SLACK_UI = slack_ui
    return _SLACK_UI


_SLACK_UI_V2 = None


def slack_ui_v2_module():
    """The `custom.slack.ui` version 2 contract module beside this script
    (#38715, ADR 35345 D15), imported on first use like `slack_ui`."""
    global _SLACK_UI_V2
    if _SLACK_UI_V2 is None:
        slack_ui_module()  # puts the scripts directory on sys.path
        try:
            import slack_ui_v2
        except ImportError as error:
            raise ConnectorError(f"slack_ui_v2.py is missing beside slack_connector.py (the version 2 card arm "
                                 f"needs it; plain verbs and version 1 cards do not): {error}")
        _SLACK_UI_V2 = slack_ui_v2
    return _SLACK_UI_V2


def ui_tables(checkpoint):
    """`checkpoint.ui` (spec 23499 FR-35345-6; ADR 35345 D9): operation records
    keyed by the request message id, presentations keyed by `ui_id`, consumed
    event ids. Created on first use — no schema bump."""
    ui = checkpoint.setdefault("ui", {})
    ui.setdefault("operations", {})
    ui.setdefault("presentations", {})
    ui.setdefault("consumed_event_ids", [])
    return ui


def ui_now():
    """The one clock behind every UI record stamp (FR-35345-6): epoch seconds,
    or the ISO-8601 instant `SLACK_CONNECTOR_UI_NOW` names when the mailbox
    seams are armed, so a test moves time instead of sleeping (#25315). A
    malformed pin fails closed rather than silently reading the wall clock."""
    raw = os.environ.get(UI_NOW_ENV) if mailbox_seams_enabled() else None
    if not raw:
        return time.time()
    try:
        return slack_ui_module().epoch(raw)
    except ValueError:
        raise ConnectorError(f"{UI_NOW_ENV} must be an ISO-8601 instant; got {raw!r}")


def ui_stage_open(stage):
    """An operation still awaiting the relay — anything but `terminal`:
    `submitting` (record written, `send` not yet returned), `submitted`,
    `retry_wait`. One classifier for both sites here and the listener's sweep."""
    slack_ui = slack_ui_module()
    return stage in (slack_ui.STAGE_SUBMITTING, slack_ui.STAGE_SUBMITTED, slack_ui.STAGE_RETRY_WAIT)


def last_outbound_kind(last):
    """`ui` for a card, `plain` for a message, None when nothing was sent."""
    if not last:
        return None
    return UI_OUTBOUND_KIND if last.get("kind") == UI_OUTBOUND_KIND else "plain"


def refuse_ui(alias, reason, last_kind, next_text):
    """FR-35345-1(d): the one refusal line — stdout, exit 2, nothing sent,
    nothing recorded. Only the plain edit's `kind_mismatch` names
    `last_outbound_kind`; a rich update's refusal is explained by the
    presentation state, not by the newest outbound, and carries no such
    member (pass `last_kind=None`)."""
    line = {"outcome": "refused", "reason": reason, "lane": alias}
    if last_kind is not None:
        line["last_outbound_kind"] = last_kind
    line["next"] = next_text
    print(json.dumps(line))
    return EXIT_INPUT


def lane_live_presentation(ui, alias):
    """The lane's most recent LIVE presentation in `ui.presentations` as
    `(ui_id, card)`, or None (ADR 35345 D6 Amendment 1): the card a rich
    update addresses, whatever plain messages followed it. Most recent by
    `posted_at`, the higher send-order `seq` winning a tie."""
    mine = [(uid, card) for uid, card in ui["presentations"].items() if card.get("lane") == alias]
    if not mine:
        # No UI state for this lane: `status --json` (and the plain edit gate)
        # never need the contract module here, so a copy of this script
        # without `slack_ui.py` keeps serving them (Constitution XIII).
        return None
    slack_ui = slack_ui_module()
    live = [(uid, card) for uid, card in mine if card.get("state") == slack_ui.PRESENTATION_LIVE]
    if not live:
        return None
    # Latest `posted_at` (send time); ties by the higher send-order `seq`
    # (FR-35345-6), then insertion order.
    return max(enumerate(live), key=lambda pair: (pair[1][1].get("posted_at") or "",
                                                  int(pair[1][1].get("seq") or 0), pair[0]))[1]


def lane_presentation(ui, alias):
    """`status --json`'s per-lane `presentation` (FR-35345-6): `{ui_id, revision,
    state, pending_operation_id, posted_at, expires_at}` of the lane's live
    card, or None."""
    found = lane_live_presentation(ui, alias)
    if found is None:
        return None
    ui_id, card = found
    return {"ui_id": ui_id, "revision": card.get("revision"), "state": card.get("state"),
            "pending_operation_id": card.get("pending_operation_id"), "posted_at": card.get("posted_at"),
            "expires_at": card.get("expires_at"), "version": card.get("version") or 1,
            "pending_submission": card.get("pending_submission")}


def ui_update_target(checkpoint, alias):
    """What `--replace-last --message-json` addresses: `((ui_id, expected_revision),
    None)` for the lane's most recent live presentation (ADR 35345 D6
    Amendment 1: plain messages since do not change the target), else
    `(None, (reason, last_kind, next))` for `refuse_ui` (FR-35345-1(d),
    FM-35345-12), in the spec's order: (i) `presentation_pending` while an
    open post operation of the lane awaits its result (even with an older
    live card: the update was meant for the new one) — the pending-update
    pointer is arm (i)'s other half, checked after the same-id dispatch;
    (ii) the live presentation; (iii) `revision_unknown` after an unresolved
    conflict; (iv) else
    `no_live_presentation` (none ever posted here, the last one ended
    without a presentation, or it is fallback / expired). The connector
    never converts a plain message into a card; `kind_mismatch` is the
    plain edit's refusal on a card."""
    slack_ui = slack_ui_module()
    ui = ui_tables(checkpoint)
    new_post = f"`reply --to {alias} --message-json -` to post a new card"
    # Arm (i): an open post operation of this lane (its `confirmed` unread —
    # the relay mints `ui_id` in that result, so no presentation record
    # exists yet). The update was meant for that newest card, so an older
    # live presentation does not take it; plain replies are transparent.
    # Keyed on `ui.operations`, never the lane ledger: the ledger is a
    # bounded FIFO that plain sends can trim while a post is open.
    posts = [rec for rec in ui["operations"].values() if rec.get("lane") == alias and rec.get("kind") == slack_ui.POST]
    if any(ui_stage_open(rec.get("stage")) for rec in posts):
        return None, ("presentation_pending", None,
                      f"the card posted in {alias} has no result from the relay yet: wait for its "
                      f"confirmation and update then, or use {new_post}")
    live = lane_live_presentation(ui, alias)
    if live is not None:
        ui_id, card = live
        return (ui_id, int(card["revision"])), None
    cards = [(uid, card) for uid, card in ui["presentations"].items() if card.get("lane") == alias]
    unknown = [uid for uid, card in cards if card.get("state") == slack_ui.PRESENTATION_REVISION_UNKNOWN]
    if unknown:
        return None, ("revision_unknown", None,
                      f"card {unknown[-1]} in {alias} moved under a conflicting update and its revision is unknown: "
                      f"use {new_post}")
    if cards:
        states = sorted({card.get("state") or "not recorded" for _, card in cards})
        return None, ("no_live_presentation", None,
                      f"the card in {alias} is {' / '.join(states)} — no controls to update: use {new_post}")
    if posts:
        newest_post = max(posts, key=lambda rec: rec.get("started_at") or "")
        return None, ("no_live_presentation", None,
                      f"the last card in {alias} was not confirmed ({newest_post.get('status') or 'no result'}); "
                      f"there is nothing to update: use {new_post}")
    return None, ("no_live_presentation", None, f"no card is live in {alias}: use {new_post}")


def ui_pending_update_refusal(ui, alias, ui_id):
    """FR-35345-2(f): the presentation's `pending_operation_id` names an
    update that is not yet terminal (submitting, submitted, retry_wait); the
    next DIFFERENT update parks — two same-revision updates would race at the
    relay and could strand the card `revision_unknown`. Checked after the
    same-id dispatch, so the same words again still reprint that update's own
    line. A pointer at a terminal record is idle."""
    pending = (ui["presentations"].get(ui_id) or {}).get("pending_operation_id")
    if pending and ui_stage_open((ui["operations"].get(pending) or {}).get("stage")):
        return ("presentation_pending", None,
                f"an update of card {ui_id} in {alias} is still awaiting the relay's result: wait for it, "
                f"then send the next update (the same words again reprint that update's line)")
    return None


def ui_operation_age(record):
    """Epoch seconds of the record's last stage change: `result_at` once
    terminal, else `submitted_at`, else `started_at`."""
    stamp = record.get("result_at") or record.get("submitted_at") or record.get("started_at")
    return ui_stamp_epoch(slack_ui_module(), stamp)


def prune_ui_operations(ui, now):
    """FR-35345-6 at admission: a terminal record older than the relay's receipt
    retention goes; then terminal records oldest-first down to the cap. An open
    record is never evicted (the listener's sweep settles it). Returns None when
    a slot is free, else the `next` sentence of the `ui_operations_full`
    refusal (FM-35345-17): the deadline after which the oldest in-flight
    record resolves."""
    slack_ui = slack_ui_module()
    operations = ui["operations"]
    evict_ui_operations(slack_ui, ui, now, cap=slack_ui.UI_OPERATIONS_MAX - 1)  # the listener's tick prunes alike
    if len(operations) < slack_ui.UI_OPERATIONS_MAX:
        return None

    def resolves_at(record):
        if record.get("stage") == slack_ui.STAGE_SUBMITTED and record.get("deadline_at"):
            return slack_ui.epoch(record["deadline_at"])
        if record.get("stage") == slack_ui.STAGE_RETRY_WAIT and record.get("retry_at"):
            return slack_ui.epoch(record["retry_at"]) + slack_ui.UI_RESULT_DEADLINE_S
        return ui_operation_age(record) + slack_ui.UI_RESULT_DEADLINE_S

    oldest = min(resolves_at(record) for record in operations.values())
    return (f"{len(operations)} interactive operations await the relay's result; the oldest resolves "
            f"by {slack_ui.iso(oldest)} — wait for it, then send this call again")


def ui_pending_line(record, operation_id, key, alias, requester, note=None, cards=None):
    """FR-35345-2(e): the one stdout line of an admitted post / update (or a
    version 2 reconcile, D15). `pending` is not the `queued`/`sent`/`updated`
    receipt family (ADR 35345 D4/D8): the mailbox took the operation; Slack
    has not rendered anything yet. `note` says when the call meant one thing
    and the connector did another (a v2 card cannot be edited in place)."""
    line = {
        "outcome": "pending",
        "operation_id": operation_id,
        "ui_id": record.get("ui_id"),
        "lane": alias,
        "conversation": record.get("key"),
        "kind": record["kind"],
        "idempotency_key": key,
        "summary": f"{requester} · {alias} · pending",
        "next": UI_RECONCILE_NEXT if record["kind"] == "reconcile" else UI_PENDING_NEXT,
    }
    if note:
        line["note"] = note
    if cards:
        line["cards"] = cards  # ruling 25: the lane's card capability on every reply line
        line["reply_shape"] = reply_shape_line(cards, alias)  # #41245: and its reply shape
    return line


def ui_mark_operation(lane, ui, kind, operation_id, ui_id, text):
    """Under the lock, before the send (FR-35345-2(d)). A post owns the lane's
    whole `last_outbound` (`kind: ui`) and its own ledger entry (the object's
    `text`, `interim: false`, stamped `kind: ui` and `operation_id` so the
    entry names its family). An update owns no entry, touches `last_outbound`
    not at all and rewrites nothing at admission: it names itself on the
    presentation as `pending_operation_id` and keeps its bounded `text` on
    its own record only until the relay's verdict (#36324; D9 Amendment 1);
    the post entry takes the update's `operation_id` and that text, marked,
    when the relay confirms (the listener, FR-35345-3(b))."""
    route = lane.get("route") or {}
    if kind == slack_ui_module().UPDATE:
        card = ui["presentations"].get(ui_id)
        if card is not None:
            card["pending_operation_id"] = operation_id
        record = ui["operations"].get(operation_id)
        if record is not None:
            record["text"] = text[:TEXT_BOUND]
        return
    # Never `ui_id` or `revision`: the presentation record alone knows the card.
    lane["last_outbound"] = {
        "container_id": route.get("container_id") or route.get("target_client_mailbox_id"),
        "remote_message_id": operation_id,
        "sent_at": utc_now(),
        "kind": UI_OUTBOUND_KIND,
        "operation_id": operation_id,
    }
    if append_outbound_entry(lane, operation_id, text, interim=False):
        stamp_ui_entry(lane, operation_id)


def ui_undo_operation_marks(lane, ui, operation_id):
    """A failed send (or FM-35345-7's `not_sent`) undoes the operation's marks
    BY KEY, never from a snapshot. The record itself is only read: a failed
    send's caller removes it, `not_sent` keeps it terminal for the retention
    window. A failed update clears the presentation's `pending_operation_id`
    and touches nothing else. A failed post drops its own ledger entry; then
    `last_outbound` is touched only if it still names this operation — rebuilt
    from the newest remaining ledger entry (its `kind` and `operation_id`
    and nothing else) or cleared when the ledger is empty. An outbound that landed in between is never erased,
    and a real card is never relabelled plain."""
    slack_ui = slack_ui_module()
    record = ui["operations"].get(operation_id) or {}
    ledger = [entry for entry in lane.get("outbound") or [] if entry.get("message_id") != operation_id]
    lane["outbound"] = ledger
    if record.get("kind") == slack_ui.UPDATE:
        # A failed update: the presentation's pending pointer is cleared;
        # `last_outbound` and the live card are untouched.
        clear_pending_pointer(ui, operation_id)
        return
    last = lane.get("last_outbound") or {}
    if last.get("operation_id") != operation_id:
        return
    # Newest by `sent_at_ms`, the later entry winning a same-millisecond tie.
    _, newest = max(enumerate(ledger), key=lambda pair: (int(pair[1].get("sent_at_ms") or 0), pair[0]),
                    default=(None, None))
    if newest is None:
        lane["last_outbound"] = None
        return
    route = lane.get("route") or {}
    rebuilt = {
        "container_id": route.get("container_id") or route.get("target_client_mailbox_id"),
        "remote_message_id": newest["message_id"],
        "sent_at": newest.get("sent_at") or utc_now(),
        "edit_target": newest["message_id"],
    }
    if newest.get("kind") == UI_OUTBOUND_KIND:
        # The entry's `kind` and `operation_id` and nothing else (`edit_target`
        # stays, FR-35345-2(d)): the `--text` kind gate keeps a card out of the
        # plain edit path, and whether a rich update can address it is the
        # presentation record's business.
        rebuilt.update(kind=UI_OUTBOUND_KIND, operation_id=newest.get("operation_id"))
    lane["last_outbound"] = rebuilt


def outstanding_submissions(ui, alias):
    """The lane's version 2 cards with an unsettled business submission, oldest tap first."""
    cards = [(uid, card) for uid, card in (ui.get("presentations") or {}).items()
             if card.get("lane") == alias and card.get("version") == 2 and card.get("pending_submission")]
    return sorted(cards, key=lambda pair: int((pair[1].get("pending_submission") or {}).get("action_seq") or 0))


def settle_outstanding_submissions(alias, *, matched=None):
    """ADR 35345 D15 item 5: the agent's next reply in the lane settles every
    outstanding tap first — one `custom.slack.ui.reconcile` per card, sent
    before the reply, `status: succeeded`, `show_template` = the declared
    template the reply matched (`matched` = (ui_id, name)), else the card's
    synthesized `done:<id>` for the pressed control, else none. Records the
    operation (kind `reconcile`) and marks the card `settled`; a failed send
    puts the tap back so the next reply settles it. Returns
    [(operation_id, record, key)] in send order; [] when nothing was pending
    (the common case costs one state read)."""
    try:
        slack_ui = slack_ui_module()
        v2 = slack_ui_v2_module()
    except ConnectorError:
        return []
    with StateStore() as store:
        state = store.load(require=True)
        checkpoint = state["checkpoint"]
        ui = checkpoint.get("ui") or {}
        pending_cards = outstanding_submissions(ui, alias)
        if not pending_cards:
            return []
        lane = (checkpoint.get("lanes") or {}).get(alias) or {}
        mailbox = state.get("mailbox") or {}
        sender_id = mailbox.get("client_mailbox_id")
        send_state_file = mailbox.get("state_file") or mailbox_cli_state_file()
        if not sender_id:
            return []
        plans = []
        for ui_id, card in pending_cards:
            pending = card["pending_submission"]
            name = matched[1] if matched and matched[0] == ui_id else v2.settlement_template(card)[0]
            try:
                envelope = v2.build_reconcile_envelope(
                    ui_id=ui_id, event_id=pending["event_id"], action_seq=pending["action_seq"],
                    base_model_revision=pending["model_revision"], show_template=name)
            except slack_ui.SlackUiInputError as error:
                diag(f"ui reconcile skipped (card {ui_id}: {error})")
                continue
            payload_json = json.dumps(envelope, separators=(",", ":"))
            key = reply_idempotency_key(
                lane.get("key") or alias,
                f"ui:reconcile:{ui_id}:{pending['event_id']}:{slack_ui.canonical_json(envelope['body']['payload'])}")
            op_id = message_id_from_key(key)
            existing = ui["operations"].get(op_id)
            if existing is not None and existing.get("stage") != slack_ui.STAGE_SUBMITTING:
                continue  # already settled by this very reconcile
            record = existing or slack_ui.new_operation_record(
                lane=alias, key=lane.get("key") or alias, transport="mailbox", relay=card.get("relay"),
                kind=slack_ui.RECONCILE, payload_sha256=slack_ui.payload_digest(envelope), now=ui_now(), ui_id=ui_id)
            record.update(version=2, event_id=pending["event_id"], show_template=name)
            ui["operations"][op_id] = record
            card["pending_submission"] = None
            card["state"] = v2.PRESENTATION_SETTLED
            card["settled_by"] = op_id
            plans.append((op_id, key, payload_json, card.get("relay"), ui_id, pending))
        store.save(state)
    cli = mailbox_cli()
    sent_ops = []
    for op_id, key, payload_json, relay, ui_id, pending in plans:
        sent = run_mailbox_cli(cli, [
            "send", "--mailbox-id", sender_id, "--state-file", send_state_file,
            "--target-mailbox-id", relay, "--message-id", op_id, "--payload-json", payload_json,
        ])
        with StateStore() as store:
            state = store.load(require=True)
            ui = ui_tables(state["checkpoint"])
            card = ui["presentations"].get(ui_id)
            if sent.returncode != 0:
                # The tap is still outstanding: the next reply settles it (fail closed by key).
                ui["operations"].pop(op_id, None)
                if card is not None:
                    card.update(pending_submission=pending, state=slack_ui.PRESENTATION_LIVE, settled_by=None)
                store.save(state)
                lines = (sent.stderr or "").strip().splitlines()
                diag(f"ui reconcile of card {ui_id} not sent (exit {sent.returncode}{': ' + lines[-1] if lines else ''}); "
                     f"the next reply settles it")
                continue
            record = ui["operations"].get(op_id)
            if record is not None and record.get("stage") == slack_ui.STAGE_SUBMITTING:
                record = slack_ui.mark_submitted(record, now=ui_now())
                ui["operations"][op_id] = record
            store.save(state)
        diag(f"ui reconcile sent (op {op_id}, card {ui_id}, view {(record or {}).get('show_template') or 'relay default'})")
        sent_ops.append((op_id, record, key))
    return sent_ops


def reply_message_json(args):
    """`reply --to <lane> --message-json <json>|-` (#35345; spec 23499
    FR-35345-1/-2/-5/-6; ADR 35345 D6/D8/D9/D13/D14): one Slack-shaped object
    becomes a `custom.slack.ui` post — or, with `--replace-last`, an update of
    the lane's confirmed live card by its stored `ui_id` and revision. The
    connector admits locally (envelope and bounds only; the relay owns the
    Block Kit grammar), records the operation under the state lock, sends ONCE
    by a stable message id derived like a plain reply's (a retried tool call
    resends nothing), and prints `pending` at mailbox admission. Slack render
    confirmation arrives later as a `capability_result` the listener consumes;
    nothing here waits for it."""
    slack_ui = slack_ui_module()
    if getattr(args, "attach", None):
        raise InputError("--attach does not ride --message-json: files go on the plain reply path (ADR 35345 D6)")
    raw = sys.stdin.read() if args.message_json == "-" else args.message_json
    if not raw or not raw.strip():
        raise InputError("--message-json - needs the JSON object on stdin (or pass the JSON text as the value)")
    kind = slack_ui.UPDATE if args.replace_last else slack_ui.POST
    try:
        admitted = slack_ui.admit_message_json(raw, kind=kind)
    except slack_ui.SlackUiInputError as error:
        raise InputError(str(error))
    canonical = slack_ui.canonical_json(admitted)
    cli = mailbox_cli()
    take_up_stale_operations(slack_ui, cli, args.to)  # FM-35345-7: before this reply is judged
    with StateStore() as store:
        state = store.load(require=True)
        checkpoint = state["checkpoint"]
        lane = (checkpoint.get("lanes") or {}).get(args.to)
        if lane is None:
            raise ConnectorError(
                f"unknown lane {args.to!r}; every listener line is prefixed with the lane to reply to"
            )
        route = lane.get("route") or {}
        if route.get("transport") != "mailbox" or not lane.get("relay") or not route.get("conversation_id"):
            # FR-35345-1(e): only the Muse Tag relay renders UI.
            where = "a Slack lane" if route.get("transport") == "slack" else "a mailbox lane the relay did not originate"
            raise InputError(
                f"ui_needs_relay_lane: --message-json posts through the Muse Tag relay only; lane {args.to} is "
                f"{where} — reply there with --text"
            )
        mailbox = state.get("mailbox") or {}
        sender_id = mailbox.get("client_mailbox_id")
        if not sender_id:
            raise ConnectorError(
                "no mailbox registration: arm the mailbox `listen` first (the daemon's startup sequence; --mailbox-id optional)"
            )
        send_state_file = mailbox.get("state_file") or mailbox_cli_state_file()
        target = route.get("target_client_mailbox_id")
        if not target:
            raise ConnectorError("this lane has no mailbox target recorded; it cannot be replied to")
        if target == sender_id:
            # #27890: a legacy pre-guard lane admitted from our own echo can
            # still sit in state.json; the rich path refuses it as the plain one does.
            raise ConnectorError("refusing to reply to this worker's own mailbox id (self-echo lane)")
        newest, _received, newest_envelope = newest_inbound("mailbox", lane["key"], checkpoint, args.to)
        requester = ((newest_envelope or {}).get("actor") or {}).get("display") or lane["key"]
        ui = ui_tables(checkpoint)
        ui_id = expected_revision = None
        # ADR 35345 D15 item 1: which version this card takes, from cached facts (no probe).
        versions = relay_ui_versions(state, target)
        cards = cards_line(state, lane)  # ruling 25: on every reply line
        if "behavior" in admitted and 2 not in versions:
            raise InputError(
                f"message JSON `behavior` needs a relay that serves custom.slack.ui version 2 for you; the relay of lane "
                f"{args.to} ({target}) serves {'version ' + ', '.join(map(str, versions)) if versions else 'no UI version'} "
                f"— remove `behavior` and post the card as today")
        try:
            v2 = slack_ui_v2_module() if 2 in versions else None
        except ConnectorError as error:
            # Constitution XIII: a copy without slack_ui_v2.py still posts version 1 cards.
            if "behavior" in admitted:
                raise
            diag(f"{error}; posting version 1")
            v2 = None
        note = matched = None
        if args.replace_last and v2 is not None:
            live = lane_live_presentation(ui, args.to)
            if live is not None and live[1].get("version") == 2:
                # D15 item 6 / D6 Amendment 2: a version 2 card is not edited. The
                # reply's blocks either ARE a declared template (the reconcile alone
                # shows it) or become a new card below the settled one.
                live_id, live_card = live
                if live_card.get("pending_submission"):
                    name, is_match = v2.settlement_template(live_card, admitted["blocks"])
                    if is_match:
                        matched = (live_id, name)
                if matched is None:
                    kind, note = slack_ui.POST, UI_NEW_CARD_NOTE
        version = 1
        behavior = None
        if kind == slack_ui.POST and v2 is not None and matched is None:
            # #38715 QA r16 F2: sized as the request this lane sends, so a long card
            # steps down the template ladder (or takes version 1) instead of a refusal.
            version = v2.choose_version(admitted, relay_versions=versions, conversation_id=route["conversation_id"])
            if "behavior" in admitted:
                if version == 2:
                    try:
                        behavior = v2.admit_behavior(admitted["behavior"])
                    except slack_ui.SlackUiInputError as error:
                        raise InputError(str(error))
            elif admitted.get("on_invalid") != "fallback":
                synthesis = v2.synthesize(admitted, conversation_id=route["conversation_id"])
                behavior = synthesis.behavior if version == 2 else None
                ladder_note = v2.degradation_note(synthesis)
                if ladder_note:
                    diag(ladder_note)
        if matched is None and settle_needed(ui, args.to):
            settle_now = True
        else:
            settle_now = False
        try:
            if matched is not None:
                envelope = None
                key_text = None
            elif kind == slack_ui.UPDATE:
                target_card, refusal = ui_update_target(checkpoint, args.to)
                if refusal is not None:
                    return refuse_ui(args.to, *refusal)
                ui_id, expected_revision = target_card
                envelope = slack_ui.build_update_envelope(admitted, ui_id=ui_id, expected_revision=expected_revision)
                # FR-35345-2(c): the key binds the card and the revision it
                # addresses, so the same words at the next revision are a new
                # operation and the same call at the same revision is the same one.
                key_text = f"ui:update:{ui_id}:{expected_revision}:{canonical}"
            elif version == 2:
                envelope = v2.build_post_envelope(admitted, behavior, conversation_id=route["conversation_id"])
                key_text = f"ui:v2:{canonical}"
            else:
                envelope = slack_ui.build_post_envelope(admitted, conversation_id=route["conversation_id"])
                key_text = canonical
        except slack_ui.SlackUiInputError as error:
            raise InputError(str(error))
    if matched is not None or settle_now:
        # D15 item 5: the tap is settled before anything else goes out.
        settled = settle_outstanding_submissions(args.to, matched=matched)
        if matched is not None:
            for op_id, record, key in settled:
                if record.get("ui_id") == matched[0]:
                    print(json.dumps(ui_pending_line(record, op_id, key, args.to, requester, cards=cards)))
                    return 0
            raise ConnectorError(f"the reconcile of card {matched[0]} could not be sent; send the reply again")
    with StateStore() as store:
        state = store.load(require=True)
        checkpoint = state["checkpoint"]
        lane = (checkpoint.get("lanes") or {}).get(args.to)
        if lane is None:
            raise ConnectorError(f"lane {args.to!r} disappeared while the reply was being prepared")
        route = lane.get("route") or {}
        newest, _received, _envelope = newest_inbound("mailbox", lane["key"], checkpoint, args.to)
        ui = ui_tables(checkpoint)
        # FR-35345-5(5): `slack_ui` already refused an envelope over the 16 KiB
        # provider bound (`UI_REQUEST_MAX_BYTES`), measured on this same form.
        payload_json = json.dumps(envelope, separators=(",", ":"))
        key = args.key or reply_idempotency_key(lane["key"], key_text, newest)
        operation_id = message_id_from_key(key)
        digest = slack_ui.payload_digest(envelope)
        existing = ui["operations"].get(operation_id)
        if existing is not None:
            if existing.get("payload_sha256") != digest:
                raise ConnectorError("operation id was already used with a different payload; refusing to reuse it")
            if existing.get("stage") != slack_ui.STAGE_SUBMITTING:
                # The same dispatch again: the recorded line, no second send.
                print(json.dumps(ui_pending_line(existing, operation_id, key, args.to, requester, cards=cards)))
                return 0
            # A crash between the record and the send's return (FM-35345-7):
            # the same id goes again and the receiver dedups (INV-6).
            record = existing
        else:
            pending = ui_pending_update_refusal(ui, args.to, ui_id) if args.replace_last else None
            if pending is not None:
                return refuse_ui(args.to, *pending)
            full = prune_ui_operations(ui, ui_now())
            if full is not None:
                return refuse_ui(args.to, "ui_operations_full", None, full)
            expiry = {"expires_in_seconds": admitted["expires_in_seconds"]} if "expires_in_seconds" in admitted else {}
            record = slack_ui.new_operation_record(
                lane=args.to, key=lane["key"], transport="mailbox", relay=target, kind=kind, payload_sha256=digest,
                now=ui_now(), ui_id=ui_id, expected_revision=expected_revision, **expiry,
            )
            if kind == slack_ui.POST:
                # FR-35345-6: the per-`checkpoint.ui` send-order counter, the
                # live-card tie-break the listener copies onto the presentation.
                ui["last_seq"] = int(ui.get("last_seq") or 0) + 1
                record["seq"] = ui["last_seq"]
            if version == 2:
                # ADR 35345 D15 item 7: bounded facts for the later settlement.
                record["version"] = 2
                record["template_digests"] = v2.template_digests(behavior)
                record["done_templates"] = v2.done_templates(admitted, behavior) if "behavior" not in admitted else {}
            ui["operations"][operation_id] = record
            # Marks are written once, with the record: a crash-window resend
            # (FM-35345-7) re-sends the id but never restamps `last_outbound`
            # over an outbound that landed after the crash.
            ui_mark_operation(lane, ui, kind, operation_id, ui_id, admitted["text"])
        store.save(state)
    sent = run_mailbox_cli(cli, [
        "send", "--mailbox-id", sender_id, "--state-file", send_state_file,
        "--target-mailbox-id", target, "--message-id", operation_id,
        "--payload-json", payload_json,
    ])
    with StateStore() as store:
        state = store.load(require=True)
        checkpoint = state["checkpoint"]
        ui = ui_tables(checkpoint)
        lane = (checkpoint.get("lanes") or {}).get(args.to)
        if sent.returncode != 0:
            # Fail closed (FR-35345-2(d)): the record goes and its marks are
            # undone by key, so a retry re-sends the same id.
            if lane is not None:
                ui_undo_operation_marks(lane, ui, operation_id)
            ui["operations"].pop(operation_id, None)
            store.save(state)
            lines = (sent.stderr or "").strip().splitlines()
            cause = f": {lines[-1].strip()!r}" if lines else ""
            raise ConnectorError(
                f"muse-mailbox send failed (exit {sent.returncode}{cause}); recorded no operation so a retry re-sends"
            )
        record = ui["operations"].get(operation_id) or record
        if record.get("stage") == slack_ui.STAGE_SUBMITTING:
            # A transition, not an assignment: the listener may have settled
            # this record while `send` ran (FM-35345-7), and a settled record
            # never moves backwards.
            record = slack_ui.mark_submitted(record, now=ui_now())
        ui["operations"][operation_id] = record
        store.save(state)
    print(json.dumps(ui_pending_line(record, operation_id, key, args.to, requester, note=note, cards=cards)))
    return 0


def settle_needed(ui, alias):
    """True when a version 2 card of the lane holds an unsettled tap."""
    return bool(outstanding_submissions(ui, alias))


def cmd_reply(args):
    """The one reply verb (D1/D2): `send`, `respond`, and `update` were never
    three intents — they were one reply under three names because the two
    transports were built independently and editing was filed as its own
    capability. The lane alias makes the call identical across transports. A
    reply posts (or edits with `--replace-last`) and records its receipt; it
    acknowledges nothing (`adr:23499-slack-connector-runtime-contract#D18`)."""
    if getattr(args, "message_json", None) is not None:
        return reply_message_json(args)
    # #37018 (FR-35345-1(a)): `--text -` is the same `-` convention as
    # `--message-json -` — stdin is the text; a bare `-` is never sent.
    text = unescape_literal_newlines(sys.stdin.read() if args.text in (None, "-") else args.text)
    if not isinstance(text, str) or not text.strip():
        if args.text == "-":
            raise InputError("--text - needs the text on stdin (or pass the text as the value)")
        raise InputError("reply needs text: pass --text or --message-json, or pipe text on stdin")
    with StateStore() as store:
        state = store.load(require=True)
        checkpoint = state["checkpoint"]
        lane = (checkpoint.get("lanes") or {}).get(args.to)
        if (lane is not None and args.replace_last
                and last_outbound_kind(lane.get("last_outbound")) == UI_OUTBOUND_KIND):
            # ADR 35345 D4/D6 (FR-35345-1(d)), read under the lock: a card is
            # never rewritten by a plain edit.
            # `next` has three arms (FR-35345-1(d)): the rich update when it
            # would go through, "wait, then" it when it would be
            # presentation_pending, else a plain reply.
            target, refusal = ui_update_target(checkpoint, args.to)
            pending = (refusal is None and ui_pending_update_refusal(ui_tables(checkpoint), args.to, target[0]) is not None) \
                or (refusal is not None and refusal[0] == "presentation_pending")
            rich = f"`reply --to {args.to} --replace-last --message-json -`"
            if pending:
                fits = f"wait, then {rich} to update it"
            elif refusal is None:
                fits = f"use {rich} to update it, or a plain `reply --to {args.to} --text …` to say something new"
            else:
                fits = f"use a plain `reply --to {args.to} --text …` to say something new"
            return refuse_ui(args.to, "kind_mismatch", UI_OUTBOUND_KIND,
                             f"the newest outbound in {args.to} is an interactive card: {fits}")
    if lane is None:
        raise ConnectorError(
            f"unknown lane {args.to!r}; every listener line is prefixed with the lane to reply to"
        )
    route = lane.get("route") or {}
    attach = reply_attachments(args, route)
    if route.get("transport") == "mailbox" and lane.get("relay"):
        # ADR 35345 D15 item 5: a plain reply settles the lane's outstanding tap first.
        settle_outstanding_submissions(args.to)
    # D18 item 3: the key is scoped to the lane's newest inbound line.
    newest, _received, newest_envelope = newest_inbound(route.get("transport"), lane["key"], checkpoint, args.to)
    # ADR 25011 D22 item 4: the tool row's `└` line is the result's `summary`.
    requester = ((newest_envelope or {}).get("actor") or {}).get("display") or lane["key"]
    if args.replace_last:
        receipt = replace_last_reply(args.to, lane, text)
        receipt["summary"] = f"{requester} · {args.to} · ✓" + (" · edited" if receipt.get("folded") else "")
        receipt["cards"] = cards_line(state, lane)  # ruling 25: on every reply line
        receipt["reply_shape"] = reply_shape_line(receipt["cards"], args.to)  # #41245
        print(json.dumps(receipt))
        return 0
    key = args.key or reply_idempotency_key(lane["key"], text, newest, attach=attach)
    if route.get("transport") == "mailbox":
        receipt = mailbox_reply(route, key, text, attach=attach)
        # `adr:23499-slack-connector-runtime-contract#D8`: the mailbox arm records too, so `--replace-last` has
        # something to supersede. Its receipt names the id `message_id` and its "container" is
        # the target mailbox.
        record_last_outbound(
            args.to,
            route.get("container_id") or route.get("target_client_mailbox_id"),
            receipt.get("message_id"),
            text=text,
        )
    else:
        receipt = slack_reply(route, key, text)
        record_last_outbound(args.to, route.get("container_id"), receipt.get("remote_message_id"), text=text)
    cards = cards_line(state, lane)
    print(json.dumps(dict(receipt, lane=args.to, summary=f"{requester} · {args.to} · ✓", cards=cards,
                          reply_shape=reply_shape_line(cards, args.to))))
    return 0


def transport_arg(args):
    explicit = getattr(args, "transport", None)
    return canonical_transport(explicit) if explicit else None


# ---------------------------------------------------------------------------
# `progress-sink` — the channel end of the agents watcher (#41802; spec 23499
# FR-41802-2, spec 25011 FR-41802-1; owner rulings 56/56a/57/59). The
# watcher (`agents.py watch`) pipes each rendered ☐/◐/⛔/✅/✖ list here; this
# verb rewrites the lane's plan post IN PLACE BY ID — Slack `chat.update`
# by ts, the relay's `message_edit` by the original id — so a later
# coordinator message displaces nothing, and answers with the message id and
# its last edit stamp (the watcher's backoff). The target is the plan post the
# lane recorded (`note_plan_post`); before one exists the answer is
# `skipped: no_plan` and nothing is sent (#41959). A lane that cannot fold an
# edit posts only the news as a successor; a card is refused.
# ---------------------------------------------------------------------------

SINK_ROW_GLYPHS = ("☐", "⏳", "◐", "⛔", "✅", "✖")
SINK_OPEN_GLYPHS = ("☐", "⏳", "◐", "⛔")
SINK_ROW_RE = re.compile(r"^(☐|⏳|◐|⛔|✅✔|✅|✖)\s?(.*)$")


def sink_row(line):
    """`(mark, rest)` when `line` is a list row, else None."""
    match = SINK_ROW_RE.match(line)
    return (match.group(1), match.group(2)) if match else None


def sink_row_label(rest):
    """The row's head before the first ` · `: `<name> — <what>`, what the plan's own rows carry."""
    return rest.split(" · ", 1)[0].strip()


def lane_can_fold(lane):
    """True when the lane's edit rewrites in place: Slack always; the mailbox only on a relay lane whose CLI has the
    edit verb (`#D20`). Otherwise an "edit" is a successor message, which a periodic sink must never post."""
    route = lane.get("route") or {}
    if route.get("transport") == "slack":
        return True
    return bool(lane.get("relay") and route.get("conversation_id") and mailbox_capability("edit"))


def load_lane(alias):
    with StateStore() as store:
        state = store.load(require=True)
        lane = (state["checkpoint"].get("lanes") or {}).get(alias)
    if lane is None:
        raise InputError(f"unknown lane {alias!r}; every listener line is prefixed with the lane to reply to")
    return lane


def ledger_entry(lane, message_id):
    for entry in lane.get("outbound") or []:
        if entry.get("message_id") == message_id:
            return entry
    return None


def plan_post_open(lane, message_id):
    """True when `message_id` can still be the list's target: its ledger text carries an OPEN row, or the ledger no
    longer has it (a lane recorded before the entry was pinned). A finished goal's all-✅ list is no plan post: a
    reused lane's next goal answers `no_plan` until its own plan is posted (review of PR #41981)."""
    entry = ledger_entry(lane, message_id)
    if entry is None:
        return True
    return any(row and row[0] in SINK_OPEN_GLYPHS for row in map(sink_row, (entry.get("text") or "").split("\n")))


def sink_target(lane, message_id=None):
    """`(message_id, kind)`: the message the list edits — the lane's recorded plan post (`note_plan_post`; a fresh plan
    post moves the list once), else the id the watcher carried back (a lane recorded before #41959), each only while
    its text still carries an open row; else nothing: never the lane's newest message, which before the plan post is
    the daemon's ACK, a progress reply or a question card (QA r25; review of PR #41981). `ui` when the target itself
    is the lane's card, so the card refusal stays."""
    last = lane.get("last_outbound") or {}
    for candidate in (lane.get("plan_message_id"), message_id):
        if candidate and plan_post_open(lane, candidate):
            return candidate, ("ui" if last.get("remote_message_id") == candidate and last_outbound_kind(last) == UI_OUTBOUND_KIND else "plan")
    return None, None


def apply_list(text, rows, single_row=False):
    """The new message text. Block mode: the run of row lines (first to last) becomes the incoming rows; the lines
    around it stay as the coordinator wrote them. Row mode (`--row`, one step of the coordinator's own): the row whose
    head matches the incoming row's head is rewritten; else an open row naming the step's first word; else the row
    is appended (FR-41802-2(b); a ticked row is never rewritten by a later step of the same first word)."""
    lines = text.split("\n") if text else []
    incoming = [line for line in rows if sink_row(line)]
    if not incoming:
        return text
    if single_row:
        mark, rest = sink_row(incoming[0])
        label = sink_row_label(rest)
        head = label.split(" — ", 1)[0].strip().lower()
        index = next((i for i, line in enumerate(lines) if sink_row(line) and sink_row_label(sink_row(line)[1]).lower() == label.lower()), None)
        if index is None:
            index = next((i for i, line in enumerate(lines) if sink_row(line) and sink_row(line)[0] in SINK_OPEN_GLYPHS
                          and head and head in sink_row(line)[1].lower()), None)
        if index is None:
            lines.append(incoming[0])
        else:
            lines[index] = incoming[0]
        return "\n".join(lines)
    row_lines = [i for i, line in enumerate(lines) if sink_row(line)]
    if not row_lines:
        return "\n".join(lines + incoming) if lines else "\n".join(incoming)
    first, last = row_lines[0], row_lines[-1]
    return "\n".join(lines[:first] + incoming + lines[last + 1:])


def sink_write(alias, lane, message_id, text, fold):
    """Rewrite `message_id` in place (Slack `chat.update` by ts; the relay's `message_edit` by the original id) and stamp
    the ledger entry; the lane's `--replace-last` cursor stays where the coordinator's newest post put it (only
    `sent_at` is bumped, #26855). Without fold, the text goes out as a new message through the `#D8` successor path.
    Returns (id, stamp_ms, folded)."""
    route = lane.get("route") or {}
    if not fold:
        receipt = replace_last_reply(alias, lane, text)
        return receipt.get("remote_message_id"), now_ms(), False
    if route.get("transport") == "slack":
        edit_lane_message(alias, lane, message_id, text, f"edit:{message_id}")
    else:
        key = reply_idempotency_key(lane.get("key") or alias, text, answering=f"sink_edit:{message_id}:{now_ms()}")
        mailbox_edit(route, key, message_id, text)
    stamp = now_ms()
    with StateStore() as store:
        state = store.load(require=True)
        current = (state["checkpoint"].get("lanes") or {}).get(alias)
        if current is not None:
            if current.get("last_outbound"):
                current["last_outbound"]["sent_at"] = utc_now()
            entry = ledger_entry(current, message_id)
            if entry is not None:
                entry["text"] = text
                entry["edited_at_ms"] = stamp
            store.save(state)
    return message_id, stamp, True


def cmd_progress_sink(args):
    """`progress-sink --to <lane> [--message-id <id>] [--news] [--row] [--stamp]` (FR-41802-2): the rendered list on
    stdin; one JSON line back — `message_id`, `edited_at_ms`, `folded`, `progress` (edits | marks | card | none). A card
    as the target is `refused` with exit 3 (not applicable): the watcher learns it once and stops calling."""
    lane = load_lane(args.to)
    target, kind = sink_target(lane, args.message_id)
    fold = lane_can_fold(lane) if target else False
    progress = "none" if not target else "card" if kind == UI_OUTBOUND_KIND else "edits" if fold else "marks"
    entry = ledger_entry(lane, target) if target else None
    stamp = int((entry or {}).get("edited_at_ms") or 0)
    if progress == "none":
        # #41959: no plan post yet — the status file keeps the list; nothing on the wire, no id carried back, so the
        # ACK or a progress reply is never the target. The next call after the plan post edits it.
        if not args.stamp and not sys.stdin.read().strip():
            raise InputError("progress-sink needs the rendered list on stdin")
        print(json.dumps({"message_id": None, "edited_at_ms": 0, "progress": progress, "skipped": "no_plan"}))
        return 0
    if args.stamp:
        print(json.dumps({"message_id": target, "edited_at_ms": stamp, "progress": progress}))
        return 0
    text = sys.stdin.read()
    rows = [line for line in text.split("\n") if line.strip()]
    if not rows:
        raise InputError("progress-sink needs the rendered list on stdin")
    if progress == "card":
        print(json.dumps({"outcome": "refused", "reason": "progress: card", "message_id": target, "edited_at_ms": stamp, "progress": progress,
                          "next": "the plan is a card: update it with reply --replace-last --message-json - yourself"}))
        return EXIT_NOT_APPLICABLE
    if progress == "marks" and not args.news:
        # cannot fold: only the news goes out as a new message, never a start mark or a tick
        print(json.dumps({"message_id": target, "edited_at_ms": stamp, "progress": progress, "skipped": "cannot_fold"}))
        return 0
    current_text = (entry or {}).get("text") or ""
    new_text = apply_list(current_text, rows, single_row=args.row)
    if new_text == current_text:
        print(json.dumps({"message_id": target, "edited_at_ms": stamp, "progress": progress, "skipped": "unchanged"}))
        return 0
    message_id, stamp, folded = sink_write(args.to, lane, target, new_text, fold)
    print(json.dumps({"message_id": message_id, "edited_at_ms": stamp, "folded": folded, "progress": progress,
                      "summary": f"{args.to} · list · {'edited' if folded else 'posted'}"}))
    return 0


def cmd_claim(args):
    """D11: hand a conversation to a coordinator. From this call on its events
    go to the feed — never to the daemon's stream — until `unclaim`.
    `delegate` does this for the daemon; the verb stands alone for recovery."""
    with StateStore() as store:
        state = store.load(require=True)
        checkpoint = state["checkpoint"]
        alias, lane = lane_for_conversation(checkpoint, args.conversation, transport_arg(args))
        claim = apply_claim(checkpoint, alias, lane, getattr(args, "handoff_id", None))
        evict_bounded(checkpoint)
        store.save(state)
    print(json.dumps({
        "status": "claimed",
        "conversation": args.conversation,
        "lane": alias,
        "transport": claim.get("transport"),
        "handoff_id": claim.get("handoff_id"),
    }))
    return 0


def cmd_unclaim(args):
    """Return a conversation to the daemon: its next message wakes the daemon
    again (D20: nothing is replayed)."""
    with StateStore() as store:
        state = store.load(require=True)
        checkpoint = state["checkpoint"]
        alias, lane = lane_for_conversation(checkpoint, args.conversation, transport_arg(args))
        claim = release_claim(checkpoint, lane)
        evict_bounded(checkpoint)
        store.save(state)
    print(json.dumps({
        "status": "unclaimed",
        "conversation": args.conversation,
        "lane": alias,
        "was_claimed": claim is not None,
    }))
    return 0


def whole_inbound_text(checkpoint, item):
    """The text `delegate`'s snapshot carries for one inbound line: the retained
    `full_text` when the compact line cut it at TEXT_BOUND (#30788: the feed
    keeps the bounded `content.text`, so a 4,645-character paste reached the
    coordinator without its last line — the question. The handoff is a file
    the coordinator reads, not a display line, and the starter bounds its own
    quote). Once the retained window has dropped the event the bounded text
    ends with a line that says so — never the compact line's `show` hint,
    which `show` would answer "outside the retained window" (review of
    #30799) — so the cut is never silent and no dead call is offered."""
    envelope = item.get("envelope") or {}
    text = item.get("text") or ""
    if not (envelope.get("content") or {}).get("truncated"):
        return text
    retained = (checkpoint.get("retained_events") or {}).get(item.get("event_id")) or {}
    full_text = retained.get("full_text")
    if isinstance(full_text, str) and full_text:
        return full_text
    return f"{text}\n… truncated; the retained window no longer holds this event"


def conversation_snapshot(checkpoint, state, alias, lane, limit):
    """(entries, watermark): the conversation both ways, oldest first, capped
    to the newest `limit` entries. Inbound comes from the feed (the full
    record; the retained window when a lane predates feeds), outbound from the
    lane's ledger. Each inbound says whether the lane has `answered` it — a
    plain reply (not an interim post) followed it, by time (D20: no ledger) —
    so the starter can quote every message still waiting for an answer
    (#28200). `watermark` is the newest inbound event the snapshot carries, so
    a listener started after it duplicates nothing the coordinator read."""
    route = lane.get("route") or {}
    transport = route.get("transport")
    replied_ms = answered_at_ms(lane)
    inbound = read_feed(transport, lane.get("key"))
    if not inbound:
        for event_id, entry in (checkpoint.get("retained_events") or {}).items():
            envelope = (entry or {}).get("envelope") or {}
            if envelope.get("lane") != alias:
                continue
            actor = envelope.get("actor") or {}
            inbound.append({
                "event_id": event_id,
                "from": actor.get("display") or actor.get("id") or "unknown",
                "text": (envelope.get("content") or {}).get("text") or "",
                "received_at_ms": 0,
                "occurred_at": envelope.get("occurred_at"),
                "envelope": envelope,  # #30643: the attachment lines ride this arm too
            })
    if transport == "mailbox":
        own = (state.get("mailbox") or {}).get("client_mailbox_id")
    else:
        own = ((state.get("connector") or {}).get("identity") or {}).get("bot_user_id")
    ranked = []
    for seq, item in enumerate(inbound):
        text = whole_inbound_text(checkpoint, item)  # #30788: whole, not the display cut
        ranked.append((int(item.get("received_at_ms") or 0), 0, seq, {
            "direction": "inbound",
            "event_id": item.get("event_id"),
            "from": item.get("from"),
            # #30643: the trigger's line is never replayed to the coordinator,
            # so the starter quote carries where each attachment landed (the
            # mailbox arm's line, like the compact line's — D20 item 7).
            # The `context:` row and `[context]` lines ride the same arm: the
            # handoff is where the coordinator reads the whole window the
            # starter only quotes.
            "text": (with_message_lines(text, item.get("envelope") or {})
                     if ((item.get("envelope") or {}).get("container") or {}).get("type") == "mailbox"
                     else text),
            "at": item.get("occurred_at"),
            "answered": replied_ms is not None and replied_ms >= int(item.get("received_at_ms") or 0),
        }))
    for seq, sent in enumerate(lane.get("outbound") or []):
        if sent.get("kind") == UI_OUTBOUND_KIND and not sent.get("text"):
            # FR-35345-3(b): a wordless evicted-arm entry (admitted before #36324,
            # or a late `confirmed` after the deadline arm dropped the words)
            # answers the lane — the coordinator never reads a blank "already sent" line.
            continue
        entry = {
            "direction": "outbound",
            "message_id": sent.get("message_id"),
            "from": own or "connector",
            "text": sent.get("text") or "",
            "sent": True,
            "at": sent.get("sent_at"),
        }
        ranked.append((int(sent.get("sent_at_ms") or 0), 1, seq, entry))
    ranked.sort(key=lambda entry: entry[:3])
    ordered = [entry[3] for entry in ranked]
    if limit is not None:
        # #28206 as read by D20: the limit bounds CONTEXT, never a line still
        # waiting for an answer — a window that cut an older unanswered line
        # would leave it unshown and unserved (the scoped listener starts
        # after the watermark).
        start = len(ordered) - limit
        for index, entry in enumerate(ordered):
            if index >= start:
                break
            if entry["direction"] == "inbound" and not entry.get("answered"):
                start = index
                break
        ordered = ordered[max(start, 0):]
    watermark = None
    for entry in ordered:
        if entry["direction"] == "inbound":
            watermark = entry["event_id"]
    return ordered, watermark


def daemon_registry_helper():
    configured = os.environ.get(DAEMON_REGISTRY_HELPER_ENV)
    if configured:
        return configured
    here = os.path.dirname(os.path.realpath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "daemon", "scripts", "daemon_registry.py"))


def registry_helper_timeout_s(seam_armed):
    """How long `delegate` waits for the registry helper. The override is a
    per-transport test seam (FR-020, as `pending_max`): honored only under the
    caller's own seam, so a leaked value can never shorten a real launch."""
    if seam_armed and os.environ.get("SLACK_CONNECTOR_REGISTRY_TIMEOUT_S"):
        try:
            return max(float(os.environ["SLACK_CONNECTOR_REGISTRY_TIMEOUT_S"]), 0.1)
        except ValueError:
            pass
    return REGISTRY_HELPER_TIMEOUT_S


def recover_registry_row(transport, key, args):
    """D15: before a conversation whose lane died is dispatched again, let the
    daemon registry helper validate (and orphan) its row the way the daemon's
    own `recover` pass would — `launch` refuses an active row over a dead lane.
    Best effort: the launch that follows is what decides."""
    argv = [
        sys.executable or "python3", daemon_registry_helper(), "recover",
        "--connector", f"slack-connector:{transport}", "--conversation", key,
    ]
    if args.daemon_session_id:
        argv += ["--daemon-session-id", args.daemon_session_id]
    if args.daemon_session_name:
        argv += ["--daemon-session-name", args.daemon_session_name]
    try:
        # stdin closed: the helper reads stdin only for `--peers-json -`, which
        # is never passed here, and an inherited open pipe (a daemon under a
        # piped runner) would park the child forever (review).
        run = subprocess.run(argv, text=True, capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        diag(f"daemon_registry recover did not run ({error}); the launch decides")
        return
    for line in run.stderr.splitlines()[-20:]:
        if line.strip():
            diag(f"daemon_registry: {line}")
    if run.returncode != 0:
        diag(f"daemon_registry recover exited {run.returncode}; the launch decides")


SUMMARY_DETAIL_MAX = 80  # the cause's share of the tool row's `└` line (#37181)
RECEIPT_DETAIL_MAX = 300  # the cause's share of the receipt's decisive prefix (#37687)
# #37687: a launch that outlives the exec tool's 10 s foreground yield comes
# back through the background-terminal inbox, whose body cap leaves the
# receipt about 600 characters, so the fields the daemon's one line needs are
# printed first, in this order, and everything else after them.
RECEIPT_LEAD_KEYS = ("outcome", "error", "ack_update", "next", "detail", "summary")


def receipt_line(report):
    """The receipt as one JSON line, the decisive fields first (#37687)."""
    ordered = {key: report[key] for key in RECEIPT_LEAD_KEYS if key in report}
    ordered.update((key, value) for key, value in report.items() if key not in ordered)
    return json.dumps(ordered)


def clip_text(text, limit):
    """`text` whole when it fits `limit`, else its head and one ellipsis."""
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def launch_failure_detail(body):
    """The helper's one-line cause for a failed launch (#37181): its `message`
    with whitespace collapsed, else the `error` code it sent instead."""
    message = body.get("message")
    text = " ".join(str(message).split()) if isinstance(message, str) else ""
    return text or str(body.get("error") or body.get("reason") or "the lane did not start")


def failed_launch_ack_text(detail):
    """The one sentence the requester reads in place of "On it" (#37181):
    plain words, the runtime's cause in brackets, and what to do next. Order
    (audit #38191 C9/P2): the daemon's own `reply` in the requester's language
    is the voice; this fixed English edit is the guarantee behind it — it lands
    whether or not the model's turn sends that reply (`ack_update`)."""
    return (f"I couldn't start a worker for this right now ({detail.rstrip('.')})."
            " Send your message again and I'll retry.")


def edit_own_ack(alias, text, what):
    """Edit the connector's own interim acknowledgement in `alias` to `text`
    through the `--replace-last` machinery (in place on Slack; a relay edit or
    a D8 successor on the mailbox — every arm keeps the entry interim, so the
    lane still reads unanswered). Returns `updated`, or `failed` after one
    stderr line naming what could not be told, when the edit did not go out."""
    try:
        with StateStore() as store:
            lane = ((store.load(require=True).get("checkpoint") or {}).get("lanes") or {}).get(alias)
        if lane is None:
            raise ConnectorError(f"lane {alias} is gone; nothing to edit")
        replace_last_reply(alias, lane, text)
        return "updated"
    except (ConnectorError, OSError, subprocess.SubprocessError, ValueError) as error:
        diag(f"delegate: could not {what}: {error}")
        return "failed"


def update_failed_launch_ack(alias, detail):
    """The interim acknowledgement becomes the failure line (#37181); the
    caller's outcome is already `failed` either way."""
    return edit_own_ack(alias, failed_launch_ack_text(detail), "tell the requester the launch failed")


def cmd_delegate(args):
    """D13: the daemon's whole dispatch in one call — acknowledge to the human
    through the normal reply path, claim the conversation, snapshot both
    directions, and launch the coordinator through the daemon registry helper.
    Prints ONE JSON line and passes the helper's exit code through (0 launched
    or reused, 3 conflict, 6 failed). A failed acknowledgement claims and
    launches nothing; a helper refusal releases the claim this call made."""
    text = args.text or ""
    if not text.strip():
        raise InputError("delegate needs --text: the acknowledgement the human sees")
    limit = args.snapshot_limit
    if limit is None or limit < 0:
        raise InputError("--snapshot-limit must be a non-negative integer")
    with StateStore() as store:
        state = store.load(require=True)
        checkpoint = state["checkpoint"]
        lane = (checkpoint.get("lanes") or {}).get(args.to)
        if lane is None:
            raise ConnectorError(
                f"unknown lane {args.to!r}; every listener line is prefixed with the lane to delegate"
            )
        already_claimed = lane_is_claimed(checkpoint, args.to)
        route = lane.get("route") or {}
        transport = route.get("transport")
        key = lane.get("key")
        # D20: the trigger is the lane's newest inbound line; a lane whose
        # newest line already has a plain reply after it has nothing to hand off.
        trigger, received_at_ms, envelope = newest_inbound(transport, key, checkpoint, args.to)
        # #31985 (ADR 31985 D1): the standing steward. A re-arm of the recorded
        # steward lane (a restarted daemon, the lane gone) needs no new line:
        # the steward's last words were a plain reply. Another lane asking for
        # one while the recorded conversation is still claimed is refused.
        steward = steward_record_for(checkpoint)
        steward_rearm = bool(getattr(args, "steward", False)) and steward is not None and steward.get("lane") == args.to
        steward_elsewhere = (
            steward.get("lane")
            if getattr(args, "steward", False) and steward is not None and steward.get("lane") != args.to
            and claim_for(checkpoint, steward.get("transport"), steward.get("key")) is not None
            else None
        )
        # FR-31985-2(f): a plain dispatch on the recorded steward lane (the D15
        # `[unattended]` re-dispatch) carries the role the human already asked
        # for; the daemon never has to remember the flag. Only the explicit
        # flag skips the unanswered gate below.
        want_steward = bool(getattr(args, "steward", False)) or (steward is not None and steward.get("lane") == args.to)
    if steward_elsewhere is not None and not steward_lane_live(steward):
        # #38187 (ADR 25011 D7 Amendment 1): the recorded steward lane is gone
        # (the human had it ended, or it died) — a fresh arm here is not a
        # second steward; the refusal is for a LIVE one. Probed after the state
        # lock is released: it shells out to the registry (review of #38345).
        steward_elsewhere = None
    if not trigger or (lane_answered(lane, received_at_ms) and not steward_rearm):
        raise InputError(f"delegate: lane {args.to} has no unanswered line to hand off")
    cards = cards_line(state, lane)  # ruling 25: the connect receipt states the lane's card capability
    report = {
        "outcome": None,
        "handoff_id": None,
        "tmux_session": None,
        "backend": None,
        "lane_ref": None,
        "conversation": key,
        "lane": args.to,
        "transport": transport,
        "event_id": trigger,
        "watermark": trigger,
        "ack_message_id": None,
        "muse_session_id": None,
        "cards": cards,
        # #41245: and the lane's reply shape, so the delegated lane inherits the channel style.
        "reply_shape": reply_shape_line(cards, args.to),
    }
    if want_steward:
        report["steward"] = True

    def finish(outcome, code, **extra):
        report["outcome"] = outcome
        report.update(extra)
        # adr:25011#D27 item 2: the helper's `next` rides through unchanged;
        # only an outcome delegate decides without a helper line (already_owned,
        # its own error arms) gets a hint here (guidance, never enforcement — D20).
        if not report.get("next"):
            report["next"] = (
                "nothing to do: a live coordinator serves this lane; say one line and end the turn"
                if outcome == "already_owned"
                else "report this one line to your human and open no lane; never retry blindly"
            )
        # ADR 25011 D22 item 4: the tool row's `└` line — the lane and the
        # handoff, so the daemon narrates nothing after the call (D18).
        # #31985: the lane is named by its backend-qualified `lane_ref` (the
        # tmux session name, so unchanged for tmux lanes; a pane id for Herdr).
        lane_session = report.get("lane_ref") or report.get("tmux_session") or args.to
        if outcome in ("launched", "reused"):
            # #37181: the backend the registry launched in, so a daemon-wide
            # `start --lane-backend` shows on the line (an older helper names none).
            backend_word = f" · {report['backend']}" if report.get("backend") else ""
            report["summary"] = f"lane {lane_session}{backend_word} · handoff {report.get('snapshot_count', 0)} messages"
            if report.get("steward"):
                report["summary"] += " · fleet steward"
            project = report.get("project")
            # The tier echo below mirrors `sizing_words` in the daemon's
            # `daemon_registry.py` by hand (that helper runs as a subprocess,
            # so it cannot be imported): change both.
            if isinstance(project, dict):
                # #38715 PR 6: `project <slug>`, or the refusal the daemon must say
                if project.get("outcome") == "created":
                    report["summary"] += f" · project {project.get('slug')}"
                else:
                    why = project.get("reason") or project.get("error") or "refused"
                    report["summary"] += f" · project {project.get('outcome') or 'refused'} ({why})"
            elif isinstance(report.get("sizing"), dict) and report["sizing"].get("tier") == "thread":
                # The thread side of the same echo: the gate was open (or a
                # delegation recorded) and this hand-off stayed a thread.
                why = f"agents gate {report['sizing'].get('agents_gate')}"
                if report["sizing"].get("delegation") not in (None, "auto"):
                    why += f", delegation {report['sizing']['delegation']}"
                report["summary"] += f" · sized thread ({why})"
        elif outcome == "already_owned":
            report["summary"] = f"lane {lane_session} · already owned"
        else:
            report["summary"] = f"{args.to} · {outcome}" + (f" · {report['error']}" if report.get("error") else "")
            if report.get("detail"):
                report["summary"] += f" · {clip_text(report['detail'], SUMMARY_DETAIL_MAX)}"
        if report.get("repeat"):
            report["summary"] += " · repeat"  # #29739: the same dispatch answered again
        print(receipt_line(report), flush=True)
        return code

    if want_steward:
        # The mechanics are the project skill's (spec 25011 FR-31985-4/-7):
        # a workspace without it gets a refusal here, never an ordinary
        # coordinator that cannot do what was asked.
        skill_path = os.path.join(args.workspace or os.getcwd(), ".agents", "skills", "fleet-steward", "SKILL.md")
        if not os.path.isfile(skill_path):
            return finish(
                "steward_skill_missing", 6, error=f"no fleet-steward skill at {skill_path}",
                next="tell them this workspace has no fleet-steward skill (a project skill under"
                     " .agents/skills), so no steward can run here; open no lane",
            )
        if steward_elsewhere is not None:
            return finish(
                "steward_exists", 3, error=f"lane {steward_elsewhere} already keeps this daemon's fleet steward",
                # #38187: name the two human-named paths, never a bare no — the
                # daemon relays this line as the requester's answer.
                next=f"tell them the fleet steward already runs in lane {steward_elsewhere}: to stop it, say"
                     " 'stop the fleet steward' there; to restart it there, ask there; to move it here ('kill the"
                     " fleet watcher and start one here' names it) you end that exact lane now — kill it, mark its"
                     " row retired — and run this delegate again; never a second steward beside a live one",
            )
    if already_claimed:
        # D15: a claimed conversation is its coordinator's only while that lane
        # lives. Alive → nothing happens here. Dead → the registry row is
        # recovered, the stale claim released, and the dispatch runs afresh.
        # #31985 (adr:31985#D7): the registry judges liveness through the
        # lane's recorded backend (`lookup --live`); the connector's own tmux
        # probe is the fallback only for a claim that names a tmux lane. A
        # Herdr lane the registry cannot judge is unknown, never dead — but a
        # registry that holds NO row for a Herdr claim is definitive: nobody
        # owns it, so the claim is stale and the dispatch runs afresh. A tmux
        # or legacy claim keeps its own tmux probe below (D29 item 4).
        claim = claim_for(checkpoint, transport, key) or {}
        backend = claim_backend(claim)
        lane_ref = claim_lane_ref(claim, args.to)
        owner_session = claim_tmux_session(claim, args.to) if backend == "tmux" else None
        owner = {"tmux_session": owner_session, "backend": backend, "lane_ref": lane_ref}
        answer = registry_lookup(transport, key, live=True)
        live = None
        if answer != REGISTRY_LOOKUP_FAILED:
            live = answer["live"]
            if answer["row"] is None and backend != "tmux":
                live = False  # `not_found`; a tmux claim keeps its legacy probe below
        if not isinstance(live, bool):
            if backend != "tmux":
                return finish(
                    "owner_unknown", 6, handoff_id=claim.get("handoff_id"), **owner,
                    reason=f"the daemon registry cannot tell whether {backend} lane {lane_ref} is alive; claim kept",
                    next="run `daemon_registry.py recover` to reconcile the lane, then `delegate` again;"
                         " or `unclaim` to hand the conversation back — open no lane yourself",
                )
            try:
                live = tmux_session_is_live(owner_session)
            except (OSError, subprocess.TimeoutExpired) as error:
                return finish("failed", 6, error=f"tmux unavailable; cannot tell whether {owner_session} is alive: {error}")
        if live:
            receipt = dispatch_receipt(claim)
            if receipt is not None:
                # #29739: the same dispatch again (the line was drained after
                # the first result, or landed after the claim and went to the
                # coordinator's feed) — the recorded receipt, so the daemon's
                # one line is the same one line.
                report.update(receipt)
                return finish(receipt.get("outcome") or "launched", 0, repeat=True)
            return finish(
                "already_owned", 0, conversation=key, lane=args.to,
                handoff_id=claim.get("handoff_id"), **owner,
            )
        recover_registry_row(transport, key, args)
        with StateStore() as store:
            state = store.load(require=True)
            checkpoint = state["checkpoint"]
            current = (checkpoint.get("lanes") or {}).get(args.to)
            if current is not None:
                release_claim(checkpoint, current)
                store.save(state)
        already_claimed = False

    # (a) The acknowledgement rides the reply path: same key derivation (D18
    # item 3, scoped to the trigger) and is recorded interim, so a retry
    # resends nothing and the lane still reads unanswered.
    idempotency_key = reply_idempotency_key(key, text, trigger)
    try:
        if transport == "mailbox":
            receipt = mailbox_reply(route, idempotency_key, text)
            ack_id = receipt.get("message_id")
            record_last_outbound(
                args.to, route.get("container_id") or route.get("target_client_mailbox_id"),
                ack_id, text=text, interim=True,
            )
        else:
            receipt = slack_reply(route, idempotency_key, text)
            ack_id = receipt.get("remote_message_id")
            record_last_outbound(args.to, route.get("container_id"), ack_id, text=text, interim=True)
    except ConnectorError as error:
        return finish("error", EXIT_INPUT if isinstance(error, InputError) else EXIT_ERROR, error=str(error))
    report["ack_message_id"] = ack_id

    # (b) claim + (c) snapshot under one lock: nothing admitted after this point
    # reaches the daemon, and the snapshot ends where the feed does.
    with StateStore() as store:
        state = store.load(require=True)
        checkpoint = state["checkpoint"]
        lane = (checkpoint.get("lanes") or {}).get(args.to) or lane
        claim = apply_claim(checkpoint, args.to, lane, None)
        claim["launching"] = True  # #28181: cleared when the launch returns or times out
        claim.pop("receipt", None)  # #29739: written again when this launch returns
        previous_steward = checkpoint.get("steward")
        if want_steward:
            checkpoint["steward"] = steward_record(args.to, lane, trigger, envelope)
        entries, watermark = conversation_snapshot(checkpoint, state, args.to, lane, limit)
        evict_bounded(checkpoint)
        store.save(state)
    report["watermark"] = watermark or trigger
    snapshot_text = "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries)
    report["snapshot_count"] = len(entries)  # ADR 25011 D22 item 4: the `└ handoff N messages` fact

    def rollback():
        if already_claimed:
            return
        with StateStore() as store:
            state = store.load(require=True)
            checkpoint = state["checkpoint"]
            current = (checkpoint.get("lanes") or {}).get(args.to)
            if current is not None:
                release_claim(checkpoint, current)
            if want_steward:
                # The record follows the claim: a launch that never happened
                # armed nothing (the earlier record, if any, stands again).
                if previous_steward is None:
                    checkpoint.pop("steward", None)
                else:
                    checkpoint["steward"] = previous_steward
            store.save(state)

    def clear_launching():
        # #28181: the claim is kept, but it is judged by its stamp again.
        with StateStore() as store:
            state = store.load(require=True)
            claim = claim_for(state["checkpoint"], transport, key)
            if claim is not None and claim.pop("launching", None) is not None:
                store.save(state)

    # (d) the launch, through the daemon skill's registry helper. #30542: the
    # ref carries the lane's `requester` and `thread` facts when it has them,
    # so the starter can name the person and cite the thread.
    conversation_ref = dict(route, key=key)
    for fact in ("requester", "thread"):
        if lane.get(fact):
            conversation_ref[fact] = lane[fact]
    helper = daemon_registry_helper()
    argv = [
        sys.executable or "python3", helper, "launch",
        "--connector", f"slack-connector:{transport}",
        "--conversation", key,
        "--lane", args.to,
        "--conversation-ref", json.dumps(conversation_ref, separators=(",", ":")),
        # ADR 37480 D1 rule 1: the daemon compares these by bytes only, so
        # they leave here in this connector's one canonical rendering.
        "--event-id", canonical_event_id(trigger),
        "--watermark", canonical_event_id(report["watermark"]),
        "--ack-posted", "yes",
        "--progress-reply-id", str(ack_id),
        "--workspace", args.workspace or os.getcwd(),
        "--connector-script", os.path.realpath(__file__),
        "--snapshot-file", "-",
    ]
    # D11-D13: the coordinator never addresses the daemon, so the daemon's own
    # session id is provenance only — passed through when given, never required.
    if args.daemon_session_id:
        argv += ["--daemon-session-id", args.daemon_session_id]
    if args.daemon_session_name:
        argv += ["--daemon-session-name", args.daemon_session_name]
    if want_steward:
        argv.append("--steward")  # the handoff's `role` and the starter's one role line
    if getattr(args, "lane_backend", None):
        argv += ["--backend", args.lane_backend]  # #38187: this one dispatch's backend
    if getattr(args, "project", False):
        argv.append("--project")  # #38715 PR 6: the daemon sized this ask as a project (spec 23499 FR-38715-64)
    if args.muse_bin:
        argv += ["--muse-bin", args.muse_bin]
    elif os.environ.get(MUSE_BIN_ENV):
        argv += ["--muse-bin", os.environ[MUSE_BIN_ENV]]
    for extra in args.muse_arg or []:
        # One token per arg: split in two, a value that starts with `--` (the
        # daemon's default `--muse-arg=--yolo`) reads as an option to the
        # helper's argparse and every dispatch fails `usage`.
        argv.append(f"--muse-arg={extra}")
    try:
        run = subprocess.run(
            argv, input=snapshot_text, text=True, capture_output=True,
            timeout=registry_helper_timeout_s(mailbox_seams_enabled() if transport == "mailbox" else test_seams_enabled()),
        )
    except FileNotFoundError:
        rollback()
        return finish("error", EXIT_ERROR, error=f"daemon registry helper not found: {helper}")
    except subprocess.TimeoutExpired:
        # Unknown outcome, not a refusal (review): the helper starts the tmux
        # lane before it polls liveness, so the coordinator may be running.
        # Releasing the claim here would wake the daemon for a conversation a
        # coordinator already tails — two responders. Keep it; a lane that is in
        # fact dead comes back through the D15 unattended path or `recover`.
        clear_launching()
        return finish(
            "failed", 6,
            error="daemon registry helper timed out; claim kept (the coordinator may be running) — run"
                  " `daemon_registry.py recover` to reconcile the lane, or `unclaim` to hand the conversation back",
        )
    for line in run.stderr.splitlines()[-20:]:
        if line.strip():
            diag(f"daemon_registry: {line}")
    body = {}
    for line in reversed(run.stdout.splitlines()):
        if line.strip().startswith("{"):
            try:
                body = json.loads(line)
            except ValueError:
                body = {}
            break
    extra = {
        "handoff_id": body.get("handoff_id"),
        "tmux_session": body.get("tmux_session"),
        # #31985: the lane's backend-qualified location; an older helper
        # answers neither, and the claim then reads as a tmux lane.
        "backend": body.get("backend"),
        "lane_ref": body.get("lane_ref"),
    }
    if body.get("handoff_path"):
        extra["handoff_path"] = body["handoff_path"]
    if isinstance(body.get("project"), dict):
        # #38715 PR 6: the helper's project line (created / skipped / failed)
        # rides the receipt so the daemon's one line names the slug or the why.
        extra["project"] = body["project"]
    if isinstance(body.get("sizing"), dict):
        # #38715 (daemon audit PR-B): the tier the helper took and why, when it
        # was a choice (open `agents` gate or a recorded delegation).
        extra["sizing"] = body["sizing"]
    if isinstance(body.get("lane_settings"), dict):
        # #38715 QA round 10 (D-R10-DM-2): the launch facts the daemon reads
        # (gates, engine args, their source) - the daemon only ever sees this receipt.
        extra["lane_settings"] = body["lane_settings"]
    if isinstance(body.get("agents_gate"), str):
        # Owner ruling 2026-09-20 (c): `in lane` / `absent in lane` on a created
        # project; the helper's `next` (forwarded below) says the launch defect.
        extra["agents_gate"] = body["agents_gate"]
    if isinstance(body.get("attach"), str) and body["attach"].strip():
        # Owner ruling 28 (#38715, 2026-09-22): how a person sits in front of
        # the lane (the runtime's attach command, relayed by the helper; a tmux
        # lane always, a Herdr pane when its receipt has one). Owner ruling 48
        # (2026-09-23): operator detail — it rides this receipt and the
        # daemon's own TUI line only; the requester's acknowledgement is never
        # edited to carry it (one channel message, no successor). An older
        # helper names none and the receipt and the line read as before.
        extra["attach"] = body["attach"].strip()
    # adr:25011#D27 item 2: the helper's `next` hint is the daemon's one line.
    if isinstance(body.get("next"), str) and body["next"].strip():
        extra["next"] = body["next"]
    if run.returncode == 0:
        outcome = body.get("outcome") or "launched"
        if body.get("handoff_id"):
            with StateStore() as store:
                state = store.load(require=True)
                checkpoint = state["checkpoint"]
                current = (checkpoint.get("lanes") or {}).get(args.to)
                if current is not None:
                    claim = apply_claim(
                        checkpoint, args.to, current, body["handoff_id"], tmux_session=body.get("tmux_session"),
                        backend=body.get("backend"), lane_ref=body.get("lane_ref"),
                    )
                    # #28181: the D15 grace runs from the moment the lane exists,
                    # not from the claim stamped before a boot that may outlast it.
                    claim["claimed_at"] = utc_now_precise()
                    claim.pop("launching", None)
                    # #29739: the receipt this call prints, kept for a repeat of
                    # the same dispatch (`dispatch_receipt`).
                    claim["receipt"] = dict(report, outcome=outcome, **extra)
                    store.save(state)
        return finish(outcome, 0, **extra)
    rollback()
    outcome = body.get("outcome") or {3: "conflict", 6: "failed"}.get(run.returncode, "failed")
    error = body.get("error") or body.get("reason")
    if error:
        extra["error"] = error
    if outcome != "conflict":
        # #37181 (spec 23499 FR-37181-1): the requester was told "On it" and
        # would otherwise hear nothing more. Any non-zero helper answer but a
        # conflict (`failed`, a usage error, an evidence refusal — no lane
        # exists either way) edits the connector's OWN acknowledgement into
        # one plain failure line (still interim, so the lane reads unanswered
        # and the next message re-dispatches), and the receipt carries the
        # helper's cause as `detail`. A failed edit changes the receipt
        # (`ack_update`), never the outcome. #37687: the requester's line
        # carries the whole cause; the receipt's `detail` is bounded so the
        # decisive prefix survives the background inbox cut. `next` stays the
        # helper's (adr:25011#D27 item 2): its `launch_failed` hint says what
        # the orphaned row means for the next inbound line, and `ack_update`
        # right before it says whether the requester already reads the failure.
        detail = launch_failure_detail(body)
        extra["detail"] = clip_text(detail, RECEIPT_DETAIL_MAX)
        extra["ack_update"] = update_failed_launch_ack(args.to, detail)
    return finish(outcome, run.returncode or EXIT_ERROR, **extra)


def cmd_steward(args):
    """#31985: the standing fleet-steward record `delegate --steward` writes.
    `status` prints it (null when none); `disarm` forgets it - the lane keeps
    its conversation as an ordinary coordinator, and only a human's next ask
    arms one again. Neither touches a claim, a lane or the registry."""
    with StateStore() as store:
        state = store.load(require=True)
        checkpoint = state["checkpoint"]
        record = steward_record_for(checkpoint)
        if args.action == "disarm":
            checkpoint.pop("steward", None)
            store.save(state)
            lane = (record or {}).get("lane")
            print(json.dumps({
                "outcome": "disarmed", "was_armed": record is not None, "lane": lane,
                "summary": f"fleet steward · {lane} disarmed" if record else "fleet steward · none armed",
            }))
            return 0
        status = steward_status(checkpoint)
    print(json.dumps({
        "outcome": "steward", "steward": status,
        "summary": f"fleet steward · {status['lane']}" if status else "fleet steward · none armed",
    }))
    return 0


def ui_status_fields(checkpoint, alias):
    """The lane row's `presentation` (lane F's live-card reader) and
    `ui_pending` (operations still awaiting the relay). A copy of this script
    without `slack_ui.py` that meets UI state another copy wrote publishes
    both as null with one diag instead of failing `status` (Constitution XIII)."""
    ui = checkpoint.get("ui") or {}
    operations = [op for op in (ui.get("operations") or {}).values() if op.get("lane") == alias]
    try:
        return {
            "presentation": lane_presentation(ui_tables(checkpoint), alias),
            "ui_pending": sum(1 for op in operations if ui_stage_open(op.get("stage"))),
        }
    except ConnectorError as error:
        diag(f"status: lane {alias} has interactive-card state this copy cannot read ({error}); "
             "presentation and ui_pending are null")
        return {"presentation": None, "ui_pending": None}


def status_lanes(checkpoint, state=None):
    """The lane table `status --json` publishes (pre-cutover ledger D4 as
    amended by D24, now `adr:23499-slack-connector-runtime-contract#D8`). Deleting
    `conversations` left the DAEMON — which never reads the listener's compact
    lines — with no way to recover a lane's conversation key for its claim
    ledger, or to know whether `--replace-last` will work there. Both live here,
    off the model's hot path: the model replies by alias and never calls
    `status` at all.

    `can_edit` says the LANE accepts an edit (`adr:23499-slack-connector-runtime-contract#D8`), not which
    mechanism serves it: Slack rewrites in place via `chat.update`, the mailbox
    posts a plain successor whose relationship rides only in the reply receipt.
    The earlier "only Slack can edit" reading is the retired `adr:23499-slack-connector-runtime-contract#D15`."""
    return [
        {
            "alias": alias,
            "key": lane.get("key"),
            "transport": (lane.get("route") or {}).get("transport"),
            # `adr:23499-slack-connector-runtime-contract#D8`: both transports can express an edit — Slack by
            # `chat.update`, the mailbox by a plain successor. The flag says the
            # LANE can be edited, not which mechanism does it; `folded` on the
            # reply receipt says whether the connector rewrote in place.
            "can_edit": bool((lane.get("route") or {}).get("transport")),
            "last_seen": lane.get("last_seen"),
            # #27816 D11: a claimed conversation belongs to a coordinator.
            "claimed": lane_is_claimed(checkpoint, alias),
            # D15: whether that coordinator's scoped listener holds the
            # conversation lock right now, and (#28432) whether the holder
            # runs under the Monitor tool — null with no holder or no verdict.
            "listener_alive": probe["alive"],
            "listener_under_monitor": probe["under_monitor"],
            # #30542: who asked and which thread, from the relay's context
            # block (presentation, relay-asserted); null until an event says.
            "requester": lane.get("requester"),
            "thread": lane.get("thread"),
            # Ruling 25 (#38715): the lane's card capability, the value every
            # reply line carries (`cards_line`).
            "cards": cards_line(state, lane),
            # #35345: the lane's live interactive card (the six FR-35345-6
            # members) from `checkpoint.ui.presentations`, or null.
            **ui_status_fields(checkpoint, alias),
        }
        for alias, lane, probe in (
            (alias, lane, scoped_listener_probe((lane.get("route") or {}).get("transport"), lane.get("key")))
            for alias, lane in sorted((checkpoint.get("lanes") or {}).items(), key=lambda item: lane_sort_key(item[0]))
        )
    ]


def cmd_status(_args):
    with StateStore() as store:
        # #30502: a COLD state answers too. The daemon's `start` reads this verb
        # before the first `listen` to learn the id the bare arm will register,
        # and the mailbox needs no `auth`; every field is simply empty.
        state = store.load() or {"schema_version": SCHEMA_VERSION}
    connector = state.get("connector") or {}
    checkpoint = state.get("checkpoint") or fresh_checkpoint("0")
    binding = state.get("binding") or {}
    try:
        _, token_source = resolve_token(state)
    except ConnectorError:
        token_source = None
    mailbox = state.get("mailbox") or {}
    # #28176: whether each transport's ONE unscoped listener is live (the lease
    # it holds), so the daemon's `start` can say what to arm and a live
    # transport is never armed twice.
    listeners = {t: transport_listener(t) for t in TRANSPORT_LISTENER_TRANSPORTS}
    # #30502: the id the mailbox listener holds or a bare `listen` will attach —
    # the persisted id first, else the derived default, the precedence `listen`
    # itself applies — so `start` can name it before the arm and the bare
    # `/daemon` connect announces the id its human picks in Slack.
    listeners["mailbox"]["mailbox_id"] = mailbox.get("client_mailbox_id") or derive_mailbox_id()
    # #41206 (owner ruling 41): the durable row text the daemon shows —
    # `connected`, `reconnecting since <t> (attempt n, last error: <e>, next
    # try in Ns)` while the LIVE listener is on its ladder, `stopped:
    # <reason>` after an end — on the record the daemon reads; a dead
    # listener's leftover ladder record is not a row.
    row = mailbox_listener_row(mailbox, listeners["mailbox"])
    if row is not None:
        listeners["mailbox"]["row"] = row
    if row == "stopped: disconnected" and isinstance(mailbox.get("disconnected_at"), str):
        listeners["mailbox"]["disconnected_at"] = mailbox["disconnected_at"]  # r22 SR-DAEMON R-5
    if listeners["mailbox"]["listener"] == "live" and isinstance(mailbox.get("reconnecting"), dict):
        listeners["mailbox"]["reconnecting_since"] = mailbox["reconnecting"].get("since")
    print(
        json.dumps(
            {
                "connector_id": CONNECTOR_ID,
                "connector_version": CONNECTOR_VERSION,
                "protocol_version": PROTOCOL_VERSION,
                "schema_version": state["schema_version"],
                "token_source": token_source,
                "identity": connector.get("identity"),
                "scopes": connector.get("scopes"),
                "validated_at": connector.get("validated_at"),
                "binding": {
                    "id": binding.get("id"),
                    "container_id": binding.get("container_id"),
                    "container_type": binding.get("container_type"),
                },
                "cursor": checkpoint.get("cursor"),
                # D13 derives the mailbox id (persisted →
                # `daemon-<unixname>-<host>-1`) instead of taking it from the
                # caller, so publishing it here is the only way a human learns
                # which id peers should address once a fallback fires.
                "mailbox": {
                    "client_mailbox_id": mailbox.get("client_mailbox_id"),
                    "connected": bool(mailbox.get("connected")),
                    # #37011: the mailbox listener's own heartbeat and, when
                    # it says this host's session was active within the
                    # self-held window, the one verdict `start` formats.
                    "last_poll_at": mailbox.get("last_poll_at"),
                    "recent_binding": recent_mailbox_binding(mailbox),
                    # #41206: set while the live listener re-attaches after a
                    # stream death (`{"since", "attempt", "last_error", "next_try_s"}`).
                    "reconnecting": mailbox.get("reconnecting"),
                },
                "lanes": status_lanes(checkpoint, state),
                # #31985: the one standing fleet steward, null unless a human
                # asked for one (`delegate --steward`); `start` reports it.
                "steward": steward_status(checkpoint),
                "listeners": listeners,
                "tracked_thread_count": len(checkpoint.get("tracked_threads") or {}),
                "last_poll_at": checkpoint.get("last_poll_at"),
                # ADR 37480 D1: the declaration the daemon's generic starter reads.
                "reference": connector_reference_path(),
                "env_pass": list(LANE_ENV_PASS),
                "capabilities": {f"slack-connector:{t}": dict(TRANSPORT_CAPABILITIES[t]) for t in TRANSPORT_LISTENER_TRANSPORTS},
            }
        )
    )
    return 0


def cmd_disconnect(args):
    """Tear down the connection the connector owns (stop), SCOPED to ONE transport
    (round-3 finding): `--transport mailbox` downs only the
    mailbox flag, `--transport slack` only the slack (connector) flag. Downing
    both would silently
    stop the other, still-live transport (and leave `connector.connected=False`
    after a mailbox-only session, contradicting FR-002b). Sets the down flag so a
    `listen` under a persistent Monitor exits cleanly. Best-effort; safe to call
    when never connected."""
    # required=True at the parser; read directly so a missing transport fails
    # loud, never a silent mailbox default. Both aliases are accepted here too.
    transport = canonical_transport(args.transport)
    with StateStore() as store:
        state = store.load()
        if state:
            if transport == "mailbox":
                mailbox = state.get("mailbox")
                if mailbox:
                    mailbox["connected"] = False
                    # r22 SR-DAEMON R-5: a human's stop, stamped so the daemon's
                    # `start` can tell it from a failure and leave it stopped
                    # across a restart; the next `listen` clears it.
                    mailbox["disconnected_at"] = utc_now()
                    state["mailbox"] = mailbox
            else:  # slack
                state.setdefault("connector", {})["connected"] = False
            store.save(state)
    print(json.dumps({"status": "disconnected", "transport": transport}))
    return 0


def main(argv=None):
    """Ten verbs: the nine of FR-001 — six on the model's hot path `listen`,
    `reply`, `show`; `auth`, `status`, `disconnect` off it (`ack` retired by
    `adr:23499-slack-connector-runtime-contract#D18`) — plus the two-layer
    daemon's three (#27816,
    `adr:25011-daemon-session-coordination#D11-D13`): `delegate` (the daemon's
    one dispatch call), `claim` and `unclaim` (its recovery pair) — plus
    `steward` (#31985, ADR 31985 D1, FR-31985-2(d)) and `progress-sink`
    (#41802, FR-41802-2: the channel end of the agents watcher), with
    `listen --conversation` for the coordinator's scoped Monitor. `bind`,
    `connect`, `conversations`, `send`, `respond`, `update`, `react`, `fetch`,
    `upload`, and `describe` are gone — folded in or deleted outright."""
    parser = argparse.ArgumentParser(prog="slack_connector", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    auth = subparsers.add_parser("auth")
    auth.add_argument("--token-stdin", action="store_true")
    listen_parser = subparsers.add_parser("listen")
    # D7: the start flags live on `listen` because `listen` IS the start verb.
    listen_parser.add_argument("--channel", default=None)
    listen_parser.add_argument("--owner", default=None)
    listen_parser.add_argument("--thread", default=None)
    listen_parser.add_argument("--only-owner", action="store_true")
    listen_parser.add_argument("--no-auto-react", action="store_true")
    # D13: no parser default — `resolve_listen_transport` picks it, so a bare
    # `listen` starts the token-less mailbox rather than an OAuth Slack poll.
    # One transport, one name in the caller's hands: `listen` and `disconnect`
    # accept the SAME words. Before this, a Slack user started with
    # `--transport poll` and had to stop with `--transport slack`, and the D7
    # record's own example (`listen --transport slack`) was an argparse error.
    # `slack` is the canonical word (see `canonical_transport`); `poll` is its accepted alias.
    listen_parser.add_argument(
        "--transport", default=None, choices=["poll", "slack", "mailbox"]
    )
    listen_parser.add_argument("--mailbox-id", default=None)
    listen_parser.add_argument(
        "--daemon-skill",
        action="store_true",
        help="Publish agent and daemon-skill discovery tags on this mailbox.",
    )
    listen_parser.add_argument("--session-name-hint", default=None)
    listen_parser.add_argument("--workspace-hint", default=None)
    # #27816 D12: a coordinator's scoped listener — one conversation, strictly
    # after the handoff watermark, same line shape as the unscoped stream.
    listen_parser.add_argument("--conversation", default=None, metavar="KEY")
    listen_parser.add_argument("--cursor", default=None, metavar="EVENT_ID")
    listen_parser.add_argument("--once", action="store_true")
    # D15: how old a claim must be before a conversation nobody tails wakes the
    # unscoped listener again (default UNATTENDED_GRACE_S_DEFAULT).
    listen_parser.add_argument("--unattended-grace", type=float, default=None, metavar="SECONDS")
    # FR-28175-1 (as narrowed by ADR 25011 D20): a post that rides the scoped arm.
    listen_parser.add_argument("--say", default=None, metavar="TEXT")
    # ADR 25011 D22: native delivery — the session that owns this listener.
    listen_parser.add_argument("--deliver-to", default=None, metavar="SESSION")
    listen_parser.add_argument("--muse-bin", default=None, metavar="PATH", dest="muse_bin_listen")
    reply = subparsers.add_parser("reply")
    reply.add_argument("--to", required=True, metavar="LANE")
    content = reply.add_mutually_exclusive_group()
    # `-` reads the text from stdin (#37018), like `--message-json -` below.
    content.add_argument("--text", default=None, metavar="TEXT|-")
    # #35345 (ADR 35345 D6/D14): one Slack-shaped `{"text", "blocks", …}` object;
    # `-` reads it from stdin, any other value is the JSON text itself.
    content.add_argument("--message-json", default=None, metavar="JSON|-", dest="message_json")
    reply.add_argument("--replace-last", action="store_true")
    reply.add_argument("--key", default=None)
    # D20 item 6: files ride the mailbox only, behind the `attach` capability.
    reply.add_argument("--attach", action="append", default=[], metavar="PATH")
    show = subparsers.add_parser("show")
    show.add_argument("--event-id", required=True)
    show.add_argument("--json", action="store_true", required=True)
    subparsers.add_parser("status").add_argument("--json", action="store_true", required=True)
    # `--transport` is REQUIRED — no silent default. Both verbs now take the
    # SAME three choices, so the rule stands on BLAST RADIUS alone: a bare
    # `disconnect` used to down BOTH transports, and a wrong default there
    # silently stops the transport a human is debugging, where a wrong `listen`
    # default only costs a restart.
    disconnect_p = subparsers.add_parser("disconnect")
    disconnect_p.add_argument(
        "--transport", required=True, choices=["slack", "poll", "mailbox"]
    )
    # #27816 D11/D13: the two-layer daemon's verbs.
    claim_p = subparsers.add_parser("claim")
    claim_p.add_argument("--conversation", required=True, metavar="KEY")
    claim_p.add_argument("--handoff-id", default=None)
    claim_p.add_argument("--transport", default=None, choices=["slack", "poll", "mailbox"])
    unclaim_p = subparsers.add_parser("unclaim")
    unclaim_p.add_argument("--conversation", required=True, metavar="KEY")
    unclaim_p.add_argument("--transport", default=None, choices=["slack", "poll", "mailbox"])
    delegate_p = subparsers.add_parser("delegate")
    delegate_p.add_argument("--to", required=True, metavar="LANE")
    delegate_p.add_argument("--text", required=True)
    delegate_p.add_argument("--daemon-session-id", default=None)
    # #28180: optional — `delegate` runs as the daemon's child, so its working
    # directory IS the daemon's workspace; the flag is for a human-named one.
    delegate_p.add_argument("--workspace", default=None)
    delegate_p.add_argument("--daemon-session-name", default=None)
    delegate_p.add_argument("--muse-bin", default=None)
    delegate_p.add_argument("--muse-arg", action="append", default=[])
    delegate_p.add_argument("--snapshot-limit", type=int, default=SNAPSHOT_LIMIT_DEFAULT)
    # #31985 (ADR 31985 D1): the standing fleet steward - only when the human
    # asked for one in this conversation; never a default.
    delegate_p.add_argument("--steward", action="store_true")
    # #38187 (ADR 25011 D7 Amendment 1): a daemon that cannot reach a named
    # Herdr target hands the named action to a coordinator launched where it
    # can; forwarded as the registry's existing `launch --backend`. Absent, the
    # daemon-wide record, else the launching context, decides as before.
    delegate_p.add_argument("--lane-backend", choices=("tmux", "herdr"), default=None)
    # #38715 PR 6 (spec 23499 FR-38715-64): the daemon sized this ask as a
    # project; forwarded as the registry's `launch --project`, which decides
    # (gate, `set delegation`, the agents helper) and answers `project`.
    delegate_p.add_argument("--project", action="store_true")
    steward_p = subparsers.add_parser("steward")
    steward_p.add_argument("action", choices=("status", "disarm"))
    # #41802 (FR-41802-2): the channel end of the agents watcher.
    sink_p = subparsers.add_parser("progress-sink")
    sink_p.add_argument("--to", required=True, metavar="LANE")
    sink_p.add_argument("--message-id", default=None, metavar="ID", dest="message_id")
    sink_p.add_argument("--news", action="store_true")
    sink_p.add_argument("--row", action="store_true")
    sink_p.add_argument("--stamp", action="store_true")
    args = parser.parse_args(argv)

    handlers = {
        "auth": cmd_auth,
        "listen": cmd_listen,
        "reply": cmd_reply,
        "show": cmd_show,
        "status": cmd_status,
        "disconnect": cmd_disconnect,
        "claim": cmd_claim,
        "unclaim": cmd_unclaim,
        "delegate": cmd_delegate,
        "steward": cmd_steward,
        "progress-sink": cmd_progress_sink,
    }
    try:
        code = handlers[args.command](args)
    except InputError as error:
        diag(str(error))
        code = EXIT_INPUT
    except ConnectorError as error:
        diag(str(error))
        code = EXIT_ERROR
    except KeyboardInterrupt:
        return 130  # a Ctrl-C is a stop, like SIGTERM: no listener end is recorded
    except Exception as error:  # INV-3: a traceback could embed header/token text
        if test_seams_enabled() and os.environ.get("SLACK_CONNECTOR_DEBUG"):
            raise  # test-only: surface the real traceback under the fake server
        diag(f"unexpected {error.__class__.__name__}; failing closed")
        code = EXIT_ERROR
    note_listener_end(code)  # the unscoped listener's end, for `status --json`
    return code


if __name__ == "__main__":
    sys.exit(main())
