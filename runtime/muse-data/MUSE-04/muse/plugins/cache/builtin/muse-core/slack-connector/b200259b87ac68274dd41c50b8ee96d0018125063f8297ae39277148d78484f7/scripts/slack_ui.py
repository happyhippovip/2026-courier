"""Pure contract helpers for the connector's `custom.slack.ui` version 1 arm.

Owning issue #35345; authority `docs/adr/35345-slack-native-interactive-agent-
controls.md` D6 (one Slack-shaped message object), D9 (bounded connector
state), D12 (result matrix), D13 (local validation depth), D14 (the four
optional post members). Owning spec 23499 FR-35345-1/-3/-4/-5/-6.

What lives here: admission of the `--message-json` object, the request
envelope the relay expects, result / event decoding, the D12 disposition
matrix, and the D9 record transitions. Everything is a pure function of its
arguments: no I/O, no network, no clock, standard library only (ADR 23499
D1). The connector script imports this module from its own directory. What
does not live here (D13): Block Kit grammar; the relay validates the 17 block
families and 23 action types.

Bounds and their sources (spec parameters for FR-35345-5), read from the
vendored snapshot `crates/plugins/core-skill-tests/slack-connector/schemas/`
(release `2026-09-13-python-msp-ui-8f78e4a-v1`), which is never loaded here
(D2):

- UI_REQUEST_MAX_BYTES 16384 (FR-35345-5 step 5): the escaped compact
  serialization of the COMPLETE envelope must fit the mailbox provider's
  opaque-payload bound (`CLIENT_PAYLOAD_MAX_BYTES`, verified live on
  `muse-mailbox send`); the relay's `max_request_bytes` 65536 is looser and
  never reached. Admission pre-checks the bare object against the same
  number; the builder checks the whole request.
- UI_MAX_JSON_DEPTH 16 = `x-musetag-limits.max_json_depth`, measured on the
  COMPLETE envelope (FR-35345-5 step 3): admission wraps the object in the
  same `{version,to_role,body:{name,version,payload}}` shape it will be sent
  in and measures that.
- UI_MAX_BLOCKS 49 = `$defs.blocks.maxItems` (Slack allows 50; the relay keeps
  one block for its expiry status). MAX_EXPIRES_IN_SECONDS 604800, MAX_CONVERSATION_ID_CHARS 4096,
  MAX_UI_ID_CHARS 64 = the matching maxLength / maximum in `$defs.post` and
  `$defs.update`.
- UI_RESULT_DEADLINE_S 600, UI_RETRY_MAX 3, the [1, 300] s retry-delay clamp,
  UI_OPERATIONS_MAX 200, UI_PRESENTATIONS_MAX 100 and UI_CONSUMED_EVENTS_MAX
  500 are spec 23499 FR-35345-6's parameters (derivations there); the relay
  retains results 604800 s and actions 86400 s, so a same-id retry inside
  those windows still observes the result.
"""

import dataclasses
import datetime
import hashlib
import json
import re

CAPABILITY_NAME = "custom.slack.ui"
CAPABILITY_VERSION = 1
POST = "post"
UPDATE = "update"
POST_MESSAGE_TYPE = "custom.slack.ui.post"
UPDATE_MESSAGE_TYPE = "custom.slack.ui.update"
RECONCILE = "reconcile"  # the version 2 settlement (slack_ui_v2; ADR 35345 D15)
OPERATION_KINDS = (POST, UPDATE, RECONCILE)

POST_MEMBERS = frozenset(("text", "blocks", "expires_in_seconds", "single_use", "on_invalid", "option_sources", "behavior"))
UPDATE_MEMBERS = frozenset(("text", "blocks", "option_sources"))
UPDATE_POLICY_MEMBERS = frozenset(("expires_in_seconds", "single_use"))
ON_INVALID_VALUES = ("fallback", "reject")
DEFAULT_ON_INVALID = "fallback"

UI_REQUEST_MAX_BYTES = 16384
UI_MAX_JSON_DEPTH = 16
UI_MAX_BLOCKS = 49
MAX_RESULT_ERRORS = 8  # $defs.result.body.errors maxItems
MAX_EXPIRES_IN_SECONDS = 604800
MAX_CONVERSATION_ID_CHARS = 4096
MAX_UI_ID_CHARS = 64

RESULT_STATUSES = ("confirmed", "fallback_sent", "rejected", "conflict", "unavailable", "uncertain")
DEFINITIVE_STATUSES = frozenset(("confirmed", "fallback_sent", "rejected", "conflict"))
RATE_LIMITED_REASON = "rate_limited"
NOT_SENT = "not_sent"  # the connector's own terminal status: the CLI never held the operation

