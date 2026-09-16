'use strict';

const fs = require('fs');
const path = require('path');
const { LegacyAdapter } = require('./legacy_adapter');

/**
 * MigrationEngine
 * Executes crash-resilient migration from legacy RC3 state to V2.
 */
class MigrationEngine {
  constructor(options = {}) {
    this.adapter = options.adapter || new LegacyAdapter();
    this.storageDir = options.storageDir || './migration_data';
    this.checkpointFile = path.join(this.storageDir, 'migration_checkpoint.json');
    this.lockFile = path.join(this.storageDir, 'migration.lock');
    this.quarantineFile = path.join(this.storageDir, 'quarantine.jsonl');
  }

  acquireLock() {
    fs.mkdirSync(this.storageDir, { recursive: true });
    if (fs.existsSync(this.lockFile)) {
      const lockData = fs.readFileSync(this.lockFile, 'utf8');
      throw new Error(`Migration locked by process: ${lockData}`);
    }
    fs.writeFileSync(this.lockFile, JSON.stringify({ pid: process.pid, time: Date.now() }), 'utf8');
  }

  releaseLock() {
    if (fs.existsSync(this.lockFile)) {
      fs.unlinkSync(this.lockFile);
    }
  }

  loadCheckpoint() {
    if (fs.existsSync(this.checkpointFile)) {
      return JSON.parse(fs.readFileSync(this.checkpointFile, 'utf8'));
    }
    return { migrated_count: 0, last_seq: 0, status: 'NOT_STARTED', completed: false };
  }

  saveCheckpoint(checkpoint) {
    fs.mkdirSync(this.storageDir, { recursive: true });
    fs.writeFileSync(this.checkpointFile, JSON.stringify(checkpoint, null, 2), 'utf8');
  }

  migrateRecords(records, crashSimulation = null) {
    this.acquireLock();
    try {
      let checkpoint = this.loadCheckpoint();
      const migrated = [];
      const quarantined = [];

      // Crash at 0% simulation
      if (crashSimulation === 'CRASH_AT_0_PCT' && checkpoint.status === 'NOT_STARTED') {
        checkpoint.status = 'IN_PROGRESS';
        this.saveCheckpoint(checkpoint);
        throw new Error('SIMULATED_CRASH_AT_0_PERCENT');
      }

      const startIndex = checkpoint.migrated_count;

      for (let i = startIndex; i < records.length; i++) {
        // Crash at 50% simulation
        if (crashSimulation === 'CRASH_AT_50_PCT' && i === Math.floor(records.length / 2)) {
          checkpoint.migrated_count = i;
          checkpoint.status = 'IN_PROGRESS';
          this.saveCheckpoint(checkpoint);
          throw new Error('SIMULATED_CRASH_AT_50_PERCENT');
        }

        const raw = records[i];
        try {
          if (!raw || typeof raw !== 'object' || Object.keys(raw).length === 0) {
            throw new Error('Malformed record structure');
          }
          const adapted = this.adapter.adaptTaskRecord(raw);
          migrated.push(adapted);
          checkpoint.migrated_count++;
          checkpoint.last_seq = i + 1;
        } catch (err) {
          quarantined.push({ raw, error: err.message, index: i });
          fs.appendFileSync(this.quarantineFile, JSON.stringify({ raw, error: err.message }) + '\n', 'utf8');
        }
      }

      // Crash at 100% simulation (after records migrated, before lock release)
      if (crashSimulation === 'CRASH_AT_100_PCT' && !checkpoint.completed) {
        checkpoint.completed = true;
        checkpoint.status = 'COMPLETED';
        this.saveCheckpoint(checkpoint);
        throw new Error('SIMULATED_CRASH_AT_100_PERCENT');
      }

      checkpoint.status = 'COMPLETED';
      checkpoint.completed = true;
      this.saveCheckpoint(checkpoint);

      return {
        success: true,
        migrated_count: checkpoint.migrated_count,
        quarantined_count: quarantined.length,
        migrated,
        quarantined
      };
    } finally {
      this.releaseLock();
    }
  }
}

module.exports = { MigrationEngine };
