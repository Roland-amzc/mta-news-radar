# MTA News Radar 引擎深度重构 Plan

> 基于已批准的 `spec.md`。范围:仅引擎核心。语言:Python(沿用仓库现有栈)。

## 架构概览

新引擎是独立包 `radar/`,八个组件,依赖严格由外指向内(编排依赖接口,不依赖具体实现):

| 组件 | 职责(一句话) |
|---|---|
| **config** | 读取并校验 `topics.yaml` → `TopicSpec / SourceSpec`;非法配置立即报错(F1)。 |
| **models** | 全系统统一契约数据结构:`Item / SourceSpec / TopicSpec / SourceHealth / TopicResult`。 |
| **fetchers**(抓取层,可插拔) | `类型→抓取器`注册表。`FeedFetcher` 覆盖 `rss/podcast/youtube/arxiv`,`ArxivAuthorFetcher` 按作者 ID 锚定。统一输出 `Item[] + SourceHealth`(F3/F7/F11)。 |
| **scorers**(打分层,可插拔) | `名称→策略`注册表。`KeywordScorer`、`NoneScorer` 实做,`LlmScorer` 留桩(F5)。 |
| **pipeline** | 单主题管线:`fetch→prefilter→window→dedup→score→rank/gate` → `TopicResult`(F2/F4/F6/F8)。 |
| **dedup** | 主题内按链接/标题归一去重,保留高 tier 来源(F9)。 |
| **writer** | `TopicResult` → `data/<topic>/latest.json` + 顶层 `data/index.json`(F10)。 |
| **runner + CLI** | 顶层编排:加载配置 → 按主题循环调 pipeline(逐主题隔离)→ writer(F2/F11)。 |

依赖方向:`runner → pipeline → {fetchers, scorers, dedup} → models`;`config → models`。新增主题改 yaml、新增源类型/策略加一个实现文件,均不碰 pipeline/runner(N2/N3)。

## 核心数据结构

### 统一数据结构(`radar/models.py`)

```python
@dataclass(frozen=True)
class SourceSpec:
    name: str
    type: str                       # rss | arxiv | arxiv_author | podcast | youtube
    tier: str                       # official | media | aggregator | self_media | entity
    url: str | None = None          # arxiv_author 可无 url(由 author_id 构造)
    sub_label: str | None = None
    prefilter: bool = False         # 是否对该源套用 topic.prefilter_keywords
    author_id: str | None = None    # arxiv_author 锚定用
    host: str | None = None         # 播客主持人(透传)
    enabled: bool = True
    status: str | None = None       # yaml 里 ok/verify/todo,仅元信息透传

@dataclass(frozen=True)
class TopicSpec:
    id: str
    name: str
    mode: str                       # topic | entity
    window_hours: float             # "72h"/"1w"/"2w" 解析为小时
    scorer: str                     # keyword | none | llm | keyword_prefilter+llm
    sources: list[SourceSpec]
    keywords: list[str] = field(default_factory=list)        # 主题相关性打分用(KeywordScorer)
    sub_labels: list[str] = field(default_factory=list)
    prefilter_keywords: list[str] = field(default_factory=list)  # 高频源粗筛用(与 keywords 分开)
    score_gate: float = 0.0         # topic 模式门禁阈值(默认 0 = 不过滤)

@dataclass
class Item:
    id: str                         # 稳定哈希(source_name+title+url)
    title: str
    url: str
    source_name: str
    tier: str
    topic_id: str
    summary: str | None = None      # feed 的 summary/description,打分用 title+summary
    published: datetime | None = None
    sub_label: str | None = None
    score: float | None = None      # none/entity 策略留 None
    score_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

@dataclass
class SourceHealth:
    source_name: str
    type: str
    status: str                     # ok | failed | skipped
    fetched: int = 0                # 抓到条数(粗筛/窗过滤前)
    error: str | None = None        # failed 时的原因 / skipped 时的跳过原因

@dataclass
class TopicResult:
    topic_id: str
    name: str
    mode: str
    window_hours: float
    generated_at: str               # ISO8601 UTC
    items: list[Item]
    source_health: list[SourceHealth]
    stats: dict[str, int] = field(default_factory=dict)  # fetched_total/after_prefilter/after_window/after_dedup/final
    topic_error: str | None = None  # 主题级硬错时非空,items 为 []
```

### 可插拔接口

```python
# radar/fetchers/base.py
class Fetcher(Protocol):
    def fetch(self, source: SourceSpec, topic: TopicSpec,
              now: datetime) -> tuple[list[Item], SourceHealth]: ...

# radar/scorers/base.py
class Scorer(Protocol):
    def score(self, items: list[Item], topic: TopicSpec) -> list[Item]: ...
```

### 注册表

