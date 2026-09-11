const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BFTEpochGasAuctionEngine } = require('../lib/bft_epoch_gas_auction_engine');

console.log('Testing BFT Dynamic Epoch Gas Token Auction Consensus Engine...');

const engine = new BFTEpochGasAuctionEngine('node_0', 1000);

// Test 1: Submit bids
const b1 = engine.submitBid('agent_A', 400, 20);
const b2 = engine.submitBid('agent_B', 400, 15);
const b3 = engine.submitBid('agent_C', 400, 10);
assert.strictEqual(engine.bids.length, 3);
console.log('✓ Test 1: 3 competitive gas bids collected for epoch allocation');

// Test 2: Resolve uniform clearing price auction
const res = engine.resolveAuction(1);
assert.strictEqual(res.allocatedGas, 1000);
assert.strictEqual(res.clearingPrice, 10); // agent_C is marginal winner with 200 units
assert.strictEqual(res.allocations.length, 3);
assert.strictEqual(res.allocations[0].allocatedGas, 400); // agent_A full
assert.strictEqual(res.allocations[1].allocatedGas, 400); // agent_B full
assert.strictEqual(res.allocations[2].allocatedGas, 200); // agent_C partial
console.log('✓ Test 2: Uniform price auction cleared 1000 units with clearing price 10');

// Test 3: Quorum Certification
const sig0 = { nodeId: 'node_0', signature: require('crypto').createHash('sha256').update('node_0:' + res.hash + ':1').digest('hex') };
const sig1 = { nodeId: 'node_1', signature: require('crypto').createHash('sha256').update('node_1:' + res.hash + ':1').digest('hex') };
const sig2 = { nodeId: 'node_2', signature: require('crypto').createHash('sha256').update('node_2:' + res.hash + ':1').digest('hex') };

const cert = engine.certifyAuction(res, [sig0, sig1, sig2], 3);
assert.strictEqual(cert.certified, true);
assert.strictEqual(cert.certifiedRecord.quorumCert.count, 3);
console.log('✓ Test 3: 2f+1 quorum certification completed for auction epoch 1');

// Test 4: Sub-quorum rejected fail-closed
const res2 = engine.resolveAuction(2);
const certFail = engine.certifyAuction(res2, [sig0], 3);
assert.strictEqual(certFail.certified, false);
console.log('✓ Test 4: Insufficient signature set rejected fail-closed');

// Test 5: Export evidence report
const evidenceReport = {
  experiment: 'bft_epoch_gas_auction_engine',
  timestamp: new Date().toISOString(),
  totalCapacity: engine.totalCapacity,
  lastClearedEpoch: cert.certifiedRecord.auctionResult.epoch,
  clearingPrice: cert.certifiedRecord.auctionResult.clearingPrice,
  allocatedGas: cert.certifiedRecord.auctionResult.allocatedGas,
  status: 'VERIFIED'
};

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_EPOCH_GAS_AUCTION_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.strictEqual(fs.existsSync(evidencePath), true);
console.log('✓ Test 5: Evidence report written to SAMPLE_EPOCH_GAS_AUCTION_REPORT.json');

console.log('All BFT Epoch Gas Auction Engine tests passed successfully!');
