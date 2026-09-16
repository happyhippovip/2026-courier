// Diagnostic Bundle Manager — Isolated Forensic Snapshots
// Location: runtime/diagnostics/<diagnostic-id>/
// Invariant: Diagnostic bundles must be fingerprintable and append-only. Never overwrite prior diagnostics.

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

class DiagnosticBundleManager {
  constructor(baseDir = null) {
    this.baseDir = baseDir || path.join(__dirname, '..', 'runtime', 'diagnostics');
    if (!fs.existsSync(this.baseDir)) {
      fs.mkdirSync(this.baseDir, { recursive: true });
    }
  }

  createBundle({
    task_id,
    process_lease,
    task_state = {},
    recent_logs = '',
    git_status = '',
    git_diff_stat = '',
    resource_usage = {},
    progress_evidence = [],
    screenshot_metadata = null,
    reason = 'DIAGNOSTIC_THRESHOLD_REACHED'
  }) {
    if (!task_id) throw new Error('[DIAGNOSTIC_ERROR] task_id is required');

    const timestamp = new Date().toISOString();
    const diagnosticId = `DIAG-${Date.now()}-${crypto.randomBytes(3).toString('hex').toUpperCase()}`;
    const bundleDir = path.join(this.baseDir, diagnosticId);
    fs.mkdirSync(bundleDir, { recursive: true });

    // 1. Write core artifacts
    fs.writeFileSync(path.join(bundleDir, 'task_state.json'), JSON.stringify(task_state, null, 2), 'utf8');
    fs.writeFileSync(path.join(bundleDir, 'process_state.json'), JSON.stringify(process_lease || {}, null, 2), 'utf8');
    fs.writeFileSync(path.join(bundleDir, 'recent_logs.txt'), recent_logs || '(no logs captured)', 'utf8');
    fs.writeFileSync(path.join(bundleDir, 'git_status.txt'), git_status || '(git clean or untracked)', 'utf8');
    fs.writeFileSync(path.join(bundleDir, 'git_diff_stat.txt'), git_diff_stat || '(no diff)', 'utf8');
    fs.writeFileSync(path.join(bundleDir, 'resource_usage.json'), JSON.stringify(resource_usage, null, 2), 'utf8');
    fs.writeFileSync(path.join(bundleDir, 'progress_evidence.json'), JSON.stringify(progress_evidence, null, 2), 'utf8');

    if (screenshot_metadata) {
      fs.writeFileSync(path.join(bundleDir, 'screenshot_metadata.json'), JSON.stringify(screenshot_metadata, null, 2), 'utf8');
    }

    // 2. Compute canonical SHA-256 fingerprint across artifacts
    const canonicalHashPayload = {
      diagnostic_id: diagnosticId,
      task_id,
      timestamp,
      process_lease_id: process_lease?.process_lease_id || 'NONE',
      logs_sha: crypto.createHash('sha256').update(recent_logs).digest('hex'),
      git_sha: crypto.createHash('sha256').update(git_status).digest('hex')
    };
    const fingerprint = crypto.createHash('sha256').update(JSON.stringify(canonicalHashPayload)).digest('hex');

    // 3. Write diagnostic report
    const report = {
      diagnostic_id: diagnosticId,
      task_id,
      timestamp,
      reason,
      fingerprint,
      artifacts: [
        'task_state.json',
        'process_state.json',
        'recent_logs.txt',
        'git_status.txt',
        'git_diff_stat.txt',
        'resource_usage.json',
        'progress_evidence.json'
      ].concat(screenshot_metadata ? ['screenshot_metadata.json'] : []),
      summary: {
        process_status: process_lease?.status || 'UNKNOWN',
        logs_length: recent_logs.length,
        evidence_count: progress_evidence.length,
        resource_state: resource_usage.resource_state || 'NORMAL'
      }
    };

    fs.writeFileSync(path.join(bundleDir, 'diagnostic_report.json'), JSON.stringify(report, null, 2), 'utf8');

    return {
      diagnostic_id: diagnosticId,
      bundle_dir: bundleDir,
      fingerprint,
      report
    };
  }

  getBundle(diagnosticId) {
    const reportPath = path.join(this.baseDir, diagnosticId, 'diagnostic_report.json');
    if (!fs.existsSync(reportPath)) return null;
    return JSON.parse(fs.readFileSync(reportPath, 'utf8'));
  }
}

module.exports = {
  DiagnosticBundleManager
};
