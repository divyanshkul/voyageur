"""Report formatter (Phase 4c).

Renders the Report into multiple output formats: full Markdown for Streamlit,
a short chat message for conversational output, and a structured JSON dict
for API consumers.
"""

import logging

from app.models import Report

logger = logging.getLogger(__name__)


def to_markdown(report: Report) -> str:
    """Render the full report as Markdown."""
    lines: list[str] = []

    lines.append(f"## Your Hotel Options in {report.preferences.destination}\n")

    # Top pick section
    if report.top_pick:
        hotel = report.top_pick.hotel
        lines.append(f"### Top Pick: {hotel.name} ({hotel.rating}*)\n")
        lines.append(f"{report.summary}\n")

    # Comparison table
    lines.append("| Hotel | OTA Price | Direct Price | You Save |")
    lines.append("|-------|-----------|-------------|----------|")

    for c in report.comparisons:
        ota = f"Rs.{c.ota_price:,}" if c.ota_price else "N/A"
        direct = f"Rs.{c.direct_price:,}" if c.direct_price else "N/A"
        savings = (
            f"{c.savings_percent}%"
            if c.savings_percent is not None and c.savings_percent > 0
            else "-"
        )
        lines.append(f"| {c.hotel.name} | {ota} | {direct} | {savings} |")

    # Details section
    lines.append("\n### Details\n")

    for i, c in enumerate(report.comparisons, 1):
        lines.append(f"**{i}. {c.hotel.name}** ({c.hotel.rating}*)")

        if c.direct_price is not None:
            lines.append(f"- Direct Rate: Rs.{c.direct_price:,}/night")
        else:
            lines.append("- Direct Rate: Not quoted")

        if c.ota_price is not None:
            lines.append(f"- OTA Rate: Rs.{c.ota_price:,}/night")
        else:
            lines.append("- OTA Rate: N/A")

        if c.savings_percent is not None:
            lines.append(f"- Savings: {c.savings_percent}%")
        else:
            lines.append("- Savings: N/A")

        avail = c.call_result.availability
        if avail is True:
            lines.append("- Availability: Yes")
        elif avail is False:
            lines.append("- Availability: No")
        else:
            lines.append("- Availability: Unknown")

        lines.append(
            f"- Cancellation: {c.call_result.cancellation_policy or 'Not discussed'}"
        )

        if c.call_result.promotions:
            lines.append(f"- Promotions: {c.call_result.promotions}")

        lines.append("")  # blank line between hotels

    # Average savings footer
    if report.average_savings_percent:
        lines.append("---")
        lines.append(
            f"*Average savings across hotels: {report.average_savings_percent}%*"
        )

    md = "\n".join(lines)

    logger.info("markdown_rendered | length=%d", len(md))

    return md


def to_chat_message(report: Report) -> str:
    """Short-form message suitable for chat responses."""
    if report.top_pick:
        hotel = report.top_pick.hotel
        direct = report.top_pick.direct_price
        savings = report.top_pick.savings_percent

        msg = f"I recommend **{hotel.name}** ({hotel.rating}*)"
        if direct is not None:
            msg += f" at Rs.{direct:,}/night."
        else:
            msg += "."

        if savings is not None and savings > 0:
            msg += f" That's {savings}% less than online platforms."

        msg += "\n\nWant me to share the hotel's number so you can book directly?"
    else:
        n = len(report.comparisons)
        msg = f"I called {n} hotels. Here's what I found:\n"
        for c in report.comparisons:
            hotel = c.hotel
            if c.direct_price is not None:
                msg += f"- **{hotel.name}**: Rs.{c.direct_price:,}/night"
            else:
                msg += f"- **{hotel.name}**: price not available"
            if c.call_result.availability is True:
                msg += " (available)"
            elif c.call_result.availability is False:
                msg += " (not available)"
            msg += "\n"

    logger.info("chat_message_rendered | length=%d", len(msg))

    return msg


def to_json(report: Report) -> dict:
    """Serialize the report to a JSON-compatible dict."""
    data = report.model_dump(mode="json")

    logger.info("json_serialization_complete")

    return data
