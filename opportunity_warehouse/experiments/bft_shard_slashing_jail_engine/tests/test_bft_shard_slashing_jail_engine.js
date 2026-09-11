const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BFTShardSlashingJailEngine } = require('../lib/bft_shard_slashing_jail_engine');

console.log('Testing BFT Shard Dynamic Slashing & Jail Consensus Engine...');
const engine = new BFTShardSlashingJailEngine({
  slashPenaltyFraction: 0.25,
  defaultJailDurationEpochs: 4
});

engine.registerValidator('val-malicious-01', 1000);
assert.ok(engine.isEligible('val-malicious-01'));

// Double-sign equivocation evidence
const evidence = {
  validatorId: 'val-malicious-01',
  view: 12,
  blockA: { hash: 'hash_block_12a', height: 12 },
  blockB: { hash: 'hash_block_12b', height: 12 }
};

const incident = engine.processEquivocationEvidence(evidence);
assert.strictEqual(incident.slashedAmount, 250);
assert.strictEqual(incident.remainingStake, 750);
assert.strictEqual(incident.jailedUntilEpoch, 4);

// Validator should now be jailed and not eligible
assert.ok(!engine.isEligible('val-malicious-01'));

// Fast forward epoch to 4 -> eligible again
engine.advanceEpoch(4);
assert.ok(engine.isEligible('val-malicious-01'));

const report = {
  experiment: 'bft_shard_slashing_jail_engine',
  status: 'VERIFIED',
  testSuite: 'test_bft_shard_slashing_jail_engine',
  lastIncident: incident,
  totalIncidents: engine.slashingIncidents.length,
  timestamp: new Date().toISOString()
};

fs.writeFileSync(
  path.join(__dirname, 'SAMPLE_BFT_SLASHING_JAIL_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);

console.log('✓ BFT Shard Dynamic Slashing & Jail Consensus Engine verified successfully.');
