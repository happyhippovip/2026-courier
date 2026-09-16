'use strict';

/**
 * ZeroSpendBoundaryGovernor
 * Enforces zero-spend invariants, detects immediate and deferred
 * liabilities, and governs capability boundaries.
 */
class ZeroSpendBoundaryGovernor {
  constructor(options = {}) {
    this.autonomousSpendLimitEur = options.autonomousSpendLimitEur !== undefined ? options.autonomousSpendLimitEur : 0.00;
    this.approvalTokenCore = options.approvalTokenCore || null;
  }

  classifyAction(actionType, actionPayload = {}) {
    // Read-only / research actions
    const researchActions = new Set([
      'CODE_SEARCH', 'FILE_READ', 'LINT_INSPECT', 'ANALYZE_AST',
      'RUN_READ_ONLY_TESTS', 'GENERATE_DIFF_PREVIEW', 'SYSTEM_INFO'
    ]);
    if (researchActions.has(actionType)) {
      return { category: 'RESEARCH', requiresHumanGate: false };
    }

    // Local file mutations within workspace
    const localMutationActions = new Set([
      'WRITE_LOCAL_FILE', 'RUN_COMPILATION', 'EXECUTE_UNIT_TESTS'
    ]);
    if (localMutationActions.has(actionType)) {
      return { category: 'LOCAL_MUTATION', requiresHumanGate: false };
    }

    // External mutations
    const externalMutationActions = new Set([
      'GIT_PUSH', 'DEPLOY_SERVICE', 'PUBLISH_PACKAGE', 'SEND_EXTERNAL_MESSAGE'
    ]);
    if (externalMutationActions.has(actionType)) {
      return { category: 'EXTERNAL_MUTATION', requiresHumanGate: true };
    }

    // Financial actions
    const financialActions = new Set([
      'PLACE_TRADE', 'SIGNUP_SERVICE', 'PROVISION_PAID_RESOURCE', 'SEND_PAYMENT'
    ]);
    if (financialActions.has(actionType) || (actionPayload && (actionPayload.spend_eur > 0 || actionPayload.cost_eur > 0))) {
      return { category: 'FINANCIAL', requiresHumanGate: true };
    }

    return { category: 'UNKNOWN', requiresHumanGate: true };
  }

  detectDeferredLiabilities(actionType, actionPayload = {}) {
    const risks = [];
    const payloadStr = JSON.stringify(actionPayload).toLowerCase();

    // 1. Free trial auto-conversion
    if (
      payloadStr.includes('trial') &&
      (payloadStr.includes('auto_renew') || payloadStr.includes('card_required') || payloadStr.includes('billing'))
    ) {
      risks.push({
        type: 'DEFERRED_TRIAL_AUTO_CONVERSION',
        severity: 'CRITICAL',
        detail: 'Action registers a trial with recurring auto-renewal or card attachment'
      });
    }

    // 2. Cloud hourly compute provisioning
    if (
      payloadStr.includes('instance_type') ||
      payloadStr.includes('provision_cluster') ||
      payloadStr.includes('hourly_rate')
    ) {
      risks.push({
        type: 'DEFERRED_CLOUD_HOURLY_COST',
        severity: 'HIGH',
        detail: 'Action provisions cloud infrastructure that accrues continuous hourly charges'
      });
    }

    // 3. Trade orders (limit, market, future obligations)
    if (
      actionType === 'PLACE_TRADE' ||
      payloadStr.includes('order_type') ||
      payloadStr.includes('buy_order') ||
      payloadStr.includes('margin_call')
    ) {
      risks.push({
        type: 'DEFERRED_TRADE_LIABILITY',
        severity: 'CRITICAL',
        detail: 'Action places a trade or commits capital to financial market contracts'
      });
    }

    return {
      hasDeferredLiabilities: risks.length > 0,
      risks
    };
  }

  evaluateExecution(request) {
    const {
      action_type,
      action_payload = {},
      approval_token = null,
      context = {}
    } = request;

    const classification = this.classifyAction(action_type, action_payload);
    const deferred = this.detectDeferredLiabilities(action_type, action_payload);
    const costEur = Number(action_payload.cost_eur || action_payload.spend_eur || 0.00);

    // Rule 1: Research actions run autonomously without gate
    if (classification.category === 'RESEARCH' && !deferred.hasDeferredLiabilities && costEur === 0) {
      return {
        authorized: true,
        category: 'RESEARCH',
        reason: 'AUTONOMOUS_RESEARCH_ALLOWED'
      };
    }

    // Rule 2: Immediate spend exceeding autonomous limit requires gate
    if (costEur > this.autonomousSpendLimitEur) {
      if (!approval_token) {
        return {
          authorized: false,
          category: classification.category,
          reason: 'HUMAN_GATE_REQUIRED_FOR_SPEND',
          detail: `Cost €${costEur.toFixed(2)} exceeds autonomous limit €${this.autonomousSpendLimitEur.toFixed(2)}`
        };
      }
    }

    // Rule 3: Deferred liabilities strictly require human gate
    if (deferred.hasDeferredLiabilities && !approval_token) {
      return {
        authorized: false,
        category: 'FINANCIAL_DEFERRED',
        reason: 'HUMAN_GATE_REQUIRED_FOR_DEFERRED_LIABILITY',
        risks: deferred.risks
      };
    }

    // Rule 4: External mutations require human gate
    if (classification.requiresHumanGate && !approval_token) {
      return {
        authorized: false,
        category: classification.category,
        reason: 'HUMAN_GATE_REQUIRED_FOR_MUTATION',
        detail: `Action '${action_type}' requires explicit human gate approval`
      };
    }

    // Rule 5: If an approval token is provided, verify it through ApprovalTokenCore
    if (approval_token) {
      if (!this.approvalTokenCore) {
        return {
          authorized: false,
          reason: 'APPROVAL_TOKEN_CORE_NOT_CONFIGURED'
        };
      }

      const tokenVerdict = this.approvalTokenCore.verifyAndConsumeToken(approval_token, action_type, {
        ...context,
        cost_eur: costEur
      });

      if (!tokenVerdict.approved) {
        return {
          authorized: false,
          reason: `TOKEN_REJECTED: ${tokenVerdict.reason}`,
          detail: tokenVerdict.detail
        };
      }

      return {
        authorized: true,
        category: classification.category,
        reason: 'AUTHORIZED_BY_HUMAN_GATE_TOKEN',
        token_id: tokenVerdict.token_id
      };
    }

    // Default: Local mutations within sandbox with 0 spend allowed
    return {
      authorized: true,
      category: classification.category,
      reason: 'AUTONOMOUS_LOCAL_MUTATION_ALLOWED'
    };
  }
}

module.exports = { ZeroSpendBoundaryGovernor };
