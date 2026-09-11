/**
 * Context Window Token Bounded-Priority Skip List
 * Probabilistic multi-level skip list providing O(log N) search,
 * insertion, and deletion for dynamic token saliency ranking.
 */

class SkipNode {
  constructor(score, token, level) {
    this.score = score;
    this.token = token;
    this.forward = new Array(level + 1).fill(null);
  }
}

class SkipList {
  constructor(maxLevel = 4, p = 0.5) {
    this.maxLevel = maxLevel;
    this.p = p;
    this.level = 0;
    this.header = new SkipNode(-Infinity, null, maxLevel);
    this.size = 0;
  }

  randomLevel() {
    let lvl = 0;
    while (Math.random() < this.p && lvl < this.maxLevel) {
      lvl++;
    }
    return lvl;
  }

  insert(score, token) {
    const update = new Array(this.maxLevel + 1).fill(null);
    let current = this.header;

    for (let i = this.level; i >= 0; i--) {
      while (current.forward[i] && current.forward[i].score < score) {
        current = current.forward[i];
      }
      update[i] = current;
    }

    current = current.forward[0];

    if (current && current.score === score && current.token === token) {
      return; // Already present
    }

    const lvl = this.randomLevel();
    if (lvl > this.level) {
      for (let i = this.level + 1; i <= lvl; i++) {
        update[i] = this.header;
      }
      this.level = lvl;
    }

    const newNode = new SkipNode(score, token, lvl);
    for (let i = 0; i <= lvl; i++) {
      newNode.forward[i] = update[i].forward[i];
      update[i].forward[i] = newNode;
    }

    this.size++;
  }

  search(score) {
    let current = this.header;
    for (let i = this.level; i >= 0; i--) {
      while (current.forward[i] && current.forward[i].score < score) {
        current = current.forward[i];
      }
    }
    current = current.forward[0];
    return (current && current.score === score) ? current.token : null;
  }

  delete(score) {
    const update = new Array(this.maxLevel + 1).fill(null);
    let current = this.header;

    for (let i = this.level; i >= 0; i--) {
      while (current.forward[i] && current.forward[i].score < score) {
        current = current.forward[i];
      }
      update[i] = current;
    }

    current = current.forward[0];

    if (current && current.score === score) {
      for (let i = 0; i <= this.level; i++) {
        if (update[i].forward[i] !== current) break;
        update[i].forward[i] = current.forward[i];
      }

      while (this.level > 0 && this.header.forward[this.level] === null) {
        this.level--;
      }

      this.size--;
      return true;
    }
    return false;
  }
}

module.exports = { SkipList, SkipNode };