# Spec 23499 FR-35345-6 parameters (module constants by decision; see the docstring).
UI_RESULT_DEADLINE_S = 600
UI_RETRY_MAX = 3
UI_RETRY_DELAY_MIN_S = 1
UI_RETRY_DELAY_MAX_S = 300
UI_OPERATIONS_MAX = 200
UI_PRESENTATIONS_MAX = 100
UI_CONSUMED_EVENTS_MAX = 500
RELAY_DEFAULT_EXPIRES_IN_SECONDS = 86400

# D9 / FR-35345-6 operation stages: `submitting` (record written, `send` not yet returned),
# `submitted` (waiting for the result; D8 `pending`), `retry_wait` (rate limited; the same id
# retries at `retry_at`), `terminal` (`status` set). FR-35345-3(a): a result whose status equals a
# terminal record's is a redelivery and is silent; a terminal `uncertain` or `unavailable` accepts
# ONE later definitive result and surfaces the change; every other terminal never changes.
STAGE_SUBMITTING = "submitting"
STAGE_SUBMITTED = "submitted"
STAGE_RETRY_WAIT = "retry_wait"
STAGE_TERMINAL = "terminal"
PRESENTATION_LIVE = "live"
PRESENTATION_FALLBACK = "fallback"
PRESENTATION_EXPIRED = "expired"
PRESENTATION_REVISION_UNKNOWN = "revision_unknown"
PRESENTATION_SETTLED = "settled"  # a version 2 card after its tap was reconciled (slack_ui_v2; ADR 35345 D15)

ACTION_ID = re.compile(r"[A-Za-z0-9_.-]{1,64}")
# A multi-pick — `checkboxes` or a `multi_*` select — accumulates across taps and is read at the
# Submit press from the event's `state`; its ticks never reach the coordinator (owner ruling 49,
# 2026-09-23 19:45Z). Lives here, not in slack_ui_v2, so a version 1 click needs no version 2 module.
MULTI_PICK_ELEMENT_TYPES = frozenset(("checkboxes", "multi_static_select", "multi_users_select",
                                      "multi_channels_select", "multi_conversations_select",
                                      "multi_external_select"))
_TYPE_NAMES = ((bool, "boolean"), (int, "integer"), (float, "number"), (str, "string"), (list, "array"), (dict, "object"))


class SlackUiInputError(ValueError):
    """Actionable refusal: the message says what was wrong and what is allowed."""


def type_name(value):
    if value is None:
        return "null"
    return next((name for cls, name in _TYPE_NAMES if isinstance(value, cls)), type(value).__name__)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _compact_bytes(obj):
    # ensure_ascii escapes non-ASCII, so len() is the byte count of the form the CLI re-serializes.
    return len(json.dumps(obj, separators=(",", ":")))


def json_depth(obj):
    """Nesting depth: a scalar is 0, an object or array is 1 + its deepest child."""
    stack, deepest = [(obj, 1)], 0
    while stack:
        node, depth = stack.pop()
        if isinstance(node, dict):
            children = list(node.values())
        elif isinstance(node, list):
            children = node
        else:
            continue
        deepest = max(deepest, depth)
        stack.extend((child, depth + 1) for child in children if isinstance(child, (dict, list)))
    return deepest


def _envelope(payload):
    return {"version": CAPABILITY_VERSION, "to_role": "capability",
            "body": {"name": CAPABILITY_NAME, "version": CAPABILITY_VERSION, "payload": payload}}


def _depth_error(depth):
    return SlackUiInputError(f"message JSON nests {depth} levels deep inside the mailbox envelope; "
                             f"at most {UI_MAX_JSON_DEPTH} are admitted (relay max_json_depth)")


