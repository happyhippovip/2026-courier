# L5 Desktop Hub — first vertical slices

The Desktop Hub shows Courier's canonical runtime state as three customer-facing
piles — **Needs you · Working · Done** — and relays human decisions to the
controller. It is a reader plus a relay. The controller (`courier_core`) remains
the only writer and the only authority.

## Run it

Against a real local Courier, with three real synthetic tasks (checked, blocked, running):

```
python -m courier_hub.demo            # prints the hub URL; Ctrl+C stops everything
```

Against an existing install:

```
python -m courier_hub --home <COURIER_HOME> --controller http://127.0.0.1:<port> --print-url
```

The hub binds `127.0.0.1` only. It needs nothing beyond the Python standard library
and the repository's own `courier_core`.

## Where truth comes from

| Shown | Source |
| --- | --- |
| Piles, cards, receipts | `<home>/courier.db`, read through a read-only `Journal` (the controller's own projection and events) |
| "Courier is running / isn't running / safe mode" | `GET /v1/health` on the controller |
| A decision on a Needs-you card | `POST /v1/tasks/<id>/resolve` (`effect_confirmed`, `retry_authorized`, `cancel`) with the desktop user as actor, the blocked attempt and a reason |
| Stop on a Working card | `POST /v1/tasks/<id>/cancel` with the desktop user as actor |

The hub keeps no state of its own. Restarting the hub, the controller or both
shows the same piles, because they are recomputed from the journal on every read.

## Projection rules (courier_hub/model.py)

| Runtime | Pile | Customer label |
| --- | --- | --- |
| QUEUED | Working | Waiting to start |
| CLAIMED, RUNNING, RETRY_PENDING | Working | In progress (recovery does not change the card) |
| VERIFYING, ACCEPTED | Working | Checking the result |
| any working state with stop requested | Working | Stopping |
| BLOCKED | Needs you | Did Courier manage to …? + It happened · Try once more · Stop here |
| COMPLETE, resolution verified | Done | Checked by Courier (the only check mark) |
| COMPLETE, resolution effect_confirmed | Done | Confirmed by *person* — Courier did not verify it |
| FAILED | Done | Couldn't complete this safely |
| CANCELLED | Done | Stopped |
| CANCELLED, resolution cancelled_effect_unknown | Done | Outcome uncertain — Courier stopped trying; the earlier action may already have happened |

A stop recorded after a non-idempotent action had already started keeps the label
"Stopped", but never says nothing happened: "Stopped after the action had started.
Part of it may already have happened." A runtime state the hub does not know is
shown as "State not recognised by this hub", with no actions.

"Try once more" asks for confirmation first and names the concrete consequence.
It is not offered once a stop has been requested. Internal ids (dispatch, attempt,
worker, effect key, event names) appear only in the receipt's "For support" section.

## When an answer is lost

| What happened | What the hub says |
| --- | --- |
| Controller not reachable: nothing was sent | "Courier isn't reachable right now. Nothing was sent." |
| Request sent, answer lost (the decision may be recorded) | "Courier may have recorded this, but its answer was lost", with the item as Courier has recorded it now |
| The browser lost its connection to the hub | "Couldn't confirm whether your decision arrived", then a refresh from the journal |
| The same decision repeated | "Already recorded"; the runtime keeps exactly one |
| A different decision about an already-decided question | "This no longer needs a decision" (stale), nothing changes |

## Quiet when idle

The hub re-reads the journal only when its head sequence changes. The page
re-renders only when what it shows changes (or once a minute for relative
times), and stops polling while its tab is hidden.

## Authority shown today

Working cards and receipts show "Courier may, without asking again" and "Courier
must ask before". These lines state only what the runtime enforces today: an
idempotent task may retry by itself; a non-idempotent task never repeats on its
own. Standing permissions granted ahead of time do not exist in the runtime yet,
and the hub says so.

## Security

- Binds `127.0.0.1` only.
- Refuses any request whose `Host` header is not the hub itself (DNS rebinding).
- Every POST must carry `X-Courier-Hub: 1` and a JSON body, so a web page cannot forge a decision.
- Strict Content-Security-Policy and no inline scripts.

## Tests

- `tests/hub/` (pytest) runs against the real controller and HTTP service: projection mapping, restart and reload, BLOCKED to Needs you, every Human Desk decision, duplicate and conflicting decisions, a lost answer after the controller recorded a decision, stale screens, controller offline, Working and stop (before and after start), receipts, idle reads, 500 tasks, and hostile requests.
- `tests/desktop/` (`node --test`) covers the page logic: rendering, distinct outcomes, connection and reconnect, single-flight decisions, response handling, escaping, keyboard reachability. Its fixture is generated from the Python model, and `tests/hub/test_hub_fixture.py` keeps the two in sync.

## Not yet

- No packaging into the Windows launcher (L6); see `docs/v1/L6_DESKTOP_HUB_WINDOWS_HANDOFF.md`.
- No push notifications, no mobile companion.
- No standing authority.
- No visual mapping onto the approved world: the styling is a neutral dark-glass placeholder.
