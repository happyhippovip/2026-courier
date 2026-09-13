// Money Factory V3 P0 Foundation — Unified Interface
// Single entry point for autonomous economic operation

const path = require('path');
const { OpportunityWarehouse, LIFECYCLES } = require('./warehouse');
const { MoneyScorer } = require('./scoring');
const { PortfolioManager, HORIZONS, STRATEGY_CATEGORIES } = require('./portfolios');
const { INITIAL_SEEDS } = require('./seed_classes');
const { CycleLedger, CYCLE_TYPES, CYCLE_STATUS } = require('./cycle_ledger');
const { PredictionCalibrator } = require('./prediction_calibration');
const { SafetyGateManager, SAFETY_INVARIANTS, HUMAN_GATE_OPERATIONS } = require('./safety_gates');
const { AntiLoopPolicy, ECONOMIC_LOOP_STAGES } = require('./anti_loop_policy');
const { LeaderboardGenerator } = require('./leaderboard_generator');
const { EvidenceLedger, SIGNAL_CLASSES } = require('./evidence_ledger');
const { CheapestTestSelector } = require('./cheapest_test');
const { SupervisorCompatibility } = require('./supervisor_compat');
const { First5EuroSimulator } = require('./first_5_euro_simulator');

class MoneyFactory {
  constructor(customWarehouseDir = null) {
    this.warehouseDir = customWarehouseDir || path.join(__dirname, '..', 'opportunity_warehouse');
    this.warehouse = new OpportunityWarehouse(this.warehouseDir);
    this.portfolioManager = new PortfolioManager();
    this.cycleLedger = new CycleLedger(path.join(this.warehouseDir, 'research', '2026'));
    this.predictionCalibrator = new PredictionCalibrator(path.join(this.warehouseDir, 'evidence'));
    this.evidenceLedger = new EvidenceLedger(path.join(this.warehouseDir, 'evidence'));

    this._initializeSeedsIfEmpty();
  }

  _initializeSeedsIfEmpty() {
    const existing = this.warehouse.getAllOpportunities();
    if (existing.length === 0) {
      for (const seed of INITIAL_SEEDS) {
        this.warehouse.addOpportunity(seed);
      }
      this.refreshLeaderboard();
    }
  }

  refreshLeaderboard() {
    return LeaderboardGenerator.generateMarkdown(this.warehouse);
  }

  getWarehouse() {
    return this.warehouse;
  }

  getCycleLedger() {
    return this.cycleLedger;
  }

  getPredictionCalibrator() {
    return this.predictionCalibrator;
  }

  getEvidenceLedger() {
    return this.evidenceLedger;
  }
}

module.exports = {
  MoneyFactory,
  OpportunityWarehouse,
  LIFECYCLES,
  MoneyScorer,
  PortfolioManager,
  HORIZONS,
  STRATEGY_CATEGORIES,
  INITIAL_SEEDS,
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
};
