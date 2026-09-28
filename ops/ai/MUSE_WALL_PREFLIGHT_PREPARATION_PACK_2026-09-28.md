# Muse Wall Preflight Preparation Pack — 2026-09-28 02:00

Status: PREP / READ_ONLY
Purpose: use cheap Google capacity before Muse starts so the 02:00 Muse wall spends its time on bounded verification rather than rediscovery.

## Preconditions

Muse stdout physical contract is already PROVEN and must not be retested unless version/adapter/CLI contract changes.

Do not use Muse as final source writer.
Do not run physical RUN_1/RUN_2 unless their explicit gates are satisfied.
MAX_HEAVY_JOBS=1.

## Cheap Google prep lanes

### MPREP-01 — Muse input index
Collect exact durable refs Muse should read first.
No source scan.
Output: minimal ordered input list.

### MPREP-02 — Completed-result fingerprint index
Map completed relevant results and do-not-repeat fingerprints.
Output: skip list for Muse.

### MPREP-03 — Contradiction shortlist
From durable result summaries only, identify unresolved contradictions worth independent Muse review.
Output: max 10 items.

### MPREP-04 — Missing-evidence shortlist
List only acceptance claims still lacking deterministic evidence.
Output: exact claim + missing evidence.

### MPREP-05 — Restart-matrix open cells
Map restart scenarios to PROVEN/OPEN/BLOCKED.
Output: only OPEN/BLOCKED cells for Muse.

### MPREP-06 — Proof-card missing fields
Map current Proof Card required fields to present/unknown.
Output: unknown fields only.

### MPREP-07 — Core-freeze blocker shortlist
Identify earliest causal blockers to Core Freeze from durable state.
Output: ordered blockers, no new design.

### MPREP-08 — Wall-reliability open checks
List unproven claim/lease/harvest/NEXT_READY/TRUE_IDLE checks.
Output: bounded checklist.

### MPREP-09 — Pilot-prep independent review packet
Collect pilot templates/metrics/privacy questions that benefit from QA.
No customer invention.
Output: compact Muse review packet.

### MPREP-10 — Muse taskbank generator input
Using MPREP-01..09 only, prepare exact independent Muse task candidates.
Do not exceed real work.
Output: MUSE_READY_TASKS with inputs, done condition, fingerprint.

## End rule

If prep proves there are only N unique Muse-worthy tasks, create N tasks.
Do not manufacture a 30/50/100 wall merely because capacity exists.
