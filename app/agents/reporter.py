"""Report Agent -- integration layer (Phase 4-int).

Wires the price comparison engine (4a), LLM report generator (4b), and
report formatter (4c) into a single ReportAgent that produces the final
OTA-vs-direct comparison report.
"""

import logging
import time

from app.agents.report_formatter import to_markdown
from app.agents.report_generator import generate_report
from app.agents.report_pricing import compare_prices
from app.models import CallResult, Report, TravelPreferences

logger = logging.getLogger(__name__)


class ReportAgent:
    """Orchestrates price comparison, LLM summary, and markdown formatting."""

    def __init__(self, openai_client):
        self._openai = openai_client

    async def run(
        self,
        call_results: list[CallResult],
        prefs: TravelPreferences,
    ) -> Report:
        """Generate the full report from call results and preferences.

        Pipeline:
          1. compare_prices  -- compute savings for each hotel
          2. generate_report -- LLM summary + Report assembly
          3. to_markdown     -- render the final markdown view
        """
        logger.info(
            "report_start | call_results=%d destination=%s",
            len(call_results),
            prefs.destination,
        )
        start_time = time.time()

        # Step 1: Price comparison
        comparisons = compare_prices(call_results)

        # Step 2: LLM report generation
        report = await generate_report(comparisons, prefs, self._openai)

        # Step 3: Markdown formatting
        report.markdown = to_markdown(report)

        elapsed = time.time() - start_time

        logger.info(
            "report_complete | top_pick=%s avg_savings=%s took=%.1fs",
            report.top_pick.hotel.name if report.top_pick else "none",
            f"{report.average_savings_percent}%"
            if report.average_savings_percent is not None
            else "N/A",
            elapsed,
        )

        return report
