"""Collects AI news from configured RSS/API sources into the canonical item shape."""

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from time import mktime

import feedparser
import requests

from core import config

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 7
HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub("", text or "")).strip()


def _make_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _to_utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _collect_rss(source: dict) -> list[dict]:
    items = []
    feed = feedparser.parse(source["url"])
    if getattr(feed, "bozo", False) and not feed.entries:
        raise ValueError(f"feedparser could not parse {source['url']}: {feed.bozo_exception}")

    for entry in feed.entries:
        url = entry.get("link", "")
        if not url:
            continue
        published_struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if published_struct:
            published_dt = datetime.fromtimestamp(mktime(published_struct), tz=timezone.utc)
        else:
            published_dt = datetime.now(timezone.utc)

        raw_content = _strip_html(entry.get("summary", "") or entry.get("title", ""))

        items.append({
            "id": _make_id(url),
            "title": entry.get("title", "").strip(),
            "source": source["name"],
            "url": url,
            "published": _to_utc_iso(published_dt),
            "raw_content": raw_content,
        })
    return items


def _collect_hn(source: dict) -> list[dict]:
    params = {"query": source.get("query", "AI"), "tags": "story"}
    resp = requests.get(HN_SEARCH_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    items = []
    for hit in data.get("hits", []):
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        title = hit.get("title", "")
        if not title:
            continue
        created_at = hit.get("created_at")
        published_dt = (
            datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if created_at else datetime.now(timezone.utc)
        )
        items.append({
            "id": _make_id(url),
            "title": title.strip(),
            "source": source["name"],
            "url": url,
            "published": _to_utc_iso(published_dt),
            "raw_content": title,
        })
    return items


def collect() -> list[dict]:
    """Reads config/sources.yaml, pulls items from each source, and returns a flat
    list of canonical-shape dicts filtered to the last LOOKBACK_DAYS days.

    A failing source is logged and skipped — never crashes the run.
    """
    sources = config.load_sources()
    all_items = []

    for source in sources:
        name = source.get("name", "unknown")
        try:
            if source["type"] == "rss":
                items = _collect_rss(source)
            elif source["type"] == "hn":
                items = _collect_hn(source)
            else:
                logger.warning("Unknown source type for %s: %s", name, source.get("type"))
                continue
            logger.info("Collected %d items from %s", len(items), name)
            all_items.extend(items)
        except Exception as exc:
            logger.error("Source %s failed, skipping: %s", name, exc)
            continue

    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    filtered = [
        item for item in all_items
        if datetime.strptime(item["published"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) >= cutoff
    ]
    logger.info("Collected %d items total, %d within last %d days", len(all_items), len(filtered), LOOKBACK_DAYS)
    return filtered