def admit_message_json(raw, *, kind):
    """Parse and validate one `--message-json` object for a `post` or `update`.

    Returns a shallow copy holding exactly the members the model supplied.
    Refuses (SlackUiInputError) anything the connector can decide locally:
    invalid JSON, a non-object, an unknown member, a missing or malformed
    `text` / `blocks`, a mistyped optional member, or a size / depth / block
    count over the relay's bounds. Block internals are the relay's (D13).
    """
    if kind == POST:
        allowed, label = POST_MEMBERS, "a post"
    elif kind == UPDATE:
        allowed, label = UPDATE_MEMBERS, "an update (--replace-last)"
    else:
        raise ValueError(f"kind must be {POST!r} or {UPDATE!r}, got {kind!r}")
    try:
        obj = json.loads(raw)
    except RecursionError:
        raise _depth_error(UI_MAX_JSON_DEPTH + 1) from None
    except json.JSONDecodeError as err:
        raise SlackUiInputError(
            f"message JSON is not valid JSON: {err.msg} (line {err.lineno} column {err.colno})") from None
    if not isinstance(obj, dict):
        raise SlackUiInputError(f"message JSON must be a JSON object with `text` and `blocks`; got {type_name(obj)}")
    size = _compact_bytes(obj)
    if size > UI_REQUEST_MAX_BYTES:
        raise SlackUiInputError(
            f"message JSON is {size} bytes serialized; the complete request must fit in {UI_REQUEST_MAX_BYTES} bytes")
    depth = json_depth(_envelope(obj))
    if depth > UI_MAX_JSON_DEPTH:
        raise _depth_error(depth)
    unknown = sorted(set(obj) - allowed)
    if unknown:
        names = ", ".join(f"`{name}`" for name in unknown)
        noun, verb = ("member", "is") if len(unknown) == 1 else ("members", "are")
        message = f"message JSON {noun} {names} {verb} not accepted for {label}; allowed members: {', '.join(sorted(allowed))}"
        if kind == UPDATE and set(unknown) & UPDATE_POLICY_MEMBERS:
            message += " (an update keeps the original card's expiry and single-use policy)"
        raise SlackUiInputError(message)
    _check_text(obj)
    _check_blocks(obj)
    if "expires_in_seconds" in obj:
        value = obj["expires_in_seconds"]
        if not _is_int(value) or not 1 <= value <= MAX_EXPIRES_IN_SECONDS:
            raise SlackUiInputError(
                f"message JSON `expires_in_seconds` must be an integer from 1 to {MAX_EXPIRES_IN_SECONDS}; got {value!r}")
    if "single_use" in obj and not isinstance(obj["single_use"], bool):
        raise SlackUiInputError(f"message JSON `single_use` must be true or false; got {obj['single_use']!r}")
    if "on_invalid" in obj and obj["on_invalid"] not in ON_INVALID_VALUES:
        raise SlackUiInputError(
            f"message JSON `on_invalid` must be one of: {', '.join(ON_INVALID_VALUES)}; got {obj['on_invalid']!r}")
    if "option_sources" in obj:
        _check_option_sources(obj["option_sources"])
    if "behavior" in obj and not isinstance(obj["behavior"], dict):
        # The shape inside is slack_ui_v2.admit_behavior's (ADR 35345 D15 item 3).
        raise SlackUiInputError(f"message JSON `behavior` must be an object; got {type_name(obj['behavior'])}")
    return dict(obj)


def _check_option_sources(sources):
    # FR-35345-1(b): keys match ^[A-Za-z0-9_.-]{1,64}$, values are non-empty arrays; the option
    # shape inside is the relay's.
    if not isinstance(sources, dict):
        raise SlackUiInputError(
            f"message JSON `option_sources` must be an object mapping action ids to option arrays; got {type_name(sources)}")
    for key, options in sources.items():
        if not ACTION_ID.fullmatch(key):
            raise SlackUiInputError(
                f"message JSON `option_sources` key {key!r} is not an action id (1-64 characters of A-Z a-z 0-9 _ . -)")
        if not isinstance(options, list) or not options:
            got = "an empty array" if options == [] else type_name(options)
            raise SlackUiInputError(f"message JSON `option_sources[{key!r}]` must be a non-empty array of options; got {got}")


def _check_text(obj):
    what = "(the fallback and notification text)"
    if "text" not in obj:
        raise SlackUiInputError(f"message JSON requires a non-empty string `text` {what}; it is missing")
    text = obj["text"]
    if not isinstance(text, str):
        raise SlackUiInputError(f"message JSON `text` must be a non-empty string {what}; got {type_name(text)}")
    if not text.strip():
        raise SlackUiInputError(f"message JSON `text` must be a non-empty string {what}; got an empty string")
    # The schema's 40000-character `text` cap is never reached under the 16 KiB request bound.


def _check_blocks(obj):
    if "blocks" not in obj:
        raise SlackUiInputError("message JSON requires a non-empty `blocks` array of Block Kit blocks; it is missing")
    blocks = obj["blocks"]
    if not isinstance(blocks, list) or not blocks:
        got = "an empty array" if blocks == [] else type_name(blocks)
        raise SlackUiInputError(f"message JSON `blocks` must be a non-empty array of Block Kit blocks; got {got}")
    if len(blocks) > UI_MAX_BLOCKS:
        raise SlackUiInputError(
            f"message JSON has {len(blocks)} blocks; at most {UI_MAX_BLOCKS} are admitted per message "
            "(Slack allows 50 and the relay reserves one for its expiry status)")
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            got = type_name(block)
        elif "type" not in block:
            got = "an object without `type`"
        elif not isinstance(block["type"], str) or not block["type"]:
            got = f"`type` of {type_name(block['type'])}"
        else:
            continue
        raise SlackUiInputError(
            f"message JSON `blocks[{index}]` must be an object with a string `type` (a Block Kit block); got {got}")
    _check_action_ids_unique(blocks)
    _check_multi_pick_has_a_button(blocks)


