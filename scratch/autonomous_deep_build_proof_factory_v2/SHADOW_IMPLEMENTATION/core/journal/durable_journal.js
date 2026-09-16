'use strict';

/**
 * SHADOW IMPLEMENTATION: DURABLE JOURNAL WITH SHA-256 HASH CHAINING
 * Component: shadow/core/journal/durable_journal.js
 * Mission: WINDOWS_AUTONOMOUS_DEEP_BUILD_PROOF_FACTORY_V2
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

class JournalIntegrityError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'JournalIntegrityError';
    this.details = details;
  }
}

class DurableJournal {
  constructor(journalPath, options = {}) {
    this.journalPath = journalPath;
    this.dir = path.dirname(journalPath);
    if (!fs.existsSync(this.dir)) {
      fs.mkdirSync(this.dir, { recursive: true });
    }

    // Mutation test switches
    this.disableHashChaining = options.disableHashChaining || false;
    this.failOpenOnGaps = options.failOpenOnGaps || false;

    this.lastSeq = 0;
    this.lastHash = '0000000000000000000000000000000000000000000000000000000000000000';
    this.events = [];

    this._initialize();
  }

  _initialize() {
    if (fs.existsSync(this.journalPath)) {
      this.verifyAndLoad();
    } else {
      fs.writeFileSync(this.journalPath, '', 'utf8');
    }
  }

  computeEntryHash(seq, prevHash, eventData) {
    if (this.disableHashChaining) {
      return 'static_mutant_hash';
    }
    const payload = `${seq}:${prevHash}:${JSON.stringify(eventData)}`;
    return crypto.createHash('sha256').update(payload).digest('hex');
  }

  append(eventData, explicitActor = 'SYSTEM') {
    const seq = this.lastSeq + 1;
    const prevHash = this.lastHash;
    const timestamp = new Date().toISOString();

    const entryPayload = {
      event_id: 'evt_' + crypto.randomBytes(6).toString('hex'),
      seq,
      prev_hash: prevHash,
      timestamp,
      actor: explicitActor,
      data: eventData
    };

    const entryHash = this.computeEntryHash(seq, prevHash, entryPayload.data);
    entryPayload.entry_hash = entryHash;

    const line = JSON.stringify(entryPayload) + '\n';
    fs.appendFileSync(this.journalPath, line, 'utf8');

    this.lastSeq = seq;
    this.lastHash = entryHash;
    this.events.push(entryPayload);

    return entryPayload;
  }

  appendEntry(eventData, explicitActor = 'SYSTEM') {
    return this.append(eventData, explicitActor);
  }

  verifyAndLoad() {
    if (!fs.existsSync(this.journalPath)) return [];
    const content = fs.readFileSync(this.journalPath, 'utf8');
    const lines = content.split('\n').filter(l => l.trim().length > 0);

    let expectedSeq = 1;
    let expectedPrevHash = '0000000000000000000000000000000000000000000000000000000000000000';
    const verifiedEvents = [];

    for (let i = 0; i < lines.length; i++) {
      let entry;
      try {
        entry = JSON.parse(lines[i]);
      } catch (err) {
        // Crash truncation recovery check
        if (i === lines.length - 1) {
          // Truncated trailing write; perform crash repair
          this._repairTruncatedTail(lines.slice(0, -1));
          break;
        } else {
          throw new JournalIntegrityError(`Corrupt JSON on line ${i + 1}`, { line: lines[i] });
        }
      }

      // Check sequence monotonicity
      if (entry.seq !== expectedSeq) {
        if (!this.failOpenOnGaps) {
          throw new JournalIntegrityError(
            `Sequence gap detected at line ${i + 1}: expected seq ${expectedSeq}, found ${entry.seq}`,
            { expectedSeq, foundSeq: entry.seq }
          );
        }
      }

      // Check hash chain continuity
      if (!this.disableHashChaining) {
        if (entry.prev_hash !== expectedPrevHash) {
          throw new JournalIntegrityError(
            `Hash chain broken at seq ${entry.seq}: expected prev_hash ${expectedPrevHash}, found ${entry.prev_hash}`,
            { seq: entry.seq, expectedPrevHash, foundPrevHash: entry.prev_hash }
          );
        }

        const calculatedHash = this.computeEntryHash(entry.seq, entry.prev_hash, entry.data);
        if (entry.entry_hash !== calculatedHash) {
          throw new JournalIntegrityError(
            `Entry hash mismatch at seq ${entry.seq}: stored ${entry.entry_hash}, computed ${calculatedHash}`,
            { seq: entry.seq, storedHash: entry.entry_hash, computedHash: calculatedHash }
          );
        }
      }

      expectedSeq = entry.seq + 1;
      expectedPrevHash = entry.entry_hash;
      verifiedEvents.push(entry);
    }

    this.lastSeq = verifiedEvents.length > 0 ? verifiedEvents[verifiedEvents.length - 1].seq : 0;
    this.lastHash = verifiedEvents.length > 0 ? verifiedEvents[verifiedEvents.length - 1].entry_hash : '0000000000000000000000000000000000000000000000000000000000000000';
    this.events = verifiedEvents;

    return verifiedEvents;
  }

  _repairTruncatedTail(validLines) {
    const repairedContent = validLines.map(l => l.trim()).join('\n') + (validLines.length > 0 ? '\n' : '');
    fs.writeFileSync(this.journalPath, repairedContent, 'utf8');
  }

  getAllEvents() {
    return [...this.events];
  }
}

module.exports = {
  DurableJournal,
  JournalIntegrityError
};
