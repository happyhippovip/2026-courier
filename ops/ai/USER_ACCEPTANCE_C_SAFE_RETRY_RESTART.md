# User Acceptance C — Failure / Retry / Restart: "Kann ich sicher Retry/Restart machen?"

Status: OPERATOR ACCEPTANCE (USER WINDOW) — 2026-09-28
Product Shell: NOT unlocked. Prep-only. NO script edits in this pass (writer scope).

## USER_PROBLEM
A normal user/operator asking "kann ich sicher Retry/Restart machen?" gets
procedures that fail dangerously: the RUN_1/RUN_2 operator path cannot work as
written and can clobber live state and kill the wrong process.

## CURRENT_RUNTIME_TRUTH (verified by reads, shell down, no execution)
- `scripts/mac_worker/run_1_mac.sh:20` starts `python3 -m server.app --port=8080
  --db=ledger_run1.db`, but `server/app.py` has NO argument parsing
  (`server/app.py:559-560` hardcodes `app.run(host="0.0.0.0", port=8080)`).
  `--db` is silently ignored; state goes to `server/state/central_state.json`
  (`server/app.py:11`) — the LIVE state file. Isolation fails silently and
  `ledger_run1.db` (touched at `:10`) stays an empty decoy.
- "Worker" step (`run_1_mac.sh:27`) runs `python3 -m scripts.integration_contract`,
  which has NO `__main__`/loop/poll logic (pure packet library) → no-op, empty log,
  Task A can never execute.
- "Verifier" step (`run_1_mac.sh:31`) passes `--target=A`, but
  `scripts/courier_verifier.py:175-176` is bare `run_loop()` with no argv parsing
  (`--target` ignored) and `run_loop` sleeps/polls indefinitely (`:173`) in the
  FOREGROUND → the script blocks forever; evidence steps are never reached.
- No trap/cleanup: Ctrl-C/interrupt orphans the background server on 8080, so the
  next run aborts at the port check. Worker PID is never saved.
- `scripts/mac_worker/run_2_mac.sh:9-14` does `kill -9 $(cat logs/server.pid)` with
  ZERO ownership check (PID-reuse can kill an unrelated process), then removes the
  pidfile unconditionally.
- Retry taxonomy is doc-only: 0 hits for RETRY_IMMEDIATE/HUMAN_ACTION_REQUIRED/
  RESOURCE_GUARD/RETRY_EXHAUSTED/COOLDOWN_REQUIRED in `server/`+`scripts/`.
- Spec drift: `ops/ai/PROVIDER_ISOLATION_SPEC.md:16` says tasks move back to
  "PENDING" — no PENDING task status exists in the server.
- GOVERNED PATHS THAT DO EXIST: `POST /tasks/<id>/resume`
  (`server/app.py:516`, retry; force_success refused), `POST /tasks/reclaim_stale`
  (`:412`), ACK_DUPLICATE on resend (`:365-369`).

## ACCEPTANCE_REQUIREMENT
C-1: Every operator-facing run/retry/restart procedure MUST execute end-to-end
  against REAL entrypoints (no ignored flags, no no-op modules, no vapor args).
C-2: Preflight MUST verify isolation explicitly: which state file, which port,
  which processes (ownership-checked), and refuse to start otherwise.
C-3: Interrupt (Ctrl-C/timeout) MUST clean up owned processes; background PIDs MUST
  be saved + ownership-verified before any signal; `kill -9` on an unverified PID
  is FORBIDDEN.
C-4: Safe retry for users = the governed task paths (resume/reclaim/ACK_DUPLICATE),
  surfaced with plain-language guidance (links item B). Raw process killing is
  never presented as a user action.

## MISSING_SYSTEM_SUPPORT
- Corrected run scripts + real worker entrypoint wiring (Central Writer scope).
- Preflight + ownership-check + trap/cleanup in operator scripts.
- User-facing retry guidance for resume/reclaim paths.

## PREPARABLE_NOW (no code, this pass)
- This requirement + preflight checklist (state file assertion, port assertion,
  PID ownership rule: pid + start-identity match before signal).

## BLOCKED_UNTIL
- Central Writer repair (out of this window's scope) + Mac physical runner.
- No physical RUNs from this window, ever.

## NEXT
D — Proof/Verifikation (item D file).
