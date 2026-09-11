/**
 * Corda-Style Notary Service Consensus Engine
 * Implements UTXO-model double-spend prevention and conflict resolution for multi-agent workflows.
 * Before an agent consumes a state ref (e.g. allocating a token budget or claiming an order),
 * a distributed notary cluster signs off that the input state has not been consumed previously.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class StateRef {
  constructor(txId, index) {
    this.txId = txId;
    this.index = index;
    this.key = `${txId}:${index}`;
  }
}

class NotaryTransaction {
  constructor(inputs, outputs, command, consumingAgent) {
    this.inputs = inputs || []; // Array of StateRef
    this.outputs = outputs || []; // Array of output objects
    this.command = command;
    this.consumingAgent = consumingAgent;
    this.txId = sha256({
      inputs: this.inputs.map(i => i.key).sort(),
      outputs: this.outputs,
      command: this.command,
      consumingAgent: this.consumingAgent
    });
  }
}

class CordaNotaryConsensus {
  constructor(notaryNodes, faultTolerance) {
    this.notaryNodes = notaryNodes; // ['notary_0', 'notary_1', 'notary_2']
    this.n = notaryNodes.length;
    this.f = faultTolerance || Math.floor((this.n - 1) / 3);
    this.quorum = 2 * this.f + 1;

    // Committed states: stateKey -> { consumingTxId, consumingAgent, timestamp }
    this.spentStates = new Map();
    // Notarized transaction ledger: txId -> { tx, signatures }
    this.notarizedLedger = new Map();
  }

  notarizeTransaction(tx) {
    // Check for double spends among input states
    for (const input of tx.inputs) {
      if (this.spentStates.has(input.key)) {
        const previousSpend = this.spentStates.get(input.key);
        throw new Error(`DOUBLE_SPEND_DETECTED: State ${input.key} was already consumed by transaction ${previousSpend.consumingTxId}`);
      }
    }

    // Collect quorum notary signatures
    const signatures = {};
    for (let i = 0; i < this.quorum; i++) {
      const notary = this.notaryNodes[i];
      signatures[notary] = sha256(`${notary}_notarize_${tx.txId}`);
    }

    // Atomically mark inputs as spent
    const now = new Date().toISOString();
    for (const input of tx.inputs) {
      this.spentStates.set(input.key, {
        consumingTxId: tx.txId,
        consumingAgent: tx.consumingAgent,
        timestamp: now
      });
    }

    const record = {
      txId: tx.txId,
      tx,
      signatures,
      notarizedAt: now
    };

    this.notarizedLedger.set(tx.txId, record);
    return record;
  }

  isStateSpent(stateKey) {
    return this.spentStates.has(stateKey);
  }

  getSpentStateDetails(stateKey) {
    return this.spentStates.get(stateKey) || null;
  }
}

module.exports = { CordaNotaryConsensus, NotaryTransaction, StateRef };
