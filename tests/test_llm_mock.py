"""Proves scorer/categorizer/summarizer handle both well-formed and malformed LLM
JSON output without raising or crashing the pipeline."""

from agents import categorizer, scorer, summarizer


def _item(id_, title="Some AI headline", raw_content="Some AI news content."):
    return {
        "id": id_, "title": title, "source": "OpenAI",
        "url": f"https://example.com/{id_}", "published": "", "raw_content": raw_content,
    }


def test_scorer_happy_path(monkeypatch):
    def fake_llm(prompt, json_mode=False):
        return [{"id": "1", "score": 8, "score_reason": "relevant"}, {"id": "2", "score": 3, "score_reason": "niche"}]

    monkeypatch.setattr(scorer, "get_llm_response", fake_llm)
    result = scorer.score_items([_item("1"), _item("2")])
    assert result[0]["id"] == "1"
    assert result[0]["score"] == 8


def test_scorer_drops_items_on_malformed_response(monkeypatch):
    monkeypatch.setattr(scorer, "get_llm_response", lambda prompt, json_mode=False: None)
    result = scorer.score_items([_item("1"), _item("2")])
    assert result == []


def test_categorizer_happy_path(monkeypatch):
    def fake_llm(prompt, json_mode=False):
        return [{"id": "1", "category": "New Models"}]

    monkeypatch.setattr(categorizer, "get_llm_response", fake_llm)
    result = categorizer.categorize_items([_item("1")])
    assert result[0]["category"] == "New Models"


def test_categorizer_falls_back_on_malformed_response(monkeypatch):
    monkeypatch.setattr(categorizer, "get_llm_response", lambda prompt, json_mode=False: "not json")
    result = categorizer.categorize_items([_item("1")])
    assert result[0]["category"] == categorizer.FALLBACK_CATEGORY


def test_summarizer_happy_path(monkeypatch):
    def fake_llm(prompt, json_mode=False):
        return [{"id": "1", "summary": "This is a plain-language summary."}]

    monkeypatch.setattr(summarizer, "get_llm_response", fake_llm)
    result = summarizer.summarize_items([_item("1")])
    assert result[0]["summary"] == "This is a plain-language summary."


def test_summarizer_drops_items_without_summary(monkeypatch):
    monkeypatch.setattr(summarizer, "get_llm_response", lambda prompt, json_mode=False: [{"id": "1"}])
    result = summarizer.summarize_items([_item("1")])
    assert result == []
