"""Pure contract helpers for the connector's `custom.slack.ui` version 2 arm.

Owning issue #38715; authority `docs/adr/35345-slack-native-interactive-
agent-controls.md` D15 (the relay answers a tap first; the agent's next reply
settles it) with D2 Amendment 1, D4 Amendment 1, D6 Amendment 2 and D14
Amendment 1. Owning spec 23499 FR-35345-10.

What lives here, as pure functions (no I/O, no clock; standard library plus
the sibling `slack_ui` module for the shared error type, canonical JSON and
the v1 record shapes): which version a card takes, the synthesized
`behavior`, admission of a declared one, the v2 post and reconcile
envelopes, the v2 result / event parsers and template matching. The Block
Kit grammar and the agreement between `on_action` and the controls are the
relay's (D13).

Bounds, read from the vendored `schemas/custom.slack.ui.post.v2.json`
(`x-musetag-limits`; never loaded here, D2): `max_request_bytes` 65536 —
the mailbox CLI frames a large payload (verified live on 2026-09-21 with
20/40/60 KiB sends), so the relay's request bound is the one that holds;
`v2_max_templates` 16; `max_json_depth` 16 as for version 1. A synthesized
behavior is sized as the full request and steps down a ladder (per-control
templates, then per-block ones) before the card takes version 1 (#38715 QA
r16 F2): a card the version 1 path posts is never refused for its
synthesized templates.

A press view is ONE context line and nothing else (#41246). The relay's
version 2 contract (`SLACK_UI_V2.md`, "Behavior and state") APPENDS a
`business_submission`'s `show_template` under the card's base view with the
controls removed, and overlays the terminal template the same way; it never
replaces the base view. A pressed view that copied the header or the
question therefore showed them twice (the owner's 2026-09-23 tap). A pick's
`selection_summary` view is the one the relay renders in place of the base
view, so it keeps the whole form.
"""

import dataclasses
import hashlib
import json

import slack_ui

CAPABILITY_VERSION = 2
POST_MESSAGE_TYPE = "custom.slack.ui.post"
RECONCILE_MESSAGE_TYPE = "custom.slack.ui.reconcile"
RECONCILE = "reconcile"
RUNTIME = "declarative-v1"
BUSINESS = "business_submission"
PRESENTATION = "presentation"
ACTION_KINDS = (PRESENTATION, BUSINESS)
TRANSITIONS = ("next_supplied_page", "previous_supplied_page", "selection_summary", "toggle")
BEHAVIOR_MEMBERS = frozenset(("runtime", "templates", "on_action", "pages", "initial_view_state"))
ACTION_MEMBERS = frozenset(("kind", "show_template", "transition", "state_key", "alternate_template", "forward"))
TEMPLATE_MEMBERS = frozenset(("text", "blocks", "option_sources"))
V2_REQUEST_MAX_BYTES = 65536
MAX_TEMPLATES = 16
PRESSED_PREFIX = "pressed:"
DONE_PREFIX = "done:"
PRESENTATION_SUFFIX = " · presentation"
RESULT_STATUSES = slack_ui.RESULT_STATUSES + ("queued",)
SILENT_STATUSES = ("confirmed", "fallback_sent", "queued")
PRESENTATION_SETTLED = slack_ui.PRESENTATION_SETTLED
NO_EVENT_ELEMENT_TYPES = ("workflow_button", "image")


@dataclasses.dataclass(frozen=True)
class Control:
    """One interactive element of a card: its logical id, the label a person
    sees on it, its Block Kit type and the index of the block that holds it."""

    action_id: str
    label: str
    element_type: str
    block_index: int = 0


# A press or a submit is a business submission the agent answers; every other
# widget (selects, radios, checkboxes, overflow, date/time pickers, directory
# pickers) is a pick the relay summarises by itself (owner 2026-09-21 ~23:55Z:
# "not just button ... give user some early reply first").
BUSINESS_ELEMENT_TYPES = frozenset(("button", "plain_text_input", "number_input", "email_text_input",
                                    "url_text_input", "feedback_buttons", "icon_button"))
