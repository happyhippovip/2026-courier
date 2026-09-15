# V1 ENDGAME M3 — PHYSICAL WINDOWS QUALIFICATION PACK

1. MAC CANONICAL REQUEST -> ATOMIC PUBLICATION
AUTHORITATIVE FILE/STATE: coordination/mac_to_windows/requests/<req_id>.json
BEFORE: Missing
ACTION: mac_request_producer.py writes via temp file atomic rename
EXPECTED AFTER: Present and valid schema 1.0
REQUIRED FINGERPRINT/IDENTITY: windows_validation_request_id = <req_id>
PASS: File appears atomically without partial read
FAIL: File locked or corrupt
CRASH/RESTART EXPECTATION: If crash before rename, no file; if after, valid file.

2. WINDOWS NATIVE DISCOVERY
AUTHORITATIVE FILE/STATE: Windows local memory / discovery log
BEFORE: Unaware of <req_id>
ACTION: Windows loop scans requests/ directory
EXPECTED AFTER: <req_id> added to processing queue
REQUIRED FINGERPRINT/IDENTITY: windows_validation_request_id
PASS: Discovers and initiates claim
FAIL: Ignores request or crashes parsing
CRASH/RESTART EXPECTATION: Restart re-discovers from disk.

3. WINDOWS CLAIM PERSISTENCE
AUTHORITATIVE FILE/STATE: coordination/windows_to_mac/claims/<req_id>.claim.json
BEFORE: Missing
ACTION: Windows OS-atomic exclusive write
EXPECTED AFTER: Claim file present, holding Windows pid
REQUIRED FINGERPRINT/IDENTITY: node_id + <req_id>
PASS: Exclusive claim successful
FAIL: FileExistsError (duplicate claim prevention)
CRASH/RESTART EXPECTATION: Orphan claim reconciled via heartbeat/pid expiry.

4. WINDOWS EFFECT OWNERSHIP
AUTHORITATIVE FILE/STATE: Windows local worker process memory
BEFORE: Idle
ACTION: Execute required workload (e.g. create test file)
EXPECTED AFTER: Effect created on Windows filesystem
REQUIRED FINGERPRINT/IDENTITY: process identity bound to <req_id>
PASS: Effect exactly matches request parameters
FAIL: Effect missing or mutated wrong scope
CRASH/RESTART EXPECTATION: Restart causes Re-Discovery -> Claim -> Replay.

5. WINDOWS INDEPENDENT RESULT CUSTOMS
AUTHORITATIVE FILE/STATE: Windows memory / verification routines
BEFORE: Unverified
ACTION: Windows self-inspects the created effect
EXPECTED AFTER: Verification PASS
REQUIRED FINGERPRINT/IDENTITY: Canonical effect hash
PASS: Customs logic validates effect presence
FAIL: Customs rejects effect
CRASH/RESTART EXPECTATION: Reruns verification if result not yet atomic.

6. ATOMIC WINDOWS RESULT
AUTHORITATIVE FILE/STATE: coordination/windows_to_mac/results/<req_id>.res.json
BEFORE: Missing
ACTION: Atomic rename write of result data
EXPECTED AFTER: Result file present
REQUIRED FINGERPRINT/IDENTITY: result_fingerprint = sha256(request_id + status + observed_behavior)
PASS: File appears atomically
FAIL: Truncated or missing
CRASH/RESTART EXPECTATION: Safe retry if crash before rename.

7. MAC NATIVE CONSUMPTION
AUTHORITATIVE FILE/STATE: Mac local memory (mac_result_consumer.py)
BEFORE: Unaware of result
ACTION: Scans results/ directory for <req_id>.res.json
EXPECTED AFTER: Parses result JSON
REQUIRED FINGERPRINT/IDENTITY: <req_id>
PASS: Parses successfully
FAIL: Skips if truncated or missing schema_version
CRASH/RESTART EXPECTATION: Re-scans on restart.

8. FINGERPRINT VERIFICATION
AUTHORITATIVE FILE/STATE: Mac memory
BEFORE: Untrusted
ACTION: Re-hashes (request_id + status + observed_behavior) and compares to result_fingerprint
EXPECTED AFTER: Match
REQUIRED FINGERPRINT/IDENTITY: result_fingerprint
PASS: Hashes match exactly
FAIL: Reject as FINGERPRINT INVALID
CRASH/RESTART EXPECTATION: Pure function, stateless.

9. ACK
AUTHORITATIVE FILE/STATE: coordination/mac_to_windows/acks/<req_id>.ack.json
BEFORE: Missing
ACTION: Atomic rename write of ACK
EXPECTED AFTER: ACK file present
REQUIRED FINGERPRINT/IDENTITY: <req_id> + result_id
PASS: File written, state = RESULT_ACKNOWLEDGED
FAIL: File missing or race condition
CRASH/RESTART EXPECTATION: If crash before ACK, Mac re-consumes result and re-writes ACK.

10. DURABLE TERMINAL STATE
AUTHORITATIVE FILE/STATE: Courier Goal Satisfaction Engine DB
BEFORE: Windows goal OPEN
ACTION: Mac records effect as VERIFIED_COMPLETE
EXPECTED AFTER: Goal SATISFIED
REQUIRED FINGERPRINT/IDENTITY: effect fingerprint matched to goal contract
PASS: Goal transitions to SATISFIED
FAIL: Goal remains OPEN
CRASH/RESTART EXPECTATION: Recalculates from task-envelopes.

11. REPLAY SAME LOGICAL REQUEST
AUTHORITATIVE FILE/STATE: coordination/mac_to_windows/requests/<req_id>.json
BEFORE: Exists
ACTION: Send identical logical request
EXPECTED AFTER: Duplicate rejected or idempotent
REQUIRED FINGERPRINT/IDENTITY: <req_id>
PASS: Windows recognizes duplicate (via ACK or Claim)
FAIL: Windows executes again
CRASH/RESTART EXPECTATION: Idempotent.

12. LOGICAL EFFECT REMAINS EXACTLY 1
AUTHORITATIVE FILE/STATE: Windows filesystem / effect target
BEFORE: 1 effect
ACTION: Verify effect count
EXPECTED AFTER: 1 effect
REQUIRED FINGERPRINT/IDENTITY: Canonical effect hash
PASS: Exactly once semantics proven
FAIL: >1 effect (Duplicate mutation)
CRASH/RESTART EXPECTATION: Retains exactly 1 effect.


# V1 ENDGAME M4 — SUCCESSION / FALSE-IDLE FORENSICS

M4_RESULT=PASS
FALSE_GLOBAL_IDLE_PATHS=0
QUEUE_EMPTY_EQUALS_GOAL_COMPLETE_PATHS=0
HUMAN_GATE_GLOBAL_STOP_PATHS=0
PRODUCTION_SUCCESSION=PASS
RESTART_SUCCESSION=PASS
HUMAN_WEITER_REQUIRED=NO
