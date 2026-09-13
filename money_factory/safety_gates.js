// Safety Gates & Spend Interceptor
// Hard-coded economic safety policy:
// REAL_TRADES = 0
// REAL_FUNDS_TOUCHED = NO
// REAL_POSITIONS_CHANGED = 0
// REAL_WALLETS_CONNECTED = NO
// WALLET_SIGNING = NO
// AUTONOMOUS_SPEND_LIMIT_EUR = 0

const crypto = require('crypto');

const SAFETY_INVARIANTS = Object.freeze({
  REAL_TRADES: 0,
  REAL_FUNDS_TOUCHED: 'NO',
  REAL_POSITIONS_CHANGED: 0,
  REAL_WALLETS_CONNECTED: 'NO',
  WALLET_SIGNING: 'NO',
  AUTONOMOUS_SPEND_LIMIT_EUR: 0
});

const HUMAN_GATE_OPERATIONS = Object.freeze([
  'payment',
  'subscription',
  'purchase',
  'upgrade',
  'overage',
  'publication',
  'production_deployment',
  'customer_outreach',
  'external_message',
  'real_trade',
  'wallet_signing',
  'account_creation',
  'login_2fa_kyc',
  'real_spend'
]);

class SafetyGateManager {
  static getInvariants() {
    return { ...SAFETY_INVARIANTS };
  }

  static checkOperation(operationName, details = {}) {
    const op = operationName.toLowerCase().replace(/[\s-]/g, '_');
    if (HUMAN_GATE_OPERATIONS.includes(op)) {
      return {
        allowed: false,
        requires_human_gate: true,
        gate_type: op.toUpperCase(),
        reason: `Operation '${operationName}' strictly requires explicit human physical approval.`,
        details
      };
    }
    return {
      allowed: true,
      requires_human_gate: false,
      gate_type: 'NONE'
    };
  }

  static createSpendRequest({
    price_eur,
    price,
    amount_eur,
    purpose,
    recipient = 'UNKNOWN',
    opportunity_id,
    experiment_id = 'UNKNOWN',
    evidence,
    expected_upside_eur,
    maximum_loss_eur,
    cheapest_alternative,
    why_free_option_is_insufficient,
    human_approval_required
  }) {
    const effectivePrice = price_eur !== undefined ? price_eur : (amount_eur !== undefined ? amount_eur : price);
    if (effectivePrice === undefined || typeof effectivePrice !== 'number' || effectivePrice <= 0) {
      throw new Error('[SPEND_SAFETY_ERROR] price_eur must be a positive number.');
    }
    if (!purpose || typeof purpose !== 'string' || purpose.trim().length < 5) {
      throw new Error('[SPEND_SAFETY_ERROR] purpose must be a substantive description.');
    }

    // Check for strict closure requirements when invoked with new signature or explicit opportunity/why fields
    const isClosureCall = (amount_eur !== undefined || opportunity_id !== undefined || why_free_option_is_insufficient !== undefined);

    if (isClosureCall) {
      if (!opportunity_id) {
        throw new Error('[SPEND_SAFETY_ERROR] opportunity_id is required for SPEND_REQUEST.');
      }
      if (!why_free_option_is_insufficient) {
        throw new Error('[SPEND_SAFETY_ERROR] why_free_option_is_insufficient is required for SPEND_REQUEST.');
      }
    }

    const effectiveEvidence = evidence || 'Proposal evidence attached';
    const effectiveWhyFree = why_free_option_is_insufficient || 'Free alternatives cannot bypass third-party external listing/transaction fee requirements';
    const effectiveOppId = opportunity_id || 'UNKNOWN';

    if (human_approval_required !== undefined && human_approval_required !== true) {
      throw new Error('[SPEND_SAFETY_VIOLATION] human_approval_required must be strictly true.');
    }

    const id = `SPEND-REQ-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-${crypto.randomBytes(3).toString('hex').toUpperCase()}`;

    return {
      spend_request_id: id,
      price: effectivePrice,
      price_eur: effectivePrice,
      amount_eur: effectivePrice,
      purpose,
      recipient,
      opportunity_id: effectiveOppId,
      experiment_id,
      evidence: effectiveEvidence,
      expected_upside: expected_upside_eur || 'UNKNOWN',
      expected_upside_eur: expected_upside_eur || 'UNKNOWN',
      maximum_loss: maximum_loss_eur !== undefined ? maximum_loss_eur : effectivePrice,
      maximum_loss_eur: maximum_loss_eur !== undefined ? maximum_loss_eur : effectivePrice,
      cheapest_alternative: cheapest_alternative || 'Zero-cost local simulation / open-source alternative',
      why_free_option_is_insufficient: effectiveWhyFree,
      human_approval_required: true,
      autonomous_execution_allowed: false,
      approved: false,
      status: 'PENDING_HUMAN_APPROVAL',
      created_at: new Date().toISOString(),
      safety_invariants: { ...SAFETY_INVARIANTS }
    };
  }

  static executeSpend(spendRequest) {
    throw new Error(
      `[CRITICAL_SAFETY_VIOLATION] Autonomous spend execution strictly forbidden! ` +
      `AUTONOMOUS_SPEND_LIMIT_EUR = 0. Request '${spendRequest.spend_request_id || 'UNKNOWN'}' ` +
      `requires manual human authorization outside the autonomous engine.`
    );
  }

  static executeTrade(tradeParams) {
    throw new Error(
      `[CRITICAL_SAFETY_VIOLATION] Autonomous real trading strictly forbidden! ` +
      `REAL_TRADES = 0, REAL_POSITIONS_CHANGED = 0, REAL_WALLETS_CONNECTED = NO.`
    );
  }

  static signWithWallet(walletParams) {
    throw new Error(
      `[CRITICAL_SAFETY_VIOLATION] Autonomous wallet signing strictly forbidden! ` +
      `WALLET_SIGNING = NO, REAL_WALLETS_CONNECTED = NO.`
    );
  }
}

module.exports = {
  SAFETY_INVARIANTS,
  HUMAN_GATE_OPERATIONS,
  SafetyGateManager
};
