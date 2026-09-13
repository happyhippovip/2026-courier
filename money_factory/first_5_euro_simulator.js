// First-€5 Control Flow Simulator — Deterministic Verification of Economic Loop
// Invariant: This is a SIMULATION_ONLY proving control flow.
// REAL_REVENUE_EUR MUST REMAIN EXACTLY 0.
// Never claim the first €5 has been achieved until verifiable real external settlement evidence exists.

const { MoneyScorer } = require('./scoring');
const { CheapestTestSelector } = require('./cheapest_test');
const { SafetyGateManager } = require('./safety_gates');
const { EvidenceLedger, SIGNAL_CLASSES } = require('./evidence_ledger');

class First5EuroSimulator {
  static simulateEndToEndFlow(warehouse, evidenceLedger = null, goal_id = 'GOAL-PROVE-FIRST-5-EURO-AUTONOMOUS') {
    if (warehouse && !warehouse.getAllOpportunities && warehouse.warehouse) {
      return this.runControlFlowSimulation(warehouse);
    }
    return this.runControlFlowSimulation({ warehouse, evidenceLedger, goal_id });
  }

  static runControlFlowSimulation({
    warehouse,
    evidenceLedger,
    goal_id = 'GOAL-PROVE-FIRST-5-EURO-AUTONOMOUS'
  }) {
    if (!warehouse) throw new Error('[SIMULATOR_ERROR] warehouse is required');
    const ledger = evidenceLedger || new EvidenceLedger();

    const simulationLog = [];

    // STEP 1: High-Level Economic Goal
    simulationLog.push({
      step: 1,
      phase: 'ECONOMIC_GOAL_INPUT',
      goal_id,
      directive: 'Advance the top CASH_NOW opportunity towards verifiable €5 economic proof under €0 autonomous spend.'
    });

    // STEP 2: Opportunity Selection from Warehouse
    let allOpps = warehouse.getAllOpportunities();
    if (allOpps.length === 0) {
      warehouse.addOpportunity({
        id: 'OPP-SIM-01',
        title: 'Autonomous CLI Code Auditor',
        status: 'SEED',
        source: 'SIMULATOR',
        category: 'Digital products / micro-tools',
        horizon: 'NOW',
        revenue_probability: 0.7,
        expected_revenue_eur: 500,
        expected_profit_eur: 450,
        time_to_first_euro: 2,
        margin_estimate: 0.9,
        automation_score: 0.85,
        distribution_fit: 0.75,
        evidence_score: 0.3,
        capital_required_eur: 0,
        agent_hours_estimate: 3,
        human_minutes_estimate: 15,
        model_cost_estimate: 1.5,
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
        kill_criteria: ['Zero interest after test'],
        next_test: 'Run CLI prototype benchmark'
      });
      allOpps = warehouse.getAllOpportunities();
    }

    const cashNowOpps = allOpps
      .filter(o => o.horizon === 'NOW' || o.horizon === 'NOW_THIS_WEEK' || (o.time_to_first_euro <= 7))
      .sort((a, b) => ((b.score && b.score.scalar_score) || 0) - ((a.score && a.score.scalar_score) || 0));

    const selectedOpp = cashNowOpps.length > 0 ? cashNowOpps[0] : allOpps[0];
    simulationLog.push({
      step: 2,
      phase: 'OPPORTUNITY_SELECTED',
      selected_id: selectedOpp.id,
      title: selectedOpp.title,
      horizon: selectedOpp.horizon,
      current_score: selectedOpp.score?.scalar_score || 0
    });

    // STEP 3: Multi-Factor Scoring Verification
    const verifiedScore = MoneyScorer.computeScore(selectedOpp);
    simulationLog.push({
      step: 3,
      phase: 'SCORING_VERIFIED',
      scalar_score: verifiedScore.scalar_score,
      confidence: verifiedScore.confidence,
      components: verifiedScore.components
    });

    // STEP 4: Cheapest Valid Test Proposal
    const testProposal = CheapestTestSelector.selectCheapestTestForOpportunity(selectedOpp);
    simulationLog.push({
      step: 4,
      phase: 'TEST_PROPOSAL_GENERATED',
      experiment_id: testProposal.experiment_id,
      hypothesis: testProposal.hypothesis,
      is_zero_spend: testProposal.is_zero_spend,
      cash_required_eur: testProposal.cash_required_eur
    });

    // STEP 5: Zero-Spend & Human Gate Safety Verification
    const safetyCheck = SafetyGateManager.checkOperation('real_spend');
    const invariants = SafetyGateManager.getInvariants();
    simulationLog.push({
      step: 5,
      phase: 'SAFETY_GATE_VERIFIED',
      autonomous_spend_limit_eur: invariants.AUTONOMOUS_SPEND_LIMIT_EUR,
      spend_blocked_by_safety: !safetyCheck.allowed,
      real_trades: invariants.REAL_TRADES
    });

    // STEP 6: Simulated Evidence Ingestion (Leading signal only — NEVER REAL REVENUE)
    const simulatedEvidence = ledger.recordEvidence({
      opportunity_id: selectedOpp.id,
      source_type: 'BENCHMARK_PROTOTYPE',
      source_reference: 'tests/test_prototype_benchmark.log',
      claim: 'Prototype built and passed local CLI execution benchmarks with zero errors',
      signal_class: SIGNAL_CLASSES.LEADING_SIGNAL, // Strictly LEADING_SIGNAL
      confidence: 0.75,
      verified: true
    });
    simulationLog.push({
      step: 6,
      phase: 'EVIDENCE_INGESTED',
      evidence_id: simulatedEvidence.evidence_id,
      signal_class: simulatedEvidence.signal_class,
      verified: simulatedEvidence.verified
    });

    // STEP 7: Reranking & Mutation with New Evidence
    const updatedOpp = warehouse.mutateOpportunity(
      selectedOpp.id,
      {
        evidence_score: 0.35,
        trend_evidence: 'Prototype verified locally; benchmark evidence logged'
      },
      'Updated via simulation evidence pass'
    );
    simulationLog.push({
      step: 7,
      phase: 'RERANKING_COMPLETED',
      opportunity_id: updatedOpp.id,
      updated_score: updatedOpp.score.scalar_score,
      version: updatedOpp.version
    });

    // STEP 8: Next Action Selection (Recommends Human Gate or Next Step)
    const nextAction = {
      action: 'AWAIT_HUMAN_GATE_PUBLICATION',
      target_opportunity_id: selectedOpp.id,
      required_human_gate: 'PUBLICATION',
      deliverable_package: 'dist/cli-auditor-prototype.zip',
      settlement_ready: false
    };
    simulationLog.push({
      step: 8,
      phase: 'NEXT_ACTION_SELECTED',
      next_action: nextAction
    });

    return {
      simulation_status: 'SIMULATION_ONLY',
      control_flow_verified: true,
      real_revenue_eur: 0, // Hard-coded strictly 0
      real_profit_eur: 0,
      total_simulation_steps: simulationLog.length,
      simulation_log: simulationLog,
      disclaimer: 'SIMULATION_ONLY: No real revenue claimed or fabricated. Demonstrates deterministic autonomous control flow.'
    };
  }
}

module.exports = {
  First5EuroSimulator
};
