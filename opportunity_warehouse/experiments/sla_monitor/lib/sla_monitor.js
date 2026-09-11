class SlaMonitor {
  constructor(options = {}) {
    this.maxAcceptableLatencyMs = options.maxAcceptableLatencyMs || 250;
    this.history = [];
  }

  recordPing(responseTimeMs, statusCode = 200, error = null) {
    const isSuccess = statusCode >= 200 && statusCode < 400 && !error;
    const isWithinSla = isSuccess && responseTimeMs <= this.maxAcceptableLatencyMs;

    const record = {
      timestamp: new Date().toISOString(),
      responseTimeMs,
      statusCode,
      isSuccess,
      isWithinSla,
      error: error ? error.toString() : null
    };

    this.history.push(record);
    return record;
  }

  getMetrics() {
    const total = this.history.length;
    if (total === 0) {
      return { totalPings: 0, uptimePct: 100, slaCompliancePct: 100, avgLatencyMs: 0 };
    }

    let successCount = 0;
    let slaCount = 0;
    let totalLatency = 0;

    for (const r of this.history) {
      if (r.isSuccess) successCount++;
      if (r.isWithinSla) slaCount++;
      totalLatency += r.responseTimeMs;
    }

    return {
      totalPings: total,
      successfulPings: successCount,
      slaCompliantPings: slaCount,
      uptimePct: Number(((successCount / total) * 100).toFixed(2)),
      slaCompliancePct: Number(((slaCount / total) * 100).toFixed(2)),
      avgLatencyMs: Number((totalLatency / total).toFixed(2))
    };
  }
}

module.exports = { SlaMonitor };