def _elements(blocks):
    """(element, block index) of every interactive element — an `actions` /
    `context_actions` element, a `section` accessory, an `input` element —
    with or without an `action_id` (Block Kit makes it optional)."""
    found = []
    for index, block in enumerate(blocks):
        if block.get("type") in ("actions", "context_actions"):
            elements = [e for e in block.get("elements") or [] if isinstance(e, dict)]
        elif block.get("type") == "section" and isinstance(block.get("accessory"), dict):
            elements = [block["accessory"]]
        elif block.get("type") == "input" and isinstance(block.get("element"), dict):
            elements = [block["element"]]
        else:
            continue
        found.extend((e, index) for e in elements)
    return found


def _has_action_id(element):
    return isinstance(element.get("action_id"), str) and bool(element["action_id"])


def _controls(blocks):
    """The elements that carry an `action_id`: the ones a click can be attributed to."""
    return [(e, i) for e, i in _elements(blocks) if _has_action_id(e)]


def _control_ids(blocks):
    return [(element["action_id"], index) for element, index in _controls(blocks)]


def _check_multi_pick_has_a_button(blocks):
    """Review of PR #41509: under owner ruling 49 a multi-pick's ticks are held,
    so a card whose checkboxes / multi-select has no button beside it would
    swallow every answer. Refuse it at compose time, pointing at example 10."""
    elements = [element for element, _index in _elements(blocks)]
    # Only a button with its own action_id can attribute the press; a multi-pick counts with or without an id,
    # because the listener's tick hold keys on the element type (review of PR #41642).
    if any(element.get("type") == "button" and _has_action_id(element) for element in elements):
        return
    for element in elements:
        if element.get("type") in MULTI_PICK_ELEMENT_TYPES:
            who = repr(element["action_id"]) if _has_action_id(element) else "without an action_id"
            raise SlackUiInputError(
                f"message JSON has a {element['type']} control {who} and no button with its own action_id: a multi-pick is "
                "read at the Submit press (its ticks never reach you) — add one Submit button with its own action_id "
                "beside it (reference example 10)")


def _check_action_ids_unique(blocks):
    """QA r22 SR-DAEMON D3 (#41308): three buttons shared one `action_id`, so the
    click line could not say which was tapped and the synthesized tap-time line
    showed the first button's label whatever the tap. Slack requires the ids to
    be unique too; refuse at compose time, naming the id, the count and the fix."""
    seen = {}
    for action_id, index in _control_ids(blocks):
        seen.setdefault(action_id, []).append(index)
    for action_id, indexes in seen.items():
        if len(indexes) > 1:
            where = ", ".join(f"blocks[{i}]" for i in indexes)
            raise SlackUiInputError(
                f"message JSON action_id {action_id!r} is used by {len(indexes)} controls ({where}); give each control "
                "its own action_id — the click line and the tap-time line are keyed by it")


def _require_admitted(admitted, allowed):
    if not isinstance(admitted, dict) or not {"text", "blocks"} <= set(admitted) <= allowed:
        raise SlackUiInputError("envelope input must be the object admit_message_json returned for this kind")


def _wrap(kind, payload):
    envelope = _envelope(payload)
    size = _compact_bytes(envelope)
    if size > UI_REQUEST_MAX_BYTES:
        raise SlackUiInputError(f"the {kind} request is {size} bytes serialized; "
                                f"at most {UI_REQUEST_MAX_BYTES} bytes fit the mailbox payload")
    return envelope


def build_post_envelope(admitted, *, conversation_id):
    """The `custom.slack.ui.post` request: the model's members unchanged plus the
    connector-injected `type` and `conversation_id`. `on_invalid` defaults to
    `fallback` (D12) only when absent; expiry and single-use stay absent so the
    relay applies its own defaults (D14). The relay mints `ui_id` and returns
    it in the confirmed result, so a post carries none."""
    _require_admitted(admitted, POST_MEMBERS)
    if "behavior" in admitted:
        raise SlackUiInputError("`behavior` is a version 2 member; a version 1 post carries none (slack_ui_v2)")
    if not isinstance(conversation_id, str) or not 1 <= len(conversation_id) <= MAX_CONVERSATION_ID_CHARS:
        raise SlackUiInputError(f"conversation_id must be a non-empty string of at most {MAX_CONVERSATION_ID_CHARS} characters")
    payload = {"type": POST, "conversation_id": conversation_id, **admitted}
    payload.setdefault("on_invalid", DEFAULT_ON_INVALID)
    return _wrap(POST, payload)


def build_update_envelope(admitted, *, ui_id, expected_revision):
    """The `custom.slack.ui.update` request for the connector-held `ui_id` and
    `expected_revision`; the model's members pass through unchanged."""
    _require_admitted(admitted, UPDATE_MEMBERS)
    if not isinstance(ui_id, str) or not 1 <= len(ui_id) <= MAX_UI_ID_CHARS:
        raise SlackUiInputError(f"ui_id must be a non-empty string of at most {MAX_UI_ID_CHARS} characters")
    if not _is_int(expected_revision) or expected_revision < 1:
        raise SlackUiInputError("expected_revision must be an integer >= 1")
    return _wrap(UPDATE, {"type": UPDATE, "ui_id": ui_id, "expected_revision": expected_revision, **admitted})


