"""Within-week (URL + fuzzy title) and cross-week (sent history) deduplication."""

import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from rapidfuzz import fuzz

from core import config

logger = logging.getLogger(__name__)

CROSS_WEEK_WINDOW_DAYS = 28
FUZZY_TITLE_THRESHOLD = 87

# Earlier entries are treated as more authoritative when two near-dupes must be merged.
SOURCE_AUTHORITY = ["OpenAI", "Anthropic", "Google AI", "Microsoft AI"]


def _authority_rank(source: str) -> int:
    return SOURCE_AUTHORITY.index(source) if source in SOURCE_AUTHORITY else len(SOURCE_AUTHORITY)


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_")]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def dedupe_within_week(items: list[dict]) -> list[dict]:
    """Drops exact URL duplicates, then fuzzy-matches titles and drops near-dupes,
    keeping the item from the most authoritative source."""
    seen_urls: dict[str, dict] = {}
    for item in items:
        norm_url = normalize_url(item["url"])
        if norm_url not in seen_urls:
            seen_urls[norm_url] = item
        elif _authority_rank(item["source"]) < _authority_rank(seen_urls[norm_url]["source"]):
            seen_urls[norm_url] = item

    deduped: list[dict] = []
    for candidate in seen_urls.values():
        match_idx = None
        for idx, kept in enumerate(deduped):
            if fuzz.token_sort_ratio(candidate["title"], kept["title"]) >= FUZZY_TITLE_THRESHOLD:
                match_idx = idx
                break
        if match_idx is None:
            deduped.append(candidate)
        elif _authority_rank(candidate["source"]) < _authority_rank(deduped[match_idx]["source"]):
            deduped[match_idx] = candidate

    return deduped


def _load_history() -> dict:
    if not config.SENT_HISTORY_PATH.exists():
        return {}
    with open(config.SENT_HISTORY_PATH, "r") as f:
        return json.load(f)


def _prune_history(history: dict) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=CROSS_WEEK_WINDOW_DAYS)
    return {
        item_id: sent_at for item_id, sent_at in history.items()
        if datetime.fromisoformat(sent_at.replace("Z", "+00:00")) >= cutoff
    }


def dedupe_cross_week(items: list[dict]) -> list[dict]:
    """Drops any item whose id was already sent within the rolling window."""
    history = _prune_history(_load_history())
    return [item for item in items if item["id"] not in history]


def record_sent(ids: list[str]) -> None:
    """Appends newly sent ids to sent_history.json after a successful send."""
    history = _prune_history(_load_history())
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for item_id in ids:
        history[item_id] = now_iso

    config.SENT_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(config.SENT_HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)
    logger.info("Recorded %d ids to sent_history.json", len(ids))
