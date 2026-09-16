'use strict';

const crypto = require('crypto');

/**
 * VirtualSoakSimulator
 * Simulates extended multi-day and multi-year operations across accelerated
 * virtual time to verify resource stability, log compaction, and leak-free operation.
 */
class VirtualSoakSimulator {
  constructor(options = {}) {
    this.virtualClockMs = options.startTimeMs || Date.now();
    this.maxJournalEntriesBeforeCompaction = options.maxJournalEntriesBeforeCompaction || 500;
    this.retainedTasks = new Map();
    this.journal = [];
    this.compactedSnapshots = [];
    this.activeLeases = new Set();
    this.activeHandles = 0;
    this.allowTaskRetentionLeak = options.allowTaskRetentionLeak || false;
  }

  advanceTime(deltaMs) {
    this.virtualClockMs += deltaMs;
  }

  now() {
    return this.virtualClockMs;
  }

  recordJournalEntry(entry) {
    const prevHash = this.journal.length > 0
      ? this.journal[this.journal.length - 1].hash
      : (this.compactedSnapshots.length > 0 ? this.compactedSnapshots[this.compactedSnapshots.length - 1].anchorHash : '0'.repeat(64));

    const seq = this.journal.length + 1;
    const canonical = JSON.stringify({ seq, prevHash, entry, time: this.virtualClockMs });
    const hash = crypto.createHash('sha256').update(canonical).digest('hex');

    this.journal.push({ seq, prevHash, entry, hash, time: this.virtualClockMs });

    // Compaction trigger
    if (this.journal.length >= this.maxJournalEntriesBeforeCompaction) {
      this.compactJournal();
    }
  }

  compactJournal() {
    if (this.journal.length === 0) return;

    const lastEntry = this.journal[this.journal.length - 1];
    const snapshot = {
      snapshotId: `snap_${this.compactedSnapshots.length + 1}`,
      compactedAtVirtualTime: this.virtualClockMs,
      entriesCompacted: this.journal.length,
      anchorHash: lastEntry.hash,
      stateSummary: {
        activeLeasesCount: this.activeLeases.size,
        activeHandlesCount: this.activeHandles
      }
    };

    this.compactedSnapshots.push(snapshot);
    // Keep only last 50 entries as active tail buffer
    this.journal = this.journal.slice(-50);
  }

  simulateTaskLifecycle(taskId) {
    // 1. Acquire lease
    const leaseId = `lease_${taskId}`;
    this.activeLeases.add(leaseId);
    this.activeHandles++;

    // 2. Dispatch event
    this.recordJournalEntry({ type: 'TASK_DISPATCHED', taskId, leaseId });

    // 3. Work execution & deliverable
    if (this.allowTaskRetentionLeak) {
      this.retainedTasks.set(taskId, { id: taskId, data: 'x'.repeat(1000) }); // Leak simulation
    }

    // 4. Complete & release
    this.activeLeases.delete(leaseId);
    this.activeHandles--;
    this.recordJournalEntry({ type: 'TASK_COMPLETED', taskId, leaseId });
  }

  runSimulation({ durationMs, taskIntervalMs, tasksPerInterval = 1 }) {
    const endTime = this.virtualClockMs + durationMs;
    let completedTasks = 0;

    while (this.virtualClockMs < endTime) {
      for (let i = 0; i < tasksPerInterval; i++) {
        completedTasks++;
        this.simulateTaskLifecycle(`task_${completedTasks}`);
      }
      this.advanceTime(taskIntervalMs);
    }

    return {
      completedTasks,
      virtualDurationMs: durationMs,
      finalVirtualTime: this.virtualClockMs,
      activeLeasesRemaining: this.activeLeases.size,
      activeHandlesRemaining: this.activeHandles,
      retainedTasksRemaining: this.retainedTasks.size,
      compactedSnapshotsCount: this.compactedSnapshots.length,
      activeJournalEntries: this.journal.length
    };
  }
}

module.exports = { VirtualSoakSimulator };
