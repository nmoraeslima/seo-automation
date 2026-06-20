from seo_automation.briefing import build_keyword_briefing
from seo_automation.windsor import SearchConsoleRow


def _row(query, clicks=0, impressions=0, ctr=0.0, position=0.0, page=""):
    return SearchConsoleRow(
        query=query, page=page, clicks=clicks, impressions=impressions,
        ctr=ctr, position=position,
    )


def test_build_briefing_uses_exact_match():
    rows = [
        _row("seo para iniciantes", clicks=10, impressions=100, position=4.0),
        _row("seo para iniciantes 2024", clicks=2, impressions=50, position=8.0),
        _row("trafego pago", clicks=5, impressions=20, position=2.0),
    ]
    b = build_keyword_briefing("seo para iniciantes", rows, llm=None)
    assert b.keyword == "seo para iniciantes"
    assert b.clicks == 10
    assert b.impressions == 100
    assert b.position == 4.0
    # query relacionada (compartilha tokens) deve aparecer
    assert "seo para iniciantes 2024" in b.related_queries
    # query nao relacionada nao deve aparecer
    assert "trafego pago" not in b.related_queries


def test_build_briefing_fallback_outline_without_llm():
    b = build_keyword_briefing("marketing digital", [], llm=None)
    assert b.title
    assert b.headings
    assert b.suggested_word_count > 0


def test_ctr_computed_from_clicks_and_impressions():
    rows = [_row("x palavra", clicks=25, impressions=100, position=3.0)]
    b = build_keyword_briefing("x palavra", rows, llm=None)
    assert b.ctr == 0.25
