# MTA News Radar 内容加工层 Plan

> 基于已批准的 digest-spec.md。语言:Python(沿用 radar/ 包栈)。LLM:Claude Haiku 4.5。

## 架构概览

新增 `radar/digest/` 包,八个职责块,依赖单向(runner → service → {digester, cache} → models):

| 组件 | 职责 |
|---|---|
| **models 扩展** | `Item` 增 `title_zh`/`summary_zh`;`TopicResult.stats` 增 `digest_targets`/`from_cache`/`llm_calls`。 |
| **digest/base** | `Digester` 协议 + `DigestRequest`/`DigestOutput` 数据结构。 |
| **digest/claude** | `ClaudeDigester`:Haiku 4.5,有限并发逐条调用,structured output。 |
| **digest/noop** | `NoopDigester`:返回空(无 key / 降级)。 |
| **digest/cache** | `DigestCache`:`id→{title_zh,summary_zh}` JSON 持久化。 |
| **digest/service** | `DigestService`:选 top-N → 查缓存 → 调 digester(预算闸)→ 回填 → 记 stats。 |
| **digest/__init__** | `build_digester(config)` 工厂:有 `ANTHROPIC_API_KEY` 且启用 → Claude,否则 Noop。 |
| **runner 集成** | `run_all` 建 service;每主题 `run_topic` 后 `process`;末尾存缓存。 |

## 核心数据结构

### models 扩展(`radar/models.py`)
```python
@dataclass
class Item:
    ...
    title_zh: str | None = None     # LLM 中文标题(英文则翻译)
    summary_zh: str | None = None   # LLM 2-3 句中文摘要
```
`TopicResult.stats` 追加键:`digest_targets`(top-N 目标数)、`from_cache`(命中缓存数)、`llm_calls`(实际调 LLM 数)。

### 加工接口与数据(`radar/digest/base.py`)
```python
@dataclass(frozen=True)
class DigestRequest:
    id: str
    title: str
    summary: str | None

@dataclass(frozen=True)
class DigestOutput:
    title_zh: str
    summary_zh: str

@dataclass(frozen=True)
class DigestConfig:
    top_n: int = 24            # 每主题加工前 N 条
    max_items_per_run: int = 200  # 单次运行新加工上限(预算闸)
    model: str = "claude-haiku-4-5"
    max_concurrency: int = 6

class Digester(Protocol):
    # 返回 id->DigestOutput;缺失的 id = 该条加工失败,跳过
    def digest(self, requests: list[DigestRequest]) -> dict[str, DigestOutput]: ...
```

## 模块设计

### radar/digest/base.py
**职责:** `Digester` 协议 + 数据结构 + `DigestConfig`。**依赖:** 标准库。

### radar/digest/claude.py
**职责:** 调 Claude Haiku 4.5 把一批条目加工成中文要点。
**对外接口:** `ClaudeDigester(config, client=None)`;`digest(requests) -> dict[id, DigestOutput]`。
**实现:** 每条一次 `client.messages.create`(并发 `ThreadPoolExecutor`,上限 `max_concurrency`);system 指示"中文标题≤30字 + 2-3 句中文摘要,忠实不编造,英文则翻译";`output_config={"format":{"type":"json_schema","schema":{title_zh,summary_zh}}}` 保证结构化;解析失败/异常 → 跳过该 id(不抛)。**绝不发请求时无 key**(由工厂保证)。
**依赖:** `anthropic` SDK、`base`、`concurrent.futures`。

### radar/digest/noop.py
**职责:** `NoopDigester.digest` 返回 `{}`(无 key / 禁用 / 降级)。**依赖:** `base`。

### radar/digest/cache.py
**职责:** 跨运行持久化加工结果。
**对外接口:** `DigestCache(path)`;`get(id) -> DigestOutput|None`;`put(id, output)`;`load()`;`save()`。文件 `data/digest-cache.json`(`{id: {title_zh, summary_zh}}`)。**依赖:** `json`、`base`。

### radar/digest/service.py
**职责:** 编排单主题加工。
**对外接口:** `DigestService(digester, cache, config)`;`process(result: TopicResult, topic: TopicSpec) -> None`(原地回填);`budget_left() -> int`(跨主题共享单次上限)。
**步骤:** ① `targets = result.items[:config.top_n]`;② 命中缓存的直接回填、计 `from_cache`;③ 未缓存的取前 `budget_left` 条 → `digester.digest` → 写缓存、回填、计 `llm_calls`、扣预算;④ 写 `result.stats`(digest_targets/from_cache/llm_calls)。**依赖:** `base`、`cache`、`models`。

