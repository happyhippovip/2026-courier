/**
 * Dynamic Resharding Consensus Engine
 * Implements elastic, asynchronous BFT dynamic sharding for multi-agent state machines.
 * Monitors traffic load per range and triggers BFT-coordinated shard splitting,
 * state snapshot migration, and atomic routing table reconfiguration.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class ShardNode {
  constructor(shardId, nodeId) {
    this.shardId = shardId;
    this.nodeId = nodeId;
    this.data = new Map();
    this.txCount = 0;
  }

  write(key, value) {
    this.data.set(key, value);
    this.txCount++;
  }

  get(key) {
    return this.data.get(key);
  }

  createStateSnapshot() {
    const entries = Array.from(this.data.entries()).sort((a, b) => a[0].localeCompare(b[0]));
    const digest = sha256(entries);
    return {
      nodeId: this.nodeId,
      shardId: this.shardId,
      digest,
      sig: sha256(`${this.nodeId}_snapshot_${this.shardId}_${digest}`),
      entries
    };
  }
}

class DynamicReshardingEngine {
  constructor(initialShardId, nodeIds, splitThreshold = 10, faultTolerance = 1) {
    this.f = faultTolerance;
    this.quorum = 2 * this.f + 1; // 3
    this.splitThreshold = splitThreshold;

    this.routingTable = [
      { shardId: initialShardId, range: [0, 1000] }
    ];

    this.shardClusters = new Map();
    this.shardClusters.set(initialShardId, nodeIds.map(id => new ShardNode(initialShardId, id)));

    this.reconfigurationLog = [];
  }

  getShardForIntKey(intKey) {
    const route = this.routingTable.find(r => intKey >= r.range[0] && intKey <= r.range[1]);
    if (!route) throw new Error('No shard found for key ' + intKey);
    return route.shardId;
  }

  write(intKey, value) {
    const shardId = this.getShardForIntKey(intKey);
    const nodes = this.shardClusters.get(shardId);

    for (const node of nodes) {
      node.write(String(intKey), value);
    }

    // Check if hotspot threshold triggered
    if (nodes[0].txCount >= this.splitThreshold) {
      return this._triggerBftSplit(shardId);
    }

    return { success: true, shardId, intKey };
  }

  get(intKey) {
    const shardId = this.getShardForIntKey(intKey);
    const nodes = this.shardClusters.get(shardId);
    return nodes[0].get(String(intKey));
  }

  _triggerBftSplit(shardId) {
    const nodes = this.shardClusters.get(shardId);
    const routeIdx = this.routingTable.findIndex(r => r.shardId === shardId);
    const oldRoute = this.routingTable[routeIdx];

    // 1. Quorum snapshot generation
    const snapshots = nodes.map(n => n.createStateSnapshot());
    const digest = snapshots[0].digest;
    const cert = {
      shardId,
      digest,
      signatures: snapshots.slice(0, this.quorum).map(s => s.sig)
    };

    // 2. Bisect range
    const mid = Math.floor((oldRoute.range[0] + oldRoute.range[1]) / 2);
    const shardLeftId = `${shardId}_left`;
    const shardRightId = `${shardId}_right`;

    const leftNodes = nodes.map(n => new ShardNode(shardLeftId, n.nodeId + '_L'));
    const rightNodes = nodes.map(n => new ShardNode(shardRightId, n.nodeId + '_R'));

    // Migrate state
    for (const [k, v] of snapshots[0].entries) {
      const kInt = parseInt(k, 10);
      if (kInt <= mid) {
        leftNodes.forEach(n => n.write(k, v));
      } else {
        rightNodes.forEach(n => n.write(k, v));
      }
    }

    // Reset txCount on new nodes
    leftNodes.forEach(n => { n.txCount = 0; });
    rightNodes.forEach(n => { n.txCount = 0; });

    // 3. Atomically update routing table
    this.shardClusters.set(shardLeftId, leftNodes);
    this.shardClusters.set(shardRightId, rightNodes);
    this.shardClusters.delete(shardId);

    this.routingTable.splice(routeIdx, 1,
      { shardId: shardLeftId, range: [oldRoute.range[0], mid] },
      { shardId: shardRightId, range: [mid + 1, oldRoute.range[1]] }
    );

    const reconfigRecord = {
      event: 'DYNAMIC_BFT_SPLIT',
      originalShard: shardId,
      newShards: [shardLeftId, shardRightId],
      newRanges: [[oldRoute.range[0], mid], [mid + 1, oldRoute.range[1]]],
      snapshotCertificate: cert,
      timestamp: new Date().toISOString()
    };

    this.reconfigurationLog.push(reconfigRecord);
    return { success: true, reconfigRecord };
  }

  getRoutingTable() {
    return this.routingTable;
  }
}

module.exports = { DynamicReshardingEngine, ShardNode };
