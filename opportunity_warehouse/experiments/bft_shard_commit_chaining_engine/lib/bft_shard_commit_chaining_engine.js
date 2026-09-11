/**
 * Byzantine Dynamic Shard State Commit-Proof Chaining Consensus Engine
 * Chains cryptographic Commit Proofs (CP) across sharded BFT clusters,
 * enabling asynchronous cross-shard transactions without cross-cluster consensus stalls.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class BFTShardCommitChainingEngine {
  constructor(shardId, quorumThreshold = 3) {
    this.shardId = shardId;
    this.quorumThreshold = quorumThreshold;
    this.commitProofs = new Map(); // blockHash -> CommitProof
    this.chainedBlocks = [];
  }

  generateCommitProof(blockNumber, stateRoot, signatures) {
    const validSignatures = new Set();
    const payloadHash = sha256({ shardId: this.shardId, blockNumber, stateRoot });

    for (const sig of signatures) {
      const expected = sha256(`${sig.nodeId}:${payloadHash}`);
      if (sig.signature === expected) {
        validSignatures.add(sig.nodeId);
      }
    }

    if (validSignatures.size < this.quorumThreshold) {
      return { verified: false, validSignatures: validSignatures.size, required: this.quorumThreshold };
    }

    const proof = {
      shardId: this.shardId,
      blockNumber,
      stateRoot,
      proofHash: payloadHash,
      signers: Array.from(validSignatures),
      timestamp: Date.now()
    };

    this.commitProofs.set(payloadHash, proof);
    return { verified: true, proof };
  }

  proposeChainedCrossShardBlock(blockNumber, crossShardTx, parentProofHash) {
    // Verify that the referenced parent commit proof exists and is valid
    if (!this.commitProofs.has(parentProofHash)) {
      throw new Error(`Invalid parent commit proof: ${parentProofHash} not found or unverified`);
    }

    const parentProof = this.commitProofs.get(parentProofHash);

    const block = {
      shardId: this.shardId,
      blockNumber,
      crossShardTx,
      parentProofHash,
      parentBlockNumber: parentProof.blockNumber,
      parentShardId: parentProof.shardId,
      timestamp: Date.now()
    };
    block.blockHash = sha256(block);
    this.chainedBlocks.push(block);

    return block;
  }

  verifyChainIntegrity() {
    for (const block of this.chainedBlocks) {
      if (!this.commitProofs.has(block.parentProofHash)) return false;
      const proof = this.commitProofs.get(block.parentProofHash);
      if (proof.signers.length < this.quorumThreshold) return false;
    }
    return true;
  }
}

module.exports = { BFTShardCommitChainingEngine };
