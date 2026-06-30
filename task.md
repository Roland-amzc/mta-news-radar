# MTA News Radar 引擎深度重构 Tasks

> 基于已批准的 `spec.md` + `plan.md`。按依赖顺序由内向外构建。
> 注:按用户要求,本文档**不含每任务验证方式**;验证统一见 `checklist.md`。

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `requirements.txt` | PyYAML 从 dev 提到 runtime |
| 新建 | `radar/__init__.py` | 包标识 |
| 新建 | `radar/models.py` | 数据结构 + ConfigError + make_item_id |
| 新建 | `radar/fetchers/base.py` | Fetcher 协议 |
| 新建 | `radar/fetchers/feed.py` | FeedFetcher(rss/podcast/youtube/arxiv) |
| 新建 | `radar/fetchers/arxiv_author.py` | ArxivAuthorFetcher |
| 新建 | `radar/fetchers/__init__.py` | FETCHERS 注册表 + get_fetcher |
| 新建 | `radar/scorers/base.py` | Scorer 协议 |
| 新建 | `radar/scorers/keyword.py` | KeywordScorer + tier 权重 |
| 新建 | `radar/scorers/none_.py` | NoneScorer |
| 新建 | `radar/scorers/llm.py` | LlmScorer(桩) |
| 新建 | `radar/scorers/__init__.py` | SCORERS 注册表 + get_scorer |
| 新建 | `radar/dedup.py` | dedupe |
| 新建 | `radar/config.py` | load_topics / parse_window / 校验 |
| 新建 | `radar/pipeline.py` | run_topic + prefilter/window_filter/rank_and_gate |
| 新建 | `radar/writer.py` | write_topic / write_index |
| 新建 | `radar/runner.py` | run_all |
| 新建 | `run_radar.py` | CLI 入口 |
| 新建 | `tests/fixtures/radar/*.xml` | 样本 feed(rss/atom/arxiv) |
| 新建 | `tests/test_radar_config.py` | 配置校验测试 |
| 新建 | `tests/test_radar_fetchers.py` | feed 解析测试 |
| 新建 | `tests/test_radar_scorers.py` | 打分策略测试 |
| 新建 | `tests/test_radar_dedup.py` | 去重测试 |
| 新建 | `tests/test_radar_pipeline.py` | 管线端到端测试 |

> **测试节奏(采纳 review opt4):** 每个模块任务完成即补对应 `tests/test_radar_<module>.py`,不要全堆到最后;T18 只留端到端 + 全量跑测。

---

## T0: 配置契约修正(部分已在文档阶段完成)
**文件:** `topics.yaml`(已改)、本组决策供 T13/T14 实现参照
**依赖:** 无
**说明:** 采纳 review 第 1/2/3/5 点,已落实到 `topics.yaml`:
1. 给 6 个打分主题补 `keywords`(与 `prefilter_keywords` 分开);`entity_radar` 不需要。
2. 顶部注明可运行类型 `rss/arxiv/arxiv_author/podcast/youtube`;`scrape/x_account/enabled:false/author_id:TODO` 源「解析但跳过」。
3. 姚顺宇 源 `enabled: false`(author_id 待补)。
4. 契约规则(供代码实现):`sub_label` 可空(配了才透传)、`published=None` 保留殿后、跳过源记 `status=skipped`。

## T1: 依赖与包骨架
**文件:** `requirements.txt`、`radar/__init__.py`、`radar/fetchers/__init__.py`(占位)、`radar/scorers/__init__.py`(占位)
**依赖:** 无
**步骤:**
1. 把 `PyYAML==6.0.2` 加入 `requirements.txt`(runtime)。
2. 新建 `radar/` 及 `radar/fetchers/`、`radar/scorers/` 目录,各放空 `__init__.py`(注册表内容后续任务填)。

## T2: models 数据结构
**文件:** `radar/models.py`
**依赖:** T1
**步骤:**
1. 定义 `SourceSpec / TopicSpec / Item / SourceHealth / TopicResult`(字段同 plan.md,**含新增**:`TopicSpec.keywords`、`Item.summary`、`SourceHealth.status(ok|failed|skipped)`、`TopicResult.stats` 与 `topic_error`)。
2. 定义 `ConfigError(Exception)`。
3. 写 `make_item_id(source_name, title, url) -> str`(稳定哈希,如 sha1 前 16 位)。

