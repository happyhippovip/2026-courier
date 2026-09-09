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
    purpose,
    evidence,
    expected_upside_eur,
    maximum_loss_eur,
    cheapest_alternative,
    human_approval_required
  }) {
    if (price_eur === undefined || typeof price_eur !== 'number' || price_eur <= 0) {
      throw new Error('[SPEND_SAFETY_ERROR] price_eur must be a positive number.');
    }
    if (!purpose || typeof purpose !== 'string' || purpose.trim().length < 5) {
      throw new Error('[SPEND_SAFETY_ERROR] purpose must be a substantive description.');
    }
    if (!evidence || evidence === 'UNKNOWN') {
      throw new Error('[SPEND_SAFETY_ERROR] evidence must be provided (cannot be UNKNOWN or empty).');
    }
    if (human_approval_required !== true) {
      throw new Error('[SPEND_SAFETY_VIOLATION] human_approval_required must be strictly true.');
    }

    const id = `SPEND-REQ-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-${crypto.randomBytes(3).toString('hex').toUpperCase()}`;

    return {
      spend_request_id: id,
      price: price_eur,
      price_eur: price_eur,
      purpose,
      evidence,
      expected_upside: expected_upside_eur || 'UNKNOWN',
      expected_upside_eur: expected_upside_eur || 'UNKNOWN',
      maximum_loss: maximum_loss_eur !== undefined ? maximum_loss_eur : price_eur,
      maximum_loss_eur: maximum_loss_eur !== undefined ? maximum_loss_eur : price_eur,
      cheapest_alternative: cheapest_alternative || 'Zero-cost local simulation / open-source alternative',
      human_approval_required: true,
      autonomous_execution_allowed: false,
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
