# Native delivery (ADR 25011 D22, gate `MUSE_EXPERIMENTAL_NATIVE_CONNECTOR_DELIVERY`)

Read this when your transcript shows a `◆ Message from <name> · <lane> · <inbox> · <time>`
row, or when your starter prompt said "Arm nothing".

## What the daemon sees

- Each connector message is delivered to your session as a session message and
  wakes you the way a peer message does; the row's `└` line is the requester's
  text. Answer with `reply --to <lane>` exactly as for a printed line.
- A row ending `· owned by <lane session>` is the operator's copy of a message a
  live coordinator already received. It costs you nothing: no turn, no reply.
- A row ending `· owner gone · relaunching` is a follow-up whose coordinator lane
  is dead. Your single call is `delegate`, the same as for an `[unattended]` line.
- Every `delegate` / `reply` / `start` / `recover` prints a `summary` field; the tool
  row shows it as its `└` line, so there is nothing to narrate afterwards.
- Forwarding is at-least-once: after a listener restart the same message can
  arrive a second time as a second row. Answer it once; a repeat is not a new
  request.
- Slack is not forwarded in this slice: a Slack `listen` refuses while the gate is
  on. Arm Slack only with the gate off.

## What the coordinator sees

- The starter says "Arm nothing" because the daemon's listener forwards every
  later message of the conversation to the coordinator's own session as the
  same `◆ Message from …` row. It finds that session in the registry row, so
  the coordinator's first call is one `daemon_registry.py bind … --muse-session-id
  <its own session id>`; then the work, in the same turn.
- Nothing to re-arm after a stop; the conversation stays with the session for as
  long as it lives.

## Replying (the same contract as the printed-line path)

- Ordinary markdown, any length; Slack renders bold, bullets, code fences and
  `[label](url)` links (`markdown_text`, #29362). No lane ids or template words in the text.
- More than one step, or over about a minute, starts with the plan as your
  first reply (posted once) — `*Plan*` on its own line, one sentence on what
  and how, then one `☐ <step> — <how, or what it produces>` line per step —
  and right after each step finishes the next call re-sends the whole plan
  with that step `✅` through `reply --replace-last`, never batched at the
  end; never `- [ ]` / `- [x]` (Slack strips markdown task lists). The
  handoff's `reply_shapes` holds a worked plan.
- Multi-line text goes on stdin (the `<<'MSG'` heredoc, the one taught form):
  a double-quoted `\n` is unescaped only when the text has no real newline
  (spec 23499 FR-017), so mixed text would keep a raw backslash-n.

## Why the flag is always on the arm

The model cannot inspect the gate (environment variables are never echoed), so
the arm in the skill body (`SKILL.md` § Onboard a connector) carries the
daemon's session id unconditionally; the listener ignores the flag with the
gate off and requires it with the gate on.
