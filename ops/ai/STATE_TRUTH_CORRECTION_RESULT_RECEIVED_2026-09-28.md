# Restart Evidence Correction — RESULT_RECEIVED is authoritative

Date: 2026-09-28
Status: CONFIRMED SOURCE-CODE CONTRADICTION

Confirmed in server/app.py:
- POST /tasks/result accepts a valid durable result
- task status becomes RESULT_RECEIVED
- verifier later consumes RESULT_RECEIVED
- PASS verification moves task to RECONCILED
- there is no authoritative VALIDATED_PENDING_VERIFY state in server/app.py

Therefore any restart/proof packet that claims VALIDATED_PENDING_VERIFY as a real Courier durable state is stale/incorrect and must not be used as PASS evidence.

Required correction for any local/generated packet:
VALIDATED_PENDING_VERIFY -> RESULT_RECEIVED

Retest trigger:
- server/app.py state machine changes
- a new canonical state enum explicitly introduces a different state

Do not infer new statuses from prose. Evidence packets must use states that exist in source/runtime truth.
