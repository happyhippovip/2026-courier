const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { VCGTokenAuction } = require('../lib/vcg_auction');

const auction = new VCGTokenAuction(500); // 500 token capacity

const bids = [
  { agentId: 'agent_A', tokensRequested: 300, bidValue: 60 },
  { agentId: 'agent_B', tokensRequested: 200, bidValue: 50 },
  { agentId: 'agent_C', tokensRequested: 300, bidValue: 40 }
];

// Test 1: Optimal allocation under capacity constraint (500)
// Agent A (300, 60) + Agent B (200, 50) = 500 tokens, welfare = 110 (optimal!)
// Agent C (300, 40) is left out.
const outcome = auction.runAuction(bids);
assert.strictEqual(outcome.totalWelfare, 110);
assert.strictEqual(outcome.totalTokensAllocated, 500);
console.log('✓ Test 1: Social welfare maximizing allocation achieved (Welfare: 110, Tokens: 500/500)');

// Test 2: VCG externality payments accurately computed
const allocA = outcome.allocations.find(a => a.agentId === 'agent_A');
const allocB = outcome.allocations.find(a => a.agentId === 'agent_B');
const allocC = outcome.allocations.find(a => a.agentId === 'agent_C');

// Without Agent A: remaining bids are B (200, 50) and C (300, 40). Both fit (500 tokens)! Welfare without A = 90.
// Others in optimal: B has 50.
// Payment A = 90 - 50 = 40!
assert.strictEqual(allocA.won, true);
assert.strictEqual(allocA.vcgPayment, 40);
assert.strictEqual(allocA.netUtility, 20); // 60 - 40 = 20

// Without Agent B: remaining bids are A (300, 60) and C (300, 40). Only one fits. Optimal without B is A (60).
// Others in optimal: A has 60.
// Payment B = 60 - 60 = 0!
assert.strictEqual(allocB.won, true);
assert.strictEqual(allocB.vcgPayment, 0);
assert.strictEqual(allocB.netUtility, 50);

// Agent C lost
assert.strictEqual(allocC.won, false);
assert.strictEqual(allocC.vcgPayment, 0);
console.log('✓ Test 2: VCG externality payments verified (Agent A pays 40, Agent B pays 0)');

// Test 3: Uncontended allocation yields zero payment
const uncontendedAuction = new VCGTokenAuction(1000);
const uncontendedOutcome = uncontendedAuction.runAuction([
  { agentId: 'agent_X', tokensRequested: 200, bidValue: 100 }
]);
assert.strictEqual(uncontendedOutcome.allocations[0].vcgPayment, 0, 'Uncontended agent pays 0');
console.log('✓ Test 3: Uncontended agent pays 0 externality');

// Test 4: Write sample evidence report
const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_VCG_AUCTION_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  auctionParameters: { capacity: 500 },
  bidsSubmitted: bids,
  auctionOutcome: outcome
}, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_VCG_AUCTION_REPORT.json');

console.log('All VCG Token Auction tests passed successfully!');
