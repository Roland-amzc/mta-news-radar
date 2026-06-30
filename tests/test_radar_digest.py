"""Tests for radar.digest: service / cache / factory with an injected fake."""

from __future__ import annotations

import json

from radar.digest import DigestConfig, build_digester
from radar.digest.base import DigestOutput, DigestRequest, parse_digest_json
from radar.digest.cache import DigestCache
from radar.digest.noop import NoopDigester
from radar.digest.openai_compat import OpenAICompatibleDigester
from radar.digest.service import DigestService
from radar.models import Item, TopicResult, TopicSpec


class FakeDigester:
    """Returns canned Chinese output; can skip ids to simulate per-item failure."""

    def __init__(self, skip_ids=()):
        self.skip = set(skip_ids)
        self.calls = 0
        self.batches = 0

    def digest(self, requests):
        self.batches += 1
        self.calls += len(requests)
        return {
            r.id: DigestOutput(f"中文标题-{r.title}", f"中文摘要-{r.title}")
            for r in requests
            if r.id not in self.skip
        }


def _item(i):
    return Item(id=f"id{i}", title=f"t{i}", url=f"u/{i}", source_name="s",
                tier="media", topic_id="t", summary=f"s{i}")


def _result(n):
    return TopicResult(topic_id="t", name="T", mode="topic", window_hours=72,
                       generated_at="2026-06-30T00:00:00+00:00",
                       items=[_item(i) for i in range(n)], source_health=[], stats={})


def _topic():
    return TopicSpec(id="t", name="T", mode="topic", window_hours=72, scorer="keyword", sources=[])


def test_backfills_top_n_only(tmp_path):
    cache = DigestCache(tmp_path / "c.json")
    svc = DigestService(FakeDigester(), cache, DigestConfig(top_n=3))
    result = _result(5)
    svc.process(result, _topic())
    assert all(result.items[i].title_zh and result.items[i].summary_zh for i in range(3))
    assert result.items[3].title_zh is None and result.items[4].title_zh is None
    assert result.stats["digest_targets"] == 3
    assert result.stats["llm_calls"] == 3


def test_cache_hit_no_llm_second_run(tmp_path):
    cache = DigestCache(tmp_path / "c.json")
    fake = FakeDigester()
    svc = DigestService(fake, cache, DigestConfig(top_n=3))
    svc.process(_result(3), _topic())
    assert fake.calls == 3
    # second run on same ids -> all cached
    result2 = _result(3)
    svc.process(result2, _topic())
    assert result2.stats["from_cache"] == 3
    assert result2.stats["llm_calls"] == 0
    assert result2.items[0].title_zh == "中文标题-t0"


def test_budget_cap(tmp_path):
    cache = DigestCache(tmp_path / "c.json")
    svc = DigestService(FakeDigester(), cache, DigestConfig(top_n=5, max_items_per_run=2))
    result = _result(5)
    svc.process(result, _topic())
    assert result.stats["llm_calls"] == 2
    digested = [it for it in result.items if it.title_zh]
    assert len(digested) == 2


def test_noop_no_zh(tmp_path):
    cache = DigestCache(tmp_path / "c.json")
    svc = DigestService(NoopDigester(), cache, DigestConfig(top_n=3))
    result = _result(3)
    svc.process(result, _topic())
    assert all(it.title_zh is None for it in result.items)
    assert result.stats["llm_calls"] == 0


def test_partial_failure(tmp_path):
    cache = DigestCache(tmp_path / "c.json")
    svc = DigestService(FakeDigester(skip_ids=["id1"]), cache, DigestConfig(top_n=3))
    result = _result(3)
    svc.process(result, _topic())
    assert result.items[0].title_zh and result.items[2].title_zh
    assert result.items[1].title_zh is None  # id1 failed -> left empty


def test_cache_roundtrip(tmp_path):
    path = tmp_path / "c.json"
    cache = DigestCache(path)
    cache.put("id0", DigestOutput("标题", "摘要"))
    cache.save()
    reloaded = DigestCache(path).load()
    got = reloaded.get("id0")
    assert got is not None and got.title_zh == "标题" and got.summary_zh == "摘要"


def test_factory_no_key_returns_noop(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    digester = build_digester(DigestConfig())
    assert isinstance(digester, NoopDigester)


def test_factory_disabled_returns_noop(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("DIGEST_ENABLED", "0")
    assert isinstance(build_digester(DigestConfig()), NoopDigester)


# ---- shared JSON parser ----

def test_parse_digest_json_variants():
    assert parse_digest_json('{"title_zh":"标题","summary_zh":"摘要"}') == DigestOutput("标题", "摘要")
    # code fence + prose around it
    fenced = '这是结果:\n```json\n{"title_zh":"甲","summary_zh":"乙"}\n```'
    assert parse_digest_json(fenced) == DigestOutput("甲", "乙")
    assert parse_digest_json("not json at all") is None
    assert parse_digest_json('{"title_zh":"","summary_zh":"x"}') is None  # empty field
    assert parse_digest_json(None) is None


# ---- OpenAI-compatible digester (injected fake client) ----

class _Msg:
    def __init__(self, content): self.content = content

class _Choice:
    def __init__(self, content): self.message = _Msg(content)

class _Resp:
    def __init__(self, content): self.choices = [_Choice(content)]

class _Completions:
    def __init__(self, fn): self._fn = fn
    def create(self, **kw): return self._fn(**kw)

class FakeOpenAIClient:
    """Mimics openai client.chat.completions.create."""
    def __init__(self, fn): self.chat = type("C", (), {"completions": _Completions(fn)})()


def test_openai_compatible_digester():
    def reply(model, messages, **kw):
        title = messages[-1]["content"].split("\n")[0]
        return _Resp(json.dumps({"title_zh": "中文-" + title, "summary_zh": "摘要-" + title}))
    d = OpenAICompatibleDigester(DigestConfig(), api_key="x", base_url="x", model="m",
                                 client=FakeOpenAIClient(reply))
    out = d.digest([DigestRequest("id0", "Hello", "body"), DigestRequest("id1", "World", None)])
    assert out["id0"].title_zh == "中文-Hello" and out["id1"].summary_zh == "摘要-World"


def test_openai_compatible_malformed_skipped():
    d = OpenAICompatibleDigester(DigestConfig(), api_key="x", base_url="x", model="m",
                                 client=FakeOpenAIClient(lambda **kw: _Resp("garbage, no json")))
    assert d.digest([DigestRequest("id0", "Hi", None)]) == {}


def test_factory_openai_compatible(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("DIGEST_ENABLED", raising=False)
    monkeypatch.setenv("DIGEST_API_KEY", "k")
    monkeypatch.setenv("DIGEST_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DIGEST_MODEL", "deepseek-chat")
    assert isinstance(build_digester(DigestConfig()), OpenAICompatibleDigester)
