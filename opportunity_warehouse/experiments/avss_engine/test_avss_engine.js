const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { AVSSEngine } = require('./lib/avss_engine');

console.log('Testing Asynchronous Verifiable Secret Sharing (AVSS) Engine...');

const engine = new AVSSEngine(1019, 509, 4);

// Secret = 42, threshold t = 2 (degree = 2, requires 3 shares)
const secret = 42;
const coeffs = engine.createPolynomial(secret, 2);
const commitments = engine.computeCommitments(coeffs);

// Generate shares for 5 agents (x = 1..5)
const shares = [];
for (let x = 1; x <= 5; x++) {
  const s = engine.evaluate(coeffs, x);
  shares.push([x, s]);
}

// Test 1: Each agent independently verifies their share against public commitments
for (const [x, s] of shares) {
  const valid = engine.verifyShare(x, s, commitments);
  assert.strictEqual(valid, true);
}
console.log('✓ Test 1: All 5 shares independently verified against Feldman homomorphic commitments');

// Test 2: Tampered share rejected
const tamperedShare = (shares[0][1] + 1) % 509;
const tamperedValid = engine.verifyShare(shares[0][0], tamperedShare, commitments);
assert.strictEqual(tamperedValid, false);
console.log('✓ Test 2: Tampered share correctly flagged as invalid');

// Test 3: Reconstruction using any 3 shares (e.g. shares for x=1, x=3, x=5)
const subset = [shares[0], shares[2], shares[4]];
const reconstructed = engine.reconstruct(subset);
assert.strictEqual(reconstructed, secret);
console.log('✓ Test 3: Secret successfully reconstructed from 3 valid shares (secret: ' + reconstructed + ')');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 391,
  component: 'avss_engine',
  primeModulusP: 1019,
  fieldOrderQ: 509,
  generatorG: 4,
  thresholdT: 2,
  sharesCount: 5,
  shareVerificationVerified: true,
  secretReconstructionVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_AVSS_ENGINE_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_AVSS_ENGINE_REPORT.json');
console.log('All AVSS Engine tests passed successfully!');
