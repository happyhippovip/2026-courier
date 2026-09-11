/**
 * pricing_oracle.js - Multi-Provider LLM Token Cost Index & Pricing Oracle
 * Maintains current token rates and computes exact financial differentials for prompt optimizations.
 */
class TokenPricingOracle {
  constructor(customRates = {}) {
    this.models = {
      'claude-3-5-sonnet': { provider: 'Anthropic', inputPerM: 3.00, outputPerM: 15.00 },
      'claude-3-haiku': { provider: 'Anthropic', inputPerM: 0.25, outputPerM: 1.25 },
      'gpt-4o': { provider: 'OpenAI', inputPerM: 2.50, outputPerM: 10.00 },
      'gpt-4o-mini': { provider: 'OpenAI', inputPerM: 0.15, outputPerM: 0.60 },
      'gemini-1-5-pro': { provider: 'Google', inputPerM: 3.50, outputPerM: 10.50 },
      'gemini-1-5-flash': { provider: 'Google', inputPerM: 0.075, outputPerM: 0.30 },
      'deepseek-v3': { provider: 'DeepSeek', inputPerM: 0.14, outputPerM: 0.28 },
      ...customRates
    };
  }

  getModel(modelId) {
    return this.models[modelId] || null;
  }

  calculateCost(modelId, inputTokens = 0, outputTokens = 0) {
    const model = this.getModel(modelId);
    if (!model) {
      throw new Error('Unknown modelId: ' + modelId);
    }

    const inputCost = (inputTokens / 1000000) * model.inputPerM;
    const outputCost = (outputTokens / 1000000) * model.outputPerM;
    const totalCost = inputCost + outputCost;

    return {
      modelId,
      provider: model.provider,
      inputTokens,
      outputTokens,
      inputCostUsd: +inputCost.toFixed(6),
      outputCostUsd: +outputCost.toFixed(6),
      totalCostUsd: +totalCost.toFixed(6)
    };
  }

  calculateSavings(modelId, rawTokens = 0, trimmedTokens = 0) {
    const raw = this.calculateCost(modelId, rawTokens, 0);
    const trimmed = this.calculateCost(modelId, trimmedTokens, 0);
    const savedTokens = Math.max(0, rawTokens - trimmedTokens);
    const savedDollars = Math.max(0, raw.totalCostUsd - trimmed.totalCostUsd);
    const savingsPercent = rawTokens > 0 ? +((savedTokens / rawTokens) * 100).toFixed(2) : 0;

    return {
      modelId,
      rawTokens,
      trimmedTokens,
      savedTokens,
      savingsPercent,
      rawCostUsd: raw.totalCostUsd,
      trimmedCostUsd: trimmed.totalCostUsd,
      savedCostUsd: +savedDollars.toFixed(6)
    };
  }

  compareAllModels(rawTokens = 10000, trimmedTokens = 6000) {
    const comparisons = [];
    for (const modelId in this.models) {
      comparisons.push(this.calculateSavings(modelId, rawTokens, trimmedTokens));
    }
    return comparisons;
  }
}

module.exports = { TokenPricingOracle };
