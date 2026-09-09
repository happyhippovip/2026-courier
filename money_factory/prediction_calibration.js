// Prediction vs. Actuals Calibration Ledger
// Rules:
// 1. Snapshot predictions at decision time.
// 2. Reconcile against empirical actuals when captured.
// 3. Compute error metrics: absolute error, relative error.
// 4. Invariant: Historical predictions must NEVER be overwritten.

const fs = require('fs');
const path = require('path');

class PredictionCalibrator {
  constructor(storageDir = null) {
    this.storageDir = storageDir || path.join(__dirname, '..', 'opportunity_warehouse', 'evidence');
    if (!fs.existsSync(this.storageDir)) {
      fs.mkdirSync(this.storageDir, { recursive: true });
    }
    this.ledgerFile = path.join(this.storageDir, 'prediction_calibration_ledger.json');
    this.records = new Map();
    this._load();
  }

  _load() {
    if (fs.existsSync(this.ledgerFile)) {
      try {
        const raw = JSON.parse(fs.readFileSync(this.ledgerFile, 'utf8'));
        if (Array.isArray(raw)) {
          for (const item of raw) {
            this.records.set(item.opportunity_id, item);
          }
        }
      } catch (err) {
        console.error(`[PREDICTION_CALIBRATOR] Error loading ${this.ledgerFile}:`, err.message);
      }
    }
  }

  _persist() {
    const list = Array.from(this.records.values());
    const tmp = `${this.ledgerFile}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(list, null, 2), 'utf8');
    fs.renameSync(tmp, this.ledgerFile);
  }

  recordPrediction(opportunityId, cycleId, predictionData) {
    if (!opportunityId) throw new Error('[PREDICTION_ERROR] opportunityId is required.');
    if (!predictionData) throw new Error('[PREDICTION_ERROR] predictionData is required.');

    const requiredFields = [
      'predicted_revenue_eur',
      'predicted_profit_eur',
      'confidence',
      'evidence_quality',
      'decision_made'
    ];

    for (const f of requiredFields) {
      if (predictionData[f] === undefined) {
        throw new Error(`[PREDICTION_ERROR] Missing mandatory field '${f}'`);
      }
    }

    const existing = this.records.get(opportunityId) || {
      opportunity_id: opportunityId,
      prediction_history: [],
      actual_outcomes: [],
      calibration_summary: null
    };

    const snapshot = {
      prediction_id: `PRED-${Date.now()}-${existing.prediction_history.length + 1}`,
      cycle_id: cycleId,
      recorded_at: new Date().toISOString(),
      predicted_revenue_eur: predictionData.predicted_revenue_eur,
      predicted_profit_eur: predictionData.predicted_profit_eur,
      confidence: predictionData.confidence,
      evidence_quality: predictionData.evidence_quality,
      decision_made: predictionData.decision_made,
      hypothesis: predictionData.hypothesis || 'UNKNOWN'
    };

    // Immutable append: never overwrite previous snapshots
    existing.prediction_history.push(snapshot);
    existing.latest_prediction = snapshot;

    this.records.set(opportunityId, existing);
    this._persist();

    return snapshot;
  }

  recordActualOutcome(opportunityId, actualsData) {
    const existing = this.records.get(opportunityId);
    if (!existing || existing.prediction_history.length === 0) {
      throw new Error(`[CALIBRATION_ERROR] Cannot record actual outcome for '${opportunityId}': no prediction history exists.`);
    }

    const requiredFields = [
      'actual_revenue_eur',
      'actual_profit_eur',
      'actual_outcome',
      'lesson'
    ];

    for (const f of requiredFields) {
      if (actualsData[f] === undefined) {
        throw new Error(`[CALIBRATION_ERROR] Missing actuals field '${f}'`);
      }
    }

    const latestPred = existing.latest_prediction;
    const actualRev = Number(actualsData.actual_revenue_eur) || 0;
    const predRev = Number(latestPred.predicted_revenue_eur) || 0;

    const actualProfit = Number(actualsData.actual_profit_eur) || 0;
    const predProfit = Number(latestPred.predicted_profit_eur) || 0;

    const absErrorRevenue = Math.abs(predRev - actualRev);
    const relErrorRevenue = predRev > 0 ? (absErrorRevenue / predRev) : (actualRev > 0 ? 1.0 : 0.0);

    const absErrorProfit = Math.abs(predProfit - actualProfit);
    const relErrorProfit = predProfit > 0 ? (absErrorProfit / predProfit) : (actualProfit > 0 ? 1.0 : 0.0);

    const outcomeRecord = {
      outcome_id: `OUTCOME-${Date.now()}-${existing.actual_outcomes.length + 1}`,
      reconciled_at: new Date().toISOString(),
      matched_prediction_id: latestPred.prediction_id,
      actual_revenue_eur: actualRev,
      actual_profit_eur: actualProfit,
      actual_outcome: actualsData.actual_outcome,
      lesson: actualsData.lesson,
      metrics: {
        absolute_error_revenue: parseFloat(absErrorRevenue.toFixed(2)),
        relative_error_revenue: parseFloat(relErrorRevenue.toFixed(4)),
        absolute_error_profit: parseFloat(absErrorProfit.toFixed(2)),
        relative_error_profit: parseFloat(relErrorProfit.toFixed(4))
      }
    };

    existing.actual_outcomes.push(outcomeRecord);
    existing.calibration_summary = {
      last_reconciled: outcomeRecord.reconciled_at,
      total_predictions: existing.prediction_history.length,
      total_outcomes: existing.actual_outcomes.length,
      latest_metrics: outcomeRecord.metrics
    };

    this.records.set(opportunityId, existing);
    this._persist();

    return outcomeRecord;
  }

  getCalibration(opportunityId) {
    return this.records.get(opportunityId) || null;
  }
}

module.exports = {
  PredictionCalibrator
};
