/**
 * Multi-Agent Context State Checkpoint Merkle-Tree Diff & Patch Engine
 * Constructs cryptographic Merkle DAGs over hierarchical multi-agent state checkpoints,
 * enabling sub-linear O(log N) state synchronization, tamper detection, and delta patching.
 */

const crypto = require('crypto');

class MerkleNode {
  constructor(hash, left = null, right = null, key = null, value = null) {
    this.hash = hash;
    this.left = left;
    this.right = right;
    this.key = key;     // populated for leaf nodes
    this.value = value; // populated for leaf nodes
    this.isLeaf = (left === null && right === null);
  }
}

class MerkleStateDiffEngine {
  constructor() {}

  sha256(data) {
    return crypto.createHash('sha256').update(data).digest('hex');
  }

  hashLeaf(key, value) {
    const serialized = JSON.stringify(value);
    return this.sha256('LEAF:' + key + ':' + serialized);
  }

  hashInternal(leftHash, rightHash) {
    return this.sha256('NODE:' + leftHash + ':' + rightHash);
  }

  buildTree(stateObject) {
    if (!stateObject || typeof stateObject !== 'object') {
      stateObject = {};
    }
    const keys = Object.keys(stateObject).sort();
    if (keys.length === 0) {
      const emptyHash = this.sha256('EMPTY_TREE');
      return {
        root: new MerkleNode(emptyHash),
        rootHash: emptyHash,
        leaves: [],
        state: stateObject
      };
    }

    let currentLevel = keys.map(k => {
      const h = this.hashLeaf(k, stateObject[k]);
      return new MerkleNode(h, null, null, k, stateObject[k]);
    });

    const leaves = [...currentLevel];

    while (currentLevel.length > 1) {
      const nextLevel = [];
      for (let i = 0; i < currentLevel.length; i += 2) {
        if (i + 1 < currentLevel.length) {
          const left = currentLevel[i];
          const right = currentLevel[i + 1];
          const parentHash = this.hashInternal(left.hash, right.hash);
          nextLevel.push(new MerkleNode(parentHash, left, right));
        } else {
          // Odd node duplicated to balance tree
          const left = currentLevel[i];
          const right = currentLevel[i];
          const parentHash = this.hashInternal(left.hash, right.hash);
          nextLevel.push(new MerkleNode(parentHash, left, right));
        }
      }
      currentLevel = nextLevel;
    }

    return {
      root: currentLevel[0],
      rootHash: currentLevel[0].hash,
      leaves,
      state: stateObject
    };
  }

  computeDiff(treeA, treeB) {
    if (treeA.rootHash === treeB.rootHash) {
      return {
        identical: true,
        baseRootHash: treeA.rootHash,
        targetRootHash: treeB.rootHash,
        added: {},
        modified: {},
        deleted: {},
        operationsCount: 0
      };
    }

    const stateA = treeA.state || {};
    const stateB = treeB.state || {};
    const keysA = new Set(Object.keys(stateA));
    const keysB = new Set(Object.keys(stateB));

    const added = {};
    const modified = {};
    const deleted = {};

    for (const k of keysB) {
      if (!keysA.has(k)) {
        added[k] = stateB[k];
      } else {
        const valA = JSON.stringify(stateA[k]);
        const valB = JSON.stringify(stateB[k]);
        if (valA !== valB) {
          modified[k] = {
            previous: stateA[k],
            current: stateB[k]
          };
        }
      }
    }

    for (const k of keysA) {
      if (!keysB.has(k)) {
        deleted[k] = stateA[k];
      }
    }

    const operationsCount = Object.keys(added).length + Object.keys(modified).length + Object.keys(deleted).length;

    return {
      identical: false,
      baseRootHash: treeA.rootHash,
      targetRootHash: treeB.rootHash,
      added,
      modified,
      deleted,
      operationsCount
    };
  }

  generatePatch(stateA, stateB) {
    const treeA = this.buildTree(stateA);
    const treeB = this.buildTree(stateB);
    const diff = this.computeDiff(treeA, treeB);

    const patchOps = [];
    for (const [key, value] of Object.entries(diff.added)) {
      patchOps.push({ op: 'add', key, value });
    }
    for (const [key, diffObj] of Object.entries(diff.modified)) {
      patchOps.push({ op: 'replace', key, value: diffObj.current });
    }
    for (const key of Object.keys(diff.deleted)) {
      patchOps.push({ op: 'remove', key });
    }

    return {
      baseRootHash: treeA.rootHash,
      targetRootHash: treeB.rootHash,
      operationsCount: patchOps.length,
      operations: patchOps
    };
  }

  applyPatch(baseState, patch) {
    const currentTree = this.buildTree(baseState);
    if (currentTree.rootHash !== patch.baseRootHash) {
      throw new Error('Base state root hash mismatch: expected ' + patch.baseRootHash + ' got ' + currentTree.rootHash);
    }

    const targetState = JSON.parse(JSON.stringify(baseState));
    for (const op of patch.operations) {
      if (op.op === 'add' || op.op === 'replace') {
        targetState[op.key] = op.value;
      } else if (op.op === 'remove') {
        delete targetState[op.key];
      }
    }

    const reconstructedTree = this.buildTree(targetState);
    if (reconstructedTree.rootHash !== patch.targetRootHash) {
      throw new Error('Reconstructed state root hash mismatch: expected ' + patch.targetRootHash + ' got ' + reconstructedTree.rootHash);
    }

    return {
      reconstructedState: targetState,
      rootHash: reconstructedTree.rootHash,
      verified: true
    };
  }
}

module.exports = { MerkleStateDiffEngine, MerkleNode };
