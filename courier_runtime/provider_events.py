"""Provider-event ingress for Kirby: real provider signals -> Kirby calls.

Turns line-oriented provider signals (Antigravity turn-end/idle, Muse
status lines) into calls on courier_runtime.continuity.Kirby, so a provider
going idle after one task reconciles and continues instead of making
Dennis the manual Continue button.

Line grammar (one event per line; ``checkpoint=``/``reason=`` capture the
remainder of the line and therefore come last)::

    TURN_ENDED outcome=DONE checkpoint=<free text>
    TURN_ENDED outcome=BLOCKED reason=<free text>
    TURN_ENDED outcome=STILL_OPEN | FAILED_FINAL
    IDLE
    OUTPUT <raw provider text, scanned for saturation signals>
    HEARTBEAT [progress=0|1] [checkpoint=<free text>]

Fail-closed: unknown lines are IGNORED, an unknown/missing outcome
reconciles as STILL_OPEN and never completes work, and events for an
unknown slot are IGNORED_NO_SLOT (slots are opened explicitly so the pool
cap is never bypassed). This module never spawns windows or processes;
session start stays Kirby's injected ``start_session``.
"""
OUTCOMES = ("DONE", "BLOCKED", "STILL_OPEN", "FAILED_FINAL")

_REMAINDER_KEYS = ("checkpoint=", "reason=")


def parse_line(line):
    """Split one line into (kind, fields, raw_text). Returns (None, {}, "") for blank lines."""
    text = (line or "").strip()
    if not text:
        return None, {}, ""
    head, _, rest = text.partition(" ")
    kind = head.upper()
    fields, raw = {}, rest
    if kind in ("TURN_ENDED", "HEARTBEAT", "WORKKEY_READY"):
        fields, raw = {}, ""
        tokens, remainder = rest.split(), None
        for i, tok in enumerate(tokens):
            for key in _REMAINDER_KEYS:
                if tok.startswith(key):
                    remainder = " ".join([tok[len(key):]] + tokens[i + 1:])
                    fields[key[:-1]] = remainder.strip()
                    break
            if remainder is not None:
                break
            if "=" in tok:
                k, _, v = tok.partition("=")
                fields[k] = v
    return kind, fields, raw.strip()


def handle(kirby, slot, line):
    """Feed one provider line to Kirby for ``slot``. Returns a result string."""
    kind, fields, raw = parse_line(line)
    if kind is None:
        return "IGNORED"
    session = kirby.sessions.get(slot)
    if session is None:
        return "IGNORED_NO_SLOT"
    if kind == "IDLE":
        return kirby.wake(slot)
    if kind == "RECONNECTED":
        reconnected = kirby.reconnect_slot(slot)
        return reconnected.state
    if kind == "WORKKEY_READY":
        key = fields.get("key", "").strip()
        if not key:
            return "IGNORED"
        prio = int(fields["priority"]) if str(fields.get("priority", "")).isdigit() else 100
        deps = [d for d in fields.get("depends_on", "").split(",") if d]
        eff = fields.get("effect_class", "idempotent")
        kirby.add_workkeys([key], priority=prio, depends_on=deps, effect_class=eff)
        return kirby.wake(slot)
    if kind == "HEARTBEAT":
        kirby.heartbeat(slot, progress=fields.get("progress") == "1",
                        checkpoint=fields.get("checkpoint"))
        return "HEARTBEAT"
    if kind == "OUTPUT":
        receipt = kirby.on_provider_output(slot, raw)
        kirby.heartbeat(slot)                              # alive, but output is not progress
        return "ROTATED" if receipt else "OUTPUT"
    if kind == "TURN_ENDED":
        outcome = fields.get("outcome")
        outcome = outcome if outcome in OUTCOMES else "STILL_OPEN"
        sig_workkey = fields.get("workkey", "")
        sig_result_id = fields.get("result_id", "")
        sig_token = int(fields["token"]) if str(fields.get("token", "")).isdigit() else None
        if sig_workkey:
            target = kirby.workkeys.get(sig_workkey)
            if target is not None and target.state == "DONE":
                return "DUPLICATE_IGNORED"
            if session.workkey != sig_workkey:
                return "REJECTED_STALE_WRITER"
        if sig_result_id and any(w.result_id == sig_result_id and w.state == "DONE" for w in kirby.workkeys.values()):
            return "DUPLICATE_IGNORED"
        claimed = kirby.workkeys.get(session.workkey)
        if claimed is None or claimed.owner != session.session_id or claimed.token != session.token:
            if sig_token is not None and sig_token != session.token:
                return "REJECTED_STALE_WRITER"
            return kirby.wake(slot)                        # nothing claimed: reconcile only
        token_to_use = sig_token if sig_token is not None else session.token
        return kirby.on_turn_end(slot, outcome, token_to_use,
                                 checkpoint=fields.get("checkpoint", ""),
                                 reason=fields.get("reason", ""),
                                 workkey=sig_workkey or None,
                                 result_id=sig_result_id)
    return "IGNORED"


def drive(kirby, slot, lines):
    """Feed an iterable of provider lines. Never prequeues: call per batch of new lines."""
    return [handle(kirby, slot, line) for line in lines]


def read_new_lines(path, offset):
    """Incremental file read for the host loop: returns (lines, new_offset)."""
    with open(path, encoding="utf-8") as f:
        f.seek(offset)
        lines = [ln.rstrip("\n") for ln in f]
        return lines, f.tell()
