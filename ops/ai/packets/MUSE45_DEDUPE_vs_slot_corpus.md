# MUSE-45 DEDUPE — my T-A..T-K vs predecessor slot corpus (correction packet)

MISSION=COURIER_LIVE_SHOW_CONTINUE, slot MUSE-45, date 2026-09-26.
Cause: I worked T-A..T-K WITHOUT first inventorying runtime/slots/MUSE-45/,
which holds ~35 predecessor reports (T8-T25, VERIFY_*, CLAIM/CHECKPOINT, 3 prior
sessions same mission). Several of my packets duplicate that corpus. This packet
maps DUPLICATE (predecessor primary, mine = independent re-verification) vs
NOVEL (genuinely new), so no finding is double-counted.

## DUPLICATE — predecessor primary (mine corroborates at later tree state)

- T-A core (16 DONE, 16 logs, 4/3/2/1 staged pattern): duplicates
  VERIFY_done_slots.md + T18_verify_logs_delta.md (they found the logs first).
- T-B wiring + F1/F2: duplicates T8_service_bootstrap.md (theirs deeper; I MISSED
  F-T8-2 AtLogon-not-boot MEDIUM + venv-ordering/log-homes/handshake — my gap).
- T-C V1/V2: duplicates VERIFY_dlq07_dlq08.md (theirs deeper: pool-exhaustion
  residual with max_workers=5). S1/S2/S3 duplicate T13_backlog_dedupe.md
  (D-T13-3/D-T13-1) + T11 line-pin drift notes.
- T-E dedupe section: duplicates T13 (shallower; I missed D-T13-2/D-T13-4).
- T-F portability: duplicates T9_portability.md + T23 + PORTABILITY_mac_win.md.
- T-H replenish locus: duplicates T12_queue_wiring.md (theirs deeper:
  rejection-reason finding).
- T-I DLQ pins: corroborates BACKLOG_corroboration.md + T11 drift pattern.
- T26 queued "dispatcher/validator coverage spot": ALREADY covered by
  T10_testgap_repo.md (DIRECT/SUBPROCESS/ZERO map, G-T10-1/G-T10-4). NOT redone;
  instead reverified below (T20-pattern).

## NOVEL — first recorded in MUSE-45 corpus (verified by slot-wide grep)

- T-A delta: Google-07:45-checkpoint cross-check (active_limit OK; provider flag;
  queue.db + 65/65 without tree evidence). Time-novel: checkpoint postdates
  predecessor sessions.
- T-B/F3: stop.bat overbroad CIM kill (test-pinned legacy — new to corpus).
- T-B/F4: orphaned launchers server/start_server.bat + windows_worker/start.py
  (0 refs; T8 listed one as "manual", not as orphan).
- T-D/G1: zero test coverage for the courier_continue 8s hang-abandon path
  (both "hung" candidates ruled out by scope). CONFIRMED gap.
- T-D/G2: shipped-config tests pin provider_launch_enabled=false (resolves the
  checkpoint/tree flag conflict; WALL_config_note covered other keys).
- T-E/R1+R2: duplicate artifacts block (run_chief_commander.py:627-630) +
  claim_task stray blanks still present (cosmetic residues, not in T11).
- T-F freshness + stop contrast: time-novel re-scan (no foreign movement) +
  wall-stop exact-identity precedent for F3's fix direction.
- T-G queue.db angle: absent-from-tree is EXPECTED (gitignored state/) yet 2
  TestQueueDBSchema tests require a live daemon run first (fresh-checkout red).
- T-H hygiene: test_auto_replenishment deletes ~/.courier_runtime home state,
  hardcoded test keys, fixed port 8081 (collision surface; other contexts only
  in T9/T11/T14).
- T-J: WIN-01..05 all WORKING (vs T15 census 16/1/47) — live foreign scale-up.
- T-K/H1: soak_test.py runs on live root and would overwrite foreign DONE
  states (start/stop set IDLE/READY unconditionally). Predecessors only
  inventoried the file.

## T26-reverify (T10 verdicts at current tree, no new topic opened)

- Positive refs re-confirmed: courier_github_dispatcher, intake_dispatcher,
  courier_verifier referenced by 5 test files (auto_replenishment, github_
  dispatcher, intake_dispatcher_state_guards, server_integration_contract,
  tomato_two_torture). Matches T10 DIRECT/SUBPROCESS verdicts.
- ZERO verdicts re-confirmed: task_routing, validate_chief_relay,
  validate_courier_task, start_verifier have 0 test references. G-T10-1/G-T10-4
  still OPEN. No drift since T10.

## Going forward (this session)

- No new T- topics that the corpus covers. Novel-only packets from here.
- Predecessor discipline adopted: corroboration notes go to my slot dir;
  ops/ai/packets/ only for NOVEL findings (this packet corrects the 10 prior).
- My 10 packets stand as evidence (point-in-time, independently re-verified
  pins) but primacy belongs to the slot files listed above wherever overlapping.