```python
# radar/fetchers/__init__.py
FETCHERS: dict[str, Fetcher] = {
    "rss": FeedFetcher(), "podcast": FeedFetcher(),
    "youtube": FeedFetcher(), "arxiv": FeedFetcher(),
    "arxiv_author": ArxivAuthorFetcher(),
}
def get_fetcher(source_type: str) -> Fetcher: ...   # 未知类型 → 报错(scrape/x_account 将来在此注册)

# radar/scorers/__init__.py
SCORERS: dict[str, Scorer] = {
    "keyword": KeywordScorer(), "none": NoneScorer(),
    "llm": LlmScorer(),                       # 桩,内部委托 KeywordScorer
    "keyword_prefilter+llm": LlmScorer(),     # 本次:prefilter 在 pipeline 做,打分走桩
}
def get_scorer(name: str) -> Scorer: ...

class ConfigError(Exception): ...             # config 校验失败抛出
```

## 模块设计

### radar/models.py
**职责:** 纯数据结构 + `ConfigError`,无业务逻辑。
**对外接口:** 上述数据类。
**依赖:** 标准库(dataclasses, datetime, typing)。

### radar/config.py
**职责:** 加载 + 校验 `topics.yaml`。
**对外接口:** `load_topics(path: Path) -> list[TopicSpec]`;内部 `parse_window(text: str) -> float`(`72h→72 / 1w→168 / 2w→336 / 3d→72`);常量 `DEFERRED_TYPES = {"scrape", "x_account"}`。
**校验规则(违反即 `ConfigError`):** `mode∈{topic,entity}`;`scorer∈SCORERS`;`source.type ∈ FETCHERS ∪ DEFERRED_TYPES`(否则视为拼错 → 报错);`window` 可解析;`entity` 模式 `scorer` 必须为 `none`。
**解析但跳过(不报错,留待 pipeline 标 `skipped`):** `type∈DEFERRED_TYPES` 的源、`enabled: false` 的源、`arxiv_author` 且 `author_id=="TODO"` 的源——仍构造 `SourceSpec`(`enabled` 反映可运行性),不在此处剔除。
**注:** 校验只对**可运行源**要求 `url`(`arxiv_author` 改要求有效 `author_id`);被跳过的源不校验 url/author_id。
**依赖:** `models`、PyYAML、`fetchers`/`scorers` 注册表键。

### radar/fetchers/
**职责:** 把一个源抓成统一 `Item[] + SourceHealth`;异常一律转 `SourceHealth(status="failed", error=...)`,不抛出(F11)。
- `base.py`:`Fetcher` 协议 + 共享 helper `entry_to_item`(feedparser entry → Item:`title/url/summary`(取 entry 的 summary/description),`published` 用 dateutil 解析为 UTC、失败 None)。
- `feed.py`:`FeedFetcher`——requests 带超时拉字节,**先 `raise_for_status()`**(403/404/超时 → `failed`,避免错误页被当成空 feed)→ feedparser 解析;若 `bozo` 且 0 条目 → `failed`,0 条目但解析正常 → `ok` 且 `fetched=0`。覆盖 `rss/podcast/youtube/arxiv`。
- `arxiv_author.py`:`ArxivAuthorFetcher`——由 `author_id` 构造 `http://arxiv.org/a/<author_id>.atom`,只含该 ID 论文(F7)。
**依赖:** `models, requests, feedparser, dateutil`。

### radar/scorers/
**职责:** 给 `items` 设 `score`。
- `keyword.py`:`KeywordScorer`——对 **`title + summary`** 统计 `topic.keywords`(为空时回退 `prefilter_keywords`)命中度,`score = 命中度 × 0.7 + tier 权重 × 0.3`,归一 [0,1];记 `score_reason`(命中词)。
- `none_.py`:`NoneScorer`——不打分,`score` 保持 None,原样返回。
- `llm.py`:`LlmScorer`——桩,内部委托 `KeywordScorer`,`TODO` 标注未来接 LLM,绝不发网络请求(AC5)。
**依赖:** `models`;tier 权重为模块常量。

### radar/dedup.py
**职责:** 主题内去重/合并。
**对外接口:** `dedupe(items: list[Item]) -> list[Item]`。按归一 URL(去 query/fragment)分组 + 标题相似度(difflib)合并近重复;每组保留 tier rank 最高、其次时间最新(F9)。
**依赖:** `models`、标准库(difflib, urllib)。

