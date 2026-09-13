// lib/analyzer.js
// Fast, zero-dependency token auditor and rule-bloat detector for AI coding agents.

const fs = require('fs');
const path = require('path');

// Leading model input pricing per 1M tokens (USD)
const PRICING_PER_MILLION = {
  'claude-3-5-sonnet': 3.00,
  'gpt-4o': 2.50,
  'gemini-1-5-pro': 1.25
};

// Known agent config and rule file patterns
// Known agent config and rule file patterns
const AGENT_FILE_PATTERNS = [
  /\.cursorrules$/i,
  /\.cursor[\\/]rules[\\/].*\.mdc?$/i,
  /\.gemini[\\/].*\.md$/i,
  /\.windsurfrules$/i,
  /\.?clinerules$/i,
  /CLINEmode(\.md)?$/i,
  /CLINE_RULES(\.md)?$/i,
  /\.copilot-instructions\.md$/i,
  /AGENTS?\.md$/i
];

class ContextAnalyzer {
  constructor(options = {}) {
    this.sessionTurns = options.sessionTurns || 40; // Average developer session turns
    this.sessionsPerMonth = options.sessionsPerMonth || 20; // Working days
  }

  // Fast Byte-Pair heuristic: ~4 characters per token in standard English / code
  static estimateTokens(text) {
    if (!text || typeof text !== 'string') return 0;
    // Word-based + character heuristic for accurate approximation
    const words = text.trim().split(/\s+/).filter(Boolean);
    const charCount = text.length;
    // Weight word count (1.33 tokens/word) and raw length (char/3.8)
    const tokenEst = Math.round((words.length * 1.3) + (charCount / 14));
    return Math.max(words.length > 0 ? 1 : 0, tokenEst);
  }

  // Scan a directory or single file for agent rule files
  scanDirectory(targetDir, maxDepth = 4) {
    const resolvedTarget = path.resolve(targetDir);
    if (!fs.existsSync(resolvedTarget)) {
      return [];
    }

    const stat = fs.statSync(resolvedTarget);
    if (stat.isFile()) {
      return [{
        fullPath: resolvedTarget,
        relPath: path.basename(resolvedTarget)
      }];
    }

    const matchedFiles = [];

    const walk = (dir, currentDepth) => {
      if (currentDepth > maxDepth) return;
      let entries = [];
      try {
        entries = fs.readdirSync(dir, { withFileTypes: true });
      } catch (err) {
        return; // Ignore unreadable directories
      }

      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        const relPath = path.relative(resolvedTarget, fullPath).replace(/\\/g, '/');

        // Ignore noisy directories
        if (entry.isDirectory()) {
          if (['node_modules', '.git', 'dist', 'build', '.next', 'coverage'].includes(entry.name)) {
            continue;
          }
          walk(fullPath, currentDepth + 1);
        } else if (entry.isFile()) {
          const isMatch = AGENT_FILE_PATTERNS.some(pat => pat.test(relPath) || pat.test(entry.name));
          if (isMatch) {
            matchedFiles.push({ fullPath, relPath });
          }
        }
      }
    };

