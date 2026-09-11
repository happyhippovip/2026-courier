/**
 * Multi-Agent Distributed Logical Matrix Clock Resolver Engine
 * Implements N x N matrix clocks where M[i][j] represents what node i knows
 * about node j's latest logical timestamp, enabling optimal log garbage collection.
 */

class MatrixClockNode {
  constructor(nodeId, nodeIndex, totalNodes) {
    this.nodeId = nodeId;
    this.nodeIndex = nodeIndex;
    this.totalNodes = totalNodes;
    // M[totalNodes][totalNodes] initialized to 0
    this.matrix = Array.from({ length: totalNodes }, () => new Array(totalNodes).fill(0));
    this.localLog = [];
  }

  // Local event occurred
  tick() {
    this.matrix[this.nodeIndex][this.nodeIndex]++;
    return this.matrix[this.nodeIndex][this.nodeIndex];
  }

  // Append entry to local log with current timestamp
  logEvent(data) {
    const timestamp = this.tick();
    const entry = { data, timestamp, nodeId: this.nodeId };
    this.localLog.push(entry);
    return entry;
  }

  // Receive message containing sender's matrix clock
  receiveMessage(senderIndex, senderMatrix) {
    this.tick();

    // Update row for self: element-wise max
    for (let j = 0; j < this.totalNodes; j++) {
      this.matrix[this.nodeIndex][j] = Math.max(
        this.matrix[this.nodeIndex][j],
        senderMatrix[senderIndex][j]
      );
    }

    // Update knowledge of what others know
    for (let i = 0; i < this.totalNodes; i++) {
      if (i !== this.nodeIndex) {
        for (let j = 0; j < this.totalNodes; j++) {
          this.matrix[i][j] = Math.max(this.matrix[i][j], senderMatrix[i][j]);
        }
      }
    }
  }

  // Find minimum timestamp for nodeIndex known by ALL nodes (safe GC threshold)
  getGarbageCollectionThreshold(targetIndex) {
    let minKnown = Infinity;
    for (let k = 0; k < this.totalNodes; k++) {
      if (this.matrix[k][targetIndex] < minKnown) {
        minKnown = this.matrix[k][targetIndex];
      }
    }
    return minKnown;
  }
}

module.exports = { MatrixClockNode };
