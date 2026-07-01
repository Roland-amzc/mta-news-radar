"""Tests for radar.scorers: keyword / none / llm (stub + real judging)."""

from __future__ import annotations

import json

from radar.models import Item, TopicSpec
from radar.scorers import SCORERS, get_scorer
from radar.scorers.keyword import KeywordScorer
from radar.scorers.llm import LlmScorer, RelevanceCache, parse_relevance_json


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


def test_keyword_prefilter_llm_scorer_resolves_to_keyword():
    # frontier's registered scorer name; must NOT trigger real LLM calls (ADR-009 scope decision)
    assert get_scorer("keyword_prefilter+llm") is SCORERS["keyword"]


# ---- LlmScorer: real judging (fake OpenAI-compatible client) ----


class _Msg:
    def __init__(self, content): self.content = content

class _Choice:
    def __init__(self, content): self.message = _Msg(content)

class _Resp:
    def __init__(self, content): self.choices = [_Choice(content)]

class _Completions:
    def __init__(self, fn): self._fn = fn
    def create(self, **kw): return self._fn(**kw)

class FakeClient:
    def __init__(self, fn): self.chat = type("C", (), {"completions": _Completions(fn)})()


def test_parse_relevance_json_valid():
    assert parse_relevance_json('{"score": 0.8, "reason": "on topic"}') == (0.8, "on topic")


def test_parse_relevance_json_rejects_out_of_range():
    assert parse_relevance_json('{"score": 1.5, "reason": "x"}') is None


def test_parse_relevance_json_rejects_garbage():
    assert parse_relevance_json("not json at all") is None


def test_llm_scorer_uses_client_judgment_over_keyword():
    client = FakeClient(lambda **kw: _Resp(json.dumps({"score": 0.9, "reason": "clearly on topic"})))
    scorer = LlmScorer(client=client, model="m")
    item = _item("unrelated cooking content")  # would score low on keywords
    scorer.score([item], _topic())
    assert item.score == 0.9
    assert item.score_reason == "clearly on topic"


def test_llm_scorer_falls_back_to_keyword_on_parse_failure():
    client = FakeClient(lambda **kw: _Resp("not valid json"))
    scorer = LlmScorer(client=client, model="m")
    item = _item("agent LLM news")
    keyword_only = _item("agent LLM news")
    KeywordScorer().score([keyword_only], _topic())
    scorer.score([item], _topic())
    assert item.score == keyword_only.score  # kept the keyword baseline


def test_llm_scorer_respects_budget_across_items():
    client = FakeClient(lambda **kw: _Resp(json.dumps({"score": 0.7, "reason": "judged"})))
    scorer = LlmScorer(client=client, model="m", budget=1)
    a, b = _item("a"), _item("b")
    scorer.score([a, b], _topic())
    judged = [i for i in (a, b) if i.score == 0.7]
    assert len(judged) == 1  # only one item consumed the budget of 1


def test_llm_scorer_uses_cache_and_skips_client_call():
    calls = []
    client = FakeClient(lambda **kw: (calls.append(1), _Resp(json.dumps({"score": 0.5, "reason": "x"})))[1])
    cache = RelevanceCache(path=__file__ + ".unused")  # never touches disk in this test
    cache.put("cached-item", 0.42, "from cache")
    scorer = LlmScorer(client=client, model="m", cache=cache)
    item = Item(id="cached-item", title="anything", url="u", source_name="s", tier="media", topic_id="t")
    scorer.score([item], _topic())
    assert item.score == 0.42 and item.score_reason == "from cache"
    assert calls == []  # cache hit -> no LLM call


def test_relevance_cache_round_trip(tmp_path):
    path = tmp_path / "relevance-cache.json"
    cache = RelevanceCache(path)
    cache.put("x", 0.6, "reason x")
    cache.save()
    reloaded = RelevanceCache(path).load()
    assert reloaded.get("x") == (0.6, "reason x")
