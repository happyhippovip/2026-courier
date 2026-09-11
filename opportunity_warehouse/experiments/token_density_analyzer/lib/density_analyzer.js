const MODEL_SPECS = {
  'gpt-4o': { maxContext: 128000, costPer1kInput: 0.0025, tokenRatio: 1.0 },
  'claude-3-5-sonnet': { maxContext: 200000, costPer1kInput: 0.003, tokenRatio: 1.05 },
  'gemini-1-5-pro': { maxContext: 2000000, costPer1kInput: 0.00125, tokenRatio: 0.98 },
  'llama-3-3-70b': { maxContext: 128000, costPer1kInput: 0.0008, tokenRatio: 1.02 },
  'deepseek-v3': { maxContext: 64000, costPer1kInput: 0.00014, tokenRatio: 0.95 }
};

class TokenDensityAnalyzer {
  constructor(options = {}) {
    this.customSpecs = options.specs || {};
  }

  getModelSpec(modelId) {
    return this.customSpecs[modelId] || MODEL_SPECS[modelId] || {
      maxContext: 128000,
      costPer1kInput: 0.002,
      tokenRatio: 1.0
    };
  }

  estimateTokens(text, modelId = 'gpt-4o') {
    const spec = this.getModelSpec(modelId);
    const charCount = text ? text.length : 0;
    const wordCount = text ? text.trim().split(/\s+/).filter(Boolean).length : 0;
    
    // Standard heuristic: ~4 chars per token for English/code, weighted by model ratio
    const rawTokens = Math.ceil((charCount / 4.0) * spec.tokenRatio);
    return {
      charCount,
      wordCount,
      estimatedTokens: Math.max(0, rawTokens),
      modelId
    };
  }

  analyzePromptEfficiency(originalText, trimmedText, modelId = 'gpt-4o') {
    const spec = this.getModelSpec(modelId);
    const orig = this.estimateTokens(originalText, modelId);
    const trimmed = this.estimateTokens(trimmedText, modelId);

    const tokensSaved = Math.max(0, orig.estimatedTokens - trimmed.estimatedTokens);
    const savingsPercent = orig.estimatedTokens > 0 
      ? Number(((tokensSaved / orig.estimatedTokens) * 100).toFixed(2))
      : 0;

    const originalCost = (orig.estimatedTokens / 1000) * spec.costPer1kInput;
    const trimmedCost = (trimmed.estimatedTokens / 1000) * spec.costPer1kInput;
    const costSavings = Number((originalCost - trimmedCost).toFixed(6));

    const originalUtilizationPct = Number(((orig.estimatedTokens / spec.maxContext) * 100).toFixed(4));
    const trimmedUtilizationPct = Number(((trimmed.estimatedTokens / spec.maxContext) * 100).toFixed(4));

    return {
      modelId,
      maxContext: spec.maxContext,
      original: {
        tokens: orig.estimatedTokens,
        chars: orig.charCount,
        costEstimateEurUsd: Number(originalCost.toFixed(6)),
        contextUtilizationPct: originalUtilizationPct
      },
      trimmed: {
        tokens: trimmed.estimatedTokens,
        chars: trimmed.charCount,
        costEstimateEurUsd: Number(trimmedCost.toFixed(6)),
        contextUtilizationPct: trimmedUtilizationPct
      },
      savings: {
        tokensSaved,
        savingsPercent,
        costSavingsEurUsd: costSavings
      }
    };
  }

  benchmarkAcrossFrontierModels(originalText, trimmedText) {
    const results = {};
    for (const modelId of Object.keys(MODEL_SPECS)) {
      results[modelId] = this.analyzePromptEfficiency(originalText, trimmedText, modelId);
    }
    return results;
  }
}

module.exports = { TokenDensityAnalyzer, MODEL_SPECS };
