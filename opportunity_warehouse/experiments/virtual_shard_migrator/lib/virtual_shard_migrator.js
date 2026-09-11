/**
 * Multi-Agent Distributed Consistent Hash Ring Virtual Shard Migrator
 * Manages dynamic shard splitting and non-blocking data migration
 * across distributed agent context nodes to eliminate load hotspots.
 */

class VirtualShardMigrator {
  constructor() {
    this.shards = new Map(); // shardId -> { range: [start, end], ownerNode: string, count: number, state: 'ACTIVE' | 'SPLITTING' }
    this.nextShardId = 1;
  }

  createInitialShard(start, end, ownerNode) {
    const id = 'shard-' + this.nextShardId++;
    this.shards.set(id, { range: [start, end], ownerNode, count: 0, state: 'ACTIVE' });
    return id;
  }

  recordWrite(shardId) {
    const shard = this.shards.get(shardId);
    if (!shard) return null;
    shard.count++;

    // Hotspot trigger threshold: count >= 100
    if (shard.count >= 100 && shard.state === 'ACTIVE') {
      return this.initiateSplit(shardId);
    }
    return null;
  }

  initiateSplit(shardId) {
    const shard = this.shards.get(shardId);
    shard.state = 'SPLITTING';

    const [start, end] = shard.range;
    const mid = Math.floor((start + end) / 2);

    const childA = 'shard-' + this.nextShardId++;
    const childB = 'shard-' + this.nextShardId++;

    this.shards.set(childA, { range: [start, mid], ownerNode: shard.ownerNode, count: Math.floor(shard.count / 2), state: 'ACTIVE' });
    this.shards.set(childB, { range: [mid + 1, end], ownerNode: shard.ownerNode + '-replica', count: Math.ceil(shard.count / 2), state: 'ACTIVE' });

    this.shards.delete(shardId);

    return {
      parentShard: shardId,
      newShards: [childA, childB],
      status: 'SPLIT_COMPLETED'
    };
  }
}

module.exports = { VirtualShardMigrator };
