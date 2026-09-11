const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { StateReconstructor } = require('../lib/state_reconstructor');

const tempDir = path.join(__dirname, 'temp_recon_test');
if (fs.existsSync(tempDir)) fs.rmSync(tempDir, { recursive: true, force: true });
fs.mkdirSync(tempDir, { recursive: true });

const testEvidence = path.join(tempDir, 'evidence');
const testCheckpoint = path.join(tempDir, 'CHECKPOINT.json');
const testSnapshot = path.join(tempDir, 'SNAPSHOT.json');

fs.mkdirSync(testEvidence, { recursive: true });
fs.writeFileSync(testCheckpoint, JSON.stringify({ completed_phases: ['P1', 'P2', 'P3'] }), 'utf8');

const reconstructor = new StateReconstructor({
  evidenceDir: testEvidence,
  checkpointPath: testCheckpoint,
  snapshotPath: testSnapshot
});

console.log('--- TEST 1: Baseline Reconstruction (Pre-Revenue) ---');
const baseline = reconstructor.reconstructState();
assert.strictEqual(baseline.symphony_overall.percent, 97);
assert.strictEqual(baseline.symphony_overall.remaining_to_v1, 3);
assert.strictEqual(baseline.proven_revenue_eur, 0);
assert.strictEqual(baseline.completed_intelligence_phases, 3);
console.log('PASS [Test 1]: Pre-revenue snapshot reconstructed accurately (97% Symphony, 0% Revenue).');

console.log('--- TEST 2: Reconstruction Post-Revenue Achievement ---');
// Record €5 in evidence ledger
const { SIGNAL_CLASSES } = require('../../../../money_factory/evidence_ledger');
reconstructor.ledger.recordEvidence({
  opportunity_id: 'OPP-SEED-DIGITAL-01',
  source_type: 'GUMROAD_WEBHOOK',
  claim: 'Test Order €5',
  signal_class: SIGNAL_CLASSES.REAL_REVENUE,
  claim_value_eur: 5.00,
  verified: true,
  external_verification_artifact: 'https://gumroad.com/receipt?id=123'
});

const postRev = reconstructor.reconstructState();
assert.strictEqual(postRev.symphony_overall.percent, 100);
assert.strictEqual(postRev.symphony_overall.remaining_to_v1, 0);
assert.strictEqual(postRev.subsystems.revenue_proof, 100);
assert.strictEqual(postRev.proven_revenue_eur, 5.00);
assert(postRev.next_major_technical_gate.includes('COMMERCIAL_TRUTH_PROVEN'));
console.log('PASS [Test 2]: Post-revenue state promotes seamlessly to 100% Symphony Convergence.');

// Clean up
fs.rmSync(tempDir, { recursive: true, force: true });
console.log('\n>>> ALL 2 STATE RECONSTRUCTOR TESTS PASS (100% DETERMINISTIC) <<<');
