const crypto = require('crypto');

class CheckpointLedger {
  constructor() {
    this.entries = [];
  }

  hash(str) {
    return crypto.createHash('sha256').update(str || '').digest('hex');
  }

  recordRun(options = {}) {
    const { runId, originalText, trimmedText, metadata } = options;
    const origHash = this.hash(originalText);
    const trimHash = this.hash(trimmedText);

    const origBytes = originalText ? Buffer.byteLength(originalText, 'utf8') : 0;
    const trimBytes = trimmedText ? Buffer.byteLength(trimmedText, 'utf8') : 0;
    const bytesSaved = Math.max(0, origBytes - trimBytes);

    const entry = {
      runId: runId || 'run_' + Date.now().toString(36),
      timestamp: new Date().toISOString(),
      originalHash: origHash,
      trimmedHash: trimHash,
      originalBytes: origBytes,
      trimmedBytes: trimBytes,
      bytesSaved,
      reductionPct: origBytes > 0 ? Number(((bytesSaved / origBytes) * 100).toFixed(2)) : 0,
      metadata: metadata || {}
    };

    this.entries.push(entry);
    return entry;
  }

  findByRunId(runId) {
    return this.entries.find(e => e.runId === runId) || null;
  }

  getSummary() {
    let totalOrig = 0;
    let totalTrim = 0;
    for (const e of this.entries) {
      totalOrig += e.originalBytes;
      totalTrim += e.trimmedBytes;
    }
    const totalSaved = Math.max(0, totalOrig - totalTrim);
    return {
      totalRuns: this.entries.length,
      totalOriginalBytes: totalOrig,
      totalTrimmedBytes: totalTrim,
      totalBytesSaved: totalSaved,
      overallReductionPct: totalOrig > 0 ? Number(((totalSaved / totalOrig) * 100).toFixed(2)) : 0
    };
  }
}

module.exports = { CheckpointLedger };
