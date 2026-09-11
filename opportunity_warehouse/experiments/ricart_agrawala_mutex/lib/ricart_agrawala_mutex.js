/**
 * Ricart-Agrawala Distributed Mutual Exclusion Engine
 * Implements optimal distributed lock arbitration across autonomous agents
 * using Lamport logical timestamps, deterministic tie-breaking, and deferred queueing.
 */

class RicartAgrawalaNode {
  constructor(nodeId, networkMesh) {
    this.nodeId = nodeId;
    this.networkMesh = networkMesh; // Map of nodeId -> RicartAgrawalaNode
    this.logicalClock = 0;
    this.state = 'RELEASED'; // 'RELEASED' | 'WANTED' | 'HELD'
    this.requestTimestamp = 0;
    this.deferredReplies = [];
    this.outstandingReplies = 0;
    this.criticalSectionCallback = null;
  }

  tick() {
    this.logicalClock++;
    return this.logicalClock;
  }

  updateClock(incomingClock) {
    this.logicalClock = Math.max(this.logicalClock, incomingClock) + 1;
    return this.logicalClock;
  }

  // Request entry to the critical section
  requestCS(onEnter) {
    this.tick();
    this.state = 'WANTED';
    this.requestTimestamp = this.logicalClock;
    this.criticalSectionCallback = onEnter;

    const peers = Array.from(this.networkMesh.keys()).filter(id => id !== this.nodeId);
    this.outstandingReplies = peers.length;

    if (this.outstandingReplies === 0) {
      this.state = 'HELD';
      if (this.criticalSectionCallback) this.criticalSectionCallback();
      return;
    }

    for (const peerId of peers) {
      const peer = this.networkMesh.get(peerId);
      peer.handleRequest({
        from: this.nodeId,
        timestamp: this.requestTimestamp
      });
    }
  }

  // Handle incoming REQUEST message
  handleRequest(req) {
    this.updateClock(req.timestamp);

    const hasPriority = (
      this.state === 'HELD' ||
      (this.state === 'WANTED' && (
        this.requestTimestamp < req.timestamp ||
        (this.requestTimestamp === req.timestamp && this.nodeId < req.from)
      ))
    );

    if (hasPriority) {
      this.deferredReplies.push(req.from);
    } else {
      const sender = this.networkMesh.get(req.from);
      sender.handleReply({ from: this.nodeId, timestamp: this.logicalClock });
    }
  }

  // Handle incoming REPLY message
  handleReply(reply) {
    this.updateClock(reply.timestamp);
    this.outstandingReplies--;

    if (this.outstandingReplies === 0 && this.state === 'WANTED') {
      this.state = 'HELD';
      if (this.criticalSectionCallback) {
        this.criticalSectionCallback();
      }
    }
  }

  // Exit the critical section and flush deferred replies
  releaseCS() {
    this.state = 'RELEASED';
    const queue = [...this.deferredReplies];
    this.deferredReplies = [];

    for (const peerId of queue) {
      const peer = this.networkMesh.get(peerId);
      peer.handleReply({ from: this.nodeId, timestamp: this.tick() });
    }
  }
}

module.exports = { RicartAgrawalaNode };
