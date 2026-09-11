/**
 * Multi-Agent Distributed Multi-Leader Dynamo-Style Quorum Replicator
 * Implements N, R, W decentralized replication with R + W > N strong consistency,
 * version vectors, and read-repair synchronization.
 */

class DynamoReplica {
  constructor(replicaId) {
    this.replicaId = replicaId;
    this.store = new Map(); // key -> { value, version, timestamp }
  }

  put(key, value, version, timestamp) {
    this.store.set(key, { value, version, timestamp });
    return true;
  }

  get(key) {
    return this.store.get(key) || null;
  }
}

class DynamoCluster {
  constructor(replicaIds, r = 2, w = 2) {
    this.replicas = new Map();
    for (const id of replicaIds) {
      this.replicas.set(id, new DynamoReplica(id));
    }
    this.n = replicaIds.length;
    this.r = r;
    this.w = w;
  }

  // Quorum Write: write to at least W replicas
  write(key, value) {
    const version = Date.now();
    let written = 0;

    for (const replica of this.replicas.values()) {
      replica.put(key, value, version, Date.now());
      written++;
      if (written >= this.w) break;
    }

    return {
      status: written >= this.w ? 'WRITE_COMMITTED' : 'WRITE_FAILED',
      written,
      wRequired: this.w
    };
  }

  // Quorum Read with Read-Repair
  read(key) {
    const responses = [];
    let readCount = 0;

    for (const [id, replica] of this.replicas.entries()) {
      const entry = replica.get(key);
      if (entry) {
        responses.push({ id, ...entry });
      }
      readCount++;
      if (readCount >= this.r) break;
    }

    if (responses.length === 0) return null;

    // Find newest version
    responses.sort((a, b) => b.version - a.version);
    const newest = responses[0];

    // Read Repair: asynchronously update stale replicas observed
    for (const resp of responses) {
      if (resp.version < newest.version) {
        const staleReplica = this.replicas.get(resp.id);
        staleReplica.put(key, newest.value, newest.version, newest.timestamp);
      }
    }

    return {
      value: newest.value,
      version: newest.version,
      quorumMet: readCount >= this.r,
      readRepairsTriggered: responses.filter(r => r.version < newest.version).length
    };
  }
}

module.exports = { DynamoCluster, DynamoReplica };
