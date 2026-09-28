# Courier Wall Task Packet Schema

Status: CANONICAL TASK PACKET SPECIFICATION  
Schema Version: `courier-wall-task-packet-1.0`

## Required Fields

Every wall task packet conforms to the following schema:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "WallTaskPacket",
  "type": "object",
  "required": [
    "TASK_ID",
    "PRIORITY",
    "DEPENDENCIES",
    "EXACT_INPUTS",
    "EXACT_FILES_OR_RESULTS",
    "ALLOWED_ACTION",
    "DONE_CONDITION",
    "EXPECTED_OUTPUT",
    "DO_NOT_REPEAT_FINGERPRINT"
  ],
  "properties": {
    "TASK_ID": { "type": "string" },
    "PRIORITY": { "type": "string", "enum": ["P0", "P1", "P2"] },
    "DEPENDENCIES": { "type": "string" },
    "EXACT_INPUTS": { "type": "string" },
    "EXACT_FILES_OR_RESULTS": { "type": "string" },
    "ALLOWED_ACTION": { "type": "string", "enum": ["READ_AND_VERIFY", "TARGETED_TEST", "SYNTHESIS", "PHYSICAL_PROOF"] },
    "DONE_CONDITION": { "type": "string" },
    "EXPECTED_OUTPUT": { "type": "string" },
    "RETEST_TRIGGER": { "type": "string" },
    "DO_NOT_REPEAT_FINGERPRINT": { "type": "string" }
  }
}
```

## Result Format

After execution, every completed task produces a result record:
- File path: `ops/ai/wall_results/<TASK_ID>_result.md`
- Fields:
  - `STATUS`: PASS | FAIL | BLOCKED | RETEST_AFTER_FINAL_SHA
  - `INPUTS_READ`: Exact file paths
  - `OUTPUT_FILE`: Path to output
  - `DO_NOT_REPEAT`: SHA-256 fingerprint
  - `VERDICT`: Concise conclusion and evidence
- Ledger append: Recorded in `ops/ai/wall_ledger/ledger.jsonl`.
