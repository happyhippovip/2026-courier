
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { EvidenceLedger, SIGNAL_CLASSES } = require('../../../money_factory/evidence_ledger');

const testStorage = path.join(__dirname, 'test_evidence');
if (fs.existsSync(testStorage)) fs.rmSync(testStorage, { recursive: true, force: true });
fs.mkdirSync(testStorage, { recursive: true });

const ledger = new EvidenceLedger(testStorage);

console.log('[TEST 1] Valid Order Ingestion...');
const validReceipt = {
  opportunity_id: 'OPP-SEED-DIGITAL-01',
  source_type: 'GUMROAD_WEBHOOK',
  claim: 'Customer purchased agent-context-trimmer v1.0.0',
  signal_class: SIGNAL_CLASSES.REAL_REVENUE,
  claim_value_eur: 5.00,
  verified: true,
  external_verification_artifact: 'https://gumroad.com/receipt?id=REC-TEST-001',
  raw_payload: { order_id: 'ORD-TEST-001', gross_amount_eur: 5.00 }
};

const entry1 = ledger.recordEvidence(validReceipt);
assert.strictEqual(entry1.verified, true);
assert.strictEqual(entry1.claim_value_eur, 5.00);
assert.strictEqual(ledger.getRealRevenueTotal('OPP-SEED-DIGITAL-01'), 5.00);

console.log('[TEST 2] Idempotency: Duplicate Settlement Prevention...');
const entry2 = ledger.recordEvidence(validReceipt);
assert.strictEqual(entry2.evidence_id, entry1.evidence_id, 'Duplicate order should return existing entry');
assert.strictEqual(ledger.getRealRevenueTotal('OPP-SEED-DIGITAL-01'), 5.00, 'Total revenue must not double-count');

console.log('[TEST 3] Fail-Closed: Unverified Real Revenue Rejection...');
assert.throws(() => {
  ledger.recordEvidence({
    opportunity_id: 'OPP-SEED-DIGITAL-01',
    source_type: 'MODEL_ASSERTION',
    claim: 'AI predicts $5 revenue',
    signal_class: SIGNAL_CLASSES.REAL_REVENUE,
    claim_value_eur: 5.00,
    verified: false
  });
}, /EVIDENCE_ERROR/, 'Model assertion or unverified claim must throw');

console.log('[TEST 4] Fail-Closed: Zero or Negative Revenue Rejection...');
assert.throws(() => {
  ledger.recordEvidence({
    opportunity_id: 'OPP-SEED-DIGITAL-01',
    source_type: 'GUMROAD_WEBHOOK',
    claim: 'Free order',
    signal_class: SIGNAL_CLASSES.REAL_REVENUE,
    claim_value_eur: 0.00,
    verified: true,
    external_verification_artifact: 'rec_0'
  });
}, /EVIDENCE_ERROR/, 'Zero or negative revenue must throw');

// Clean up
fs.rmSync(testStorage, { recursive: true, force: true });
console.log('\n>>> ALL 4 ORDER SETTLEMENT INTEGRATION TESTS PASS (100% DETERMINISTIC) <<<');
