# MUSE-45 T-O — daemon.py + runtime_state.py review (read-only)

Branch fix-cb1-new @ 329abd80. daemon.py read 1-592 (whole exec/claim/deliver
path) + runtime_state.py 1-121 (whole). Shell DOWN; static only. No edits.
First MUSE-45 review of these files.

## Verified strengths (OBSERVED)

- Phase machine: CLAIMED->STARTED->RESULT_PENDING->RESULT_READY->deliver;
  STARTED never replayed (:452-460, released to recovery); legacy phaseless
  treated as STARTED (:76-77, :426-427); RECOVERY_BLOCKED retains result on
  storage failure (:441-449, :589-592); RESULT durable before delivery
  (:557-563); 4xx REJECTED->RELEASE_PENDING persisted-then-released (:572-581).
- run_muse: timeout min(cfg,3600)s + 8MB cap (:368-372), nonzero-exit ambiguous
  no-retry (:378-379), cleanup_group verified post-run, ORPHANS_REMAIN blocks
  new execution (:384-389).
- Delivery: 4xx-final vs transport/5xx-retryable split (:153-159), 8 attempts
  exp backoff (:205-217); result_id/run_id uuid per execution, reused verbatim
  on redelivery (:547-548, :568) = idempotent redeliver.
- Artifact chain: path safety (:219-225), hash at collect (:227-248, missing/
  unsafe demotes SUCCESS->FAILED), re-hash before upload (:190), server-echo
  check + art- prefix (:199), per-artifact persist (:202).
- Gates: single-daemon flock (:392-402), orphan gate (:136-142), binding checks
  (:118-133), STOP honored (:450-451, :492-493, :513-515), claim under
  admission lock + resource gate (:491-498), API-key FATAL exit(2) (:415-417).
- runtime_state: textbook atomic_json (mkstemp+fsync+replace+dir-fsync :34-47),
  fail-loud corrupt state (:16-23), revalidating cleanup_group (:90-121).

## Findings

- O4 MEDIUM: NATIVE echo runs the FULL task instruction via shell=True.
  daemon.py:259-262 allowlists by FIRST WORD only, then :275 executes the
  entire instruction string (`subprocess.run(instruction, shell=True,
  executable="/bin/bash")`). "echo ok; <anything>" passes the gate and runs
  everything. Reachability chain: :522-524 auto-reroutes mac+ANTIGRAVITY tasks
  mentioning "echo" into NATIVE. Exploitability hinges on the task-author
  trust boundary (server API-key holders; boundary strength UNKNOWN from
  here). Owner decision: argv-echo/quote, or restrict NATIVE to trusted lanes.
  Not fixed here (foreign scope, no runner).
- O3 LOW (feeds O4): :522-524 sniffs instruction CONTENT ("echo" substring)
  to switch execution mode. Content-driven mode switch in prod path.
- O5 LOW: run_agy passes --dangerously-skip-permissions (:301), 300s timeout
  but NO output cap (vs 8MB in run_muse); communicate() buffers unbounded.
- O6 LOW: bare `except:` at :315 swallows even KeyboardInterrupt during agy
  output parse; loop continues instead of clean shutdown.
- O2 LOW: corrupt current_task.json crashes daemon at startup (:423-425 plain
  json.load outside try). Contained by supervisor (fast-exit -> PAUSED_ERROR),
  but message is a bare traceback.
- O1 INFO: runtime_state.py:61 docstring claims fingerprint includes
  "executable", but code hashes pid/pgid/lstart only (comm deliberately
  excluded :69-71). Doc overclaims; code is the safer choice.

## Verdict

Worker core is as disciplined as its supervisor except O4, the one MEDIUM:
a first-word allowlist over a full-string shell. Everything else LOW/INFO.
Owner triage required for O4's trust boundary; no action by me.
