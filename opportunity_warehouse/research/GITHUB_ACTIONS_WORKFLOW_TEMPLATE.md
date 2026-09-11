# GITHUB ACTIONS CI/CD WORKFLOW TEMPLATE
**DOCUMENT:** `opportunity_warehouse/research/GITHUB_ACTIONS_WORKFLOW_TEMPLATE.md`  
**USAGE:** Add to `.github/workflows/agent-context-audit.yml`  

```yaml
name: Agent Context Bloat Audit

on:
  pull_request:
    paths:
      - '.cursorrules'
      - '.cursor/rules/**'
      - '.windsurfrules'
      - '.clinerules'
      - 'AGENTS.md'
      - '.gemini/**'
  push:
    branches:
      - main

jobs:
  audit-context-bloat:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20

      - name: Run Context Bloat Audit
        run: |
          npx agent-context-trimmer --audit --threshold 20 --json > audit_results.json
          cat audit_results.json

      - name: Comment on PR with Token Savings
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            if (fs.existsSync('audit_results.json')) {
              const audit = JSON.parse(fs.readFileSync('audit_results.json', 'utf8'));
              const comment = [
                '### ⚡ Agent Context Bloat Audit Report',
                `- **Files Scanned:** ${audit.summary.files_scanned}`,
                `- **Total Tokens Per Turn:** ${audit.summary.total_tokens_per_turn}`,
                `- **Wasted Boilerplate:** ${audit.summary.wasted_tokens_per_turn} tokens (${audit.summary.optimization_percent}% bloat)`,
                `- **Potential Annual Waste:** $${audit.estimated_savings.annual_cost_usd} USD`,
                '',
                '👉 Run `agent-context-trimmer` locally to optimize instructions.'
              ].join('\n');
              github.rest.issues.createComment({
                issue_number: context.issue.number,
                owner: context.repo.owner,
                repo: context.repo.repo,
                body: comment
              });
            }
```
