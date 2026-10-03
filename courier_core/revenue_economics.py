from dataclasses import dataclass

@dataclass
class UnitEconomics:
    total_cost_usd: float
    total_revenue_usd: float

    @property
    def gross_margin_usd(self) -> float:
        return self.total_revenue_usd - self.total_cost_usd

    @property
    def gross_margin_percent(self) -> float:
        if self.total_revenue_usd <= 0:
            return 0.0
        return (self.gross_margin_usd / self.total_revenue_usd) * 100.0

class RevenueCalculator:
    """MAC-15: Compute cost/revenue/margin primitives without making purchases."""
    @staticmethod
    def calculate_economics(cost: float, revenue: float) -> UnitEconomics:
        if cost < 0 or revenue < 0:
            raise ValueError("Cost and revenue must be non-negative.")
        return UnitEconomics(total_cost_usd=cost, total_revenue_usd=revenue)
