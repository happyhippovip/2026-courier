/**
 * pre_commit_linter.js - Git Hook Pre-Commit Context & Token Linter
 * Scans staged prompt files, detects token bloat, flags secret leaks, and offers autofixes.
 */
class PreCommitContextLinter {
  constructor(options = {}) {
    this.options = {
      maxTokensWarning: options.maxTokensWarning || 2000,
      maxTokensError: options.maxTokensError || 6000,
      blockOnWarning: options.blockOnWarning || false,
      ...options
    };
  }

  estimateTokens(text) {
    if (!text) return 0;
    return Math.ceil(text.length / 4);
  }

  lintFile(file) {
    const filename = file.path || 'unknown_file';
    const content = file.content || '';
    const tokenCount = this.estimateTokens(content);
    const issues = [];
    let fixedContent = content;

    // Check secrets
    const secretMatches = content.match(/(sk-[a-zA-Z0-9]{32,}|ghp_[a-zA-Z0-9]{36}|AIza[0-9A-Za-z-_]{35})/g);
    if (secretMatches) {
      issues.push({
        severity: 'error',
        code: 'SECRET_LEAK_DETECTED',
        message: 'Potential unredacted API key detected: ' + secretMatches[0].substring(0, 8) + '...'
      });
    }

    // Check token thresholds
    if (tokenCount > this.options.maxTokensError) {
      issues.push({
        severity: 'error',
        code: 'TOKEN_BUDGET_EXCEEDED',
        message: 'File token count (' + tokenCount + ') exceeds maximum error limit (' + this.options.maxTokensError + ')'
      });
    } else if (tokenCount > this.options.maxTokensWarning) {
      issues.push({
        severity: 'warning',
        code: 'TOKEN_BUDGET_WARNING',
        message: 'File token count (' + tokenCount + ') exceeds warning threshold (' + this.options.maxTokensWarning + ')'
      });
    }

    // Check repetitive separator banners
    const bannerMatches = content.match(/([-=_]{10,})/g);
    if (bannerMatches && bannerMatches.length > 2) {
      issues.push({
        severity: 'warning',
        code: 'REPETITIVE_SEPARATOR_BLOAT',
        message: 'Found ' + bannerMatches.length + ' long repetitive separator lines'
      });
      // Autofix: collapse multiple separator lines
      fixedContent = fixedContent.replace(/([-=_]{10,}\r?\n){2,}/g, '----------\n');
    }

    // Check trailing whitespace
    if (/ +$/m.test(content)) {
      fixedContent = fixedContent.replace(/[ \t]+$/gm, '');
    }

    const hasErrors = issues.some(i => i.severity === 'error');
    const hasWarnings = issues.some(i => i.severity === 'warning');
    const fixedTokenCount = this.estimateTokens(fixedContent);

    return {
      filename,
      tokenCount,
      fixedTokenCount,
      tokensSavedIfFixed: Math.max(0, tokenCount - fixedTokenCount),
      issues,
      hasErrors,
      hasWarnings,
      fixedContent
    };
  }

  lintAll(files = [], options = {}) {
    const results = files.map(f => this.lintFile(f));
    let totalErrors = 0;
    let totalWarnings = 0;
    let totalSavedIfFixed = 0;

    results.forEach(r => {
      if (r.hasErrors) totalErrors++;
      if (r.hasWarnings) totalWarnings++;
      totalSavedIfFixed += r.tokensSavedIfFixed;
    });

    const shouldBlock = totalErrors > 0 || (this.options.blockOnWarning && totalWarnings > 0);

    return {
      timestamp: new Date().toISOString(),
      summary: {
        totalFilesScanned: files.length,
        totalErrors,
        totalWarnings,
        totalTokensSavedIfFixed: totalSavedIfFixed,
        passed: !shouldBlock,
        exitCode: shouldBlock ? 1 : 0
      },
      fileResults: results
    };
  }
}

module.exports = { PreCommitContextLinter };
