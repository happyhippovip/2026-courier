// Zero-dependency context budget analyzer & allocation planner
function estimateTokens(text) {
  if (!text) return 0;
  // Standard heuristic: ~4 characters per token
  return Math.ceil(text.trim().length / 4);
}

function parseSections(content) {
  const lines = content.split('\n');
  const sections = [];
  let currentTitle = 'General Preamble';
  let currentLines = [];

  for (const line of lines) {
    if (line.startsWith('#')) {
      if (currentLines.join('\n').trim().length > 0) {
        sections.push({ title: currentTitle, text: currentLines.join('\n').trim() });
      }
      currentLines = [];
      currentTitle = line.replace(/^#+\s*/, '').trim() || 'Untitled Section';
    } else {
      currentLines.push(line);
    }
  }
  if (currentLines.join('\n').trim().length > 0) {
    sections.push({ title: currentTitle, text: currentLines.join('\n').trim() });
  }
  return sections;
}

function analyzeContextBudget(rulesContent, options = {}) {
  const totalWindow = options.totalContextWindow || 32000;
  const maxBudgetRatio = options.maxBudgetRatio || 0.10; // Max 10% for system instructions
  const maxAllowedTokens = Math.floor(totalWindow * maxBudgetRatio);

  const sections = parseSections(rulesContent);
  let totalTokens = 0;

  const sectionAnalysis = sections.map(sec => {
    const tokens = estimateTokens(sec.text);
    totalTokens += tokens;
    return {
      title: sec.title,
      estimated_tokens: tokens,
      percent_of_rules: 0 // Will compute below
    };
  });

  for (const sec of sectionAnalysis) {
    sec.percent_of_rules = totalTokens > 0 ? Math.round((sec.estimated_tokens / totalTokens) * 1000) / 10 : 0;
  }

  const isOverBudget = totalTokens > maxAllowedTokens;
  const headroomTokens = maxAllowedTokens - totalTokens;

  return {
    context_window_size: totalWindow,
    max_allowed_rules_tokens: maxAllowedTokens,
    total_rules_tokens: totalTokens,
    percent_of_context_window: Math.round((totalTokens / totalWindow) * 1000) / 10,
    is_over_budget: isOverBudget,
    headroom_tokens: headroomTokens,
    sections: sectionAnalysis,
    recommendation: isOverBudget
      ? `Warning: Rules exceed budget by ${Math.abs(headroomTokens)} tokens. Prune high-consumption sections.`
      : 'Healthy: Rules occupy well within safe context budget limits.',
    analyzed_at: new Date().toISOString()
  };
}

module.exports = { estimateTokens, parseSections, analyzeContextBudget };
