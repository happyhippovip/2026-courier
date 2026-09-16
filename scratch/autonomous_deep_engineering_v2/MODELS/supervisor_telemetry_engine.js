/**
 * SUPERVISOR TELEMETRY & PROGRESS EVIDENCE ENGINE (V2 LAB)
 * 
 * Enforces:
 * 1. Progress Evidence Science: Heartbeat != Progress, CPU != Progress, Time != Hang.
 * 2. 5-min Check Progress, 15-min Capture Diagnostics, Time alone never kills.
 * 3. Diagnostic Bundle Integrity & Non-Authority to terminate progressing work.
 * 4. Screenshot Privacy Protection & Credential Redaction.
 * 5. Multi-Machine Independent Resource Governor (Mac heat does not throttle Windows).
 */

const crypto = require('crypto');

class SupervisorTelemetryEngine {
  constructor() {
    this.machineStates = {
      WINDOWS_HOST: 'NORMAL',
      MAC_HOST: 'NORMAL'
    };
  }

  setMachineResourceState(machine, state) {
    this.machineStates[machine] = state;
  }

  isMachineThrottled(machine) {
    const s = this.machineStates[machine];
    return s === 'PRESSURE' || s === 'THERMAL_PRESSURE';
  }

  /**
   * Progress Evidence Science: Evaluates health and progress state.
   */
  static classifyProgress({
    elapsed_ms,
    cpu_percent = 0,
    has_heartbeat = false,
    log_bytes_grown = 0,
    artifacts_created = 0,
    state_transitions = 0,
    is_expected_wait = false
  }) {
    // 1. Evidence of actual forward progress
    if (log_bytes_grown > 0 || artifacts_created > 0 || state_transitions > 0) {
      return {
        classification: 'GENUINE_PROGRESS',
        action: 'MAINTAIN_EXECUTION',
        reason: 'Observable durable progress evidence detected (log growth, artifact creation, or state change).'
      };
    }

    // 2. Expected external wait (e.g. bounded sleep or remote polling)
    if (is_expected_wait) {
      return {
        classification: 'VALID_WAITING',
        action: 'MAINTAIN_EXECUTION',
        reason: 'Worker is in an explicitly declared expected wait condition.'
      };
    }

    // 3. Busy loop: High CPU but zero evidence produced
    if (cpu_percent > 85 && log_bytes_grown === 0 && artifacts_created === 0) {
      if (elapsed_ms > 300000) { // > 5 minutes of high CPU without output
        return {
          classification: 'BUSY_LOOP',
          action: 'CAPTURE_DIAGNOSTIC_BUNDLE',
          reason: 'High CPU utilization with zero durable output growth over threshold.'
        };
      }
    }

    // 4. Silent / Stall policies based on elapsed time without evidence
    if (elapsed_ms >= 900000) { // >= 15 minutes
      return {
        classification: 'STALLED_NO_EVIDENCE',
        action: 'CAPTURE_DIAGNOSTIC_BUNDLE',
        reason: '15+ minutes elapsed with zero progress evidence. Capture diagnostic bundle (do not terminate without inspection).'
      };
    }

    if (elapsed_ms >= 300000) { // >= 5 minutes
      return {
        classification: 'POTENTIALLY_STALLED',
        action: 'CHECK_PROGRESS',
        reason: '5+ minutes elapsed without evidence. Trigger progress check probe.'
      };
    }

    // Normal active waiting under 5 minutes
    return {
      classification: 'ACTIVE_WAITING',
      action: 'MAINTAIN_EXECUTION',
      reason: 'Under 5-minute threshold; normal execution window.'
    };
  }

  /**
   * Validates Diagnostic Bundle completeness and integrity.
   */
  static validateDiagnosticBundle(bundle) {
    const required = ['task_state', 'process_state', 'recent_logs', 'git_status', 'resource_usage'];
    const missing = required.filter(f => !bundle[f]);

    if (missing.length > 0) {
      return { valid: false, reason: `Missing required diagnostic sections: ${missing.join(', ')}` };
    }

    if (bundle.task_state.task_id !== bundle.process_state.task_id) {
      return { valid: false, reason: 'Task ID mismatch between task_state and process_state' };
    }

    return { valid: true, reason: 'Diagnostic bundle complete and self-consistent' };
  }

  /**
   * Screenshot Privacy Redaction Engine.
   */
  static evaluateScreenshotPrivacy(metadata) {
    const sensitivePatterns = [
      /(?:^|[^a-zA-Z0-9])passwords?(?:$|[^a-zA-Z0-9])/i,
      /(?:^|[^a-zA-Z0-9])api[_-]?keys?(?:$|[^a-zA-Z0-9])/i,
      /(?:^|[^a-zA-Z0-9])secrets?(?:$|[^a-zA-Z0-9])/i,
      /(?:^|[^a-zA-Z0-9])tokens?(?:$|[^a-zA-Z0-9])/i,
      /(?:^|[^a-zA-Z0-9])seed[_-]?phrases?(?:$|[^a-zA-Z0-9])/i,
      /(?:^|[^a-zA-Z0-9])credit[_-]?cards?(?:$|[^a-zA-Z0-9])/i,
      /(?:^|[^a-zA-Z0-9])cvv(?:$|[^a-zA-Z0-9])/i,
      /(?:^|[^a-zA-Z0-9])private[_-]?keys?(?:$|[^a-zA-Z0-9])/i,
      /SECRET_ACCESS_KEY/i,
      /API_KEY/i,
      /BEARER\s+[A-Za-z0-9_\-\.]+/i
    ];

    const content = `${metadata.window_title || ''} ${metadata.detected_text || ''} ${metadata.app_name || ''}`;
    for (const pat of sensitivePatterns) {
      if (pat.test(content)) {
        return {
          allowed: false,
          action: 'SCREENSHOT_CAPTURE_BLOCKED_OR_REDACT_REQUIRED',
          pattern: pat.toString(),
          reason: `Privacy-sensitive credential or secret detected: ${pat}`
        };
      }
    }

    return {
      allowed: true,
      action: 'ALLOW_SCREENSHOT_SECONDARY_EVIDENCE',
      reason: 'No sensitive credentials detected in capture metadata'
    };
  }
}

module.exports = { SupervisorTelemetryEngine };
