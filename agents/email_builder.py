"""Renders the categorized, summarized items into an Outlook-safe HTML email plus a
plain-text fallback, and persists the built email so 'send' mode can reuse the exact
email that was previewed."""

import json
import logging
from datetime import date

from jinja2 import Environment, FileSystemLoader

from agents.categorizer import CATEGORIES, CATEGORY_EMOJI
from core import config

logger = logging.getLogger(__name__)

TOP_PICKS_COUNT = 3
INTRO_LINE = "A few things worth knowing this week — here's what's happening in AI, in plain English."

_env = Environment(loader=FileSystemLoader(str(config.TEMPLATES_DIR)), autoescape=False)


def _group_by_category(items: list[dict]) -> list[dict]:
    grouped = []
    for category in CATEGORIES:
        category_items = [item for item in items if item.get("category") == category]
        if category_items:
            grouped.append({
                "name": category,
                "emoji": CATEGORY_EMOJI.get(category, ""),
                "entries": category_items,
            })
    return grouped


def build_email(items: list[dict]) -> dict:
    sorted_items = sorted(items, key=lambda i: i.get("score", 0), reverse=True)
    top_picks = sorted_items[:TOP_PICKS_COUNT]

    date_str = date.today().strftime("%B %d, %Y")
    context = {
        "date_str": date_str,
        "intro_line": INTRO_LINE,
        "top_picks": top_picks,
        "categories": _group_by_category(items),
        "accent_color": config.ACCENT_COLOR,
    }

    html = _env.get_template("email.html.j2").render(**context)
    text = _env.get_template("email.txt.j2").render(**context)

    email = {
        "subject": f"AI Weekly Digest — {date_str}",
        "html": html,
        "text": text,
    }

    config.LAST_DIGEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(config.LAST_DIGEST_PATH, "w") as f:
        json.dump({"email": email, "item_ids": [item["id"] for item in items]}, f, indent=2)

    logger.info("Built email with %d items across %d categories", len(items), len(context["categories"]))
    return email
