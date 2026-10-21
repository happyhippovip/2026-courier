// Kolibri Evidence Badge (Lane L5 - Kolibri Visual Verification)
// Evaluates strict evidence tuples against the Fail-Closed Evidence Contract.
// Implements BYTE_LEVEL_GOLD_VERIFIED resolution.
// Fail closed (V151): VERIFIED needs the full tuple, a 64-hex artifact hash, the contract
// resolution "BYTE_LEVEL_GOLD_VERIFIED" and a journal proof the hub derived from the journaled
// RESULT_ACCEPTED event that binds journal_entry_id and accepted_result_id. This module cannot
// authenticate data by itself; it only refuses green whenever that binding is absent or broken.

export const EVIDENCE_STATES = Object.freeze({
  VERIFIED: "VERIFIED",       // Byte-level gold verified with full 6-tuple
  REPORTED: "REPORTED",       // Unconfirmed claim
  BLOCKED: "BLOCKED",         // Active block
  UNKNOWN: "UNKNOWN",         // Missing or contradictory data
});

// Kolibri neon tokens (kolibri.css); the fallbacks are the same values.
export const EVIDENCE_BADGE_COLORS = Object.freeze({
  [EVIDENCE_STATES.VERIFIED]: "var(--neon-green, #10b981)",
  [EVIDENCE_STATES.REPORTED]: "var(--neon-blue, #3b82f6)",
  [EVIDENCE_STATES.BLOCKED]: "var(--neon-red, #ef4444)",
  [EVIDENCE_STATES.UNKNOWN]: "var(--neon-gray, #6b7280)",
});

// The only resolution that may turn the badge green (handoff evidence_contract.verified_resolution).
// Generic controller values such as "verified" are not translated here.
export const VERIFIED_RESOLUTION = "BYTE_LEVEL_GOLD_VERIFIED";

function textOf(value) {
  if (value && typeof value === "object") value = value.value ?? value.reason;
  return typeof value === "string" || typeof value === "number" ? String(value).trim() : "";
}

function sameId(a, b) {
  return a !== undefined && a !== null && b !== undefined && b !== null && String(a) === String(b);
}

// A blocker counts only while it is current and belongs to the displayed task.
// Returns { reason } for a valid block, { foreign: true } for a blocker bound elsewhere, or null.
function activeBlocker(item) {
  const b = item.blocker;
  if (b && typeof b === "object") {
    if (b.active === false || b.resolved || b.resolved_at || b.cleared_at) return null;
    if (b.task_id !== undefined && !sameId(b.task_id, item.task_id ?? item.evidence?.task_id)) {
      return { foreign: true };
    }
  }
  const reason = textOf(b).toUpperCase();
  return reason ? { reason } : null;
}

// Journal proof as produced by the hub from the RESULT_ACCEPTED event:
// { event: "RESULT_ACCEPTED", seq: <int > 0>, result_id: <accepted_result_id> }.
function proofBinds(proof, details) {
  if (!proof || typeof proof !== "object" || proof.event !== "RESULT_ACCEPTED") return false;
  if (!Number.isInteger(proof.seq) || proof.seq <= 0) return false;
  if (!sameId(proof.result_id, details.accepted_result_id)) return false;
  return String(details.journal_entry_id) === `journal:${proof.seq}:RESULT_ACCEPTED`;
}

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

  // Active blocker check: BLOCKED only with a current, task-bound, documented reason.
  const blocker = activeBlocker(item);
  const rawState = (textOf(item.state) || textOf(item.status)).toUpperCase();
  if (blocker?.foreign) {
    return {
      state: EVIDENCE_STATES.UNKNOWN,
      resolution: "BLOCKER_NOT_BOUND",
      valid: false,
      details: {},
    };
  }
  if (blocker) {
    return {
      state: EVIDENCE_STATES.BLOCKED,
      resolution: "ACTIVE_BLOCK",
      valid: false,
      details: { blocker: blocker.reason },
    };
  }
  if (rawState === "BLOCKED") {
    return {
      state: EVIDENCE_STATES.UNKNOWN,
      resolution: "BLOCKED_WITHOUT_REASON",
      valid: false,
      details: {},
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
  const conflicts = [];
  const details = {};
  for (const field of REQUIRED_TUPLE) {
    const val = evidence[field] ?? item[field];
    if (val === undefined || val === null || String(val).trim() === "") {
      missing.push(field);
    } else {
      details[field] = val;
    }
    const outer = item[field];
    const inner = evidence[field];
    if (evidence !== item && outer !== undefined && outer !== null && inner !== undefined
        && inner !== null && String(outer) !== String(inner)) {
      conflicts.push(field);
    }
  }

  // Contradictions are refused; agreement alone proves nothing (see proofBinds).
  if (conflicts.length > 0) {
    return {
      state: EVIDENCE_STATES.UNKNOWN,
      resolution: "CONTRADICTORY_BINDING",
      valid: false,
      details: { conflicts },
    };
  }

  const resolution = textOf(evidence.resolution ?? item.resolution);
  if (resolution.toUpperCase() === "REJECTED") {
    return {
      state: EVIDENCE_STATES.UNKNOWN,
      resolution: "RESOLUTION_REJECTED",
      valid: false,
      details: { missing },
    };
  }

  // Boolean alone insufficient; a complete tuple alone is insufficient too.
  if (missing.length === 0 && resolution !== VERIFIED_RESOLUTION) {
    return {
      state: EVIDENCE_STATES.UNKNOWN,
      resolution: resolution ? "RESOLUTION_NOT_VERIFIED" : "RESOLUTION_MISSING",
      valid: false,
      details: { resolution: resolution || null },
    };
  }

  if (missing.length === 0 && !proofBinds(evidence.proof ?? item.proof, details)) {
    return {
      state: EVIDENCE_STATES.UNKNOWN,
      resolution: "JOURNAL_PROOF_MISSING",
      valid: false,
      details: {},
    };
  }

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
