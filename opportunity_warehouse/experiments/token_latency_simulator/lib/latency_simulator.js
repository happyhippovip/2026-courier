// Empirical token processing speeds (tokens/sec) & pricing ($ / million prompt tokens)
const PROVIDER_METRICS = {
  claude_3_5_sonnet: {
    name: 'Anthropic Claude 3.5 Sonnet',
    prompt_rate_tokens_per_sec: 4500,
    price_per_m_prompt_tokens: 3.00,
    base_overhead_ms: 320
  },
  gpt_4o: {
    name: 'OpenAI GPT-4o',
    prompt_rate_tokens_per_sec: 5200,
    price_per_m_prompt_tokens: 2.50,
    base_overhead_ms: 280
  },
  gemini_1_5_flash: {
    name: 'Google Gemini 1.5 Flash',
    prompt_rate_tokens_per_sec: 8000,
    price_per_m_prompt_tokens: 0.35,
    base_overhead_ms: 190
  }
};

function calculateLatencyMs(tokens, providerKey) {
  const provider = PROVIDER_METRICS[providerKey];
  if (!provider) throw new Error(`Unknown provider: ${providerKey}`);
  const processingTimeMs = (tokens / provider.prompt_rate_tokens_per_sec) * 1000;
  return Math.round(provider.base_overhead_ms + processingTimeMs);
}

function simulateSavings(originalTokens, optimizedTokens, requestsPerMonth = 1000) {
  if (originalTokens < optimizedTokens) {
    throw new Error('Original tokens must be greater than or equal to optimized tokens');
  }
  const tokenDelta = originalTokens - optimizedTokens;
  const reductionPercent = Math.round((tokenDelta / originalTokens) * 1000) / 10;
  const totalTokensSaved = tokenDelta * requestsPerMonth;

  const providerBreakdowns = {};
  for (const [key, meta] of Object.entries(PROVIDER_METRICS)) {
    const origLatency = calculateLatencyMs(originalTokens, key);
    const optLatency = calculateLatencyMs(optimizedTokens, key);
    const latencySavedMs = origLatency - optLatency;

    const monthlyCostOriginal = (originalTokens * requestsPerMonth / 1000000) * meta.price_per_m_prompt_tokens;
    const monthlyCostOptimized = (optimizedTokens * requestsPerMonth / 1000000) * meta.price_per_m_prompt_tokens;
    const monthlyDollarsSaved = Math.round((monthlyCostOriginal - monthlyCostOptimized) * 100) / 100;

    const monthlySecondsWaitingSaved = Math.round((latencySavedMs * requestsPerMonth) / 1000);

    providerBreakdowns[key] = {
      name: meta.name,
      original_latency_ms: origLatency,
      optimized_latency_ms: optLatency,
      latency_saved_ms_per_request: latencySavedMs,
      monthly_cost_saved_usd: monthlyDollarsSaved,
      monthly_wait_time_saved_seconds: monthlySecondsWaitingSaved
    };
  }

  return {
    scenario: {
      original_tokens: originalTokens,
      optimized_tokens: optimizedTokens,
      tokens_saved_per_request: tokenDelta,
      reduction_percent: reductionPercent,
      requests_per_month: requestsPerMonth,
      total_tokens_saved_monthly: totalTokensSaved
    },
    providers: providerBreakdowns,
    analyzed_at: new Date().toISOString()
  };
}

module.exports = {
  PROVIDER_METRICS,
  calculateLatencyMs,
  simulateSavings
};
