/**
 * canary_validator.js - Automated Rollback Dry-Run & Non-Destructive Canary Validator
 * Executes simulated rule pruning against test fixtures, verifies code integrity, and issues rollback tokens.
 */
const crypto = require('crypto');

class CanaryValidator {
  constructor(options = {}) {
    this.maxAllowedRisk = options.maxAllowedRisk || 0.0;
    this.secretSalt = options.secretSalt || 'symphony_canary_secret_2026';
  }

  evaluateFixture(fixture, rules = []) {
    // Check if fixture contains required markers
    const originalContent = fixture.content || '';
    let prunedContent = originalContent;
    const ruleTrace = [];
    let riskPoints = 0;

    for (const rule of rules) {
      if (rule.pattern && rule.action === 'trim') {
        const regex = new RegExp(rule.pattern, 'g');
        const matches = prunedContent.match(regex);
        if (matches) {
          prunedContent = prunedContent.replace(regex, '');
          ruleTrace.push({ ruleId: rule.id, matchesCount: matches.length });
        }
      } else if (rule.action === 'drop_critical') {
        // High risk rule
        riskPoints += 50;
      }
    }

    // Integrity checks: ensure function signatures, return statements, or required brackets are preserved
    if (originalContent.includes('function') && !prunedContent.includes('function')) {
      riskPoints += 40;
    }
    if (originalContent.includes('return') && !prunedContent.includes('return')) {
      riskPoints += 40;
    }
    const openBraces = (prunedContent.match(/\{/g) || []).length;
    const closeBraces = (prunedContent.match(/\}/g) || []).length;
    if (openBraces !== closeBraces) {
      riskPoints += 60;
    }

    const riskIndex = Math.min(1.0, riskPoints / 100);
    return {
      fixtureName: fixture.name || 'unnamed_fixture',
      originalLength: originalContent.length,
      prunedLength: prunedContent.length,
      charsSaved: originalContent.length - prunedContent.length,
      riskIndex: +riskIndex.toFixed(2),
      ruleTrace,
      passed: riskIndex <= this.maxAllowedRisk
    };
  }

  executeCanary(fixtures = [], rules = []) {
    const results = fixtures.map(f => this.evaluateFixture(f, rules));
    let totalRisk = 0;
    let allPassed = true;

    results.forEach(r => {
      totalRisk += r.riskIndex;
      if (!r.passed) allPassed = false;
    });

    const averageRisk = fixtures.length > 0 ? +(totalRisk / fixtures.length).toFixed(2) : 0;
    const isApproved = allPassed && averageRisk <= this.maxAllowedRisk;

    let authorizationToken = null;
    if (isApproved) {
      const payload = JSON.stringify({ approved: true, count: fixtures.length, timestamp: Date.now() });
      const hash = crypto.createHmac('sha256', this.secretSalt).update(payload).digest('hex').substring(0, 24);
      authorizationToken = 'ROLLBACK_AUTH_' + hash.toUpperCase();
    }

    return {
      timestamp: new Date().toISOString(),
      summary: {
        totalFixtures: fixtures.length,
        averageRiskIndex: averageRisk,
        isApproved,
        authorizationToken
      },
      fixturesResults: results
    };
  }
}

module.exports = { CanaryValidator };
