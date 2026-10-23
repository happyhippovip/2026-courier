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
cap is never bypassed). A TURN_ENDED outcome=DONE line is not a workkey
final: without a ledger engine it returns NOT_PROVEN, and with one it
calls LedgerEngine.finish_turn, which marks DONE only when that workkey's
task has a journal RESULT_ACCEPTED. This module never spawns windows or
processes; session start stays Kirby's injected ``start_session``.
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


def _campaign_lock(kirby):
    """The lock LedgerEngine.finish_turn already uses. Not a second writer."""
    from courier_runtime.ledger_engine import _exclusive
    return _exclusive(kirby.path.with_suffix(kirby.path.suffix + ".lock"))


def _reload(kirby):
    """Replace this Kirby image with the campaign file.

    finish_turn saves a different Kirby under the campaign lock. The caller's
    object would otherwise keep CLAIMED and the next IDLE or HEARTBEAT would
    write that stale image over a journal-proven DONE. A missing file is left
    alone: loading it would wipe workkeys that have not been saved yet.
    """
    if kirby.path.exists():
        kirby._load()


def _finish_proven_done(kirby, slot, fields, engine):
    """DONE with an engine. finish_turn takes the campaign lock itself, so this
    must not already hold it."""
    with _campaign_lock(kirby):
        _reload(kirby)
        session = kirby.sessions.get(slot)
        if session is None:
            return "IGNORED_NO_SLOT"
        claimed = kirby.workkeys.get(session.workkey)
        if claimed is None or claimed.owner != session.session_id or claimed.token != session.token:
            return kirby.wake(slot)
        if not session.accepting:
            return "REJECTED_STALE_WRITER"
        workkey, token = session.workkey, session.token
        checkpoint = fields.get("checkpoint", "")
    from courier_runtime.ledger_engine import task_id_for
    result = engine.finish_turn(slot, workkey, token, task_id_for(workkey), checkpoint=checkpoint)
    with _campaign_lock(kirby):
        _reload(kirby)
    return result


def _handle_under_lock(kirby, slot, kind, fields, raw):
    _reload(kirby)
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
        if outcome == "DONE":
            # No engine: a DONE line is not proof and must not finalise.
            if not session.accepting:
                return "REJECTED_STALE_WRITER"
            return "NOT_PROVEN"
        return kirby.on_turn_end(slot, outcome, session.token,
                                 checkpoint=fields.get("checkpoint", ""),
                                 reason=fields.get("reason", ""))
    return "IGNORED"


def handle(kirby, slot, line, engine=None):
    """Feed one provider line to Kirby for ``slot``. Returns a result string.

    ``engine``, when given, is the LedgerEngine that may finalise a DONE
    signal. A DONE signal never calls Kirby.on_turn_end directly.
    """
    kind, fields, raw = parse_line(line)
    if kind is None:
        return "IGNORED"
    if kind == "TURN_ENDED":
        outcome = fields.get("outcome")
        outcome = outcome if outcome in OUTCOMES else "STILL_OPEN"
        if outcome == "DONE" and engine is not None:
            return _finish_proven_done(kirby, slot, fields, engine)
    with _campaign_lock(kirby):
        return _handle_under_lock(kirby, slot, kind, fields, raw)


def drive(kirby, slot, lines, engine=None):
    """Feed an iterable of provider lines. Never prequeues: call per batch of new lines."""
    return [handle(kirby, slot, line, engine=engine) for line in lines]


def read_new_lines(path, offset):
    """Return only newline-terminated records and a physical byte offset.

    A provider may be interrupted halfway through a write, including a UTF-8
    character. Preserve that suffix for the next read, never promote a partial
    DONE record. A malformed complete record is ignored as a whole rather
    than poisoning all later signals or decoding into a valid terminal event.
    """
    with open(path, "rb") as f:
        f.seek(offset)
        data = f.read()
    end = data.rfind(b"\n") + 1
    lines = []
    for record in data[:end].split(b"\n")[:-1]:
        if record.endswith(b"\r"):
            record = record[:-1]  # CRLF (Windows) provider logs: normalize at the boundary
        try:
            lines.append(record.decode("utf-8"))
        except UnicodeDecodeError:
            lines.append("INVALID_UTF8")  # unknown protocol kind: fail closed
    return lines, offset + end