### radar/pipeline.py
**职责:** 跑单主题完整管线。
**对外接口:** `run_topic(topic: TopicSpec, now: datetime, *, max_feeds: int|None=None) -> TopicResult`。
**步骤:** ① 遍历源,**跳过** `type∈DEFERRED_TYPES` / `enabled=False` / `arxiv_author 且 author_id=="TODO"` 的源(记 `SourceHealth(status="skipped")`);可运行源逐源 `get_fetcher(type).fetch`(try/except 隔离,异常 → `status="failed"`)→ items+health(记 `fetched_total`);② prefilter(`src.prefilter=True` 的条目用 `topic.prefilter_keywords` 过滤,F8;记 `after_prefilter`);③ window(`published` 非空且早于 `now - window_hours` 丢弃,`published=None` 保留,F4;记 `after_window`);④ dedup(F9;记 `after_dedup`);⑤ score(`get_scorer(topic.scorer).score`,F5);⑥ rank/gate(`topic`→按 score 降序+丢 `score<score_gate`;`entity`→按 published 降序、None 殿后,F6;记 `final`);⑦ 组装 `TopicResult`(含 `stats`)。
**依赖:** `fetchers, scorers, dedup, models`。

### radar/writer.py
**职责:** 落盘。
**对外接口:** `write_topic(result, output_dir) -> Path`(`data/<topic_id>/latest.json`,序列化 items + source_health(含 status)+ stats + topic_error,datetime→ISO);`write_index(results, output_dir) -> Path`(`data/index.json`:id/name/mode/window/条目数/stats/生成时间/topic_error)。
**依赖:** `models, json, pathlib`。

### radar/runner.py + run_radar.py
**职责:** 顶层编排 + CLI。
**对外接口:** `run_all(config_path, output_dir, now, *, only, max_feeds) -> list[TopicResult]`;`run_radar.py` argparse:`--config`(默认 topics.yaml)/`--output-dir`(默认 data)/`--only <topic_id>`/`--max-feeds`/`--now <ISO>`(测试用)。按主题 try/except 隔离(F2):主题级硬错也构造 `TopicResult(items=[], topic_error=...)` 并 `write_topic` 落盘(保证「每主题产出」),再继续其余主题。`ConfigError → 非 0`。
**依赖:** `config, pipeline, writer`。

## 模块交互

```
run_radar.py (CLI)
└─ runner.run_all(config_path, output_dir, now, only, max_feeds)
   ├─ config.load_topics(config_path) ──► list[TopicSpec]      # 校验失败 → ConfigError → 非0退出
   ├─ for topic in topics (按 --only 过滤):
   │   └─ try:                                                 # ── 主题级隔离 (F2) ──
   │       result = pipeline.run_topic(topic, now, max_feeds)
   │         ├─ for src in topic.sources:
   │         │    if src.type in DEFERRED_TYPES or not src.enabled or (arxiv_author & author_id=="TODO"):
   │         │        health = SourceHealth(status="skipped", error="deferred/disabled")  # 不抓取
   │         │    else:
   │         │        try: items_s, health = fetchers.get_fetcher(src.type).fetch(src, topic, now)  # 源级隔离 (F11)
   │         │        except Exception as e: items_s, health = [], SourceHealth(status="failed", error=str(e))
   │         ├─ prefilter(items, topic.prefilter_keywords)     # 仅 src.prefilter=True (F8) → stats.after_prefilter
   │         ├─ window_filter(items, now, topic.window_hours)  # published 非空才过滤,None 保留 (F4) → after_window
   │         ├─ dedup.dedupe(items)                            # 留高 tier (F9) → after_dedup
   │         ├─ scorers.get_scorer(topic.scorer).score(items, topic)  # 打分用 keywords/title+summary (F5)
   │         └─ rank_and_gate(items, topic.mode, topic.score_gate)    # (F6) → stats.final
   │       writer.write_topic(result, output_dir)              # data/<topic_id>/latest.json (F10)
   │     except Exception as e:                                # 主题级硬错也落盘 (opt5)
   │       writer.write_topic(TopicResult(items=[], topic_error=str(e), ...), output_dir)
   ├─ writer.write_index(results, output_dir)                  # data/index.json
   └─ return results
   exit: ConfigError→2 ; 全部主题失败→1 ; 否则→0
```

**隔离边界:** 源级(pipeline 内,记 health 不抛)满足 F11/AC2;主题级(runner 内 try/except)满足 F2。正常的「源全失败/空主题」走非异常路径,返回 `items=[]` 的合法 `TopicResult`,满足 N8/AC11。

**数据流转:** `topics.yaml → TopicSpec[] → 每源 Item[]+SourceHealth → 粗筛/窗/去重/打分/排序 → TopicResult → data/<topic>/latest.json`;`TopicResult[] → data/index.json`。

## 文件组织

