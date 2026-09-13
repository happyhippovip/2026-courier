// lib/reporter.js
// Formats terminal summaries and self-contained interactive HTML audit reports.

const fs = require('fs');
const path = require('path');

class AuditReporter {
  static formatTerminal(auditResult) {
    const lines = [];
    lines.push('================================================================');
    lines.push('         AGENT CONTEXT & TOKEN COST AUDIT REPORT               ');
    lines.push('================================================================');
    lines.push(`Target Workspace : ${auditResult.workspace_dir}`);
    lines.push(`Files Discovered : ${auditResult.files_discovered_count}`);
    lines.push(`Tokens Per Turn  : ${auditResult.total_context_tokens_per_turn.toLocaleString()} tokens`);
    lines.push(`Token Waste/Turn : ${auditResult.total_wasted_tokens_per_turn.toLocaleString()} tokens (${auditResult.optimization_potential_percent}% reducible)`);
    lines.push(`Issues Detected  : ${auditResult.total_issues_detected}`);
    lines.push('----------------------------------------------------------------');
    lines.push('PROJECTED MONTHLY COST (40 turns/day x 20 working days):');

    for (const [model, cost] of Object.entries(auditResult.cost_breakdown)) {
      lines.push(`  - ${model.padEnd(18)} : Total: $${cost.monthly_total_burn_usd.toFixed(2)} | Waste: $${cost.monthly_wasted_burn_usd.toFixed(2)} (Save: $${cost.potential_monthly_savings_usd.toFixed(2)}/mo)`);
    }

    lines.push('----------------------------------------------------------------');
    lines.push('DISCOVERED RULE FILES:');
    for (const f of auditResult.files) {
      lines.push(`  * ${f.file} (${f.estimated_tokens.toLocaleString()} tokens, ${f.issues.length} issues)`);
      for (const iss of f.issues) {
        lines.push(`      [${iss.severity}] Line ${iss.line}: ${iss.message}`);
      }
    }
    lines.push('================================================================');
    lines.push('RECOMMENDATION:');
    if (auditResult.total_wasted_tokens_per_turn > 0) {
      lines.push(`Trim redundant rules and move embedded code blocks out of system prompts`);
      lines.push(`to save an estimated $${auditResult.cost_breakdown['claude-3-5-sonnet'].potential_monthly_savings_usd}/month immediately.`);
    } else {
      lines.push('Your agent configurations are already lean and optimal!');
    }
    lines.push('================================================================\n');

    return lines.join('\n');
  }

  static generateHtmlReport(auditResult, outputPath) {
    const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Agent Context Trimmer - Audit Report</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 2rem; }
    .container { max-width: 900px; margin: 0 auto; }
    h1 { color: #38bdf8; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #94a3b8; font-size: 0.95rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; padding: 1.25rem; border-radius: 8px; border: 1px solid #334155; }
    .card-title { color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .card-val { font-size: 1.75rem; font-weight: bold; margin-top: 0.5rem; color: #f8fafc; }
    .highlight { color: #4ade80; }
    .table { width: 100%; border-collapse: collapse; margin-top: 1rem; background: #1e293b; border-radius: 8px; overflow: hidden; border: 1px solid #334155; }
    th, td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #334155; }
    th { background: #0f172a; color: #94a3b8; font-weight: 600; font-size: 0.85rem; }
    .badge { padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
    .badge-high { background: #ef444422; color: #f87171; border: 1px solid #ef444455; }
    .badge-warn { background: #f59e0b22; color: #fbbf24; border: 1px solid #f59e0b55; }
    .badge-low { background: #3b82f622; color: #60a5fa; border: 1px solid #3b82f655; }
  </style>
</head>
<body>
  <div class="container">
    <h1>Agent Context & Token Cost Audit</h1>
    <div class="subtitle">Generated for: ${auditResult.workspace_dir} | ${auditResult.scanned_at_utc}</div>

    <div class="grid">
      <div class="card">
        <div class="card-title">Context Tokens / Turn</div>
        <div class="card-val">${auditResult.total_context_tokens_per_turn.toLocaleString()}</div>
      </div>
      <div class="card">
        <div class="card-title">Token Waste / Turn</div>
        <div class="card-val highlight">${auditResult.total_wasted_tokens_per_turn.toLocaleString()}</div>
      </div>
      <div class="card">
        <div class="card-title">Sonnet Monthly Savings</div>
        <div class="card-val highlight">$${auditResult.cost_breakdown['claude-3-5-sonnet'].potential_monthly_savings_usd}</div>
      </div>
      <div class="card">
        <div class="card-title">GPT-4o Monthly Savings</div>
        <div class="card-val highlight">$${auditResult.cost_breakdown['gpt-4o'].potential_monthly_savings_usd}</div>
      </div>
    </div>

    <h2>Discovered Rule Files & Issues</h2>
    ${auditResult.files.map(f => `
      <div class="card" style="margin-bottom: 1rem;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <strong style="color: #38bdf8;">${f.file}</strong>
          <span style="color: #94a3b8; font-size: 0.85rem;">${f.estimated_tokens.toLocaleString()} tokens | ${f.line_count} lines</span>
        </div>
        ${f.issues.length === 0 ? '<p style="color: #4ade80; font-size: 0.9rem; margin-top: 0.5rem;">Clean file - No redundant rules detected.</p>' : `
          <table class="table">
            <thead>
              <tr><th>Severity</th><th>Line</th><th>Issue Details</th><th>Est. Waste</th></tr>
            </thead>
            <tbody>
              ${f.issues.map(iss => `
                <tr>
                  <td><span class="badge badge-${iss.severity === 'HIGH' ? 'high' : iss.severity === 'WARNING' ? 'warn' : 'low'}">${iss.severity}</span></td>
                  <td>${iss.line}</td>
                  <td>${iss.message}</td>
                  <td>+${iss.estimated_tokens_wasted || 0} tok</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `}
      </div>
    `).join('')}
  </div>
</body>
</html>`;

    fs.writeFileSync(outputPath, html, 'utf8');
    return outputPath;
  }
}

module.exports = { AuditReporter };
