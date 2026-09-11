/**
 * shingle_similarity.js - Semantic Prompt Redundancy Index & Shingle Similarity Measurer
 * Computes k-shingle Jaccard coefficients to detect near-duplicate paragraphs and prompt instructions.
 */
class PromptShingleSimilarity {
  constructor(options = {}) {
    this.k = options.k || 3; // 3-word shingles by default
    this.similarityThreshold = options.similarityThreshold || 0.70;
  }

  getWords(text) {
    if (!text || typeof text !== 'string') return [];
    return text.toLowerCase().replace(/[^a-z0-9_\s]/g, ' ').split(/\s+/).filter(w => w.length > 0);
  }

  generateShingles(text) {
    const words = this.getWords(text);
    const shingles = new Set();
    if (words.length < this.k) {
      if (words.length > 0) shingles.add(words.join(' '));
      return shingles;
    }

    for (let i = 0; i <= words.length - this.k; i++) {
      const shingle = words.slice(i, i + this.k).join(' ');
      shingles.add(shingle);
    }
    return shingles;
  }

  calculateJaccard(setA, setB) {
    if (!setA || !setB || setA.size === 0 || setB.size === 0) return 0.0;
    let intersection = 0;
    for (const item of setA) {
      if (setB.has(item)) intersection++;
    }
    const union = setA.size + setB.size - intersection;
    return Number((intersection / union).toFixed(3));
  }

  analyzeParagraphs(promptText) {
    if (!promptText || typeof promptText !== 'string') {
      return { totalParagraphs: 0, redundancyPairs: [], recommendedDeduplications: [] };
    }

    const rawParagraphs = promptText.split(/\n\s*\n/).map(p => p.trim()).filter(p => p.length > 20);
    const shinglesList = rawParagraphs.map((p, idx) => ({
      index: idx,
      preview: p.slice(0, 60) + '...',
      shingles: this.generateShingles(p),
      length: p.length
    }));

    const redundancyPairs = [];
    for (let i = 0; i < shinglesList.length; i++) {
      for (let j = i + 1; j < shinglesList.length; j++) {
        const sim = this.calculateJaccard(shinglesList[i].shingles, shinglesList[j].shingles);
        if (sim >= this.similarityThreshold) {
          redundancyPairs.push({
            paragraphA: { index: i, preview: shinglesList[i].preview },
            paragraphB: { index: j, preview: shinglesList[j].preview },
            jaccardSimilarity: sim,
            isRedundant: true
          });
        }
      }
    }

    return {
      totalParagraphs: rawParagraphs.length,
      redundancyCount: redundancyPairs.length,
      redundancyPairs,
      recommendedDeduplications: redundancyPairs.map(r => ({
        action: 'Deduplicate paragraph ' + r.paragraphB.index + ' with reference to paragraph ' + r.paragraphA.index,
        similarity: r.jaccardSimilarity
      })),
      timestamp: new Date().toISOString()
    };
  }
}

module.exports = { PromptShingleSimilarity };
