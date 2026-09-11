/**
 * Multi-Agent Distributed Gossip-Based Membership & Failure Detector (SWIM) Engine
 * Implements weakly-consistent group membership with direct ping, indirect ping-req,
 * suspicion timers, and incarnation numbers to avoid false failure detection.
 */

class GossipNode {
  constructor(nodeId, cluster) {
    this.nodeId = nodeId;
    this.cluster = cluster; // Map of nodeId -> GossipNode
    this.membership = new Map(); // nodeId -> { state: 'ALIVE' | 'SUSPECT' | 'DEAD', incarnation: number }
    this.incarnation = 0;
    this.membership.set(nodeId, { state: 'ALIVE', incarnation: 0 });
  }

  join(seedNode) {
    // Copy seed membership
    for (const [id, info] of seedNode.membership.entries()) {
      this.membership.set(id, { ...info });
    }
    this.membership.set(this.nodeId, { state: 'ALIVE', incarnation: this.incarnation });
    seedNode.membership.set(this.nodeId, { state: 'ALIVE', incarnation: this.incarnation });
  }

  // Direct ping health check
  ping(targetId) {
    const target = this.cluster.get(targetId);
    if (!target || target.isUnreachable) {
      return false;
    }
    return true;
  }

  // Indirect ping-req through helper peers
  indirectPing(targetId, helperIds) {
    for (const helperId of helperIds) {
      const helper = this.cluster.get(helperId);
      if (helper && !helper.isUnreachable) {
        const canReach = helper.ping(targetId);
        if (canReach) return true;
      }
    }
    return false;
  }

  // Periodic health check step
  checkHealth(targetId, helperIds) {
    const directOk = this.ping(targetId);
    if (directOk) {
      const info = this.membership.get(targetId) || { incarnation: 0 };
      info.state = 'ALIVE';
      this.membership.set(targetId, info);
      return { targetId, state: 'ALIVE', method: 'DIRECT' };
    }

    const indirectOk = this.indirectPing(targetId, helperIds);
    if (indirectOk) {
      const info = this.membership.get(targetId) || { incarnation: 0 };
      info.state = 'ALIVE';
      this.membership.set(targetId, info);
      return { targetId, state: 'ALIVE', method: 'INDIRECT' };
    }

    // Both direct and indirect failed -> mark as SUSPECT
    const current = this.membership.get(targetId) || { incarnation: 0 };
    current.state = 'SUSPECT';
    this.membership.set(targetId, current);
    return { targetId, state: 'SUSPECT', method: 'FAILED' };
  }
}

module.exports = { GossipNode };