    walk(resolvedTarget, 0);
    return matchedFiles;
  }

  // Analyze single file content for bloat, duplicate rules, and giant code blocks
  analyzeFile(filePath, relPath = null) {
    const displayPath = relPath || path.basename(filePath);
    if (!fs.existsSync(filePath)) {
      throw new Error(`File not found: ${filePath}`);
    }

    const content = fs.readFileSync(filePath, 'utf8');
    const lines = content.split('\n');
    const tokenCount = ContextAnalyzer.estimateTokens(content);
    const bytes = Buffer.byteLength(content, 'utf8');

    const issues = [];
    const ruleDirectives = [];
    const seenSentences = new Map();

    // Line-by-line inspection
    let inCodeBlock = false;
    let codeBlockLines = 0;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();

      // Detect code blocks
      if (trimmed.startsWith('```')) {
        if (!inCodeBlock) {
          inCodeBlock = true;
          codeBlockLines = 0;
        } else {
          inCodeBlock = false;
          if (codeBlockLines > 25) {
            issues.push({
              type: 'GIANT_EMBEDDED_CODE_BLOCK',
              line: i + 1,
              severity: 'WARNING',
              message: `Embedded code block is ${codeBlockLines} lines long. Large static code blocks should be referenced as external files rather than permanently injected into system prompts.`,
              estimated_tokens_wasted: Math.round(codeBlockLines * 8)
            });
          }
        }
        continue;
      }

      if (inCodeBlock) {
        codeBlockLines++;
        continue;
      }

      // Check for duplicate rule statements (bullet points or numbered instructions)
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || /^\d+\./.test(trimmed)) {
        const cleanedRule = trimmed.replace(/^[-*\d.]+\s*/, '').toLowerCase().replace(/[^\p{L}\p{N}\s]/gu, '').replace(/\s+/g, ' ').trim();
        if (cleanedRule.length >= 10) {
          if (seenSentences.has(cleanedRule)) {
            const firstLine = seenSentences.get(cleanedRule);
            issues.push({
              type: 'DUPLICATE_RULE',
              line: i + 1,
              severity: 'HIGH',
              message: `Duplicate or highly redundant rule. Identical to instruction on line ${firstLine}: "${trimmed.substring(0, 60)}..."`,
              estimated_tokens_wasted: ContextAnalyzer.estimateTokens(trimmed)
            });
          } else {
            seenSentences.set(cleanedRule, i + 1);
            ruleDirectives.push({ line: i + 1, text: trimmed });
          }
        }
      }

      // Detect obsolete or verbose boilerplate phrases
      if (/you are an ai language model/i.test(trimmed) || /as an expert senior engineer/i.test(trimmed)) {
        issues.push({
          type: 'VERBOSE_BOILERPLATE',
          line: i + 1,
          severity: 'LOW',
          message: `Generic role preamble adds tokens without steering agent capability: "${trimmed}"`,
          estimated_tokens_wasted: ContextAnalyzer.estimateTokens(trimmed)
        });
      }
    }

    return {
      file: displayPath,
      full_path: filePath,
      bytes,
      line_count: lines.length,
      estimated_tokens: tokenCount,
      issues,
      rule_directives_count: ruleDirectives.length
    };
  }

  // Audit entire workspace
  auditWorkspace(targetDir) {
    const files = this.scanDirectory(targetDir);
    const fileReports = [];

    let totalTokens = 0;
    let totalBytes = 0;
    let totalIssues = 0;
    let totalWastedTokens = 0;

    for (const f of files) {
      const rep = this.analyzeFile(f.fullPath, f.relPath);
      fileReports.push(rep);
      totalTokens += rep.estimated_tokens;
      totalBytes += rep.bytes;
      totalIssues += rep.issues.length;
      for (const iss of rep.issues) {
        totalWastedTokens += (iss.estimated_tokens_wasted || 0);
      }
    }

    // Compounded session and monthly cost calculation
    // Model re-sends system prompt on every turn of a session
    const tokensPerTurn = totalTokens;
    const tokensPerSession = tokensPerTurn * this.sessionTurns;
    const tokensPerMonth = tokensPerSession * this.sessionsPerMonth;

    const wastedTokensPerTurn = totalWastedTokens;
    const wastedTokensPerSession = wastedTokensPerTurn * this.sessionTurns;
    const wastedTokensPerMonth = wastedTokensPerSession * this.sessionsPerMonth;

    const costBreakdown = {};
    for (const [model, ratePerM] of Object.entries(PRICING_PER_MILLION)) {
      const monthlyTotalCost = (tokensPerMonth / 1_000_000) * ratePerM;
      const monthlyWastedCost = (wastedTokensPerMonth / 1_000_000) * ratePerM;
      costBreakdown[model] = {
        rate_per_million: ratePerM,
        monthly_total_burn_usd: parseFloat(monthlyTotalCost.toFixed(2)),
        monthly_wasted_burn_usd: parseFloat(monthlyWastedCost.toFixed(2)),
        potential_monthly_savings_usd: parseFloat(monthlyWastedCost.toFixed(2))
      };
    }

    return {
      workspace_dir: targetDir,
      scanned_at_utc: new Date().toISOString(),
      files_discovered_count: files.length,
      total_context_tokens_per_turn: totalTokens,
      total_wasted_tokens_per_turn: totalWastedTokens,
      optimization_potential_percent: totalTokens > 0 ? parseFloat(((totalWastedTokens / totalTokens) * 100).toFixed(1)) : 0,
      total_issues_detected: totalIssues,
      summary: {
        files_scanned: files.length,
        total_tokens_per_turn: totalTokens,
        wasted_tokens_per_turn: totalWastedTokens,
        optimization_percent: totalTokens > 0 ? parseFloat(((totalWastedTokens / totalTokens) * 100).toFixed(1)) : 0,
        total_issues: totalIssues,
        duplicate_rules: fileReports.reduce((acc, f) => acc + f.issues.filter(i => i.type === 'DUPLICATE_RULE').length, 0),
        code_blocks: fileReports.reduce((acc, f) => acc + f.issues.filter(i => i.type === 'GIANT_EMBEDDED_CODE_BLOCK').length, 0),
        wasted_tokens: totalWastedTokens
      },
      estimated_savings: {
        monthly_cost_usd: costBreakdown['claude-3-5-sonnet'].potential_monthly_savings_usd,
        annual_cost_usd: parseFloat((costBreakdown['claude-3-5-sonnet'].potential_monthly_savings_usd * 12).toFixed(2))
      },
      cost_breakdown: costBreakdown,
      files: fileReports
    };
  }
}

module.exports = {
  ContextAnalyzer,
  PRICING_PER_MILLION
};
