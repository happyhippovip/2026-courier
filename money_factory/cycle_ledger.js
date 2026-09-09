// Research Cycle Ledger
// Identity: MONEY-YYYY-MM-DD (e.g. MONEY-2026-09-08 or MONEY-2026-09-08-WEEKLY_RADAR)
// Scheduled cycle types:
// WEEKLY_RADAR, MONTHLY_DEEP_RESEARCH, MIDMONTH_CHALLENGER, EVENT_DRIVEN_RERANK, MONTHLY_CALIBRATION, YEARLY_STRATEGIC_RESET
// Completed cycle fields:
// cycle_id, started_at, finished_at, sources, ranking_before, ranking_after, diff, validation, artifact_refs, fingerprint, status
// Invariants:
// - A cycle is VERIFIED only when required evidence exists
// - Missed cycles must be catch-up capable and idempotent

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const CYCLE_TYPES = Object.freeze({
  WEEKLY_RADAR: 'WEEKLY_RADAR',
  MONTHLY_DEEP_RESEARCH: 'MONTHLY_DEEP_RESEARCH',
  MIDMONTH_CHALLENGER: 'MIDMONTH_CHALLENGER',
  EVENT_DRIVEN_RERANK: 'EVENT_DRIVEN_RERANK',
  MONTHLY_CALIBRATION: 'MONTHLY_CALIBRATION',
  YEARLY_STRATEGIC_RESET: 'YEARLY_STRATEGIC_RESET'
});

const CYCLE_STATUS = Object.freeze({
  INITIATED: 'INITIATED',
  IN_PROGRESS: 'IN_PROGRESS',
  COMPLETED: 'COMPLETED',
  VERIFIED: 'VERIFIED',
  REJECTED: 'REJECTED'
});

class CycleLedger {
  constructor(storageDir = null) {
    this.storageDir = storageDir || path.join(__dirname, '..', 'opportunity_warehouse', 'research', '2026');
    if (!fs.existsSync(this.storageDir)) {
      fs.mkdirSync(this.storageDir, { recursive: true });
    }
    this.ledgerFile = path.join(this.storageDir, 'cycle_ledger.json');
    this.cycles = new Map();
    this._load();
  }

  _load() {
    if (fs.existsSync(this.ledgerFile)) {
      try {
        const raw = JSON.parse(fs.readFileSync(this.ledgerFile, 'utf8'));
        if (Array.isArray(raw)) {
          for (const c of raw) {
            this.cycles.set(c.cycle_id, c);
          }
        }
      } catch (err) {
        console.error(`[CYCLE_LEDGER] Warning: Could not parse ${this.ledgerFile}:`, err.message);
      }
    }
  }

  _persist() {
    const list = Array.from(this.cycles.values());
    const tmp = `${this.ledgerFile}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(list, null, 2), 'utf8');
    fs.renameSync(tmp, this.ledgerFile);
  }

  static generateFingerprint(payload) {
    const canonical = {
      cycle_id: payload.cycle_id,
      sources: payload.sources || [],
      ranking_before: (payload.ranking_before || []).map(r => `${r.id || r}:${r.score || 0}`),
      ranking_after: (payload.ranking_after || []).map(r => `${r.id || r}:${r.score || 0}`),
      diff: payload.diff || {}
    };
    return crypto.createHash('sha256').update(JSON.stringify(canonical)).digest('hex');
  }

  validateCycleCompleteness(cycleData) {
    const missing = [];
    if (!cycleData.cycle_id || !/^MONEY-\d{4}-\d{2}-\d{2}/.test(cycleData.cycle_id)) {
      missing.push('cycle_id (must match MONEY-YYYY-MM-DD pattern)');
    }
    if (!cycleData.started_at) missing.push('started_at');
    if (!cycleData.finished_at) missing.push('finished_at');
    if (!Array.isArray(cycleData.sources) || cycleData.sources.length === 0) {
      missing.push('sources (must be non-empty array)');
    } else {
      for (const s of cycleData.sources) {
        if (!s.uri || !s.date) missing.push('sources entries must contain uri and date');
      }
    }
    if (!Array.isArray(cycleData.ranking_after) || cycleData.ranking_after.length === 0) {
      missing.push('ranking_after (must be non-empty array)');
    }
    if (!cycleData.diff || typeof cycleData.diff !== 'object') {
      missing.push('diff (must be an object)');
    }
    if (!cycleData.validation || cycleData.validation.passed !== true) {
      missing.push('validation (validation.passed must be strictly true)');
    }
    if (!cycleData.artifact_refs || !Array.isArray(cycleData.artifact_refs)) {
      missing.push('artifact_refs (must be an array)');
    }
    return {
      is_complete: missing.length === 0,
      missing
    };
  }

  recordCycle(cycleData) {
    const cycleId = cycleData.cycle_id;
    if (!cycleId) {
      throw new Error('[CYCLE_LEDGER_ERROR] cycle_id is mandatory');
    }

    // Idempotency check: If an identical cycle is already recorded, return existing
    if (this.cycles.has(cycleId)) {
      const existing = this.cycles.get(cycleId);
      const fp = CycleLedger.generateFingerprint(cycleData);
      if (existing.fingerprint === fp) {
        return {
          status: 'IDEMPOTENT_NOOP',
          cycle: existing
        };
      }
    }

    const validation = this.validateCycleCompleteness(cycleData);
    const fingerprint = CycleLedger.generateFingerprint(cycleData);

    const record = {
      cycle_id: cycleId,
      cycle_type: cycleData.cycle_type || CYCLE_TYPES.WEEKLY_RADAR,
      started_at: cycleData.started_at || new Date().toISOString(),
      finished_at: cycleData.finished_at || new Date().toISOString(),
      sources: cycleData.sources || [],
      ranking_before: cycleData.ranking_before || [],
      ranking_after: cycleData.ranking_after || [],
      diff: cycleData.diff || {},
      validation: cycleData.validation || { passed: false },
      artifact_refs: cycleData.artifact_refs || [],
      fingerprint: fingerprint,
      status: validation.is_complete ? CYCLE_STATUS.VERIFIED : CYCLE_STATUS.REJECTED,
      validation_errors: validation.missing
    };

    this.cycles.set(cycleId, record);
    this._persist();

    return {
      status: record.status,
      cycle: record
    };
  }

  getCycle(cycleId) {
    return this.cycles.get(cycleId) || null;
  }

  detectMissedCycles(expectedCycleIds) {
    const missed = [];
    for (const id of expectedCycleIds) {
      const existing = this.cycles.get(id);
      if (!existing || existing.status !== CYCLE_STATUS.VERIFIED) {
        missed.push(id);
      }
    }
    return missed;
  }

  catchUpMissedCycle(missedCycleId, synthesizerFn) {
    if (this.cycles.has(missedCycleId) && this.cycles.get(missedCycleId).status === CYCLE_STATUS.VERIFIED) {
      return { status: 'ALREADY_VERIFIED', cycle: this.cycles.get(missedCycleId) };
    }
    const syntheticPayload = synthesizerFn(missedCycleId);
    return this.recordCycle(syntheticPayload);
  }
}

module.exports = {
  CYCLE_TYPES,
  CYCLE_STATUS,
  CycleLedger
};
