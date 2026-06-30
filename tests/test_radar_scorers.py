"""Tests for radar.scorers: keyword / none / llm-stub."""

from __future__ import annotations

from radar.models import Item, TopicSpec
from radar.scorers import get_scorer
from radar.scorers.keyword import KeywordScorer
from radar.scorers.llm import LlmScorer


def _topic(scorer: str = "keyword", keywords=None) -> TopicSpec:
    return TopicSpec(id="t", name="t", mode="topic" if scorer != "none" else "entity",
                     window_hours=72, scorer=scorer, sources=[],
                     keywords=keywords if keywords is not None else ["agent", "LLM"])


def _item(title: str, tier: str = "media", summary: str | None = None) -> Item:
    return Item(id=title, title=title, url="u/" + title, source_name="s",
                tier=tier, topic_id="t", summary=summary)


def test_keyword_scores_hits_higher_than_misses():
    hit = _item("A new LLM agent framework")
    miss = _item("Cooking soup recipes")
    KeywordScorer().score([hit, miss], _topic())
    assert hit.score > miss.score
    assert "hits" in (hit.score_reason or "")


def test_keyword_uses_summary_text():
    item = _item("Untitled", summary="this discusses an agent system")
    KeywordScorer().score([item], _topic())
    assert item.score > 0


def test_keyword_higher_tier_scores_higher_when_keywords_equal():
    official = _item("agent LLM", tier="official")
    selfmed = _item("agent LLM", tier="self_media")
    KeywordScorer().score([official, selfmed], _topic())
    assert official.score > selfmed.score


def test_none_scorer_leaves_score_none():
    items = [_item("anything")]
    get_scorer("none").score(items, _topic(scorer="none", keywords=[]))
    assert items[0].score is None


def test_llm_stub_matches_keyword_output():
    items1 = [_item("agent LLM news"), _item("unrelated")]
    items2 = [_item("agent LLM news"), _item("unrelated")]
    KeywordScorer().score(items1, _topic())
    LlmScorer().score(items2, _topic())
    assert [i.score for i in items1] == [i.score for i in items2]


def test_keyword_fallback_to_tier_when_no_keywords():
    item = _item("anything", tier="official")
    KeywordScorer().score([item], _topic(keywords=[]))
    assert item.score is not None and "tier-only" in (item.score_reason or "")
