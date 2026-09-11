/**
 * Context Window Token Dynamic Bounded Fast Succinct Persistent Suffix Automaton Equivalence Filter
 * Implements a directed acyclic word graph (DAWG) over token sequences,
 * providing O(|pattern|) exact substring search and sequence factor counting in O(N) space.
 */

class SAMState {
  constructor(len = 0, link = -1) {
    this.len = len;
    this.link = link;
    this.next = new Map(); // char -> stateIndex
    this.firstPos = -1;
  }
}

class PersistentSuffixAutomatonFilter {
  constructor() {
    this.states = [];
    this.sz = 0;
    this.last = 0;
    this._init();
  }

  _init() {
    this.states = [new SAMState(0, -1)];
    this.sz = 1;
    this.last = 0;
  }

  extend(c, idx) {
    const cur = this.sz++;
    this.states.push(new SAMState(this.states[this.last].len + 1, -1));
    this.states[cur].firstPos = idx;

    let p = this.last;
    while (p !== -1 && !this.states[p].next.has(c)) {
      this.states[p].next.set(c, cur);
      p = this.states[p].link;
    }

    if (p === -1) {
      this.states[cur].link = 0;
    } else {
      const q = this.states[p].next.get(c);
      if (this.states[p].len + 1 === this.states[q].len) {
        this.states[cur].link = q;
      } else {
        const clone = this.sz++;
        const cloneState = new SAMState(this.states[p].len + 1, this.states[q].link);
        cloneState.next = new Map(this.states[q].next);
        cloneState.firstPos = this.states[q].firstPos;
        this.states.push(cloneState);

        while (p !== -1 && this.states[p].next.get(c) === q) {
          this.states[p].next.set(c, clone);
          p = this.states[p].link;
        }
        this.states[q].link = clone;
        this.states[cur].link = clone;
      }
    }
    this.last = cur;
  }

  build(text) {
    this._init();
    for (let i = 0; i < text.length; i++) {
      this.extend(text[i], i);
    }
  }

  contains(pattern) {
    let curr = 0;
    for (let i = 0; i < pattern.length; i++) {
      const c = pattern[i];
      if (!this.states[curr].next.has(c)) return false;
      curr = this.states[curr].next.get(c);
    }
    return true;
  }

  findFirstOccurrence(pattern) {
    let curr = 0;
    for (let i = 0; i < pattern.length; i++) {
      const c = pattern[i];
      if (!this.states[curr].next.has(c)) return -1;
      curr = this.states[curr].next.get(c);
    }
    return this.states[curr].firstPos - pattern.length + 1;
  }

  countDistinctSubstrings() {
    let total = 0;
    for (let i = 1; i < this.sz; i++) {
      total += this.states[i].len - this.states[this.states[i].link].len;
    }
    return total;
  }

  getMetrics() {
    return {
      totalStates: this.sz,
      distinctSubstrings: this.countDistinctSubstrings(),
      complexity: 'O(|P|)_QUERY_TIME_O_N_SPACE',
      automatonModel: 'MINIMAL_TRANSITION_DAWG'
    };
  }
}

module.exports = { SAMState, PersistentSuffixAutomatonFilter };
