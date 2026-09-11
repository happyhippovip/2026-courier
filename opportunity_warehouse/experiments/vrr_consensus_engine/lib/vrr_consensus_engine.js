/**
 * Multi-Agent Distributed Viewstamped Replication Revisited (VRR) Engine
 * Implements Primary-Backup consensus with View Numbers, Op Numbers,
 * and View Change state transition upon primary failure.
 */

class VRRReplica {
  constructor(replicaId, cluster) {
    this.replicaId = replicaId;
    this.cluster = cluster; // Map of replicaId -> VRRReplica
    this.viewNumber = 0;
    this.status = 'NORMAL'; // 'NORMAL' | 'VIEW_CHANGE'
    this.opNumber = 0;
    this.commitNumber = 0;
    this.log = [];
    this.viewChangeVotes = new Map(); // view -> Set of replicaIds
  }

  isPrimary() {
    const ids = Array.from(this.cluster.keys()).sort();
    return ids[this.viewNumber % ids.length] === this.replicaId;
  }

  // Client requests transaction to primary
  clientRequest(operation) {
    if (!this.isPrimary() || this.status !== 'NORMAL') {
      throw new Error('Not primary or not in NORMAL status');
    }

    this.opNumber++;
    const opRecord = { view: this.viewNumber, op: this.opNumber, operation };
    this.log.push(opRecord);

    // Send PREPARE to backups
    let prepareOkCount = 1; // Self
    const majority = Math.floor(this.cluster.size / 2) + 1;

    for (const [id, backup] of this.cluster.entries()) {
      if (id !== this.replicaId) {
        const ok = backup.handlePrepare(this.viewNumber, this.opNumber, operation, this.commitNumber);
        if (ok) prepareOkCount++;
      }
    }

    if (prepareOkCount >= majority) {
      this.commitNumber = this.opNumber;
      return { status: 'COMMITTED', opNumber: this.opNumber, view: this.viewNumber };
    }

    return { status: 'PREPARE_FAILED' };
  }

  handlePrepare(view, op, operation, commitNum) {
    if (view === this.viewNumber && this.status === 'NORMAL') {
      this.opNumber = op;
      this.log.push({ view, op, operation });
      this.commitNumber = commitNum;
      return true;
    }
    return false;
  }

  // Trigger View Change upon primary failure
  startViewChange(newView) {
    this.status = 'VIEW_CHANGE';
    this.viewNumber = newView;
    if (!this.viewChangeVotes.has(newView)) {
      this.viewChangeVotes.set(newView, new Set());
    }
    this.viewChangeVotes.get(newView).add(this.replicaId);

    const majority = Math.floor(this.cluster.size / 2) + 1;
    for (const [id, peer] of this.cluster.entries()) {
      if (id !== this.replicaId) {
        peer.handleStartViewChange(newView, this.replicaId);
      }
    }

    if (this.viewChangeVotes.get(newView).size >= majority && this.isPrimary()) {
      this.status = 'NORMAL';
      return { status: 'NEW_VIEW_ESTABLISHED', view: newView };
    }
  }

  handleStartViewChange(newView, senderId) {
    if (newView > this.viewNumber) {
      this.status = 'VIEW_CHANGE';
      this.viewNumber = newView;
    }
    if (newView === this.viewNumber) {
      if (!this.viewChangeVotes.has(newView)) {
        this.viewChangeVotes.set(newView, new Set());
      }
      this.viewChangeVotes.get(newView).add(senderId);
      const majority = Math.floor(this.cluster.size / 2) + 1;
      if (this.viewChangeVotes.get(newView).size >= majority && this.isPrimary()) {
        this.status = 'NORMAL';
      }
    }
  }
}

module.exports = { VRRReplica };