```
mta-news-radar/
├── topics.yaml                      # 已存在(注册表)
├── run_radar.py                     # 新建:CLI 入口
├── radar/                           # 新建:引擎包(旧 scripts/ 不动)
│   ├── __init__.py
│   ├── models.py                    # 数据结构 + ConfigError
│   ├── config.py                    # load_topics / parse_window / 校验
│   ├── pipeline.py                  # run_topic + prefilter/window_filter/rank_and_gate
│   ├── dedup.py                     # dedupe
│   ├── writer.py                    # write_topic / write_index
│   ├── runner.py                    # run_all
│   ├── fetchers/
│   │   ├── __init__.py              # FETCHERS 注册表 + get_fetcher
│   │   ├── base.py                  # Fetcher 协议
│   │   ├── feed.py                  # FeedFetcher(rss/podcast/youtube/arxiv)
│   │   └── arxiv_author.py          # ArxivAuthorFetcher
│   └── scorers/
│       ├── __init__.py              # SCORERS 注册表 + get_scorer
│       ├── base.py                  # Scorer 协议
│       ├── keyword.py               # KeywordScorer + tier 权重常量
│       ├── none_.py                 # NoneScorer
│       └── llm.py                   # LlmScorer(桩)
├── tests/
│   ├── fixtures/radar/              # 新建:样本 feed(rss/atom/arxiv).xml
│   ├── test_radar_config.py
│   ├── test_radar_fetchers.py
│   ├── test_radar_scorers.py
│   ├── test_radar_dedup.py
│   └── test_radar_pipeline.py
├── data/
│   ├── index.json                   # 新增产出:主题清单
│   ├── frontier/latest.json         # 新增产出:每主题一目录
│   └── …(旧 latest-24h.json 等不再更新)
└── requirements.txt                 # 修改:PyYAML 从 dev 提到 runtime
```

## 技术决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 改造形态 | 新建 `radar/` 包,旧 `update_news.py` 不动 | 已选「干净切断」;5672 行单体回归风险高;依赖反转(N3)要干净边界 |
| feed 解析 | feedparser(已在 requirements) | 统一吃 rss/atom/podcast/youtube/arxiv;省手写 XML 容错 |
| HTTP 抓取 | requests 带超时拉 bytes、**先 `raise_for_status()`** 再喂 feedparser | 否则 403/404 错误页会被当成「成功 0 条」误判健康;Nature/MIT/Endpoints 已知 403 风险 |
| topics.yaml 解析 | PyYAML,提到 runtime requirements | 运行时需加载,dev-only 不够 |
| 未实现源类型 | `scrape/x_account`/`enabled:false`/`author_id:TODO` → **解析但跳过**(`skipped`),仅未知类型才报错 | 让当前 topics.yaml 合法可加载(否则 13 个 todo 源会让 load 直接失败,与 checklist 冲突) |
| 源类型→抓取器 | 5 类型注册到 2 实现(Feed/ArxivAuthor) | rss/podcast/youtube/arxiv 都是 feed,DRY;仅 arxiv_author 需按 ID 构 atom URL |
| arxiv_author 锚定 | arXiv 作者 atom feed(`arxiv.org/a/<id>.atom`) | 作者 ID 唯一,从源头杜绝同名混淆(F7) |
| 打分=策略模式 | name→Scorer 注册表;keyword/none 实做,llm 桩委托 keyword | F5/N2;新增策略加一文件,不碰 pipeline |
| 打分关键词字段 | `keywords`(相关性打分)与 `prefilter_keywords`(高频源粗筛)**分开** | 多数主题原本无打分词会退化成只看 tier;分开后各主题可独立调相关性 |
| 打分输入 | `title + summary`(feed 摘要进 `Item`) | 仅标题对 arXiv/播客/新书筛选太弱 |
| keyword 打分公式 | `命中度×0.7 + tier×0.3`,归一 [0,1] | 简单可解释可测;非 AI 主题不依赖 AI 相关性 |
| 源健康/计数 | `SourceHealth.status: ok\|failed\|skipped`;阶段计数放主题级 `TopicResult.stats` | prefilter/window/dedup 在合并池上做,挂单源语义不对;主题级计数支撑 AC8/AC2/AC11 |
| 并发抓取 | 暂不做,顺序 + 逐源 try/except | YAGNI;隔离更易测;ThreadPool 留后续优化(接口不变) |
| 时间处理 | dateutil 解析 → 统一 UTC,无则 None | 多源格式杂;None 不参与窗过滤但保留(entity 全收) |
| 输出形态 | 每主题 `data/<id>/latest.json` + 顶层 `data/index.json` | F10;index 清单为将来前端预留,零成本 |
| 配置错误 | `ConfigError` 冒泡 → CLI 非 0 退出 | F1/AC1 明确失败,不静默 |
| 失败处理 | 源级记 `failed`/`skipped` 不抛;主题级 runner try/except **且写出 `items=[] + topic_error` 的产出** | F2/F11;保证「每主题都有产出文件」(opt5);正常空结果走非异常路径(N8) |
