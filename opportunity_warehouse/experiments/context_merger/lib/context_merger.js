function mergeAgentContexts(agentContextMap) {
  const agentNames = Object.keys(agentContextMap);
  if (agentNames.length === 0) {
    return { shared_base_rules: '', agent_overlays: {}, total_savings_tokens: 0 };
  }

  // Split lines for each agent
  const linesByAgent = {};
  let totalRawTokens = 0;

  for (const name of agentNames) {
    const lines = agentContextMap[name].split('\n').map(l => l.trim()).filter(Boolean);
    linesByAgent[name] = new Set(lines);
    totalRawTokens += Math.ceil(agentContextMap[name].length / 4);
  }

  // Identify lines shared by ALL agents
  const firstAgentLines = Array.from(linesByAgent[agentNames[0]]);
  const sharedLines = firstAgentLines.filter(line => {
    return agentNames.every(name => linesByAgent[name].has(line));
  });

  const sharedSet = new Set(sharedLines);
  const overlays = {};
  let deduplicatedTokens = Math.ceil(sharedLines.join('\n').length / 4);

  for (const name of agentNames) {
    const specificLines = Array.from(linesByAgent[name]).filter(l => !sharedSet.has(l));
    overlays[name] = specificLines.join('\n');
    deduplicatedTokens += Math.ceil(overlays[name].length / 4);
  }

  const tokensSaved = Math.max(0, totalRawTokens - deduplicatedTokens);
  const reductionPercent = totalRawTokens > 0 ? Math.round((tokensSaved / totalRawTokens) * 1000) / 10 : 0;

  return {
    agents_count: agentNames.length,
    shared_rules_lines_count: sharedLines.length,
    shared_base_rules: sharedLines.join('\n'),
    agent_overlays: overlays,
    metrics: {
      original_total_tokens: totalRawTokens,
      optimized_total_tokens: deduplicatedTokens,
      tokens_saved_per_round: tokensSaved,
      reduction_percent: reductionPercent
    },
    merged_at: new Date().toISOString()
  };
}

module.exports = { mergeAgentContexts };
