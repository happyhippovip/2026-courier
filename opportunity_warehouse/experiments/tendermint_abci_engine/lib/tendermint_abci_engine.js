/**
 * Tendermint-ABCI Consensus Engine
 * Implements the Application Blockchain Interface (ABCI) separating consensus from state machine logic.
 * Methods: InitChain -> CheckTx -> BeginBlock -> DeliverTx -> EndBlock -> Commit.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class ABCIApplication {
  constructor() {
    this.state = {
      accounts: new Map(), // account -> balanceEur
      transactionLog: []
    };
    this.appHash = sha256('GENESIS_STATE');
    this.height = 0;
  }

  initChain(initialAccounts = {}) {
    for (const [acct, bal] of Object.entries(initialAccounts)) {
      this.state.accounts.set(acct, bal);
    }
    this.appHash = sha256(Object.fromEntries(this.state.accounts));
    return { code: 0, appHash: this.appHash };
  }

  checkTx(tx) {
    // Mempool validation: verify spend does not exceed autonomous limits
    if (tx.spendEur !== undefined && tx.spendEur > 0.00 && tx.type === 'AUTONOMOUS') {
      return { code: 1, log: 'AUTONOMOUS_SPEND_VIOLATION: Spend must be <= 0.00' };
    }
    return { code: 0, log: 'OK' };
  }

  beginBlock(height, proposer) {
    this.height = height;
    this.currentBlockTxs = [];
    return { code: 0 };
  }

  deliverTx(tx) {
    const check = this.checkTx(tx);
    if (check.code !== 0) return check;

    // Apply state change
    if (tx.type === 'COMMERCIAL_SETTLEMENT') {
      const current = this.state.accounts.get(tx.recipient) || 0;
      this.state.accounts.set(tx.recipient, current + tx.amountEur);
    }

    this.state.transactionLog.push(tx);
    this.currentBlockTxs.push(tx);
    return { code: 0, log: 'DELIVERED_SUCCESS' };
  }

  endBlock(height) {
    return { code: 0, validatorUpdates: [] };
  }

  commit() {
    this.appHash = sha256({
      height: this.height,
      accounts: Object.fromEntries(this.state.accounts),
      txCount: this.state.transactionLog.length
    });
    return { code: 0, data: this.appHash };
  }
}

class ABCIConsensusCoordinator {
  constructor(app) {
    this.app = app;
  }

  executeBlock(height, proposer, txs) {
    this.app.beginBlock(height, proposer);
    const deliverResults = [];
    for (const tx of txs) {
      deliverResults.push(this.app.deliverTx(tx));
    }
    this.app.endBlock(height);
    const commitRes = this.app.commit();
    return {
      height,
      proposer,
      appHash: commitRes.data,
      deliverResults
    };
  }
}

module.exports = { ABCIApplication, ABCIConsensusCoordinator };