INPUT_ELEMENT_TYPES = frozenset(("plain_text_input", "number_input", "email_text_input", "url_text_input"))
PICKED_PREFIX = "picked:"
# A multi-pick — `checkboxes` or a `multi_*` select — accumulates across taps and is read at
# the submit from the event's `state`. A re-rendered element carries no `initial_options`, so
# a summary view would untick it and the next tap would report only the new tick: its
# presentation names no view (the schema's bare `{"kind": "presentation"}`), Slack keeps the
# ticks, and the one Submit button is the card's single business submission (owner
# 2026-09-23 15:02Z: "multi-select probably has to be some submit button … we can only submit once").
MULTI_PICK_ELEMENT_TYPES = slack_ui.MULTI_PICK_ELEMENT_TYPES  # one set; the v1 path reads it without this module
SELECTION = "{{selection}}"  # the relay fills a selection summary's plain_text placeholder
# The synthesis ladder, top rung first: (name, one template set per block). A
# press view is line-only on every rung, so the ladder only trades template
# count (and a pick's copies of the form) for size.
RUNGS = (("per_control", False), ("grouped", True))
RUNG_WORDS = {"per_control": "per-control templates", "grouped": "per-block templates"}


NEUTRAL_LABEL = "your choice"  # a text-less control (feedback buttons, checkboxes, radios) never shows its id


def _label(element, fallback_label=None):
    """What a person sees on the control: its text, else its placeholder, else
    the input block's label, else a neutral word (QA r16 F4). Option text is
    not used: the relay's `{{selection}}` already is the option text."""
    for member in ("text", "placeholder"):
        value = element.get(member)
        if isinstance(value, dict) and isinstance(value.get("text"), str) and value["text"].strip():
            return value["text"].strip()
    if isinstance(fallback_label, str) and fallback_label.strip():
        return fallback_label.strip()
    return NEUTRAL_LABEL


def _control(element, index, fallback_label=None):
    if not isinstance(element, dict) or not isinstance(element.get("action_id"), str) or not element["action_id"]:
        return None
    if element.get("type") in NO_EVENT_ELEMENT_TYPES:
        return None
    return Control(element["action_id"], _label(element, fallback_label), str(element.get("type") or ""), index)


def interactive_elements(blocks):
    """The card's controls in reading order: every `actions` or
    `context_actions` element, a `section` accessory and an `input` element
    that carries an `action_id` (a `workflow_button` produces no event and an
    image is not a control)."""
    found = []
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        if block.get("type") in ("actions", "context_actions"):
            for element in block.get("elements") or []:
                control = _control(element, index)
                if control:
                    found.append(control)
        elif block.get("type") == "section":
            control = _control(block.get("accessory"), index)
            if control:
                found.append(control)
        elif block.get("type") == "input":
            label = block.get("label") if isinstance(block.get("label"), dict) else None
            control = _control(block.get("element"), index, fallback_label=(label or {}).get("text"))
            if control:
                found.append(control)
    return found


def control_kind(control):
    """`business_submission` for a button, a dispatch-action input or a feedback
    button; `presentation` (a selection summary) for every other widget."""
    return BUSINESS if control.element_type in BUSINESS_ELEMENT_TYPES else PRESENTATION


def line_view(line):
    """The press view: one context line, nothing else. The relay appends it
    under the card (base view, controls removed) at the tap and overlays the
    `done:` line the same way, so any block copied here would show twice."""
    return [{"type": "context", "elements": [{"type": "mrkdwn", "text": line}]}]


