/**
 * Multi-Agent Distributed Consistent Snapshot Engine (Chandy-Lamport V2)
 * Coordinates consistent global snapshots across asynchronous agent communication channels
 * capturing local agent state vectors and in-transit messages.
 */

class SnapshotNode {
  constructor(nodeId, network) {
    this.nodeId = nodeId;
    this.network = network; // Map of nodeId -> SnapshotNode
    this.localState = { contextTokens: 0, sequence: 0 };
    this.snapshot = null;
    this.recordingChannels = new Map(); // channelId -> Array of messages
    this.markersReceived = new Set();
  }

  updateState(tokensDelta) {
    this.localState.contextTokens += tokensDelta;
    this.localState.sequence++;
  }

  initiateSnapshot(snapshotId) {
    this.snapshot = {
      snapshotId,
      nodeId: this.nodeId,
      state: { ...this.localState },
      channelStates: {}
    };

    const peers = Array.from(this.network.keys()).filter(id => id !== this.nodeId);
    for (const peerId of peers) {
      this.recordingChannels.set(peerId, []);
      const peer = this.network.get(peerId);
      peer.receiveMarker(this.nodeId, snapshotId);
    }
  }

  receiveMarker(senderId, snapshotId) {
    if (!this.snapshot) {
      // First marker seen: save local state and propagate marker
      this.snapshot = {
        snapshotId,
        nodeId: this.nodeId,
        state: { ...this.localState },
        channelStates: {}
      };
      this.markersReceived.add(senderId);

      const peers = Array.from(this.network.keys()).filter(id => id !== this.nodeId);
      for (const peerId of peers) {
        if (peerId !== senderId) {
          this.recordingChannels.set(peerId, []);
          const peer = this.network.get(peerId);
          peer.receiveMarker(this.nodeId, snapshotId);
        }
      }
    } else {
      // Subsequent marker on channel: stop recording that channel
      this.markersReceived.add(senderId);
      if (this.recordingChannels.has(senderId)) {
        this.snapshot.channelStates[senderId] = [...this.recordingChannels.get(senderId)];
        this.recordingChannels.delete(senderId);
      }
    }
  }

  receiveMessage(senderId, message) {
    if (this.recordingChannels.has(senderId)) {
      this.recordingChannels.get(senderId).push(message);
    }
    this.updateState(message.tokenCount || 0);
  }
}

module.exports = { SnapshotNode };
