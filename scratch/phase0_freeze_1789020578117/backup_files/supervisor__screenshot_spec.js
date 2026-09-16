// Screenshot Fallback Interface & Privacy Guard Spec
// Rules:
// 1. Screenshot is SECONDARY evidence only.
// 2. Trigger ONLY when logs/state/process evidence is insufficient AND diagnostic threshold is reached.
// 3. Prefer window/app target, NOT full desktop.
// 4. Invariant: Never capture sensitive data. If sensitive UI suspected: SCREENSHOT_BLOCKED_PRIVACY.

const crypto = require('crypto');

const SENSITIVE_UI_KEYWORDS = [
  'password',
  'passwd',
  'token',
  'secret',
  '2fa',
  'otp',
  'authenticator',
  'credit card',
  'cvv',
  'billing',
  'private key',
  'seed phrase',
  'recovery phrase',
  'login prompt',
  'credential'
];

class ScreenshotSpec {
  static evaluateCaptureEligibility({
    diagnosticThresholdReached = false,
    logsSufficient = true,
    processEvidenceSufficient = true,
    permissionGranted = true,
    windowTitle = '',
    appTarget = ''
  }) {
    // Check 1: Secondary evidence only — if logs/process evidence are sufficient, do NOT capture
    if (logsSufficient && processEvidenceSufficient) {
      return {
        eligible: false,
        reason: 'LOGS_OR_EVIDENCE_SUFFICIENT: Screenshot capture not warranted when text evidence is available'
      };
    }

    // Check 2: Must have reached diagnostic threshold
    if (!diagnosticThresholdReached) {
      return {
        eligible: false,
        reason: 'THRESHOLD_NOT_MET: Screenshot capture permitted only after diagnostic threshold is reached'
      };
    }

    // Check 3: Permission
    if (!permissionGranted) {
      return {
        eligible: false,
        reason: 'PERMISSION_DENIED: Screenshot capture disallowed by environment policy'
      };
    }

    // Check 4: Privacy Guard
    const targetString = `${windowTitle} ${appTarget}`.toLowerCase();
    for (const kw of SENSITIVE_UI_KEYWORDS) {
      if (targetString.includes(kw)) {
        return {
          eligible: false,
          blocked_by_privacy: true,
          status: 'SCREENSHOT_BLOCKED_PRIVACY',
          reason: `SCREENSHOT_BLOCKED_PRIVACY: Sensitive keyword '${kw}' detected in target window/app title`
        };
      }
    }

    return {
      eligible: true,
      blocked_by_privacy: false,
      reason: 'ELIGIBLE_FOR_TARGETED_CAPTURE',
      target: appTarget || windowTitle || 'TARGET_PROCESS_WINDOW'
    };
  }

  static createScreenshotMetadata({
    task_id,
    process_lease_id,
    machine_id = 'WINDOWS_LOCAL',
    window_or_app_target,
    reason = 'DIAGNOSTIC_SECONDARY_EVIDENCE',
    path_or_reference = null,
    is_blocked_by_privacy = false
  }) {
    const timestamp = new Date().toISOString();
    const status = is_blocked_by_privacy ? 'SCREENSHOT_BLOCKED_PRIVACY' : (path_or_reference ? 'CAPTURED' : 'SPEC_REFERENCE');

    const canonical = {
      task_id,
      process_lease_id,
      machine_id,
      window_or_app_target,
      timestamp,
      status
    };
    const fingerprint = crypto.createHash('sha256').update(JSON.stringify(canonical)).digest('hex');

    return {
      captured_at: timestamp,
      reason,
      task_id,
      process_lease_id,
      machine_id,
      window_or_app_target: window_or_app_target || 'APPLICATION_WINDOW_ONLY',
      privacy_filter_applied: true,
      status,
      path_or_reference: is_blocked_by_privacy ? 'NONE_PRIVACY_BLOCKED' : (path_or_reference || 'VIRTUAL_REFERENCE'),
      fingerprint
    };
  }
}

module.exports = {
  SENSITIVE_UI_KEYWORDS,
  ScreenshotSpec
};
