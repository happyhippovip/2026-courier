# Shard 04 — Consumed-Decision Idempotency (READ_ONLY_C2)
- BASE=ee2bb49b | DATE=2026-09-28 | GATE: uncommitted DURABLE/YES vs committed PENDING (nicht revalidiert)
- SCOPE-FILES: scripts/consume_chief_command.py (157-204, 46-60, 105-108), scripts/run_chief_relay_cycle.py (34-62, 147-168), tests/test_run_chief_relay_cycle.py (mock-only)

SHARD=04
STATUS=SHARD_DONE (4 Subcases, 0 Source-Edits, keine Runs)
SUBCASES_DONE=S1-redelivery-ACK, S2-taskfile-overwrite, S3-torn-write-replay, S4-check-then-act-race
CONFIRMED_SOURCE_DEFECTS=S2, S3, S4 (alle low; unattended-Autonomie-Relevanz)
EVIDENCE_GAPS=S1 (kein idempotenter ACK-Pfad spezifiziert)
DISPROVEN=keine (Message-ID-Dedupe selbst funktioniert: parent_id/message_id-Abgleich consumer:57-59 + relay:56)
FIX_PACKETS=1 (S2+S3+S4, ein Owner, eine Datei-Familie)
NEXT_OWNER=Central Writer (Fix) / Chief-Relay-Owner (ACK-Policy für S1)
DO_NOT_REPEAT=RESULT_RECEIVED/VPV/S2-wall/MAC09-SUCCESS-Fix/MAC03-empty/Server-fsync/T-antigravity-intern

## S1 Redelivery ohne idempotenten ACK → EVIDENCE_GAP (minor)
- Wiederholung desselben Commands nach Erfolg → validate failt mit CONSUMER_ERROR/Duplicate (consumer:107-108) statt ACK. Für max_iterations=1 + nicht-redelivernden Chief heute ok; unattended Redelivery würde Endlos-Fail loopen. Policy fehlt.

## S2 Gleiches task_id, neue message_id → stiller Overwrite → DEFECT
- Dedupe-Key (message_id/parent_id) vs Publish-Key ({task_id}-result.json, consumer:201, relay:166): zweite Decision zur selben Task überschreibt Ergebnis ohne Konflikt. Relay prüft ebenfalls nur message-Ebene (relay:51-56). FIX: Task-Level-Kollision → FAIL statt Overwrite.

## S3 Torn-Write + Skip-Corrupt → Replay-Loch → DEFECT
- Publish via plain write_text (consumer:202, kein tmp/replace); check_dedupe überspringt korrupte Files still (consumer:55-56) → nach Crash mid-write gilt Decision als unverbraucht → Doppel-Ausführung. FIX: atomic write.

## S4 Check-then-Act ohne Lock → DEFECT (concurrency)
- check_dedupe-Glob (consumer:46-60) + Publish (consumer:200-202) ohne Lock; zwei konkurrierende Consumer können beide passieren → Doppel-Publish. Heute single-operator-low-risk; Autonomie-Ziel verlangt koordinierte Exklusivität. FIX: Lock oder atomic-create.

FIX_PACKET: FILES=scripts/consume_chief_command.py (+relay-Aufrufer für S1-Policy); CAUSAL_BUG=Publish-Key task_id ohne Task-Kollisionsschutz, non-atomic write, lockloser Check-then-Act; MIN_FIX=exists-Check auf {task_id}-result.json→FAIL + tmp/replace-Publish + exklusiver Lock um Check+Write; TARGETED_TEST=瓶颈: redeliver-same-task-new-msg→FAIL, kill-mid-write→kein Re-Exec, 2×konkurrent→genau 1 Publish; OWNER=Central Writer; BEFORE_RUN1|LATER=LATER (Chief-Relay-Pfad, kein RUN_1/2-Pfad; S1-Policy davor klären)
