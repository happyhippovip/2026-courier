'use strict';

/**
 * TestWeakeningDetector
 * Analyzes candidate test code changes against baseline versions to detect
 * intentional or accidental test suite weakening, removed assertions,
 * tautological bypasses, and skipped tests.
 */
class TestWeakeningDetector {
  constructor(options = {}) {
    this.allowRelaxation = options.allowRelaxation || false;
  }

  analyzeSource(sourceText) {
    if (!sourceText || typeof sourceText !== 'string') {
      return {
        assertionCount: 0,
        testCount: 0,
        skippedCount: 0,
        emptyTestCount: 0,
        tautologyCount: 0,
        suppressionCount: 0
      };
    }

    // 1. Count assertions
    const assertionRegex = /\b(assert\.[a-zA-Z0-9_]+|assert\(|expect\([^)]+\)\.[a-zA-Z0-9_]+|should\.[a-zA-Z0-9_]+)\b/g;
    const allAssertionMatches = sourceText.match(assertionRegex) || [];

    // 2. Count tautological assertions
    const tautologyRegexes = [
      /assert\s*\(\s*true\s*\)/g,
      /assert\.ok\s*\(\s*true\s*\)/g,
      /assert\.strictEqual\s*\(\s*(true|1|'a'|"a")\s*,\s*\1\s*\)/g,
      /expect\s*\(\s*true\s*\)\.to(Be|Equal)\s*\(\s*true\s*\)/g,
      /assert\s*\(\s*1\s*===\s*1\s*\)/g
    ];
    let tautologyCount = 0;
    for (const rx of tautologyRegexes) {
      const matches = sourceText.match(rx);
      if (matches) tautologyCount += matches.length;
    }

    const effectiveAssertionCount = Math.max(0, allAssertionMatches.length - tautologyCount);

    // 3. Count total tests
    const testRegex = /\b(it|test)\s*\(\s*['"`]/g;
    const testMatches = sourceText.match(testRegex) || [];
    const testCount = testMatches.length;

    // 4. Count skipped tests
    const skipRegex = /\b(it\.skip|test\.skip|xit|describe\.skip|xdescribe)\s*\(/g;
    const skipMatches = sourceText.match(skipRegex) || [];
    const skippedCount = skipMatches.length;

    // 5. Count empty test bodies: it('...', () => {}) or test("...", function() {})
    const emptyTestRegex = /\b(it|test)\s*\(\s*['"`][^'"`]+['"`]\s*,\s*(async\s*)?(\(\s*\)|function\s*\(\s*\))\s*=>?\s*\{\s*\}\s*\)/g;
    const emptyMatches = sourceText.match(emptyTestRegex) || [];
    const emptyTestCount = emptyMatches.length;

    // 6. Count suppression comments
    const suppressionRegex = /(\/\/\s*@ts-(ignore|nocheck)|\/\*\s*eslint-disable|\/\/\s*eslint-disable-line|\/\*\s*istanbul ignore)/g;
    const suppressionMatches = sourceText.match(suppressionRegex) || [];
    const suppressionCount = suppressionMatches.length;

    return {
      assertionCount: effectiveAssertionCount,
      grossAssertionCount: allAssertionMatches.length,
      testCount,
      skippedCount,
      emptyTestCount,
      tautologyCount,
      suppressionCount
    };
  }

  compare(baselineSource, candidateSource) {
    const baseMetrics = this.analyzeSource(baselineSource);
    const candMetrics = this.analyzeSource(candidateSource);

    const violations = [];

    // Check assertion degradation
    if (candMetrics.assertionCount < baseMetrics.assertionCount) {
      violations.push(
        `ASSERTIONS_DECREASED: Baseline had ${baseMetrics.assertionCount} valid assertions, candidate has only ${candMetrics.assertionCount}`
      );
    }

    // Check test count decrease
    if (candMetrics.testCount < baseMetrics.testCount) {
      violations.push(
        `TEST_COUNT_DECREASED: Baseline had ${baseMetrics.testCount} tests, candidate has only ${candMetrics.testCount}`
      );
    }

    // Check newly introduced skipped tests
    if (candMetrics.skippedCount > baseMetrics.skippedCount) {
      violations.push(
        `TESTS_SKIPPED: Newly introduced ${candMetrics.skippedCount - baseMetrics.skippedCount} skipped tests/suites`
      );
    }

    // Check empty test bodies
    if (candMetrics.emptyTestCount > baseMetrics.emptyTestCount) {
      violations.push(
        `EMPTY_TEST_BODIES_DETECTED: Candidate contains ${candMetrics.emptyTestCount} empty test cases`
      );
    }

    // Check tautological assertions
    if (candMetrics.tautologyCount > baseMetrics.tautologyCount) {
      violations.push(
        `TAUTOLOGICAL_ASSERTIONS_INTRODUCED: Candidate introduced ${candMetrics.tautologyCount - baseMetrics.tautologyCount} tautological assertions`
      );
    }

    // Check suppression comments
    if (candMetrics.suppressionCount > baseMetrics.suppressionCount) {
      violations.push(
        `SUPPRESSION_DIRECTIVES_INJECTED: Candidate introduced ${candMetrics.suppressionCount - baseMetrics.suppressionCount} lint/type suppression comments`
      );
    }

    return {
      passed: violations.length === 0,
      violations,
      baseMetrics,
      candMetrics
    };
  }
}

module.exports = { TestWeakeningDetector };
