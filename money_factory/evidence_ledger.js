// Evidence Ledger — Canonical Economic Evidence Store
// Rules:
// 1. Every opportunity lifecycle decision must cite durable evidence.
// 2. No evidence-free transition to WINNER.
// 3. No model assertion counts as independent evidence.
// 4. Signal classes: REAL_REVENUE, REAL_PROFIT, REAL_COST, EXTERNAL_DEMAND_SIGNAL, LEADING_SIGNAL, SYNTHETIC_TEST_SIGNAL, UNKNOWN.

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const SIGNAL_CLASSES = Object.freeze({
  REAL_REVENUE: 'REAL_REVENUE',
  REAL_PROFIT: 'REAL_PROFIT',
  REAL_COST: 'REAL_COST',
  EXTERNAL_DEMAND_SIGNAL: 'EXTERNAL_DEMAND_SIGNAL',
  LEADING_SIGNAL: 'LEADING_SIGNAL',
  SYNTHETIC_TEST_SIGNAL: 'SYNTHETIC_TEST_SIGNAL',
  UNKNOWN: 'UNKNOWN'
});

class EvidenceLedger {
  constructor(storageDir = null, warehouse = null) {
    this.storageDir = storageDir || path.join(__dirname, '..', 'opportunity_warehouse', 'evidence');
    this.warehouse = warehouse;
    if (!fs.existsSync(this.storageDir)) {
      fs.mkdirSync(this.storageDir, { recursive: true });
    }
    this.ledgerFile = path.join(this.storageDir, 'evidence_ledger.jsonl');
    this.records = [];
    this._load();
  }

  _load() {
    if (fs.existsSync(this.ledgerFile)) {
      try {
        const lines = fs.readFileSync(this.ledgerFile, 'utf8').split('\n').filter(Boolean);
        this.records = [];
        for (const l of lines) {
          try {
            this.records.push(JSON.parse(l));
          } catch (lineErr) {
            // Trailing corruption recovery: skip incomplete/truncated lines from abrupt crash
          }
        }
      } catch (err) {
        console.error(`[EVIDENCE_LEDGER] Warning loading ${this.ledgerFile}:`, err.message);
      }
    }
  }

  static computeFingerprint({ opportunity_id, source_type, source_reference, claim, signal_class, timestamp }) {
    const canonical = {
      opportunity_id,
      source_type,
      source_reference,
      claim,
      signal_class,
      timestamp
    };
    return crypto.createHash('sha256').update(JSON.stringify(canonical)).digest('hex');
  }

