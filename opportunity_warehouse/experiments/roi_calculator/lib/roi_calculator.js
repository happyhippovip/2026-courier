/**
 * roi_calculator.js - Enterprise ROI & Payback Calculator
 * Computes exact monthly/annual token cost savings, payback periods, and generates financial markdown tables.
 */
class EnterpriseRoiCalculator {
  constructor(options = {}) {
    this.ratesPerMillion = {
      'claude-3-5-sonnet': 3.00,
      'gpt-4o': 2.50,
      'gemini-1-5-pro': 3.50,
      'deepseek-v3': 0.14,
      ...options.ratesPerMillion
    };
    this.trimmingEfficiency = options.trimmingEfficiency || 0.38; // 38% reduction
  }

  calculate(inputs = {}) {
    const teamSize = inputs.teamSize || 10;
    const promptsPerDevPerDay = inputs.promptsPerDevPerDay || 40;
    const avgTokensPerPrompt = inputs.avgTokensPerPrompt || 12000;
    const model = inputs.model || 'claude-3-5-sonnet';
    const workingDaysPerMonth = inputs.workingDaysPerMonth || 21;
    const licenseCostEur = inputs.licenseCostEur || 199.00; // Team Pack default

    const rate = this.ratesPerMillion[model] || 3.00;

    const dailyPromptsTotal = teamSize * promptsPerDevPerDay;
    const monthlyPromptsTotal = dailyPromptsTotal * workingDaysPerMonth;

    const monthlyBaselineTokens = monthlyPromptsTotal * avgTokensPerPrompt;
    const monthlySavedTokens = monthlyBaselineTokens * this.trimmingEfficiency;
    const monthlyTrimmedTokens = monthlyBaselineTokens - monthlySavedTokens;

    const monthlyBaselineCost = (monthlyBaselineTokens / 1000000) * rate;
    const monthlyTrimmedCost = (monthlyTrimmedTokens / 1000000) * rate;
    const monthlyGrossSavings = monthlyBaselineCost - monthlyTrimmedCost;

    const annualGrossSavings = monthlyGrossSavings * 12;
    const netAnnualSavings = annualGrossSavings - licenseCostEur;
    const roiPercentage = licenseCostEur > 0 ? +((netAnnualSavings / licenseCostEur) * 100).toFixed(1) : 0;

    const dailySavings = monthlyGrossSavings / workingDaysPerMonth;
    const paybackDays = dailySavings > 0 ? +(licenseCostEur / dailySavings).toFixed(1) : 0;

    return {
      model,
      ratePerMillionInput: rate,
      teamSize,
      promptsPerDevPerDay,
      avgTokensPerPrompt,
      workingDaysPerMonth,
      monthlyMetrics: {
        baselineTokens: Math.round(monthlyBaselineTokens),
        trimmedTokens: Math.round(monthlyTrimmedTokens),
        tokensSaved: Math.round(monthlySavedTokens),
        baselineCostUsd: +monthlyBaselineCost.toFixed(2),
        trimmedCostUsd: +monthlyTrimmedCost.toFixed(2),
        grossSavingsUsd: +monthlyGrossSavings.toFixed(2)
      },
      annualMetrics: {
        grossSavingsUsd: +annualGrossSavings.toFixed(2),
        licenseCostEur,
        netSavingsUsd: +netAnnualSavings.toFixed(2),
        roiPercentage,
        paybackDays
      }
    };
  }

  generateMarkdownTable(calcResult) {
    const m = calcResult.monthlyMetrics;
    const a = calcResult.annualMetrics;

    let md = '### Enterprise ROI Financial Summary (' + calcResult.model + ')\n\n';
    md += '| Financial Metric | Monthly Value | Annualized Value |\n';
    md += '| :--- | :--- | :--- |\n';
    md += '| **Baseline Token Bill** | $' + m.baselineCostUsd + ' | $' + (m.baselineCostUsd * 12).toFixed(2) + ' |\n';
    md += '| **With Context Trimmer** | $' + m.trimmedCostUsd + ' | $' + (m.trimmedCostUsd * 12).toFixed(2) + ' |\n';
    md += '| **Net Token Savings** | **$' + m.grossSavingsUsd + '** | **$' + a.grossSavingsUsd + '** |\n';
    md += '| **License Cost (Team)** | - | €' + a.licenseCostEur + ' |\n';
    md += '| **Net ROI** | - | **' + a.roiPercentage + '%** |\n';
    md += '| **Payback Period** | **' + a.paybackDays + ' working days** | - |\n';

    return md;
  }
}

module.exports = { EnterpriseRoiCalculator };
