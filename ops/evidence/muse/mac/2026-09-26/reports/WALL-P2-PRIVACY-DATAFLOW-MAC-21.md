# WALL-P2-PRIVACY-DATAFLOW — draft MD (MUSE-MAC-21)

TASK_ID=WALL-P2-PRIVACY-DATAFLOW
STATUS=DONE
WORKER=MUSE-MAC-21 · HOST=MAC · MODE=READ_ONLY · 2026-09-26T14:53Z
EVIDENCE=static code reads only (HEAD 332a42f9). No keychain read, no secret
  touched, no credential executed. Wording is evidence-gated: what is shown
  below is what the code does, not a security audit.

## Where things run
- Server (`server/app.py`) binds 0.0.0.0:8080 (app.py:502) — LAN-reachable by
  default. Any pilot deployment must decide deliberately whether that binding
  stays; the code does not restrict it to localhost.
- Mac worker daemon + verifier run as local user processes on the Mac.
- Windows runtime is a separate scope (hard separation); this draft makes no
  Windows claims.

## Credentials: env first, keychain read-only where present
- Server requires COURIER_API_KEY + COURIER_VERIFIER_API_KEY from the
  environment and refuses to start without them (app.py:11-16); known
  insecure defaults ("dev-secret-key", "your_secure_api_key_here", "") are
  rejected fail-closed (app.py:17-22), and the verifier key must differ from
  the worker key (app.py:37).
- `revenue_worker_adapter.py:33-44` reads two items from macOS Keychain via
  `security find-generic-password` (courier_api_key, courier_server_url);
  failures are swallowed (`except: pass`) and the worker continues without
  them — i.e. keychain is best-effort, never a hard dependency, and nothing
  is ever WRITTEN to the keychain by this code.
- `register_social_channel.py:113` stores only a credential REFERENCE string
  (`MACOS_KEYCHAIN_<PLATFORM>_<SLUG>_PILOT`) as metadata — the secret itself
  never enters the channel registry. Publishing policy for registered
  channels defaults to REQUIRE_EXPLICIT_HUMAN_APPROVAL.

## Data flow (customer words, evidence behind each line)
- Tasks, results, and artifacts flow worker -> server over HTTP with Bearer
  auth (worker key) on every endpoint sampled (@require_auth throughout).
- Verification requires a SECOND, distinct key (@require_verifier_auth on
  /tasks/verify and /tasks/pending_verification) — the worker cannot certify
  its own result (test coverage: Z04 :173/:192).
- State lives in server/state/central_state.json (+ supervisor state.json);
  worker logs and snapshots sit beside the repo. No evidence of external
  exfiltration paths in the sampled code; full egress audit is NOT claimed
  here (would need dependency + network review — flagged as follow-up).

## What we tell the customer (safe claims only)
- "Your keys stay in your environment or your Mac keychain. Courier reads
  them; it never writes secrets anywhere."
- "Two separate keys: one for doing work, one for checking it. A worker
  cannot approve its own result."
- "Publishing anything externally always waits for your explicit approval."
- Do NOT yet claim: LAN-binding hardening, full egress audit, Windows
  credential story.

BLOCKER=NONE
NEXT=next pending P2 by wall priority