def summary_view(blocks, block_index, line):
    """The form as it stands — every control kept, so the relay re-renders it
    usable — plus one plain-text context line right after the block that
    holds the pick; the relay fills `{{selection}}` with what was picked.
    None when it would not fit the block bound."""
    context = {"type": "context", "elements": [{"type": "plain_text", "text": line, "emoji": False}]}
    out = list(blocks[: block_index + 1]) + [context] + list(blocks[block_index + 1:])
    return out if len(out) <= slack_ui.UI_MAX_BLOCKS else None


def _plan(admitted, controls, grouped):
    """One (templates, on_action) plan: per control, or per block when
    `grouped`. A press view is the line alone (the relay appends it); a pick
    keeps the form (the relay re-renders that view in place)."""
    templates, on_action = {}, {}
    blocks = admitted["blocks"]
    for control in controls:
        kind = control_kind(control)
        suffix = f"block{control.block_index}" if grouped else control.action_id
        if kind == PRESENTATION:
            if control.element_type in MULTI_PICK_ELEMENT_TYPES:
                on_action[control.action_id] = {"kind": PRESENTATION}  # no view: the ticks stay, the submit reads `state`
                continue
            name = PICKED_PREFIX + suffix
            if name not in templates:
                line = f"Selected: {SELECTION}" if grouped else f"{control.label}: {SELECTION}"
                view = summary_view(blocks, control.block_index, line)
                if view is None:
                    return None
                templates[name] = {"text": line, "blocks": view}
            on_action[control.action_id] = {"kind": PRESENTATION, "transition": "selection_summary",
                                            "state_key": control.action_id, "show_template": name}
            continue
        pressed_name, done_name = PRESSED_PREFIX + suffix, DONE_PREFIX + suffix
        if pressed_name not in templates:
            received = control.element_type in INPUT_ELEMENT_TYPES
            if grouped:
                pressed_line, done_line = "✅ working…", "✅ done"
            else:
                pressed_line = f"✅ {control.label} · " + ("received, working…" if received else "working…")
                done_line = f"✅ {control.label}"
            templates[pressed_name] = {"text": pressed_line, "blocks": line_view(pressed_line)}
            templates[done_name] = {"text": done_line, "blocks": line_view(done_line)}
        on_action[control.action_id] = {"kind": BUSINESS, "show_template": pressed_name}
    if len(templates) > MAX_TEMPLATES:
        return None
    return {"runtime": RUNTIME, "templates": templates, "on_action": on_action}


@dataclasses.dataclass(frozen=True)
class Synthesis:
    """The rung a synthesized behavior settled on (None: version 1), the
    behavior, its request size, and every rung tried with its size (None
    when that rung's templates outnumbered the bound)."""

    rung: object
    behavior: object
    request_bytes: object
    tried: tuple


def synthesize(admitted, *, conversation_id=None):
    """D15 item 2 as extended: the minimal behavior for an object without one.
    Per control: a pick (`presentation`, `selection_summary`) gets a
    `picked:<id>` view — the form kept, one `<label>: {{selection}}` line —
    the relay renders by itself; a multi-pick (`MULTI_PICK_ELEMENT_TYPES`)
    gets a view-less `presentation` — nothing re-renders, Slack keeps the
    ticks, the submit's event `state` carries the set; a press or submit (`business_submission`)
    gets `pressed:<id>` (one line, `✅ <label> · working…`, which the relay
    appends under the card) and `done:<id>` (`✅ <label>`) for the
    settlement. Each rung is sized as the full request (the longest
    conversation id when none is given): past the 16 templates or the
    65,536 bytes, the controls of one block share templates (`…:block<n>`,
    label-neutral lines); past every rung the card is a version 1 card
    (`Synthesis.behavior` None). None for a card with no control or a view
    that would not fit."""
    controls = interactive_elements(admitted["blocks"])
    if not controls:
        return None
    tried = []
    for rung, grouped in RUNGS:
        behavior = _plan(admitted, controls, grouped)
        if behavior is None:
            tried.append((rung, None))
            continue
        size = request_bytes(admitted, behavior, conversation_id=conversation_id)
        tried.append((rung, size))
        if size <= V2_REQUEST_MAX_BYTES:
            return Synthesis(rung, behavior, size, tuple(tried))
    return Synthesis(None, None, None, tuple(tried))


