/**
 * Multi-Agent Distributed Multi-Raft Partitioned Shard Replication Engine
 * Hosts multiple independent Raft consensus groups on a common physical node pool,
 * providing isolated failure domains and linear horizontal scale per shard.
 */

class RaftShardGroup {
  constructor(shardId, nodePool) {
    this.shardId = shardId;
    this.nodePool = nodePool; // Array of node IDs participating in this shard
    this.leaderId = null;
    this.term = 0;
    this.log = [];
  }

  electLeader(nodeId) {
    if (!this.nodePool.includes(nodeId)) {
      throw new Error('Node not in shard pool');
    }
    this.term++;
    this.leaderId = nodeId;
    return { shardId: this.shardId, leaderId: this.leaderId, term: this.term };
  }

  appendEntry(entry) {
    if (!this.leaderId) {
      throw new Error('No leader elected for shard ' + this.shardId);
    }
    const record = { shardId: this.shardId, index: this.log.length, term: this.term, entry };
    this.log.push(record);
    return record;
  }
}

class MultiRaftNode {
  constructor(nodeId) {
    this.nodeId = nodeId;
    this.activeShardGroups = new Map(); // shardId -> RaftShardGroup
  }

  registerShard(shardGroup) {
    this.activeShardGroups.set(shardGroup.shardId, shardGroup);
  }

  routeTransaction(shardId, data) {
    const shard = this.activeShardGroups.get(shardId);
    if (!shard) throw new Error('Unknown shard: ' + shardId);
    return shard.appendEntry(data);
  }
}

module.exports = { MultiRaftNode, RaftShardGroup };
