# Courier Durable Evidence Index 100X — 2026-09-28

**Authority**: GOOGLE_CLI (Durable Evidence Indexer 100X)  
**Status**: COMPLETE & CANONICAL  
**Reference Pointers**:  
- [`ops/ai/WALL_SYSTEM.md`](file:///Users/user/Downloads/2026-courier/ops/ai/WALL_SYSTEM.md)  
- [`ops/ai/WALL_QUEUE_CURRENT.md`](file:///Users/user/Downloads/2026-courier/ops/ai/WALL_QUEUE_CURRENT.md)  
- [`ops/ai/COST_SAFE_GATE_TRANSITION_POLICY_2026-09-28.md`](file:///Users/user/Downloads/2026-courier/ops/ai/COST_SAFE_GATE_TRANSITION_POLICY_2026-09-28.md)  
- [`ops/ai/GATE_STATE_CURRENT.md`](file:///Users/user/Downloads/2026-courier/ops/ai/GATE_STATE_CURRENT.md)  

---

## Compact Evidence Indexes

### Entry 1: Canonical Truth Lineage & Base Fingerprint
```ini
CLAIM=CANONICAL_TRUTH_LINEAGE_BASE
EVIDENCE_REF=ops/ai/GATE_STATE_CURRENT.md, ops/ai/WALL_QUEUE_CURRENT.md
BOUND_SHA_OR_FINGERPRINT=4c1e24ccc522042af826bc4c2b595daf85d097f9 (candidate-b-1)
VALID=YES
STALE=NO
RETEST_TRIGGER=Rebase or divergence of candidate-b-1 base commit
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 2: Task / Result / Attempt / Dispatch Identity Binding
```ini
CLAIM=TASK_RESULT_ATTEMPT_DISPATCH_BINDING
EVIDENCE_REF=scripts/integration_contract.py, tests/test_result_identity_binding.py, ops/ai/coordination_reports/FAMILY_21_LEDGER_FINGERPRINT_SYNTHESIS.md
BOUND_SHA_OR_FINGERPRINT=G181_LEDGER_ID_UNIQUENESS_PROVEN / res-{task_id}-{attempt_id}
VALID=YES
STALE=NO
RETEST_TRIGGER=Modifications to schemas/thought_coverage_ledger.schema.json or scripts/integration_contract.py
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 3: Candidate Bundle & FINAL_SHA Status
```ini
CLAIM=FINAL_SHA_CANDIDATE_BUNDLE
EVIDENCE_REF=ops/ai/GATE_STATE_CURRENT.md, ops/ai/GOOGLE_PRE_CODEX_GATE_2026-09-27.md, ops/ai/coordination_reports/FAMILY_18_CENTRAL_WRITER_COMPRESSED.md
BOUND_SHA_OR_FINGERPRINT=REPORTED_FINAL_SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf / BASE=4c1e24cc
VALID=NO (DURABILITY_PENDING - Not yet resolvable on origin/candidate-b-1)
STALE=NO
RETEST_TRIGGER=Candidate commit becomes durably resolvable on GitHub origin/candidate-b-1
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 4: Targeted-Test Result Surface
```ini
CLAIM=TARGETED_TEST_EXECUTION_SURFACE
EVIDENCE_REF=tests/test_artifact_upload_flow.py, tests/test_p3_server_idempotency.py, tests/test_result_identity_binding.py, tests/test_integration_contract.py
BOUND_SHA_OR_FINGERPRINT=44_TARGETED_TESTS_PASS_SKIPPED_0
VALID=YES (on base 4c1e24cc)
STALE=NO (Accurate baseline; revalidated against candidate commit once published)
RETEST_TRIGGER=Commit of FINAL_SHA to candidate-b-1
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 5: 12-Case Acceptance Surface Baseline
```ini
CLAIM=TWELVE_CASE_ACCEPTANCE_SURFACE_BASELINE
EVIDENCE_REF=ops/ai/GOOGLE_PRE_CODEX_GATE_2026-09-27.md, ops/ai/FAILURE_SEMANTICS_AUDIT_2026-09-28.md
BOUND_SHA_OR_FINGERPRINT=5_PASS_7_FAIL_DIAGNOSTIC_BASELINE
VALID=YES (Accurately proves the 4 causal defects exist on unpatched base)
STALE=NO
RETEST_TRIGGER=Publication of FINAL_SHA incorporating the Q027/Family 18 patch packet
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 6: Replay & Trusted Content Verification
```ini
CLAIM=REPLAY_TRUSTED_CONTENT_INVARIANTS
EVIDENCE_REF=ops/ai/coordination_reports/FAMILY_23_REPLAY_PROOF_SYNTHESIS.md, ops/ai/coordination_reports/FAMILY_24_TRUSTED_CONTENT_PROOF_SYNTHESIS.md
BOUND_SHA_OR_FINGERPRINT=5_TUPLE_MATCH_STREAM_HASHING_PROVEN
VALID=YES
STALE=NO
RETEST_TRIGGER=Changes to server/app.py duplicate checking logic or verifier hashing
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 7: Reconcile & Deterministic NEXT_READY
```ini
CLAIM=RECONCILE_AND_NEXT_READY_DETERMINISM
EVIDENCE_REF=ops/ai/coordination_reports/FAMILY_25_MOTOR_PROOF_SYNTHESIS.md, ops/ai/wall_ledger/ledger.jsonl
BOUND_SHA_OR_FINGERPRINT=467_ENTRIES_DETERMINISTIC_SORTING_PROVEN
VALID=YES
STALE=NO
RETEST_TRIGGER=Task schema modifications or ledger schema version change
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 8: Restart Matrix (All 6 Stages + 3 Failures)
```ini
CLAIM=RESTART_MATRIX_FAIL_CLOSED_SAFETY
EVIDENCE_REF=ops/ai/MAC_RESTART_MATRIX_EVIDENCE_PACKET_2026-09-28.md, ops/ai/coordination_reports/FAMILY_26_RESTART_MATRIX_SYNTHESIS.md
BOUND_SHA_OR_FINGERPRINT=9_SCENARIOS_FAIL_CLOSED_NO_REPLAY_PROVEN
VALID=YES
STALE=NO
RETEST_TRIGGER=Changes to server state recovery or worker watchdog reclamation
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 9: Proof Card & Autonomy Grading Specifications
```ini
CLAIM=PROOF_CARD_AUTONOMY_GRADE_A4
EVIDENCE_REF=ops/ai/MAC_PROOF_CARD_AND_CORE_FREEZE_PACKET_2026-09-28.md, ops/ai/coordination_reports/FAMILY_30_MORNING_LEDGER_HANDOFF_SYNTHESIS.md
BOUND_SHA_OR_FINGERPRINT=P3_PROOF_LEVEL_A4_AUTONOMY_SPEC_PROVEN
VALID=YES
STALE=NO
RETEST_TRIGGER=Changes to core freeze criteria or proof card schema
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 10: Source / Build / Runtime Binding Framework
```ini
CLAIM=SOURCE_BUILD_RUNTIME_FINGERPRINT_FRAMEWORK
EVIDENCE_REF=ops/ai/MAC_FINGERPRINT_BINDING_FRAMEWORK_2026-09-28.md, ops/ai/MAC_EXACT_BINDING_SPECIFICATION_2026-09-28.md
BOUND_SHA_OR_FINGERPRINT=FINGERPRINT_FRAMEWORK_V1_2026-09-28
VALID=YES
STALE=NO
RETEST_TRIGGER=Change in runtime Python interpreter version or host OS kernel
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 11: Staging Physical Canary Attestation
```ini
CLAIM=STAGING_PHYSICAL_CANARY_PROOFS
EVIDENCE_REF=ops/ai/wall_v2/publish_queue/PHYSICAL_CANARY_PROOF_BUNDLE_2026-09-27.md
BOUND_SHA_OR_FINGERPRINT=PHYS-001..004_PORT_8081_PASS
VALID=YES (on staging coordinator)
STALE=NO
RETEST_TRIGGER=Final candidate physical verification post-Codex review
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 12: Obsolete Port 8080 Unisolated Proof
```ini
CLAIM=UNISOLATED_PORT_8080_CANARY
EVIDENCE_REF=ops/ai/STALE_EVIDENCE_INVALIDATION_REPORT_2026-09-28.md
BOUND_SHA_OR_FINGERPRINT=PHYS-CANARY-8080-PRE-SPLIT
VALID=NO
STALE=YES
RETEST_TRIGGER=Superseded by Port 8081 isolation bundle
REUSABLE_BY_HOSTS=NONE (Quarantined)
```

### Entry 13: Obsolete Candidate-b-2 Artifacts
```ini
CLAIM=REJECTED_CANDIDATE_B2_LINEAGE
EVIDENCE_REF=ops/ai/STALE_EVIDENCE_INVALIDATION_REPORT_2026-09-28.md
BOUND_SHA_OR_FINGERPRINT=83940de3d7d33776a712e7506aa76726d16f8587
VALID=NO
STALE=YES
RETEST_TRIGGER=Superseded by canonical candidate-b-1 lineage
REUSABLE_BY_HOSTS=NONE (Quarantined)
```


### Entry 14: Failure Semantics 12-Invariant Verification
```ini
CLAIM=FAILURE_SEMANTICS_12_CASE_AUDIT
EVIDENCE_REF=ops/ai/FAILURE_SEMANTICS_AUDIT_2026-09-28.md, scripts/integration_contract.py, tests/test_p3_server_idempotency.py
BOUND_SHA_OR_FINGERPRINT=FAILURE_SEMANTICS_12_OF_12_PROVEN
VALID=YES
STALE=NO
RETEST_TRIGGER=Server routing changes or contract schema modifications
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 15: Muse 02:00 Preflight & Staged QA Bank
```ini
CLAIM=MUSE_WALL_0200_PREFLIGHT_BANK
EVIDENCE_REF=ops/ai/mprep_results/MPREP_SYNTHESIS_PACK_2026-09-28.md, ops/ai/MUSE_WALL_PREFLIGHT_PREPARATION_PACK_2026-09-28.md
BOUND_SHA_OR_FINGERPRINT=MPREP01..10_CONTRACT_STAGED_MUSE_QA_01..05
VALID=YES
STALE=NO
RETEST_TRIGGER=02:00 wall opening or change in Muse CLI contract
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 16: Resource Admission & Bounded Polling Spec
```ini
CLAIM=RESOURCE_ADMISSION_AND_BOUNDED_POLLING
EVIDENCE_REF=ops/ai/MAC_RESOURCE_ADMISSION_AND_BACKOFF_SPEC_2026-09-28.md, ops/ai/coordination_reports/FAMILY_29_COST_RESOURCE_SYNTHESIS.md
BOUND_SHA_OR_FINGERPRINT=MAX_HEAVY_JOBS=1_NO_TIGHT_POLLING_SPEC
VALID=YES
STALE=NO
RETEST_TRIGGER=Host topology or concurrency governor changes
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 17: Worker / Verifier Key Separation
```ini
CLAIM=WORKER_VERIFIER_KEY_SEPARATION
EVIDENCE_REF=ops/ai/MAC_WORKER_VERIFIER_KEY_SEPARATION_CHECKLIST_2026-09-28.md, server/app.py:485-486
BOUND_SHA_OR_FINGERPRINT=INDEPENDENT_VERIFIER_AUTH_ENFORCED
VALID=YES
STALE=NO
RETEST_TRIGGER=Auth schema changes in /tasks/verify or /artifacts
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 18: Bounded Pilot Intake & Cohort Qualification Rubric
```ini
CLAIM=BOUNDED_PILOT_INTAKE_AND_ONBOARDING
EVIDENCE_REF=ops/ai/PILOT_PREPARATION_PACKET_2026-09-27.md, docs/COURIER_USER_REPO_ONBOARDING_AND_IDEA_INTAKE_2026-09-27.md
BOUND_SHA_OR_FINGERPRINT=COHORT_QUALIFICATION_RUBRIC_V1
VALID=YES
STALE=NO
RETEST_TRIGGER=Pilot cohort expansion or permission model updates
REUSABLE_BY_HOSTS=MAC, WINDOWS
```


### Entry 19: Opus 4.6 Windows Convergence Queue 100 Wire
```ini
CLAIM=OPUS46_WINDOWS_QUEUE_100_WIRE
EVIDENCE_REF=ops/ai/OPUS46_WINDOWS_QUEUE_100_2026-09-28.md, ops/ai/WALL_QUEUE_CURRENT.md
BOUND_SHA_OR_FINGERPRINT=OPUS46_WINDOWS_QUEUE_100_COST_GUARDED
VALID=YES
STALE=NO
RETEST_TRIGGER=Updates to OPUS46_WINDOWS_QUEUE_100 or queue retirement
REUSABLE_BY_HOSTS=WINDOWS
```

### Entry 20: Cost-Safe Gate Transition & Current Gate State Authority
```ini
CLAIM=COST_SAFE_GATE_TRANSITION_POLICY
EVIDENCE_REF=ops/ai/COST_SAFE_GATE_TRANSITION_POLICY_2026-09-28.md, ops/ai/GATE_STATE_CURRENT.md
BOUND_SHA_OR_FINGERPRINT=GATE_STATE_DURABILITY_PENDING_REPORTED_34b0a426
VALID=YES
STALE=NO
RETEST_TRIGGER=Publication of FINAL_SHA to remote canonical GitHub repo or gate fingerprint change
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 21: Model Capability Registry & Cost-Tier Boundary
```ini
CLAIM=MODEL_CAPABILITY_REGISTRY_AND_COST_TIERS
EVIDENCE_REF=ops/ai/COURIER_MODEL_CAPABILITY_REGISTRY_2026-09-28.md, ops/ai/COST_SAFE_GATE_TRANSITION_POLICY_2026-09-28.md
BOUND_SHA_OR_FINGERPRINT=CAPABILITY_CLASSES_C0_C1_C2_C3_C4_C5_V1
VALID=YES
STALE=NO
RETEST_TRIGGER=Changes to model class assignments or provider routing contracts
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 22: Worker Self-Identification & Routing Contract
```ini
CLAIM=WORKER_SELF_IDENTIFICATION_CONTRACT
EVIDENCE_REF=ops/ai/WORKER_SELF_IDENTIFICATION_AND_ROUTING_CONTRACT_2026-09-28.md
BOUND_SHA_OR_FINGERPRINT=WORKER_SELF_ID_SCHEMA_V1
VALID=YES
STALE=NO
RETEST_TRIGGER=Changes to worker claim telemetry fields or capability classes
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 23: Model-Aware Wall Routing & Window Concurrency Budget
```ini
CLAIM=MODEL_AWARE_WALL_ROUTING_AND_CONCURRENCY
EVIDENCE_REF=ops/ai/MODEL_AWARE_WALL_ROUTING_POLICY_2026-09-28.md, ops/ai/OPUS46_WINDOWS_QUEUE_100_USAGE.md
BOUND_SHA_OR_FINGERPRINT=OPUS_CONCURRENCY_4_TO_8_C0_FIRST_RULE
VALID=YES
STALE=NO
RETEST_TRIGGER=Changes to concurrency limits or model cost structures
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 24: Wall Task Packet Schema & Deterministic Invalidation Contract
```ini
CLAIM=WALL_TASK_PACKET_SCHEMA_CONTRACT
EVIDENCE_REF=ops/ai/WALL_TASK_PACKET_SCHEMA.md, ops/ai/WALL_SYSTEM.md
BOUND_SHA_OR_FINGERPRINT=SCHEMA_V1_DO_NOT_REPEAT_FINGERPRINT_BOUND
VALID=YES
STALE=NO
RETEST_TRIGGER=Modifications to packet frontmatter or done condition requirements
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 25: End-to-End Finish-to-Pilot Playbook Invariant Sequence
```ini
CLAIM=FINISH_TO_PILOT_PLAYBOOK_INVARIANT_SEQUENCE
EVIDENCE_REF=ops/ai/END_TO_END_FINISH_TO_PILOT_PLAYBOOK_2026-09-27.md, ops/ai/WALL_QUEUE_CURRENT.md
BOUND_SHA_OR_FINGERPRINT=TEN_STEP_CRITICAL_PATH_FINISH_TO_PILOT
VALID=YES
STALE=NO
RETEST_TRIGGER=Alteration of critical path milestones 1..10
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 26: RUN_1 & RUN_2 Zero-Relay Evidence Capture Architecture
```ini
CLAIM=RUN1_RUN2_ZERO_RELAY_EVIDENCE_CAPTURE
EVIDENCE_REF=ops/ai/RUN1_RUN2_EVIDENCE_CAPTURE_DESIGN_2026-09-28.md, ops/ai/MAC_RUN1_ISOLATION_AND_PREFLIGHT_CHECKLIST_2026-09-28.md, ops/ai/MAC_RUN2_RESTART_EXECUTION_HARNESS_2026-09-28.md
BOUND_SHA_OR_FINGERPRINT=RUN1_12_DATUM_RUN2_14_DATUM_CAPTURE_DESIGN
VALID=YES
STALE=NO
RETEST_TRIGGER=Changes to verification payload schemas or canary task definitions
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 27: Extended Execution Ledger & Finish Gate Invariant
```ini
CLAIM=EXTENDED_EXECUTION_LEDGER_AND_FINISH_GATE
EVIDENCE_REF=ops/ai/EXTENDED_EXECUTION_LEDGER_SPEC_2026-09-27.md, ops/ai/LEDGER_FINISH_GATE_2026-09-27.md, ops/ai/wall_ledger/ledger.jsonl
BOUND_SHA_OR_FINGERPRINT=471_TOTAL_RECONCILED_LEDGER_ENTRIES_FROZEN
VALID=YES
STALE=NO
RETEST_TRIGGER=New unharvested queue completion or ledger schema revision
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

### Entry 28: Adaptive Queue & Batch Sizing Specification
```ini
CLAIM=ADAPTIVE_QUEUE_AND_BATCH_SIZING
EVIDENCE_REF=ops/ai/ADAPTIVE_QUEUE_AND_PACKAGE_SIZING_2026-09-27.md
BOUND_SHA_OR_FINGERPRINT=ADAPTIVE_SIZING_V1_SCALE_RATIO_BOUND
VALID=YES
STALE=NO
RETEST_TRIGGER=Queue size threshold adjustments or worker latency drift
REUSABLE_BY_HOSTS=MAC, WINDOWS
```

---

## 3. Coverage Certification

All 28 canonical evidence domains across all 30 Work Families (`FAMILY_01..30`), 10 Opus 4.6 Convergence Families (`COST`, `LEDGER`, `MOTOR`, `PILOT`, `PROOF`, `REPLAY`, `RESTART`, `TRUST`, `TRUTH`, `WALL`), Post-Pre-Codex Priorities (`PPREP-01..10`), Failure Semantics, and System Routing/Cost Boundaries are 100% indexed, validated, and bound to deterministic invalidation triggers.

