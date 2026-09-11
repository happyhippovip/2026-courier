/**
 * Byzantine Dynamic Shard State Re-balancing Consensus Engine
 * Detects cross-shard transaction hotspots and coordinates atomic key-range
 * re-partitioning and state migration certified by cross-shard 2f+1 quorums.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class BFTShardRebalancingEngine {
  constructor(shardId, totalShards = 2) {
    this.shardId = shardId;
    this.totalShards = totalShards;
    this.routingTable = new Map(); // keyPrefix -> shardId
    this.loadStats = new Map();    // shardId -> txCount
    this.rebalanceHistory = [];
  }

  setRoutingTable(tableObj) {
    this.routingTable.clear();
    for (const [prefix, sid] of Object.entries(tableObj)) {
      this.routingTable.set(prefix, sid);
    }
  }

  recordLoad(shardId, txCount) {
    this.loadStats.set(shardId, (this.loadStats.get(shardId) || 0) + txCount);
  }

  detectImbalance(imbalanceRatioThreshold = 2.0) {
    const s0Load = this.loadStats.get('shard_0') || 0;
    const s1Load = this.loadStats.get('shard_1') || 0;
    const maxLoad = Math.max(s0Load, s1Load);
    const minLoad = Math.max(1, Math.min(s0Load, s1Load));

    const ratio = maxLoad / minLoad;
    return {
      imbalanced: ratio >= imbalanceRatioThreshold,
      ratio: Number(ratio.toFixed(2)),
      hotspot: s0Load > s1Load ? 'shard_0' : 'shard_1'
    };
  }

  proposeRebalance(epoch, migrationPlan) {
    const proposal = {
      epoch,
      sourceShard: migrationPlan.sourceShard,
      targetShard: migrationPlan.targetShard,
      migratedPrefixes: migrationPlan.prefixes,
      timestamp: Date.now()
    };
    proposal.hash = sha256(proposal);
    return proposal;
  }

  certifyRebalance(proposal, signatures, quorumThreshold = 3) {
    const validSigners = new Set();

    for (const sig of signatures) {
      const expected = sha256(`${sig.nodeId}:${proposal.hash}:${proposal.epoch}`);
      if (sig.signature === expected) {
        validSigners.add(sig.nodeId);
      }
    }

    if (validSigners.size < quorumThreshold) {
      return { committed: false, validSigners: validSigners.size, required: quorumThreshold };
    }

    // Apply migration to routing table
    for (const p of proposal.migratedPrefixes) {
      this.routingTable.set(p, proposal.targetShard);
    }

    const commitRecord = {
      epoch: proposal.epoch,
      proposal,
      signers: Array.from(validSigners),
      newRouting: Object.fromEntries(this.routingTable)
    };
    this.rebalanceHistory.push(commitRecord);

    return { committed: true, commitRecord };
  }

  routeKey(key) {
    for (const [prefix, sid] of this.routingTable.entries()) {
      if (key.startsWith(prefix)) return sid;
    }
    return this.shardId; // fallback
  }
}

module.exports = { BFTShardRebalancingEngine };
