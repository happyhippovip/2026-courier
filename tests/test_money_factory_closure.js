// Deterministic Test Suite for Courier Money Factory P0 Closure / First-€5 Readiness
// Proves all closure invariants, evidence ledger integrity, cheapest test selection,
// supervisor plane envelope compatibility, anti-loop controls, and First5EuroSimulator.

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const os = require('os');

const {
  MoneyFactory,
  OpportunityWarehouse,
  LIFECYCLES,
  MoneyScorer,
  PortfolioManager,
  HORIZONS,
  STRATEGY_CATEGORIES,
  CycleLedger,
  CYCLE_TYPES,
  CYCLE_STATUS,
  PredictionCalibrator,
  SafetyGateManager,
  SAFETY_INVARIANTS,
  HUMAN_GATE_OPERATIONS,
  AntiLoopPolicy,
  ECONOMIC_LOOP_STAGES,
  LeaderboardGenerator,
  EvidenceLedger,
  SIGNAL_CLASSES,
  CheapestTestSelector,
  SupervisorCompatibility,
  First5EuroSimulator
} = require('../money_factory');

function runClosureTestSuite() {
  console.log('================================================================');
  console.log(' MONEY FACTORY P0 CLOSURE — DETERMINISTIC VERIFICATION SUITE');
  console.log('================================================================\n');

  let passed = 0;
  let failed = 0;
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'mf-closure-test-'));

  try {
    // -------------------------------------------------------------
    // TEST 1: Ingestion Idempotency & Schema Validation
    // -------------------------------------------------------------
    console.log('--- TEST 1: Ingestion Idempotency & Schema Validation ---');
    const warehouse = new OpportunityWarehouse(path.join(tempDir, 'warehouse'));
    const oppData = {
      id: 'OPP-CLOSURE-01',
      title: 'Headless Webhook Debugger Micro-Tool',
      status: 'SEED',
      source: 'UNIT_TEST',
      category: 'Digital products / micro-tools',
      horizon: 'NOW',
      revenue_probability: 0.6,
      expected_revenue_eur: 500,
      expected_profit_eur: 450,
      time_to_first_euro: 2,
      margin_estimate: 0.9,
      automation_score: 0.85,
      distribution_fit: 0.7,
      evidence_score: 0.4,
      capital_required_eur: 0,
      agent_hours_estimate: 3,
      human_minutes_estimate: 15,
      model_cost_estimate: 1.0,
      risk_score: 0.2,
      confidence: 0.7,
      channel_fit: { cli: 0.9 },
      human_gates: ['PUBLICATION'],
      predicted_revenue_eur: 500,
      predicted_profit_eur: 450,
      actual_revenue_eur: 0,
      actual_profit_eur: 0,
      payback_period_days: 7,
      downside_risk: 'LOW',
      kill_criteria: ['Zero organic clicks in 7 days'],
      next_test: 'Run CLI dry-run smoke test'
    };

    const added1 = warehouse.addOpportunity(oppData);
    assert.strictEqual(added1.status, 'CREATED');
    assert.strictEqual(added1.opportunity.id, 'OPP-CLOSURE-01');
    assert.strictEqual(added1.opportunity.version, 1, 'Initial version must be 1');

    // Attempt duplicate ingestion
    const added2 = warehouse.addOpportunity(oppData);
    assert.strictEqual(added2.status, 'IDEMPOTENT_NOOP');
    assert.strictEqual(added2.opportunity.id, 'OPP-CLOSURE-01');
    assert.strictEqual(added2.opportunity.version, 1, 'Duplicate ingestion must not increment version');
    assert.strictEqual(warehouse.getAllOpportunities().length, 1, 'Warehouse must maintain exactly 1 entry');

    // Invalidation on missing fields
    assert.throws(() => {
      warehouse.addOpportunity({ id: 'OPP-INVALID', title: 'Missing required fields' });
    }, /missing mandatory fields/);

    console.log('PASS [Test 1]: Ingestion is strictly idempotent and validates schemas.');
    passed++;

    // -------------------------------------------------------------
    // TEST 2: Monotonic Version Bump on Mutation
    // -------------------------------------------------------------
    console.log('--- TEST 2: Monotonic Version Bump on Mutation ---');
    const mutated1 = warehouse.mutateOpportunity('OPP-CLOSURE-01', {
      evidence_score: 0.55
    }, 'Update evidence score after manual review');
    assert.strictEqual(mutated1.version, 2, 'First mutation must increment version to 2');
    assert.strictEqual(mutated1.evidence_score, 0.55);

    const mutated2 = warehouse.mutateOpportunity('OPP-CLOSURE-01', {
      status: 'PROVING'
    }, 'Promote to PROVING');
    assert.strictEqual(mutated2.version, 3, 'Second mutation must increment version to 3');
    assert.strictEqual(mutated2.status, 'PROVING');

    const reloadedOpp = warehouse.getOpportunity('OPP-CLOSURE-01');
    assert.strictEqual(reloadedOpp.version, 3, 'Persisted version must be 3');
    console.log('PASS [Test 2]: Opportunity version increments monotonically on mutation.');
    passed++;

    // -------------------------------------------------------------
    // TEST 3: Evidence Ledger Signal Class Validation & Hashing
    // -------------------------------------------------------------
    console.log('--- TEST 3: Evidence Ledger Signal Class Validation & Hashing ---');
    const evidenceDir = path.join(tempDir, 'evidence');
    const evidenceLedger = new EvidenceLedger(evidenceDir);

    // Valid signal class append
    const validEvidence = evidenceLedger.recordEvidence({
      opportunity_id: 'OPP-CLOSURE-01',
      signal_class: SIGNAL_CLASSES.EXTERNAL_DEMAND_SIGNAL,
      evidence_type: 'INBOUND_GITHUB_ISSUE',
      source: 'https://github.com/example/repo/issues/1',
      summary: 'External user asked for paid commercial license',
      raw_payload: { issue_id: 1, user: 'external_dev' },
      verified: false
    });
    assert.ok(validEvidence.evidence_id.startsWith('EVD-'));
    assert.strictEqual(validEvidence.signal_class, SIGNAL_CLASSES.EXTERNAL_DEMAND_SIGNAL);
    assert.strictEqual(validEvidence.fingerprint.length, 64, 'Must have valid SHA-256 fingerprint');

    // Invalid signal class rejected
    assert.throws(() => {
      evidenceLedger.recordEvidence({
        opportunity_id: 'OPP-CLOSURE-01',
        signal_class: 'INVALID_HALLUCINATED_SIGNAL',
        evidence_type: 'RANDO',
        source: 'local',
        summary: 'Invalid'
      });
    }, /Invalid signal_class/);

    console.log('PASS [Test 3]: Evidence Ledger strictly enforces canonical signal classes and SHA-256 fingerprinting.');
    passed++;

    // -------------------------------------------------------------
    // TEST 4: Rejection of Synthetic/Model Claims as Real Revenue
    // -------------------------------------------------------------
    console.log('--- TEST 4: Rejection of Synthetic/Model Claims as Real Revenue ---');
    // Record synthetic test signal with nominal euro value
    evidenceLedger.recordEvidence({
      opportunity_id: 'OPP-CLOSURE-01',
      signal_class: SIGNAL_CLASSES.SYNTHETIC_TEST_SIGNAL,
      evidence_type: 'MOCK_PURCHASE_FLOW',
      source: 'local_synthetic_runner',
      summary: 'Synthetic checkout flow completed in test suite',
      claim_value_eur: 49.99,
      verified: true
    });

    // Real revenue total must remain strictly 0
    assert.strictEqual(evidenceLedger.getRealRevenueTotal(), 0, 'SYNTHETIC_TEST_SIGNAL must never count towards REAL_REVENUE');
    assert.strictEqual(evidenceLedger.getRealRevenueTotal('OPP-CLOSURE-01'), 0);

    // Recording model internal reasoning as real revenue must be rejected
    assert.throws(() => {
      evidenceLedger.recordEvidence({
        opportunity_id: 'OPP-CLOSURE-01',
        signal_class: SIGNAL_CLASSES.REAL_REVENUE,
        evidence_type: 'MODEL_ASSERTION',
        source: 'MODEL_INTERNAL_REASONING',
        summary: 'Agent believes customer will definitely pay',
        claim_value_eur: 50.0
      });
    }, /Model assertions cannot count as independent evidence/);

    console.log('PASS [Test 4]: Synthetic and model-generated assertions are strictly rejected as real revenue.');
    passed++;

    // -------------------------------------------------------------
    // TEST 5: Verified Real External Revenue Settlement Invariant
    // -------------------------------------------------------------
    console.log('--- TEST 5: Verified Real External Revenue Settlement Invariant ---');
    // Unverified REAL_REVENUE or missing external artifact is rejected
    assert.throws(() => {
      evidenceLedger.recordEvidence({
        opportunity_id: 'OPP-CLOSURE-01',
        signal_class: SIGNAL_CLASSES.REAL_REVENUE,
        evidence_type: 'INVOICE_SENT',
        source: 'stripe_pending_invoice_inv_123',
        summary: 'Invoice issued to client',
        claim_value_eur: 50.0,
        verified: false
      });
    }, /REAL_REVENUE signal_class strictly requires verified external artifact/);
    assert.strictEqual(evidenceLedger.getRealRevenueTotal(), 0, 'Unverified invoice must not count as settled real revenue');

    // Verified external settlement with artifact
    const verifiedSettlement = evidenceLedger.recordEvidence({
      opportunity_id: 'OPP-CLOSURE-01',
      signal_class: SIGNAL_CLASSES.REAL_REVENUE,
      evidence_type: 'STRIPE_PAYMENT_SETTLEMENT',
      source: 'stripe_charge_ch_abc123_bank_deposit_ref_999',
      summary: 'Client cleared payment of 50 EUR into bank account',
      claim_value_eur: 50.0,
      verified: true,
      external_verification_artifact: 'receipts/stripe_ch_abc123.pdf'
    });
    assert.strictEqual(evidenceLedger.getRealRevenueTotal(), 50.0, 'Verified settlement must count as real revenue');
    assert.strictEqual(evidenceLedger.hasVerifiedSignal('OPP-CLOSURE-01', SIGNAL_CLASSES.REAL_REVENUE), true);

    console.log('PASS [Test 5]: Real revenue is strictly gate-kept to verified external settlements.');
    passed++;

    // -------------------------------------------------------------
    // TEST 6: Soft Portfolio Allocation (Never Force Bad Bets)
    // -------------------------------------------------------------
    console.log('--- TEST 6: Soft Portfolio Allocation ---');
    const emptyWarehouse = new OpportunityWarehouse(path.join(tempDir, 'empty_warehouse'));
    const portfolioMgr = new PortfolioManager();
    const allocations = portfolioMgr.allocateBudget(emptyWarehouse, 1000);

    // Empty warehouse must yield empty allocation without throwing or hallucinating opportunities
    for (const h of Object.values(HORIZONS)) {
      assert.ok(Array.isArray(allocations[h]), `Allocation for horizon ${h} must be an array`);
      assert.strictEqual(allocations[h].length, 0, `Allocation for empty horizon ${h} must be empty`);
    }

    // Horizon alias verification
    assert.strictEqual(HORIZONS.NOW_THIS_WEEK, 'NOW_THIS_WEEK');
    assert.strictEqual(HORIZONS.NEXT_30_DAYS, 'NEXT_30_DAYS');
    assert.strictEqual(HORIZONS.NEXT_365_DAYS, 'NEXT_365_DAYS');
    assert.strictEqual(HORIZONS.ASYMMETRIC, 'ASYMMETRIC');

    console.log('PASS [Test 6]: Portfolio allocation operates softly without forcing sub-threshold opportunities.');
    passed++;

    // -------------------------------------------------------------
    // TEST 7: Cheapest Valid Test Selector (€0 P0 Preference)
    // -------------------------------------------------------------
    console.log('--- TEST 7: Cheapest Valid Test Selector ---');
    const oppForTest = warehouse.getOpportunity('OPP-CLOSURE-01');
    const testProposal = CheapestTestSelector.generateTestProposal(oppForTest);

    assert.strictEqual(testProposal.proposal_type, 'ECONOMIC_TEST_PROPOSAL');
    assert.strictEqual(testProposal.opportunity_id, 'OPP-CLOSURE-01');
    assert.strictEqual(testProposal.cash_required_eur, 0.0, 'P0 test proposal must strictly require €0 cash');
    assert.ok(testProposal.agent_time_estimate <= 4.0, 'Agent time estimate must be capped for quick verification');
    assert.ok(testProposal.evidence_plan.length > 0, 'Evidence plan must be explicit');
    assert.ok(testProposal.kill_or_promote_rule.length > 0, 'Kill/promote rule must be explicit');

    console.log('PASS [Test 7]: CheapestTestSelector generates valid €0 P0 test proposals.');
    passed++;

    // -------------------------------------------------------------
    // TEST 8: Enhanced SPEND_REQUEST Schema & Approvals
    // -------------------------------------------------------------
    console.log('--- TEST 8: Enhanced SPEND_REQUEST Schema ---');
    // Missing why_free_option_is_insufficient
    assert.throws(() => {
      SafetyGateManager.createSpendRequest({
        amount_eur: 15.0,
        purpose: 'Domain name purchase',
        recipient: 'Namecheap',
        opportunity_id: 'OPP-CLOSURE-01',
        experiment_id: 'EXP-TEST-01'
      });
    }, /why_free_option_is_insufficient is required/);

    // Missing opportunity_id
    assert.throws(() => {
      SafetyGateManager.createSpendRequest({
        amount_eur: 15.0,
        purpose: 'Domain name purchase',
        recipient: 'Namecheap',
        why_free_option_is_insufficient: 'Need live custom domain for SSL verification'
      });
    }, /opportunity_id is required/);

    // Valid spend request
    const spendReq = SafetyGateManager.createSpendRequest({
      amount_eur: 10.0,
      purpose: 'API test credits',
      recipient: 'External API Provider',
      opportunity_id: 'OPP-CLOSURE-01',
      experiment_id: 'EXP-CLOSURE-TEST-01',
      why_free_option_is_insufficient: 'Free tier rate limit exceeded during smoke test'
    });
    assert.strictEqual(spendReq.approved, false, 'Spend requests must start unapproved');
    assert.strictEqual(spendReq.opportunity_id, 'OPP-CLOSURE-01');
    assert.strictEqual(spendReq.experiment_id, 'EXP-CLOSURE-TEST-01');
    assert.strictEqual(spendReq.why_free_option_is_insufficient, 'Free tier rate limit exceeded during smoke test');

    console.log('PASS [Test 8]: Enhanced SPEND_REQUEST requires opportunity context and justification.');
    passed++;

    // -------------------------------------------------------------
    // TEST 9: Enhanced Prediction Calibration Schema
    // -------------------------------------------------------------
    console.log('--- TEST 9: Enhanced Prediction Calibration Schema ---');
    const calibrator = new PredictionCalibrator(path.join(tempDir, 'calibration'));
    const pred = calibrator.recordForecast({
      opportunity_id: 'OPP-CLOSURE-01',
      experiment_id: 'EXP-CLOSURE-TEST-01',
      predicted_probability: 0.75,
      predicted_revenue_eur: 50.0
    });
    assert.strictEqual(pred.experiment_id, 'EXP-CLOSURE-TEST-01');
    assert.strictEqual(pred.predicted_probability, 0.75);
    assert.ok(pred.predicted_at);

    // Resolve outcome
    const resolved = calibrator.resolveForecast(pred.forecast_id, {
      actual_outcome: true,
      actual_revenue_eur: 50.0
    });
    assert.strictEqual(resolved.status, 'RESOLVED');
    assert.strictEqual(resolved.actual_outcome, true);
    assert.strictEqual(resolved.absolute_error, 0.25); // |0.75 - 1.0| = 0.25
    assert.strictEqual(resolved.brier_contribution, 0.0625); // (0.75 - 1.0)^2 = 0.0625

    console.log('PASS [Test 9]: Prediction calibration schema tracks experiment IDs and Brier scores accurately.');
    passed++;

    // -------------------------------------------------------------
    // TEST 10: Anti-Loop Zero-Information Experiment Blocking
    // -------------------------------------------------------------
    console.log('--- TEST 10: Anti-Loop Zero-Information Experiment Blocking ---');
    const pastExperiments = [
      {
        experiment_id: 'EXP-PREV-01',
        hypothesis: 'Validate buyer willingness via GitHub issue ping',
        evidence_yielded: 0,
        result: 'INCONCLUSIVE'
      }
    ];

    // Attempting identical experiment with zero new evidence
    const blockedDispatch = AntiLoopPolicy.validateExperimentDispatch({
      opportunity_id: 'OPP-CLOSURE-01',
      hypothesis: 'Validate buyer willingness via GitHub issue ping',
      previous_experiments: pastExperiments,
      new_angle_or_evidence: false
    });
    assert.strictEqual(blockedDispatch.allowed, false);
    assert.ok(blockedDispatch.reason.includes('ANTI_LOOP_VIOLATION'));

    // Allowed dispatch when new angle or hypothesis is present
    const allowedDispatch = AntiLoopPolicy.validateExperimentDispatch({
      opportunity_id: 'OPP-CLOSURE-01',
      hypothesis: 'Test direct outreach with revised landing demo',
      previous_experiments: pastExperiments,
      new_angle_or_evidence: true
    });
    assert.strictEqual(allowedDispatch.allowed, true);

    console.log('PASS [Test 10]: AntiLoopPolicy blocks repeated zero-information experiments.');
    passed++;

    // -------------------------------------------------------------
    // TEST 11: Anti-Loop Stagnant Opportunity Demotion / Kill
    // -------------------------------------------------------------
    console.log('--- TEST 11: Anti-Loop Stagnant Opportunity Demotion / Kill ---');
    const stagnantEvaluation = AntiLoopPolicy.evaluateStagnantOpportunity({
      consecutive_zero_info_runs: 3,
      lifecycle: 'TESTING',
      days_in_lifecycle: 14
    });
    assert.strictEqual(stagnantEvaluation.should_retire, true);
    assert.strictEqual(stagnantEvaluation.recommended_action, 'DEMOTE_OR_KILL');
    assert.ok(stagnantEvaluation.reason.includes('stagnant'));

    const activeEvaluation = AntiLoopPolicy.evaluateStagnantOpportunity({
      consecutive_zero_info_runs: 1,
      lifecycle: 'TESTING',
      days_in_lifecycle: 2
    });
    assert.strictEqual(activeEvaluation.should_retire, false);

    console.log('PASS [Test 11]: AntiLoopPolicy detects stagnant opportunities and recommends demotion/kill.');
    passed++;

    // -------------------------------------------------------------
    // TEST 12: Supervisor Compatibility Envelope Binding
    // -------------------------------------------------------------
    console.log('--- TEST 12: Supervisor Compatibility Envelope Binding ---');
    const economicEnvelope = SupervisorCompatibility.wrapEconomicTask({
      goal_id: 'GOAL-FIRST-5-EURO',
      task_id: 'TASK-ECONOMIC-EXP-01',
      task_version: 1,
      worker_id: 'worker-win-01',
      machine_id: 'win-box',
      evidence_refs: ['EVID-001', 'EVID-002'],
      payload: {
        action: 'RUN_CHEAPEST_TEST',
        opportunity_id: 'OPP-CLOSURE-01'
      }
    });

    assert.strictEqual(economicEnvelope.supervisor_envelope_version, 'v1');
    assert.strictEqual(economicEnvelope.goal_id, 'GOAL-FIRST-5-EURO');
    assert.strictEqual(economicEnvelope.task_id, 'TASK-ECONOMIC-EXP-01');
    assert.strictEqual(economicEnvelope.worker_id, 'worker-win-01');
    assert.deepStrictEqual(economicEnvelope.evidence_refs, ['EVID-001', 'EVID-002']);

    const boundEnvelope = SupervisorCompatibility.bindProcessLease(economicEnvelope, {
      process_lease_id: 'LEASE-PROC-999',
      pid: 12345,
      command: 'node run_experiment.js'
    });
    assert.strictEqual(boundEnvelope.process_lease_id, 'LEASE-PROC-999');
    assert.strictEqual(boundEnvelope.bound_pid, 12345);
    assert.ok(boundEnvelope.bound_at);

    console.log('PASS [Test 12]: SupervisorCompatibility envelope creates clean interoperability with supervisor plane.');
    passed++;

    // -------------------------------------------------------------
    // TEST 13: First-€5 End-to-End Control Flow Simulator
    // -------------------------------------------------------------
    console.log('--- TEST 13: First-€5 End-to-End Control Flow Simulator ---');
    const simWarehouse = new OpportunityWarehouse(path.join(tempDir, 'sim_warehouse'));
    const simEvidence = new EvidenceLedger(path.join(tempDir, 'sim_evidence'));

    const simResult = First5EuroSimulator.simulateEndToEndFlow(simWarehouse, simEvidence);
    assert.strictEqual(simResult.simulation_status, 'SIMULATION_ONLY');
    assert.strictEqual(simResult.control_flow_verified, true);
    assert.strictEqual(simResult.real_revenue_eur, 0, 'Real revenue must be strictly 0 in simulation');
    assert.strictEqual(simResult.real_profit_eur, 0, 'Real profit must be strictly 0 in simulation');
    assert.strictEqual(simResult.total_simulation_steps, 8, 'Must execute all 8 canonical steps');

    const steps = simResult.simulation_log.map(s => s.phase);
    assert.deepStrictEqual(steps, [
      'ECONOMIC_GOAL_INPUT',
      'OPPORTUNITY_SELECTED',
      'SCORING_VERIFIED',
      'TEST_PROPOSAL_GENERATED',
      'SAFETY_GATE_VERIFIED',
      'EVIDENCE_INGESTED',
      'RERANKING_COMPLETED',
      'NEXT_ACTION_SELECTED'
    ]);

    console.log('PASS [Test 13]: First5EuroSimulator proves complete autonomous 8-step flow with 0 real revenue fabricated.');
    passed++;

  } catch (err) {
    console.error('\nFAILURE IN TEST SUITE:', err);
    failed++;
  } finally {
    try {
      fs.rmSync(tempDir, { recursive: true, force: true });
    } catch (e) {}
  }

  console.log('\n================================================================');
  console.log(` CLOSURE RESULTS: ${passed} PASSED | ${failed} FAILED | 0 ERRORS`);
  console.log('================================================================');
  assert.strictEqual(failed, 0, 'All deterministic closure tests must pass');
}

runClosureTestSuite();