def synthesize_behavior(admitted, *, conversation_id=None):
    """The behavior `synthesize` settles on; None for version 1."""
    synthesis = synthesize(admitted, conversation_id=conversation_id)
    return synthesis.behavior if synthesis is not None else None


def degradation_note(synthesis):
    """One operator line when the ladder stepped down (None on the top rung):
    what the per-control templates would have cost and what went out."""
    if synthesis is None or synthesis.rung == "per_control":
        return None
    first_rung, first_size = synthesis.tried[0]
    cost = (f"make this card {first_size} bytes (at most {V2_REQUEST_MAX_BYTES} fit a version 2 request)"
            if first_size is not None
            else f"exceed the relay's bounds ({MAX_TEMPLATES} templates, {slack_ui.UI_MAX_BLOCKS} blocks a view)")
    if synthesis.rung is None:
        outcome = "posting version 1 (no early reply at the tap)"
    else:
        outcome = f"posting {RUNG_WORDS[synthesis.rung]} ({synthesis.request_bytes} bytes)"
    return f"custom.slack.ui version 2: {RUNG_WORDS[first_rung]} {cost}; {outcome}"


def done_templates(admitted, behavior):
    """control id -> the `done:` template its settlement shows (synthesized behaviors only)."""
    return {control.action_id: DONE_PREFIX + (behavior["on_action"][control.action_id]["show_template"][len(PRESSED_PREFIX):])
            for control in interactive_elements(admitted["blocks"])
            if control_kind(control) == BUSINESS and control.action_id in behavior.get("on_action", {})
            and str(behavior["on_action"][control.action_id].get("show_template", "")).startswith(PRESSED_PREFIX)}


def choose_version(admitted, *, relay_versions, conversation_id=None):
    """D15 item 1: version 2 when the relay advertises it, the card has a
    control and no explicit `on_invalid: fallback` (D14 Amendment 1), and a
    behavior exists — declared, or synthesizable within the template and
    request-size bounds."""
    if CAPABILITY_VERSION not in set(relay_versions or ()):
        return 1
    if admitted.get("on_invalid") == "fallback":
        return 1
    if "behavior" in admitted:
        return 2
    return 2 if synthesize_behavior(admitted, conversation_id=conversation_id) is not None else 1


def _bad(message):
    return slack_ui.SlackUiInputError(message)


def _check_view(name, view):
    if not isinstance(view, dict):
        raise _bad(f"behavior template {name!r} must be an object with text and blocks")
    unknown = sorted(set(view) - TEMPLATE_MEMBERS)
    if unknown:
        raise _bad(f"behavior template {name!r} member {unknown[0]!r} is not accepted; allowed: blocks, option_sources, text")
    text = view.get("text")
    if not isinstance(text, str) or not text.strip():
        raise _bad(f"behavior template {name!r} requires a non-empty string text")
    blocks = view.get("blocks")
    if not isinstance(blocks, list) or not blocks or len(blocks) > slack_ui.UI_MAX_BLOCKS:
        raise _bad(f"behavior template {name!r} requires 1 to {slack_ui.UI_MAX_BLOCKS} blocks")
    for index, block in enumerate(blocks):
        if not isinstance(block, dict) or not isinstance(block.get("type"), str) or not block["type"]:
            raise _bad(f"behavior template {name!r} blocks[{index}] must be an object with a string type")


