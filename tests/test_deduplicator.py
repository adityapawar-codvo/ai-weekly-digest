from agents.deduplicator import normalize_url, dedupe_within_week


def test_normalize_url_strips_utm_params():
    a = normalize_url("https://example.com/article?utm_source=x&utm_medium=y&id=42")
    b = normalize_url("https://example.com/article?id=42")
    assert a == b


def test_normalize_url_ignores_trailing_slash_and_case():
    a = normalize_url("https://Example.com/Article/")
    b = normalize_url("https://example.com/Article")
    assert a == b


def _item(id_, title, source, url):
    return {"id": id_, "title": title, "source": source, "url": url, "published": "", "raw_content": ""}


def test_dedupe_within_week_drops_exact_url_dupes():
    items = [
        _item("1", "GPT-6 released", "OpenAI", "https://a.com/x?utm_source=twitter"),
        _item("2", "GPT-6 released", "TechCrunch", "https://a.com/x"),
    ]
    result = dedupe_within_week(items)
    assert len(result) == 1
    assert result[0]["source"] == "OpenAI"  # more authoritative source kept


def test_dedupe_within_week_drops_fuzzy_title_dupes_keeping_authoritative():
    items = [
        _item("1", "OpenAI releases GPT-6, its new flagship model", "TechCrunch", "https://tc.com/a"),
        _item("2", "OpenAI releases GPT-6, a new flagship model", "OpenAI", "https://openai.com/b"),
    ]
    result = dedupe_within_week(items)
    assert len(result) == 1
    assert result[0]["source"] == "OpenAI"


def test_dedupe_within_week_keeps_distinct_items():
    items = [
        _item("1", "GPT-6 released", "OpenAI", "https://a.com/x"),
        _item("2", "New quantum chip announced", "Google AI", "https://b.com/y"),
    ]
    result = dedupe_within_week(items)
    assert len(result) == 2
