"""Slippage Analytics service for calculating and analyzing slippage and price impact."""

import logging
from typing import Any, Dict, List

from ..models.route_comparison import RouteComparison
from ..models.trade_request import TradeRequest

logger = logging.getLogger(__name__)


class SlippageAnalyticsService:
    """Service for analyzing slippage and price impact across trade routes."""

    def __init__(self):
        pass

    def analyze_route_comparisons(
        self,
        routes: List[RouteComparison],
        trade_request: TradeRequest,
    ) -> Dict[str, Any]:
        """Analyze a list of route comparisons and provide insights.

        Args:
            routes: List of RouteComparison objects from different DEXs.
            trade_request: The original trade request.

        Returns:
            A dictionary containing analysis results.
        """
        if not routes:
            return {
                "best_route": None,
                "worst_route": None,
                "average_slippage": 0.0,
                "price_impact_range": (0.0, 0.0),
                "recommendation": "No routes available",
            }

        # Sort by slippage estimate (ascending)
        sorted_routes = sorted(routes, key=lambda r: r.slippage_estimate)
        best_route = sorted_routes[0]
        worst_route = sorted_routes[-1]

        # Calculate averages
        avg_slippage = sum(r.slippage_estimate for r in routes) / len(routes)
        avg_price_impact = sum(r.price_impact_pct for r in routes) / len(routes)
        avg_fill_probability = sum(r.fill_probability for r in routes) / len(routes)

        # Determine price impact range
        price_impacts = [r.price_impact_pct for r in routes]
        min_price_impact = min(price_impacts)
        max_price_impact = max(price_impacts)

        # Generate a recommendation
        recommendation = self._generate_recommendation(best_route, trade_request)

        return {
            "best_route": best_route,
            "worst_route": worst_route,
            "average_slippage": avg_slippage,
            "average_price_impact": avg_price_impact,
            "average_fill_probability": avg_fill_probability,
            "price_impact_range": (min_price_impact, max_price_impact),
            "slippage_range": (
                min(r.slippage_estimate for r in routes),
                max(r.slippage_estimate for r in routes),
            ),
            "recommendation": recommendation,
            "route_count": len(routes),
        }

    def _generate_recommendation(
        self, best_route: RouteComparison, trade_request: TradeRequest
    ) -> str:
        """Generate a human-readable recommendation based on the best route.

        Args:
            best_route: The route with the lowest slippage.
            trade_request: The original trade request.

        Returns:
            A recommendation string.
        """
        intent = trade_request.intent.lower()
        if intent == "low_slippage":
            return (
                f"For low slippage, use {best_route.dex_name} with expected slippage of "
                f"{best_route.slippage_estimate:.2f}% and price impact of {best_route.price_impact_pct:.2f}%."
            )
        elif intent == "fast_execution":
            # We might want to consider gas estimate or fill probability for speed
            return (
                f"For fast execution, consider {best_route.dex_name} with high fill probability of "
                f"{best_route.fill_probability:.0%} and estimated gas of {best_route.gas_estimate:.4f} SOL."
            )
        else:  # best_output or default
            return (
                f"For best output, {best_route.dex_name} offers the highest expected output with "
                f"{best_route.fill_probability:.0%} fill probability and {best_route.slippage_estimate:.2f}% slippage."
            )

    def calculate_price_impact(
        self, expected_price: float, actual_price: float
    ) -> float:
        """Calculate price impact percentage.

        Args:
            expected_price: The expected price before the trade.
            actual_price: The actual price after the trade.

        Returns:
            Price impact as a percentage (can be negative).
        """
        if expected_price == 0:
            return 0.0
        return ((actual_price - expected_price) / expected_price) * 100

    def calculate_slippage(
        self, expected_output: float, actual_output: float
    ) -> float:
        """Calculate slippage percentage.

        Args:
            expected_output: The expected output amount.
            actual_output: The actual output amount received.

        Returns:
            Slippage as a percentage (positive if worse than expected).
        """
        if expected_output == 0:
            return 0.0
        return ((expected_output - actual_output) / expected_output) * 100

    def assess_route_quality(self, route: RouteComparison) -> str:
        """Assess the quality of a route based on its metrics.

        Args:
            route: A RouteComparison object.

        Returns:
            A qualitative assessment (e.g., "Excellent", "Good", "Fair", "Poor").
        """
        # We can define thresholds for slippage, price impact, and fill probability
        slippage_thresholds = [(0.1, "Excellent"), (0.5, "Good"), (1.0, "Fair"), (float("inf"), "Poor")]
        impact_thresholds = [(0.1, "Excellent"), (0.5, "Good"), (1.0, "Fair"), (float("inf"), "Poor")]
        fill_thresholds = [(0.95, "Excellent"), (0.9, "Good"), (0.8, "Fair"), (0.0, "Poor")]

        # Determine the worst category among the three
        slippage_quality = "Poor"
        for threshold, label in slippage_thresholds:
            if route.slippage_estimate <= threshold:
                slippage_quality = label
                break

        impact_quality = "Poor"
        for threshold, label in impact_thresholds:
            if route.price_impact_pct <= threshold:
                impact_quality = label
                break

        fill_quality = "Poor"
        for threshold, label in fill_thresholds:
            if route.fill_probability >= threshold:
                fill_quality = label
                break

        # Return the worst of the three (since we want to be conservative)
        qualities = [slippage_quality, impact_quality, fill_quality]
        if "Poor" in qualities:
            return "Poor"
        if "Fair" in qualities:
            return "Fair"
        if "Good" in qualities:
            return "Good"
        return "Excellent"


# Example usage
if __name__ == "__main__":
    # This is just for demonstration; in practice, the service is used by other components.
    service = SlippageAnalyticsService()
    print("SlippageAnalyticsService initialized.")