## T3: Fetcher 协议
**文件:** `radar/fetchers/base.py`
**依赖:** T2
**步骤:**
1. 用 `typing.Protocol` 定义 `Fetcher`,方法 `fetch(source, topic, now) -> tuple[list[Item], SourceHealth]`。
2. 抽出共享 helper `entry_to_item(entry, source, topic, now)`(feedparser entry → Item;`summary` 取 entry 的 `summary`/`description`;`published` 用 dateutil 解析为 UTC、失败 None)。

## T4: FeedFetcher
**文件:** `radar/fetchers/feed.py`
**依赖:** T2、T3
**步骤:**
1. `FeedFetcher.fetch`:用注入的 `requests.Session`(带超时常量)拉 `source.url` 字节,**`resp.raise_for_status()`**。
2. `feedparser.parse(bytes)` → 遍历 entries → `entry_to_item` → `Item[]`。
3. `bozo` 且 0 条目 → 视为失败;0 条目但解析正常 → `status="ok", fetched=0`。
4. 任何异常(含 HTTP 4xx/5xx)→ 返回 `([], SourceHealth(status="failed", error=str(e)))`;成功 → `SourceHealth(status="ok", fetched=len)`。

## T5: ArxivAuthorFetcher
**文件:** `radar/fetchers/arxiv_author.py`
**依赖:** T2、T3、T4
**步骤:**
1. 由 `source.author_id` 构造 `http://arxiv.org/a/<author_id>.atom`。
2. 复用 feed 解析逻辑(调用共享 helper / 内部委托 FeedFetcher)抓取并映射 Item。
3. 失败隔离同 T4。

## T6: FETCHERS 注册表
**文件:** `radar/fetchers/__init__.py`
**依赖:** T4、T5
**步骤:**
1. 实例化并注册:`rss/podcast/youtube/arxiv → FeedFetcher`,`arxiv_author → ArxivAuthorFetcher`。
2. `get_fetcher(source_type)`:未知类型 raise `ValueError`(供 config 校验捕获)。

## T7: Scorer 协议
**文件:** `radar/scorers/base.py`
**依赖:** T2
**步骤:** 用 `Protocol` 定义 `Scorer.score(items, topic) -> list[Item]`。

## T8: KeywordScorer
**文件:** `radar/scorers/keyword.py`
**依赖:** T2、T7
**步骤:**
1. 定义 `TIER_WEIGHT`(official>media>aggregator>self_media>entity,归一 [0,1])。
2. `score`:取 `kw = topic.keywords or topic.prefilter_keywords`;对每条 item,在 **`title + (summary or "")`** 上算 `kw` 命中度 ×0.7 + `TIER_WEIGHT[tier]`×0.3 → `item.score`,`score_reason` 记命中词。`kw` 为空时退化为仅 tier 权重。

## T9: NoneScorer
**文件:** `radar/scorers/none_.py`
**依赖:** T2、T7
**步骤:** `score`:不改 `item.score`(保持 None),原样返回。

## T10: LlmScorer(桩)
**文件:** `radar/scorers/llm.py`
**依赖:** T8
**步骤:** `score`:`return KeywordScorer().score(items, topic)`;类与方法加 `TODO: 未来接 LLM 精判` 注释;**不引入任何网络/SDK**。

## T11: SCORERS 注册表
**文件:** `radar/scorers/__init__.py`
**依赖:** T8、T9、T10
**步骤:**
1. 注册 `keyword→KeywordScorer`、`none→NoneScorer`、`llm→LlmScorer`、`keyword_prefilter+llm→LlmScorer`。
2. `get_scorer(name)`:未知 raise `ValueError`。

## T12: dedup
**文件:** `radar/dedup.py`
**依赖:** T2
**步骤:**
1. `normalize_url`(去 query/fragment、小写 host)。
2. `dedupe`:按归一 URL 分组;组内/跨组用 difflib 比标题相似度合并近重复;每组保留 tier rank 最高、其次 published 最新。

## T13: config 加载与校验
**文件:** `radar/config.py`
**依赖:** T2、T6、T11
**步骤:**
1. `parse_window(text)`:`Nh/Nd/Nw → 小时`(浮点)。常量 `DEFERRED_TYPES = {"scrape", "x_account"}`。
2. `load_topics(path)`:PyYAML 读 → 构造 `TopicSpec`(含 `keywords`)/`SourceSpec`(含 `enabled`)。
3. 校验(违反 raise `ConfigError`,带清晰信息):`mode∈{topic,entity}`;`scorer∈SCORERS`;`type ∈ FETCHERS ∪ DEFERRED_TYPES`(否则视为拼错→报错);`window` 可解析;`entity` 模式 `scorer` 必须 `none`。
4. **可运行源**(非 deferred、`enabled!=False`)才要求字段:`arxiv_author` 须有有效 `author_id`(非 `"TODO"`)、其余须有 `url`;deferred/禁用/`author_id:TODO` 的源**不校验、不剔除**,留到 pipeline 标 `skipped`。

