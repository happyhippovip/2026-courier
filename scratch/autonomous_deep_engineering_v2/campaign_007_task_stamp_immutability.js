/**
 * CAMPAIGN 007: TASK STAMP IMMUTABILITY SUITE
 * 
 * Attacks task definition after STAMPED across 10 critical fields.
 * Proves in-place mutation is 100% rejected and explicit supersession preserves audit history.
 */

const fs = require('fs');
const path = require('path');
const { TaskStampEngine } = require('./MODELS/task_stamp_engine');

const LAB_ROOT = __dirname;
const CAMPAIGN_LEDGER = path.join(LAB_ROOT, 'CAMPAIGN_LEDGER.jsonl');
const EXPERIMENT_LEDGER = path.join(LAB_ROOT, 'EXPERIMENT_LEDGER.jsonl');
const MISSION_STATE = path.join(LAB_ROOT, 'MISSION_STATE.json');
const CHECKPOINT = path.join(LAB_ROOT, 'CURRENT_RESUME_CHECKPOINT.md');
const PROOF_MATRIX_JSON = path.join(LAB_ROOT, 'PROOF_MATRIX.json');
const PROOF_MATRIX_MD = path.join(LAB_ROOT, 'PROOF_MATRIX.md');
const COUNTEREXAMPLES_DIR = path.join(LAB_ROOT, 'MINIMIZED_COUNTEREXAMPLES');

