"""Assigns each item to one of a fixed set of category buckets."""

import logging

from core.llm import get_llm_response

logger = logging.getLogger(__name__)

BATCH_SIZE = 10
FALLBACK_CATEGORY = "Industry & Adoption"

CATEGORIES = [
    "New Models",
    "Tools & Products",
    "Industry & Adoption",
    "Research",
    "Safety & Policy",
]

CATEGORY_EMOJI = {
    "New Models": "🧠",
    "Tools & Products": "🛠️",
    "Industry & Adoption": "🏢",
    "Research": "🔬",
    "Safety & Policy": "🛡️",
}

PROMPT_TEMPLATE = """Assign each item below to exactly one of these categories:
{categories}

Items:
{items_block}

Return a JSON array, one object per item, in this exact shape:
[{{"id": "<id>", "category": "<one of the category names above, verbatim>"}}]"""


def _format_items_block(items: list[dict]) -> str:
    lines = []
    for item in items:
        snippet = (item.get("raw_content") or "")[:300]
        lines.append(f"id: {item['id']}\ntitle: {item['title']}\nsnippet: {snippet}\n")
    return "\n".join(lines)


def _chunks(items: list[dict], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def categorize_items(items: list[dict]) -> list[dict]:
    categories_by_id: dict[str, str] = {}

    for batch in _chunks(items, BATCH_SIZE):
        prompt = PROMPT_TEMPLATE.format(
            categories="\n".join(f"- {c}" for c in CATEGORIES),
            items_block=_format_items_block(batch),
        )
        result = get_llm_response(prompt, json_mode=True)

        if not isinstance(result, list):
            logger.error("Categorizer batch failed to parse, using fallback category for %d items", len(batch))
            continue

        for entry in result:
            if not isinstance(entry, dict) or "id" not in entry:
                continue
            category = entry.get("category", FALLBACK_CATEGORY)
            categories_by_id[entry["id"]] = category if category in CATEGORIES else FALLBACK_CATEGORY

    return [
        {**item, "category": categories_by_id.get(item["id"], FALLBACK_CATEGORY)}
        for item in items
    ]
