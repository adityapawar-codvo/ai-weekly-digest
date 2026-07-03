"""Produces a 2-3 sentence plain-language summary for each item, grounded strictly in
raw_content to prevent hallucination."""

import logging

from core.llm import get_llm_response

logger = logging.getLogger(__name__)

BATCH_SIZE = 5  # smaller than scorer/categorizer since summaries are longer output

PROMPT_TEMPLATE = """Write a 2-3 sentence plain-language summary for each AI news item \
below, for employees at a general, non-technical company (sales, HR, ops, finance, \
plus some engineers). Each summary must answer: what is it, and why might it matter to \
us? Avoid jargon (no "MoE", "context window", "RLHF", etc.) without a one-word plain \
explanation.

CRITICAL: base each summary strictly on the "content" text given for that item. Do not \
invent facts, numbers, or claims that aren't in the content.

Items:
{items_block}

Return a JSON array, one object per item, in this exact shape:
[{{"id": "<id>", "summary": "<2-3 plain sentences>"}}]"""


def _format_items_block(items: list[dict]) -> str:
    lines = []
    for item in items:
        content = (item.get("raw_content") or "")[:1500]
        lines.append(f"id: {item['id']}\ntitle: {item['title']}\ncontent: {content}\n")
    return "\n".join(lines)


def _chunks(items: list[dict], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def summarize_items(items: list[dict]) -> list[dict]:
    summaries_by_id: dict[str, str] = {}

    for batch in _chunks(items, BATCH_SIZE):
        prompt = PROMPT_TEMPLATE.format(items_block=_format_items_block(batch))
        result = get_llm_response(prompt, json_mode=True)

        if not isinstance(result, list):
            logger.error("Summarizer batch failed to parse, using fallback summary for %d items", len(batch))
            for item in batch:
                summaries_by_id[item["id"]] = item.get("raw_content", "")[:300]
            continue

        for entry in result:
            if not isinstance(entry, dict) or "id" not in entry:
                continue
            summaries_by_id[entry["id"]] = entry.get("summary", "")

    summarized = []
    for item in items:
        if item["id"] in summaries_by_id:
            summary = summaries_by_id[item["id"]]
        else:
            logger.warning("No summary for item %s (%s), using raw content", item["id"], item["title"])
            summary = item.get("raw_content", "")[:300]

        if summary:
            summarized.append({**item, "summary": summary})
        else:
            logger.warning("Empty summary for item %s (%s), using title as fallback", item["id"], item["title"])
            summarized.append({**item, "summary": item.get("title", "")})

    return summarized
