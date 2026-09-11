/**
 * Multi-Tenant Context Window Token Auction & Vickrey-Clarke-Groves (VCG) Mechanism
 * Implements a truthful, incentive-compatible combinatorial auction for scarce context window slots,
 * computing social-welfare maximizing allocations and externality payments that eliminate bidding manipulation.
 */

class VCGTokenAuction {
  constructor(totalTokenCapacity = 1000) {
    this.capacity = totalTokenCapacity;
  }

  // Solves 0-1 knapsack to find allocation maximizing total valuation
  solveOptimalAllocation(bids, capacity = this.capacity) {
    const n = bids.length;
    // DP table: dp[i][w] = max value using subset of first i bids with capacity w
    // To handle general token capacities efficiently, we use a standard bounded knapsack solver
    const dp = Array.from({ length: n + 1 }, () => new Array(capacity + 1).fill(0));

    for (let i = 1; i <= n; i++) {
      const b = bids[i - 1];
      const cost = b.tokensRequested;
      const val = b.bidValue;

      for (let w = 0; w <= capacity; w++) {
        if (cost <= w) {
          dp[i][w] = Math.max(dp[i - 1][w], dp[i - 1][w - cost] + val);
        } else {
          dp[i][w] = dp[i - 1][w];
        }
      }
    }

    // Backtrack to find selected bids
    let w = capacity;
    const selected = [];
    for (let i = n; i >= 1; i--) {
      if (dp[i][w] !== dp[i - 1][w]) {
        selected.push(bids[i - 1]);
        w -= bids[i - 1].tokensRequested;
      }
    }

    selected.reverse();
    const totalWelfare = dp[n][capacity];
    const totalTokensAllocated = selected.reduce((sum, b) => sum + b.tokensRequested, 0);

    return {
      selected,
      totalWelfare,
      totalTokensAllocated,
      remainingCapacity: capacity - totalTokensAllocated
    };
  }

  // Computes VCG allocations and externality payments
  runAuction(bids) {
    const optimal = this.solveOptimalAllocation(bids, this.capacity);
    const winners = optimal.selected;
    const winnerIds = new Set(winners.map(w => w.agentId));

    const results = [];

    for (const winner of winners) {
      // 1. Social welfare of other winners in optimal allocation
      const welfareOthersOptimal = winners
        .filter(w => w.agentId !== winner.agentId)
        .reduce((sum, w) => sum + w.bidValue, 0);

      // 2. Solve optimal allocation without winner i
      const bidsWithoutI = bids.filter(b => b.agentId !== winner.agentId);
      const optimalWithoutI = this.solveOptimalAllocation(bidsWithoutI, this.capacity);
      const welfareWithoutI = optimalWithoutI.totalWelfare;

      // 3. VCG externality payment: welfareWithoutI - welfareOthersOptimal
      const payment = Math.max(0, welfareWithoutI - welfareOthersOptimal);
      const netUtility = winner.bidValue - payment;

      results.push({
        agentId: winner.agentId,
        won: true,
        tokensAllocated: winner.tokensRequested,
        bidValue: winner.bidValue,
        vcgPayment: Number(payment.toFixed(2)),
        netUtility: Number(netUtility.toFixed(2))
      });
    }

    // Add losers
    for (const b of bids) {
      if (!winnerIds.has(b.agentId)) {
        results.push({
          agentId: b.agentId,
          won: false,
          tokensAllocated: 0,
          bidValue: b.bidValue,
          vcgPayment: 0,
          netUtility: 0
        });
      }
    }

    return {
      capacity: this.capacity,
      totalWelfare: optimal.totalWelfare,
      totalTokensAllocated: optimal.totalTokensAllocated,
      allocations: results
    };
  }
}

module.exports = { VCGTokenAuction };
