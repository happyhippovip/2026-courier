/**
 * BFT Shard Finality Ratchet Consensus Engine
 * Implements monotonic epoch ratcheting across distributed shard quorums.
 * Prevents historical rollback and enforces forward-progress invariants during network partitions.
 */

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

class BftShardRatchetEngine {
  constructor(options = {}) {
    this.shardId = options.shardId || 'shard-0';
    this.currentEpoch = 0;
    this.highestCommittedEpoch = 0;
    this.epochCommitments = new Map();
    this.ratchetHistory = [];
  }

  proposeEpochTransition(proposedEpoch, stateRoot, quorumSignatures) {
    // Invariant 1: Monotonic forward ratchet (never regress or repeat)
    if (proposedEpoch <= this.highestCommittedEpoch) {
      throw new Error(`RATCHET_VIOLATION: Proposed epoch ${proposedEpoch} must be strictly greater than committed ${this.highestCommittedEpoch}`);
    }

    // Invariant 2: Quorum threshold verification (2f + 1)
    const requiredQuorum = 3;
    if (!quorumSignatures || quorumSignatures.length < requiredQuorum) {
      throw new Error(`QUORUM_DEFICIT: Received ${quorumSignatures ? quorumSignatures.length : 0} signatures, minimum ${requiredQuorum} required`);
    }

    const commitment = {
      shardId: this.shardId,
      epoch: proposedEpoch,
      previousEpoch: this.highestCommittedEpoch,
      stateRoot,
      signatures: quorumSignatures,
      ratchetTimestamp: new Date().toISOString(),
      commitmentHash: crypto.createHash('sha256').update(`${this.shardId}:${proposedEpoch}:${stateRoot}`).digest('hex')
    };

    this.highestCommittedEpoch = proposedEpoch;
    this.currentEpoch = proposedEpoch;
    this.epochCommitments.set(proposedEpoch, commitment);
    this.ratchetHistory.push(commitment);

    return commitment;
  }

  getRatchetProof(epoch) {
    return this.epochCommitments.get(epoch) || null;
  }
}

function runSelfTest() {
  console.log('Testing BFT Shard Finality Ratchet Consensus Engine...');
  const engine = new BftShardRatchetEngine({ shardId: 'shard-alpha' });

  // Test 1: Epoch 1 commit with valid 2f+1 signatures
  const sigs1 = ['sig-node-1', 'sig-node-2', 'sig-node-3'];
  const c1 = engine.proposeEpochTransition(1, '0xaaa111...', sigs1);
  console.log('✓ Test 1: Epoch 1 successfully committed with 2f+1 quorum (hash:', c1.commitmentHash.substring(0, 10), '...)');

  // Test 2: Epoch 2 commit
  const sigs2 = ['sig-node-1', 'sig-node-3', 'sig-node-4'];
  const c2 = engine.proposeEpochTransition(2, '0xbbb222...', sigs2);
  console.log('✓ Test 2: Epoch 2 ratcheted forward monotonically (prev:', c2.previousEpoch, 'curr:', c2.epoch, ')');

  // Test 3: Rollback rejection invariant
  let caughtRollback = false;
  try {
    engine.proposeEpochTransition(1, '0xinvalid...', sigs2);
  } catch (err) {
    caughtRollback = true;
    console.log('✓ Test 3: Rollback attempt to Epoch 1 rejected fail-closed:', err.message);
  }
  if (!caughtRollback) throw new Error('Failed to reject rollback!');

  // Test 4: Quorum deficit rejection
  let caughtQuorum = false;
  try {
    engine.proposeEpochTransition(3, '0xccc333...', ['sig-only-1']);
  } catch (err) {
    caughtQuorum = true;
    console.log('✓ Test 4: Quorum deficit rejected fail-closed:', err.message);
  }
  if (!caughtQuorum) throw new Error('Failed to reject quorum deficit!');

  const report = {
    test: 'BFT_SHARD_RATCHET_ENGINE',
    passed: true,
    highestEpoch: engine.highestCommittedEpoch,
    historyLength: engine.ratchetHistory.length,
    timestamp: new Date().toISOString()
  };

  fs.writeFileSync(path.join(__dirname, 'evidence', 'SAMPLE_BFT_SHARD_RATCHET_REPORT.json'), JSON.stringify(report, null, 2));
  console.log('✓ Test 5: Evidence report written to SAMPLE_BFT_SHARD_RATCHET_REPORT.json');
  console.log('All BFT Shard Finality Ratchet Consensus tests passed successfully!');
}

if (require.main === module) {
  runSelfTest();
}

module.exports = { BftShardRatchetEngine };
