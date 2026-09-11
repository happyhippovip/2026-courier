/**
 * Byzantine Dynamic Epoch Gas Token Auction Consensus Engine
 * Executes a uniform-price batch auction at epoch boundaries to allocate
 * block space and compute quotas to autonomous agent swarms with 2f+1 quorum finality.
 */

const crypto = require('crypto');

function sha256(data) {
  return crypto.createHash('sha256').update(typeof data === 'string' ? data : JSON.stringify(data)).digest('hex');
}

class BFTEpochGasAuctionEngine {
  constructor(nodeId, totalCapacity = 1000) {
    this.nodeId = nodeId;
    this.totalCapacity = totalCapacity; // total gas units per epoch
    this.bids = []; // array of { bidderId, gasUnits, maxPrice }
    this.clearedAuctions = [];
  }

  submitBid(bidderId, gasUnits, maxPrice) {
    if (gasUnits <= 0 || maxPrice <= 0) throw new Error('Invalid bid parameters');
    const bid = {
      bidderId,
      gasUnits,
      maxPrice,
      timestamp: Date.now()
    };
    bid.hash = sha256(bid);
    this.bids.push(bid);
    return bid;
  }

  resolveAuction(epoch) {
    // Sort bids descending by maxPrice
    const sortedBids = [...this.bids].sort((a, b) => b.maxPrice - a.maxPrice);

    let allocatedGas = 0;
    let clearingPrice = 0;
    const winningAllocations = [];

    for (const bid of sortedBids) {
      if (allocatedGas + bid.gasUnits <= this.totalCapacity) {
        allocatedGas += bid.gasUnits;
        winningAllocations.push({
          bidderId: bid.bidderId,
          allocatedGas: bid.gasUnits,
          bidPrice: bid.maxPrice
        });
        clearingPrice = bid.maxPrice; // uniform clearing price set by marginal winner
      } else {
        const remaining = this.totalCapacity - allocatedGas;
        if (remaining > 0) {
          allocatedGas += remaining;
          winningAllocations.push({
            bidderId: bid.bidderId,
            allocatedGas: remaining,
            bidPrice: bid.maxPrice
          });
          clearingPrice = bid.maxPrice;
        }
        break;
      }
    }

    const auctionResult = {
      epoch,
      totalCapacity: this.totalCapacity,
      allocatedGas,
      clearingPrice,
      allocations: winningAllocations,
      timestamp: Date.now()
    };
    auctionResult.hash = sha256(auctionResult);
    return auctionResult;
  }

  certifyAuction(auctionResult, signatures, quorumThreshold = 3) {
    const validSigners = new Set();

    for (const sig of signatures) {
      const expected = sha256(`${sig.nodeId}:${auctionResult.hash}:${auctionResult.epoch}`);
      if (sig.signature === expected) {
        validSigners.add(sig.nodeId);
      }
    }

    if (validSigners.size < quorumThreshold) {
      return { certified: false, validSigners: validSigners.size, required: quorumThreshold };
    }

    const certifiedRecord = {
      auctionResult,
      quorumCert: {
        signers: Array.from(validSigners),
        count: validSigners.size
      },
      certifiedAt: Date.now()
    };

    this.clearedAuctions.push(certifiedRecord);
    this.bids = []; // reset for next epoch

    return { certified: true, certifiedRecord };
  }
}

module.exports = { BFTEpochGasAuctionEngine };
