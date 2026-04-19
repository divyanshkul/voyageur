"""Price comparison engine (Phase 4a).

Compares OTA prices against direct-call prices for each hotel, computes
savings amounts and percentages, and sorts results by best deal first.
"""

import logging

from app.models import CallResult, HotelComparison

logger = logging.getLogger(__name__)


def compare_prices(call_results: list[CallResult]) -> list[HotelComparison]:
    """Compare OTA vs direct prices for each call result.

    Returns a sorted list of HotelComparison objects:
      1. Available + cheaper first
      2. Available + unknown verdict
      3. Unavailable at bottom
    """
    comparisons: list[HotelComparison] = []
    valid_count = 0
    best_savings: float | None = None

    for cr in call_results:
        ota_price = cr.hotel.ota_price
        direct_price = cr.direct_price

        if cr.status != "completed":
            # Incomplete call -- cannot compare
            comparison = HotelComparison(
                hotel=cr.hotel,
                call_result=cr,
                ota_price=ota_price,
                direct_price=direct_price,
                savings_amount=None,
                savings_percent=None,
                verdict="unknown",
            )
        elif direct_price is not None and ota_price is not None:
            # Both prices available -- full comparison
            savings_amount = ota_price - direct_price
            savings_percent = round((savings_amount / ota_price) * 100, 1) if ota_price != 0 else 0.0

            if savings_amount > 0:
                verdict = "cheaper"
            elif savings_amount == 0:
                verdict = "same"
            else:
                verdict = "more_expensive"

            comparison = HotelComparison(
                hotel=cr.hotel,
                call_result=cr,
                ota_price=ota_price,
                direct_price=direct_price,
                savings_amount=savings_amount,
                savings_percent=savings_percent,
                verdict=verdict,
            )
            valid_count += 1

            if best_savings is None or savings_percent > best_savings:
                best_savings = savings_percent
        else:
            # Only one price (or neither) -- cannot determine verdict
            comparison = HotelComparison(
                hotel=cr.hotel,
                call_result=cr,
                ota_price=ota_price,
                direct_price=direct_price,
                savings_amount=None,
                savings_percent=None,
                verdict="unknown",
            )

        comparisons.append(comparison)

    # Sort: available + cheaper first, then available + unknown, then unavailable
    def _sort_key(c: HotelComparison) -> tuple[int, int, float]:
        avail = c.call_result.availability
        if avail is True:
            avail_rank = 0
        elif avail is None:
            avail_rank = 1
        else:
            avail_rank = 2

        verdict_rank = {"cheaper": 0, "same": 1, "unknown": 2, "more_expensive": 3}
        v_rank = verdict_rank.get(c.verdict, 4)

        # Higher savings percent sorts first (negate for ascending sort)
        savings = -(c.savings_percent or 0.0)

        return (avail_rank, v_rank, savings)

    comparisons.sort(key=_sort_key)

    # Compute average savings for logging
    savings_values = [c.savings_percent for c in comparisons if c.savings_percent is not None]
    avg_savings = round(sum(savings_values) / len(savings_values), 1) if savings_values else None

    logger.info(
        "price_comparison | results_processed=%d valid_comparisons=%d best_savings=%s avg_savings=%s",
        len(call_results),
        valid_count,
        f"{best_savings}%" if best_savings is not None else "N/A",
        f"{avg_savings}%" if avg_savings is not None else "N/A",
    )

    return comparisons