def canonical_json(obj):
    """`json.dumps(obj, sort_keys=True, separators=(",", ":"))` — FR-35345-2(c)'s canonical form."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def payload_digest(obj):
    """SHA-256 of the canonical JSON for D9 records (`payload_sha256`)."""
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def operation_id(lane_key, admitted, *, newest_inbound=None, ui_id=None, expected_revision=None):
    """FR-35345-2(c) / INV-35345-7: the operation id is derived from the content, never minted at
    random, so the same card again before the next inbound line is the same operation (the mailbox
    `(sender, message_id)` dedup drops a second send) and any changed content is a new one. Byte-for-
    byte the connector's `message_id_from_key(reply_idempotency_key(lane key, <text>, newest
    inbound))` with `<text>` the canonical JSON for a post and
    `"ui:update:" + ui_id + ":" + expected_revision + ":" + canonical JSON` for an update."""
    if (ui_id is None) != (expected_revision is None):
        raise SlackUiInputError("an update id needs both ui_id and expected_revision; a post id neither")
    text = canonical_json(admitted)
    if ui_id is not None:
        text = f"ui:update:{ui_id}:{expected_revision}:{text}"
    parts = [lane_key, text] if newest_inbound is None else [lane_key, newest_inbound, text]
    key = hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()[:32]
    return "muse-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


@dataclasses.dataclass(frozen=True)
class Result:
    """One decoded `capability_result`; `raw` keeps exactly what the relay said."""

    request_message_id: str
    status: str
    ui_id: object
    revision: object
    reason: object
    retry_after_seconds: object
    errors: tuple
    raw: dict


@dataclasses.dataclass(frozen=True)
class Event:
    """One decoded `capability_event` (`type: action`), fields as upstream."""

    event_id: str
    ui_id: str
    revision: int
    action_id: str
    action_type: str
    values: tuple
    state: dict
    actor_slack_id: str
    action_ts: str
    raw: dict


def _capability_body(payload, role):
    if not isinstance(payload, dict):
        raise SlackUiInputError(f"{role} envelope must be a JSON object; got {type_name(payload)}")
    if payload.get("to_role") != role:
        raise SlackUiInputError(f"{role} envelope to_role must be {role}; got {payload.get('to_role')!r}")
    version = payload.get("version")
    if not _is_int(version) or version != CAPABILITY_VERSION:
        raise SlackUiInputError(f"{role} envelope version must be {CAPABILITY_VERSION}; got {version!r}")
    body = payload.get("body")
    if not isinstance(body, dict):
        raise SlackUiInputError(f"{role} envelope body must be a JSON object; got {type_name(body)}")
    if body.get("name") != CAPABILITY_NAME:
        raise SlackUiInputError(f"{role} body name must be {CAPABILITY_NAME}; got {body.get('name')!r}")
    body_version = body.get("version")
    if not _is_int(body_version) or body_version != CAPABILITY_VERSION:
        # D2: a version change lands as a reviewed snapshot update, never by reading v2 bytes as v1.
        raise SlackUiInputError(f"{role} body version must be {CAPABILITY_VERSION}; got {body_version!r}")
    return body


def required_str(body, role, field):
    if field not in body:
        raise SlackUiInputError(f"{role} body requires a non-empty string {field}; it is missing")
    value = body[field]
    if not isinstance(value, str) or not value:
        got = "an empty string" if value == "" else type_name(value)
        raise SlackUiInputError(f"{role} body requires a non-empty string {field}; got {got}")
    return value


def _optional(body, role, field, cls, what):
    value = body.get(field)
    if value is not None and (not isinstance(value, cls) or isinstance(value, bool)):
        raise SlackUiInputError(f"{role} body {field} must be {what} or null; got {type_name(value)}")
    return value


def parse_capability_result(payload):
    """Decode a `capability_result` envelope; malformed input is a refusal."""
    role = "capability_result"
    body = _capability_body(payload, role)
    request_message_id = required_str(body, role, "request_message_id")
    status = required_str(body, role, "status")
    if status not in RESULT_STATUSES:
        # FR-35345-3(a): a status outside the vendored enum is malformed, never guessed at.
        raise SlackUiInputError(f"{role} body status must be one of: {', '.join(RESULT_STATUSES)}; got {status!r}")
    # `errors` is a plain array in $defs.result (not nullable): absence is the only empty case.
    errors = body.get("errors", [])
    if not isinstance(errors, list) or not all(
            isinstance(e, dict) and isinstance(e.get("path"), str) and isinstance(e.get("code"), str) for e in errors):
        raise SlackUiInputError(f"{role} body errors must be an array of {{path, code}} string pairs")
    return Result(
        request_message_id=request_message_id,
        status=status,
        ui_id=_optional(body, role, "ui_id", str, "a string"),
        revision=_optional(body, role, "revision", int, "an integer"),
        reason=_optional(body, role, "reason", str, "a string"),
        retry_after_seconds=_optional(body, role, "retry_after_seconds", int, "an integer"),
        # Projected and capped at the boundary: the record is bounded state (FR-35345-6).
        errors=tuple({"path": e["path"], "code": e["code"]} for e in errors[:MAX_RESULT_ERRORS]),
        raw=payload,
    )


def parse_capability_event(payload):
    """Decode a `capability_event` action envelope; malformed input is a refusal. An action_type outside
    the snapshot's 23 passes through: the relay owns that catalogue; the connector does not interpret (D10)."""
    role = "capability_event"
    body = _capability_body(payload, role)
    if body.get("type") != "action":
        raise SlackUiInputError(f"{role} body type must be action; got {body.get('type')!r}")
    revision = body.get("revision")
    if not _is_int(revision) or revision < 1:
        raise SlackUiInputError(f"{role} body revision must be an integer >= 1; got {revision!r}")
    values = body.get("values")
    if not isinstance(values, list):
        raise SlackUiInputError(f"{role} body values must be an array of strings; got {type_name(values)}")
    if not all(isinstance(v, str) for v in values):
        raise SlackUiInputError(f"{role} body values must be an array of strings; got {values!r}")
    state = body.get("state")
    if not isinstance(state, dict) or not all(
            isinstance(v, list) and all(isinstance(s, str) for s in v) for v in state.values()):
        got = type_name(state) if not isinstance(state, dict) else "an object with a non-string-array value"
        raise SlackUiInputError(f"{role} body state must be an object of string arrays; got {got}")
    return Event(
        event_id=required_str(body, role, "event_id"),
        ui_id=required_str(body, role, "ui_id"),
        revision=revision,
        action_id=required_str(body, role, "action_id"),
        action_type=required_str(body, role, "action_type"),
        values=tuple(values),
        state=state,
        actor_slack_id=required_str(body, role, "actor_slack_id"),
        action_ts=required_str(body, role, "action_ts"),
        raw=payload,
    )


def classify_result(result, *, retries=0):
    """D12 / FR-35345-3(b): `silent` (confirmed, fallback_sent); `retry` (unavailable whose reason is
    exactly rate_limited, with an integer delay and retries below UI_RETRY_MAX); else `surface`."""
    if result.status in ("confirmed", "fallback_sent"):
        return "silent"
    if (result.status == "unavailable" and result.reason == RATE_LIMITED_REASON
            and _is_int(result.retry_after_seconds) and retries < UI_RETRY_MAX):
        return "retry"
    return "surface"


def iso(seconds):
    """Epoch seconds -> the ISO-8601 UTC instant the records carry."""
    return datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def epoch(instant):
    """ISO-8601 UTC instant (with or without fraction) -> epoch seconds."""
    return datetime.datetime.fromisoformat(instant.replace("Z", "+00:00")).timestamp()


def new_operation_record(*, lane, key, transport, relay, kind, payload_sha256, now,
                         expires_in_seconds=RELAY_DEFAULT_EXPIRES_IN_SECONDS, ui_id=None, expected_revision=None):
    """FR-35345-6 operation record, written at `submitting` before the send. The caller keys it by the
    request message id (`checkpoint.ui.operations[<operation id>]`); the record does not repeat its key.
    Never the text or blocks."""
    if kind not in OPERATION_KINDS:
        raise ValueError(f"kind must be one of {OPERATION_KINDS}, got {kind!r}")
    return {"lane": lane, "key": key, "transport": transport, "relay": relay, "kind": kind,
            "ui_id": ui_id, "expected_revision": expected_revision, "payload_sha256": payload_sha256,
            "expires_in_seconds": expires_in_seconds, "stage": STAGE_SUBMITTING, "started_at": iso(now),
            "status": None, "reason": None, "errors": [], "retry_after_seconds": None, "retries": 0,
            "submitted_at": None, "retry_at": None, "deadline_at": None, "result_at": None,
            "surfaced_at": None}


def mark_submitted(operation, *, now, deadline_seconds=UI_RESULT_DEADLINE_S):
    """The mailbox accepted the send (D8): `submitted` with a fresh `deadline_at`. Also the return
    from `retry_wait` once `muse-mailbox retry` succeeded."""
    return dict(operation, stage=STAGE_SUBMITTED, submitted_at=operation.get("submitted_at") or iso(now),
                retry_at=None, deadline_at=iso(now + deadline_seconds))


def mark_terminal(operation, *, now, status, reason=None):
    """Connector-decided terminal states, all surfaced: `uncertain` (deadline, FR-35345-3(b); failed
    retry, (c)) and `not_sent` (FM-35345-7: the CLI never held the operation, so the owner is told to
    send the post again)."""
    return Transition("surface", dict(operation, stage=STAGE_TERMINAL, status=status, reason=reason,
                                      result_at=iso(now), surfaced_at=iso(now), retry_at=None))


def expire_operation(operation, *, now, deadline_seconds=UI_RESULT_DEADLINE_S):
    """No result by `deadline_at`: terminal `uncertain`, surfaced under the same id (D12)."""
    return mark_terminal(operation, now=now, status="uncertain", reason=f"no result within {deadline_seconds} s")


def operation_deadline_passed(operation, *, now):
    """True when a `submitted` operation is past `deadline_at`."""
    return operation["stage"] == STAGE_SUBMITTED and now > epoch(operation["deadline_at"])


def retry_due(operation, *, now):
    """True when a `retry_wait` operation is at or past `retry_at`."""
    return operation["stage"] == STAGE_RETRY_WAIT and now >= epoch(operation["retry_at"])


def new_presentation_record(*, lane, key, transport, relay, revision, operation_id, now, expires_at,
                            state=PRESENTATION_LIVE):
    """FR-35345-6 presentation record; the caller keys it (`checkpoint.ui.presentations[<ui_id>]`)."""
    return {"lane": lane, "key": key, "transport": transport, "relay": relay, "revision": revision,
            "operation_id": operation_id, "state": state, "posted_at": iso(now), "expires_at": expires_at,
            "last_event_at": None}


@dataclasses.dataclass(frozen=True)
class Transition:
    """Records after one result or event plus the disposition: results silent|retry|surface; events
    route|stale. `presentation_id` is the map key of the returned presentation (the relay's ui_id, or
    the operation id for a fallback card); `note` names a surfaced change to an already-surfaced
    operation."""

    disposition: str
    operation: object = None
    presentation: object = None
    presentation_id: object = None
    retry_after_seconds: object = None
    result: object = None
    event: object = None
    note: object = None


# Wrong-kind markers for apply_result / apply_event (the members each reads), NOT the FR-35345-6 member
# lists: new_operation_record / new_presentation_record own those.
_OPERATION_SHAPE = frozenset(("stage", "status", "retries", "kind", "ui_id", "expected_revision",
                              "lane", "key", "transport", "relay"))
_PRESENTATION_SHAPE = frozenset(("revision", "state", "operation_id", "lane", "key", "transport", "relay"))


def _require_shape(record, members, what):
    if not isinstance(record, dict) or not members <= set(record):
        missing = sorted(members - set(record)) if isinstance(record, dict) else sorted(members)
        raise SlackUiInputError(f"{what} record is missing {', '.join(missing)}; the wrong record kind was passed")


def next_state(record_id, record, message, *, presentation=None, pending_update=None, now):
    """Pure FR-35345-3/-4 transition, one seam over `apply_result` / `apply_event`. With a Result,
    `record` is the operation under `operations[record_id]` (and `presentation` its card, if any);
    with an Event, `record` is the presentation under `presentations[record_id]` (and
    `pending_update` a `submitted` update on it, if any). A record of the wrong kind is refused,
    never a KeyError. Inputs are never mutated."""
    if isinstance(message, Result):
        return apply_result(record_id, record, message, presentation=presentation, now=now)
    if isinstance(message, Event):
        return apply_event(record_id, record, message, pending_update=pending_update, now=now)
    raise TypeError(f"next_state takes a Result or an Event, got {type(message).__name__}")


def apply_result(operation_id, operation, result, *, presentation=None, now):
    """FR-35345-3(a)/(b): the operation under `operations[operation_id]` after `result`."""
    _require_shape(operation, _OPERATION_SHAPE, "operation")
    if presentation is not None:
        _require_shape(presentation, _PRESENTATION_SHAPE, "presentation")
    if result.request_message_id != operation_id:
        raise SlackUiInputError(
            f"capability_result for {result.request_message_id} does not belong to operation {operation_id}")
    note = None
    if operation["stage"] == STAGE_TERMINAL:
        # FR-35345-3(a): same status = redelivery; only a terminal uncertain / unavailable accepts
        # ONE later definitive result (and surfaces the change); every other terminal never changes.
        late = operation["status"] in ("uncertain", "unavailable") and result.status in DEFINITIVE_STATUSES
        if not late:
            return Transition("silent", operation, presentation, operation["ui_id"], result=result)
        note = f"{operation['kind']} {result.status} after {operation['status']}"
    disposition = classify_result(result, retries=operation["retries"])
    updated = dict(operation, reason=result.reason, errors=[dict(e) for e in result.errors],
                   retry_after_seconds=result.retry_after_seconds, result_at=iso(now))
    card, card_id = presentation, operation["ui_id"]
    if disposition == "retry":
        delay = min(max(result.retry_after_seconds, UI_RETRY_DELAY_MIN_S), UI_RETRY_DELAY_MAX_S)
        updated.update(stage=STAGE_RETRY_WAIT, retry_at=iso(now + delay), retries=operation["retries"] + 1)
        return Transition("retry", updated, presentation, card_id, retry_after_seconds=delay, result=result)
    updated.update(stage=STAGE_TERMINAL, status=result.status, retry_at=None)
    if result.status == "confirmed":
        if not result.ui_id:
            updated.update(reason="confirmed result carried no ui_id", surfaced_at=iso(now))
            return Transition("surface", updated, presentation, card_id, result=result, note=note)
        updated["ui_id"] = card_id = result.ui_id
        if presentation is None or operation["ui_id"] != result.ui_id:
            card = new_presentation_record(
                lane=operation["lane"], key=operation["key"], transport=operation["transport"],
                relay=operation["relay"], revision=result.revision if result.revision is not None else 1,
                operation_id=operation_id, now=now, expires_at=_expires_at(operation, now))
        else:
            revision = result.revision if result.revision is not None else presentation["revision"]
            card = _settled(dict(presentation, operation_id=operation_id, revision=revision), operation_id)
    elif result.status == "fallback_sent":
        # The relay posted the text without controls: a `fallback` presentation, keyed by the relay's
        # ui_id when it returned one, else by the operation id (FR-35345-3(b)).
        updated["ui_id"] = card_id = result.ui_id or operation_id
        card = new_presentation_record(
            lane=operation["lane"], key=operation["key"], transport=operation["transport"], relay=operation["relay"],
            revision=result.revision, operation_id=operation_id, now=now, expires_at=_expires_at(operation, now),
            state=PRESENTATION_FALLBACK)
    elif result.status == "conflict" and presentation is not None:
        # The card is live at the relay's revision when it says which; otherwise unknown.
        card = _settled(dict(presentation, revision=result.revision) if result.revision is not None
                        else dict(presentation, state=PRESENTATION_REVISION_UNKNOWN), operation_id)
    if disposition == "silent" and note is None:
        return Transition("silent", updated, card, card_id, result=result)
    updated["surfaced_at"] = iso(now)
    return Transition("surface", updated, card, card_id, result=result, note=note)


def _settled(card, operation_id):
    """FR-35345-3(b): a terminal result for an update clears the card's `pending_operation_id`
    while it still names that operation. Returns a fresh copy (never mutates `card`), so the
    caller's write-back cannot restore a pointer it just cleared and a stored card passed straight
    in stays untouched (#35345 E2E, lane L2). A newer update's marker survives."""
    if card.get("pending_operation_id") == operation_id:
        return dict(card, pending_operation_id=None)
    return card


def _expires_at(operation, now):
    since = operation.get("submitted_at") or iso(now)
    return iso(epoch(since) + (operation.get("expires_in_seconds") or RELAY_DEFAULT_EXPIRES_IN_SECONDS))


def apply_event(ui_id, presentation, event, *, pending_update=None, now):
    """FR-35345-4(a): the presentation under `presentations[ui_id]` after `event`: `route` or `stale`."""
    _require_shape(presentation, _PRESENTATION_SHAPE, "presentation")
    if pending_update is not None:
        _require_shape(pending_update, _OPERATION_SHAPE, "operation")
    if event.ui_id != ui_id:
        raise SlackUiInputError(f"capability_event for {event.ui_id} does not belong to presentation {ui_id}")
    # FR-35345-4(a): the click must land on the current revision, or on the next one when a
    # submitted update is outstanding (the click beat its `confirmed`); anything else is stale (D10).
    expected = (pending_update["expected_revision"] + 1
                if pending_update and pending_update["stage"] == STAGE_SUBMITTED
                and pending_update["ui_id"] == ui_id else None)
    if event.revision not in (presentation["revision"], expected):
        return Transition("stale", presentation=presentation, presentation_id=ui_id, event=event)
    return Transition("route", presentation=dict(presentation, last_event_at=iso(now)), presentation_id=ui_id,
                      event=event)


def event_seen(seen_ids, event_id, *, cap=UI_CONSUMED_EVENTS_MAX):
    """Bounded FIFO dedupe for consumed event ids (D9 / FR-35345-6): returns `(already_seen, seen_ids)`;
    a new id is appended and the oldest dropped past `cap`. Pure: the input list is not mutated."""
    if event_id in seen_ids:
        return True, seen_ids
    updated = list(seen_ids) + [event_id]
    return False, updated[-cap:] if len(updated) > cap else updated
