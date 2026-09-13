#!/usr/bin/env node
// bin/agent-context-trimmer.js
// Command line entry point for Agent Context Trimmer

const path = require('path');
const fs = require('fs');
const { ContextAnalyzer } = require('../lib/analyzer');
const { AuditReporter } = require('../lib/reporter');

function printUsage() {
  console.log(`
Usage: agent-context-trimmer [options] [target-directory]

Options:
  --html [path]       Generate self-contained HTML audit dashboard (e.g. --html audit.html)
  --turns [N]         Average turns per developer session (default: 40)
  --sessions [N]      Developer sessions per month (default: 20)
  --json              Output raw JSON report to stdout
  --version, -v       Print current version
  --help, -h          Print this help menu

Examples:
  agent-context-trimmer .
  agent-context-trimmer --html report.html ./my-project
`);
}

function main() {
  const args = process.argv.slice(2);

  if (args.includes('--help') || args.includes('-h')) {
    printUsage();
    process.exit(0);
  }

  if (args.includes('--version') || args.includes('-v')) {
    const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8'));
    console.log(`agent-context-trimmer v${pkg.version}`);
    process.exit(0);
  }

  let targetDir = process.cwd();
  let htmlPath = null;
  let jsonOutput = false;
  let sessionTurns = 40;
  let sessionsPerMonth = 20;

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--html') {
      htmlPath = args[++i] || 'agent-token-audit.html';
    } else if (arg === '--json') {
      jsonOutput = true;
    } else if (arg === '--turns') {
      sessionTurns = parseInt(args[++i], 10) || 40;
    } else if (arg === '--sessions') {
      sessionsPerMonth = parseInt(args[++i], 10) || 20;
    } else if (!arg.startsWith('-')) {
      targetDir = path.resolve(arg);
    }
  }

  if (!fs.existsSync(targetDir)) {
    console.error(`Error: Target directory does not exist: ${targetDir}`);
    process.exit(1);
  }

  const analyzer = new ContextAnalyzer({ sessionTurns, sessionsPerMonth });
  const report = analyzer.auditWorkspace(targetDir);

  if (jsonOutput) {
    console.log(JSON.stringify(report, null, 2));
  } else {
    console.log(AuditReporter.formatTerminal(report));
  }

  if (htmlPath) {
    const resolvedHtml = path.resolve(process.cwd(), htmlPath);
    AuditReporter.generateHtmlReport(report, resolvedHtml);
    console.log(`Saved interactive HTML report to: ${resolvedHtml}`);
  }
}

if (require.main === module) {
  main();
}
