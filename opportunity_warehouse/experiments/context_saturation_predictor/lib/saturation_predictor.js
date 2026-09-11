/**
 * saturation_predictor.js - LLM Context Window Saturation & Degradation Predictor
 * Models attention degradation, lost-in-the-middle risks, and saturation hazards
 * across frontier LLMs (Claude 3.5 Sonnet, GPT-4o, Gemini 1.5 Pro, Llama 3.1).
 */
class ContextSaturationPredictor {
  constructor() {
    this.modelRegistry = {
      'claude-3-5-sonnet': { maxTokens: 200000, sweetSpotTokens: 140000, middleLossStart: 0.35, middleLossEnd: 0.75 },
      'gpt-4o': { maxTokens: 128000, sweetSpotTokens: 90000, middleLossStart: 0.30, middleLossEnd: 0.70 },
      'gemini-1-5-pro': { maxTokens: 2000000, sweetSpotTokens: 1500000, middleLossStart: 0.40, middleLossEnd: 0.80 },
      'llama-3-1-70b': { maxTokens: 128000, sweetSpotTokens: 80000, middleLossStart: 0.25, middleLossEnd: 0.75 }
    };
  }

  estimateTokens(text) {
    if (!text || typeof text !== 'string') return 0;
    return Math.ceil(text.length * 0.25);
  }

  predictSaturation(promptText, targetModel = 'claude-3-5-sonnet', criticalInstructionPositions = []) {
    const modelProfile = this.modelRegistry[targetModel] || this.modelRegistry['claude-3-5-sonnet'];
    const totalTokens = this.estimateTokens(promptText);
    const totalChars = (promptText || '').length;

    const saturationRatio = totalTokens / modelProfile.maxTokens;
    const saturationPercentage = Number((saturationRatio * 100).toFixed(2));

    let degradationRisk = 'LOW';
    if (saturationRatio >= 0.90) {
      degradationRisk = 'CRITICAL';
    } else if (saturationRatio >= 0.70) {
      degradationRisk = 'HIGH';
    } else if (saturationRatio >= 0.45) {
      degradationRisk = 'MODERATE';
    }

    // Evaluate "lost in the middle" hazards for critical instructions
    const lostInMiddleWarnings = [];
    if (criticalInstructionPositions.length > 0 && totalChars > 0) {
      criticalInstructionPositions.forEach((pos, idx) => {
        const depth = pos / totalChars;
        if (depth >= modelProfile.middleLossStart && depth <= modelProfile.middleLossEnd) {
          lostInMiddleWarnings.push({
            instructionIndex: idx + 1,
            characterPosition: pos,
            relativeDepthPercentage: Number((depth * 100).toFixed(1)),
            warning: 'Critical instruction is located in the attention blind-spot (middle ' + (depth * 100).toFixed(0) + '% depth). Relocate to top or bottom of prompt.'
          });
        }
      });
    }

    const recommendations = [];
    if (degradationRisk === 'CRITICAL' || degradationRisk === 'HIGH') {
      recommendations.push('Execute AST token trimming to bring prompt under ' + modelProfile.sweetSpotTokens.toLocaleString() + ' tokens.');
    }
    if (lostInMiddleWarnings.length > 0) {
      recommendations.push('Relocate ' + lostInMiddleWarnings.length + ' critical instruction(s) out of the middle attention zone.');
    }
    if (recommendations.length === 0) {
      recommendations.push('Prompt is operating within optimal model attention boundaries.');
    }

    return {
      targetModel,
      promptMetrics: {
        totalChars,
        estimatedTokens: totalTokens,
        modelCapacityTokens: modelProfile.maxTokens,
        sweetSpotTokens: modelProfile.sweetSpotTokens
      },
      saturationPercentage,
      degradationRisk,
      lostInMiddleWarnings,
      recommendations,
      timestamp: new Date().toISOString()
    };
  }
}

module.exports = { ContextSaturationPredictor };
