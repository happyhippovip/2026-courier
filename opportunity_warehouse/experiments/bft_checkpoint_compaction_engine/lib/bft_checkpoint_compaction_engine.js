/**
 * Multi-Agent Distributed Asynchronous Verifiable Byzantine Checkpoint Compaction Engine
 * Periodically generates 2f+1 certified stable checkpoints to safely prune historical blocks
 * and state transitions, bounding memory and disk footprint while preserving verifiable state continuity.
 */

const crypto = require('crypto');

function hashObject(obj) {
  return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex');
}

class CheckpointCertificate {
  constructor(blockHeight, stateRoot, signatures) {
    this.blockHeight = blockHeight;
    this.stateRoot = stateRoot;
    this.signatures = signatures;
    this.certId = hashObject({ blockHeight, stateRoot, sigs: signatures.map(s => s.nodeId).sort() });
    this.timestamp = Date.now();
  }
}

class BFTCheckpointCompactionEngine {
  constructor(nodeCount = 4, checkpointInterval = 5) {
    this.nodeCount = nodeCount;
    this.f = Math.floor((nodeCount - 1) / 3); // f=1
    this.quorumSize = 2 * this.f + 1; // 3
    this.checkpointInterval = checkpointInterval;

    this.blocks = new Map(); // height -> block
    this.stateRoots = new Map(); // height -> stateRoot
    this.checkpointVotes = new Map(); // "height:nodeId" -> sig
    this.stableCheckpoints = new Map(); // height -> CheckpointCertificate
    this.lastTruncatedHeight = 0;

    // Genesis Block at Height 0
    this._addGenesis();
  }

  _addGenesis() {
    const genesis = { height: 0, parentHash: '0000', txs: [], blockHash: 'genesis_hash' };
    this.blocks.set(0, genesis);
    this.stateRoots.set(0, 'state_root_genesis');
  }

  appendBlock(height, parentHash, txs, stateRoot) {
    if (height <= this.lastTruncatedHeight) {
      throw new Error('Cannot append block below or at truncated height: ' + this.lastTruncatedHeight);
    }
    const block = { height, parentHash, txs, blockHash: hashObject({ height, parentHash, txs }) };
    this.blocks.set(height, block);
    this.stateRoots.set(height, stateRoot);
    return block;
  }

  signCheckpoint(height, stateRoot, nodeId) {
    if (!this.stateRoots.has(height)) {
      throw new Error('Cannot sign checkpoint for unknown block height: ' + height);
    }
    const localRoot = this.stateRoots.get(height);
    if (localRoot !== stateRoot) {
      throw new Error('State root mismatch for height ' + height + ': local ' + localRoot + ' !== ' + stateRoot);
    }

    const voteKey = height + ':' + nodeId;
    if (this.checkpointVotes.has(voteKey)) {
      throw new Error('Double signing checkpoint detected from node ' + nodeId);
    }

    const sig = hashObject({ height, stateRoot, nodeId, role: 'CHECKPOINT_SIGNATURE' });
    this.checkpointVotes.set(voteKey, { nodeId, sig });

    // Collect votes for this height and stateRoot
    const matchingVotes = [];
    for (const [k, v] of this.checkpointVotes.entries()) {
      if (k.startsWith(height + ':')) {
        matchingVotes.push(v);
      }
    }

    if (matchingVotes.length >= this.quorumSize && !this.stableCheckpoints.has(height)) {
      const cert = new CheckpointCertificate(height, stateRoot, matchingVotes.slice(0, this.quorumSize));
      this.stableCheckpoints.set(height, cert);
      return { certCreated: true, cert };
    }

    return { certCreated: false, voteCount: matchingVotes.length };
  }

  truncateHistory(checkpointHeight) {
    const cert = this.stableCheckpoints.get(checkpointHeight);
    if (!cert) {
      throw new Error('Cannot truncate history: stable checkpoint missing for height ' + checkpointHeight);
    }

    let prunedBlocks = 0;
    for (const [h, b] of this.blocks.entries()) {
      if (h < checkpointHeight) {
        this.blocks.delete(h);
        prunedBlocks++;
      }
    }

    this.lastTruncatedHeight = checkpointHeight;
    return {
      truncatedToHeight: checkpointHeight,
      prunedBlocks,
      activeBlocksRemaining: this.blocks.size,
      stableCheckpointStateRoot: cert.stateRoot
    };
  }

  getStats() {
    return {
      nodeCount: this.nodeCount,
      activeBlocksCount: this.blocks.size,
      stableCheckpointsCount: this.stableCheckpoints.size,
      lastTruncatedHeight: this.lastTruncatedHeight
    };
  }
}

module.exports = { CheckpointCertificate, BFTCheckpointCompactionEngine };
