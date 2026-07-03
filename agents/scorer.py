"""Scores each item 1-10 for relevance to a general non-technical company, then
keeps roughly the top 10-15."""

import logging

from core.llm import get_llm_response

logger = logging.getLogger(__name__)

BATCH_SIZE = 10
KEEP_TOP_N = 12
DEFAULT_SCORE = 5

PROMPT_TEMPLATE = """You are helping filter AI news for a weekly email digest sent to \
employees at a general, non-technical company (sales, HR, ops, finance, plus some \
engineers). Rate each item below 1-10 for how important/relevant it is for that \
audience.

Reward: practical relevance, clarity, things that could affect how the company works \
or what tools it uses.
Penalize: dense academic research with no practical angle, incremental version bumps, \
pure hype with no substance.

Items:
{items_block}

Return a JSON array, one object per item, in this exact shape:
[{{"id": "<id>", "score": <integer 1-10>, "score_reason": "<one short sentence>"}}]"""


def _format_items_block(items: list[dict]) -> str:
    lines = []
    for item in items:
        snippet = (item.get("raw_content") or "")[:300]
        lines.append(f"id: {item['id']}\ntitle: {item['title']}\nsource: {item['source']}\nsnippet: {snippet}\n")
    return "\n".join(lines)


def _chunks(items: list[dict], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def score_items(items: list[dict]) -> list[dict]:
    scores_by_id: dict[str, dict] = {}

    for batch in _chunks(items, BATCH_SIZE):
        prompt = PROMPT_TEMPLATE.format(items_block=_format_items_block(batch))
        result = get_llm_response(prompt, json_mode=True)

        if not isinstance(result, list):
            logger.error("Scorer batch failed to parse, dropping %d items from scoring", len(batch))
            continue

        for entry in result:
            if not isinstance(entry, dict) or "id" not in entry:
                continue
            scores_by_id[entry["id"]] = {
                "score": entry.get("score", DEFAULT_SCORE),
                "score_reason": entry.get("score_reason", ""),
            }

    scored_items = []
    for item in items:
        if item["id"] in scores_by_id:
            scored_items.append({**item, **scores_by_id[item["id"]]})
        else:
            logger.warning("No score returned for item %s (%s), dropping", item["id"], item["title"])

    scored_items.sort(key=lambda i: i["score"], reverse=True)
    return scored_items[:KEEP_TOP_N]
