class CanaryEvaluator {
  constructor(options = {}) {
    this.minAccuracyThreshold = options.minAccuracyThreshold !== undefined ? options.minAccuracyThreshold : 0.98;
    this.maxLatencyMs = options.maxLatencyMs || 50;
  }

  evaluatePromptPair(originalPrompt, trimmedPrompt, evaluationSuite = []) {
    // Check basic structural integrity
    if (!trimmedPrompt || typeof trimmedPrompt !== 'string') {
      return {
        passed: false,
        reason: 'Trimmed prompt is empty or invalid',
        rollbackRecommended: true
      };
    }

    let passedTests = 0;
    const testResults = [];

    for (const test of evaluationSuite) {
      const { name, assertionFn } = test;
      let testPassed = false;
      let errorMsg = null;
      try {
        testPassed = Boolean(assertionFn(trimmedPrompt, originalPrompt));
      } catch (err) {
        testPassed = false;
        errorMsg = err.message;
      }

      if (testPassed) passedTests++;
      testResults.push({ name, passed: testPassed, error: errorMsg });
    }

    const totalTests = evaluationSuite.length;
    const accuracy = totalTests > 0 ? (passedTests / totalTests) : 1.0;
    const meetsAccuracy = accuracy >= this.minAccuracyThreshold;
    const rollbackRecommended = !meetsAccuracy;

    return {
      passed: meetsAccuracy,
      totalTests,
      passedTests,
      accuracyRate: Number(accuracy.toFixed(4)),
      minAccuracyThreshold: this.minAccuracyThreshold,
      rollbackRecommended,
      testResults
    };
  }

  generateCanaryReport(canaryResult, metadata = {}) {
    return {
      timestamp: new Date().toISOString(),
      metadata,
      canaryResult,
      status: canaryResult.passed ? 'CANARY_PROMOTED_TO_PRODUCTION' : 'CANARY_ROLLED_BACK_FAIL_SAFE'
    };
  }
}

module.exports = { CanaryEvaluator };
