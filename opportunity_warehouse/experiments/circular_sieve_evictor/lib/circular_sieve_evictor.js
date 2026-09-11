/**
 * Adaptive Token Context Window Circular Sieve & Sliding Evictor
 * Implements SIEVE / Second-Chance eviction over a circular buffer
 * with invariant token pinning and amortized O(1) eviction complexity.
 */

class CircularSieveEvictor {
  constructor(capacity = 5) {
    this.capacity = capacity;
    this.entries = []; // Array of { key, data, visited: boolean, pinned: boolean }
    this.hand = 0;
  }

  get(key) {
    const entry = this.entries.find(e => e.key === key);
    if (entry) {
      entry.visited = true;
      return entry.data;
    }
    return null;
  }

  put(key, data, pinned = false) {
    const existing = this.entries.find(e => e.key === key);
    if (existing) {
      existing.data = data;
      existing.visited = true;
      existing.pinned = existing.pinned || pinned;
      return;
    }

    if (this.entries.length >= this.capacity) {
      this.evict();
    }

    this.entries.push({ key, data, visited: false, pinned });
  }

  evict() {
    let checked = 0;
    const n = this.entries.length;

    while (checked < n * 2) {
      const idx = this.hand % n;
      const entry = this.entries[idx];

      if (entry.pinned) {
        // Skip pinned entry
        this.hand++;
        checked++;
        continue;
      }

      if (entry.visited) {
        // Second chance: clear visited bit
        entry.visited = false;
        this.hand++;
        checked++;
      } else {
        // Evict unvisited unpinned entry
        this.entries.splice(idx, 1);
        return entry;
      }
    }

    // Fallback: evict first unpinned entry
    const unpinnedIdx = this.entries.findIndex(e => !e.pinned);
    if (unpinnedIdx !== -1) {
      return this.entries.splice(unpinnedIdx, 1)[0];
    }
    return null;
  }

  size() {
    return this.entries.length;
  }
}

module.exports = { CircularSieveEvictor };
