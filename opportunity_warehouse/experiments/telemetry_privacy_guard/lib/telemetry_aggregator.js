/**
 * telemetry_aggregator.js - Anonymized Usage Telemetry Aggregator & Privacy Guard
 * Strips all PII, hashes machine identifiers with one-way salt, and produces bucketized privacy metrics.
 */
const crypto = require('crypto');

class TelemetryPrivacyGuard {
  constructor(options = {}) {
    this.salt = options.salt || 'symphony_static_privacy_salt_2026';
    this.tokenBucketSize = options.tokenBucketSize || 50;
    this.latencyBucketMs = options.latencyBucketMs || 10;
  }

  hashIdentifier(rawId) {
    if (!rawId) return 'anon_' + crypto.randomBytes(4).toString('hex');
    return crypto.createHmac('sha256', this.salt).update(String(rawId)).digest('hex').substring(0, 16);
  }

  bucketize(value, bucketSize) {
    if (typeof value !== 'number' || isNaN(value)) return 0;
    return Math.round(value / bucketSize) * bucketSize;
  }

  sanitizeEvent(rawEvent = {}) {
    const machineHash = this.hashIdentifier(rawEvent.machineId || rawEvent.workspacePath || 'unknown');
    const tokensSaved = this.bucketize(rawEvent.tokensSaved || 0, this.tokenBucketSize);
    const latencyMs = this.bucketize(rawEvent.latencyMs || 0, this.latencyBucketMs);

    const cleanEvent = {
      eventTimestamp: new Date().toISOString(),
      machineHash,
      version: rawEvent.version || '1.0.0',
      command: rawEvent.command || 'trim',
      tokensSaved,
      latencyMs,
      rulesAppliedCount: typeof rawEvent.rulesAppliedCount === 'number' ? rawEvent.rulesAppliedCount : 0,
      exitCode: typeof rawEvent.exitCode === 'number' ? rawEvent.exitCode : 0,
      success: rawEvent.exitCode === 0
    };

    return cleanEvent;
  }

  aggregate(events = []) {
    const cleanEvents = events.map(e => this.sanitizeEvent(e));
    let totalTokensSaved = 0;
    let totalLatencyMs = 0;
    let totalSuccess = 0;
    const machineSet = new Set();

    cleanEvents.forEach(e => {
      totalTokensSaved += e.tokensSaved;
      totalLatencyMs += e.latencyMs;
      if (e.success) totalSuccess++;
      machineSet.add(e.machineHash);
    });

    const count = cleanEvents.length;
    const avgLatency = count > 0 ? Math.round(totalLatencyMs / count) : 0;
    const successRate = count > 0 ? +(totalSuccess / count).toFixed(4) : 1.0;

    return {
      aggregatedAt: new Date().toISOString(),
      metrics: {
        totalEvents: count,
        uniqueMachines: machineSet.size,
        totalTokensSavedBucketized: totalTokensSaved,
        averageLatencyMsBucketized: avgLatency,
        successRate
      },
      privacyGuarantees: {
        piiRemoved: true,
        identifiersHashed: true,
        bucketized: true,
        rawTextPreserved: false
      }
    };
  }

  assertZeroPii(cleanEvent) {
    const prohibitedKeys = [
      'prompt', 'promptContent', 'code', 'fileContent', 'filePath',
      'workspacePath', 'userName', 'email', 'apiKey', 'secret', 'gitBranch'
    ];
    for (const key of prohibitedKeys) {
      if (key in cleanEvent) {
        throw new Error('PII violation: prohibited key ' + key + ' found in telemetry event');
      }
    }
    return true;
  }
}

module.exports = { TelemetryPrivacyGuard };
