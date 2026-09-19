# WORK SCRIPT — optional existing-session trigger

## User scope correction — 2026-09-18

WORK SCRIPT is a feature of the separate Courier Symphony application/package,
not an automation attached to the user's currently working Mac Muse or CLI.
The existing Mac installation is protected: do not inject prompts, attach to its
personal sessions, restart processes, install hooks, change shortcuts, settings,
authentication, permissions or startup behavior. Do not activate anything there.

Any future integration below refers ONLY to an explicitly selected, application-
owned session in that separate product, after its owner authorizes the boundary.
The fact that the product is developed or installed on this Mac is NOT permission
to reuse the user's live Muse/terminal session. Keep the preview disconnected.
This correction supersedes the earlier request to identify the user's live CLI
window for input delivery. Product packaging and integration remain unverified.

Implemented: OFF/ON control, 120s deterministic checks, 2s CSS-only green pulse,
single-flight check, same-origin cross-tab lock, local durable submission journal,
no unchanged-fingerprint resend, fail-closed uncertainty, and no resume on reload.
No running task is killed when OFF is pressed. A hidden/sleeping browser may
delay timers; exact wall-clock frequency and overnight operation are not promised.

Live status: **NOT CONNECTED**. index.html is a disconnected integration preview,
not the user's working Muse CLI. No model/provider process is started by this module.
No keyboard/clipboard hooks, shell command, terminal setting, auth changes, task
creation, scheduler, or Goal creation. No Windows physical behavior is claimed.

The existing studio/muse-bench only appends a queue file and has no existing-session
input transport. The pre_courier_muse runner starts a fresh agy process using a
permission bypass and cannot be used. Existing studio/backend files remain owner-held.

## Integration by the existing UI/CLI owner

Import mountWorkScript from widget.mjs and pass a host element and an existing
owner-controlled adapter. Do not load adapters or endpoints from user/URL data.
Required adapter contract: `courier-existing-session-resume/v1`.

`inspect({signal})` returns contract + status BUSY, IDLE, BLOCKED or READY.
READY includes a grant with operation_id, goal_id, task_id, attempt_id,
fingerprint, session_id, runtime_id, lease_token, expires_at (Unix ms),
session_idle, scope_owned, allowed, cost_authorized, human_gate.
The grant is from the canonical authority, not the model or client fields.

`submit({grant,prompt,idempotency_key,signal})` must ATOMICALLY authenticate,
revalidate current task/lease/session/process, check current permissions/budget,
reserve canonical idempotency and route to exactly that idle existing session.
No key injection into the active OS window and no new provider launch. A busy or
changed session must reject. Receipt binds operation_id, task_id and session_id
and status ACCEPTED/REJECTED. ACCEPTED is delivery only, never task COMPLETED.
Global replay/race safety belongs to this existing authority; browser locks are
same-origin only and cannot prove cross-device uniqueness. No such backend was
available or implemented here. Do not map the current queue-only endpoint to this
adapter and claim that a running CLI received anything.

Browser ACK timeout, crash or storage failure leaves a PENDING journal entry.
Do not delete it to resume blindly. Owner must reconcile against durable canonical
delivery evidence; no automated retry on ambiguity. OFF aborts pending client I/O,
but cannot recall an already delivered prompt. Cleared storage is not permission
to replay: backend idempotency remains required. No secrets/lease tokens stored
in the browser journal; storage contains task keys and delivery states only.

Test: `node --test work-script/controller.test.mjs`. Fake adapter and fake clock;
passing these tests proves local controller logic, not production CLI delivery.

Owner handoff: identify the separate Courier application/package and its explicitly
application-owned session; the product UI owner provides the authenticated
input/idle adapter. Do not request access to or connect the user's working Mac CLI.
Do not release or reset another worker's lease. Keep the live toggle off until
that boundary is implemented and accepted.
