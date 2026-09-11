/**
 * benchmark_harness.js - Semantic Prompt Compression Benchmark & Regression Harness
 * Assesses instruction retention, code symbol preservation, and noise removal rates.
 */
class PromptBenchmarkHarness {
  constructor(options = {}) {
    this.minAcceptableRetention = options.minAcceptableRetention || 0.95; // 95%
  }

  evaluateTestCase(testCase) {
    const raw = testCase.rawPrompt || '';
    const trimmed = testCase.trimmedPrompt || '';
    const requiredSymbols = testCase.requiredSymbols || [];
    const expectedKeywords = testCase.expectedKeywords || [];
    const prohibitedPatterns = testCase.prohibitedPatterns || [];

    // Check required symbols
    let symbolsPreserved = 0;
    const missingSymbols = [];
    for (const sym of requiredSymbols) {
      if (trimmed.includes(sym)) {
        symbolsPreserved++;
      } else {
        missingSymbols.push(sym);
      }
    }
    const symbolRetentionRate = requiredSymbols.length > 0 ? symbolsPreserved / requiredSymbols.length : 1.0;

    // Check expected keywords
    let keywordsPreserved = 0;
    const missingKeywords = [];
    for (const kw of expectedKeywords) {
      if (trimmed.includes(kw)) {
        keywordsPreserved++;
      } else {
        missingKeywords.push(kw);
      }
    }
    const keywordRetentionRate = expectedKeywords.length > 0 ? keywordsPreserved / expectedKeywords.length : 1.0;

    // Check prohibited patterns (noise that should have been pruned)
    let noiseRemoved = 0;
    const remainingNoise = [];
    for (const pat of prohibitedPatterns) {
      const regex = new RegExp(pat);
      if (!regex.test(trimmed)) {
        noiseRemoved++;
      } else {
        remainingNoise.push(pat);
      }
    }
    const noiseRemovalRate = prohibitedPatterns.length > 0 ? noiseRemoved / prohibitedPatterns.length : 1.0;

    // Semantic accuracy retention
    const semanticRetention = (symbolRetentionRate * 0.6) + (keywordRetentionRate * 0.4);
    const passed = semanticRetention >= this.minAcceptableRetention && missingSymbols.length === 0;

    const charsSaved = raw.length - trimmed.length;
    const compressionRatio = raw.length > 0 ? +((charsSaved / raw.length) * 100).toFixed(2) : 0;

    return {
      testCaseId: testCase.id || 'unnamed_case',
      passed,
      semanticRetentionRate: +semanticRetention.toFixed(4),
      symbolRetentionRate: +symbolRetentionRate.toFixed(4),
      keywordRetentionRate: +keywordRetentionRate.toFixed(4),
      noiseRemovalRate: +noiseRemovalRate.toFixed(4),
      compressionRatio,
      missingSymbols,
      missingKeywords,
      remainingNoise
    };
  }

  runSuite(testCases = []) {
    const results = testCases.map(tc => this.evaluateTestCase(tc));
    let passedCount = 0;
    let totalRetention = 0;
    let totalCompression = 0;

    results.forEach(r => {
      if (r.passed) passedCount++;
      totalRetention += r.semanticRetentionRate;
      totalCompression += r.compressionRatio;
    });

    const count = testCases.length;
    const avgRetention = count > 0 ? +(totalRetention / count).toFixed(4) : 1.0;
    const avgCompression = count > 0 ? +(totalCompression / count).toFixed(2) : 0;
    const allPassed = passedCount === count;

    return {
      timestamp: new Date().toISOString(),
      summary: {
        totalCases: count,
        passedCases: passedCount,
        failedCases: count - passedCount,
        averageSemanticRetention: avgRetention,
        averageCompressionRatioPercent: avgCompression,
        allPassed
      },
      results
    };
  }
}

module.exports = { PromptBenchmarkHarness };
