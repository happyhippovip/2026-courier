/**
 * Context Token Amortization & Multi-Turn Cost Depreciation Engine
 * Quantifies economic value of cached vs dynamic context across multi-turn agent sessions.
 */

class TokenAmortizationEngine {
  constructor(pricingModel = {}) {
    // Pricing in EUR / USD per 1,000,000 tokens
    this.pricing = {
      baseInputPerMillion: pricingModel.baseInputPerMillion || 3.00,       // e.g. Claude 3.5 Sonnet base
      cachedInputPerMillion: pricingModel.cachedInputPerMillion || 0.30,   // e.g. 90% discount on cache read
      cacheWritePerMillion: pricingModel.cacheWritePerMillion || 3.75,     // e.g. 25% premium on cache write
      outputPerMillion: pricingModel.outputPerMillion || 15.00,
      currency: pricingModel.currency || 'EUR'
    };
  }

  calculateTurnCost(tokens = {}) {
    const cachedTokens = tokens.cachedTokens || 0;
    const freshInputTokens = tokens.freshInputTokens || 0;
    const outputTokens = tokens.outputTokens || 0;
    const isFirstTurnWrite = tokens.isFirstTurnWrite || false;

    // Unoptimized cost (all input charged at base rate)
    const totalInput = cachedTokens + freshInputTokens;
    const unoptimizedCost = (totalInput / 1000000) * this.pricing.baseInputPerMillion +
                            (outputTokens / 1000000) * this.pricing.outputPerMillion;

    // Optimized cost
    let cachedInputCost = 0;
    if (isFirstTurnWrite) {
      // First turn pays write premium for cached portion
      cachedInputCost = (cachedTokens / 1000000) * this.pricing.cacheWritePerMillion;
    } else {
      // Subsequent turns pay discounted read rate
      cachedInputCost = (cachedTokens / 1000000) * this.pricing.cachedInputPerMillion;
    }

    const freshCost = (freshInputTokens / 1000000) * this.pricing.baseInputPerMillion;
    const outputCost = (outputTokens / 1000000) * this.pricing.outputPerMillion;
    const optimizedCost = cachedInputCost + freshCost + outputCost;

    const savings = unoptimizedCost - optimizedCost;
    const savingsPercent = unoptimizedCost > 0 ? (savings / unoptimizedCost) * 100 : 0;

    return {
      unoptimizedCost: Number(unoptimizedCost.toFixed(6)),
      optimizedCost: Number(optimizedCost.toFixed(6)),
      savings: Number(savings.toFixed(6)),
      savingsPercent: Number(savingsPercent.toFixed(2))
    };
  }

  findBreakEvenTurn(cachedTokens) {
    if (cachedTokens <= 0) return 1;

    // Write cost premium: (writePrice - basePrice) * tokens
    // Read savings per turn: (basePrice - readPrice) * tokens
    const writePremiumPerMillion = this.pricing.cacheWritePerMillion - this.pricing.baseInputPerMillion;
    const readSavingsPerMillion = this.pricing.baseInputPerMillion - this.pricing.cachedInputPerMillion;

    if (readSavingsPerMillion <= 0) return Infinity; // Never breaks even

    // In turn 1, we incur write premium.
    // In turn 2 onwards, we save readSavings.
    // Break-even is turn 1 + ceil(writePremium / readSavings)
    const additionalTurnsNeeded = Math.ceil(writePremiumPerMillion / readSavingsPerMillion);
    return 1 + additionalTurnsNeeded;
  }

  generateAmortizationSchedule(options = {}) {
    const totalTurns = options.totalTurns || 10;
    const cachedTokens = options.cachedTokens || 50000;
    const freshInputPerTurn = options.freshInputPerTurn || 1500;
    const outputPerTurn = options.outputPerTurn || 800;

    const turns = [];
    let cumUnoptimized = 0;
    let cumOptimized = 0;

    for (let t = 1; t <= totalTurns; t++) {
      const isFirstTurn = (t === 1);
      const turnMetrics = this.calculateTurnCost({
        cachedTokens,
        freshInputTokens: freshInputPerTurn,
        outputTokens: outputPerTurn,
        isFirstTurnWrite: isFirstTurn
      });

      cumUnoptimized += turnMetrics.unoptimizedCost;
      cumOptimized += turnMetrics.optimizedCost;

      const cumSavings = cumUnoptimized - cumOptimized;
      const cumSavingsPercent = (cumSavings / cumUnoptimized) * 100;

      turns.push({
        turn: t,
        turnCostUnoptimized: turnMetrics.unoptimizedCost,
        turnCostOptimized: turnMetrics.optimizedCost,
        turnSavings: turnMetrics.savings,
        cumulativeUnoptimized: Number(cumUnoptimized.toFixed(4)),
        cumulativeOptimized: Number(cumOptimized.toFixed(4)),
        cumulativeSavings: Number(cumSavings.toFixed(4)),
        cumulativeSavingsPercent: Number(cumSavingsPercent.toFixed(2))
      });
    }

    const breakEvenTurn = this.findBreakEvenTurn(cachedTokens);

    return {
      currency: this.pricing.currency,
      cachedTokens,
      freshInputPerTurn,
      outputPerTurn,
      totalTurns,
      breakEvenTurn,
      totalUnoptimizedCost: Number(cumUnoptimized.toFixed(4)),
      totalOptimizedCost: Number(cumOptimized.toFixed(4)),
      totalNetSavings: Number((cumUnoptimized - cumOptimized).toFixed(4)),
      netSavingsPercent: Number((((cumUnoptimized - cumOptimized) / cumUnoptimized) * 100).toFixed(2)),
      schedule: turns
    };
  }
}

module.exports = { TokenAmortizationEngine };
