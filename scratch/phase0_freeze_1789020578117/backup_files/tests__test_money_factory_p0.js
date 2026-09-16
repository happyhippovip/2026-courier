// Deterministic Test Suite for Courier Money Factory P0 Build
// Proves all 18 core invariants and behaviors deterministically without mocks or fake passes.

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
  AntiLoopPolicy
} = require('../money_factory');

function runTestSuite() {
  console.log('================================================================');
  console.log(' COURIER MONEY FACTORY P0 — COMPREHENSIVE DETERMINISTIC SUITE');
  console.log('================================================================\n');

  let passed = 0;
  let failed = 0;
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'mf-p0-test-'));

  try {
    // -------------------------------------------------------------
    // TEST 1: Idempotent Opportunity Ingestion
    // -------------------------------------------------------------
    console.log('--- TEST 1: Idempotent Opportunity Ingestion ---');
    const warehouse = new OpportunityWarehouse(tempDir);
    const testOpp = {
      id: 'OPP-TEST-01',
      title: 'Deterministic Test Asset',
      status: 'SEED',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      source: 'UNIT_TEST',
      category: 'Digital products / micro-tools',
      horizon: 'NOW',
      revenue_probability: 0.5,
      expected_revenue_eur: 1000,
      expected_profit_eur: 900,
      time_to_first_euro: 3,
      margin_estimate: 0.9,
      automation_score: 0.8,
      distribution_fit: 0.7,
      evidence_score: 0.3,
      capital_required_eur: 0,
      agent_hours_estimate: 5,
      human_minutes_estimate: 20,
      model_cost_estimate: 2,
      risk_score: 0.2,
      confidence: 0.6,
      channel_fit: { cli: 0.9 },
      trend_evidence: 'High developer demand',
      source_evidence: 'UNKNOWN',
      next_test: 'Run CLI prototype benchmark',
      human_gates: ['PUBLICATION'],
      predicted_revenue_eur: 1000,
      predicted_profit_eur: 900,
      actual_revenue_eur: 0,
      actual_profit_eur: 0,
      prediction_error: 'UNKNOWN',
      promote_kill_reason: 'UNKNOWN'
    };

    const res1 = warehouse.addOpportunity(testOpp);
    assert.strictEqual(res1.status, 'CREATED');

    // Ingest again: must be idempotent
    const res2 = warehouse.addOpportunity(testOpp);
    assert.strictEqual(res2.status, 'IDEMPOTENT_NOOP');
    assert.strictEqual(warehouse.getAllOpportunities().length, 1);
    console.log('PASS [Test 1]: Opportunity ingestion is strictly idempotent.');
    passed++;

    // -------------------------------------------------------------
    // TEST 2: No Historical Overwrite (Audit Ledger Immutability)
    // -------------------------------------------------------------
    console.log('--- TEST 2: No Historical Overwrite ---');
    warehouse.mutateOpportunity('OPP-TEST-01', { title: 'Updated Title V2' }, 'Title refinement');
    warehouse.mutateOpportunity('OPP-TEST-01', { expected_revenue_eur: 1500 }, 'Revised upward');

    const history = warehouse.getHistory('OPP-TEST-01');
    assert.strictEqual(history.length, 3, 'Must have exactly 3 ledger events');
    assert.strictEqual(history[0].event_type, 'OPPORTUNITY_CREATED');
    assert.strictEqual(history[0].snapshot.title, 'Deterministic Test Asset', 'Original snapshot must be preserved');
    assert.strictEqual(history[1].event_type, 'OPPORTUNITY_MUTATED');
    assert.strictEqual(history[1].details.reason, 'Title refinement');
    assert.strictEqual(history[2].details.reason, 'Revised upward');
    console.log('PASS [Test 2]: Append-only audit history ledger preserves all snapshots without overwrite.');
    passed++;

    // -------------------------------------------------------------
    // TEST 3: Stable Scoring for Same Inputs
    // -------------------------------------------------------------
    console.log('--- TEST 3: Stable Scoring for Same Inputs ---');
    const score1 = MoneyScorer.computeScore(testOpp);
    const score2 = MoneyScorer.computeScore(testOpp);
    assert.strictEqual(score1.scalar_score, score2.scalar_score);
    assert.strictEqual(score1.confidence, score2.confidence);
    assert.deepStrictEqual(score1.components, score2.components);
    assert.ok(score1.scalar_score > 0, 'Score must be positive');
    console.log(`PASS [Test 3]: Scoring computation is deterministic and stable (Score: ${score1.scalar_score}).`);
    passed++;

    // -------------------------------------------------------------
    // TEST 4: Explicit UNKNOWN Handling
    // -------------------------------------------------------------
    console.log('--- TEST 4: UNKNOWN Handling ---');
    const oppWithUnknowns = {
      ...testOpp,
      id: 'OPP-TEST-UNK-02',
      trend_evidence: 'UNKNOWN',
      source_evidence: 'UNKNOWN',
      time_to_first_euro: 'UNKNOWN',
      evidence_score: 'UNKNOWN'
    };
    const scoredUnknown = MoneyScorer.computeScore(oppWithUnknowns);
    assert.strictEqual(scoredUnknown.evidence_score, 'UNKNOWN');
    assert.strictEqual(scoredUnknown.evidence_breakdown.trend_evidence, 'UNKNOWN');
    assert.strictEqual(scoredUnknown.evidence_breakdown.is_empirically_verified, false);
    assert.ok(scoredUnknown.scalar_score > 0, 'Fallbacks allow compute without crash');
    console.log('PASS [Test 4]: UNKNOWN evidence explicitly preserved and handled gracefully.');
    passed++;

    // -------------------------------------------------------------
    // TEST 5: Portfolio Ranking Across Horizons
    // -------------------------------------------------------------
    console.log('--- TEST 5: Portfolio Ranking Across Horizons ---');
    const pm = new PortfolioManager();
    const o30d = { ...testOpp, id: 'OPP-30D', horizon: '30D', score: { scalar_score: 50.0 } };
    const oNow = { ...testOpp, id: 'OPP-NOW', horizon: 'NOW', score: { scalar_score: 80.0 } };
    const oAsym = { ...testOpp, id: 'OPP-ASYM', horizon: 'ASYMMETRIC', score: { scalar_score: 120.0 } };

    const ranked = pm.rankAllHorizons([o30d, oNow, oAsym]);
    assert.strictEqual(ranked[HORIZONS.NOW].length, 1);
    assert.strictEqual(ranked[HORIZONS.NOW][0].id, 'OPP-NOW');
    assert.strictEqual(ranked[HORIZONS.HORIZON_30D][0].id, 'OPP-30D');
    assert.strictEqual(ranked[HORIZONS.ASYMMETRIC][0].id, 'OPP-ASYM');

    const alloc = pm.calculateAllocation([o30d, oNow, oAsym], 100);
    assert.strictEqual(alloc.allocations.CASH_NOW.allocated_agent_hours, 50);
    assert.strictEqual(alloc.allocations.GROWTH.allocated_agent_hours, 35);
    assert.strictEqual(alloc.allocations.MOONSHOTS.allocated_agent_hours, 15);
    console.log('PASS [Test 5]: Portfolio horizons and default capacity weights correctly computed.');
    passed++;

    // -------------------------------------------------------------
    // TEST 6: Lifecycle Transitions
    // -------------------------------------------------------------
    console.log('--- TEST 6: Lifecycle Transitions ---');
    // SEED -> ACTIVE requires reason
    warehouse.promoteOpportunity('OPP-TEST-01', LIFECYCLES.ACTIVE, 'Approved for active testing sprint');
    assert.strictEqual(warehouse.getOpportunity('OPP-TEST-01').status, LIFECYCLES.ACTIVE);

    // ACTIVE -> PROVING requires evidence_score >= 0.20
    warehouse.promoteOpportunity('OPP-TEST-01', LIFECYCLES.PROVING, 'Evidence threshold met');
    assert.strictEqual(warehouse.getOpportunity('OPP-TEST-01').status, LIFECYCLES.PROVING);

    // PROVING -> WINNER fails if actual_revenue_eur <= 0
    assert.throws(() => {
      warehouse.promoteOpportunity('OPP-TEST-01', LIFECYCLES.WINNER, 'Claimed winner prematurely');
    }, /actual_revenue_eur > 0/);

    // Provide actual revenue and promote to WINNER
    warehouse.mutateOpportunity('OPP-TEST-01', { actual_revenue_eur: 50.0 });
    warehouse.promoteOpportunity('OPP-TEST-01', LIFECYCLES.WINNER, 'First 50 EUR settled in bank');
    assert.strictEqual(warehouse.getOpportunity('OPP-TEST-01').status, LIFECYCLES.WINNER);

    // Kill opportunity requires substantive reason
    warehouse.killOpportunity('OPP-TEST-01', 'Market changed; competitor launched free tool');
    assert.strictEqual(warehouse.getOpportunity('OPP-TEST-01').status, LIFECYCLES.KILLED);
    console.log('PASS [Test 6]: Lifecycle state transitions enforce evidence gates at every step.');
    passed++;

    // -------------------------------------------------------------
    // TEST 7: Prediction History Immutability
    // -------------------------------------------------------------
    console.log('--- TEST 7: Prediction History Immutability ---');
    const calibrator = new PredictionCalibrator(path.join(tempDir, 'evidence'));
    calibrator.recordPrediction('OPP-TEST-01', 'MONEY-2026-09-08', {
      predicted_revenue_eur: 1000,
      predicted_profit_eur: 900,
      confidence: 0.6,
      evidence_quality: 'MEDIUM',
      decision_made: 'BUILD_PROTOTYPE'
    });

    calibrator.recordPrediction('OPP-TEST-01', 'MONEY-2026-09-15', {
      predicted_revenue_eur: 1200,
      predicted_profit_eur: 1100,
      confidence: 0.7,
      evidence_quality: 'HIGH',
      decision_made: 'EXPAND_DISTRIBUTION'
    });

    const calData = calibrator.getCalibration('OPP-TEST-01');
    assert.strictEqual(calData.prediction_history.length, 2);
    assert.strictEqual(calData.prediction_history[0].predicted_revenue_eur, 1000);
    assert.strictEqual(calData.prediction_history[1].predicted_revenue_eur, 1200);

    // Reconcile with actuals
    const outcome = calibrator.recordActualOutcome('OPP-TEST-01', {
      actual_revenue_eur: 1150,
      actual_profit_eur: 1050,
      actual_outcome: 'Product launched and sold 23 licenses',
      lesson: 'Conversion was 15% higher than original estimate'
    });
    assert.strictEqual(outcome.metrics.absolute_error_revenue, 50);
    console.log('PASS [Test 7]: Prediction history is strictly immutable; actuals calibration verified.');
    passed++;

    // -------------------------------------------------------------
    // TEST 8: Cycle Idempotency
    // -------------------------------------------------------------
    console.log('--- TEST 8: Cycle Idempotency ---');
    const cycleLedger = new CycleLedger(path.join(tempDir, 'research', '2026'));
    const cyclePayload = {
      cycle_id: 'MONEY-2026-09-08',
      cycle_type: CYCLE_TYPES.WEEKLY_RADAR,
      started_at: '2026-09-08T08:00:00.000Z',
      finished_at: '2026-09-08T09:00:00.000Z',
      sources: [{ uri: 'https://example.com/trends', date: '2026-09-08' }],
      ranking_before: [{ id: 'OPP-01', score: 10 }],
      ranking_after: [{ id: 'OPP-01', score: 15 }],
      diff: { promoted: ['OPP-01'] },
      validation: { passed: true },
      artifact_refs: ['research/2026/RADAR-2026-09-08.md']
    };

    const cRes1 = cycleLedger.recordCycle(cyclePayload);
    assert.strictEqual(cRes1.status, CYCLE_STATUS.VERIFIED);

    // Duplicate submission
    const cRes2 = cycleLedger.recordCycle(cyclePayload);
    assert.strictEqual(cRes2.status, 'IDEMPOTENT_NOOP');
    console.log('PASS [Test 8]: Cycle recording is strictly idempotent.');
    passed++;

    // -------------------------------------------------------------
    // TEST 9: Missed-Cycle Catch-up
    // -------------------------------------------------------------
    console.log('--- TEST 9: Missed-Cycle Catch-up ---');
    const expectedCycles = ['MONEY-2026-09-01', 'MONEY-2026-09-08'];
    const missed = cycleLedger.detectMissedCycles(expectedCycles);
    assert.deepStrictEqual(missed, ['MONEY-2026-09-01']);

    // Catch up missed cycle
    const catchupRes = cycleLedger.catchUpMissedCycle('MONEY-2026-09-01', (id) => ({
      cycle_id: id,
      cycle_type: CYCLE_TYPES.WEEKLY_RADAR,
      started_at: '2026-09-01T08:00:00.000Z',
      finished_at: '2026-09-01T09:00:00.000Z',
      sources: [{ uri: 'https://example.com/archive', date: '2026-09-01' }],
      ranking_before: [],
      ranking_after: [{ id: 'OPP-01', score: 10 }],
      diff: { initialized: true },
      validation: { passed: true },
      artifact_refs: ['research/2026/RADAR-2026-09-01.md']
    }));
    assert.strictEqual(catchupRes.status, CYCLE_STATUS.VERIFIED);
    console.log('PASS [Test 9]: Missed cycles detected and recovered into VERIFIED state.');
    passed++;

    // -------------------------------------------------------------
    // TEST 10: Evidence Requirement Before VERIFIED
    // -------------------------------------------------------------
    console.log('--- TEST 10: Evidence Requirement Before VERIFIED ---');
    const incompleteCycle = {
      cycle_id: 'MONEY-2026-09-15',
      started_at: '2026-09-15T08:00:00.000Z',
      finished_at: '2026-09-15T09:00:00.000Z',
      sources: [], // EMPTY SOURCES
      ranking_after: [],
      diff: {},
      validation: { passed: false }
    };
    const incRes = cycleLedger.recordCycle(incompleteCycle);
    assert.strictEqual(incRes.status, CYCLE_STATUS.REJECTED);
    console.log('PASS [Test 10]: Cycles lacking required evidence are rejected from VERIFIED status.');
    passed++;

    // -------------------------------------------------------------
    // TEST 11: Zero-Spend Enforcement
    // -------------------------------------------------------------
    console.log('--- TEST 11: Zero-Spend Enforcement ---');
    assert.strictEqual(SAFETY_INVARIANTS.AUTONOMOUS_SPEND_LIMIT_EUR, 0);
    assert.throws(() => {
      SafetyGateManager.executeSpend({ spend_request_id: 'SPEND-001', price_eur: 5 });
    }, /Autonomous spend execution strictly forbidden/);
    console.log('PASS [Test 11]: Hard zero-spend limit strictly enforced.');
    passed++;

    // -------------------------------------------------------------
    // TEST 12: SPEND_REQUEST Generation
    // -------------------------------------------------------------
    console.log('--- TEST 12: SPEND_REQUEST Generation ---');
    const req = SafetyGateManager.createSpendRequest({
      price_eur: 15.0,
      purpose: 'Domain registration for verified pilot',
      evidence: 'https://trends.google.com/keyword-volume',
      expected_upside_eur: 500,
      maximum_loss_eur: 15.0,
      cheapest_alternative: 'Use free GitHub Pages subdomain',
      human_approval_required: true
    });
    assert.ok(req.spend_request_id.startsWith('SPEND-REQ-'));
    assert.strictEqual(req.status, 'PENDING_HUMAN_APPROVAL');
    assert.strictEqual(req.human_approval_required, true);
    assert.strictEqual(req.autonomous_execution_allowed, false);
    console.log('PASS [Test 12]: Structured SPEND_REQUEST generated with mandatory human gates.');
    passed++;

    // -------------------------------------------------------------
    // TEST 13: Publication, Deploy, Outreach Human Gates
    // -------------------------------------------------------------
    console.log('--- TEST 13: Publication, Deploy, Outreach Human Gates ---');
    const gPub = SafetyGateManager.checkOperation('publication');
    assert.strictEqual(gPub.allowed, false);
    assert.strictEqual(gPub.gate_type, 'PUBLICATION');

    const gDep = SafetyGateManager.checkOperation('production_deployment');
    assert.strictEqual(gDep.allowed, false);
    assert.strictEqual(gDep.gate_type, 'PRODUCTION_DEPLOYMENT');

    const gOut = SafetyGateManager.checkOperation('customer_outreach');
    assert.strictEqual(gOut.allowed, false);
    assert.strictEqual(gOut.gate_type, 'CUSTOMER_OUTREACH');
    console.log('PASS [Test 13]: Production deploy, publication, and outreach operations require HUMAN_GATE.');
    passed++;

    // -------------------------------------------------------------
    // TEST 14: No Trading / Wallet Actions
    // -------------------------------------------------------------
    console.log('--- TEST 14: No Trading / Wallet Actions ---');
    assert.strictEqual(SAFETY_INVARIANTS.REAL_TRADES, 0);
    assert.strictEqual(SAFETY_INVARIANTS.REAL_WALLETS_CONNECTED, 'NO');
    assert.throws(() => {
      SafetyGateManager.executeTrade({ asset: 'BTC', amount: 0.1 });
    }, /Autonomous real trading strictly forbidden/);
    assert.throws(() => {
      SafetyGateManager.signWithWallet({ payload: '0x123' });
    }, /Autonomous wallet signing strictly forbidden/);
    console.log('PASS [Test 14]: Financial trading and wallet signing strictly prohibited.');
    passed++;

    // -------------------------------------------------------------
    // TEST 15: No Fake Revenue (Money Truth Firewall)
    // -------------------------------------------------------------
    console.log('--- TEST 15: No Fake Revenue (Money Truth Firewall) ---');
    const fakeSignal = AntiLoopPolicy.validateEconomicEvidence({
      evidence_type: 'FAST_TEST_MODE',
      is_synthetic_test: true
    });
    assert.strictEqual(fakeSignal.is_valid_economic_signal, false);
    assert.strictEqual(fakeSignal.allowed_for_winner_promotion, false);

    const unconfirmedRev = AntiLoopPolicy.validateEconomicEvidence({
      evidence_type: 'REAL_REVENUE',
      external_bank_or_stripe_proof: false
    });
    assert.strictEqual(unconfirmedRev.is_valid_economic_signal, false);
    assert.strictEqual(unconfirmedRev.allowed_for_winner_promotion, false);

    const verifiedRev = AntiLoopPolicy.validateEconomicEvidence({
      evidence_type: 'REAL_REVENUE',
      external_bank_or_stripe_proof: true
    });
    assert.strictEqual(verifiedRev.is_valid_economic_signal, true);
    assert.strictEqual(verifiedRev.allowed_for_winner_promotion, true);
    console.log('PASS [Test 15]: Synthetic fast test mode and unconfirmed revenue strictly rejected.');
    passed++;

    // -------------------------------------------------------------
    // TEST 16: No Fake Engagement
    // -------------------------------------------------------------
    console.log('--- TEST 16: No Fake Engagement ---');
    const fakeEngage = AntiLoopPolicy.validateEconomicEvidence({
      evidence_type: 'CLICKS',
      engagement_source: 'BOT_FARM'
    });
    assert.strictEqual(fakeEngage.is_valid_economic_signal, false);
    console.log('PASS [Test 16]: Bot farm and synthetic engagement disallowed.');
    passed++;

    // -------------------------------------------------------------
    // TEST 17: No Autonomous Account Farming
    // -------------------------------------------------------------
    console.log('--- TEST 17: No Autonomous Account Farming ---');
    assert.throws(() => {
      AntiLoopPolicy.validateAccountAction('ACCOUNT_FARMING');
    }, /Disallowed autonomous action/);
    console.log('PASS [Test 17]: Autonomous account farming strictly blocked.');
    passed++;

    // -------------------------------------------------------------
    // TEST 18: Anti-Loop Infrastructure Invariant
    // -------------------------------------------------------------
    console.log('--- TEST 18: Anti-Loop Infrastructure Invariant ---');
    // Attempting infrastructure change without blocking defect
    const unblockedMod = AntiLoopPolicy.validateInfrastructureChangeRequest({
      is_courier_frozen: true,
      has_blocking_defect: false,
      justification: 'Refactoring Courier internal task scheduler for cleanliness'
    });
    assert.strictEqual(unblockedMod.allowed, false);
    assert.ok(unblockedMod.reason.includes('ANTI_LOOP_VIOLATION'));

    // Permitted bugfix with reproducible test case blocking an opportunity
    const permittedFix = AntiLoopPolicy.validateInfrastructureChangeRequest({
      is_courier_frozen: true,
      has_blocking_defect: true,
      reproducible_test_case: 'tests/test_lock_contention_failure.js',
      impacted_opportunity_id: 'OPP-SEED-COURIER-07',
      justification: 'Writer lock deadlocks when 2 agents ping simultaneously'
    });
    assert.strictEqual(permittedFix.allowed, true);
    console.log('PASS [Test 18]: Infrastructure changes post-freeze strictly blocked unless verified defect blocks revenue.');
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
  console.log(` RESULTS: ${passed} PASSED | ${failed} FAILED | 0 ERRORS`);
  console.log('================================================================');
  assert.strictEqual(failed, 0, 'All deterministic tests must pass');
}

runTestSuite();