### radar/digest/__init__.py
**职责:** `build_digester(config) -> Digester`:`os.environ.get("ANTHROPIC_API_KEY")` 存在且 `DIGEST_ENABLED!=0` → `ClaudeDigester`,否则 `NoopDigester`(打印一行降级提示)。**依赖:** `claude`、`noop`、`base`。

### radar/runner.py(修改)
`run_all` 开头:`cache=DigestCache(output_dir/"digest-cache.json").load()`;`service=DigestService(build_digester(cfg), cache, cfg)`。每主题:`result=run_topic(...)` → `service.process(result, topic)` → `write_topic(result)`。循环末:`cache.save()`。降级/无 key 时 service 用 Noop,行为=不加工。

## 模块交互

```
runner.run_all
 ├─ cache = DigestCache(...).load()
 ├─ service = DigestService(build_digester(cfg), cache, cfg)   # 无 key → Noop
 ├─ for topic:
 │    result = pipeline.run_topic(topic, now)
 │    service.process(result, topic):                          # 原地回填 zh
 │       targets = result.items[:top_n]
 │       hit = [t for t in targets if cache.get(t.id)]         # → from_cache
 │       miss = [t for t in targets if not cache.get(t.id)][:budget_left]
 │       outs = digester.digest([DigestRequest(t.id,t.title,t.summary) for t in miss])  # llm_calls
 │       for id,out in outs: cache.put(id,out)
 │       for t in targets: if cache.get(t.id): t.title_zh, t.summary_zh = cache值
 │       result.stats += {digest_targets,from_cache,llm_calls}
 │    writer.write_topic(result, output_dir)
 └─ cache.save()
```
降级:`build_digester` 无 key → Noop → `digest` 返回 `{}` → 无条目获 zh → 引擎照常产出(AC5)。单条解析失败 → 不在 outs 里 → 该条留空(AC6)。

## 文件组织
```
mta-news-radar/
├── radar/digest/
│   ├── __init__.py        # build_digester 工厂
│   ├── base.py            # Digester 协议 + 数据结构 + DigestConfig
│   ├── claude.py          # ClaudeDigester(Haiku 4.5)
│   ├── noop.py            # NoopDigester
│   ├── cache.py           # DigestCache
│   └── service.py         # DigestService
├── radar/models.py        # 修改:Item +title_zh/summary_zh
├── radar/runner.py        # 修改:集成 DigestService
├── tests/test_radar_digest.py   # 新建:FakeDigester 注入 + 缓存/预算/降级
├── requirements.txt       # 修改:加 anthropic
└── data/digest-cache.json # 产出(gitignore)
```

## 技术决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| model | `claude-haiku-4-5`($1/$5 per 1M) | 便宜、批量总结+翻译质量足够;200K 上下文绰绰有余 |
| 调用形态 | 同步 + 有限并发(逐条一次调用) | 即时、runner 不挂起轮询;Batch API(50%折扣/异步≤1h)留作放量后优化 |
| 结构化输出 | `output_config` json_schema `{title_zh,summary_zh}` | 保证可解析,不靠正则抠 JSON |
| 缓存 | `data/digest-cache.json`(gitignore),按 item id | 加工过不重复花钱(F3/N7);稳态增量成本≈只新条目 |
| 预算闸 | `max_items_per_run`(默认 200),跨主题共享 | 单次成本硬上限(F4/AC4) |
| 降级 | 无 `ANTHROPIC_API_KEY`/`DIGEST_ENABLED=0` → Noop;单条失败→留空 | F6/AC5/AC6;本地无 key 也能跑 |
| 密钥 | `ANTHROPIC_API_KEY` 走环境变量,不入库/不入日志 | N3 |
| 可测 | `Digester` 协议注入 `FakeDigester`,零网络 | N4/AC8 |
| 集成点 | runner 在 `run_topic` 后、`write_topic` 前 process | digest 只看最终 top-N;pipeline 保持纯净(依赖反转 N5) |
| 成本估算 | ~$0.0009/条全价;首轮 200 条 ≈ $0.18,稳态仅新条目 | 量级可接受;Batch API 可再砍半 |