## T14: pipeline
**文件:** `radar/pipeline.py`
**依赖:** T6、T11、T12、T2
**步骤:**
1. `run_topic`:遍历源——`type∈DEFERRED_TYPES` / `enabled=False` / `arxiv_author 且 author_id=="TODO"` → 记 `SourceHealth(status="skipped")`,**不抓取**;其余源 `get_fetcher(type).fetch`(逐源 try/except,异常→`status="failed"`,收 items+health)。记 `stats.fetched_total`。
2. `prefilter`:对 `src.prefilter=True` 来源的 items,`title+summary` 不含任一 `topic.prefilter_keywords` 则丢。记 `stats.after_prefilter`。
3. `window_filter`:`published` 非空且 `< now - window_hours` 丢;`published=None` 保留。记 `stats.after_window`。
4. `dedupe`(T12)。记 `stats.after_dedup`。
5. `get_scorer(topic.scorer).score`。
6. `rank_and_gate`:`topic`→按 score 降序、丢 `score<score_gate`;`entity`→按 published 降序(None 殿后)。记 `stats.final`。
7. 组装并返回 `TopicResult`(含 `source_health` 与 `stats`)。

## T15: writer
**文件:** `radar/writer.py`
**依赖:** T2
**步骤:**
1. `write_topic`:`TopicResult` → dict(含 items、`source_health`(带 status)、`stats`、`topic_error`)→ `data/<topic_id>/latest.json`(mkdir parents)。
2. `write_index`:汇总各 `TopicResult` 元信息(id/name/mode/window/条目数/stats/topic_error/生成时间)→ `data/index.json`。
3. datetime 序列化为 ISO 字符串。

## T16: runner
**文件:** `radar/runner.py`
**依赖:** T13、T14、T15
**步骤:**
1. `run_all`:`load_topics` → 按 `only` 过滤 → for topic:`try run_topic + write_topic`;`except` → 构造 `TopicResult(items=[], topic_error=str(e))` 并 `write_topic` 落盘(保证每主题都有产出),记失败后继续。
2. 末尾 `write_index`,返回 `results`。

## T17: CLI 入口
**文件:** `run_radar.py`
**依赖:** T16
**步骤:**
1. argparse:`--config`(默认 `topics.yaml`)、`--output-dir`(默认 `data`)、`--only`、`--max-feeds`、`--now`(ISO,测试用)。
2. 调 `run_all`;捕获 `ConfigError → 退出码 2`;全部主题失败 → `1`;否则 `0`。

## T18: 端到端测试与全量跑测
**文件:** `tests/fixtures/radar/*.xml`、`tests/test_radar_*.py`(各模块测试已随对应任务写好,此处补端到端 + 跑全量)
**依赖:** T2–T17
**步骤:**
1. 固定样本 feed(RSS、Atom、arXiv RSS)放 `tests/fixtures/radar/`。
2. `test_radar_config`:合法当前 topics.yaml → 7 主题且 deferred/禁用源记 skipped;未知 type / 缺必填 → `ConfigError`。
3. `test_radar_fetchers`:样本解析(注入假 session,不走网络);403/非 feed → `status="failed"`;summary 进 Item。
4. `test_radar_scorers`:keyword 用 `keywords` 对 title+summary 打分排序、none 不打分、llm 桩等价 keyword。
5. `test_radar_dedup`:同故事多源留高 tier。
6. `test_radar_pipeline`:mock fetcher 跑 `run_topic`,验跳过源/窗(含 published=None)/门禁/两种 mode/空主题/`stats` 计数。
7. `pytest tests/test_radar_*.py` 全量绿。

## 执行顺序

```
T0 → T1 → T2 ─┬→ T3 → T4 → T5 → T6 ─┐
              ├→ T7 → T8 → T10 ─┐    │
              │       T9 ───────┤    │
              │                 T11 ─┤
              ├→ T12 ────────────────┤
              │                      ├→ T13 → T14 → T16 → T17 → T18
              └→ T15 ────────────────┘
```
（T0 配置契约已在文档阶段落实到 topics.yaml;T2 之后 fetchers 链 / scorers 链 / dedup / writer 可并行推进,汇合于 config+pipeline。各模块测试随任务即写,T18 收尾端到端。）
