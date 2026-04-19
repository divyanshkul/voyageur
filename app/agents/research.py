"""Research Agent -- integration layer (Phase 2-int).

Supports two modes:
1. FACILE mode (default when SERPAPI_API_KEY is set): runs the full facile
   pipeline (planner -> critique -> SerpAPI hotel discovery -> top 5)
2. MOCK mode (fallback): uses mock Places + SerpAPI clients with local ranking

The output is always a list[Hotel] that the downstream approval/calling/report
pipeline consumes unchanged.
"""

import asyncio
import logging
import os
import time

from app.models import Hotel, TravelPreferences
from app.services.places import GooglePlacesClient
from app.services.serpapi import SerpAPIClient
from app.agents.research_brain import (
    format_shortlist_for_approval,
    generate_search_queries,
    should_broaden_search,
)
from app.agents.research_ranker import rank_hotels

logger = logging.getLogger(__name__)


class ResearchAgent:
    """Orchestrates hotel search -- either via facile pipeline or mock."""

    def __init__(
        self,
        places_client: GooglePlacesClient,
        serpapi_client: SerpAPIClient,
        openai_client,
        *,
        openai_api_key: str = "",
        serpapi_api_key: str = "",
    ) -> None:
        self._places = places_client
        self._serpapi = serpapi_client
        self._openai = openai_client

        # Keys passed explicitly from config (not os.getenv which may miss dotenv)
        self._openai_key = openai_api_key or os.getenv("OPENAI_API_KEY", "")
        self._serpapi_key = serpapi_api_key or os.getenv("SERPAPI_API_KEY", "")
        self._has_serpapi = bool(self._serpapi_key and self._serpapi_key != "your-serpapi-api-key")

        # Facile planner+critique runs whenever we have OpenAI (always).
        # Phase 1 hotel discovery uses real SerpAPI if key is set, else facile MockSerpApiClient.
        self._use_facile = bool(self._openai_key)
        self._last_facile_result = None

        if self._use_facile:
            mode = "SerpAPI live" if self._has_serpapi else "mock hotels (no SerpAPI key)"
            logger.info("ResearchAgent using FACILE pipeline (planner+critique+%s)", mode)
        else:
            logger.info("ResearchAgent using MOCK pipeline (no OpenAI key)")

    async def run(self, prefs: TravelPreferences) -> list[Hotel]:
        """Execute the research pipeline. Returns ranked hotel list."""
        if self._use_facile:
            return await self._run_facile(prefs)
        return await self._run_mock(prefs)

    async def _run_facile(self, prefs: TravelPreferences) -> list[Hotel]:
        """Run the full facile pipeline: planner -> critique -> SerpAPI discovery."""
        from app.services.facile_adapter import run_facile_pipeline

        t0 = time.perf_counter()
        logger.info("ResearchAgent.run_facile starting dest=%s", prefs.destination)

        try:
            result = await run_facile_pipeline(
                prefs,
                openai_api_key=self._openai_key,
                serpapi_key=self._serpapi_key if self._has_serpapi else None,
            )

            # Store the full pipeline result for itinerary display
            self._last_facile_result = result

            elapsed = time.perf_counter() - t0
            logger.info(
                "ResearchAgent.run_facile done hotels=%d elapsed=%.1fs",
                len(result.hotels), elapsed,
            )

            if not result.hotels:
                logger.warning("Facile returned 0 hotels, falling back to mock")
                return await self._run_mock(prefs)

            return result.hotels

        except Exception:
            logger.exception("Facile pipeline failed, falling back to mock")
            return await self._run_mock(prefs)

    async def _run_mock(self, prefs: TravelPreferences) -> list[Hotel]:
        """Fallback: run the mock pipeline (original Phase 2 behavior)."""
        t0 = time.perf_counter()

        # 1. Generate search queries via LLM
        queries = await generate_search_queries(prefs, self._openai)
        logger.info("ResearchAgent.run_mock | queries=%s", queries)

        # 2. Run hotel search + OTA pricing in parallel
        search_coros = [self._places.search_hotels(q) for q in queries]
        pricing_coro = self._serpapi.get_ota_prices(
            prefs.destination, prefs.check_in, prefs.check_out,
        )

        gather_results = await asyncio.gather(*search_coros, pricing_coro)

        hotel_lists: list[list[Hotel]] = list(gather_results[:-1])
        ota_prices: dict[str, int] = gather_results[-1]

        # 3. Flatten and deduplicate
        seen_ids: set[str] = set()
        all_hotels: list[Hotel] = []
        for hotel_list in hotel_lists:
            for h in hotel_list:
                if h.place_id not in seen_ids:
                    seen_ids.add(h.place_id)
                    all_hotels.append(h)

        logger.info(
            "ResearchAgent.run_mock | total_raw=%d | deduplicated=%d",
            sum(len(hl) for hl in hotel_lists), len(all_hotels),
        )

        # 4. Rank
        ranked = rank_hotels(all_hotels, prefs, ota_prices)

        # 5. Broaden if needed
        broaden, broader_query = should_broaden_search(ranked, prefs)
        if broaden and broader_query:
            extra = await self._places.search_hotels(broader_query)
            for h in extra:
                if h.place_id not in seen_ids:
                    seen_ids.add(h.place_id)
                    all_hotels.append(h)
            ranked = rank_hotels(all_hotels, prefs, ota_prices)

        elapsed = time.perf_counter() - t0
        logger.info(
            "ResearchAgent.run_mock | time=%.2fs | hotels=%d",
            elapsed, len(ranked),
        )
        return ranked

    def format_for_approval(self, hotels: list[Hotel]) -> str:
        """Format the ranked shortlist for user approval."""
        return format_shortlist_for_approval(hotels)

    def get_itinerary_message(self) -> str | None:
        """Return a formatted itinerary message if facile pipeline was used."""
        if self._last_facile_result:
            return self._last_facile_result.format_itinerary_message()
        return None

    def get_facile_result(self):
        """Return the raw FacilePipelineResult if available."""
        return self._last_facile_result
