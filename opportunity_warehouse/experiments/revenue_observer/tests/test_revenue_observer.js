const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RevenueObserver } = require('../lib/revenue_observer');

const tempDir = path.join(__dirname, 'temp_observer_test');
if (fs.existsSync(tempDir)) fs.rmSync(tempDir, { recursive: true, force: true });
fs.mkdirSync(tempDir, { recursive: true });

const testInbox = path.join(tempDir, 'inbox');
const testProcessed = path.join(tempDir, 'processed');
const testEvidence = path.join(tempDir, 'evidence');
const testSnapshot = path.join(tempDir, 'SNAPSHOT.json');

// Seed test snapshot
const initialSnapshot = {
  symphony_overall: { percent: 97, remaining_to_v1: 3 },
  subsystems: { revenue_proof: 0 },
  proven_revenue_eur: 0
};
fs.writeFileSync(testSnapshot, JSON.stringify(initialSnapshot, null, 2), 'utf8');

const observer = new RevenueObserver({
  inboxDir: testInbox,
  processedDir: testProcessed,
  evidenceDir: testEvidence,
  snapshotPath: testSnapshot
});

console.log('--- TEST 1: Rejection of Invalid / Zero Amount Orders ---');
fs.writeFileSync(path.join(testInbox, 'bad_order_1.json'), JSON.stringify({
  order_id: 'BAD-01',
  gross_amount_eur: 0,
  currency: 'EUR',
  payment_status: 'PAID',
  product_id: 'OPP-SEED-DIGITAL-01'
}), 'utf8');

const rejectResults = observer.processInbox();
assert.strictEqual(rejectResults.length, 1);
assert.strictEqual(rejectResults[0].status, 'REJECTED');
assert(rejectResults[0].error.includes('positive number'));
// Clean up rejected file from inbox
fs.unlinkSync(path.join(testInbox, 'bad_order_1.json'));
console.log('PASS [Test 1]: Zero-amount receipt rejected fail-closed.');

console.log('--- TEST 2: Valid Order Ingestion & Snapshot Promotion ---');
fs.writeFileSync(path.join(testInbox, 'order_real_001.json'), JSON.stringify({
  order_id: 'ORD-GUMROAD-99418',
  product_id: 'OPP-SEED-DIGITAL-01',
  product_name: 'agent-context-trimmer v1.0.0',
  gross_amount_eur: 5.00,
  currency: 'EUR',
  payment_status: 'PAID',
  customer_email: 'buyer@example.com',
  receipt_url: 'https://gumroad.com/receipt?id=REC-99418'
}), 'utf8');

const successResults = observer.processInbox();
assert.strictEqual(successResults.length, 1);
assert.strictEqual(successResults[0].status, 'SETTLED');
assert.strictEqual(successResults[0].revenue_eur, 5.00);

// Verify moved out of inbox into processed
assert(!fs.existsSync(path.join(testInbox, 'order_real_001.json')));
assert(fs.existsSync(path.join(testProcessed, 'order_real_001.json')));

// Verify EvidenceLedger contains verified 5.00
assert.strictEqual(observer.ledger.getRealRevenueTotal(), 5.00);

// Verify Progress Snapshot promoted to 100%
const updatedSnap = JSON.parse(fs.readFileSync(testSnapshot, 'utf8'));
assert.strictEqual(updatedSnap.proven_revenue_eur, 5.00);
assert.strictEqual(updatedSnap.symphony_overall.percent, 100);
assert.strictEqual(updatedSnap.subsystems.revenue_proof, 100);
assert(updatedSnap.next_major_technical_gate.includes('COMMERCIAL_TRUTH_PROVEN'));
console.log('PASS [Test 2]: Valid order settles revenue and promotes snapshot to 100% Symphony convergence.');

console.log('--- TEST 3: Idempotent Replay Prevention ---');
// Try placing duplicate processed order back into inbox
fs.copyFileSync(path.join(testProcessed, 'order_real_001.json'), path.join(testInbox, 'order_real_001.json'));
const duplicateResults = observer.processInbox();
assert.strictEqual(duplicateResults.length, 1);
assert.strictEqual(duplicateResults[0].status, 'SETTLED');
// Revenue must still be strictly 5.00 (not 10.00)
assert.strictEqual(observer.ledger.getRealRevenueTotal(), 5.00);
console.log('PASS [Test 3]: Duplicate order settlement is strictly idempotent and prevents double counting.');

// Clean up
fs.rmSync(tempDir, { recursive: true, force: true });
console.log('\n>>> ALL 3 REVENUE OBSERVER INTEGRATION TESTS PASS (100% DETERMINISTIC) <<<');
