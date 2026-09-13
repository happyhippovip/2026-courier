// Portfolio Layer — Strategic Balancing & Horizon Ranking
// Horizons: NOW (this week), 30D (this month), 365D (this year), ASYMMETRIC (extreme upside)
// Initial strategy categories:
// CASH NOW ~50%
// GROWTH ~35%
// MOONSHOTS ~15%
// (Defaults, not hard quotas)

const HORIZONS = Object.freeze({
  NOW: 'NOW',
  NOW_THIS_WEEK: 'NOW_THIS_WEEK',
  HORIZON_30D: '30D',
  NEXT_30_DAYS: 'NEXT_30_DAYS',
  HORIZON_365D: '365D',
  NEXT_365_DAYS: 'NEXT_365_DAYS',
  ASYMMETRIC: 'ASYMMETRIC'
});

const STRATEGY_CATEGORIES = Object.freeze({
  CASH_NOW: 'CASH_NOW',
  GROWTH: 'GROWTH',
  MOONSHOTS: 'MOONSHOTS'
});

class PortfolioManager {
  constructor(weights = null) {
    this.defaultWeights = weights || {
      [STRATEGY_CATEGORIES.CASH_NOW]: 0.50,
      [STRATEGY_CATEGORIES.GROWTH]: 0.35,
      [STRATEGY_CATEGORIES.MOONSHOTS]: 0.15
    };
  }

  getWeights() {
    return { ...this.defaultWeights };
  }

  suggestCategory(opp) {
    if (opp.category && Object.values(STRATEGY_CATEGORIES).includes(opp.category)) {
      return opp.category;
    }
    const horizon = opp.horizon || '30D';
    const timeToEuro = Number(opp.time_to_first_euro) || 30;
    const risk = Number(opp.risk_score) || 0.5;

    if (horizon === HORIZONS.ASYMMETRIC || risk >= 0.75) {
      return STRATEGY_CATEGORIES.MOONSHOTS;
    }
    if (horizon === HORIZONS.NOW || horizon === HORIZONS.NOW_THIS_WEEK || timeToEuro <= 7) {
      return STRATEGY_CATEGORIES.CASH_NOW;
    }
    return STRATEGY_CATEGORIES.GROWTH;
  }

  rankByHorizon(opportunities, horizon) {
    const isNow = (h) => h === 'NOW' || h === 'NOW_THIS_WEEK';
    const is30d = (h) => h === '30D' || h === 'NEXT_30_DAYS';
    const is365d = (h) => h === '365D' || h === 'NEXT_365_DAYS';
    const isAsym = (h) => h === 'ASYMMETRIC';

    return opportunities
      .filter(o => {
        if (isNow(horizon)) return isNow(o.horizon);
        if (is30d(horizon)) return is30d(o.horizon);
        if (is365d(horizon)) return is365d(o.horizon);
        if (isAsym(horizon)) return isAsym(o.horizon);
        return o.horizon === horizon;
      })
      .sort((a, b) => {
        const scoreA = (a.score && a.score.scalar_score) || 0;
        const scoreB = (b.score && b.score.scalar_score) || 0;
        return scoreB - scoreA;
      });
  }

  rankAllHorizons(opportunities) {
    const nowList = this.rankByHorizon(opportunities, HORIZONS.NOW);
    const list30 = this.rankByHorizon(opportunities, HORIZONS.HORIZON_30D);
    const list365 = this.rankByHorizon(opportunities, HORIZONS.HORIZON_365D);
    const asymList = this.rankByHorizon(opportunities, HORIZONS.ASYMMETRIC);

    return {
      [HORIZONS.NOW]: nowList,
      [HORIZONS.NOW_THIS_WEEK]: nowList,
      [HORIZONS.HORIZON_30D]: list30,
      [HORIZONS.NEXT_30_DAYS]: list30,
      [HORIZONS.HORIZON_365D]: list365,
      [HORIZONS.NEXT_365_DAYS]: list365,
      [HORIZONS.ASYMMETRIC]: asymList
    };
  }

  calculateAllocation(opportunities, totalAgentHoursCapacity = 100) {
    const buckets = {
      [STRATEGY_CATEGORIES.CASH_NOW]: [],
      [STRATEGY_CATEGORIES.GROWTH]: [],
      [STRATEGY_CATEGORIES.MOONSHOTS]: []
    };

    for (const opp of opportunities) {
      const cat = this.suggestCategory(opp);
      if (buckets[cat]) {
        buckets[cat].push(opp);
      }
    }

    // Sort descending by score
    for (const cat of Object.keys(buckets)) {
      buckets[cat].sort((a, b) => {
        const sa = (a.score && a.score.scalar_score) || 0;
        const sb = (b.score && b.score.scalar_score) || 0;
        return sb - sa;
      });
    }

    return {
      weights: this.getWeights(),
      total_capacity_hours: totalAgentHoursCapacity,
      allocations: {
        [STRATEGY_CATEGORIES.CASH_NOW]: {
          target_share: this.defaultWeights[STRATEGY_CATEGORIES.CASH_NOW],
          allocated_agent_hours: totalAgentHoursCapacity * this.defaultWeights[STRATEGY_CATEGORIES.CASH_NOW],
          count: buckets[STRATEGY_CATEGORIES.CASH_NOW].length,
          opportunities: buckets[STRATEGY_CATEGORIES.CASH_NOW]
        },
        [STRATEGY_CATEGORIES.GROWTH]: {
          target_share: this.defaultWeights[STRATEGY_CATEGORIES.GROWTH],
          allocated_agent_hours: totalAgentHoursCapacity * this.defaultWeights[STRATEGY_CATEGORIES.GROWTH],
          count: buckets[STRATEGY_CATEGORIES.GROWTH].length,
          opportunities: buckets[STRATEGY_CATEGORIES.GROWTH]
        },
        [STRATEGY_CATEGORIES.MOONSHOTS]: {
          target_share: this.defaultWeights[STRATEGY_CATEGORIES.MOONSHOTS],
          allocated_agent_hours: totalAgentHoursCapacity * this.defaultWeights[STRATEGY_CATEGORIES.MOONSHOTS],
          count: buckets[STRATEGY_CATEGORIES.MOONSHOTS].length,
          opportunities: buckets[STRATEGY_CATEGORIES.MOONSHOTS]
        }
      }
    };
  }

  allocateBudget(warehouseOrOpportunities, budgetEur = 0) {
    const opps = Array.isArray(warehouseOrOpportunities)
      ? warehouseOrOpportunities
      : (warehouseOrOpportunities.getAllOpportunities ? warehouseOrOpportunities.getAllOpportunities() : []);

    const ranked = this.rankAllHorizons(opps);
    return ranked;
  }
}

module.exports = {
  HORIZONS,
  STRATEGY_CATEGORIES,
  PortfolioManager
};
