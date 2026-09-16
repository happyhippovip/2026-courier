'use strict';

const crypto = require('crypto');

/**
 * ApprovalTokenCore
 * Cryptographic human-gate authorization system.
 * Generates and verifies single-use scoped approval tokens.
 */
class ApprovalTokenCore {
  constructor(secretKey = 'dev_human_gate_secret_key') {
    this.secretKey = secretKey;
    this.consumedNonces = new Set();
  }

  _canonicalString(fields) {
    return [
      fields.token_id,
      fields.action_type,
      JSON.stringify(fields.scope_binding || {}),
      Number(fields.max_liability_eur || 0).toFixed(2),
      fields.nonce,
      fields.issued_at_ms,
      fields.expires_at_ms
    ].join('|');
  }

  issueToken({ token_id, action_type, scope_binding = {}, max_liability_eur = 0.00, ttl_ms = 300000 }) {
    const now = Date.now();
    const token = {
      token_id: token_id || `tok_${crypto.randomUUID()}`,
      action_type,
      scope_binding,
      max_liability_eur: Number(max_liability_eur),
      nonce: crypto.randomBytes(16).toString('hex'),
      issued_at_ms: now,
      expires_at_ms: now + ttl_ms
    };

    const canonical = this._canonicalString(token);
    token.signature = crypto.createHmac('sha256', this.secretKey).update(canonical).digest('hex');
    return token;
  }

  verifyAndConsumeToken(token, requestedAction, context = {}) {
    if (!token || typeof token !== 'object') {
      return { approved: false, reason: 'TOKEN_MISSING_OR_MALFORMED' };
    }

    const {
      token_id,
      action_type,
      scope_binding,
      max_liability_eur,
      nonce,
      issued_at_ms,
      expires_at_ms,
      signature
    } = token;

    if (!token_id || !action_type || !nonce || !signature) {
      return { approved: false, reason: 'TOKEN_MISSING_REQUIRED_FIELDS' };
    }

    // 1. Verify signature
    const canonical = this._canonicalString(token);
    const expectedSig = crypto.createHmac('sha256', this.secretKey).update(canonical).digest('hex');
    if (!crypto.timingSafeEqual(Buffer.from(signature, 'hex'), Buffer.from(expectedSig, 'hex'))) {
      return { approved: false, reason: 'INVALID_SIGNATURE' };
    }

    // 2. Check expiration
    const now = context.current_time_ms || Date.now();
    if (now > expires_at_ms) {
      return { approved: false, reason: 'TOKEN_EXPIRED', detail: `Expired at ${expires_at_ms}, now ${now}` };
    }

    // 3. Check action match
    if (action_type !== requestedAction) {
      return {
        approved: false,
        reason: 'ACTION_TYPE_MISMATCH',
        detail: `Token issued for '${action_type}', but requested action is '${requestedAction}'`
      };
    }

    // 4. Check scope binding
    if (scope_binding && context.target_scope) {
      for (const [key, expectedVal] of Object.entries(scope_binding)) {
        if (context.target_scope[key] !== expectedVal) {
          return {
            approved: false,
            reason: 'SCOPE_BINDING_MISMATCH',
            detail: `Scope field '${key}' mismatch: expected '${expectedVal}', got '${context.target_scope[key]}'`
          };
        }
      }
    }

    // 5. Check liability limit
    const costEur = Number(context.cost_eur || 0.00);
    if (costEur > Number(max_liability_eur)) {
      return {
        approved: false,
        reason: 'LIABILITY_LIMIT_EXCEEDED',
        detail: `Cost €${costEur.toFixed(2)} exceeds approved limit €${Number(max_liability_eur).toFixed(2)}`
      };
    }

    // 6. Check single-use nonce (atomic consumption)
    if (this.consumedNonces.has(nonce)) {
      return {
        approved: false,
        reason: 'TOKEN_ALREADY_CONSUMED',
        detail: `Nonce ${nonce} has already been consumed`
      };
    }

    // Consume nonce
    this.consumedNonces.add(nonce);

    return {
      approved: true,
      reason: 'TOKEN_VERIFIED_AND_CONSUMED',
      token_id,
      nonce
    };
  }
}

module.exports = { ApprovalTokenCore };
