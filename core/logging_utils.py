"""Per-run logging and maintainer failure alerts."""

import logging
from datetime import datetime, timezone

from core import config

logger = logging.getLogger(__name__)


def setup_logging() -> str:
    """Configures root logging to stream to console + a per-run log file. Returns
    the log file path."""
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = config.LOGS_DIR / f"{timestamp}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
        force=True,
    )
    return str(log_path)


def log_stage(stage: str, count: int) -> None:
    logger.info("[stage] %s -> %d items", stage, count)
    print(f"::notice title=Digest {stage}::{count} items")


def alert_failure(exc: Exception) -> None:
    """Best-effort failure alert to the maintainer — must never itself crash the run."""
    logger.error("Run failed: %s", exc, exc_info=True)
    print(f"::error title=Digest run failed::{exc}")

    try:
        from agents import mailer

        alert_email = {
            "subject": "AI Weekly Digest — run failed",
            "html": f"<p>The AI Weekly Digest run failed with:</p><pre>{exc}</pre>",
            "text": f"The AI Weekly Digest run failed with:\n{exc}",
        }
        mailer.send(alert_email, [config.MAINTAINER_EMAIL], bcc=False)
    except Exception as alert_exc:
        logger.error("Failed to send failure alert email: %s", alert_exc)
