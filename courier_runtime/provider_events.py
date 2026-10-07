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
    if kind in ("TURN_ENDED", "HEARTBEAT"):
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
    if kind == "HEARTBEAT":
        kirby.heartbeat(slot, progress=fields.get("progress") == "1",
                        checkpoint=fields.get("checkpoint"))
        return "HEARTBEAT"
    if kind == "OUTPUT":
        receipt = kirby.on_provider_output(slot, raw)
        kirby.heartbeat(slot)                              # alive, but output is not progress
        if receipt and receipt.get("action") == "RECOVERY_BLOCKED":
            return "RECOVERY_BLOCKED"
        return "ROTATED" if receipt else "OUTPUT"
    if kind == "TURN_ENDED":
        outcome = fields.get("outcome")
        outcome = outcome if outcome in OUTCOMES else "STILL_OPEN"
        claimed = kirby.workkeys.get(session.workkey)
        if claimed is None or claimed.owner != session.session_id or claimed.token != session.token:
            return kirby.wake(slot)                        # nothing claimed: reconcile only
        return kirby.on_turn_end(slot, outcome, session.token,
                                 checkpoint=fields.get("checkpoint", ""),
                                 reason=fields.get("reason", ""))
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
