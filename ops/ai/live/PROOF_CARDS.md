# Proof Cards

Dieses Dokument enthält die vorbereiteten Proof Cards für die Zertifizierung und Verifikation der ausgeführten Courier-Runs. Jeder Run muss eine solche Card generieren, um die Integrität nachzuweisen.

## Proof Card Template

**Run ID:** `[RUN_ID]`
**Date/Time:** `[TIMESTAMP]`

### 1. Source
- **SHA:** `FINAL_SHA_PLACEHOLDER_SOURCE`
- **Integrity Check:** `[PASS/FAIL]`

### 2. Build
- **SHA:** `FINAL_SHA_PLACEHOLDER_BUILD`
- **Build Environment:** `[ENV_DETAILS]`

### 3. Runtime
- **SHA:** `FINAL_SHA_PLACEHOLDER_RUNTIME`
- **Execution Engine:** `[ENGINE_VERSION]`

### 4. Covered Surface
- **Phases Executed:** `[z.B. Phase A, Phase B]`
- **State Dirs Validated:** `[LIST_OF_DIRS]`
- **Log Streams Validated:** `[LIST_OF_STREAMS]`

### 5. Evidence IDs
- **Preflight Evidence:** `[EVIDENCE_ID_1]`
- **Execution Evidence:** `[EVIDENCE_ID_2]`
- **Postflight Evidence:** `[EVIDENCE_ID_3]`

### 6. Human Intervention
- **Status:** `[NONE / DETECTED]`
- **Details:** `[Falls aufgetreten, genaue Beschreibung des Eingriffs]`

### 7. UNKNOWN
- **Anomalies:** `[NONE / LIST]`
- **Foreign Processes Detected:** `[COUNT]`
- **Orphans Handled:** `[COUNT]`

### 8. Restart Evidence
- **Replay Count (Phase A):** `[COUNT, expected 1]`
- **Reconciliation Validated:** `[TRUE/FALSE]`
- **Stale/Duplicate Results:** `[COUNT]`

### 9. Resource Evidence
- **Peak CPU:** `[%]`
- **Peak RAM:** `[MB]`
- **Heavy Jobs Active:** `[MAX_REACHED]`
- **Admissions Rejected:** `[COUNT]`
