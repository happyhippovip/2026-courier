# TURBO SHARD 09 — RUN_1 independent A-once witness (Post-Codex-Packet)

SHARD=09 (RUN_1 independent A-once witness)
STATUS=PACKET_READY (kein Codex → keine Aktualisierung an realer Evidence;
0 Executions, 0 Edits)
FILES=scripts/run1_physical/RUN1_A_ONCE_PROOF_CONTRACT.md,
scripts/run1_physical/verify_proof_contracts.py::verify_a_once,
server/app.py (claim 327-339, task_result 364-411),
scripts/mac_worker/daemon.py (run_muse/current_task.json)
CAUSAL_RISK=Aktuelle A-once-Prüfung zählt nur Snapshot-Counter
(process_a==1, REUSE WB01-Producer-Stub) — ein Zähler beweist keine
Einmal-Ausführung; Doppel-Dispatch mit losem Counter wäre unsichtbar.
MIN_FIX=Witness-Regel (Writer, post-Codex): A-once = EXAKT 1 dispatch_id
in central_state.json tasks[A] + EXAKT 1 gebundenes result (attempt/
dispatch-Identität) + Verifier-Record mit fremder verifier_id +
Artifact-Bytes-Hash serverseitig; Snapshot-Counter nur als Konsistenz-,
nie als Beweis-Feld (synthetic → reject).
MIN_TEST=Negativ-Test: fabrizierter Snapshot (counter=1, erfundene IDs)
muss FAILen (IDs nicht in central_state.json); Positiv-Test erst mit
echtem RUN_1-Evidence-Dir.
EVIDENCE=WB01-Producer-Befund (REUSE, nicht neu erklärt); claim-Mint
(app.py:329-331); Dup-Schutz (364-370); MAC11 (Assertions UNCHECKED —
gilt weiter bis echter Lauf).
OWNER=WINDOWS_ANTIGRAVITY_CENTRAL_WRITER
BEFORE_RUN1=YES (Verdikt-Regel vor RUN_1-PASS; Codex-Review selbst nicht betroffen)
DO_NOT_REPEAT_FINGERPRINT=museturbo-09-aonce-witness; musemac-producer-stub-bd539f18; musewb01-producer-packet
STATUS=DONE (1 Shard, kein zweiter)
