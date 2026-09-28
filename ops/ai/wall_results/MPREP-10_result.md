# Result for MPREP-10: Muse Taskbank Generator Input

TASK=MPREP-10
STATUS=PASS
RESULTS_REUSED=ops/ai/mprep_results/MPREP-01.result.txt through MPREP-09.result.txt, ops/ai/mprep_results/MUSE_READY_TASK_BANK.md, ops/ai/MUSE_WALL_PREFLIGHT_PREPARATION_PACK_2026-09-28.md
OUTPUT=Bounded Muse Ready Taskbank (Generated and Validated):
Exactly 4 Bounded QA Tasks for 02:00 Muse Wall:
1. **MUSE-01: Independent QA of Central Writer Patch Specification**
   - Inputs: `ops/ai/coordination_reports/FAMILY_18_CENTRAL_WRITER_COMPRESSED.md`, `scripts/courier_verifier.py:70-95`, `scripts/integration_contract.py:150-170`, `server/app.py:355-375`
   - Action: Verify that the 4 specified fixes resolve the 7 FAIL cases in the 12-case matrix without regression.
   - Done Condition: Compact verification review with verdict `SPEC_SOUND=YES|NO`.
   - Fingerprint: `muse_task_01_spec_qa_v1`
2. **MUSE-02: Independent Review of Grandma-Test 3-State UI Copy**
   - Inputs: `ops/ai/coordination_reports/FAMILY_14_FIRST_FRIEND_UX_READINESS.md`, `docs/COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md`
   - Action: Evaluate 3 primary states (`ARBEITET`, `BRAUCHT DICH`, `FERTIG`) and German copy to ensure 100% free of jargon.
   - Done Condition: Signed Grandma-Test audit with approved string table.
   - Fingerprint: `muse_task_02_grandma_ux_v1`
3. **MUSE-03: Independent Verification of First Pilot Onboarding Runbook**
   - Inputs: `ops/ai/coordination_reports/FAMILY_15_ONBOARDING_MANUAL_PILOT.md`
   - Action: Audit 6-step setup protocol to verify setup <= 15 min without admin/root.
   - Done Condition: Time budget audit with verdict `SETUP_UNDER_15M=YES|NO`.
   - Fingerprint: `muse_task_03_onboarding_audit_v1`
4. **MUSE-04: Pre-Codex Gate Checklist Cross-Check**
   - Inputs: `ops/ai/GOOGLE_PRE_CODEX_GATE_2026-09-27.md`, `ops/ai/specialist_reports/SPECIALIST_I_PRE_CODEX_HANDOFF_COMPRESSOR.md`
   - Action: Cross-check all 7 pre-Codex criteria against candidate-b-1 base SHA (`4c1e24cc`) confirming gate `PRE_CODEX_READY=NO` safely held.
   - Done Condition: Independent gate attestation confirming `GATE_HELD_VALID=YES`.
   - Fingerprint: `muse_task_04_pre_codex_crosscheck_v1`

MISSING=None.
BLOCKER=None.
MUSE_INPUT=Execute these exactly 4 bounded QA tasks. Do not manufacture speculative tasks.
DO_NOT_REPEAT_FINGERPRINT=mprep-10-muse-taskbank-generator-input-v1

DO_NOT_REPEAT_FINGERPRINT=sha256-98d9f6cc11a98ca1
