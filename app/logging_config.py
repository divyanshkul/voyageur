"""Structured logging setup for Voyageur.

Call setup_logging() once at app startup. All modules use logging.getLogger(__name__).
"""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Call once at app startup. All modules use logging.getLogger(__name__)."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper()))
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    # Avoid duplicate handlers on reload
    if not root.handlers:
        root.addHandler(handler)
    # Quiet noisy libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
