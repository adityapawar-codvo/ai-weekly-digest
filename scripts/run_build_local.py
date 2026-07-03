"""Runs the full 'build' pipeline against real RSS sources with the LLM stages
stubbed out (no API key needed), and writes the resulting HTML to data/preview.html
for visual inspection in a browser.

Usage: python scripts/run_build_local.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents import categorizer, collector, deduplicator, email_builder
from core import config


def fake_score(items):
    return [{**item, "score": 10 - i, "score_reason": "stubbed for local preview"} for i, item in enumerate(items)]


def fake_summarize(items):
    return [{**item, "summary": (item["raw_content"] or item["title"])[:220]} for item in items]


def main():
    items = collector.collect()
    print(f"Collected {len(items)} items")

    items = deduplicator.dedupe_within_week(items)
    items = deduplicator.dedupe_cross_week(items)
    print(f"{len(items)} items after dedupe")

    items = fake_score(items)[:12]
    items = categorizer.categorize_items(items)  # will fall back to default category without a real key
    items = fake_summarize(items)
    print(f"{len(items)} items after scoring/categorizing/summarizing (stubbed)")

    email = email_builder.build_email(items)

    preview_path = config.BASE_DIR / "data" / "preview.html"
    preview_path.write_text(email["html"])
    print(f"Wrote preview HTML to {preview_path}")


if __name__ == "__main__":
    main()