  recordEvidence({
    opportunity_id,
    source_type,
    evidence_type,
    source_reference,
    source,
    claim,
    summary,
    signal_class = SIGNAL_CLASSES.UNKNOWN,
    confidence = 0.5,
    verified = false,
    claim_value_eur = 0.0,
    external_verification_artifact = null,
    raw_payload = null
  }) {
    const effectiveSourceType = source_type || evidence_type;
    const effectiveClaim = claim || summary;
    const effectiveSourceRef = source_reference || source || 'UNKNOWN';

    if (!opportunity_id || !effectiveSourceType || !effectiveClaim) {
      throw new Error('[EVIDENCE_ERROR] opportunity_id, source_type, and claim are required');
    }

    if (this.warehouse && typeof this.warehouse.getOpportunity === 'function') {
      const opp = this.warehouse.getOpportunity(opportunity_id);
      if (!opp) {
        throw new Error(`[EVIDENCE_ERROR] Opportunity '${opportunity_id}' does not exist in warehouse`);
      }
    }

    if (!Object.values(SIGNAL_CLASSES).includes(signal_class)) {
      throw new Error(`[EVIDENCE_ERROR] Invalid signal_class '${signal_class}'. Must be one of: ${Object.values(SIGNAL_CLASSES).join(', ')}`);
    }

    // Invariant: claim_value_eur validation
    if (signal_class === SIGNAL_CLASSES.REAL_REVENUE) {
      if (typeof claim_value_eur !== 'number' || isNaN(claim_value_eur) || claim_value_eur <= 0) {
        throw new Error('[EVIDENCE_ERROR] claim_value_eur must be a positive number for REAL_REVENUE');
      }
    }

    // Invariant: No model assertion counts as independent verification
    let isVerified = Boolean(verified);
    if (effectiveSourceType === 'MODEL_ASSERTION' || effectiveSourceType === 'INTERNAL_ESTIMATE' || effectiveSourceType === 'SYNTHETIC' || effectiveSourceRef === 'MODEL_INTERNAL_REASONING') {
      if (signal_class === SIGNAL_CLASSES.REAL_REVENUE) {
        throw new Error('[EVIDENCE_ERROR] Model assertions cannot count as independent evidence for REAL_REVENUE');
      }
      isVerified = false;
    }

    // Invariant: REAL_REVENUE strictly requires external verifiable artifact
    if (signal_class === SIGNAL_CLASSES.REAL_REVENUE && (!external_verification_artifact || !isVerified)) {
      throw new Error('[EVIDENCE_ERROR] REAL_REVENUE signal_class strictly requires verified external artifact (e.g. bank/payment receipt)');
    }

    // Invariant: REAL_REVENUE duplicate settlement prevention (idempotent no-op to prevent double-counting)
    if (signal_class === SIGNAL_CLASSES.REAL_REVENUE && isVerified) {
      const duplicate = this.records.find(r =>
        r.opportunity_id === opportunity_id &&
        r.signal_class === SIGNAL_CLASSES.REAL_REVENUE &&
        r.verified === true &&
        ((external_verification_artifact && r.external_verification_artifact === external_verification_artifact) ||
         (effectiveSourceRef !== 'UNKNOWN' && r.source_reference === effectiveSourceRef))
      );
      if (duplicate) {
        return duplicate;
      }
    }

    const timestamp = new Date().toISOString();
    const evidenceId = `EVD-MF-${Date.now()}-${crypto.randomBytes(3).toString('hex').toUpperCase()}`;
    const fingerprint = EvidenceLedger.computeFingerprint({
      opportunity_id,
      source_type: effectiveSourceType,
      source_reference: effectiveSourceRef,
      claim: effectiveClaim,
      signal_class,
      timestamp
    });

    const entry = {
      evidence_id: evidenceId,
      opportunity_id,
      timestamp,
      source_type: effectiveSourceType,
      evidence_type: effectiveSourceType,
      source_reference: effectiveSourceRef,
      source: effectiveSourceRef,
      claim: effectiveClaim,
      summary: effectiveClaim,
      signal_class,
      confidence: Math.max(0.0, Math.min(1.0, Number(confidence) || 0.5)),
      claim_value_eur: Number(claim_value_eur) || 0.0,
      fingerprint,
      verified: isVerified,
      external_verification_artifact,
      raw_payload
    };

    this.records.push(entry);

    // Ensure newline separation if prior write crashed without trailing newline
    if (fs.existsSync(this.ledgerFile)) {
      const stats = fs.statSync(this.ledgerFile);
      if (stats.size > 0) {
        const fd = fs.openSync(this.ledgerFile, 'r');
        const buf = Buffer.alloc(1);
        fs.readSync(fd, buf, 0, 1, stats.size - 1);
        fs.closeSync(fd);
        if (buf.toString('utf8') !== '\n') {
          fs.appendFileSync(this.ledgerFile, '\n', 'utf8');
        }
      }
    }

    fs.appendFileSync(this.ledgerFile, JSON.stringify(entry) + '\n', 'utf8');

    return entry;
  }

  getEvidenceForOpportunity(opportunityId) {
    return this.records.filter(r => r.opportunity_id === opportunityId);
  }

  hasVerifiedSignal(opportunityId, signalClass) {
    return this.records.some(r => r.opportunity_id === opportunityId && r.signal_class === signalClass && r.verified === true);
  }

  getRealRevenueTotal(opportunityId = null) {
    // Invariant: REAL_REVENUE must be strictly 0 unless verified real external revenue evidence exists
    let total = 0;
    const targets = opportunityId ? this.getEvidenceForOpportunity(opportunityId) : this.records;
    for (const r of targets) {
      if (r.signal_class === SIGNAL_CLASSES.REAL_REVENUE && r.verified === true) {
        total += Number(r.claim_value_eur || 0);
      }
    }
    return total;
  }
}

module.exports = {
  SIGNAL_CLASSES,
  EvidenceLedger
};
