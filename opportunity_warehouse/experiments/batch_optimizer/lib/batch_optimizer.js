const fs = require('fs');
const path = require('path');

const TARGET_FILES = ['.cursorrules', 'AGENTS.md', 'CLAUDE.md', '.windsurfrules'];

function findRulesFiles(dir) {
  let found = [];
  if (!fs.existsSync(dir)) return found;

  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== 'node_modules' && entry.name !== '.git' && !entry.name.startsWith('.')) {
        found = found.concat(findRulesFiles(fullPath));
      }
    } else if (TARGET_FILES.includes(entry.name)) {
      found.push(fullPath);
    }
  }
  return found;
}

function auditWorkspaceBatch(workspaceRoots) {
  const reports = [];
  let aggregateTotalTokens = 0;
  let aggregateEstimatedSavings = 0;

  for (const root of workspaceRoots) {
    const rulesFiles = findRulesFiles(root);
    let wsTokens = 0;

    for (const file of rulesFiles) {
      try {
        const content = fs.readFileSync(file, 'utf8');
        const tokenEstimate = Math.ceil(content.length / 4);
        wsTokens += tokenEstimate;
      } catch {}
    }

    const estimatedSavingsTokens = Math.round(wsTokens * 0.42); // 42% average reduction
    aggregateTotalTokens += wsTokens;
    aggregateEstimatedSavings += estimatedSavingsTokens;

    reports.push({
      workspace_path: root,
      rules_files_found: rulesFiles.length,
      files: rulesFiles.map(f => path.basename(f)),
      total_tokens_est: wsTokens,
      tokens_saved_est: estimatedSavingsTokens,
      percent_savings: wsTokens > 0 ? 42.0 : 0
    });
  }

  return {
    total_workspaces_scanned: workspaceRoots.length,
    aggregate_total_tokens: aggregateTotalTokens,
    aggregate_tokens_saved: aggregateEstimatedSavings,
    aggregate_monthly_cost_saved_usd: Math.round((aggregateEstimatedSavings * 1500 / 1000000 * 3.00) * 100) / 100,
    workspaces: reports,
    scanned_at: new Date().toISOString()
  };
}

module.exports = { findRulesFiles, auditWorkspaceBatch, TARGET_FILES };
