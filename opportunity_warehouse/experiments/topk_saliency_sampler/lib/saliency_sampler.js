/**
 * Context Window Streaming Token Bounded Priority Queue & Top-K Saliency Sampler
 * Implements a bounded Min-Heap priority queue maintaining the Top-K salient context items,
 * streaming continuous token chunks in O(N log K) time while guaranteeing pinned invariants are never evicted.
 */

class TopKSaliencySampler {
  constructor(k = 5) {
    this.k = k;
    this.heap = []; // Min-heap of { id, text, saliency, effectiveSaliency, sequenceIndex, pinned }
    this.nextSeq = 0;
    this.totalIngested = 0;
    this.totalEvicted = 0;
  }

  getEffectiveSaliency(item) {
    return item.pinned ? Infinity : (item.saliency || 0);
  }

  bubbleUp(index) {
    while (index > 0) {
      const parentIdx = Math.floor((index - 1) / 2);
      if (this.heap[index].effectiveSaliency < this.heap[parentIdx].effectiveSaliency) {
        // Swap
        const temp = this.heap[index];
        this.heap[index] = this.heap[parentIdx];
        this.heap[parentIdx] = temp;
        index = parentIdx;
      } else {
        break;
      }
    }
  }

  siftDown(index) {
    const len = this.heap.length;
    while (true) {
      let smallest = index;
      const left = 2 * index + 1;
      const right = 2 * index + 2;

      if (left < len && this.heap[left].effectiveSaliency < this.heap[smallest].effectiveSaliency) {
        smallest = left;
      }
      if (right < len && this.heap[right].effectiveSaliency < this.heap[smallest].effectiveSaliency) {
        smallest = right;
      }

      if (smallest !== index) {
        const temp = this.heap[index];
        this.heap[index] = this.heap[smallest];
        this.heap[smallest] = temp;
        index = smallest;
      } else {
        break;
      }
    }
  }

  insert(id, text, saliency = 1.0, pinned = false) {
    this.totalIngested++;
    const item = {
      id,
      text,
      saliency,
      effectiveSaliency: pinned ? Infinity : saliency,
      sequenceIndex: this.nextSeq++,
      pinned
    };

    if (this.heap.length < this.k) {
      this.heap.push(item);
      this.bubbleUp(this.heap.length - 1);
      return { retained: true, evictedItem: null };
    }

    // If candidate has strictly higher saliency than minimum in heap
    if (item.effectiveSaliency > this.heap[0].effectiveSaliency) {
      const evicted = this.heap[0];
      this.totalEvicted++;
      this.heap[0] = item;
      this.siftDown(0);
      return { retained: true, evictedItem: evicted };
    } else {
      this.totalEvicted++;
      return { retained: false, evictedItem: item };
    }
  }

  getRetained(sortMode = 'CHRONOLOGICAL') {
    const copy = [...this.heap];
    if (sortMode === 'CHRONOLOGICAL') {
      return copy.sort((a, b) => a.sequenceIndex - b.sequenceIndex);
    } else {
      return copy.sort((a, b) => b.effectiveSaliency - a.effectiveSaliency);
    }
  }

  getStats() {
    return {
      capacityK: this.k,
      retainedCount: this.heap.length,
      totalIngested: this.totalIngested,
      totalEvicted: this.totalEvicted,
      minSaliencyRetained: this.heap.length > 0 ? this.heap[0].saliency : 0
    };
  }
}

module.exports = { TopKSaliencySampler };
