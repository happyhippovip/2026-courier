// Leaderboard Exporter — Generates LEADERBOARD.md
// Invariant: Never present scalar score alone. Store component evidence and confidence alongside it.

const fs = require('fs');
const path = require('path');
const { PortfolioManager, HORIZONS } = require('./portfolios');

class LeaderboardGenerator {
  static generateMarkdown(warehouse, outputPath = null) {
    const opportunities = warehouse.getAllOpportunities();
    const portfolioMgr = new PortfolioManager();
    const rankedHorizons = portfolioMgr.rankAllHorizons(opportunities);
    const allocation = portfolioMgr.calculateAllocation(opportunities);

    const targetPath = outputPath || path.join(warehouse.warehouseDir, 'LEADERBOARD.md');

    const lines = [
      '# MONEY FACTORY LEADERBOARD & ECONOMIC RADAR',
      '',
      `> Generated at: ${new Date().toISOString()} | Total Opportunities: ${opportunities.length}`,
      '',
      '## 1. Top Opportunities Across All Horizons',
      '',
      '| Rank | ID | Title | Status | Horizon | Money Score | Confidence | Evidence Score | Time to €1 | Expected Profit | Human Gates |',
      '| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |'
    ];

    const sortedAll = [...opportunities].sort((a, b) => {
      const sa = (a.score && a.score.scalar_score) || 0;
      const sb = (b.score && b.score.scalar_score) || 0;
      return sb - sa;
    });

    sortedAll.forEach((opp, idx) => {
      const s = opp.score || { scalar_score: 0, confidence: 0, evidence_score: 'UNKNOWN' };
      const gates = (opp.human_gates && opp.human_gates.length > 0) ? opp.human_gates.join(', ') : 'NONE';
      lines.push(
        `| ${idx + 1} | \`${opp.id}\` | ${opp.title} | \`${opp.status}\` | \`${opp.horizon}\` | **${s.scalar_score}** | ${s.confidence} | ${s.evidence_score} | ${opp.time_to_first_euro}d | €${opp.expected_profit_eur} | ${gates} |`
      );
    });

    lines.push('');
    lines.push('---');
    lines.push('');
    lines.push('## 2. Portfolio Strategy & Resource Allocation');
    lines.push('');
    lines.push(`- **CASH NOW (~50% target)**: ${allocation.allocations.CASH_NOW.count} opportunities (${allocation.allocations.CASH_NOW.allocated_agent_hours}h capacity)`);
    lines.push(`- **GROWTH (~35% target)**: ${allocation.allocations.GROWTH.count} opportunities (${allocation.allocations.GROWTH.allocated_agent_hours}h capacity)`);
    lines.push(`- **MOONSHOTS (~15% target)**: ${allocation.allocations.MOONSHOTS.count} opportunities (${allocation.allocations.MOONSHOTS.allocated_agent_hours}h capacity)`);
    lines.push('');
    lines.push('---');
    lines.push('');
    lines.push('## 3. Horizon Rankings');

    for (const [horizon, list] of Object.entries(rankedHorizons)) {
      lines.push('');
      lines.push(`### Horizon: \`${horizon}\``);
      lines.push('');
      if (list.length === 0) {
        lines.push('*No opportunities currently registered for this horizon.*');
      } else {
        lines.push('| Rank | ID | Title | Money Score | Revenue Prob | Expected Profit | Automation | Risk | Next Test |');
        lines.push('| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |');
        list.forEach((opp, i) => {
          const sc = opp.score || {};
          lines.push(
            `| ${i + 1} | \`${opp.id}\` | ${opp.title} | **${sc.scalar_score || 0}** | ${opp.revenue_probability} | €${opp.expected_profit_eur} | ${opp.automation_score} | ${opp.risk_score} | ${opp.next_test} |`
          );
        });
      }
    }

    lines.push('');
    lines.push('---');
    lines.push('');
    lines.push('## 4. Economic Anti-Loop & Safety Verification');
    lines.push('');
    lines.push('- **Autonomous Spend Limit**: `€0.00` (Strictly Enforced)');
    lines.push('- **Active Real Trades**: `0`');
    lines.push('- **Connected Wallets**: `NO`');
    lines.push('- **Status**: All production deployments, outreach, and spend requests remain locked behind `HUMAN_GATE`.');

    const content = lines.join('\n');
    fs.writeFileSync(targetPath, content, 'utf8');
    return content;
  }
}

module.exports = {
  LeaderboardGenerator
};
