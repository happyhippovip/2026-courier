# TASK_09 — Artifact / State / Log Paths

STATUS=DONE
NEW_EVIDENCE=CONFIRMED

## Production Paths
STATE_FILE=/Users/user/Downloads/2026-courier/server/state/central_state.json
ARTIFACT_PATH (candidate-b-1)=server/state/artifacts/  (blobs/<sha256[:2]>/<sha256>, records/<artifact_id>.json)
LOG_PATHS=
  /Users/user/Downloads/2026-courier/scripts/mac_worker/logs/worker.log   (mac worker)
  /Users/user/Downloads/2026-courier/logs/courier_motor.log               (untracked)
  /Users/user/Downloads/2026-courier/logs/courier_motor.err               (untracked)

## Canary Paths
CANARY_STATE_FILE=/Users/user/Downloads/courier_canary/server/state/central_state.json
CANARY_ARTIFACT_DROP=/Users/user/Downloads/courier_canary/artifacts/
  canary_A.txt (bytes: COURIER-A2B-A\n, SHA-256: 96c1471cc2dfc55d49de5a3279dc927774a84b0f5c5bdc7c5755f19d8de9391c)
CANARY_LOCK_PATH=/Users/user/Downloads/courier_canary/locks/

## Candidate-b-1 Artifact Store Layout (server-owned)
ARTIFACT_BLOBS=server/state/artifacts/blobs/<sha256[:2]>/<sha256>
ARTIFACT_RECORDS=server/state/artifacts/records/<artifact_id>.json
ARTIFACT_ID_FORMAT=art-<sha256_of_binding_material_64hex>
ENV_OVERRIDE=COURIER_ARTIFACT_DIR, COURIER_ARTIFACT_MAX_BYTES (default 16MB)

## Key Path Safety Rule
is_safe_artifact_name() rejects: absolute paths, drive letters, UNC paths, ".." traversals
Validated in scripts/artifact_store.py against both PureWindowsPath and PurePosixPath.

PROVEN=All paths physically confirmed. Artifact store layout from candidate-b-1 source-audited.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_10

## UPDATE 17:33 — Verifier CWD Finding
VERIFIER_CWD=/Users/user/.courier_runtime  (proven via lsof -p 42002)
CANARY_IMPACT=Canary verifier MUST be started with CWD = canary workspace root
RISK=If verifier starts from wrong CWD, relative artifact paths may resolve incorrectly
MITIGATION=In run_canary.sh: cd /Users/user/Downloads/courier_canary && python3 .../courier_verifier.py

## UPDATE 17:33 — Memory Pressure
SWAP_USED=13.54GB / 14GB (critical)
ACTIVE_MUSE_PROCESSES=35
RECOMMENDATION=Run canary only during low-load window; do not add more muse processes
