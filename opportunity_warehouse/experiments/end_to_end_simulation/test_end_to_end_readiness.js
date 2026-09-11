const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RevenueObserver } = require('../../experiments/revenue_observer/lib/revenue_observer');
const { StateReconstructor } = require('../../experiments/state_reconstruction/lib/state_reconstructor');

const sandboxDir = path.join(__dirname, 'sandbox_sim');
if (fs.existsSync(sandboxDir)) fs.rmSync(sandboxDir, { recursive: true, force: true });
fs.mkdirSync(sandboxDir, { recursive: true });

const inbox = path.join(sandboxDir, 'inbox');
const processed = path.join(sandboxDir, 'processed');
const evidence = path.join(sandboxDir, 'evidence');
const snapshot = path.join(sandboxDir, 'SNAPSHOT.json');
const checkpoint = path.join(sandboxDir, 'CHECKPOINT.json');

fs.mkdirSync(inbox, { recursive: true });
fs.mkdirSync(evidence, { recursive: true });

// 1. Initial State: 97% Symphony, 0 Revenue
fs.writeFileSync(snapshot, JSON.stringify({
  symphony_overall: { percent: 97, remaining_to_v1: 3 },
  subsystems: { revenue_proof: 0 },
  proven_revenue_eur: 0
}, null, 2), 'utf8');

fs.writeFileSync(checkpoint, JSON.stringify({
  completed_phases: ['P1', 'P2', 'P3']
}, null, 2), 'utf8');

const observer = new RevenueObserver({
  inboxDir: inbox,
  processedDir: processed,
  evidenceDir: evidence,
  snapshotPath: snapshot
});

console.log('--- SIMULATION STEP 1: Pre-Launch Empty Poll ---');
const emptyPoll = observer.processInbox();
assert.strictEqual(emptyPoll.length, 0);
assert.strictEqual(observer.ledger.getRealRevenueTotal(), 0.0);
console.log('PASS [Step 1]: Pre-launch inbox empty; zero revenue recorded.');

console.log('--- SIMULATION STEP 2: Live Customer Purchase (€5.00) Arrives in Inbox ---');
const liveOrder = {
  order_id: 'ORD-LIVE-EUR5-77889',
  product_id: 'OPP-SEED-DIGITAL-01',
  product_name: 'agent-context-trimmer v1.0.0',
  gross_amount_eur: 5.00,
  currency: 'EUR',
  payment_status: 'PAID',
  customer_email: 'verified_developer@agency.io',
  receipt_url: 'https://gumroad.com/receipt?id=REC-77889'
};
fs.writeFileSync(path.join(inbox, 'order_live_001.json'), JSON.stringify(liveOrder, null, 2), 'utf8');

console.log('--- SIMULATION STEP 3: Automated Order Ingestion & Settlement ---');
const settleResults = observer.processInbox();
assert.strictEqual(settleResults.length, 1);
assert.strictEqual(settleResults[0].status, 'SETTLED');
assert.strictEqual(settleResults[0].revenue_eur, 5.00);
assert.strictEqual(observer.ledger.getRealRevenueTotal(), 5.00);

// Check snapshot promoted to 100%
const promotedSnap = JSON.parse(fs.readFileSync(snapshot, 'utf8'));
assert.strictEqual(promotedSnap.proven_revenue_eur, 5.00);
assert.strictEqual(promotedSnap.symphony_overall.percent, 100);
assert.strictEqual(promotedSnap.subsystems.revenue_proof, 100);
console.log('PASS [Step 3]: Real €5 revenue settled; snapshot successfully promoted to 100% Symphony convergence.');

console.log('--- SIMULATION STEP 4: State Reconstructor Validates Self-Healing Convergence ---');
const reconstructor = new StateReconstructor({
  evidenceDir: evidence,
  checkpointPath: checkpoint,
  snapshotPath: snapshot
});
const reconstructed = reconstructor.reconstructState();
assert.strictEqual(reconstructed.proven_revenue_eur, 5.00);
assert.strictEqual(reconstructed.symphony_overall.percent, 100);
assert(reconstructed.next_major_technical_gate.includes('COMMERCIAL_TRUTH_PROVEN'));
console.log('PASS [Step 4]: Independent state reconstructor confirms 100% convergence from durable ledger.');

// Clean up sandbox
fs.rmSync(sandboxDir, { recursive: true, force: true });
console.log('\n>>> ALL 4 END-TO-END SETTLEMENT SIMULATION STEPS PASS (100% DETERMINISTIC) <<<');