def admit_behavior(behavior):
    """D15 item 3: a declared behavior is checked by shape and bound only —
    `runtime`, at most MAX_TEMPLATES templates each shaped like a post, an
    `on_action` keyed by action ids whose values are objects with a known
    `kind`. The relay owns everything else and refuses at its boundary."""
    if not isinstance(behavior, dict):
        raise _bad(f"message JSON `behavior` must be an object; got {slack_ui.type_name(behavior)}")
    unknown = sorted(set(behavior) - BEHAVIOR_MEMBERS)
    if unknown:
        raise _bad(f"message JSON `behavior` member {unknown[0]!r} is not accepted; allowed: {', '.join(sorted(BEHAVIOR_MEMBERS))}")
    if behavior.get("runtime") != RUNTIME:
        raise _bad(f"message JSON `behavior.runtime` must be {RUNTIME!r}; got {behavior.get('runtime')!r}")
    templates = behavior.get("templates")
    if not isinstance(templates, dict):
        raise _bad("message JSON `behavior.templates` must be an object of name -> {text, blocks}")
    if len(templates) > MAX_TEMPLATES:
        raise _bad(f"message JSON `behavior.templates` holds {len(templates)} templates; the relay allows {MAX_TEMPLATES}")
    for name, view in templates.items():
        if not isinstance(name, str) or not 1 <= len(name) <= 255:
            raise _bad("behavior template names are strings of 1 to 255 characters")
        _check_view(name, view)
    on_action = behavior.get("on_action")
    if not isinstance(on_action, dict):
        raise _bad("message JSON `behavior.on_action` must be an object of action id -> action")
    for action_id, action in on_action.items():
        if not isinstance(action_id, str) or not slack_ui.ACTION_ID.fullmatch(action_id):
            raise _bad(f"behavior on_action key {action_id!r} is not an action id (1-64 characters of A-Z a-z 0-9 _ . -)")
        if not isinstance(action, dict):
            raise _bad(f"behavior on_action[{action_id!r}] must be an object with a kind")
        if action.get("kind") not in ACTION_KINDS:
            raise _bad(f"behavior on_action[{action_id!r}] kind must be one of: {', '.join(ACTION_KINDS)}")
        unknown = sorted(set(action) - ACTION_MEMBERS)
        if unknown:
            raise _bad(f"behavior on_action[{action_id!r}] member {unknown[0]!r} is not accepted")
        if "transition" in action and action["transition"] not in TRANSITIONS:
            raise _bad(f"behavior on_action[{action_id!r}] transition must be one of: {', '.join(TRANSITIONS)}")
    pages = behavior.get("pages")
    if pages is not None and (not isinstance(pages, list) or len(pages) > MAX_TEMPLATES
                              or not all(isinstance(p, str) and p for p in pages)):
        raise _bad(f"message JSON `behavior.pages` must be an array of at most {MAX_TEMPLATES} template names")
    if "initial_view_state" in behavior and not isinstance(behavior["initial_view_state"], dict):
        raise _bad("message JSON `behavior.initial_view_state` must be an object")
    return dict(behavior)


def _envelope(payload):
    return {"version": 1, "to_role": "capability",
            "body": {"name": slack_ui.CAPABILITY_NAME, "version": CAPABILITY_VERSION, "payload": payload}}


def _wrap(kind, payload):
    envelope = _envelope(payload)
    size = len(json.dumps(envelope, separators=(",", ":")))
    if size > V2_REQUEST_MAX_BYTES:
        raise _bad(f"the {kind} request is {size} bytes serialized; at most {V2_REQUEST_MAX_BYTES} bytes fit a version 2 request")
    depth = slack_ui.json_depth(envelope)
    if depth > slack_ui.UI_MAX_JSON_DEPTH:
        raise _bad(f"the {kind} request nests {depth} levels deep; at most {slack_ui.UI_MAX_JSON_DEPTH} are admitted")
    return envelope


def _post_payload(admitted, behavior, conversation_id):
    payload = {"type": slack_ui.POST, "conversation_id": conversation_id}
    payload.update({k: v for k, v in admitted.items() if k != "behavior"})
    payload["on_invalid"] = "reject"
    payload["behavior"] = behavior
    return payload