function runCampaign007() {
  console.log('=== EXECUTING CAMPAIGN 007: TASK STAMP IMMUTABILITY ===\n');

  const engine = new TaskStampEngine();
  const task = engine.createTask({
    task_id: 'TASK-STAMP-TEST-001',
    goal_id: 'GOAL-TEST',
    command: 'node run_checks.js',
    scope_paths: ['src/validator.js'],
    acceptance_criteria: ['All pass'],
    is_writer: true,
    risk_class: 'HIGH',
    human_gates: ['GATE_DEPLOY_CONFIRM'],
    required_evidence: ['junit_xml']
  });

  // Stamp the task
  engine.stamp(task.task_id);
  const originalFp = task.task_fingerprint;
  console.log(`>>> Stamped task ${task.task_id} (Fingerprint: ${originalFp.slice(0, 16)}...)\n`);

  // 1. Attack 10 fields with in-place mutation
  const fieldsToAttack = [
    { field: 'goal_id', val: 'GOAL-HIJACKED' },
    { field: 'scope_paths', val: ['src/unauthorized.js'] },
    { field: 'acceptance_criteria', val: ['Skip checks'] },
    { field: 'assigned_worker_id', val: 'ROGUE_WORKER' },
    { field: 'is_writer', val: false },
    { field: 'risk_class', val: 'LOW' },
    { field: 'human_gates', val: [] }, // Bypassing gate
    { field: 'required_evidence', val: [] }, // Dropping evidence
    { field: 'command', val: 'rm -rf /' },
    { field: 'version', val: 99 }
  ];

  console.log(`>>> Mounting 10 in-place mutation attacks on STAMPED task...`);
  for (let i = 0; i < fieldsToAttack.length; i++) {
    const { field, val } = fieldsToAttack[i];
    let blocked = false;
    let errorMsg = '';

    try {
      engine.attemptMutation(task.task_id, field, val);
    } catch (err) {
      if (err.message.includes('[IMMUTABILITY_ERROR]')) {
        blocked = true;
        errorMsg = err.message;
      }
    }

    if (!blocked) {
      throw new Error(`[CRITICAL_P0_MUTATION_BREACH] Field '${field}' was mutated on STAMPED task!`);
    }

    console.log(`    [${String(i + 1).padStart(2, '0')}/10] Mutation of '${field}' -> BLOCKED (${errorMsg.slice(0, 65)}...)`);
  }
  console.log('    All 10 mutation attempts rejected fail-closed.\n');

  // Verify fingerprint is unchanged
  if (task.task_fingerprint !== originalFp) {
    throw new Error('[FINGERPRINT_CORRUPTION] Task fingerprint changed despite blocked mutations!');
  }

  // 2. Safe Version Supersession
  console.log('>>> Testing explicit version supersession...');
  const v2 = engine.supersedeTask(task.task_id, {
    command: 'node run_checks.js --v2',
    scope_paths: ['src/validator.js', 'src/helper.js']
  });

  if (v2.version !== 2 || v2.supersedes !== task.task_id || task.superseded_by !== v2.task_id) {
    throw new Error('[SUPERSEDING_ERROR] Version superseding links are malformed');
  }

  // Verify v1 remains intact
  if (task.command !== 'node run_checks.js' || task.scope_paths.length !== 1) {
    throw new Error('[MUTATION_LEAK] v1 was corrupted during v2 minting');
  }
  console.log(`    Verified: Task ${task.task_id} superseded by ${v2.task_id}. v1 definition remains 100% immutable.\n`);

  // 3. Counterexample capture
  const ce = {
    id: 'CE-008',
    defect_class: 'SILENT_IN_FLIGHT_MUTATION',
    description: 'If an orchestrator mutates scope or acceptance criteria while worker is in-flight, returned result verification fails or executes unauthorized side-effects.',
    attempted_mutations_blocked: fieldsToAttack.map(f => f.field),
    proven_behavior: '10/10 in-place mutations blocked fail-closed; explicit superseding version required.'
  };
  const cePath = path.join(COUNTEREXAMPLES_DIR, 'counterexample_silent_mutation.json');
  fs.writeFileSync(cePath, JSON.stringify(ce, null, 2), 'utf8');
  console.log(`    Saved minimized counterexample to ${cePath}\n`);

  // 4. Update PROOF_MATRIX
  const pm = JSON.parse(fs.readFileSync(PROOF_MATRIX_JSON, 'utf8'));
  pm.rows.push({
    invariant: 'TASK_STAMP_POST_STAMP_IMMUTABILITY',
    component: 'TaskStampEngine',
    tests: 11,
    mutations: 10,
    windows_proven: true,
    mac_proof_needed: false,
    codex_review: false,
    status: 'VERIFIED_PASS'
  });
  fs.writeFileSync(PROOF_MATRIX_JSON, JSON.stringify(pm, null, 2), 'utf8');

  let pmmd = fs.readFileSync(PROOF_MATRIX_MD, 'utf8');
  ppmd_row = `| TASK_STAMP_POST_STAMP_IMMUTABILITY | TaskStampEngine | 11 tests | 10 mutations killed | YES | NO | NO | VERIFIED_PASS |\n`;
  fs.writeFileSync(PROOF_MATRIX_MD, pmmd + ppmd_row, 'utf8');

  // 5. Log to Ledgers
  const campRecord = {
    campaign_id: 'CAMPAIGN_007',
    campaign_name: 'TASK_STAMP_IMMUTABILITY',
    timestamp: new Date().toISOString(),
    status: 'COMPLETE',
    information_gain: 'Proved post-stamp immutability across 10 fields (goal, scope, criteria, worker, writer class, risk, human gates, evidence, command, version). 10/10 mutations blocked fail-closed. Proved explicit version supersession creates clean new version without mutating parent.',
    metrics: { mutations_tested: 10, mutations_killed: 10, mutations_survived: 0 }
  };
  fs.appendFileSync(CAMPAIGN_LEDGER, JSON.stringify(campRecord) + '\n', 'utf8');

  const expRecord = {
    experiment_id: 'EXP_007_TASK_STAMP_IMMUTABILITY',
    campaign_id: 'CAMPAIGN_007',
    hypothesis: 'Enforcing immutability post-STAMPED prevents unauthorized scope/criteria tampering and guarantees reproducible audit integrity.',
    status: 'VERIFIED_PASS',
    exit_code: 0,
    timestamp: new Date().toISOString(),
    evidence_refs: [cePath]
  };
  fs.appendFileSync(EXPERIMENT_LEDGER, JSON.stringify(expRecord) + '\n', 'utf8');

  // 6. Advance Mission State
  const state = JSON.parse(fs.readFileSync(MISSION_STATE, 'utf8'));
  state.last_completed_campaign = 'CAMPAIGN_007';
  state.current_campaign = 'CAMPAIGN_008';
  state.current_experiment = 'EXP_008_NO_STACKING_CONCURRENCY';
  state.last_verified_step = 'Campaign 007 completed: 10 post-stamp mutations killed; CE-008 counterexample saved';
  state.last_updated_at = new Date().toISOString();
  state.tests_added += 11;
  state.tests_passed += 11;
  state.generated_cases += 11;
  state.windows_proven_count += 1;
  state.information_gain_recent = 'Task stamp immutability proven across 10 fields; zero silent in-flight mutations';
  state.next_exact_action = 'Execute Campaign 008: No-Stacking Concurrency (multiple synthetic task arrivals & scope lease HOLD)';
  fs.writeFileSync(MISSION_STATE, JSON.stringify(state, null, 2), 'utf8');

  // 7. Update Checkpoint
  let cp = fs.readFileSync(CHECKPOINT, 'utf8');
  cp = cp.replace('CURRENT_CAMPAIGN: CAMPAIGN_007 (TASK STAMP IMMUTABILITY)', 'CURRENT_CAMPAIGN: CAMPAIGN_008 (NO-STACKING CONCURRENCY)');
  cp = cp.replace('CURRENT_EXPERIMENT: EXP_007_TASK_STAMP_IMMUTABILITY', 'CURRENT_EXPERIMENT: EXP_008_NO_STACKING_CONCURRENCY');
  cp = cp.replace('LAST_COMPLETED_CAMPAIGN: CAMPAIGN_006 (EXACTLY-ONCE EFFECT ATTACK)', 'LAST_COMPLETED_CAMPAIGN: CAMPAIGN_007 (TASK STAMP IMMUTABILITY)');
  cp = cp.replace('Completed: 6 / 100+ (CAMPAIGN_001 – CAMPAIGN_006)', 'Completed: 7 / 100+ (CAMPAIGN_001 – CAMPAIGN_007)');
  fs.writeFileSync(CHECKPOINT, cp, 'utf8');

  console.log('CAMPAIGN 007 COMPLETED SUCCESSFULLY.');
}

runCampaign007();
