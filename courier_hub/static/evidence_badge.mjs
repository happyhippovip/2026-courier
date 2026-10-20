// Kolibri Evidence Badge (Lane L5 - Kolibri Visual Verification)
// Evaluates strict evidence tuples against the Fail-Closed Evidence Contract.
// Implements BYTE_LEVEL_GOLD_VERIFIED resolution.

export const EVIDENCE_STATES = Object.freeze({
  VERIFIED: "VERIFIED",       // Byte-level gold verified with full 6-tuple
  REPORTED: "REPORTED",       // Unconfirmed claim
  BLOCKED: "BLOCKED",         // Active block
  UNKNOWN: "UNKNOWN",         // Missing or contradictory data
});

export const EVIDENCE_BADGE_COLORS = Object.freeze({
  [EVIDENCE_STATES.VERIFIED]: "#10b981", // Green
  [EVIDENCE_STATES.REPORTED]: "#3b82f6", // Blue
  [EVIDENCE_STATES.BLOCKED]: "#ef4444",  // Red
  [EVIDENCE_STATES.UNKNOWN]: "#6b7280",  // Gray
});

export const REQUIRED_TUPLE = Object.freeze([
  "journal_entry_id",
  "task_id",
  "attempt",
  "dispatch_id",
  "accepted_result_id",
  "artifact_sha256",
]);

/**
 * Escapes HTML characters to prevent XSS.
 * @param {string} str
 * @returns {string}
 */
export function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Evaluates evidence for an item according to the evidence contract.
 * @param {Object} item
 * @returns {{ state: string, resolution: string, valid: boolean, details: Object }}
 */
export function evaluateEvidence(item) {
  if (!item || typeof item !== "object") {
    return {
      state: EVIDENCE_STATES.UNKNOWN,
      resolution: "MISSING_RECORD",
      valid: false,
      details: {},
    };
  }

  // Active blocker check
  const blocker = String(item.blocker?.value || item.blocker || "").trim().toUpperCase();
  const rawState = String(item.state?.value || item.status || item.state || "").trim().toUpperCase();
  if (blocker || rawState === "BLOCKED") {
    return {
      state: EVIDENCE_STATES.BLOCKED,
      resolution: "ACTIVE_BLOCK",
      valid: false,
      details: { blocker: blocker || "BLOCKED" },
    };
  }

  // Extract evidence record or properties from item
  const evidence = item.evidence || item;

  // Synthetic IDs rejected
  const idCandidates = [
    item.event_id,
    evidence.journal_entry_id,
    item.id,
    item.task_id,
  ].filter(Boolean).map(String);

  for (const cid of idCandidates) {
    if (cid === "evt:unknown:0" || cid.startsWith("evt:gen:") || cid.startsWith("evt:synth:")) {
      return {
        state: EVIDENCE_STATES.UNKNOWN,
        resolution: "SYNTHETIC_ID_REJECTED",
        valid: false,
        details: { rejected_id: cid },
      };
    }
  }

  // Check required tuple
  const missing = [];
  const details = {};
  for (const field of REQUIRED_TUPLE) {
    const val = evidence[field] ?? item[field];
    if (val === undefined || val === null || String(val).trim() === "") {
      missing.push(field);
    } else {
      details[field] = val;
    }
  }

  // Boolean alone insufficient
  if (missing.length === 0) {
    const sha = String(details.artifact_sha256 || "");
    if (/^[a-fA-F0-9]{64}$/.test(sha)) {
      return {
        state: EVIDENCE_STATES.VERIFIED,
        resolution: "BYTE_LEVEL_GOLD_VERIFIED",
        valid: true,
        details,
      };
    }
  }

  // If claimed/started/reported but missing some tuple elements
  if (rawState === "CLAIMED" || rawState === "STARTED" || rawState === "REPORTED" || rawState === "RUNNING") {
    return {
      state: EVIDENCE_STATES.REPORTED,
      resolution: "UNCONFIRMED_CLAIM",
      valid: false,
      details: { missing, reported_state: rawState },
    };
  }

  return {
    state: EVIDENCE_STATES.UNKNOWN,
    resolution: "MISSING_OR_CONTRADICTORY",
    valid: false,
    details: { missing },
  };
}

/**
 * Renders an accessible HTML evidence badge.
 * @param {Object} item
 * @returns {string} HTML snippet
 */
export function renderEvidenceBadge(item) {
  const result = evaluateEvidence(item);
  const color = EVIDENCE_BADGE_COLORS[result.state] || EVIDENCE_BADGE_COLORS[EVIDENCE_STATES.UNKNOWN];
  const label = result.state;
  const resolution = result.resolution;

  return `<span class="evidence-badge" data-state="${escapeHtml(result.state)}" data-resolution="${escapeHtml(resolution)}" style="background-color:${color};color:#ffffff;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:600;display:inline-block;" title="Resolution: ${escapeHtml(resolution)}" aria-label="Evidence status: ${escapeHtml(label)} (${escapeHtml(resolution)})">${escapeHtml(label)}</span>`;
}