def request_bytes(admitted, behavior, *, conversation_id=None):
    """The serialized size of the version 2 post this object and behavior
    make — with the longest conversation id when none is given, so a size
    judged early is never smaller than the one sent."""
    if conversation_id is None:
        conversation_id = "x" * slack_ui.MAX_CONVERSATION_ID_CHARS
    return len(json.dumps(_envelope(_post_payload(admitted, behavior, conversation_id)), separators=(",", ":")))


def build_post_envelope(admitted, behavior, *, conversation_id):
    """The version 2 post: the object's members, the behavior, and
    `on_invalid: reject` (the relay's only value; an explicit `fallback` is a
    version 1 card, D14 Amendment 1)."""
    if admitted.get("on_invalid") == "fallback":
        raise _bad("a version 2 post has no fallback: `on_invalid: fallback` keeps the card on version 1")
    if not isinstance(conversation_id, str) or not 1 <= len(conversation_id) <= slack_ui.MAX_CONVERSATION_ID_CHARS:
        raise _bad(f"conversation_id must be a non-empty string of at most {slack_ui.MAX_CONVERSATION_ID_CHARS} characters")
    return _wrap(slack_ui.POST, _post_payload(admitted, behavior, conversation_id))


def build_reconcile_envelope(*, ui_id, event_id, action_seq, base_model_revision, show_template=None):
    """The `custom.slack.ui.reconcile` that settles one business submission
    as `succeeded` (D15 item 5: what happened is the reply's to say)."""
    payload = {"type": RECONCILE, "ui_id": ui_id, "event_id": event_id, "action_seq": int(action_seq),
               "base_model_revision": int(base_model_revision), "status": "succeeded"}
    if show_template:
        payload["show_template"] = show_template
    return _wrap(RECONCILE, payload)


def template_digests(behavior):
    """name -> SHA-256 of the template's canonical blocks: the bounded record
    a presentation keeps so a later reply can be matched (D9: never the blocks)."""
    return {name: hashlib.sha256(slack_ui.canonical_json(view["blocks"]).encode("utf-8")).hexdigest()
            for name, view in (behavior.get("templates") or {}).items()}


def matching_template(digests, blocks):
    """The declared template whose blocks equal `blocks`, else None."""
    digest = hashlib.sha256(slack_ui.canonical_json(blocks).encode("utf-8")).hexdigest()
    for name, known in (digests or {}).items():
        if known == digest:
            return name
    return None


@dataclasses.dataclass(frozen=True)
class ResultV2:
    request_message_id: str
    status: str
    ui_id: object
    model_revision: object
    action_seq: object
    render_generation: object
    reason: object
    retry_after_seconds: object
    errors: tuple
    raw: dict


@dataclasses.dataclass(frozen=True)
class EventV2:
    event_id: str
    ui_id: str
    kind: str
    action_seq: int
    model_revision: int
    action_id: str
    action_type: str
    values: tuple
    state: dict
    actor_slack_id: str
    action_ts: str
    raw: dict


def _body(payload, role):
    if not isinstance(payload, dict) or payload.get("to_role") != role:
        raise _bad(f"{role} envelope to_role must be {role}")
    body = payload.get("body")
    if not isinstance(body, dict) or body.get("name") != slack_ui.CAPABILITY_NAME:
        raise _bad(f"{role} body name must be {slack_ui.CAPABILITY_NAME}")
    if body.get("version") != CAPABILITY_VERSION:
        raise _bad(f"{role} body version must be {CAPABILITY_VERSION}; got {body.get('version')!r}")
    return body


def _opt_int(body, role, field):
    value = body.get(field)
    if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
        raise _bad(f"{role} body {field} must be an integer or null")
    return value


