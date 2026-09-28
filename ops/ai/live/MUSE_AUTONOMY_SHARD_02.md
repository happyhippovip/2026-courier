# Autonomy Shard 02 — Decision-Continuation Recovery (READ_ONLY_C2)

SHARD=02
STATUS=SHARD_COMPLETE
OWNER=MUSE_C2_SAFFRON_OCCULT / HOST=MAC / 2026-09-28
SCOPE=crash between Chief-Decision and Next-Task-Dispatch.
READ: scripts/consume_chief_command.py (full, 222 lines),
 scripts/queue_processor.py (full, 25), scripts/intake_dispatcher.py (full, 74).
0 executions, 0 edits, 0 ledger, MAX_HEAVY respected (abstention).
PEERS: .muse_swarm/done=01; claims 03-12 peer-active (untouched, no overlap:
 mine is the only decision-continuation lane).

SUBCASES_DONE=5 (S1,S2,S3-reuse,S4,S5)
S1 Crash after validate+execute, before processed write (consume :199-202):
 re-run re-executes deterministically; execution is side-effect-free
 (files_changed=0, summary strings only, :173-184) → no lost work, no
 harmful duplicate. DISPROVEN (lost-work risk).
S2 Torn processed write (:202 direct write_text, no tmp/fsync/replace) +
 dedupe skips corrupt files (:54-56 `except: continue`) → retry misses the
 torn result → silent duplicate execution + same-name overwrite (:201).
 CONFIRMED_SOURCE_DEFECT → P1.
S3 Dispatch-side crash window (intake :26 gh-run → :65 state write with
 fresh uuid :11; queue :18 dispatch BEFORE :19 move) → duplicate external
 dispatch on retry. REUSE — established Q1/Q3 writer-lane findings
 (DUPLICATE_SKIP, not re-reported as new).
S4 Concurrent-consumer TOCTOU (glob+read, no lock, :46-60) → DISPROVEN for
 sanctioned single-process deploy (pins single process; cf. WHAT-IS-LEFT I).
 Multi-proc residual noted, needs deployment model (not packetized).
S5 Dedupe scope misses incoming duplicates: validate scans only
 [processed_dir] (:107) though incoming_dir is available (:63,:166) → two
 identical command files both validate; plus processed filename keys on
 task_id not message_id (:201) → last-wins silent overwrite.
 CONFIRMED_SOURCE_DEFECT → P2.

CONFIRMED_SOURCE_DEFECTS=S2 (torn-write + skip-corrupt dedupe), S5
 (incoming-blind dedupe + task_id-collision filename)
EVIDENCE_GAPS=(none new; S4 multi-proc model is owner-known deployment
 question, not evidence)
DISPROVEN=S1 (lost-work), S4-sanctioned (concurrent double-exec),
 S3-as-new (reuse Q1/Q3)
FIX_PACKETS=
 P1 FILES=scripts/consume_chief_command.py
 CAUSAL_BUG=torn JSON in processed_dir is skipped by dedupe (:54-56) so a
 crashed write retries as fresh execution (:202 non-atomic).
 MIN_FIX=atomic write (tmp+fsync+replace) for processed_file; dedupe
 fail-closed on unreadable processed file (treat as present → park for
 human/owner review instead of `continue`).
 TARGETED_TEST=kill -9 during write → retry must park, not duplicate
 (crash-injection, owner lane). OWNER=chief-lane writer. LATER.
 P2 FILES=scripts/consume_chief_command.py
 CAUSAL_BUG=validate_command dedupes against processed_dir only (:107);
 incoming_dir with identical message_id passes twice; processed filename
 (:201) keys on task_id so second result silently overwrites first.
 MIN_FIX=check_dedupe([processed_dir, incoming_dir]) using already-passed
 incoming_dir; processed filename keyed on message_id (+ task_id index
 line inside payload).
 TARGETED_TEST=drop identical command twice → second must VALID-fail as
 duplicate. OWNER=chief-lane writer. LATER.
NEXT_OWNER=chief-lane writer (P1+P2); G-lane untouched; queue/intake (S3)
 stays with intake writer lane.
DO_NOT_REPEAT_FINGERPRINT=sha256-muse-shard-02-deccont-01
