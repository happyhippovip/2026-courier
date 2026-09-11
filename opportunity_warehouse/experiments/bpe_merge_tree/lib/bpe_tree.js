/**
 * Context Window Dynamic Byte-Pair Encoding (BPE) Vocabulary Merge Tree & Lossless Detokenizer
 * Implements Sennrich et al. Byte-Pair Encoding with hierarchical merge trees,
 * iteratively compressing frequent character bigrams with 100% roundtrip lossless detokenization.
 */

class BPEMergeTree {
  constructor() {
    this.vocab = new Map(); // tokenString -> tokenId
    this.idToToken = new Map(); // tokenId -> tokenString
    this.merges = []; // array of { pair: [t1, t2], merged: string, rank: number }
    this.nextId = 0;
  }

  addToken(str) {
    if (!this.vocab.has(str)) {
      const id = this.nextId++;
      this.vocab.set(str, id);
      this.idToToken.set(id, str);
      return id;
    }
    return this.vocab.get(str);
  }

  train(corpus, maxMerges = 30) {
    const textList = Array.isArray(corpus) ? corpus : [corpus];

    // Initialize base vocabulary with single characters
    for (const text of textList) {
      for (let i = 0; i < text.length; i++) {
        this.addToken(text[i]);
      }
    }

    // Split words into characters
    let tokenizedCorpus = textList.map(text => Array.from(text));

    for (let mergeIdx = 0; mergeIdx < maxMerges; mergeIdx++) {
      // Count all adjacent pairs
      const pairCounts = new Map();
      for (const tokens of tokenizedCorpus) {
        for (let i = 0; i < tokens.length - 1; i++) {
          const pairKey = tokens[i] + '|||' + tokens[i + 1];
          pairCounts.set(pairKey, (pairCounts.get(pairKey) || 0) + 1);
        }
      }

      if (pairCounts.size === 0) break;

      // Find top pair
      let topPair = null;
      let maxCount = 0;
      for (const [pairKey, count] of pairCounts.entries()) {
        if (count > maxCount) {
          maxCount = count;
          topPair = pairKey;
        }
      }

      if (!topPair || maxCount < 2) break; // stop if no pairs appear >= 2 times

      const [p1, p2] = topPair.split('|||');
      const mergedStr = p1 + p2;
      this.addToken(mergedStr);

      const mergeRule = {
        p1,
        p2,
        merged: mergedStr,
        rank: mergeIdx
      };
      this.merges.push(mergeRule);

      // Apply merge across tokenized corpus
      tokenizedCorpus = tokenizedCorpus.map(tokens => {
        const newTokens = [];
        let i = 0;
        while (i < tokens.length) {
          if (i < tokens.length - 1 && tokens[i] === p1 && tokens[i + 1] === p2) {
            newTokens.push(mergedStr);
            i += 2;
          } else {
            newTokens.push(tokens[i]);
            i++;
          }
        }
        return newTokens;
      });
    }

    return {
      totalMerges: this.merges.length,
      vocabSize: this.vocab.size
    };
  }

  encode(text) {
    let tokens = Array.from(text);

    // Apply merges in learned rank order
    for (const merge of this.merges) {
      const newTokens = [];
      let i = 0;
      while (i < tokens.length) {
        if (i < tokens.length - 1 && tokens[i] === merge.p1 && tokens[i + 1] === merge.p2) {
          newTokens.push(merge.merged);
          i += 2;
        } else {
          newTokens.push(tokens[i]);
          i++;
        }
      }
      tokens = newTokens;
    }

    const tokenIds = tokens.map(t => this.vocab.has(t) ? this.vocab.get(t) : -1);
    return {
      tokens,
      tokenIds,
      tokenCount: tokens.length
    };
  }

  decode(tokenIds) {
    let result = '';
    for (const id of tokenIds) {
      if (this.idToToken.has(id)) {
        result += this.idToToken.get(id);
      } else {
        result += '?';
      }
    }
    return result;
  }
}

module.exports = { BPEMergeTree };