def parse_capability_result(payload):
    """Decode a version 2 `capability_result`; malformed input is a refusal."""
    role = "capability_result"
    body = _body(payload, role)
    request_message_id = slack_ui.required_str(body, role, "request_message_id")
    status = slack_ui.required_str(body, role, "status")
    if status not in RESULT_STATUSES:
        raise _bad(f"{role} body status must be one of: {', '.join(RESULT_STATUSES)}; got {status!r}")
    errors = body.get("errors", [])
    if not isinstance(errors, list) or not all(
            isinstance(e, dict) and isinstance(e.get("path"), str) and isinstance(e.get("code"), str) for e in errors):
        raise _bad(f"{role} body errors must be an array of {{path, code}} string pairs")
    ui_id = body.get("ui_id")
    if ui_id is not None and not isinstance(ui_id, str):
        raise _bad(f"{role} body ui_id must be a string or null")
    reason = body.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise _bad(f"{role} body reason must be a string or null")
    return ResultV2(request_message_id, status, ui_id, _opt_int(body, role, "model_revision"),
                    _opt_int(body, role, "action_seq"), _opt_int(body, role, "render_generation"), reason,
                    _opt_int(body, role, "retry_after_seconds"),
                    tuple({"path": e["path"], "code": e["code"]} for e in errors[:slack_ui.MAX_RESULT_ERRORS]), payload)


def as_v1_result(result):
    """The v1 `Result` the shared transition matrix reads: `model_revision`
    is the card's revision and `queued` (the relay durably accepted a
    reconcile) is a silent, settled outcome like `confirmed`."""
    status = "confirmed" if result.status == "queued" else result.status
    return slack_ui.Result(result.request_message_id, status, result.ui_id, result.model_revision, result.reason,
                           result.retry_after_seconds, result.errors, result.raw)


def parse_capability_event(payload):
    """Decode a version 2 action event; malformed input is a refusal."""
    role = "capability_event"
    body = _body(payload, role)
    if body.get("type") != "action":
        raise _bad(f"{role} body type must be action; got {body.get('type')!r}")
    kind = slack_ui.required_str(body, role, "kind")
    if kind not in ACTION_KINDS:
        raise _bad(f"{role} body kind must be one of: {', '.join(ACTION_KINDS)}; got {kind!r}")
    for field in ("action_seq", "model_revision"):
        value = body.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < (1 if field == "model_revision" else 0):
            raise _bad(f"{role} body {field} must be a non-negative integer")
    values = body.get("values")
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise _bad(f"{role} body values must be an array of strings")
    state = body.get("state")
    if not isinstance(state, dict) or not all(
            isinstance(v, list) and all(isinstance(s, str) for s in v) for v in state.values()):
        raise _bad(f"{role} body state must be an object of string arrays")
    return EventV2(
        event_id=slack_ui.required_str(body, role, "event_id"), ui_id=slack_ui.required_str(body, role, "ui_id"),
        kind=kind, action_seq=body["action_seq"], model_revision=body["model_revision"],
        action_id=slack_ui.required_str(body, role, "action_id"),
        action_type=slack_ui.required_str(body, role, "action_type"), values=tuple(values), state=state,
        actor_slack_id=slack_ui.required_str(body, role, "actor_slack_id"),
        action_ts=slack_ui.required_str(body, role, "action_ts"), raw=payload)


def pending_submission(event, *, action_id=None):
    """The bounded note a presentation keeps of its one outstanding business
    submission (D15 item 4); None for a presentation event."""
    if event.kind != BUSINESS:
        return None
    return {"event_id": event.event_id, "action_seq": event.action_seq, "model_revision": event.model_revision,
            "action_id": action_id or event.action_id}


def settlement_template(card, blocks=None):
    """D15 item 5: the `show_template` of a settlement — the declared template
    whose blocks equal the reply's, else the synthesized `done:<id>` of the
    pressed control, else None (the relay's default terminal view). Returns
    `(name, matched)`; `matched` says the reply IS that template."""
    if blocks is not None:
        name = matching_template(card.get("template_digests"), blocks)
        if name is not None:
            return name, True
    pressed = (card.get("pending_submission") or {}).get("action_id")
    return (card.get("done_templates") or {}).get(pressed), False
